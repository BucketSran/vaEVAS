//! Public-structure analytic source values in the real Controller transaction.
use super::*;
use serde_json::{json, Value};
fn fixture() -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    let r: Request =
        serde_json::from_str(include_str!("../tests/analytic_lifecycle_request.json")).unwrap();
    let work = crate::transition_source_plan::Work::default();
    let config = r.transient.unwrap();
    crate::analytic_source::charge_config(&config, &work).unwrap();
    let t = Trajectory::new_with_work(config, r.driven.len(), Some(work.clone())).unwrap();
    let token = crate::analytic_request::Request::prepare(&r.program, &t, &r.driven).unwrap();
    let p =
        crate::initialization::resolve(r.program, &r.driven, &t.checked_value_bounds(0.).unwrap())
            .unwrap();
    crate::event_floor::check_provided_binding(token.context(), &p, &t, &r.driven).unwrap();
    let m = EventModel::new_with_context(
        p,
        r.driven,
        r.tolerances,
        Some(&t),
        Some(token.context().clone()),
    )
    .unwrap();
    let m = token.activate(m, &t).unwrap();
    assert!(m.history_admission.is_none() && m.floor_source.is_none() && m.forcing.is_none());
    let states = m.initial();
    let state_bounds = states.iter().copied().map(I::point).collect::<Vec<_>>();
    let operators = Operators::new_until_with_source_context(
        &m.program,
        &t,
        &m.driven,
        &states,
        1.,
        &m.tolerances,
        Some(token.context().clone()),
    )
    .unwrap();
    assert!(work.same_owner(token.work()));
    assert!(work.same_owner(t.analytic_work().unwrap()));
    assert!(work.same_owner(operators.history_copy_work().unwrap()));
    assert!(std::sync::Arc::ptr_eq(
        operators.source_context.as_ref().unwrap(),
        token.context()
    ));
    let circuit = m
        .circuit_at(&states, &[], &t.checked_value_bounds(0.).unwrap())
        .unwrap();
    let solution = circuit.solve(&t.checked_values(0.).unwrap()).unwrap();
    let frame = Frame {
        value_proofs: Default::default(),
        time_proofs: Default::default(),
        time: 0.,
        states,
        state_bounds,
        solution,
        circuit,
        operators,
    };
    let c = Controller {
        accepted: frame,
        event: 0,
        records: vec![],
        outputs: vec![],
    };
    let calendar = independent_schedule(&m, &t).unwrap();
    assert_eq!(calendar.len(), 2);
    (m, t, c, calendar)
}
fn frame(f: &Frame) -> Value {
    json!({"time":f.time,"states":f.states,"state_bounds":f.state_bounds.iter().map(|i|[i.lo,i.hi]).collect::<Vec<_>>(),"value_proofs":format!("{:?}",f.value_proofs),"time_proofs":format!("{:?}",f.time_proofs),"solution":f.solution,"certified_voltage_bounds":f.solution.certified_voltage_bounds,"circuit":f.circuit.forcing_frame_snapshot(),"operators":f.operators.analytic_empty_snapshot(),"original_context_caches":f.operators.source_context.as_ref().unwrap().analytic_cache_snapshot()})
}
fn signature(c: &Controller, calendar: &[ScheduledEvent]) -> Value {
    json!({"accepted":frame(&c.accepted),"event":c.event,"records":c.records,"outputs":c.outputs.iter().map(frame).collect::<Vec<_>>(),"calendar":calendar.iter().map(ScheduledEvent::analytic_test_snapshot).collect::<Vec<_>>()})
}
fn normalize(v: &mut Value) {
    match v {
        Value::Object(map) => {
            map.remove("affine_factor_identity");
            map.remove("source_context");
            for child in map.values_mut() {
                normalize(child);
            }
        }
        Value::Array(items) => {
            for item in items {
                normalize(item);
            }
        }
        _ => (),
    }
}
#[test]
fn analytic_original_allowance_natural_exhaustion_preserves_complete_frame_and_two_retries() {
    let (m, t, mut c, mut calendar) = fixture();
    c.accept_changed_events(&m, &t, &mut calendar, event_acceptance::Strategy::Static)
        .unwrap();
    assert_eq!(c.records.len(), 1);
    assert_eq!(c.event, 1);
    assert!(!c.outputs.is_empty());
    // Physical sine at t=1/6 is 1/2+sqrt(3)/8. Its complete mathematical
    // image rounds to this unique binary64 at the source sample and store.
    // A stored binary proof must not be the unrounded irrational source value.
    let expected = 0.7165063509461097;
    assert_eq!(c.accepted.states[0], expected);
    assert_eq!(c.accepted.state_bounds[0], I::point(expected));
    if let Some(proof) = c.accepted.value_proofs.get(&0) {
        assert_eq!(
            proof,
            &num_rational::BigRational::from_float(expected).unwrap()
        );
    }
    let before = signature(&c, &calendar);
    let (cm, ct, mut clean, mut clean_calendar) = fixture();
    clean
        .accept_changed_events(
            &cm,
            &ct,
            &mut clean_calendar,
            event_acceptance::Strategy::Static,
        )
        .unwrap();
    let mut a = before.clone();
    let mut b = signature(&clean, &clean_calendar);
    normalize(&mut a);
    normalize(&mut b);
    assert_eq!(a, b);
    let w = m.analytic_request.as_ref().unwrap().work();
    let mut attempts = 0;
    loop {
        attempts += 1;
        match c.prepare_events(&m, &t, &calendar) {
            Ok(_) => (),
            Err(e) => {
                assert_eq!(e.kind, "step_budget");
                break;
            }
        }
        assert!(attempts < 10_000);
    }
    assert!(
        w.spent() > 1_000_000_000,
        "production original allowance must exhaust naturally"
    );
    assert_eq!(signature(&c, &calendar), before);
    for _ in 0..2 {
        let spent = w.spent();
        assert_eq!(
            c.accept_changed_events(&m, &t, &mut calendar, event_acceptance::Strategy::Static)
                .unwrap_err()
                .kind,
            "step_budget"
        );
        assert!(w.spent() >= spent);
        assert_eq!(signature(&c, &calendar), before);
        assert_eq!(
            c.refine_pending_input_root(&m, &t, &mut calendar)
                .unwrap_err()
                .kind,
            "step_budget"
        );
        assert_eq!(signature(&c, &calendar), before);
    }
    println!("analytic natural exhaustion: sources=33, original_limit=1000000000, attempts={attempts}, spent={}, accepted_events={}, outputs={}",w.spent(),c.records.len(),c.outputs.len());
}
#[test]
fn analytic_original_binding_still_rejects_initial_program_rewrite() {
    let (m, t, _, _) = fixture();
    let mut changed = m.program.clone();
    changed.states[0].initial = 0.125.into();
    let token = m.analytic_request.as_ref().unwrap();
    assert_eq!(
        crate::event_floor::check_provided_binding(token.context(), &changed, &t, &m.driven)
            .unwrap_err()
            .kind,
        "invalid_ir"
    );
}
#[test]
fn analytic_original_binding_rejects_source_order_and_driven_order_changes() {
    let (m, t, _, _) = fixture();
    let token = m.analytic_request.as_ref().unwrap();
    let mut changed = t.clone();
    changed.config.analytic_sources.swap(0, 2);
    assert_eq!(
        crate::event_floor::check_provided_binding(
            token.context(),
            &m.program,
            &changed,
            &m.driven
        )
        .unwrap_err()
        .kind,
        "invalid_ir"
    );
    let mut names = m.driven.clone();
    names.swap(0, 2);
    assert_eq!(
        crate::event_floor::check_provided_binding(token.context(), &m.program, &t, &names)
            .unwrap_err()
            .kind,
        "invalid_ir"
    );
}

