//! One transaction for changed-event state and its matching future calendar.
use super::*;
use crate::schedule::{history_epoch, HistoryEpoch};

#[derive(Clone, Copy)]
pub(super) enum Strategy {
    Static,
    Held,
    History,
}

// Held roots already have their final certificates. History roots need the
// extended candidate trajectory, bounded first by independent deadlines.
pub(super) enum CalendarPlan {
    Held(Vec<ScheduledEvent>),
    History {
        pending: Vec<ScheduledEvent>,
        consumed: Vec<(usize, i8)>,
    },
}

impl CalendarPlan {
    fn horizon(&self, trajectory: &Trajectory) -> f64 {
        let pending = match self {
            Self::Held(future) => future,
            Self::History { pending, .. } => pending,
        };
        pending
            .first()
            .map_or(trajectory.config.stop, |event| event.time)
    }

    fn resolve(
        self,
        model: &EventModel,
        trajectory: &Trajectory,
        next: &Frame,
        until: f64,
    ) -> Result<Vec<ScheduledEvent>, Error> {
        match self {
            Self::Held(future) => Ok(future),
            Self::History { pending, consumed } => history_epoch(
                model,
                trajectory,
                &next.operators,
                HistoryEpoch {
                    states: &next.state_bounds,
                    after: Some(next.time),
                    until,
                    consumed: &consumed,
                    pending: &pending,
                },
            ),
        }
    }
}

impl Controller {
    pub(super) fn accept_changed_events(
        &mut self,
        model: &EventModel,
        trajectory: &Trajectory,
        calendar: &mut Vec<ScheduledEvent>,
        strategy: Strategy,
    ) -> Result<(), Error> {
        // Close old-flow observation/reset before predicting changed flow.
        // All subsequent work owns a candidate; the accepted frame, event
        // cursor, records and old calendar remain intact on every error.
        let time = calendar[self.event].time;
        let (mut next, records, end) =
            self.prepare_events_until(model, trajectory, calendar, Some(time))?;
        self.prepare_physical_history(
            model,
            trajectory,
            &mut next,
            &calendar[self.event..end],
            &calendar[end..],
        )?;
        let plan = match strategy {
            Strategy::Static => {
                // The immutable static calendar keeps its original cursor.
                // Copy only the connected observation cluster and its next
                // deadline; cloning every remaining occurrence is quadratic.
                let mut cluster_end = end;
                let mut boundary = next.time;
                let mut steps = 0;
                while cluster_end < calendar.len() && calendar[cluster_end].bounds().lo <= boundary
                {
                    if calendar[cluster_end].time > boundary {
                        if steps >= 64 {
                            return Err(Error::new(
                                "event_budget",
                                "bounded static event closure exceeds 64 microevents",
                            ));
                        }
                        steps += 1;
                        boundary = calendar[cluster_end].time;
                    }
                    cluster_end += 1;
                }
                CalendarPlan::Held(calendar[end..(cluster_end + 1).min(calendar.len())].to_vec())
            }
            Strategy::Held => CalendarPlan::Held(self.prepare_held_future(
                model,
                trajectory,
                &next,
                &records,
                &calendar[end..],
            )?),
            Strategy::History => self.prepare_history_future(
                model,
                trajectory,
                &mut next,
                &calendar[self.event..end],
                &calendar[end..],
            )?,
        };
        {
            let (mut next, mut future) =
                Self::prepare_final_history(model, trajectory, next, plan)?;
            let mut records = records;
            let mut phases = vec![
                (self.accepted.clone(), Vec::new()),
                (next.clone(), calendar[self.event..end].to_vec()),
            ];
            let mut microevents = 0;
            let mut static_cursor = end;
            while future
                .first()
                .is_some_and(|event| event.bounds().lo <= next.time)
            {
                if microevents >= 64
                    || self.records.len() + records.len() >= crate::schedule::EVENT_BUDGET
                {
                    return Err(Error::new("event_budget","bounded causal event closure exceeds 64 microevents or the global event budget"));
                }
                let candidate = Controller {
                    accepted: next,
                    event: 0,
                    records: Vec::new(),
                    outputs: Vec::new(),
                };
                let time = future[0].time;
                let (mut following, new_records, end) =
                    candidate.prepare_events_until(model, trajectory, &future, Some(time))?;
                let physical_batch = future[..end].to_vec();
                static_cursor += end;
                candidate.prepare_physical_history(
                    model,
                    trajectory,
                    &mut following,
                    &future[..end],
                    &future[end..],
                )?;
                let plan = match strategy {
                    Strategy::Static => CalendarPlan::Held(future[end..].to_vec()),
                    Strategy::Held => CalendarPlan::Held(candidate.prepare_held_future(
                        model,
                        trajectory,
                        &following,
                        &new_records,
                        &future[end..],
                    )?),
                    Strategy::History => candidate.prepare_history_future(
                        model,
                        trajectory,
                        &mut following,
                        &future[..end],
                        &future[end..],
                    )?,
                };
                (next, future) = Self::prepare_final_history(model, trajectory, following, plan)?;
                records.extend(new_records);
                phases.push((next.clone(), physical_batch));
                microevents += 1;
            }
            // Prepare every requested phase observation before publication.
            // Cloned queries cannot alter the candidate's physical sequence.
            let mut outputs = Vec::new();
            for &time in &trajectory.config.output_times {
                if time <= self.accepted.time || time >= next.time {
                    continue;
                }
                let mut phase = &phases[0].0;
                for (frame, physical_batch) in &phases[1..] {
                    let mut occurred = true;
                    for event in physical_batch {
                        occurred &= match event.physical_order_at(time) {
                            Some(std::cmp::Ordering::Less | std::cmp::Ordering::Equal) => true,
                            Some(std::cmp::Ordering::Greater) => false,
                            None => {
                                return Err(Error::new(
                                    "event_resolution",
                                    "output query cannot certify its physical event phase",
                                ))
                            }
                        };
                    }
                    if !occurred {
                        break;
                    }
                    phase = frame;
                }
                outputs.push(prepare_root_window(
                    model,
                    trajectory,
                    phase,
                    EventMoment {
                        representative: time,
                        observation: I::point(time),
                        fired_roots: &[],
                        prediction_end: time,
                    },
                    &[],
                )?);
            }
            self.commit_events(
                next,
                records,
                if matches!(strategy, Strategy::Static) {
                    static_cursor
                } else {
                    0
                },
            );
            self.outputs = outputs;
            if !matches!(strategy, Strategy::Static) {
                *calendar = future;
            }
            Ok(())
        }
    }

