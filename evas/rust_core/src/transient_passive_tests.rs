//! Observer state, records and its timer calendar form the physical transaction.
use super::*;
use crate::ir::{Program, Tolerances, TransientInputs};
use serde_json::json;

fn fixture(due: f64) -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    let physical = json!({"source":"passive.va","line":1,"column":1,"instance":"D"});
    let observer = json!({"source":"passive.va","line":2,"column":1,"instance":"M"});
    let constant = |value: f64| json!({"op":"affine","constant":value,"terms":[]});
    let timer =
        json!({"kind":"timer","start":0.5,"period":0,"time_tolerance":0.001,"enabled":true});
    let voltage = json!({"op":"affine","constant":0,"terms":[{"node":2,"coefficient":1}]});
    let program: Program = serde_json::from_value(json!({
        "schema_version":SCHEMA_VERSION,"nodes":["0","u","y"],"operators":[],
        "states":[{"instance":"D","name":"q","kind":"real","initial":0},
            {"instance":"M","name":"seen","kind":"real","initial":0},
            {"instance":"M","name":"due","kind":"real","initial":2}],
        "contributions":[{"branch":{"instance":"D","local_positive":"out","local_negative":"ref","kind":"voltage"},
            "positive":2,"negative":0,"rhs":{"op":"state","state":0},"origin":physical}],
        "events":[{"origin":physical,"trigger":timer,"body":[{"kind":"assign","state":0,"rhs":constant(1.)}]},
            {"origin":observer,"trigger":timer,"body":[{"kind":"if","relation":"gt","left":voltage,"right":constant(0.5),
                "origin":observer,"then_body":[{"kind":"assign","state":1,"rhs":voltage},
                    {"kind":"assign","state":2,"rhs":constant(due)},
                    {"kind":"display","format":"seen %g","args":[{"op":"state","state":1}],"origin":observer}],"else_body":[]}]},
            {"origin":observer,"trigger":{"kind":"held_timer","start":{"op":"state","state":2},"period":constant(0.),"enabled":constant(1.),"time_tolerance":0.001},
                "body":[{"kind":"assign","state":1,"rhs":constant(2.)}]}]
    })).unwrap();
    let model = EventModel::new(program, vec!["u".into()], Tolerances::default()).unwrap();
    let trajectory = Trajectory::new(
        TransientInputs {
            strobetimes: vec![],
            pwl: vec![vec![[0., 0.], [1., 1.]]],
            output_times: vec![0., 0.25, 1.],
            stop: 1.,
            max_step: 1.,
        },
        1,
    )
    .unwrap();
    let states = model.initial();
    let state_bounds = states.iter().copied().map(I::point).collect::<Vec<_>>();
    let circuit = model.circuit(&states).unwrap();
    let calendar = schedule_held(&model, &trajectory, &state_bounds).unwrap();
    let controller = Controller {
        accepted: Frame {
            time: 0.,
            solution: circuit.solve(&trajectory.values(0.)).unwrap(),
            circuit,
            states,
            state_bounds,
            operators: Operators::default(),
        },
        event: 0,
        records: vec![],
        outputs: vec![],
    };
    (model, trajectory, controller, calendar)
}

#[test]
fn failed_observer_future_rolls_back_physical_state_display_and_timer_then_retries() {
    let (bad, trajectory, mut controller, mut calendar) = fixture(-1.);
    let signature = |calendar: &Vec<ScheduledEvent>| {
        calendar
            .iter()
            .map(|e| (e.event, e.time, e.bounds()))
            .collect::<Vec<_>>()
    };
    let old = signature(&calendar);
    for _ in 0..2 {
        assert!(controller
            .accept_relocalized(&bad, &trajectory, &mut calendar)
            .is_err());
        assert_eq!(controller.accepted.time, 0.);
        assert_eq!(controller.accepted.states, [0., 0., 2.]);
        assert_eq!(
            controller.accepted.state_bounds,
            [I::ZERO, I::ZERO, I::point(2.)]
        );
        assert_eq!(controller.accepted.solution.voltages[2], 0.);
        assert_eq!(controller.event, 0);
        assert!(controller.records.is_empty() && controller.outputs.is_empty());
        assert_eq!(signature(&calendar), old);
    }
    let (good, _, mut clean, mut clean_calendar) = fixture(0.75);
    controller
        .accept_relocalized(&good, &trajectory, &mut calendar)
        .unwrap();
    clean
        .accept_relocalized(&good, &trajectory, &mut clean_calendar)
        .unwrap();
    assert_eq!(controller.accepted.states, [1., 1., 0.75]);
    assert_eq!(controller.accepted.states, clean.accepted.states);
    assert_eq!(
        controller.accepted.state_bounds,
        clean.accepted.state_bounds
    );
    assert_eq!(
        serde_json::to_value(&controller.records).unwrap(),
        serde_json::to_value(&clean.records).unwrap()
    );
    assert_eq!(signature(&calendar), signature(&clean_calendar));
    assert!(calendar.iter().any(|e| e.event == 2 && e.time == 0.75));
    controller
        .accept_relocalized(&good, &trajectory, &mut calendar)
        .unwrap();
    assert_eq!(controller.accepted.states, [1., 2., 0.75]);
}

