use super::*;
use crate::ir::{Term, TransientInputs};
fn program() -> Program {
    serde_json::from_value(serde_json::json!({
        "schema_version": crate::ir::SCHEMA_VERSION,
        "nodes": ["0", "u", "y"],
        "contributions": [],
        "states": [{"instance": "dut", "name": "q", "kind": "real", "initial": 0.25}],
        "events": [],
        "operators": [],
        "step_bounds": []
    }))
    .unwrap()
}
fn constant(v: f64) -> Expression {
    Expression::Affine {
        constant: v,
        terms: vec![],
    }
}
fn source_voltage() -> Expression {
    Expression::Affine {
        constant: 0.,
        terms: vec![Term {
            node: 1,
            coefficient: 1.,
        }],
    }
}
fn select(left: Expression, right: Expression, owner: &str) -> Expression {
    Expression::Select {
        left: Box::new(left),
        right: Box::new(right),
        then_value: Box::new(constant(1.)),
        else_value: Box::new(constant(0.)),
        relation: crate::ir::Relation::Gt,
        origin: Origin {
            source: "probe.va".into(),
            line: 1,
            column: 1,
            instance: owner.into(),
            expansion: vec![],
        },
    }
}
fn trajectory(points: Vec<[f64; 2]>) -> Trajectory {
    Trajectory::new(
        TransientInputs {
            pwl: vec![points],
            output_times: vec![0., 1.],
            stop: 1.,
            max_step: 1.,
            strobetimes: vec![],
        },
        1,
    )
    .unwrap()
}
fn collect_for(roots: &mut Roots, e: &Expression, t: &Trajectory, s: &[I]) -> Result<(), Error> {
    roots.collect(e, &program(), &["u".into()], t, s)
}
#[test]
fn scans_every_segment_then_reuses() {
    let t = trajectory(vec![[0., 0.], [0.25, 1.], [0.5, 0.], [0.75, 1.], [1., 0.]]);
    let e = select(source_voltage(), constant(0.5), "dut");
    let mut r = Roots::new();
    collect_for(&mut r, &e, &t, &[I::ZERO]).unwrap();
    assert_eq!(r.roots.len(), 4);
    for (v, want) in r.roots.iter().zip([0.125, 0.375, 0.625, 0.875]) {
        assert!(v.value.lo <= want && want <= v.value.hi);
    }
    let b = r.budget;
    for _ in 0..64 {
        collect_for(&mut r, &e, &t, &[I::ZERO]).unwrap();
    }
    assert_eq!(r.roots.len(), 4);
    assert!(b - r.budget < 1024);
}
#[test]
fn new_roots_recompute_changed_state_and_source() {
    let t = trajectory(vec![[0., 0.], [1., 1.]]);
    let e = select(source_voltage(), Expression::State { state: 0 }, "dut");
    for q in [0.25, 0.75] {
        let mut r = Roots::new();
        collect_for(&mut r, &e, &t, &[I::point(q)]).unwrap();
        assert_eq!(r.roots.len(), 1);
        let v = r.roots[0].value;
        assert!(v.lo <= q && q <= v.hi);
    }
    let t2 = trajectory(vec![[0., 0.], [1., 2.]]);
    let mut r = Roots::new();
    collect_for(&mut r, &e, &t2, &[I::point(0.5)]).unwrap();
    let v = r.roots[0].value;
    assert!(v.lo <= 0.25 && 0.25 <= v.hi);
}
#[test]
fn different_expressions_do_not_merge_equal_root_boxes() {
    let t = trajectory(vec![[0., 0.], [1., 3.]]);
    let mut r = Roots::new();
    collect_for(
        &mut r,
        &select(source_voltage(), constant(1.), "dut"),
        &t,
        &[I::ZERO],
    )
    .unwrap();
    let other = Expression::Add {
        left: Box::new(source_voltage()),
        right: Box::new(constant(0.)),
    };
    collect_for(&mut r, &select(other, constant(1.), "dut"), &t, &[I::ZERO]).unwrap();
    assert_eq!(r.roots.len(), 2);
    assert_eq!(
        r.finish(&mut vec![I::point(0.), I::point(1.)], 0., 1.)
            .unwrap_err()
            .kind,
        "condition_precision"
    );
}
#[test]
fn hit_does_not_skip_owner_check() {
    let t = trajectory(vec![[0., 0.], [1., 1.]]);
    let mut r = Roots::new();
    collect_for(
        &mut r,
        &select(source_voltage(), Expression::State { state: 0 }, "dut"),
        &t,
        &[I::point(0.5)],
    )
    .unwrap();
    assert!(collect_for(
        &mut r,
        &select(source_voltage(), Expression::State { state: 0 }, "other"),
        &t,
        &[I::point(0.5)]
    )
    .is_err());
}
#[test]
fn hit_does_not_skip_invalid_subtree() {
    let t = trajectory(vec![[0., 0.], [1., 1.]]);
    let mut r = Roots::new();
    let mut e = select(source_voltage(), constant(0.5), "dut");
    collect_for(&mut r, &e, &t, &[I::ZERO]).unwrap();
    if let Expression::Select { then_value, .. } = &mut e {
        **then_value = select(Expression::Operator { operator: 0 }, constant(0.), "dut");
    }
    assert!(collect_for(&mut r, &e, &t, &[I::ZERO]).is_err());
}
#[test]
fn failed_scan_must_not_be_cached_as_complete() {
    let t = trajectory(vec![[0., 0.25], [1., 1.]]);
    let mut r = Roots::new();
    let e = select(source_voltage(), Expression::State { state: 0 }, "dut");
    let s = [I { lo: 0.2, hi: 0.3 }];
    assert!(collect_for(&mut r, &e, &t, &s).is_err());
    assert!(
        collect_for(&mut r, &e, &t, &s).is_err(),
        "same Roots must not report success after a failed scan"
    );
}

