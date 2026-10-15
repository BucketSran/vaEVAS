//! Optional mathematical time values. These never replace numerical state bounds.
use crate::event_conditions::Selection;
use crate::events::EventModel;
use crate::exact_source::RootTime;
use crate::interval::Interval as I;
use crate::ir::{Expression, StateKind, Term};
use crate::pwl::Trajectory;
use std::collections::BTreeSet;

pub(crate) use crate::exact_source::TimeProofs;

fn identity_nodes(model: &EventModel, trajectory: &Trajectory) -> BTreeSet<usize> {
    let nodes: Vec<_> = model
        .driven
        .iter()
        .map(|name| {
            model
                .program
                .nodes
                .iter()
                .position(|node| node == name)
                .unwrap()
        })
        .collect();
    nodes
        .iter()
        .enumerate()
        .filter_map(|(index, &node)| {
            let points = trajectory.config.pwl.get(index)?;
            // Every original linear segment is the identity when both endpoints
            // are (t,t). The original-curve API excludes generated/clipped sources.
            if !points.iter().all(|p| p[0] == p[1]) {
                return None;
            }
            let expression = Expression::Affine {
                constant: 0.,
                terms: vec![Term {
                    node,
                    coefficient: 1.,
                }],
            };
            trajectory
                .original_guard_curve(&expression, &nodes)
                .map(|_| node)
        })
        .collect()
}

fn literal(expr: &Expression) -> Option<f64> {
    if let Expression::Affine { constant, terms } = expr {
        (terms.is_empty() && constant.is_finite()).then_some(*constant)
    } else {
        None
    }
}

pub(crate) fn value(expr: &Expression, states: &TimeProofs) -> Option<RootTime> {
    expression_value(expr, states, None, &BTreeSet::new())
}

fn shifted(root: RootTime, offset: f64) -> Option<RootTime> {
    root.shifted_fixed(offset, root.bounds()? + I::point(offset))
}

fn expression_value(
    expr: &Expression,
    states: &TimeProofs,
    root: Option<&RootTime>,
    identity: &BTreeSet<usize>,
) -> Option<RootTime> {
    match expr {
        Expression::State { state } => states.get(state).cloned(),
        Expression::Affine { constant, terms }
            if terms.iter().filter(|term| term.node != 0).count() == 1
                && terms
                    .iter()
                    .filter(|term| term.node != 0)
                    .all(|term| term.coefficient == 1. && identity.contains(&term.node)) =>
        {
            // Node zero is the validated electrical ground, identically zero.
            // Do not drop any other term, including unknown zero coefficients.
            shifted(root?.clone(), *constant)
        }
        Expression::Add { left, right } => {
            if let Some(offset) = literal(right) {
                shifted(expression_value(left, states, root, identity)?, offset)
            } else if let Some(offset) = literal(left) {
                shifted(expression_value(right, states, root, identity)?, offset)
            } else {
                None
            }
        }
        // No zero cancellation or unknown scalar equivalence is a provenance proof.
        _ => None,
    }
}

pub(crate) fn apply(
    model: &EventModel,
    trajectory: &Trajectory,
    selection: &Selection,
    before: &TimeProofs,
    root: Option<&RootTime>,
    before_bounds: &[I],
    after_bounds: &[I],
) -> TimeProofs {
    let before: TimeProofs = before
        .iter()
        .filter(|(s, r)| {
            before_bounds
                .get(**s)
                .is_some_and(|bounds| r.refine(*bounds).is_some())
        })
        .map(|(&s, r)| (s, r.clone()))
        .collect();
    crate::diagnostics::counter("time_proof_root_calls", usize::from(root.is_some()));
    let mut result = before.clone();
    let identity = if root.is_some() && !selection.actions.is_empty() {
        identity_nodes(model, trajectory)
    } else {
        BTreeSet::new()
    };
    for (event, indices) in &selection.actions {
        let mut local = before.clone();
        let assignments = model.program.events[*event].assignments();
        for &index in indices {
            let assignment = assignments[index];
            let proof = expression_value(&assignment.rhs, &local, root, &identity);
            local.remove(&assignment.state);
            result.remove(&assignment.state);
            if let Some(proof) = proof
                .filter(|_| matches!(model.program.states[assignment.state].kind, StateKind::Real))
            {
                local.insert(assignment.state, proof.clone());
                result.insert(assignment.state, proof);
            }
        }
    }
    result.retain(|s, r| {
        after_bounds
            .get(*s)
            .is_some_and(|bounds| r.refine(*bounds).is_some())
    });
    crate::diagnostics::counter("time_proof_result_slots", result.len());
    result
}

