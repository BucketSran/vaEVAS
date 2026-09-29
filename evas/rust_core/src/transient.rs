//! Time advancement around the static solver. Trials never mutate accepted state.
use crate::event_accuracy::{unresolved, GuardBounds};
use crate::events::EventModel;
use crate::ir::{Error, EventRecord, Request, Response, Solution, TransientTrace, SCHEMA_VERSION};
use crate::pwl::{Root, Trajectory};
use crate::solver::Circuit;

struct Crossing {
    time: f64,
    event: usize,
    root: Root,
}

struct Frame {
    time: f64,
    states: Vec<f64>,
    solution: Solution,
    circuit: Circuit,
}

fn schedule(model: &EventModel, trajectory: &Trajectory) -> Result<Vec<Crossing>, Error> {
    if model.guards.is_empty() {
        return Ok(Vec::new());
    }
    let bounds = GuardBounds::new(&model.program, &model.driven)?;
    let initial = model.initial();
    let circuit = model.circuit(&initial)?;
    let mut values = vec![Vec::new(); model.guards.len()];
    for &time in &trajectory.knots {
        // Retain normal physical residual acceptance; bounds are an additional
        // check, not a replacement for solving the original contributions.
        circuit.solve(&trajectory.values(time))?;
        for (value, row) in bounds
            .values(&trajectory.value_bounds(time))
            .into_iter()
            .zip(&mut values)
        {
            row.push(value);
        }
    }
    let mut crossings = Vec::new();
    for (index, values) in values.iter().enumerate() {
        let event = &model.program.events[index];
        let roots = trajectory
            .roots(values, event.direction)
            .map_err(|mut error| {
                error
                    .message
                    .push_str(&format!(" at {}", event.origin.label()));
                error
            })?;
        for root in roots {
            crossings.push(Crossing {
                time: root.bounds.hi,
                event: index,
                root,
            });
        }
    }
    crossings.sort_by(|a, b| {
        a.root
            .bounds
            .lo
            .total_cmp(&b.root.bounds.lo)
            .then(a.event.cmp(&b.event))
    });
    let mut start = 0;
    while start < crossings.len() {
        let mut end = start + 1;
        let mut time = crossings[start].time;
        while end < crossings.len() && crossings[end].root.bounds.lo <= time {
            let first = &crossings[start];
            let next = &crossings[end];
            let same_guard = model.program.events[first.event].guard
                == model.program.events[next.event].guard
                || bounds.same_zero_set(first.event, next.event);
            if !first.root.coincides(&next.root, same_guard) {
                return Err(unresolved(
                    "cannot certify ordering of distinct cross roots with overlapping bounds",
                ));
            }
            time = time.max(next.time);
            end += 1;
        }
        for crossing in &mut crossings[start..end] {
            let event = &model.program.events[crossing.event];
            if !crossing
                .root
                .accepts(time, event.time_tolerance, event.expression_tolerance)
            {
                return Err(unresolved(&format!(
                    "cross root uncertainty or representable time exceeds tolerances at {}",
                    event.origin.label()
                )));
            }
            crossing.time = time;
        }
        start = end;
    }
    Ok(crossings)
}

fn prepare_event(
    model: &EventModel,
    trajectory: &Trajectory,
    accepted: &Frame,
    time: f64,
    events: &[usize],
) -> Result<Frame, Error> {
    let before = accepted.circuit.solve(&trajectory.values(time))?;
    let states = model.apply(events, &before.voltages, &accepted.states)?;
    let circuit = model.circuit(&states)?;
    let solution = circuit.solve(&trajectory.values(time))?;
    Ok(Frame {
        time,
        states,
        solution,
        circuit,
    })
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
    let crossings = schedule(&model, &trajectory)?;
    let initial = model.initial();
    let circuit = model.circuit(&initial)?;
    let mut accepted = Frame {
        time: 0.0,
        solution: circuit.solve(&trajectory.values(0.0))?,
        states: initial,
        circuit,
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
        if time <= accepted.time {
            return Err(Error::new(
                "event_resolution",
                "max_step cannot advance representable time",
            ));
        }
        let candidate = accepted.circuit.solve(&trajectory.values(time))?;
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
            let next = prepare_event(&model, &trajectory, &accepted, event_time, &ids)?;
            let mut records = Vec::new();
            for &id in &ids {
                let guard_value = model.guards[id].value(&next.solution.voltages, &next.states)?;
                if guard_value.abs() > model.program.events[id].expression_tolerance {
                    return Err(Error::new(
                        "event_resolution",
                        "accepted event violates cross expression tolerance",
                    ));
                }
                records.push(EventRecord {
                    time: event_time,
                    event: id,
                    origin: model.program.events[id].origin.label(),
                    guard_value,
                    before: accepted.states.clone(),
                    after: next.states.clone(),
                });
            }
            // Commit frame, circuit, cursor and history only after all checks.
            accepted = next;
            event = end_event;
            trace.events.extend(records);
        } else {
            accepted.time = time;
            accepted.solution = candidate;
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
            "events":[{"guard":{"op":"affine","constant":-0.5,"terms":[{"node":1,"coefficient":1}]},
                "direction":0,"time_tolerance":1e-12,"expression_tolerance":1e-9,
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
}
