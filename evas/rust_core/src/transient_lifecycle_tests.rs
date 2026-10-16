//! Exercise the production calendar/record commit owner, not a mock controller.
use super::*;
use crate::ir::{Program, Tolerances, TransientInputs};
use serde_json::json;

// Mathematical root identity and callback observation are distinct contracts.
fn assert_half_root_execution(event: &ScheduledEvent) {
    assert!(event.bounds().lo <= 0.5 && event.bounds().hi >= 0.5);
    if event.is_cross() {
        assert!(event.time > 0.5);
        assert!(event.time - 0.5 <= 1e-9);
        assert_eq!(event.observation_bounds(), I::point(event.time));
    } else {
        assert_eq!(event.time, 0.5);
    }
}

fn relocalization_fixture() -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    let origin = json!({"source":"relocalization.va","line":1,"column":1,"instance":"dut"});
    let program: Program = serde_json::from_value(json!({
        "schema_version": SCHEMA_VERSION, "nodes": ["0","u","y"],
        "states": [{"instance":"dut","name":"q","kind":"real","initial":0.75}],
        "events": [
            {"origin":origin,"trigger":{"kind":"timer","start":0.25,"period":0,
             "time_tolerance":1e-12,"enabled":true},"body":[{"kind":"assign","state":0,
             "rhs":{"op":"affine","constant":0.5,"terms":[]}}]},
            {"origin":origin,"trigger":{"kind":"cross","direction":1,"time_tolerance":1e-9,
             "expression_tolerance":1e-8,"guard":{"op":"add",
               "left":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]},
               "right":{"op":"multiply","left":{"op":"affine","constant":-1,"terms":[]},
                 "right":{"op":"state","state":0}}}},"body":[]},
            {"origin":origin,"trigger":{"kind":"cross","direction":1,"time_tolerance":1e-9,
             "expression_tolerance":1e-8,"guard":{"op":"affine","constant":-0.5,
                 "terms":[{"node":1,"coefficient":1}]}},"body":[]}
        ],
        "contributions":[{"branch":{"instance":"dut","local_positive":"p","local_negative":"r","kind":"voltage"},
          "positive":2,"negative":0,"rhs":{"op":"state","state":0},"origin":origin}]
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
            pwl_errors_v: None,
            strobetimes: Vec::new(),
            pwl: vec![vec![[0., 0.], [1., 1.]]],
            output_times: vec![0., 1.],
            stop: 1.,
            max_step: 1.,
        },
        1,
    )
    .unwrap();
    let states = model.initial();
    let state_bounds: Vec<_> = states.iter().copied().map(I::point).collect();
    let calendar = schedule_held(&model, &trajectory, &state_bounds).unwrap();
    let operators = Operators::new(&model.program, &trajectory, &model.driven, &states).unwrap();
    let circuit = model.circuit(&states).unwrap();
    let accepted = Frame {
        time_proofs: Default::default(),
        time: 0.,
        solution: circuit.solve(&[0.]).unwrap(),
        circuit,
        operators,
        states,
        state_bounds,
    };
    (
        model,
        trajectory,
        Controller {
            accepted,
            event: 0,
            records: vec![],
            outputs: Vec::new(),
        },
        calendar,
    )
}

#[test]
fn failed_future_guard_ordering_rolls_back_then_retries_in_the_same_controller() {
    check_failed_future_guard_ordering(relocalization_fixture);
}

fn timer_relocalization_fixture() -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    let (base, trajectory, controller, _) = relocalization_fixture();
    let mut program = base.program;
    program.events[1].trigger = serde_json::from_value(json!({"kind":"held_timer",
        "start":{"op":"state","state":0},"period":{"op":"affine","constant":0,"terms":[]},
        "time_tolerance":1e-9,"enabled":{"op":"affine","constant":1,"terms":[]}}))
    .unwrap();
    let model = EventModel::new(program, base.driven, base.tolerances).unwrap();
    let calendar = schedule_held(&model, &trajectory, &controller.accepted.state_bounds).unwrap();
    (model, trajectory, controller, calendar)
}

#[test]
fn failed_dynamic_timer_ordering_preserves_the_complete_frame_then_retries() {
    check_failed_future_guard_ordering(timer_relocalization_fixture);
}

fn timer_history_fixture() -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    let (base, trajectory, _, _) = timer_relocalization_fixture();
    let mut program = base.program;
    program.operators = serde_json::from_value(json!([{"kind":"idt","ic":0,
        "input":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]},
        "origin":{"source":"relocalization.va","line":2,"column":1,"instance":"dut"}}]))
    .unwrap();
    program.contributions[0].rhs = serde_json::from_value(json!({"op":"add",
        "left":{"op":"state","state":0},"right":{"op":"operator","operator":0}}))
    .unwrap();
    let model = EventModel::new(program, base.driven, base.tolerances).unwrap();
    let states = model.initial();
    let state_bounds: Vec<_> = states.iter().copied().map(I::point).collect();
    let calendar = schedule_held(&model, &trajectory, &state_bounds).unwrap();
    let operators = Operators::new_until(
        &model.program,
        &trajectory,
        &model.driven,
        &states,
        prediction_end(&model, &trajectory, calendar.first()),
        &model.tolerances,
    )
    .unwrap();
    let circuit = model
        .circuit_with(&states, &operators.values(0.).unwrap())
        .unwrap();
    let accepted = Frame {
        time_proofs: Default::default(),
        time: 0.,
        solution: circuit.solve(&[0.]).unwrap(),
        circuit,
        operators,
        states,
        state_bounds,
    };
    (
        model,
        trajectory,
        Controller {
            accepted,
            event: 0,
            records: vec![],
            outputs: Vec::new(),
        },
        calendar,
    )
}

#[test]
fn held_timer_with_history_ordering_failure_and_retry_preserves_history() {
    check_failed_future_guard_ordering(timer_history_fixture);
}

#[test]
fn failed_new_timer_flow_horizon_rolls_back_then_corrected_retry_matches_clean() {
    let (base, trajectory, _, _) = timer_relocalization_fixture();
    let mut program = serde_json::to_value(base.program).unwrap();
    program["nodes"].as_array_mut().unwrap().push(json!("z"));
    program["events"].as_array_mut().unwrap().pop(); // No independent .5 deadline.
    program["operators"] = json!([{"kind":"idt","ic":1,
        "input":{"op":"power","exponent":2,"base":{"op":"affine","constant":0,
            "terms":[{"node":3,"coefficient":1}]}},
        "origin":{"source":"relocalization.va","line":2,"column":1,"instance":"dut"}}]);
    program["contributions"]
        .as_array_mut()
        .unwrap()
        .push(json!({
        "branch":{"instance":"dut","local_positive":"a","local_negative":"r","kind":"voltage"},
        "positive":3,"negative":0,"rhs":{"op":"operator","operator":0},
        "origin":{"source":"relocalization.va","line":2,"column":1,"instance":"dut"}}));
    let model = EventModel::new(
        serde_json::from_value(program.clone()).unwrap(),
        base.driven.clone(),
        base.tolerances.clone(),
    )
    .unwrap();
    let states = model.initial();
    let state_bounds: Vec<_> = states.iter().copied().map(I::point).collect();
    let mut calendar = schedule_held(&model, &trajectory, &state_bounds).unwrap();
    let operators = Operators::new_until(
        &model.program,
        &trajectory,
        &model.driven,
        &states,
        0.25,
        &model.tolerances,
    )
    .unwrap();
    let circuit = model
        .circuit_with(&states, &operators.values(0.).unwrap())
        .unwrap();
    let accepted = Frame {
        time_proofs: Default::default(),
        time: 0.,
        solution: circuit.solve(&[0.]).unwrap(),
        circuit,
        operators,
        states,
        state_bounds,
    };
    let history = accepted.operators.clone();
    let before: Vec<_> = calendar
        .iter()
        .map(|e| (e.time, e.event, e.bounds()))
        .collect();
    let mut controller = Controller {
        accepted,
        event: 0,
        records: vec![],
        outputs: Vec::new(),
    };
    // y'=y^2 blows up at 1. Predicting all the way to the newly requested
    // timer(1) must fail after the new calendar succeeds, without committing it.
    program["events"][0]["body"][0]["rhs"]["constant"] = json!(1.);
    let bad = EventModel::new(
        serde_json::from_value(program).unwrap(),
        base.driven,
        base.tolerances,
    )
    .unwrap();
    let error = controller
        .accept_relocalized(&bad, &trajectory, &mut calendar)
        .unwrap_err();
    assert_eq!(error.kind, "waveform_accuracy");
    assert_eq!(controller.accepted.time, 0.);
    assert_eq!(controller.accepted.states, [0.75]);
    assert!(controller.records.is_empty());
    assert_eq!(controller.event, 0);
    assert!(controller.accepted.operators.same_reset_history(&history));
    assert_eq!(
        before,
        calendar
            .iter()
            .map(|e| (e.time, e.event, e.bounds()))
            .collect::<Vec<_>>()
    );
    let (expected, records, end) = controller
        .prepare_events_until(&model, &trajectory, &calendar, Some(0.25))
        .unwrap();
    controller
        .accept_relocalized(&model, &trajectory, &mut calendar)
        .unwrap();
    assert_eq!(controller.accepted.states, expected.states);
    assert_eq!(
        serde_json::to_value(&controller.records).unwrap(),
        serde_json::to_value(records).unwrap()
    );
    assert_eq!(end, 1);
    assert_half_root_execution(&calendar[0]);
    let bound = controller.accepted.operators.bounds(0.5).unwrap()[0];
    assert!(bound.lo <= 2. && bound.hi >= 2.);
}

