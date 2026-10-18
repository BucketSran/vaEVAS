//! Shared Native/Floor owner and real Controller transaction regressions.

use super::*;
use crate::diagnostics::{capture, Options, Report};
use crate::ir::{Program, Tolerances, TransientInputs};
use serde_json::{json, Value};
use std::sync::{
    atomic::{AtomicUsize, Ordering},
    Arc,
};

fn nf_fixture() -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    let o = json!({"source":"native-floor-combination.va","line":1,"column":1,"instance":"M"});
    let c = |x: f64| json!({"op":"affine","constant":x,"terms":[]});
    // Keep the original Divide. Expected bins are independently 0 at .03 and
    // 1 at .09 for these exact binary64 leaf constants, not endpoint interpolation.
    let floor = json!({"op":"event_math","function":"floor","origin":o,"args":[
        {"op":"add","left":{"op":"multiply","left":{"op":"divide",
        "left":{"op":"affine","constant":0.,"terms":[{"node":1,"coefficient":1.}]},
        "right":c(0.9)},"right":c(15.)},"right":c(0.5)}]});
    let typed = json!({"op":"integer_primitive","function":"bit_and","origin":o,"args":[
        {"op":"integer_primitive","function":"shift_right","origin":o,"args":[
            {"op":"integer_state","state":0},{"op":"integer_literal","value":0}]},
        {"op":"integer_literal","value":1}]});
    let event = |start: f64| {
        json!({"origin":o,"trigger":{"kind":"timer","start":start,
        "period":0.,"enabled":true,"time_tolerance":1e-12},"body":[
        {"kind":"assign","state":0,"rhs":floor},
        {"kind":"display","format":"q=%d","args":[{"op":"state","state":0}],"origin":o}]})
    };
    let p: Program = serde_json::from_value(json!({"schema_version":SCHEMA_VERSION,
        "nodes":["0","u","y"],"states":[
            {"instance":"M","name":"q","kind":"integer","initial":1.},
            {"instance":"M","name":"k","kind":"integer","initial":0.}],
        "events":[event(0.125),event(0.5),event(0.875)],
        "operators":[{"kind":"transition","input":typed,"delay":0.,"rise":0.125,"fall":0.125,"origin":o}],
        "contributions":[{"branch":{"instance":"M","local_positive":"out","local_negative":"ref","kind":"voltage"},
            "positive":2,"negative":0,"rhs":{"op":"operator","operator":0},"origin":o}]})).unwrap();
    let t = Trajectory::new(
        TransientInputs {
            pwl_errors_v: None,
            strobetimes: vec![],
            pwl: vec![vec![[0., 0.03], [0.2, 0.03], [0.4, 0.09], [1., 0.09]]],
            output_times: vec![0., 0.0625, 0.25, 0.375, 0.75, 1.],
            stop: 1.,
            max_step: 0.125,
        },
        1,
    )
    .unwrap();
    // This must use root's merged one-owner factory, not a hand-made ProofContext.
    let m = EventModel::new_with_trajectory(p, vec!["u".into()], Tolerances::default(), Some(&t))
        .unwrap();
    let states = m.initial();
    let bounds: Vec<_> = states.iter().copied().map(I::point).collect();
    let calendar = independent_schedule(&m, &t).unwrap();
    let owner = m.source_context.as_ref().unwrap().clone();
    assert!(Arc::ptr_eq(
        &owner,
        &m.floor_source.as_ref().unwrap().source
    ));
    let operators = Operators::new_until_with_held_points(
        &m.program,
        &t,
        &m.driven,
        &states,
        &bounds,
        &m.typed_transition_targets,
        owner.clone(),
        t.config.stop,
        &m.tolerances,
    )
    .unwrap();
    nf_same_owner(&m, &operators);
    let circuit = m
        .circuit_with(&states, &operators.values(0.).unwrap())
        .unwrap();
    let solution = circuit.solve(&t.values(0.)).unwrap();
    (
        m,
        t,
        Controller {
            accepted: Frame {
                value_proofs: Default::default(),
                time_proofs: Default::default(),
                time: 0.,
                states,
                state_bounds: bounds,
                solution,
                circuit,
                operators,
            },
            event: 0,
            records: vec![],
            outputs: vec![],
        },
        calendar,
    )
}
fn nf_same_owner(m: &EventModel, ops: &Operators) {
    let source = m.source_context.as_ref().unwrap();
    let floor = &m.floor_source.as_ref().unwrap().source;
    assert!(Arc::ptr_eq(source, floor));
    let actual = ops.test_held_contexts();
    assert!(!actual.is_empty());
    for native in actual {
        assert!(Arc::ptr_eq(source, &native));
        // Same actual ProofContext object implies the same embedded Work. Compare
        // its borrowed field too, never pointers to separately cloned Work wrappers.
        assert!(std::ptr::eq(source.borrow_work(), native.borrow_work()));
        assert!(Arc::ptr_eq(&source.program_arc(), &native.program_arc()));
    }
}
fn nf_frame(f: &Frame) -> Value {
    json!({"time":f.time,"states":f.states,
        "bounds":f.state_bounds.iter().map(|b|[b.lo,b.hi]).collect::<Vec<_>>(),
        "solution":serde_json::to_value(&f.solution).unwrap(),
        "value_proofs":format!("{:?}",f.value_proofs),
        "time_proofs":format!("{:?}",f.time_proofs),
        // Existing test accessor includes stored curves/enclosures/segments/queue,
        // not merely Arc addresses or current scalar operator values.
        "history":format!("{:?}",f.operators.test_transition_histories())})
}
fn nf_signature(c: &Controller, calendar: &[ScheduledEvent]) -> Value {
    json!({"accepted":nf_frame(&c.accepted),"eventcursor":c.event,
        "records_and_display":serde_json::to_value(&c.records).unwrap(),
        "outputs":c.outputs.iter().map(nf_frame).collect::<Vec<_>>(),
        "calendar":calendar.iter().map(|e|json!([e.time,e.event,e.bounds().lo,e.bounds().hi,
            format!("{:?}",crate::schedule::common_root(std::slice::from_ref(e)))])).collect::<Vec<_>>()})
}
fn nf_copy_record(r: &EventRecord) -> EventRecord {
    EventRecord {
        time: r.time,
        observation_time_bounds: r.observation_time_bounds,
        event: r.event,
        origin: r.origin.clone(),
        kind: r.kind,
        guard_value: r.guard_value,
        fired_triggers: r
            .fired_triggers
            .iter()
            .map(|f| FiredTrigger {
                trigger: f.trigger,
                kind: f.kind,
                guard_value: f.guard_value,
                time_bounds: f.time_bounds,
            })
            .collect(),
        before: r.before.clone(),
        after: r.after.clone(),
        display_records: r.display_records.clone(),
    }
}
fn nf_both_consumers(r: &Report) {
    assert!(
        r.counters
            .get("floor_source_exact_decisions")
            .copied()
            .unwrap_or(0)
            > 0,
        "the actual original-tree Floor decision did not run"
    );
    assert!(
        r.counters
            .get("native29_actual_evaluate_calls")
            .copied()
            .unwrap_or(0)
            > 0,
        "the actual typed target point/box evaluator did not run"
    );
}

