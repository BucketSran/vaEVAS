//! Optional exact values local to one event-path proof. Unknown incoming boxes
//! remain unknown; rational certificates never replace inherited uncertainty.
use crate::exact_source::{binary, enclosure, Budget};
use crate::interval::Interval as I;
use crate::ir::{EventMathFunction as F, Expression as E};
use num_rational::BigRational as R;
use num_traits::{Signed, Zero};
#[path = "event_history_proof.rs"]
pub(crate) mod history;

pub(crate) type Proofs = std::collections::BTreeMap<usize, R>;

pub(crate) struct Context<'a> {
    states: &'a Proofs,
    nodes: Vec<Option<R>>,
    operators: Vec<I>,
    floor_work: Option<crate::transition_source_plan::Work>,
    history_work: Option<crate::transition_source_plan::Work>,
    floor_bounds: Option<Vec<I>>,
}
impl<'a> Context<'a> {
    // Identity, not equality: two different accepted Frames can contain two
    // distinct exact rationals inside the same outward-rounded interval.
    pub(crate) fn proof_identity(&self) -> *const Proofs {
        self.states as *const Proofs
    }

    pub(crate) fn floor_work(&self) -> Option<&crate::transition_source_plan::Work> {
        self.floor_work.as_ref()
    }

    pub(crate) fn try_new(
        model: &crate::events::EventModel,
        trajectory: &crate::pwl::Trajectory,
        inputs: &[I],
        states: &'a Proofs,
        root: Option<&crate::exact_source::RootTime>,
    ) -> Result<Self, crate::ir::Error> {
        if crate::analytic_request::proof_owner(model).is_some() {
            return history::context_new(model, trajectory, inputs, states, root);
        }
        if let Some(request) = &model.floor_source {
            request.check_source(trajectory)?;
            // Context::new invokes at_root at most once per actual driven input.
            // The helper keeps its local200000 cap, reserved before invocation.
            if root.is_some() {
                crate::event_floor::charge(
                    request.work(),
                    model.driven.len().saturating_add(1).saturating_mul(8),
                    "floor_source_binding_scan",
                )?;
                let calls = trajectory
                    .exact_sources
                    .iter()
                    .zip(inputs)
                    .take(model.driven.len())
                    .filter(|(source, bounds)| {
                        source.is_some() && !(bounds.finite() && bounds.lo == bounds.hi)
                    })
                    .count();
                crate::event_floor::charge(
                    request.work(),
                    200000 * calls,
                    "floor_source_helper_reservations",
                )?;
                crate::diagnostics::counter("floor_source_helper_calls", calls);
            }
            crate::event_floor::charge(
                request.work(),
                144 * (model.program.nodes.len() + states.len() + inputs.len() + 1),
                "floor_source_copy",
            )?;
            crate::event_floor::charge(
                request.work(),
                1024 * (states.len() + inputs.len()),
                "floor_source_exact_enclosure",
            )?;
        }
        let indices = model
            .floor_source
            .as_ref()
            .map(|r| r.input_nodes())
            .transpose()?;
        let mut result = if indices.is_some() {
            Self::build(model, trajectory, inputs, states, root, indices)
        } else {
            Self::new(model, trajectory, inputs, states, root)
        };
        result.floor_work = model.floor_source.as_ref().map(|r| r.work().clone());
        if result.floor_work.is_some() {
            let mut b = vec![
                I {
                    lo: f64::NEG_INFINITY,
                    hi: f64::INFINITY
                };
                model.program.nodes.len()
            ];
            b[0] = I::ZERO;
            for (&node, &v) in indices.unwrap().iter().zip(inputs) {
                b[node] = v;
            }
            result.floor_bounds = Some(b);
        }
        Ok(result)
    }
    pub(crate) fn try_with_operators(&self, operators: &[I]) -> Result<Self, crate::ir::Error> {
        if self.history_work.is_some() {
            return history::context_operators(self, operators);
        }
        if let Some(w) = &self.floor_work {
            crate::event_floor::charge(
                w,
                self.nodes.len().saturating_add(1),
                "floor_source_binding_scan",
            )?;
            let limbs = self
                .nodes
                .iter()
                .flatten()
                .map(|r| 1 + (r.numer().bits() + r.denom().bits()).div_ceil(64) as usize)
                .sum::<usize>();
            crate::event_floor::charge(
                w,
                limbs + operators.len() + self.nodes.len() * 2 + 1,
                "floor_source_copy",
            )?;
        }
        Ok(self.with_operators(operators))
    }

