//! Query-independent, best-effort recovery of an event voltage certificate.
//! A single sample/edge/filter path can also request refinement before a local
//! failure. These are additional mathematical-root reference requirements.
//! Physical history/output certificates remain centered on actual execution e
//! and must retain all true input, inherited-state and numerical uncertainty.
//! Unknown root-reference demand is not a root-reference accuracy certificate.
use super::*;

/// The additional root-reference assessment is independent of physical
/// acceptance. Unknown never denotes a passed root-reference requirement.
enum RootReferenceAssessment {
    Certified,
    Failed(Error),
    Unknown,
}
impl RootReferenceAssessment {
    fn failure(self) -> Option<Error> {
        match self {
            Self::Failed(error) => Some(error),
            Self::Certified | Self::Unknown => None,
        }
    }
}

impl Controller {
    fn filter_root_budget(
        &self,
        model: &EventModel,
        trajectory: &Trajectory,
        event: &ScheduledEvent,
    ) -> Option<crate::settlement_bounds::FilterBudget> {
        if !self.records.is_empty() || !trajectory.has_only_physical_inputs() {
            return None;
        }
        let path = self.accepted.operators.single_filter_budget(event.time)?;
        let location = event.bounds().hull(I::point(event.time));
        let (inputs, slopes) = trajectory.range(location).ok()?;
        let point_inputs = trajectory.value_bounds(event.time);
        let blocks = [model.triggers[event.event].event];
        let roots = if event.is_arrival() {
            vec![event.event]
        } else {
            vec![]
        };
        let evaluation = self.accepted.operators.evaluation(event.time).ok()?;
        let prepared = crate::settlement::prepare_window(
            model,
            (&blocks, &roots),
            (&trajectory.values(event.time), &point_inputs),
            &trajectory.value_bounds(event.time),
            &self.accepted.states,
            &evaluation.values,
            &self.accepted.state_bounds,
            &evaluation.bounds,
            Some(&self.accepted.circuit),
        )
        .ok()?;
        let selection = model
            .conditions
            .select_at_roots(&blocks, &point_inputs, &roots, &self.accepted.state_bounds)
            .ok()?;
        let observation = model.conditions.select(&[], &point_inputs).ok()?;
        let sampled_program = model
            .selected_program_at_roots(&prepared.bounds, &point_inputs, &roots)
            .ok()?;
        let observed_program = model
            .selected_program(&prepared.bounds, &point_inputs)
            .ok()?;
        let sample =
            crate::settlement_bounds::Bounds::for_program(model, &selection, &sampled_program)
                .ok()?;
        let output =
            crate::settlement_bounds::Bounds::for_program(model, &observation, &observed_program)
                .ok()?;
        sample.filter_root_budget(
            &output,
            model,
            &path,
            &inputs,
            &point_inputs,
            &slopes,
            &self.accepted.state_bounds,
            &self.accepted.states,
            *prepared.states.first()?,
            I::point(location.hi) - I::point(location.lo),
        )
    }

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
        let location = event.bounds().hull(I::point(event.time));
        let (inputs, slopes) = trajectory.range(location).ok()?;
        let point_inputs = trajectory.value_bounds(event.time);
        let blocks = [model.triggers[event.event].event];
        let roots = if event.is_arrival() {
            vec![event.event]
        } else {
            vec![]
        };
        let prepared = crate::settlement::prepare_window(
            model,
            (&blocks, &roots),
            (&trajectory.values(event.time), &point_inputs),
            &trajectory.value_bounds(event.time),
            &self.accepted.states,
            &[],
            &self.accepted.state_bounds,
            &[],
            Some(&self.accepted.circuit),
        )
        .ok()?;
        let selection = model
            .conditions
            .select_at_roots(&blocks, &point_inputs, &roots, &self.accepted.state_bounds)
            .ok()?;
        let observation = model.conditions.select(&[], &point_inputs).ok()?;
        let sampled_program = model
            .selected_program_at_roots(&prepared.bounds, &point_inputs, &roots)
            .ok()?;
        let observed_program = model
            .selected_program(&prepared.bounds, &point_inputs)
            .ok()?;
        let sample =
            crate::settlement_bounds::Bounds::for_program(model, &selection, &sampled_program)
                .ok()?;
        let output =
            crate::settlement_bounds::Bounds::for_program(model, &observation, &observed_program)
                .ok()?;
        let sampled = sample.sampled_state_enclosures(&inputs, &self.accepted.state_bounds, &[])?;
        sample.input_root_demand(
            &output,
            model,
            event.time,
            &point_inputs,
            &slopes,
            &self.accepted.state_bounds,
            &self.accepted.states,
            &sampled,
            &prepared.solution.voltages,
        )
    }

    fn root_reference_assessment(
        &self,
        chain: Option<&crate::settlement_bounds::FilterBudget>,
        demand: Option<&crate::accuracy::Demand>,
    ) -> RootReferenceAssessment {
        if let Some(chain) = chain.filter(|chain| chain.predicted_error_bound > chain.budget) {
            return RootReferenceAssessment::Failed(Error::new(
                "waveform_accuracy",
                format!(
                    "event location error at {}: {:e} exceeds voltage budget {:e}",
                    chain.consumer, chain.predicted_error_bound, chain.budget
                ),
            ));
        }
        if let Some(demand) = demand.filter(|d| d.assessment.error_bound > d.assessment.budget) {
            return RootReferenceAssessment::Failed(Error::new(
                "waveform_accuracy",
                format!(
                    "event location error at {}: {:e} exceeds voltage budget {:e}",
                    demand.assessment.consumer,
                    demand.assessment.error_bound,
                    demand.assessment.budget
                ),
            ));
        }
        if chain.is_some() || demand.is_some() {
            RootReferenceAssessment::Certified
        } else {
            RootReferenceAssessment::Unknown
        }
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
                    exact_root: None,
                    representative: time,
                    observation: I::point(time),
                    fired_roots: &[],
                    mathematical_roots: &[],
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
        let chain = if crossings.get(self.event + 1).is_none()
            && !model.relocalized_guards.iter().any(|held| *held)
        {
            self.filter_root_budget(model, trajectory, event)
        } else {
            None
        };
        // For consumers without an allocated filter budget, original source
        // arithmetic can resolve a polynomial root down to adjacent binary64
        // times. Keep the allocated filter's budgeted stopping policy intact.
        // Refinement is independent of the query grid:
        // selecting a post-root phase must not require querying a history
        // before its execution representative.
        let exact_source = chain.is_none()
            && event
                .exact_input_value(
                    model,
                    trajectory,
                    event.bounds().lo + (event.bounds().hi - event.bounds().lo) * 0.5,
                )
                .is_some();
        let demand = if chain.is_none() {
            self.input_root_demand(model, trajectory, event)
        } else {
            None
        };
        let location_failure = self
            .root_reference_assessment(chain.as_ref(), demand.as_ref())
            .failure();
        // Preserve the existing source-only root-reference recovery strategy.
        // Full contraction alone does not grant an unknown root-reference certificate.
        let proactive = exact_source
            || location_failure.is_some()
            || (chain.is_none() && !model.program.operators.is_empty());
        let failure = match self.preflight_root_consumer(model, trajectory, crossings) {
            Ok(_) if !proactive => return Ok(()),
            Ok(_) => location_failure,
            Err(error) if matches!(error.kind, "waveform_accuracy" | "event_accuracy") => {
                Some(error)
            }
            Err(error) => return Err(error),
        };
        if let Some(chain) = &chain {
            crate::diagnostics::detail("filter_root_budget", "proposed", Some(event.time), chain);
        } else if let Some(demand) = &demand {
            crate::diagnostics::detail("root_demand", "assessed", Some(event.time), demand);
            if demand.source == crate::accuracy::Source::Retained {
                return failure.map_or(Ok(()), Err);
            }
        } else {
            crate::diagnostics::detail(
                "root_demand",
                "unknown",
                Some(event.time),
                &serde_json::json!({"source":"unknown", "failure":failure.as_ref().map(|e| &e.message)}),
            );
        }
        let mut target = chain
            .as_ref()
            .and_then(|d| d.target_width)
            .or_else(|| demand.as_ref().and_then(|d| d.target_width));
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
            let changed = refined.bounds() != candidate[self.event].bounds()
                || refined.execution_root() != candidate[self.event].execution_root();
            candidate[self.event] = refined;
            let result = if changed {
                self.preflight_root_consumer(model, trajectory, &candidate)
                    .and_then(|_| {
                        let event = &candidate[self.event];
                        let chain = self.filter_root_budget(model, trajectory, event);
                        let demand = self.input_root_demand(model, trajectory, event);
                        self.root_reference_assessment(chain.as_ref(), demand.as_ref())
                            .failure()
                            .map_or(Ok(()), Err)
                    })
            } else {
                last_failure.map_or(Ok(()), Err)
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
                Err(error) => last_failure = Some(error),
            }
            if target.is_none()
                || remaining == 0
                || last_failure
                    .as_ref()
                    .is_some_and(|e| !matches!(e.kind, "waveform_accuracy" | "event_accuracy"))
            {
                break;
            }
            target = None;
        }
        last_failure.map_or(Ok(()), Err)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ir::{Program, Tolerances, TransientInputs};

    #[test]
    fn filter_budget_rejection_and_retry_keep_history_and_calendar_private() {
        let input =
            serde_json::json!({"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]});
        let origin = |line| serde_json::json!({"source":"budget.va","line":line,"column":1,"instance":"dut"});
        let program: Program = serde_json::from_value(serde_json::json!({
            "schema_version":SCHEMA_VERSION, "nodes":["0","u","e","y"],
            "states":[{"instance":"dut","name":"q","kind":"real","initial":0}],
            "operators":[
                {"kind":"transition","input":{"op":"state","state":0},"delay":0.125,"rise":0.5,"fall":0.5,"origin":origin(2)},
                {"kind":"laplace_nd","input":{"op":"affine","constant":0,"terms":[{"node":2,"coefficient":1}]},"numerator":[1],"denominator":[1,0.25],"origin":origin(3)}],
            "contributions":[
                {"branch":{"instance":"dut","local_positive":"0","local_negative":"e","kind":"voltage"},
                 "positive":0,"negative":2,"rhs":{"op":"multiply","left":{"op":"affine","constant":-1,"terms":[]},"right":{"op":"operator","operator":0}},"origin":origin(2)},
                {"branch":{"instance":"dut","local_positive":"0","local_negative":"y","kind":"voltage"},
                 "positive":0,"negative":3,"rhs":{"op":"multiply","left":{"op":"affine","constant":-1,"terms":[]},"right":{"op":"operator","operator":1}},"origin":origin(3)}],
            "events":[{"trigger":{"kind":"cross","guard":{"op":"add",
                "left":{"op":"multiply","left":input,"right":input},
                "right":{"op":"affine","constant":-2,"terms":[]}},
                "direction":1,"time_tolerance":1e-3,"expression_tolerance":1e-3},
                "body":[{"kind":"assign","state":0,"rhs":input}],"origin":origin(1)}]
        })).unwrap();
        let mut model = EventModel::new(
            program,
            vec!["u".into()],
            Tolerances {
                absolute: 1e-30,
                relative: 0.,
            },
        )
        .unwrap();
        let trajectory = Trajectory::new(
            TransientInputs {
                pwl_errors_v: None,
                strobetimes: Vec::new(),
                pwl: vec![vec![[0., 0.], [3., 3.]]],
                output_times: vec![0., 3.],
                stop: 3.,
                max_step: 1.,
            },
            1,
        )
        .unwrap();
        let operators =
            Operators::new(&model.program, &trajectory, &model.driven, &model.initial()).unwrap();
        let circuit = model
            .circuit_with(&model.initial(), &operators.values(0.).unwrap())
            .unwrap();
        let accepted = Frame {
            time_proofs: Default::default(),
            time: 0.,
            states: model.initial(),
            state_bounds: vec![I::ZERO],
            solution: circuit.solve(&[0.]).unwrap(),
            circuit,
            operators,
        };
        let mut calendar = schedule(&model, &trajectory, &accepted.operators).unwrap();
        let original = calendar.clone();
        let mut controller = Controller {
            accepted: accepted.clone(),
            event: 0,
            records: Vec::new(),
            outputs: Vec::new(),
        };
        for _ in 0..2 {
            assert!(controller
                .refine_pending_input_root(&model, &trajectory, &mut calendar)
                .is_err());
            assert_eq!(calendar[0].bounds(), original[0].bounds());
            assert_eq!(calendar[0].time, original[0].time);
            assert_eq!(controller.accepted.state_bounds, accepted.state_bounds);
            assert!(controller
                .accepted
                .operators
                .same_reset_history(&accepted.operators));
            assert_eq!(controller.event, 0);
            assert!(controller.records.is_empty() && controller.outputs.is_empty());
        }
        model.tolerances.absolute = 2.01e-6;
        controller
            .refine_pending_input_root(&model, &trajectory, &mut calendar)
            .unwrap();
        assert!(calendar[0].bounds().hi - calendar[0].bounds().lo > 1e-14);
        assert!(controller
            .accepted
            .operators
            .same_reset_history(&accepted.operators));
        let mut clean_calendar = original;
        let mut clean = Controller {
            accepted,
            event: 0,
            records: Vec::new(),
            outputs: Vec::new(),
        };
        clean
            .refine_pending_input_root(&model, &trajectory, &mut clean_calendar)
            .unwrap();
        controller
            .accept_events(&model, &trajectory, &calendar)
            .unwrap();
        clean
            .accept_events(&model, &trajectory, &clean_calendar)
            .unwrap();
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
        assert_eq!(controller.records.len(), 1);
    }
}
