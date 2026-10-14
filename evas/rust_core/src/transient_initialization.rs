//! Exact fixed zero timers are a local preparation, before histories exist.
//! Unchanged transition seeds retain the ordinary event transaction.
use super::*;
use crate::ir::{Expression, OperatorSpec, Statement};
use std::collections::BTreeSet;

fn unsupported(message: &str) -> Error {
    Error::new("unsupported_initial_history", message)
}
fn check_expression(e: &Expression, model: &EventModel, owner: &str) -> Result<(), Error> {
    let (nodes, _, operators) =
        crate::continuous::integral_dependency_edges(e, &model.program, owner)?;
    let driven: BTreeSet<_> = model
        .driven
        .iter()
        .filter_map(|n| model.program.nodes.iter().position(|v| v == n))
        .collect();
    if !operators.is_empty() || nodes.iter().any(|n| *n != 0 && !driven.contains(n)) {
        return Err(unsupported(
            "transition bootstrap events must read only held state and directly driven inputs",
        ));
    }
    Ok(())
}
fn check_body(body: &[Statement], model: &EventModel, owner: &str) -> Result<(), Error> {
    for statement in body {
        match statement {
            Statement::Assign(a) => check_expression(&a.rhs, model, owner)?,
            Statement::If {
                left,
                right,
                then_body,
                else_body,
                ..
            } => {
                check_expression(left, model, owner)?;
                check_expression(right, model, owner)?;
                check_body(then_body, model, owner)?;
                check_body(else_body, model, owner)?;
            }
        }
    }
    Ok(())
}

pub(super) struct Prepared {
    pub(super) states: Vec<f64>,
    pub(super) bounds: Vec<I>,
    pub(super) records: Vec<EventRecord>,
    zero: BTreeSet<usize>,
}
impl Prepared {
    pub(super) fn cursor(&self, calendar: &[ScheduledEvent]) -> Result<usize, Error> {
        let end = calendar.iter().take_while(|e| e.time == 0.).count();
        for event in &calendar[..end] {
            if event.bounds() != I::ZERO || event.clock().and_then(|c| c.bounds()) != Some(I::ZERO)
            {
                return Err(unsupported(
                    "transition bootstrap requires exact zero clocks",
                ));
            }
        }
        if calendar[..end]
            .iter()
            .map(|e| e.event)
            .collect::<BTreeSet<_>>()
            != self.zero
            || end != self.zero.len()
        {
            return Err(Error::new(
                "event_consistency",
                "bootstrap zero-event identities disagree with calendar",
            ));
        }
        if calendar
            .get(end)
            .is_some_and(|event| event.bounds().lo <= 0.)
        {
            return Err(unsupported(
                "transition bootstrap cannot separate the next event from zero",
            ));
        }
        Ok(end)
    }
}

