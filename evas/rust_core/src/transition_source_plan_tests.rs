use super::*;
use crate::ir::{Origin, Term, TransientInputs};
fn program() -> Program {
    serde_json::from_value(serde_json::json!({
        "schema_version":21,"nodes":["0","u","y"],"contributions":[],
        "states":[{"instance":"dut","name":"q","kind":"real","initial":0.25}],
        "events":[],"operators":[],"step_bounds":[]
    }))
    .unwrap()
}
fn source() -> Expression {
    Expression::Affine {
        constant: 0.,
        terms: vec![Term {
            node: 1,
            coefficient: 1.,
        }],
    }
}
fn q() -> Expression {
    Expression::State { state: 0 }
}
fn mul(a: Expression, b: Expression) -> Expression {
    Expression::Multiply {
        left: Box::new(a),
        right: Box::new(b),
    }
}
fn add(a: Expression, b: Expression) -> Expression {
    Expression::Add {
        left: Box::new(a),
        right: Box::new(b),
    }
}
fn select(rel: Relation, l: Expression, r: Expression, a: Expression, b: Expression) -> Expression {
    Expression::Select {
        relation: rel,
        left: Box::new(l),
        right: Box::new(r),
        then_value: Box::new(a),
        else_value: Box::new(b),
        origin: Origin {
            source: "source-plan.va".into(),
            line: 1,
            column: 1,
            instance: "dut".into(),
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
fn spec(e: Expression, t: &Trajectory, w: Work) -> Arc<Spec> {
    Spec::new(&e, &program(), t, &["u".into()], "dut", w)
        .unwrap()
        .unwrap()
}
fn ramp() -> Trajectory {
    trajectory(vec![[0., 0.], [1., 1.]])
}
fn gate(r: f64) -> Expression {
    select(
        Relation::Gt,
        source(),
        constant(r),
        constant(1.),
        constant(0.),
    )
}
#[test]
fn schedules_all_source_roots_without_observation_points() {
    let t = trajectory(vec![[0., 0.], [0.25, 1.], [0.5, 0.], [0.75, 1.], [1., 0.]]);
    let p = Plan::build(spec(gate(0.5), &t, Work::default()), &[I::ZERO]).unwrap();
    assert_eq!(
        *p.cuts,
        vec![0., 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1.]
    );
    assert_eq!(p.seed().value, 0.);
    let mut old = p.seed();
    for (time, value) in [(0.125, 1.), (0.375, 0.), (0.625, 1.), (0.875, 0.)] {
        old = p.prepare(time, &old).unwrap();
        assert_eq!(old.value, value);
    }
    assert_eq!(p.next_after(0.126), Some(0.25));
    assert!(p.due_at(0.125));
    assert!(!p.due_at(0.126));
}
#[test]
fn root_zero_point_seed_precedes_right_mode() {
    for rel in [Relation::Gt, Relation::Ge] {
        let e = select(rel, source(), constant(0.), constant(1.), constant(0.));
        let p = Plan::build(spec(e, &ramp(), Work::default()), &[I::ZERO]).unwrap();
        assert_eq!(
            p.seed().value,
            if matches!(rel, Relation::Gt) { 0. } else { 1. }
        );
        assert_eq!(p.prepare(0., &p.seed()).unwrap().value, 1.);
    }
}
#[test]
fn timer_zero_final_state_does_not_replace_seed() {
    let e = select(Relation::Ge, source(), constant(0.), q(), constant(0.));
    let s = spec(e, &ramp(), Work::default());
    let old = Plan::build(s.clone(), &[I::ONE]).unwrap();
    let new = Plan::build(s, &[I::ZERO]).unwrap();
    assert_eq!(old.seed().value, 1.);
    assert_eq!(new.prepare(0., &old.seed()).unwrap().value, 0.);
}
#[test]
fn old_epoch_is_required_at_shared_boundary() {
    let e = select(
        Relation::Le,
        source(),
        constant(0.25),
        mul(constant(2.), q()),
        q(),
    );
    let s = spec(e, &ramp(), Work::default());
    let old = Plan::build(s.clone(), &[I::ZERO]).unwrap();
    let new = Plan::build(s, &[I::ONE]).unwrap();
    assert!(new.prepare(0.25, &old.seed()).is_err()); // L=0, P=2, R=1.
    assert_eq!(old.seed().value, 0.); // failed trial cannot change old plan.
}
#[test]
fn isolated_and_third_point_values_are_rejected() {
    for point in [1., 2.] {
        let above = if point == 1. { 0. } else { 1. };
        let inner = select(
            Relation::Le,
            source(),
            constant(0.25),
            constant(point),
            constant(above),
        );
        let e = select(Relation::Ge, source(), constant(0.25), inner, constant(0.));
        assert!(Plan::build(spec(e, &ramp(), Work::default()), &[I::ZERO]).is_err());
    }
}
#[test]
fn floating_cancellation_does_not_fake_point_equality() {
    // Nominal arithmetic rounds the middle leaf to zero, but original math is 1.
    let middle = add(add(constant(1e16), constant(1.)), constant(-1e16));
    let inner = select(Relation::Le, source(), constant(0.25), middle, constant(0.));
    let e = select(Relation::Ge, source(), constant(0.25), inner, constant(0.));
    assert!(Plan::build(spec(e, &ramp(), Work::default()), &[I::ZERO]).is_err());
}
#[test]
fn affine_held_leaf_and_original_decimal_root_are_proved() {
    let e = select(
        Relation::Gt,
        source(),
        constant(0.9),
        add(mul(constant(2.), q()), constant(0.5)),
        constant(0.),
    );
    let t = trajectory(vec![[0., 0.], [3e-8, 0.], [3.02e-8, 1.8], [1., 1.8]]);
    let p = Plan::build(spec(e, &t, Work::default()), &[I::point(0.25)]).unwrap();
    assert!(p.due_at(3.01e-8));
    assert_eq!(p.prepare(3.01e-8, &p.seed()).unwrap().value, 1.);
}
#[test]
fn unproved_roots_provenance_and_event_overlap_stay_rejected() {
    let t = trajectory(vec![[0., 0.], [1., 3.]]);
    assert!(Plan::build(spec(gate(1.), &t, Work::default()), &[I::ZERO]).is_err());
    let mut t = ramp();
    t.exact_sources[0] = None;
    assert!(Plan::build(spec(gate(0.5), &t, Work::default()), &[I::ZERO]).is_err());
    let p = Plan::build(spec(gate(0.5), &ramp(), Work::default()), &[I::ZERO]).unwrap();
    assert!(p.check_incoming(0., I { lo: 0.49, hi: 0.51 }).is_err());
    assert!(p.check_incoming(0., I::point(0.5)).is_ok());
    assert!(p.check_incoming(0., I { lo: 0.4, hi: 0.49 }).is_ok());

}
#[test]
fn structural_hidden_continuous_leaf_is_not_admitted() {
    let leaf = mul(constant(0.), source());
    let e = select(Relation::Gt, source(), constant(0.25), constant(1.), leaf);
    assert!(Spec::new(
        &e,
        &program(),
        &ramp(),
        &["u".into()],
        "dut",
        Work::default()
    )
    .is_err());
}
#[test]
fn shared_budget_counts_failed_trials_and_clones() {
    let w = Work::limited([1, 8192, 1_000_000_000]);
    let s = spec(gate(0.5), &ramp(), w.clone());
    let p = Plan::build(s.clone(), &[I::ZERO]).unwrap();
    let clone = p.clone();
    assert!(p.same_proof(&clone));
    assert_eq!(
        Plan::build(s.clone(), &[I::ZERO]).err().unwrap().kind,
        "step_budget"
    );
    assert_eq!(
        Plan::build(s, &[I::ZERO]).err().unwrap().kind,
        "step_budget"
    );
    assert!(p.same_proof(&clone));
    let s = spec(
        gate(1.),
        &trajectory(vec![[0., 0.], [1., 3.]]),
        Work::limited([1, 8192, 1_000_000_000]),
    );
    assert_eq!(
        Plan::build(s.clone(), &[I::ZERO]).err().unwrap().kind,
        "condition_precision"
    );
    assert_eq!(
        Plan::build(s, &[I::ZERO]).err().unwrap().kind,
        "step_budget"
    );
}
#[test]
fn terminal_point_cannot_schedule_unproved_future() {
    let e = select(
        Relation::Ge,
        source(),
        constant(1.),
        constant(1.),
        constant(0.),
    );
    let p = Plan::build(spec(e, &ramp(), Work::default()), &[I::ZERO]).unwrap();
    assert!(p.prepare(1., &p.seed()).is_err());
}

#[test]
fn state_shape_and_all_potential_predicates_are_validated() {
    let s = spec(gate(0.5), &ramp(), Work::default());
    for states in [
        vec![],
        vec![I::ZERO, I::ONE],
        vec![I {
            lo: f64::NAN,
            hi: 1.,
        }],
        vec![I { lo: 1., hi: 0. }],
    ] {
        assert_eq!(
            Plan::build(s.clone(), &states).err().unwrap().kind,
            "invalid_ir"
        );
    }
    let hidden = select(Relation::Gt, q(), constant(0.), constant(1.), constant(0.));
    let e = select(Relation::Gt, source(), constant(2.), hidden, constant(0.));
    assert_eq!(
        Plan::build(spec(e, &ramp(), Work::default()), &[I { lo: -1., hi: 1. }])
            .err()
            .unwrap()
            .kind,
        "condition_precision"
    );
}
#[test]
fn value_only_rebind_reuses_complete_cut_proof() {
    let e = select(Relation::Gt, source(), constant(0.5), q(), constant(0.));
    let w = Work::default();
    let p = Plan::build(spec(e, &ramp(), w.clone()), &[I::ONE]).unwrap();
    let cuts = w.0.cuts.load(Ordering::Relaxed);
    let plans = w.0.plans.load(Ordering::Relaxed);
    let same = p.rebind(&[I::ONE]).unwrap();
    assert!(p.same_proof(&same));
    assert_eq!(w.0.plans.load(Ordering::Relaxed), plans);
    let changed = p.rebind(&[I::point(2.)]).unwrap();
    assert!(Arc::ptr_eq(&p.cuts, &changed.cuts));
    assert_eq!(w.0.cuts.load(Ordering::Relaxed), cuts);
    assert_eq!(changed.prepare(0.5, &p.seed()).unwrap().value, 2.);
    assert_eq!(p.prepare(0.5, &p.seed()).unwrap().value, 1.);
    let e = select(Relation::Gt, source(), q(), constant(1.), constant(0.));
    let p = Plan::build(spec(e, &ramp(), Work::default()), &[I::point(0.25)]).unwrap();
    let changed = p.rebind(&[I::point(0.75)]).unwrap();
    assert!(!Arc::ptr_eq(&p.cuts, &changed.cuts));
    assert!(changed.due_at(0.75));
    assert!(!changed.due_at(0.25));
}
#[test]
fn unsupported_exact_tree_is_rejected_before_a_plan() {
    for e in [
        Expression::Divide {
            left: Box::new(source()),
            right: Box::new(constant(2.)),
        },
        Expression::Power {
            base: Box::new(source()),
            exponent: 1,
        },
    ] {
        let e = select(Relation::Gt, e, constant(0.25), constant(1.), constant(0.));
        let error = Spec::new(
            &e,
            &program(),
            &ramp(),
            &["u".into()],
            "dut",
            Work::default(),
        )
        .err()
        .unwrap();
        assert!(matches!(
            error.kind,
            "unsupported_operator" | "unsupported_transient"
        ));
    }
}

#[test]
fn terminal_held_update_must_match_new_epoch_left_mode() {
    let e = select(Relation::Ge, source(), constant(0.), q(), constant(0.));
    let old = Plan::build(spec(e, &ramp(), Work::default()), &[I::point(3.)]).unwrap();
    let new = old.rebind(&[I::point(4.)]).unwrap();
    assert_eq!(new.prepare(1., &old.seed()).unwrap().value, 4.);
    assert_eq!(old.seed().value, 3.);

    // A newly selected value at the domain endpoint has no right-hand proof.
    // Rebinding a held operand must not turn an isolated point into a mode.
    let e = select(Relation::Ge, source(), constant(1.), q(), constant(0.));
    let old = Plan::build(spec(e, &ramp(), Work::default()), &[I::point(3.)]).unwrap();
    let new = old.rebind(&[I::point(4.)]).unwrap();
    assert!(new.prepare(1., &old.seed()).is_err());
}

#[test]
fn exact_zero_plateaus_keep_all_knots_and_predicate_truth() {
    let t = trajectory(vec![[0.,-1.],[0.25,0.],[0.5,0.],[0.75,1.],[1.,1.]]);
    for relation in [Relation::Lt, Relation::Le, Relation::Gt, Relation::Ge] {
        let p = Plan::build(spec(select(relation.clone(),source(),constant(0.),constant(1.),constant(0.)), &t, Work::default()), &[I::ZERO]).unwrap();
        assert_eq!(*p.cuts, vec![0.,0.25,0.5,0.75,1.]);
        let truth = |sign: i32| match relation { Relation::Lt => sign<0, Relation::Le => sign<=0, Relation::Gt => sign>0, Relation::Ge => sign>=0 };
        assert_eq!(p.seed().value, if truth(-1) {1.} else {0.});
        let at_plateau = p.prepare(0.25,&p.seed()).unwrap();
        assert_eq!(at_plateau.value, if truth(0) {1.} else {0.});
        let after = p.prepare(0.5,&at_plateau).unwrap();
        assert_eq!(after.value, if truth(1) {1.} else {0.});
        assert!(p.check_incoming(0.,I{lo:0.24,hi:0.26}).is_err());
    }
    let all_zero = trajectory(vec![[0.,0.],[0.25,0.],[1.,0.]]);
    let p=Plan::build(spec(gate(0.),&all_zero,Work::default()), &[I::ZERO]).unwrap();
    assert_eq!(p.seed().value,0.);
    assert_eq!(p.prepare(1.,&p.seed()).unwrap().value,0.);
}
