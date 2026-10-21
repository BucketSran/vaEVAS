//! Narrow ordinary held-target composition with the existing history calendar.
//! This supplies no new predicate, source, analytic or forcing permission.
use crate::events::EventModel;
use crate::interval::Interval as I;
use crate::ir::{Error, EventTrigger};
use crate::operators::Operators;
use crate::pwl::Trajectory;
use crate::schedule::{history_epoch, independent_epoch, HistoryEpoch, ScheduledEvent};

pub(crate) fn qualify(model: &EventModel) -> Result<(), Error> {
    let refusal = || {
        Error::new(
        "unsupported_held_integer_target",
        "typed held targets require the ordinary independent calendar or a pure held history calendar",
    )
    };
    if model.typed_transition_targets.is_empty()
        || !model.guard_operators.iter().any(|ops| !ops.is_empty())
        || model.forcing.is_some()
        || model.analytic_request.is_some()
        || model.history_admission.is_some()
        || model.floor_source.is_some()
    {
        return Err(refusal());
    }
    for (index, leaf) in model.triggers.iter().enumerate() {
        if matches!(leaf.trigger, EventTrigger::Cross { .. })
            && (model.relocalized_guards[index]
                || (model.dynamic_guards[index] && model.guard_operators[index].is_empty()))
        {
            // Held timers retain the old independent rescheduling proof. A
            // typed target cannot authorize an unrelated dynamic/held guard.
            return Err(refusal());
        }
    }
    Ok(())
}

pub(crate) fn initialize(
    model: &EventModel,
    trajectory: &Trajectory,
    states: &[f64],
    initial_bounds: Option<&[I]>,
) -> Result<(Operators, Vec<ScheduledEvent>), Error> {
    qualify(model)?;
    let context = model.source_context.as_ref().ok_or_else(|| {
        Error::new(
            "invalid_ir",
            "typed history calendar lost its original owner",
        )
    })?;
    crate::event_floor::check_provided_binding(context, &model.program, trajectory, &model.driven)?;
    // A missing bootstrap box means declaration state, just as on the ordinary
    // typed path. Existing bootstrap boxes are copied whole, never normalized
    // to their nominal state before the constructor audits every dependency.
    context.charge(4 + states.len() * 4)?;
    let bounds: Vec<_> = match initial_bounds {
        Some(actual) => actual.to_vec(),
        None => states.iter().copied().map(I::point).collect(),
    };
    let pending = independent_epoch(model, trajectory, &bounds, None)?;
    let until = pending
        .first()
        .map_or(trajectory.config.stop, |event| event.time);
    let operators = Operators::new_until_with_typed_calendar(
        &model.program,
        trajectory,
        &model.driven,
        states,
        &bounds,
        &model.typed_transition_targets,
        context.clone(),
        until,
        &model.tolerances,
    )?;
    let calendar = history_epoch(
        model,
        trajectory,
        &operators,
        HistoryEpoch {
            states: &bounds,
            after: None,
            until,
            consumed: &[],
            pending: &pending,
        },
    )?;
    Ok((operators, calendar))
}

#[cfg(test)]
#[path = "history_calendar_typed_target_tests.rs"]
mod tests;
