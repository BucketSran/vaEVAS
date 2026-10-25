//! Admission boundaries for compact event-only control IR.
use crate::ir::{Error, Program};
use serde_json::Value;

/// Internal borrowed metadata, produced only by the mandatory bounded pass.
/// It is neither wire state nor a substitute for source qualification.
#[derive(Debug)]
pub(crate) struct Admission<'a> {
    program: &'a Program,
    floor_events: Vec<bool>,
    source_floor: bool,
    pub(crate) targets: std::collections::BTreeSet<usize>,
    pub(crate) copy_items: usize,
    history_candidate: bool,
}
impl<'a> Admission<'a> {
    pub(crate) fn history_candidate(&self) -> bool {
        self.history_candidate
    }
    pub(crate) fn program(&self) -> &'a Program {
        self.program
    }
    pub(crate) fn source_floor(&self) -> bool {
        self.source_floor
    }
    pub(crate) fn floor_event(&self, event: usize) -> bool {
        self.floor_events[event]
    }
}
#[derive(Default, Clone, Copy)]
struct Summary {
    operand: bool,
    coefficient: bool,
    floor: bool,
    constant: Option<f64>,
    event_only: bool,
    round_pending: bool,
    round_invalid: bool,
}
fn binary_scale(v: f64) -> bool {
    let b = v.abs().to_bits();
    let e = b >> 52;
    let f = b & ((1_u64 << 52) - 1);
    v == 0. || v.is_finite() && if e == 0 { f.count_ones() == 1 } else { f == 0 }
}
// One private owner boundary for the final admission table. The mandatory
// None path uses the already bounded validation metadata without a source owner.
fn floor_metadata(
    value: &Value,
    summaries: &std::collections::HashMap<usize, Summary>,
    event_count: usize,
    work: Option<&crate::transition_source_plan::Work>,
) -> Result<(Vec<bool>, bool), Error> {
    // The existing Work uses logical visits/copies. Reserve before the root
    // lookup or any allocation. 32 fixed units cover setup and root lookup;
    // per event: 8 body-map lookup, 8 summary lookup/read, 8 allocation/write
    // and iterator work, 8 full second any-pass visit/read. Typed Event has
    // exactly body/trigger/origin. The mandatory pass already bounds all data.
    if let Some(w) = work {
        crate::event_floor::charge(w, 0, "floor_source_admission_metadata")?;
        crate::event_floor::charge(
            w,
            floor_metadata_cost(event_count),
            "floor_source_admission_metadata",
        )?;
    }
    #[cfg(test)]
    crate::diagnostics::counter("floor_metadata_root_lookup", 1);
    let floor_events = value
        .get("events")
        .and_then(Value::as_array)
        .map(|events| {
            #[cfg(test)]
            crate::diagnostics::counter("floor_metadata_allocate", 1);
            events
                .iter()
                .map(|e| {
                    #[cfg(test)]
                    crate::diagnostics::counter("floor_metadata_event_visit", 1);
                    e.get("body").is_some_and(|v| {
                        summaries
                            .get(&(v as *const Value as usize))
                            .is_some_and(|s| s.floor)
                    })
                })
                .collect::<Vec<_>>()
        })
        .unwrap_or_default();
    #[cfg(test)]
    crate::diagnostics::counter("floor_metadata_any_enter", 1);
    let source_floor = floor_events.iter().any(|v| {
        #[cfg(test)]
        crate::diagnostics::counter("floor_metadata_any_visit", 1);
        *v
    });
    Ok((floor_events, source_floor))
}
fn floor_metadata_cost(event_count: usize) -> usize {
    32usize.saturating_add(event_count.saturating_mul(32))
}

