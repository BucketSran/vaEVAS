//! Optional exact values local to one event-path proof. Unknown incoming boxes
//! remain unknown; rational certificates never replace inherited uncertainty.
use crate::exact_source::{binary, enclosure, Budget};
use crate::interval::Interval as I;
use crate::ir::{EventMathFunction as F, Expression as E};
use num_rational::BigRational as R;
use num_traits::{Signed, Zero};

pub(crate) type Proofs = std::collections::BTreeMap<usize, R>;

pub(crate) struct Context<'a> {
    states: &'a Proofs,
    nodes: Vec<Option<R>>,
    operators: Vec<I>,
}
impl<'a> Context<'a> {
    pub(crate) fn with_operators(&self, operators: &[I]) -> Self {
        Self {
            states: self.states,
            nodes: self.nodes.clone(),
            operators: operators.to_vec(),
        }
    }
    pub(crate) fn operators(&self) -> &[I] {
        &self.operators
    }
    pub(crate) fn new(
        model: &crate::events::EventModel,
        trajectory: &crate::pwl::Trajectory,
        inputs: &[I],
        states: &'a Proofs,
        root: Option<&crate::exact_source::RootTime>,
    ) -> Self {
        let mut nodes = vec![None; model.program.nodes.len()];
        nodes[0] = binary(0.);
        for (k, (name, &bounds)) in model.driven.iter().zip(inputs).enumerate() {
            let original = root
                .and_then(|r| trajectory.exact_sources.get(k)?.as_ref()?.at_root(r))
                .filter(|v| enclosure(v).is_some_and(|i| bounds.lo <= i.lo && i.hi <= bounds.hi));
            nodes[model.program.nodes.iter().position(|n| n == name).unwrap()] =
                original.or_else(|| point(bounds));
        }
        Self {
            states,
            nodes,
            operators: Vec::new(),
        }
    }
}

