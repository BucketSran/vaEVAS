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

#[derive(Clone)]
pub(crate) struct SourceSlew {
    plan: Arc<Plan>,
    history: HeldSlew,
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
        let expression = context.slew_dc_leaves(expression, owner)?;
        let spec = Spec::new_with_context(&expression, context, owner)?.ok_or_else(|| {
            Error::new(
                "unsupported_operator",
                "selected slew needs original-source predicates",
            )
        })?;
        let bounds: Vec<_> = state_values.iter().copied().map(I::point).collect();
        let plan = Arc::new(Plan::build_for_slew(spec, &bounds)?);
        let seed = plan.seed();
        // The terminal cut is the original context's finite stop, not an
        // independently supplied horizon that could mismatch this proof.
        let stop = plan.cuts().last().unwrap().time;
        let mut targets = Vec::with_capacity(plan.cuts().len());
        for cut in plan.cuts() {
            plan.debit_boundary()?;
            let target = plan.slew_target_after(&cut.exact)?;
            targets.push((cut.clone(), target.value, target.bounds));
        }
        let history = HeldSlew::new((seed.value, seed.bounds), targets, rise, fall, stop)?;
        Ok(Self { plan, history })
    }
    pub(crate) fn value(&self, time: f64) -> Result<f64, Error> {
        self.history.value(time)
    }
    pub(crate) fn bounds(&self, time: f64) -> Result<I, Error> {
        self.history.range(I::point(time))
    }
    pub(crate) fn range(&self, time: I) -> Result<I, Error> {
        self.history.range(time)
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
