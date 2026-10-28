//! The right limit tau+ of cross-fired source-order event bodies.
//!
//! LRM 2.4 5.10.3.1: a cross event occurs after the threshold crossing. A
//! body fired only by cross leaves observes the post-crossing side of a
//! comparison whose difference is exactly zero at the root (events.md
//! #cross-right-limit). In order: a fired guard with the same exact zero set
//! gives sign(k)*s; a stateless input-only difference takes its derivative
//! sign over [lo, next_up(hi)]; a difference whose reads do not move over the
//! right window W keeps the tie; a W enclosure may decide the comparison.
//! Source rounding does not decide the side: the zero-set and derivative
//! certificates read through RN boundaries. Without a certificate the
//! comparison is refused; only identical arms may continue.
use super::*;
use crate::exact_source::history_paid::Paid;
use num_rational::BigRational as R;
use num_traits::{Signed, Zero};
use std::collections::BTreeMap;

pub(super) enum Outcome {
    // Decision and whether a post-root certificate decided it.
    Decided(bool, bool),
    // Exactly zero at tau without a one-sided or right-window certificate.
    Unsided(Error),
    // The enclosure does not decide and no fired guard certifies a side.
    Undecided,
}

fn whole() -> I {
    I {
        lo: f64::NEG_INFINITY,
        hi: f64::INFINITY,
    }
}

/// Budget, resource and IR failures are reported as such, never as a missing
/// certificate (the same split as the batch-level right window).
fn certificate_gap(error: &Error) -> bool {
    !matches!(
        error.kind,
        "step_budget"
            | "resource_budget"
            | "event_budget"
            | "event_loop_budget"
            | "forcing_entry_budget"
            | "invalid_ir"
            | "invalid_inputs"
    )
}

/// The difference of two procedure values is exactly zero at the root: equal
/// point enclosures, or equal exact values when the enclosures meet zero.
pub(super) fn tie(a: &Cell, b: &Cell, w: &Work) -> Result<bool, Error> {
    let d = a.bound()? - b.bound()?;
    if d.zero() {
        return Ok(true);
    }
    if d.lo > 0. || d.hi < 0. {
        return Ok(false);
    }
    let Some((x, y)) = a.proof.as_ref().zip(b.proof.as_ref()) else {
        return Ok(false);
    };
    let mut p = Paid::new(w);
    let order = p.cmp(x, y);
    Ok(p.finish(order)?.is_some_and(|o| o.is_eq()))
}

/// Exact first-order form in driven nodes and accepted states.
#[derive(Clone)]
struct Linear {
    constant: R,
    nodes: BTreeMap<usize, R>,
    states: BTreeMap<usize, R>,
}
impl Linear {
    fn constant(value: R) -> Self {
        Self {
            constant: value,
            nodes: BTreeMap::new(),
            states: BTreeMap::new(),
        }
    }
    fn is_constant(&self) -> bool {
        self.nodes.is_empty() && self.states.is_empty()
    }
}
fn combine(a: &Linear, b: &Linear, op: char, p: &mut Paid) -> Option<Linear> {
    fn merge(
        a: &BTreeMap<usize, R>,
        b: &BTreeMap<usize, R>,
        op: char,
        p: &mut Paid,
    ) -> Option<BTreeMap<usize, R>> {
        let mut out = BTreeMap::new();
        for (&key, value) in a {
            p.pay(2)?;
            out.insert(key, p.copy(value)?);
        }
        for (&key, value) in b {
            p.pay(2)?;
            let next = match out.get(&key) {
                Some(old) => p.op(old, value, op)?,
                None if op == '-' => p.negated(value)?,
                None => p.copy(value)?,
            };
            if next.is_zero() {
                out.remove(&key);
            } else {
                out.insert(key, next);
            }
        }
        Some(out)
    }
    Some(Linear {
        constant: p.op(&a.constant, &b.constant, op)?,
        nodes: merge(&a.nodes, &b.nodes, op, p)?,
        states: merge(&a.states, &b.states, op, p)?,
    })
}
fn scale(a: &Linear, k: &R, p: &mut Paid) -> Option<Linear> {
    let map = |m: &BTreeMap<usize, R>, p: &mut Paid| -> Option<BTreeMap<usize, R>> {
        let mut out = BTreeMap::new();
        for (&key, value) in m {
            p.pay(2)?;
            let next = p.op(value, k, '*')?;
            if !next.is_zero() {
                out.insert(key, next);
            }
        }
        Some(out)
    };
    Some(Linear {
        constant: p.op(&a.constant, k, '*')?,
        nodes: map(&a.nodes, p)?,
        states: map(&a.states, p)?,
    })
}