    pub(crate) fn with_operators(&self, operators: &[I]) -> Self {
        Self {
            states: self.states,
            nodes: self.nodes.clone(),
            operators: operators.to_vec(),
            floor_work: self.floor_work.clone(),
            history_work: self.history_work.clone(),
            floor_bounds: self.floor_bounds.clone(),
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
        Self::build(model, trajectory, inputs, states, root, None)
    }
    fn build(
        model: &crate::events::EventModel,
        trajectory: &crate::pwl::Trajectory,
        inputs: &[I],
        states: &'a Proofs,
        root: Option<&crate::exact_source::RootTime>,
        indices: Option<&[usize]>,
    ) -> Self {
        let mut nodes = vec![None; model.program.nodes.len()];
        nodes[0] = binary(0.);
        for (k, (name, &bounds)) in model.driven.iter().zip(inputs).enumerate() {
            // A finite inherited singleton already certifies this exact binary
            // value. The old root result could only be used if enclosed by
            // that same singleton, so both rational values would be equal.
            // Restrict this order to the source Floor consumer. Nonpoint boxes
            // and every legacy caller retain their original root proof.
            let value = if indices.is_some() && bounds.finite() && bounds.lo == bounds.hi {
                point(bounds)
            } else {
                root.and_then(|r| trajectory.exact_sources.get(k)?.as_ref()?.at_root(r))
                    .filter(|v| {
                        enclosure(v).is_some_and(|i| bounds.lo <= i.lo && i.hi <= bounds.hi)
                    })
                    .or_else(|| point(bounds))
            };
            let node = indices.map_or_else(
                || model.program.nodes.iter().position(|n| n == name).unwrap(),
                |indices| indices[k],
            );
            nodes[node] = value;
        }
        Self {
            states,
            nodes,
            operators: Vec::new(),
            floor_work: None,
            history_work: None,
            floor_bounds: None,
        }
    }
}

#[derive(Clone)]
pub(crate) struct LocalState {
    bounds: Vec<I>,
    exact: Vec<Option<R>>,
    nodes: Option<Vec<Option<R>>>,
    floor_work: Option<crate::transition_source_plan::Work>,
    history_work: Option<crate::transition_source_plan::Work>,
    floor_bounds: Option<Vec<I>>,
}
impl std::ops::Deref for LocalState {
    type Target = [I];
    fn deref(&self) -> &[I] {
        &self.bounds
    }
}
impl LocalState {
    /// Only the strict point-lineage consumer supplies these source proofs.
    /// Unlike legacy constructors, singleton bounds do not manufacture proof.
    pub(crate) fn strict_point_lineage(
        bounds: &[I],
        proofs: &Proofs,
        nodes: Vec<Option<R>>,
        work: &crate::transition_source_plan::Work,
    ) -> Result<Option<Self>, crate::ir::Error> {
        work.debit(
            2,
            (16 + bounds.len() * 4 + nodes.len() * 2 + proofs.len() * 4) as u64,
        )?;
        for value in proofs.values() {
            work.step()?;
            let bits = value.numer().bits().saturating_add(value.denom().bits());
            work.debit(2, 1 + bits.div_ceil(64))?;
            if value.numer().bits() > crate::exact_source::MAX_BITS
                || value.denom().bits() > crate::exact_source::MAX_BITS
            {
                return Ok(None);
            }
        }
        if !valid_with_work(proofs, bounds, work)? {
            return Ok(None);
        }
        let mut exact = vec![None; bounds.len()];
        for (&state, value) in proofs {
            // All limb copying was reserved before cloning or allocating.
            exact[state] = Some(value.clone());
        }
        Ok(Some(Self {
            bounds: bounds.to_vec(),
            exact,
            nodes: Some(nodes),
            floor_work: None,
            history_work: None,
            floor_bounds: None,
        }))
    }