// Reuse the original public source geometry and tolerances. Only event kind and
// the receiving held operator change; no fresh quota is introduced for history.
pub(super) fn sampled_transition_fixture(
) -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    let mut wire: Value =
        serde_json::from_str(include_str!("../tests/analytic_lifecycle_request.json")).unwrap();
    for (event, start) in wire["program"]["events"]
        .as_array_mut()
        .unwrap()
        .iter_mut()
        .zip([0.125, 0.75])
    {
        event["trigger"] = json!({"kind":"timer", "start":start, "period":0,
            "time_tolerance":1e-12, "enabled":true});
    }
    let origin = wire["program"]["events"][0]["origin"].clone();
    wire["program"]["operators"] = json!([{"kind":"transition",
        "input":{"op":"state","state":0}, "delay":0,
        "rise":0.125, "fall":0.125, "origin":origin}]);
    // Keep the original voltage branch orientation and its negative sign.
    wire["program"]["contributions"][0]["rhs"]["right"] = json!({"op":"operator","operator":0});
    // Request binding includes this real pre-timer observation. Publication may
    // replace seeded outputs with this batch, so generate a nonempty batch too.
    wire["transient"]["output_times"]
        .as_array_mut()
        .unwrap()
        .insert(1, json!(0.03125));
    let r: Request = serde_json::from_value(wire).unwrap();
    let work = crate::transition_source_plan::Work::default();
    let config = r.transient.unwrap();
    crate::analytic_source::charge_config(&config, &work).unwrap();
    let t = Trajectory::new_with_work(config, r.driven.len(), Some(work.clone())).unwrap();
    let token = crate::analytic_request::Request::prepare(&r.program, &t, &r.driven).unwrap();
    assert!(token.fixed_timer_held_transitions());
    let p =
        crate::initialization::resolve(r.program, &r.driven, &t.checked_value_bounds(0.).unwrap())
            .unwrap();
    crate::event_floor::check_provided_binding(token.context(), &p, &t, &r.driven).unwrap();
    let m = EventModel::new_with_context(
        p,
        r.driven,
        r.tolerances,
        Some(&t),
        Some(token.context().clone()),
    )
    .unwrap();
    let m = token.activate(m, &t).unwrap();
    assert!(m.history_admission.is_none() && m.floor_source.is_none() && m.forcing.is_none());
    let states = m.initial();
    let state_bounds = states.iter().copied().map(I::point).collect::<Vec<_>>();
    let operators = Operators::new_until_with_analytic_request(
        &token,
        &m.program,
        &t,
        &m.driven,
        &states,
        Some(&state_bounds),
        &m.typed_transition_targets,
        1.,
        &m.tolerances,
    )
    .unwrap();
    assert!(work.same_owner(token.work()));
    assert!(work.same_owner(t.analytic_work().unwrap()));
    assert!(work.same_owner(operators.history_copy_work().unwrap()));
    assert!(std::sync::Arc::ptr_eq(
        operators.source_context.as_ref().unwrap(),
        token.context()
    ));
    let circuit = m
        .circuit_at(
            &states,
            &operators.values(0.).unwrap(),
            &t.checked_value_bounds(0.).unwrap(),
        )
        .unwrap();
    let solution = circuit.solve(&t.checked_values(0.).unwrap()).unwrap();
    let accepted = Frame {
        value_proofs: Default::default(),
        time_proofs: Default::default(),
        time: 0.,
        states,
        state_bounds,
        solution,
        circuit,
        operators,
    };
    // Timers need not publish a phase output. Keep an explicit accepted initial
    // output so rejected candidates must preserve nonempty output history.
    let c = Controller {
        outputs: vec![accepted.clone()],
        accepted,
        event: 0,
        records: vec![],
    };
    let calendar = independent_schedule(&m, &t).unwrap();
    assert_eq!(calendar.len(), 2);
    (m, t, c, calendar)
}