/// Linear form of an IR guard expression, rounding read through.
fn expression_linear(e: &E, p: &mut Paid) -> Option<Linear> {
    p.pay(1)?;
    match e {
        E::Affine { constant, terms } => {
            let mut out = Linear::constant(p.binary(*constant)?);
            for t in terms {
                p.pay(2)?;
                if t.node == 0 || t.coefficient == 0. {
                    continue;
                }
                let c = p.binary(t.coefficient)?;
                let next = match out.nodes.get(&t.node) {
                    Some(old) => p.op(old, &c, '+')?,
                    None => c,
                };
                if next.is_zero() {
                    out.nodes.remove(&t.node);
                } else {
                    out.nodes.insert(t.node, next);
                }
            }
            Some(out)
        }
        E::State { state } => {
            let mut out = Linear::constant(R::zero());
            out.states.insert(*state, p.binary(1.)?);
            Some(out)
        }
        E::Add { left, right } => {
            let a = expression_linear(left, p)?;
            let b = expression_linear(right, p)?;
            combine(&a, &b, '+', p)
        }
        E::Multiply { left, right } => {
            let a = expression_linear(left, p)?;
            let b = expression_linear(right, p)?;
            product(&a, &b, p)
        }
        E::Divide { left, right } => {
            let a = expression_linear(left, p)?;
            let b = expression_linear(right, p)?;
            quotient(&a, &b, p)
        }
        E::RealBoundary { value, .. } => expression_linear(value, p),
        E::RealBinary {
            operation,
            left,
            right,
            ..
        } => {
            let a = expression_linear(left, p)?;
            let b = expression_linear(right, p)?;
            match operation {
                ir::RealOperation::Add => combine(&a, &b, '+', p),
                ir::RealOperation::Subtract => combine(&a, &b, '-', p),
                ir::RealOperation::Multiply => product(&a, &b, p),
                ir::RealOperation::Divide => quotient(&a, &b, p),
            }
        }
        _ => None,
    }
}
fn product(a: &Linear, b: &Linear, p: &mut Paid) -> Option<Linear> {
    if a.is_constant() {
        scale(b, &a.constant, p)
    } else if b.is_constant() {
        scale(a, &b.constant, p)
    } else {
        None
    }
}
fn quotient(a: &Linear, b: &Linear, p: &mut Paid) -> Option<Linear> {
    if !b.is_constant() || b.constant.is_zero() {
        return None;
    }
    let one = p.binary(1.)?;
    let inverse = p.op(&one, &b.constant, '/')?;
    scale(a, &inverse, p)
}

/// Graph ids reachable from `roots`, in topological (increasing) order.
fn reachable(b: &Builder<'_>, roots: &[Id]) -> Result<Vec<Id>, Error> {
    let n = roots.iter().copied().max().map_or(0, |m| m + 1);
    b.w.debit(2, (n as u64).saturating_mul(16).saturating_add(64))?;
    let mut seen = vec![false; n];
    let mut stack = roots.to_vec();
    while let Some(id) = stack.pop() {
        b.w.step()?;
        if seen[id] {
            continue;
        }
        seen[id] = true;
        let node = b
            .graph
            .node(id)
            .ok_or_else(|| invalid("right-limit graph node missing"))?;
        stack.extend_from_slice(&node.operands);
    }
    Ok((0..n).filter(|&id| seen[id]).collect())
}

