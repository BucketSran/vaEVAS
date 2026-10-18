//! Same Controller retries after new rational transition history was prepared.
use super::*;
use crate::ir::{Tolerances, TransientInputs};

fn fixture(good: bool) -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    let program = serde_json::from_str(if good {
        include_str!("../../tests/fixtures/rational-transition-rollback/good.json")
    } else {
        include_str!("../../tests/fixtures/rational-transition-rollback/bad.json")
    })
    .unwrap();
    let model = EventModel::new(
        program,
        vec!["u".into()],
        Tolerances {
            absolute: 1e-12,
            relative: 0.,
        },
    )
    .unwrap();
    let trajectory = Trajectory::new(
        TransientInputs {
            pwl_errors_v: None,
            strobetimes: vec![],
            pwl: vec![vec![[0., 0.16], [1., 0.16]]],
            output_times: vec![0., 0.125, 0.2, 0.5],
            stop: 0.6,
            max_step: 0.05,
        },
        1,
    )
    .unwrap();
    let states = model.initial();
    let state_bounds = states.iter().copied().map(I::point).collect::<Vec<_>>();
    let operators = Operators::new(&model.program, &trajectory, &model.driven, &states).unwrap();
    let circuit = model
        .circuit_with(&states, &operators.values(0.).unwrap())
        .unwrap();
    let solution = circuit.solve(&trajectory.values(0.)).unwrap();
    let mut controller = Controller {
        accepted: Frame {
            states,
            state_bounds,
            operators,
            circuit,
            solution,
            time: 0.,
            value_proofs: Default::default(),
            time_proofs: Default::default(),
        },
        event: 0,
        records: vec![],
        outputs: vec![],
    };
    let mut calendar =
        schedule_held(&model, &trajectory, &controller.accepted.state_bounds).unwrap();
    controller
        .accept_relocalized(&model, &trajectory, &mut calendar)
        .unwrap();
    assert_eq!(controller.accepted.time, 0.1);
    assert!(controller.accepted.value_proofs.contains_key(&0));
    assert!(controller.accepted.state_bounds[0].lo < controller.accepted.state_bounds[0].hi);
    (model, trajectory, controller, calendar)
}

fn signature(calendar: &[ScheduledEvent]) -> Vec<(usize, u64, u64, u64)> {
    calendar
        .iter()
        .map(|e| {
            (
                e.event,
                e.time.to_bits(),
                e.bounds().lo.to_bits(),
                e.bounds().hi.to_bits(),
            )
        })
        .collect()
}
fn same_frame(a: &Frame, b: &Frame) {
    assert_eq!(a.time, b.time);
    assert_eq!(a.states, b.states);
    assert_eq!(a.state_bounds, b.state_bounds);
    assert_eq!(a.value_proofs, b.value_proofs);
    assert_eq!(a.time_proofs, b.time_proofs);
    assert_eq!(a.solution.voltages, b.solution.voltages);
    assert!(a.operators.same_reset_history(&b.operators));
    for t in [0.125, 0.175, 0.2, 0.24, 0.5] {
        assert_eq!(
            a.operators.values(t).unwrap(),
            b.operators.values(t).unwrap()
        );
        assert_eq!(
            a.operators.bounds(t).unwrap(),
            b.operators.bounds(t).unwrap()
        );
    }
}

#[test]
fn rational_transition_late_calendar_failure_retries_same_controller_without_publication() {
    let (bad, trajectory, mut controller, mut calendar) = fixture(false);
    let before = controller.accepted.clone();
    let queue = signature(&calendar);
    let old_records = serde_json::to_value(&controller.records).unwrap();
    let (candidate, records, _) = controller
        .prepare_events(&bad, &trajectory, &calendar)
        .unwrap();
    assert_eq!(candidate.time, 0.15);
    assert_eq!(candidate.states[2], -1.);
    assert_ne!(candidate.value_proofs[&0], before.value_proofs[&0]);
    assert!(records.iter().any(|r| !r.display_records.is_empty()));
    assert!((candidate.operators.values(0.2).unwrap().iter().sum::<f64>() - 0.081).abs() < 1e-14);
    assert_ne!(
        candidate.operators.values(0.2).unwrap(),
        before.operators.values(0.2).unwrap()
    );
    for _ in 0..2 {
        let error = controller
            .accept_relocalized(&bad, &trajectory, &mut calendar)
            .unwrap_err();
        assert_eq!(error.kind, "event_resolution");
        assert!(error
            .message
            .contains("dynamic timer start or period regime"));
        same_frame(&controller.accepted, &before);
        assert_eq!(signature(&calendar), queue);
        assert_eq!(
            serde_json::to_value(&controller.records).unwrap(),
            old_records
        );
        assert!(controller.outputs.is_empty());
        assert_eq!(controller.event, 0);
    }
    let (good, _, mut clean, mut clean_calendar) = fixture(true);
    controller
        .accept_relocalized(&good, &trajectory, &mut calendar)
        .unwrap();
    clean
        .accept_relocalized(&good, &trajectory, &mut clean_calendar)
        .unwrap();
    same_frame(&controller.accepted, &clean.accepted);
    assert_eq!(signature(&calendar), signature(&clean_calendar));
    assert_eq!(
        serde_json::to_value(&controller.records).unwrap(),
        serde_json::to_value(&clean.records).unwrap()
    );
    assert_eq!(controller.accepted.time, 0.15);
    assert_eq!(controller.accepted.states[2], 0.5);
    assert_eq!(controller.outputs.len(), clean.outputs.len());
    for (a, b) in controller.outputs.iter().zip(&clean.outputs) {
        same_frame(a, b);
    }
}

#[test]
fn rational_value_maps_must_match_their_own_old_and_candidate_state_boxes() {
    let (_, _, controller, _) = fixture(true);
    let before = controller.accepted;
    let mut wrong = before.value_proofs.clone();
    wrong.insert(0, crate::exact_source::binary(1.).unwrap());
    let mut old = before.operators.clone();
    let error = old
        .advance_old(
            before.time,
            I::point(before.time),
            &before.states,
            &before.state_bounds,
            None,
            Some(&wrong),
        )
        .unwrap_err();
    assert_eq!(error.kind, "event_resolution");
    assert!(error
        .message
        .contains("value proof outside matching state enclosure"));
    assert_eq!(
        old.values(0.2).unwrap(),
        before.operators.values(0.2).unwrap()
    );
    let error = before
        .operators
        .evaluation(before.time)
        .unwrap()
        .advanced_until_with_value_proofs(
            I::point(before.time),
            &before.states,
            &before.state_bounds,
            &[],
            0.6,
            None,
            Some(&before.time_proofs),
            Some(&wrong),
        )
        .err()
        .unwrap();
    assert_eq!(error.kind, "event_resolution");
    assert!(error
        .message
        .contains("value proof outside matching candidate state enclosure"));
}
