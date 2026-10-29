//! A driven sampled predicate shares the real Controller transaction and original Work.
use super::*;
use crate::diagnostics::{capture, Options};
use crate::ir::{Program, Tolerances, TransientInputs};
use serde_json::{json, Value};

fn fixture() -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    let o = json!({"source":"sampled_predicate.va","line":1,"column":1,"instance":"M"});
    let constant = |x| json!({"op":"affine","constant":x,"terms":[]});
    let p: Program = serde_json::from_value(json!({
        "schema_version":SCHEMA_VERSION,"nodes":["0","u","y","z"],
        "states":[{"instance":"M","name":"q","kind":"real","initial":0}],
        "events":[{"trigger":{"kind":"timer","start":0.125,"period":0,"enabled":true,"time_tolerance":1e-9},"origin":o,
            "body":[{"kind":"assign","state":0,"rhs":{"op":"affine","constant":0.25,"terms":[{"node":1,"coefficient":1}]}}]},
            {"trigger":{"kind":"timer","start":0.25,"period":0,"enabled":true,"time_tolerance":1e-9},"origin":o,
            "body":[{"kind":"assign","state":0,"rhs":{"op":"affine","constant":0.25,"terms":[{"node":1,"coefficient":1}]}}]}],
        "operators":[{"kind":"transition","input":{"op":"state","state":0},"delay":0,"rise":0.125,"fall":0.125,"origin":o}],
        "contributions":[
            {"branch":{"instance":"M","local_positive":"out_y","local_negative":"ref","kind":"voltage"},"positive":2,"negative":0,
                "rhs":{"op":"select","relation":"gt","left":{"op":"add","left":{"op":"state","state":0},"right":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":-1}]}},"right":constant(0.125),"then_value":constant(1.),"else_value":constant(0.),"origin":o},"origin":o},
            {"branch":{"instance":"M","local_positive":"out_z","local_negative":"ref","kind":"voltage"},"positive":3,"negative":0,"rhs":{"op":"operator","operator":0},"origin":o}]
    })).unwrap();
    let t = Trajectory::new(
        TransientInputs {
            analytic_sources: vec![],
            pwl_errors_v: None,
            strobetimes: vec![],
            pwl: vec![vec![[0., 0.], [1., 1.]]],
            output_times: vec![0., 0.0625, 0.1875, 1.],
            stop: 1.,
            max_step: 0.125,
            proof_work_limit: None,
        },
        1,
    )
    .unwrap();
    let m = EventModel::new_with_trajectory(p, vec!["u".into()], Tolerances::default(), Some(&t))
        .unwrap();
    let states = m.initial();
    let bounds = states.iter().copied().map(I::point).collect::<Vec<_>>();
    let (ops, calendar) = history_calendar::initialize(&m, &t, &states).unwrap();
    let inputs = t.values(0.);
    let circuit = m
        .circuit_at(
            &states,
            &ops.values(0.).unwrap(),
            &inputs.iter().copied().map(I::point).collect::<Vec<_>>(),
        )
        .unwrap();
    let solution = circuit.solve(&inputs).unwrap();
    let controller = Controller {
        accepted: Frame {
            value_proofs: Default::default(),
            time_proofs: Default::default(),
            time: 0.,
            states,
            state_bounds: bounds,
            solution,
            circuit,
            operators: ops,
        },
        event: 0,
        records: vec![],
        outputs: vec![],
    };
    (m, t, controller, calendar)
}

fn warm(m: &EventModel, t: &Trajectory, c: &mut Controller, calendar: &mut Vec<ScheduledEvent>) {
    c.accept_changed_events(m, t, calendar, event_acceptance::Strategy::Static)
        .unwrap();
    assert_eq!(c.event, 1);
    assert!(
        !c.records.is_empty(),
        "warm event must publish a real event record"
    );
    assert!(
        !c.outputs.is_empty(),
        "warm event must prepare a real earlier output query"
    );
    assert_eq!(c.outputs[0].time, 0.0625);
    assert_eq!(c.outputs[0].states, [0.]);
    assert_eq!(c.accepted.states, [0.375]);
}

// Keep every solution field (including internal transported bounds), circuit
// equations/tolerances/cache identity, proof map, transition, queue and output.
fn frame(f: &Frame) -> Value {
    json!({"time":f.time,"states":f.states,"bounds":f.state_bounds.iter().map(|b|[b.lo,b.hi]).collect::<Vec<_>>(),
        "value_proofs":format!("{:?}",f.value_proofs),"time_proofs":format!("{:?}",f.time_proofs),
        "solution":f.solution,"certified_voltage_bounds":f.solution.certified_voltage_bounds,
        "circuit":f.circuit.forcing_frame_snapshot(),
        "transitions":format!("{:?}",f.operators.test_transition_histories()),
        "source_owner":f.operators.source_context.as_ref().map(|c|std::sync::Arc::as_ptr(c) as usize)})
}
fn signature(c: &Controller, calendar: &[ScheduledEvent]) -> Value {
    json!({"accepted":frame(&c.accepted),"event":c.event,"records":c.records,
        "outputs":c.outputs.iter().map(frame).collect::<Vec<_>>(),
        "calendar":calendar.iter().map(ScheduledEvent::analytic_test_snapshot).collect::<Vec<_>>()})
}
fn without_rebuilt_cache_addresses(mut value: Value) -> Value {
    fn visit(v: &mut Value) {
        match v {
            Value::Object(m) => {
                if let Some(id) = m.get_mut("affine_factor_identity") {
                    if !id.is_null() {
                        *id = json!(0);
                    }
                }
                for child in m.values_mut() {
                    visit(child);
                }
            }
            Value::Array(a) => {
                for child in a {
                    visit(child);
                }
            }
            _ => {}
        }
    }
    visit(&mut value);
    value
}
fn copy_record(r: &EventRecord) -> EventRecord {
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

#[test]
fn sampled_predicate_same_controller_two_late_failures_then_legal_retry() {
    let (m, t, mut c, mut calendar) = fixture();
    warm(&m, &t, &mut c, &mut calendar);
    let before = signature(&c, &calendar);
    let history = c.accepted.operators.clone();
    let mut clean = Controller {
        accepted: c.accepted.clone(),
        event: c.event,
        records: c.records.iter().map(copy_record).collect(),
        outputs: c.outputs.clone(),
    };
    let mut clean_calendar = calendar.clone();
    let source = c
        .accepted
        .operators
        .source_context
        .as_ref()
        .unwrap()
        .clone();
    let work = source.borrow_work();
    let start = work.spent();
    for _ in 0..2 {
        let (mut candidate, _, end) = c
            .prepare_events_until(&m, &t, &calendar, Some(calendar[c.event].time))
            .unwrap();
        assert!((candidate.states[0] - 0.5).abs() < 1e-12);
        let pending = calendar[end..].to_vec();
        c.prepare_physical_history(&m, &t, &mut candidate, &calendar[c.event..end], &pending)
            .unwrap();
        assert_ne!(
            candidate.operators.test_transition_histories(),
            history.test_transition_histories()
        );
        assert!(std::sync::Arc::ptr_eq(
            candidate.operators.source_context.as_ref().unwrap(),
            &source
        ));
        // The production final voltage check must fail after real event and
        // history preparation. Only the disposable candidate is perturbed.
        candidate.solution.voltages[2] += 0.01;
        let error = Controller::prepare_final_history(
            &m,
            &t,
            candidate,
            event_acceptance::CalendarPlan::Held(pending),
        )
        .err()
        .unwrap();
        assert_eq!(error.kind, "waveform_accuracy");
        assert_eq!(signature(&c, &calendar), before);
        assert!(c.accepted.operators.same_reset_history(&history));
    }
    assert!(work.spent() > start);
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
        without_rebuilt_cache_addresses(signature(&c, &calendar)),
        without_rebuilt_cache_addresses(signature(&clean, &clean_calendar))
    );
    assert!(c
        .accepted
        .operators
        .same_reset_history(&clean.accepted.operators));
}

#[test]
fn sampled_predicate_natural_original_work_exhaustion_and_two_sticky_retries() {
    let (answer, report) = capture(Options::default(), || {
        let (m, t, mut c, mut calendar) = fixture();
        warm(&m, &t, &mut c, &mut calendar);
        let before = signature(&c, &calendar);
        let history = c.accepted.operators.clone();
        let source = c
            .accepted
            .operators
            .source_context
            .as_ref()
            .unwrap()
            .clone();
        let work = source.borrow_work();
        let mut tries = 0;
        loop {
            tries += 1;
            match c.prepare_events(&m, &t, &calendar) {
                Ok(_) => {}
                Err(e) => {
                    assert_eq!(e.kind, "step_budget");
                    break;
                }
            }
            assert!(
                tries < 1_000_000,
                "original request accounting never reached its unmodified limit"
            );
        }
        assert!(work.spent() > 1_000_000_000);
        let spent = work.spent();
        let (_, retry) = capture(Options::default(), || {
            for _ in 0..2 {
                assert_eq!(
                    c.prepare_events(&m, &t, &calendar).err().unwrap().kind,
                    "step_budget"
                );
                assert_eq!(work.spent(), spent);
                assert_eq!(signature(&c, &calendar), before);
                assert!(c.accepted.operators.same_reset_history(&history));
            }
            Ok(())
        });
        for name in [
            "source_predicate_qualified_events",
            "floor_source_helper_calls",
            "floor_source_copy",
        ] {
            assert!(
                !retry.counters.contains_key(name),
                "exhausted retry did new work: {name}"
            );
        }
        eprintln!(
            "sampled_predicate_natural_tries={tries} retry={}",
            serde_json::to_string(&retry.counters).unwrap()
        );
        Ok(tries)
    });
    answer.unwrap();
    assert!(
        report
            .counters
            .get("source_predicate_qualified_events")
            .copied()
            .unwrap_or(0)
            > 0
    );
    eprintln!(
        "sampled_predicate_accounting={}",
        serde_json::to_string(&report.counters).unwrap()
    );
}
