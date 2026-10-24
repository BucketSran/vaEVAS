//! The RN witness belongs to a disposable candidate, not the accepted frame.
use super::*;
use crate::transition_source_plan::Work;

fn fixture() -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    let request: Request =
        serde_json::from_str(include_str!("testdata/rn_cell_gain_two.json")).unwrap();
    let model = EventModel::new_with_procedure_work(
        request.program,
        request.driven,
        request.tolerances,
        Work::default(),
    )
    .unwrap();
    let mut trajectory = Trajectory::new(request.transient.unwrap(), model.driven.len()).unwrap();
    trajectory
        .bind_procedure_work(crate::real_expression::work(&model))
        .unwrap();
    let states = model.initial();
    let operators = Operators::new(&model.program, &trajectory, &model.driven, &states).unwrap();
    let circuit = model.circuit_with(&states, &[]).unwrap();
    let inputs = crate::event_value_proof::history::inputs(&model, &trajectory, 0.).unwrap();
    let solution = circuit.solve(&inputs).unwrap();
    let calendar = independent_schedule(&model, &trajectory).unwrap();
    (
        model,
        trajectory,
        Controller {
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
        },
        calendar,
    )
}

#[test]
fn rn_cell_two_discarded_candidates_then_same_controller_legal_retry() {
    let (model, t, mut controller, mut calendar) = fixture();
    let (clean_model, clean_t, mut clean, mut clean_calendar) = fixture();
    let before = controller.accepted.clone();
    let calendar_before = calendar
        .iter()
        .map(|e| (e.event, e.time, e.bounds()))
        .collect::<Vec<_>>();
    let work = crate::real_expression::work(&model);
    let mut spent = work.spent();
    for _ in 0..2 {
        let seen = std::rc::Rc::new(std::cell::Cell::new(0));
        let count = seen.clone();
        let error = event_acceptance::test_with_final_candidate(
            move |frame| {
                count.set(count.get() + 1);
                let view = frame
                    .circuit
                    .procedure_occurrence()
                    .or_else(|| frame.circuit.procedure_view())
                    .unwrap();
                assert!(view.plan.test_cell_certificate().is_some());
                let y = frame.solution.voltages.len() - 1;
                frame.solution.voltages[y] += 0.25;
            },
            || {
                controller.accept_changed_events(
                    &model,
                    &t,
                    &mut calendar,
                    event_acceptance::Strategy::Static,
                )
            },
        )
        .unwrap_err();
        assert!(seen.get() > 0);
        assert_eq!(error.kind, "waveform_accuracy");
        assert_eq!(controller.accepted.time, before.time);
        assert_eq!(controller.accepted.states, before.states);
        assert_eq!(controller.accepted.state_bounds, before.state_bounds);
        assert_eq!(controller.accepted.value_proofs, before.value_proofs);
        assert_eq!(controller.accepted.time_proofs, before.time_proofs);
        assert_eq!(
            controller.accepted.solution.voltages,
            before.solution.voltages
        );
        assert_eq!(controller.event, 0);
        assert!(controller.records.is_empty());
        assert!(controller.outputs.is_empty());
        assert_eq!(
            calendar
                .iter()
                .map(|e| (e.event, e.time, e.bounds()))
                .collect::<Vec<_>>(),
            calendar_before
        );
        assert!(work.spent() > spent);
        spent = work.spent();
    }
    controller
        .accept_changed_events(
            &model,
            &t,
            &mut calendar,
            event_acceptance::Strategy::Static,
        )
        .unwrap();
    // A separate accepted frame, with its own request owner, is an independent
    // state oracle; use that model for the clean transaction as well.
    clean
        .accept_changed_events(
            &clean_model,
            &clean_t,
            &mut clean_calendar,
            event_acceptance::Strategy::Static,
        )
        .unwrap();
    assert_eq!(controller.accepted.states, vec![1., -1.]);
    assert_eq!(controller.accepted.states, clean.accepted.states);
    assert_eq!(
        controller.accepted.solution.voltages,
        clean.accepted.solution.voltages
    );
    assert_eq!(
        serde_json::to_value(&controller.records).unwrap(),
        serde_json::to_value(&clean.records).unwrap()
    );
    assert_eq!(controller.event, clean.event);
    let view = controller.accepted.circuit.procedure_occurrence().unwrap();
    let certificate = view.plan.test_cell_certificate().unwrap();
    let (root, proof_box) = certificate.test_witness();
    let y = model.program.nodes.iter().position(|n| n == "y").unwrap();
    assert_eq!(
        root[y],
        num_rational::BigRational::from_integer((-1).into())
    );
    assert!(proof_box[y].lo < root[y] && root[y] < proof_box[y].hi);
    assert!(certificate
        .matches(
            &[I::point(0.5)],
            &[I::point(0.), I::point(0.)],
            Some(
                &root
                    .iter()
                    .map(|r| num_traits::ToPrimitive::to_f64(r).unwrap())
                    .collect::<Vec<_>>()
            ),
            work
        )
        .unwrap());
    assert!(!certificate
        .matches(
            &[I { lo: 0.49, hi: 0.51 }],
            &[I::point(0.), I::point(0.)],
            None,
            work
        )
        .unwrap());
    assert_eq!(
        certificate
            .matches(
                &[I::point(0.5)],
                &[I::point(0.), I::point(0.)],
                None,
                &Work::default()
            )
            .unwrap_err()
            .kind,
        "invalid_ir"
    );
}