    #[cfg(test)]
    fn finish_changed_events(
        &mut self,
        model: &EventModel,
        trajectory: &Trajectory,
        calendar: &mut Vec<ScheduledEvent>,
        next: Frame,
        records: Vec<EventRecord>,
        plan: CalendarPlan,
    ) -> Result<(), Error> {
        let (next, future) = Self::prepare_final_history(model, trajectory, next, plan)?;
        self.commit_events(next, records, 0);
        *calendar = future;
        Ok(())
    }
    fn prepare_final_history(
        model: &EventModel,
        trajectory: &Trajectory,
        mut next: Frame,
        plan: CalendarPlan,
    ) -> Result<(Frame, Vec<ScheduledEvent>), Error> {
        let until = plan.horizon(trajectory);
        next.operators = next.operators.evaluation(next.time)?.advanced_until(
            I::point(next.time),
            &next.states,
            &next.state_bounds,
            &[],
            until,
        )?;
        let future = plan.resolve(model, trajectory, &next, until)?;
        next.operators
            .check_deadline_order(next.time, future.first().map(|event| event.bounds()))?;
        // Nonlinear extension can widen the endpoint enclosure. Certify the
        // stored observation against the final history, not just reset closure.
        let inputs = trajectory.value_bounds(next.time);
        model.certify(
            &model.conditions.select(&[], &inputs)?,
            &inputs,
            &next.state_bounds,
            &next.operators.bounds(next.time)?,
            &next.solution.voltages,
            &next.states,
        )?;
        // No fallible operation may split state and matching calendar publication.
        Ok((next, future))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn history_final_fixture() -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
        let (base, trajectory, mut controller, _) =
            super::super::lifecycle_controller_tests::history_guard_fixture();
        let mut program = base.program;
        // Keep only the .25 threshold change and z=t history cross. Removing
        // the independent .5 cross lets history_epoch localize the new .625
        // root in the extended trajectory, rather than an empty early epoch.
        program.events.truncate(2);
        let model = EventModel::new(program, base.driven, base.tolerances).unwrap();
        assert!(!model.guard_operators[1].is_empty());
        let (operators, calendar) =
            history_calendar::initialize(&model, &trajectory, &controller.accepted.states).unwrap();
        controller.accepted.operators = operators;
        (model, trajectory, controller, calendar)
    }

