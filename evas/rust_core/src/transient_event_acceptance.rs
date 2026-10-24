//! One transaction for changed-event state and its matching future calendar.
use super::*;
use crate::schedule::HistoryEpoch;

#[cfg(test)]
type FinalCandidateHook = Box<dyn FnMut(&mut Frame)>;

#[cfg(test)]
thread_local! {
    static FINAL_CANDIDATE_HOOK: std::cell::RefCell<Option<FinalCandidateHook>> =
        std::cell::RefCell::new(None);
}

#[cfg(test)]
pub(super) fn test_with_final_candidate<R>(
    hook: impl FnMut(&mut Frame) + 'static,
    body: impl FnOnce() -> R,
) -> R {
    struct Restore(Option<FinalCandidateHook>);
    impl Drop for Restore {
        fn drop(&mut self) {
            FINAL_CANDIDATE_HOOK.with(|slot| *slot.borrow_mut() = self.0.take());
        }
    }
    let _restore = Restore(FINAL_CANDIDATE_HOOK.with(|slot| slot.replace(Some(Box::new(hook)))));
    body()
}

#[derive(Clone, Copy)]
pub(super) enum Strategy {
    Static,
    Held,
    History,
}

// Only the first static batch sees the complete calendar. Later batches
// consume the connected cluster and next deadline already selected from it.
#[derive(Clone, Copy)]
enum CalendarScope {
    Complete,
    Bounded,
}

struct PreparedBatch {
    frame: Frame,
    records: Vec<EventRecord>,
    end: usize,
    future: Vec<ScheduledEvent>,
}

// Calendar IDs name trigger leaves; isolation is certified for event bodies
// from the complete original IR, not from the selected mode or state changes.
pub(super) fn passive_batch(model: &EventModel, batch: &[ScheduledEvent]) -> bool {
    !batch.is_empty()
        && batch
            .iter()
            .all(|event| model.passive_events[model.triggers[event.event].event])
}

// Passive callbacks change observer state, never physical history. A timed
// runtime advanced to b may already have consumed an edge, so a query below b
// must advance the immutable pre-suffix seed instead of reading it backwards.
fn observation_seed(
    model: &EventModel,
    phases: &[(Frame, Vec<ScheduledEvent>)],
    phase: usize,
    time: f64,
) -> Result<Frame, Error> {
    let mut seed = if let Some(g) = &model.forcing {
        phases[phase].0.charge_forcing_copy(g)?;
        phases[phase].0.clone()
    } else {
        phases[phase].0.candidate_clone()?
    };
    let mut physical = phase;
    while physical > 0 && passive_batch(model, &phases[physical].1) {
        physical -= 1;
    }
    if physical != phase {
        seed.operators = if model.forcing.is_some() {
            phases[physical].0.operators.forcing_clone()?
        } else {
            phases[physical].0.operators.candidate_clone()?
        };
    }
    seed.operators.rebase_source_observation(time)?;
    Ok(seed)
}

#[cfg(test)]
pub(super) fn test_observation_seed(
    model: &EventModel,
    phases: &[(Frame, Vec<ScheduledEvent>)],
    phase: usize,
    time: f64,
) -> Result<Frame, Error> {
    observation_seed(model, phases, phase, time)
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
        batch: Option<&[ScheduledEvent]>,
    ) -> Result<Vec<ScheduledEvent>, Error> {
        match self {
            Self::Held(future) => Ok(future),
            Self::History { pending, consumed } => {
                crate::schedule::history_epoch_with_time_proofs_and_boundary(
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
                    Some(&next.time_proofs),
                    batch,
                )
            }
        }
    }
}

// A fully prepared cluster owns every value needed for publication. Construct
// it using immutable accepted state; no candidate round or query can publish.
struct PreparedEvents {
    frame: Frame,
    records: Vec<EventRecord>,
    outputs: Vec<Frame>,
    calendar: CalendarUpdate,
}

// Static calendars retain their original storage and advance a cursor. The
// relocalized strategies replace the calendar and start at cursor zero.
enum CalendarUpdate {
    StaticCursor(usize),
    Replace(Vec<ScheduledEvent>),
}

