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
    // Last physical target/cut consumed. It can follow the user root while
    // remaining inside that event's original discovery window.
    cursor: RootTime,
}

pub(crate) struct TargetStep {
    pub(crate) target: Target,
    pub(crate) changed: bool,
    pub(crate) window: I,
    pub(crate) root: Option<RootTime>,
}
pub(crate) struct Prepared {
    pub(crate) source: Source,
    pub(crate) target: Target,
    pub(crate) changed: bool,
    pub(crate) time_bounds: I,
    pub(crate) exact_root: Option<RootTime>,
    pub(crate) steps: Vec<TargetStep>,
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
                cursor: RootTime::point(0.).unwrap(),
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
    /// Rebase only a cloned observation cursor inside an already certified
    /// post-event phase. No source cut may have been consumed after the query.
    pub(crate) fn rebase_observation(&mut self, time: f64) -> Result<(), Error> {
        if time >= self.time {
            return Ok(());
        }
        let query = RootTime::point(time);
        if !self
            .last_root
            .as_ref()
            .zip(query.as_ref())
            .is_some_and(|(root, query)| {
                root.refine(self.last_window).is_some()
                    && root.order(query) != std::cmp::Ordering::Greater
            })
            || query
                .as_ref()
                .is_none_or(|q| self.cursor.order(q) == std::cmp::Ordering::Greater)
            || self
                .plan
                .next_after(time)
                .is_some_and(|cut| cut <= self.time)
        {
            return Err(Error::new(
                "event_resolution",
                "output query cannot rebase its certified source phase",
            ));
        }
        self.time = time;
        // This is an ordinary observation. The event's original root/window
        // still belongs to the immutable accepted frame, not this point query.
        self.last_root = None;
        self.last_window = I::point(time);
        self.cursor = query.unwrap();
        Ok(())
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
                "event_resolution",
                "source event overlaps an unproved source-target boundary: changed same-time epoch requires previous frame replay",
            ));
        }
        let moment = effective_root
            .cloned()
            .or_else(|| RootTime::point(time))
            .ok_or_else(|| Error::new("event_resolution", "missing source phase root"))?;
        let upper = RootTime::point(time).unwrap();
        let mut target = self.target.clone();
        let mut cursor = self.cursor.clone();
        let mut steps = Vec::new();
        if !(time == self.time && unchanged) {
            if moment.order(&cursor) == std::cmp::Ordering::Less {
                return Err(Error::new(
                    "event_resolution",
                    "source epoch would reverse a consumed physical root",
                ));
            }
            // Close OLD held flow strictly before the user root, then install
            // the new held epoch at that root, then close its flow up to the
            // representative. Distinct roots are never collapsed into one.
            for cut in self.plan.cuts().iter().filter(|cut| {
                cut.exact.order(&self.cursor) == std::cmp::Ordering::Greater
                    && cut.exact.order(&moment) == std::cmp::Ordering::Less
            }) {
                self.plan.debit_boundary()?;
                if cut.bounds.hi < proof_window.lo || cut.bounds.lo > proof_window.hi {
                    return Err(Error::new(
                        "event_consistency",
                        "source history skipped a required physical boundary",
                    ));
                }
                let value = self.plan.prepare_root(&cut.exact, &target)?;
                let changed = !self.spec.equal_targets(&value, &target)?;
                steps.push(TargetStep {
                    target: value.clone(),
                    changed,
                    window: cut.bounds,
                    root: Some(cut.exact.clone()),
                });
                target = value;
            }
            let value = next.prepare_root(&moment, &target)?;
            let changed = !self.spec.equal_targets(&value, &target)?;
            steps.push(TargetStep {
                target: value.clone(),
                changed,
                window: proof_window,
                root: effective_root.cloned(),
            });
            target = value;
            cursor = moment.clone();
            for cut in next.cuts().iter().filter(|cut| {
                cut.exact.order(&moment) == std::cmp::Ordering::Greater
                    && cut.exact.order(&upper) != std::cmp::Ordering::Greater
            }) {
                next.debit_boundary()?;
                if cut.bounds.hi < proof_window.lo || cut.bounds.lo > proof_window.hi {
                    return Err(Error::new(
                        "event_consistency",
                        "source history skipped a required physical boundary",
                    ));
                }
                let value = next.prepare_root(&cut.exact, &target)?;
                let changed = !self.spec.equal_targets(&value, &target)?;
                steps.push(TargetStep {
                    target: value.clone(),
                    changed,
                    window: cut.bounds,
                    root: Some(cut.exact.clone()),
                });
                target = value;
                cursor = cut.exact.clone();
            }
        }
        let changed = !target.same_certificate(&self.target)
            && !self.spec.equal_targets(&target, &self.target)?;
        let time_bounds = steps.last().map_or(proof_window, |s| s.window);
        let exact_root = steps
            .last()
            .and_then(|s| s.root.clone())
            .or_else(|| effective_root.cloned());
        Ok(Prepared {
            source: Self {
                spec: self.spec.clone(),
                plan: next,
                certified,
                target: target.clone(),
                time,
                last_root: effective_root.cloned(),
                last_window: proof_window,
                cursor,
            },
            target,
            changed,
            time_bounds,
            exact_root,
            steps,
        })
    }
    /// Close only the OLD held epoch before sampling the user event. Keep the
    /// original execution cursor so final settlement can replay the new epoch.
    pub(crate) fn prepare_prefix(
        &self,
        window: I,
        root: Option<&RootTime>,
    ) -> Result<(Self, Vec<TargetStep>), Error> {
        self.plan.check_incoming(self.time, window, root)?;
        let mut source = self.clone();
        let mut steps = Vec::new();
        let Some(root) = root else {
            return Ok((source, steps));
        };
        for cut in self.plan.cuts().iter().filter(|cut| {
            cut.exact.order(&self.cursor) == std::cmp::Ordering::Greater
                && cut.exact.order(root) == std::cmp::Ordering::Less
        }) {
            self.plan.debit_boundary()?;
            if cut.bounds.hi < window.lo || cut.bounds.lo > window.hi {
                return Err(Error::new(
                    "event_consistency",
                    "source history skipped a required physical boundary",
                ));
            }
            let target = self.plan.prepare_root(&cut.exact, &source.target)?;
            let changed = !self.spec.equal_targets(&target, &source.target)?;
            steps.push(TargetStep {
                target: target.clone(),
                changed,
                window: cut.bounds,
                root: Some(cut.exact.clone()),
            });
            source.target = target;
            source.cursor = cut.exact.clone();
        }
        Ok((source, steps))
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
            && self.cursor == other.cursor
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

    #[test]
    fn old_prefix_and_new_epoch_use_distinct_exact_roots_once() {
        let source = source();
        let before = source.clone();
        let time = 0.5_f64.next_up();
        let window = I {
            lo: 0.5_f64.next_down(),
            hi: time,
        };
        let root = RootTime::from_clock(
            crate::exact_time::Clock {
                start: 0.1,
                period: 0.4,
                index: 1,
            },
            window,
        )
        .unwrap();
        assert_eq!(
            root.order(&RootTime::point(0.5).unwrap()),
            std::cmp::Ordering::Greater
        );
        let (prefix, steps) = source.prepare_prefix(window, Some(&root)).unwrap();
        assert_eq!(steps.len(), 1);
        assert_eq!(steps[0].target.value, 1.);
        assert_eq!(steps[0].root, RootTime::point(0.5));
        assert_eq!(prefix.target().value, 1.);
        assert!(source.same_epoch(&before));
        let final_epoch = prefix
            .prepare(time, window, &[I::point(2.)], Some(&root))
            .unwrap();
        assert_eq!(final_epoch.steps.len(), 1);
        assert_eq!(final_epoch.steps[0].root, Some(root.clone()));
        assert_eq!(final_epoch.target.value, 2.);
        let retained = final_epoch.source.clone();
        let repeat = retained
            .prepare(time, I::point(time), &[I::point(2.)], None)
            .unwrap();
        assert!(repeat.steps.is_empty());
        assert!(retained.same_epoch(&repeat.source));
        assert!(source
            .prepare(time, I::point(time), &[I::point(2.)], Some(&root))
            .is_err());
        assert!(source.same_epoch(&before));
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
                analytic_sources: vec![],
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
    fn observation_cursor_requires_post_root_proof_and_preserves_accepted_epoch() {
        let (query, mut window, root) = nonpoint_moment();
        window.hi = query.next_up();
        let accepted = source()
            .prepare(window.hi, window, &[I::ONE], Some(&root))
            .unwrap()
            .source;
        let before = accepted.clone();
        let mut observed = accepted.clone();
        observed.rebase_observation(query).unwrap();
        let prepared = observed
            .prepare(query, I::point(query), &[I::ONE], None)
            .unwrap();
        assert!(!prepared.changed);
        assert_eq!(prepared.time_bounds, I::point(query));
        assert!(prepared.exact_root.is_none());
        assert!(accepted.same_epoch(&before));

        let mut rejected = accepted.clone();
        assert!(rejected.rebase_observation(window.lo).is_err());
        assert!(rejected.same_epoch(&before));
        let mut unproved = source()
            .prepare(0.25, I::point(0.25), &[I::ONE], None)
            .unwrap()
            .source;
        let original = unproved.clone();
        assert!(unproved.rebase_observation(0.2).is_err());
        assert!(unproved.same_epoch(&original));
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

        // A retained window cannot repair newly supplied inconsistent evidence.
        let error = retained
            .prepare(time, I::point(time), &[I::ONE], Some(&root))
            .err()
            .unwrap();
        assert_eq!(error.kind, "condition_precision");
        assert!(retained.same_epoch(&before));
        let mut history = crate::transition::Transition::new(0., 0., 0.125, 0.125).unwrap();
        let old_history = history.clone();
        let error = history
            .advance_at_with_exact(
                time,
                I::point(time),
                retained.target.value,
                retained.target.bounds,
                true,
                Some(&root),
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