    #[test]
    fn static_calendar_cursor_cluster_rollback_retry_and_successor_are_preserved() {
        let (base, trajectory, _, _) = super::super::lifecycle_controller_tests::fixture();
        let mut value = serde_json::to_value(&base.program).unwrap();
        value["operators"] = serde_json::json!([]);
        for contribution in value["contributions"].as_array_mut().unwrap() {
            contribution["rhs"] = serde_json::json!({"op":"state","state":0});
        }
        for state in value["states"].as_array_mut().unwrap() {
            state["initial"] = serde_json::json!(0);
        }
        let event = |start, period, state, constant| {
            serde_json::json!({
                "origin":value["events"][0]["origin"],
                "trigger":{"kind":"timer","start":start,"period":period,"time_tolerance":1e-6,"enabled":true},
                "body":[{"kind":"assign","state":state,"rhs":{"op":"affine","constant":constant,"terms":[]}}]
            })
        };
        let first = event(0.1, 0.2, 0, 1.);
        let close = event(0.30000000000000004, 0., 1, 1.);
        let conflict = event(0.30000000000000004, 0., 1, 2.);
        let successor = event(0.8, 0., 1, 3.);
        value["events"] = serde_json::json!([first, close, conflict, successor]);
        let make = |value| {
            let model = EventModel::new(
                serde_json::from_value(value).unwrap(),
                base.driven.clone(),
                base.tolerances.clone(),
            )
            .unwrap();
            let states = model.initial();
            let operators =
                Operators::new(&model.program, &trajectory, &model.driven, &states).unwrap();
            let calendar = independent_schedule(&model, &trajectory).unwrap();
            let circuit = model
                .circuit_with(&states, &operators.values(0.).unwrap())
                .unwrap();
            let controller = Controller {
                accepted: Frame {
                    time: 0.,
                    solution: circuit.solve(&[0.]).unwrap(),
                    circuit,
                    operators,
                    state_bounds: states.iter().copied().map(I::point).collect(),
                    states,
                },
                event: 0,
                records: vec![],
                outputs: vec![],
            };
            (model, controller, calendar)
        };
        let (bad, mut controller, mut calendar) = make(value.clone());
        let signature = |calendar: &Vec<ScheduledEvent>| {
            calendar
                .iter()
                .map(|e| (e.event, e.time, e.bounds()))
                .collect::<Vec<_>>()
        };
        let original = signature(&calendar);
        controller
            .accept_changed_events(&bad, &trajectory, &mut calendar, Strategy::Static)
            .unwrap();
        assert_eq!(controller.event, 1);
        assert_eq!(signature(&calendar), original);
        let before = controller.accepted.clone();
        let records = serde_json::to_value(&controller.records).unwrap();
        for _ in 0..2 {
            assert_eq!(
                controller
                    .accept_changed_events(&bad, &trajectory, &mut calendar, Strategy::Static)
                    .unwrap_err()
                    .kind,
                "event_conflict"
            );
            assert_eq!(controller.event, 1);
            assert_eq!(controller.accepted.time, before.time);
            assert_eq!(controller.accepted.states, before.states);
            assert_eq!(controller.accepted.state_bounds, before.state_bounds);
            assert_eq!(serde_json::to_value(&controller.records).unwrap(), records);
            assert_eq!(signature(&calendar), original);
        }
        value["events"][2]["body"] = serde_json::json!([]);
        let (good, mut clean, mut clean_calendar) = make(value);
        clean
            .accept_changed_events(&good, &trajectory, &mut clean_calendar, Strategy::Static)
            .unwrap();
        while controller.event < calendar.len() {
            controller
                .accept_changed_events(&good, &trajectory, &mut calendar, Strategy::Static)
                .unwrap();
            assert_eq!(signature(&calendar), original);
            clean
                .accept_changed_events(&good, &trajectory, &mut clean_calendar, Strategy::Static)
                .unwrap();
            assert_eq!(controller.event, clean.event);
            assert_eq!(controller.accepted.states, clean.accepted.states);
            assert_eq!(
                serde_json::to_value(&controller.records).unwrap(),
                serde_json::to_value(&clean.records).unwrap()
            );
        }
        assert_eq!(controller.accepted.states, [1., 3.]);
        assert_eq!(controller.records.len(), calendar.len());
        assert_eq!(controller.event, calendar.len());
    }