/// Exact linear forms and exact values at tau of the reachable values, with
/// source rounding read through. A value stored by an assignment of this
/// activation is a latched read: it has neither (its tau value is not the
/// value at te), so no zero-set or derivative certificate passes through it.
struct Forms {
    linear: Vec<Option<Linear>>,
    exact: Vec<Option<R>>,
}
fn forms(b: &Builder<'_>, ids: &[Id], p: &mut Paid) -> Forms {
    let n = ids.last().map_or(0, |&m| m + 1);
    let mut linear: Vec<Option<Linear>> = vec![None; n];
    let mut exact: Vec<Option<R>> = vec![None; n];
    for &id in ids {
        if p.pay(4).is_none() {
            break;
        }
        if b.stored.get(id).copied().unwrap_or(true) {
            continue;
        }
        let Some(node) = b.graph.node(id) else {
            break;
        };
        let cell = &b.values[id];
        let args = &node.operands;
        let arg = |k: usize| args.get(k).copied();
        let point_exact = |p: &mut Paid| {
            cell.proof.as_ref().and_then(|v| p.copy(v)).or_else(|| {
                cell.image
                    .filter(|v| v.lo.to_bits() == v.hi.to_bits())
                    .and_then(|v| p.binary(v.lo))
            })
        };
        let (form, value) = match &node.operation {
            O::Literal(v) => (p.binary(*v).map(Linear::constant), p.binary(*v)),
            O::Affine { constant, terms } => {
                let form = expression_linear(
                    &E::Affine {
                        constant: *constant,
                        terms: terms.to_vec(),
                    },
                    p,
                );
                (form, point_exact(p))
            }
            O::State(state) => {
                let mut form = Linear::constant(R::zero());
                let one = p.binary(1.);
                if let Some(one) = one {
                    form.states.insert(*state, one);
                }
                (Some(form), point_exact(p))
            }
            O::Boundary(..) | O::IntegerStore(..) | O::CheckedInteger(..) => {
                let a = arg(0);
                (
                    a.and_then(|a| linear[a].clone()),
                    a.and_then(|a| exact[a].clone()),
                )
            }
            O::Add | O::Real(ir::RealOperation::Add, _) => binary(&linear, &exact, args, '+', p),
            O::Real(ir::RealOperation::Subtract, _) => binary(&linear, &exact, args, '-', p),
            O::Multiply | O::Real(ir::RealOperation::Multiply, _) => {
                binary(&linear, &exact, args, '*', p)
            }
            O::Divide | O::Real(ir::RealOperation::Divide, _) => {
                binary(&linear, &exact, args, '/', p)
            }
            _ => (None, None),
        };
        linear[id] = form;
        exact[id] = value;
    }
    Forms { linear, exact }
}
fn binary(
    linear: &[Option<Linear>],
    exact: &[Option<R>],
    args: &[Id],
    op: char,
    p: &mut Paid,
) -> (Option<Linear>, Option<R>) {
    let (Some(&a), Some(&b)) = (args.first(), args.get(1)) else {
        return (None, None);
    };
    let form = linear[a]
        .as_ref()
        .zip(linear[b].as_ref())
        .and_then(|(x, y)| match op {
            '+' | '-' => combine(x, y, op, p),
            '*' => product(x, y, p),
            _ => quotient(x, y, p),
        });
    let value = exact[a]
        .as_ref()
        .zip(exact[b].as_ref())
        .and_then(|(x, y)| p.op(x, y, op));
    (form, value)
}

/// k with d = k*g exactly (k != 0), as a sign.
fn ratio(d: &Linear, g: &Linear, p: &mut Paid) -> Option<i8> {
    let pivot = g
        .nodes
        .iter()
        .next()
        .map(|(n, c)| (d.nodes.get(n), c))
        .or_else(|| g.states.iter().next().map(|(s, c)| (d.states.get(s), c)))?;
    let numerator = pivot.0?;
    let k = p.op(numerator, pivot.1, '/')?;
    if k.is_zero() {
        return None;
    }
    let same = |a: Option<&R>, b: Option<&R>, p: &mut Paid| -> Option<bool> {
        let zero = R::zero();
        let scaled = p.op(&k, b.unwrap_or(&zero), '*')?;
        Some(p.cmp(a.unwrap_or(&zero), &scaled)?.is_eq())
    };
    if !same(Some(&d.constant), Some(&g.constant), p)? {
        return None;
    }
    for key in d.nodes.keys().chain(g.nodes.keys()) {
        if !same(d.nodes.get(key), g.nodes.get(key), p)? {
            return None;
        }
    }
    for key in d.states.keys().chain(g.states.keys()) {
        if !same(d.states.get(key), g.states.get(key), p)? {
            return None;
        }
    }
    Some(if k.is_positive() { 1 } else { -1 })
}