// Dispatch metadata only. Reuse the mandatory original Value and its existing
// 100000 structural allowance. The table stores node coordinates, never copied
// expressions or an expanded voltage graph. Insufficient metadata leaves the
// established route in charge; it does not grant admission or fresh work.
fn history_candidate(
    value: &Value,
    items: &mut usize,
    work: Option<&crate::transition_source_plan::Work>,
) -> Result<bool, Error> {
    struct Scan<'a> {
        items: &'a mut usize,
        work: Option<&'a crate::transition_source_plan::Work>,
        error: Option<Error>,
    }
    let mut scan = Scan {
        items,
        work,
        error: None,
    };
    fn candidate(value: &Value, scan: &mut Scan<'_>) -> Option<bool> {
        fn visit(scan: &mut Scan<'_>) -> Option<()> {
            if *scan.items >= 100_000 {
                return None;
            }
            if let Some(w) = scan.work {
                if let Err(error) = w.step() {
                    scan.error = Some(error);
                    return None;
                }
            }
            *scan.items += 1;
            crate::diagnostics::counter("history_structural_metadata_visits", 1);
            Some(())
        }
        fn selected(value: &Value, scan: &mut Scan<'_>) -> Option<bool> {
            visit(scan)?;
            match value {
                Value::Object(m) => {
                    if m.get("op").and_then(Value::as_str) == Some("select") {
                        return Some(true);
                    }
                    for child in m.values() {
                        if selected(child, scan)? {
                            return Some(true);
                        }
                    }
                }
                Value::Array(a) => {
                    for child in a {
                        if selected(child, scan)? {
                            return Some(true);
                        }
                    }
                }
                _ => (),
            }
            Some(false)
        }
        fn reads(value: &Value, nodes: &[usize], scan: &mut Scan<'_>) -> Option<bool> {
            visit(scan)?;
            match value {
                Value::Object(m) => {
                    if let Some(n) = m.get("node").and_then(Value::as_u64) {
                        for &node in nodes {
                            visit(scan)?;
                            if n as usize == node {
                                return Some(true);
                            }
                        }
                    }
                    for child in m.values() {
                        if reads(child, nodes, scan)? {
                            return Some(true);
                        }
                    }
                }
                Value::Array(a) => {
                    for child in a {
                        if reads(child, nodes, scan)? {
                            return Some(true);
                        }
                    }
                }
                _ => (),
            }
            Some(false)
        }
        fn guarded(value: &Value, nodes: &[usize], scan: &mut Scan<'_>) -> Option<bool> {
            visit(scan)?;
            match value {
                Value::Object(m) => {
                    if m.get("op").and_then(Value::as_str) == Some("select") {
                        for key in ["left", "right"] {
                            if let Some(v) = m.get(key) {
                                if reads(v, nodes, scan)? {
                                    return Some(true);
                                }
                            }
                        }
                    }
                    for child in m.values() {
                        if guarded(child, nodes, scan)? {
                            return Some(true);
                        }
                    }
                }
                Value::Array(a) => {
                    for child in a {
                        if guarded(child, nodes, scan)? {
                            return Some(true);
                        }
                    }
                }
                _ => (),
            }
            Some(false)
        }
        let Some(operators) = value.get("operators").and_then(Value::as_array) else {
            return Some(false);
        };
        let mut transition = false;
        for operator in operators {
            visit(scan)?;
            if operator.get("kind").and_then(Value::as_str) == Some("transition") {
                transition = true;
                break;
            }
        }
        if !transition {
            return Some(false);
        }
        let Some(contributions) = value.get("contributions").and_then(Value::as_array) else {
            return Some(false);
        };
        let mut outputs = Vec::new();
        for c in contributions {
            visit(scan)?;
            let positive = c.get("positive").and_then(Value::as_u64)?;
            let negative = c.get("negative").and_then(Value::as_u64)?;
            if (negative == 0 || positive == 0) && selected(c.get("rhs")?, scan)? {
                visit(scan)?;
                outputs.push(if negative == 0 { positive } else { negative } as usize);
            }
        }
        if outputs.is_empty() {
            return Some(false);
        }
        for c in contributions {
            visit(scan)?;
            if guarded(c.get("rhs")?, &outputs, scan)? {
                return Some(true);
            }
        }
        Some(false)
    }
    let found = candidate(value, &mut scan);
    if let Some(error) = scan.error {
        return Err(error);
    }
    Ok(found.unwrap_or(false))
}