    #[test]
    fn history_final_certificate_refusal_preserves_controller_and_corrected_root_retry() {
        // z=t, q=.75 initially, timer(.25) changes q to .625. A legal history
        // plan must invalidate the .75 cross and produce .625 after extension.
        // Corrupt only candidate V(y)=q after event closure to isolate the
        // shared final voltage gate following actual history_epoch resolution.
        let (model, trajectory, mut controller, mut calendar) = history_final_fixture();
        let states = controller.accepted.states.clone();
        let bounds = controller.accepted.state_bounds.clone();
        let voltages = controller.accepted.solution.voltages.clone();
        let history = controller.accepted.operators.clone();
        let original: Vec<_> = calendar
            .iter()
            .map(|e| (e.time, e.event, e.bounds()))
            .collect();
        for _ in 0..2 {
            let (mut next, records, end) = controller
                .prepare_events_until(&model, &trajectory, &calendar, Some(0.25))
                .unwrap();
            let plan = controller
                .prepare_history_future(
                    &model,
                    &trajectory,
                    &mut next,
                    &calendar[controller.event..end],
                    &calendar[end..],
                )
                .unwrap();
            assert!(matches!(plan, CalendarPlan::History { .. }));
            assert!((next.solution.voltages[2] - 0.625).abs() < 1e-8);
            next.solution.voltages[2] += 0.01;
            let error = controller
                .finish_changed_events(&model, &trajectory, &mut calendar, next, records, plan)
                .unwrap_err();
            assert_eq!(error.kind, "waveform_accuracy");
            assert!(error.message.contains("same-time forward error at y:"));
            assert_eq!(controller.accepted.time, 0.);
            assert_eq!(controller.accepted.states, states);
            assert_eq!(controller.accepted.state_bounds, bounds);
            assert_eq!(controller.accepted.solution.voltages, voltages);
            assert!(controller.accepted.operators.same_reset_history(&history));
            assert_eq!(
                controller.accepted.operators.bounds(0.25).unwrap(),
                history.bounds(0.25).unwrap()
            );
            assert_eq!(controller.event, 0);
            assert!(controller.records.is_empty());
            assert_eq!(
                calendar
                    .iter()
                    .map(|e| (e.time, e.event, e.bounds()))
                    .collect::<Vec<_>>(),
                original
            );
        }
        controller
            .accept_history_events(&model, &trajectory, &mut calendar)
            .unwrap();
        assert_eq!(calendar.len(), 1);
        assert_eq!(calendar[0].event, 1);
        assert!((calendar[0].time - 0.625).abs() < 1e-9);
        let (clean_model, clean_trajectory, mut clean, mut clean_calendar) =
            history_final_fixture();
        clean
            .accept_history_events(&clean_model, &clean_trajectory, &mut clean_calendar)
            .unwrap();
        assert_eq!(controller.accepted.time, clean.accepted.time);
        assert_eq!(controller.accepted.states, clean.accepted.states);
        assert_eq!(
            controller.accepted.state_bounds,
            clean.accepted.state_bounds
        );
        assert_eq!(
            controller.accepted.solution.voltages,
            clean.accepted.solution.voltages
        );
        assert!(controller
            .accepted
            .operators
            .same_reset_history(&clean.accepted.operators));
        assert_eq!(
            controller.accepted.operators.bounds(1.).unwrap(),
            clean.accepted.operators.bounds(1.).unwrap()
        );
        assert_eq!(controller.event, clean.event);
        assert_eq!(
            serde_json::to_value(&controller.records).unwrap(),
            serde_json::to_value(&clean.records).unwrap()
        );
        assert_eq!(
            calendar
                .iter()
                .map(|e| (e.time, e.event, e.bounds()))
                .collect::<Vec<_>>(),
            clean_calendar
                .iter()
                .map(|e| (e.time, e.event, e.bounds()))
                .collect::<Vec<_>>()
        );
    }

