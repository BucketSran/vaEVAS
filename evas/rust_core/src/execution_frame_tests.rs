//! Source captures must belong to the circuit's current activation.
use super::*;
fn model() -> EventModel {
    let request: Request = serde_json::from_str(r###"{"program": {"nodes": ["0", "u", "y", "z"], "contributions": [{"branch": {"instance": "M", "local_positive": "0", "local_negative": "y", "kind": "voltage"}, "positive": 0, "negative": 2, "rhs": {"op": "multiply", "left": {"constant": -1.0, "terms": [], "op": "affine"}, "right": {"state": 0, "op": "state"}}, "origin": {"source": "alias.va", "line": 2, "column": 106, "instance": "M", "expansion": []}}, {"branch": {"instance": "M", "local_positive": "0", "local_negative": "z", "kind": "voltage"}, "positive": 0, "negative": 3, "rhs": {"constant": -1.0, "terms": [], "op": "affine"}, "origin": {"source": "alias.va", "line": 2, "column": 114, "instance": "M", "expansion": []}}], "states": [{"instance": "M", "name": "q", "kind": "real", "initial": 0.0}], "events": [{"trigger": {"kind": "initial_step"}, "body": [{"state": 0, "rhs": {"value": {"value": {"constant": 0.0, "terms": [{"node": 0, "coefficient": -1.0}, {"node": 1, "coefficient": 1.0}], "op": "affine"}, "kind": "sample", "origin": {"source": "alias.va", "line": 2, "column": 92, "instance": "M", "expansion": []}, "op": "real_boundary"}, "kind": "store", "origin": {"source": "alias.va", "line": 2, "column": 90, "instance": "M", "expansion": []}, "op": "real_boundary"}, "kind": "assign"}], "origin": {"source": "alias.va", "line": 2, "column": 75, "instance": "M", "expansion": []}, "procedure_id": 0, "expanded_statement_ordinal": 0}], "operators": [], "schema_version": 33, "step_bounds": [], "procedures": [{"procedure_id": 0, "instance": "M", "body": [{"expanded_statement_ordinal": 0, "action": {"event": 0, "kind": "event_gate"}}, {"expanded_statement_ordinal": 1, "action": {"state": 0, "rhs": {"value": {"operation": "multiply", "left": {"constant": 2.0, "terms": [], "op": "affine"}, "right": {"value": {"constant": 0.0, "terms": [{"node": 0, "coefficient": -1.0}, {"node": 1, "coefficient": 1.0}], "op": "affine"}, "kind": "sample", "origin": {"source": "alias.va", "line": 2, "column": 101, "instance": "M", "expansion": []}, "op": "real_boundary"}, "origin": {"source": "alias.va", "line": 2, "column": 100, "instance": "M", "expansion": []}, "op": "real_binary"}, "kind": "store", "origin": {"source": "alias.va", "line": 2, "column": 97, "instance": "M", "expansion": []}, "op": "real_boundary"}, "kind": "assign"}}, {"expanded_statement_ordinal": 2, "action": {"contribution": 0, "kind": "contribution_capture"}}, {"expanded_statement_ordinal": 3, "action": {"contribution": 1, "kind": "contribution_capture"}}]}], "real_bindings": []}, "driven": ["u"], "samples": [], "transient": {"pwl": [[[0, 0.25], [1, 0.75]]], "output_times": [0, 0.25, 0.5, 0.75, 1], "stop": 1, "max_step": 0.125}, "tolerances": {"absolute": 1e-12, "relative": 1e-10}}"###).unwrap();
    EventModel::new_with_procedure_work(
        request.program,
        request.driven,
        request.tolerances,
        crate::transition_source_plan::Work::default(),
    )
    .unwrap()
}
#[test]
fn ordinary_current_activation_rejects_old_source_capture() {
    let model = model();
    let states = model.initial();
    let state_bounds: Vec<_> = states.iter().copied().map(I::point).collect();
    let old = model.circuit_at(&states, &[], &[I::point(0.25)]).unwrap();
    let old_solution = old.solve(&[0.3125]).unwrap();
    let current = model.circuit_at(&states, &[], &[I::point(0.3125)]).unwrap();
    let view = current.procedure_view().unwrap();
    let old_view = old.procedure_view().unwrap();
    assert!(!std::sync::Arc::ptr_eq(&old_view.plan, &view.plan));
    let certify = |voltages: &[f64]| {
        view.plan.certificate(
            &model.program,
            &model.driven,
            model.tolerances.clone(),
            &[I::point(0.3125)],
            &state_bounds,
            &[],
            voltages,
            &states,
            None,
            crate::real_expression::work(&model),
        )
    };
    let y = model
        .program
        .nodes
        .iter()
        .position(|name| name == "y")
        .unwrap();
    assert_eq!(old_solution.voltages[y], 0.5);
    assert_eq!(
        certify(&old_solution.voltages).unwrap_err().kind,
        "waveform_accuracy"
    );
    let solution = current.solve(&[0.3125]).unwrap();
    assert_eq!(solution.voltages[y], 0.625);
    certify(&solution.voltages).unwrap();
}

fn uncertain_before_model() -> EventModel {
    let program = serde_json::from_str(r###"{"schema_version": 33, "nodes": ["0", "u", "y"], "states": [{"instance": "M", "name": "q", "kind": "real", "initial": 1.0}], "events": [], "operators": [], "step_bounds": [], "real_bindings": [], "contributions": [{"positive": 0, "negative": 2, "rhs": {"op": "affine", "constant": -2, "terms": []}, "origin": {"source": "full-before.va", "line": 1, "column": 1, "instance": "M", "expansion": []}, "branch": {"instance": "M", "local_positive": "0", "local_negative": "y", "kind": "voltage"}}, {"positive": 0, "negative": 2, "rhs": {"op": "affine", "constant": -3, "terms": []}, "origin": {"source": "full-before.va", "line": 1, "column": 1, "instance": "M", "expansion": []}, "branch": {"instance": "M", "local_positive": "0", "local_negative": "y", "kind": "voltage"}}], "procedures": [{"procedure_id": 0, "instance": "M", "body": [{"expanded_statement_ordinal": 0, "action": {"kind": "procedure_if", "relation": "gt", "left": {"op": "state", "state": 0}, "right": {"op": "affine", "constant": 1, "terms": []}, "then_body": [{"expanded_statement_ordinal": 1, "action": {"kind": "contribution_capture", "contribution": 0}}], "else_body": [{"expanded_statement_ordinal": 2, "action": {"kind": "contribution_capture", "contribution": 1}}], "origin": {"source": "full-before.va", "line": 1, "column": 1, "instance": "M", "expansion": []}}}]}]}"###).unwrap();
    EventModel::new_with_procedure_work(
        program,
        vec!["u".into()],
        crate::ir::Tolerances::default(),
        crate::transition_source_plan::Work::default(),
    )
    .unwrap()
}
#[test]
fn ordinary_full_before_branch_must_not_use_nominal_state() {
    let model = uncertain_before_model();
    let before = [1.];
    let bounds = [I {
        lo: f64::from_bits(1f64.to_bits() - 1),
        hi: f64::from_bits(1f64.to_bits() + 1),
    }];
    let old = model.observation_selection(&[I::ZERO], &before, &bounds, &[], &[]);
    assert!(old.is_err());
    assert_eq!(old.err().unwrap().kind, "event_condition");
    let current = ordinary_procedure_circuit(&model, &before, &bounds, &[I::ZERO]);
    assert!(
        current.is_err(),
        "current ordinary circuit silently accepted nominal q=1 for q>1 over a straddling interval"
    );
    assert_eq!(current.err().unwrap().kind, "event_condition");
}

#[test]
fn ordinary_full_before_qualification_is_paid_and_exhaustion_sticky() {
    let model = uncertain_before_model();
    let work = crate::real_expression::work(&model);
    let initial_spent = work.spent();
    let states = [1.];
    let bounds = [I::point(1.)];
    let circuit = ordinary_procedure_circuit(&model, &states, &bounds, &[I::ZERO]).unwrap();
    let solution = circuit.solve(&[0.]).unwrap();
    assert_eq!(solution.voltages[2], 3.);
    assert!(work.spent() > initial_spent);
    let view = circuit.procedure_view().unwrap();
    view.plan
        .certificate(
            &model.program,
            &model.driven,
            model.tolerances.clone(),
            &[I::ZERO],
            &bounds,
            &[],
            &solution.voltages,
            &states,
            None,
            work,
        )
        .unwrap();
    // Consume the unchanged default request allowance after real setup and
    // qualification. A later trial cannot allocate a fresh owner or refund it.
    work.debit(2, 1_000_000_000 - work.spent()).unwrap();
    let mut spent = work.spent();
    for _ in 0..2 {
        let result = ordinary_procedure_circuit(&model, &states, &bounds, &[I::ZERO]);
        assert!(result.is_err());
        assert_eq!(result.err().unwrap().kind, "step_budget");
        assert!(work.spent() > spent);
        spent = work.spent();
        assert_eq!(states, [1.]);
        assert_eq!(solution.voltages[2], 3.);
    }
    let fresh = uncertain_before_model();
    ordinary_procedure_circuit(&fresh, &states, &bounds, &[I::ZERO]).unwrap();
}
