//! Captured source-position input through the production Controller transaction.
use super::*;
use serde_json::{json, Value};
fn fixture() -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    let r: Request = serde_json::from_str(include_str!(
        "../tests/fixtures/ir33_history_lifecycle.json"
    ))
    .unwrap();
    let mut t = Trajectory::new(r.transient.unwrap(), r.driven.len()).unwrap();
    let m = EventModel::new_with_trajectory(r.program, r.driven, r.tolerances, Some(&t)).unwrap();
    t.bind_procedure_work(crate::real_expression::work(&m))
        .unwrap();
    let states = m.initial();
    let bounds = states.iter().copied().map(I::point).collect::<Vec<_>>();
    let ops = Operators::new_until_with_source_context(
        &m.program,
        &t,
        &m.driven,
        &states,
        1.,
        &m.tolerances,
        m.source_context.clone(),
    )
    .unwrap();
    let values = ops.values(0.).unwrap();
    let op_bounds = ops.bounds(0.).unwrap();
    let circuit = m
        .circuit_at_procedure_observation(
            &states,
            &bounds,
            &values,
            &op_bounds,
            &t.checked_value_bounds(0.).unwrap(),
            &t,
            0.,
        )
        .unwrap();
    let solution = circuit.solve(&t.checked_values(0.).unwrap()).unwrap();
    let calendar = independent_schedule(&m, &t).unwrap();
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
    assert_eq!(controller.accepted.operators.test_source_cursors().len(), 1);
    (m, t, controller, calendar)
}
fn signature(c: &Controller, calendar: &[ScheduledEvent]) -> Value {
    json!({"states":c.accepted.states,"time":c.accepted.time,
        "bounds":c.accepted.state_bounds.iter().map(|b|[b.lo,b.hi]).collect::<Vec<_>>(),
        "values":format!("{:?}",c.accepted.value_proofs),"times":format!("{:?}",c.accepted.time_proofs),
        "solution":c.accepted.solution,"voltage_bounds":c.accepted.solution.certified_voltage_bounds,
        "histories":format!("{:?}",c.accepted.operators.test_transition_histories()),
        "cursors":c.accepted.operators.test_source_cursors(),"event":c.event,"records":c.records,
        "outputs":c.outputs.iter().map(|f|json!([f.time,f.states,f.solution.voltages])).collect::<Vec<_>>(),
        "calendar":calendar.iter().map(|e|json!([e.time,e.event,e.bounds().lo,e.bounds().hi])).collect::<Vec<_>>()})
}
#[test]
fn procedure_history_two_late_rejections_then_legal_retry_preserve_accepted_cursor() {
    let (m, t, mut c, mut calendar) = fixture();
    let (cm, ct, mut clean, mut clean_calendar) = fixture();
    let before = signature(&c, &calendar);
    let work = crate::real_expression::work(&m);
    let start = work.spent();
    for _ in 0..2 {
        let error = event_acceptance::test_with_final_candidate(
            |frame| {
                assert_eq!(frame.states, [1.]);
                assert_eq!(frame.operators.test_source_cursors()[0]["target"], 1.);
                let y = frame.solution.voltages.len() - 1;
                frame.solution.voltages[y] += 0.01;
            },
            || c.accept_changed_events(&m, &t, &mut calendar, event_acceptance::Strategy::Static),
        )
        .unwrap_err();
        assert_eq!(error.kind, "waveform_accuracy");
        assert_eq!(signature(&c, &calendar), before);
    }
    assert!(work.spent() > start);
    c.accept_changed_events(&m, &t, &mut calendar, event_acceptance::Strategy::Static)
        .unwrap();
    clean
        .accept_changed_events(
            &cm,
            &ct,
            &mut clean_calendar,
            event_acceptance::Strategy::Static,
        )
        .unwrap();
    assert_eq!(signature(&c, &calendar), signature(&clean, &clean_calendar));
    assert_eq!(c.accepted.operators.values(0.5625).unwrap(), [0.5]);
    assert_eq!(c.accepted.operators.values(0.75).unwrap(), [1.]);
}
#[test]
fn procedure_history_exhausted_original_owner_stays_exhausted_across_two_retries() {
    let (m, t, c, calendar) = fixture();
    let before = signature(&c, &calendar);
    let work = crate::real_expression::work(&m);
    // Exhaust the original default request owner, rather than replacing it
    // with a fresh small allowance on a candidate or rebind.
    work.debit(2, 1_000_000_000 - work.spent()).unwrap();
    for _ in 0..2 {
        assert_eq!(
            c.prepare_events(&m, &t, &calendar).err().unwrap().kind,
            "step_budget"
        );
        assert_eq!(signature(&c, &calendar), before);
    }
    let (cm, ct, mut clean, mut clean_calendar) = fixture();
    clean
        .accept_changed_events(
            &cm,
            &ct,
            &mut clean_calendar,
            event_acceptance::Strategy::Static,
        )
        .unwrap();
    assert_eq!(clean.accepted.states, [1.]);
}
