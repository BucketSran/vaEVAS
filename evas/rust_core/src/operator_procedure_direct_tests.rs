//! Direct histories must retain source dependency and request accounting gates.
use super::*;
fn fixture() -> (Program, Trajectory, Vec<String>) {
    let request: crate::ir::Request = serde_json::from_str(r###"{"program": {"nodes": ["0", "filtered", "u", "y"], "contributions": [{"branch": {"instance": "dut", "local_positive": "r", "local_negative": "y", "kind": "voltage"}, "positive": 0, "negative": 3, "rhs": {"op": "multiply", "left": {"constant": -1.0, "terms": [], "op": "affine"}, "right": {"binding": 0, "op": "real_local"}}, "origin": {"source": "snapshots.va", "line": 4, "column": 13, "instance": "dut", "expansion": []}}, {"branch": {"instance": "dut", "local_positive": "r", "local_negative": "y", "kind": "voltage"}, "positive": 0, "negative": 3, "rhs": {"op": "multiply", "left": {"constant": -1.0, "terms": [], "op": "affine"}, "right": {"binding": 0, "op": "real_local"}}, "origin": {"source": "snapshots.va", "line": 6, "column": 13, "instance": "dut", "expansion": []}}, {"branch": {"instance": "dut", "local_positive": "filtered", "local_negative": "r", "kind": "voltage"}, "positive": 1, "negative": 0, "rhs": {"operator": 0, "op": "operator"}, "origin": {"source": "snapshots.va", "line": 7, "column": 13, "instance": "dut", "expansion": []}}], "states": [], "events": [], "operators": [{"input": {"constant": 0.0, "terms": [{"node": 0, "coefficient": -1.0}, {"node": 2, "coefficient": 1.0}], "op": "affine"}, "numerator": [1.0], "denominator": [1.0, 0.5], "origin": {"source": "snapshots.va", "line": 7, "column": 30, "instance": "dut", "expansion": []}, "kind": "laplace_nd"}], "schema_version": 33, "step_bounds": [], "procedures": [{"procedure_id": 0, "instance": "dut", "body": [{"expanded_statement_ordinal": 0, "action": {"binding": 0, "value": {"value": {"value": {"constant": 0.0, "terms": [{"node": 0, "coefficient": -1.0}, {"node": 2, "coefficient": 1.0}], "op": "affine"}, "kind": "sample", "origin": {"source": "snapshots.va", "line": 3, "column": 21, "instance": "dut", "expansion": []}, "op": "real_boundary"}, "kind": "snapshot", "origin": {"source": "snapshots.va", "line": 3, "column": 13, "instance": "dut", "expansion": []}, "op": "real_boundary"}, "origin": {"source": "snapshots.va", "line": 3, "column": 13, "instance": "dut", "expansion": []}, "kind": "real_bind"}}, {"expanded_statement_ordinal": 1, "action": {"contribution": 0, "kind": "contribution_capture"}}, {"expanded_statement_ordinal": 2, "action": {"binding": 0, "value": {"value": {"operation": "add", "left": {"binding": 0, "op": "real_local"}, "right": {"constant": 1.0, "terms": [], "op": "affine"}, "origin": {"source": "snapshots.va", "line": 5, "column": 27, "instance": "dut", "expansion": []}, "op": "real_binary"}, "kind": "snapshot", "origin": {"source": "snapshots.va", "line": 5, "column": 13, "instance": "dut", "expansion": []}, "op": "real_boundary"}, "origin": {"source": "snapshots.va", "line": 5, "column": 13, "instance": "dut", "expansion": []}, "kind": "real_bind"}}, {"expanded_statement_ordinal": 3, "action": {"contribution": 1, "kind": "contribution_capture"}}, {"expanded_statement_ordinal": 4, "action": {"contribution": 2, "kind": "contribution_capture"}}]}], "real_bindings": [{"procedure_id": 0, "name": "local", "origin": {"source": "snapshots.va", "line": 2, "column": 1, "instance": "dut", "expansion": []}, "lifetime": "occurrence"}]}, "driven": ["u"], "samples": [], "transient": {"pwl": [[[0, 0.25], [2, 0.25]]], "output_times": [0, 0.5, 1, 2], "stop": 2, "max_step": 2}, "tolerances": {"absolute": 1e-10, "relative": 1e-10}}"###).unwrap();
    let mut trajectory = Trajectory::new(request.transient.unwrap(), request.driven.len()).unwrap();
    trajectory
        .bind_procedure_work(&crate::transition_source_plan::Work::default())
        .unwrap();
    (request.program, trajectory, request.driven)
}
#[test]
fn procedure_direct_laplace_never_erases_source_boundary_or_internal_dependency() {
    let (mut p, t, driven) = fixture();
    assert!(procedure_direct_laplace(&p, &t, &driven).unwrap());
    let node = p.nodes.iter().position(|n| n == "y").unwrap();
    let OperatorSpec::LaplaceNd { input, origin, .. } = &mut p.operators[0] else {
        unreachable!()
    };
    let original = input.clone();
    *input = Expression::RealBoundary {
        value: Box::new(original.clone()),
        kind: crate::ir::RealBoundaryKind::Sample,
        origin: origin.clone(),
    };
    assert!(!procedure_direct_laplace(&p, &t, &driven).unwrap());
    let OperatorSpec::LaplaceNd { input, .. } = &mut p.operators[0] else {
        unreachable!()
    };
    *input = Expression::Affine {
        constant: 0.,
        terms: vec![crate::ir::Term {
            node,
            coefficient: 0.,
        }],
    };
    assert!(
        !procedure_direct_laplace(&p, &t, &driven).unwrap(),
        "zero coefficient cannot erase a structural feedback dependency"
    );
}
#[test]
fn procedure_direct_laplace_qualification_keeps_original_owner_exhausted() {
    let (p, t, driven) = fixture();
    let work = t.procedure_work().unwrap();
    assert!(procedure_direct_laplace(&p, &t, &driven).unwrap());
    assert!(work.spent() > 0);
    work.debit(2, 1_000_000_000 - work.spent()).unwrap();
    let mut spent = work.spent();
    for _ in 0..2 {
        assert_eq!(
            procedure_direct_laplace(&p, &t, &driven).unwrap_err().kind,
            "step_budget"
        );
        assert!(work.spent() > spent);
        spent = work.spent();
    }
    let (p, t, driven) = fixture();
    assert!(procedure_direct_laplace(&p, &t, &driven).unwrap());
}

#[test]
fn procedure_direct_laplace_mixed_histories_keep_original_route() {
    let (mut p, t, driven) = fixture();
    let OperatorSpec::LaplaceNd { input, origin, .. } = &p.operators[0] else {
        unreachable!()
    };
    p.operators.push(OperatorSpec::Idt {
        input: input.clone(),
        ic: 0.,
        reset: None,
        origin: origin.clone(),
    });
    assert!(!procedure_direct_laplace(&p, &t, &driven).unwrap());
    let (mut p, t, driven) = fixture();
    p.states.push(serde_json::from_str(
        r#"{"instance":"dut","name":"held","kind":"real","initial":0.0}"#,
    ).unwrap());
    assert!(!procedure_direct_laplace(&p, &t, &driven).unwrap());
}

#[test]
fn procedure_direct_laplace_higher_order_keeps_original_route() {
    let (mut p, t, driven) = fixture();
    let OperatorSpec::LaplaceNd { denominator, .. } = &mut p.operators[0] else {
        unreachable!()
    };
    denominator.push(0.25);
    assert!(!procedure_direct_laplace(&p, &t, &driven).unwrap());
}