#[test]
fn native_floor_static_warm_late_voltage_failure_twice_and_legal_retry() {
    let (m, t, mut c, mut calendar) = nf_fixture();
    c.accept_changed_events(&m, &t, &mut calendar, event_acceptance::Strategy::Static)
        .unwrap();
    assert_eq!(c.accepted.states, [0., 0.]);
    assert_eq!(c.accepted.state_bounds, [I::point(0.), I::point(0.)]);
    assert!(!c.records.is_empty());
    assert_eq!(c.records[0].display_records[0].text, "q=0");
    assert!(
        !c.outputs.is_empty(),
        "warm accepted output prefix must be real"
    );
    let before = nf_signature(&c, &calendar);
    let history = c.accepted.operators.clone();
    // Clean comparison branches the SAME accepted prefix; it is not used for the
    // two failure attempts, and it shares the original request owner without refund.
    let mut clean = Controller {
        accepted: c.accepted.clone(),
        event: c.event,
        records: c.records.iter().map(nf_copy_record).collect(),
        outputs: c.outputs.clone(),
    };
    let mut clean_calendar = calendar.clone();
    let work = m.source_context.as_ref().unwrap().borrow_work();
    let start = work.spent();
    for retry in 0..2 {
        let hooks = Arc::new(AtomicUsize::new(0));
        let observed = hooks.clone();
        let expected_owner = m.source_context.as_ref().unwrap().clone();
        let old_history = history.test_transition_histories();
        let (answer, report) = capture(Options::default(), || {
            event_acceptance::test_with_final_candidate(
                move |next: &mut Frame| {
                    observed.fetch_add(1, Ordering::Relaxed);
                    assert_eq!(next.states, [1., 0.]);
                    assert_eq!(next.state_bounds, [I::point(1.), I::point(0.)]);
                    for actual in next.operators.test_held_contexts() {
                        assert!(Arc::ptr_eq(&expected_owner, &actual));
                    }
                    assert_ne!(next.operators.test_transition_histories(), old_history);
                    // Change only disposable final candidate. The real existing
                    // voltage gate below this hook must produce waveform_accuracy.
                    next.solution.voltages[2] += 0.01;
                },
                || {
                    c.accept_changed_events(
                        &m,
                        &t,
                        &mut calendar,
                        event_acceptance::Strategy::Static,
                    )
                },
            )
        });
        assert!(
            hooks.load(Ordering::Relaxed) > 0,
            "late production gate was never reached"
        );
        assert_eq!(answer.unwrap_err().kind, "waveform_accuracy");
        nf_both_consumers(&report);
        assert_eq!(nf_signature(&c, &calendar), before, "retry={retry}");
        assert!(c.accepted.operators.same_reset_history(&history));
        nf_same_owner(&m, &c.accepted.operators);
    }
    assert!(work.spent() > start, "failure must not refund shared Work");
    // Disable hook by leaving scoped guard. Retry on the ORIGINAL controller.
    c.accept_changed_events(&m, &t, &mut calendar, event_acceptance::Strategy::Static)
        .unwrap();
    clean
        .accept_changed_events(
            &m,
            &t,
            &mut clean_calendar,
            event_acceptance::Strategy::Static,
        )
        .unwrap();
    assert_eq!(
        nf_signature(&c, &calendar),
        nf_signature(&clean, &clean_calendar)
    );
    assert_eq!(c.accepted.states, [1., 0.]);
    assert_eq!(c.accepted.state_bounds, [I::point(1.), I::point(0.)]);
    assert!(c
        .records
        .iter()
        .flat_map(|r| &r.display_records)
        .any(|d| d.text == "q=1"));
    let v = c.accepted.operators.values(0.75).unwrap();
    let b = c.accepted.operators.bounds(0.75).unwrap();
    assert_eq!(v[0], 1.);
    assert_eq!(b[0], I::point(1.));
    nf_same_owner(&m, &c.accepted.operators);
    // Static strategy only. This does not certify Held/History calendars.
}