    fn prepay_copy(&self) -> Result<(), crate::ir::Error> {
        if self.history_work.is_some() {
            return history::charge_local_copy(self);
        }
        if let Some(w) = &self.floor_work {
            let mut items = 16
                + self.bounds.len() * 4
                + self.exact.len()
                + self.nodes.as_ref().map_or(0, Vec::len)
                + self.floor_bounds.as_ref().map_or(0, Vec::len);
            for r in self
                .exact
                .iter()
                .flatten()
                .chain(self.nodes.iter().flatten().flatten())
            {
                crate::event_floor::charge(w, 1, "floor_source_ast")?;
                items += 8 + (r.numer().bits() + r.denom().bits()).div_ceil(64) as usize;
            }
            crate::event_floor::charge(w, items, "floor_source_copy")?;
        }
        Ok(())
    }
    pub(crate) fn try_clone(&self) -> Result<Self, crate::ir::Error> {
        self.prepay_copy()?;
        Ok(self.clone())
    }
    pub(crate) fn try_value(&self, e: &E, nodes: &[I]) -> Result<Option<R>, crate::ir::Error> {
        if let Some(w) = self.history_work.as_ref() {
            return history::value(self, e, nodes, w);
        }
        let Some(w) = &self.floor_work else {
            return Ok(self.value(e, nodes));
        };
        // Retain the old exact evaluator's local cap. Prepay every rational
        // clone it can perform before invoking it, including state/source limbs.
        let size = crate::event_floor::encoded_size(e, w)?;
        crate::event_floor::charge(w, size * 144, "floor_source_copy")?;
        self.value_with_work(e, nodes, &mut || {
            crate::event_floor::charge(w, 1, "floor_source_exact_ops").ok()
        })
        .map_err(|_| crate::ir::Error::new("step_budget", "source floor provenance work exhausted"))
    }
    pub(crate) fn prepay_comparison(&self, other: &Self) -> Result<(), crate::ir::Error> {
        if self.history_work.is_some() {
            return history::charge_local_comparison(self, other);
        }
        if let Some(w) = &self.floor_work {
            crate::event_floor::charge(
                w,
                144 * (self.len() + other.len() + 1),
                "floor_source_identity_debit",
            )?;
        }
        Ok(())
    }
    pub(crate) fn history_work(&self) -> Option<&crate::transition_source_plan::Work> {
        self.history_work.as_ref()
    }
    pub(crate) fn try_enclosure(&self, value: &R) -> Result<Option<I>, crate::ir::Error> {
        if let Some(w) = &self.history_work {
            crate::exact_source::enclosure_with_work(value, w)
        } else {
            Ok(enclosure(value))
        }
    }
    pub(crate) fn floor_bound(&self, n: usize) -> Option<I> {
        self.floor_bounds.as_ref()?.get(n).copied()
    }
    pub(crate) fn floor_work(&self) -> Option<&crate::transition_source_plan::Work> {
        self.floor_work.as_ref()
    }
    pub(crate) fn floor_node(&self, n: usize) -> Option<&R> {
        self.nodes.as_ref()?.get(n)?.as_ref()
    }
    pub(crate) fn try_with_context(
        bounds: &[I],
        context: Option<&Context<'_>>,
    ) -> Result<Self, crate::ir::Error> {
        if context.is_some_and(|c| c.history_work.is_some()) {
            return history::local_new(bounds, context.unwrap());
        }
        if let Some(w) = context.and_then(|c| c.floor_work.as_ref()) {
            let c = context.unwrap();
            crate::event_floor::charge(
                w,
                c.nodes
                    .len()
                    .saturating_add(c.states.len())
                    .saturating_add(1),
                "floor_source_binding_scan",
            )?;
            let limbs = c
                .nodes
                .iter()
                .flatten()
                .chain(c.states.values())
                .map(|r| 1 + (r.numer().bits() + r.denom().bits()).div_ceil(64) as usize)
                .sum::<usize>();
            crate::event_floor::charge(
                w,
                limbs + c.nodes.len() * 2 + bounds.len() * 4 + 1,
                "floor_source_copy",
            )?;
            crate::event_floor::charge(w, 1024 * c.states.len(), "floor_source_exact_enclosure")?;
        }
        Ok(Self::with_context(bounds, context))
    }