fn check_failed_future_guard_ordering(
    fixture: fn() -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>),
) {
    let (model, trajectory, mut controller, mut calendar) = fixture();
    let original: Vec<_> = calendar
        .iter()
        .map(|e| (e.time, e.event, e.bounds()))
        .collect();
    let voltages = controller.accepted.solution.voltages.clone();
    let history = controller.accepted.operators.clone();
    let mut program = model.program.clone();
    // q = (binary64 1/3)*u + (binary64 5/12). At u=.25 its
    // enclosure overlaps the independent exact .5 root. Do not invent a tie.
    program.events[0].body = serde_json::from_value(json!([{"kind":"assign","state":0,
        "rhs":{"op":"affine","constant":5./12.,"terms":[{"node":1,"coefficient":1./3.}]}}]))
    .unwrap();
    let ambiguous =
        EventModel::new(program, model.driven.clone(), model.tolerances.clone()).unwrap();
    let error = controller
        .accept_relocalized(&ambiguous, &trajectory, &mut calendar)
        .unwrap_err();
    assert_eq!(error.kind, "event_resolution");
    assert!(error.message.contains("ordering"));
    assert_eq!(controller.accepted.time, 0.);
    assert_eq!(controller.accepted.states, vec![0.75]);
    assert_eq!(controller.accepted.state_bounds, vec![I::point(0.75)]);
    assert_eq!(controller.accepted.solution.voltages, voltages);
    assert!(controller.accepted.operators.same_reset_history(&history));
    assert_eq!(controller.event, 0);
    assert!(controller.records.is_empty());
    assert_eq!(
        calendar
            .iter()
            .map(|e| (e.time, e.event, e.bounds()))
            .collect::<Vec<_>>(),
        original
    );
    let (clean_model, clean_trajectory, mut clean, mut clean_calendar) = fixture();
    controller
        .accept_relocalized(&model, &trajectory, &mut calendar)
        .unwrap();
    clean
        .accept_relocalized(&clean_model, &clean_trajectory, &mut clean_calendar)
        .unwrap();
    assert_eq!(controller.accepted.states, clean.accepted.states);
    assert!(controller
        .accepted
        .operators
        .same_reset_history(&clean.accepted.operators));
    assert_eq!(
        controller.accepted.state_bounds,
        clean.accepted.state_bounds
    );
    assert_eq!(
        serde_json::to_value(&controller.records).unwrap(),
        serde_json::to_value(&clean.records).unwrap()
    );
    assert_eq!(
        calendar
            .iter()
            .map(|e| (e.time, e.event, e.bounds()))
            .collect::<Vec<_>>(),
        clean_calendar
            .iter()
            .map(|e| (e.time, e.event, e.bounds()))
            .collect::<Vec<_>>()
    );
    assert_eq!(calendar.len(), 2);
    assert_half_root_execution(&calendar[0]);
    assert_half_root_execution(&calendar[1]);
}

#[test]
fn held_polynomial_jump_rejects_without_consuming_calendar_then_retries() {
    let (base, trajectory, mut controller, _) = relocalization_fixture();
    let mut program = serde_json::to_value(&base.program).unwrap();
    program["events"][1]["trigger"]["guard"]["left"] = json!({"op":"power","exponent":2,
        "base":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]}});
    let model = EventModel::new(
        serde_json::from_value(program.clone()).unwrap(),
        base.driven.clone(),
        base.tolerances.clone(),
    )
    .unwrap();
    let mut calendar =
        schedule_held(&model, &trajectory, &controller.accepted.state_bounds).unwrap();
    let original: Vec<_> = calendar
        .iter()
        .map(|e| (e.time, e.event, e.bounds()))
        .collect();
    program["events"][0]["body"][0]["rhs"]["constant"] = json!(0.01);
    let jumping = EventModel::new(
        serde_json::from_value(program).unwrap(),
        base.driven.clone(),
        base.tolerances.clone(),
    )
    .unwrap();
    for _ in 0..2 {
        assert_eq!(
            controller
                .accept_relocalized(&jumping, &trajectory, &mut calendar)
                .unwrap_err()
                .kind,
            "unsupported_cross"
        );
        assert_eq!(controller.accepted.time, 0.);
        assert_eq!(controller.accepted.states, vec![0.75]);
        assert_eq!(controller.accepted.state_bounds, vec![I::point(0.75)]);
        assert_eq!(controller.event, 0);
        assert!(controller.records.is_empty());
        assert_eq!(
            calendar
                .iter()
                .map(|e| (e.time, e.event, e.bounds()))
                .collect::<Vec<_>>(),
            original
        );
    }
    controller
        .accept_relocalized(&model, &trajectory, &mut calendar)
        .unwrap();
    assert_eq!(controller.accepted.states, vec![0.5]);
    assert_eq!(controller.records.len(), 1);
    assert_eq!(calendar.len(), 2);
    assert_half_root_execution(&calendar[0]);
    assert!(
        calendar[1].bounds().lo <= 2f64.sqrt() / 2. && calendar[1].bounds().hi >= 2f64.sqrt() / 2.
    );
}

pub(super) fn fixture() -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
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
            pwl_errors_v: None,
            strobetimes: Vec::new(),
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
        time_proofs: Default::default(),
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
            outputs: Vec::new(),
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
    // A changed reset map must never acquire the preceding physical root's
    // immutable certificate, even if it is presented as a retention candidate.
    let mut reset_candidate = candidate.operators.clone();
    assert!(!reset_candidate.retain_unchanged_physical_certificate(&controller.accepted.operators));

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

pub(super) fn nonlinear_horizon_fixture(
) -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
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
            pwl_errors_v: None,
            strobetimes: Vec::new(),
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
        &model.tolerances,
    )
    .unwrap();
    let circuit = model
        .circuit_with(&states, &operators.values(0.).unwrap())
        .unwrap();
    let accepted = Frame {
        time_proofs: Default::default(),
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
            outputs: Vec::new(),
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

pub(super) fn history_guard_fixture() -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    let (base, trajectory, _, _) = relocalization_fixture();
    let mut program = serde_json::to_value(base.program).unwrap();
    program["nodes"].as_array_mut().unwrap().push(json!("z"));
    program["events"][0]["body"][0]["rhs"]["constant"] = json!(0.625);
    program["events"][1]["trigger"]["guard"]["left"]["terms"][0]["node"] = json!(3);
    program["operators"] = json!([{"kind":"idt","ic":0,
        "input":{"op":"affine","constant":1,"terms":[]},
        "origin":{"source":"relocalization.va","line":2,"column":1,"instance":"dut"}}]);
    program["contributions"]
        .as_array_mut()
        .unwrap()
        .push(json!({
        "branch":{"instance":"dut","local_positive":"a","local_negative":"r","kind":"voltage"},
        "positive":3,"negative":0,"rhs":{"op":"operator","operator":0},
        "origin":{"source":"relocalization.va","line":2,"column":1,"instance":"dut"}}));
    let model = EventModel::new(
        serde_json::from_value(program).unwrap(),
        base.driven,
        base.tolerances,
    )
    .unwrap();
    let states = model.initial();
    let state_bounds = states.iter().copied().map(I::point).collect();
    let (operators, calendar) = history_calendar::initialize(&model, &trajectory, &states).unwrap();
    let circuit = model
        .circuit_with(&states, &operators.values(0.).unwrap())
        .unwrap();
    let accepted = Frame {
        time_proofs: Default::default(),
        time: 0.,
        solution: circuit.solve(&[0.]).unwrap(),
        circuit,
        operators,
        states,
        state_bounds,
    };
    (
        model,
        trajectory,
        Controller {
            accepted,
            event: 0,
            records: vec![],
            outputs: Vec::new(),
        },
        calendar,
    )
}

#[test]
fn history_calendar_failure_preserves_frame_and_retry_matches_clean() {
    let (model, trajectory, mut controller, mut calendar) = history_guard_fixture();
    let history = controller.accepted.operators.clone();
    let voltages = controller.accepted.solution.voltages.clone();
    let original: Vec<_> = calendar
        .iter()
        .map(|e| (e.time, e.event, e.bounds()))
        .collect();
    let mut bad = serde_json::to_value(&model.program).unwrap();
    // At t=.25 the integral is .25. Moving its threshold below .25 jumps
    // across zero and requires a same-time closure that is intentionally absent.
    bad["events"][0]["body"][0]["rhs"]["constant"] = json!(0.125);
    let bad = EventModel::new(
        serde_json::from_value(bad).unwrap(),
        model.driven.clone(),
        model.tolerances.clone(),
    )
    .unwrap();
    for _ in 0..2 {
        assert_eq!(
            controller
                .accept_history_events(&bad, &trajectory, &mut calendar)
                .unwrap_err()
                .kind,
            "unsupported_cross"
        );
        assert_eq!(controller.accepted.time, 0.);
        assert_eq!(controller.accepted.states, [0.75]);
        assert_eq!(controller.accepted.state_bounds, [I::point(0.75)]);
        assert_eq!(controller.accepted.solution.voltages, voltages);
        assert!(controller.accepted.operators.same_reset_history(&history));
        assert_eq!(controller.event, 0);
        assert!(controller.records.is_empty());
        assert_eq!(
            calendar
                .iter()
                .map(|e| (e.time, e.event, e.bounds()))
                .collect::<Vec<_>>(),
            original
        );
    }
    let (clean_model, clean_trajectory, mut clean, mut clean_calendar) = history_guard_fixture();
    controller
        .accept_history_events(&model, &trajectory, &mut calendar)
        .unwrap();
    clean
        .accept_history_events(&clean_model, &clean_trajectory, &mut clean_calendar)
        .unwrap();
    assert_eq!(controller.accepted.states, clean.accepted.states);
    assert_eq!(
        controller.accepted.state_bounds,
        clean.accepted.state_bounds
    );
    assert_eq!(
        controller.accepted.solution.voltages,
        clean.accepted.solution.voltages
    );
    assert!(controller
        .accepted
        .operators
        .same_reset_history(&clean.accepted.operators));
    assert_eq!(
        serde_json::to_value(&controller.records).unwrap(),
        serde_json::to_value(&clean.records).unwrap()
    );
    assert_eq!(
        calendar
            .iter()
            .map(|e| (e.time, e.event, e.bounds()))
            .collect::<Vec<_>>(),
        clean_calendar
            .iter()
            .map(|e| (e.time, e.event, e.bounds()))
            .collect::<Vec<_>>()
    );
    assert_half_root_execution(&calendar[0]);
}

