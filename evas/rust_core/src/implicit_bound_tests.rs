//! Certified mesh bounds and transaction invariants for implicit flows.
use super::*;
use crate::ir::Relation;
use serde_json::json;
fn c(x: f64) -> Expression {
    Expression::Affine {
        constant: x,
        terms: vec![],
    }
}
fn n(i: usize) -> Expression {
    Expression::Affine {
        constant: 0.,
        terms: vec![crate::ir::Term {
            node: i,
            coefficient: 1.,
        }],
    }
}
fn choose(a: Expression, b: Expression) -> Expression {
    Expression::Select {
        relation: Relation::Gt,
        left: Box::new(n(1)),
        right: Box::new(c(0.)),
        then_value: Box::new(a),
        else_value: Box::new(b),
        origin: Origin {
            source: "probe.va".into(),
            instance: "dut".into(),
            line: 1,
            column: 1,
            expansion: vec![],
        },
    }
}
#[test]
fn interval_lower_not_midpoint_and_zero_policy() {
    let cap = |v: I, strict| crate::step_bounds::frame_cap(&[(c(1.), n(1))], &[I::ZERO, v], strict);
    assert_eq!(
        cap(
            I {
                lo: 0.125,
                hi: 0.25
            },
            true
        )
        .unwrap(),
        Some(0.125)
    );
    for v in [
        I {
            lo: -0.125,
            hi: 0.5,
        },
        I { lo: 0., hi: 0.5 },
        I::ZERO,
    ] {
        assert_eq!(cap(v, true).unwrap_err().kind, "invalid_bound_step");
    }
    assert!(cap(
        I {
            lo: 0.1,
            hi: f64::INFINITY
        },
        true
    )
    .is_err());
    assert_eq!(cap(I::ZERO, false).unwrap(), Some(0.));
    assert_eq!(
        cap(I::point(f64::from_bits(1)), true).unwrap(),
        Some(f64::from_bits(1))
    );
}
#[test]
fn uncertain_boolean_and_strict_numeric_select() {
    let v = [
        I::ZERO,
        I {
            lo: -0.125,
            hi: 0.25,
        },
    ];
    let active = choose(c(1.), c(0.));
    assert_eq!(
        crate::step_bounds::frame_cap(&[(active.clone(), c(0.0625))], &v, true).unwrap(),
        Some(0.0625)
    );
    for x in [-1., 0.] {
        assert_eq!(
            crate::step_bounds::frame_cap(&[(active.clone(), c(x))], &v, true)
                .unwrap_err()
                .kind,
            "invalid_bound_step"
        );
    }
    assert_eq!(
        crate::step_bounds::frame_cap(&[(c(1.), choose(c(0.0625), c(0.125)))], &v, true)
            .unwrap_err()
            .kind,
        "condition_precision"
    );
    assert_eq!(
        crate::step_bounds::frame_cap(
            &[(
                c(0.),
                Expression::Divide {
                    left: Box::new(c(1.)),
                    right: Box::new(c(0.))
                }
            )],
            &v,
            true
        )
        .unwrap(),
        None
    );
}
#[test]
fn interval_coordinate_and_filter_feedthrough() {
    // State x=[1,2], voltage y=[3,4], source u=[5,6].
    // Program order deliberately differs: node 1=u, node 2=y.
    // Filter output q=2*x+3*y+4*u+5 lies in [36,45].
    let bounds = ImplicitBounds {
        expressions: vec![(c(1.), n(3))],
        nodes: vec![None, Some(2), Some(1)],
        outputs: vec![Polynomial::Linear(vec![
            I::point(2.),
            I::point(3.),
            I::point(4.),
            I::point(5.),
        ])],
    };
    let state = [I { lo: 1., hi: 2. }, I { lo: 3., hi: 4. }];
    let source = [I { lo: 5., hi: 6. }];
    let cap = bounds.cap(&state, &source).unwrap().unwrap();
    assert!(cap <= 36. && cap > 35.9999999999);
    let mut b = bounds.clone();
    b.expressions = vec![(c(1.), n(1))];
    assert_eq!(b.cap(&state, &source).unwrap(), Some(5.));
    b.expressions = vec![(c(1.), n(2))];
    assert_eq!(b.cap(&state, &source).unwrap(), Some(3.));
    b.expressions = vec![(c(1.), n(0))];
    assert_eq!(
        b.cap(&state, &source).unwrap_err().kind,
        "invalid_bound_step"
    );
}
#[test]
fn short_step_budget_rollback_and_same_object_retry() {
    // y+y²=z and z'=1+2y, z(0)=0 give the independent solution y=t.
    let origin = json!({"source":"bound.va","line":1,"column":1,"instance":"dut"});
    let program: Program = serde_json::from_value(json!({
        "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","u","y"],
        "operators":[{"kind":"idt","ic":0,"origin":origin,
            "input":{"op":"affine","constant":1,"terms":[{"node":2,"coefficient":2}]}}],
        "contributions":[{"branch":{"instance":"dut","local_positive":"p","local_negative":"r","kind":"voltage"},
            "positive":2,"negative":0,"origin":origin,
            "rhs":{"op":"add","left":{"op":"operator","operator":0},
                "right":{"op":"multiply","left":{"op":"affine","constant":-1,"terms":[]},
                    "right":{"op":"power","exponent":2,"base":{"op":"affine","constant":0,"terms":[{"node":2,"coefficient":1}]}}}}}]
    })).unwrap();
    let full_config = TransientInputs {
        strobetimes: vec![],
        pwl: vec![vec![[0., 1.], [0.25, 1.]]],
        output_times: vec![0., 0.25],
        stop: 0.25,
        max_step: 0.125,
    };
    let driven = vec!["u".into()];
    let tolerances = Tolerances {
        absolute: 1e-8,
        relative: 0.,
    };
    let mut prefix_config = full_config.clone();
    prefix_config.stop = 0.03125;
    prefix_config.output_times = vec![0., 0.03125];
    let trajectory = Trajectory::new(prefix_config, 1).unwrap();
    let (mut flow, _) = initialize(&program, &trajectory, &driven, &tolerances).unwrap();
    Arc::get_mut(&mut flow.context).unwrap().trajectory = Trajectory::new(full_config, 1).unwrap();
    let tiny = f64::from_bits(1);
    flow.implicit.as_mut().unwrap().bounds = Some(ImplicitBounds {
        expressions: vec![(c(1.), c(tiny))],
        nodes: vec![None, Some(2), Some(1)],
        outputs: vec![],
    });
    let clean = flow.clone();
    let prefix = flow.steps.clone();
    let initial = flow.initial.clone();
    let parameters = flow.parameters.clone();
    let end = flow.certified_end();
    let mut work = 3;
    assert_eq!(
        flow.propagate_with_budget(0.125, &mut work)
            .unwrap_err()
            .kind,
        "waveform_accuracy"
    );
    assert_eq!(work, 0);
    assert!(Arc::ptr_eq(&flow.steps, &prefix));
    assert_eq!(flow.certified_end(), end);
    assert_eq!(flow.initial, initial);
    assert_eq!(flow.parameters, parameters);
    // A new request for exactly one representable step succeeds on the same object.
    let mut fresh = clean;
    let target = end.next_up();
    flow.propagate_with_budget(target, &mut 3).unwrap();
    fresh.propagate_with_budget(target, &mut 3).unwrap();
    assert_eq!(flow.certified_end(), target);
    assert_eq!(
        flow.state_bounds(I::point(target)).unwrap(),
        fresh.state_bounds(I::point(target)).unwrap()
    );
}
