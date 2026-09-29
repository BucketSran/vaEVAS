//! Same-engine integration probes after accepting nonzero integral history.
use super::*;
use crate::ir::{Program, Tolerances, TransientInputs};
use serde_json::{json, Value};

const GAIN: f64 = 1073741824.0;
const ICS: [f64; 4] = [1.25, -0.5, 3.0, -2.0];
const SCALES: [f64; 4] = [1.0, -2.0, 2.0, 0.5];

fn source(tail: f64) -> Trajectory {
    Trajectory::new(
        TransientInputs {
            // Every corrected source preserves the complete accepted [0,1].
            pwl: vec![vec![[0.0, -1.0], [1.0, -1.0], [3.0, tail]]],
            output_times: vec![0.0, 1.0, 2.0, 3.0],
            stop: 3.0,
            max_step: 3.0,
        },
        1,
    )
    .unwrap()
}

fn fixture() -> (EventModel, Trajectory, Frame) {
    let mut operators = Vec::new();
    let mut contributions = Vec::new();
    let mut states = Vec::new();
    let mut events = Vec::new();
    for (instance, name) in ["a", "b"].into_iter().enumerate() {
        // Both instances reuse source coordinates. Each contributes two idt
        // calls to ONE branch, so neither target nor source location is a key.
        let origin =
            |line| json!({"source":"integrator.va","line":line,"column":1,"instance":name});
        for slot in 0..2 {
            let index = 2 * instance + slot;
            operators.push(json!({"kind":"idt", "ic":ICS[index], "origin":origin(10+slot),
                "input":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":SCALES[index]}]}}));
            contributions.push(json!({
                "branch":{"instance":name,"local_positive":"p","local_negative":"r","kind":"voltage"},
                "positive":2+instance,"negative":0,"origin":origin(10+slot),
                "rhs":{"op":"multiply","left":{"op":"affine","constant":GAIN,"terms":[]},
                    "right":{"op":"operator","operator":index}}}));
        }
        contributions.push(json!({
            "branch":{"instance":name,"local_positive":"p","local_negative":"r","kind":"voltage"},
            "positive":2+instance,"negative":0,"origin":origin(12),
            "rhs":{"op":"state","state":instance}}));
        states.push(json!({"instance":name,"name":"n","kind":"integer","initial":2+2*instance}));
        events.push(json!({"origin":origin(13),
            "trigger":{"kind":"timer","start":1,"period":1,"time_tolerance":0.001,"enabled":true},
            "assignments":[{"state":instance,"rhs":{"op":"add","left":{"op":"state","state":instance},
                "right":{"op":"affine","constant":1,"terms":[]}}}]}));
    }
    let program: Program = serde_json::from_value(json!({
        "schema_version":SCHEMA_VERSION,"nodes":["0","u","ya","yb"],
        "operators":operators,"contributions":contributions,"states":states,"events":events
    }))
    .unwrap();
    let model = EventModel::new(
        program,
        vec!["u".into()],
        Tolerances {
            absolute: 1e-10,
            relative: 0.0,
        },
    )
    .unwrap();
    let trajectory = source(3.0); // u=-1 before 1, then u=-1+2h.
    let states = model.initial();
    let operators = Operators::new(&model.program, &trajectory, &model.driven, &states).unwrap();
    let circuit = model
        .circuit_with(&states, &operators.values(0.0).unwrap())
        .unwrap();
    let initial = Frame {
        time: 0.0,
        state_bounds: states.iter().copied().map(I::point).collect(),
        states,
        solution: circuit.solve(&trajectory.values(0.0)).unwrap(),
        circuit,
        operators,
    };
    // Reach t=1 through the real trial/settlement path, then accept both events.
    let endpoint = prepare_event(&model, &trajectory, &initial, 1.0, &[]).unwrap();
    let (accepted, records) = prepare_batch(&model, &trajectory, &endpoint, 1.0, &[0, 1]).unwrap();
    assert_records(&records, 1.0, &[2.0, 4.0], &[3.0, 5.0]);
    assert_answer(&accepted, -1.0, &[3.0, 5.0]);
    (model, trajectory, accepted)
}

fn assert_answer(frame: &Frame, area: f64, states: &[f64]) {
    // Anchors below are exact dyadic hand integrals, independent of idt code.
    let expected: Vec<_> = ICS
        .iter()
        .zip(SCALES)
        .map(|(ic, scale)| ic + scale * area)
        .collect();
    assert_eq!(frame.operators.values(frame.time).unwrap(), expected);
    for (bound, value) in frame
        .operators
        .bounds(frame.time)
        .unwrap()
        .iter()
        .zip(&expected)
    {
        assert!(bound.lo <= *value && *value <= bound.hi);
    }
    assert_eq!(frame.states, states);
    assert_eq!(
        frame.state_bounds,
        states.iter().copied().map(I::point).collect::<Vec<_>>()
    );
    for instance in 0..2 {
        assert_eq!(
            frame.solution.voltages[2 + instance],
            GAIN * (expected[2 * instance] + expected[2 * instance + 1]) + states[instance]
        );
    }
}

fn assert_records(records: &[EventRecord], time: f64, before: &[f64], after: &[f64]) {
    assert_eq!(records.len(), 2);
    for (id, record) in records.iter().enumerate() {
        assert_eq!(record.event, id);
        assert_eq!(record.time, time);
        assert_eq!(record.kind, "timer");
        assert_eq!(record.before, before);
        assert_eq!(record.after, after);
    }
}

fn snapshot(frame: &Frame, trajectory: &Trajectory) -> Value {
    let history: Vec<_> = [0.0, 1.0, 2.0, 2.1, 2.5, 3.0]
        .into_iter()
        .map(|time| {
            let bounds: Vec<_> = frame
                .operators
                .bounds(time)
                .unwrap()
                .iter()
                .map(|b| [b.lo, b.hi])
                .collect();
            json!([
                time,
                frame.operators.values(time).unwrap(),
                bounds,
                frame.operators.next_breakpoint(time)
            ])
        })
        .collect();
    json!({"time":frame.time,"states":frame.states,
        "state_bounds":frame.state_bounds.iter().map(|b| [b.lo,b.hi]).collect::<Vec<_>>(),
        "solution":frame.solution,"history":history,
        "circuit_solution":frame.circuit.solve(&trajectory.values(frame.time)).unwrap()})
}

#[test]
fn nonzero_multi_instance_history_survives_failure_discard_and_earlier_retry() {
    let (model, trajectory, accepted) = fixture();
    let baseline = snapshot(&accepted, &trajectory);
    // A clean attempt primes the SAME model's certificate cache before failure.
    let (clean, clean_records) =
        prepare_batch(&model, &trajectory, &accepted, 2.0, &[0, 1]).unwrap();
    let clean_snapshot = snapshot(&clean, &trajectory);
    assert_answer(&clean, -1.0, &[4.0, 6.0]);
    assert_records(&clean_records, 2.0, &[3.0, 5.0], &[4.0, 6.0]);
    drop(clean); // Successful trial is deliberately not accepted.
    assert_eq!(snapshot(&accepted, &trajectory), baseline);
    // At 2.1, history is queried successfully; its amplified rounding enclosure
    // cannot satisfy the fixed voltage budget. The error comes from settlement.
    assert_eq!(accepted.operators.values(2.1).unwrap().len(), 4);
    assert_eq!(accepted.operators.bounds(2.1).unwrap().len(), 4);
    for _ in 0..2 {
        let error = prepare_event(&model, &trajectory, &accepted, 2.1, &[])
            .err()
            .unwrap();
        assert_eq!(error.kind, "waveform_accuracy");
        assert_eq!(snapshot(&accepted, &trajectory), baseline);
    }
    // No budget relaxation: retry a representable earlier candidate after the
    // accepted endpoint. It must match the never-failed candidate completely.
    let (retry, records) = prepare_batch(&model, &trajectory, &accepted, 2.0, &[0, 1]).unwrap();
    assert_eq!(snapshot(&retry, &trajectory), clean_snapshot);
    assert_eq!(
        serde_json::to_value(&records).unwrap(),
        serde_json::to_value(&clean_records).unwrap()
    );
    assert_eq!(snapshot(&accepted, &trajectory), baseline);
    let (next, records) = prepare_batch(&model, &trajectory, &retry, 3.0, &[0, 1]).unwrap();
    assert_answer(&next, 1.0, &[5.0, 7.0]);
    assert_records(&records, 3.0, &[4.0, 6.0], &[5.0, 7.0]);
    assert_eq!(next.operators.next_breakpoint(3.0), None);
}

#[test]
fn corrected_future_preserves_accepted_prefix_and_invalidates_same_time_values() {
    let (model, trajectory, accepted) = fixture();
    let baseline = snapshot(&accepted, &trajectory);
    let (original, _) = prepare_batch(&model, &trajectory, &accepted, 2.0, &[0, 1]).unwrap();
    assert_eq!(original.operators.values(2.0).unwrap()[0], 0.25);
    let corrected_source = source(15.0); // Same past; after 1, u=-1+8h.
    let operators = Operators::new(
        &model.program,
        &corrected_source,
        &model.driven,
        &accepted.states,
    )
    .unwrap();
    // Rebind only the analytic future; keep the actual accepted state/circuit.
    assert_eq!(
        operators.values(1.0).unwrap(),
        accepted.operators.values(1.0).unwrap()
    );
    assert_eq!(
        operators.bounds(1.0).unwrap(),
        accepted.operators.bounds(1.0).unwrap()
    );
    let corrected = Frame {
        operators,
        ..accepted
    };
    let corrected_baseline = snapshot(&corrected, &corrected_source);
    for _ in 0..2 {
        assert_eq!(
            prepare_event(&model, &corrected_source, &corrected, 2.1, &[])
                .err()
                .unwrap()
                .kind,
            "waveform_accuracy"
        );
        assert_eq!(snapshot(&corrected, &corrected_source), corrected_baseline);
    }
    let (next, records) =
        prepare_batch(&model, &corrected_source, &corrected, 2.0, &[0, 1]).unwrap();
    // Integral at accepted time is 1/4; new segment area is -1+8/2=3.
    assert_eq!(next.operators.values(2.0).unwrap()[0], 3.25);
    assert_answer(&next, 2.0, &[4.0, 6.0]);
    assert_records(&records, 2.0, &[3.0, 5.0], &[4.0, 6.0]);
    assert_eq!(snapshot(&corrected, &corrected_source), corrected_baseline);
    // The consumed frame was moved, not recreated; its accepted components are
    // still equal to the original snapshot after future rebinding.
    let after = snapshot(&corrected, &corrected_source);
    for key in [
        "time",
        "states",
        "state_bounds",
        "solution",
        "circuit_solution",
    ] {
        assert_eq!(after[key], baseline[key]);
    }
}
