//! A rejected held-timer replacement must not publish candidate state or history.
use super::*;
use crate::ir::{Program, Tolerances, TransientInputs};
use serde_json::json;

// One program family covers both calendar strategies. The otherwise unreachable
// h=2 cross makes History use its real operator-dependent guard path.
fn program(history: bool) -> Program {
    let origin = json!({"source":"timer_boundary.va","line":1,"column":1,"instance":"dut"});
    let constant = |x: f64| json!({"op":"affine","constant":x,"terms":[]});
    let state = |s: usize| json!({"op":"state","state":s});
    let assign = |s: usize, rhs: serde_json::Value| json!({"kind":"assign","state":s,"rhs":rhs});
    let increment = |s| assign(s, json!({"op":"add","left":state(s),"right":constant(1.)}));
    let timer = |start: f64| json!({"kind":"timer","start":start,"period":0.,"enabled":true,"time_tolerance":1e-12});
    let held = json!({"kind":"held_timer","start":state(0),"period":constant(0.),"enabled":constant(1.),"time_tolerance":0.001});
    let event = |trigger, body: Vec<serde_json::Value>| json!({"trigger":trigger,"body":body,"origin":origin});
    let input = json!({"op":"affine","constant":0.,"terms":[{"node":1,"coefficient":1.}]});
    let mut events = vec![
        event(timer(0.125), vec![increment(2)]),
        event(timer(0.5), vec![assign(0, input)]),
        event(held, vec![increment(1)]),
    ];
    if history {
        events.push(event(json!({"kind":"cross","guard":{"op":"affine","constant":-2.,"terms":[{"node":4,"coefficient":1.}]},"direction":1,"time_tolerance":1e-12,"expression_tolerance":1e-8}),vec![assign(2,state(2))]));
    }
    let contribution = |node, rhs| json!({"branch":{"instance":"dut","local_positive":format!("n{node}"),"local_negative":"r","kind":"voltage"},"positive":node,"negative":0,"rhs":rhs,"origin":origin});
    serde_json::from_value(json!({
        "schema_version":SCHEMA_VERSION,"nodes":["0","u","y","z","h"],
        "states":[{"instance":"dut","name":"b","kind":"real","initial":0.75},
            {"instance":"dut","name":"n","kind":"integer","initial":0.},
            {"instance":"dut","name":"k","kind":"integer","initial":0.},
            {"instance":"dut","name":"p","kind":"real","initial":0.5}],
        "events":events,"operators":[{"kind":"idt","input":constant(1.),"ic":0.75,"origin":origin}],
        "contributions":[contribution(2,state(1)),contribution(3,state(2)),contribution(4,json!({"op":"operator","operator":0}))]
    })).unwrap()
}

fn trajectory(bad: bool) -> Trajectory {
    let pwl = if bad {
        vec![[0., 0.], [0.125, 0.125], [0.5, 0.5], [1., 1.]]
    } else {
        vec![[0., 0.], [0.125, 0.125], [0.5, 0.875], [1., 1.]]
    };
    Trajectory::new(
        TransientInputs {
            pwl_errors_v: None,
            pwl: vec![pwl],
            strobetimes: vec![0., 0.125, 0.25, 0.5, 0.75, 1.],
            output_times: vec![0., 0.0625, 1.],
            stop: 1.,
            max_step: 1.,
        },
        1,
    )
    .unwrap()
}