#[derive(Clone)]
pub(crate) struct LocalState {
    bounds: Vec<I>,
    exact: Vec<Option<R>>,
    nodes: Option<Vec<Option<R>>>,
}
impl std::ops::Deref for LocalState {
    type Target = [I];
    fn deref(&self) -> &[I] {
        &self.bounds
    }
}
impl LocalState {
    pub(crate) fn new(bounds: &[I]) -> Self {
        Self {
            bounds: bounds.to_vec(),
            exact: bounds.iter().map(|v| point(*v)).collect(),
            nodes: None,
        }
    }
    pub(crate) fn with_context(bounds: &[I], context: Option<&Context<'_>>) -> Self {
        let mut local = Self::with_proofs(bounds, context.map(|c| c.states));
        local.nodes = context.map(|c| c.nodes.clone());
        local
    }
    pub(crate) fn with_proofs(bounds: &[I], proofs: Option<&Proofs>) -> Self {
        let mut local = Self::new(bounds);
        if let Some(proofs) = proofs {
            for (&state, value) in proofs {
                if let Some(b) = bounds.get(state) {
                    if enclosure(value).is_some_and(|v| b.lo <= v.lo && v.hi <= b.hi) {
                        local.exact[state] = Some(value.clone());
                    }
                }
            }
        }
        local
    }
    pub(crate) fn assign(&mut self, state: usize, expr: &E, nodes: &[I], bounds: I) {
        let exact = self.value(expr, nodes);
        // A proof is optional. The ordinary interval path still owns finite,
        // domain and resource diagnostics and remains the conservative fallback.
        let tighter = exact
            .as_ref()
            .and_then(enclosure)
            .filter(|v| bounds.lo <= v.lo && v.hi <= bounds.hi);
        self.bounds[state] = tighter.unwrap_or(bounds);
        self.exact[state] = exact.filter(|_| tighter.is_some());
    }
    pub(crate) fn merge(&mut self, yes: Self, no: &Self) {
        *self = yes;
        for (a, b) in self.exact.iter_mut().zip(&no.exact) {
            if *a != *b {
                *a = None;
            }
        }
    }
    pub(crate) fn value(&self, expr: &E, nodes: &[I]) -> Option<R> {
        self.value_with_work(expr, nodes, &mut || Some(()))
            .ok()
            .flatten()
    }
    /// Charge a caller's aggregate allowance before each visited node and
    /// exact arithmetic operation, retaining the evaluator's per-expression
    /// limits. Unknown provenance is distinct from an exhausted allowance.
    pub(crate) fn value_with_work<W: FnMut() -> Option<()>>(
        &self,
        expr: &E,
        nodes: &[I],
        work: &mut W,
    ) -> Result<Option<R>, ()> {
        let mut exhausted = false;
        let result = evaluate(
            expr,
            nodes,
            &self.exact,
            self.nodes.as_deref(),
            &mut Budget(0),
            0,
            &mut 0,
            &mut || {
                let result = work();
                exhausted |= result.is_none();
                result
            },
        );
        if exhausted {
            Err(())
        } else {
            Ok(result)
        }
    }
    /// Ordinary event/time proof retains its existing per-expression allowance.
    pub(crate) fn assign_proof(&mut self, state: usize, expr: &E, nodes: &[I]) {
        self.exact[state] = self.value(expr, nodes);
    }
    /// Replay optional scalar provenance in a private proof frame. Aggregate
    /// exhaustion must stop replay, rather than merely clearing one value.
    pub(crate) fn assign_proof_with_work<W: FnMut() -> Option<()>>(
        &mut self,
        state: usize,
        expr: &E,
        nodes: &[I],
        work: &mut W,
    ) -> Result<(), ()> {
        self.exact[state] = self.value_with_work(expr, nodes, work)?;
        Ok(())
    }
}
fn point(v: I) -> Option<R> {
    (v.lo == v.hi).then(|| binary(v.lo)).flatten()
}
#[allow(clippy::too_many_arguments)]
fn evaluate<W: FnMut() -> Option<()>>(
    e: &E,
    nodes: &[I],
    states: &[Option<R>],
    node_proofs: Option<&[Option<R>]>,
    budget: &mut Budget,
    depth: usize,
    count: &mut usize,
    work: &mut W,
) -> Option<R> {
    work()?;
    *count += 1;
    if depth > 64 || *count > 512 {
        return None;
    }
    match e {
        E::Affine { constant, terms } => {
            if terms.len() > 512 {
                return None;
            }
            let mut value = binary(*constant)?;
            for term in terms {
                work()?;
                if term.node == 0 {
                    continue;
                }
                let v = node_proofs
                    .and_then(|p| p.get(term.node))
                    .and_then(|v| v.clone())
                    .or_else(|| point(*nodes.get(term.node)?))?;
                work()?;
                let product = budget.check(binary(term.coefficient)? * v)?;
                work()?;
                value = budget.check(value + product)?;
            }
            Some(value)
        }
        E::State { state } => budget.check(states.get(*state)?.as_ref()?.clone()),
        E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
            let a = evaluate(
                left,
                nodes,
                states,
                node_proofs,
                budget,
                depth + 1,
                count,
                work,
            )?;
            let b = evaluate(
                right,
                nodes,
                states,
                node_proofs,
                budget,
                depth + 1,
                count,
                work,
            )?;
            work()?;
            if matches!(e, E::Add { .. }) {
                budget.check(a + b)
            } else if matches!(e, E::Multiply { .. }) {
                budget.check(a * b)
            } else if b.is_zero() {
                None
            } else {
                budget.check(a / b)
            }
        }
        E::Power { base, exponent } if *exponent <= 32 => {
            let a = evaluate(
                base,
                nodes,
                states,
                node_proofs,
                budget,
                depth + 1,
                count,
                work,
            )?;
            let mut result = binary(1.)?;
            for _ in 0..*exponent {
                work()?;
                result = budget.check(result * &a)?;
            }
            Some(result)
        }
        E::EventMath { function, args, .. } => {
            let a = evaluate(
                args.first()?,
                nodes,
                states,
                node_proofs,
                budget,
                depth + 1,
                count,
                work,
            )?;
            match function {
                F::Abs if args.len() == 1 => {
                    work()?;
                    budget.check(a.abs())
                }
                F::Min | F::Max if args.len() == 2 => {
                    let b = evaluate(
                        &args[1],
                        nodes,
                        states,
                        node_proofs,
                        budget,
                        depth + 1,
                        count,
                        work,
                    )?;
                    work()?;
                    budget.check(if matches!(function, F::Min) {
                        a.min(b)
                    } else {
                        a.max(b)
                    })
                }
                _ => None,
            }
        }
        _ => None,
    }
}

/// Replay the selected original assignments in a private proof frame. Every
/// block starts from the same old state; unsupported writes clear provenance.
pub(crate) fn apply(
    model: &crate::events::EventModel,
    selection: &crate::event_conditions::Selection,
    inputs: &[I],
    before: &[I],
    after: &[I],
    context: &Context<'_>,
) -> Proofs {
    let nodes = crate::causal_event::input_nodes(model, inputs);
    let initial = LocalState::with_context(before, Some(context));
    let mut result = initial
        .exact
        .iter()
        .enumerate()
        .filter_map(|(s, v)| Some((s, v.clone()?)))
        .collect::<Proofs>();
    for (event, indices) in &selection.actions {
        let mut local = initial.clone();
        let assignments = model.program.events[*event].assignments();
        for &index in indices {
            let a = &assignments[index];
            let exact = local.value(&a.rhs, &nodes);
            local.exact[a.state] = exact.clone();
            result.remove(&a.state);
            if let Some(value) = exact {
                result.insert(a.state, value);
            }
        }
    }
    result.retain(|s, value| {
        after
            .get(*s)
            .is_some_and(|b| enclosure(value).is_some_and(|v| b.lo <= v.lo && v.hi <= b.hi))
    });
    result
}

pub(crate) fn valid(proofs: &Proofs, bounds: &[I]) -> bool {
    proofs.iter().all(|(state, value)| {
        bounds
            .get(*state)
            .is_some_and(|b| enclosure(value).is_some_and(|v| b.lo <= v.lo && v.hi <= b.hi))
    })
}