#[test]
fn exact_original_midpoint_survives_a_local_horizon() {
    let mut t = trajectory(vec![[0., 0.], [3e-8, 0.], [3.02e-8, 1.8], [1., 1.8]]);
    t.config.stop = 3.01e-8;
    let mut r = Roots::new();
    collect_for(
        &mut r,
        &select(source_voltage(), constant(0.9), "dut"),
        &t,
        &[I::ZERO],
    )
    .unwrap();
    assert_eq!(r.roots.len(), 1);
    assert_eq!(r.roots[0].value, I::point(3.01e-8));
    let mut cuts = vec![I::ZERO, I::point(3.01e-8)];
    r.finish(&mut cuts, 0., 3.01e-8).unwrap();
    assert_eq!(cuts, vec![I::ZERO, I::point(3.01e-8)]);
    assert!(t
        .original_guard_curve_until(&source_voltage(), &[1], 2.)
        .is_none());
}
#[test]
fn missing_original_source_does_not_tighten_a_root() {
    let mut t = trajectory(vec![[0., 0.], [3e-8, 0.], [3.02e-8, 1.8], [1., 1.8]]);
    t.exact_sources[0] = None;
    let mut r = Roots::new();
    collect_for(
        &mut r,
        &select(source_voltage(), constant(0.9), "dut"),
        &t,
        &[I::ZERO],
    )
    .unwrap();
    assert_ne!(r.roots[0].value.lo, r.roots[0].value.hi);
    assert!(r
        .finish(&mut vec![I::ZERO, I::point(3.01e-8)], 0., 3.01e-8)
        .is_err());
}
#[test]
fn uncertain_held_threshold_never_becomes_a_point_root() {
    let t = trajectory(vec![[0., 0.], [1., 1.]]);
    let mut r = Roots::new();
    collect_for(
        &mut r,
        &select(source_voltage(), Expression::State { state: 0 }, "dut"),
        &t,
        &[I { lo: 0.49, hi: 0.51 }],
    )
    .unwrap();
    assert!(r.roots[0].value.lo <= 0.49 && r.roots[0].value.hi >= 0.51);
    assert!(r
        .finish(&mut vec![I::ZERO, I::point(0.5)], 0., 0.5)
        .is_err());
}
#[test]
fn exact_nonrepresentable_root_retains_endpoint_rejection() {
    let t = trajectory(vec![[0., 0.], [1., 3.]]);
    let mut r = Roots::new();
    collect_for(
        &mut r,
        &select(source_voltage(), constant(1.), "dut"),
        &t,
        &[I::ZERO],
    )
    .unwrap();
    assert_ne!(r.roots[0].value.lo, r.roots[0].value.hi);
    assert!(r
        .finish(&mut vec![I::ZERO, I::point(1. / 3.)], 0., 1. / 3.)
        .is_err());
}
