//! Candidate-owned cursor over an immutable piecewise-held source proof.
//! Cloning an Operators candidate does not publish this cursor or its target.
use crate::exact_source::RootTime;
use crate::interval::Interval as I;
use crate::ir::Error;
use crate::transition_source_plan::{Cut, Plan, Spec, Target};
use std::sync::Arc;

#[derive(Clone)]
pub(crate) struct Source {
    spec: Arc<Spec>,
    plan: Plan,
    certified: Vec<Plan>,
    target: Target,
    time: f64,
    last_root: Option<RootTime>,
    last_window: I,
}

pub(crate) struct Prepared {
    pub(crate) source: Source,
    pub(crate) target: Target,
    pub(crate) changed: bool,
    pub(crate) time_bounds: I,
    pub(crate) exact_root: Option<RootTime>,
}

impl Source {
    /// Construction receives the already settled initial held state. Preserve
    /// the point seed separately from the right-hand target installed at zero.
    pub(crate) fn initialized(
        spec: Arc<Spec>,
        states: &[I],
    ) -> Result<(Self, Target, bool), Error> {
        let plan = Plan::build(spec.clone(), states)?;
        let point = plan.seed();
        let right = plan.prepare(0., &point)?;
        let changed = !spec.equal_targets(&point, &right)?;
        Ok((
            Self {
                spec,
                certified: vec![plan.clone()],
                plan,
                target: right,
                time: 0.,
                last_root: RootTime::point(0.),
                last_window: I::ZERO,
            },
            point,
            changed,
        ))
    }
    pub(crate) fn target(&self) -> &Target {
        &self.target
    }
    pub(crate) fn cut_at(&self, time: f64) -> Option<&Cut> {
        self.plan.cut_at(time)
    }
    pub(crate) fn next_after(&self, time: f64) -> Option<f64> {
        self.plan.next_after(time)
    }
    pub(crate) fn cuts(&self) -> &[Cut] {
        self.plan.cuts()
    }
    pub(crate) fn check_incoming(
        &self,
        after: f64,
        bounds: I,
        root: Option<&RootTime>,
    ) -> Result<(), Error> {
        self.plan.check_incoming(after, bounds, root)
    }
    pub(crate) fn prepare(
        &self,
        time: f64,
        bounds: I,
        states: &[I],
        root: Option<&RootTime>,
    ) -> Result<Prepared, Error> {
        if !time.is_finite()
            || !bounds.finite()
            || bounds.lo > time
            || time > bounds.hi
            || time < self.time
        {
            return Err(Error::new(
                "event_consistency",
                "invalid source history advancement time",
            ));
        }
        // Final-history extension and queries may re-enter an already consumed
        // boundary at its upper representative. Reuse this candidate's exact
        // cut certificate only for the unchanged time; never a neighboring root.
        let effective_root = root.or_else(|| {
            (time == self.time && bounds == I::point(time))
                .then_some(self.last_root.as_ref())
                .flatten()
        });
        self.plan
            .check_incoming(self.time, bounds, effective_root)?;
        if self
            .plan
            .next_after(self.time)
            .is_some_and(|cut| cut < time)
        {
            return Err(Error::new(
                "event_consistency",
                "source history skipped a required physical boundary",
            ));
        }
        let mut cached = None;
        for plan in &self.certified {
            if plan.same_context(states)? {
                cached = Some(plan.clone());
                break;
            }
        }
        let next = match cached {
            Some(plan) => plan,
            None => self.plan.rebind(states)?,
        };
        let mut certified = self.certified.clone();
        if !certified.iter().any(|plan| plan.same_proof(&next)) {
            certified.push(next.clone());
        }

        next.check_incoming(self.time, bounds, effective_root)?;
        let unchanged = self.plan.same_proof(&next);
        if time == self.time && !unchanged {
            return Err(Error::new(
                "event_consistency",
                "changed source epoch at the same time requires previous frame replay",
            ));
        }
        let target = if unchanged && (!self.plan.due_at(time) || time == self.time) {
            self.target.clone()
        } else {
            next.prepare(time, &self.target)?
        };
        let changed = !target.same_certificate(&self.target)
            && !self.spec.equal_targets(&target, &self.target)?;
        let cut = next.cut_at(time);
        let time_bounds = cut.map_or(bounds, |cut| cut.bounds);
        let exact_root = cut
            .map(|cut| cut.exact.clone())
            .or_else(|| effective_root.cloned());
        Ok(Prepared {
            source: Self {
                spec: self.spec.clone(),
                plan: next,
                certified,
                target: target.clone(),
                time,
                last_root: exact_root.clone(),
                last_window: time_bounds,
            },
            target,
            changed,
            time_bounds,
            exact_root,
        })
    }
    /// Copy only successful immutable proofs into a replay candidate. History,
    /// target and cursor still start from the original accepted frame.
    pub(crate) fn reuse_certificates(&mut self, proven: &Self) -> Result<(), Error> {
        if !Arc::ptr_eq(&self.spec, &proven.spec) {
            return Err(Error::new(
                "invalid_ir",
                "source proof replay Spec mismatch",
            ));
        }
        for plan in &proven.certified {
            if !self.certified.iter().any(|old| old.same_proof(plan)) {
                self.certified.push(plan.clone());
            }
        }
        Ok(())
    }
    pub(crate) fn same_epoch(&self, other: &Self) -> bool {
        Arc::ptr_eq(&self.spec, &other.spec)
            && self.plan.same_proof(&other.plan)
            && self.target.same_certificate(&other.target)
            && self.time == other.time
            && self.certified.len() == other.certified.len()
            && self
                .certified
                .iter()
                .zip(&other.certified)
                .all(|(a, b)| a.same_proof(b))
            && self.last_root == other.last_root
            && self.last_window == other.last_window
    }
}
