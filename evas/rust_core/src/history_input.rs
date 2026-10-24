//! Source-position operator inputs and exact cuts of monotone RN guards.
//! Current graphs describe one epoch. Every guard cut re-executes the original
//! procedure; structural admission continues to inspect all original arms.
use crate::exact_source::{history_paid::Paid, RootTime};
use crate::interval::Interval as I;
use crate::ir::{Error, Expression as E, Relation as Rel};
use crate::transition_source_plan::{ProofContext, Work};
use num_rational::BigRational as R;
use num_traits::Zero;
use std::sync::Arc;
fn unsupported() -> Error {
    Error::new("unsupported_history_input", "history input requires certified source/held arithmetic and monotone affine RN guard preimages")
}
fn required<T>(value: Option<T>) -> Result<T, Error> {
    value.ok_or_else(unsupported)
}
fn rational<T>(w: &Work, f: impl FnOnce(&mut Paid<'_>) -> Option<T>) -> Result<T, Error> {
    let mut paid = Paid::new(w);
    let result = f(&mut paid);
    required(paid.finish(result)?)
}
pub(crate) fn activate(
    context: &ProofContext,
    states: &[I],
    root: &RootTime,
) -> Result<Arc<crate::procedure::Plan>, Error> {
    let (p, t, _) = context.original_binding();
    let w = context.borrow_work();
    w.debit(2, (p.nodes.len() * 64 + 64) as u64)?;
    let mut bands = vec![None; p.nodes.len()];
    let mut nodes = vec![
        I {
            lo: f64::NEG_INFINITY,
            hi: f64::INFINITY
        };
        p.nodes.len()
    ];
    nodes[0] = I::ZERO;
    for (&node, index) in context.event_input_nodes().iter().zip(0..) {
        w.step()?;
        let band = match t.sample_domain_at_root(index, root, w)? {
            Some(band) => band,
            None => {
                let curve = required(t.exact_sources.get(index).and_then(Option::as_ref))?;
                let value = required(curve.at_root_history(root, w)?)?;
                required(crate::source_domain::Domain::point(&value, w)?)?
            }
        };
        nodes[node] = required(band.native_enclosure(w)?)?;
        bands[node] = Some(band);
    }
    let proofs = crate::event_value_proof::Proofs::new();
    let proof =
        crate::event_value_proof::Context::history_inputs(&proofs, p.nodes.len(), bands, w)?;
    let plan = crate::procedure::execute(p, &[], &nodes, states, Some(&proof), w)?;
    w.debit(2, (std::mem::size_of_val(&plan) + 32) as u64)?;
    Ok(Arc::new(plan))
}
fn line(e: &E, context: &ProofContext, segment: I) -> Result<Option<(R, R)>, Error> {
    let (_, t, _) = context.original_binding();
    let w = context.borrow_work();
    w.step()?;
    match e {
        E::Affine { .. } => match crate::exact_source::Curve::expression_history(
            e,
            context.event_input_nodes(),
            &t.exact_sources,
            t.config.stop,
            &crate::exact_source::TimeProofs::new(),
            w,
        )? {
            Some(curve) => curve.affine_history(segment, w),
            None => Ok(None),
        },
        _ => Ok(None),
    }
}
fn constant(e: &E, context: &ProofContext, states: &[I], segment: I) -> Result<Option<R>, Error> {
    let w = context.borrow_work();
    w.step()?;
    Ok(match e {
        E::Affine { constant, terms } if terms.is_empty() => {
            Some(rational(w, |p| p.binary(*constant))?)
        }
        E::Affine { .. } => match line(e, context, segment)? {
            Some((a, b)) if b.is_zero() => Some(a),
            _ => None,
        },
        E::State { state } => match states.get(*state) {
            Some(b) if b.lo.to_bits() == b.hi.to_bits() => Some(rational(w, |p| p.binary(b.lo))?),
            _ => None,
        },
        E::RealBoundary { value, .. } => constant(value, context, states, segment)?
            .map(|v| round(&v, w))
            .transpose()?
            .map(|v| rational(w, |p| p.binary(v)))
            .transpose()?,
        E::Add { left, right }
        | E::Multiply { left, right }
        | E::Divide { left, right }
        | E::RealBinary { left, right, .. } => {
            match (
                constant(left, context, states, segment)?,
                constant(right, context, states, segment)?,
            ) {
                (Some(a), Some(b)) => Some(if let E::RealBinary { operation, .. } = e {
                    let a = round(&a, w)?;
                    let b = round(&b, w)?;
                    let value = crate::real_expression::point(*operation, a, b)?;
                    rational(w, |p| p.binary(value))?
                } else {
                    rational(w, |p| {
                        p.op(
                            &a,
                            &b,
                            match e {
                                E::Add { .. } => '+',
                                E::Multiply { .. } => '*',
                                _ => '/',
                            },
                        )
                    })?
                }),
                _ => None,
            }
        }
        _ => None,
    })
}
fn round(value: &R, w: &Work) -> Result<f64, Error> {
    crate::real_rounding::round_ratio(value, false, &mut |n| w.debit(2, n)).map_err(|e| match e {
        crate::real_rounding::Fault::Quota(e) => e,
        other => crate::real_expression::fault(other),
    })
}
fn flip(r: Rel) -> Rel {
    match r {
        Rel::Lt => Rel::Gt,
        Rel::Le => Rel::Ge,
        Rel::Gt => Rel::Lt,
        Rel::Ge => Rel::Le,
    }
}
/// Exact preimage of RN(x) relation b, including midpoint tie ownership.
fn unround(relation: Rel, b: &R, w: &Work) -> Result<(Rel, R), Error> {
    let inclusive = matches!(relation, Rel::Le | Rel::Gt);
    let mut lower = round(b, w)?;
    let order = rational(w, |p| {
        let a = p.binary(lower)?;
        p.cmp(&a, b)
    })?;
    if order.is_gt() || order.is_eq() && !inclusive {
        lower = lower.next_down();
    }
    let upper = lower.next_up();
    if !lower.is_finite() || !upper.is_finite() {
        return Err(unsupported());
    }
    let mid = rational(w, |p| {
        let a = p.binary(lower)?;
        let b = p.binary(upper)?;
        let sum = p.op(&a, &b, '+')?;
        let two = p.binary(2.)?;
        p.op(&sum, &two, '/')
    })?;
    let rel = if lower.to_bits() & 1 == 0 {
        Rel::Le
    } else {
        Rel::Lt
    };
    Ok((
        if matches!(relation, Rel::Gt | Rel::Ge) {
            match rel {
                Rel::Le => Rel::Gt,
                _ => Rel::Ge,
            }
        } else {
            rel
        },
        mid,
    ))
}
fn binary_value(e: &E) -> bool {
    match e {
        E::RealBinary { .. } | E::RealBoundary { .. } | E::State { .. } => true,
        E::Affine { terms, .. } => terms.is_empty(),
        _ => false,
    }
}
fn pull(
    e: &E,
    relation: Rel,
    b: &R,
    context: &ProofContext,
    states: &[I],
    segment: I,
) -> Result<Option<RootTime>, Error> {
    let w = context.borrow_work();
    w.step()?;
    if constant(e, context, states, segment)?.is_some() {
        return Ok(None);
    }
    match e {
        E::RealBoundary { value, .. } => {
            if binary_value(value) {
                return pull(value, relation, b, context, states, segment);
            }
            let (rel, cut) = unround(relation, b, w)?;
            pull(value, rel, &cut, context, states, segment)
        }
        E::Affine { .. } => {
            let (a, slope) = required(line(e, context, segment)?)?;
            if slope.is_zero() {
                return Ok(None);
            }
            let root = rational(w, |p| {
                let delta = p.op(b, &a, '-')?;
                p.op(&delta, &slope, '/')
            })?;
            w.debit(2, 64)?;
            Ok(Some(RootTime::raw(root)))
        }
        E::Add { left, right }
        | E::Multiply { left, right }
        | E::Divide { left, right }
        | E::RealBinary { left, right, .. } => {
            let real = matches!(e, E::RealBinary { .. });
            // Binary64 ingress operands are multiples of the least subnormal.
            // Finite Add/Sub cannot turn a nonzero exact result into zero.
            // This comparison proof never changes stored values or their sign.
            let exact_zero = real
                && b.is_zero()
                && matches!(
                    e,
                    E::RealBinary {
                        operation: crate::ir::RealOperation::Add
                            | crate::ir::RealOperation::Subtract,
                        ..
                    }
                );
            if exact_zero {
                crate::diagnostics::counter("history_input_zero_comparison", 1);
            }
            let (mut rel, mut cut) = if real && !exact_zero {
                unround(relation, b, w)?
            } else {
                (relation, rational(w, |p| p.copy(b))?)
            };
            let a = constant(left, context, states, segment)?;
            let c = constant(right, context, states, segment)?;
            let (variable, fixed, is_left) = match (a, c) {
                (None, Some(v)) => (left, v, true),
                (Some(v), None) => (right, v, false),
                _ => return Err(unsupported()),
            };
            let fixed = if real {
                let v = round(&fixed, w)?;
                rational(w, |p| p.binary(v))?
            } else {
                fixed
            };
            let operation = match e {
                E::Add { .. } => crate::ir::RealOperation::Add,
                E::Multiply { .. } => crate::ir::RealOperation::Multiply,
                E::Divide { .. } => crate::ir::RealOperation::Divide,
                E::RealBinary { operation, .. } => *operation,
                _ => unreachable!(),
            };
            use crate::ir::RealOperation as Op;
            cut = match operation {
                Op::Add => rational(w, |p| p.op(&cut, &fixed, '-'))?,
                Op::Subtract if is_left => rational(w, |p| p.op(&cut, &fixed, '+'))?,
                Op::Subtract => {
                    rel = flip(rel);
                    rational(w, |p| p.op(&fixed, &cut, '-'))?
                }
                Op::Multiply | Op::Divide
                    if !fixed.is_zero() && (is_left || operation == Op::Multiply) =>
                {
                    if rational(w, |p| {
                        let zero = p.binary(0.)?;
                        p.cmp(&fixed, &zero)
                    })?
                    .is_lt()
                    {
                        rel = flip(rel);
                    }
                    rational(w, |p| {
                        p.op(
                            &cut,
                            &fixed,
                            if operation == Op::Multiply { '/' } else { '*' },
                        )
                    })?
                }
                _ => return Err(unsupported()),
            };
            if real && !binary_value(variable) {
                let (r, c) = unround(rel, &cut, w)?;
                rel = r;
                cut = c;
            }
            pull(variable, rel, &cut, context, states, segment)
        }
        _ => Err(unsupported()),
    }
}
fn guard_ranges(
    plan: &crate::procedure::Plan,
    context: &ProofContext,
    states: &[I],
    segment: I,
) -> Result<Vec<I>, Error> {
    let (p, t, _) = context.original_binding();
    let w = context.borrow_work();
    w.debit(
        2,
        (p.nodes.len() * 64 + plan.guards.len() * 32 + 128) as u64,
    )?;
    let mut bands = vec![None; p.nodes.len()];
    let mut nodes = vec![
        I {
            lo: f64::NEG_INFINITY,
            hi: f64::INFINITY
        };
        p.nodes.len()
    ];
    nodes[0] = I::ZERO;
    for (index, &node) in context.event_input_nodes().iter().enumerate() {
        let curve = required(t.exact_sources.get(index).and_then(Option::as_ref))?;
        let (a, b) = required(curve.affine_history(segment, w)?)?;
        let (lo, hi) = rational(w, |p| {
            let t0 = p.binary(segment.lo)?;
            let t1 = p.binary(segment.hi)?;
            let x = p.op(&b, &t0, '*')?;
            let x = p.op(&a, &x, '+')?;
            let y = p.op(&b, &t1, '*')?;
            let y = p.op(&a, &y, '+')?;
            Some(if p.cmp(&x, &y)?.is_gt() {
                (y, x)
            } else {
                (x, y)
            })
        })?;
        let band = required(crate::source_domain::Domain::rational_bounds(lo, hi, w)?)?;
        nodes[node] = required(band.native_enclosure(w)?)?;
        bands[node] = Some(band);
    }
    let proofs = crate::event_value_proof::Proofs::new();
    let proof =
        crate::event_value_proof::Context::history_inputs(&proofs, p.nodes.len(), bands, w)?;
    let roots = plan
        .guards
        .iter()
        .flat_map(|g| [g.left, g.right])
        .collect::<Vec<_>>();
    plan.history_ranges(&roots, &nodes, states, &proof, w)
}
pub(crate) fn guard_roots(
    plan: &crate::procedure::Plan,
    context: &ProofContext,
    states: &[I],
    segment: I,
) -> Result<Vec<RootTime>, Error> {
    let w = context.borrow_work();
    w.debit(2, (plan.guards.len() * 64 + 64) as u64)?;
    let ranges = guard_ranges(plan, context, states, segment)?;
    let mut roots = Vec::new();
    for (index, guard) in plan.guards.iter().enumerate() {
        let (yes, no) =
            crate::event_numeric::sign(guard.relation, ranges[index * 2] - ranges[index * 2 + 1]);
        if yes || no {
            continue;
        }
        w.step()?;
        let left = plan.history_expression(guard.left, w)?;
        let right = plan.history_expression(guard.right, w)?;
        let a = constant(&left, context, states, segment)?;
        let b = constant(&right, context, states, segment)?;
        let root = match (a, b) {
            (Some(_), Some(_)) => None,
            (None, Some(b)) => pull(&left, guard.relation, &b, context, states, segment)?,
            (Some(a), None) => pull(&right, flip(guard.relation), &a, context, states, segment)?,
            _ => return Err(unsupported()),
        };
        if let Some(root) = root {
            roots.push(root);
        }
    }
    Ok(roots)
}
fn between(a: &RootTime, b: &RootTime, w: &Work) -> Result<RootTime, Error> {
    let value = rational(w, |p| {
        let sum = p.op(a.rational(), b.rational(), '+')?;
        let two = p.binary(2.)?;
        p.op(&sum, &two, '/')
    })?;
    w.debit(2, 64)?;
    Ok(RootTime::raw(value))
}
pub(crate) fn partition(context: &ProofContext, states: &[I]) -> Result<Vec<RootTime>, Error> {
    let (_, t, _) = context.original_binding();
    let w = context.borrow_work();
    // Shaped and uncertain source guards require a separate preimage proof.
    if t.has_source_uncertainty() {
        return Err(unsupported());
    }
    w.debit(2, (t.knots.len() * 64 + 64) as u64)?;
    let mut cuts = vec![required(RootTime::point(0.))?];
    w.debit(1, 1)?;
    for pair in t.knots.windows(2) {
        if pair[0] >= t.config.stop {
            break;
        }
        let segment = I {
            lo: pair[0],
            hi: pair[1].min(t.config.stop),
        };
        let end = required(RootTime::point(segment.hi))?;
        let mut cursor = required(RootTime::point(segment.lo))?;
        while cursor.order_with_work(&end, w)?.is_lt() {
            let mut probe = between(&cursor, &end, w)?;
            let next = loop {
                let plan = activate(context, states, &probe)?;
                let roots = guard_roots(&plan, context, states, segment)?;
                w.debit(2, end.copy_items() as u64)?;
                let mut next = end.clone();
                for root in roots {
                    if root.order_with_work(&cursor, w)?.is_gt()
                        && root.order_with_work(&next, w)?.is_lt()
                    {
                        next = root;
                    }
                }
                if !next.order_with_work(&probe, w)?.is_gt() {
                    probe = between(&cursor, &next, w)?;
                } else {
                    break next;
                }
            };
            w.debit(1, 1)?;
            w.debit(2, (next.copy_items() + 64) as u64)?;
            cursor = next.clone();
            cuts.push(next);
        }
    }
    Ok(cuts)
}
pub(crate) fn held_value(
    plan: &crate::procedure::Plan,
    operator: usize,
    context: &ProofContext,
    states: &[I],
) -> Result<crate::procedure_operations::Cell, Error> {
    let w = context.borrow_work();
    let (_, t, _) = context.original_binding();
    let expression = plan.input_expression(operator, w)?;
    if constant(
        &expression,
        context,
        states,
        I {
            lo: 0.,
            hi: t.config.stop,
        },
    )?
    .is_none()
    {
        return Err(unsupported());
    }
    plan.input_cell(operator, w)
}

pub(crate) fn required_frame(e: &E, w: &Work) -> Result<bool, Error> {
    w.step()?;
    if matches!(
        e,
        E::RealLocal { .. } | E::RealBinary { .. } | E::RealBoundary { .. } | E::RealCall { .. }
    ) {
        return Ok(true);
    }
    let mut found = false;
    crate::procedure::call_children(e, &mut |child| {
        found |= required_frame(child, w)?;
        Ok(())
    })?;
    Ok(found)
}