#[test]
fn two_delays_accuracy_failure_discard_and_earlier_retry_preserve_frame() {
    let origin = |column| json!({"source":"cascade.va","line":1,"column":column,"instance":"dut"});
    let program: Program = serde_json::from_value(json!({
        "schema_version":SCHEMA_VERSION,"nodes":["0","u","y"],
        "operators":[
            {"kind":"abs_delay","input":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]},"delay":0.1,"origin":origin(1)},
            {"kind":"abs_delay","input":{"op":"operator","operator":0},"delay":0.2,"origin":origin(2)}],
        "contributions":[{"branch":{"instance":"dut","local_positive":"p","local_negative":"r","kind":"voltage"},
            "positive":2,"negative":0,"rhs":{"op":"multiply","left":{"op":"affine","constant":1073741824.0,"terms":[]},"right":{"op":"operator","operator":1}},"origin":origin(3)}]
    })).unwrap();
    let model = EventModel::new(
        program,
        vec!["u".into()],
        Tolerances {
            absolute: 1e-10,
            relative: 0.0,
        },
    )
    .unwrap();
    let trajectory = Trajectory::new(
        TransientInputs {
            pwl_errors_v: None,
            strobetimes: Vec::new(),
            pwl: vec![vec![[0.0, 0.0], [3.0, 1.0]]],
            output_times: vec![0.0, 3.0],
            stop: 3.0,
            max_step: 3.0,
        },
        1,
    )
    .unwrap();
    let operators = Operators::new(&model.program, &trajectory, &model.driven, &[]).unwrap();
    let circuit = model
        .circuit_with(&[], &operators.values(0.0).unwrap())
        .unwrap();
    let accepted = Frame {
        time_proofs: Default::default(),
        time: 0.0,
        solution: circuit.solve(&trajectory.values(0.0)).unwrap(),
        circuit,
        operators,
        states: vec![],
        state_bounds: vec![],
    };
    let original = accepted.operators.bounds(1.0).unwrap();
    let voltages = accepted.solution.voltages.clone();
    assert_eq!(
        prepare_event(&model, &trajectory, &accepted, 1.0, &[])
            .err()
            .unwrap()
            .kind,
        "waveform_accuracy"
    );
    let discarded = prepare_event(&model, &trajectory, &accepted, 0.25, &[]).unwrap();
    assert_eq!(discarded.solution.voltages[2], 0.0);
    drop(discarded);
    let retry = prepare_event(&model, &trajectory, &accepted, 0.25, &[]).unwrap();
    assert_eq!(retry.solution.voltages[2], 0.0);
    assert_eq!(retry.operators.bounds(1.0).unwrap(), original);
    assert_eq!(accepted.time, 0.0);
    assert_eq!(accepted.solution.voltages, voltages);
    assert_eq!(accepted.operators.bounds(1.0).unwrap(), original);
    assert_eq!(accepted.operators.values(0.0).unwrap(), [0.0, 0.0]);
}

fn delayed_timer_root_fixture(
    threshold: f64,
) -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    let (base, _, _, _) = history_guard_fixture();
    let mut program = serde_json::to_value(base.program).unwrap();
    program["states"][0]["initial"] = json!(0.);
    program["states"].as_array_mut().unwrap().push(json!({
        "instance":"dut","name":"n","kind":"integer","initial":0}));
    program["events"].as_array_mut().unwrap().pop();
    program["events"][0]["trigger"] = json!({"kind":"timer","start":0.1,"period":0.2,
        "time_tolerance":1e-6,"enabled":true});
    program["events"][0]["body"] = json!([
        {"kind":"assign","state":1,"rhs":{"op":"add","left":{"op":"state","state":1},
          "right":{"op":"affine","constant":1,"terms":[]}}},
        {"kind":"assign","state":0,"rhs":{"op":"add","left":{"op":"state","state":1},
          "right":{"op":"affine","constant":-1,"terms":[]}}}]);
    program["events"][1]["trigger"]["guard"] = json!({"op":"affine","constant":-threshold,
        "terms":[{"node":3,"coefficient":1}]});
    program["operators"][0]["input"] = json!({"op":"state","state":0});
    let model = EventModel::new(
        serde_json::from_value(program).unwrap(),
        base.driven,
        Tolerances {
            absolute: 1.,
            relative: 0.,
        },
    )
    .unwrap();
    let trajectory = Trajectory::new(
        TransientInputs {
            pwl_errors_v: None,
            strobetimes: Vec::new(),
            pwl: vec![vec![[0., 0.], [0.31, 0.31]]],
            output_times: vec![0., 0.31],
            stop: 0.31,
            max_step: 0.31,
        },
        1,
    )
    .unwrap();
    let states = model.initial();
    let state_bounds = states.iter().copied().map(I::point).collect();
    let (operators, calendar) = history_calendar::initialize(&model, &trajectory, &states).unwrap();
    let circuit = model
        .circuit_with(&states, &operators.values(0.).unwrap())
        .unwrap();
    let accepted = Frame {
        time_proofs: Default::default(),
        time: 0.,
        solution: circuit.solve(&[0.]).unwrap(),
        circuit,
        operators,
        states,
        state_bounds,
    };
    (
        model,
        trajectory,
        Controller {
            accepted,
            event: 0,
            records: vec![],
            outputs: Vec::new(),
        },
        calendar,
    )
}

#[test]
fn timer_window_hidden_root_refusal_rolls_back_and_retries_same_controller() {
    let (base, trajectory, mut controller, mut calendar) = delayed_timer_root_fixture(1e-18);
    let mut program = base.program.clone();
    if let EventTrigger::Cross { time_tolerance, .. } = &mut program.events[1].trigger {
        *time_tolerance = 1e-20;
    }
    let bad = EventModel::new(program, base.driven.clone(), base.tolerances.clone()).unwrap();
    controller
        .accept_history_events(&bad, &trajectory, &mut calendar)
        .unwrap();
    let before_time = controller.accepted.time;
    let before_states = controller.accepted.states.clone();
    let before_bounds = controller.accepted.state_bounds.clone();
    let before_voltages = controller.accepted.solution.voltages.clone();
    let before_operators = controller.accepted.operators.clone();
    let records = serde_json::to_value(&controller.records).unwrap();
    let original = calendar
        .iter()
        .map(|e| (e.time, e.event, e.bounds()))
        .collect::<Vec<_>>();
    for _ in 0..2 {
        let error = controller
            .accept_history_events(&bad, &trajectory, &mut calendar)
            .unwrap_err();
        assert_eq!(error.kind, "event_resolution");
        assert!(error.message.contains("cross_ttol_unrepresentable"));
        assert_eq!(controller.accepted.time, before_time);
        assert_eq!(controller.accepted.states, before_states);
        assert_eq!(controller.accepted.state_bounds, before_bounds);
        assert_eq!(controller.accepted.solution.voltages, before_voltages);
        assert!(controller
            .accepted
            .operators
            .same_reset_history(&before_operators));
        assert_eq!(controller.event, 0);
        assert_eq!(serde_json::to_value(&controller.records).unwrap(), records);
        assert_eq!(
            calendar
                .iter()
                .map(|e| (e.time, e.event, e.bounds()))
                .collect::<Vec<_>>(),
            original
        );
    }
    let (good, clean_trajectory, mut clean, mut clean_calendar) = delayed_timer_root_fixture(1e-18);
    clean
        .accept_history_events(&good, &clean_trajectory, &mut clean_calendar)
        .unwrap();
    clean
        .accept_history_events(&good, &clean_trajectory, &mut clean_calendar)
        .unwrap();
    controller
        .accept_history_events(&good, &trajectory, &mut calendar)
        .unwrap();
    assert_eq!(controller.accepted.states, clean.accepted.states);
    assert_eq!(
        controller.accepted.state_bounds,
        clean.accepted.state_bounds
    );
    assert_eq!(
        controller.accepted.solution.voltages,
        clean.accepted.solution.voltages
    );
    assert!(controller
        .accepted
        .operators
        .same_reset_history(&clean.accepted.operators));
    assert_eq!(
        serde_json::to_value(&controller.records).unwrap(),
        serde_json::to_value(&clean.records).unwrap()
    );
    assert_eq!(
        calendar
            .iter()
            .map(|e| (e.time, e.event, e.bounds()))
            .collect::<Vec<_>>(),
        clean_calendar
            .iter()
            .map(|e| (e.time, e.event, e.bounds()))
            .collect::<Vec<_>>()
    );
}

