//! Query-independent, best-effort recovery of an event voltage certificate.
//! A single sample/edge/filter path can also request refinement before a local
//! failure. Later history/output certificates remain mandatory in every case.
use super::*;

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
        let (inputs, slopes) = trajectory.range(event.bounds()).ok()?;
        let blocks = [model.triggers[event.event].event];
        let roots = [event.event];
        let evaluation = self.accepted.operators.evaluation(event.time).ok()?;
        let prepared = crate::settlement::prepare_window(
            model,
            (&blocks, &roots),
            (&trajectory.values(event.time), &inputs),
            &self.accepted.states,
            &evaluation.values,
            &self.accepted.state_bounds,
            &evaluation.bounds,
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
            I::point(event.bounds().hi) - I::point(event.bounds().lo),
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
        let chain = if crossings.get(self.event + 1).is_none()
            && !model.relocalized_guards.iter().any(|held| *held)
        {
            self.filter_root_budget(model, trajectory, event)
        } else {
            None
        };
        let proactive = chain
            .as_ref()
            .is_some_and(|d| d.target_width.is_some() && d.predicted_error_bound > d.budget);
        let failure = match self.preflight_root_consumer(model, trajectory, crossings) {
            Ok(_) if !proactive => return Ok(()),
            Ok(_) => None,
            Err(error) if matches!(error.kind, "waveform_accuracy" | "event_accuracy") => {
                Some(error)
            }
            Err(error) => return Err(error),
        };
        let demand = if chain.is_none() {
            self.input_root_demand(model, trajectory, event)
        } else {
            None
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
            let changed = refined.bounds() != candidate[self.event].bounds();
            candidate[self.event] = refined;
            let result = if changed {
                self.preflight_root_consumer(model, trajectory, &candidate)
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