pub(crate) fn validate(program: &Program) -> Result<Admission<'_>, Error> {
    admit(program, None)
}
pub(crate) fn admit<'a>(
    program: &'a Program,
    work: Option<&crate::transition_source_plan::Work>,
) -> Result<Admission<'a>, Error> {
    if let Some(w) = work {
        crate::event_floor::charge(w, 0, "floor_source_admission_walk")?;
    }
    // None retains the original mandatory validation serializer and limits.
    // A supplied source owner pays before every new buffer and visit.
    let value = if let Some(w) = work {
        let bytes = crate::event_floor::admission_bytes(program, w)?;
        crate::event_floor::charge(
            w,
            bytes.len().saturating_mul(32),
            "floor_source_admission_copy",
        )?;
        serde_json::from_slice(&bytes).map_err(|e| Error::new("invalid_ir", e.to_string()))?
    } else {
        serde_json::to_value(program).map_err(|e| Error::new("invalid_ir", e.to_string()))?
    };
    let mut stack = vec![(&value, 0usize, false)];
    let mut items = 0usize;
    let mut copy_items = 0usize;
    let mut invalid_round_role = false;
    let mut summaries = std::collections::HashMap::<usize, Summary>::new();
    while !stack.is_empty() {
        if let Some(w) = work {
            crate::event_floor::charge(w, 1, "floor_source_admission_walk")?;
        }
        let (v, depth, finish) = stack.pop().unwrap();
        let key = v as *const Value as usize;
        if !finish {
            items += 1;
            copy_items = copy_items.saturating_add(1 + v.as_str().map_or(0, str::len));
            if items > 100_000 || depth + usize::from(v.is_array() || v.is_object()) > 96 {
                return Err(Error::new(
                    "resource_budget",
                    "IR exceeds 100000 values/containers or depth96",
                ));
            }
            stack.push((v, depth, true));
            match v {
                Value::Object(m) => {
                    if let Some(w) = work {
                        crate::event_floor::charge(w, m.len(), "floor_source_admission_walk")?;
                    }
                    stack.extend(m.values().map(|x| (x, depth + 1, false)));
                }
                Value::Array(a) => {
                    if let Some(w) = work {
                        crate::event_floor::charge(w, a.len(), "floor_source_admission_walk")?;
                    }
                    stack.extend(a.iter().map(|x| (x, depth + 1, false)));
                }
                _ => {}
            }
            continue;
        }
        let get = |v: &Value| {
            summaries
                .get(&(v as *const Value as usize))
                .copied()
                .unwrap_or_default()
        };
        let mut summary = Summary::default();
        match v {
            Value::Array(a) => {
                for child in a {
                    let c = get(child);
                    summary.coefficient |= c.coefficient;
                    summary.floor |= c.floor;
                    summary.event_only |= c.event_only;
                    summary.round_invalid |= c.round_invalid || c.round_pending;
                }
            }
            Value::Object(m) => {
                if let Some(w) = work {
                    crate::event_floor::charge(w, m.len(), "floor_source_admission_walk")?;
                }
                summary.coefficient = m
                    .get("coefficient")
                    .and_then(Value::as_f64)
                    .is_some_and(|x| !binary_scale(x));
                for child in m.values() {
                    let c = get(child);
                    summary.coefficient |= c.coefficient;
                    summary.floor |= c.floor;
                    summary.event_only |= c.event_only;
                    summary.round_invalid |= c.round_invalid;
                    if c.round_pending {
                        // Only new conversion sites pay for role lookup. This
                        // is the existing bounded mandatory postorder, with no
                        // second walk, payload clone, or request owner.
                        if let Some(w) = work {
                            crate::event_floor::charge(w, 16, "integer_round_role_validation")?;
                        }
                        let allowed = m.get("kind").and_then(Value::as_str) == Some("assign")
                            && m.get("rhs").is_some_and(|rhs| std::ptr::eq(rhs, child))
                            && m.get("state")
                                .and_then(Value::as_u64)
                                .and_then(|state| usize::try_from(state).ok())
                                .and_then(|state| program.states.get(state))
                                .is_some_and(|state| state.kind == crate::ir::StateKind::Integer);
                        summary.round_invalid |= !allowed;
                    }
                }
                let child = |name: &str| m.get(name).map(get).unwrap_or_default();
                summary.event_only |= m.get("op").and_then(Value::as_str).is_some_and(|op| {
                    matches!(
                        op,
                        "integer_primitive" | "checked_index" | "checked_integer" | "array_read"
                    )
                });
                match m.get("op").and_then(Value::as_str) {
                    Some("affine") => {
                        summary.operand = child("terms").coefficient;
                        if m.get("terms")
                            .and_then(Value::as_array)
                            .is_some_and(Vec::is_empty)
                        {
                            summary.constant = m.get("constant").and_then(Value::as_f64);
                        }
                    }
                    Some("integer_round") => {
                        summary.floor = true;
                        summary.round_pending = true;
                    }
                    Some("divide") => summary.operand = true,
                    Some("add") => {
                        summary.operand = child("left").operand || child("right").operand
                    }
                    Some("multiply") => {
                        let a = child("left");
                        let b = child("right");
                        summary.operand = a.operand
                            || b.operand
                            || [a.constant, b.constant]
                                .iter()
                                .flatten()
                                .any(|x| !binary_scale(*x));
                    }
                    Some("event_math")
                        if m.get("function").and_then(Value::as_str) == Some("floor") =>
                    {
                        summary.floor = m
                            .get("args")
                            .and_then(Value::as_array)
                            .and_then(|a| a.first())
                            .is_some_and(|a| get(a).operand);
                    }
                    _ => {}
                }
            }
            _ => {}
        }
        if let Some(w) = work {
            crate::event_floor::charge(w, 8, "floor_source_admission_copy")?;
        }
        if depth == 0 {
            invalid_round_role = summary.round_pending || summary.round_invalid;
        }
        summaries.insert(key, summary);
    }
    if invalid_round_role {
        return Err(Error::new(
            "invalid_ir",
            "integer_round is only allowed as the RHS root of a scalar integer assignment",
        ));
    }
    let (floor_events, source_floor) =
        floor_metadata(&value, &summaries, program.events.len(), work)?;
    if let Some(w) = work {
        crate::event_floor::charge(w, program.events.len() + 8, "floor_source_admission_walk")?;
    }
    let event_only = |v: &Value| {
        summaries
            .get(&(v as *const Value as usize))
            .is_some_and(|s| s.event_only)
    };
    let mut held = std::collections::BTreeSet::new();
    if let Some(w) = work {
        crate::event_floor::charge(
            w,
            32usize.saturating_add(program.operators.len().saturating_mul(2)),
            "event_admission_operator_metadata",
        )?;
    }
    if let Some(operators) = value.get("operators").and_then(Value::as_array) {
        for (index, spec) in operators.iter().enumerate() {
            if let Some(w) = work {
                let fields = spec.as_object().map_or(0, |m| m.len());
                crate::event_floor::charge(
                    w,
                    64usize.saturating_add(fields.saturating_mul(16)),
                    "event_admission_operator_metadata",
                )?;
            }
            let typed = spec.get("kind").and_then(Value::as_str) == Some("transition")
                && spec.get("input").is_some_and(event_only);
            if typed {
                if let Some(w) = work {
                    crate::event_floor::charge(
                        w,
                        8usize.saturating_mul(held.len().saturating_add(1)),
                        "event_admission_target_set",
                    )?;
                }
                held.insert(index);
            }
            if spec.as_object().is_some_and(|fields| {
                fields
                    .iter()
                    .any(|(name, v)| !(typed && name == "input") && event_only(v))
            }) {
                return Err(Error::new(
                    "unsupported_analysis",
                    "checked arithmetic outside a typed held Transition input",
                ));
            }
        }
    }
    if value
        .as_object()
        .unwrap()
        .iter()
        // Procedure bodies have the same typed executor as event bodies and
        // are validated by procedure::validate, including inactive branches.
        // Numerical equation/trigger fields still cannot own these operations.
        .any(|(name, v)| {
            name != "events" && name != "operators" && name != "procedures" && event_only(v)
        })
    {
        return Err(Error::new(
            "unsupported_analysis",
            "checked integer/index and array access require an isolated observer event body",
        ));
    }
    if value
        .get("events")
        .and_then(Value::as_array)
        .is_some_and(|events| {
            events
                .iter()
                .any(|e| e.get("trigger").is_some_and(event_only))
        })
    {
        return Err(Error::new(
            "unsupported_analysis",
            "checked event arithmetic cannot appear in an event trigger",
        ));
    }
    let history_candidate = history_candidate(&value, &mut items, work)?;
    Ok(Admission {
        history_candidate,
        program,
        floor_events,
        source_floor,
        targets: held,
        copy_items,
    })
}

