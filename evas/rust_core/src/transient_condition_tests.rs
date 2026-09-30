//! Condition failures and discarded paths must not alter an accepted frame.
use super::*;
use crate::ir::{Program, Tolerances, TransientInputs};
use serde_json::{json, Value};

fn source(points: &[[f64; 2]]) -> Trajectory {
    Trajectory::new(
        TransientInputs {
            pwl: vec![points.to_vec()],
            output_times: vec![0.0, 1.0],
            stop: 1.0,
            max_step: 1.0,
        },
        1,
    )
    .unwrap()
}

fn fixture(body: Value, history: bool, points: &[[f64; 2]]) -> (EventModel, Trajectory, Frame) {
    let origin = json!({"source":"conditions.va","line":2,"column":1,"instance":"dut"});
    let operators = if history {
        json!([{"kind":"transition","input":{"op":"state","state":0},
        "delay":0,"rise":0.25,"fall":0.25,"origin":origin}])
    } else {
        json!([])
    };
    let program: Program = serde_json::from_value(json!({
        "schema_version":SCHEMA_VERSION,"nodes":["0","u","y"],
        "states":[{"instance":"dut","name":"q","kind":"real","initial":2}],
        "events":[{"trigger":{"kind":"timer","start":0.25,"period":0.25,"time_tolerance":0.001,"enabled":true},
            "origin":origin,"body":body}],
        "operators":operators,
        "contributions":[{"branch":{"instance":"dut","local_positive":"r","local_negative":"y","kind":"voltage"},
            "positive":0,"negative":2,"origin":origin,
            "rhs":{"op":"multiply","left":{"op":"affine","constant":-1,"terms":[]},
                "right":if history {json!({"op":"operator","operator":0})} else {json!({"op":"state","state":0})}}}]
    })).unwrap();
    let model = EventModel::new(program, vec!["u".into()], Tolerances::default()).unwrap();
    let trajectory = source(points);
    let states = model.initial();
    let operators = Operators::new(&model.program, &trajectory, &model.driven, &states).unwrap();
    let circuit = model
        .circuit_with(&states, &operators.values(0.0).unwrap())
        .unwrap();
    let frame = Frame {
        time: 0.0,
        state_bounds: states.iter().copied().map(I::point).collect(),
        states,
        solution: circuit.solve(&trajectory.values(0.0)).unwrap(),
        circuit,
        operators,
    };
    (model, trajectory, frame)
}

fn conditional(threshold: f64, yes: Value, no: Value) -> Value {
    json!([{"kind":"if","relation":"ge",
        "left":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]},
        "right":{"op":"affine","constant":threshold,"terms":[]},
        "then_body":yes,"else_body":no,
        "origin":{"source":"conditions.va","line":3,"column":1,"instance":"dut"}}])
}

fn increment(amount: f64) -> Value {
    json!([{"kind":"assign","state":0,"rhs":{"op":"add","left":{"op":"state","state":0},
        "right":{"op":"affine","constant":amount,"terms":[]}}}])
}

fn set(value: f64) -> Value {
    json!([{"kind":"assign","state":0,"rhs":{"op":"affine","constant":value,"terms":[]}}])
}