impl PreparedEvents {
    fn prepare(
        controller: &Controller,
        model: &EventModel,
        trajectory: &Trajectory,
        calendar: &[ScheduledEvent],
        strategy: Strategy,
    ) -> Result<Self, Error> {
        let work = model.analytic_request.as_ref().map(|token| token.work());
        // Keep the original entry and per-visit costs. Charge only reached
        // batches/phases, rather than the Cartesian product of all requested
        // observations and all future calendar entries on every transaction.
        let scan = || -> Result<(), Error> {
            if let Some(w) = work {
                w.debit(2, 128)?;
            }
            Ok(())
        };
        let batch_storage = |events: &[ScheduledEvent], first: usize| -> Result<(), Error> {
            if let Some(w) = work {
                let row =
                    (model.program.nodes.len() * 8 + model.program.states.len() * 16 + 512) as u64;
                let end = crate::schedule::batch_end(events, first, model)?;
                for _event in &events[first..end] {
                    scan()?;
                    // Preserve the original per-leaf record/state storage
                    // allowance before prepare_changed_batch allocates it.
                    w.debit(2, row)?;
                }
            }
            Ok(())
        };
        fn reserve_candidate<T>(
            values: &mut Vec<T>,
            additional: usize,
            work: Option<&crate::transition_source_plan::Work>,
        ) -> Result<(), Error> {
            let required = values.len().saturating_add(additional);
            if required > values.capacity() {
                let capacity = required.max(values.capacity().saturating_mul(2)).max(4);
                if let Some(w) = work {
                    let words =
                        std::mem::size_of::<T>().div_ceil(std::mem::size_of::<usize>()) as u64;
                    // The new allocation and movement of existing shallow
                    // entries are paid before either happens. Deep ownership
                    // stays with candidate_clone/copy_calendar.
                    w.debit(
                        2,
                        (capacity as u64)
                            .saturating_add(values.len() as u64)
                            .saturating_mul(words),
                    )?;
                }
                values.reserve_exact(capacity - values.len());
            }
            Ok(())
        }
        if let Some(w) = work {
            w.debit(2, 16_384)?;
        }
        batch_storage(calendar, controller.event)?;
        // Close old-flow observation/reset before predicting changed flow.
        // All subsequent work owns a candidate; the accepted frame, event
        // cursor, records and old calendar remain intact on every error.
        let PreparedBatch {
            frame: mut next,
            mut records,
            end,
            mut future,
        } = controller.prepare_changed_batch(
            model,
            trajectory,
            calendar,
            strategy,
            CalendarScope::Complete,
        )?;
        if let Some(g) = &model.forcing {
            controller.accepted.charge_forcing_copy(g)?;
            next.charge_forcing_copy(g)?;
        }
        let mut phases = Vec::new();
        reserve_candidate(&mut phases, 2, work)?;
        phases.push((controller.accepted.candidate_clone()?, Vec::new()));
        phases.push((
            next.candidate_clone()?,
            crate::schedule::copy_calendar(&calendar[controller.event..end], model)?,
        ));
        let mut microevents = 0;
        let mut static_cursor = end;
        loop {
            // A forced point owns an accepted prefix. Its physical phase must
            // follow every consumed batch and precede the retained successor.
            // This also covers a point below a rounded event representative:
            // local history preserves the exact clock and physical seed.
            let mut forced = None;
            for &time in &trajectory.config.strobetimes {
                scan()?;
                if time <= controller.accepted.time || time > next.time {
                    continue;
                }
                let mut after_phases = true;
                'phases: for (_, batch) in &phases[1..] {
                    scan()?;
                    for event in batch {
                        scan()?;
                        if !matches!(
                            event_order(model, trajectory, event, time)?,
                            Some(std::cmp::Ordering::Less | std::cmp::Ordering::Equal)
                        ) {
                            after_phases = false;
                            break 'phases;
                        }
                    }
                }
                if !after_phases {
                    continue;
                }
                let before_future = match future.first() {
                    Some(event) => {
                        event_order(model, trajectory, event, time)?
                            == Some(std::cmp::Ordering::Greater)
                    }
                    None => true,
                };
                if before_future {
                    forced = Some(time);
                    break;
                }
            }
            if let Some(time) = forced {
                if time != next.time {
                    let seed = observation_seed(model, &phases, phases.len() - 1, time)?;
                    next = prepare_root_window(
                        model,
                        trajectory,
                        &seed,
                        EventMoment {
                            exact_root: None,
                            occurrence_certified: false,
                            representative: time,
                            observation: I::point(time),
                            fired_roots: &[],
                            prediction_end: prediction_end(model, trajectory, future.first()),
                        },
                        &[],
                    )?;
                }
                break;
            }
            let future_due = future
                .first()
                .map(|event| event_bounds(model, event))
                .transpose()?
                .is_some_and(|bounds| bounds.lo <= next.time);
            if !future_due {
                break;
            }
            if microevents >= crate::schedule::CAUSAL_MICROEVENT_BUDGET
                || controller.records.len() + records.len() >= crate::schedule::EVENT_BUDGET
            {
                return Err(Error::new("event_budget","bounded causal event closure exceeds 64 microevents or the global event budget"));
            }
            let candidate = Controller {
                accepted: next,
                event: 0,
                records: Vec::new(),
                outputs: Vec::new(),
            };
            batch_storage(&future, 0)?;
            let batch = candidate.prepare_changed_batch(
                model,
                trajectory,
                &future,
                strategy,
                CalendarScope::Bounded,
            )?;
            let physical_batch = crate::schedule::copy_calendar(&future[..batch.end], model)?;
            static_cursor += batch.end;
            next = batch.frame;
            future = batch.future;
            reserve_candidate(&mut records, batch.records.len(), work)?;
            records.extend(batch.records);
            let phase = if let Some(g) = &model.forcing {
                next.charge_forcing_copy(g)?;
                next.clone()
            } else {
                next.candidate_clone()?
            };
            reserve_candidate(&mut phases, 1, work)?;
            phases.push((phase, physical_batch));
            microevents += 1;
        }
        // Prepare every requested phase observation before publication.
        // Cloned queries cannot alter the candidate's physical sequence.
        let mut outputs = Vec::new();
        for &time in &trajectory.config.output_times {
            scan()?;
            if time <= controller.accepted.time || time >= next.time {
                continue;
            }
            let mut phase = 0;
            for (index, (_, physical_batch)) in phases.iter().enumerate().skip(1) {
                scan()?;
                let mut occurred = true;
                for event in physical_batch {
                    scan()?;
                    occurred &= match event_order(model, trajectory, event, time)? {
                        Some(std::cmp::Ordering::Less | std::cmp::Ordering::Equal) => true,
                        Some(std::cmp::Ordering::Greater) => false,
                        None => {
                            record_ambiguous_event(model, event, "event_acceptance.phase", time)?;
                            return Err(Error::new(
                                "event_resolution",
                                "output query cannot certify its physical event phase",
                            ));
                        }
                    };
                }
                if !occurred {
                    break;
                }
                phase = index;
            }
            let seed = observation_seed(model, &phases, phase, time)?;
            reserve_candidate(&mut outputs, 1, work)?;
            outputs.push(prepare_root_window(
                model,
                trajectory,
                &seed,
                EventMoment {
                    exact_root: None,
                    occurrence_certified: false,
                    representative: time,
                    observation: I::point(time),
                    fired_roots: &[],
                    prediction_end: time,
                },
                &[],
            )?);
        }
        Ok(Self {
            frame: next,
            records,
            outputs,
            calendar: if matches!(strategy, Strategy::Static) {
                CalendarUpdate::StaticCursor(static_cursor)
            } else {
                CalendarUpdate::Replace(future)
            },
        })
    }

    // Consuming the result publishes exactly once, with no fallible work
    // between the frame, cursor, records, outputs and matching calendar.
    fn publish(self, controller: &mut Controller, calendar: &mut Vec<ScheduledEvent>) {
        let end = match &self.calendar {
            CalendarUpdate::StaticCursor(end) => *end,
            CalendarUpdate::Replace(_) => 0,
        };
        controller.commit_events(self.frame, self.records, end);
        controller.outputs = self.outputs;
        if let CalendarUpdate::Replace(future) = self.calendar {
            *calendar = future;
        }
    }
}