    pub(crate) fn new(bounds: &[I]) -> Self {
        Self {
            bounds: bounds.to_vec(),
            exact: bounds.iter().map(|v| point(*v)).collect(),
            nodes: None,
            floor_work: None,
            history_work: None,
            floor_bounds: None,
        }
    }
    pub(crate) fn with_context(bounds: &[I], context: Option<&Context<'_>>) -> Self {
        let mut local = Self::with_proofs(bounds, context.map(|c| c.states));
        local.nodes = context.map(|c| c.nodes.clone());
        local.floor_work = context.and_then(|c| c.floor_work.clone());
        local.floor_bounds = context.and_then(|c| c.floor_bounds.clone());
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
    pub(crate) fn try_assign(
        &mut self,
        state: usize,
        expr: &E,
        nodes: &[I],
        bounds: I,
    ) -> Result<(), crate::ir::Error> {
        if self.history_work.is_some() {
            return history::assign(self, state, expr, nodes, bounds);
        }
        let has_floor = if let Some(w) = self.floor_work() {
            crate::event_floor::contains_charged(expr, w)?
        } else {
            false
        };
        if has_floor {
            let e = crate::event_floor::resolve(expr, nodes, self)?;
            let w = self
                .floor_work
                .as_ref()
                .ok_or_else(|| {
                    crate::ir::Error::new("event_condition", "source floor assignment lacks owner")
                })?
                .clone();
            let exact = self.try_value(&e, nodes)?;
            crate::event_floor::charge(&w, 1024, "floor_source_exact_enclosure")?;
            let tighter = exact
                .as_ref()
                .and_then(enclosure)
                .filter(|v| bounds.lo <= v.lo && v.hi <= bounds.hi);
            self.bounds[state] = tighter.unwrap_or(bounds);
            self.exact[state] = exact.filter(|_| tighter.is_some());
        } else if self.floor_work.is_some() {
            let exact = self.try_value(expr, nodes)?;
            if let Some(w) = &self.floor_work {
                crate::event_floor::charge(w, 1024, "floor_source_exact_enclosure")?;
            }
            let tighter = exact
                .as_ref()
                .and_then(enclosure)
                .filter(|v| bounds.lo <= v.lo && v.hi <= bounds.hi);
            self.bounds[state] = tighter.unwrap_or(bounds);
            self.exact[state] = exact.filter(|_| tighter.is_some());
        } else {
            self.assign(state, expr, nodes, bounds);
        }
        Ok(())
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
            #[cfg(test)]
            if let (Some(a), Some(b)) = (a.as_ref(), b.as_ref()) {
                crate::diagnostics::counter(
                    "history_merge_large_pairs",
                    usize::from(
                        a.numer()
                            .bits()
                            .max(a.denom().bits())
                            .max(b.numer().bits())
                            .max(b.denom().bits())
                            > 512,
                    ),
                );
            }
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
        E::IntegerPrimitive {
            function,
            args,
            origin,
        } => {
            use num_traits::ToPrimitive;
            let mut visited = 0usize;
            let value = crate::integer_primitive::evaluate(
                *function,
                args,
                origin,
                &mut |state| {
                    let r = states
                        .get(state)
                        .and_then(|v| v.as_ref())
                        .filter(|r| r.is_integer())
                        .and_then(|r| r.to_integer().to_i32());
                    r.ok_or_else(|| {
                        crate::ir::Error::new("unknown_proof", "integer state proof missing")
                    })
                },
                &mut || {
                    visited += 1;
                    work().ok_or_else(|| {
                        crate::ir::Error::new("resource_budget", "integer proof work exhausted")
                    })?;
                    if *count + visited > 512 || depth + visited > 64 {
                        return Err(crate::ir::Error::new(
                            "unknown_proof",
                            "integer proof expression limit",
                        ));
                    }
                    Ok(())
                },
            )
            .ok()?;
            *count += visited;
            budget.check(binary(f64::from(value))?)
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
                F::Floor if args.len() == 1 => {
                    work()?;
                    budget.check(a.floor())
                }
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

/// Meter the source-request variant without changing old optional provenance.
pub(crate) fn apply_charged(
    model: &crate::events::EventModel,
    selection: &crate::event_conditions::Selection,
    inputs: &[I],
    before: &[I],
    after: &[I],
    context: &Context<'_>,
) -> Result<Proofs, crate::ir::Error> {
    if let Some(w) = context.history_work.as_ref() {
        return history::apply(model, selection, inputs, before, after, context, w);
    }
    let Some(w) = context.floor_work.as_ref() else {
        return Ok(apply(model, selection, inputs, before, after, context));
    };
    crate::event_floor::charge(w, model.program.nodes.len() + 1, "floor_source_copy")?;
    let nodes = crate::causal_event::input_nodes(model, inputs);
    let initial = LocalState::try_with_context(before, Some(context))?;
    initial.prepay_copy()?;
    let mut result = initial
        .exact
        .iter()
        .enumerate()
        .filter_map(|(s, v)| Some((s, v.clone()?)))
        .collect::<Proofs>();
    for (event, indices) in &selection.actions {
        let mut local = initial.try_clone()?;
        let body = &model.program.events[*event].body;
        let size = crate::event_floor::encoded_size(body, w)?;
        crate::event_floor::charge(w, size, "floor_source_copy")?;
        let assignments = model.program.events[*event].assignments();
        for &index in indices {
            let a = &assignments[index];
            let exact = if crate::event_floor::contains_charged(&a.rhs, w)? {
                let resolved = crate::event_floor::resolve(&a.rhs, &nodes, &local)?;
                local.try_value(&resolved, &nodes)?
            } else {
                local.try_value(&a.rhs, &nodes)?
            };
            crate::event_floor::charge(w, 144, "floor_source_copy")?;
            local.exact[a.state] = exact.clone();
            result.remove(&a.state);
            if let Some(value) = exact {
                result.insert(a.state, value);
            }
        }
    }
    crate::event_floor::charge(w, result.len() * 8, "floor_source_copy")?;
    let mut checked = Proofs::new();
    for (state, value) in result {
        crate::event_floor::charge(w, 1024, "floor_source_exact_enclosure")?;
        if after
            .get(state)
            .is_some_and(|b| enclosure(&value).is_some_and(|v| b.lo <= v.lo && v.hi <= b.hi))
        {
            checked.insert(state, value);
        }
    }
    Ok(checked)
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

/// exact old valid() semantics, only explicit original Work accounting added.
pub(crate) fn valid_with_work(
    proofs: &Proofs,
    bounds: &[I],
    w: &crate::transition_source_plan::Work,
) -> Result<bool, crate::ir::Error> {
    w.debit(2, 0)?;
    w.debit(
        2,
        (proofs.len() as u64).saturating_mul(16).saturating_add(16),
    )?;
    for (&state, value) in proofs {
        let Some(bound) = bounds.get(state) else {
            return Ok(false);
        };
        if !crate::exact_source::enclosure_with_work(value, w)?
            .is_some_and(|enclosure| bound.lo <= enclosure.lo && enclosure.hi <= bound.hi)
        {
            return Ok(false);
        }
    }
    Ok(true)
}

#[cfg(test)]
mod native_floor_tests {
    use super::*;
    #[test]
    fn negative_rational_floor_charges_existing_work_and_exhaustion_returns_unknown() {
        let local = LocalState {
            bounds: vec![],
            exact: vec![],
            nodes: Some(vec![binary(0.), Some(R::new((-1).into(), 3.into()))]),
            floor_work: None,
            history_work: None,
            floor_bounds: None,
        };
        let node = E::Affine {
            constant: 0.,
            terms: vec![crate::ir::Term {
                node: 1,
                coefficient: 1.,
            }],
        };
        let expr = E::EventMath {
            function: F::Floor,
            args: vec![node],
            origin: crate::ir::Origin {
                source: "floor.va".into(),
                line: 1,
                column: 1,
                instance: "dut".into(),
                expansion: vec![],
            },
        };
        let nodes = [
            I::ZERO,
            I {
                lo: -0.34,
                hi: -0.33,
            },
        ];
        assert_eq!(local.value(&expr, &nodes), binary(-1.));
        assert!(local.value_with_work(&expr, &nodes, &mut || None).is_err());
    }
}