    #[test]
    fn final_transition_deadline_refusal_preserves_controller_and_retry() {
        let (model, trajectory, mut controller, mut calendar) =
            super::super::lifecycle_controller_tests::fixture();
        // The event creates a transition start at exactly .625. The exact
        // binary-rational timer .1 + .525 is slightly later, but its enclosure
        // overlaps that start. User-event/operator ordering must be certified
        // by the final gate after candidate extension, before publication.
        let mut future_program = model.program.clone();
        future_program.events.truncate(1);
        future_program.events[0].trigger = serde_json::from_value(serde_json::json!({
            "kind":"timer", "start":0.1, "period":0.525,
            "time_tolerance":1e-12, "enabled":true,
        }))
        .unwrap();
        let future_model = EventModel::new(
            future_program,
            model.driven.clone(),
            model.tolerances.clone(),
        )
        .unwrap();
        let future: Vec<_> = independent_schedule(&future_model, &trajectory)
            .unwrap()
            .into_iter()
            .filter(|e| e.time > 0.5)
            .collect();
        assert!(future[0].bounds().lo <= 0.625 && future[0].bounds().hi >= 0.625);
        assert_ne!(future[0].bounds().lo, future[0].bounds().hi);
        let states = controller.accepted.states.clone();
        let bounds = controller.accepted.state_bounds.clone();
        let voltages = controller.accepted.solution.voltages.clone();
        let history = controller.accepted.operators.clone();
        let original: Vec<_> = calendar
            .iter()
            .map(|e| (e.time, e.event, e.bounds()))
            .collect();
        for _ in 0..2 {
            let (next, records, _) = controller
                .prepare_events_until(&model, &trajectory, &calendar, Some(0.5))
                .unwrap();
            assert_eq!(next.operators.next_breakpoint(0.5), Some(0.625));
            let error = controller
                .finish_changed_events(
                    &model,
                    &trajectory,
                    &mut calendar,
                    next,
                    records,
                    CalendarPlan::Held(future.clone()),
                )
                .unwrap_err();
            assert_eq!(error.kind, "event_resolution");
            assert!(error.message.contains("transition deadline ordering"));
            assert_eq!(controller.accepted.time, 0.);
            assert_eq!(controller.accepted.states, states);
            assert_eq!(controller.accepted.state_bounds, bounds);
            assert_eq!(controller.accepted.solution.voltages, voltages);
            assert!(controller.accepted.operators.same_reset_history(&history));
            assert_eq!(
                controller.accepted.operators.bounds(1.).unwrap(),
                history.bounds(1.).unwrap()
            );
            assert_eq!(
                controller.accepted.operators.next_breakpoint(0.),
                history.next_breakpoint(0.)
            );
            assert_eq!(controller.event, 0);
            assert!(controller.records.is_empty());
            assert_eq!(
                calendar
                    .iter()
                    .map(|e| (e.time, e.event, e.bounds()))
                    .collect::<Vec<_>>(),
                original
            );
        }
        controller
            .accept_relocalized(&model, &trajectory, &mut calendar)
            .unwrap();
        let (clean_model, clean_trajectory, mut clean, mut clean_calendar) =
            super::super::lifecycle_controller_tests::fixture();
        clean
            .accept_relocalized(&clean_model, &clean_trajectory, &mut clean_calendar)
            .unwrap();
        assert_eq!(controller.accepted.time, clean.accepted.time);
        assert_eq!(controller.accepted.states, clean.accepted.states);
        assert_eq!(
            controller.accepted.state_bounds,
            clean.accepted.state_bounds
        );
        assert_eq!(
            controller.accepted.solution.voltages,
            clean.accepted.solution.voltages
        );
        assert!(controller
            .accepted
            .operators
            .same_reset_history(&clean.accepted.operators));
        assert_eq!(
            controller.accepted.operators.bounds(0.75).unwrap(),
            clean.accepted.operators.bounds(0.75).unwrap()
        );
        assert_eq!(
            controller.accepted.operators.next_breakpoint(0.5),
            clean.accepted.operators.next_breakpoint(0.5)
        );
        assert_eq!(controller.event, clean.event);
        assert_eq!(
            serde_json::to_value(&controller.records).unwrap(),
            serde_json::to_value(&clean.records).unwrap()
        );
        assert_eq!(
            calendar
                .iter()
                .map(|e| (e.time, e.event, e.bounds()))
                .collect::<Vec<_>>(),
            clean_calendar
                .iter()
                .map(|e| (e.time, e.event, e.bounds()))
                .collect::<Vec<_>>()
        );
    }

