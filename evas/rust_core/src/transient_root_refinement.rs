//! Query-independent, best-effort recovery of an event voltage certificate.
//! This is not a continuous-time sensitivity allocator. Later history/output
//! certificates remain mandatory, including failures that this preflight misses.
use super::*;

impl Controller {
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
        let old_bounds = event.bounds();
        let refined = event.refine_input_root(model, trajectory, &self.accepted.operators)?;
        if refined.bounds() == old_bounds {
            return Err(failure);
        }
        let mut candidate = crossings.to_vec();
        candidate[self.event] = refined;
        // One retry from the same accepted frame, never from failed history.
        // Failure leaves the original calendar, state, records and outputs intact.
        self.preflight_root_consumer(model, trajectory, &candidate)?;
        let refined = candidate[self.event].clone();
        crate::diagnostics::record(
            "root_refinement",
            "accepted",
            Some(old_bounds.lo),
            Some(old_bounds.hi),
            1,
            Some(&format!(
                "{}; refined=[{:.17e},{:.17e}]; original trigger tolerances retained",
                failure.message,
                refined.bounds().lo,
                refined.bounds().hi
            )),
        );
        crossings[self.event] = refined;
        Ok(())
    }
}
