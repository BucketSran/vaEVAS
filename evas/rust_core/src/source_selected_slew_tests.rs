//! A failed future calendar cannot publish a selected-slew candidate or record.
use super::*;
use crate::ir::{Program, Tolerances, TransientInputs};
use serde_json::json;

fn fixture(due: f64, period: f64) -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    fixture_with_dc(due, period, false)
}

fn fixture_with_dc(
    due: f64,
    period: f64,
    dc: bool,
) -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    let physical = json!({"source":"selected.va","line":1,"column":1,"instance":"D"});
    let observer = json!({"source":"selected.va","line":2,"column":1,"instance":"M"});
    let constant = |value: f64| json!({"op":"affine","constant":value,"terms":[]});
    let voltage = json!({"op":"affine","constant":0,"terms":[{"node":2,"coefficient":1}]});
    let program: Program = serde_json::from_value(json!({
        "schema_version":SCHEMA_VERSION,"nodes":if dc {vec!["0","u","y","v"]} else {vec!["0","u","y"]},
        "operators":[{"kind":"slew","rise":1,"fall":-2,"origin":physical,
            "input":{"op":"select","relation":"gt","origin":physical,
                "left":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]},
                "right":constant(0.25),"then_value":if dc {json!({"op":"affine","constant":0.,"terms":[{"node":3,"coefficient":1.}]})} else {constant(1.)},"else_value":constant(0.)}}],
        "states":[{"instance":"M","name":"seen","kind":"real","initial":0},
            {"instance":"M","name":"due","kind":"real","initial":2}],
        "contributions":[{"branch":{"instance":"D","local_positive":"out","local_negative":"ref","kind":"voltage"},
            "positive":2,"negative":0,"rhs":{"op":"operator","operator":0},"origin":physical}],
        "events":[{"origin":observer,"trigger":{"kind":"timer","start":0.5,"period":0,"time_tolerance":0.001,"enabled":true},
            "body":[{"kind":"assign","state":0,"rhs":voltage},
                {"kind":"assign","state":1,"rhs":constant(due)},
                {"kind":"display","format":"selected %g","args":[{"op":"state","state":0}],"origin":observer}]},
            {"origin":observer,"trigger":{"kind":"held_timer","start":{"op":"state","state":1},"period":constant(period),"enabled":constant(1.),"time_tolerance":0.001},
                "body":[{"kind":"assign","state":0,"rhs":constant(2.)}]}]
    })).unwrap();
    let driven = if dc {
        vec!["u".into(), "v".into()]
    } else {
        vec!["u".into()]
    };
    let count = driven.len();
    let model = EventModel::new(program, driven, Tolerances::default()).unwrap();
    let trajectory = Trajectory::new(
        TransientInputs {
            pwl_errors_v: None,
            strobetimes: vec![],
            pwl: if dc {
                vec![vec![[0., 0.], [1., 1.]], vec![[0., 1.], [1., 1.]]]
            } else {
                vec![vec![[0., 0.], [1., 1.]]]
            },
            output_times: vec![0., 0.5, 1.],
            stop: 1.,
            max_step: 1.,
        },
        count,
    )
    .unwrap();
    let states = model.initial();
    let state_bounds = states.iter().copied().map(I::point).collect::<Vec<_>>();
    let operators = Operators::new(&model.program, &trajectory, &model.driven, &states).unwrap();
    let circuit = model
        .circuit_with(&states, &operators.values(0.).unwrap())
        .unwrap();
    let mut controller = Controller {
        accepted: Frame {
            value_proofs: Default::default(),
            time_proofs: Default::default(),
            time: 0.,
            solution: circuit.solve(&trajectory.values(0.)).unwrap(),
            circuit,
            states,
            state_bounds,
            operators,
        },
        event: 0,
        records: vec![],
        outputs: vec![],
    };
    // Accept the original source threshold before the late observer candidate.
    let root = crate::exact_source::RootTime::point(0.25).unwrap();
    let next = prepare_root_window(
        &model,
        &trajectory,
        &controller.accepted,
        EventMoment {
            exact_root: Some(&root),
            representative: 0.25,
            observation: I::point(0.25),
            fired_roots: &[],
            prediction_end: 0.5,
        },
        &[],
    )
    .unwrap();
    controller.commit_events(next, vec![], 0);
    let calendar = schedule_held(&model, &trajectory, &controller.accepted.state_bounds).unwrap();
    (model, trajectory, controller, calendar)
}