#[test]
fn native_floor_actual_mixed_prepare_naturally_exhausts_default_one_billion_then_two_retries() {
    let (m, t, mut c, mut calendar) = nf_fixture();
    c.accept_changed_events(&m, &t, &mut calendar, event_acceptance::Strategy::Static)
        .unwrap();
    let before = nf_signature(&c, &calendar);
    let owner = m.source_context.as_ref().unwrap().clone();
    let work = owner.borrow_work();
    let (answer, report) = capture(Options::default(), || {
        let mut prepares = 0;
        let mut totals = std::collections::BTreeMap::<&'static str, u64>::new();
        loop {
            prepares += 1;
            // Actual mixed callback+target preparation of the next fixed timer.
            // Do NOT debit Work manually, lower a cap, loop candidate_clone alone,
            // call an unrelated proof helper, or replace the Controller/owner.
            let prior_work = work.spent();
            let (attempt, one) =
                capture(Options::default(), || c.prepare_events(&m, &t, &calendar));
            for (name, n) in &one.counters {
                *totals.entry(*name).or_default() += *n;
            }
            match attempt {
                Ok((candidate, records, _)) => {
                    nf_both_consumers(&one);
                    assert!(
                        work.spent() > prior_work,
                        "actual mixed prepare added no charge"
                    );
                    assert_eq!(candidate.states, [1., 0.]);
                    assert_eq!(candidate.state_bounds, [I::point(1.), I::point(0.)]);
                    assert_eq!(records[0].display_records[0].text, "q=1");
                    nf_same_owner(&m, &candidate.operators);
                }
                Err(e) => {
                    assert_eq!(e.kind, "step_budget", "{}", e.message);
                    // If 128 plans or 8192 cuts fails first, preserve that failure:
                    // it is NOT a successful original Work-1e9 exhaustion result.
                    assert!(
                        work.spent() > 1_000_000_000,
                        "other cap exhausted first: {}",
                        e.message
                    );
                    assert!(e.message.contains("slot 2"), "{}", e.message);
                    break;
                }
            }
            assert!(
                prepares < 10000,
                "test watchdog only; no product cap change"
            );
            assert_eq!(nf_signature(&c, &calendar), before);
        }
        Ok::<_, crate::ir::Error>((prepares, totals))
    });
    let (prepares, totals) = answer.unwrap();
    // Nested capture reports may not merge into report; per-success assertions
    // above establish BOTH consumers on every successful mixed preparation.
    eprintln!(
        "mixed_default_work prepares={prepares} spent={} actual_totals={totals:?} outer={:?}",
        work.spent(),
        report.counters
    );
    for retry in 0..2 {
        let spent = work.spent();
        let (answer, retry_report) = capture(Options::default(), || {
            c.accept_changed_events(&m, &t, &mut calendar, event_acceptance::Strategy::Static)
        });
        assert_eq!(answer.unwrap_err().kind, "step_budget");
        assert_eq!(
            work.spent(),
            spent,
            "sticky failure must precede added debit"
        );
        // Actual no-new-work assertion, not just absence of a final output.
        for (name, n) in &retry_report.counters {
            assert!(
                *n == 0 || name.contains("exhausted"),
                "retry={retry}: {name}={n}"
            );
        }
        assert_eq!(nf_signature(&c, &calendar), before);
        nf_same_owner(&m, &c.accepted.operators);
        assert!(Arc::ptr_eq(m.source_context.as_ref().unwrap(), &owner));
        eprintln!(
            "mixed_default_retry={retry} counters={:?}",
            retry_report.counters
        );
    }
}
