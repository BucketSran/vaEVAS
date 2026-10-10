//! Query-independent, best-effort recovery of an event voltage certificate.
//! This is not a continuous-time sensitivity allocator. Later history/output
//! certificates remain mandatory, including failures that this preflight misses.
use super::*;

impl Controller {
    /// Assess only the direct affine sampling case. Reuse the production
    /// settlement, original accepted uncertainty and selected event branches.
    /// No point is substituted for the root in the actual candidate.
    fn input_root_demand(
        &self,
        model: &EventModel,
        trajectory: &Trajectory,
        event: &ScheduledEvent,
    ) -> Option<crate::accuracy::Demand> {
        if !model.program.operators.is_empty() || !trajectory.has_only_physical_inputs() {
            return None;
        }
        let _timing = crate::diagnostics::span("root.assessment");
        let (inputs, slopes) = trajectory.range(event.bounds()).ok()?;
        let blocks = [model.triggers[event.event].event];
        let roots = [event.event];
        let prepared = crate::settlement::prepare_window(
            model,
            (&blocks, &roots),
            (&trajectory.values(event.time), &inputs),
            &self.accepted.states,
            &[],
            &self.accepted.state_bounds,
            &[],
            Some(&self.accepted.circuit),
        )
        .ok()?;
        let selection = model
            .conditions
            .select_at_roots(&blocks, &inputs, &roots)
            .ok()?;
        let point_inputs = trajectory.value_bounds(event.time);
        let observation = model.conditions.select(&[], &point_inputs).ok()?;
        let sample = crate::settlement_bounds::Bounds::new(model, &selection).ok()?;
        let output = crate::settlement_bounds::Bounds::new(model, &observation).ok()?;
        sample.input_root_demand(
            &output,
            model,
            event.time,
            &point_inputs,
            &slopes,
            &self.accepted.state_bounds,
            &self.accepted.states,
            &prepared.bounds,
            &prepared.solution.voltages,
        )
    }

    // Inspect the event and its first physical history deadline. In particular,
    // a delayed transition is still flat at event acceptance, so its activation
    // must be checked before deciding whether the root needs refinement. These
    // checkpoints come from history, never the requested output grid. This is a
    // demand probe, not a proof of accuracy between or beyond the checkpoints.
    fn preflight_root_consumer(
        &self,
        model: &EventModel,
        trajectory: &Trajectory,
        crossings: &[ScheduledEvent],
    ) -> Result<(), Error> {
        crate::diagnostics::counter("root_preflight_calls", 1);
        let (next, _, end) = self.prepare_events_until(model, trajectory, crossings, None)?;
        if let Some(time) = next.operators.next_breakpoint(next.time).filter(|&time| {
            time > next.time
                && time <= trajectory.config.stop
                && crossings
                    .get(end)
                    .is_none_or(|event| time < event.bounds().lo)
        }) {
            prepare_root_window(
                model,
                trajectory,
                &next,
                EventMoment {
                    representative: time,
                    observation: I::point(time),
                    fired_roots: &[],
                    prediction_end: prediction_end(model, trajectory, crossings.get(end)),
                },
                &[],
            )?;
        }
        Ok(())
    }

    pub(super) fn refine_pending_input_root(
        &self,
        model: &EventModel,
        trajectory: &Trajectory,
        crossings: &mut [ScheduledEvent],
    ) -> Result<(), Error> {
        let Some(event) = crossings.get(self.event) else {
            return Ok(());
        };
        if !event.can_refine_input_root(model)
            || event.bounds().lo <= self.accepted.time
            // Narrowing a disjoint enclosure cannot change event ordering or
            // grouping. Connected clusters need a separate ordering transaction.
            || crossings.get(self.event + 1).is_some_and(|next| next.bounds().lo <= event.time)
            || self.event.checked_sub(1).and_then(|i| crossings.get(i))
                .is_some_and(|prior| prior.time >= event.bounds().lo)
        {
            return Ok(());
        }
        let failure = match self.preflight_root_consumer(model, trajectory, crossings) {
            Ok(_) => return Ok(()),
            Err(error) if matches!(error.kind, "waveform_accuracy" | "event_accuracy") => error,
            Err(error) => return Err(error),
        };
        let demand = self.input_root_demand(model, trajectory, event);
        if let Some(demand) = &demand {
            crate::diagnostics::detail("root_demand", "assessed", Some(event.time), demand);
            if demand.source == crate::accuracy::Source::Retained {
                return Err(failure);
            }
        } else {
            crate::diagnostics::detail(
                "root_demand",
                "unknown",
                Some(event.time),
                &serde_json::json!({"source":"unknown", "failure":failure.message}),
            );
        }
        let mut target = demand.as_ref().and_then(|d| d.target_width);
        // A later event may amplify this sampled state. Until its demand is
        // propagated backwards, keep the existing full contraction. Held
        // calendars can discover such an event only after this trial commits.
        if crossings.get(self.event + 1).is_some()
            || model.relocalized_guards.iter().any(|held| *held)
        {
            target = None;
            crate::diagnostics::detail(
                "root_policy",
                "legacy_future_events",
                Some(event.time),
                &serde_json::json!({"reason":"future event demand is not allocated"}),
            );
        }
        if demand.as_ref().is_some_and(|d| d.future_input_coupling) {
            target = None;
            crate::diagnostics::detail(
                "root_policy",
                "legacy_input_feedthrough",
                Some(event.time),
                &serde_json::json!({"reason":"future consumer budget is not allocated"}),
            );
        }
        let mut remaining = crate::dynamic_roots::REFINEMENT_WORK;
        let mut candidate = crossings.to_vec();
        // At most a target trial and one legacy fallback, sharing the work
        // budget. Every trial starts from self.accepted, not failed history.
        let mut last_failure = failure;
        for attempt in 0..2 {
            let old_bounds = candidate[self.event].bounds();
            let (refined, work) = candidate[self.event].refine_input_root(
                model,
                trajectory,
                &self.accepted.operators,
                target,
                remaining,
            )?;
            remaining = remaining.saturating_sub(work.iterations);
            let changed = refined.bounds() != candidate[self.event].bounds();
            candidate[self.event] = refined;
            let result = if changed {
                self.preflight_root_consumer(model, trajectory, &candidate)
            } else {
                Err(last_failure)
            };
            let bounds = candidate[self.event].bounds();
            crate::diagnostics::detail(
                "root_refinement",
                if result.is_ok() {
                    "accepted"
                } else {
                    "rejected"
                },
                Some(candidate[self.event].time),
                &serde_json::json!({
                    "attempt":attempt+1, "target_width":target,
                    "width_before":(I::point(old_bounds.hi)-I::point(old_bounds.lo)).hi,
                    "width_after":(I::point(bounds.hi)-I::point(bounds.lo)).hi,
                    "bounds_after":[bounds.lo,bounds.hi], "iterations":work.iterations,
                    "stop":work.stop, "remaining_work":remaining,
                }),
            );
            match result {
                Ok(()) => {
                    crossings[self.event] = candidate[self.event].clone();
                    return Ok(());
                }
                Err(error) => last_failure = error,
            }
            if target.is_none()
                || remaining == 0
                || !matches!(last_failure.kind, "waveform_accuracy" | "event_accuracy")
            {
                break;
            }
            target = None;
        }
        Err(last_failure)
    }
}