#[test]
fn selected_slew_history_observation_and_late_failure_retry_are_atomic() {
    check_late_failure_retry(false);
}

#[test]
fn physical_dc_slew_history_and_late_failure_retry_are_atomic() {
    check_late_failure_retry(true);
}

fn check_late_failure_retry(dc: bool) {
    let make = |due, period| {
        if dc {
            fixture_with_dc(due, period, true)
        } else {
            fixture(due, period)
        }
    };
    let (bad, trajectory, mut controller, mut calendar) = make(-1., 1.);
    let before = controller.accepted.clone();
    let signature = |c: &Vec<ScheduledEvent>| {
        c.iter()
            .map(|e| (e.event, e.time, e.bounds()))
            .collect::<Vec<_>>()
    };
    let queue = signature(&calendar);
    let (candidate, records, _) = controller
        .prepare_events(&bad, &trajectory, &calendar)
        .unwrap();
    assert_eq!(candidate.time, 0.5);
    assert_eq!(candidate.states, [0.25, -1.]);
    assert!(records
        .iter()
        .any(|record| !record.display_records.is_empty()));
    assert_eq!(candidate.operators.values(0.75).unwrap(), [0.5]);
    for _ in 0..2 {
        let error = controller
            .accept_relocalized(&bad, &trajectory, &mut calendar)
            .unwrap_err();
        assert_eq!(error.kind, "event_resolution");
        assert_eq!(
            error.message,
            "cannot certify dynamic timer start or period regime"
        );
        assert_eq!(controller.accepted.time, before.time);
        assert_eq!(controller.accepted.states, before.states);
        assert_eq!(controller.accepted.state_bounds, before.state_bounds);
        assert_eq!(controller.accepted.value_proofs, before.value_proofs);
        assert_eq!(controller.accepted.time_proofs, before.time_proofs);
        assert_eq!(
            controller.accepted.solution.voltages,
            before.solution.voltages
        );
        assert!(controller
            .accepted
            .operators
            .same_reset_history(&before.operators));
        assert!(controller.records.is_empty() && controller.outputs.is_empty());
        assert_eq!(controller.event, 0);
        assert_eq!(signature(&calendar), queue);
    }
    let (good, _, mut clean, mut clean_calendar) = make(0.75, 0.);
    controller
        .accept_relocalized(&good, &trajectory, &mut calendar)
        .unwrap();
    clean
        .accept_relocalized(&good, &trajectory, &mut clean_calendar)
        .unwrap();
    assert_eq!(controller.accepted.states, [0.25, 0.75]);
    assert_eq!(controller.accepted.states, clean.accepted.states);
    assert_eq!(
        controller.accepted.state_bounds,
        clean.accepted.state_bounds
    );
    assert_eq!(
        controller.accepted.value_proofs,
        clean.accepted.value_proofs
    );
    assert_eq!(controller.accepted.time_proofs, clean.accepted.time_proofs);
    assert_eq!(
        serde_json::to_value(&controller.records).unwrap(),
        serde_json::to_value(&clean.records).unwrap()
    );
    assert_eq!(signature(&calendar), signature(&clean_calendar));
    for time in [0.5, 0.625, 0.75, 1.] {
        assert_eq!(
            controller.accepted.operators.values(time).unwrap(),
            clean.accepted.operators.values(time).unwrap()
        );
        assert_eq!(
            controller.accepted.operators.bounds(time).unwrap(),
            clean.accepted.operators.bounds(time).unwrap()
        );
    }
    controller
        .accept_relocalized(&good, &trajectory, &mut calendar)
        .unwrap();
    assert_eq!(controller.accepted.states, [2., 0.75]);
}
