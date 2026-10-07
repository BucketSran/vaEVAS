//! Rebuild history-dependent calendars inside the controller's event transaction.
use super::*;
use crate::guard_trajectory::GuardTrajectory;
use crate::schedule::{history_epoch, independent_epoch, reschedule_independent, HistoryEpoch};

pub(super) fn initialize(
    model: &EventModel,
    trajectory: &Trajectory,
    states: &[f64],
) -> Result<(Operators, Vec<ScheduledEvent>), Error> {
    let bounds: Vec<_> = states.iter().copied().map(I::point).collect();
    let pending = independent_epoch(model, trajectory, &bounds, None)?;
    let until = pending
        .first()
        .map_or(trajectory.config.stop, |event| event.time);
    let operators = Operators::new_until(
        &model.program,
        trajectory,
        &model.driven,
        states,
        until,
        &model.tolerances,
    )?;
    let calendar = history_epoch(
        model,
        trajectory,
        &operators,
        HistoryEpoch {
            states: &bounds,
            after: None,
            until,
            consumed: &[],
            pending: &pending,
        },
    )?;
    Ok((operators, calendar))
}

impl Controller {
    pub(super) fn accept_history_events(
        &mut self,
        model: &EventModel,
        trajectory: &Trajectory,
        calendar: &mut Vec<ScheduledEvent>,
    ) -> Result<(), Error> {
        self.accept_changed_events(
            model,
            trajectory,
            calendar,
            event_acceptance::Strategy::History,
        )
    }

    pub(super) fn prepare_history_future(
        &self,
        model: &EventModel,
        trajectory: &Trajectory,
        next: &Frame,
        batch: &[ScheduledEvent],
        remaining: &[ScheduledEvent],
    ) -> Result<event_acceptance::CalendarPlan, Error> {
        let time = batch[0].time;
        let consumed: Vec<_> = batch.iter().map(|e| e.event).collect();
        let consumed_history: Vec<_> = batch
            .iter()
            .filter_map(|e| e.dynamic_direction().map(|direction| (e.event, direction)))
            .collect();
        let window = batch
            .iter()
            .fold(I::point(time), |window, event| window.hull(event.bounds()));
        let fixed_batch = batch.iter().all(ScheduledEvent::is_fixed_timer);
        let before = GuardTrajectory::new_held(
            model,
            trajectory,
            Some(&self.accepted.operators),
            Some(&self.accepted.state_bounds),
        )?;
        let after = GuardTrajectory::new_held(
            model,
            trajectory,
            Some(&next.operators),
            Some(&next.state_bounds),
        )?;
        // At any possible event time a continuous state still has its old-flow
        // value. Substitute the new held state over the WHOLE observation
        // window, not just the representative at its upper endpoint.
        let continuous_after = GuardTrajectory::new_held(
            model,
            trajectory,
            Some(&self.accepted.operators),
            Some(&next.state_bounds),
        )?;
        let mut changed = vec![true; model.triggers.len()];
        for (index, leaf) in model.triggers.iter().enumerate() {
            let owner = &model.program.events[leaf.event].origin.instance;
            if let EventTrigger::HeldTimer {
                start,
                period,
                enabled,
                ..
            } = &leaf.trigger
            {
                changed[index] = false;
                for expression in [start, period, enabled] {
                    changed[index] |= crate::events::affine(expression, &model.program, owner)?
                        .state_dependencies
                        .iter()
                        .any(|&s| self.accepted.state_bounds[s] != next.state_bounds[s]);
                }
            } else if matches!(leaf.trigger, EventTrigger::Timer { .. }) {
                changed[index] = false;
            }
            let EventTrigger::Cross { guard, .. } = &leaf.trigger else {
                continue;
            };
            let direct_change = before.changed_by(
                guard,
                owner,
                &self.accepted.state_bounds,
                &next.state_bounds,
            )?;
            if model.guard_operators[index].is_empty() {
                changed[index] = direct_change;
            }
            let mut keeps_history = true;
            for &operator in &model.guard_operators[index] {
                keeps_history &= next.operators.keeps_guard_value(operator)?;
            }
            if fixed_batch && window.lo != window.hi && !model.guard_operators[index].is_empty() {
                // Root isolation resumes at b. Certify the post-event tube
                // from every possible tau to b, including the final timer in
                // an overlap cluster. A root here must never be skipped.
                if !matches!(
                    after.event_value(guard, window, owner)?.sign(),
                    Some(-1 | 1)
                ) {
                    return Err(Error::new(
                        "event_resolution",
                        "cannot exclude a history crossing inside the timer observation window",
                    ));
                }
            }
            if keeps_history && !direct_change {
                continue;
            }
            if !keeps_history && window.lo != window.hi {
                return Err(Error::new("unsupported_cross",
                    "discontinuous guard history over an uncertain event window requires an event closure contract"));
            }
            let left = before.event_value(guard, window, owner)?.sign();
            let right = if keeps_history {
                continuous_after.event_value(guard, window, owner)?.sign()
            } else {
                after.range(guard, I::point(time), owner)?.0.sign()
            };
            if consumed.contains(&index) || !matches!(left, Some(-1 | 1)) || left != right {
                return Err(Error::new("unsupported_cross",
                    "event-dependent guard jump or uncertain same-time crossing requires an event closure contract"));
            }
        }
        let pending = reschedule_independent(
            model,
            trajectory,
            &next.state_bounds,
            time,
            &changed,
            remaining,
        )?;
        Ok(event_acceptance::CalendarPlan::History {
            pending,
            consumed: consumed_history,
        })
    }
}
