//! Exact event bookkeeping for the admitted history consumer. This owner is
//! separate from Floor capability and never changes admission or mathematical caps.
use super::*;
use crate::exact_source::history_paid::Paid;
use crate::{
    events::EventModel,
    ir::{Error, Statement},
    transition_source_plan::Work,
};
use num_traits::ToPrimitive;
use std::collections::BTreeMap;

// Both capabilities already qualified the original independent calendar.
// A Forcing execution borrows its original ledger and physical node mapping.
pub(crate) fn work(model: &EventModel) -> Option<&Work> {
    model
        .history_admission
        .as_ref()
        .map(|a| a.context.borrow_work())
        .or_else(|| {
            model
                .forcing
                .as_ref()
                .filter(|g| g.requires_composed_history())
                .map(|g| g.request_work())
        })
}
pub(crate) fn input_nodes(model: &EventModel) -> Option<&[usize]> {
    model
        .history_admission
        .as_ref()
        .map(|a| a.context.event_input_nodes())
        .or_else(|| {
            model
                .forcing
                .as_ref()
                .filter(|g| g.requires_composed_history())
                .map(|g| g.input_nodes())
        })
}
pub(crate) fn inputs(
    model: &EventModel,
    t: &crate::pwl::Trajectory,
    time: f64,
) -> Result<Vec<f64>, Error> {
    if let Some(w) = crate::analytic_request::proof_owner(model).map(|o| o.work()) {
        t.history_values(time, w)
    } else {
        Ok(t.values(time))
    }
}
pub(crate) fn input_bounds(
    model: &EventModel,
    t: &crate::pwl::Trajectory,
    time: f64,
) -> Result<Vec<I>, Error> {
    if let Some(w) = crate::analytic_request::proof_owner(model).map(|o| o.work()) {
        t.history_value_bounds(time, w)
    } else {
        Ok(t.value_bounds(time))
    }
}
pub(crate) fn input_range(
    model: &EventModel,
    t: &crate::pwl::Trajectory,
    time: I,
) -> Result<(Vec<I>, Vec<I>), Error> {
    if let Some(w) = crate::analytic_request::proof_owner(model).map(|o| o.work()) {
        t.history_range(time, w)
    } else {
        t.range(time)
    }
}
fn storage<T>(n: usize, w: &Work) -> Result<(), Error> {
    w.debit(2, 0)?;
    w.debit(
        2,
        (n as u64)
            .saturating_mul(std::mem::size_of::<T>().div_ceil(std::mem::size_of::<usize>()) as u64),
    )
}
// Rust 1.95 alloc::collections::btree has B=6: 11 key/value slots,
// 12 child edges. A real insert/remove searches at most 11 keys per level,
// splits/merges at most once per level, and may allocate two nodes plus a
// new root. Four complete node-storage/move footprints per level plus 64
// key/counter steps bound this single edit. A B>=2 tree's height is bounded
// by log2(len+1)+2. Deep Rational clones are charged separately by copy().
pub(crate) fn map_edit<T>(n: usize, w: &Work) -> Result<(), Error> {
    w.debit(2, 0)?;
    w.debit(2, 8)?;
    let levels = (usize::BITS - n.saturating_add(1).max(1).leading_zeros()) as u64 + 2;
    let item = (std::mem::size_of::<usize>() + std::mem::size_of::<T>())
        .div_ceil(std::mem::size_of::<usize>()) as u64;
    let node = 11u64.saturating_mul(item).saturating_add(12 + 8);
    w.debit(
        2,
        levels.saturating_mul(node.saturating_mul(4).saturating_add(64)),
    )
}
pub(crate) fn insert<T>(
    map: &mut BTreeMap<usize, T>,
    key: usize,
    value: T,
    w: &Work,
) -> Result<(), Error> {
    map_edit::<T>(map.len(), w)?;
    map.insert(key, value);
    Ok(())
}
pub(crate) fn remove<T>(map: &mut BTreeMap<usize, T>, key: usize, w: &Work) -> Result<(), Error> {
    map_edit::<T>(map.len(), w)?;
    map.remove(&key);
    Ok(())
}
pub(crate) fn lookup<'a, T>(
    map: &'a BTreeMap<usize, T>,
    key: usize,
    w: &Work,
) -> Result<Option<&'a T>, Error> {
    w.debit(2, 0)?;
    for (k, v) in map {
        w.step()?;
        if *k == key {
            return Ok(Some(v));
        }
        if *k > key {
            break;
        }
    }
    Ok(None)
}
fn charge_rat_comparison(a: &R, b: &R, w: &Work) -> Result<(), Error> {
    w.debit(2, 0)?;
    w.debit(2, 4)?;
    let limbs = [
        a.numer().bits(),
        a.denom().bits(),
        b.numer().bits(),
        b.denom().bits(),
    ]
    .into_iter()
    .map(|n| n.div_ceil(64))
    .sum::<u64>();
    w.debit(2, limbs.saturating_add(4))?;
    #[cfg(test)]
    crate::diagnostics::counter("history_local_comparison_limb_items", limbs as usize);
    Ok(())
}
pub(crate) fn same_rat(a: &R, b: &R, w: &Work) -> Result<bool, Error> {
    charge_rat_comparison(a, b, w)?;
    Ok(a == b)
}
pub(crate) fn equal(a: &Proofs, b: &Proofs, w: &Work) -> Result<bool, Error> {
    w.debit(2, 0)?;
    w.step()?;
    if a.len() != b.len() {
        return Ok(false);
    }
    for ((ka, va), (kb, vb)) in a.iter().zip(b) {
        w.step()?;
        if ka != kb || !same_rat(va, vb, w)? {
            return Ok(false);
        }
    }
    Ok(true)
}
pub(crate) fn copy_map(source: &Proofs, w: &Work) -> Result<Proofs, Error> {
    w.debit(2, 0)?;
    let mut out = Proofs::new();
    for (&state, value) in source {
        w.step()?;
        let mut p = Paid::new(w);
        let copied = p.copy(value);
        if let Some(copied) = p.finish(copied)? {
            insert(&mut out, state, copied, w)?
        }
    }
    Ok(out)
}
pub(crate) fn context_new<'a>(
    model: &EventModel,
    t: &crate::pwl::Trajectory,
    inputs: &[I],
    states: &'a Proofs,
    root: Option<&crate::exact_source::RootTime>,
) -> Result<Context<'a>, Error> {
    let role = crate::analytic_request::proof_owner(model).expect("paid value role");
    let w = role.work();
    w.debit(2, 0)?;
    storage::<Option<R>>(model.program.nodes.len(), w)?;
    let mut nodes = vec![None; model.program.nodes.len()];
    let mut p = Paid::new(w);
    let zero = p.binary(0.);
    nodes[0] = p.finish(zero)?;
    let indices = role.input_nodes();
    for (k, bounds) in inputs.iter().enumerate() {
        w.step()?;
        let mut value = if let (Some(root), Some(Some(curve))) = (root, t.exact_sources.get(k)) {
            curve.at_root_history(root, w)?
        } else {
            None
        };
        if let Some(v) = value.as_ref() {
            if !crate::exact_source::enclosure_with_work(v, w)?
                .is_some_and(|i| bounds.lo <= i.lo && i.hi <= bounds.hi)
            {
                value = None
            }
        }
        if value.is_none() && bounds.finite() && bounds.lo == bounds.hi {
            let mut p = Paid::new(w);
            let v = p.binary(bounds.lo);
            value = p.finish(v)?;
        }
        if let Some(&node) = indices.get(k) {
            nodes[node] = value
        } else {
            return Err(Error::new(
                "event_condition",
                "history proof input binding mismatch",
            ));
        }
    }
    w.step()?;
    Ok(Context {
        states,
        nodes,
        operators: vec![],
        floor_work: None,
        history_work: Some(w.clone()),
        floor_bounds: None,
    })
}
fn copy_options(values: &[Option<R>], w: &Work) -> Result<Vec<Option<R>>, Error> {
    storage::<Option<R>>(values.len(), w)?;
    let mut out = Vec::with_capacity(values.len());
    for value in values {
        w.step()?;
        let mut p = Paid::new(w);
        let copied = value.as_ref().and_then(|v| p.copy(v));
        out.push(p.finish(copied)?)
    }
    Ok(out)
}
pub(crate) fn context_operators<'a>(c: &Context<'a>, ops: &[I]) -> Result<Context<'a>, Error> {
    let w = c.history_work.as_ref().unwrap();
    let nodes = copy_options(&c.nodes, w)?;
    storage::<I>(ops.len(), w)?;
    w.step()?;
    Ok(Context {
        states: c.states,
        nodes,
        operators: ops.to_vec(),
        floor_work: None,
        history_work: Some(w.clone()),
        floor_bounds: None,
    })
}
pub(crate) fn local_new(bounds: &[I], c: &Context<'_>) -> Result<LocalState, Error> {
    let w = c.history_work.as_ref().unwrap();
    storage::<I>(bounds.len(), w)?;
    storage::<Option<R>>(bounds.len(), w)?;
    let mut exact = Vec::with_capacity(bounds.len());
    for b in bounds {
        w.step()?;
        let mut p = Paid::new(w);
        let value = if b.finite() && b.lo == b.hi {
            p.binary(b.lo)
        } else {
            None
        };
        exact.push(p.finish(value)?)
    }
    for (&state, v) in c.states {
        w.step()?;
        if let Some(b) = bounds.get(state) {
            if crate::exact_source::enclosure_with_work(v, w)?
                .is_some_and(|i| b.lo <= i.lo && i.hi <= b.hi)
            {
                let mut p = Paid::new(w);
                let v = p.copy(v);
                exact[state] = p.finish(v)?
            }
        }
    }
    let nodes = copy_options(&c.nodes, w)?;
    w.step()?;
    Ok(LocalState {
        bounds: bounds.to_vec(),
        exact,
        nodes: Some(nodes),
        floor_work: None,
        history_work: Some(w.clone()),
        floor_bounds: None,
    })
}
pub(crate) fn charge_local_copy(local: &LocalState) -> Result<(), Error> {
    let w = local.history_work.as_ref().unwrap();
    storage::<I>(local.bounds.len(), w)?;
    storage::<Option<R>>(local.exact.len(), w)?;
    if let Some(nodes) = &local.nodes {
        storage::<Option<R>>(nodes.len(), w)?
    }
    for v in local.exact.iter().chain(local.nodes.iter().flatten()) {
        w.step()?;
        if let Some(v) = v {
            w.debit(2, 4)?;
            w.debit(
                2,
                32 + 4 * v.numer().bits().max(v.denom().bits()).div_ceil(64),
            )?;
        }
    }
    w.debit(2, 8)
}
pub(crate) fn charge_local_comparison(a: &LocalState, b: &LocalState) -> Result<(), Error> {
    let w = a.history_work.as_ref().unwrap();
    w.debit(2, 0)?;
    for (x, y) in a.exact.iter().zip(&b.exact) {
        w.step()?;
        if let (Some(x), Some(y)) = (x, y) {
            charge_rat_comparison(x, y, w)?;
        }
    }
    Ok(())
}
// Keep the explicit proof inputs and their original accounting owner together.
#[allow(clippy::too_many_arguments)]
fn eval(
    e: &E,
    nodes: &[I],
    states: &[Option<R>],
    proofs: Option<&[Option<R>]>,
    p: &mut Paid<'_>,
    w: &Work,
    depth: usize,
    count: &mut usize,
) -> Option<R> {
    p.pay(1)?;
    *count += 1;
    if depth > 64 || *count > 512 {
        return None;
    }
    match e {
        E::Affine { constant, terms } => {
            if terms.len() > 512 {
                return None;
            }
            let mut value = p.binary(*constant)?;
            for term in terms {
                p.pay(1)?;
                if term.node == 0 {
                    continue;
                }
                let v = if let Some(Some(v)) = proofs.and_then(|n| n.get(term.node)) {
                    p.copy(v)?
                } else {
                    let b = nodes.get(term.node)?;
                    if b.lo != b.hi {
                        return None;
                    }
                    p.binary(b.lo)?
                };
                let c = p.binary(term.coefficient)?;
                let product = p.op(&c, &v, '*')?;
                value = p.op(&value, &product, '+')?;
            }
            Some(value)
        }
        E::State { state } => {
            let v = p.copy(states.get(*state)?.as_ref()?)?;
            p.checked(v)
        }
        E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
            let a = eval(left, nodes, states, proofs, p, w, depth + 1, count)?;
            let b = eval(right, nodes, states, proofs, p, w, depth + 1, count)?;
            p.op(
                &a,
                &b,
                if matches!(e, E::Add { .. }) {
                    '+'
                } else if matches!(e, E::Multiply { .. }) {
                    '*'
                } else {
                    '/'
                },
            )
        }
        E::Power { base, exponent } if *exponent <= 32 => {
            let a = eval(base, nodes, states, proofs, p, w, depth + 1, count)?;
            let mut v = p.binary(1.)?;
            for _ in 0..*exponent {
                v = p.op(&v, &a, '*')?
            }
            Some(v)
        }
        E::IntegerPrimitive {
            function,
            args,
            origin,
        } => {
            // This optional arithmetic proof inherits the pre-existing evaluator. It
            // neither invokes Floor resolution nor grants a new primitive role.
            let failure = std::cell::RefCell::new(None);
            let debit = |n| -> Result<(), Error> {
                match w.debit(2, n) {
                    Ok(()) => Ok(()),
                    Err(error) => {
                        *failure.borrow_mut() = Some(error);
                        Err(Error::new(
                            "step_budget",
                            "history integer proof work exhausted",
                        ))
                    }
                }
            };
            let mut visited = 0;
            let result = crate::integer_primitive::evaluate(
                *function,
                args,
                origin,
                &mut |state| {
                    debit(0)?;
                    debit(3)?;
                    let r = states.get(state).and_then(Option::as_ref).ok_or_else(|| {
                        Error::new("unknown_proof", "integer state proof missing")
                    })?;
                    debit(1 + r.numer().bits().div_ceil(64) + r.denom().bits().div_ceil(64))?;
                    if !r.is_integer() {
                        return Err(Error::new("unknown_proof", "noninteger state proof"));
                    }
                    r.numer().to_i32().ok_or_else(|| {
                        Error::new("unknown_proof", "integer state proof outside i32")
                    })
                },
                &mut || {
                    visited += 1;
                    debit(0)?;
                    debit(1)?;
                    if *count + visited > 512 || depth + visited > 64 {
                        return Err(Error::new(
                            "unknown_proof",
                            "integer proof expression limit",
                        ));
                    }
                    Ok(())
                },
            );
            if let Some(error) = failure.into_inner() {
                p.accept::<()>(Err(error))?;
            }
            let value = result.ok()?;
            *count += visited;
            let v = p.binary(f64::from(value))?;
            p.checked(v)
        }
        E::EventMath { function, args, .. } => {
            let a = eval(args.first()?, nodes, states, proofs, p, w, depth + 1, count)?;
            match function {
                F::Floor if args.len() == 1 => p.floor(&a),
                F::Abs if args.len() == 1 => {
                    let z = p.binary(0.)?;
                    if p.cmp(&a, &z)?.is_lt() {
                        p.op(&z, &a, '-')
                    } else {
                        p.copy(&a)
                    }
                }
                F::Min | F::Max if args.len() == 2 => {
                    let b = eval(&args[1], nodes, states, proofs, p, w, depth + 1, count)?;
                    let order = p.cmp(&a, &b)?;
                    let a_first = if matches!(function, F::Min) {
                        !order.is_gt()
                    } else {
                        !order.is_lt()
                    };
                    if a_first {
                        Some(a)
                    } else {
                        Some(b)
                    }
                }
                _ => None,
            }
        }
        _ => None,
    }
}
pub(crate) fn value(local: &LocalState, e: &E, nodes: &[I], w: &Work) -> Result<Option<R>, Error> {
    // Primitive callbacks borrow the shared counter independently, so their actual
    // state limb extraction can be charged without aliasing the arithmetic frame.
    let mut p = Paid::new(w);
    let result = eval(
        e,
        nodes,
        &local.exact,
        local.nodes.as_deref(),
        &mut p,
        w,
        0,
        &mut 0,
    );
    p.finish(result)
}
pub(crate) fn assign(
    local: &mut LocalState,
    state: usize,
    e: &E,
    nodes: &[I],
    bounds: I,
) -> Result<(), Error> {
    let w = local.history_work.as_ref().unwrap();
    let exact = value(local, e, nodes, w)?;
    let tighter = match exact.as_ref() {
        Some(v) => crate::exact_source::enclosure_with_work(v, w)?
            .filter(|i| bounds.lo <= i.lo && i.hi <= bounds.hi),
        None => None,
    };
    w.step()?;
    local.bounds[state] = tighter.unwrap_or(bounds);
    local.exact[state] = exact.filter(|_| tighter.is_some());
    Ok(())
}
fn nth<'a>(
    body: &'a [Statement],
    index: &mut usize,
    w: &Work,
) -> Result<Option<(usize, &'a E)>, Error> {
    for statement in body {
        w.step()?;
        match statement {
            Statement::Assign(a) => {
                if *index == 0 {
                    return Ok(Some((a.state, &a.rhs)));
                }
                *index -= 1;
            }
            Statement::ArrayWrite { states, rhs, .. } => {
                for state in states {
                    w.step()?;
                    if *index == 0 {
                        return Ok(Some((*state, rhs)));
                    }
                    *index -= 1;
                }
            }
            Statement::If {
                then_body,
                else_body,
                ..
            } => {
                if let Some(a) = nth(then_body, index, w)? {
                    return Ok(Some(a));
                }
                if let Some(a) = nth(else_body, index, w)? {
                    return Ok(Some(a));
                }
            }
            Statement::Loop {
                initialize,
                body,
                update,
                ..
            } => {
                for part in [initialize, body, update] {
                    if let Some(a) = nth(part, index, w)? {
                        return Ok(Some(a));
                    }
                }
            }
            _ => (),
        }
    }
    Ok(None)
}
pub(crate) fn assignment<'a>(
    model: &'a EventModel,
    event: usize,
    index: usize,
    w: &Work,
) -> Result<(usize, &'a E), Error> {
    w.debit(2, 0)?;
    w.step()?;
    nth(&model.program.events[event].body, &mut index.clone(), w)?.ok_or_else(|| {
        Error::new(
            "event_condition",
            "selected proof assignment is outside original body",
        )
    })
}
pub(crate) fn apply(
    model: &EventModel,
    selection: &crate::event_conditions::Selection,
    inputs: &[I],
    before: &[I],
    after: &[I],
    context: &Context<'_>,
    w: &Work,
) -> Result<Proofs, Error> {
    storage::<I>(model.program.nodes.len(), w)?;
    let mut nodes = vec![
        I {
            lo: f64::NEG_INFINITY,
            hi: f64::INFINITY
        };
        model.program.nodes.len()
    ];
    nodes[0] = I::ZERO;
    for (&index, value) in crate::analytic_request::proof_owner(model)
        .expect("paid apply role")
        .input_nodes()
        .iter()
        .zip(inputs)
    {
        w.step()?;
        nodes[index] = *value
    }
    let initial = local_new(before, context)?;
    let mut result = Proofs::new();
    for (state, v) in initial.exact.iter().enumerate() {
        w.step()?;
        if let Some(v) = v {
            let mut p = Paid::new(w);
            let copied = p.copy(v);
            if let Some(v) = p.finish(copied)? {
                insert(&mut result, state, v, w)?
            }
        }
    }
    for (event, indices) in &selection.actions {
        w.step()?;
        let mut local = initial.try_clone()?;
        for &index in indices {
            w.step()?;
            let (state, e) = assignment(model, *event, index, w)?;
            let exact = value(&local, e, &nodes, w)?;
            let mut p = Paid::new(w);
            let copy = exact.as_ref().and_then(|v| p.copy(v));
            local.exact[state] = p.finish(copy)?;
            remove(&mut result, state, w)?;
            if let Some(v) = exact {
                insert(&mut result, state, v, w)?
            }
        }
    }
    let mut checked = Proofs::new();
    for (state, value) in result {
        w.step()?;
        if let Some(b) = after.get(state) {
            if crate::exact_source::enclosure_with_work(&value, w)?
                .is_some_and(|i| b.lo <= i.lo && i.hi <= b.hi)
            {
                insert(&mut checked, state, value, w)?
            }
        }
    }
    Ok(checked)
}

