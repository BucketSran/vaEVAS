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
    plan: Arc<Plan>,
    certified: Vec<Arc<Plan>>,
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

fn same_plan(left: &Arc<Plan>, right: &Arc<Plan>) -> bool {
    // Plans are private, immutable, successfully validated proofs. Sharing one
    // allocation therefore implies the original finite structural equality.
    Arc::ptr_eq(left, right) || left.same_proof(right)
}

impl Source {
    /// Construction receives the already settled initial held state. Preserve
    /// the point seed separately from the right-hand target installed at zero.
    pub(crate) fn initialized(
        spec: Arc<Spec>,
        states: &[I],
    ) -> Result<(Self, Target, bool), Error> {
        let plan = Arc::new(Plan::build(spec.clone(), states)?);
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
        // Final-history queries may re-enter the accepted upper representative
        // without new time evidence. Its root and original window are one
        // certificate; restoring only the root would invent a point enclosure.
        let retained_root = (root.is_none() && time == self.time && bounds == I::point(time))
            .then_some(self.last_root.as_ref())
            .flatten();
        let effective_root = root.or(retained_root);
        let proof_window = retained_root.map_or(bounds, |_| self.last_window);
        if retained_root.is_some_and(|root| root.refine(proof_window).is_none()) {
            return Err(Error::new(
                "event_resolution",
                "retained source root is outside its accepted event window",
            ));
        }
        self.plan
            .check_incoming(self.time, proof_window, effective_root)?;
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
            None => Arc::new(self.plan.rebind(states)?),
        };
        let mut certified = self.certified.clone();
        if !certified.iter().any(|plan| same_plan(plan, &next)) {
            certified.push(next.clone());
        }

        next.check_incoming(self.time, proof_window, effective_root)?;
        let unchanged = same_plan(&self.plan, &next);
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
        let time_bounds = cut.map_or(proof_window, |cut| cut.bounds);
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
            if !self.certified.iter().any(|old| same_plan(old, plan)) {
                self.certified.push(plan.clone());
            }
        }
        Ok(())
    }
    pub(crate) fn same_epoch(&self, other: &Self) -> bool {
        Arc::ptr_eq(&self.spec, &other.spec)
            && same_plan(&self.plan, &other.plan)
            && self.target.same_certificate(&other.target)
            && self.time == other.time
            && self.certified.len() == other.certified.len()
            && self
                .certified
                .iter()
                .zip(&other.certified)
                .all(|(a, b)| same_plan(a, b))
            && self.last_root == other.last_root
            && self.last_window == other.last_window
    }
}

#[cfg(test)]
mod sharing_tests {
    use super::*;
    use crate::ir::{Program, TransientInputs, SCHEMA_VERSION};
    use crate::pwl::Trajectory;
    use crate::transition_source_plan::Work;
    use serde_json::json;
    use std::borrow::Borrow;

    fn source() -> Source {
        source_with_threshold(json!({"op":"affine","constant":0.5,"terms":[]}), 1.)
    }

