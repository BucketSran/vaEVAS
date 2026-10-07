//! Time advancement around the static solver. Trials never mutate accepted state.
use crate::events::EventModel;
use crate::interval::Interval as I;
use crate::ir::{
    Error, EventRecord, EventTrigger, FiredTrigger, Request, Response, Solution, TransientTrace,
    SCHEMA_VERSION,
};
use crate::operators::Operators;
use crate::pwl::Trajectory;
use crate::schedule::{
    independent_schedule, reschedule_held, schedule, schedule_held, ScheduledEvent,
};
use crate::solver::Circuit;

#[path = "transient_history_calendar.rs"]
mod history_calendar;

struct Frame {
    time: f64,
    states: Vec<f64>,
    state_bounds: Vec<I>,
    solution: Solution,
    circuit: Circuit,
    operators: Operators,
}

// Own every event-commit mutation in the production controller. Preparing a
// batch or rejecting its deadlines cannot consume a calendar entry or record.
struct Controller {
    accepted: Frame,
    event: usize,
    records: Vec<EventRecord>,
}

impl Controller {
    fn accept_events(
        &mut self,
        model: &EventModel,
        trajectory: &Trajectory,
        crossings: &[ScheduledEvent],
    ) -> Result<(), Error> {
        let (next, records, end) = self.prepare_events(model, trajectory, crossings)?;
        self.commit_events(next, records, end);
        Ok(())
    }

    fn prepare_events(
        &self,
        model: &EventModel,
        trajectory: &Trajectory,
        crossings: &[ScheduledEvent],
    ) -> Result<(Frame, Vec<EventRecord>, usize), Error> {
        let result = self.prepare_events_until(model, trajectory, crossings, None)?;
        result
            .0
            .operators
            .check_deadline_order(result.0.time, crossings.get(result.2).map(|e| e.bounds()))?;
        Ok(result)
    }

    fn prepare_events_until(
        &self,
        model: &EventModel,
        trajectory: &Trajectory,
        crossings: &[ScheduledEvent],
        horizon: Option<f64>,
    ) -> Result<(Frame, Vec<EventRecord>, usize), Error> {
        let time = crossings[self.event].time;
        let mut end = self.event;
        while end < crossings.len() && crossings[end].time == time {
            end += 1;
        }
        let (next, records) = crate::diagnostics::outcome(
            "event_candidate",
            time,
            prepare_calendar_batch(
                model,
                trajectory,
                &self.accepted,
                time,
                &crossings[self.event..end],
                horizon.unwrap_or_else(|| prediction_end(model, trajectory, crossings.get(end))),
            ),
        )?;
        Ok((next, records, end))
    }

    fn accept_relocalized(
        &mut self,
        model: &EventModel,
        trajectory: &Trajectory,
        crossings: &mut Vec<ScheduledEvent>,
    ) -> Result<(), Error> {
        // Close observation/reset at the event before predicting new flow.
        // The changed held calendar, not its stale predecessor, owns the next
        // prediction horizon. No fallible phase mutates the accepted frame.
        let time = crossings[self.event].time;
        let (mut next, records, end) =
            self.prepare_events_until(model, trajectory, crossings, Some(time))?;
        let window = records.iter().fold(I::point(next.time), |t, r| {
            let [lo, hi] = r.observation_time_bounds.unwrap_or([r.time, r.time]);
            t.hull(I { lo, hi })
        });
        let inputs = trajectory.range(window)?.0;
        let projection = crate::event_accuracy::GuardBounds::held(
            &model.program,
            &model.driven,
            &model.dynamic_guards,
            &self.accepted.state_bounds,
        )?;
        let mut changed = projection.changed_by(&self.accepted.state_bounds, &next.state_bounds);
        let before = projection.values(&inputs);
        let after = crate::event_accuracy::GuardBounds::held(
            &model.program,
            &model.driven,
            &model.dynamic_guards,
            &next.state_bounds,
        )?
        .values(&inputs);
        let old_trajectory = crate::guard_trajectory::GuardTrajectory::new_held(
            model,
            trajectory,
            None,
            Some(&self.accepted.state_bounds),
        )?;
        let new_trajectory = crate::guard_trajectory::GuardTrajectory::new_held(
            model,
            trajectory,
            None,
            Some(&next.state_bounds),
        )?;
        for (index, held) in model.relocalized_guards.iter().enumerate() {
            if let EventTrigger::HeldTimer {
                start,
                period,
                enabled,
                ..
            } = &model.triggers[index].trigger
            {
                let owner = &model.program.events[model.triggers[index].event]
                    .origin
                    .instance;
                for expression in [start, period, enabled] {
                    changed[index] |= crate::events::affine(expression, &model.program, owner)?
                        .state_dependencies
                        .iter()
                        .any(|&s| self.accepted.state_bounds[s] != next.state_bounds[s]);
                }
                continue;
            }
            let (a, b) = if *held && model.dynamic_guards[index] {
                let EventTrigger::Cross { guard, .. } = &model.triggers[index].trigger else {
                    unreachable!()
                };
                let owner = &model.program.events[model.triggers[index].event]
                    .origin
                    .instance;
                changed[index] = old_trajectory.changed_by(
                    guard,
                    owner,
                    &self.accepted.state_bounds,
                    &next.state_bounds,
                )?;
                (
                    old_trajectory.range(guard, window, owner)?.0,
                    new_trajectory.range(guard, window, owner)?.0,
                )
            } else {
                (before[index], after[index])
            };
            if !held || !changed[index] {
                continue;
            }
            let a = a.sign();
            let b = b.sign();
            if a.is_none() || b.is_none() || a != b {
                return Err(Error::new(
                    "unsupported_cross",
                    "event-dependent guard jump or uncertain same-time crossing requires an event closure contract",
                ));
            }
        }
        let future = reschedule_held(
            model,
            trajectory,
            &next.state_bounds,
            next.time,
            &changed,
            &crossings[end..],
        )?;
        next.operators = next.operators.evaluation(next.time)?.advanced_until(
            I::point(next.time),
            &next.states,
            &next.state_bounds,
            &[],
            prediction_end(model, trajectory, future.first()),
        )?;
        next.operators
            .check_deadline_order(next.time, future.first().map(|e| e.bounds()))?;
        // Extending a nonlinear dense history can widen its endpoint box.
        // The committed observation must satisfy the budget against that
        // final history as well as the earlier reset/observation closure.
        let point_inputs = trajectory.value_bounds(next.time);
        model.certify(
            &model.conditions.select(&[], &point_inputs)?,
            &point_inputs,
            &next.state_bounds,
            &next.operators.bounds(next.time)?,
            &next.solution.voltages,
            &next.states,
        )?;
        // Build and validate the future first; calendar replacement and state
        // acceptance have no remaining fallible operation between them.
        self.commit_events(next, records, 0);
        *crossings = future;
        Ok(())
    }

    fn commit_events(&mut self, next: Frame, records: Vec<EventRecord>, end: usize) {
        let time = next.time;
        self.accepted = next;
        self.event = end;
        let committed = records.len();
        self.records.extend(records);
        crate::diagnostics::record(
            "event_batch",
            "committed",
            Some(time),
            Some(time),
            committed,
            None,
        );
    }
}

// Current policy chooses the certified mathematical root as the actual cross
// observation. Its enclosure and fired-root constraints travel together; b is
// only a representative. No late-trigger policy is silently substituted.
struct EventMoment<'a> {
    representative: f64,
    observation: I,
    fired_roots: &'a [usize],
    prediction_end: f64,
}

fn prediction_end(
    _model: &EventModel,
    trajectory: &Trajectory,
    next: Option<&ScheduledEvent>,
) -> f64 {
    next.map_or(trajectory.config.stop, |event| event.time)
}

#[cfg(test)]
#[path = "transient_idt_tests.rs"]
mod idt_accepted_history_tests;

#[cfg(test)]
#[path = "transient_condition_tests.rs"]
mod condition_history_tests;

#[cfg(test)]
#[path = "transient_window_tests.rs"]
mod window_history_tests;

