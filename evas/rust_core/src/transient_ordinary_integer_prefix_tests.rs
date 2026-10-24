//! Actual public-produced ordinary integer prefix in the full Controller.
//! Fixture generation and its independent rational oracle live next to the VA.
use super::*;
use crate::diagnostics::{capture, Options, Report};
use serde_json::{json, Value};
use std::sync::{
    atomic::{AtomicUsize, Ordering},
    Arc,
};

fn slot(m: &EventModel, name: &str) -> usize {
    m.program
        .states
        .iter()
        .position(|s| s.instance == "M" && s.name == name)
        .unwrap()
}
fn node(m: &EventModel, name: &str) -> usize {
    m.program.nodes.iter().position(|n| n == name).unwrap()
}
fn fixture() -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    // This file is emitted by compile_sources, never synthesized in Rust.
    let request: Request = serde_json::from_str(include_str!(
        "../tests/fixtures/ordinary_integer_prefix_joint.request.json"
    ))
    .unwrap();
    let mut trajectory = Trajectory::new(request.transient.unwrap(), request.driven.len()).unwrap();
    let m = EventModel::new_with_trajectory(
        request.program,
        request.driven,
        request.tolerances,
        Some(&trajectory),
    )
    .unwrap();
    assert_eq!(m.typed_transition_targets.len(), 1);
    assert_eq!(m.program.operators.len(), 2);
    // Declaration seeds are zero in IR33. Execute the actual original
    // initial gate once through the same preparation used by public run,
    // before histories, retaining its explicit record and original Work.
    assert!(m.initial().iter().all(|&v|v==0.));
    trajectory.bind_procedure_work(crate::real_expression::work(&m)).unwrap();
    let prepared=initialization::prepare(&m,&trajectory).unwrap().unwrap();
    assert_eq!(prepared.records.len(),1);
    let initial=&prepared.records[0];
    assert_eq!(initial.kind,"initial_step");
    assert_eq!(initial.time,0.);
    assert!(initial.observation_time_bounds.is_none_or(|b|b==[0.,0.]));
    assert!(initial.guard_value.is_none() && initial.fired_triggers.is_empty());
    assert_eq!(initial.before,vec![0.;m.program.states.len()]);
    assert_eq!(initial.after,prepared.states);
    assert_eq!(prepared.states[slot(&m,"keep")],7.);
    assert_eq!(prepared.states[slot(&m,"ratio")],1.);
    let states=prepared.states.clone();
    let bounds=prepared.bounds.clone();
    let calendar = independent_schedule(&m, &trajectory).unwrap();
    assert_eq!(calendar.len(), 3);
    let cursor=prepared.cursor(&calendar).unwrap();
    assert_eq!(cursor,0,"initial gate must not consume the future timers");
    let owner = m.source_context.as_ref().unwrap().clone();
    // IR33 executes the original RN Floor/store/clamp through procedures,
    // not the legacy mathematical Floor request. Both still share the same
    // original owner with the typed Transition transaction.
    assert!(m.floor_source.is_none());
    assert!(owner.borrow_work().same_owner(m.mixed_cold_work.get().unwrap()));
    let operators = Operators::new_until_with_held_points(
        &m.program,
        &trajectory,
        &m.driven,
        &states,
        &bounds,
        &m.typed_transition_targets,
        owner,
        trajectory.config.stop,
        &m.tolerances,
    )
    .unwrap();
    same_owner(&m, &operators);
    let circuit = m
        .circuit_with(&states, &operators.values(0.).unwrap())
        .unwrap();
    let solution = circuit.solve(&trajectory.values(0.)).unwrap();
    let controller = Controller {
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
        event: cursor,
        records: prepared.records,
        outputs: vec![],
    };
    (m, trajectory, controller, calendar)
}
fn same_owner(m: &EventModel, operators: &Operators) {
    let context = m.source_context.as_ref().unwrap();
    assert!(m.floor_source.is_none());
    assert!(context.borrow_work().same_owner(m.mixed_cold_work.get().unwrap()));
    assert!(Arc::ptr_eq(context,operators.source_context.as_ref().unwrap()));
    let held = operators.test_held_contexts();
    assert_eq!(held.len(), 1);
    for actual in held {
        assert!(Arc::ptr_eq(context, &actual));
        assert!(std::ptr::eq(context.borrow_work(), actual.borrow_work()));
        assert!(Arc::ptr_eq(&context.program_arc(), &actual.program_arc()));
    }
    // Both typed and unrelated plain Transition histories must be present.
    assert_eq!(operators.test_transition_histories().len(), 2);
}
fn frame(f: &Frame) -> Value {
    json!({"time":f.time,"states":f.states,
        "state_bounds":f.state_bounds.iter().map(|b|[b.lo,b.hi]).collect::<Vec<_>>(),
        "solution":f.solution,"certified_voltage_bounds":f.solution.certified_voltage_bounds,
        "circuit":f.circuit.forcing_frame_snapshot(),
        "value_proofs":format!("{:?}",f.value_proofs),
        "time_proofs":format!("{:?}",f.time_proofs),
        // Transition's full Debug/PartialEq includes queued segments, retained
        // exact/enclosure data and all past changes, not just current values.
        "all_transition_histories":format!("{:?}",f.operators.test_transition_histories()),
        "source_context_identity":f.operators.source_context.as_ref().map(|c|Arc::as_ptr(c) as usize)})
}
fn signature(c: &Controller, calendar: &[ScheduledEvent]) -> Value {
    json!({"accepted":frame(&c.accepted),"event_cursor":c.event,
        "records_and_displays":c.records,"outputs":c.outputs.iter().map(frame).collect::<Vec<_>>(),
        "calendar":calendar.iter().map(ScheduledEvent::analytic_test_snapshot).collect::<Vec<_>>()})
}
fn normalize_clean(value: &mut Value) {
    match value {
        Value::Object(map) => {
            // Only independently rebuilt factor allocation addresses differ.
            map.remove("affine_factor_identity");
            for child in map.values_mut() {
                normalize_clean(child);
            }
        }
        Value::Array(items) => {
            for child in items {
                normalize_clean(child);
            }
        }
        _ => (),
    }
}
fn unchanged_frame(actual: &Frame, expected: &Frame) {
    assert_eq!(frame(actual), frame(expected));
    assert!(actual.operators.same_reset_history(&expected.operators));
    // Covers complete Runtime input, bounds, owner and private AffineState Eq
    // as well as retained held-spec/context identities and lifecycle flags.
    assert!(actual.operators.same_forcing_frame(&expected.operators));
    assert_eq!(
        actual.operators.test_transition_histories(),
        expected.operators.test_transition_histories()
    );
}
fn unchanged(
    c: &Controller,
    calendar: &[ScheduledEvent],
    before: &Value,
    accepted: &Frame,
    outputs: &[Frame],
) {
    assert_eq!(signature(c, calendar), *before);
    unchanged_frame(&c.accepted, accepted);
    assert_eq!(c.outputs.len(), outputs.len());
    for (a, b) in c.outputs.iter().zip(outputs) {
        unchanged_frame(a, b);
    }
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
fn typed_target_evaluated(report: &Report) {
    // Floor/store/clamp correctness is asserted on the original source
    // results and first-store overflow below, rather than a legacy counter.
    assert!(
        report
            .counters
            .get("native29_actual_evaluate_calls")
            .copied()
            .unwrap_or(0)
            > 0,
        "the actual typed point/box evaluator did not execute"
    );
}
fn expected(m: &EventModel, f: &Frame, ratio: f64, q: f64, spare: f64) {
    for (name, value) in [("ratio", ratio), ("q", q), ("keep", 7.), ("spare", spare)] {
        let index = slot(m, name);
        assert_eq!(f.states[index], value, "{name}");
        assert_eq!(f.state_bounds[index], I::point(value), "{name}");
    }
}
fn warm(m: &EventModel, t: &Trajectory, c: &mut Controller, calendar: &mut Vec<ScheduledEvent>) {
    c.accept_changed_events(m, t, calendar, event_acceptance::Strategy::Static)
        .unwrap();
    expected(m, &c.accepted, 1., 1., 0.25);
    assert!(!c.records.is_empty());
    assert_eq!(c.records.last().unwrap().display_records[0].text, "ratio=1 q=1 keep=7");
    assert!(
        !c.outputs.is_empty(),
        "warm accepted output prefix must be real"
    );
    same_owner(m, &c.accepted.operators);
}

#[test]
fn public_integer_prefix_two_late_failures_then_retry_preserves_complete_frame() {
    // The first selected ratio store must reject signed32 overflow before the
    // following min-clamp can hide a negative value. Original source is intact;
    // only this negative control's physical input levels change.
    for value in [-1e9,1e9] {
        let mut wire:Value=serde_json::from_str(include_str!("../tests/fixtures/ordinary_integer_prefix_joint.request.json")).unwrap();
        for point in wire["transient"]["pwl"][0].as_array_mut().unwrap() {
            point[1]=json!(value);
        }
        let request:Request=serde_json::from_value(wire).unwrap();
        let ratio=request.program.states.iter().position(|s|s.name=="ratio").unwrap();
        let error=crate::run(request).err().unwrap();
        assert_eq!(error.kind,"integer_range");
        assert!(error.message.contains(&format!("state {ratio}")));
    }
    let (m, t, mut c, mut calendar) = fixture();
    warm(&m, &t, &mut c, &mut calendar);
    let before = signature(&c, &calendar);
    let accepted = c.accepted.clone();
    let outputs = c.outputs.clone();
    let mut clean = Controller {
        accepted: c.accepted.clone(),
        event: c.event,
        records: c.records.iter().map(copy_record).collect(),
        outputs: c.outputs.clone(),
    };
    let mut clean_calendar = calendar.clone();
    let owner = m.source_context.as_ref().unwrap().clone();
    let work = owner.borrow_work();
    let original_spent = work.spent();
    let y = node(&m, "y");
    for retry in 0..2 {
        let seen = Arc::new(AtomicUsize::new(0));
        let hook_seen = seen.clone();
        let old_histories = accepted.operators.test_transition_histories();
        let expected_owner = owner.clone();
        let before_fee = work.spent();
        let (answer, report) = capture(Options::default(), || {
            event_acceptance::test_with_final_candidate(
                move |candidate: &mut Frame| {
                    hook_seen.fetch_add(1, Ordering::Relaxed);
                    assert_ne!(
                        candidate.operators.test_transition_histories(),
                        old_histories
                    );
                    for actual in candidate.operators.test_held_contexts() {
                        assert!(Arc::ptr_eq(&expected_owner, &actual));
                    }
                    // The sole fault changes a disposable final candidate. The
                    // existing production waveform_accuracy gate rejects it.
                    candidate.solution.voltages[y] += 0.01;
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
        assert!(seen.load(Ordering::Relaxed) > 0);
        assert_eq!(answer.unwrap_err().kind, "waveform_accuracy");
        typed_target_evaluated(&report);
        assert!(
            work.spent() > before_fee,
            "retry={retry} refunded shared work"
        );
        unchanged(&c, &calendar, &before, &accepted, &outputs);
        same_owner(&m, &c.accepted.operators);
    }
    assert!(work.spent() > original_spent);
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
    expected(&m, &c.accepted, 3., 3., 0.75);
    assert_eq!(
        c.records.last().unwrap().display_records[0].text,
        "ratio=3 q=3 keep=7"
    );
    let mut actual = signature(&c, &calendar);
    let mut independent = signature(&clean, &clean_calendar);
    normalize_clean(&mut actual);
    normalize_clean(&mut independent);
    assert_eq!(actual, independent);
    assert!(c
        .accepted
        .operators
        .same_reset_history(&clean.accepted.operators));
    assert!(c
        .accepted
        .operators
        .same_forcing_frame(&clean.accepted.operators));
    let values = c.accepted.operators.values(0.75).unwrap();
    let bounds = c.accepted.operators.bounds(0.75).unwrap();
    assert_eq!(values, [1., 0.75]);
    assert_eq!(bounds, [I::point(1.), I::point(0.75)]);
    same_owner(&m, &c.accepted.operators);
}

#[test]
fn public_integer_prefix_natural_default_work_then_two_sticky_full_frame_retries() {
    let (m, t, mut c, mut calendar) = fixture();
    warm(&m, &t, &mut c, &mut calendar);
    let before = signature(&c, &calendar);
    let accepted = c.accepted.clone();
    let outputs = c.outputs.clone();
    let owner = m.source_context.as_ref().unwrap().clone();
    let work = owner.borrow_work();
    let mut attempts = 0;
    loop {
        attempts += 1;
        let prior = work.spent();
        let (answer, report) = capture(Options::default(), || c.prepare_events(&m, &t, &calendar));
        match answer {
            Ok((candidate, records, _)) => {
                typed_target_evaluated(&report);
                assert!(work.spent() > prior);
                expected(&m, &candidate, 3., 3., 0.75);
                assert_eq!(records[0].display_records[0].text, "ratio=3 q=3 keep=7");
                same_owner(&m, &candidate.operators);
            }
            Err(error) => {
                assert_eq!(error.kind, "step_budget", "{}", error.message);
                assert!(
                    work.spent() > 1_000_000_000,
                    "another cap exhausted first: {}",
                    error.message
                );
                assert!(error.message.contains("slot 2"), "{}", error.message);
                break;
            }
        }
        assert!(
            attempts < 10000,
            "test watchdog, never a product cap change"
        );
        unchanged(&c, &calendar, &before, &accepted, &outputs);
    }
    for retry in 0..2 {
        let spent = work.spent();
        let (answer, report) = capture(Options::default(), || {
            c.accept_changed_events(&m, &t, &mut calendar, event_acceptance::Strategy::Static)
        });
        assert_eq!(answer.unwrap_err().kind, "step_budget");
        assert_eq!(
            work.spent(),
            spent,
            "sticky failure must precede fresh work"
        );
        for (name, n) in &report.counters {
            assert!(
                *n == 0 || name.contains("exhausted"),
                "retry={retry}: {name}={n}"
            );
        }
        unchanged(&c, &calendar, &before, &accepted, &outputs);
        same_owner(&m, &c.accepted.operators);
        assert!(Arc::ptr_eq(&owner, m.source_context.as_ref().unwrap()));
    }
    eprintln!(
        "ordinary_integer_prefix actual_preparations={attempts} original_work_spent={}",
        work.spent()
    );
}