fn fixture(
    history: bool,
) -> (
    EventModel,
    Trajectory,
    Trajectory,
    Controller,
    Vec<ScheduledEvent>,
) {
    let model = EventModel::new(
        program(history),
        vec!["u".into()],
        Tolerances {
            absolute: 1e-8,
            relative: 0.,
        },
    )
    .unwrap();
    let good = trajectory(false);
    let bad = trajectory(true);
    let states = model.initial();
    let state_bounds: Vec<_> = states.iter().copied().map(I::point).collect();
    let (operators, calendar) = if history {
        assert!(model.guard_operators.iter().any(|v| !v.is_empty()));
        history_calendar::initialize(&model, &good, &states).unwrap()
    } else {
        assert!(model.guard_operators.iter().all(|v| v.is_empty()));
        let calendar = schedule_held(&model, &good, &state_bounds).unwrap();
        let operators = Operators::new_until(
            &model.program,
            &good,
            &model.driven,
            &states,
            prediction_end(&model, &good, calendar.first()),
            &model.tolerances,
        )
        .unwrap();
        (operators, calendar)
    };
    let circuit = model
        .circuit_with(&states, &operators.values(0.).unwrap())
        .unwrap();
    let accepted = Frame {
        value_proofs: Default::default(),
        time_proofs: Default::default(),
        time: 0.,
        solution: circuit.solve(&good.values(0.)).unwrap(),
        circuit,
        operators,
        states,
        state_bounds,
    };
    // The warm event prepares the real 0.0625 query, so rollback checks
    // exercise a nonempty accepted output buffer.
    (
        model,
        good,
        bad,
        Controller {
            accepted,
            event: 0,
            records: vec![],
            outputs: Vec::new(),
        },
        calendar,
    )
}

fn accept(
    controller: &mut Controller,
    model: &EventModel,
    trajectory: &Trajectory,
    calendar: &mut Vec<ScheduledEvent>,
    history: bool,
) -> Result<(), Error> {
    controller.accept_changed_events(
        model,
        trajectory,
        calendar,
        if history {
            event_acceptance::Strategy::History
        } else {
            event_acceptance::Strategy::Held
        },
    )
}

type CalendarEntry = (
    usize,
    u64,
    u64,
    u64,
    Option<std::cmp::Ordering>,
    Option<std::cmp::Ordering>,
);

fn signature(calendar: &[ScheduledEvent]) -> Vec<CalendarEntry> {
    calendar
        .iter()
        .map(|e| {
            (
                e.event,
                e.time.to_bits(),
                e.bounds().lo.to_bits(),
                e.bounds().hi.to_bits(),
                e.physical_order_at(0.5),
                e.physical_order_at(0.75),
            )
        })
        .collect()
}

fn same_frame(actual: &Frame, expected: &Frame) {
    assert_eq!(actual.time.to_bits(), expected.time.to_bits());
    assert_eq!(actual.states, expected.states);
    assert_eq!(actual.state_bounds, expected.state_bounds);
    assert_eq!(actual.solution.voltages, expected.solution.voltages);
    assert!(actual.operators.same_reset_history(&expected.operators));
    assert_eq!(
        actual.operators.values(actual.time).unwrap(),
        expected.operators.values(expected.time).unwrap()
    );
    assert_eq!(
        actual.operators.bounds(actual.time).unwrap(),
        expected.operators.bounds(expected.time).unwrap()
    );
}

fn assert_integral_ic(model: &EventModel, frame: &Frame) {
    let h = model.program.nodes.iter().position(|n| n == "h").unwrap();
    // Independent analytic history h(t)=3/4+t; it cannot be reset to zero
    // or seeded from the sampled held timer's new start.
    assert!((frame.solution.voltages[h] - (0.75 + frame.time)).abs() <= 1e-8);
}

