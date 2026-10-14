//! Calendar replacement must publish states, histories and records atomically.
use super::*;

// One program family covers both calendar strategies. The otherwise unreachable
// h=2 cross makes History use its real operator-dependent guard path.
fn program(history: bool, shape: &str) -> Program {
    let origin = json!({"source":"timer_boundary.va","line":1,"column":1,"instance":"dut"});
    let constant = |x: f64| json!({"op":"affine","constant":x,"terms":[]});
    let state = |s: usize| json!({"op":"state","state":s});
    let assign = |s: usize, rhs: serde_json::Value| json!({"kind":"assign","state":s,"rhs":rhs});
    let increment = |s| assign(s, json!({"op":"add","left":state(s),"right":constant(1.)}));
    let display =
        |s| json!({"kind":"display","format":"count %g","args":[state(s)],"origin":origin});
    let timer = |start: f64, period: f64| json!({"kind":"timer","start":start,"period":period,"enabled":true,"time_tolerance":if period==0. {0.} else {1e-12}});
    let held = |period| json!({"kind":"held_timer","start":state(0),"period":period,"enabled":constant(1.),"time_tolerance":0.001});
    let event = |trigger, body: Vec<serde_json::Value>| json!({"trigger":trigger,"body":body,"origin":origin});
    // Integer counters only increase; these branch conditions select the same
    // first/second occurrences as n==0 and k==2 in the public VA fixtures.
    let at_most = |s, n, body: Vec<serde_json::Value>| json!({"kind":"if","relation":"le","left":state(s),"right":constant(n),"then_body":body,"else_body":[],"origin":origin});
    let input = json!({"op":"affine","constant":0.,"terms":[{"node":1,"coefficient":1.}]});
    let warm = event(timer(0.125, 0.), vec![increment(2), display(2)]);
    let mut events = match shape {
        "other" => vec![
            warm,
            event(timer(0.5, 0.), vec![assign(0, input.clone()), display(0)]),
            event(held(constant(0.)), vec![increment(1), display(1)]),
        ],
        "or" => vec![
            warm,
            event(
                json!({"kind":"or","triggers":[timer(0.5,0.),held(constant(0.))]}),
                vec![
                    at_most(1, 0., vec![assign(0, input.clone())]),
                    increment(1),
                    display(1),
                ],
            ),
        ],
        "window" | "phase" => {
            let second = json!({"kind":"if","relation":"ge","left":state(2),"right":constant(2.),"then_body":[at_most(2,2.,vec![assign(0,input.clone())])],"else_body":[],"origin":origin});
            let mut events = vec![
                event(timer(0.1, 0.2), vec![increment(2), second, display(2)]),
                event(held(constant(0.)), vec![increment(1)]),
            ];
            if shape == "phase" {
                events.push(event(timer(0.3, 0.), vec![increment(1), display(1)]));
            }
            events
        }
        "period" => vec![event(
            held(state(3)),
            vec![
                increment(1),
                json!({"kind":"if","relation":"ge","left":state(1),"right":constant(2.),"then_body":[at_most(1,2.,vec![assign(3,constant(0.25))])],"else_body":[],"origin":origin}),
                display(1),
            ],
        )],
        _ => panic!("unknown timer boundary case"),
    };
    if history {
        events.push(event(json!({"kind":"cross","guard":{"op":"affine","constant":-2.,"terms":[{"node":4,"coefficient":1.}]},"direction":1,"time_tolerance":1e-12,"expression_tolerance":1e-8}),vec![assign(2,state(2))]));
    }
    let contribution = |node, rhs| json!({"branch":{"instance":"dut","local_positive":format!("n{node}"),"local_negative":"r","kind":"voltage"},"positive":node,"negative":0,"rhs":rhs,"origin":origin});
    serde_json::from_value(json!({
        "schema_version":SCHEMA_VERSION,"nodes":["0","u","y","z","h"],
        "states":[{"instance":"dut","name":"b","kind":"real","initial":if shape=="period" {0.} else {0.75}},
            {"instance":"dut","name":"n","kind":"integer","initial":0.},
            {"instance":"dut","name":"k","kind":"integer","initial":0.},
            {"instance":"dut","name":"p","kind":"real","initial":0.5}],
        "events":events,"operators":[{"kind":"idt","input":constant(1.),"ic":0.75,"origin":origin}],
        "contributions":[contribution(2,state(1)),contribution(3,state(2)),contribution(4,json!({"op":"operator","operator":0}))]
    })).unwrap()
}

