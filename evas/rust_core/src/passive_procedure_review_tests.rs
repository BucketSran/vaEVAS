//! Real source model: active integer write, nonzero idt history and an isolated
//! observer with a selected, later-overwritten divide. No fresh-process retry.
use super::*;
use crate::transition_source_plan::Work;
use serde_json::{json, Value};
use std::sync::Arc;

fn fixture(
    work: Work,
) -> (
    EventModel,
    Trajectory,
    Trajectory,
    Controller,
    Vec<ScheduledEvent>,
) {
    let bad: Request = serde_json::from_str(include_str!("passive_procedure_bad.json")).unwrap();
    let good: Request = serde_json::from_str(include_str!("passive_procedure_good.json")).unwrap();
    assert_eq!(
        serde_json::to_value(&bad.program).unwrap(),
        serde_json::to_value(&good.program).unwrap()
    );
    let mut trajectory = Trajectory::new(bad.transient.unwrap(), bad.driven.len()).unwrap();
    trajectory.bind_procedure_work(&work).unwrap();
    let mut good_trajectory = Trajectory::new(good.transient.unwrap(), good.driven.len()).unwrap();
    good_trajectory.bind_procedure_work(&work).unwrap();
    let model =
        EventModel::new_with_procedure_work(bad.program, bad.driven, bad.tolerances, work.clone())
            .unwrap();
    assert!(work.same_owner(crate::real_expression::work(&model)));
    let states = model.initial();
    let state_bounds = states.iter().copied().map(I::point).collect::<Vec<_>>();
    let operators = Operators::new(&model.program, &trajectory, &model.driven, &states).unwrap();
    assert_eq!(operators.values(0.).unwrap(), [0.25]);
    let inputs = trajectory.checked_value_bounds(0.).unwrap();
    let circuit = model
        .circuit_at(&states, &operators.values(0.).unwrap(), &inputs)
        .unwrap();
    let solution = circuit.solve(&trajectory.values(0.)).unwrap();
    let calendar = independent_schedule(&model, &trajectory).unwrap();
    assert_eq!(calendar.len(), 2);
    let controller = Controller {
        accepted: Frame {
            value_proofs: Default::default(),
            time_proofs: Default::default(),
            time: 0.,
            states,
            state_bounds,
            solution,
            circuit,
            operators,
        },
        event: 0,
        records: Vec::new(),
        outputs: Vec::new(),
    };
    (model, trajectory, good_trajectory, controller, calendar)
}
fn snapshot(controller: &Controller, calendar: &[ScheduledEvent]) -> Value {
    json!({"time":controller.accepted.time,"states":controller.accepted.states,
        "bounds":controller.accepted.state_bounds.iter().map(|b|[b.lo,b.hi]).collect::<Vec<_>>(),
        "solution":controller.accepted.solution,"proofs":format!("{:?}{:?}",controller.accepted.value_proofs,controller.accepted.time_proofs),
        "cursor":controller.event,"records":controller.records,"outputs":controller.outputs.len(),
        "queue":calendar.iter().map(ScheduledEvent::analytic_test_snapshot).collect::<Vec<_>>()})
}
#[test]
fn passive_procedure_review_two_failed_trials_then_same_controller_legal_retry() {
    let work = Work::default();
    let (model, bad, good, mut controller, calendar) = fixture(work.clone());
    let before = snapshot(&controller, &calendar);
    let history = controller.accepted.operators.clone();
    let binding = controller
        .accepted
        .circuit
        .procedure_view()
        .unwrap()
        .clone();
    let mut spent = work.spent();
    for _ in 0..2 {
        assert_eq!(
            controller
                .accept_events(&model, &bad, &calendar)
                .unwrap_err()
                .kind,
            "real_arithmetic"
        );
        assert_eq!(snapshot(&controller, &calendar), before);
        assert!(Arc::ptr_eq(
            controller.accepted.circuit.procedure_view().unwrap(),
            &binding
        ));
        assert!(controller.accepted.operators.same_reset_history(&history));
        assert_eq!(controller.accepted.operators.values(0.75).unwrap(), [1.]);
        assert!(work.spent() > spent);
        spent = work.spent();
    }
    controller.accept_events(&model, &good, &calendar).unwrap();
    let (clean_model, _, clean_good, mut clean, clean_calendar) = fixture(Work::default());
    clean
        .accept_events(&clean_model, &clean_good, &clean_calendar)
        .unwrap();
    assert_eq!(
        snapshot(&controller, &calendar),
        snapshot(&clean, &clean_calendar)
    );
    assert!(controller
        .accepted
        .operators
        .same_reset_history(&clean.accepted.operators));
    assert_eq!(controller.accepted.states, [3., 3.75, 2., 1.]);
    assert_eq!(controller.event, 2);
    assert_eq!(controller.records.len(), 2);
    assert_eq!(
        controller
            .records
            .iter()
            .flat_map(|r| r.display_records.iter())
            .map(|r| r.text.as_str())
            .collect::<Vec<_>>(),
        ["sample 3.75 2 1"]
    );
    let occurrence = controller.accepted.circuit.procedure_occurrence().unwrap();
    assert_eq!(&occurrence.plan.base[..], &[I::ZERO; 4]);
    assert_eq!(occurrence.plan.actions.len(), 2);
    assert!(occurrence.plan.work.same_owner(&work));
    println!("same Controller rollback: state/bounds/solution/proofs/binding/history/queue/records/output unchanged twice; Work spent {spent}; legal retry equal clean");
}
#[test]
fn passive_procedure_review_exact_original_owner_budget_is_sticky_before_publication() {
    let original = Work::default();
    let (model, _, good, controller, calendar) = fixture(original.clone());
    controller.prepare_events(&model, &good, &calendar).unwrap();
    let limit = original.spent() - 1;
    let work = Work::limited([128, 8192, limit]);
    let (model, _, good, mut controller, calendar) = fixture(work.clone());
    let before = snapshot(&controller, &calendar);
    let mut spent = work.spent();
    for _ in 0..2 {
        assert_eq!(
            controller
                .accept_events(&model, &good, &calendar)
                .unwrap_err()
                .kind,
            "step_budget"
        );
        assert_eq!(snapshot(&controller, &calendar), before);
        assert!(work.spent() > spent);
        spent = work.spent();
    }
    assert!(crate::real_expression::work(&model).same_owner(&work));
    println!(
        "actual same-owner cap-1={limit} rejects before commit; retry spent={spent}, no refund"
    );
}
