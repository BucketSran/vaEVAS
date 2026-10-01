//! Full-window sample and disposable joint-history invariants.
use super::*;
use crate::ir::{Program, Tolerances, TransientInputs};
use serde_json::json;

fn fixture() -> (EventModel, Trajectory, Frame) {
    let origin = json!({"source":"sample.va","line":1,"column":1,"instance":"dut"});
    let program:Program=serde_json::from_value(json!({
        "schema_version":SCHEMA_VERSION,"nodes":["0","u","y"],
        "states":[{"instance":"dut","name":"q","kind":"real","initial":0}],
        "operators":[{"kind":"idt","ic":0,"input":{"op":"state","state":0},"origin":origin}],
        "events":[{"origin":origin,"trigger":{"kind":"timer","start":0.75,"period":0,"time_tolerance":1,"enabled":true},
            "body":[{"kind":"assign","state":0,"rhs":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]}}]}],
        "contributions":[{"branch":{"instance":"dut","local_positive":"p","local_negative":"r","kind":"voltage"},
            "positive":2,"negative":0,"rhs":{"op":"operator","operator":0},"origin":origin}]
    })).unwrap();
    let model = EventModel::new(
        program,
        vec!["u".into()],
        Tolerances {
            absolute: 1.0,
            relative: 2.0,
        },
    )
    .unwrap();
    let trajectory = Trajectory::new(
        TransientInputs {
            pwl: vec![vec![[0.0, 0.0], [1.0, 1.0]]],
            output_times: vec![0.0, 1.0],
            stop: 1.0,
            max_step: 1.0,
        },
        1,
    )
    .unwrap();
    let states = model.initial();
    let operators = Operators::new(&model.program, &trajectory, &model.driven, &states).unwrap();
    let circuit = model
        .circuit_with(&states, &operators.values(0.0).unwrap())
        .unwrap();
    let frame = Frame {
        time: 0.0,
        state_bounds: vec![I::ZERO],
        states,
        operators,
        solution: circuit.solve(&[0.0]).unwrap(),
        circuit,
    };
    (model, trajectory, frame)
}

#[test]
fn sample_window_survives_candidate_discard_and_tight_budget_failure() {
    let (model, trajectory, base) = fixture();
    let window = I { lo: 0.25, hi: 0.75 };
    let original = base.operators.bounds(1.0).unwrap();
    let candidate =
        prepare_event_with_bounds(&model, &trajectory, &base, window.hi, window, &[0]).unwrap();
    assert!(candidate.state_bounds[0].lo <= 0.25 && candidate.state_bounds[0].hi >= 0.75);
    let future = candidate.operators.bounds(1.0).unwrap();
    // q=tau, y(1)=tau*(1-tau): exact values at tau=.25/.75 and .5.
    assert!(future[0].lo <= 3.0 / 16.0 && future[0].hi >= 1.0 / 4.0);
    assert_eq!(base.operators.bounds(1.0).unwrap(), original);
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
    assert!(
        prepare_event_with_bounds(&strict, &trajectory, &base, window.hi, window, &[0]).is_err()
    );
    assert_eq!(base.states, [0.0]);
    assert_eq!(base.state_bounds, [I::ZERO]);
    assert_eq!(base.operators.bounds(1.0).unwrap(), original);
    let retry =
        prepare_event_with_bounds(&model, &trajectory, &base, window.hi, window, &[0]).unwrap();
    assert_eq!(retry.operators.bounds(1.0).unwrap(), future);
}