#[test]
fn observer_samples_event_operator_tube_not_the_b_point_bound() {
    let (base, trajectory, _, _) = fixture(0.75);
    let mut value = serde_json::to_value(&base.program).unwrap();
    let origin = value["events"][0]["origin"].clone();
    value["operators"] = json!([{"kind":"idt","input":{"op":"affine","constant":1,"terms":[]},"ic":0,"origin":origin}]);
    value["contributions"][0]["rhs"] =
        json!({"op":"add","left":{"op":"state","state":0},"right":{"op":"operator","operator":0}});
    let model = EventModel::new(
        serde_json::from_value(value).unwrap(),
        base.driven.clone(),
        base.tolerances.clone(),
    )
    .unwrap();
    let states = model.initial();
    let operators = Operators::new(&model.program, &trajectory, &model.driven, &states).unwrap();
    let circuit = model
        .circuit_with(&states, &operators.values(0.).unwrap())
        .unwrap();
    let before = Frame {
        time: 0.,
        solution: circuit.solve(&trajectory.values(0.)).unwrap(),
        circuit,
        state_bounds: states.iter().copied().map(I::point).collect(),
        states,
        operators,
    };
    let (next, records) = prepare_batch_with_bounds(
        &model,
        &trajectory,
        &before,
        0.51,
        I { lo: 0.49, hi: 0.51 },
        &[0, 1],
    )
    .unwrap();
    assert!(next.state_bounds[1].lo <= 1.49 && next.state_bounds[1].hi >= 1.51);
    assert!(next.state_bounds[1].hi - next.state_bounds[1].lo > 0.019);
    assert!((next.states[1] - 1.51).abs() < 1e-12);
    assert!(
        next.solution.certified_voltage_bounds.as_ref().unwrap()[2][1]
            - next.solution.certified_voltage_bounds.as_ref().unwrap()[2][0]
            < 1e-10
    );
    assert_eq!(records.len(), 2);
    assert_eq!(before.states, [0., 0., 2.]);
}

#[test]
fn observer_only_event_does_not_restart_or_change_physical_history() {
    let (base, trajectory, _, _) = fixture(0.75);
    let mut value = serde_json::to_value(&base.program).unwrap();
    let origin = value["events"][0]["origin"].clone();
    value["operators"] =
        json!([{"kind":"idt","input":{"op":"state","state":0},"ic":0,"origin":origin}]);
    value["contributions"][0]["rhs"] =
        json!({"op":"add","left":{"op":"state","state":0},"right":{"op":"operator","operator":0}});
    let model = EventModel::new(
        serde_json::from_value(value).unwrap(),
        base.driven.clone(),
        base.tolerances.clone(),
    )
    .unwrap();
    let states = model.initial();
    let operators = Operators::new(&model.program, &trajectory, &model.driven, &states).unwrap();
    let circuit = model
        .circuit_with(&states, &operators.values(0.).unwrap())
        .unwrap();
    let before = Frame {
        time: 0.,
        solution: circuit.solve(&trajectory.values(0.)).unwrap(),
        circuit,
        state_bounds: states.iter().copied().map(I::point).collect(),
        states,
        operators,
    };
    let (first, _) = prepare_batch(&model, &trajectory, &before, 0.5, &[0, 1]).unwrap();
    let observed = prepare_batch(&model, &trajectory, &first, 0.75, &[2])
        .unwrap()
        .0;
    let query = prepare_event(&model, &trajectory, &first, 0.75, &[]).unwrap();
    assert_eq!(observed.states, [1., 2., 0.75]);
    assert_eq!(query.states, [1., 1., 0.75]);
    assert!(observed.operators.same_reset_history(&query.operators));
    for time in [0.75, 0.875, 1.] {
        assert_eq!(
            observed.operators.values(time).unwrap(),
            query.operators.values(time).unwrap()
        );
        assert_eq!(
            observed.operators.bounds(time).unwrap(),
            query.operators.bounds(time).unwrap()
        );
    }
    assert_eq!(observed.solution.voltages, query.solution.voltages);
    assert_eq!(
        observed.solution.certified_voltage_bounds,
        query.solution.certified_voltage_bounds
    );
}
