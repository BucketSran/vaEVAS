//! Zero-time held closure before a transition history or voltage solve exists.
//! Every reachable read is proved to use held state or an original input.
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
            Statement::Display { args, .. } => {
                for a in args {
                    check_expression(a, model, owner)?;
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
pub(super) struct Held {
    pub(super) states: Vec<f64>,
    pub(super) bounds: Vec<I>,
    pub(super) records: Vec<EventRecord>,
    zero: Vec<usize>,
    pub(super) future: Option<Vec<ScheduledEvent>>,
    pub(super) fresh_point_graph: bool,
}
impl Held {
    pub(super) fn cursor(
        &self,
        model: &EventModel,
        calendar: &[ScheduledEvent],
    ) -> Result<usize, Error> {
        if self.future.is_some() { return Ok(0); }
        let end = calendar.iter().take_while(|e| e.time == 0.).count();
        for event in &calendar[..end] {
            if event.bounds() != I::ZERO
                || event.clock().and_then(|c| c.bounds()) != Some(I::ZERO)
                || !matches!(
                    model.triggers[event.event].trigger,
                    EventTrigger::Timer { .. }
                )
            {
                return Err(unsupported(
                    "transition bootstrap only accepts exact fixed timer events at zero",
                ));
            }
        }
        let actual: BTreeSet<_> = calendar[..end].iter().map(|e| e.event).collect();
        if actual != self.zero.iter().copied().collect() || end != self.zero.len() {
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
fn batch(
    model: &EventModel,
    trajectory: &Trajectory,
    before: &[f64],
    before_bounds: &[I],
    ids: &[usize],
) -> Result<(Vec<f64>, Vec<I>, Vec<EventRecord>), Error> {
    let blocks: Vec<_> = ids
        .iter()
        .map(|&i| model.triggers[i].event)
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect();
    for &block in &blocks {
        let event = &model.program.events[block];
        check_body(&event.body, model, &event.origin.instance)?;
    }
    let input_bounds = trajectory.value_bounds(0.);
    let selection = model
        .conditions
        .select_at_roots(&blocks, &input_bounds, ids, before_bounds)?;
    model.check_selection_writers(&selection)?;
    model.check_contribution_predicate_updates(&selection)?;
    // Only driven slots can be read: all other slots are structurally absent.
    // This projection is an expression input, never a claimed circuit solution.
    let mut direct = vec![0.; model.program.nodes.len()];
    for (name, value) in model.driven.iter().zip(trajectory.values(0.)) {
        direct[model.program.nodes.iter().position(|n| n == name).unwrap()] = value;
    }
    let (states, displays) = model.apply_with_displays(&selection, &direct, before, 0.)?;
    let certificate = crate::settlement_bounds::Bounds::held_inputs(model, &selection)?;
    let bounds =
        certificate.check_states(model, &input_bounds, before_bounds, &[], &[], &states)?;
    let replay = model.apply_with_displays(&selection, &direct, before, 0.)?;
    if replay.0 != states
        || replay
            .1
            .iter()
            .map(|d| (&d.text, d.event, d.time))
            .ne(displays.iter().map(|d| (&d.text, d.event, d.time)))
        || model
            .conditions
            .select_at_roots(&blocks, &input_bounds, ids, before_bounds)?
            != selection
    {
        return Err(Error::new(
            "event_consistency",
            "initial held closure changed during replay",
        ));
    }
    let mut records = Vec::new();
    for block in blocks {
        let event = &model.program.events[block];
        let kind = match event.trigger {
            EventTrigger::Or { .. } => "or",
            EventTrigger::InitialStep { .. } => "initial_step",
            EventTrigger::Timer { .. } | EventTrigger::HeldTimer { .. } => "timer",
            _ => return Err(unsupported("invalid bootstrap event kind")),
        };
        let fired = if kind == "or" {
            ids.iter()
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
        };
        records.push(EventRecord {
            time: 0.,
            observation_time_bounds: None,
            event: block,
            origin: event.origin.label(),
            kind,
            guard_value: None,
            fired_triggers: fired,
            before: before.to_vec(),
            after: states.clone(),
            display_records: displays
                .iter()
                .filter(|d| d.event == block)
                .cloned()
                .collect(),
        });
    }
    Ok((states, bounds, records))
}
// A fresh construction is justified only for source-free transitions and
// independent affine source integrals. Other history graphs retain their
// existing closed-graph bootstrap; no global history guard is weakened.
fn fresh_point_graph(model: &EventModel, bounds: &[I], states: &[f64]) -> bool {
    if bounds.iter().zip(states).any(|(&b, &s)| b != I::point(s)) { return false; }
    let driven: BTreeSet<_> = model.driven.iter().filter_map(|n|
        model.program.nodes.iter().position(|v| v == n)).collect();
    model.program.operators.iter().all(|op| match op {
        OperatorSpec::Transition { input, origin, .. } =>
            crate::continuous::integral_dependency_edges(input, &model.program, &origin.instance)
                .is_ok_and(|(nodes, _, ops)| nodes.iter().all(|&n| n == 0) && ops.is_empty()),
        OperatorSpec::Idt { input, ic, reset: None, origin } if ic.is_finite() =>
            crate::events::affine(input, &model.program, &origin.instance).is_ok_and(|row|
                row.operator_dependencies.is_empty() && row.state_dependencies.is_empty()
                && row.node_dependencies.iter().all(|n| *n == 0 || driven.contains(n))),
        _ => false,
    })
}

fn held_zero_closure(
    model: &EventModel, trajectory: &Trajectory, seed_states: &BTreeSet<usize>,
) -> Result<Option<Held>, Error> {
    if model.triggers.iter().any(|t| !matches!(t.trigger,
        EventTrigger::InitialStep { .. } | EventTrigger::Timer { .. } | EventTrigger::HeldTimer { .. })) {
        return Err(unsupported("zero-time held transition initialization requires a timer-only calendar"));
    }
    let initials: Vec<_> = model.triggers.iter().enumerate().filter_map(|(i,t)|
        matches!(t.trigger, EventTrigger::InitialStep { .. }).then_some(i)).collect();
    if initials.iter().any(|&id| {
        let owner = &model.program.events[model.triggers[id].event].origin.instance;
        model.program.contributions.iter().any(|c| &c.origin.instance == owner)
    }) {
        return Err(Error::new("unsupported_initial_event", "initial display requires a passive measurement model"));
    }
    let before = model.initial();
    let original_bounds: Vec<_> = before.iter().copied().map(I::point).collect();
    let (initial, initial_bounds, mut records) = batch(model, trajectory, &before, &original_bounds, &initials)?;
    if initial_bounds.iter().zip(&initial).any(|(&b,&s)| b != I::point(s)) {
        return Err(unsupported("held transition initialization requires point state certificates"));
    }
    let calendar = schedule_held(model, trajectory, &initial_bounds)?;
    let end = calendar.iter().take_while(|e| e.time == 0.).count();
    if end == 0 { return Ok(None); }
    for e in &calendar[..end] {
        if e.bounds() != I::ZERO || e.clock().and_then(|c| c.bounds()) != Some(I::ZERO) {
            return Err(unsupported("held transition bootstrap requires an exact zero clock"));
        }
    }
    if calendar.get(end).is_some_and(|e| e.bounds().lo <= 0.) {
        return Err(unsupported("held transition bootstrap cannot separate its future from zero"));
    }
    let zero: Vec<_> = calendar[..end].iter().map(|e| e.event).collect();
    // The proof must cover the actual initial calendar, including HeldTimer.
    let stages: Vec<Vec<usize>> = [&initials,&zero].iter().map(|ids|
        ids.iter().map(|&i| model.triggers[i].event).collect()).collect();
    let mut protected = seed_states.clone();
    for leaf in &model.triggers {
        if let EventTrigger::HeldTimer { start, period, enabled, .. } = &leaf.trigger {
            let owner = &model.program.events[leaf.event].origin.instance;
            for expression in [start, period, enabled] {
                protected.extend(crate::events::affine(expression,&model.program,owner)?.state_dependencies);
            }
        }
    }
    if crate::settlement_bounds::unchanged_initial_states(&model.program, &stages, &protected) {
        return Ok(None);
    }
    let (states, bounds, zero_records) = batch(model, trajectory, &initial, &initial_bounds, &zero)?;
    let seed_unchanged = seed_states.iter().all(|&s|
        states[s].to_bits() == before[s].to_bits() && bounds[s] == original_bounds[s]);
    if bounds.iter().zip(&states).any(|(&b,&s)| b != I::point(s)) {
        return Err(unsupported("held transition initialization requires final point state certificates"));
    }
    let mut changed = vec![false; model.triggers.len()];
    for (i,leaf) in model.triggers.iter().enumerate() {
        if let EventTrigger::HeldTimer { start, period, enabled, .. } = &leaf.trigger {
            let owner = &model.program.events[leaf.event].origin.instance;
            for expression in [start,period,enabled] {
                changed[i] |= crate::events::affine(expression,&model.program,owner)?
                    .state_dependencies.iter().any(|&s| initial_bounds[s] != bounds[s]);
            }
        }
    }
    // Do not silently drop a newly enabled same-time timer. This finite
    // transaction does not define an iterative zero-time event fixed point.
    let final_calendar = schedule_held(model, trajectory, &bounds)?;
    if final_calendar.iter().any(|e| e.bounds().lo <= 0. && !zero.contains(&e.event)) {
        return Err(unsupported("zero-time update creates an unconsumed same-time timer"));
    }
    if seed_unchanged { return Ok(None); }
    let future = crate::schedule::reschedule_held(model,trajectory,&bounds,0.,&changed,&calendar[end..],&calendar[..end])?;
    records.extend(zero_records);
    let fresh_point_graph = fresh_point_graph(model,&bounds,&states);
    Ok(Some(Held { states, bounds, records, zero, future:Some(future), fresh_point_graph }))
}

pub(super) fn prepare_states(
    model: &EventModel,
    trajectory: &Trajectory,
) -> Result<Option<Held>, Error> {
    let zero: Vec<_> = model
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
    let assigned: BTreeSet<_> = zero
        .iter()
        .flat_map(|&i| model.program.events[model.triggers[i].event].assignments())
        .map(|a| a.state)
        .collect();
    let mut needs = false;
    let mut source_free = true;
    let mut seed_states = BTreeSet::new();
    for spec in &model.program.operators {
        if let OperatorSpec::Transition { input, origin, .. } = spec {
            let (nodes, states, operators) = crate::continuous::integral_dependency_edges(
                input,
                &model.program,
                &origin.instance,
            )?;
            source_free &= nodes.iter().all(|&n| n == 0) && operators.is_empty();
            seed_states.extend(states.iter().copied());
            needs |= nodes.iter().any(|&n| n != 0) || states.iter().any(|s| assigned.contains(s));
        }
    }
    if source_free && !seed_states.is_empty() && model.triggers.iter().all(|t|
        matches!(t.trigger, EventTrigger::InitialStep { .. } | EventTrigger::Timer { .. } | EventTrigger::HeldTimer { .. })) && model.triggers.iter().any(|t|
        matches!(t.trigger, EventTrigger::HeldTimer { .. })) {
        return held_zero_closure(model, trajectory, &seed_states);
    }
    if !needs {
        return Ok(None);
    }
    // A proof selects the original transaction; it does not consume events or
    // publish preplayed records. Source plans must always establish point/right
    // semantics, even if the held part of their target is invariant.
    let initials: Vec<_> = model.triggers.iter().enumerate()
        .filter_map(|(i,t)| matches!(t.trigger, EventTrigger::InitialStep { .. }).then_some(i))
        .collect();
    let stages: Vec<Vec<usize>> = [&initials, &zero].iter().map(|ids|
        ids.iter().map(|&i| model.triggers[i].event).collect()).collect();
    if source_free && crate::settlement_bounds::unchanged_initial_states(
        &model.program, &stages, &seed_states,
    ) {
        return Ok(None);
    }
    for &id in &initials {
        let owner = &model.program.events[model.triggers[id].event]
            .origin
            .instance;
        if model
            .program
            .contributions
            .iter()
            .any(|c| &c.origin.instance == owner)
        {
            return Err(Error::new(
                "unsupported_initial_event",
                "initial display requires a passive measurement model",
            ));
        }
    }
    let before = model.initial();
    let before_bounds: Vec<_> = before.iter().copied().map(I::point).collect();
    let (initial, bounds, mut records) =
        batch(model, trajectory, &before, &before_bounds, &initials)?;
    let (states, bounds, zero_records) = batch(model, trajectory, &initial, &bounds, &zero)?;
    // A second sufficient proof uses the actual pure-closure result. A
    // constant assignment may preserve this initial seed without being an
    // identity for every possible state. Compare both nominal bits and the
    // entire enclosure of every structural seed dependency.
    if source_free && seed_states.iter().all(|&s|
        states[s].to_bits() == before[s].to_bits() && bounds[s] == before_bounds[s]) {
        return Ok(None);
    }
    // Preserve the existing structural transition-cross diagnostic before
    // this early initialization path can hide it behind a bootstrap limit.
    // EventModel has already expanded guard dependencies through node groups.
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
        return Err(unsupported(
            "transition bootstrap requires a calendar independent of held state and histories",
        ));
    }
    records.extend(zero_records);
    let fresh_point_graph = source_free && fresh_point_graph(model, &bounds, &states);
    Ok(Some(Held {
        states,
        bounds,
        records,
        zero,
        future: None,
        fresh_point_graph,
    }))
}