fn rollback_then_retry(history: bool) {
    let (model, good, bad, mut controller, mut calendar) = fixture(history);
    accept(&mut controller, &model, &good, &mut calendar, history).unwrap();
    assert_eq!(controller.records.len(), 1);
    assert!(!controller.outputs.is_empty());
    assert_integral_ic(&model, &controller.accepted);
    let accepted = controller.accepted.clone();
    let records = serde_json::to_value(&controller.records).unwrap();
    let outputs = controller.outputs.clone();
    let cursor = controller.event;
    let calendar_signature = signature(&calendar);
    assert_eq!(calendar[cursor].bounds(), I::point(0.5));
    // SAME model, SAME Controller, SAME pending Vec and accepted histories.
    // Good/bad trajectories agree over the entire already accepted prefix;
    // only the candidate's future external source changes.
    assert_eq!(good.values(accepted.time), bad.values(accepted.time));
    for _ in 0..2 {
        let error = accept(&mut controller, &model, &bad, &mut calendar, history).unwrap_err();
        eprintln!(
            "timer refusal history={history}: {} {}",
            error.kind, error.message
        );
        assert_eq!(error.kind, "event_resolution");
        assert!(
            error.message.contains("timer"),
            "unexpected refusal: {}",
            error.message
        );
        same_frame(&controller.accepted, &accepted);
        assert_eq!(controller.event, cursor);
        assert_eq!(signature(&calendar), calendar_signature);
        assert_eq!(serde_json::to_value(&controller.records).unwrap(), records);
        assert_eq!(controller.outputs.len(), outputs.len());
        for (a, b) in controller.outputs.iter().zip(&outputs) {
            same_frame(a, b);
        }
    }
    // Retry the same model and same object under the legal future source.
    accept(&mut controller, &model, &good, &mut calendar, history).unwrap();
    let (fresh_model, fresh_good, _, mut clean, mut clean_calendar) = fixture(history);
    accept(
        &mut clean,
        &fresh_model,
        &fresh_good,
        &mut clean_calendar,
        history,
    )
    .unwrap();
    accept(
        &mut clean,
        &fresh_model,
        &fresh_good,
        &mut clean_calendar,
        history,
    )
    .unwrap();
    same_frame(&controller.accepted, &clean.accepted);
    assert_eq!(signature(&calendar), signature(&clean_calendar));
    assert_eq!(controller.event, clean.event);
    assert_eq!(
        serde_json::to_value(&controller.records).unwrap(),
        serde_json::to_value(&clean.records).unwrap()
    );
    assert_eq!(controller.records.len(), 2);
    assert_eq!(controller.outputs.len(), clean.outputs.len());
    for (a, b) in controller.outputs.iter().zip(&clean.outputs) {
        same_frame(a, b);
    }
    assert_integral_ic(&model, &controller.accepted);
    let b = model
        .program
        .states
        .iter()
        .position(|s| s.name == "b")
        .unwrap();
    assert!(controller.accepted.state_bounds[b].lo > controller.accepted.time);
    assert!(calendar.iter().any(|e| matches!(
        model.triggers[e.event].trigger,
        EventTrigger::HeldTimer { .. }
    )));
}

#[test]
fn changed_timer_failure_is_atomic_and_retryable_in_both_calendars() {
    for history in [false, true] {
        rollback_then_retry(history);
    }
}

fn live_filter_fixture() -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    let mut p = program(false);
    let origin = json!({"source":"live_filter_rollback.va","line":1,"column":1,"instance":"dut"});
    p.operators=serde_json::from_value(json!([
        {"kind":"transition","input":{"op":"state","state":2},"delay":0,"rise":0.5,"fall":0.5,"origin":origin},
        {"kind":"laplace_nd","input":{"op":"multiply","left":{"op":"affine","constant":2,"terms":[{"node":1,"coefficient":1}]},"right":{"op":"operator","operator":0}},"numerator":[1],"denominator":[1,0.25],"origin":{"source":"live_filter_rollback.va","line":1,"column":2,"instance":"dut"}}
    ])).unwrap();
    p.contributions[2].rhs = serde_json::from_value(json!({"op":"operator","operator":1})).unwrap();
    p.events[1].body.push(
        serde_json::from_value(
            json!({"kind":"assign","state":2,"rhs":{"op":"affine","constant":0,"terms":[]}}),
        )
        .unwrap(),
    );
    p.events.push(serde_json::from_value(json!({"trigger":{"kind":"timer","start":0.25,"period":0,"enabled":true,"time_tolerance":1e-12},"body":[{"kind":"assign","state":2,"rhs":{"op":"state","state":2}}],"origin":origin})).unwrap());
    let model = EventModel::new(
        p,
        vec!["u".into()],
        Tolerances {
            absolute: 1e-8,
            relative: 0.,
        },
    )
    .unwrap();
    let trajectory = trajectory(false);
    let states = model.initial();
    let state_bounds = states.iter().copied().map(I::point).collect::<Vec<_>>();
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
        value_proofs: Default::default(),
        time_proofs: Default::default(),
        time: 0.,
        solution: circuit.solve(&trajectory.values(0.)).unwrap(),
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
            outputs: vec![],
        },
        calendar,
    )
}