#[test]
fn later_microevent_failure_rolls_back_entire_sequence_and_same_controller_retry() {
    let (base, trajectory, _, _) = delayed_timer_root_fixture(1e-18);
    let mut program = serde_json::to_value(base.program).unwrap();
    let origin = program["events"][0]["origin"].clone();
    program["states"]
        .as_array_mut()
        .unwrap()
        .push(json!({"instance":"dut","name":"s","kind":"real","initial":0}));
    program["contributions"][0]["rhs"] = json!({"op":"state","state":2});
    program["events"].as_array_mut().unwrap().push(json!({"origin":origin,"trigger":{"kind":"timer","start":0.30000000000000004,"period":0,"time_tolerance":1e-6,"enabled":true},"body":[]}));
    let mut later = program["events"][1].clone();
    later["trigger"]["guard"] =
        json!({"op":"affine","constant":-3e-18,"terms":[{"node":3,"coefficient":1}]});
    later["body"] = json!([{"kind":"assign","state":2,"rhs":{"op":"affine","constant":0,"terms":[{"node":3,"coefficient":1e36}]}}]);
    program["events"].as_array_mut().unwrap().push(later);
    let make = |value: serde_json::Value| {
        let model = EventModel::new(
            serde_json::from_value(value).unwrap(),
            base.driven.clone(),
            base.tolerances.clone(),
        )
        .unwrap();
        let states = model.initial();
        let (operators, calendar) =
            history_calendar::initialize(&model, &trajectory, &states).unwrap();
        let circuit = model
            .circuit_with(&states, &operators.values(0.).unwrap())
            .unwrap();
        let controller = Controller {
            accepted: Frame {
                time_proofs: Default::default(),
                time: 0.,
                solution: circuit.solve(&[0.]).unwrap(),
                circuit,
                operators,
                state_bounds: states.iter().copied().map(I::point).collect(),
                states,
            },
            event: 0,
            records: vec![],
            outputs: vec![],
        };
        (model, controller, calendar)
    };
    let (bad, mut controller, mut calendar) = make(program.clone());
    controller
        .accept_history_events(&bad, &trajectory, &mut calendar)
        .unwrap();
    // Local execution preserves the hidden roots inside this next timer
    // transaction; its later failure must roll back the whole transaction.
    let before = controller.accepted.clone();
    let records = serde_json::to_value(&controller.records).unwrap();
    let original: Vec<_> = calendar
        .iter()
        .map(|e| (e.event, e.time, e.bounds()))
        .collect();
    for _ in 0..2 {
        let error = controller
            .accept_history_events(&bad, &trajectory, &mut calendar)
            .unwrap_err();
        assert_eq!(error.kind, "singular_system", "{:?}", error);
        // The first microevent is valid. Only the later event introduces the
        // amplified joint voltage/state equation and fails its uniqueness gate.
        assert_eq!(controller.accepted.time, before.time);
        assert_eq!(controller.accepted.states, before.states);
        assert_eq!(controller.accepted.state_bounds, before.state_bounds);
        assert_eq!(
            controller.accepted.solution.voltages,
            before.solution.voltages
        );
        assert!(controller
            .accepted
            .operators
            .same_reset_history(&before.operators));
        assert_eq!(controller.event, 0);
        assert!(controller.outputs.is_empty());
        assert_eq!(serde_json::to_value(&controller.records).unwrap(), records);
        assert_eq!(
            calendar
                .iter()
                .map(|e| (e.event, e.time, e.bounds()))
                .collect::<Vec<_>>(),
            original
        );
    }
    program["events"][3]["body"][0]["rhs"]["terms"][0]["coefficient"] = json!(1.);
    let (good, mut clean, mut clean_calendar) = make(program);
    clean
        .accept_history_events(&good, &trajectory, &mut clean_calendar)
        .unwrap();
    clean
        .accept_history_events(&good, &trajectory, &mut clean_calendar)
        .unwrap();
    controller
        .accept_history_events(&good, &trajectory, &mut calendar)
        .unwrap();
    assert_eq!(controller.accepted.time, clean.accepted.time);
    assert_eq!(controller.accepted.states, clean.accepted.states);
    assert_eq!(
        controller.accepted.state_bounds,
        clean.accepted.state_bounds
    );
    assert_eq!(
        controller.accepted.solution.voltages,
        clean.accepted.solution.voltages
    );
    assert!(controller
        .accepted
        .operators
        .same_reset_history(&clean.accepted.operators));
    assert_eq!(
        serde_json::to_value(&controller.records).unwrap(),
        serde_json::to_value(&clean.records).unwrap()
    );
    assert_eq!(
        calendar
            .iter()
            .map(|e| (e.event, e.time, e.bounds()))
            .collect::<Vec<_>>(),
        clean_calendar
            .iter()
            .map(|e| (e.event, e.time, e.bounds()))
            .collect::<Vec<_>>()
    );
}

#[test]
fn local_event_permission_rejects_missing_distinct_and_stale_physical_certificates() {
    use crate::schedule::{history_epoch, ordered_observation, HistoryEpoch};
    let (model, trajectory, mut controller, mut calendar) = delayed_timer_root_fixture(1e-18);
    controller
        .accept_history_events(&model, &trajectory, &mut calendar)
        .unwrap();
    let time = calendar[0].time;
    let (mut next, _, end) = controller
        .prepare_events_until(&model, &trajectory, &calendar, Some(time))
        .unwrap();
    let plan = controller
        .prepare_history_future(
            &model,
            &trajectory,
            &mut next,
            &calendar[..end],
            &calendar[end..],
        )
        .unwrap();
    let event_acceptance::CalendarPlan::History {
        pending,
        consumed,
        retained_history,
    } = plan
    else {
        panic!("history plan required")
    };
    let future = history_epoch(
        &model,
        &trajectory,
        &next.operators,
        HistoryEpoch {
            states: &next.state_bounds,
            after: Some(next.time),
            until: trajectory.config.stop,
            consumed: &consumed,
            pending: &pending,
            retained_history: &retained_history,
        },
    )
    .unwrap();
    let (clock, _) = next.operators.local_epoch().unwrap();
    assert!(ordered_observation(&[], clock, &model)
        .err()
        .unwrap()
        .message
        .contains("no event identity"));
    let root = future
        .iter()
        .find(|event| event.dynamic_direction().is_some())
        .unwrap();
    let permission = ordered_observation(std::slice::from_ref(root), clock, &model).unwrap();
    let original = next.operators.clone();
    next.operators.observe_local(permission).unwrap();
    // Identical mathematical geometry is insufficient: the proof belongs to
    // the immutable pre-observation flow, not the newly mapped history.
    let stale = ordered_observation(std::slice::from_ref(root), clock, &model).unwrap();
    let error = next.operators.observe_local(stale).unwrap_err();
    assert!(error.message.contains("immutable physical mode history"));
    let mut foreign = original.clone();
    foreign
        .anchor_event(clock, time, trajectory.config.stop)
        .unwrap();
    let stale = ordered_observation(std::slice::from_ref(root), clock, &model).unwrap();
    assert!(foreign
        .observe_local(stale)
        .unwrap_err()
        .message
        .contains("immutable physical mode history"));
    let mixed = vec![calendar[0].clone(), root.clone()];
    assert!(ordered_observation(&mixed, clock, &model)
        .err()
        .unwrap()
        .message
        .contains("distinct physical events"));
}
#[test]
fn later_same_time_writer_conflict_rolls_back_whole_sequence_and_same_controller_retry() {
    let (base, trajectory, _, _) = delayed_timer_root_fixture(1e-18);
    let mut program = serde_json::to_value(base.program).unwrap();
    let origin = program["events"][0]["origin"].clone();
    program["states"]
        .as_array_mut()
        .unwrap()
        .push(json!({"instance":"dut","name":"s","kind":"real","initial":0}));
    program["contributions"][0]["rhs"] = json!({"op":"state","state":2});
    program["events"].as_array_mut().unwrap().push(json!({"origin":origin,"trigger":{"kind":"timer","start":0.30000000000000004,"period":0,"time_tolerance":1e-6,"enabled":true},"body":[]}));
    let mut later = program["events"][1].clone();
    later["trigger"]["guard"] =
        json!({"op":"affine","constant":-3e-18,"terms":[{"node":3,"coefficient":1}]});
    later["body"] = json!([{"kind":"assign","state":2,"rhs":{"op":"affine","constant":0,"terms":[{"node":3,"coefficient":1.}]}}]);
    program["events"].as_array_mut().unwrap().push(later);
    let mut competing = program["events"][3].clone();
    competing["body"] =
        json!([{"kind":"assign","state":2,"rhs":{"op":"affine","constant":2,"terms":[]}}]);
    program["events"].as_array_mut().unwrap().push(competing);
    let make = |value: serde_json::Value| {
        let model = EventModel::new(
            serde_json::from_value(value).unwrap(),
            base.driven.clone(),
            base.tolerances.clone(),
        )
        .unwrap();
        let states = model.initial();
        let (operators, calendar) =
            history_calendar::initialize(&model, &trajectory, &states).unwrap();
        let circuit = model
            .circuit_with(&states, &operators.values(0.).unwrap())
            .unwrap();
        let controller = Controller {
            accepted: Frame {
                time_proofs: Default::default(),
                time: 0.,
                solution: circuit.solve(&[0.]).unwrap(),
                circuit,
                operators,
                state_bounds: states.iter().copied().map(I::point).collect(),
                states,
            },
            event: 0,
            records: vec![],
            outputs: vec![],
        };
        (model, controller, calendar)
    };
    let (bad, mut controller, mut calendar) = make(program.clone());
    controller
        .accept_history_events(&bad, &trajectory, &mut calendar)
        .unwrap();
    // Local execution preserves the hidden roots inside this next timer
    // transaction; its later failure must roll back the whole transaction.
    let before = controller.accepted.clone();
    let records = serde_json::to_value(&controller.records).unwrap();
    let original: Vec<_> = calendar
        .iter()
        .map(|e| (e.event, e.time, e.bounds()))
        .collect();
    for _ in 0..2 {
        let error = controller
            .accept_history_events(&bad, &trajectory, &mut calendar)
            .unwrap_err();
        assert_eq!(error.kind, "event_conflict", "{:?}", error);
        // The first hidden-root microevent is valid. Two distinct event
        // blocks at the later physical root select the same writer state.
        assert_eq!(controller.accepted.time, before.time);
        assert_eq!(controller.accepted.states, before.states);
        assert_eq!(controller.accepted.state_bounds, before.state_bounds);
        assert_eq!(
            controller.accepted.solution.voltages,
            before.solution.voltages
        );
        assert!(controller
            .accepted
            .operators
            .same_reset_history(&before.operators));
        assert_eq!(controller.event, 0);
        assert!(controller.outputs.is_empty());
        assert_eq!(serde_json::to_value(&controller.records).unwrap(), records);
        assert_eq!(
            calendar
                .iter()
                .map(|e| (e.event, e.time, e.bounds()))
                .collect::<Vec<_>>(),
            original
        );
    }
    program["events"][4]["body"] = json!([]);
    let (good, mut clean, mut clean_calendar) = make(program);
    clean
        .accept_history_events(&good, &trajectory, &mut clean_calendar)
        .unwrap();
    clean
        .accept_history_events(&good, &trajectory, &mut clean_calendar)
        .unwrap();
    controller
        .accept_history_events(&good, &trajectory, &mut calendar)
        .unwrap();
    assert_eq!(controller.accepted.time, clean.accepted.time);
    assert_eq!(controller.accepted.states, clean.accepted.states);
    assert_eq!(
        controller.accepted.state_bounds,
        clean.accepted.state_bounds
    );
    assert_eq!(
        controller.accepted.solution.voltages,
        clean.accepted.solution.voltages
    );
    assert!(controller
        .accepted
        .operators
        .same_reset_history(&clean.accepted.operators));
    assert_eq!(
        serde_json::to_value(&controller.records).unwrap(),
        serde_json::to_value(&clean.records).unwrap()
    );
    assert_eq!(
        calendar
            .iter()
            .map(|e| (e.event, e.time, e.bounds()))
            .collect::<Vec<_>>(),
        clean_calendar
            .iter()
            .map(|e| (e.event, e.time, e.bounds()))
            .collect::<Vec<_>>()
    );
}