fn state_refs(expr: &Expression, refs: &mut BTreeSet<usize>) {
    match expr {
        Expression::State { state } => {
            refs.insert(*state);
        }
        Expression::Add { left, right }
        | Expression::Multiply { left, right }
        | Expression::Divide { left, right } => {
            state_refs(left, refs);
            state_refs(right, refs);
        }
        Expression::Power { base, .. } => state_refs(base, refs),
        Expression::Select {
            left,
            right,
            then_value,
            else_value,
            ..
        } => {
            state_refs(left, refs);
            state_refs(right, refs);
            state_refs(then_value, refs);
            state_refs(else_value, refs);
        }
        _ => {}
    }
}

pub(crate) fn invalidate_timers(
    triggers: &[crate::events::TriggerLeaf],
    before: &TimeProofs,
    after: &TimeProofs,
    changed: &mut [bool],
) {
    for (index, leaf) in triggers.iter().enumerate() {
        if let crate::ir::EventTrigger::HeldTimer {
            start,
            period,
            enabled,
            ..
        } = &leaf.trigger
        {
            let mut refs = BTreeSet::new();
            for expr in [start, period, enabled] {
                state_refs(expr, &mut refs);
            }
            if refs.iter().any(|s| before.get(s) != after.get(s)) {
                changed[index] = true;
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ir::{EventTrigger, Tolerances, TransientInputs};
    use num_rational::BigRational as R;
    use serde_json::json;
    fn root(value: R) -> RootTime {
        RootTime::affine(-value, R::from_integer(1.into()), I { lo: 0., hi: 1. }).unwrap()
    }
    fn fixture() -> (EventModel, Trajectory) {
        let origin = json!({"source":"time.va","line":1,"column":1,"instance":"dut"});
        let p=serde_json::from_value(json!({"schema_version":crate::ir::SCHEMA_VERSION,
            "nodes":["0","alias","y"],"operators":[],
            "states":[{"instance":"dut","name":"a","kind":"real","initial":0},
                {"instance":"dut","name":"due","kind":"real","initial":0},
                {"instance":"dut","name":"b","kind":"real","initial":0}],
            "contributions":[{"origin":origin,"branch":{"instance":"dut","local_positive":"out","local_negative":"ref","kind":"voltage"},"positive":2,"negative":0,"rhs":{"op":"state","state":0}}],
            "events":[{"origin":origin,"trigger":{"kind":"timer","start":0.5,"period":0,"enabled":true,"time_tolerance":0.001},"body":[
                {"kind":"assign","state":0,"rhs":{"op":"affine","constant":0,"terms":[{"node":0,"coefficient":-1},{"node":1,"coefficient":1}]}},
                {"kind":"assign","state":1,"rhs":{"op":"add","left":{"op":"state","state":0},"right":{"op":"affine","constant":0.1,"terms":[]}}},
                {"kind":"assign","state":1,"rhs":{"op":"affine","constant":0,"terms":[{"node":2,"coefficient":1}]}}]},
                {"origin":origin,"trigger":{"kind":"timer","start":0.5,"period":0,"enabled":true,"time_tolerance":0.001},"body":[
                {"kind":"assign","state":2,"rhs":{"op":"add","left":{"op":"state","state":0},"right":{"op":"affine","constant":0.2,"terms":[]}}}]}]
        })).unwrap();
        let m = EventModel::new(p, vec!["alias".into()], Tolerances::default()).unwrap();
        let t = Trajectory::new(
            TransientInputs {
                pwl: vec![vec![[0., 0.], [1., 1.]]],
                output_times: vec![0., 1.],
                strobetimes: vec![],
                stop: 1.,
                max_step: 1.,
            },
            1,
        )
        .unwrap();
        (m, t)
    }
    #[test]
    fn selected_order_and_cross_block_before_are_distinct() {
        let (model, trajectory) = fixture();
        let callback = root(R::new(1.into(), 3.into()));
        let mut before = TimeProofs::new();
        before.insert(0, root(R::new(1.into(), 4.into())));
        let selection = Selection {
            actions: vec![(0, vec![0, 1]), (1, vec![0])],
            ..Default::default()
        };
        let result = apply(
            &model,
            &trajectory,
            &selection,
            &before,
            Some(&callback),
            &[I::point(0.25), I::ZERO, I::ZERO],
            &[I { lo: 0., hi: 1. }; 3],
        );
        assert_eq!(result[&1], shifted(callback, 0.1).unwrap());
        assert_eq!(result[&2], shifted(before[&0].clone(), 0.2).unwrap());
        let overwritten = Selection {
            actions: vec![(0, vec![0, 1, 2])],
            ..Default::default()
        };
        let result = apply(
            &model,
            &trajectory,
            &overwritten,
            &before,
            Some(&root(R::new(1.into(), 3.into()))),
            &[I::point(0.25), I::ZERO, I::ZERO],
            &[I { lo: 0., hi: 1. }; 3],
        );
        assert!(!result.contains_key(&1));
    }
    #[test]
    fn complete_original_curve_and_unknown_zero_reference_qualify_separately() {
        let (model, mut trajectory) = fixture();
        assert!(identity_nodes(&model, &trajectory).contains(&1));
        trajectory.config.pwl[0] = vec![[0., 0.], [0.5, 0.4], [1., 1.]];
        assert!(identity_nodes(&model, &trajectory).is_empty());
        let callback = root(R::new(1.into(), 3.into()));
        let expression = Expression::Affine {
            constant: 0.,
            terms: vec![
                Term {
                    node: 1,
                    coefficient: 1.,
                },
                Term {
                    node: 2,
                    coefficient: 0.,
                },
            ],
        };
        assert!(expression_value(
            &expression,
            &TimeProofs::new(),
            Some(&callback),
            &BTreeSet::from([1])
        )
        .is_none());
    }
    #[test]
    fn generated_identity_curve_cannot_become_an_original_time_source() {
        let (mut model, mut trajectory) = fixture();
        model.program.nodes.push("generated".into());
        model.driven.push("generated".into());
        trajectory
            .add_enclosed_source(vec![[0., 0.], [1., 1.]], 0.)
            .unwrap();
        assert!(!identity_nodes(&model, &trajectory).contains(&3));
    }
    #[test]
    fn contained_failure_discards_optional_proof_without_altering_bounds() {
        let (model, trajectory) = fixture();
        let selection = Selection {
            actions: vec![(0, vec![0, 1])],
            ..Default::default()
        };
        let bounds = [I::ZERO; 3];
        let result = apply(
            &model,
            &trajectory,
            &selection,
            &TimeProofs::new(),
            Some(&root(R::new(1.into(), 3.into()))),
            &bounds,
            &bounds,
        );
        assert!(result.is_empty());
        assert_eq!(bounds, [I::ZERO; 3]);
    }
    #[test]
    fn same_numeric_enclosure_different_time_or_cleared_proof_invalidates_all_timer_refs() {
        let a = root(R::new(1.into(), 3.into()));
        let b = root(R::new(1.into(), 3.into()) + R::new(1.into(), (1_u64 << 60).into()));
        assert_eq!(a.bounds(), b.bounds());
        let constant = || {
            Box::new(Expression::Affine {
                constant: 0.,
                terms: vec![],
            })
        };
        let refs = [
            Expression::State { state: 0 },
            Expression::State { state: 0 },
            Expression::Multiply {
                left: constant(),
                right: Box::new(Expression::State { state: 0 }),
            },
        ];
        for (field, expression) in refs.into_iter().enumerate() {
            let mut start = constant();
            let mut period = constant();
            let mut enabled = constant();
            match field {
                0 => start = Box::new(expression),
                1 => period = Box::new(expression),
                _ => enabled = Box::new(expression),
            }
            let triggers = vec![crate::events::TriggerLeaf {
                event: 0,
                index: 0,
                trigger: EventTrigger::HeldTimer {
                    start,
                    period,
                    enabled,
                    time_tolerance: 0.001,
                },
            }];
            let before = TimeProofs::from([(0, a.clone())]);
            for after in [TimeProofs::from([(0, b.clone())]), TimeProofs::new()] {
                let mut changed = [false];
                invalidate_timers(&triggers, &before, &after, &mut changed);
                assert!(changed[0]);
            }
        }
    }
    #[test]
    fn failed_candidate_with_new_time_proofs_retries_same_controller_without_leaks() {
        use crate::transient::{Controller, Frame};
        let (base, trajectory) = fixture();
        let mut program = base.program;
        let origin = program.contributions[0].origin.clone();
        for (index, delay) in [0.1, 0.1_f64.next_up()].into_iter().enumerate() {
            let mut origin = origin.clone();
            origin.line = 10 + index;
            program.operators.push(crate::ir::OperatorSpec::Transition {
                input: Expression::State { state: 0 },
                delay,
                rise: 0.25,
                fall: 0.25,
                origin: origin.clone(),
            });
        }
        let model = EventModel::new(program, vec!["alias".into()], Tolerances::default()).unwrap();
        let states = vec![0.25, 0., 0.];
        let bounds = states.iter().copied().map(I::point).collect::<Vec<_>>();
        let operators =
            crate::operators::Operators::new(&model.program, &trajectory, &model.driven, &states)
                .unwrap();
        let circuit = model
            .circuit_with(&states, &operators.values(0.).unwrap())
            .unwrap();
        let frame = Frame {
            time: 0.,
            states: states.clone(),
            state_bounds: bounds.clone(),
            solution: circuit.solve(&trajectory.values(0.)).unwrap(),
            circuit,
            operators,
            time_proofs: TimeProofs::from([(0, root(R::new(1.into(), 4.into())))]),
        };
        let calendar = crate::schedule::schedule_held(&model, &trajectory, &bounds).unwrap();
        let mut controller = Controller {
            accepted: frame.clone(),
            event: 0,
            records: vec![],
            outputs: vec![],
        };
        let before = controller.accepted.time_proofs.clone();
        let callback = root(R::new(1.into(), 2.into()));
        let (candidate, _) = crate::transient::prepare_root_window_selected_impl(
            &model,
            &trajectory,
            &controller.accepted,
            crate::transient::EventMoment {
                exact_root: Some(&callback),
                representative: 0.5,
                observation: I::point(0.5),
                fired_roots: &[0],
                prediction_end: 1.,
            },
            &[0],
            false,
        )
        .unwrap();
        assert_ne!(candidate.time_proofs, before);
        assert!(candidate.operators.next_breakpoint(0.).is_some());
        let bad_calendar: Vec<_> = calendar.iter().filter(|e| e.event == 0).cloned().collect();
        let error = controller
            .accept_events(&model, &trajectory, &bad_calendar)
            .err()
            .unwrap();
        assert!(error.message.contains("ordering of operator deadlines"));
        assert_eq!(controller.accepted.time_proofs, before);
        assert_eq!(controller.accepted.states, states);
        assert_eq!(controller.event, 0);
        assert!(controller.records.is_empty());
        assert_eq!(controller.accepted.operators.next_breakpoint(0.), None);
        let retry: Vec<_> = calendar.iter().filter(|e| e.event == 1).cloned().collect();
        let mut baseline = Controller {
            accepted: frame,
            event: 0,
            records: vec![],
            outputs: vec![],
        };
        controller
            .accept_events(&model, &trajectory, &retry)
            .unwrap();
        baseline.accept_events(&model, &trajectory, &retry).unwrap();
        assert_eq!(
            controller.accepted.time_proofs,
            baseline.accepted.time_proofs
        );
        assert_eq!(
            controller.accepted.state_bounds,
            baseline.accepted.state_bounds
        );
        assert_eq!(controller.accepted.states, baseline.accepted.states);
        assert_eq!(
            serde_json::to_value(&controller.records).unwrap(),
            serde_json::to_value(&baseline.records).unwrap()
        );
        assert_eq!(
            controller.accepted.operators.values(0.75).unwrap(),
            baseline.accepted.operators.values(0.75).unwrap()
        );
    }
    #[test]
    fn branch_review_ground_zero_is_exact_but_unknown_zero_and_integer_are_not_provenance() {
        let (mut model, trajectory) = fixture();
        let callback = root(R::new(1.into(), 3.into()));
        let select = Selection {
            actions: vec![(0, vec![0])],
            ..Default::default()
        };
        let bounds = [I { lo: 0., hi: 1. }; 3];
        let result = apply(
            &model,
            &trajectory,
            &select,
            &TimeProofs::new(),
            Some(&callback),
            &bounds,
            &bounds,
        );
        assert_eq!(result[&0], callback);
        // The original voltage expression contains both ground (-1) and identity (+1).
        // An explicit zero reference to a different node remains a dependency.
        let unknown_zero = Expression::Affine {
            constant: 0.,
            terms: vec![
                Term {
                    node: 0,
                    coefficient: -1.,
                },
                Term {
                    node: 1,
                    coefficient: 1.,
                },
                Term {
                    node: 2,
                    coefficient: 0.,
                },
            ],
        };
        assert!(expression_value(
            &unknown_zero,
            &TimeProofs::new(),
            Some(&callback),
            &BTreeSet::from([1])
        )
        .is_none());
        model.program.states[0].kind = StateKind::Integer;
        let integer = apply(
            &model,
            &trajectory,
            &select,
            &TimeProofs::new(),
            Some(&callback),
            &bounds,
            &bounds,
        );
        assert!(integer.is_empty());
        // Even an integer-valued callback does not create a Real time identity.
        let one = root(R::from_integer(1.into()));
        let points = [I::point(1.); 3];
        assert!(apply(
            &model,
            &trajectory,
            &select,
            &TimeProofs::new(),
            Some(&one),
            &points,
            &points
        )
        .is_empty());
        // Applying the same selected write clears a stale key; bounds are untouched.
        let before = TimeProofs::from([(0, one.clone())]);
        assert!(apply(
            &model,
            &trajectory,
            &select,
            &before,
            Some(&one),
            &points,
            &points
        )
        .is_empty());
        assert_eq!(points, [I::point(1.); 3]);
    }
}

#[cfg(test)]
mod held_review_tests {
    use super::*;
    use crate::ir::{Tolerances, TransientInputs};
    use num_rational::BigRational as R;
    use serde_json::{json, Value};
    fn c(v: f64) -> Value {
        json!({"op":"affine","constant":v,"terms":[]})
    }
    fn st(s: usize) -> Value {
        json!({"op":"state","state":s})
    }
    fn node(n: usize) -> Value {
        json!({"op":"affine","constant":0,"terms":[{"node":n,"coefficient":1}]})
    }
    fn add(a: Value, b: Value) -> Value {
        json!({"op":"add","left":a,"right":b})
    }
    fn asn(s: usize, e: Value) -> Value {
        json!({"kind":"assign","state":s,"rhs":e})
    }
    fn model(bodies: Vec<Vec<Value>>) -> EventModel {
        let origin = json!({"source":"review.va","line":1,"column":1,"instance":"D"});
        let events:Vec<_>=bodies.into_iter().map(|body|json!({"origin":origin,"trigger":{"kind":"timer","start":0.5,"period":0,"enabled":true,"time_tolerance":1e-6},"body":body})).collect();
        let p=serde_json::from_value(json!({"schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","ordinary_name","$abstime","generated","y"],"states":[{"instance":"D","name":"a","kind":"real","initial":0.25},{"instance":"D","name":"b","kind":"real","initial":0},{"instance":"D","name":"c","kind":"real","initial":0}],"events":events,"operators":[],"contributions":[{"origin":origin,"branch":{"instance":"D","local_positive":"out","local_negative":"ref","kind":"voltage"},"positive":4,"negative":0,"rhs":st(0)}]})).unwrap();
        EventModel::new(
            p,
            vec![
                "ordinary_name".into(),
                "$abstime".into(),
                "generated".into(),
            ],
            Tolerances::default(),
        )
        .unwrap()
    }
    fn trajectory(fake: Vec<[f64; 2]>) -> Trajectory {
        let mut t = Trajectory::new(
            TransientInputs {
                pwl: vec![vec![[0., 0.], [0.25, 0.25], [1., 1.]], fake],
                strobetimes: vec![],
                output_times: vec![0., 1.],
                stop: 1.,
                max_step: 0.1,
            },
            2,
        )
        .unwrap();
        t.add_enclosed_source(vec![[0., 0.], [1., 1.]], 0.).unwrap();
        t
    }
    fn proof(v: R) -> RootTime {
        RootTime::affine(-v, R::from_integer(1.into()), I { lo: -2., hi: 3. }).unwrap()
    }
    #[test]
    fn original_full_curve_not_name_sample_or_generated_curve_qualifies() {
        let m = model(vec![vec![
            asn(0, node(1)),
            asn(1, node(2)),
            asn(2, node(3)),
        ]]);
        for fake in [
            vec![[0., 0.], [0.5, 0.5], [1., 0.75]],
            vec![[0., 0.], [0.25, 0.125], [0.5, 0.5], [1., 1.]],
        ] {
            let t = trajectory(fake);
            assert_eq!(identity_nodes(&m, &t), BTreeSet::from([1]));
            let selection = Selection {
                actions: vec![(0, vec![0, 1, 2])],
                ..Default::default()
            };
            let root = proof(R::new(1.into(), 3.into()));
            let got = apply(
                &m,
                &t,
                &selection,
                &TimeProofs::new(),
                Some(&root),
                &[I::point(0.25), I::ZERO, I::ZERO],
                &[I { lo: 0., hi: 1. }; 3],
            );
            assert_eq!(got.len(), 1);
            assert_eq!(got.get(&0), Some(&root));
        }
    }
    #[test]
    fn block_before_local_order_unknown_write_and_final_containment() {
        let m = model(vec![
            vec![
                asn(0, node(1)),
                asn(0, add(st(0), c(0.1))),
                asn(0, json!({"op":"multiply","left":st(0),"right":c(1.)})),
            ],
            vec![asn(1, add(st(0), c(0.2)))],
        ]);
        let t = trajectory(vec![[0., 0.], [1., 0.75]]);
        let root = proof(R::new(1.into(), 3.into()));
        let old = proof(R::new(1.into(), 4.into()));
        let before = TimeProofs::from([(0, old.clone())]);
        let bb = [I::point(0.25), I::ZERO, I::ZERO];
        let wide = [I { lo: 0., hi: 1. }; 3];
        let selection = Selection {
            actions: vec![(0, vec![0, 1]), (1, vec![0])],
            ..Default::default()
        };
        let got = apply(&m, &t, &selection, &before, Some(&root), &bb, &wide);
        assert_eq!(
            got.get(&0),
            Some(&proof(
                R::new(1.into(), 3.into()) + crate::exact_source::binary(0.1).unwrap()
            ))
        );
        assert_eq!(
            got.get(&1),
            Some(&proof(
                R::new(1.into(), 4.into()) + crate::exact_source::binary(0.2).unwrap()
            ))
        );
        let clear = Selection {
            actions: vec![(0, vec![0, 1, 2])],
            ..Default::default()
        };
        assert!(!apply(&m, &t, &clear, &before, Some(&root), &bb, &wide).contains_key(&0));
        assert!(!apply(&m, &t, &selection, &before, None, &bb, &wide).contains_key(&0));
        assert_eq!(
            apply(&m, &t, &Selection::default(), &before, None, &bb, &bb),
            before
        );
        assert!(apply(
            &m,
            &t,
            &Selection::default(),
            &before,
            None,
            &bb,
            &[I::ZERO; 3]
        )
        .is_empty());
        assert!(value(
            &serde_json::from_value(json!({"op":"multiply","left":c(0.),"right":st(0)})).unwrap(),
            &before
        )
        .is_none());
    }
    #[test]
    fn same_interval_proof_change_clear_and_hidden_zero_dependencies_invalidate() {
        let a = proof(R::new(1.into(), 3.into()));
        let b = proof(R::new(1.into(), 3.into()) + R::new(1.into(), (1u64 << 60).into()));
        assert_eq!(a.bounds(), b.bounds());
        let hidden = json!({"op":"multiply","left":c(0.),"right":st(0)});
        let expressions = [
            st(0),
            add(c(1.), hidden.clone()),
            json!({"op":"select","relation":"gt","left":c(1.),"right":c(0.),"then_value":c(1.),"else_value":hidden,"origin":{"source":"review.va","line":1,"column":1,"instance":"D"}}),
        ];
        let mut leaves = vec![];
        for (i, expr) in expressions.into_iter().enumerate() {
            let (start, period, enabled) = match i {
                0 => (expr, c(0.), c(1.)),
                1 => (c(0.5), expr, c(1.)),
                _ => (c(0.5), c(0.), expr),
            };
            leaves.push(crate::events::TriggerLeaf {event:i,index:0,trigger:serde_json::from_value(json!({"kind":"held_timer","start":start,"period":period,"enabled":enabled,"time_tolerance":1e-6})).unwrap()});
        }
        let before = TimeProofs::from([(0, a.clone())]);
        for after in [TimeProofs::from([(0, b)]), TimeProofs::new()] {
            let mut changed = vec![false; 3];
            invalidate_timers(&leaves, &before, &after, &mut changed);
            assert_eq!(changed, vec![true; 3]);
        }
        let mut unchanged = vec![false; 3];
        invalidate_timers(&leaves, &before, &before.clone(), &mut unchanged);
        assert_eq!(unchanged, vec![false; 3]);
    }
}
