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
            Statement::ArrayWrite { .. } | Statement::Loop { .. } => {
                return Err(unsupported(
                    "runtime loop is not supported in bootstrap initialization",
                ))
            }
            Statement::Assign(a) => check_expression(&a.rhs, model, owner)?,
            Statement::Display { args, .. } => {
                // Bootstrap has no solved internal node or operator history.
                // Validate every display argument before candidate replay.
                for argument in args {
                    check_expression(argument, model, owner)?;
                }
            }
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
    let initial_ids: Vec<_> = model
        .triggers
        .iter()
        .enumerate()
        .filter_map(|(index, leaf)| {
            matches!(leaf.trigger, EventTrigger::InitialStep { .. }).then_some(index)
        })
        .collect();
    let initial_blocks: Vec<_> = initial_ids
        .iter()
        .map(|&index| model.triggers[index].event)
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
            match crate::events::affine(input, &model.program, &origin.instance) {
                Ok(row)
                    if row.node_dependencies.is_empty() && row.operator_dependencies.is_empty() =>
                {
                    seeds.extend(row.state_dependencies);
                }
                _ => {
                    // Gather the complete structural seed set for direct-source
                    // targets. This is not target admission: the one real
                    // constructor still proves all piecewise-held leaves/cuts
                    // after the final zero-time state has been certified.
                    let (nodes, dependencies, operators) =
                        crate::continuous::integral_dependency_edges(
                            input,
                            &model.program,
                            &origin.instance,
                        )?;
                    let driven: BTreeSet<_> = model
                        .driven
                        .iter()
                        .filter_map(|name| model.program.nodes.iter().position(|node| node == name))
                        .collect();
                    if !operators.is_empty()
                        || nodes
                            .iter()
                            .any(|node| *node != 0 && !driven.contains(node))
                    {
                        return Ok(None); // Preserve general/coupled constructor diagnostics.
                    }
                    seeds.extend(dependencies);
                }
            }
        }
    }
    if seeds.is_disjoint(&assigned)
        || crate::settlement_bounds::unchanged_initial_states(
            &model.program,
            &[initial_blocks.clone(), blocks.clone()],
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
    if initial_blocks.iter().any(|block| blocks.contains(block)) {
        return Err(unsupported(
            "transition bootstrap cannot order an initial/timer OR body",
        ));
    }
    if initial_blocks.iter().any(|&block| {
        let owner = &model.program.events[block].origin.instance;
        model
            .program
            .contributions
            .iter()
            .any(|c| &c.origin.instance == owner)
    }) {
        return Err(Error::new(
            "unsupported_initial_event",
            "initial display requires a passive measurement model",
        ));
    }
    for &block in initial_blocks.iter().chain(&blocks) {
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
    // Build candidates in language order; neither stage commits any history,
    // calendar consumption or record. Histories are constructed once from the
    // final seed only after both stages pass their certificates.
    let before = model.initial();
    let before_bounds: Vec<_> = before.iter().copied().map(I::point).collect();
    // Transition constructors read only their complete structural seed set.
    // Other held values may retain arithmetic uncertainty in Prepared/Frame;
    // they are not exact inputs to any cold history in this restricted graph.
    // Keep the existing all-point rule for every other operator composition.
    let point_states = if model
        .program
        .operators
        .iter()
        .all(|spec| matches!(spec, OperatorSpec::Transition { .. }))
    {
        seeds
    } else {
        (0..model.program.states.len()).collect()
    };
    let (initial_states, initial_bounds, mut records) = prepare_stage(
        model,
        trajectory,
        &initial_blocks,
        &initial_ids,
        &before,
        &before_bounds,
        &point_states,
    )?;
    let ids: Vec<_> = zero.iter().copied().collect();
    let (states, bounds, timer_records) = prepare_stage(
        model,
        trajectory,
        &blocks,
        &ids,
        &initial_states,
        &initial_bounds,
        &point_states,
    )?;
    records.extend(timer_records);
    Ok(Some(Prepared {
        states,
        bounds,
        records,
        zero,
    }))
}

type PreparedStage = (Vec<f64>, Vec<I>, Vec<EventRecord>);

fn prepare_stage(
    model: &EventModel,
    trajectory: &Trajectory,
    blocks: &[usize],
    ids: &[usize],
    before: &[f64],
    before_bounds: &[I],
    point_states: &BTreeSet<usize>,
) -> Result<PreparedStage, Error> {
    if blocks.is_empty() {
        return Ok((before.to_vec(), before_bounds.to_vec(), Vec::new()));
    }
    let inputs = trajectory.value_bounds(0.);
    let selection = model
        .conditions
        .select_at_roots(blocks, &inputs, ids, before_bounds)?;
    model.check_selection_writers(&selection)?;
    let mut direct = vec![0.; model.program.nodes.len()];
    for (name, value) in model.driven.iter().zip(trajectory.values(0.)) {
        direct[model.program.nodes.iter().position(|n| n == name).unwrap()] = value;
    }
    let (states, display_records) = model.apply_with_displays(&selection, &direct, before, 0.)?;
    let bounds = crate::settlement_bounds::Bounds::held_inputs(model, &selection)?.check_states(
        model,
        &inputs,
        before_bounds,
        &[],
        &[],
        &states,
    )?;
    if states.len() != model.program.states.len()
        || bounds.len() != states.len()
        || bounds
            .iter()
            .zip(&states)
            .enumerate()
            .any(|(index, (&b, &s))| {
                !s.is_finite()
                    || !b.finite()
                    || s < b.lo
                    || s > b.hi
                    || point_states.contains(&index) && b != I::point(s)
            })
    {
        return Err(unsupported(
            "transition bootstrap requires finite final point state certificates",
        ));
    }
    let (replay_states, replay_displays) =
        model.apply_with_displays(&selection, &direct, before, 0.)?;
    let same_displays = replay_displays.len() == display_records.len()
        && replay_displays.iter().zip(&display_records).all(|(a, b)| {
            a.time == b.time && a.event == b.event && a.origin == b.origin && a.text == b.text
        });
    if replay_states != states
        || !same_displays
        || model
            .conditions
            .select_at_roots(blocks, &inputs, ids, before_bounds)?
            != selection
    {
        return Err(Error::new(
            "event_consistency",
            "initial held closure changed during replay",
        ));
    }
    let records = blocks
        .iter()
        .map(|&block| {
            let event = &model.program.events[block];
            let or = matches!(event.trigger, EventTrigger::Or { .. });
            EventRecord {
                time: 0.,
                observation_time_bounds: None,
                event: block,
                origin: event.origin.label(),
                kind: if or {
                    "or"
                } else if matches!(event.trigger, EventTrigger::InitialStep { .. }) {
                    "initial_step"
                } else {
                    "timer"
                },
                guard_value: None,
                fired_triggers: if or {
                    ids.iter()
                        .filter(|&&i| model.triggers[i].event == block)
                        .map(|&i| FiredTrigger {
                            trigger: model.triggers[i].index,
                            kind: if matches!(
                                model.triggers[i].trigger,
                                EventTrigger::InitialStep { .. }
                            ) {
                                "initial_step"
                            } else {
                                "timer"
                            },
                            guard_value: None,
                            time_bounds: None,
                        })
                        .collect()
                } else {
                    Vec::new()
                },
                before: before.to_vec(),
                after: states.clone(),
                display_records: display_records
                    .iter()
                    .filter(|record| record.event == block)
                    .cloned()
                    .collect(),
            }
        })
        .collect();
    Ok((states, bounds, records))
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
                pwl_errors_v: None,
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

    fn nonseed_model() -> EventModel {
        let origin = json!({"source":"nonseed.va","line":1,"column":1,"instance":"dut"});
        let c = |value| json!({"op":"affine","constant":value,"terms":[]});
        let s = |state| json!({"op":"state","state":state});
        let a = |state, rhs| json!({"kind":"assign","state":state,"rhs":rhs});
        let u = json!({"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]});
        let timer = |start| {
            json!({"kind":"timer","start":start,"period":0,
                                  "time_tolerance":1e-12,"enabled":true})
        };
        let program: Program = serde_json::from_value(json!({
            "schema_version":SCHEMA_VERSION,"nodes":["0","u","y"],
            "states":[{"instance":"dut","name":"x","kind":"real","initial":0},
                {"instance":"dut","name":"p","kind":"real","initial":0},
                {"instance":"dut","name":"span","kind":"real","initial":0},
                {"instance":"dut","name":"warm","kind":"real","initial":0}],
            "events":[{"origin":origin,"trigger":timer(0.),"body":[a(2,c(1.)),
                a(0,json!({"op":"multiply","left":c(0.45),"right":u}))]},
                {"origin":origin,"trigger":timer(0.25),"body":[a(3,c(1.)),a(2,c(0.))]},
                {"origin":origin,"trigger":timer(0.5),"body":[{"kind":"if",
                    "relation":"gt","left":u,"right":c(0.),"then_body":[a(1,s(0))],
                    "else_body":[a(1,c(0.))],"origin":origin}]}],
            "operators":[{"kind":"transition","input":s(2),"delay":0,
                "rise":0.125,"fall":0.5,"origin":origin}],
            "contributions":[{"origin":origin,"branch":{"instance":"dut",
                "local_positive":"p","local_negative":"r","kind":"voltage"},
                "positive":2,"negative":0,"rhs":{"op":"add",
                    "left":{"op":"multiply","left":c(1e12),"right":s(1)},
                    "right":{"op":"operator","operator":0}}}]
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

    fn nonseed_trajectory(good: bool) -> Trajectory {
        Trajectory::new(
            TransientInputs {
                pwl_errors_v: None,
                strobetimes: vec![],
                pwl: vec![vec![
                    [0., 0.16],
                    [0.25, 0.16],
                    [0.5, if good { -0.16 } else { 0.16 }],
                    [1., if good { -0.16 } else { 0.16 }],
                ]],
                output_times: vec![0., 0.125, 0.375, 0.75, 1.],
                stop: 1.,
                max_step: 1.,
            },
            1,
        )
        .unwrap()
    }

    fn nonseed_controller(
        model: &EventModel,
        trajectory: &Trajectory,
    ) -> (Controller, Vec<ScheduledEvent>) {
        let prepared = prepare(model, trajectory).unwrap().unwrap();
        // .45*.16 is an independently nonrepresentable binary64 product.
        assert!(prepared.bounds[0].lo < prepared.bounds[0].hi);
        assert_eq!(prepared.bounds[2], I::ONE);
        let operators =
            Operators::new(&model.program, trajectory, &model.driven, &prepared.states).unwrap();
        let circuit = model
            .circuit_at(
                &prepared.states,
                &operators.values(0.).unwrap(),
                &trajectory.value_bounds(0.),
            )
            .unwrap();
        let solution = circuit.solve(&trajectory.values(0.)).unwrap();
        let calendar = independent_schedule(model, trajectory).unwrap();
        let event = prepared.cursor(&calendar).unwrap();
        (
            Controller {
                accepted: Frame {
                    value_proofs: Default::default(),
                    time_proofs: Default::default(),
                    time: 0.,
                    states: prepared.states,
                    state_bounds: prepared.bounds,
                    operators,
                    circuit,
                    solution,
                },
                event,
                records: prepared.records,
                outputs: vec![],
            },
            calendar,
        )
    }

    #[test]
    fn bootstrap_nonseed_bounds_survive_same_controller_late_failure_and_retry() {
        let model = nonseed_model();
        let good = nonseed_trajectory(true);
        let bad = nonseed_trajectory(false);
        let (mut controller, mut calendar) = nonseed_controller(&model, &good);
        let accept = |controller: &mut Controller,
                      trajectory: &Trajectory,
                      calendar: &mut Vec<ScheduledEvent>| {
            controller.accept_changed_events(
                &model,
                trajectory,
                calendar,
                event_acceptance::Strategy::Static,
            )
        };
        accept(&mut controller, &good, &mut calendar).unwrap();
        assert_eq!(controller.accepted.time, 0.25);
        assert!(controller.accepted.state_bounds[0].lo < controller.accepted.state_bounds[0].hi);
        let before = controller.accepted.clone();
        let records = serde_json::to_value(&controller.records).unwrap();
        let cursor = controller.event;
        let signature = |events: &[ScheduledEvent]| {
            events
                .iter()
                .map(|event| {
                    (
                        event.event,
                        event.time.to_bits(),
                        event.bounds().lo.to_bits(),
                        event.bounds().hi.to_bits(),
                    )
                })
                .collect::<Vec<_>>()
        };
        let calendar_before = signature(&calendar);
        let same_frame = |actual: &Frame, expected: &Frame| {
            assert_eq!(actual.time, expected.time);
            assert_eq!(actual.states, expected.states);
            assert_eq!(actual.state_bounds, expected.state_bounds);
            assert_eq!(actual.solution.voltages, expected.solution.voltages);
            assert!(actual.operators.same_reset_history(&expected.operators));
            assert_eq!(
                actual.operators.bounds(actual.time).unwrap(),
                expected.operators.bounds(expected.time).unwrap()
            );
            assert_eq!(
                actual.operators.values(actual.time).unwrap(),
                expected.operators.values(expected.time).unwrap()
            );
        };
        let outputs = controller.outputs.clone();
        for _ in 0..2 {
            // Bad/good agree throughout the accepted prefix. Only the future
            // .5 condition changes; bad forwards x's inherited uncertainty.
            let error = accept(&mut controller, &bad, &mut calendar).unwrap_err();
            assert!(
                error.message.contains("forward error"),
                "{} {}",
                error.kind,
                error.message
            );
            same_frame(&controller.accepted, &before);
            assert_eq!(controller.event, cursor);
            assert_eq!(signature(&calendar), calendar_before);
            assert_eq!(serde_json::to_value(&controller.records).unwrap(), records);
            assert_eq!(controller.outputs.len(), outputs.len());
            for (actual, expected) in controller.outputs.iter().zip(&outputs) {
                same_frame(actual, expected);
            }
        }
        accept(&mut controller, &good, &mut calendar).unwrap();
        let (mut clean, mut clean_calendar) = nonseed_controller(&model, &good);
        accept(&mut clean, &good, &mut clean_calendar).unwrap();
        accept(&mut clean, &good, &mut clean_calendar).unwrap();
        same_frame(&controller.accepted, &clean.accepted);
        assert_eq!(
            serde_json::to_value(&controller.records).unwrap(),
            serde_json::to_value(&clean.records).unwrap()
        );
        assert_eq!(signature(&calendar), signature(&clean_calendar));
        // The unrelated span history falls from 1 to 0 over [.25,.75].
        // A rejected p update cannot advance or replace its accepted edge.
        assert_eq!(
            controller.accepted.operators.values(0.5).unwrap(),
            vec![0.5]
        );
        assert_eq!(controller.accepted.operators.values(1.).unwrap(), vec![0.]);
        assert_eq!(controller.accepted.solution.voltages[2], 0.5);
        assert!(controller.accepted.state_bounds[0].lo < controller.accepted.state_bounds[0].hi);
    }

    #[test]
    fn bootstrap_nontransition_compositions_keep_the_existing_all_point_rule() {
        let mut model = nonseed_model();
        model.program.operators.push(
            serde_json::from_value(json!({
                "kind":"idt","input":{"op":"operator","operator":0},"ic":0,
                "origin":{"source":"nonseed.va","line":1,"column":1,"instance":"dut"}
            }))
            .unwrap(),
        );
        let error = prepare(&model, &nonseed_trajectory(true)).err().unwrap();
        assert_eq!(error.kind, "unsupported_initial_history");
        assert!(
            error.message.contains("finite final point"),
            "{}",
            error.message
        );
    }

    #[test]
    fn bootstrap_point_rule_still_covers_all_structural_transition_dependencies() {
        let mut model = nonseed_model();
        let OperatorSpec::Transition { input, .. } = &mut model.program.operators[0] else {
            unreachable!()
        };
        *input = serde_json::from_value(json!({"op":"add","left":{"op":"state","state":2},
            "right":{"op":"multiply","left":{"op":"affine","constant":0,"terms":[]},
                     "right":{"op":"state","state":0}}}))
        .unwrap();
        assert_eq!(
            prepare(&model, &nonseed_trajectory(true))
                .err()
                .unwrap()
                .kind,
            "unsupported_initial_history"
        );
    }
}