#[test]
fn live_filter_installed_candidate_final_gate_failure_retries_same_controller() {
    let (model, trajectory, mut controller, mut calendar) = live_filter_fixture();
    for _ in 0..2 {
        accept(&mut controller, &model, &trajectory, &mut calendar, false).unwrap();
    }
    let accepted = controller.accepted.clone();
    assert_eq!(accepted.time, 0.25);
    // Independent quadratic ramp response from the original source segment:
    // at .125, e=0, u=.125, e'=2, u'=2, hence p=4.25*s+4*s².
    let expected = -0.21875 + 0.5625 * (-0.5_f64).exp();
    assert!((accepted.solution.voltages[4] - expected).abs() < 1e-11);
    assert!(accepted.solution.voltages[4] > 0.);
    let old_future = accepted.operators.bounds(0.75).unwrap();
    let old_calendar = signature(&calendar);
    let old_records = serde_json::to_value(&controller.records).unwrap();
    let old_cursor = controller.event;
    let (mut candidate, _records, end) = controller
        .prepare_events_until(&model, &trajectory, &calendar, Some(0.5))
        .unwrap();
    assert_eq!(candidate.time, 0.5);
    assert_eq!(candidate.states[2], 0.);
    assert!(!candidate.operators.same_reset_history(&accepted.operators));
    assert!(candidate.solution.voltages[4] > accepted.solution.voltages[4]);
    assert!(
        (candidate.solution.voltages[4] - candidate.operators.values(0.5).unwrap()[1]).abs()
            < 1e-12
    );
    // The real candidate already consumed old forcing and installed the new
    // parent target. Fail only its final observation certification afterwards.
    candidate.solution.voltages[4] += 0.01;
    let error = Controller::prepare_final_history(
        &model,
        &trajectory,
        candidate,
        event_acceptance::CalendarPlan::Held(calendar[end..].to_vec()),
    )
    .err()
    .unwrap();
    assert_eq!(error.kind, "waveform_accuracy");
    assert!(
        error.message.contains("same-time forward error at h:"),
        "{}",
        error.message
    );
    same_frame(&controller.accepted, &accepted);
    assert_eq!(
        controller.accepted.operators.bounds(0.75).unwrap(),
        old_future
    );
    assert_eq!(signature(&calendar), old_calendar);
    assert_eq!(controller.event, old_cursor);
    assert_eq!(
        serde_json::to_value(&controller.records).unwrap(),
        old_records
    );
    accept(&mut controller, &model, &trajectory, &mut calendar, false).unwrap();
    let (clean_model, clean_trajectory, mut clean, mut clean_calendar) = live_filter_fixture();
    for _ in 0..3 {
        accept(
            &mut clean,
            &clean_model,
            &clean_trajectory,
            &mut clean_calendar,
            false,
        )
        .unwrap();
    }
    same_frame(&controller.accepted, &clean.accepted);
    assert_eq!(signature(&calendar), signature(&clean_calendar));
    assert_eq!(
        controller.accepted.operators.bounds(0.75).unwrap(),
        clean.accepted.operators.bounds(0.75).unwrap()
    );
}