#[test]
fn failed_condition_and_discard_preserve_nonzero_history_and_retry_path() {
    let points = [[0.0, 1.0], [0.25, 1.0], [0.5, 0.1], [1.0, 0.9]];
    let (model, trajectory, initial) = fixture(
        conditional(0.5, increment(1.0), increment(2.0)),
        true,
        &points,
    );
    let (first, records) = prepare_batch(&model, &trajectory, &initial, 0.25, &[0]).unwrap();
    assert_eq!(records.len(), 1);
    let accepted = prepare_event(&model, &trajectory, &first, 0.5, &[]).unwrap();
    assert_eq!(accepted.states, [3.0]);
    assert_eq!(accepted.operators.values(0.5).unwrap(), [3.0]);
    let before_bounds = accepted.operators.bounds(0.5).unwrap();
    // Successful false-arm trial is discarded, then the next predicate fails.
    let (discarded, _) = prepare_batch(&model, &trajectory, &accepted, 0.625, &[0]).unwrap();
    assert_eq!(discarded.states, [5.0]);
    for _ in 0..2 {
        assert_eq!(
            prepare_batch(&model, &trajectory, &accepted, 0.75, &[0])
                .err()
                .unwrap()
                .kind,
            "event_condition"
        );
        assert_eq!(accepted.time, 0.5);
        assert_eq!(accepted.states, [3.0]);
        assert_eq!(accepted.solution.voltages[2], 3.0);
        assert_eq!(accepted.operators.values(0.5).unwrap(), [3.0]);
        assert_eq!(accepted.operators.bounds(0.5).unwrap(), before_bounds);
        assert_eq!(accepted.operators.next_breakpoint(0.5), None);
    }
    let corrected = source(&[[0.0, 1.0], [0.25, 1.0], [0.5, 0.1], [1.0, 1.7]]);
    let (retry, records) = prepare_batch(&model, &corrected, &accepted, 0.75, &[0]).unwrap();
    assert_eq!(retry.states, [4.0]);
    assert_eq!(records.len(), 1);
    assert_eq!(records[0].before, [3.0]);
    assert_eq!(retry.operators.values(0.75).unwrap(), [3.0]);
    assert_eq!(retry.operators.values(0.875).unwrap(), [3.5]);
    // Same accepted state in a fresh model/cache must give identical history.
    let (fresh, same_source, start) = fixture(
        conditional(0.5, increment(1.0), increment(2.0)),
        true,
        &[[0.0, 1.0], [0.25, 1.0], [0.5, 0.1], [1.0, 1.7]],
    );
    let (one, _) = prepare_batch(&fresh, &same_source, &start, 0.25, &[0]).unwrap();
    let two = prepare_event(&fresh, &same_source, &one, 0.5, &[]).unwrap();
    let (control, _) = prepare_batch(&fresh, &same_source, &two, 0.75, &[0]).unwrap();
    assert_eq!(retry.state_bounds, control.state_bounds);
    assert_eq!(retry.solution.voltages, control.solution.voltages);
    assert_eq!(
        retry.operators.bounds(0.875).unwrap(),
        control.operators.bounds(0.875).unwrap()
    );
}

#[test]
fn sampled_uncertainty_survives_empty_steps_and_unwritten_arm_without_operators() {
    let sample = json!([{"kind":"assign","state":0,"rhs":{"op":"affine","constant":0,
        "terms":[{"node":1,"coefficient":1}]}}]);
    let (model, trajectory, initial) = fixture(
        conditional(0.75, json!([]), sample),
        false,
        &[[0.0, 0.1], [1.0, 0.9]],
    );
    let accepted = prepare_event(&model, &trajectory, &initial, 0.5, &[0]).unwrap();
    assert_eq!(accepted.states, [0.5]);
    assert!(accepted.state_bounds[0].lo < accepted.state_bounds[0].hi);
    for (time, events) in [(0.625, vec![]), (1.0, vec![0])] {
        let next = prepare_event(&model, &trajectory, &accepted, time, &events).unwrap();
        assert_eq!(next.states, accepted.states);
        assert_eq!(next.state_bounds, accepted.state_bounds);
        let selection = model
            .conditions
            .select(&events, &trajectory.value_bounds(time))
            .unwrap();
        assert!(model.assigned(&selection).is_empty());
    }
}

#[test]
fn failed_sample_certificate_and_changed_arm_retry_preserve_frame() {
    let sample = json!([{"kind":"assign","state":0,"rhs":{"op":"affine","constant":-0.5,
        "terms":[{"node":1,"coefficient":1}]}}]);
    let (model, trajectory, initial) = fixture(
        conditional(0.25, sample, increment(1.0)),
        false,
        &[[0.0, 0.1], [1.0, 0.9]],
    );
    for _ in 0..2 {
        assert_eq!(
            prepare_batch(&model, &trajectory, &initial, 0.5, &[0])
                .err()
                .unwrap()
                .kind,
            "event_accuracy"
        );
        assert_eq!(initial.states, [2.0]);
        assert_eq!(initial.state_bounds, [I::point(2.0)]);
        assert_eq!(initial.solution.voltages[2], 2.0);
    }
    let corrected = source(&[[0.0, 0.1], [1.0, 0.1]]);
    let (retry, records) = prepare_batch(&model, &corrected, &initial, 0.5, &[0]).unwrap();
    assert_eq!(retry.states, [3.0]);
    assert_eq!(records.len(), 1);
}

