//! Optional mathematical time values. These never replace numerical state bounds.
use crate::event_conditions::Selection;
use crate::events::EventModel;
use crate::exact_source::RootTime;
use crate::interval::Interval as I;
use crate::ir::{EventMathFunction, Expression, StateKind, Term};
use crate::pwl::Trajectory;
use std::collections::BTreeSet;
#[path = "event_history_time.rs"]
mod history;

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
    expression_with_points(expr, states, root, identity, None)
}

fn expression_with_points(
    expr: &Expression,
    states: &TimeProofs,
    root: Option<&RootTime>,
    identity: &BTreeSet<usize>,
    points: Option<&crate::event_value_proof::LocalState>,
) -> Option<RootTime> {
    let exact_offset = |expr| {
        literal(expr)
            .and_then(crate::exact_source::binary)
            .or_else(|| points?.value(expr, &[]))
    };
    match expr {
        Expression::IntegerPrimitive { .. } => None,
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
            let add = |time, offset| {
                let time = expression_with_points(time, states, root, identity, points)?;
                let offset = exact_offset(offset)?;
                // LocalState proves the complete scalar expression from point
                // inputs. Its rational result need not be a binary64 point.
                // Keep discovery and accepted-state bounds unchanged; neither
                // a nominal value nor an inherited nonpoint state is proof.
                let discovery = time.bounds()? + crate::exact_source::enclosure(&offset)?;
                let sum = crate::exact_source::Budget(0).check(time.rational() + offset)?;
                RootTime::affine(
                    -sum,
                    num_rational::BigRational::from_integer(1.into()),
                    discovery,
                )
            };
            add(left, right).or_else(|| add(right, left))
        }
        Expression::EventMath { function, args, .. }
            if matches!(function, EventMathFunction::Min | EventMathFunction::Max)
                && args.len() == 2 =>
        {
            let exact = |arg| {
                expression_with_points(arg, states, root, identity, points)
                    .or_else(|| RootTime::point(literal(arg)?))
            };
            let a = exact(&args[0])?;
            let b = exact(&args[1])?;
            let order = a.order(&b);
            let first = if matches!(function, EventMathFunction::Min) {
                order != std::cmp::Ordering::Greater
            } else {
                order != std::cmp::Ordering::Less
            };
            Some(if first { a } else { b })
        }
        // No zero cancellation or unknown scalar equivalence is a provenance proof.
        _ => None,
    }
}

pub(crate) fn apply_charged(
    model: &EventModel,
    trajectory: &Trajectory,
    selection: &Selection,
    before: &TimeProofs,
    root: Option<&RootTime>,
    before_bounds: &[I],
    after_bounds: &[I],
) -> Result<TimeProofs, crate::ir::Error> {
    if let Some(w) = crate::event_value_proof::history::work(model) {
        return history::apply(
            model,
            trajectory,
            selection,
            before,
            root,
            before_bounds,
            after_bounds,
            w,
        );
    }
    Ok(apply(
        model,
        trajectory,
        selection,
        before,
        root,
        before_bounds,
        after_bounds,
    ))
}
/// Reuse the physical event's validated scalar context for ordinary time
/// arithmetic. Paid Floor/history consumers retain their established route.
#[allow(clippy::too_many_arguments)]
pub(crate) fn apply_with_context_charged(
    model: &EventModel,
    trajectory: &Trajectory,
    selection: &Selection,
    before: &TimeProofs,
    root: Option<&RootTime>,
    before_bounds: &[I],
    after_bounds: &[I],
    context: &crate::event_value_proof::Context<'_>,
) -> Result<TimeProofs, crate::ir::Error> {
    if crate::analytic_request::proof_owner(model).is_some() || context.floor_work().is_some() {
        // Preserve the original owner and its Result, including exhausted
        // retries. This bridge grants no new paid-history/Floor capability.
        return apply_charged(
            model,
            trajectory,
            selection,
            before,
            root,
            before_bounds,
            after_bounds,
        );
    }
    let points =
        crate::event_value_proof::LocalState::try_with_context(before_bounds, Some(context))?;
    Ok(apply_using_points(
        model,
        trajectory,
        selection,
        before,
        root,
        before_bounds,
        after_bounds,
        Some(&points),
    ))
}

/// Explicit original owner for the already qualified mixed held-ramp preview.
#[allow(clippy::too_many_arguments)]
pub(crate) fn apply_with_bound_source(
    model: &EventModel,
    trajectory: &Trajectory,
    selection: &Selection,
    before: &TimeProofs,
    root: &RootTime,
    before_bounds: &[I],
    after_bounds: &[I],
    source: &crate::transition_source_plan::ProofContext,
) -> Result<TimeProofs, crate::ir::Error> {
    crate::event_floor::check_provided_binding(source, &model.program, trajectory, &model.driven)?;
    history::apply_with_input_nodes(
        model,
        trajectory,
        selection,
        before,
        Some(root),
        before_bounds,
        after_bounds,
        source.borrow_work(),
        Some(source.event_input_nodes()),
    )
}