// Compare real nonempty operator frames directly, without querying a rejected
// owner's provider or using analytic_empty_snapshot.
pub(super) fn sampled_transition_unchanged(a: &Frame, b: &Frame) {
    assert_eq!(a.time, b.time);
    assert_eq!(a.states, b.states);
    assert_eq!(a.state_bounds, b.state_bounds);
    assert_eq!(a.value_proofs, b.value_proofs);
    assert_eq!(a.time_proofs, b.time_proofs);
    assert_eq!(
        serde_json::to_value(&a.solution).unwrap(),
        serde_json::to_value(&b.solution).unwrap()
    );
    assert_eq!(
        a.circuit.forcing_frame_snapshot(),
        b.circuit.forcing_frame_snapshot()
    );
    assert!(a.operators.same_reset_history(&b.operators));
    assert!(a.operators.same_forcing_frame(&b.operators));
    assert_eq!(
        a.operators
            .source_context
            .as_ref()
            .unwrap()
            .analytic_cache_snapshot(),
        b.operators
            .source_context
            .as_ref()
            .unwrap()
            .analytic_cache_snapshot()
    );
}

#[test]
fn analytic_sampled_transition_original_allowance_two_failed_retries_preserve_full_frame() {
    let (m, t, mut c, mut calendar) = sampled_transition_fixture();
    c.accept_changed_events(&m, &t, &mut calendar, event_acceptance::Strategy::Static)
        .unwrap();
    assert_eq!(c.event, 1);
    assert_eq!(c.records.len(), 1);
    assert!(!c.outputs.is_empty());
    // The physical sine value .5+sqrt(2)/8 is irrational; its selected
    // sample/store is the unique binary64 value independently bracketed
    // using an integer sqrt at512bits (not the native sine representative).
    let expected = 0.6767766952966369;
    assert_eq!(c.accepted.states[0], expected);
    assert_eq!(c.accepted.state_bounds[0].lo, expected);
    assert_eq!(c.accepted.state_bounds[0].hi, expected);
    if let Some(proof) = c.accepted.value_proofs.get(&0) {
        assert_eq!(proof, &crate::exact_source::binary(expected).unwrap());
    }
    // The accepted sample actually reaches the Transition, including its error.
    let values = c.accepted.operators.values(0.25).unwrap();
    let bounds = c.accepted.operators.bounds(0.25).unwrap();
    assert_eq!(values.len(), 1);
    assert_eq!(values[0], c.accepted.states[0]);
    assert!(bounds[0].lo <= c.accepted.state_bounds[0].lo);
    assert!(bounds[0].hi >= c.accepted.state_bounds[0].hi);
    let before = c.accepted.clone();
    let outputs = c.outputs.clone();
    let event = c.event;
    let records = serde_json::to_value(&c.records).unwrap();
    let calendar_before = calendar
        .iter()
        .map(ScheduledEvent::analytic_test_snapshot)
        .collect::<Vec<_>>();
    let cache_before = c
        .accepted
        .operators
        .source_context
        .as_ref()
        .unwrap()
        .analytic_cache_snapshot();
    let w = m.analytic_request.as_ref().unwrap().work();
    let mut attempts = 0;
    loop {
        attempts += 1;
        match c.prepare_events(&m, &t, &calendar) {
            Ok(_) => (),
            Err(error) => {
                assert_eq!(error.kind, "step_budget");
                break;
            }
        }
        assert!(attempts < 10_000);
    }
    assert!(
        attempts > 1 && w.spent() > 1_000_000_000,
        "exhaust original shared allowance by actual sampled candidate work"
    );
    for _ in 0..2 {
        let spent = w.spent();
        assert_eq!(
            c.accept_changed_events(&m, &t, &mut calendar, event_acceptance::Strategy::Static)
                .unwrap_err()
                .kind,
            "step_budget"
        );
        assert!(w.spent() >= spent);
        sampled_transition_unchanged(&before, &c.accepted);
        assert_eq!(c.event, event);
        assert_eq!(serde_json::to_value(&c.records).unwrap(), records);
        assert_eq!(c.outputs.len(), outputs.len());
        for (a, b) in c.outputs.iter().zip(&outputs) {
            sampled_transition_unchanged(a, b);
        }
        assert_eq!(
            calendar
                .iter()
                .map(ScheduledEvent::analytic_test_snapshot)
                .collect::<Vec<_>>(),
            calendar_before
        );
        assert_eq!(
            c.accepted
                .operators
                .source_context
                .as_ref()
                .unwrap()
                .analytic_cache_snapshot(),
            cache_before
        );
    }
    println!(
        "sampled Transition original_limit=1000000000, attempts={attempts}, spent={}",
        w.spent()
    );
}