/// Cross leaves of the executing body with their calendar leaf index.
fn fired_cross_guards<'a>(b: &Builder<'a>) -> Result<Vec<(usize, &'a E)>, Error> {
    let mut base = 0usize;
    for event in &b.p.events[..b.event] {
        b.w.step()?;
        base += event.trigger.leaves()?.len();
    }
    let mut out = Vec::new();
    for (k, trigger) in b.p.events[b.event]
        .trigger
        .leaves()?
        .into_iter()
        .enumerate()
    {
        b.w.step()?;
        if let ir::EventTrigger::Cross { guard, .. } = trigger {
            out.push((base + k, guard));
        }
    }
    Ok(out)
}

/// A fired cross guard with the same exact zero set and a certified side.
/// Inconsistent sides of matching leaves are no proof.
fn same_zero_set(b: &Builder<'_>, d: Option<&Linear>, p: &mut Paid) -> Result<Option<I>, Error> {
    let Some(d) = d else {
        return Ok(None);
    };
    let mut read = None;
    let mut conflict = false;
    for (leaf, guard) in fired_cross_guards(b)? {
        let Some(side) = crate::event_conditions::post_root_side(leaf) else {
            continue;
        };
        let Some(g) = expression_linear(guard, p) else {
            continue;
        };
        let Some(k) = ratio(d, &g, p) else {
            continue;
        };
        let value = crate::event_conditions::side_value(k * side);
        match read {
            None => read = Some(value),
            Some(old) if old != value => conflict = true,
            _ => {}
        }
    }
    Ok(read.filter(|_| !conflict))
}

/// Derivative sign of a stateless difference in driven inputs that is exactly
/// zero at tau; an exactly zero derivative of this affine form is a plateau.
/// An internal node read (another instance's output, say) counts when the
/// pre-event provider expands it to an affine form in driven inputs only.
fn input_slope(
    b: &Builder<'_>,
    d: Option<&Linear>,
    zero: bool,
    p: &mut Paid,
) -> Result<Option<I>, Error> {
    let Some(d) = d.filter(|d| zero && d.states.is_empty()) else {
        return Ok(None);
    };
    let Some(slopes) = crate::event_conditions::post_root_input_slopes() else {
        return Ok(None);
    };
    let mut sum = I::ZERO;
    for (&node, c) in &d.nodes {
        let slope = match slopes.by_node.get(node).copied().flatten() {
            Some(slope) => Some(slope),
            None => node_slope(b, node, &slopes, p)?,
        };
        let Some((slope, c)) = slope.zip(p.enclose(c)) else {
            return Ok(None);
        };
        sum = sum + c * slope;
    }
    Ok(if sum.zero() {
        Some(I::ZERO)
    } else {
        sum.sign().map(crate::event_conditions::side_value)
    })
}

/// Derivative enclosure of an internal node forced through independent
/// grounded branches by driven inputs alone (no state, history or selection).
fn node_slope(
    b: &Builder<'_>,
    node: usize,
    slopes: &crate::event_conditions::InputSlopes,
    p: &mut Paid,
) -> Result<Option<I>, Error> {
    // The same admission as the pre-event provider: unconditional branches only.
    if !crate::procedure::unconditional_contributions(b.p, b.w)? {
        return Ok(None);
    }
    let probe = E::Affine {
        constant: 0.,
        terms: vec![ir::Term {
            node,
            coefficient: 1.,
        }],
    };
    let expanded = match crate::causal_voltage::expand_paid(&probe, b.p, &slopes.driven, b.w) {
        Ok(expanded) => expanded,
        Err(error) if certificate_gap(&error) => return Ok(None),
        Err(error) => return Err(error),
    };
    let Some(form) = expression_linear(&expanded, p).filter(|f| f.states.is_empty()) else {
        return Ok(None);
    };
    let mut sum = I::ZERO;
    for (&input, c) in &form.nodes {
        let Some((slope, c)) = slopes
            .by_node
            .get(input)
            .copied()
            .flatten()
            .zip(p.enclose(c))
        else {
            return Ok(None);
        };
        sum = sum + c * slope;
    }
    Ok(Some(sum))
}