pub(crate) fn copy_history(
    source: &TimeProofs,
    w: &crate::transition_source_plan::Work,
) -> Result<TimeProofs, crate::ir::Error> {
    history::copy_map(source, w)
}
pub(crate) fn equal_history(
    a: &TimeProofs,
    b: &TimeProofs,
    w: &crate::transition_source_plan::Work,
) -> Result<bool, crate::ir::Error> {
    history::equal(a, b, w)
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
    apply_using_points(
        model,
        trajectory,
        selection,
        before,
        root,
        before_bounds,
        after_bounds,
        None,
    )
}

#[allow(clippy::too_many_arguments)]
fn apply_using_points(
    model: &EventModel,
    trajectory: &Trajectory,
    selection: &Selection,
    before: &TimeProofs,
    root: Option<&RootTime>,
    before_bounds: &[I],
    after_bounds: &[I],
    initial_points: Option<&crate::event_value_proof::LocalState>,
) -> TimeProofs {
    let mut before: TimeProofs = before
        .iter()
        .filter(|(s, r)| {
            before_bounds
                .get(**s)
                .is_some_and(|bounds| r.refine(*bounds).is_some())
        })
        .map(|(&s, r)| (s, r.clone()))
        .collect();
    // A simple held start with a genuinely point accepted value is an exact
    // absolute time. Seed only real timer starts, never arbitrary observer
    // constants or a nominal endpoint of an uncertain time interval.
    for leaf in &model.triggers {
        if let crate::ir::EventTrigger::HeldTimer { start, .. } = &leaf.trigger {
            if let Expression::State { state } = start.as_ref() {
                if matches!(model.program.states[*state].kind, StateKind::Real) {
                    if let Some(bounds) = before_bounds.get(*state) {
                        if bounds.finite() && bounds.lo == bounds.hi {
                            if let Some(point) = RootTime::point(bounds.lo) {
                                before.entry(*state).or_insert(point);
                            }
                        }
                    }
                }
            }
        }
    }
    crate::diagnostics::counter("time_proof_root_calls", usize::from(root.is_some()));
    let mut result = before.clone();
    let identity = if root.is_some() && !selection.actions.is_empty() {
        identity_nodes(model, trajectory)
    } else {
        BTreeSet::new()
    };
    for (event, indices) in &selection.actions {
        let mut local = before.clone();
        // Each callback starts from the accepted frame, never another
        // callback's provisional assignments or the final after-state.
        let mut points = initial_points
            .cloned()
            .unwrap_or_else(|| crate::event_value_proof::LocalState::new(before_bounds));
        let assignments = model.program.events[*event].assignments();
        for &index in indices {
            let assignment = &assignments[index];
            let proof =
                expression_with_points(&assignment.rhs, &local, root, &identity, Some(&points))
                    .or_else(|| {
                        // A literal reset of an already tracked time is still exact.
                        // Never seed all observer constants, or restore a proof cleared
                        // by an earlier unsupported write in this same callback.
                        local
                            .contains_key(&assignment.state)
                            .then(|| RootTime::point(literal(&assignment.rhs)?))
                            .flatten()
                    });
            // Empty fallback nodes keep unproved voltage/history reads
            // unknown. Contextual nodes carry only the existing physical
            // proof; every operand is still checked by LocalState.
            points.assign_proof(assignment.state, &assignment.rhs, &[]);
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
        Expression::EventMath {
            function: EventMathFunction::Min | EventMathFunction::Max,
            args,
            ..
        } => {
            for arg in args {
                state_refs(arg, refs);
            }
        }
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
                analytic_sources: vec![],
                pwl_errors_v: None,
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

    fn extremum(
        function: crate::ir::EventMathFunction,
        a: Expression,
        b: Expression,
    ) -> Expression {
        Expression::EventMath {
            function,
            args: vec![a, b],
            origin: serde_json::from_value(
                json!({"source":"time.va","line":1,"column":1,"instance":"dut"}),
            )
            .unwrap(),
        }
    }
    fn constant(value: f64) -> Expression {
        Expression::Affine {
            constant: value,
            terms: vec![],
        }
    }
    fn assignments(values: Vec<(usize, Expression)>) -> (EventModel, Trajectory) {
        let (base, trajectory) = fixture();
        let mut program = base.program;
        program.contributions.clear();
        program.nodes.truncate(2);
        program.events[0].body = serde_json::from_value(json!(values
            .into_iter()
            .map(|(state, rhs)| json!({"kind":"assign","state":state,"rhs":rhs}))
            .collect::<Vec<_>>()))
        .unwrap();
        (
            EventModel::new(program, base.driven, Tolerances::default()).unwrap(),
            trajectory,
        )
    }

    #[test]
    fn tracked_literal_sentinel_preserves_min_without_tagging_other_constants() {
        let (model, trajectory) = assignments(vec![
            (0, constant(1e30)),
            (1, constant(42.)),
            (
                1,
                extremum(
                    crate::ir::EventMathFunction::Min,
                    Expression::State { state: 0 },
                    Expression::State { state: 2 },
                ),
            ),
        ]);
        let early = root(R::new(1.into(), 4.into()));
        let later = root(R::new(1.into(), 3.into()));
        let before = TimeProofs::from([(0, early), (2, later.clone())]);
        let old_bounds = [I::point(0.25), I::ZERO, I { lo: 0.3, hi: 0.4 }];
        let after_bounds = [
            I::point(1e30),
            I { lo: 0.3, hi: 0.4 },
            I { lo: 0.3, hi: 0.4 },
        ];
        let result = apply(
            &model,
            &trajectory,
            &Selection {
                actions: vec![(0, vec![0, 1, 2])],
                ..Default::default()
            },
            &before,
            None,
            &old_bounds,
            &after_bounds,
        );
        assert_eq!(result.get(&0), Some(&RootTime::point(1e30).unwrap()));
        assert_eq!(result.get(&1), Some(&later));
        assert_eq!(result.len(), 3);
        let select = Selection {
            actions: vec![(0, vec![1])],
            ..Default::default()
        };
        let literal = apply(
            &model,
            &trajectory,
            &select,
            &before,
            None,
            &old_bounds,
            &[old_bounds[0], I::point(42.), old_bounds[2]],
        );
        assert!(!literal.contains_key(&1));
        let invalid_before = [I::ZERO, old_bounds[1], old_bounds[2]];
        let cleared = apply(
            &model,
            &trajectory,
            &Selection {
                actions: vec![(0, vec![0])],
                ..Default::default()
            },
            &before,
            None,
            &invalid_before,
            &after_bounds,
        );
        assert!(
            !cleared.contains_key(&0),
            "an already invalidated proof cannot authorize a literal reset"
        );
    }

    #[test]
    fn unsupported_write_clears_before_literal_reset_and_unknown_min_max_stay_unproved() {
        let (model, trajectory) = assignments(vec![
            (
                0,
                Expression::Multiply {
                    left: Box::new(Expression::State { state: 0 }),
                    right: Box::new(constant(1.)),
                },
            ),
            (0, constant(1e30)),
            (
                1,
                extremum(
                    crate::ir::EventMathFunction::Min,
                    Expression::State { state: 0 },
                    Expression::State { state: 2 },
                ),
            ),
        ]);
        let later = root(R::new(1.into(), 3.into()));
        let before = TimeProofs::from([(0, root(R::new(1.into(), 4.into()))), (2, later.clone())]);
        let result = apply(
            &model,
            &trajectory,
            &Selection {
                actions: vec![(0, vec![0, 1, 2])],
                ..Default::default()
            },
            &before,
            None,
            &[I::point(0.25), I::ZERO, I { lo: 0.3, hi: 0.4 }],
            &[
                I::point(1e30),
                I { lo: 0.3, hi: 0.4 },
                I { lo: 0.3, hi: 0.4 },
            ],
        );
        assert_eq!(result, TimeProofs::from([(2, later)]));
        for function in [
            crate::ir::EventMathFunction::Min,
            crate::ir::EventMathFunction::Max,
        ] {
            assert!(value(
                &extremum(function, Expression::State { state: 0 }, constant(0.)),
                &result
            )
            .is_none());
        }
        assert_eq!(before.len(), 2);
    }

    #[test]
    fn min_max_compare_exact_roots_with_equal_boxes_and_require_both_proofs() {
        use crate::ir::EventMathFunction::{Max, Min};
        let a = root(R::new(1.into(), 3.into()));
        let b = root(R::new(1.into(), 3.into()) + R::new(1.into(), (1_u64 << 60).into()));
        assert_eq!(a.bounds(), b.bounds());
        let states = TimeProofs::from([(0, a.clone()), (1, b.clone())]);
        for (function, expected) in [(Min, a.clone()), (Max, b.clone())] {
            let expression = extremum(
                function,
                Expression::State { state: 0 },
                Expression::State { state: 1 },
            );
            assert_eq!(value(&expression, &states), Some(expected));
            assert_eq!(
                value(
                    &expression,
                    &TimeProofs::from([(0, a.clone()), (1, a.clone())])
                ),
                Some(a.clone())
            );
            assert!(value(&expression, &TimeProofs::from([(0, a.clone())])).is_none());
        }
        assert_eq!(
            value(
                &extremum(Min, Expression::State { state: 0 }, constant(0.)),
                &states
            ),
            RootTime::point(0.)
        );
        assert_eq!(
            value(
                &extremum(Max, Expression::State { state: 0 }, constant(1e30)),
                &states
            ),
            RootTime::point(1e30)
        );
        assert!(
            value(&constant(1e30), &states).is_none(),
            "standalone literals do not seed provenance"
        );
        assert!(value(
            &extremum(Min, Expression::State { state: 0 }, constant(f64::INFINITY)),
            &states
        )
        .is_none());
    }

    #[test]
    fn min_max_proof_changes_invalidate_nested_start_period_and_enable() {
        for function in [
            crate::ir::EventMathFunction::Min,
            crate::ir::EventMathFunction::Max,
        ] {
            let expression = extremum(function, Expression::State { state: 0 }, constant(0.5));
            let triggers: Vec<_> = (0..3)
                .map(|field| crate::events::TriggerLeaf {
                    event: 0,
                    index: field,
                    trigger: EventTrigger::HeldTimer {
                        start: Box::new(if field == 0 {
                            expression.clone()
                        } else {
                            constant(0.)
                        }),
                        period: Box::new(if field == 1 {
                            expression.clone()
                        } else {
                            constant(0.)
                        }),
                        enabled: Box::new(if field == 2 {
                            expression.clone()
                        } else {
                            constant(1.)
                        }),
                        time_tolerance: 0.001,
                    },
                })
                .collect();
            let a = root(R::new(1.into(), 3.into()));
            let b = root(R::new(1.into(), 3.into()) + R::new(1.into(), (1_u64 << 60).into()));
            assert_eq!(a.bounds(), b.bounds());
            let before = TimeProofs::from([(0, a)]);
            for after in [TimeProofs::from([(0, b)]), TimeProofs::new()] {
                let mut changed = vec![false; 3];
                invalidate_timers(&triggers, &before, &after, &mut changed);
                assert_eq!(changed, vec![true; 3]);
            }
        }
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
            value_proofs: Default::default(),
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
        let (candidate, _, _) = crate::transient::prepare_root_window_selected_impl(
            &model,
            &trajectory,
            &controller.accepted,
            crate::transient::EventMoment {
                exact_root: Some(&callback),
                occurrence_certified: false,
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
                analytic_sources: vec![],
                pwl_errors_v: None,
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

#[cfg(test)]
mod held_point_tests {
    use super::*;
    use crate::ir::{Program, Tolerances, TransientInputs, SCHEMA_VERSION};
    use serde_json::{json, Value};

    fn c(x: f64) -> Value {
        json!({"op":"affine","constant":x,"terms":[]})
    }
    fn s(i: usize) -> Value {
        json!({"op":"state","state":i})
    }
    fn add(a: Value, b: Value) -> Value {
        json!({"op":"add","left":a,"right":b})
    }
    fn assign(i: usize, rhs: Value) -> Value {
        json!({"kind":"assign","state":i,"rhs":rhs})
    }
    fn origin() -> Value {
        json!({"source":"held-point.va","line":1,"column":1,"instance":"dut"})
    }
    fn trajectory(good: bool) -> Trajectory {
        Trajectory::new(
            TransientInputs {
                analytic_sources: vec![],
                pwl_errors_v: None,
                strobetimes: vec![],
                pwl: vec![vec![
                    [0., 0.16],
                    [0.25, 0.16],
                    [0.5, if good { -0.16 } else { 0.16 }],
                    [1., if good { -0.16 } else { 0.16 }],
                ]],
                output_times: vec![0., 0.25, 0.5, 1.],
                stop: 1.,
                max_step: 1.,
            },
            1,
        )
        .unwrap()
    }
    fn model(body: Value, with_history: bool) -> EventModel {
        let mut p: Program = serde_json::from_value(json!({
            "schema_version":SCHEMA_VERSION,"nodes":["0","u","y"],
            "states":[{"instance":"dut","name":"due","kind":"real","initial":0.5},
                {"instance":"dut","name":"half","kind":"real","initial":0.1},
                {"instance":"dut","name":"x","kind":"real","initial":0},
                {"instance":"dut","name":"p","kind":"real","initial":0},
                {"instance":"dut","name":"span","kind":"real","initial":1}],
            "events":[{"origin":origin(),"trigger":{"kind":"held_timer","start":s(0),
                "period":c(0.),"enabled":c(1.),"time_tolerance":1e-9},"body":body}],
            "contributions":[{"origin":origin(),"branch":{"instance":"dut",
                "local_positive":"p","local_negative":"r","kind":"voltage"},
                "positive":2,"negative":0,"rhs":c(0.)}],"operators":[]
        }))
        .unwrap();
        if with_history {
            p.operators = serde_json::from_value(json!([{"kind":"transition","input":s(4),
                "delay":0,"rise":0.125,"fall":0.5,"origin":origin()}]))
            .unwrap();
            p.contributions[0].rhs = serde_json::from_value(add(
                json!({"op":"operator","operator":0}),
                json!({"op":"multiply","left":c(1e12),"right":s(3)}),
            ))
            .unwrap();
        }
        EventModel::new(
            p,
            vec!["u".into()],
            Tolerances {
                absolute: 1e-8,
                relative: 0.,
            },
        )
        .unwrap()
    }
    #[test]
    fn held_point_seed_offsets_follow_source_order_and_after_bounds() {
        for before_write in [true, false] {
            let change = assign(1, c(0.125));
            let due = assign(0, add(s(0), s(1)));
            let body = if before_write {
                json!([change, due])
            } else {
                json!([due, change])
            };
            let model = model(body, false);
            let trajectory = trajectory(true);
            let before = [I::point(0.1), I::point(0.1), I::ZERO, I::ZERO, I::ONE];
            let offset = if before_write { 0.125 } else { 0.1 };
            let exact = crate::exact_source::binary(0.1).unwrap()
                + crate::exact_source::binary(offset).unwrap();
            let mut after = before;
            after[0] = crate::exact_source::enclosure(&exact).unwrap();
            after[1] = I::point(0.125);
            let selection = Selection {
                actions: vec![(0, vec![0, 1])],
                ..Default::default()
            };
            let proof = apply(
                &model,
                &trajectory,
                &selection,
                &TimeProofs::new(),
                None,
                &before,
                &after,
            );
            assert_eq!(proof[&0].rational(), &exact);
            assert!(
                !proof.contains_key(&1),
                "ordinary offset constants are not time seeds"
            );
            after[0] = I::point(0.9);
            assert!(!apply(
                &model,
                &trajectory,
                &selection,
                &TimeProofs::new(),
                None,
                &before,
                &after
            )
            .contains_key(&0));
        }
    }
    #[test]
    fn contextual_source_offsets_follow_same_callback_assignment_order() {
        for sample_first in [true, false] {
            let sample = assign(
                1,
                json!({"op":"affine","constant":0.,
                "terms":[{"node":1,"coefficient":1.}]}),
            );
            let due = assign(0, add(s(0), s(1)));
            let body = if sample_first {
                json!([sample, due])
            } else {
                json!([due, sample])
            };
            let model = model(body, false);
            let trajectory = trajectory(true);
            let before = [I::point(0.5), I::point(0.125), I::ZERO, I::ZERO, I::ONE];
            let mut after = before;
            after[0] = I { lo: 0.5, hi: 0.75 };
            after[1] = I::point(0.16);
            let values = crate::event_value_proof::Proofs::new();
            let root = RootTime::point(0.25).unwrap();
            let context = crate::event_value_proof::Context::try_new(
                &model,
                &trajectory,
                &[I::point(0.16)],
                &values,
                Some(&root),
            )
            .unwrap();
            let selection = Selection {
                actions: vec![(0, vec![0, 1])],
                ..Default::default()
            };
            let result = apply_with_context_charged(
                &model,
                &trajectory,
                &selection,
                &TimeProofs::new(),
                Some(&root),
                &before,
                &after,
                &context,
            )
            .unwrap();
            let expected = crate::exact_source::binary(0.5).unwrap()
                + crate::exact_source::binary(if sample_first { 0.16 } else { 0.125 }).unwrap();
            assert_eq!(result[&0].rational(), &expected);
            // A contradictory accepted enclosure never inherits the witness.
            after[0] = I::point(0.9);
            assert!(!apply_with_context_charged(
                &model,
                &trajectory,
                &selection,
                &TimeProofs::new(),
                Some(&root),
                &before,
                &after,
                &context
            )
            .unwrap()
            .contains_key(&0));
        }
    }

    #[test]
    fn contextual_unknown_zero_weight_and_nonpoint_operands_do_not_seed_time() {
        for sample in [
            json!({"op":"affine","constant":0.,"terms":[{"node":1,"coefficient":1.}]}),
            json!({"op":"affine","constant":0.,"terms":[{"node":1,"coefficient":0.}]}),
            s(2),
        ] {
            let model = model(
                json!([assign(1, sample), assign(0, add(s(0), s(1)))]),
                false,
            );
            let trajectory = trajectory(true);
            let before = [
                I::point(0.5),
                I::ZERO,
                I { lo: -1., hi: 1. },
                I::ZERO,
                I::ONE,
            ];
            let mut after = before;
            after[0] = I { lo: 0., hi: 2. };
            after[1] = I { lo: -1., hi: 1. };
            let values = crate::event_value_proof::Proofs::new();
            let context = crate::event_value_proof::Context::try_new(
                &model,
                &trajectory,
                &[I { lo: -1., hi: 1. }],
                &values,
                None,
            )
            .unwrap();
            let selection = Selection {
                actions: vec![(0, vec![0, 1])],
                ..Default::default()
            };
            assert!(!apply_with_context_charged(
                &model,
                &trajectory,
                &selection,
                &TimeProofs::new(),
                None,
                &before,
                &after,
                &context
            )
            .unwrap()
            .contains_key(&0));
        }
    }

    #[test]
    fn contextual_bridge_delegates_original_analytic_role_without_new_time_proofs() {
        use crate::ir::EventTrigger;
        use crate::transition_source_plan::Work;
        let source_read = json!({"op":"affine","constant":0.,
            "terms":[{"node":1,"coefficient":1.}]});
        let mut program = model(
            json!([assign(1, source_read), assign(0, add(s(0), s(1)))]),
            false,
        )
        .program;
        program.events[0].trigger = EventTrigger::Timer {
            start: 0.5,
            period: 0.,
            enabled: true,
            time_tolerance: 1e-9,
        };
        let work = Work::default();
        let config: TransientInputs = serde_json::from_value(json!({
            "pwl":[[]],"output_times":[0.,1.],"stop":1.,"max_step":1.,
            "analytic_sources":[{"kind":"sine","sinedc":0.16,"ampl":0.,
                "freq":1.,"sinephase":0.,"source_name":"Vin",
                "terminals":["u","0"],"polarity":1,"parameter_origin":"explicit-v1"}]
        }))
        .unwrap();
        let trajectory = Trajectory::new_with_work(config, 1, Some(work.clone())).unwrap();
        let driven = vec!["u".into()];
        let request =
            crate::analytic_request::Request::prepare(&program, &trajectory, &driven).unwrap();
        let model = EventModel::new_with_context(
            program,
            driven,
            Tolerances::default(),
            Some(&trajectory),
            Some(request.context().clone()),
        )
        .unwrap();
        let model = request.activate(model, &trajectory).unwrap();
        assert!(matches!(
            crate::analytic_request::proof_owner(&model),
            Some(crate::analytic_request::ProofOwner::Analytic(_))
        ));
        assert!(crate::event_value_proof::history::work(&model).is_none());
        let values = crate::event_value_proof::Proofs::new();
        let root = RootTime::point(0.5).unwrap();
        let context = crate::event_value_proof::Context::try_new(
            &model,
            &trajectory,
            &[I::point(0.16)],
            &values,
            Some(&root),
        )
        .unwrap();
        let before = [I::point(0.5), I::point(0.125), I::ZERO, I::ZERO, I::ONE];
        let mut after = before;
        after[0] = I { lo: 0.5, hi: 0.75 };
        after[1] = I::point(0.16);
        let times = TimeProofs::from([(0, root.clone())]);
        let selection = Selection {
            actions: vec![(0, vec![0, 1])],
            ..Default::default()
        };
        let legacy = apply_charged(
            &model,
            &trajectory,
            &selection,
            &times,
            Some(&root),
            &before,
            &after,
        )
        .unwrap();
        assert!(
            !legacy.contains_key(&0),
            "analytic admission does not grant this time role"
        );
        let spent = work.spent();
        let actual = apply_with_context_charged(
            &model,
            &trajectory,
            &selection,
            &times,
            Some(&root),
            &before,
            &after,
            &context,
        )
        .unwrap();
        assert_eq!(actual, legacy);
        assert_eq!(
            work.spent(),
            spent,
            "delegation must not enter a new proof/copy path"
        );
        assert!(work.same_owner(request.work()));
    }

    #[test]
    fn contextual_bridge_propagates_original_history_work_exhaustion() {
        use crate::transition_source_plan::{ProofContext, Work};
        let fixture = crate::history_consumer_fixture::fixture();
        let program: Program = serde_json::from_value(fixture["program"].clone()).unwrap();
        let trajectory = Trajectory::new(
            serde_json::from_value(fixture["transient"].clone()).unwrap(),
            1,
        )
        .unwrap();
        let driven = vec!["temp".into()];
        let work = Work::limited([128, 8192, 1_000_000]);
        let owner =
            ProofContext::event_request_with_work(&program, &trajectory, &driven, 0, work.clone())
                .unwrap();
        let model = EventModel::new_with_context(
            program,
            driven,
            Tolerances::default(),
            Some(&trajectory),
            Some(owner.clone()),
        )
        .unwrap();
        assert!(work.same_owner(crate::event_value_proof::history::work(&model).unwrap()));
        let values = crate::event_value_proof::Proofs::new();
        // The bridge must delegate on the model's paid history role, even
        // with an ordinary Context. No replacement ledger or optional failure.
        let context = crate::event_value_proof::Context::new(
            &model,
            &trajectory,
            &[I::point(0.5)],
            &values,
            None,
        );
        let bounds = [I::ZERO, I::point(0.25)];
        let times = TimeProofs::from([(1, RootTime::point(0.25).unwrap())]);
        loop {
            match apply_with_context_charged(
                &model,
                &trajectory,
                &Selection::default(),
                &times,
                None,
                &bounds,
                &bounds,
                &context,
            ) {
                Ok(_) => (),
                Err(error) => {
                    assert_eq!(error.kind, "step_budget");
                    break;
                }
            }
        }
        let mut spent = work.spent();
        for _ in 0..2 {
            assert_eq!(
                apply_with_context_charged(
                    &model,
                    &trajectory,
                    &Selection::default(),
                    &times,
                    None,
                    &bounds,
                    &bounds,
                    &context
                )
                .unwrap_err()
                .kind,
                "step_budget"
            );
            assert!(work.same_owner(owner.borrow_work()));
            assert!(work.spent() >= spent);
            spent = work.spent();
        }
    }

    #[test]
    fn exact_nonbinary_scalar_offset_preserves_time_and_original_bounds() {
        let selection = Selection {
            actions: vec![(0, vec![0])],
            ..Default::default()
        };
        let model = model(
            json!([assign(
                0,
                add(s(0), json!({"op":"divide","left":c(0.5),"right":s(1)}))
            )]),
            false,
        );
        let trajectory = trajectory(true);
        let before = [I::point(0.1), I::point(3.), I::ZERO, I::ZERO, I::ONE];
        let exact = crate::exact_source::binary(0.1).unwrap()
            + num_rational::BigRational::new(1.into(), 6.into());
        let mut after = before;
        after[0] = crate::exact_source::enclosure(&exact).unwrap();
        assert_ne!(after[0].lo, after[0].hi);
        let proof = apply(
            &model,
            &trajectory,
            &selection,
            &TimeProofs::new(),
            None,
            &before,
            &after,
        );
        assert_eq!(proof[&0].rational(), &exact);
        // Optional exact arithmetic cannot replace contradictory accepted bounds.
        after[0] = I::point(0.9);
        assert!(!apply(
            &model,
            &trajectory,
            &selection,
            &TimeProofs::new(),
            None,
            &before,
            &after
        )
        .contains_key(&0));
    }

    #[test]
    fn nonpoint_and_hidden_unknown_offsets_never_become_time_certificates() {
        let selection = Selection {
            actions: vec![(0, vec![0])],
            ..Default::default()
        };
        let trajectory = trajectory(true);
        for offset in [
            s(1),
            json!({"op":"multiply","left":c(0.),"right":s(2)}),
            json!({"op":"divide","left":c(0.5),"right":s(1)}),
        ] {
            let model = model(json!([assign(0, add(s(0), offset))]), false);
            let before = [
                I::point(0.1),
                I { lo: 0.1, hi: 0.2 },
                I { lo: -1., hi: 1. },
                I::ZERO,
                I::ONE,
            ];
            let after = [I { lo: 0., hi: 1. }; 5];
            assert!(!apply(
                &model,
                &trajectory,
                &selection,
                &TimeProofs::new(),
                None,
                &before,
                &after
            )
            .contains_key(&0));
        }
        let mut before = [I::point(0.1); 5];
        before[0] = I { lo: 0.1, hi: 0.2 };
        let uncertain_start = model(json!([assign(0, add(s(0), c(0.1)))]), false);
        let after = [I { lo: 0., hi: 1. }; 5];
        assert!(!apply(
            &uncertain_start,
            &trajectory,
            &selection,
            &TimeProofs::new(),
            None,
            &before,
            &after
        )
        .contains_key(&0));

        before[0] = I::point(0.1);
        let overwritten = model(
            json!([
                assign(
                    1,
                    json!({"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]})
                ),
                assign(0, add(s(0), s(1)))
            ]),
            false,
        );
        let both = Selection {
            actions: vec![(0, vec![0, 1])],
            ..Default::default()
        };
        assert!(!apply(
            &overwritten,
            &trajectory,
            &both,
            &TimeProofs::new(),
            None,
            &before,
            &after
        )
        .contains_key(&0));
    }
    #[test]
    fn failed_held_point_candidate_retries_same_controller_with_future_history_and_error() {
        held_offset_failure_retry(false);
    }
    #[test]
    fn failed_nonbinary_offset_candidate_retries_same_controller_without_leaks() {
        held_offset_failure_retry(true);
    }
    fn held_offset_failure_retry(nonbinary: bool) {
        use crate::transient::{event_acceptance, Controller, Frame};
        let offset = if nonbinary {
            json!({"op":"divide","left":c(0.5),"right":s(1)})
        } else {
            s(1)
        };
        let body = json!([assign(0,add(s(0),offset)),{"kind":"if","relation":"gt",
            "left":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]},
            "right":c(0.),"then_body":[assign(3,s(2))],"else_body":[assign(3,c(0.))],"origin":origin()}]);
        let model = model(body, true);
        let good = trajectory(true);
        let bad = trajectory(false);
        let mut states = vec![0.5, if nonbinary { 3. } else { 0.1 }, 0.45 * 0.16, 0., 1.];
        let mut bounds = states.iter().copied().map(I::point).collect::<Vec<_>>();
        bounds[2] = I::point(0.45) * I::point(0.16);
        assert!(bounds[2].lo < bounds[2].hi);
        let mut operators =
            crate::operators::Operators::new(&model.program, &good, &model.driven, &states)
                .unwrap();
        states[4] = 0.;
        bounds[4] = I::ZERO;
        operators
            .advance(0.25, I::point(0.25), &states, &bounds, &[4])
            .unwrap();
        assert_eq!(operators.values(0.5).unwrap(), vec![0.5]);
        let circuit = model
            .circuit_with(&states, &operators.values(0.25).unwrap())
            .unwrap();
        let solution = circuit.solve(&good.values(0.25)).unwrap();
        let frame = Frame {
            time: 0.25,
            states,
            state_bounds: bounds,
            operators,
            circuit,
            solution,
            time_proofs: Default::default(),
            value_proofs: Default::default(),
        };
        let mut calendar =
            crate::schedule::schedule_held(&model, &good, &frame.state_bounds).unwrap();
        let mut controller = Controller {
            accepted: frame.clone(),
            event: 0,
            records: vec![],
            outputs: vec![],
        };
        let saved_calendar = calendar.clone();
        let signatures = |events: &[crate::schedule::ScheduledEvent]| {
            events
                .iter()
                .map(|e| {
                    (
                        e.event,
                        e.time.to_bits(),
                        e.bounds().lo.to_bits(),
                        e.bounds().hi.to_bits(),
                    )
                })
                .collect::<Vec<_>>()
        };
        let same = |a: &Frame, b: &Frame| {
            assert_eq!(a.time, b.time);
            assert_eq!(a.states, b.states);
            assert_eq!(a.state_bounds, b.state_bounds);
            assert_eq!(a.time_proofs, b.time_proofs);
            assert_eq!(a.value_proofs, b.value_proofs);
            assert_eq!(a.solution.voltages, b.solution.voltages);
            assert!(a.operators.same_reset_history(&b.operators));
            assert_eq!(
                a.operators.values(0.5).unwrap(),
                b.operators.values(0.5).unwrap()
            );
            assert_eq!(
                a.operators.values(1.).unwrap(),
                b.operators.values(1.).unwrap()
            );
        };
        for _ in 0..2 {
            let error = controller
                .accept_changed_events(
                    &model,
                    &bad,
                    &mut calendar,
                    event_acceptance::Strategy::Static,
                )
                .unwrap_err();
            assert_eq!(error.kind, "waveform_accuracy");
            assert!(error.message.contains("forward error"));
            same(&controller.accepted, &frame);
            assert_eq!(controller.event, 0);
            assert!(controller.records.is_empty());
            assert!(controller.outputs.is_empty());
            assert_eq!(signatures(&calendar), signatures(&saved_calendar));
        }
        controller
            .accept_changed_events(
                &model,
                &good,
                &mut calendar,
                event_acceptance::Strategy::Static,
            )
            .unwrap();
        let mut clean = Controller {
            accepted: frame,
            event: 0,
            records: vec![],
            outputs: vec![],
        };
        let mut clean_calendar = saved_calendar;
        clean
            .accept_changed_events(
                &model,
                &good,
                &mut clean_calendar,
                event_acceptance::Strategy::Static,
            )
            .unwrap();
        same(&controller.accepted, &clean.accepted);
        assert_eq!(
            serde_json::to_value(&controller.records).unwrap(),
            serde_json::to_value(&clean.records).unwrap()
        );
        assert_eq!(signatures(&calendar), signatures(&clean_calendar));
        assert_eq!(
            controller.accepted.operators.values(0.5).unwrap(),
            vec![0.5]
        );
        assert_eq!(controller.accepted.operators.values(1.).unwrap(), vec![0.]);
        assert!(controller.accepted.state_bounds[2].lo < controller.accepted.state_bounds[2].hi);
        assert!(controller.accepted.time_proofs.contains_key(&0));
    }
}