#[test]
fn shared_self_counter_conflict_preserves_frame_then_retries_in_same_controller() {
    let (base, trajectory, _, _) = relocalization_fixture();
    let mut program = base.program;
    program.states[0].initial = 4.0.into();
    program.events.truncate(2);
    for event in &mut program.events {
        event.trigger = EventTrigger::Timer {
            start: 0.,
            period: 0.,
            time_tolerance: 1e-12,
            enabled: true,
        };
        event.body = serde_json::from_value(json!([{"kind":"assign","state":0,
            "rhs":{"op":"add","left":{"op":"state","state":0},
            "right":{"op":"affine","constant":1,"terms":[]}}}]))
        .unwrap();
    }
    let model = EventModel::new(program, base.driven, base.tolerances).unwrap();
    let states = model.initial();
    let operators = Operators::new(&model.program, &trajectory, &model.driven, &states).unwrap();
    let history = operators.clone();
    let circuit = model.circuit(&states).unwrap();
    let solution = circuit.solve(&[0.]).unwrap();
    let voltages = solution.voltages.clone();
    let state_bounds: Vec<_> = states.iter().copied().map(I::point).collect();
    let mut controller = Controller {
        accepted: Frame {
            time_proofs: Default::default(),
            time: 0.,
            states,
            state_bounds: state_bounds.clone(),
            circuit,
            solution,
            operators,
        },
        event: 0,
        records: vec![],
        outputs: vec![],
    };
    let calendar = independent_schedule(&model, &trajectory).unwrap();
    assert_eq!(calendar.len(), 2);
    let error = controller
        .accept_events(&model, &trajectory, &calendar)
        .unwrap_err();
    assert_eq!(error.kind, "event_conflict");
    assert_eq!(controller.accepted.time, 0.);
    assert_eq!(controller.accepted.states, [4.]);
    assert_eq!(controller.accepted.state_bounds, state_bounds);
    assert_eq!(controller.accepted.solution.voltages, voltages);
    assert!(controller.accepted.operators.same_reset_history(&history));
    assert!(controller.records.is_empty());
    assert_eq!(controller.event, 0);
    // Retry one selected event with the same model, accepted frame and controller.
    controller
        .accept_events(&model, &trajectory, &calendar[..1])
        .unwrap();
    assert_eq!(controller.accepted.states, [5.]);
    assert_eq!(controller.records.len(), 1);
    assert_eq!(controller.event, 1);
}

// Review F3: original PWL arithmetic must survive a changed held-clock epoch,
// and the production controller must remain retryable after replanning fails.
fn raw_source_held_epoch_fixture() -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    raw_source_held_epoch_fixture_at(0.5000000000000001)
}

fn raw_source_held_epoch_fixture_at(
    fixed: f64,
) -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    let origin = json!({"source":"raw-source-held-epoch.va","line":1,"column":1,"instance":"dut"});
    let increment = |state| {
        json!({"kind":"assign","state":state,"rhs":{"op":"add",
        "left":{"op":"state","state":state},"right":{"op":"affine","constant":1,"terms":[]}}})
    };
    let cross = |threshold: f64, body: serde_json::Value| {
        json!({"origin":origin,"trigger":{"kind":"cross",
        "direction":1,"time_tolerance":1e-9,"expression_tolerance":1e-8,
        "guard":{"op":"affine","constant":-threshold,"terms":[{"node":1,"coefficient":1}]}},"body":body})
    };
    let program: Program = serde_json::from_value(json!({
        "schema_version":SCHEMA_VERSION,"nodes":["0","u","y","z"],
        "states":[{"instance":"dut","name":"next","kind":"real","initial":0.9},
            {"instance":"dut","name":"first","kind":"integer","initial":0},
            {"instance":"dut","name":"timer","kind":"integer","initial":0},
            {"instance":"dut","name":"second","kind":"integer","initial":0},
            {"instance":"dut","name":"held","kind":"integer","initial":0}],
        "events":[cross(0.5,json!([
            {"kind":"assign","state":0,"rhs":{"op":"affine","constant":0.75,"terms":[]}},increment(1)])),
            {"origin":origin,"trigger":{"kind":"timer","start":fixed,
                "period":0,"time_tolerance":1e-9,"enabled":true},"body":[increment(2)]},
            cross(0.5000000000000001,json!([increment(3)])),
            {"origin":origin,"trigger":{"kind":"held_timer","start":{"op":"state","state":0},
                "period":{"op":"affine","constant":0,"terms":[]},"time_tolerance":1e-9,
                "enabled":{"op":"affine","constant":1,"terms":[]}},"body":[increment(4)]}],
        "operators":[{"kind":"idt","input":{"op":"affine","constant":1,"terms":[]},"ic":0,"origin":origin}],
        "contributions":[
            {"branch":{"instance":"dut","local_positive":"p","local_negative":"r","kind":"voltage"},
                "positive":2,"negative":0,"rhs":{"op":"add","left":{"op":"state","state":1},
                    "right":{"op":"add","left":{"op":"state","state":2},
                    "right":{"op":"add","left":{"op":"state","state":3},"right":{"op":"state","state":4}}}},"origin":origin},
            {"branch":{"instance":"dut","local_positive":"p2","local_negative":"r","kind":"voltage"},
                "positive":3,"negative":0,"rhs":{"op":"operator","operator":0},"origin":origin}]
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
            pwl_errors_v: None,
            strobetimes: Vec::new(),
            pwl: vec![vec![[0., 0.1], [1., 0.9]]],
            output_times: vec![0., 1.],
            stop: 1.,
            max_step: 1.,
        },
        1,
    )
    .unwrap();
    let states = model.initial();
    let state_bounds: Vec<_> = states.iter().copied().map(I::point).collect();
    let calendar = schedule_held(&model, &trajectory, &state_bounds).unwrap();
    let operators = Operators::new(&model.program, &trajectory, &model.driven, &states).unwrap();
    let circuit = model
        .circuit_with(&states, &operators.values(0.).unwrap())
        .unwrap();
    let accepted = Frame {
        time_proofs: Default::default(),
        time: 0.,
        solution: circuit.solve(&trajectory.values(0.)).unwrap(),
        circuit,
        operators,
        states,
        state_bounds,
    };
    // Retain a real output owner so rollback checks are not merely empty-list checks.
    let outputs = vec![accepted.clone()];
    (
        model,
        trajectory,
        Controller {
            accepted,
            event: 0,
            records: vec![],
            outputs,
        },
        calendar,
    )
}

fn assert_raw_source_frame_same(actual: &Frame, expected: &Frame) {
    assert_eq!(actual.time, expected.time);
    assert_eq!(actual.states, expected.states);
    assert_eq!(actual.state_bounds, expected.state_bounds);
    assert_eq!(actual.solution.voltages, expected.solution.voltages);
    assert!(actual.operators.same_reset_history(&expected.operators));
    for time in [0., 0.5, 0.75, 1.] {
        assert_eq!(
            actual.operators.values(time).unwrap(),
            expected.operators.values(time).unwrap()
        );
        assert_eq!(
            actual.operators.bounds(time).unwrap(),
            expected.operators.bounds(time).unwrap()
        );
    }
}