    #[test]
    fn nonlinear_final_certificate_refusal_preserves_controller_and_corrected_retry() {
        // z'=z² until .5, then z'=-z². The true event observation is 2,
        // and the extended history ends at z(2)=.5. Deliberately corrupt only
        // the stored candidate observation after successful event closure.
        // This isolates the last voltage gate from earlier candidate checks;
        // removing that gate would publish an inaccurate observation.
        let (model, trajectory, mut controller, mut calendar) =
            super::super::lifecycle_controller_tests::nonlinear_horizon_fixture();
        let time = controller.accepted.time;
        let states = controller.accepted.states.clone();
        let bounds = controller.accepted.state_bounds.clone();
        let voltages = controller.accepted.solution.voltages.clone();
        let history = controller.accepted.operators.clone();
        let cursor = controller.event;
        let records = serde_json::to_value(&controller.records).unwrap();
        let original: Vec<_> = calendar
            .iter()
            .map(|e| (e.time, e.event, e.bounds()))
            .collect();
        for _ in 0..2 {
            let (mut next, candidate_records, _) = controller
                .prepare_events_until(&model, &trajectory, &calendar, Some(0.5))
                .unwrap();
            assert!((next.solution.voltages[1] - 2.).abs() < 1e-9);
            next.solution.voltages[1] += 0.01;
            let error = controller
                .finish_changed_events(
                    &model,
                    &trajectory,
                    &mut calendar,
                    next,
                    candidate_records,
                    CalendarPlan::Held(vec![]),
                )
                .unwrap_err();
            assert_eq!(error.kind, "waveform_accuracy");
            assert!(
                error
                    .message
                    .contains("cannot certify same-time forward error at y:"),
                "{}",
                error.message
            );
            assert_eq!(controller.accepted.time, time);
            assert_eq!(controller.accepted.states, states);
            assert_eq!(controller.accepted.state_bounds, bounds);
            assert_eq!(controller.accepted.solution.voltages, voltages);
            assert!(controller.accepted.operators.same_reset_history(&history));
            assert_eq!(
                controller.accepted.operators.bounds(0.5).unwrap(),
                history.bounds(0.5).unwrap()
            );
            assert_eq!(
                controller.accepted.operators.bounds(0.75).unwrap_err().kind,
                "event_resolution"
            );
            assert_eq!(controller.event, cursor);
            assert_eq!(serde_json::to_value(&controller.records).unwrap(), records);
            assert_eq!(
                calendar
                    .iter()
                    .map(|e| (e.time, e.event, e.bounds()))
                    .collect::<Vec<_>>(),
                original
            );
        }
        controller
            .accept_relocalized(&model, &trajectory, &mut calendar)
            .unwrap();
        let (clean_model, clean_trajectory, mut clean, mut clean_calendar) =
            super::super::lifecycle_controller_tests::nonlinear_horizon_fixture();
        clean
            .accept_relocalized(&clean_model, &clean_trajectory, &mut clean_calendar)
            .unwrap();
        assert_eq!(controller.accepted.time, clean.accepted.time);
        assert_eq!(controller.accepted.states, clean.accepted.states);
        assert_eq!(
            controller.accepted.state_bounds,
            clean.accepted.state_bounds
        );
        assert_eq!(
            controller.accepted.solution.voltages,
            clean.accepted.solution.voltages
        );
        assert!(controller
            .accepted
            .operators
            .same_reset_history(&clean.accepted.operators));
        let future = controller.accepted.operators.bounds(2.).unwrap();
        assert!(future[0].lo <= 0.5 && future[0].hi >= 0.5);
        assert_eq!(future, clean.accepted.operators.bounds(2.).unwrap());
        assert_eq!(controller.event, clean.event);
        assert_eq!(
            serde_json::to_value(&controller.records).unwrap(),
            serde_json::to_value(&clean.records).unwrap()
        );
        assert_eq!(
            calendar
                .iter()
                .map(|e| (e.time, e.event, e.bounds()))
                .collect::<Vec<_>>(),
            clean_calendar
                .iter()
                .map(|e| (e.time, e.event, e.bounds()))
                .collect::<Vec<_>>()
        );
    }
}
