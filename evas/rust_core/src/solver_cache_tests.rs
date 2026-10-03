use super::*;
use serde_json::json;

fn circuit(coefficient: f64, constant: f64) -> Circuit {
    let program = serde_json::from_value(json!({
        "schema_version": crate::ir::SCHEMA_VERSION, "nodes":["0","u","y"],
        "contributions":[{
            "branch":{"instance":"dut","local_positive":"a","local_negative":"r","kind":"voltage"},
            "positive":2,"negative":0,
            "rhs":{"op":"affine","constant":constant,"terms":[{"node":1,"coefficient":1.0},{"node":2,"coefficient":coefficient}]},
            "origin":{"source":"cache-test","line":1,"column":1,"instance":"dut"}
        }]})).unwrap();
    Circuit::new(program, &["u".into()], Tolerances::default()).unwrap()
}

#[test]
fn identical_matrix_reuses_factors_but_solves_current_rhs() {
    let previous = circuit(0.25, 0.0);
    assert_eq!(previous.solve(&[0.75]).unwrap().voltages[2], 1.0);
    let mut candidate = circuit(0.25, 1.5);
    candidate.reuse_affine_factor_from(&previous);
    assert!(Arc::ptr_eq(
        candidate.affine_factor.as_ref().unwrap(),
        previous.affine_factor.as_ref().unwrap()
    ));
    assert_eq!(candidate.solve(&[0.75]).unwrap().voltages[2], 3.0);
    assert_eq!(previous.solve(&[0.75]).unwrap().voltages[2], 1.0);
}

#[test]
fn a_coefficient_or_variable_order_change_invalidates_the_cache() {
    let previous = circuit(0.25, 0.0);
    previous.solve(&[0.75]).unwrap();
    for coefficient in [0.25 + f64::EPSILON, 0.5] {
        let mut candidate = circuit(coefficient, 0.0);
        candidate.reuse_affine_factor_from(&previous);
        assert!(!Arc::ptr_eq(
            candidate.affine_factor.as_ref().unwrap(),
            previous.affine_factor.as_ref().unwrap()
        ));
        assert!(candidate.affine_factor.as_ref().unwrap().get().is_none());
        let solution = candidate.solve(&[0.75]).unwrap();
        assert!((solution.voltages[2] - 0.75 / (1.0 - coefficient)).abs() < 1e-12);
    }
    let mut candidate = circuit(0.25, 0.0);
    candidate.unknown = vec![1];
    candidate.reuse_affine_factor_from(&previous);
    assert!(!Arc::ptr_eq(
        candidate.affine_factor.as_ref().unwrap(),
        previous.affine_factor.as_ref().unwrap()
    ));
}

#[test]
fn failed_rhs_does_not_poison_either_shared_user() {
    let previous = circuit(0.25, 0.0);
    previous.solve(&[0.75]).unwrap();
    let mut candidate = circuit(0.25, 1e308);
    candidate.reuse_affine_factor_from(&previous);
    assert_eq!(
        candidate.solve(&[1e308]).unwrap_err().kind,
        "nonfinite_arithmetic"
    );
    assert_eq!(candidate.solve(&[-1e308]).unwrap().voltages[2], 0.0);
    assert_eq!(previous.solve(&[0.75]).unwrap().voltages[2], 1.0);
}
