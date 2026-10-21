//! Immutable original-source proof and one call site's held-target limiter.
//! Source partition work belongs to the same request pool as Transition.
use crate::exact_source::RootTime;
use crate::interval::Interval as I;
use crate::ir::{Error, Expression};
use crate::slew::HeldSlew;
use crate::transition_source_plan::{Cut, Plan, ProofContext, Spec};
use std::sync::Arc;

pub(crate) fn selected(expression: &Expression) -> bool {
    match expression {
        Expression::Select { .. } => true,
        Expression::Add { left, right }
        | Expression::Multiply { left, right }
        | Expression::Divide { left, right } => selected(left) || selected(right),
        Expression::Power { base, .. } => selected(base),
        _ => false,
    }
}

/// A selected slew whose sources occur only in Select predicates. Every
/// numerical value leaf is a constant or held state, so a shaped physical
/// source can decide cuts but never supplies a value, even with zero weight.
pub(crate) fn predicate_only_sources(expression: &Expression) -> bool {
    fn value(e: &Expression) -> bool {
        match e {
            Expression::Affine { terms, .. } => terms.is_empty(),
            Expression::State { .. } => true,
            Expression::Select {
                then_value,
                else_value,
                ..
            } => value(then_value) && value(else_value),
            Expression::Add { left, right }
            | Expression::Multiply { left, right }
            | Expression::Divide { left, right } => value(left) && value(right),
            Expression::Power { base, .. } => value(base),
            _ => false,
        }
    }
    selected(expression) && value(expression)
}

#[derive(Clone)]
pub(crate) struct SourceSlew {
    plan: Arc<Plan>,
    history: HeldSlew,
    // Per-cut paid enclosure of exact_root - representative, computed once.
    offsets: Arc<[std::sync::OnceLock<Option<I>>]>,
}
impl SourceSlew {
    pub(crate) fn new(
        expression: &Expression,
        context: Arc<ProofContext>,
        owner: &str,
        state_values: &[f64],
        rise: f64,
        fall: f64,
    ) -> Result<Self, Error> {
        // The shared context binds the original program/source mapping and
        // quota. DC normalization audits the original tree before substituting
        // target leaves; predicates and their physical root identities survive.
        let (expression, factor) = context.slew_admission(expression, owner)?;
        let spec = Spec::source_slew_with_context(&expression, context, owner, factor)?
            .ok_or_else(|| {
                Error::new(
                    "unsupported_operator",
                    "selected slew needs original-source predicates",
                )
            })?;
        let bounds: Vec<_> = state_values.iter().copied().map(I::point).collect();
        let plan = Arc::new(Plan::build_for_slew(spec, &bounds)?);
        let seed = plan.slew_seed()?;
        // The terminal cut is the original context's finite stop, not an
        // independently supplied horizon that could mismatch this proof.
        let stop = plan.cuts().last().unwrap().time;
        plan.charge_slew_build()?;
        let mut targets = Vec::with_capacity(plan.cuts().len());
        for cut in plan.cuts() {
            plan.debit_boundary()?;
            let target = plan.slew_target_after(&cut.exact)?;
            targets.push((cut.clone(), target.value, target.bounds));
        }
        let history = HeldSlew::new((seed.value, seed.bounds), targets, rise, fall, stop)?;
        let offsets = (0..plan.cuts().len())
            .map(|_| std::sync::OnceLock::new())
            .collect();
        Ok(Self {
            plan,
            history,
            offsets,
        })
    }
    pub(crate) fn value(&self, time: f64) -> Result<f64, Error> {
        self.history.value(time)
    }
    pub(crate) fn bounds(&self, time: f64) -> Result<I, Error> {
        self.range(I::point(time))
    }
    pub(crate) fn range(&self, time: I) -> Result<I, Error> {
        let window = self.history.range(time)?;
        if time.lo != time.hi || window.lo == window.hi {
            return Ok(window);
        }
        // A point after a cut whose binary64 window is wider than the
        // limiter's resolution: locate the exact cut once (paid) and use it.
        let Some(index) = self.history.point_epoch(time.lo) else {
            return Ok(window);
        };
        let offset = match self.offsets[index].get() {
            Some(offset) => *offset,
            None => {
                let offset = self.plan.exact_cut_offset(index)?;
                let _ = self.offsets[index].set(offset);
                offset
            }
        };
        match offset {
            Some(offset) => self.history.point_range_with_offset(time.lo, index, offset),
            None => Ok(window),
        }
    }
    pub(crate) fn next_breakpoint(&self, after: f64) -> Option<f64> {
        self.history.next_breakpoint(after)
    }
    pub(crate) fn cuts(&self) -> &[Cut] {
        self.plan.cuts()
    }
    pub(crate) fn cut_at(&self, time: f64) -> Option<&Cut> {
        self.plan.cut_at(time)
    }
    pub(crate) fn check_incoming(
        &self,
        after: f64,
        window: I,
        root: Option<&RootTime>,
    ) -> Result<(), Error> {
        self.plan.check_incoming(after, window, root)
    }
    pub(crate) fn same_history(&self, other: &Self) -> bool {
        Arc::ptr_eq(&self.plan, &other.plan) && self.history.same_history(&other.history)
    }
}