#[cfg(test)]
#[path = "transient_lifecycle_tests.rs"]
mod lifecycle_controller_tests;

#[cfg(test)]
fn prepare_event_with_bounds(
    model: &EventModel,
    trajectory: &Trajectory,
    accepted: &Frame,
    time: f64,
    time_bounds: I,
    events: &[usize],
) -> Result<Frame, Error> {
    prepare_root_window(
        model,
        trajectory,
        accepted,
        EventMoment {
            representative: time,
            observation: time_bounds,
            fired_roots: &[],
            prediction_end: trajectory.config.stop,
        },
        events,
    )
}

fn prepare_root_window(
    model: &EventModel,
    trajectory: &Trajectory,
    accepted: &Frame,
    moment: EventMoment<'_>,
    events: &[usize],
) -> Result<Frame, Error> {
    let _timing = crate::diagnostics::span("controller.prepare_candidate");

    let EventMoment {
        representative: time,
        observation: time_bounds,
        fired_roots: fired_leaves,
        prediction_end,
    } = moment;
    let copying = crate::diagnostics::span("history.clone");
    let mut operators = accepted.operators.clone();
    drop(copying);
    crate::diagnostics::counter("history_clone_calls", 1);
    crate::diagnostics::counter(
        "history_clone_operator_slots",
        model.program.operators.len(),
    );
    // Every trial starts from accepted uncertainty, regardless of whether the
    // program has conditional statements or history operators.
    let old_bounds = accepted.state_bounds.as_slice();
    operators.advance(time, time_bounds, &accepted.states, old_bounds, &[])?;
    // Positive edge durations make transition continuous at a target change.
    // Freeze its current value for the same-time state/voltage solve, then
    // install the new target only in this disposable candidate history.
    let base = operators;
    let mut frozen = base.evaluation(time)?;
    frozen.bounds = base.event_bounds(time, time_bounds)?;
    let inputs = trajectory.values(time);
    let input_bounds = trajectory.range(time_bounds)?.0;
    let settle = |values: &[f64], bounds: &[I]| {
        if time_bounds.lo == time_bounds.hi {
            crate::settlement::prepare(
                model,
                events,
                (&inputs, &input_bounds),
                &accepted.states,
                values,
                old_bounds,
                bounds,
                Some(&accepted.circuit),
            )
        } else {
            crate::settlement::prepare_window(
                model,
                (events, fired_leaves),
                (&inputs, &input_bounds),
                &accepted.states,
                values,
                old_bounds,
                bounds,
                Some(&accepted.circuit),
            )
        }
    };
    let mut prepared = settle(&frozen.values, &frozen.bounds)?;
    let mut observation = (frozen.values.clone(), frozen.bounds.clone());
    let mut closed = false;
    // Reset dependencies are structurally acyclic. Propagate their instant
    // maps until stable, rebuilding assignments from accepted state each time.
    // This is an observation closure, never a chain of provisional histories.
    for _ in 0..=model.program.operators.len() {
        let (mapped, values, bounds) = frozen.observed_after(time_bounds, &prepared.bounds)?;
        if values == observation.0 && bounds == observation.1 {
            closed = true;
            break;
        }
        if !mapped.permits_same_time_change(&observation.0, &values) {
            return Err(Error::new(
                "event_consistency",
                "operator changed during same-time settlement",
            ));
        }
        observation = (values, bounds);
        prepared = settle(&observation.0, &observation.1)?;
    }
    if !closed {
        return Err(Error::new(
            "event_consistency",
            "same-time observation closure did not stabilize",
        ));
    }
    // Only the final closed state may define the future flow and targets.
    let changed: Vec<_> = prepared
        .assigned
        .iter()
        .copied()
        .filter(|&s| old_bounds[s] != prepared.bounds[s] || old_bounds[s].lo != old_bounds[s].hi)
        .collect();
    let operators = frozen.advanced_until(
        time_bounds,
        &prepared.states,
        &prepared.bounds,
        &changed,
        prediction_end,
    )?;
    let replay = settle(&observation.0, &observation.1)?;
    let history_replay = frozen.advanced_until(
        time_bounds,
        &replay.states,
        &replay.bounds,
        &changed,
        prediction_end,
    )?;
    if prepared.states != replay.states
        || prepared.bounds != replay.bounds
        || !history_replay.same_reset_history(&operators)
    {
        return Err(Error::new(
            "event_consistency",
            "closed event state or future history changed during replay",
        ));
    }
    if time_bounds.lo != time_bounds.hi {
        // Sampling at tau and observing the committed frame at b are distinct
        // obligations. Do not resample the event using post-event history.
        model.certify(
            &model
                .conditions
                .select(&[], &trajectory.value_bounds(time))?,
            &trajectory.value_bounds(time),
            &prepared.bounds,
            &operators.bounds(time)?,
            &prepared.solution.voltages,
            &prepared.states,
        )?;
    }
    Ok(Frame {
        time,
        states: prepared.states,
        state_bounds: prepared.bounds,
        solution: prepared.solution,
        circuit: prepared.circuit,
        operators,
    })
}

#[cfg(test)]
fn prepare_event(
    model: &EventModel,
    trajectory: &Trajectory,
    accepted: &Frame,
    time: f64,
    events: &[usize],
) -> Result<Frame, Error> {
    prepare_event_with_bounds(model, trajectory, accepted, time, I::point(time), events)
}

#[cfg(test)]
fn prepare_batch(
    model: &EventModel,
    trajectory: &Trajectory,
    accepted: &Frame,
    event_time: f64,
    ids: &[usize],
) -> Result<(Frame, Vec<EventRecord>), Error> {
    prepare_batch_with_bounds(
        model,
        trajectory,
        accepted,
        event_time,
        I::point(event_time),
        ids,
    )
}

#[cfg(test)]
fn prepare_batch_with_bounds(
    model: &EventModel,
    trajectory: &Trajectory,
    accepted: &Frame,
    event_time: f64,
    event_bounds: I,
    ids: &[usize],
) -> Result<(Frame, Vec<EventRecord>), Error> {
    prepare_batch_until(
        model,
        trajectory,
        accepted,
        EventMoment {
            representative: event_time,
            observation: event_bounds,
            fired_roots: ids,
            prediction_end: trajectory.config.stop,
        },
    )
}

