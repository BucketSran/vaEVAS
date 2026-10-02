//! Exercise the production calendar/record commit owner, not a mock controller.
use super::*;
use crate::ir::{Program, Tolerances, TransientInputs};
use serde_json::json;

fn fixture() -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    let origin = json!({"source":"lifecycle.va","line":1,"column":1,"instance":"dut"});
    let mut filter_origin = origin.clone();
    filter_origin["line"] = json!(2);
    let mut transition_origin = origin.clone();
    transition_origin["line"] = json!(3);
    let program:Program=serde_json::from_value(json!({
        "schema_version":SCHEMA_VERSION,"nodes":["0","u","z","y","edge"],
        "states":[{"instance":"dut","name":"q","kind":"real","initial":2},
                  {"instance":"dut","name":"rst","kind":"integer","initial":0}],
        "operators":[{"kind":"idt","ic":1,"input":{"op":"state","state":0},"reset":{"op":"state","state":1},"origin":origin},
          {"kind":"laplace_nd","input":{"op":"operator","operator":0},"numerator":[1],"denominator":[1,1],"origin":filter_origin},
          {"kind":"transition","input":{"op":"state","state":0},"delay":0.125,"rise":0.125,"fall":0.125,"origin":transition_origin}],
        "events":[{"origin":origin,"trigger":{"kind":"timer","start":0.5,"period":0,"time_tolerance":1e-12,"enabled":true},
            "body":[{"kind":"assign","state":1,"rhs":{"op":"affine","constant":1,"terms":[]}},
                    {"kind":"assign","state":0,"rhs":{"op":"affine","constant":0,"terms":[{"node":2,"coefficient":1}]}}]},
          {"origin":origin,"trigger":{"kind":"timer","start":0.75,"period":0,"time_tolerance":1e-12,"enabled":true},
            "body":[{"kind":"assign","state":1,"rhs":{"op":"affine","constant":0,"terms":[]}}]}],
        "contributions":(0..3).map(|i|json!({"branch":{"instance":"dut","local_positive":format!("p{i}"),"local_negative":"r","kind":"voltage"},
            "positive":i+2,"negative":0,"rhs":{"op":"operator","operator":i},"origin":origin})).collect::<Vec<_>>()
    })).unwrap();
    let model = EventModel::new(
        program,
        vec!["u".into()],
        Tolerances {
            absolute: 1e-8,
            relative: 1e-8,
        },
    )
    .unwrap();
    let trajectory = Trajectory::new(
        TransientInputs {
            pwl: vec![vec![[0., 0.], [1., 0.]]],
            output_times: vec![0., 1.],
            stop: 1.,
            max_step: 1.,
        },
        1,
    )
    .unwrap();
    let states = model.initial();
    let operators = Operators::new(&model.program, &trajectory, &model.driven, &states).unwrap();
    let crossings = schedule(&model, &trajectory, &operators).unwrap();
    let circuit = model
        .circuit_with(&states, &operators.values(0.).unwrap())
        .unwrap();
    let accepted = Frame {
        time: 0.,
        state_bounds: states.iter().copied().map(I::point).collect(),
        states,
        solution: circuit.solve(&[0.]).unwrap(),
        circuit,
        operators,
    };
    (
        model,
        trajectory,
        Controller {
            accepted,
            event: 0,
            records: vec![],
        },
        crossings,
    )
}

#[test]
fn failed_reset_closure_and_discard_leave_calendar_records_and_queue_unchanged() {
    let (model, trajectory, mut controller, calendar) = fixture();
    let original = controller.accepted.operators.bounds(1.).unwrap();
    let deadline = controller.accepted.operators.next_breakpoint(0.);
    let (candidate, records) = prepare_calendar_batch(
        &model,
        &trajectory,
        &controller.accepted,
        0.5,
        &calendar[..1],
        prediction_end(&model, &trajectory, calendar.get(1)),
    )
    .unwrap();
    assert_eq!(candidate.states, vec![1., 1.]);
    assert_eq!(candidate.operators.next_breakpoint(0.5), Some(0.625));
    assert_eq!(records.len(), 1);
    drop(candidate);
    let strict = EventModel::new(
        model.program.clone(),
        model.driven.clone(),
        Tolerances {
            absolute: 1e-20,
            relative: 1e-20,
        },
    )
    .unwrap();
    let error = controller
        .accept_events(&strict, &trajectory, &calendar)
        .unwrap_err();
    assert_eq!(error.kind, "waveform_accuracy");
    assert_eq!(controller.event, 0);
    assert!(controller.records.is_empty());
    assert_eq!(controller.accepted.time, 0.);
    assert_eq!(controller.accepted.states, vec![2., 0.]);
    assert_eq!(
        controller.accepted.state_bounds,
        vec![I::point(2.), I::ZERO]
    );
    assert_eq!(controller.accepted.operators.bounds(1.).unwrap(), original);
    assert_eq!(controller.accepted.operators.next_breakpoint(0.), deadline);
    let (control_model, control_trajectory, mut control, control_calendar) = fixture();
    controller
        .accept_events(&model, &trajectory, &calendar)
        .unwrap();
    control
        .accept_events(&control_model, &control_trajectory, &control_calendar)
        .unwrap();
    assert_eq!(controller.event, control.event);
    assert_eq!(
        serde_json::to_value(&controller.records).unwrap(),
        serde_json::to_value(&control.records).unwrap()
    );
    assert_eq!(
        controller.accepted.operators.bounds(1.).unwrap(),
        control.accepted.operators.bounds(1.).unwrap()
    );
    controller
        .accept_events(&model, &trajectory, &calendar)
        .unwrap();
    control
        .accept_events(&control_model, &control_trajectory, &control_calendar)
        .unwrap();
    assert_eq!(controller.event, 2);
    assert_eq!(controller.records.len(), 2);
    assert_eq!(
        controller.accepted.operators.bounds(1.).unwrap(),
        control.accepted.operators.bounds(1.).unwrap()
    );
    let z = controller.accepted.operators.bounds(1.).unwrap()[0];
    assert!(z.lo <= 1.25 && z.hi >= 1.25);
}