fn trajectory(shape: &str, bad: bool) -> Trajectory {
    let window = matches!(shape, "window" | "phase");
    let pwl = if window {
        if bad {
            vec![[0., 0.], [0.1, 0.1], [1., 1.]]
        } else {
            vec![[0., 0.], [0.1, 0.1], [0.5, 1.2], [1., 1.]]
        }
    } else if bad {
        vec![[0., 0.], [0.125, 0.125], [0.5, 0.5], [1., 1.]]
    } else {
        vec![[0., 0.], [0.125, 0.125], [0.5, 0.875], [1., 1.]]
    };
    Trajectory::new(
        TransientInputs {
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
    shape: &str,
) -> (
    EventModel,
    Trajectory,
    Trajectory,
    Controller,
    Vec<ScheduledEvent>,
) {
    let model = EventModel::new(
        program(history, shape),
        vec!["u".into()],
        Tolerances {
            absolute: 1e-8,
            relative: 0.,
        },
    )
    .unwrap();
    let good = trajectory(shape, false);
    let bad = trajectory(shape, true);
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

fn signature(
    calendar: &[ScheduledEvent],
) -> Vec<(
    usize,
    u64,
    u64,
    u64,
    Option<std::cmp::Ordering>,
    Option<std::cmp::Ordering>,
)> {
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

fn rollback_then_retry(history: bool, shape: &str) {
    let (model, good, bad, mut controller, mut calendar) = fixture(history, shape);
    if shape == "or" {
        // Actual flattened leaf IDs 1 and 2 share body 1. A body ID set
        // would incorrectly bless the unconsumed held leaf at the retry boundary.
        assert_eq!(model.triggers[1].event, model.triggers[2].event);
        assert_ne!(calendar[1].event, calendar[2].event);
    }
    accept(&mut controller, &model, &good, &mut calendar, history).unwrap();
    assert_eq!(controller.records.len(), 1);
    assert!(!controller.records[0].display_records.is_empty());
    assert!(!controller.outputs.is_empty());
    assert_integral_ic(&model, &controller.accepted);
    let accepted = controller.accepted.clone();
    let records = serde_json::to_value(&controller.records).unwrap();
    let outputs = controller.outputs.clone();
    let cursor = controller.event;
    let calendar_signature = signature(&calendar);
    if shape == "phase" {
        assert_eq!(calendar[cursor].time, 0.3);
        assert!(calendar[cursor + 1].bounds().lo <= 0.3 && calendar[cursor + 1].time > 0.3);
    } else if shape == "window" {
        assert!(
            calendar[cursor].bounds().lo < calendar[cursor].bounds().hi,
            "the incoming .1+.2 nominal clock must really be nonpoint"
        );
    } else {
        assert_eq!(calendar[cursor].bounds(), I::point(0.5));
    }
    // SAME model, SAME Controller, SAME pending Vec and accepted histories.
    // Good/bad trajectories agree over the entire already accepted prefix;
    // only the candidate's future external source changes.
    assert_eq!(good.values(accepted.time), bad.values(accepted.time));
    for _ in 0..2 {
        let error = accept(&mut controller, &model, &bad, &mut calendar, history).unwrap_err();
        eprintln!(
            "timer refusal {shape} history={history}: {} {}",
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
    let (fresh_model, fresh_good, _, mut clean, mut clean_calendar) = fixture(history, shape);
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
    assert_eq!(
        controller.records.len(),
        if shape == "phase" { 3 } else { 2 }
    );
    if shape == "phase" {
        assert_eq!(controller.records[1].time, 0.3);
        assert!(controller.records[2].time > 0.3);
        let n = model
            .program
            .states
            .iter()
            .position(|s| s.name == "n")
            .unwrap();
        assert_eq!(controller.accepted.states[n], 1.);
    }
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
        for shape in ["other", "or", "window", "phase"] {
            eprintln!("timer boundary case: {shape}, history={history}");
            rollback_then_retry(history, shape);
        }
    }
}

fn period_index_control(history: bool) {
    let (model, good, _, mut controller, mut calendar) = fixture(history, "period");
    for expected_time in [0., 0.5, 0.75, 1.] {
        assert_eq!(calendar[controller.event].time, expected_time);
        accept(&mut controller, &model, &good, &mut calendar, history).unwrap();
        assert_eq!(controller.accepted.time, expected_time);
        assert_integral_ic(&model, &controller.accepted);
        if expected_time == 0.5 {
            // Old clock index1 and new index2 are the SAME physical .5.
            // The leaf was actually consumed and must not reject/refire.
            assert_eq!(calendar[controller.event].time, 0.75);
            let p = model
                .program
                .states
                .iter()
                .position(|s| s.name == "p")
                .unwrap();
            assert_eq!(controller.accepted.states[p], 0.25);
        }
    }
    assert_eq!(
        controller
            .records
            .iter()
            .map(|r| r.time)
            .collect::<Vec<_>>(),
        vec![0., 0.5, 0.75, 1.]
    );
    let n = model
        .program
        .states
        .iter()
        .position(|s| s.name == "n")
        .unwrap();
    assert_eq!(controller.accepted.states[n], 4.);
}
#[test]
fn consumed_clock_with_changed_period_index_fires_once() {
    for history in [false, true] {
        period_index_control(history);
    }
}
