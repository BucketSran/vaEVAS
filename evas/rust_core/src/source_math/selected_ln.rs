//! One selected, stateless Ln input, retaining original source predicate proofs.
//! This is an owned-tree query adapter, not a history waveform or a new budget.
use super::{unsupported, Audit, Prepared};
use crate::analog::Analog;
use crate::interval::Interval as I;
use crate::ir::{
    Error, Expression as E, MathFunction, OperatorSpec, Origin, Program, Relation, Term, Tolerances,
};
use crate::pwl::Trajectory;
use crate::transition_source_plan::ProofContext;
use std::collections::HashSet;
use std::sync::Arc;

pub(crate) fn candidate(p: &Program) -> bool {
    p.states.is_empty()
        && p.events.is_empty()
        && p.step_bounds.is_empty()
        && p.operators.len() == 1
        && matches!(
            &p.operators[0],
            OperatorSpec::Math {
                function: MathFunction::Ln,
                input: E::Select { .. },
                ..
            }
        )
}
fn origin_items(o: &Origin) -> usize {
    8 + o.source.len()
        + o.instance.len()
        + o.expansion.iter().map(|(s, _)| s.len() + 2).sum::<usize>()
}
// Original-tree audit runs before any source value or copy. The return counts
// all storage the subsequent Program::clone will copy, not just active arms.
fn audit_input(
    e: &E,
    sources: &HashSet<usize>,
    audit: &mut Audit,
    owner: &str,
) -> Result<(bool, usize), Error> {
    audit.charge(1)?;
    match e {
        E::Affine { constant, terms } => {
            audit.charge(terms.len())?;
            if !constant.is_finite()
                || terms
                    .iter()
                    .any(|t| !t.coefficient.is_finite() || !sources.contains(&t.node))
            {
                return Err(unsupported());
            }
            Ok((!terms.is_empty(), 3 + 2 * terms.len()))
        }
        E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
            let (a, ac) = audit_input(left, sources, audit, owner)?;
            let (b, bc) = audit_input(right, sources, audit, owner)?;
            if matches!(e, E::Multiply { .. }) && a && b || matches!(e, E::Divide { .. }) && b {
                return Err(unsupported());
            }
            Ok((a || b, 3 + ac + bc))
        }
        E::Select {
            left,
            right,
            then_value,
            else_value,
            origin,
            ..
        } => {
            audit.charge(origin.expansion.len() + 8)?;
            let size = origin_items(origin);
            audit.charge(size)?;
            if origin.source.is_empty()
                || origin.instance != owner
                || origin.line == 0
                || origin.column == 0
                || !origin.valid_expansion()
            {
                return Err(unsupported());
            }
            let (_, a) = audit_input(left, sources, audit, owner)?;
            let (_, b) = audit_input(right, sources, audit, owner)?;
            let (x, c) = audit_input(then_value, sources, audit, owner)?;
            let (y, d) = audit_input(else_value, sources, audit, owner)?;
            Ok((x || y, 5 + a + b + c + d + size))
        }
        _ => Err(unsupported()),
    }
}