pub(crate) fn points(bounds: &[I], w: &Work) -> Result<LocalState, Error> {
    w.debit(2, 0)?;
    w.step()?;
    let empty = Proofs::new();
    let c = Context {
        states: &empty,
        nodes: vec![],
        operators: vec![],
        floor_work: None,
        history_work: Some(w.clone()),
        floor_bounds: None,
    };
    let mut local = local_new(bounds, &c)?;
    local.nodes = None;
    Ok(local)
}
pub(crate) fn assign_point(
    local: &mut LocalState,
    state: usize,
    e: &E,
    w: &Work,
) -> Result<(), Error> {
    local.exact[state] = value(local, e, &[], w)?;
    Ok(())
}

pub(crate) fn held_value(
    e: &E,
    program: &crate::ir::Program,
    bounds: &[I],
    proofs: Option<&Proofs>,
    w: &Work,
) -> Result<Option<R>, Error> {
    w.debit(2, 0)?;
    storage::<I>(program.nodes.len() + program.operators.len(), w)?;
    let nodes = vec![I::ZERO; program.nodes.len()];
    let operators = vec![I::ZERO; program.operators.len()];
    let selected = crate::history_admission::resolve_expression(e, &nodes, bounds, &operators, w)?;
    storage::<Option<R>>(program.nodes.len(), w)?;
    w.step()?;
    let empty = Proofs::new();
    let context = Context {
        states: proofs.unwrap_or(&empty),
        nodes: vec![None; program.nodes.len()],
        operators: vec![],
        floor_work: None,
        history_work: Some(w.clone()),
        floor_bounds: None,
    };
    let local = local_new(bounds, &context)?;
    value(&local, &selected, &nodes, w)
}