// Exercise the real full candidate without publishing it or consuming its calendar.
// This test-only bridge keeps PreparedEvents and production entry points private.
#[cfg(test)]
pub(super) fn test_prepare_discard_changed_events(
    controller: &Controller,
    model: &EventModel,
    trajectory: &Trajectory,
    calendar: &[ScheduledEvent],
    strategy: Strategy,
    inspect: impl FnOnce(&Frame),
) -> Result<(), Error> {
    let candidate = PreparedEvents::prepare(controller, model, trajectory, calendar, strategy)?;
    inspect(&candidate.frame);
    drop(candidate);
    Ok(())
}

impl Controller {
    pub(super) fn accept_changed_events(
        &mut self,
        model: &EventModel,
        trajectory: &Trajectory,
        calendar: &mut Vec<ScheduledEvent>,
        strategy: Strategy,
    ) -> Result<(), Error> {
        if let Some(graph) = &model.forcing {
            graph.ensure_live()?;
        }
        if let Some(source) = &model.source_context {
            // A shared event-source quota stays exhausted before a retry can
            // copy histories or start any other candidate preparation.
            source.charge(0)?;
        }
        let prepared = PreparedEvents::prepare(self, model, trajectory, calendar, strategy)?;
        prepared.publish(self, calendar);
        Ok(())
    }

