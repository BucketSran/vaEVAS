//! Time advancement around the static solver. Trials never mutate accepted state.
use crate::events::EventModel;
use crate::interval::Interval as I;
use crate::ir::{
    Error, EventRecord, EventTrigger, Request, Response, Solution, TransientTrace, SCHEMA_VERSION,
};
use crate::operators::Operators;
use crate::pwl::Trajectory;
use crate::schedule::schedule;
use crate::solver::Circuit;

struct Frame {
    time: f64,
    states: Vec<f64>,
    state_bounds: Vec<I>,
    solution: Solution,
    circuit: Circuit,
    operators: Operators,
}

fn prepare_event(
    model: &EventModel,
    trajectory: &Trajectory,
    accepted: &Frame,
    time: f64,
    events: &[usize],
) -> Result<Frame, Error> {
    let mut operators = accepted.operators.clone();
    // No-operator execution retains main's conditional event certificate.
    // Operator histories must keep the uncertainty in sampled event states.
    let old_bounds = if model.program.operators.is_empty() {
        accepted.states.iter().copied().map(I::point).collect()
    } else {
        accepted.state_bounds.clone()
    };
    operators.advance(time, &accepted.states, &old_bounds, &[])?;
    // Positive edge durations make transition continuous at a target change.
    // Freeze its current value for the same-time state/voltage solve, then
    // install the new target only in this disposable candidate history.
    let frozen = operators.values(time)?;
    let (states, state_bounds, circuit, solution) = crate::settlement::prepare(
        model,
        events,
        &trajectory.values(time),
        &accepted.states,
        &frozen,
        &old_bounds,
        &operators.bounds(time)?,
    )?;
    // Equal rounded inputs / equal interval endpoints do not prove that an
    // uncertain state assignment left the exact operator target unchanged.
    let changed: Vec<_> = events
        .iter()
        .flat_map(|&id| &model.program.events[id].assignments)
        .map(|a| a.state)
        .filter(|&s| old_bounds[s] != state_bounds[s] || old_bounds[s].lo != old_bounds[s].hi)
        .collect();
    operators.advance(time, &states, &state_bounds, &changed)?;
    if operators.values(time)? != frozen {
        return Err(Error::new(
            "event_consistency",
            "operator changed during same-time settlement",
        ));
    }
    Ok(Frame {
        time,
        states,
        state_bounds,
        solution,
        circuit,
        operators,
    })
}

