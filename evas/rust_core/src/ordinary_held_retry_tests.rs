//! Public frontend fixture: if (V(s)>0.5) q=1; V(y)<+q; V(z)<+idt(2,3).
//! s is the triangle (0,0),(1,1),(2,0),(3,0); default q=0, r=0.
//! The falling root must commit q=1 without changing the independent integral.
use super::*;
use serde_json::{json, Value};

fn fixture() -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    let request: Request =
        serde_json::from_str(include_str!("../tests/fixtures/ordinary_held_retry.json")).unwrap();
    let mut trajectory = Trajectory::new(request.transient.unwrap(), request.driven.len()).unwrap();
    let model = EventModel::new_with_trajectory(
        request.program,
        request.driven,
        request.tolerances,
        Some(&trajectory),
    )
    .unwrap();
    trajectory
        .bind_procedure_work(crate::real_expression::work(&model))
        .unwrap();
    let states = model.initial();
    let operators = Operators::new(&model.program, &trajectory, &model.driven, &states).unwrap();
    let circuit = model
        .circuit_at(
            &states,
            &operators.values(0.).unwrap(),
            &trajectory.checked_value_bounds(0.).unwrap(),
        )
        .unwrap();
    let solution = circuit
        .solve(&trajectory.checked_values(0.).unwrap())
        .unwrap();
    let calendar = independent_schedule(&model, &trajectory).unwrap();
    assert_eq!(calendar.len(), 2);
    let controller = Controller {
        accepted: Frame {
            value_proofs: Default::default(),
            time_proofs: Default::default(),
            time: 0.,
            state_bounds: states.iter().copied().map(I::point).collect(),
            states,
            solution,
            circuit,
            operators,
        },
        event: 0,
        records: vec![],
        outputs: vec![],
    };
    (model, trajectory, controller, calendar)
}

fn signature(c: &Controller, calendar: &[ScheduledEvent]) -> Value {
    json!({"time":c.accepted.time,"states":c.accepted.states,
        "bounds":c.accepted.state_bounds.iter().map(|b|[b.lo,b.hi]).collect::<Vec<_>>(),
        "solution":c.accepted.solution,
        "proofs":format!("{:?}{:?}",c.accepted.value_proofs,c.accepted.time_proofs),
        "cursor":c.event,"records":c.records,
        "outputs":c.outputs.iter().map(|f|json!([f.time,f.states,f.solution.voltages])).collect::<Vec<_>>(),
        "calendar":calendar.iter().map(ScheduledEvent::analytic_test_snapshot).collect::<Vec<_>>()})
}

#[test]
fn ordinary_held_two_rejected_falling_trials_then_same_controller_retry() {
    let (m, t, mut c, mut calendar) = fixture();
    let (clean_m, clean_t, mut clean, mut clean_calendar) = fixture();
    c.accept_changed_events(&m, &t, &mut calendar, event_acceptance::Strategy::Static)
        .unwrap();
    clean
        .accept_changed_events(
            &clean_m,
            &clean_t,
            &mut clean_calendar,
            event_acceptance::Strategy::Static,
        )
        .unwrap();
    assert_eq!(c.accepted.states, [0.]);
    let before = signature(&c, &calendar);
    let history = c.accepted.operators.clone();
    let work = crate::real_expression::work(&m);
    let mut spent = work.spent();
    let y = m.program.nodes.iter().position(|n| n == "y").unwrap();
    for _ in 0..2 {
        let error = event_acceptance::test_with_final_candidate(
            move |frame| {
                assert_eq!(frame.states, [1.]);
                assert_eq!(frame.operators.values(2.).unwrap(), [7.]);
                frame.solution.voltages[y] += 0.25;
            },
            || c.accept_changed_events(&m, &t, &mut calendar, event_acceptance::Strategy::Static),
        )
        .unwrap_err();
        assert_eq!(error.kind, "waveform_accuracy");
        assert_eq!(signature(&c, &calendar), before);
        assert!(c.accepted.operators.same_reset_history(&history));
        assert!(work.spent() > spent);
        spent = work.spent();
    }
    c.accept_changed_events(&m, &t, &mut calendar, event_acceptance::Strategy::Static)
        .unwrap();
    clean
        .accept_changed_events(
            &clean_m,
            &clean_t,
            &mut clean_calendar,
            event_acceptance::Strategy::Static,
        )
        .unwrap();
    assert_eq!(signature(&c, &calendar), signature(&clean, &clean_calendar));
    assert_eq!(c.accepted.states, [1.]);
    assert_eq!(c.accepted.operators.values(3.).unwrap(), [9.]);
    assert!(c
        .accepted
        .operators
        .same_reset_history(&clean.accepted.operators));
}