#[test]
fn rejected_or_batch_preserves_history_and_retry_executes_body_once() {
    let (single, trajectory, accepted) = fixture(increment(1.0), true, &[[0.0, 0.0], [1.0, 1.0]]);
    let mut program = single.program.clone();
    let leaf = EventTrigger::Cross {
        guard: crate::ir::Expression::Affine {
            constant: -0.5,
            terms: vec![crate::ir::Term {
                node: 1,
                coefficient: 1.0,
            }],
        },
        direction: 1,
        time_tolerance: 0.001,
        expression_tolerance: 0.001,
    };
    program.events[0].trigger = EventTrigger::Or {
        triggers: vec![leaf.clone(), leaf],
    };
    let model = EventModel::new(program.clone(), vec!["u".into()], Tolerances::default()).unwrap();
    let original_history = accepted.operators.bounds(0.75).unwrap();
    // Failure is after candidate settlement/history preparation, at leaf acceptance.
    for _ in 0..2 {
        let error = prepare_batch(&model, &trajectory, &accepted, 0.75, &[0, 1])
            .err()
            .unwrap();
        assert_eq!(error.kind, "event_resolution");
        assert_eq!(accepted.time, 0.0);
        assert_eq!(accepted.states, [2.0]);
        assert_eq!(accepted.operators.bounds(0.75).unwrap(), original_history);
    }
    let (retry, records) = prepare_batch(&model, &trajectory, &accepted, 0.5, &[0, 1]).unwrap();
    let fresh = EventModel::new(program, vec!["u".into()], Tolerances::default()).unwrap();
    let (control, clean_records) =
        prepare_batch(&fresh, &trajectory, &accepted, 0.5, &[0, 1]).unwrap();
    assert_eq!(retry.states, [3.0]);
    assert_eq!(retry.states, control.states);
    assert_eq!(retry.state_bounds, control.state_bounds);
    assert_eq!(
        retry.operators.bounds(1.0).unwrap(),
        control.operators.bounds(1.0).unwrap()
    );
    assert_eq!(records.len(), 1);
    assert_eq!(records[0].fired_triggers.len(), 2);
    assert_eq!(
        serde_json::to_value(records).unwrap(),
        serde_json::to_value(clean_records).unwrap()
    );
}

#[test]
fn simultaneous_cross_block_state_writers_fail_without_committing_history() {
    let (single, trajectory, accepted) = fixture(set(3.0), true, &[[0.0, 0.0], [1.0, 1.0]]);
    let mut program = single.program.clone();
    program.events.push(
        serde_json::from_value(json!({"trigger":{"kind":"timer","start":0.25,"period":0.25,
            "time_tolerance":0.001,"enabled":true},
            "origin":{"source":"conditions.va","line":4,"column":1,"instance":"dut"},
            "body":[{"kind":"assign","state":0,"rhs":{"op":"affine","constant":7.0,
                "terms":[]}}]}))
        .unwrap(),
    );
    let model = EventModel::new(program, vec!["u".into()], Tolerances::default()).unwrap();
    let original_history = accepted.operators.bounds(0.5).unwrap();
    for _ in 0..2 {
        let error = prepare_batch(&model, &trajectory, &accepted, 0.25, &[0, 1])
            .err()
            .unwrap();
        assert_eq!(error.kind, "event_conflict");
        assert_eq!(accepted.time, 0.0);
        assert_eq!(accepted.states, [2.0]);
        assert_eq!(accepted.state_bounds, [I::point(2.0)]);
        assert_eq!(accepted.operators.bounds(0.5).unwrap(), original_history);
    }
    let (first_only, records) = prepare_batch(&model, &trajectory, &accepted, 0.25, &[0]).unwrap();
    assert_eq!(first_only.states, [3.0]);
    assert_eq!(records.len(), 1);
    let (second_only, _) = prepare_batch(&model, &trajectory, &accepted, 0.25, &[1]).unwrap();
    assert_eq!(second_only.states, [7.0]);
}
