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
    assert!(
        c.accepted.state_bounds[0].lo < 0.7165063509461097
            && c.accepted.state_bounds[0].hi > 0.7165063509461096
    );
    assert!(
        c.accepted.value_proofs.is_empty(),
        "irrational sine sample must not acquire a rational value proof"
    );
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