pub(crate) struct SelectedLn {
    context: Arc<ProofContext>,
    input: E,
    input_nodes: Vec<usize>,
    node_count: usize,
    dimensions: usize,
    query_copy: usize,
}
impl Drop for SelectedLn {
    fn drop(&mut self) {
        crate::diagnostics::counter(
            "selected_ln_work_end",
            self.context.source_work_used() as usize,
        );
    }
}
impl Prepared {
    pub(crate) fn new_selected_ln(
        p: &Program,
        t: &Trajectory,
        driven: &[String],
        tol: &Tolerances,
    ) -> Result<Self, Error> {
        if !candidate(p) || p.contributions.len() != 1 {
            return Err(unsupported());
        }
        let OperatorSpec::Math { input, origin, .. } = &p.operators[0] else {
            unreachable!()
        };
        // This gate is the old affine consumer's exact Select representation
        // miss, not a catch-and-retry of arbitrary errors or successful paths.
        if !matches!(input, E::Select { .. }) {
            return Err(unsupported());
        }
        let mut audit = Audit {
            remaining: Some(100_000),
        };
        audit.charge(origin.expansion.len() + 8)?;
        audit.charge(origin_items(origin))?;
        if origin.source.is_empty()
            || origin.instance.is_empty()
            || origin.line == 0
            || origin.column == 0
            || !origin.valid_expansion()
        {
            return Err(unsupported());
        }
        audit.charge(p.nodes.len() + driven.len())?;
        let name_items = p.nodes.iter().map(|n| n.len() + 1).sum::<usize>();
        audit.charge(name_items)?;
        let mut sources = HashSet::from([0]);
        let mut input_nodes = Vec::new();
        for name in driven {
            audit.charge(name_items)?;
            let node = p
                .nodes
                .iter()
                .position(|n| n == name)
                .ok_or_else(unsupported)?;
            if !sources.insert(node) {
                return Err(unsupported());
            }
            input_nodes.push(node);
        }
        // One original affine voltage relation and one unknown output keep
        // downstream trial-copy/assembly work bounded; no internal feedback.
        let output = &p.contributions[0];
        audit.charge(p.nodes.len())?;
        let output_node = match (output.positive, output.negative) {
            (0, n) | (n, 0) if n != 0 => n,
            _ => return Err(unsupported()),
        };
        if sources.contains(&output_node)
            || p.nodes
                .iter()
                .enumerate()
                .any(|(n, _)| !sources.contains(&n) && n != output_node)
        {
            return Err(unsupported());
        }
        if let Some(errors) = &t.config.pwl_errors_v {
            audit.charge(errors.len())?;
            if errors.iter().any(|e| e.shape().is_some() && e.bound() > 0.) {
                return Err(Error::new(
                    "unsupported_source_uncertainty",
                    "selected Ln does not admit physical source-shape bands",
                ));
            }
        }
        let (_, input_items) = audit_input(input, &sources, &mut audit, &origin.instance)?;
        let mut copy = 16 + input_items + origin_items(origin);
        for c in &p.contributions {
            audit.charge(c.origin.expansion.len() + 8)?;
            audit.charge(
                origin_items(&c.origin)
                    + c.branch.instance.len()
                    + c.branch.local_positive.len()
                    + c.branch.local_negative.len(),
            )?;
            audit.charge(1)?;
            let before = audit.remaining.unwrap();
            audit.tree(&c.rhs, p, &sources, &c.origin.instance, true)?;
            let items = before - audit.remaining.unwrap();
            let dense = items.saturating_mul(p.nodes.len() + 2).saturating_mul(6);
            audit.charge(dense)?;
            // Contributions stay affine, including any single operator leaf.
            crate::events::affine(&c.rhs, p, &c.origin.instance)?;
            copy = copy.saturating_add(
                items * 4
                    + origin_items(&c.origin)
                    + c.branch.instance.len()
                    + c.branch.local_positive.len()
                    + c.branch.local_negative.len()
                    + 16,
            );
        }
        audit.charge(copy)?;
        let context = ProofContext::new_source_math(p, t, driven, copy)?;
        context.source_charge(
            "selected_ln_copy_items",
            copy + name_items
                + input_items
                + origin_items(origin)
                + driven.iter().map(|s| s.len() + 1).sum::<usize>()
                + 32,
        )?;
        let mut reduced = p.clone();
        let start = reduced.nodes.len();
        let name = "$source_math_0".to_string();
        if reduced.nodes.contains(&name) {
            return Err(Error::new(
                "invalid_ir",
                "reserved source math node collision",
            ));
        }
        reduced.nodes.push(name.clone());
        let mut extended = driven.to_vec();
        extended.push(name);
        fn replace(e: &mut E, start: usize, ctx: &ProofContext) -> Result<(), Error> {
            ctx.source_charge("selected_ln_ast_visits", 1)?;
            match e {
                E::Operator { operator: 0 } => {
                    ctx.source_charge("selected_ln_copy_items", 5)?;
                    *e = E::Affine {
                        constant: 0.,
                        terms: vec![Term {
                            node: start,
                            coefficient: 1.,
                        }],
                    };
                }
                E::Add { left, right }
                | E::Multiply { left, right }
                | E::Divide { left, right } => {
                    replace(left, start, ctx)?;
                    replace(right, start, ctx)?;
                }
                _ => (),
            }
            Ok(())
        }
        for c in &mut reduced.contributions {
            replace(&mut c.rhs, start, &context)?;
        }
        reduced.operators.clear();
        let query_copy = copy
            .saturating_add(name_items)
            .saturating_add(64 + start + driven.iter().map(|s| s.len() + 1).sum::<usize>());
        Ok(Self {
            operators: None,
            selected: Some(SelectedLn {
                context,
                input: input.clone(),
                input_nodes,
                node_count: p.nodes.len(),
                dimensions: p.nodes.len() + 2,
                query_copy,
            }),
            analog: Analog::new(reduced, extended, tol.clone())?,
            original_nodes: start,
        })
    }
}
impl SelectedLn {
    fn charge(&self, kind: &'static str, items: usize) -> Result<(), Error> {
        self.context.source_charge(kind, items)
    }
    // Count before delegating traversal/copy; every node and affine term is
    // visited under this same ledger. No full-tree query prescan is free.
    fn items(&self, e: &E) -> Result<usize, Error> {
        self.charge("selected_ln_ast_visits", 1)?;
        Ok(match e {
            E::Affine { terms, .. } => {
                self.charge("selected_ln_term_visits", terms.len())?;
                1 + terms.len()
            }
            E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
                1 + self.items(left)? + self.items(right)?
            }
            _ => return Err(unsupported()),
        })
    }
    fn interval(&self, e: &E, nodes: &[I]) -> Result<I, Error> {
        let items = self.items(e)?;
        self.charge("selected_ln_interval_debit", items.saturating_mul(16))?;
        crate::expression::expression_interval(e, nodes)
    }
    fn resolve(&self, e: &E, nodes: &[I], time: f64) -> Result<E, Error> {
        self.charge("selected_ln_ast_visits", 1)?;
        Ok(match e {
            E::Select {
                relation,
                left,
                right,
                then_value,
                else_value,
                ..
            } => {
                let a = self.resolve(left, nodes, time)?;
                let b = self.resolve(right, nodes, time)?;
                let d = self.interval(&a, nodes)? - self.interval(&b, nodes)?;
                if !d.finite() {
                    return Err(Error::new(
                        "nonfinite_arithmetic",
                        "selected Ln nonfinite predicate",
                    ));
                }
                let decision = match relation {
                    Relation::Lt => (d.hi < 0., d.lo >= 0.),
                    Relation::Le => (d.hi <= 0., d.lo > 0.),
                    Relation::Gt => (d.lo > 0., d.hi <= 0.),
                    Relation::Ge => (d.lo >= 0., d.hi < 0.),
                };
                let yes = if decision.0 || decision.1 {
                    crate::diagnostics::counter("selected_ln_interval_decisions", 1);
                    decision.0
                } else {
                    // Helper's local cap covers rational arithmetic; prepaid
                    // source-node lookup/term scans are additional outer work.
                    let items = self.items(&a)? + self.items(&b)?;
                    self.charge(
                        "selected_ln_lookup_debit",
                        items
                            .saturating_mul(self.input_nodes.len() + 1)
                            .saturating_mul(8),
                    )?;
                    let sign = self.context.source_point_sign(&a, &b, time)?;
                    match relation {
                        Relation::Lt => sign < 0,
                        Relation::Le => sign <= 0,
                        Relation::Gt => sign > 0,
                        Relation::Ge => sign >= 0,
                    }
                };
                return self.resolve(if yes { then_value } else { else_value }, nodes, time);
            }
            E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
                self.charge("selected_ln_copy_items", 3)?;
                let a = Box::new(self.resolve(left, nodes, time)?);
                let b = Box::new(self.resolve(right, nodes, time)?);
                match e {
                    E::Add { .. } => E::Add { left: a, right: b },
                    E::Multiply { .. } => E::Multiply { left: a, right: b },
                    _ => E::Divide { left: a, right: b },
                }
            }
            E::Affine { terms, .. } => {
                self.charge("selected_ln_term_visits", terms.len())?;
                self.charge("selected_ln_copy_items", 3 + terms.len() * 2)?;
                e.clone()
            }
            _ => return Err(unsupported()),
        })
    }
    pub(super) fn value(&self, values: &[f64], bounds: &[I], time: f64) -> Result<(f64, I), Error> {
        self.charge(
            "selected_ln_prepare_debit",
            2 * self.node_count + 2 * self.input_nodes.len() + 8,
        )?;
        let mut nodes = vec![I::ZERO; self.node_count];
        let mut nominal = vec![0.; self.node_count];
        for ((&node, &v), &b) in self.input_nodes.iter().zip(values).zip(bounds) {
            nodes[node] = b;
            nominal[node] = v;
        }
        let resolved = self.resolve(&self.input, &nodes, time)?;
        let items = self.items(&resolved)?;
        // The selected tree is piecewise-affine by original-tree admission.
        // Bounds retain arithmetic order, not a rounded endpoint surrogate.
        let bound = self.interval(&resolved, &nodes)?;
        let value = self
            .context
            .source_affine_value(&resolved, &nominal, items)?;
        self.charge("selected_ln_ln_debit", 1024)?;
        let enclosure = crate::math_functions::ln(bound)?;
        let value = value.ln();
        if !value.is_finite() || !enclosure.finite() {
            return Err(Error::new(
                "nonfinite_arithmetic",
                "selected Ln nonfinite result",
            ));
        }
        Ok((value, enclosure.hull(I::point(value))))
    }
    pub(super) fn charge_extension_copies(&self, inputs: usize) -> Result<(), Error> {
        // Prepay added returned/extended scalar and bound vectors before the
        // common Prepared::solve code allocates or copies them.
        self.charge(
            "selected_ln_prepare_debit",
            inputs.saturating_mul(4).saturating_add(8),
        )
    }
    pub(super) fn charge_trial_copy(&self) -> Result<(), Error> {
        // Fresh downstream stateless trial: no cache or result survives a
        // domain/voltage/resource refusal. Dense assembly is the existing solver.
        self.charge(
            "selected_ln_copy_items",
            self.query_copy
                .saturating_mul(self.dimensions)
                .saturating_mul(16),
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::diagnostics::{capture, Options};
    use crate::transition_source_plan::Work;
    use serde_json::json;
    fn fixture() -> (Program, Trajectory, Vec<String>, Tolerances) {
        let o = json!({"source":"selected.va","line":1,"column":1,"instance":"dut"});
        let u = json!({"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]});
        let scalar = |x: f64| json!({"op":"affine","constant":x,"terms":[]});
        let x = json!({"op":"add","left":u,"right":scalar(-0.2)});
        let a = json!({"op":"select","relation":"ge","left":x,"right":scalar(0.),"then_value":x,"else_value":{"op":"multiply","left":scalar(-1.),"right":x},"origin":o});
        let input = json!({"op":"select","relation":"lt","left":a,"right":scalar(0.1),"then_value":scalar(0.1),"else_value":a,"origin":o});
        let p:Program=serde_json::from_value(json!({"schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","u","y"],
            "operators":[{"kind":"math","function":"ln","input":input,"origin":o}],
            "contributions":[{"branch":{"kind":"voltage","instance":"dut","local_positive":"out","local_negative":"ref"},"positive":2,"negative":0,"rhs":{"op":"operator","operator":0},"origin":o}]})).unwrap();
        let t=Trajectory::new(serde_json::from_value(json!({"pwl":[[[0.,0.7],[1.,-0.3]]],"output_times":[0.,0.5,1.],"stop":1.,"max_step":1.})).unwrap(),1).unwrap();
        (p, t, vec!["u".into()], Tolerances::default())
    }
    fn counted(run: impl FnOnce() -> Result<(), Error>) -> crate::diagnostics::Report {
        let (result, report) = capture(Options::default(), run);
        result.unwrap();
        report
    }
    #[test]
    fn selected_source_query_encloses_hidden_clamp_and_meters_actual_work() {
        let (p, t, d, tol) = fixture();
        let report = counted(|| {
            let mut a = Prepared::new_selected_ln(&p, &t, &d, &tol)?;
            let y = a.solve(&t.values(0.5), &t.value_bounds(0.5), 0.5, &t.exact_sources)?;
            let v = y.voltages[2];
            assert!((v - 0.1f64.ln()).abs() < 1e-12);
            let b = y.certified_voltage_bounds.unwrap()[2];
            assert!(b[0] <= 0.1f64.ln() && b[1] >= 0.1f64.ln());
            assert!(!a.analog.source_trial_has_cache());
            Ok(())
        });
        assert_eq!(report.counters["selected_ln_factory_calls"], 1);
        assert_eq!(
            report.counters.get("selected_ln_exact_calls"),
            report.counters.get("selected_ln_exact_reservations")
        );
        assert!(report.counters["selected_ln_ast_visits"] > 0);
        assert!(report.counters["selected_ln_term_visits"] > 0);
        assert!(report.counters["selected_ln_copy_items"] > 0);
        assert!(report.counters["selected_ln_dense_debit"] > 0);
        assert_eq!(report.counters["selected_ln_ln_debit"], 1024);
        assert_eq!(
            report.counters["selected_ln_work_end"],
            report.counters["selected_ln_work_debit"]
        );
        println!(
            "selected_ln_accounting={}",
            serde_json::to_string(&report.counters).unwrap()
        );
    }
    #[test]
    fn interval_decisions_do_not_pay_for_unused_exact_helpers() {
        let (p, t, d, tol) = fixture();
        let report = counted(|| {
            let mut a = Prepared::new_selected_ln(&p, &t, &d, &tol)?;
            a.solve(&t.values(0.), &t.value_bounds(0.), 0., &t.exact_sources)?;
            Ok(())
        });
        assert!(report.counters["selected_ln_interval_decisions"] > 0);
        assert_eq!(
            report
                .counters
                .get("selected_ln_exact_calls")
                .copied()
                .unwrap_or(0),
            0
        );
        assert_eq!(
            report
                .counters
                .get("selected_ln_exact_debit")
                .copied()
                .unwrap_or(0),
            0
        );
    }
    #[test]
    fn nonpoint_predicate_uses_original_source_and_one_exact_reservation() {
        let (p, t, d, tol) = fixture();
        let report = counted(|| {
            let a = Prepared::new_selected_ln(&p, &t, &d, &tol)?;
            let selected = a.selected.as_ref().unwrap();
            let (v, b) = selected.value(&t.values(0.5), &[I { lo: 0.19, hi: 0.21 }], 0.5)?;
            assert!((v - 0.1f64.ln()).abs() < 1e-12);
            assert!(b.finite());
            Ok(())
        });
        let calls = report.counters["selected_ln_exact_calls"];
        assert!(calls > 0);
        assert_eq!(calls, report.counters["selected_ln_exact_reservations"]);
        assert_eq!(report.counters["selected_ln_exact_debit"], 200_000 * calls);
    }
    #[test]
    fn inactive_and_zero_weight_dependencies_reject_before_factory() {
        let (p, t, d, tol) = fixture();
        let base = serde_json::to_value(&p).unwrap();
        for bad in [
            json!({"op":"affine","constant":0,"terms":[{"node":2,"coefficient":0}]}),
            json!({"op":"state","state":0}),
            json!({"op":"operator","operator":0}),
        ] {
            let mut raw = base.clone();
            raw["operators"][0]["input"]["then_value"] = bad;
            let p: Program = serde_json::from_value(raw).unwrap();
            let (_, report) = capture(Options::default(), || {
                Prepared::new_selected_ln(&p, &t, &d, &tol).map(|_| ())
            });
            assert_eq!(report.status, "failed");
            assert!(!report.counters.contains_key("selected_ln_factory_calls"));
        }
    }
    #[test]
    fn source_identity_is_not_inferred_from_equal_ast_or_shared_quota() {
        let (p, a, d, _) = fixture();
        let mut config = a.config.clone();
        config.pwl = vec![vec![[0., 1.2], [1., 1.2]]];
        let b = Trajectory::new(config, 1).unwrap();
        let work = Work::default();
        let x = ProofContext::source_math_with_work(&p, &a, &d, 1024, work.clone()).unwrap();
        let y = ProofContext::source_math_with_work(&p, &b, &d, 1024, work).unwrap();
        let e: E = serde_json::from_value(
            json!({"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]}),
        )
        .unwrap();
        let r = E::Affine {
            constant: 0.5,
            terms: vec![],
        };
        assert_eq!(x.source_point_sign(&e, &r, 0.5).unwrap(), -1);
        assert_eq!(y.source_point_sign(&e, &r, 0.5).unwrap(), 1);
        assert_eq!(x.source_work_used(), y.source_work_used());
    }
    #[test]
    fn natural_original_owner_exhaustion_refuses_two_retries_before_clone_or_helper() {
        let (p, t, d, tol) = fixture();
        let (answer, report) = capture(Options::default(), || {
            let a = Prepared::new_selected_ln(&p, &t, &d, &tol)?;
            let s = a.selected.as_ref().unwrap();
            let e = E::Affine {
                constant: 0.,
                terms: vec![Term {
                    node: 1,
                    coefficient: 1.,
                }],
            };
            let r = E::Affine {
                constant: 0.2,
                terms: vec![],
            };
            let mut calls = 0;
            loop {
                match s.context.source_point_sign(&e, &r, 0.5) {
                    Ok(_) => calls += 1,
                    Err(error) => {
                        assert_eq!(error.kind, "step_budget");
                        break;
                    }
                }
            }
            assert!(calls > 4900 && calls < 5001);
            let (_, retry) = capture(Options::default(), || {
                for _ in 0..2 {
                    assert!(s.resolve(&s.input, &[I::ZERO; 3], 0.5).is_err());
                    assert!(s.context.source_point_sign(&e, &r, 0.5).is_err());
                }
                Ok(())
            });
            assert!(!retry.counters.contains_key("selected_ln_copy_items"));
            assert!(!retry.counters.contains_key("selected_ln_exact_calls"));
            assert_eq!(retry.counters["selected_ln_work_exhausted"], 4);
            println!(
                "selected_ln_blocked_retry={}",
                serde_json::to_string(&retry.counters).unwrap()
            );
            Ok(())
        });
        answer.unwrap();
        assert!(report.counters["selected_ln_work_end"] > 1_000_000_000);
        assert_eq!(
            report.counters["selected_ln_exact_calls"],
            report.counters["selected_ln_exact_reservations"]
        );
        assert!(report.counters["selected_ln_work_exhausted"] >= 1);
        println!(
            "selected_ln_exhaustion={}",
            serde_json::to_string(&report.counters).unwrap()
        );
    }
    #[test]
    fn domain_and_voltage_refusal_do_not_commit_downstream_trial() {
        let (p, t, d, tol) = fixture();
        let mut a = Prepared::new_selected_ln(&p, &t, &d, &tol).unwrap();
        let before = a.selected.as_ref().unwrap().context.source_work_used();
        assert!(a
            .solve(
                &t.values(0.),
                &[I { lo: 0.6, hi: 0.8 }],
                0.,
                &t.exact_sources
            )
            .is_err());
        assert!(!a.analog.source_trial_has_cache());
        assert!(a.selected.as_ref().unwrap().context.source_work_used() > before);
        let good = a
            .solve(&t.values(0.), &t.value_bounds(0.), 0., &t.exact_sources)
            .unwrap();
        assert!(good.voltages[2].is_finite());
        let mut raw = serde_json::to_value(&p).unwrap();
        raw["operators"][0]["input"]["then_value"] =
            json!({"op":"affine","constant":-1,"terms":[]});
        let p: Program = serde_json::from_value(raw).unwrap();
        let mut a = Prepared::new_selected_ln(&p, &t, &d, &tol).unwrap();
        assert!(a
            .solve(&t.values(0.5), &t.value_bounds(0.5), 0.5, &t.exact_sources)
            .is_err());
        assert!(!a.analog.source_trial_has_cache());
    }
    #[test]
    fn previously_successful_affine_ln_and_closed_ln_exp_add_zero_work() {
        let (p, t, d, _) = fixture();
        for chain in [false, true] {
            let mut value = serde_json::to_value(&p).unwrap();
            value["operators"][0]["input"] = if chain {
                json!({"op":"affine","constant":2,"terms":[]})
            } else {
                json!({"op":"affine","constant":1,"terms":[{"node":1,"coefficient":1}]})
            };
            if chain {
                let mut origin = value["operators"][0]["origin"].clone();
                origin["column"] = json!(2);
                value["operators"].as_array_mut().unwrap().push(json!({"kind":"math","function":"exp","input":{"op":"operator","operator":0},"origin":origin}));
                value["contributions"][0]["rhs"]["operator"] = json!(1);
            }
            let request: crate::ir::Request = serde_json::from_value(
                json!({"program":value,"driven":d,"samples":[],"transient":t.config}),
            )
            .unwrap();
            let report = counted(|| crate::run(request).map(|_| ()));
            assert!(report
                .counters
                .keys()
                .all(|key| !key.starts_with("selected_ln_")));
        }
    }
}