#[test]
fn raw_pwl_roots_mixed_timer_held_epoch_failure_rolls_back_then_same_controller_retries() {
    use std::cmp::Ordering;
    let (model, trajectory, mut controller, mut calendar) = raw_source_held_epoch_fixture();
    let signature = |events: &[ScheduledEvent]| {
        events
            .iter()
            .map(|e| {
                (
                    e.event,
                    e.time,
                    e.bounds(),
                    e.physical_order_at(0.5),
                    e.physical_order_at(0.5000000000000001),
                )
            })
            .collect::<Vec<_>>()
    };
    assert_eq!(
        calendar.iter().map(|e| e.event).collect::<Vec<_>>(),
        [1, 0, 2, 3]
    );
    // Exact answers follow original binary64 knots .1/.9, not rounded guard ends:
    // (.5-.1)/(.9-.1) < .5; the second source root is after the fixed timer.
    let first = calendar.iter().find(|e| e.event == 0).unwrap();
    let second = calendar.iter().find(|e| e.event == 2).unwrap();
    assert_eq!(
        crate::schedule::common_root(std::slice::from_ref(first))
            .unwrap()
            .order(&crate::exact_source::RootTime::point(0.5).unwrap()),
        Ordering::Less
    );
    assert_eq!(
        crate::schedule::common_root(std::slice::from_ref(second))
            .unwrap()
            .order(&crate::exact_source::RootTime::point(0.5000000000000001).unwrap()),
        Ordering::Greater
    );
    // The timer's tau is before the certified callback te of source 0.
    // Commit that legal prefix before testing the later rejected transaction.
    assert!(calendar[0].time < first.time);
    controller
        .accept_relocalized(&model, &trajectory, &mut calendar)
        .unwrap();
    assert_eq!(calendar[0].event, 0);
    assert_eq!(controller.records.len(), 1);
    assert_eq!(controller.records[0].event, 1);
    let before = controller.accepted.clone();
    let original_calendar = signature(&calendar);
    let original_records = serde_json::to_value(&controller.records).unwrap();
    let original_outputs = controller.outputs.clone();
    let original_cursor = controller.event;

    // Prepare the GOOD real first cross and its changed future calendar before
    // introducing a bad candidate. This verifies proof retention across epoch.
    let (next, records, end) = controller
        .prepare_events_until(&model, &trajectory, &calendar, Some(calendar[0].time))
        .unwrap();
    let future = controller
        .prepare_held_future(
            &model,
            &trajectory,
            &next,
            &records,
            &calendar[end..],
            &calendar[controller.event..end],
        )
        .unwrap();
    assert_eq!(future.iter().map(|e| e.event).collect::<Vec<_>>(), [2, 3]);
    assert_eq!(future[1].time, 0.75);
    assert_eq!(signature(&future[..1]), signature(&calendar[1..2]));
    assert_eq!(
        future[0].physical_order_at(0.5000000000000001),
        Some(Ordering::Greater)
    );
    assert_eq!(next.states, [0.75, 1., 1., 0., 0.]);

    let mut bad_program = model.program.clone();
    // z=idt(1)=t is exactly sampled as a point by itself. Keep two binary64
    // products separate: (1/3)*z+(2/3)*z has a nonpoint arithmetic enclosure
    // crossing te and no original-source time identity. Its exact binary64
    // coefficient sum is slightly below one, not an algebraic q=te identity.
    // The held start therefore cannot invent a priority at this boundary.
    // The original (u+1)/3 failure injection is preserved in the task archive;
    // a point te sample no longer has its old root-window uncertainty.
    bad_program.events[0].body[0] = serde_json::from_value(json!({"kind":"assign","state":0,
        "rhs":{"op":"add",
            "left":{"op":"multiply","left":{"op":"affine","constant":1./3.,"terms":[]},
                "right":{"op":"affine","constant":0.,"terms":[{"node":3,"coefficient":1.}]}},
            "right":{"op":"multiply","left":{"op":"affine","constant":2./3.,"terms":[]},
                "right":{"op":"affine","constant":0.,"terms":[{"node":3,"coefficient":1.}]}}}}))
    .unwrap();
    let bad = EventModel::new(bad_program, model.driven.clone(), model.tolerances.clone()).unwrap();
    let (sample, _, _) = controller
        .prepare_events_until(&bad, &trajectory, &calendar, Some(calendar[0].time))
        .unwrap();
    assert!(sample.state_bounds[0].lo < sample.state_bounds[0].hi);
    assert!(sample.state_bounds[0].lo <= sample.time && sample.time <= sample.state_bounds[0].hi);
    assert!(!sample.time_proofs.contains_key(&0));
    use num_rational::BigRational as R;
    let scale = R::from_float(1. / 3.).unwrap() + R::from_float(2. / 3.).unwrap();
    assert!(scale < R::from_integer(1.into()));
    let exact = scale * R::from_float(sample.time).unwrap();
    assert!(R::from_float(sample.state_bounds[0].lo).unwrap() <= exact);
    assert!(exact <= R::from_float(sample.state_bounds[0].hi).unwrap());
    drop(sample);
    for _ in 0..2 {
        let error = controller
            .accept_relocalized(&bad, &trajectory, &mut calendar)
            .unwrap_err();
        assert_eq!(error.kind, "event_resolution");
        assert!(
            error
                .message
                .contains("dynamic timer window overlaps the accepted boundary"),
            "{}",
            error.message
        );
        assert_raw_source_frame_same(&controller.accepted, &before);
        assert_eq!(signature(&calendar), original_calendar);
        assert_eq!(
            serde_json::to_value(&controller.records).unwrap(),
            original_records
        );
        assert_eq!(controller.event, original_cursor);
        assert_eq!(controller.outputs.len(), original_outputs.len());
        for (actual, expected) in controller.outputs.iter().zip(&original_outputs) {
            assert_raw_source_frame_same(actual, expected);
        }
    }

    let (clean_model, clean_trajectory, mut clean, mut clean_calendar) =
        raw_source_held_epoch_fixture();
    clean
        .accept_relocalized(&clean_model, &clean_trajectory, &mut clean_calendar)
        .unwrap();
    assert_raw_source_frame_same(&controller.accepted, &clean.accepted);
    while !calendar.is_empty() {
        controller
            .accept_relocalized(&model, &trajectory, &mut calendar)
            .unwrap();
        clean
            .accept_relocalized(&clean_model, &clean_trajectory, &mut clean_calendar)
            .unwrap();
        assert_raw_source_frame_same(&controller.accepted, &clean.accepted);
        assert_eq!(signature(&calendar), signature(&clean_calendar));
        assert_eq!(
            serde_json::to_value(&controller.records).unwrap(),
            serde_json::to_value(&clean.records).unwrap()
        );
        assert_eq!(controller.event, clean.event);
        assert_eq!(controller.outputs.len(), clean.outputs.len());
        for (actual, expected) in controller.outputs.iter().zip(&clean.outputs) {
            assert_raw_source_frame_same(actual, expected);
        }
    }
    assert!(clean_calendar.is_empty());
    assert_eq!(controller.accepted.states, [0.75, 1., 1., 1., 1.]);
    assert_eq!(
        controller
            .records
            .iter()
            .map(|record| record.event)
            .collect::<Vec<_>>(),
        [1, 0, 2, 3]
    );
    assert_eq!(controller.records.last().unwrap().time, 0.75);
    assert_eq!(controller.accepted.solution.voltages[2], 4.);
}

#[test]
fn extended_source_timer_cluster_later_failure_rolls_back_then_same_controller_retries() {
    let (model, trajectory, mut controller, mut calendar) = raw_source_held_epoch_fixture_at(0.5);
    // Distinct execution instants are separate transactions. Preserve both
    // legal prefix events before injecting failure at the second source te.
    while calendar[0].event != 2 {
        controller
            .accept_relocalized(&model, &trajectory, &mut calendar)
            .unwrap();
    }
    assert_eq!(
        controller
            .records
            .iter()
            .map(|r| r.event)
            .collect::<Vec<_>>(),
        [1, 0]
    );
    let before = controller.accepted.clone();
    let original_records = serde_json::to_value(&controller.records).unwrap();
    let signature = |events: &[ScheduledEvent]| {
        events
            .iter()
            .map(|e| (e.event, e.time, e.bounds(), e.physical_order_at(0.5)))
            .collect::<Vec<_>>()
    };
    let original_calendar = signature(&calendar);
    let original_outputs = controller.outputs.clone();
    let mut bad_program = model.program.clone();
    // Fail at the second source execution after the first cross and timer
    // have formed an accepted prefix. The uncertain held start touches this
    // candidate boundary and still cannot choose an arbitrary priority.
    bad_program.events[2].body.push(
        serde_json::from_value(json!({"kind":"assign","state":0,
            "rhs":{"op":"affine","constant":-1.,
                "terms":[{"node":1,"coefficient":3.}]}}))
        .unwrap(),
    );
    let bad = EventModel::new(bad_program, model.driven.clone(), model.tolerances.clone()).unwrap();
    for _ in 0..2 {
        let error = controller
            .accept_relocalized(&bad, &trajectory, &mut calendar)
            .unwrap_err();
        assert_eq!(error.kind, "event_resolution");
        assert!(error
            .message
            .contains("dynamic timer window overlaps the accepted boundary"));
        assert_raw_source_frame_same(&controller.accepted, &before);
        assert_eq!(signature(&calendar), original_calendar);
        assert_eq!(
            serde_json::to_value(&controller.records).unwrap(),
            original_records
        );
        assert_eq!(controller.event, 0);
        assert_eq!(controller.outputs.len(), original_outputs.len());
        for (actual, expected) in controller.outputs.iter().zip(&original_outputs) {
            assert_raw_source_frame_same(actual, expected);
        }
    }
    let (clean_model, clean_trajectory, mut clean, mut clean_calendar) =
        raw_source_held_epoch_fixture_at(0.5);
    while clean_calendar[0].event != 2 {
        clean
            .accept_relocalized(&clean_model, &clean_trajectory, &mut clean_calendar)
            .unwrap();
    }
    assert_raw_source_frame_same(&controller.accepted, &clean.accepted);
    while !calendar.is_empty() {
        controller
            .accept_relocalized(&model, &trajectory, &mut calendar)
            .unwrap();
        clean
            .accept_relocalized(&clean_model, &clean_trajectory, &mut clean_calendar)
            .unwrap();
        assert_raw_source_frame_same(&controller.accepted, &clean.accepted);
        assert_eq!(signature(&calendar), signature(&clean_calendar));
        assert_eq!(
            serde_json::to_value(&controller.records).unwrap(),
            serde_json::to_value(&clean.records).unwrap()
        );
        assert_eq!(controller.event, clean.event);
        assert_eq!(controller.outputs.len(), clean.outputs.len());
        for (actual, expected) in controller.outputs.iter().zip(&clean.outputs) {
            assert_raw_source_frame_same(actual, expected);
        }
    }
    assert_eq!(controller.accepted.states, [0.75, 1., 1., 1., 1.]);
    assert_eq!(
        controller
            .records
            .iter()
            .map(|r| r.event)
            .collect::<Vec<_>>(),
        [1, 0, 2, 3]
    );
}

