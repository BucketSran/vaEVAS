//! Exact fixed zero timers are a local preparation, before histories exist.
//! Unchanged transition seeds retain the ordinary event transaction.
use super::*;
use crate::ir::{Expression, OperatorSpec, Statement};
use std::collections::BTreeSet;
#[path = "transient_initial_split.rs"]
mod initial_split;

/// Closed display-only records cannot change cold histories or observe a
/// pre-initialization physical solution. Raw IR must satisfy this independently.
pub(super) fn constant_outputs(body: &[Statement]) -> bool {
    !body.is_empty()
        && body.iter().all(|statement| match statement {
            Statement::Display { args, .. } => args.iter().all(|arg| {
                matches!(arg,
            Expression::Affine { constant, terms } if constant.is_finite() && terms.is_empty())
            }),
            _ => false,
        })
}

fn unsupported(message: &str) -> Error {
    Error::new("unsupported_initial_history", message)
}
fn check_expression(e: &Expression, model: &EventModel, owner: &str) -> Result<(), Error> {
    check_expression_inner(e, model, owner, &mut BTreeSet::new())
}
fn check_expression_inner(
    e: &Expression,
    model: &EventModel,
    owner: &str,
    seen: &mut BTreeSet<usize>,
) -> Result<(), Error> {
    if !model.program.procedures.is_empty() {
        crate::real_expression::work(model).step()?;
    }
    if let Some(r) = &model.floor_source {
        crate::event_floor::charge(r.work(), 1, "floor_source_initial_scan")?;
    }
    // Dependency audit only. Typed nodes remain event-body values; bootstrap
    // execution and cold-history construction retain their existing owners.
    match e {
        Expression::RealCall { .. }
        | Expression::RealLocal { .. }
        | Expression::UnsupportedSystemCall { .. }
            if !model.program.procedures.is_empty() =>
        {
            // This is dependency admission, never execution of a function's
            // domain effects. The Plan executes only the selected call path.
            let work = crate::real_expression::work(model);
            let sources = crate::procedure::dependency_sources(&model.program, work)?;
            let row = crate::procedure::source_dependencies(e, &model.program, &sources, work)?;
            work.debit(
                2,
                ((model.driven.len()
                    + row.node_dependencies.len()
                    + row.operator_dependencies.len())
                    * 32
                    + 64) as u64,
            )?;
            let driven: BTreeSet<_> = model
                .driven
                .iter()
                .filter_map(|name| model.program.nodes.iter().position(|n| n == name))
                .collect();
            for operator in row.operator_dependencies {
                check_expression_inner(&Expression::Operator { operator }, model, owner, seen)?;
            }
            if row
                .node_dependencies
                .iter()
                .any(|n| *n != 0 && !driven.contains(n))
            {
                return Err(unsupported("transition bootstrap events must read only held state and directly driven inputs"));
            }
            return Ok(());
        }
        Expression::Operator { operator } if !model.program.procedures.is_empty() => {
            let spec = model
                .program
                .operators
                .get(*operator)
                .ok_or_else(|| Error::new("invalid_ir", "initial operator out of range"))?;
            if spec.origin().instance != owner {
                return Err(Error::new("invalid_ir", "initial operator owner mismatch"));
            }
            if let OperatorSpec::Math { input, .. } | OperatorSpec::Sin { input, .. } = spec {
                if !seen.insert(*operator) {
                    return Err(Error::new(
                        "invalid_ir",
                        "initial memoryless operator cycle",
                    ));
                }
                let result = check_expression_inner(input, model, owner, seen);
                seen.remove(operator);
                return result;
            }
        }
        Expression::EventMath {
            function: crate::ir::EventMathFunction::Floor,
            args,
            ..
        } if model
            .floor_source
            .as_ref()
            .map(|r| crate::event_floor::contains_charged(e, r.work()))
            .transpose()?
            .unwrap_or(false) =>
        {
            model
                .floor_source
                .as_ref()
                .unwrap()
                .bootstrap_numeric(e, owner)?;
            for child in args {
                check_expression_inner(child, model, owner, seen)?;
            }
            return Ok(());
        }
        Expression::IntegerPrimitive { .. } => {
            if let Some(request) = &model.floor_source {
                return request.bootstrap_numeric(e, owner);
            }
            return crate::event_numeric::validate(e, &model.program, owner);
        }
        Expression::RealBoundary { value, .. } => {
            return check_expression_inner(value, model, owner, seen)
        }
        Expression::RealBinary { left, right, .. }
        | Expression::Add { left, right }
        | Expression::Multiply { left, right }
        | Expression::Divide { left, right } => {
            check_expression_inner(left, model, owner, seen)?;
            return check_expression_inner(right, model, owner, seen);
        }
        Expression::Power { base, .. } => return check_expression_inner(base, model, owner, seen),
        Expression::Select {
            left,
            right,
            then_value,
            else_value,
            ..
        } => {
            for child in [left, right, then_value, else_value] {
                check_expression_inner(child, model, owner, seen)?;
            }
            return Ok(());
        }
        _ => (),
    }
    if let Some(request) = &model.floor_source {
        if !request.bootstrap_dependencies(e, owner)?.1 {
            return Err(unsupported(
                "transition bootstrap events must read only held state and directly driven inputs",
            ));
        }
        return Ok(());
    }
    let (nodes, _, operators) = crate::continuous::source_dependency_edges(
        e,
        &model.program,
        owner,
        Some(crate::real_expression::work(model)),
    )?;
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
    // Initial gate was consumed; every zero occurrence remains pending.
    deferred_zero: bool,
    pub(super) states: Vec<f64>,
    pub(super) bounds: Vec<I>,
    pub(super) records: Vec<EventRecord>,
    pub(super) bounded_held_transition_seeds: bool,
    pub(super) source_context: Option<std::sync::Arc<crate::transition_source_plan::ProofContext>>,
    pub(super) future: Option<Vec<ScheduledEvent>>,
    zero: BTreeSet<usize>,
}
impl Prepared {
    pub(super) fn cursor(&self, calendar: &[ScheduledEvent]) -> Result<usize, Error> {
        if self.deferred_zero {
            return Ok(0);
        }
        if self.future.is_some() {
            return Ok(0);
        }
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

// A zero-time transaction runs before any operator history exists. Besides
// the existing closed transition graph, an independent source integral can
// therefore be constructed once from its own IC and the final held state.
fn cold_work(model: &EventModel) -> &crate::transition_source_plan::Work {
    if let Some(owner) = crate::analytic_request::proof_owner(model) {
        return owner.work();
    }
    if let Some(request) = &model.floor_source {
        return request.work();
    }
    if let Some(context) = &model.source_context {
        return context.borrow_work();
    }
    model
        .mixed_cold_work
        .get_or_init(|| crate::transition_source_plan::Work::for_limit(model.proof_work_limit))
}
fn cold_charge(model: &EventModel, items: usize) -> Result<(), Error> {
    cold_work(model).debit(2, items as u64)
}
fn cold_affine(
    model: &EventModel,
    expression: &Expression,
    owner: &str,
) -> Result<crate::events::AffineState, Error> {
    // The full original-program size bounds this expression walk; each tree
    // node can allocate a dense row over the original nodes/states/operators.
    let width = model
        .program
        .nodes
        .len()
        .saturating_add(model.program.states.len())
        .saturating_add(model.program.operators.len())
        .saturating_add(1);
    cold_charge(model, model.source_copy_items.saturating_mul(width))?;
    crate::events::affine(expression, &model.program, owner)
}
fn cold_graph(model: &EventModel) -> Result<bool, Error> {
    for (index, spec) in model.program.operators.iter().enumerate() {
        cold_charge(model, 1)?;
        if matches!(spec, OperatorSpec::Transition { .. }) {
            continue;
        }
        if let OperatorSpec::Idt {
            input,
            ic,
            reset: None,
            origin,
        } = spec
        {
            let row = cold_affine(model, input, &origin.instance)?;
            cold_charge(
                model,
                row.node_dependencies
                    .len()
                    .saturating_mul(model.driven.len() + 1),
            )?;
            if ic.is_finite()
                && row.state_dependencies.is_empty()
                && row.operator_dependencies.is_empty()
                && row.node_dependencies.iter().all(|&node| {
                    node == 0
                        || model
                            .driven
                            .iter()
                            .any(|name| model.program.nodes[node] == *name)
                })
            {
                continue;
            }
        }
        // Reserve full contribution/dependency scans and dense node elimination
        // only for an operator that actually needs the existing projection.
        let width = model
            .program
            .nodes
            .len()
            .saturating_add(model.program.states.len())
            .saturating_add(model.program.operators.len())
            .saturating_add(1);
        cold_charge(
            model,
            model
                .source_copy_items
                .saturating_add(width)
                .saturating_mul(width)
                .saturating_mul(width),
        )?;
        if crate::operators::transition_filter::projection(&model.program, &model.driven, index)
            .is_none()
        {
            return Ok(false);
        }
    }
    Ok(true)
}

// This is only a sufficient t=0 filter, not a calendar. In particular it does
// not enumerate future ticks, compare clocks, or consume any occurrence.
fn possible_zero_blocks(model: &EventModel, states: &[I]) -> Result<Vec<usize>, Error> {
    let mut blocks = BTreeSet::new();
    for leaf in &model.triggers {
        cold_charge(model, 1)?;
        let possible = match &leaf.trigger {
            EventTrigger::Timer { start, enabled, .. } => *enabled && *start <= 0.,
            EventTrigger::HeldTimer { start, enabled, .. } => {
                let value = |expression: &Expression| -> Result<Option<I>, Error> {
                    let width = model
                        .program
                        .nodes
                        .len()
                        .saturating_add(states.len())
                        .saturating_add(model.program.operators.len())
                        .saturating_add(1);
                    cold_charge(model, model.source_copy_items.saturating_mul(width))?;
                    let Ok(row) = crate::affine_bounds::affine(expression, &model.program) else {
                        return Ok(None); // Unknown continues through the full paid proof.
                    };
                    let offset = model.program.nodes.len();
                    let value = states
                        .iter()
                        .enumerate()
                        .fold(*row.last().unwrap(), |sum, (index, &state)| {
                            sum + row[offset + index] * state
                        });
                    Ok(value.finite().then_some(value))
                };
                !value(enabled)?.is_some_and(|v| v.zero())
                    && !value(start)?.is_some_and(|v| v.lo > 0.)
            }
            _ => false,
        };
        if possible {
            cold_charge(model, usize::BITS as usize)?;
            blocks.insert(leaf.event);
        }
    }
    Ok(blocks.into_iter().collect())
}

fn prepare_held_zero(
    model: &EventModel,
    trajectory: &Trajectory,
    seeds: &BTreeSet<usize>,
    initial_ids: &[usize],
    initial_blocks: &[usize],
) -> Result<Option<Prepared>, Error> {
    cold_charge(
        model,
        model
            .source_copy_items
            .saturating_add(model.program.states.len().saturating_mul(8))
            .saturating_add(model.triggers.len().saturating_mul(8))
            .saturating_add(seeds.len().saturating_mul(usize::BITS as usize)),
    )?;
    let before = model.initial();
    let original_bounds: Vec<_> = before.iter().copied().map(I::point).collect();
    for &block in initial_blocks {
        let event = &model.program.events[block];
        // IR33 retains executable initialization assignments. Active-owner
        // status says nothing about their cold-history dependencies. Audit the
        // entire body below before replay, then retain the seed/calendar and
        // closed-history certificates before accepting the candidate.
        cold_charge(model, model.source_copy_items)?;
        check_body(&event.body, model, &event.origin.instance)?;
    }
    let mut mixed = MixedCold {
        original_points: (0..before.len()).collect(),
        allowed: false,
        qualified: None,
    };
    let (initial, initial_bounds, mut records) = prepare_stage(
        model,
        trajectory,
        initial_blocks,
        initial_ids,
        &before,
        &original_bounds,
        &mut mixed,
    )?;
    // Use the certified initial stage, not declaration/default seeds: an
    // initial callback can move a start to zero or enable a disabled timer.
    let possible = possible_zero_blocks(model, &initial_bounds)?;
    if possible.is_empty() {
        return Ok(deferred_initial(model, initial, initial_bounds, records));
    }
    cold_charge(
        model,
        seeds
            .len()
            .saturating_add(initial_blocks.len())
            .saturating_add(possible.len())
            .saturating_mul(usize::BITS as usize),
    )?;
    let mut protected = seeds.clone();
    for leaf in &model.triggers {
        cold_charge(model, 1)?;
        if let EventTrigger::HeldTimer {
            start,
            period,
            enabled,
            ..
        } = &leaf.trigger
        {
            let owner = &model.program.events[leaf.event].origin.instance;
            for expression in [start, period, enabled] {
                let row = cold_affine(model, expression, owner)?;
                cold_charge(
                    model,
                    row.state_dependencies
                        .len()
                        .saturating_mul(usize::BITS as usize),
                )?;
                protected.extend(row.state_dependencies);
            }
        }
    }
    // Conservatively replay every body that might fire at zero. A successful
    // proof preserves both cold seeds and future timer inputs, so the original
    // transaction remains responsible for actual execution and validation.
    if crate::settlement_bounds::unchanged_initial_states_charged(
        model,
        &[initial_blocks.to_vec(), possible],
        &protected,
        trajectory,
        cold_work(model),
    )? {
        return Ok(deferred_initial(model, initial, initial_bounds, records));
    }
    cold_charge(model, model.source_copy_items)?;
    let calendar = crate::schedule::schedule_held_charged(
        model,
        trajectory,
        &initial_bounds,
        cold_work(model),
    )?;
    cold_charge(
        model,
        calendar.len().saturating_mul(2 + usize::BITS as usize),
    )?;
    let end = calendar.iter().take_while(|e| e.time == 0.).count();
    if end == 0 {
        return Ok(deferred_initial(model, initial, initial_bounds, records));
    }
    for event in &calendar[..end] {
        if event.bounds() != I::ZERO || event.clock().and_then(|c| c.bounds()) != Some(I::ZERO) {
            return Err(unsupported(
                "held transition bootstrap requires exact zero clocks",
            ));
        }
    }
    if calendar.get(end).is_some_and(|e| e.bounds().lo <= 0.) {
        return Err(unsupported(
            "transition bootstrap cannot separate the next event from zero",
        ));
    }
    let zero: BTreeSet<_> = calendar[..end].iter().map(|e| e.event).collect();
    let ids: Vec<_> = zero.iter().copied().collect();
    let blocks: Vec<_> = ids
        .iter()
        .map(|&i| model.triggers[i].event)
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect();
    if initial_blocks.iter().any(|block| blocks.contains(block)) {
        return Err(unsupported(
            "transition bootstrap cannot order an initial/timer OR body",
        ));
    }
    for &block in &blocks {
        let event = &model.program.events[block];
        cold_charge(model, model.source_copy_items)?;
        check_body(&event.body, model, &event.origin.instance)?;
    }
    let (states, bounds, timer_records) = prepare_stage(
        model,
        trajectory,
        &blocks,
        &ids,
        &initial,
        &initial_bounds,
        &mut mixed,
    )?;
    let mut changed = vec![false; model.triggers.len()];
    for (index, leaf) in model.triggers.iter().enumerate() {
        if let EventTrigger::HeldTimer {
            start,
            period,
            enabled,
            ..
        } = &leaf.trigger
        {
            let owner = &model.program.events[leaf.event].origin.instance;
            for expression in [start, period, enabled] {
                changed[index] |= cold_affine(model, expression, owner)?
                    .state_dependencies
                    .iter()
                    .any(|&s| initial_bounds[s] != bounds[s]);
            }
        }
    }
    // TimerBoundary checks changed starts/enables against the consumed zero
    // occurrences. A new same-time occurrence is never silently discarded.
    cold_charge(
        model,
        model
            .source_copy_items
            .saturating_add(calendar.len().saturating_mul(16)),
    )?;
    let future = crate::schedule::reschedule_held_charged(
        model,
        trajectory,
        &bounds,
        0.,
        &changed,
        &calendar[end..],
        &calendar[..end],
        cold_work(model),
    )?;
    if seeds
        .iter()
        .all(|&s| states[s].to_bits() == initial[s].to_bits() && bounds[s] == initial_bounds[s])
    {
        // Initial assignments have already supplied the cold seed. Leave the
        // complete zero callback pending, including nonseed writes and checks.
        return Ok(deferred_initial(model, initial, initial_bounds, records));
    }
    if !cold_graph(model)? {
        return Err(unsupported("changed initial transition seeds require a closed transition graph or independent source integrals"));
    }
    cold_charge(model, timer_records.len())?;
    records.extend(timer_records);
    Ok(Some(Prepared {
        deferred_zero: false,
        states,
        bounds,
        records,
        bounded_held_transition_seeds: false,
        source_context: model.source_context.clone(),
        future: Some(future),
        zero,
    }))
}

// Retain the certified initial gate while leaving all ordinary zero timers
// pending. Returning None here would discard IR33 assignments and run them
// only after histories had already been constructed from declaration seeds.
fn deferred_initial(
    model: &EventModel,
    states: Vec<f64>,
    bounds: Vec<I>,
    records: Vec<EventRecord>,
) -> Option<Prepared> {
    if records.is_empty() {
        return None; // No IR33 initial gate was executed. Preserve the legacy path.
    }
    Some(Prepared {
        deferred_zero: true,
        states,
        bounds,
        records,
        bounded_held_transition_seeds: false,
        source_context: model.source_context.clone(),
        future: None,
        zero: BTreeSet::new(),
    })
}

pub(super) fn prepare(
    model: &EventModel,
    trajectory: &Trajectory,
) -> Result<Option<Prepared>, Error> {
    if let Some(request) = &model.floor_source {
        request.source.charge(0)?;
    }
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
    if let Some(prepared) =
        initial_split::prepare(model, trajectory, &initial_ids, &initial_blocks)?
    {
        return Ok(Some(prepared));
    }
    // IR33 publishes declaration seeds only. Execute the unique initial gate
    // before any first physical solve; legacy IR32 had already folded it.
    if !model.program.procedures.is_empty()
        && !model
            .triggers
            .iter()
            .any(|t| matches!(t.trigger, EventTrigger::HeldTimer { .. }))
        && !initial_blocks.is_empty()
        && (model.program.operators.is_empty() || blocks.is_empty())
    {
        cold_charge(model, model.source_copy_items)?;
        let mut stage_blocks = initial_blocks.clone();
        for &block in &blocks {
            if !stage_blocks.contains(&block) {
                stage_blocks.push(block);
            }
        }
        stage_blocks.sort_by_key(|&id| model.program.events[id].expanded_statement_ordinal);
        for &block in &stage_blocks {
            let event = &model.program.events[block];
            check_body(&event.body, model, &event.origin.instance)?;
        }
        let before = model.initial();
        let bounds = before.iter().copied().map(I::point).collect::<Vec<_>>();
        let mut stage_ids = initial_ids.clone();
        stage_ids.extend(zero.iter().copied());
        let mut mixed = MixedCold {
            original_points: BTreeSet::new(),
            allowed: false,
            qualified: None,
        };
        let (states, bounds, records) = prepare_stage(
            model,
            trajectory,
            &stage_blocks,
            &stage_ids,
            &before,
            &bounds,
            &mut mixed,
        )?;
        return Ok(Some(Prepared {
            deferred_zero: false,
            states,
            bounds,
            records,
            bounded_held_transition_seeds: false,
            source_context: model.source_context.clone(),
            future: None,
            zero,
        }));
    }
    let assigned: BTreeSet<_> = blocks
        .iter()
        .flat_map(|&i| model.program.events[i].assignments())
        .map(|a| a.state)
        .collect();
    // With no zero-timer writes the original disjoint-seed test is true for
    // every seed set. A source Floor request needs no bootstrap proof here;
    // its ordinary target construction and event validation still follow.
    if model.floor_source.is_some() && assigned.is_empty() && initial_blocks.is_empty() {
        return Ok(None);
    }
    let mut seeds = BTreeSet::new();
    // Only the ordinary fixed-timer schedule has a bounded cold constructor.
    // All other compositions retain the original point-seed certificate.
    let bounded_fixed_timers = !model.program.operators.is_empty()
        && !model.relocalized_guards.iter().any(|&v| v)
        && !model.dynamic_guards.iter().any(|&v| v)
        && model.guard_operators.iter().all(|ops| ops.is_empty())
        && model.triggers.iter().all(|t| {
            matches!(
                t.trigger,
                EventTrigger::Timer { .. } | EventTrigger::InitialStep { .. }
            )
        });
    let mut bounded_held_transition_seeds = bounded_fixed_timers;
    for (spec_index, spec) in model.program.operators.iter().enumerate() {
        bounded_held_transition_seeds &=
            crate::operators::bare_real_transition_state(spec, &model.program).is_some()
                || matches!(spec, OperatorSpec::Transition { .. })
                    && model.typed_transition_targets.contains(&spec_index);
        if let OperatorSpec::Transition { input, origin, .. } = spec {
            if model.typed_transition_targets.contains(&spec_index) {
                let context = model.source_context.as_ref().expect("typed owner");
                let required = crate::held_integer_target::dependencies(
                    input,
                    &model.program,
                    &origin.instance,
                    context,
                )?;
                crate::held_integer_target::merge_dependencies(
                    &mut seeds,
                    &required,
                    &mut |amount| context.charge(amount),
                )?;
                continue;
            }
            if let Some(request) = &model.floor_source {
                let (dependencies, allowed) =
                    request.bootstrap_dependencies(input, &origin.instance)?;
                if !allowed {
                    return Ok(None);
                }
                request.source.charge(
                    dependencies
                        .len()
                        .saturating_add(seeds.len())
                        .saturating_add(1)
                        .saturating_pow(2)
                        .saturating_mul(8),
                )?;
                seeds.extend(dependencies);
                continue;
            }
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
                        crate::continuous::source_dependency_edges(
                            input,
                            &model.program,
                            &origin.instance,
                            Some(crate::real_expression::work(model)),
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
    if !seeds.is_empty()
        && model
            .triggers
            .iter()
            .any(|t| matches!(t.trigger, EventTrigger::HeldTimer { .. }))
        && model.triggers.iter().all(|t| {
            matches!(
                t.trigger,
                EventTrigger::Timer { .. }
                    | EventTrigger::HeldTimer { .. }
                    | EventTrigger::InitialStep { .. }
            )
        })
    {
        return prepare_held_zero(model, trajectory, &seeds, &initial_ids, &initial_blocks);
    }
    if seeds.is_disjoint(&assigned) {
        if initial_blocks.is_empty() {
            return Ok(None);
        }
        for &block in &initial_blocks {
            cold_charge(model, model.source_copy_items)?;
            let event = &model.program.events[block];
            check_body(&event.body, model, &event.origin.instance)?;
        }
        let before = model.initial();
        let before_bounds = before.iter().copied().map(I::point).collect::<Vec<_>>();
        let mut mixed = MixedCold {
            original_points: BTreeSet::new(),
            allowed: false,
            qualified: None,
        };
        let (states, bounds, records) = prepare_stage(
            model,
            trajectory,
            &initial_blocks,
            &initial_ids,
            &before,
            &before_bounds,
            &mut mixed,
        )?;
        return Ok(deferred_initial(model, states, bounds, records));
    }
    // The legacy proof compares with declaration seeds. IR33 initial gates
    // can first change a seed and timer(0) can restore it; that is still a
    // changed cold-seed transaction and must not fall back after construction.
    if initial_blocks.is_empty()
        && crate::settlement_bounds::unchanged_initial_states(
            model,
            &[initial_blocks.clone(), blocks.clone()],
            &seeds,
            trajectory,
        )
    {
        return Ok(None);
    }
    let before = model.initial();
    let before_bounds: Vec<_> = before.iter().copied().map(I::point).collect();
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
    // Initial assignments in an active instance use the same dependency
    // certificate as zero timers. Physical internal/history reads remain
    // excluded by check_body, and cold_graph preserves every live history.
    for &block in initial_blocks.iter().chain(&blocks) {
        let event = &model.program.events[block];
        check_body(&event.body, model, &event.origin.instance)?;
    }
    // No other live history can be discarded or rebuilt under this proof.
    if !cold_graph(model)? {
        return Err(unsupported("changed initial transition seeds require a closed transition graph or independent source integrals"));
    }
    // Build candidates in language order; neither stage commits any history,
    // calendar consumption or record. Histories are constructed once from the
    // final seed only after both stages pass their certificates.

    // Transition constructors read only their complete structural seed set.
    // Other held values may retain arithmetic uncertainty in Prepared/Frame;
    // they are not exact inputs to any cold history in this restricted graph.
    // Keep the existing all-point rule for every other operator composition.
    let point_states = if bounded_held_transition_seeds && model.typed_transition_targets.is_empty()
    {
        BTreeSet::new()
    } else if bounded_held_transition_seeds {
        model
            .source_context
            .as_ref()
            .expect("typed owner")
            .charge(8 + 8 * seeds.len())?;
        seeds
            .iter()
            .copied()
            .filter(|&s| model.program.states[s].kind == crate::ir::StateKind::Integer)
            .collect()
    } else if model
        .program
        .operators
        .iter()
        .all(|spec| matches!(spec, OperatorSpec::Transition { .. }))
    {
        seeds
    } else {
        (0..model.program.states.len()).collect()
    };
    let ids: Vec<_> = zero.iter().copied().collect();
    let mut mixed = MixedCold {
        original_points: point_states,
        allowed: bounded_fixed_timers,
        qualified: None,
    };
    let (initial_states, initial_bounds, mut records) = prepare_stage(
        model,
        trajectory,
        &initial_blocks,
        &initial_ids,
        &before,
        &before_bounds,
        &mut mixed,
    )?;
    let (states, bounds, timer_records) = prepare_stage(
        model,
        trajectory,
        &blocks,
        &ids,
        &initial_states,
        &initial_bounds,
        &mut mixed,
    )?;
    records.extend(timer_records);
    let source_context = match mixed.qualified {
        Some((context, _)) => {
            bounded_held_transition_seeds = true;
            Some(context)
        }
        None => model.source_context.clone(),
    };
    Ok(Some(Prepared {
        deferred_zero: false,
        states,
        bounds,
        records,
        bounded_held_transition_seeds,
        source_context,
        future: None,
        zero,
    }))
}

type PreparedStage = (Vec<f64>, Vec<I>, Vec<EventRecord>);

struct MixedCold {
    original_points: BTreeSet<usize>,
    allowed: bool,
    qualified: Option<(
        std::sync::Arc<crate::transition_source_plan::ProofContext>,
        BTreeSet<usize>,
    )>,
}
impl MixedCold {
    fn accepts(
        &mut self,
        model: &EventModel,
        trajectory: &Trajectory,
        states: &[f64],
        bounds: &[I],
    ) -> Result<bool, Error> {
        if !self.allowed {
            return Ok(false);
        }
        if self.qualified.is_none() {
            let context = match &model.source_context {
                Some(context) => context.clone(),
                None => {
                    match model.mixed_cold_context.get() {
                        Some(context) => context.clone(),
                        None => {
                            let work = model.mixed_cold_work.get_or_init(|| {
                                crate::transition_source_plan::Work::for_limit(
                                    model.proof_work_limit,
                                )
                            });
                            let context = crate::transition_source_plan::ProofContext::event_request_with_work(
                            &model.program, trajectory, &model.driven,
                            model.source_copy_items, work.clone())?;
                            let _ = model.mixed_cold_context.set(context);
                            model
                                .mixed_cold_context
                                .get()
                                .expect("retained cold owner")
                                .clone()
                        }
                    }
                }
            };
            crate::event_floor::check_provided_binding(
                &context,
                &model.program,
                trajectory,
                &model.driven,
            )?;
            context.charge(1)?;
            let mut required_points = BTreeSet::new();
            let mut bare_real = false;
            for spec in &model.program.operators {
                context.charge(16 + spec.origin().instance.len())?;
                if crate::operators::bare_real_transition_state(spec, &model.program).is_some() {
                    bare_real = true;
                    continue;
                }
                let OperatorSpec::Transition { input, origin, .. } = spec else {
                    return Ok(false);
                };
                let dependencies = match crate::held_integer_target::scalar_dependencies(
                    input,
                    &model.program,
                    &origin.instance,
                    &context,
                ) {
                    Ok(dependencies) => dependencies,
                    Err(scope) if scope.kind == "unsupported_held_integer_target" => {
                        return Ok(false)
                    }
                    Err(failure) => return Err(failure),
                };
                crate::held_integer_target::merge_dependencies(
                    &mut required_points,
                    &dependencies,
                    &mut |amount| context.charge(amount),
                )?;
            }
            if !bare_real {
                return Ok(false);
            }
            self.qualified = Some((context, required_points));
        }
        let (context, points) = self.qualified.as_ref().unwrap();
        context.charge(
            8 + states
                .len()
                .saturating_mul(points.len() + 1)
                .saturating_mul(8),
        )?;
        Ok(states
            .iter()
            .zip(bounds)
            .enumerate()
            .all(|(index, (&s, &b))| !points.contains(&index) || b == I::point(s)))
    }
}

fn prepare_stage(
    model: &EventModel,
    trajectory: &Trajectory,
    blocks: &[usize],
    ids: &[usize],
    before: &[f64],
    before_bounds: &[I],
    mixed: &mut MixedCold,
) -> Result<PreparedStage, Error> {
    if blocks.is_empty() {
        return Ok((before.to_vec(), before_bounds.to_vec(), Vec::new()));
    }
    let inputs = crate::event_value_proof::history::input_bounds(model, trajectory, 0.)?;
    let empty_proofs = crate::event_value_proof::Proofs::new();
    let root = if let Some(w) = crate::analytic_request::proof_owner(model).map(|o| o.work()) {
        let mut p = crate::exact_source::history_paid::Paid::new(w);
        let v = p.binary(0.).map(crate::exact_source::history_paid::root);
        p.finish(v)?
    } else {
        crate::exact_source::RootTime::point(0.)
    };
    let mut context = (model.floor_source.is_some()
        || model.history_admission.is_some()
        || !model.program.procedures.is_empty())
    .then(|| {
        crate::event_value_proof::Context::try_new(
            model,
            trajectory,
            &inputs,
            &empty_proofs,
            root.as_ref(),
        )
    })
    .transpose()?;
    if let Some(c) = context.as_mut() {
        c.set_candidate_frame(
            before,
            &[],
            &crate::event_value_proof::history::inputs(model, trajectory, 0.)?,
            true,
        )?;
    }
    let selection = model.conditions.select_with_proofs(
        blocks,
        &inputs,
        ids,
        before_bounds,
        context.as_ref(),
    )?;
    model.check_selection_writers(&selection)?;
    if let Some(request) = &model.floor_source {
        request
            .source
            .charge(model.program.nodes.len().saturating_add(1))?;
    }
    let mut direct = vec![0.; model.program.nodes.len()];
    if let Some(request) = &model.floor_source {
        for (&node, value) in
            request
                .input_nodes()?
                .iter()
                .zip(crate::event_value_proof::history::inputs(
                    model, trajectory, 0.,
                )?)
        {
            direct[node] = value;
        }
    } else {
        for (name, value) in model
            .driven
            .iter()
            .zip(crate::event_value_proof::history::inputs(
                model, trajectory, 0.,
            )?)
        {
            direct[model.program.nodes.iter().position(|n| n == name).unwrap()] = value;
        }
    }
    let (states, display_records) =
        model.apply_with_displays_with_proofs(&selection, &direct, before, 0., context.as_ref())?;
    let bounds = if context.is_some() {
        model.certify_event_states_with_proofs(
            &selection,
            ids,
            &inputs,
            before_bounds,
            &[],
            &direct,
            &states,
            context.as_ref(),
        )?
    } else {
        crate::settlement_bounds::Bounds::held_inputs(model, &selection)?.check_states(
            model,
            &inputs,
            before_bounds,
            &[],
            &[],
            &states,
        )?
    };
    if states.len() != model.program.states.len()
        || bounds.len() != states.len()
        || bounds
            .iter()
            .zip(&states)
            .any(|(&b, &s)| !s.is_finite() || !b.finite() || s < b.lo || s > b.hi)
    {
        return Err(unsupported(
            "transition bootstrap requires finite final point state certificates",
        ));
    }
    // Finite boxes and nominal containment have already passed. Only the
    // old point requirement may demand the additional mixed-target proof.
    // Continue this transaction; do not rerun any callback or certification.
    if bounds
        .iter()
        .zip(&states)
        .enumerate()
        .any(|(index, (&b, &s))| mixed.original_points.contains(&index) && b != I::point(s))
        && !mixed.accepts(model, trajectory, &states, &bounds)?
    {
        return Err(unsupported(
            "transition bootstrap requires finite final point state certificates",
        ));
    }
    let (replay_states, replay_displays) =
        model.apply_with_displays_with_proofs(&selection, &direct, before, 0., context.as_ref())?;
    let same_displays = replay_displays.len() == display_records.len()
        && replay_displays.iter().zip(&display_records).all(|(a, b)| {
            a.time == b.time && a.event == b.event && a.origin == b.origin && a.text == b.text
        });
    if replay_states != states
        || !same_displays
        || !model
            .conditions
            .select_with_proofs(blocks, &inputs, ids, before_bounds, context.as_ref())?
            .same_path(&selection, crate::real_expression::work(model))?
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

    #[test]
    fn retained_held_initial_seed_retries_share_paid_owner_and_leave_program_unchanged() {
        let request: Request = serde_json::from_str(include_str!(
            "../tests/fixtures/initial_bootstrap_retry.request.json"
        ))
        .unwrap();
        let config = request.transient.clone().unwrap();
        let good = Trajectory::new(config.clone(), request.driven.len()).unwrap();
        let mut bad_config = config;
        bad_config.pwl[0] = vec![[0., 1.], [2., 1.]];
        let bad = Trajectory::new(bad_config, request.driven.len()).unwrap();
        let model = EventModel::new_with_trajectory(
            request.program,
            request.driven,
            request.tolerances,
            Some(&good),
        )
        .unwrap();
        let original = serde_json::to_value(&model.program).unwrap();
        let owner = cold_work(&model).clone();
        assert!(owner.same_owner(crate::real_expression::work(&model)));
        let mut spent = owner.spent();
        for _ in 0..2 {
            assert_eq!(prepare(&model, &bad).err().unwrap().kind, "integer_range");
            assert!(owner.spent() > spent);
            spent = owner.spent();
            assert_eq!(serde_json::to_value(&model.program).unwrap(), original);
            assert_eq!(model.initial(), vec![0., 0., 0.]);
        }
        let prepared = prepare(&model, &good).unwrap().unwrap();
        assert!(prepared.deferred_zero);
        assert_eq!(prepared.states, vec![0., -1., 0.]);
        assert_eq!(prepared.records.len(), 1);
        assert_eq!(prepared.records[0].kind, "initial_step");
        assert!(owner.spent() > spent);
        assert_eq!(serde_json::to_value(&model.program).unwrap(), original);
        // Exhaust this same request owner. A rejected reservation cannot be
        // reset by retrying preparation or choosing the deferred-zero path.
        assert_eq!(owner.debit(2, u64::MAX).unwrap_err().kind, "step_budget");
        for _ in 0..2 {
            assert_eq!(prepare(&model, &good).err().unwrap().kind, "step_budget");
            assert!(owner.same_owner(cold_work(&model)));
            assert_eq!(serde_json::to_value(&model.program).unwrap(), original);
        }
    }

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
                analytic_sources: vec![],
                pwl_errors_v: None,
                strobetimes: Vec::new(),
                pwl: vec![vec![[0., value], [1., value]]],
                output_times: vec![0., 1.],
                stop: 1.,
                max_step: 1.,
                proof_work_limit: None,
            },
            1,
        )
        .unwrap()
    }
    fn held_model() -> EventModel {
        let mut program = model().program.clone();
        program.events[0].trigger = serde_json::from_value(json!({
            "kind":"held_timer", "start":{"op":"affine","constant":0,"terms":[]},
            "period":{"op":"affine","constant":0,"terms":[]},
            "enabled":{"op":"affine","constant":1,"terms":[]}, "time_tolerance":0.001
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
    #[test]
    fn zero_candidate_probe_uses_post_initial_values_and_keeps_unknown_cases() {
        let mut value = serde_json::to_value(&held_model().program).unwrap();
        value["states"].as_array_mut().unwrap().extend([
            json!({"instance":"dut","name":"s","kind":"real","initial":0.125}),
            json!({"instance":"dut","name":"en","kind":"integer","initial":0}),
        ]);
        value["events"][0]["trigger"]["start"] = json!({"op":"state","state":1});
        value["events"][0]["trigger"]["enabled"] = json!({"op":"state","state":2});
        let model = EventModel::new(
            serde_json::from_value(value).unwrap(),
            vec!["u".into()],
            Tolerances {
                absolute: 1e-8,
                relative: 0.,
            },
        )
        .unwrap();
        let declared = [I::ZERO, I::point(0.125), I::ZERO];
        assert!(possible_zero_blocks(&model, &declared).unwrap().is_empty());
        let after_initial = [I::ZERO, I::ZERO, I::ONE];
        assert_eq!(
            possible_zero_blocks(&model, &after_initial).unwrap(),
            vec![0]
        );
        let future = [I::ZERO, I::point(0.125), I::ONE];
        assert!(possible_zero_blocks(&model, &future).unwrap().is_empty());
        let unknown = [I::ZERO, I { lo: 0., hi: 0.125 }, I { lo: 0., hi: 1. }];
        assert_eq!(possible_zero_blocks(&model, &unknown).unwrap(), vec![0]);
    }
    #[test]
    fn held_cold_failure_and_retry_preserve_program_calendar_and_seed() {
        let model = held_model();
        let identity = serde_json::to_value(&model.program).unwrap();
        let original = schedule_held(&model, &trajectory(0.), &[I::ZERO]).unwrap();
        for _ in 0..2 {
            // .2 + .1 has a nonpoint old-arithmetic certificate. A rejected
            // cold candidate must not consume the sole zero occurrence.
            assert_eq!(
                prepare(&model, &trajectory(0.2)).err().unwrap().kind,
                "unsupported_initial_history"
            );
            assert_eq!(model.initial(), vec![0.]);
            assert_eq!(serde_json::to_value(&model.program).unwrap(), identity);
        }
        let retry = prepare(&model, &trajectory(0.)).unwrap().unwrap();
        let clean = prepare(&held_model(), &trajectory(0.)).unwrap().unwrap();
        assert_eq!(retry.states, vec![0.1]);
        assert_eq!(retry.bounds, clean.bounds);
        assert_eq!(retry.zero, clean.zero);
        assert!(retry.future.as_ref().unwrap().is_empty());
        assert_eq!(
            serde_json::to_value(&retry.records).unwrap(),
            serde_json::to_value(&clean.records).unwrap()
        );
        assert_eq!(original.len(), 1);
        assert_eq!(original[0].time, 0.);
        assert_eq!(retry.records.len(), 1);
        let histories = Operators::new(
            &model.program,
            &trajectory(0.),
            &model.driven,
            &retry.states,
        )
        .unwrap();
        for t in [0., 0.25, 1.] {
            assert_eq!(histories.values(t).unwrap(), vec![0.1]);
        }
    }
    #[test]
    fn paid_initial_invariance_success_and_exhaustion_retain_original_owner() {
        let mut model = held_model();
        let trajectory = trajectory(0.);
        let work = crate::transition_source_plan::Work::default();
        let context = crate::transition_source_plan::ProofContext::event_request_with_work(
            &model.program,
            &trajectory,
            &model.driven,
            model.source_copy_items,
            work.clone(),
        )
        .unwrap();
        model.source_context = Some(context);
        let fallback = crate::transition_source_plan::Work::default();
        assert!(model.mixed_cold_work.set(fallback.clone()).is_ok());
        let spent = work.spent();
        assert!(crate::settlement_bounds::unchanged_initial_states_charged(
            &model,
            &[vec![], vec![]],
            &BTreeSet::from([0]),
            &trajectory,
            cold_work(&model),
        )
        .unwrap());
        assert!(work.spent() > spent); // The successful old proof path pays too.
        let ready = prepare(&model, &trajectory).unwrap().unwrap();
        assert_eq!(ready.states, vec![0.1]);
        assert_eq!(fallback.spent(), 0);
        assert!(work.debit(2, 1_000_000_001).is_err());
        let identity = serde_json::to_value(&model.program).unwrap();
        for _ in 0..2 {
            let before = work.spent();
            assert_eq!(
                prepare(&model, &trajectory).err().unwrap().kind,
                "step_budget"
            );
            assert!(work.spent() > before);
            assert_eq!(fallback.spent(), 0);
            assert!(cold_work(&model).same_owner(&work));
            assert_eq!(serde_json::to_value(&model.program).unwrap(), identity);
            assert_eq!(model.initial(), vec![0.]);
        }
    }
    #[test]
    fn one_shot_to_dense_periodic_exhausts_original_work_before_publishing_and_never_refunds() {
        let make = || {
            let mut value = serde_json::to_value(&held_model().program).unwrap();
            value["states"].as_array_mut().unwrap().push(json!({
                "instance":"dut","name":"p","kind":"real","initial":0
            }));
            value["events"][0]["trigger"]["period"] = json!({"op":"state","state":1});
            value["events"][0]["body"] = json!([
                {"kind":"assign","state":0,"rhs":{"op":"affine","constant":1,"terms":[]}},
                {"kind":"assign","state":1,"rhs":{"op":"affine","constant":0.015625,"terms":[]}}
            ]);
            EventModel::new(
                serde_json::from_value(value).unwrap(),
                vec!["u".into()],
                Tolerances {
                    absolute: 1e-8,
                    relative: 0.,
                },
            )
            .unwrap()
        };
        let model = make();
        let trajectory = trajectory(0.);
        let ready = prepare(&model, &trajectory).unwrap().unwrap();
        let future = ready.future.unwrap();
        assert_eq!(future.len(), 64);
        for (index, event) in future.iter().enumerate() {
            assert_eq!(event.time, (index + 1) as f64 / 64.);
        }
        assert_eq!(ready.records.len(), 1);
        assert_eq!(ready.states, vec![1., 0.015625]);
        let model = make();
        let work = crate::transition_source_plan::Work::limited([128, 8192, 5_000_000]);
        assert!(model.mixed_cold_work.set(work.clone()).is_ok());
        // The same request's small initial one-shot calendar is affordable.
        let original =
            crate::schedule::schedule_held_charged(&model, &trajectory, &[I::ZERO, I::ZERO], &work)
                .unwrap();
        assert_eq!(original.len(), 1);
        let identity = serde_json::to_value(&model.program).unwrap();
        // Certified disjoint clock bounds can now make one complete rebuild
        // affordable. Exhaust the original allowance with actual rebuilds,
        // checking every successful candidate instead of prescribing its cost.
        let mut completed = 0;
        loop {
            assert!(
                completed < 10_000,
                "real prepare did not exhaust its original allowance within the test guard"
            );
            let spent = work.spent();
            match prepare(&model, &trajectory) {
                Ok(Some(ready)) => {
                    assert!(work.spent() > spent);
                    let future = ready.future.unwrap();
                    assert_eq!(future.len(), 64);
                    for (index, event) in future.iter().enumerate() {
                        assert_eq!(event.time, (index + 1) as f64 / 64.);
                    }
                    assert_eq!(ready.records.len(), 1);
                    assert_eq!(ready.states, vec![1., 0.015625]);
                    assert!(cold_work(&model).same_owner(&work));
                    assert_eq!(model.initial(), vec![0., 0.]);
                    assert_eq!(serde_json::to_value(&model.program).unwrap(), identity);
                    assert_eq!(original.len(), 1);
                    assert_eq!(original[0].time, 0.);
                    completed += 1;
                }
                Err(error) => {
                    assert_eq!(error.kind, "step_budget");
                    assert!(work.spent() > spent);
                    break;
                }
                Ok(None) => panic!("initial preparation disappeared"),
            }
        }
        assert!(work.spent() > 5_000_000);
        for _ in 0..2 {
            let spent = work.spent();
            assert_eq!(
                prepare(&model, &trajectory).err().unwrap().kind,
                "step_budget"
            );
            assert!(work.spent() > spent);
            assert!(cold_work(&model).same_owner(&work));
            assert_eq!(model.initial(), vec![0., 0.]);
            assert_eq!(serde_json::to_value(&model.program).unwrap(), identity);
            assert_eq!(original.len(), 1);
            assert_eq!(original[0].time, 0.);
        }
    }
    #[test]
    fn rejected_nonbare_initial_certificate_retries_without_seed_or_record_mutation() {
        let mut model = model();
        // The new bounded route deliberately excludes even an affine wrapper.
        // Keep the former point-certificate refusal as a scope detector.
        if let OperatorSpec::Transition { input, .. } = &mut model.program.operators[0] {
            *input = serde_json::from_value(json!({"op":"add","left":{"op":"state","state":0},
                "right":{"op":"affine","constant":0,"terms":[]}}))
            .unwrap();
        }
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
                analytic_sources: vec![],
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
                proof_work_limit: None,
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
    fn invariant_calendar_model() -> EventModel {
        let mut p = nonseed_model().program;
        let c = |value| json!({"op":"affine","constant":value,"terms":[]});
        let u = json!({"op":"affine","constant":0.,"terms":[{"node":1,"coefficient":1.}]});
        let origin = p.events[0].origin.clone();
        p.events[0].body = serde_json::from_value(json!([
            {"kind":"if","relation":"gt","left":u,"right":c(0.),
             "then_body":[{"kind":"assign","state":2,"rhs":c(0.)}],
             "else_body":[{"kind":"assign","state":2,"rhs":c(1.)}],"origin":origin},
            {"kind":"assign","state":0,"rhs":{"op":"multiply","left":c(0.45),"right":u}}
        ]))
        .unwrap();
        p.events[1].body = serde_json::from_value(json!([
            {"kind":"assign","state":3,"rhs":c(1.)},
            {"kind":"assign","state":2,"rhs":c(1.)}
        ]))
        .unwrap();
        p.states.push(
            serde_json::from_value(
                json!({"instance":"dut","name":"due","kind":"real","initial":2}),
            )
            .unwrap(),
        );
        p.events.push(
            serde_json::from_value(json!({"origin":origin,
            "trigger":{"kind":"held_timer","start":{"op":"state","state":4},
                "period":c(0.),"enabled":c(1.),"time_tolerance":1e-12},
            "body":[{"kind":"assign","state":1,"rhs":c(0.)}]}))
            .unwrap(),
        );
        let OperatorSpec::Transition { rise, fall, .. } = &mut p.operators[0] else {
            unreachable!()
        };
        *rise = 0.5;
        *fall = 0.125;
        EventModel::new(
            p,
            vec!["u".into()],
            Tolerances {
                absolute: 1e-8,
                relative: 0.,
            },
        )
        .unwrap()
    }
    fn invariant_controller(
        model: &EventModel,
        t: &Trajectory,
    ) -> (Controller, Vec<ScheduledEvent>) {
        assert!(prepare(model, t).unwrap().is_none());
        let states = model.initial();
        let state_bounds = states.iter().copied().map(I::point).collect::<Vec<_>>();
        let operators = Operators::new(&model.program, t, &model.driven, &states).unwrap();
        let circuit = model
            .circuit_at(&states, &operators.values(0.).unwrap(), &t.value_bounds(0.))
            .unwrap();
        let solution = circuit.solve(&t.values(0.)).unwrap();
        let calendar = schedule_held(model, t, &state_bounds).unwrap();
        (
            Controller {
                accepted: Frame {
                    states,
                    state_bounds,
                    operators,
                    circuit,
                    solution,
                    time: 0.,
                    value_proofs: Default::default(),
                    time_proofs: Default::default(),
                },
                event: 0,
                records: vec![],
                outputs: vec![],
            },
            calendar,
        )
    }
    #[test]
    fn input_aware_seed_proof_keeps_ordinary_zero_execution_and_same_controller_late_retry() {
        let model = invariant_calendar_model();
        let good = nonseed_trajectory(true);
        let bad = nonseed_trajectory(false);
        let (mut controller, mut calendar) = invariant_controller(&model, &good);
        let accept = |c: &mut Controller, t: &Trajectory, q: &mut Vec<ScheduledEvent>| {
            c.accept_changed_events(&model, t, q, event_acceptance::Strategy::Held)
        };
        accept(&mut controller, &good, &mut calendar).unwrap();
        assert_eq!(controller.accepted.time, 0.);
        assert_eq!(controller.records.len(), 1);
        assert!(controller.accepted.state_bounds[0].lo < controller.accepted.state_bounds[0].hi);
        assert!(controller.accepted.value_proofs.contains_key(&0));
        accept(&mut controller, &good, &mut calendar).unwrap();
        assert_eq!(controller.accepted.time, 0.25);
        let before = controller.accepted.clone();
        let records = serde_json::to_value(&controller.records).unwrap();
        let signature = |q: &[ScheduledEvent]| {
            q.iter()
                .map(|e| {
                    (
                        e.event,
                        e.time.to_bits(),
                        e.bounds().lo.to_bits(),
                        e.bounds().hi.to_bits(),
                    )
                })
                .collect::<Vec<_>>()
        };
        let queue = signature(&calendar);
        let cursor = controller.event;
        let same = |a: &Frame, b: &Frame| {
            assert_eq!(a.time, b.time);
            assert_eq!(a.states, b.states);
            assert_eq!(a.state_bounds, b.state_bounds);
            assert_eq!(a.value_proofs, b.value_proofs);
            assert_eq!(a.time_proofs, b.time_proofs);
            assert_eq!(a.solution.voltages, b.solution.voltages);
            assert!(a.operators.same_reset_history(&b.operators));
            for t in [0.375, 0.5, 0.75, 1.] {
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
        let outputs = controller.outputs.clone();
        for _ in 0..2 {
            let error = accept(&mut controller, &bad, &mut calendar).unwrap_err();
            assert_eq!(error.kind, "waveform_accuracy");
            assert!(error.message.contains("forward error"));
            same(&controller.accepted, &before);
            assert_eq!(controller.event, cursor);
            assert_eq!(signature(&calendar), queue);
            assert_eq!(serde_json::to_value(&controller.records).unwrap(), records);
            assert_eq!(controller.outputs.len(), outputs.len());
            for (a, b) in controller.outputs.iter().zip(&outputs) {
                same(a, b);
            }
        }
        accept(&mut controller, &good, &mut calendar).unwrap();
        let (mut clean, mut clean_calendar) = invariant_controller(&model, &good);
        for _ in 0..3 {
            accept(&mut clean, &good, &mut clean_calendar).unwrap();
        }
        same(&controller.accepted, &clean.accepted);
        assert_eq!(signature(&calendar), signature(&clean_calendar));
        assert_eq!(
            serde_json::to_value(&controller.records).unwrap(),
            serde_json::to_value(&clean.records).unwrap()
        );
        assert_eq!(
            controller.records.iter().filter(|r| r.time == 0.).count(),
            1
        );
        assert_eq!(
            controller.accepted.operators.values(0.5).unwrap(),
            vec![0.5]
        );
        assert_eq!(controller.accepted.operators.values(1.).unwrap(), vec![1.]);
        assert!(controller.accepted.state_bounds[0].lo < controller.accepted.state_bounds[0].hi);
    }

    #[test]
    fn bounded_cold_seed_passes_actual_state_box_to_existing_transition_constructor() {
        use num_rational::BigRational as R;
        let model = model();
        let trajectory = trajectory(0.2);
        let prepared = prepare(&model, &trajectory).unwrap().unwrap();
        assert!(prepared.bounded_held_transition_seeds);
        let exact = R::from_float(0.2).unwrap() + R::from_float(0.1).unwrap();
        let b = prepared.bounds[0];
        assert!(b.lo < b.hi);
        assert!(R::from_float(b.lo).unwrap() <= exact && exact <= R::from_float(b.hi).unwrap());
        let histories = Operators::new_until_with_bootstrap_bounds(
            &model.program,
            &trajectory,
            &model.driven,
            &prepared.states,
            &prepared.bounds,
            1.,
            &model.tolerances,
        )
        .unwrap();
        let initial = histories.bounds(0.).unwrap()[0];
        for time in [0., 0.05, 0.5, 1.] {
            let bounds = histories.bounds(time).unwrap()[0];
            assert!(bounds.lo <= b.lo && bounds.hi >= b.hi);
            assert_eq!(histories.values(time).unwrap()[0], prepared.states[0]);
            assert_eq!(bounds, initial); // delay/rise must not invent a cold edge.
        }
        println!(
            "ACTUAL_COLD_SEED_BOX {}",
            json!({"states":prepared.states,
            "state_bounds":prepared.bounds.iter().map(|b|[b.lo,b.hi]).collect::<Vec<_>>(),
            "transition_bounds_at_zero":[initial.lo,initial.hi]})
        );
    }

    fn scalar_mixed_model(hidden_real: bool) -> EventModel {
        let mut value = serde_json::to_value(&model().program).unwrap();
        value["nodes"].as_array_mut().unwrap().push(json!("z"));
        value["states"]
            .as_array_mut()
            .unwrap()
            .push(json!({"instance":"dut","name":"c","kind":"integer","initial":0}));
        value["events"][0]["body"]
            .as_array_mut()
            .unwrap()
            .push(json!({"kind":"assign","state":1,"rhs":{"op":"affine","constant":1,"terms":[]}}));
        let origin = json!({"source":"init.va","line":2,"column":1,"instance":"dut"});
        let mut input = json!({"op":"select","relation":"gt",
            "left":{"op":"state","state":1},
            "right":{"op":"affine","constant":0,"terms":[]},
            "then_value":{"op":"affine","constant":0.9,"terms":[]},
            "else_value":{"op":"affine","constant":0,"terms":[]},"origin":origin});
        if hidden_real {
            input["else_value"] = json!({"op":"state","state":0});
        }
        value["operators"]
            .as_array_mut()
            .unwrap()
            .push(json!({"kind":"transition",
            "input":input,"delay":0,"rise":0.1,"fall":0.1,"origin":origin}));
        value["contributions"].as_array_mut().unwrap().push(json!({
            "branch":{"instance":"dut","local_positive":"q","local_negative":"r","kind":"voltage"},
            "positive":3,"negative":0,"rhs":{"op":"operator","operator":1},"origin":origin}));
        EventModel::new(
            serde_json::from_value(value).unwrap(),
            vec!["u".into()],
            Tolerances {
                absolute: 1e-8,
                relative: 0.,
            },
        )
        .unwrap()
    }

    #[test]
    fn mixed_scalar_cold_proof_retains_one_owner_and_original_boxes_on_retry() {
        let model = scalar_mixed_model(false);
        let trajectory = trajectory(0.2);
        let original = serde_json::to_value(&model.program).unwrap();
        let first = prepare(&model, &trajectory).unwrap().unwrap();
        let context = first.source_context.as_ref().unwrap();
        let spent = context.borrow_work().spent();
        assert!(spent > 0);
        assert!(first.bounds[0].lo < first.bounds[0].hi);
        assert_eq!(first.bounds[1], I::ONE);
        let second = prepare(&model, &trajectory).unwrap().unwrap();
        assert!(std::sync::Arc::ptr_eq(
            context,
            second.source_context.as_ref().unwrap()
        ));
        assert!(context.borrow_work().spent() > spent);
        assert_eq!(first.states, second.states);
        assert_eq!(first.bounds, second.bounds);
        assert_eq!(serde_json::to_value(&model.program).unwrap(), original);
        let histories = Operators::new_until_with_bootstrap_bounds_and_source(
            &model.program,
            &trajectory,
            &model.driven,
            &first.states,
            &first.bounds,
            1.,
            &model.tolerances,
            first.source_context.clone(),
        )
        .unwrap();
        let box_at_zero = histories.bounds(0.).unwrap()[0];
        assert!(box_at_zero.lo <= first.bounds[0].lo && box_at_zero.hi >= first.bounds[0].hi);
    }

    #[test]
    fn mixed_scalar_cold_hidden_real_arm_and_exhausted_owner_stay_rejected() {
        let model = scalar_mixed_model(true);
        let trajectory = trajectory(0.2);
        let original = serde_json::to_value(&model.program).unwrap();
        let mut spent = 0;
        for _ in 0..2 {
            assert_eq!(
                prepare(&model, &trajectory).err().unwrap().kind,
                "unsupported_initial_history"
            );
            let now = model.mixed_cold_work.get().unwrap().spent();
            assert!(now > spent);
            spent = now;
        }
        assert_eq!(serde_json::to_value(&model.program).unwrap(), original);
        let model = scalar_mixed_model(false);
        let work = crate::transition_source_plan::Work::limited([128, 8192, 0]);
        assert!(model.mixed_cold_work.set(work.clone()).is_ok());
        let mut spent = 0;
        for _ in 0..2 {
            assert_eq!(
                prepare(&model, &trajectory).err().unwrap().kind,
                "step_budget"
            );
            assert!(model.mixed_cold_work.get().unwrap().same_owner(&work));
            assert!(work.spent() > spent);
            spent = work.spent();
            assert!(model.mixed_cold_context.get().is_none());
        }
    }

    #[test]
    fn bounded_constructor_rejects_bad_boxes_and_every_nonbare_target_shape() {
        let model = model();
        let trajectory = trajectory(0.2);
        let prepared = prepare(&model, &trajectory).unwrap().unwrap();
        for bounds in [
            vec![],
            vec![I {
                lo: f64::NAN,
                hi: 1.,
            }],
            vec![I {
                lo: f64::NEG_INFINITY,
                hi: f64::INFINITY,
            }],
            vec![I::point(-1.)],
        ] {
            assert!(Operators::new_until_with_bootstrap_bounds(
                &model.program,
                &trajectory,
                &model.driven,
                &prepared.states,
                &bounds,
                1.,
                &model.tolerances
            )
            .is_err());
        }
        let origin = json!({"source":"init.va","line":1,"column":1,"instance":"dut"});
        let inputs = [
            json!({"op":"add","left":{"op":"state","state":0},"right":{"op":"affine","constant":0,"terms":[]}}),
            json!({"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]}),
            json!({"op":"select","relation":"lt","left":{"op":"affine","constant":0,"terms":[]},"right":{"op":"affine","constant":1,"terms":[]},"then_value":{"op":"state","state":0},"else_value":{"op":"state","state":999},"origin":origin}),
        ];
        for input in inputs {
            let mut p = model.program.clone();
            if let OperatorSpec::Transition { input: target, .. } = &mut p.operators[0] {
                *target = serde_json::from_value(input).unwrap();
            }
            assert!(Operators::new_until_with_bootstrap_bounds(
                &p,
                &trajectory,
                &model.driven,
                &prepared.states,
                &prepared.bounds,
                1.,
                &model.tolerances
            )
            .is_err());
        }
        for (kind, owner) in [
            (crate::ir::StateKind::Integer, "dut"),
            (crate::ir::StateKind::Real, "foreign"),
        ] {
            let mut p = model.program.clone();
            p.states[0].kind = kind;
            p.states[0].instance = owner.into();
            assert!(Operators::new_until_with_bootstrap_bounds(
                &p,
                &trajectory,
                &model.driven,
                &prepared.states,
                &prepared.bounds,
                1.,
                &model.tolerances
            )
            .is_err());
        }
        // Low-level pure Transition support does not grant another operator a bounded seed.
        let mut p = model.program.clone();
        p.operators.push(serde_json::from_value(json!({"kind":"idt","input":{"op":"state","state":0},"ic":0,"origin":{"source":"init.va","line":2,"column":1,"instance":"dut"}})).unwrap());
        assert!(Operators::new_until_with_bootstrap_bounds(
            &p,
            &trajectory,
            &model.driven,
            &prepared.states,
            &prepared.bounds,
            1.,
            &model.tolerances
        )
        .is_err());
    }
}

#[cfg(test)]
#[path = "transient_initialization_deferred_budget_tests.rs"]
mod deferred_budget_tests;