    fn source_with_threshold(threshold: serde_json::Value, initial: f64) -> Source {
        let program: Program = serde_json::from_value(json!({
            "schema_version":SCHEMA_VERSION, "nodes":["0","u"], "contributions":[],
            "states":[{"instance":"M","name":"q","kind":"real","initial":initial}]
        }))
        .unwrap();
        let expression = serde_json::from_value(json!({
            "op":"select", "relation":"gt",
            "left":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]},
            "right":threshold,
            "then_value":{"op":"state","state":0},
            "else_value":{"op":"affine","constant":0,"terms":[]},
            "origin":{"source":"sharing.va","line":1,"column":1,"instance":"M"}
        }))
        .unwrap();
        let trajectory = Trajectory::new(
            TransientInputs {
                pwl_errors_v: None,
                strobetimes: vec![],
                pwl: vec![vec![[0., 0.], [1., 1.]]],
                output_times: vec![0., 1.],
                stop: 1.,
                max_step: 1.,
            },
            1,
        )
        .unwrap();
        let spec = Spec::new(
            &expression,
            &program,
            &trajectory,
            &["u".into()],
            "M",
            Work::default(),
        )
        .unwrap()
        .unwrap();
        Source::initialized(spec, &[I::point(initial)]).unwrap().0
    }

    fn nonpoint_moment() -> (f64, I, RootTime) {
        let root = RootTime::point(0.1)
            .unwrap()
            .shifted_fixed(0.2, I::point(0.1) + I::point(0.2))
            .unwrap();
        let tight = root.bounds().unwrap();
        let window = I {
            lo: tight.lo.next_down().next_down(),
            hi: tight.hi,
        };
        assert!(root.refine(window).is_some());
        assert!(root.refine(I::point(window.hi)).is_none());
        (window.hi, window, root)
    }

    #[test]
    fn same_time_reentry_retains_complete_root_window_without_overwriting_new_evidence() {
        let (time, window, root) = nonpoint_moment();
        let first = source()
            .prepare(time, window, &[I::ONE], Some(&root))
            .unwrap();
        let retained = first.source;
        let before = retained.clone();
        let replay = retained
            .prepare(time, I::point(time), &[I::ONE], None)
            .unwrap();
        assert_eq!(
            replay.time_bounds, window,
            "reuse the accepted window, not a point or a new root enclosure"
        );
        assert_ne!(replay.time_bounds, root.bounds().unwrap());
        assert_eq!(replay.exact_root.as_ref(), Some(&root));
        assert!(retained.same_epoch(&before));

        let point_root = RootTime::point(time).unwrap();
        let explicit = retained
            .prepare(time, I::point(time), &[I::ONE], Some(&point_root))
            .unwrap();
        assert_eq!(explicit.time_bounds, I::point(time));
        assert_eq!(explicit.exact_root, Some(point_root));
        let fresh = retained.prepare(time, window, &[I::ONE], None).unwrap();
        assert_eq!(fresh.time_bounds, window);
        assert!(fresh.exact_root.is_none());
        let later = retained
            .prepare(time.next_up(), I::point(time.next_up()), &[I::ONE], None)
            .unwrap();
        assert_eq!(later.time_bounds, I::point(time.next_up()));
        assert!(later.exact_root.is_none());

        // Explicit inconsistent evidence reaches the unchanged transition
        // guard; a retained window must not repair a newly supplied root.
        let bad = retained
            .prepare(time, I::point(time), &[I::ONE], Some(&root))
            .unwrap();
        assert_eq!(bad.time_bounds, I::point(time));
        let mut history = crate::transition::Transition::new(0., 0., 0.125, 0.125).unwrap();
        let old_history = history.clone();
        let error = history
            .advance_at_with_exact(
                time,
                bad.time_bounds,
                bad.target.value,
                bad.target.bounds,
                bad.changed,
                bad.exact_root.as_ref(),
            )
            .unwrap_err();
        assert_eq!(error.kind, "event_resolution");
        assert_eq!(
            error.message,
            "exact transition root is outside event enclosure"
        );
        assert_eq!(history, old_history);
    }

    #[test]
    fn restored_window_checks_changed_plan_and_refuses_invalid_retained_pair() {
        let (time, window, root) = nonpoint_moment();
        let initial = source_with_threshold(json!({"op":"state","state":0}), 0.5);
        let retained = initial
            .prepare(time, window, &[I::point(0.5)], Some(&root))
            .unwrap()
            .source;
        let before = retained.clone();
        // Rebinding places a distinct source cut at this same upper endpoint.
        // The whole restored window must still be checked against the new Plan.
        let error = retained
            .prepare(time, I::point(time), &[I::point(time)], None)
            .err()
            .unwrap();
        assert_eq!(error.kind, "event_resolution");
        assert!(error
            .message
            .contains("overlaps an unproved source-target boundary"));
        assert!(retained.same_epoch(&before));
        let mut invalid_pair = retained.clone();
        invalid_pair.last_window = I::point(time);
        assert_eq!(
            invalid_pair
                .prepare(time, I::point(time), &[I::point(0.5)], None)
                .err()
                .unwrap()
                .kind,
            "event_resolution"
        );
        // A new nonpoint window is checked as supplied, without replacing it
        // by the earlier accepted window which did not overlap the .5 cut.
        let error = retained
            .prepare(
                time,
                I {
                    lo: window.lo,
                    hi: 0.5,
                },
                &[I::point(0.5)],
                None,
            )
            .err()
            .unwrap();
        assert_eq!(error.kind, "event_resolution");
        assert!(retained.same_epoch(&before));
    }

    #[test]
    fn candidates_share_immutable_plans_without_publishing_cursor_target_or_epoch() {
        let accepted = source();
        let clone = accepted.clone();
        assert!(accepted.same_epoch(&clone));
        assert!(
            std::ptr::eq::<Plan>(accepted.plan.borrow(), clone.plan.borrow()),
            "history clone should share the proved table"
        );
        assert!(std::ptr::eq::<Plan>(
            accepted.certified[0].borrow(),
            clone.certified[0].borrow()
        ));

        let ordinary = accepted
            .prepare(0.25, I::point(0.25), &[I::ONE], None)
            .unwrap();
        assert!(std::ptr::eq::<Plan>(
            accepted.plan.borrow(),
            ordinary.source.plan.borrow()
        ));
        assert_eq!(accepted.time, 0.);
        assert_eq!(ordinary.source.time, 0.25);
        assert_eq!(accepted.target.value, 0.);

        let changed = accepted
            .prepare(0.25, I::point(0.25), &[I::point(2.)], None)
            .unwrap();
        assert!(!accepted.plan.same_proof(&changed.source.plan));
        assert!(!std::ptr::eq::<Plan>(
            accepted.plan.borrow(),
            changed.source.plan.borrow()
        ));
        assert_eq!(accepted.certified.len(), 1);
        assert_eq!(changed.source.certified.len(), 2);
        let mut replay = accepted.clone();
        replay.reuse_certificates(&changed.source).unwrap();
        assert!(std::ptr::eq::<Plan>(
            replay.certified[1].borrow(),
            changed.source.plan.borrow()
        ));
        assert_eq!(replay.time, accepted.time);
        assert!(replay.target.same_certificate(&accepted.target));
        assert!(std::ptr::eq::<Plan>(
            replay.plan.borrow(),
            accepted.plan.borrow()
        ));

        let at_boundary = changed
            .source
            .prepare(
                0.5,
                I::point(0.5),
                &[I::point(2.)],
                Some(&RootTime::point(0.5).unwrap()),
            )
            .unwrap();
        assert_eq!(at_boundary.target.value, 2.);
        assert_eq!(at_boundary.source.time, 0.5);
        assert_eq!(accepted.time, 0.);
        assert_eq!(accepted.target.value, 0.);
        assert!(accepted.same_epoch(&clone));
        assert!(!accepted.same_epoch(&at_boundary.source));

        // Independently rebuilt allocations retain the original structural
        // comparison; shared addresses are only its successful fast path.
        let mut rebuilt = accepted.clone();
        rebuilt.plan = Arc::new(Plan::build(accepted.spec.clone(), &[I::ONE]).unwrap());
        rebuilt.certified = vec![rebuilt.plan.clone()];
        assert!(accepted.same_epoch(&rebuilt));
        assert!(!accepted.same_epoch(&source()));
        for state in [
            I::point(f64::NAN),
            I::point(f64::INFINITY),
            I { lo: 1., hi: 2. },
        ] {
            assert!(accepted
                .prepare(0.25, I::point(0.25), &[state], None)
                .is_err());
            assert!(accepted.same_epoch(&clone));
        }
    }
}