    // Own one candidate batch through observation, history and calendar
    // certification. The caller alone owns causal closure and publication.
    fn prepare_changed_batch(
        &self,
        model: &EventModel,
        trajectory: &Trajectory,
        calendar: &[ScheduledEvent],
        strategy: Strategy,
        scope: CalendarScope,
    ) -> Result<PreparedBatch, Error> {
        let time = calendar[self.event].time;
        let (mut next, records, end, physical_phase) = self.prepare_events_until_phase(
            model,
            trajectory,
            calendar,
            Some(time),
            matches!(strategy, Strategy::Static),
        )?;
        let plan = match strategy {
            Strategy::Static => {
                // The immutable static calendar keeps its original cursor.
                // Copy only the connected observation cluster and its next
                // deadline; cloning every remaining occurrence is quadratic.
                let future = match scope {
                    CalendarScope::Complete => {
                        let mut cluster_end = end;
                        let mut boundary = next.time;
                        let mut steps = 0;
                        while cluster_end < calendar.len()
                            && event_bounds(model, &calendar[cluster_end])?.lo <= boundary
                        {
                            if steps >= crate::schedule::CAUSAL_MICROEVENT_BUDGET {
                                return Err(Error::new(
                                    "event_budget",
                                    "bounded static event closure exceeds 64 microevents",
                                ));
                            }
                            steps += 1;
                            boundary = boundary.max(calendar[cluster_end].time);
                            cluster_end = crate::schedule::batch_end(calendar, cluster_end, model)?;
                        }
                        crate::schedule::copy_calendar(
                            &calendar[end..(cluster_end + 1).min(calendar.len())],
                            model,
                        )?
                    }
                    CalendarScope::Bounded => {
                        crate::schedule::copy_calendar(&calendar[end..], model)?
                    }
                };
                self.prepare_physical_history(
                    model,
                    trajectory,
                    &mut next,
                    &calendar[self.event..end],
                    &future,
                )?;
                CalendarPlan::Held(future)
            }
            Strategy::Held => {
                let future = self.prepare_held_future(
                    model,
                    trajectory,
                    &next,
                    &records,
                    &calendar[end..],
                    &calendar[self.event..end],
                )?;
                self.prepare_physical_history(
                    model,
                    trajectory,
                    &mut next,
                    &calendar[self.event..end],
                    &future,
                )?;
                CalendarPlan::Held(future)
            }
            Strategy::History => self.prepare_history_future(
                model,
                trajectory,
                &mut next,
                &calendar[self.event..end],
                &calendar[end..],
            )?,
        };
        let (frame, future) = Self::prepare_final_history_phase(
            model,
            trajectory,
            next,
            plan,
            Some(&calendar[self.event..end]),
            physical_phase
                .as_ref()
                .map(|(root, bounds)| (root, *bounds)),
        )?;
        Ok(PreparedBatch {
            frame,
            records,
            end,
            future,
        })
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
    pub(super) fn prepare_final_history(
        model: &EventModel,
        trajectory: &Trajectory,
        next: Frame,
        plan: CalendarPlan,
    ) -> Result<(Frame, Vec<ScheduledEvent>), Error> {
        Self::prepare_final_history_phase(model, trajectory, next, plan, None, None)
    }
    fn prepare_final_history_phase(
        model: &EventModel,
        trajectory: &Trajectory,
        mut next: Frame,
        plan: CalendarPlan,
        batch: Option<&[ScheduledEvent]>,
        physical_phase: Option<(&crate::exact_source::RootTime, I)>,
    ) -> Result<(Frame, Vec<ScheduledEvent>), Error> {
        let until = plan.horizon(trajectory);
        let evaluation = if let Some((root, bounds)) = physical_phase {
            next.operators
                .evaluation_at_root(next.time, Some(root), bounds)?
        } else {
            next.operators.evaluation(next.time)?
        };
        next.operators = evaluation.advanced_until_with_time_proofs(
            physical_phase.map_or(I::point(next.time), |(_, bounds)| bounds),
            &next.states,
            &next.state_bounds,
            &[],
            until,
            None,
            Some(&next.time_proofs),
        )?;
        let future = plan.resolve(model, trajectory, &next, until, batch)?;
        if physical_phase.is_some() && !future.first().is_some_and(|event| event.time == next.time)
        {
            return Err(Error::new(
                "event_resolution",
                "physical phase lost its certified pending successor",
            ));
        }
        next.operators.check_deadline_order(
            next.time,
            future
                .first()
                .map(|event| event_bounds(model, event))
                .transpose()?,
            future
                .first()
                .map(|e| event_root(model, std::slice::from_ref(e)))
                .transpose()?
                .flatten(),
        )?;
        // Nonlinear extension can widen the endpoint enclosure. Certify the
        // stored observation against the final history, not just reset closure.
        #[cfg(test)]
        FINAL_CANDIDATE_HOOK.with(|slot| {
            if let Some(hook) = slot.borrow_mut().as_mut() {
                hook(&mut next);
            }
        });
        let inputs = if let Some((root, _)) = physical_phase {
            root_epoch_phase::physical_inputs(
                model,
                trajectory,
                root,
                crate::real_expression::work(model),
            )?
        } else {
            trajectory.checked_value_bounds(next.time)?
        };
        let (operator_values, operator_bounds) = if let Some((root, bounds)) = physical_phase {
            let evaluation = next
                .operators
                .evaluation_at_root(next.time, Some(root), bounds)?;
            (evaluation.values, evaluation.bounds)
        } else {
            (
                next.operators.values(next.time)?,
                next.operators.bounds(next.time)?,
            )
        };
        // Legacy bounds certify the residual rows. Remove only an installed
        // source offset from this exact physical phase; a nonzero same-branch
        // residual remains live. Full original certificates are rechecked below.
        let projected = model
            .forcing
            .as_ref()
            .map(|g| g.legacy_voltage_view(next.time, &next.solution.voltages, &next.circuit))
            .transpose()?;
        let legacy_voltages = projected.as_deref().unwrap_or(&next.solution.voltages);
        let selection = model.observation_selection(
            &inputs,
            &next.states,
            &next.state_bounds,
            &operator_values,
            &operator_bounds,
        )?;
        let observation_proof = model
            .dc_projection
            .as_ref()
            .filter(|projection| projection.is_held_ramp())
            .map(|projection| {
                projection.observation_proof(
                    &model.program,
                    trajectory,
                    &model.driven,
                    next.time,
                    &next.state_bounds,
                    &next.time_proofs,
                )
            })
            .transpose()?
            .flatten();
        let (_, nodes) = if let Some(view) = next.circuit.procedure_occurrence() {
            view.plan.certificate(
                &model.program,
                &model.driven,
                model.tolerances.clone(),
                &inputs,
                &view.plan.base[..],
                &operator_bounds,
                legacy_voltages,
                &next.states,
                None,
                crate::real_expression::work(model),
            )?
        } else if let Some(proof) = &observation_proof {
            model.certify_observation_with_held_ramp_proof(
                &selection,
                &inputs,
                &next.state_bounds,
                &operator_bounds,
                legacy_voltages,
                &next.states,
                proof,
            )?
        } else {
            model.certify_observation(
                &selection,
                &inputs,
                &next.state_bounds,
                &operator_bounds,
                legacy_voltages,
                &next.states,
            )?
        };
        crate::observation::retain_bounds(&mut next.solution, nodes);
        if let Some(graph) = &model.forcing {
            graph.project(next.time, trajectory, &mut next.solution, &mut next.circuit)?;
        }
        // This certifies one batch; cluster closure and queries still precede publication.
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
        let (base, mut trajectory, _, _) = super::super::lifecycle_controller_tests::fixture();
        // Preserve an actual stored observation from the earlier accepted
        // transaction, not only an empty output buffer. Later closure phases
        // include .3, strictly before the exact .1+.2 physical timer.
        trajectory.config.output_times = vec![0., 0.05, 0.2, 0.3, 0.6, 0.9, 1.];
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
                    value_proofs: Default::default(),
                    time_proofs: Default::default(),
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
        assert_eq!(controller.outputs.len(), 1);
        assert_eq!(controller.outputs[0].time, 0.05);
        assert_eq!(controller.outputs[0].states, [0., 0.]);
        let before = controller.accepted.clone();
        let prior_outputs = controller.outputs.clone();
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
            assert_eq!(controller.outputs.len(), prior_outputs.len());
            for (actual, expected) in controller.outputs.iter().zip(&prior_outputs) {
                assert_eq!(actual.time, expected.time);
                assert_eq!(actual.states, expected.states);
                assert_eq!(actual.state_bounds, expected.state_bounds);
                assert_eq!(actual.solution.voltages, expected.solution.voltages);
                assert!(actual.operators.same_reset_history(&expected.operators));
                assert_eq!(
                    actual.operators.bounds(actual.time).unwrap(),
                    expected.operators.bounds(expected.time).unwrap()
                );
            }
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
            assert_eq!(controller.outputs.len(), clean.outputs.len());
            for (actual, expected) in controller.outputs.iter().zip(&clean.outputs) {
                assert_eq!(actual.time, expected.time);
                assert_eq!(actual.states, expected.states);
                assert_eq!(actual.state_bounds, expected.state_bounds);
                assert_eq!(actual.solution.voltages, expected.solution.voltages);
                assert!(actual.operators.same_reset_history(&expected.operators));
            }
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
    fn strobe_prefix_commits_and_failed_successor_retries_without_losing_it() {
        let (base, mut trajectory, _, _) = super::super::lifecycle_controller_tests::fixture();
        trajectory.config.output_times = vec![0., 0.3, 1.];
        trajectory.config.strobetimes = vec![0.3];
        let mut value = serde_json::to_value(&base.program).unwrap();
        value["operators"] = serde_json::json!([]);
        for contribution in value["contributions"].as_array_mut().unwrap() {
            contribution["rhs"] = serde_json::json!({"op":"state","state":0});
        }
        for state in value["states"].as_array_mut().unwrap() {
            state["initial"] = serde_json::json!(0);
        }
        let origin = value["events"][0]["origin"].clone();
        let event = |start, period, state, constant| {
            serde_json::json!({
                "origin":origin,
                "trigger":{"kind":"timer","start":start,"period":period,"time_tolerance":1e-6,"enabled":true},
                "body":[{"kind":"assign","state":state,"rhs":{"op":"affine","constant":constant,"terms":[]}}]
            })
        };
        value["events"] = serde_json::json!([
            event(0.1, 0.2, 1, 1.),
            event(0.3, 0., 0, 1.),
            event(0.30000000000000004, 0., 1, 2.),
            event(0.30000000000000004, 0., 1, 3.)
        ]);
        let model = EventModel::new(
            serde_json::from_value(value.clone()).unwrap(),
            base.driven.clone(),
            base.tolerances.clone(),
        )
        .unwrap();
        let states = model.initial();
        let operators =
            Operators::new(&model.program, &trajectory, &model.driven, &states).unwrap();
        let circuit = model
            .circuit_with(&states, &operators.values(0.).unwrap())
            .unwrap();
        let mut controller = Controller {
            accepted: Frame {
                value_proofs: Default::default(),
                time_proofs: Default::default(),
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
        let mut calendar = independent_schedule(&model, &trajectory).unwrap();
        for _ in 0..2 {
            controller
                .accept_changed_events(&model, &trajectory, &mut calendar, Strategy::Static)
                .unwrap();
        }
        assert_eq!(controller.accepted.time, 0.3);
        assert_eq!(controller.accepted.states, [1., 1.]);
        assert_eq!(controller.event, 2);
        assert!(controller.outputs.is_empty());
        let before = controller.accepted.clone();
        let records = serde_json::to_value(&controller.records).unwrap();
        let pending: Vec<_> = calendar
            .iter()
            .map(|e| (e.event, e.time, e.bounds()))
            .collect();
        for _ in 0..2 {
            assert_eq!(
                controller
                    .accept_changed_events(&model, &trajectory, &mut calendar, Strategy::Static)
                    .unwrap_err()
                    .kind,
                "event_conflict"
            );
            assert_eq!(controller.accepted.time, before.time);
            assert_eq!(controller.accepted.states, before.states);
            assert_eq!(controller.accepted.state_bounds, before.state_bounds);
            assert_eq!(
                controller.accepted.solution.voltages,
                before.solution.voltages
            );
            assert!(controller
                .accepted
                .operators
                .same_reset_history(&before.operators));
            assert_eq!(controller.event, 2);
            assert_eq!(serde_json::to_value(&controller.records).unwrap(), records);
            assert_eq!(
                calendar
                    .iter()
                    .map(|e| (e.event, e.time, e.bounds()))
                    .collect::<Vec<_>>(),
                pending
            );
        }
        value["events"][3]["body"] = serde_json::json!([]);
        let good = EventModel::new(
            serde_json::from_value(value).unwrap(),
            base.driven,
            base.tolerances,
        )
        .unwrap();
        while controller.event < calendar.len() {
            controller
                .accept_changed_events(&good, &trajectory, &mut calendar, Strategy::Static)
                .unwrap();
        }
        assert_eq!(controller.records.len(), calendar.len());
        assert_eq!(controller.accepted.states, [1., 1.]);
    }

    #[test]
    fn phase_query_failure_preserves_prior_outputs_and_retries_same_controller() {
        let (base, _, _, _) = super::super::lifecycle_controller_tests::fixture();
        let mut value = serde_json::to_value(&base.program).unwrap();
        let origin = value["events"][0]["origin"].clone();
        value["operators"] = serde_json::json!([]);
        value["states"][0]["initial"] = serde_json::json!(0.4);
        value["states"][1]["initial"] = serde_json::json!(0);
        for contribution in value["contributions"].as_array_mut().unwrap() {
            contribution["rhs"] = serde_json::json!({"op":"state","state":1});
        }
        value["events"] = serde_json::json!([
            {"origin":origin,"trigger":{"kind":"timer","start":0.01,"period":0,
                "time_tolerance":1e-6,"enabled":true},"body":[{"kind":"assign","state":0,
                "rhs":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":0.1}]}}]},
            {"origin":origin,"trigger":{"kind":"held_timer","start":{"op":"state","state":0},
                "period":{"op":"affine","constant":0,"terms":[]},"time_tolerance":1e-6,
                "enabled":{"op":"affine","constant":1,"terms":[]}},"body":[{"kind":"assign","state":1,
                "rhs":{"op":"add","left":{"op":"state","state":1},
                    "right":{"op":"affine","constant":1,"terms":[]}}}]}]);
        // A sampled .1*.3 is an interval, not an exact held-clock certificate.
        // .025 is a valid old-phase query; .03 is inside the uncertainty interval.
        let model = EventModel::new(
            serde_json::from_value(value).unwrap(),
            base.driven,
            base.tolerances,
        )
        .unwrap();
        let mut trajectory = Trajectory::new(
            crate::ir::TransientInputs {
                analytic_sources: vec![],
                pwl_errors_v: None,
                strobetimes: vec![],
                pwl: vec![vec![[0., 0.3], [0.5, 0.3]]],
                output_times: vec![0., 0.005, 0.025, 0.03, 0.5],
                stop: 0.5,
                max_step: 0.5,
            },
            1,
        )
        .unwrap();
        let make = || {
            let states = model.initial();
            let state_bounds: Vec<_> = states.iter().copied().map(I::point).collect();
            let operators =
                Operators::new(&model.program, &trajectory, &model.driven, &states).unwrap();
            let circuit = model
                .circuit_with(&states, &operators.values(0.).unwrap())
                .unwrap();
            let calendar = schedule_held(&model, &trajectory, &state_bounds).unwrap();
            (
                Controller {
                    accepted: Frame {
                        value_proofs: Default::default(),
                        time_proofs: Default::default(),
                        time: 0.,
                        solution: circuit.solve(&[0.3]).unwrap(),
                        circuit,
                        operators,
                        states,
                        state_bounds,
                    },
                    event: 0,
                    records: vec![],
                    outputs: vec![],
                },
                calendar,
            )
        };
        let (mut controller, mut calendar) = make();
        let (mut clean, mut clean_calendar) = make();
        controller
            .accept_relocalized(&model, &trajectory, &mut calendar)
            .unwrap();
        clean
            .accept_relocalized(&model, &trajectory, &mut clean_calendar)
            .unwrap();
        assert_eq!(controller.outputs.len(), 1);
        assert_eq!(controller.outputs[0].time, 0.005);
        let before = controller.accepted.clone();
        let prior_outputs = controller.outputs.clone();
        let records = serde_json::to_value(&controller.records).unwrap();
        let cursor = controller.event;
        let signature = |events: &[ScheduledEvent]| {
            events
                .iter()
                .map(|e| (e.event, e.time, e.bounds(), e.physical_order_at(0.03)))
                .collect::<Vec<_>>()
        };
        let old_calendar = signature(&calendar);
        let same = |a: &Frame, b: &Frame| {
            assert_eq!(a.time.to_bits(), b.time.to_bits());
            assert_eq!(a.states, b.states);
            assert_eq!(a.state_bounds, b.state_bounds);
            assert_eq!(
                serde_json::to_value(&a.solution).unwrap(),
                serde_json::to_value(&b.solution).unwrap()
            );
            assert!(a.operators.same_reset_history(&b.operators));
            for t in [a.time, 0.025, 0.03, 0.5] {
                assert_eq!(
                    a.operators.values(t).unwrap(),
                    b.operators.values(t).unwrap()
                );
                assert_eq!(
                    a.operators.bounds(t).unwrap(),
                    b.operators.bounds(t).unwrap()
                );
            }
        };
        for _ in 0..2 {
            let err = controller
                .accept_relocalized(&model, &trajectory, &mut calendar)
                .unwrap_err();
            assert_eq!(err.kind, "event_resolution");
            assert_eq!(
                err.message,
                "output query cannot certify its physical event phase"
            );
            same(&controller.accepted, &before);
            assert_eq!(signature(&calendar), old_calendar);
            assert_eq!(serde_json::to_value(&controller.records).unwrap(), records);
            assert_eq!(controller.event, cursor);
            assert_eq!(controller.outputs.len(), prior_outputs.len());
            for (a, b) in controller.outputs.iter().zip(&prior_outputs) {
                same(a, b);
            }
        }
        // Only remove the uncertifiable query. Retry on the same controller,
        // then compare its complete publication with the untouched controller.
        trajectory.config.output_times.retain(|&t| t != 0.03);
        controller
            .accept_relocalized(&model, &trajectory, &mut calendar)
            .unwrap();
        clean
            .accept_relocalized(&model, &trajectory, &mut clean_calendar)
            .unwrap();
        same(&controller.accepted, &clean.accepted);
        assert_eq!(controller.accepted.states[1], 1.);
        assert_eq!(controller.event, clean.event);
        assert_eq!(signature(&calendar), signature(&clean_calendar));
        assert_eq!(
            serde_json::to_value(&controller.records).unwrap(),
            serde_json::to_value(&clean.records).unwrap()
        );
        assert_eq!(controller.outputs.len(), 1);
        assert_eq!(controller.outputs[0].time, 0.025);
        assert_eq!(controller.outputs[0].states[1], 0.);
        for (a, b) in controller.outputs.iter().zip(&clean.outputs) {
            same(a, b);
        }
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
        assert_eq!(calendar[0].time, 0.625);
        assert_eq!(calendar[0].bounds(), I::point(0.625));
        assert_eq!(
            calendar[0].physical_order_at(0.625),
            Some(std::cmp::Ordering::Equal)
        );
        assert_eq!(
            calendar[0].physical_order_at(0.625_f64.next_down()),
            Some(std::cmp::Ordering::Greater)
        );
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

#[cfg(test)]
mod passive_seed_review {
    use super::*;
    use crate::ir::{Tolerances, TransientInputs};
    use serde_json::json;
    #[test]
    fn suffix_seed_preserves_selected_observer_state_and_stops_at_physical_or_mixed_batch() {
        let o = |s: &str| json!({"source":"seed.va","line":1,"column":1,"instance":s});
        let timer = |s: f64| json!({"kind":"timer","start":s,"period":0,"enabled":true,"time_tolerance":1e-6});
        let p=serde_json::from_value(json!({"schema_version":SCHEMA_VERSION,"nodes":["0","y"],
            "states":[{"instance":"D","name":"q","kind":"real","initial":0},{"instance":"M","name":"count","kind":"integer","initial":0}],
            "operators":[{"kind":"transition","input":{"op":"state","state":0},"delay":0,"rise":1,"fall":1,"origin":o("D")}],
            "contributions":[{"origin":o("D"),"branch":{"instance":"D","local_positive":"out","local_negative":"ref","kind":"voltage"},"positive":1,"negative":0,"rhs":{"op":"operator","operator":0}}],
            "events":[{"origin":o("M"),"trigger":{"kind":"or","triggers":[timer(0.6),timer(0.7)]},"body":[{"kind":"assign","state":1,"rhs":{"op":"affine","constant":1,"terms":[]}}]},
                {"origin":o("D"),"trigger":timer(1.1),"body":[{"kind":"assign","state":0,"rhs":{"op":"affine","constant":0,"terms":[]}}]}]})).unwrap();
        let model = EventModel::new(p, vec![], Tolerances::default()).unwrap();
        assert_eq!(model.passive_events, vec![true, false]);
        let trajectory = Trajectory::new(
            TransientInputs {
                analytic_sources: vec![],
                pwl_errors_v: None,
                pwl: vec![],
                output_times: vec![0., 0.75, 1.875, 2.5],
                strobetimes: vec![],
                stop: 2.5,
                max_step: 0.25,
            },
            0,
        )
        .unwrap();
        let calendar = schedule_held(&model, &trajectory, &[I::ZERO, I::ZERO]).unwrap();
        assert_eq!(
            calendar.iter().map(|e| e.event).collect::<Vec<_>>(),
            vec![0, 1, 2]
        );
        assert!(passive_batch(&model, &[calendar[1].clone()]));
        assert!(!passive_batch(&model, &[]));
        assert!(!passive_batch(
            &model,
            &[calendar[1].clone(), calendar[2].clone()]
        ));
        let mut base_ops = Operators::new(&model.program, &trajectory, &[], &[0., 0.]).unwrap();
        base_ops
            .advance(0., I::ZERO, &[1., 0.], &[I::ONE, I::ZERO], &[0])
            .unwrap();
        let frame = |time: f64, states: Vec<f64>, operators: Operators| {
            let circuit = model
                .circuit_with(&states, &operators.values(time).unwrap())
                .unwrap();
            Frame {
                time,
                solution: circuit.solve(&[]).unwrap(),
                circuit,
                operators,
                state_bounds: states.iter().copied().map(I::point).collect(),
                states,
                value_proofs: Default::default(),
                time_proofs: Default::default(),
            }
        };
        let initial = frame(0., vec![1., 0.], base_ops.clone());
        let mut consumed = base_ops.clone();
        consumed
            .advance(1.25, I::point(1.25), &[1., 1.], &[I::ONE, I::ONE], &[1])
            .unwrap();
        let first = frame(1.25, vec![1., 1.], consumed.clone());
        let second = frame(1.5, vec![1., 2.], consumed.clone());
        let mut changed = consumed;
        changed
            .advance(
                1.75,
                I::point(1.75),
                &[0., 2.],
                &[I::ZERO, I::point(2.)],
                &[0],
            )
            .unwrap();
        let physical = frame(1.75, vec![0., 2.], changed.clone());
        changed
            .advance(2., I::point(2.), &[0., 3.], &[I::ZERO, I::point(3.)], &[1])
            .unwrap();
        let third = frame(2., vec![0., 3.], changed);
        let phases = vec![
            (initial, vec![]),
            (first, vec![calendar[0].clone()]),
            (second, vec![calendar[1].clone()]),
            (physical, vec![calendar[2].clone()]),
            (third, vec![calendar[0].clone()]),
        ];
        assert_eq!(phases[1].0.operators.values(0.75).unwrap()[0], 1.);
        for (phase, count) in [(1, 1.), (2, 2.)] {
            let seed = observation_seed(&model, &phases, phase, 0.75).unwrap();
            assert_eq!(seed.states[1], count);
            assert_eq!(seed.operators.values(0.75).unwrap()[0], 0.75);
            let query = prepare_root_window(
                &model,
                &trajectory,
                &seed,
                EventMoment {
                    exact_root: None,
                    occurrence_certified: false,
                    representative: 0.75,
                    observation: I::point(0.75),
                    fired_roots: &[],
                    prediction_end: 0.75,
                },
                &[],
            )
            .unwrap();
            assert_eq!(query.solution.voltages[1], 0.75);
            assert_eq!(query.states[1], count);
            let future = prepare_root_window(
                &model,
                &trajectory,
                &query,
                EventMoment {
                    exact_root: None,
                    occurrence_certified: false,
                    representative: 1.5,
                    observation: I::point(1.5),
                    fired_roots: &[],
                    prediction_end: 1.5,
                },
                &[],
            )
            .unwrap();
            assert_eq!(future.solution.voltages[1], 1.);
            assert_eq!(future.states[1], count);
        }
        let seed = observation_seed(&model, &phases, 4, 1.875).unwrap();
        assert_eq!(seed.states, vec![0., 3.]);
        assert_eq!(seed.operators.values(1.875).unwrap()[0], 0.875);
        assert_eq!(
            observation_seed(&model, &phases, 3, 1.875)
                .unwrap()
                .operators
                .values(1.875)
                .unwrap()[0],
            0.875
        );
        let mut mixed = phases.clone();
        mixed[4].1.push(calendar[2].clone());
        assert_eq!(
            observation_seed(&model, &mixed, 4, 1.875)
                .unwrap()
                .operators
                .values(1.875)
                .unwrap(),
            mixed[4].0.operators.values(1.875).unwrap()
        );
        // Query failure owns only clones; the shared accepted snapshots stay intact.
        let before = phases[1].0.operators.values(0.75).unwrap();
        assert!(prepare_root_window(
            &model,
            &trajectory,
            &seed,
            EventMoment {
                exact_root: None,
                occurrence_certified: false,
                representative: f64::NAN,
                observation: I::point(f64::NAN),
                fired_roots: &[],
                prediction_end: 2.5
            },
            &[]
        )
        .is_err());
        assert_eq!(phases[1].0.operators.values(0.75).unwrap(), before);
    }
}

#[cfg(test)]
#[path = "transient_event_acceptance_paid_tests.rs"]
mod paid_candidate_tests;