#[cfg(test)]
mod source_floor_admission_tests {
    use super::*;
    use crate::diagnostics::{capture, Options};
    use crate::ir::{Tolerances, SCHEMA_VERSION};
    use crate::pwl::Trajectory;
    use crate::transition_source_plan::{ProofContext, Work};
    use serde_json::json;
    fn fixture(prefix: usize, new_floor: bool) -> (Program, Trajectory, Vec<String>) {
        let o = json!({"source":"prescan.va","line":1,"column":1,"instance":"dut"});
        let mut body = vec![
            json!({"kind":"assign","state":0,"rhs":{"op":"affine","constant":0.,"terms":[]}});
            prefix
        ];
        let arg = if new_floor {
            json!({"op":"divide","left":{"op":"affine","constant":0.,"terms":[{"node":1,"coefficient":1.}]},"right":{"op":"affine","constant":3.,"terms":[]}})
        } else {
            json!({"op":"affine","constant":0.,"terms":[{"node":1,"coefficient":8.}]})
        };
        body.push(json!({"kind":"assign","state":0,"rhs":{"op":"event_math","function":"floor","origin":o,"args":[arg]}}));
        let p:Program=serde_json::from_value(json!({"schema_version":SCHEMA_VERSION,"nodes":["0","u"],"contributions":[],"states":[{"name":"q","instance":"dut","kind":"integer","initial":0.}],"events":[{"origin":o,"trigger":{"kind":"timer","start":0.25,"period":1.,"time_tolerance":1e-12,"enabled":true},"body":body}]})).unwrap();
        let t=Trajectory::new(serde_json::from_value(json!({"pwl":[[[0.,0.03],[1.,0.03]]],"output_times":[0.,1.],"stop":1.,"max_step":1.})).unwrap(),1).unwrap();
        (p, t, vec!["u".into()])
    }
    #[test]
    fn source_floor_metadata_prepays_table_and_second_pass_before_work_and_retries() {
        for count in [0, 1, 2048] {
            let value =
                json!({"events": (0..count).map(|_| json!({"body": []})).collect::<Vec<_>>()});
            let mut summaries = std::collections::HashMap::new();
            if count > 0 {
                let body = &value["events"][count - 1]["body"];
                summaries.insert(
                    body as *const Value as usize,
                    Summary {
                        floor: true,
                        ..Summary::default()
                    },
                );
            }
            let fee = floor_metadata_cost(count);
            let work = Work::limited([128, 8192, (fee - 1) as u64]);
            for retry in 0..3 {
                let (answer, report) = capture(Options::default(), || {
                    floor_metadata(&value, &summaries, count, Some(&work))
                });
                assert!(answer.is_err(), "count={count} retry={retry}");
                let counters = format!("{:?}", report.counters);
                assert!(
                    !counters.contains("floor_metadata_"),
                    "work occurred before reservation: {counters}"
                );
                assert_eq!(work.spent(), fee as u64, "sticky retry changed spent");
                println!(
                    "metadata refused count={count} retry={retry} spent={} counters={counters}",
                    work.spent()
                );
            }
            let work = Work::limited([128, 8192, fee as u64]);
            let (answer, report) = capture(Options::default(), || {
                floor_metadata(&value, &summaries, count, Some(&work))
            });
            let (table, found) = answer.unwrap();
            assert_eq!(report.counters.get("floor_metadata_root_lookup"), Some(&1));
            assert_eq!(report.counters.get("floor_metadata_allocate"), Some(&1));
            assert_eq!(report.counters.get("floor_metadata_any_enter"), Some(&1));
            for key in ["floor_metadata_event_visit", "floor_metadata_any_visit"] {
                assert_eq!(report.counters.get(key).copied().unwrap_or(0), count as u64);
            }
            println!(
                "metadata accepted count={count} spent={} counters={:?}",
                work.spent(),
                report.counters
            );
            assert_eq!(table.len(), count);
            assert_eq!(found, count > 0);
            assert_eq!(table.iter().filter(|v| **v).count(), usize::from(count > 0));
            assert_eq!(work.spent(), fee as u64);
            assert_eq!(
                floor_metadata(&value, &summaries, count, None).unwrap(),
                (table, found)
            );
        }
    }
    #[test]
    fn source_floor_exhausted_provided_entry_and_factory_refuse_before_any_prefix_visit_twice() {
        for prefix in [0, 2048] {
            let (p, t, d) = fixture(prefix, true);
            let work = Work::limited([128, 8192, 0]);
            let source = ProofContext::new(&p, &t, &d, work.clone()).unwrap();
            assert!(work.debit(2, 1).is_err());
            let spent = work.spent();
            let token = admit(&p, None).unwrap();
            assert!(std::ptr::eq(token.program(), &p));
            for retry in 0..2 {
                let original = p.clone();
                let names = d.clone();
                let supplied = source.clone();
                let (answer, report) = capture(Options::default(), || {
                    crate::events::EventModel::new_with_context(
                        original,
                        names,
                        Tolerances::default(),
                        Some(&t),
                        Some(supplied),
                    )
                    .map(|_| ())
                });
                assert_eq!(answer.err().unwrap().kind, "step_budget");
                assert_eq!(report.counters.len(), 1);
                assert_eq!(report.counters.get("floor_source_work_exhausted"), Some(&1));
                assert_eq!(work.spent(), spent);
                let (answer, report) = capture(Options::default(), || {
                    crate::event_floor::Request::new(&token, &t, &d, Some(source.clone()))
                        .map(|_| ())
                });
                assert_eq!(answer.err().unwrap().kind, "step_budget");
                assert_eq!(report.counters.len(), 1);
                assert_eq!(report.counters.get("floor_source_work_exhausted"), Some(&1));
                assert_eq!(work.spent(), spent);
                eprintln!("source_floor_r2_sticky prefix={prefix} retry={retry} spent={spent} counters={:?}",report.counters);
            }
        }
    }
    #[test]
    fn source_floor_none_factory_consumes_mandatory_token_and_old_binary_floor_creates_no_owner() {
        for prefix in [0, 2048] {
            let (old, t, d) = fixture(prefix, false);
            let (answer, report) = capture(Options::default(), || {
                let token = admit(&old, None)?;
                assert!(!token.source_floor());
                crate::event_floor::Request::new(&token, &t, &d, None)
            });
            assert!(answer.unwrap().is_none());
            assert!(!report
                .counters
                .keys()
                .any(|k| k.starts_with("floor_source_")));
            let (new, t, d) = fixture(prefix, true);
            let (answer, report) = capture(Options::default(), || {
                let token = admit(&new, None)?;
                assert!(token.source_floor());
                crate::event_floor::Request::new(&token, &t, &d, None)
            });
            assert!(answer.unwrap().is_some());
            assert_eq!(report.counters.get("floor_source_factory_calls"), Some(&1));
            assert_eq!(report.counters.get("floor_source_owner_created"), Some(&1));
            assert!(!report.counters.contains_key("floor_source_dispatch_scan"));
            assert!(!report.counters.contains_key("floor_source_operand_scan"));
        }
    }
}