fn prepare_batch(
    model: &EventModel,
    trajectory: &Trajectory,
    accepted: &Frame,
    event_time: f64,
    ids: &[usize],
) -> Result<(Frame, Vec<EventRecord>), Error> {
    let next = prepare_event(model, trajectory, accepted, event_time, ids)?;
    next.operators.check_deadline_order(event_time, None)?;
    let mut records = Vec::new();
    for &id in ids {
        let (kind, guard_value) = match &model.program.events[id].trigger {
            EventTrigger::Cross {
                expression_tolerance,
                ..
            } => {
                let value = model.guards[id]
                    .as_ref()
                    .unwrap()
                    .value(&next.solution.voltages, &next.states)?;
                if value.abs() > *expression_tolerance {
                    return Err(Error::new(
                        "event_resolution",
                        "accepted event violates cross expression tolerance",
                    ));
                }
                ("cross", Some(value))
            }
            EventTrigger::Timer { .. } => ("timer", None),
        };
        records.push(EventRecord {
            time: event_time,
            event: id,
            origin: model.program.events[id].origin.label(),
            kind,
            guard_value,
            before: accepted.states.clone(),
            after: next.states.clone(),
        });
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
    let trajectory = Trajectory::new(request.transient.unwrap(), request.driven.len())?;
    let model = EventModel::new(request.program, request.driven, request.tolerances)?;
    let initial = model.initial();
    let operators = Operators::new(&model.program, &trajectory, &model.driven, &initial)?;
    let crossings = schedule(&model, &trajectory)?;
    let circuit = model.circuit_with(&initial, &operators.values(0.0)?)?;
    let mut accepted = Frame {
        time: 0.0,
        solution: circuit.solve(&trajectory.values(0.0))?,
        state_bounds: initial.iter().copied().map(I::point).collect(),
        states: initial,
        circuit,
        operators,
    };
    if !model.program.operators.is_empty() {
        accepted.state_bounds = model.certify(
            &[],
            &trajectory.values(0.0),
            &accepted.state_bounds,
            &accepted.operators.bounds(0.0)?,
            &accepted.solution.voltages,
            &accepted.states,
        )?;
    }
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
    let (mut output, mut event, mut knot) = (0, 0, 1);
    loop {
        accepted
            .operators
            .check_deadline_order(accepted.time, crossings.get(event).map(|e| e.bounds()))?;
        // t=0 is processed after initial_step and before the initial observation.
        // Later events are reached by the same loop after advancing to their time.
        if event < crossings.len() && crossings[event].time == accepted.time {
            let event_time = accepted.time;
            let mut end_event = event;
            while end_event < crossings.len() && crossings[end_event].time == event_time {
                end_event += 1;
            }
            let ids: Vec<_> = crossings[event..end_event]
                .iter()
                .map(|c| c.event)
                .collect();
            let (next, records) = prepare_batch(&model, &trajectory, &accepted, event_time, &ids)?;
            next.operators
                .check_deadline_order(event_time, crossings.get(end_event).map(|e| e.bounds()))?;
            // Commit frame, circuit, cursor and history only after all checks.
            accepted = next;
            event = end_event;
            trace.events.extend(records);
        }
        accepted
            .operators
            .check_deadline_order(accepted.time, crossings.get(event).map(|e| e.bounds()))?;
        if output < trace.times.len() && accepted.time == trace.times[output] {
            solutions.push(accepted.solution.clone());
            trace.states.push(accepted.states.clone());
            output += 1;
        }
        if accepted.time == trajectory.config.stop {
            break;
        }
        if trace.accepted_steps >= 1_000_000 {
            return Err(Error::new(
                "step_budget",
                "transient execution exceeded 1,000,000 accepted steps",
            ));
        }
        let mut time = (accepted.time + trajectory.config.max_step).min(trajectory.knots[knot]);
        if output < trace.times.len() {
            time = time.min(trace.times[output]);
        }
        if let Some(deadline) = accepted.operators.next_breakpoint(accepted.time) {
            time = time.min(deadline);
        }
        if time <= accepted.time {
            return Err(Error::new(
                "event_resolution",
                "max_step cannot advance representable time",
            ));
        }
        // A trial beyond an earlier scheduled event is discarded before any
        // residual check: that event may change the future waveform/constraints.
        let candidate = if model.program.operators.is_empty() {
            None
        } else {
            Some(prepare_event(&model, &trajectory, &accepted, time, &[]))
        };
        if event < crossings.len() && crossings[event].time <= time {
            let event_time = crossings[event].time;
            if event_time < time {
                trace.discarded_trials += 1;
            }
            let mut end_event = event;
            while end_event < crossings.len() && crossings[end_event].time == event_time {
                end_event += 1;
            }
            let ids: Vec<_> = crossings[event..end_event]
                .iter()
                .map(|c| c.event)
                .collect();
            let (next, records) = prepare_batch(&model, &trajectory, &accepted, event_time, &ids)?;
            next.operators
                .check_deadline_order(event_time, crossings.get(end_event).map(|e| e.bounds()))?;
            accepted = next;
            event = end_event;
            trace.events.extend(records);
        } else {
            if let Some(candidate) = candidate {
                let next = candidate?;
                next.operators
                    .check_deadline_order(time, crossings.get(event).map(|e| e.bounds()))?;
                accepted = next;
            } else {
                accepted.solution = accepted.circuit.solve(&trajectory.values(time))?;
                accepted.time = time;
            }
        }
        trace.accepted_steps += 1;
        if accepted.time == trajectory.knots[knot] {
            knot += 1;
        }
    }
    Ok(Response {
        engine: concat!("evas-events-", env!("CARGO_PKG_VERSION")).into(),
        schema_version: SCHEMA_VERSION,
        nodes: model.program.nodes,
        solutions,
        transient: Some(trace),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ir::{Program, Tolerances, TransientInputs};

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
                "assignments":[{"state":0,"rhs":{"op":"add","left":{"op":"state","state":0},"right":{"op":"affine","constant":1,"terms":[]}}}],
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
                let action = program.events[0].assignments[0].clone();
                program.events[0].assignments.push(action);
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
        program.events[0].assignments = serde_json::from_value(serde_json::json!([
            {"state":0,"rhs":{"op":"affine","constant":1.0,"terms":[]}},
            {"state":0,"rhs":{"op":"add","left":{"op":"state","state":0},
                "right":{"op":"affine","constant":2_f64.powi(-55),"terms":[]}}},
            {"state":0,"rhs":{"op":"add","left":{"op":"state","state":0},
                "right":{"op":"affine","constant":-1.0,"terms":[]}}}
        ]))
        .unwrap();
        let model = EventModel::new(program, vec!["u".into()], Tolerances::default()).unwrap();
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