/// First-order dependence on reads that move over W: (column, coefficient)
/// with columns 0.. for nodes and nodes.len().. for histories. Empty: every
/// read of this value is the same at te as at tau. None: unknown.
type Moving = Vec<(usize, I)>;
fn add(moving: &mut Moving, column: usize, c: I) {
    match moving.iter_mut().find(|(k, _)| *k == column) {
        Some((_, sum)) => *sum = *sum + c,
        None => moving.push((column, c)),
    }
}
fn point(v: Option<I>) -> Option<f64> {
    v.filter(|v| v.lo.to_bits() == v.hi.to_bits()).map(|v| v.lo)
}

struct Window {
    nodes: Vec<I>,
    operators: Vec<Option<I>>,
    // W enclosure of each reachable value; None: no certificate.
    values: Vec<Option<I>>,
}
fn window(b: &Builder<'_>, ids: &[Id]) -> Result<Option<Window>, Error> {
    let Some((procedure, operators)) = crate::event_conditions::post_root_node_window() else {
        return Ok(None);
    };
    let mut nodes = procedure.nodes;
    if nodes.len() != b.domain.node_bounds.len() {
        return Ok(None);
    }
    let n = ids.last().map_or(0, |&m| m + 1);
    b.w.debit(2, ((nodes.len() + operators.len() + n) * 32 + 64) as u64)?;
    // Other nodes over W through the same pre-event provider as at tau: only
    // nodes independent of this batch's writes, read through continuous
    // transition histories. A provider gap leaves a node unbounded.
    let histories = operators
        .iter()
        .map(|v| v.unwrap_or_else(whole))
        .collect::<Vec<_>>();
    match crate::causal_event::fill_independent_pre_event_nodes(
        b.p,
        &procedure.driven,
        &procedure.fired,
        &mut nodes,
        b.domain.state_bounds,
        &histories,
        b.w,
    ) {
        Ok(_) => {}
        Err(error) if certificate_gap(&error) => {}
        Err(error) => return Err(error),
    }
    let node_points = nodes.iter().map(|v| point(Some(*v))).collect::<Vec<_>>();
    let operator_bounds = operators
        .iter()
        .map(|v| v.unwrap_or_else(whole))
        .collect::<Vec<_>>();
    let operator_points = operators.iter().map(|v| point(*v)).collect::<Vec<_>>();
    let local = LocalState::try_with_context(b.domain.state_bounds, None)?;
    let domain = Domain {
        nodes: &node_points,
        node_bounds: &nodes,
        states: b.domain.states,
        state_bounds: b.domain.state_bounds,
        operators: &operator_points,
        operator_bounds: &operator_bounds,
        local: &local,
    };
    let mut cells: Vec<Option<Cell>> = vec![None; n];
    for &id in ids {
        b.w.step()?;
        let node = b
            .graph
            .node(id)
            .ok_or_else(|| invalid("right-limit graph node missing"))?;
        let mut args = Vec::with_capacity(node.operands.len());
        for &operand in &node.operands {
            match &cells[operand] {
                Some(cell) => args.push(cell.copy(b.w)?),
                None => break,
            }
        }
        if args.len() != node.operands.len() {
            continue;
        }
        cells[id] = match node.operation.evaluate(&args, &domain, b.w) {
            Ok(cell) => Some(cell),
            Err(error) if certificate_gap(&error) => None,
            Err(error) => return Err(error),
        };
    }
    let values = cells
        .iter()
        .map(|c| c.as_ref().and_then(|c| c.image).filter(|v| v.finite()))
        .collect();
    Ok(Some(Window {
        nodes,
        operators,
        values,
    }))
}
fn moving(
    b: &Builder<'_>,
    ids: &[Id],
    window: Option<&Window>,
) -> Result<Vec<Option<Moving>>, Error> {
    let n = ids.last().map_or(0, |&m| m + 1);
    let node_count = b.domain.node_bounds.len();
    let mut out: Vec<Option<Moving>> = vec![None; n];
    let moves_node =
        |node: usize| window.is_none_or(|w| point(w.nodes.get(node).copied()).is_none());
    let moves_operator =
        |k: usize| window.is_none_or(|w| point(w.operators.get(k).copied().flatten()).is_none());
    let constant_over_w =
        |id: usize| window.is_some_and(|w| point(w.values.get(id).copied().flatten()).is_some());
    for &id in ids {
        b.w.step()?;
        let node = b
            .graph
            .node(id)
            .ok_or_else(|| invalid("right-limit graph node missing"))?;
        let args = &node.operands;
        let get = |k: usize| args.get(k).and_then(|&a| out[a].clone());
        let root_point = |k: usize| args.get(k).and_then(|&a| point(b.values[a].image));
        let linear = |a: Option<Moving>, c: f64| -> Option<Moving> {
            Some(a?.into_iter().map(|(k, v)| (k, v * I::point(c))).collect())
        };
        let value = match &node.operation {
            O::Literal(_) | O::State(_) => Some(Moving::new()),
            O::Affine { terms, .. } => {
                let mut m = Moving::new();
                for t in terms.iter() {
                    b.w.step()?;
                    if t.node != 0 && t.coefficient != 0. && moves_node(t.node) {
                        add(&mut m, t.node, I::point(t.coefficient));
                    }
                }
                Some(m)
            }
            O::Operator(k) => Some(if moves_operator(*k) {
                vec![(node_count + k, I::ONE)]
            } else {
                Moving::new()
            }),
            O::Boundary(..) | O::IntegerStore(..) | O::CheckedInteger(..) => get(0),
            O::Add | O::Real(ir::RealOperation::Add, _) => get(0).zip(get(1)).map(|(mut a, b)| {
                for (k, c) in b {
                    add(&mut a, k, c);
                }
                a
            }),
            O::Real(ir::RealOperation::Subtract, _) => get(0).zip(get(1)).map(|(mut a, b)| {
                for (k, c) in b {
                    add(&mut a, k, -c);
                }
                a
            }),
            O::Multiply | O::Real(ir::RealOperation::Multiply, _) => match (get(0), get(1)) {
                (Some(a), Some(c)) if a.is_empty() && c.is_empty() => Some(Moving::new()),
                (Some(a), c) if a.is_empty() && root_point(0).is_some() => {
                    linear(c, root_point(0).unwrap())
                }
                (a, Some(c)) if c.is_empty() && root_point(1).is_some() => {
                    linear(a, root_point(1).unwrap())
                }
                _ => None,
            },
            O::Divide | O::Real(ir::RealOperation::Divide, _) => match (get(0), get(1)) {
                (Some(a), Some(c)) if a.is_empty() && c.is_empty() => Some(Moving::new()),
                (a, Some(c)) if c.is_empty() && root_point(1).is_some_and(|v| v != 0.) => {
                    let inverse = I::ONE / I::point(root_point(1).unwrap());
                    a.map(|a| a.into_iter().map(|(k, v)| (k, v * inverse)).collect())
                }
                _ => None,
            },
            _ => {
                let all = (0..args.len()).all(|k| get(k).is_some_and(|m| m.is_empty()));
                all.then(Moving::new)
            }
        };
        // A nonlinear value whose whole W enclosure is one point is constant.
        out[id] = match value {
            Some(mut m) => {
                m.retain(|(_, c)| !c.zero());
                if m.is_empty() || !constant_over_w(id) {
                    Some(m)
                } else {
                    Some(Moving::new())
                }
            }
            None if constant_over_w(id) => Some(Moving::new()),
            None => None,
        };
    }
    Ok(out)
}

