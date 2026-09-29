//! Time advancement around the static solver. Trials never mutate accepted state.
use crate::events::EventModel;
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
    operators.advance(time, &accepted.states)?;
    let before_circuit = model.circuit_with(&accepted.states, &operators.values(time)?)?;
    let before = before_circuit.solve(&trajectory.values(time))?;
    let states = model.apply(events, &before.voltages, &accepted.states)?;
    operators.advance(time, &states)?;
    let circuit = model.circuit_with(&states, &operators.values(time)?)?;
    let solution = circuit.solve(&trajectory.values(time))?;
    Ok(Frame {
        time,
        states,
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
        states: initial,
        circuit,
        operators,
    };
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
            accepted = next;
            event = end_event;
            trace.events.extend(records);
        } else {
            if let Some(candidate) = candidate {
                accepted = candidate?;
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
                states,
                operators,
                solution: circuit.solve(&trajectory.values(0.0)).unwrap(),
                circuit,
            };
            let first = prepare_event(&model, &trajectory, &before, 0.5, &[0]).unwrap();
            let replay = prepare_event(&model, &trajectory, &before, 0.5, &[0]).unwrap();
            assert_eq!(first.operators.next_breakpoint(0.5), Some(1.5));
            assert_eq!(replay.operators.next_breakpoint(0.5), Some(1.5));
            assert_eq!(before.operators.next_breakpoint(0.0), None);
            assert_eq!(before.states, [0.0]);
            for _ in 0..2 {
                let trial = prepare_event(&model, &trajectory, &first, 2.0, &[]);
                if inconsistent {
                    assert_eq!(trial.err().unwrap().kind, "residual_failure");
                } else {
                    assert_eq!(trial.unwrap().solution.voltages[2], 0.25);
                }
                assert_eq!(first.operators.next_breakpoint(0.5), Some(1.5));
                assert_eq!(first.solution.voltages[2], 0.0);
            }
            // A failed future trial did not consume the earlier deadline.
            let deadline = prepare_event(&model, &trajectory, &first, 1.5, &[]).unwrap();
            assert_eq!(deadline.solution.voltages[2], 0.0);
            assert_eq!(deadline.operators.next_breakpoint(1.5), Some(3.5));
        }
    }
}