#[test]
fn distinct_or_roots_at_one_execution_point_preserve_logical_multiplicity() {
    let (base, trajectory, _, _) = delayed_timer_root_fixture(1e-18);
    let make_program = |second: f64| {
        let mut data = serde_json::to_value(&base.program).unwrap();
        data["states"]
            .as_array_mut()
            .unwrap()
            .push(json!({"instance":"dut","name":"calls","kind":"integer","initial":0}));
        let first = data["events"][1]["trigger"].clone();
        let mut later = first.clone();
        later["guard"]["constant"] = json!(-second);
        data["events"][1]["trigger"] = json!({"kind":"or","triggers":[first,later]});
        data["events"][1]["body"] = json!([{"kind":"assign","state":2,"rhs":{"op":"add","left":{"op":"state","state":2},"right":{"op":"affine","constant":1,"terms":[]}}}]);
        data
    };
    // Independent source roots at .2+1e-18 and .2+3e-18 have distinct exact
    // identities but the same certified binary64 execution point. The calendar
    // must reject that unsupported same-body multiplicity before committing.
    let mut source = make_program(3e-18);
    source["operators"] = json!([]);
    for contribution in source["contributions"].as_array_mut().unwrap() {
        contribution["rhs"] = json!({"op":"affine","constant":0,"terms":[]});
    }
    let guard = |offset: f64| json!({"op":"add","left":{"op":"affine","constant":-0.2,"terms":[{"node":1,"coefficient":1}]},"right":{"op":"affine","constant":-offset,"terms":[]}});
    source["events"][1]["trigger"]["triggers"][0]["guard"] = guard(1e-18);
    source["events"][1]["trigger"]["triggers"][1]["guard"] = guard(3e-18);
    let source = EventModel::new(
        serde_json::from_value(source).unwrap(),
        base.driven.clone(),
        base.tolerances.clone(),
    )
    .unwrap();
    for _ in 0..2 {
        let error = independent_schedule(&source, &trajectory)
            .err()
            .expect("two distinct callbacks cannot be silently merged");
        assert_eq!(error.kind, "event_resolution");
        assert!(
            error.message.contains("logical multiplicity"),
            "{:?}",
            error
        );
    }
    // The local epoch can represent distinct execution instants even when their
    // global representations overlap. Both local OR occurrences must execute.
    for second in [3e-18, 1e-6] {
        let model = EventModel::new(
            serde_json::from_value(make_program(second)).unwrap(),
            base.driven.clone(),
            base.tolerances.clone(),
        )
        .unwrap();
        let states = model.initial();
        let (operators, mut calendar) =
            history_calendar::initialize(&model, &trajectory, &states).unwrap();
        let circuit = model
            .circuit_with(&states, &operators.values(0.).unwrap())
            .unwrap();
        let mut controller = Controller {
            accepted: Frame {
                time_proofs: Default::default(),
                time: 0.,
                state_bounds: states.iter().copied().map(I::point).collect(),
                solution: circuit.solve(&trajectory.values(0.)).unwrap(),
                states,
                circuit,
                operators,
            },
            event: 0,
            records: vec![],
            outputs: vec![],
        };
        while !calendar.is_empty() {
            controller
                .accept_history_events(&model, &trajectory, &mut calendar)
                .unwrap();
        }
        assert_eq!(controller.accepted.states[2], 2.);
        let callbacks: Vec<_> = controller.records.iter().filter(|r| r.event == 1).collect();
        assert_eq!(callbacks.len(), 2);
        assert!(callbacks[0].time < callbacks[1].time);
    }
}

#[test]
fn issue70_certified_return_late_failure_and_same_controller_retry() {
    fn fixture() -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
        let request: serde_json::Value =
            serde_json::from_str(include_str!("issue70_self_request.json")).unwrap();
        let model = EventModel::new(
            serde_json::from_value(request["program"].clone()).unwrap(),
            serde_json::from_value(request["driven"].clone()).unwrap(),
            serde_json::from_value(request["tolerances"].clone()).unwrap(),
        )
        .unwrap();
        let mut config: TransientInputs =
            serde_json::from_value(request["transient"].clone()).unwrap();
        config.output_times.insert(2, 0.50000000001); // Actual retained pre-return phase query.
        let trajectory = Trajectory::new(config, model.driven.len()).unwrap();
        let prepared = initialization::prepare(&model, &trajectory).unwrap();
        let states = prepared
            .as_ref()
            .map_or_else(|| model.initial(), |p| p.states.clone());
        let state_bounds = prepared.map_or_else(
            || states.iter().copied().map(I::point).collect(),
            |p| p.bounds,
        );
        let (operators, calendar) =
            history_calendar::initialize(&model, &trajectory, &states).unwrap();
        let circuit = model
            .circuit_at(
                &states,
                &operators.values(0.).unwrap(),
                &trajectory.value_bounds(0.),
            )
            .unwrap();
        let accepted = Frame {
            time_proofs: Default::default(),
            time: 0.,
            solution: circuit.solve(&trajectory.values(0.)).unwrap(),
            state_bounds,
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
                outputs: vec![],
            },
            calendar,
        )
    }
    fn calendar_identity(calendar: &[ScheduledEvent]) -> Vec<(f64, usize, I)> {
        calendar
            .iter()
            .map(|e| (e.time, e.event, e.bounds()))
            .collect()
    }
    let (model, trajectory, mut controller, mut calendar) = fixture();
    let (clean_model, clean_trajectory, mut clean, mut clean_calendar) = fixture();
    while controller.records.len() < 2 {
        controller
            .accept_history_events(&model, &trajectory, &mut calendar)
            .unwrap();
        clean
            .accept_history_events(&clean_model, &clean_trajectory, &mut clean_calendar)
            .unwrap();
    }
    assert!(controller.records.len() >= 2);
    assert!(!calendar.is_empty());
    let time = controller.accepted.time;
    let cursor = controller.event;
    let states = controller.accepted.states.clone();
    let bounds = controller.accepted.state_bounds.clone();
    let solution = controller.accepted.solution.voltages.clone();
    let history = controller.accepted.operators.clone();
    let records = serde_json::to_value(&controller.records).unwrap();
    let calendar_before = calendar_identity(&calendar);
    let outputs = controller
        .outputs
        .iter()
        .map(|f| (f.time, f.states.clone(), f.solution.voltages.clone()))
        .collect::<Vec<_>>();
    assert!(
        !outputs.is_empty(),
        "rollback must include actual retained phase outputs"
    );
    println!(
        "accepted feedback prefix: {} records, {} outputs, time {:?}",
        controller.records.len(),
        outputs.len(),
        time
    );
    let bad = EventModel::new(
        model.program.clone(),
        model.driven.clone(),
        Tolerances {
            absolute: 1e-30,
            relative: 0.,
        },
    )
    .unwrap();
    for _ in 0..2 {
        let error = controller
            .accept_history_events(&bad, &trajectory, &mut calendar)
            .unwrap_err();
        println!("late rejection: {:?}", error);
        assert_eq!(error.kind, "waveform_accuracy", "{:?}", error);
        assert_eq!(controller.event, cursor);
        assert_eq!(controller.accepted.time, time);
        assert_eq!(controller.accepted.states, states);
        assert_eq!(controller.accepted.state_bounds, bounds);
        assert_eq!(controller.accepted.solution.voltages, solution);
        assert!(controller.accepted.operators.same_reset_history(&history));
        assert_eq!(serde_json::to_value(&controller.records).unwrap(), records);
        assert_eq!(calendar_identity(&calendar), calendar_before);
        assert_eq!(
            controller
                .outputs
                .iter()
                .map(|f| (f.time, f.states.clone(), f.solution.voltages.clone()))
                .collect::<Vec<_>>(),
            outputs
        );
    }
    for _ in 0..3 {
        controller
            .accept_history_events(&model, &trajectory, &mut calendar)
            .unwrap();
        clean
            .accept_history_events(&clean_model, &clean_trajectory, &mut clean_calendar)
            .unwrap();
        assert_eq!(controller.accepted.time, clean.accepted.time);
        assert_eq!(controller.accepted.states, clean.accepted.states);
        assert_eq!(
            controller.accepted.state_bounds,
            clean.accepted.state_bounds
        );
        assert_eq!(
            controller.accepted.solution.voltages,
            clean.accepted.solution.voltages
        );
        assert!(controller
            .accepted
            .operators
            .same_reset_history(&clean.accepted.operators));
        assert_eq!(
            serde_json::to_value(&controller.records).unwrap(),
            serde_json::to_value(&clean.records).unwrap()
        );
        assert_eq!(
            calendar_identity(&calendar),
            calendar_identity(&clean_calendar)
        );
        assert_eq!(
            controller
                .outputs
                .iter()
                .map(|f| (f.time, f.states.clone(), f.solution.voltages.clone()))
                .collect::<Vec<_>>(),
            clean
                .outputs
                .iter()
                .map(|f| (f.time, f.states.clone(), f.solution.voltages.clone()))
                .collect::<Vec<_>>()
        );
    }
}