/// Post-root decision of one comparison in a body that reads at tau+.
pub(super) fn decide(
    b: &Builder<'_>,
    relation: ir::Relation,
    left: Id,
    right: Id,
    compared: Option<bool>,
    origin: &ir::Origin,
) -> Result<Outcome, Error> {
    let tied = tie(&b.values[left], &b.values[right], b.w)?;
    if let Some(value) = compared.filter(|_| !tied) {
        // Strictly signed at tau: continuous reads keep the sign at tau+.
        return Ok(Outcome::Decided(value, false));
    }
    let ids = reachable(b, &[left, right])?;
    let mut p = Paid::new(b.w);
    let forms = forms(b, &ids, &mut p);
    let difference = forms.linear[left]
        .as_ref()
        .zip(forms.linear[right].as_ref())
        .and_then(|(l, r)| combine(l, r, '-', &mut p));
    let zero = forms.exact[left]
        .as_ref()
        .zip(forms.exact[right].as_ref())
        .and_then(|(l, r)| p.cmp(l, r))
        .is_some_and(|o| o.is_eq());
    let sided = same_zero_set(b, difference.as_ref(), &mut p)?;
    let slope = if tied && sided.is_none() {
        input_slope(b, difference.as_ref(), zero, &mut p)?
    } else {
        None
    };
    // Paid owns only Work failures; an exceeded exact allowance is no proof.
    p.finish(Some(()))?;
    // Side values are strictly signed or exactly zero, so they always decide.
    let decided = |read: I| Outcome::Decided(crate::event_numeric::sign(relation, read).0, true);
    if let Some(read) = sided {
        return Ok(decided(read));
    }
    if !tied {
        return Ok(Outcome::Undecided);
    }
    if let Some(read) = slope {
        return Ok(decided(read));
    }
    let window = window(b, &ids)?;
    let moving = moving(b, &ids, window.as_ref())?;
    if let Some((l, r)) = moving[left].as_ref().zip(moving[right].as_ref()) {
        let mut d = l.clone();
        for &(k, c) in r {
            add(&mut d, k, -c);
        }
        d.retain(|(_, c)| !c.zero());
        if d.is_empty() {
            // A plateau: every read is the same at te, so the tie holds at tau+.
            return Ok(decided(I::ZERO));
        }
    }
    if let Some(w) = &window {
        if let Some((l, r)) = w.values[left].zip(w.values[right]) {
            let (yes, no) = crate::event_numeric::sign(relation, l - r);
            if yes || no {
                crate::diagnostics::counter("post_root_window_reads", 1);
                return Ok(Outcome::Decided(yes, true));
            }
        }
    }
    b.w.debit(
        2,
        (origin.source.len() + origin.instance.len())
            .saturating_mul(2)
            .saturating_add(256) as u64,
    )?;
    Ok(Outcome::Unsided(Error::new(
        "event_condition",
        format!(
            "cannot certify {relation:?} condition at {} just after its crossing root: the difference is exactly zero at tau and has no one-sided or right-window certificate",
            origin.label()
        ),
    )))
}

