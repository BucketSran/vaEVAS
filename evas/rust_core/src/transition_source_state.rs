//! Candidate-owned source target epochs. Immutable proofs are shared; physical
//! cursors and targets are committed only together with operator histories.
use crate::interval::Interval as I;
use crate::ir::Error;
use crate::transition_source_plan::{Plan, Spec, Target};
use std::sync::Arc;

#[derive(Clone)]
pub(crate) struct Source {
    spec: Arc<Spec>,
    phase: Phase,
}
#[derive(Clone)]
enum Phase {
    Pending {
        seed: Target,
    },
    Ready {
        plan: Plan,
        target: Target,
        time: f64,
    },
}
pub(crate) struct Prepared {
    pub(crate) source: Source,
    pub(crate) target: Target,
    pub(crate) changed: bool,
}
pub(crate) struct Initial {
    pub(crate) source: Source,
    pub(crate) point: Target,
    pub(crate) right: Target,
    pub(crate) changed: bool,
}
fn invalid(message: &str) -> Error {
    Error::new("event_consistency", message)
}
impl Source {
    pub(crate) fn pending(spec: Arc<Spec>, states: &[I]) -> Result<Self, Error> {
        let seed = spec.point_seed(states)?;
        Ok(Self {
            spec,
            phase: Phase::Pending { seed },
        })
    }
    pub(crate) fn provisional(&self) -> &Target {
        match &self.phase {
            Phase::Pending { seed } => seed,
            Phase::Ready { target, .. } => target,
        }
    }
    pub(crate) fn pending_initialization(&self) -> bool {
        matches!(self.phase, Phase::Pending { .. })
    }
    /// This prepares a new transaction. It never rewrites this Source or a
    /// Transition, and never reinitializes a Ready history at time zero.
    pub(crate) fn prepare_initialization(&self, states: &[I]) -> Result<Initial, Error> {
        if !self.pending_initialization() {
            return Err(invalid("source history is already initialized"));
        }
        let plan = Plan::build(self.spec.clone(), states)?;
        let point = plan.seed();
        let right = plan.prepare(0., &point)?;
        let changed = !self.spec.equal_targets(&point, &right)?;
        let source = Self {
            spec: self.spec.clone(),
            phase: Phase::Ready {
                plan,
                target: right.clone(),
                time: 0.,
            },
        };
        Ok(Initial {
            source,
            point,
            right,
            changed,
        })
    }
    pub(crate) fn cuts(&self) -> &[f64] {
        match &self.phase {
            Phase::Pending { .. } => &[],
            Phase::Ready { plan, .. } => plan.cuts(),
        }
    }
    pub(crate) fn next_after(&self, after: f64) -> Option<f64> {
        match &self.phase {
            Phase::Pending { .. } => None,
            Phase::Ready { plan, .. } => plan.next_after(after),
        }
    }
    pub(crate) fn check_incoming(&self, after: f64, bounds: I) -> Result<(), Error> {
        match &self.phase {
            Phase::Pending { .. } => Ok(()),
            Phase::Ready { plan, .. } => plan.check_incoming(after, bounds),
        }
    }
    /// Consume one physical boundary only after the held-state closure. Calls
    /// with the same epoch are idempotent; a different same-time epoch must be
    /// recomputed from its pre-boundary candidate, not appended to this queue.
    pub(crate) fn prepare(&self, time: f64, bounds: I, states: &[I]) -> Result<Prepared, Error> {
        let Phase::Ready {
            plan,
            target,
            time: old_time,
        } = &self.phase
        else {
            return Err(invalid(
                "source history requires initialization before advancement",
            ));
        };
        if !time.is_finite()
            || !bounds.finite()
            || bounds.lo > time
            || time > bounds.hi
            || time < *old_time
        {
            return Err(invalid("invalid source history advancement time"));
        }
        plan.check_incoming(*old_time, bounds)?;
        if plan.next_after(*old_time).is_some_and(|cut| cut < time) {
            return Err(invalid(
                "source history skipped a required physical boundary",
            ));
        }
        let next = plan.rebind(states)?;
        next.check_incoming(*old_time, bounds)?;
        let unchanged = plan.same_proof(&next);
        if time == *old_time && !unchanged {
            return Err(invalid(
                "changed source epoch at the same time requires replay from the previous frame",
            ));
        }
        let value = if unchanged && (!plan.due_at(time) || time == *old_time) {
            target.clone()
        } else {
            next.prepare(time, target)?
        };
        let changed =
            !value.same_certificate(target) && !self.spec.equal_targets(&value, target)?;
        let source = Self {
            spec: self.spec.clone(),
            phase: Phase::Ready {
                plan: next,
                target: value.clone(),
                time,
            },
        };
        Ok(Prepared {
            source,
            target: value,
            changed,
        })
    }
    pub(crate) fn same_epoch(&self, other: &Self) -> bool {
        if !Arc::ptr_eq(&self.spec, &other.spec) {
            return false;
        }
        match (&self.phase, &other.phase) {
            (Phase::Pending { seed: a }, Phase::Pending { seed: b }) => a.same_certificate(b),
            (
                Phase::Ready {
                    plan: a,
                    target: ta,
                    time: xa,
                },
                Phase::Ready {
                    plan: b,
                    target: tb,
                    time: xb,
                },
            ) => xa == xb && a.same_proof(b) && ta.same_certificate(tb),
            _ => false,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ir::{Expression, Origin, Program, Relation, Term, TransientInputs};
    use crate::pwl::Trajectory;
    use crate::transition_source_plan::Work;
    fn source(root: f64, states_in_leaf: bool) -> Source {
        let p:Program=serde_json::from_value(serde_json::json!({"schema_version":21,"nodes":["0","u","y"],"contributions":[],
            "states":[{"instance":"dut","name":"q","kind":"real","initial":1.}],"operators":[],"events":[],"step_bounds":[]})).unwrap();
        let constant = |v| Expression::Affine {
            constant: v,
            terms: vec![],
        };
        let e = Expression::Select {
            relation: Relation::Gt,
            left: Box::new(Expression::Affine {
                constant: 0.,
                terms: vec![Term {
                    node: 1,
                    coefficient: 1.,
                }],
            }),
            right: Box::new(constant(root)),
            then_value: Box::new(if states_in_leaf {
                Expression::State { state: 0 }
            } else {
                constant(1.)
            }),
            else_value: Box::new(constant(0.)),
            origin: Origin {
                source: "source-epoch.va".into(),
                line: 1,
                column: 1,
                instance: "dut".into(),
                expansion: vec![],
            },
        };
        let t = Trajectory::new(
            TransientInputs {
                pwl: vec![vec![[0., 0.], [1., 1.]]],
                stop: 1.,
                max_step: 1.,
                output_times: vec![0., 1.],
                strobetimes: vec![],
            },
            1,
        )
        .unwrap();
        Source::pending(
            Spec::new(&e, &p, &t, &["u".into()], "dut", Work::default())
                .unwrap()
                .unwrap(),
            &[I::ONE],
        )
        .unwrap()
    }
    #[test]
    fn initialization_is_prepared_once_from_final_epoch() {
        let s = source(-1., true);
        assert_eq!(s.provisional().value, 1.);
        assert!(s.prepare(0., I::ZERO, &[I::ZERO]).is_err());
        let a = s.prepare_initialization(&[I::point(2.)]).unwrap();
        assert_eq!(a.point.value, 2.);
        assert_eq!(a.right.value, 2.);
        assert!(!a.changed);
        assert!(s.pending_initialization());
        assert!(!a.source.pending_initialization());
        assert!(a.source.prepare_initialization(&[I::point(2.)]).is_err());
        let b = s.prepare_initialization(&[I::point(2.)]).unwrap();
        assert!(a.source.same_epoch(&b.source));
    }
    #[test]
    fn root_zero_keeps_point_seed_and_installs_right_once() {
        let s = source(0., false);
        let a = s.prepare_initialization(&[I::ONE]).unwrap();
        assert_eq!(a.point.value, 0.);
        assert_eq!(a.right.value, 1.);
        assert!(a.changed);
        let b = a.source.prepare(0., I::ZERO, &[I::ONE]).unwrap();
        assert!(!b.changed);
        assert!(a.source.same_epoch(&b.source));
    }
    #[test]
    fn missed_cut_and_failed_rebind_do_not_mutate_epoch() {
        let a = source(0.5, true)
            .prepare_initialization(&[I::ONE])
            .unwrap()
            .source;
        assert!(a.prepare(0.75, I::point(0.75), &[I::ONE]).is_err());
        assert_eq!(a.next_after(0.), Some(0.5));
        let b = a.prepare(0.5, I::point(0.5), &[I::ONE]).unwrap();
        assert!(b.changed);
        assert_eq!(b.target.value, 1.);
        let same = b.source.prepare(0.5, I::point(0.5), &[I::ONE]).unwrap();
        assert!(!same.changed);
        assert!(b
            .source
            .prepare(0.5, I::point(0.5), &[I::point(2.)])
            .is_err());
        assert!(b.source.same_epoch(&same.source));
        let retry = a.prepare(0.5, I::point(0.5), &[I::ONE]).unwrap();
        assert!(retry.source.same_epoch(&b.source));
    }
    #[test]
    fn domain_and_consumed_cut_overlap_remain_checked_on_fast_path() {
        let a = source(0.5, true)
            .prepare_initialization(&[I::ONE])
            .unwrap()
            .source;
        let b = a.prepare(0.5, I::point(0.5), &[I::ONE]).unwrap().source;
        assert!(b.prepare(0.5, I { lo: 0.49, hi: 0.51 }, &[I::ONE]).is_err());
        assert!(b.prepare(0.6, I { lo: 0.49, hi: 0.61 }, &[I::ONE]).is_err());
        let c = b.prepare(1., I::ONE, &[I::ONE]).unwrap().source;
        assert!(c.prepare(1.1, I::point(1.1), &[I::ONE]).is_err());
        assert!(c.prepare(1., I { lo: 1., hi: 1.01 }, &[I::ONE]).is_err());
        assert!(c.prepare(1., I::ONE, &[I::ONE]).is_ok());
    }
}
