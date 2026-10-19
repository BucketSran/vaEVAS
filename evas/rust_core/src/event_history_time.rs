//! Paid mathematical time provenance only for the original history owner.
use super::*;
use crate::event_value_proof::history as values;
use crate::exact_source::history_paid::{root as root_time, Paid};
use crate::{ir::Error, transition_source_plan::Work};
use num_rational::BigRational as R;
pub(super) fn copy_map(source: &TimeProofs, w: &Work) -> Result<TimeProofs, Error> {
    w.debit(2, 0)?;
    let mut out = TimeProofs::new();
    for (&state, root) in source {
        w.step()?;
        let root = root.clone_with_work(w)?;
        values::insert(&mut out, state, root, w)?;
    }
    Ok(out)
}
pub(super) fn equal(a: &TimeProofs, b: &TimeProofs, w: &Work) -> Result<bool, Error> {
    w.debit(2, 0)?;
    w.step()?;
    if a.len() != b.len() {
        return Ok(false);
    }
    for ((ka, va), (kb, vb)) in a.iter().zip(b) {
        w.step()?;
        if ka != kb || !values::same_rat(va.rational(), vb.rational(), w)? {
            return Ok(false);
        }
    }
    Ok(true)
}
fn identity(
    model: &EventModel,
    trajectory: &Trajectory,
    w: &Work,
) -> Result<BTreeSet<usize>, Error> {
    let mut out = BTreeSet::new();
    let nodes = values::input_nodes(model).ok_or_else(|| {
        Error::new(
            "invalid_ir",
            "missing qualified original time input mapping",
        )
    })?;
    for (index, &node) in nodes.iter().enumerate() {
        w.step()?;
        if trajectory.original_identity_history(index, w)? {
            values::map_edit::<()>(out.len(), w)?;
            out.insert(node);
        }
    }
    Ok(out)
}
fn offset(
    e: &Expression,
    points: &crate::event_value_proof::LocalState,
    p: &mut Paid<'_>,
) -> Option<f64> {
    p.pay(1)?;
    if let Some(v) = literal(e) {
        return Some(v);
    }
    let value = p.accept(points.try_value(e, &[]))??;
    let bounds = p.enclose(&value)?;
    (bounds.lo == bounds.hi).then_some(bounds.lo)
}
fn shift(value: R, offset: f64, p: &mut Paid<'_>) -> Option<R> {
    let discovery = p.enclose(&value)? + I::point(offset);
    let offset = p.binary(offset)?;
    let sum = p.op(&value, &offset, '+')?;
    let lo = p.binary(discovery.lo)?;
    let hi = p.binary(discovery.hi)?;
    if p.cmp(&lo, &sum)?.is_gt() || p.cmp(&sum, &hi)?.is_gt() {
        None
    } else {
        Some(sum)
    }
}
fn expression(
    e: &Expression,
    states: &TimeProofs,
    root: Option<&RootTime>,
    identity: &BTreeSet<usize>,
    points: &crate::event_value_proof::LocalState,
    p: &mut Paid<'_>,
    w: &Work,
) -> Option<R> {
    p.pay(1)?;
    match e {
        Expression::State { state } => {
            let value = p.accept(values::lookup(states, *state, w))??;
            p.copy(value.rational())
        }
        Expression::Affine { constant, terms } => {
            let mut count = 0;
            let mut valid = true;
            for term in terms {
                p.pay(1)?;
                if term.node == 0 {
                    continue;
                }
                count += 1;
                let mut found = false;
                for node in identity {
                    p.pay(1)?;
                    if *node == term.node {
                        found = true;
                        break;
                    }
                    if *node > term.node {
                        break;
                    }
                }
                valid &= term.coefficient == 1. && found;
            }
            if count != 1 || !valid {
                return None;
            }
            let copied = p.copy(root?.rational())?;
            shift(copied, *constant, p)
        }
        Expression::Add { left, right } => {
            if let Some(time) = expression(left, states, root, identity, points, p, w) {
                if let Some(off) = offset(right, points, p) {
                    return shift(time, off, p);
                }
            }
            let time = expression(right, states, root, identity, points, p, w)?;
            let off = offset(left, points, p)?;
            shift(time, off, p)
        }
        Expression::EventMath { function, args, .. }
            if args.len() == 2
                && matches!(function, EventMathFunction::Min | EventMathFunction::Max) =>
        {
            let a = expression(&args[0], states, root, identity, points, p, w)
                .or_else(|| p.binary(literal(&args[0])?))?;
            let b = expression(&args[1], states, root, identity, points, p, w)
                .or_else(|| p.binary(literal(&args[1])?))?;
            let order = p.cmp(&a, &b)?;
            let first = if matches!(function, EventMathFunction::Min) {
                !order.is_gt()
            } else {
                !order.is_lt()
            };
            Some(if first { a } else { b })
        }
        _ => None,
    }
}
#[allow(clippy::too_many_arguments)]
pub(super) fn apply(
    model: &EventModel,
    trajectory: &Trajectory,
    selection: &Selection,
    before: &TimeProofs,
    root: Option<&RootTime>,
    before_bounds: &[I],
    after_bounds: &[I],
    w: &Work,
) -> Result<TimeProofs, Error> {
    w.debit(2, 0)?;
    let mut valid = TimeProofs::new();
    for (&state, time) in before {
        w.step()?;
        if let Some(b) = before_bounds.get(state) {
            if time.refine_with_work(*b, w)?.is_some() {
                let copy = time.clone_with_work(w)?;
                values::insert(&mut valid, state, copy, w)?
            }
        }
    }
    // HeldTimer seeding is unreachable in this qualified route: EventModel's
    // original history gate accepts only independent Cross/Timer leaves.
    let mut result = copy_map(&valid, w)?;
    let identity = if root.is_some() && !selection.actions.is_empty() {
        identity(model, trajectory, w)?
    } else {
        BTreeSet::new()
    };
    crate::diagnostics::counter("time_proof_root_calls", usize::from(root.is_some()));
    for (event, indices) in &selection.actions {
        w.step()?;
        let mut local = copy_map(&valid, w)?;
        let mut points = values::points(before_bounds, w)?;
        for &index in indices {
            w.step()?;
            let (state, e) = values::assignment(model, *event, index, w)?;
            let mut p = Paid::new(w);
            let value = expression(e, &local, root, &identity, &points, &mut p, w).or_else(|| {
                if p.accept(values::lookup(&local, state, w))?.is_some() {
                    p.binary(literal(e)?)
                } else {
                    None
                }
            });
            let proof = p.finish(value)?.map(root_time);
            values::assign_point(&mut points, state, e, w)?;
            values::remove(&mut local, state, w)?;
            values::remove(&mut result, state, w)?;
            w.step()?;
            if let Some(proof) =
                proof.filter(|_| matches!(model.program.states[state].kind, StateKind::Real))
            {
                let copy = proof.clone_with_work(w)?;
                values::insert(&mut local, state, copy, w)?;
                values::insert(&mut result, state, proof, w)?;
            }
        }
    }
    let mut checked = TimeProofs::new();
    for (state, proof) in result {
        w.step()?;
        if let Some(b) = after_bounds.get(state) {
            if proof.refine_with_work(*b, w)?.is_some() {
                values::insert(&mut checked, state, proof, w)?
            }
        }
    }
    crate::diagnostics::counter("time_proof_result_slots", checked.len());
    Ok(checked)
}