pub(super) fn prepare(
    model: &EventModel,
    trajectory: &Trajectory,
) -> Result<Option<Prepared>, Error> {
    let zero: BTreeSet<_> = model
        .triggers
        .iter()
        .enumerate()
        .filter_map(|(i, t)| {
            matches!(
                t.trigger,
                EventTrigger::Timer {
                    start: 0.,
                    enabled: true,
                    ..
                }
            )
            .then_some(i)
        })
        .collect();
    let blocks: Vec<_> = zero
        .iter()
        .map(|&i| model.triggers[i].event)
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect();
    let assigned: BTreeSet<_> = blocks
        .iter()
        .flat_map(|&i| model.program.events[i].assignments())
        .map(|a| a.state)
        .collect();
    let mut seeds = BTreeSet::new();
    for spec in &model.program.operators {
        if let OperatorSpec::Transition { input, origin, .. } = spec {
            let Ok(row) = crate::events::affine(input, &model.program, &origin.instance) else {
                return Ok(None); // The original constructor owns target diagnostics.
            };
            if !row.node_dependencies.is_empty() || !row.operator_dependencies.is_empty() {
                return Ok(None); // Preserve the existing target validation path.
            }
            seeds.extend(row.state_dependencies);
        }
    }
    if seeds.is_disjoint(&assigned)
        || crate::settlement_bounds::unchanged_initial_states(
            &model.program,
            std::slice::from_ref(&blocks),
            &seeds,
        )
    {
        return Ok(None);
    }
    if model.guard_operators.iter().flatten().any(|&index| {
        matches!(
            model.program.operators[index],
            OperatorSpec::Transition { .. }
        )
    }) {
        return Err(Error::new(
            "unsupported_cross",
            "cross requires a continuous epoch history; reset/transition history is unsupported",
        ));
    }
    if model.relocalized_guards.iter().any(|&v| v)
        || model.guard_operators.iter().any(|v| !v.is_empty())
    {
        return Err(unsupported("changed initial transition seeds require a calendar independent of held state and histories"));
    }
    for &block in &blocks {
        let event = &model.program.events[block];
        check_body(&event.body, model, &event.origin.instance)?;
    }
    // No other live history can be discarded or rebuilt under this proof.
    for (index, spec) in model.program.operators.iter().enumerate() {
        if !matches!(spec, OperatorSpec::Transition { .. })
            && crate::operators::transition_filter::projection(&model.program, &model.driven, index)
                .is_none()
        {
            return Err(unsupported("changed initial transition seeds require a closed transition/filter/integral graph"));
        }
    }
    let before = model.initial();
    let before_bounds: Vec<_> = before.iter().copied().map(I::point).collect();
    let inputs = trajectory.value_bounds(0.);
    let ids: Vec<_> = zero.iter().copied().collect();
    let selection = model.conditions.select_at_roots(&blocks, &inputs, &ids)?;
    model.check_selection_writers(&selection)?;
    let mut direct = vec![0.; model.program.nodes.len()];
    for (name, value) in model.driven.iter().zip(trajectory.values(0.)) {
        direct[model.program.nodes.iter().position(|n| n == name).unwrap()] = value;
    }
    let states = model.apply(&selection, &direct, &before)?;
    let bounds = crate::settlement_bounds::Bounds::held_inputs(model, &selection)?.check_states(
        model,
        &inputs,
        &before_bounds,
        &[],
        &[],
        &states,
    )?;
    if states.len() != model.program.states.len()
        || bounds.len() != states.len()
        || bounds
            .iter()
            .zip(&states)
            .any(|(&b, &s)| !s.is_finite() || b != I::point(s))
    {
        return Err(unsupported(
            "transition bootstrap requires finite final point state certificates",
        ));
    }
    if model.apply(&selection, &direct, &before)? != states
        || model.conditions.select_at_roots(&blocks, &inputs, &ids)? != selection
    {
        return Err(Error::new(
            "event_consistency",
            "initial held closure changed during replay",
        ));
    }
    let records = blocks
        .into_iter()
        .map(|block| {
            let event = &model.program.events[block];
            let or = matches!(event.trigger, EventTrigger::Or { .. });
            EventRecord {
                time: 0.,
                observation_time_bounds: None,
                event: block,
                origin: event.origin.label(),
                kind: if or { "or" } else { "timer" },
                guard_value: None,
                fired_triggers: if or {
                    zero.iter()
                        .filter(|&&i| model.triggers[i].event == block)
                        .map(|&i| FiredTrigger {
                            trigger: model.triggers[i].index,
                            kind: "timer",
                            guard_value: None,
                            time_bounds: None,
                        })
                        .collect()
                } else {
                    Vec::new()
                },
                before: before.clone(),
                after: states.clone(),
            }
        })
        .collect();
    Ok(Some(Prepared {
        states,
        bounds,
        records,
        zero,
    }))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ir::{Program, Tolerances, TransientInputs};
    use serde_json::json;

    fn model() -> EventModel {
        let origin = json!({"source":"init.va","line":1,"column":1,"instance":"dut"});
        let program: Program = serde_json::from_value(json!({
            "schema_version":SCHEMA_VERSION,"nodes":["0","u","y"],
            "states":[{"instance":"dut","name":"q","kind":"real","initial":0}],
            "events":[{"origin":origin,"trigger":{"kind":"timer","start":0,
                "period":0,"time_tolerance":0.001,"enabled":true},
                "body":[{"kind":"assign","state":0,"rhs":{"op":"add",
                    "left":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]},
                    "right":{"op":"affine","constant":0.1,"terms":[]}}}]}],
            "operators":[{"kind":"transition","input":{"op":"state","state":0},
                "delay":0.125,"rise":0.5,"fall":0.5,"origin":origin}],
            "contributions":[{"branch":{"instance":"dut","local_positive":"p",
                "local_negative":"r","kind":"voltage"},"positive":2,"negative":0,
                "rhs":{"op":"operator","operator":0},"origin":origin}]
        }))
        .unwrap();
        EventModel::new(
            program,
            vec!["u".into()],
            Tolerances {
                absolute: 1e-8,
                relative: 0.,
            },
        )
        .unwrap()
    }
    fn trajectory(value: f64) -> Trajectory {
        Trajectory::new(
            TransientInputs {
                strobetimes: Vec::new(),
                pwl: vec![vec![[0., value], [1., value]]],
                output_times: vec![0., 1.],
                stop: 1.,
                max_step: 1.,
            },
            1,
        )
        .unwrap()
    }
    #[test]
    fn rejected_initial_certificate_retries_on_the_same_model_without_seed_or_record_mutation() {
        let model = model();
        let identity = serde_json::to_value(&model.program).unwrap();
        for _ in 0..2 {
            let error = prepare(&model, &trajectory(0.2)).err().unwrap();
            assert_eq!(error.kind, "unsupported_initial_history");
            assert_eq!(model.initial(), vec![0.]);
            assert_eq!(serde_json::to_value(&model.program).unwrap(), identity);
        }
        let retry = prepare(&model, &trajectory(0.)).unwrap().unwrap();
        let clean = prepare(&super::tests::model(), &trajectory(0.))
            .unwrap()
            .unwrap();
        assert_eq!(retry.states, vec![0.1]);
        assert_eq!(retry.bounds, clean.bounds);
        assert_eq!(
            serde_json::to_value(&retry.records).unwrap(),
            serde_json::to_value(&clean.records).unwrap()
        );
        let calendar = independent_schedule(&model, &trajectory(0.)).unwrap();
        assert_eq!(retry.cursor(&calendar).unwrap(), 1);
        let histories = Operators::new(
            &model.program,
            &trajectory(0.),
            &model.driven,
            &retry.states,
        )
        .unwrap();
        assert_eq!(histories.values(0.).unwrap(), vec![0.1]);
        assert_eq!(histories.values(1.).unwrap(), vec![0.1]);
    }

    #[test]
    fn bootstrap_keeps_the_runtime_integer_range_check() {
        let base = model();
        let mut program = base.program.clone();
        program.states[0].kind = crate::ir::StateKind::Integer;
        program.states[0].initial = serde_json::from_value(json!(2147483647)).unwrap();
        program.events[0].body = serde_json::from_value(json!([{"kind":"assign","state":0,
            "rhs":{"op":"add","left":{"op":"state","state":0},
                "right":{"op":"affine","constant":1,"terms":[]}}}]))
        .unwrap();
        let model = EventModel::new(program, base.driven, base.tolerances).unwrap();
        assert_eq!(
            prepare(&model, &trajectory(0.)).err().unwrap().kind,
            "state_range"
        );
        assert_eq!(model.initial(), vec![2147483647.]);
    }

    #[test]
    fn prepared_records_require_exact_zero_leaf_identity_without_duplication() {
        let model = model();
        let trajectory = trajectory(0.);
        let ready = prepare(&model, &trajectory).unwrap().unwrap();
        let calendar = independent_schedule(&model, &trajectory).unwrap();
        assert!(ready.cursor(&[]).is_err());
        let mut extra = calendar.clone();
        extra.push(calendar[0].clone());
        assert!(ready.cursor(&extra).is_err());
        assert_eq!(ready.cursor(&calendar).unwrap(), 1);
        assert_eq!(ready.records.len(), 1);
    }
}
