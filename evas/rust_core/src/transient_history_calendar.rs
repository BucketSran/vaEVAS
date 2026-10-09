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

    pub(super) fn prepare_physical_history(
        &self,
        model: &EventModel,
        trajectory: &Trajectory,
        next: &mut Frame,
        batch: &[ScheduledEvent],
        pending: &[ScheduledEvent],
    ) -> Result<(), Error> {
        let time = batch[0].time;
        let consumed: Vec<_> = batch.iter().map(|event| event.event).collect();
        let window = batch
            .iter()
            .fold(I::point(time), |window, event| window.hull(event.bounds()));
        let physical_anchor = batch.iter().find_map(ScheduledEvent::clock);
        if next.operators.local_epoch().is_none()
            && window.lo != window.hi
            && next.operators.history_certificate().is_some()
        {
            let probe = GuardTrajectory::new_held(
                model,
                trajectory,
                Some(&next.operators),
                Some(&next.state_bounds),
            )?;
            // Retain the physical seed when a requested post-event phase is
            // earlier than its execution frame. At equality, the current frame
            // suffices unless a certified physically due successor will advance
            // this same transaction beyond the query. Window overlap alone is
            // not permission to force an otherwise ordinary source-driven flow
            // into an autonomous local epoch.
            let mut needs_closure = trajectory.config.output_times.iter().any(|&query| {
                query >= window.lo
                    && query <= time
                    && (query < time
                        || pending.first().is_some_and(|event| {
                            event.time > query
                                && matches!(
                                    event.physical_order_at(query),
                                    Some(std::cmp::Ordering::Less | std::cmp::Ordering::Equal)
                                )
                        }))
                    && batch.iter().all(|event| {
                        matches!(
                            event.physical_order_at(query),
                            Some(std::cmp::Ordering::Less | std::cmp::Ordering::Equal)
                        )
                    })
            });
            for (index, leaf) in model.triggers.iter().enumerate() {
                if model.guard_operators[index].is_empty() || consumed.contains(&index) {
                    continue;
                }
                if let EventTrigger::Cross { guard, .. } = &leaf.trigger {
                    let owner = &model.program.events[leaf.event].origin.instance;
                    needs_closure |= !matches!(
                        probe.event_value(guard, window, owner)?.sign(),
                        Some(-1 | 1)
                    );
                }
            }
            if needs_closure {
                if !trajectory.config.strobetimes.is_empty() {
                    return Err(Error::new("unsupported_strobe", "forced solve points with a local-time causal event closure are not yet supported"));
                }
                let clock = physical_anchor.ok_or_else(|| {
                    Error::new(
                        "event_resolution",
                        "local causal closure requires an exact fixed-clock physical anchor",
                    )
                })?;
                let permission = crate::schedule::ordered_observation(batch, clock, model)?;
                if permission.delta() != I::ZERO {
                    return Err(Error::new(
                        "event_resolution",
                        "local closure cannot merge distinct physical clock anchors",
                    ));
                }
                next.operators
                    .anchor_event(clock, time, trajectory.config.stop)?;
            }
        }
        Ok(())
    }

    pub(super) fn prepare_history_future(
        &self,
        model: &EventModel,
        trajectory: &Trajectory,
        next: &mut Frame,
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
        if next.operators.local_epoch().is_none() && window.lo != window.hi {
            // Refresh independent certificates under candidate parameters before
            // asking whether an output needs a local physical phase. A changed
            // held timer may have moved beyond stop or become disabled; its old
            // calendar entry cannot authorize a local epoch. History-root tube
            // inspection and anchoring still precede history isolation below.
            let mut independent_changed = vec![true; model.triggers.len()];
            for (index, leaf) in model.triggers.iter().enumerate() {
                let owner = &model.program.events[leaf.event].origin.instance;
                match &leaf.trigger {
                    EventTrigger::Timer { .. } => independent_changed[index] = false,
                    EventTrigger::HeldTimer {
                        start,
                        period,
                        enabled,
                        ..
                    } => {
                        independent_changed[index] = false;
                        for expression in [start, period, enabled] {
                            independent_changed[index] |=
                                crate::events::affine(expression, &model.program, owner)?
                                    .state_dependencies
                                    .iter()
                                    .any(|&state| {
                                        self.accepted.state_bounds[state]
                                            != next.state_bounds[state]
                                    });
                        }
                    }
                    EventTrigger::Cross { guard, .. }
                        if model.guard_operators[index].is_empty() =>
                    {
                        independent_changed[index] = before.changed_by(
                            guard,
                            owner,
                            &self.accepted.state_bounds,
                            &next.state_bounds,
                        )?;
                    }
                    _ => {}
                }
            }
            let physical_pending = reschedule_independent(
                model,
                trajectory,
                &next.state_bounds,
                time,
                &independent_changed,
                remaining,
            )?;
            self.prepare_physical_history(model, trajectory, next, batch, &physical_pending)?;
        }
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
            if next.operators.local_epoch().is_none()
                && fixed_batch
                && window.lo != window.hi
                && !model.guard_operators[index].is_empty()
            {
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
        let mut retained = remaining.to_vec();
        if next.operators.local_epoch().is_some() {
            let mut prior = batch.last().unwrap().clone();
            for event in &mut retained {
                if changed[event.event] || !model.guard_operators[event.event].is_empty() {
                    continue;
                }
                if !event.retain_after(&prior, model)? {
                    break;
                }
                prior = event.clone();
            }
        }
        let pending = reschedule_independent(
            model,
            trajectory,
            &next.state_bounds,
            time,
            &changed,
            &retained,
        )?;
        Ok(event_acceptance::CalendarPlan::History {
            pending,
            consumed: consumed_history,
        })
    }
}