fn prepare_batch_until(
    model: &EventModel,
    trajectory: &Trajectory,
    accepted: &Frame,
    moment: EventMoment<'_>,
) -> Result<(Frame, Vec<EventRecord>), Error> {
    let event_time = moment.representative;
    let event_bounds = moment.observation;
    let ids = moment.fired_roots;
    // Calendar IDs identify leaves; settlement IDs identify event bodies.
    // Same-root certification occurred before this deduplication.
    let blocks: Vec<_> = ids
        .iter()
        .map(|&id| model.triggers[id].event)
        .collect::<std::collections::BTreeSet<_>>()
        .into_iter()
        .collect();
    let next = prepare_root_window(model, trajectory, accepted, moment, &blocks)?;
    next.operators.check_deadline_order(event_time, None)?;
    let mut records = Vec::new();
    for id in blocks {
        let mut fired = Vec::new();
        for &leaf_id in ids {
            let leaf = &model.triggers[leaf_id];
            if leaf.event != id {
                continue;
            }
            if let EventTrigger::Cross {
                expression_tolerance,
                ..
            } = &leaf.trigger
            {
                let value = if let Some(guard) = &model.guards[leaf_id] {
                    guard.value_with(
                        &next.solution.voltages,
                        &next.states,
                        &next.operators.values(event_time)?,
                    )?
                } else {
                    let EventTrigger::Cross { guard, .. } = &leaf.trigger else {
                        unreachable!()
                    };
                    let nodes: Vec<_> = next
                        .solution
                        .voltages
                        .iter()
                        .copied()
                        .map(I::point)
                        .collect();
                    let operators: Vec<_> = next
                        .operators
                        .values(event_time)?
                        .into_iter()
                        .map(I::point)
                        .collect();
                    let bound = crate::guard_trajectory::evaluate(
                        guard,
                        &nodes,
                        &operators,
                        &next
                            .states
                            .iter()
                            .copied()
                            .map(I::point)
                            .collect::<Vec<_>>(),
                        &vec![I::ZERO; nodes.len()],
                        &vec![I::ZERO; operators.len()],
                    )?
                    .0;
                    if bound.magnitude() > *expression_tolerance {
                        return Err(Error::new(
                            "event_resolution",
                            "post-event polynomial guard exceeds expression tolerance",
                        ));
                    }
                    bound.lo + (bound.hi - bound.lo) * 0.5
                };
                if value.abs() > *expression_tolerance {
                    return Err(Error::new(
                        "event_resolution",
                        "accepted event violates cross expression tolerance",
                    ));
                }
                fired.push(FiredTrigger {
                    trigger: leaf.index,
                    kind: "cross",
                    guard_value: Some(value),
                    time_bounds: None,
                });
            } else {
                fired.push(FiredTrigger {
                    trigger: leaf.index,
                    kind: "timer",
                    guard_value: None,
                    time_bounds: None,
                });
            }
        }
        let (kind, guard_value) = match &model.program.events[id].trigger {
            EventTrigger::Cross { .. } => ("cross", fired[0].guard_value),
            EventTrigger::Timer { .. } | EventTrigger::HeldTimer { .. } => ("timer", None),
            EventTrigger::Or { .. } => ("or", None),
        };
        if kind != "or" {
            fired.clear();
        }
        records.push(EventRecord {
            time: event_time,
            observation_time_bounds: (event_bounds.lo != event_bounds.hi)
                .then_some([event_bounds.lo, event_bounds.hi]),
            event: id,
            origin: model.program.events[id].origin.label(),
            kind,
            guard_value,
            fired_triggers: fired,
            before: accepted.states.clone(),
            after: next.states.clone(),
        });
    }
    Ok((next, records))
}

fn prepare_calendar_batch(
    model: &EventModel,
    trajectory: &Trajectory,
    accepted: &Frame,
    time: f64,
    scheduled: &[ScheduledEvent],
    prediction_end: f64,
) -> Result<(Frame, Vec<EventRecord>), Error> {
    let ids: Vec<_> = scheduled.iter().map(|e| e.event).collect();
    let bounds =
        scheduled
            .iter()
            .map(|event| event.bounds())
            .fold(I::point(time), |sum, bounds| I {
                lo: sum.lo.min(bounds.lo),
                hi: sum.hi.max(bounds.hi),
            });
    let (next, mut records) = prepare_batch_until(
        model,
        trajectory,
        accepted,
        EventMoment {
            representative: time,
            observation: bounds,
            fired_roots: &ids,
            prediction_end,
        },
    )?;
    for record in &mut records {
        for fired in &mut record.fired_triggers {
            let event = scheduled
                .iter()
                .find(|e| {
                    let leaf = &model.triggers[e.event];
                    leaf.event == record.event && leaf.index == fired.trigger
                })
                .unwrap();
            let bounds = event.bounds();
            fired.time_bounds = Some([bounds.lo, bounds.hi]);
        }
        record.fired_triggers.sort_by_key(|f| f.trigger);
    }
    Ok((next, records))
}

pub(crate) fn run(request: Request) -> Result<Response, Error> {
    if !request.samples.is_empty() {
        return Err(Error::new(
            "invalid_inputs",
            "transient execution cannot also contain static samples",
        ));
    }
    let transient = request.transient.unwrap();
    if request.program.states.is_empty()
        && request.program.events.is_empty()
        && request.program.operators.is_empty()
    {
        return run_stateless_transient(
            request.program,
            request.driven,
            transient,
            request.tolerances,
        );
    }
    if !request.program.operators.is_empty()
        && request
            .program
            .contributions
            .iter()
            .all(|c| !crate::analog::has_select(&c.rhs))
        && request.program.contributions.iter().any(|c| {
            crate::events::affine(&c.rhs, &request.program, &c.origin.instance)
                .is_err_and(|error| error.kind == "unsupported_transient")
        })
    {
        return crate::continuous::run_implicit(
            request.program,
            request.driven,
            transient,
            request.tolerances,
        );
    }
    let trajectory = Trajectory::new(transient, request.driven.len())?;

    let model = EventModel::new(request.program, request.driven, request.tolerances)?;
    let initial = model.initial();
    let relocalize = model.relocalized_guards.iter().any(|&held| held);
    let history_calendar = model.guard_operators.iter().any(|ops| !ops.is_empty());
    let (operators, mut crossings) = if history_calendar {
        history_calendar::initialize(&model, &trajectory, &initial)?
    } else if relocalize {
        let bounds: Vec<_> = initial.iter().copied().map(I::point).collect();
        let crossings = schedule_held(&model, &trajectory, &bounds)?;
        let operators = Operators::new_until(
            &model.program,
            &trajectory,
            &model.driven,
            &initial,
            prediction_end(&model, &trajectory, crossings.first()),
            &model.tolerances,
        )?;
        (operators, crossings)
    } else if model.dynamic_guards.iter().any(|&dynamic| dynamic) {
        let operators = Operators::new_until(
            &model.program,
            &trajectory,
            &model.driven,
            &initial,
            trajectory.config.stop,
            &model.tolerances,
        )?;
        let crossings = schedule(&model, &trajectory, &operators)?;
        (operators, crossings)
    } else {
        let crossings = independent_schedule(&model, &trajectory)?;
        let operators = Operators::new_until(
            &model.program,
            &trajectory,
            &model.driven,
            &initial,
            prediction_end(&model, &trajectory, crossings.first()),
            &model.tolerances,
        )?;
        (operators, crossings)
    };
    let circuit = model.circuit_with(&initial, &operators.values(0.0)?)?;
    let mut accepted = Frame {
        time: 0.0,
        solution: circuit.solve(&trajectory.values(0.0))?,
        state_bounds: initial.iter().copied().map(I::point).collect(),
        states: initial,
        circuit,
        operators,
    };
    let inputs = trajectory.value_bounds(0.0);
    accepted.state_bounds = model.certify(
        &model.conditions.select(&[], &inputs)?,
        &inputs,
        &accepted.state_bounds,
        &accepted.operators.bounds(0.0)?,
        &accepted.solution.voltages,
        &accepted.states,
    )?;
    let mut trace = TransientTrace {
        times: trajectory.config.output_times.clone(),
        state_names: model
            .program
            .states
            .iter()
            .map(|s| format!("{}:{}", s.instance, s.name))
            .collect(),
        states: Vec::new(),
        events: Vec::new(),
        accepted_steps: 0,
        discarded_trials: 0,
    };
    let mut solutions = Vec::new();
    let (mut output, mut knot) = (0, 1);
    let mut controller = Controller {
        accepted,
        event: 0,
        records: Vec::new(),
    };
    loop {
        controller.accepted.operators.check_deadline_order(
            controller.accepted.time,
            crossings.get(controller.event).map(|e| e.bounds()),
        )?;
        // t=0 is processed after initial_step and before the initial observation.
        // Later events are reached by the same loop after advancing to their time.
        if controller.event < crossings.len()
            && crossings[controller.event].time == controller.accepted.time
        {
            if history_calendar {
                controller.accept_history_events(&model, &trajectory, &mut crossings)?;
            } else if relocalize {
                controller.accept_relocalized(&model, &trajectory, &mut crossings)?;
            } else {
                controller.accept_events(&model, &trajectory, &crossings)?;
            }
        }
        controller.accepted.operators.check_deadline_order(
            controller.accepted.time,
            crossings.get(controller.event).map(|e| e.bounds()),
        )?;
        if output < trace.times.len() && controller.accepted.time == trace.times[output] {
            let _output = crate::diagnostics::span("output.collect");
            solutions.push(controller.accepted.solution.clone());
            trace.states.push(controller.accepted.states.clone());
            output += 1;
        }
        if controller.accepted.time == trajectory.config.stop {
            break;
        }
        if trace.accepted_steps >= 1_000_000 {
            return Err(Error::new(
                "step_budget",
                "transient execution exceeded 1,000,000 accepted steps",
            ));
        }
        let accepted_start = controller.accepted.time;
        let mut time =
            (controller.accepted.time + trajectory.config.max_step).min(trajectory.knots[knot]);
        if output < trace.times.len() {
            time = time.min(trace.times[output]);
        }
        if let Some(deadline) = controller
            .accepted
            .operators
            .next_breakpoint(controller.accepted.time)
        {
            time = time.min(deadline);
        }
        if time <= controller.accepted.time {
            return Err(Error::new(
                "event_resolution",
                "max_step cannot advance representable time",
            ));
        }
        // Discard an overshooting time proposal before evaluating history:
        // the earlier event can change the future waveform and constraints.
        if controller.event < crossings.len() && crossings[controller.event].time <= time {
            if crossings[controller.event].time < time {
                trace.discarded_trials += 1;
                crate::diagnostics::record(
                    "time_proposal",
                    "discarded",
                    Some(controller.accepted.time),
                    Some(time),
                    1,
                    Some("earlier scheduled event"),
                );
            }
            if history_calendar {
                controller.accept_history_events(&model, &trajectory, &mut crossings)?;
            } else if relocalize {
                controller.accept_relocalized(&model, &trajectory, &mut crossings)?;
            } else {
                controller.accept_events(&model, &trajectory, &crossings)?;
            }
        } else {
            if !model.program.operators.is_empty() {
                let next = crate::diagnostics::outcome(
                    "history_candidate",
                    time,
                    prepare_root_window(
                        &model,
                        &trajectory,
                        &controller.accepted,
                        EventMoment {
                            representative: time,
                            observation: I::point(time),
                            fired_roots: &[],
                            prediction_end: prediction_end(
                                &model,
                                &trajectory,
                                crossings.get(controller.event),
                            ),
                        },
                        &[],
                    ),
                )?;
                next.operators.check_deadline_order(
                    time,
                    crossings.get(controller.event).map(|e| e.bounds()),
                )?;
                controller.accepted = next;
            } else {
                // Without history operators or an event, the state and matrix
                // are unchanged. Reuse the accepted factorization, but certify
                // the same PWL/state bounds as the full candidate path before
                // committing any observation or time advance.
                let inputs = trajectory.values(time);
                let input_bounds = trajectory.value_bounds(time);
                let solution = controller.accepted.circuit.solve(&inputs)?;
                let state_bounds = model.certify(
                    &model.conditions.select(&[], &input_bounds)?,
                    &input_bounds,
                    &controller.accepted.state_bounds,
                    &[],
                    &solution.voltages,
                    &controller.accepted.states,
                )?;
                controller.accepted.solution = solution;
                controller.accepted.state_bounds = state_bounds;
                controller.accepted.time = time;
            }
        }
        trace.accepted_steps += 1;
        crate::diagnostics::record(
            "controller_step",
            "committed",
            Some(accepted_start),
            Some(controller.accepted.time),
            1,
            None,
        );
        if controller.accepted.time == trajectory.knots[knot] {
            knot += 1;
        }
    }
    trace.events = controller.records;
    Ok(Response {
        engine: concat!("evas-events-", env!("CARGO_PKG_VERSION")).into(),
        schema_version: SCHEMA_VERSION,
        nodes: model.program.nodes,
        solutions,
        transient: Some(trace),
    })
}