#[test]
fn issue70_return_isolator_failure_retries_same_controller_after_feedback_prefix() {
    use num_rational::BigRational as R;
    use num_traits::{ToPrimitive, Zero};
    fn fixture(
        request: &str,
        query: f64,
    ) -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
        let request: serde_json::Value = serde_json::from_str(request).unwrap();
        let model = EventModel::new(
            serde_json::from_value(request["program"].clone()).unwrap(),
            serde_json::from_value(request["driven"].clone()).unwrap(),
            serde_json::from_value(request["tolerances"].clone()).unwrap(),
        )
        .unwrap();
        let mut config: TransientInputs =
            serde_json::from_value(request["transient"].clone()).unwrap();
        config.output_times.insert(2, query); // Actual retained pre-return phase query.
        let trajectory = Trajectory::new(config, model.driven.len()).unwrap();
        let prepared = initialization::prepare(&model, &trajectory).unwrap();
        let states = prepared
            .as_ref()
            .map_or_else(|| model.initial(), |p| p.states.clone());
        let state_bounds = prepared.map_or_else(
            || states.iter().copied().map(I::point).collect(),
            |p| p.bounds,
        );
        let (operators, calendar) =
            history_calendar::initialize(&model, &trajectory, &states).unwrap();
        let circuit = model
            .circuit_at(
                &states,
                &operators.values(0.).unwrap(),
                &trajectory.value_bounds(0.),
            )
            .unwrap();
        let accepted = Frame {
            time_proofs: Default::default(),
            time: 0.,
            solution: circuit.solve(&trajectory.values(0.)).unwrap(),
            state_bounds,
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
                outputs: vec![],
            },
            calendar,
        )
    }
    fn calendar_identity(calendar: &[ScheduledEvent]) -> Vec<(f64, usize, I)> {
        calendar
            .iter()
            .map(|e| (e.time, e.event, e.bounds()))
            .collect()
    }

    for (request, query) in [
        (
            include_str!("issue70_self_plus1_original.json"),
            0.50000000001,
        ),
        (
            include_str!("issue70_self_minus1_original.json"),
            0.50000000001,
        ),
        (
            include_str!("issue70_self_plus3_original.json"),
            0.16666666667,
        ),
        (
            include_str!("issue70_self_minus3_original.json"),
            0.16666666667,
        ),
    ] {
        let (model, trajectory, mut controller, mut calendar) = fixture(request, query);
        let (clean_model, clean_trajectory, mut clean, mut clean_calendar) =
            fixture(request, query);
        let initial_float = controller.accepted.states[0];
        while controller.records.len() < 2 {
            controller
                .accept_history_events(&model, &trajectory, &mut calendar)
                .unwrap();
            clean
                .accept_history_events(&clean_model, &clean_trajectory, &mut clean_calendar)
                .unwrap();
        }
        assert_eq!(controller.records.len(), 2);
        let q = |t: f64| R::from_float(t).unwrap();
        let mut z = R::zero();
        let mut t = R::zero();
        let mut slope = q(initial_float);
        for record in &controller.records {
            z += &slope * (q(record.time) - &t);
            t = q(record.time);
            slope = -slope;
        }
        let next = q(calendar[0].time);
        z += &slope * (&next - &t);
        slope = -slope;
        let first_return = &next
            + (R::new(
                if initial_float > 0. {
                    1.into()
                } else {
                    (-1).into()
                },
                2.into(),
            ) - &z)
                / &slope;
        let bad_stop = first_return.to_f64().unwrap();
        assert!(bad_stop > calendar[0].time);
        let mut config = trajectory.config.clone();
        config.stop = bad_stop;
        config.output_times.retain(|&u| u < bad_stop);
        config.output_times.push(bad_stop);
        let bad_trajectory = Trajectory::new(config, model.driven.len()).unwrap();
        let accepted = controller.accepted.clone();
        let cursor = controller.event;
        let records = serde_json::to_value(&controller.records).unwrap();
        let before_calendar = calendar_identity(&calendar);
        let outputs = controller
            .outputs
            .iter()
            .map(|f| (f.time, f.states.clone(), f.solution.voltages.clone()))
            .collect::<Vec<_>>();
        assert!(!outputs.is_empty());
        println!("accepted prefix {} events; next execution {:?}; independently integrated return={:?}; failing stop={:?}",controller.records.len(),calendar[0].time,first_return,bad_stop);
        for _ in 0..2 {
            let error = controller
                .accept_history_events(&model, &bad_trajectory, &mut calendar)
                .unwrap_err();
            println!("return isolation rejection: {:?}", error);
            assert_eq!(error.kind, "event_resolution", "{:?}", error);
            assert!(
                error.message.contains("consumed-return isolation horizon"),
                "{:?}",
                error
            );
            assert!(error.message.contains("interval end"), "{:?}", error);
            assert!(error.message.contains("incoming=1"));
            assert!(error.message.contains("requested=0"));
            assert!(error.message.contains("cross "));
            assert!(error.message.contains("mathematical_root_bounds="));
            assert!(error.message.contains("observation_bounds="));
            assert!(error.message.contains("actual callback time="));
            assert_eq!(controller.event, cursor);
            assert_eq!(controller.accepted.time, accepted.time);
            assert_eq!(controller.accepted.states, accepted.states);
            assert_eq!(controller.accepted.state_bounds, accepted.state_bounds);
            assert_eq!(
                controller.accepted.solution.voltages,
                accepted.solution.voltages
            );
            assert!(controller
                .accepted
                .operators
                .same_reset_history(&accepted.operators));
            assert_eq!(serde_json::to_value(&controller.records).unwrap(), records);
            assert_eq!(calendar_identity(&calendar), before_calendar);
            assert_eq!(
                controller
                    .outputs
                    .iter()
                    .map(|f| (f.time, f.states.clone(), f.solution.voltages.clone()))
                    .collect::<Vec<_>>(),
                outputs
            );
        }
        for _ in 0..3 {
            controller
                .accept_history_events(&model, &trajectory, &mut calendar)
                .unwrap();
            clean
                .accept_history_events(&clean_model, &clean_trajectory, &mut clean_calendar)
                .unwrap();
            assert_eq!(controller.accepted.time, clean.accepted.time);
            assert_eq!(controller.accepted.states, clean.accepted.states);
            assert_eq!(
                controller.accepted.state_bounds,
                clean.accepted.state_bounds
            );
            assert_eq!(
                controller.accepted.solution.voltages,
                clean.accepted.solution.voltages
            );
            assert!(controller
                .accepted
                .operators
                .same_reset_history(&clean.accepted.operators));
            assert_eq!(
                serde_json::to_value(&controller.records).unwrap(),
                serde_json::to_value(&clean.records).unwrap()
            );
            assert_eq!(
                calendar_identity(&calendar),
                calendar_identity(&clean_calendar)
            );
            assert_eq!(
                controller
                    .outputs
                    .iter()
                    .map(|f| (f.time, f.states.clone(), f.solution.voltages.clone()))
                    .collect::<Vec<_>>(),
                clean
                    .outputs
                    .iter()
                    .map(|f| (f.time, f.states.clone(), f.solution.voltages.clone()))
                    .collect::<Vec<_>>()
            );
        }
    }
}

#[test]
fn issue70_nonmonotone_remaining_horizon_accepts_two_feedback_events_each_direction() {
    use num_rational::BigRational as R;
    use num_traits::{Signed, ToPrimitive, Zero};
    fn fixture(request: &str) -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
        let request: serde_json::Value = serde_json::from_str(request).unwrap();
        let model = EventModel::new(
            serde_json::from_value(request["program"].clone()).unwrap(),
            serde_json::from_value(request["driven"].clone()).unwrap(),
            serde_json::from_value(request["tolerances"].clone()).unwrap(),
        )
        .unwrap();
        let mut config: TransientInputs =
            serde_json::from_value(request["transient"].clone()).unwrap();
        config.stop = 3.;
        config.output_times = vec![0., 3.];
        for wave in &mut config.pwl {
            let value = wave.last().unwrap()[1];
            wave.push([3., value]);
        }
        let trajectory = Trajectory::new(config, model.driven.len()).unwrap();
        let prepared = initialization::prepare(&model, &trajectory).unwrap();
        let states = prepared
            .as_ref()
            .map_or_else(|| model.initial(), |p| p.states.clone());
        let state_bounds = prepared.map_or_else(
            || states.iter().copied().map(I::point).collect(),
            |p| p.bounds,
        );
        let (operators, calendar) =
            history_calendar::initialize(&model, &trajectory, &states).unwrap();
        let circuit = model
            .circuit_at(
                &states,
                &operators.values(0.).unwrap(),
                &trajectory.value_bounds(0.),
            )
            .unwrap();
        let accepted = Frame {
            time_proofs: Default::default(),
            time: 0.,
            solution: circuit.solve(&trajectory.values(0.)).unwrap(),
            state_bounds,
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
                outputs: vec![],
            },
            calendar,
        )
    }

    for (request, speed) in [
        (include_str!("issue70_self_plus1_original.json"), 1.),
        (include_str!("issue70_self_minus1_original.json"), -1.),
        (include_str!("issue70_self_plus3_original.json"), 3.),
        (include_str!("issue70_self_minus3_original.json"), -3.),
    ] {
        let (model, trajectory, mut controller, mut calendar) = fixture(request);
        let q = |t: f64| R::from_float(t).unwrap();
        let mut t = R::zero();
        let mut z = R::zero();
        let mut slope = q(speed);
        for n in 1..=2 {
            let mut candidates = [R::new((-1).into(), 2.into()), R::new(1.into(), 2.into())]
                .into_iter()
                .map(|a| &t + (a - &z) / &slope)
                .filter(|r| r > &t)
                .collect::<Vec<_>>();
            candidates.sort();
            let root = candidates[0].clone();
            controller
                .accept_history_events(&model, &trajectory, &mut calendar)
                .unwrap();
            let e = q(controller.accepted.time);
            assert!(e > root && &e - &root <= q(1e-9));
            z += &slope * (&e - &t);
            t = e;
            slope = -slope;
            let guard = &z * &z - R::new(1.into(), 4.into());
            assert!(guard.abs() <= q(1e-8));
            assert_eq!(guard.is_positive(), n == 1);
            assert_eq!(
                controller.accepted.states,
                vec![slope.to_f64().unwrap(), n as f64]
            );
            let index = model.program.nodes.iter().position(|n| n == "z").unwrap();
            let actual = q(controller.accepted.solution.voltages[index]);
            let budget = q(model.tolerances.absolute) + q(model.tolerances.relative) * z.abs();
            assert!((actual - &z).abs() <= budget);
            assert_eq!(controller.records.len(), n);
            let mut next_roots = [R::new((-1).into(), 2.into()), R::new(1.into(), 2.into())]
                .into_iter()
                .map(|a| &t + (a - &z) / &slope)
                .filter(|r| r > &t)
                .collect::<Vec<_>>();
            next_roots.sort();
            let box_ = calendar[0].bounds();
            assert!(q(box_.lo) <= next_roots[0] && next_roots[0] <= q(box_.hi));
            if n == 1 {
                assert_eq!(calendar.len(), 2, "later root must remain in calendar");
            }
            println!("speed={speed:?} accepted={n} mathematical_root={root:?}, execution={:?}, future_roots={}",controller.accepted.time,calendar.len());
        }
    }
}