/// Recertify a post-root guard: the box at tau must still give an exact tie
/// or the same decision; a box that decides otherwise refutes the premise.
pub(super) fn recertify(
    relation: ir::Relation,
    a: &Cell,
    b: &Cell,
    value: bool,
    w: &Work,
) -> Result<bool, Error> {
    if tie(a, b, w)? {
        return Ok(true);
    }
    Ok(control::compare(relation, a, b, w)? == Some(value))
}

/// Identical arms behave the same at every admissible te: equal statements
/// apart from source positions, with no display output (whose record needs
/// one decided path).
pub(super) fn same_arms(yes: &[S], no: &[S], w: &Work) -> Result<bool, Error> {
    let a = crate::event_floor::admission_bytes(&yes, w)?;
    let b = crate::event_floor::admission_bytes(&no, w)?;
    w.debit(2, (a.len() + b.len()) as u64)?;
    let parse = |bytes: &[u8]| {
        serde_json::from_slice::<serde_json::Value>(bytes)
            .map_err(|_| invalid("cannot read event arm for comparison"))
    };
    let (mut a, mut b) = (parse(&a)?, parse(&b)?);
    fn display(v: &serde_json::Value) -> bool {
        match v {
            serde_json::Value::Object(m) => {
                m.get("kind").and_then(serde_json::Value::as_str) == Some("display")
                    || m.values().any(display)
            }
            serde_json::Value::Array(a) => a.iter().any(display),
            _ => false,
        }
    }
    fn plain(v: &mut serde_json::Value) {
        match v {
            serde_json::Value::Object(m) => {
                m.remove("origin");
                m.values_mut().for_each(plain);
            }
            serde_json::Value::Array(a) => a.iter_mut().for_each(plain),
            _ => {}
        }
    }
    if display(&a) || display(&b) {
        return Ok(false);
    }
    plain(&mut a);
    plain(&mut b);
    Ok(a == b)
}

#[cfg(test)]
#[path = "procedure_right_limit_tests.rs"]
mod tests;