fn run_stateless_transient(
    program: crate::ir::Program,
    driven: Vec<String>,
    transient: crate::ir::TransientInputs,
    tolerances: crate::ir::Tolerances,
) -> Result<Response, Error> {
    let _timing = crate::diagnostics::span("controller.stateless");

    let trajectory = Trajectory::new(transient, driven.len())?;
    let times = trajectory.config.output_times.clone();
    let nodes = program.nodes.clone();
    let mut circuit = crate::analog::Analog::new(program, driven, tolerances)?;
    let mut solutions = Vec::new();
    let mut previous: Option<Solution> = None;
    for (sample, &time) in times.iter().enumerate() {
        let solution = circuit
            .solve(
                &trajectory.values(time),
                &trajectory.value_bounds(time),
                previous.as_ref().map(|s| s.voltages.as_slice()),
            )
            .map_err(|mut error| {
                error.sample = Some(sample);
                error
            })?;
        previous = Some(solution.clone());
        solutions.push(solution);
    }
    let sample_count = solutions.len();
    Ok(Response {
        engine: concat!("evas-events-", env!("CARGO_PKG_VERSION")).into(),
        schema_version: SCHEMA_VERSION,
        nodes,
        solutions,
        transient: Some(TransientTrace {
            times,
            state_names: Vec::new(),
            states: vec![Vec::new(); sample_count],
            events: Vec::new(),
            // Stateless observations solve working points; no physical frame
            // or integration step is accepted on this path.
            accepted_steps: 0,
            discarded_trials: 0,
        }),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ir::{Program, Tolerances, TransientInputs};

    fn idt_fixture(
        clamp: bool,
        gain: f64,
        tolerances: Tolerances,
        reset: bool,
    ) -> (EventModel, Trajectory, Frame) {
        let (original, _, _) = fixture(clamp);
        let mut program = original.program;
        let mut operator = serde_json::json!({
            "kind":"idt", "input":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]},
            "ic":0, "origin":{"source":"rollback.va","line":3,"column":1,"instance":"dut"}
        });
        if reset {
            operator["ic"] = serde_json::json!(0.25);
            operator["reset"] = serde_json::json!({"op":"state","state":0});
        }
        program.operators = serde_json::from_value(serde_json::json!([operator])).unwrap();
        program.contributions[0].rhs = serde_json::from_value(serde_json::json!({
            "op":"multiply", "left":{"op":"affine","constant":-1,"terms":[]},
            "right":{"op":"add", "left":{"op":"state","state":0},
                "right":{"op":"multiply", "left":{"op":"affine","constant":gain,"terms":[]},
                    "right":{"op":"operator","operator":0}}}
        }))
        .unwrap();
        program.events[0].trigger = EventTrigger::Timer {
            start: 1.0,
            period: 1.0,
            time_tolerance: 0.001,
            enabled: true,
        };
        let model = EventModel::new(program, vec!["u".into()], tolerances).unwrap();
        let trajectory = Trajectory::new(
            TransientInputs {
                pwl: vec![vec![[0.0, 0.0], [3.0, 1.0]]],
                output_times: vec![0.0, 3.0],
                stop: 3.0,
                max_step: 3.0,
            },
            1,
        )
        .unwrap();
        let states = model.initial();
        let operators =
            Operators::new(&model.program, &trajectory, &model.driven, &states).unwrap();
        let circuit = model
            .circuit_with(&states, &operators.values(0.0).unwrap())
            .unwrap();
        let frame = Frame {
            time: 0.0,
            state_bounds: states.iter().copied().map(I::point).collect(),
            states,
            solution: circuit.solve(&trajectory.values(0.0)).unwrap(),
            circuit,
            operators,
        };
        (model, trajectory, frame)
    }

    fn assert_initial_idt_frame(frame: &Frame, history_bounds: &[I]) {
        assert_eq!(frame.time, 0.0);
        assert_eq!(frame.states, [0.0]);
        assert_eq!(frame.state_bounds, [I::ZERO]);
        assert_eq!(frame.solution.voltages, [0.0, 0.0, 0.0]);
        assert_eq!(
            frame.circuit.solve(&[0.0]).unwrap().voltages,
            frame.solution.voltages
        );
        assert_eq!(frame.operators.values(0.0).unwrap(), [0.0]);
        assert_eq!(frame.operators.values(1.0).unwrap(), [1.0 / 6.0]);
        assert_eq!(frame.operators.bounds(1.0).unwrap(), history_bounds);
        assert_eq!(frame.operators.next_breakpoint(0.0), Some(3.0));
    }

    #[test]
    fn idt_failed_certification_preserves_frame_and_same_time_retry_uses_budget() {
        let (mut model, trajectory, before) = idt_fixture(
            false,
            1073741824.0,
            Tolerances {
                absolute: 1e-10,
                relative: 0.0,
            },
            false,
        );
        let bounds = before.operators.bounds(1.0).unwrap();
        for _ in 0..2 {
            let error = prepare_batch(&model, &trajectory, &before, 1.0, &[0])
                .err()
                .unwrap();
            assert_eq!(error.kind, "waveform_accuracy");
            assert_initial_idt_frame(&before, &bounds);
        }
        // Same model/cache, accepted state and time; a separately requested
        // looser budget permits a fresh candidate. No stale failed sample.
        model.tolerances.absolute = 1e-6;
        let (discarded, pending) = prepare_batch(&model, &trajectory, &before, 1.0, &[0]).unwrap();
        assert_eq!(discarded.states, [1.0]);
        assert_eq!(pending.len(), 1);
        drop(discarded);
        assert_initial_idt_frame(&before, &bounds);
        let (next, pending) = prepare_batch(&model, &trajectory, &before, 1.0, &[0]).unwrap();
        assert_eq!(next.states, [1.0]);
        assert_eq!(next.solution.voltages[2], 1.0 + 1073741824.0 / 6.0);
        assert_eq!(next.operators.bounds(1.0).unwrap(), bounds);
        assert_eq!(pending.len(), 1);
        let (second, _) = prepare_batch(&model, &trajectory, &next, 2.0, &[0]).unwrap();
        assert_eq!(second.states, [2.0]);
    }

    #[test]
    fn idt_residual_failure_and_successful_discard_never_change_accepted_history() {
        for clamp in [false, true] {
            let (model, trajectory, before) = idt_fixture(clamp, 1.0, Tolerances::default(), false);
            let bounds = before.operators.bounds(1.0).unwrap();
            for _ in 0..2 {
                let trial = prepare_batch(&model, &trajectory, &before, 1.0, &[0]);
                if clamp {
                    assert_eq!(trial.err().unwrap().kind, "residual_failure");
                } else {
                    let (next, records) = trial.unwrap();
                    assert_eq!(next.states, [1.0]);
                    assert_eq!(records.len(), 1);
                    assert_eq!(next.solution.voltages[2], 1.0 + 1.0 / 6.0);
                }
                assert_initial_idt_frame(&before, &bounds);
            }
        }
    }

    #[test]
    fn reset_release_bounds_are_checked_even_when_value_is_unchanged() {
        let (original, trajectory, _) = idt_fixture(false, 1.0, Tolerances::default(), true);
        // Make the two trial inputs submitted source knots. At 1e-20 V an
        // off-knot approximation of t/3 must itself be refused; this test
        // isolates reset-time uncertainty rather than PWL interpolation error.
        let trajectory = Trajectory::new(
            TransientInputs {
                pwl: vec![vec![
                    [0.0, 0.0],
                    [0.5, 1.0 / 6.0],
                    [1.0, 1.0 / 3.0],
                    [3.0, 1.0],
                ]],
                ..trajectory.config
            },
            1,
        )
        .unwrap();
        let mut program = original.program;
        program.states[0].initial = 1.0;
        program.events[0].body = serde_json::from_value(serde_json::json!([
            {"kind":"assign","state":0,"rhs":{"op":"affine","constant":0,"terms":[]}}
        ]))
        .unwrap();
        let model = EventModel::new(
            program,
            vec!["u".into()],
            Tolerances {
                absolute: 1e-20,
                relative: 0.0,
            },
        )
        .unwrap();
        let states = model.initial();
        let operators =
            Operators::new(&model.program, &trajectory, &model.driven, &states).unwrap();
        let circuit = model
            .circuit_with(&states, &operators.values(0.0).unwrap())
            .unwrap();
        let initial = Frame {
            time: 0.0,
            state_bounds: vec![I::ONE],
            states,
            operators,
            solution: circuit.solve(&trajectory.values(0.0)).unwrap(),
            circuit,
        };
        let accepted = prepare_event(&model, &trajectory, &initial, 0.5, &[]).unwrap();
        let bounds = accepted.operators.bounds(1.0).unwrap();
        for _ in 0..2 {
            let error = prepare_batch_with_bounds(
                &model,
                &trajectory,
                &accepted,
                1.0,
                I {
                    lo: 1.0f64.next_down(),
                    hi: 1.0f64.next_up(),
                },
                &[0],
            )
            .err()
            .unwrap();
            assert_eq!(error.kind, "waveform_accuracy");
            assert_eq!(accepted.time, 0.5);
            assert_eq!(accepted.states, [1.0]);
            assert_eq!(accepted.state_bounds, [I::ONE]);
            assert_eq!(accepted.operators.bounds(1.0).unwrap(), bounds);
            assert_eq!(accepted.operators.values(2.0).unwrap(), [0.25]);
        }
        // Exact release has zero-length integral. The failed uncertain trials
        // must not prevent the same accepted frame from succeeding on retry.
        let (retry, records) = prepare_batch(&model, &trajectory, &accepted, 1.0, &[0]).unwrap();
        assert_eq!(records.len(), 1);
        assert_eq!(retry.states, [0.0]);
        assert_eq!(retry.solution.voltages[2], 0.25);
        assert_eq!(retry.operators.bounds(1.0).unwrap(), [I::point(0.25)]);
        // u(t)=t/3: integral from 1 to 3/2 is 5/24, plus IC=1/4.
        assert!((retry.operators.values(1.5).unwrap()[0] - 11.0 / 24.0).abs() < 1e-15);
    }

    #[test]
    fn reset_sine_failure_discard_and_retry_preserve_accepted_histories() {
        let (original, trajectory, _) = idt_fixture(false, 1.0, Tolerances::default(), true);
        let mut program = original.program;
        program.operators.push(
            serde_json::from_value(serde_json::json!({
                "kind":"sin", "input":{"op":"operator","operator":0},
                "origin":{"source":"rollback.va","line":4,"column":1,"instance":"dut"}
            }))
            .unwrap(),
        );
        program.contributions[0].rhs = serde_json::from_value(serde_json::json!({
            "op":"multiply", "left":{"op":"affine","constant":-1,"terms":[]},
            "right":{"op":"operator","operator":1}
        }))
        .unwrap();
        let mut model = EventModel::new(program, vec!["u".into()], Tolerances::default()).unwrap();
        let states = model.initial();
        let operators =
            Operators::new(&model.program, &trajectory, &model.driven, &states).unwrap();
        let circuit = model
            .circuit_with(&states, &operators.values(0.0).unwrap())
            .unwrap();
        let before = Frame {
            time: 0.0,
            state_bounds: states.iter().copied().map(I::point).collect(),
            states,
            solution: circuit.solve(&trajectory.values(0.0)).unwrap(),
            circuit,
            operators,
        };
        let original_values = before.operators.values(1.0).unwrap();
        let original_bounds = before.operators.bounds(1.0).unwrap();
        model.tolerances = Tolerances {
            absolute: 1e-30,
            relative: 0.0,
        };
        let error = prepare_batch(&model, &trajectory, &before, 1.0, &[0])
            .err()
            .unwrap();
        assert_eq!(error.kind, "waveform_accuracy");
        model.tolerances = Tolerances::default();
        let (discarded, _) = prepare_batch(&model, &trajectory, &before, 1.0, &[0]).unwrap();
        assert_eq!(discarded.states, [1.0]);
        assert_eq!(
            discarded.operators.values(1.0).unwrap(),
            [0.25, 0.25f64.sin()]
        );
        assert_eq!(discarded.solution.voltages[2], 0.25f64.sin());
        drop(discarded);
        assert_eq!(before.time, 0.0);
        assert_eq!(before.states, [0.0]);
        assert_eq!(before.operators.values(1.0).unwrap(), original_values);
        assert_eq!(before.operators.bounds(1.0).unwrap(), original_bounds);
        let (retry, records) = prepare_batch(&model, &trajectory, &before, 1.0, &[0]).unwrap();
        assert_eq!(records.len(), 1);
        assert_eq!(retry.states, [1.0]);
        assert_eq!(retry.operators.values(1.0).unwrap(), [0.25, 0.25f64.sin()]);
        assert_eq!(retry.solution.voltages[2], 0.25f64.sin());
    }

    #[test]
    fn idt_reset_same_time_resolve_and_discard_do_not_commit_candidate() {
        let (model, trajectory, before) = idt_fixture(false, 1.0, Tolerances::default(), true);
        assert_eq!(before.states, [0.0]);
        assert_eq!(before.operators.values(1.0).unwrap(), [0.25 + 1.0 / 6.0]);
        let before_bounds = before.operators.bounds(1.0).unwrap();
        let (discarded, records) = prepare_batch(&model, &trajectory, &before, 1.0, &[0]).unwrap();
        assert_eq!(records.len(), 1);
        assert_eq!(discarded.states, [1.0]);
        assert_eq!(discarded.operators.values(1.0).unwrap(), [0.25]);
        drop(discarded);
        assert_eq!(before.time, 0.0);
        assert_eq!(before.states, [0.0]);
        assert_eq!(before.state_bounds, [I::ZERO]);
        assert_eq!(before.operators.values(1.0).unwrap(), [0.25 + 1.0 / 6.0]);
        assert_eq!(before.operators.bounds(1.0).unwrap(), before_bounds);

        let (next, records) = prepare_batch(&model, &trajectory, &before, 1.0, &[0]).unwrap();
        assert_eq!(records.len(), 1);
        assert_eq!(next.states, [1.0]);
        assert_eq!(next.operators.values(1.0).unwrap(), [0.25]);
        assert_eq!(next.solution.voltages[2], 1.25);
        let (held, _) = prepare_batch(&model, &trajectory, &next, 2.0, &[0]).unwrap();
        assert_eq!(held.states, [2.0]);
        assert_eq!(held.operators.values(2.0).unwrap(), [0.25]);
    }

    #[test]
    fn idt_corrected_input_definition_retries_same_time_with_cached_certificate() {
        let (model, trajectory, before) = idt_fixture(false, 1.0, Tolerances::default(), false);
        let bounds = before.operators.bounds(1.0).unwrap();
        let (first, _) = prepare_batch(&model, &trajectory, &before, 1.0, &[0]).unwrap();
        assert_eq!(first.solution.voltages[2], 1.0 + 1.0 / 6.0);
        // The complete source is immutable within a request. Correcting it
        // rebinds the analytic history at the accepted initial frame; it does
        // not reuse the old Operators merely because the query time matches.
        let mut config = trajectory.config.clone();
        config.pwl[0][1][1] = 2.0;
        let corrected_trajectory = Trajectory::new(config, 1).unwrap();
        let operators = Operators::new(
            &model.program,
            &corrected_trajectory,
            &model.driven,
            &before.states,
        )
        .unwrap();
        let circuit = model
            .circuit_with(&before.states, &operators.values(0.0).unwrap())
            .unwrap();
        let corrected = Frame {
            time: 0.0,
            states: before.states.clone(),
            state_bounds: before.state_bounds.clone(),
            solution: circuit.solve(&corrected_trajectory.values(0.0)).unwrap(),
            circuit,
            operators,
        };
        let (second, _) =
            prepare_batch(&model, &corrected_trajectory, &corrected, 1.0, &[0]).unwrap();
        assert_eq!(second.solution.voltages[2], 1.0 + 1.0 / 3.0);
        assert_eq!(second.states, [1.0]);
        let (retry, _) = prepare_batch(&model, &trajectory, &before, 1.0, &[0]).unwrap();
        assert_eq!(retry.solution.voltages, first.solution.voltages);
        assert_eq!(retry.state_bounds, first.state_bounds);
        assert_initial_idt_frame(&before, &bounds);
    }

    #[test]
    fn history_accuracy_failure_and_retry_leave_all_bounds_uncommitted() {
        let (original, trajectory, _) = fixture(false);
        let mut program = original.program;
        program.operators = serde_json::from_value(serde_json::json!([{
            "kind":"transition", "input":{"op":"state","state":0},
            "delay":0,"rise":3,"fall":3,
            "origin":{"source":"accuracy.va","line":3,"column":1,"instance":"dut"}
        }]))
        .unwrap();
        program.contributions[0].rhs = serde_json::from_value(serde_json::json!({
            "op":"multiply", "left":{"op":"affine","constant":-1073741824.0,"terms":[]},
            "right":{"op":"operator","operator":0}
        }))
        .unwrap();
        let model = EventModel::new(
            program,
            vec!["u".into()],
            Tolerances {
                absolute: 1e-10,
                relative: 0.0,
            },
        )
        .unwrap();
        let states = model.initial();
        let operators =
            Operators::new(&model.program, &trajectory, &model.driven, &states).unwrap();
        let circuit = model
            .circuit_with(&states, &operators.values(0.0).unwrap())
            .unwrap();
        let initial = Frame {
            time: 0.0,
            state_bounds: states.iter().copied().map(I::point).collect(),
            states,
            operators,
            solution: circuit.solve(&trajectory.values(0.0)).unwrap(),
            circuit,
        };
        let accepted = prepare_event(&model, &trajectory, &initial, 0.0, &[0]).unwrap();
        let bounds = accepted.operators.bounds(1.0).unwrap();
        for _ in 0..2 {
            let error = prepare_event(&model, &trajectory, &accepted, 1.0, &[])
                .err()
                .unwrap();
            assert_eq!(error.kind, "waveform_accuracy");
            assert_eq!(accepted.time, 0.0);
            assert_eq!(accepted.states, [1.0]);
            assert_eq!(accepted.state_bounds, [I::ONE]);
            assert_eq!(accepted.solution.voltages[2], 0.0);
            assert_eq!(accepted.operators.bounds(1.0).unwrap(), bounds);
            assert_eq!(accepted.operators.next_breakpoint(0.0), Some(3.0));
        }
    }

    #[test]
    fn sampled_state_bounds_survive_failed_amplification_and_cached_retry() {
        let (original, _, _) = fixture(false);
        let mut program = original.program;
        program.states[0].kind = crate::ir::StateKind::Real;
        program.events[0].trigger = EventTrigger::Timer {
            start: 1.0,
            period: 1.0,
            time_tolerance: 1e-12,
            enabled: true,
        };
        program.events[0].body = serde_json::from_value(serde_json::json!([
            {"kind":"assign", "state":0,"rhs":{"op":"add",
                "left":{"op":"multiply","left":{"op":"affine","constant":1e16,"terms":[]},
                    "right":{"op":"state","state":0}},
                "right":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]}}}
        ]))
        .unwrap();
        // The fixture uses 0-y on the left, so y=state-1e16.
        program.contributions[0].rhs = serde_json::from_value(serde_json::json!({
            "op":"add", "left":{"op":"affine","constant":1e16,"terms":[]},
            "right":{"op":"multiply","left":{"op":"affine","constant":-1,"terms":[]},
                "right":{"op":"state","state":0}}
        }))
        .unwrap();
        let mut model = EventModel::new(
            program,
            vec!["u".into()],
            Tolerances {
                absolute: 1e-12,
                relative: 1e-5,
            },
        )
        .unwrap();
        let trajectory = Trajectory::new(
            TransientInputs {
                pwl: vec![vec![
                    [0.0, 1.0],
                    [0.75, 1.0],
                    [1.75, 1.0f64.next_up()],
                    [2.0, 0.0],
                    [3.0, 0.0],
                ]],
                output_times: vec![0.0, 1.0, 2.0, 3.0],
                stop: 3.0,
                max_step: 3.0,
            },
            1,
        )
        .unwrap();
        let states = model.initial();
        let circuit = model.circuit(&states).unwrap();
        let before = Frame {
            time: 0.0,
            state_bounds: states.iter().copied().map(I::point).collect(),
            states,
            solution: circuit.solve(&trajectory.values(0.0)).unwrap(),
            circuit,
            operators: Operators::default(),
        };
        let first = prepare_event(&model, &trajectory, &before, 1.0, &[0]).unwrap();
        // Exact PWL u(1)=1+2^-54 is not representable as a binary64 point.
        assert_eq!(first.states, [1.0]);
        assert!(first.state_bounds[0].hi > 1.0);
        let saved_bounds = first.state_bounds.clone();
        let saved_voltages = first.solution.voltages.clone();
        for _ in 0..2 {
            let error = prepare_event(&model, &trajectory, &first, 2.0, &[0])
                .err()
                .unwrap();
            assert_eq!(error.kind, "event_accuracy");
            assert_eq!(first.time, 1.0);
            assert_eq!(first.states, [1.0]);
            assert_eq!(first.state_bounds, saved_bounds);
            assert_eq!(first.solution.voltages, saved_voltages);
        }
        // A separately requested voltage budget covers the amplified bound;
        // reusing the failed certificate cache must match a fresh model.
        model.tolerances.absolute = 32.0;
        let retry = prepare_event(&model, &trajectory, &first, 2.0, &[0]).unwrap();
        let fresh = EventModel::new(
            model.program.clone(),
            model.driven.clone(),
            model.tolerances.clone(),
        )
        .unwrap();
        let clean_first = prepare_event(&fresh, &trajectory, &before, 1.0, &[0]).unwrap();
        let clean = prepare_event(&fresh, &trajectory, &clean_first, 2.0, &[0]).unwrap();
        assert_eq!(retry.states, clean.states);
        assert_eq!(retry.state_bounds, clean.state_bounds);
        assert_eq!(retry.solution.voltages, clean.solution.voltages);
        assert_eq!(first.state_bounds, saved_bounds);
    }

    fn fixture(inconsistent_after_event: bool) -> (EventModel, Trajectory, Frame) {
        // Handwritten IR: y=n, initially n=0. A second independent y=0
        // constraint makes the first event fail its post-update residual.
        let mut value = serde_json::json!({
            "schema_version": SCHEMA_VERSION, "nodes":["0","u","y"],
            "states":[{"instance":"dut","name":"n","kind":"integer","initial":0}],
            "contributions":[{"branch":{"instance":"dut","local_positive":"0","local_negative":"y","kind":"voltage"},
                "positive":0,"negative":2,"rhs":{"op":"multiply","left":{"op":"affine","constant":-1,"terms":[]},"right":{"op":"state","state":0}},
                "origin":{"source":"rollback.va","line":1,"column":1,"instance":"dut"}}],
            "events":[{"trigger":{"kind":"cross","guard":{"op":"affine","constant":-0.5,"terms":[{"node":1,"coefficient":1}]},
                "direction":0,"time_tolerance":1e-12,"expression_tolerance":1e-9},
                "body":[{"kind":"assign", "state":0,"rhs":{"op":"add","left":{"op":"state","state":0},"right":{"op":"affine","constant":1,"terms":[]}}}],
                "origin":{"source":"rollback.va","line":2,"column":1,"instance":"dut"}}]
        });
        if inconsistent_after_event {
            let mut constraint = value["contributions"][0].clone();
            constraint["branch"]["instance"] = "clamp".into();
            constraint["origin"]["instance"] = "clamp".into();
            constraint["rhs"] = serde_json::json!({"op":"affine","constant":0,"terms":[]});
            value["contributions"]
                .as_array_mut()
                .unwrap()
                .push(constraint);
        }
        let program: Program = serde_json::from_value(value).unwrap();
        let model = EventModel::new(program, vec!["u".into()], Tolerances::default()).unwrap();
        let trajectory = Trajectory::new(
            TransientInputs {
                pwl: vec![vec![[0.0, 0.0], [1.0, 1.0], [2.0, 0.0]]],
                output_times: vec![0.0, 2.0],
                stop: 2.0,
                max_step: 2.0,
            },
            1,
        )
        .unwrap();
        let circuit = model.circuit(&model.initial()).unwrap();
        let frame = Frame {
            time: 0.0,
            state_bounds: model.initial().into_iter().map(I::point).collect(),
            states: model.initial(),
            solution: circuit.solve(&trajectory.values(0.0)).unwrap(),
            circuit,
            operators: Operators::default(),
        };
        (model, trajectory, frame)
    }

    #[test]
    fn discarded_candidate_can_be_retried_without_double_counting() {
        let (model, trajectory, before) = fixture(false);
        let discarded = prepare_event(&model, &trajectory, &before, 0.5, &[0]).unwrap();
        assert_eq!(discarded.states, [1.0]);
        let accepted = prepare_event(&model, &trajectory, &before, 0.5, &[0]).unwrap();
        assert_eq!(before.time, 0.0);
        assert_eq!(before.states, [0.0]);
        assert_eq!(accepted.states, [1.0]);
        let next = prepare_event(&model, &trajectory, &accepted, 1.5, &[0]).unwrap();
        assert_eq!(next.states, [2.0]);
        assert_eq!(next.solution.voltages[2], 2.0);
    }

    #[test]
    fn failed_post_event_residual_does_not_commit_state_or_voltage() {
        let (model, trajectory, before) = fixture(true);
        for _ in 0..2 {
            let error = prepare_event(&model, &trajectory, &before, 0.5, &[0])
                .err()
                .unwrap();
            assert_eq!(error.kind, "residual_failure");
            assert_eq!(before.time, 0.0);
            assert_eq!(before.states, [0.0]);
            assert_eq!(before.solution.voltages[2], 0.0);
        }
    }

    #[test]
    fn integer_overflow_during_event_does_not_commit() {
        let (model, trajectory, mut before) = fixture(false);
        before.states[0] = 2147483647.0;
        before.circuit = model.circuit(&before.states).unwrap();
        before.solution = before.circuit.solve(&trajectory.values(0.0)).unwrap();
        let error = prepare_event(&model, &trajectory, &before, 0.5, &[0])
            .err()
            .unwrap();
        assert_eq!(error.kind, "state_range");
        assert_eq!(before.states, [2147483647.0]);
        assert_eq!(before.time, 0.0);
        assert_eq!(before.solution.voltages[2], 2147483647.0);
    }
    #[test]
    fn timer_batch_failure_and_discard_preserve_accepted_frame() {
        for inconsistent in [false, true] {
            let (original, trajectory, _) = fixture(inconsistent);
            let mut program = original.program;
            program.events[0].trigger = EventTrigger::Timer {
                start: 0.0,
                period: 0.5,
                time_tolerance: 0.001,
                enabled: true,
            };
            let model = EventModel::new(program, vec!["u".into()], Tolerances::default()).unwrap();
            let circuit = model.circuit(&model.initial()).unwrap();
            let before = Frame {
                time: 0.0,
                state_bounds: model.initial().into_iter().map(I::point).collect(),
                states: model.initial(),
                solution: circuit.solve(&trajectory.values(0.0)).unwrap(),
                circuit,
                operators: Operators::default(),
            };
            for _ in 0..2 {
                let trial = prepare_batch(&model, &trajectory, &before, 0.0, &[0]);
                if inconsistent {
                    assert_eq!(trial.err().unwrap().kind, "residual_failure");
                } else {
                    let (next, records) = trial.unwrap();
                    assert_eq!(next.states, [1.0]);
                    assert_eq!(records.len(), 1);
                    assert_eq!(records[0].kind, "timer");
                    assert_eq!(records[0].guard_value, None);
                    // Discarding a whole prepared batch does not consume timer(0).
                }
                assert_eq!(before.states, [0.0]);
                assert_eq!(before.time, 0.0);
                assert_eq!(before.solution.voltages[2], 0.0);
            }
        }
    }
    #[test]
    fn operator_queue_and_edges_commit_with_the_whole_frame() {
        use crate::ir::{Expression, OperatorSpec, Origin};
        for inconsistent in [false, true] {
            let (original, trajectory, _) = fixture(inconsistent);
            let mut program = original.program;
            program.operators.push(OperatorSpec::Transition {
                input: Expression::State { state: 0 },
                delay: 1.0,
                rise: 2.0,
                fall: 2.0,
                origin: Origin {
                    source: "rollback.va".into(),
                    line: 3,
                    column: 1,
                    instance: "dut".into(),
                    expansion: Vec::new(),
                },
            });
            program.contributions[0].rhs = Expression::Multiply {
                left: Box::new(Expression::Affine {
                    constant: -1.0,
                    terms: Vec::new(),
                }),
                right: Box::new(Expression::Operator { operator: 0 }),
            };
            let model = EventModel::new(program, vec!["u".into()], Tolerances::default()).unwrap();
            let states = model.initial();
            let operators =
                Operators::new(&model.program, &trajectory, &model.driven, &states).unwrap();
            let circuit = model
                .circuit_with(&states, &operators.values(0.0).unwrap())
                .unwrap();
            let before = Frame {
                time: 0.0,
                state_bounds: states.iter().copied().map(I::point).collect(),
                states,
                operators,
                solution: circuit.solve(&trajectory.values(0.0)).unwrap(),
                circuit,
            };
            if inconsistent {
                // The interval map now rejects the nonidentity y=operator,
                // y=0 constraint before any queued edge can be committed.
                for _ in 0..2 {
                    assert_eq!(
                        prepare_event(&model, &trajectory, &before, 0.5, &[0])
                            .err()
                            .unwrap()
                            .kind,
                        "event_accuracy"
                    );
                    assert_eq!(before.operators.next_breakpoint(0.0), None);
                    assert_eq!(before.states, [0.0]);
                }
                continue;
            }
            let first = prepare_event(&model, &trajectory, &before, 0.5, &[0]).unwrap();
            let replay = prepare_event(&model, &trajectory, &before, 0.5, &[0]).unwrap();
            assert_eq!(first.operators.next_breakpoint(0.5), Some(1.5));
            assert_eq!(replay.operators.next_breakpoint(0.5), Some(1.5));
            assert_eq!(before.operators.next_breakpoint(0.0), None);
            assert_eq!(before.states, [0.0]);
            for _ in 0..2 {
                let trial = prepare_event(&model, &trajectory, &first, 2.0, &[]);
                assert_eq!(trial.unwrap().solution.voltages[2], 0.25);
                assert_eq!(first.operators.next_breakpoint(0.5), Some(1.5));
                assert_eq!(first.solution.voltages[2], 0.0);
            }
            // A failed future trial did not consume the earlier deadline.
            let deadline = prepare_event(&model, &trajectory, &first, 1.5, &[]).unwrap();
            assert_eq!(deadline.solution.voltages[2], 0.0);
            assert_eq!(deadline.operators.next_breakpoint(1.5), Some(3.5));
        }
    }
    #[test]
    fn uncertain_operator_order_rejects_the_prepared_batch_before_commit() {
        use crate::ir::{Expression, OperatorSpec, Origin};
        let (original, trajectory, _) = fixture(false);
        let mut program = original.program;
        for (index, delay) in [0.1_f64, 0.1_f64.next_up()].into_iter().enumerate() {
            program.operators.push(OperatorSpec::Transition {
                input: Expression::State { state: 0 },
                delay,
                rise: 0.5,
                fall: 0.5,
                origin: Origin {
                    source: "rollback.va".into(),
                    line: 3 + index,
                    column: 1,
                    instance: "dut".into(),
                    expansion: Vec::new(),
                },
            });
        }
        let model = EventModel::new(program, vec!["u".into()], Tolerances::default()).unwrap();
        let states = model.initial();
        let operators =
            Operators::new(&model.program, &trajectory, &model.driven, &states).unwrap();
        let circuit = model
            .circuit_with(&states, &operators.values(0.0).unwrap())
            .unwrap();
        let before = Frame {
            time: 0.0,
            state_bounds: states.iter().copied().map(I::point).collect(),
            states,
            operators,
            solution: circuit.solve(&trajectory.values(0.0)).unwrap(),
            circuit,
        };
        for _ in 0..2 {
            let error = prepare_batch(&model, &trajectory, &before, 1.0, &[0])
                .err()
                .unwrap();
            assert!(error.message.contains("ordering of operator deadlines"));
            assert_eq!(before.states, [0.0]);
            assert_eq!(before.operators.next_breakpoint(0.0), None);
        }
    }
    #[test]
    fn repeated_integer_writes_retry_and_fail_without_committing() {
        for timer in [false, true] {
            for failure in [None, Some("residual_failure"), Some("state_range")] {
                let (original, trajectory, _) = fixture(failure == Some("residual_failure"));
                let mut program = original.program;
                if failure == Some("state_range") {
                    program.states[0].initial = 2147483646.0;
                }
                if timer {
                    program.events[0].trigger = EventTrigger::Timer {
                        start: 0.5,
                        period: 1.0,
                        time_tolerance: 0.001,
                        enabled: true,
                    };
                }
                let action = program.events[0].body[0].clone();
                program.events[0].body.push(action);
                let model =
                    EventModel::new(program, vec!["u".into()], Tolerances::default()).unwrap();
                let circuit = model.circuit(&model.initial()).unwrap();
                let before = Frame {
                    time: 0.0,
                    state_bounds: model.initial().into_iter().map(I::point).collect(),
                    states: model.initial(),
                    operators: Operators::new(
                        &model.program,
                        &trajectory,
                        &model.driven,
                        &model.initial(),
                    )
                    .unwrap(),
                    solution: circuit.solve(&trajectory.values(0.0)).unwrap(),
                    circuit,
                };
                for _ in 0..2 {
                    let trial = prepare_batch(&model, &trajectory, &before, 0.5, &[0]);
                    if let Some(kind) = failure {
                        assert_eq!(trial.err().unwrap().kind, kind);
                    } else {
                        let (next, records) = trial.unwrap();
                        assert_eq!(next.states, [2.0]);
                        assert_eq!(next.solution.voltages[2], 2.0);
                        assert_eq!(records.len(), 1);
                        let (second, _) =
                            prepare_batch(&model, &trajectory, &next, 1.5, &[0]).unwrap();
                        assert_eq!(second.states, [4.0]);
                    }
                    // Discarded/failed trials and certificate-cache reuse must
                    // never change the accepted frame or consume an increment.
                    assert_eq!(before.time, 0.0);
                    assert_eq!(before.states, model.initial());
                    assert_eq!(before.solution.voltages[2], before.states[0]);
                }
            }
        }
    }

    #[test]
    fn forward_error_failure_and_cached_retry_leave_frame_unchanged() {
        let (original, trajectory, _) = fixture(false);
        let mut program = original.program;
        program.states[0].kind = crate::ir::StateKind::Real;
        program.events[0].body = serde_json::from_value(serde_json::json!([
            {"kind":"assign", "state":0,"rhs":{"op":"affine","constant":1.0,"terms":[]}},
            {"kind":"assign", "state":0,"rhs":{"op":"add","left":{"op":"state","state":0},
                "right":{"op":"affine","constant":2_f64.powi(-55),"terms":[]}}},
            {"kind":"assign", "state":0,"rhs":{"op":"add","left":{"op":"state","state":0},
                "right":{"op":"affine","constant":-1.0,"terms":[]}}}
        ]))
        .unwrap();
        // Exact physical output is 2^-55, whereas the replay returns zero.
        let model = EventModel::new(
            program,
            vec!["u".into()],
            Tolerances {
                absolute: 1e-20,
                relative: 0.0,
            },
        )
        .unwrap();
        let circuit = model.circuit(&model.initial()).unwrap();
        let before = Frame {
            time: 0.0,
            state_bounds: model.initial().into_iter().map(I::point).collect(),
            states: model.initial(),
            operators: Operators::new(&model.program, &trajectory, &model.driven, &model.initial())
                .unwrap(),
            solution: circuit.solve(&trajectory.values(0.0)).unwrap(),
            circuit,
        };
        for _ in 0..2 {
            assert_eq!(
                prepare_event(&model, &trajectory, &before, 0.5, &[0])
                    .err()
                    .unwrap()
                    .kind,
                "event_accuracy"
            );
            assert_eq!(before.time, 0.0);
            assert_eq!(before.states, [0.0]);
            assert_eq!(before.solution.voltages[2], 0.0);
        }
    }
}