fn nonlinear_horizon_fixture() -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    let origin = json!({"source":"horizon.va","line":1,"column":1,"instance":"dut"});
    let program: Program = serde_json::from_value(json!({
        "schema_version":SCHEMA_VERSION,"nodes":["0","y"],
        "states":[{"instance":"dut","name":"q","kind":"integer","initial":1}],
        "operators":[{"kind":"idt","ic":1,"input":{"op":"multiply",
            "left":{"op":"state","state":0},
            "right":{"op":"power","base":{"op":"affine","constant":0,
                "terms":[{"node":1,"coefficient":1}]},"exponent":2}},"origin":origin}],
        "events":[{"origin":origin,"trigger":{"kind":"timer","start":0.5,"period":0,
            "time_tolerance":1e-12,"enabled":true},
            "body":[{"kind":"assign","state":0,"rhs":{"op":"affine","constant":-1,"terms":[]}}]}],
        "contributions":[{"branch":{"instance":"dut","local_positive":"p","local_negative":"r","kind":"voltage"},
            "positive":1,"negative":0,"rhs":{"op":"operator","operator":0},"origin":origin}]
    })).unwrap();
    let model = EventModel::new(
        program,
        vec![],
        Tolerances {
            absolute: 1e-9,
            relative: 0.0,
        },
    )
    .unwrap();
    let trajectory = Trajectory::new(
        TransientInputs {
            pwl: vec![],
            output_times: vec![0., 2.],
            stop: 2.,
            max_step: 2.,
        },
        0,
    )
    .unwrap();
    let calendar = independent_schedule(&model, &trajectory).unwrap();
    let states = model.initial();
    let operators = Operators::new_until(
        &model.program,
        &trajectory,
        &model.driven,
        &states,
        prediction_end(&model, &trajectory, calendar.first()),
    )
    .unwrap();
    let circuit = model
        .circuit_with(&states, &operators.values(0.).unwrap())
        .unwrap();
    let accepted = Frame {
        time: 0.,
        solution: circuit.solve(&[]).unwrap(),
        state_bounds: states.iter().copied().map(I::point).collect(),
        states,
        circuit,
        operators,
    };
    (
        model,
        trajectory,
        Controller {
            accepted,
            event: 0,
            records: vec![],
        },
        calendar,
    )
}

#[test]
fn nonlinear_horizon_failure_discard_and_retry_preserve_production_controller() {
    let (model, trajectory, mut controller, calendar) = nonlinear_horizon_fixture();
    let prefix = controller.accepted.operators.bounds(0.5).unwrap();
    let strict = EventModel::new(
        model.program.clone(),
        vec![],
        Tolerances {
            absolute: 1e-20,
            relative: 0.0,
        },
    )
    .unwrap();
    for _ in 0..2 {
        assert_eq!(
            controller
                .accept_events(&strict, &trajectory, &calendar)
                .err()
                .unwrap()
                .kind,
            "waveform_accuracy"
        );
        assert_eq!(controller.accepted.time, 0.);
        assert_eq!(controller.accepted.states, vec![1.]);
        assert_eq!(controller.event, 0);
        assert!(controller.records.is_empty());
        assert_eq!(controller.accepted.operators.bounds(0.5).unwrap(), prefix);
        assert_eq!(
            controller
                .accepted
                .operators
                .bounds(0.75)
                .err()
                .unwrap()
                .kind,
            "event_resolution"
        );
    }
    let (discarded, records) = prepare_calendar_batch(
        &model,
        &trajectory,
        &controller.accepted,
        0.5,
        &calendar,
        2.,
    )
    .unwrap();
    let future = discarded.operators.bounds(2.).unwrap();
    assert_eq!(records.len(), 1);
    drop(discarded);
    assert_eq!(controller.event, 0);
    assert!(controller.records.is_empty());
    controller
        .accept_events(&model, &trajectory, &calendar)
        .unwrap();
    assert_eq!(controller.event, 1);
    assert_eq!(controller.records.len(), 1);
    assert_eq!(controller.accepted.states, vec![-1.]);
    assert_eq!(controller.accepted.operators.bounds(2.).unwrap(), future);
    assert!(future[0].lo <= 0.5 && future[0].hi >= 0.5);
    let (clean_model, clean_trajectory, mut clean, clean_calendar) = nonlinear_horizon_fixture();
    clean
        .accept_events(&clean_model, &clean_trajectory, &clean_calendar)
        .unwrap();
    assert_eq!(clean.accepted.operators.bounds(2.).unwrap(), future);
    assert_eq!(
        clean.accepted.solution.voltages,
        controller.accepted.solution.voltages
    );
}
