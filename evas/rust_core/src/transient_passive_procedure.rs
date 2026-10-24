//! One certified occurrence owns both physical and passive source execution.
use super::*;
use crate::event_conditions::Selection;
use crate::event_value_proof::Context;
use std::sync::Arc;

pub(super) struct Prepared {
    pub selection: Selection,
    pub states: Vec<f64>,
    pub bounds: Vec<I>,
    pub passive_states: Vec<usize>,
    pub occurrence: Circuit,
}

pub(super) fn prepare(
    model: &EventModel,
    events: &[usize],
    nodes: &[I],
    voltages: &[f64],
    before: &[f64],
    before_bounds: &[I],
    context: &Context<'_>,
) -> Result<Prepared, Error> {
    let work = crate::real_expression::work(model);
    // Reuse the caller's already-certified occurrence. No new root or ordering
    // permission is inferred from equal f64 times or overlapping windows.
    for (index, &event) in events.iter().enumerate() {
        work.step()?;
        if event >= model.program.events.len() {
            return Err(Error::new("invalid_ir", "passive event index out of range"));
        }
        for &prior in &events[..index] {
            work.step()?;
            if prior == event {
                return Err(Error::new("invalid_ir", "duplicate passive batch event"));
            }
        }
    }
    let plan = crate::procedure::execute(
        &model.program,
        events,
        nodes,
        before_bounds,
        Some(context),
        work,
    )?;
    // The same activation Arc is used by both the occurrence circuit and
    // Selection. Move its existing allocation charge before construction.
    let arc_bytes = std::mem::size_of::<crate::procedure::Plan>()
        .saturating_add(2 * std::mem::size_of::<usize>());
    work.debit(2, arc_bytes as u64)?;
    let plan = Arc::new(plan);
    let frame = context.nominal_frame().ok_or_else(|| {
        Error::new(
            "invalid_ir",
            "passive procedure requires its accepted source frame",
        )
    })?;
    let occurrence = plan.circuit(
        &model.program,
        &model.driven,
        before,
        &frame.operators,
        model.tolerances.clone(),
        work,
    )?;
    let states = plan.numeric_states(&model.program, voltages, before, Some(context), work)?;
    let bounds = plan.state_bounds(nodes, before_bounds, Some(context), work)?;
    let (action_items, passive_items) =
        plan.actions
            .iter()
            .try_fold((0usize, 0usize), |(all, passive), (event, indices)| {
                work.step()?;
                Ok::<_, Error>((
                    all.saturating_add(indices.len()),
                    passive.saturating_add(if model.passive_events[*event] {
                        indices.len()
                    } else {
                        0
                    }),
                ))
            })?;
    // Pay for both fixed-capacity outer vectors and all cloned index storage
    // before allocating. Graph and captured values remain one Arc owner.
    let outer_bytes = plan
        .actions
        .len()
        .saturating_mul(2)
        .saturating_mul(std::mem::size_of::<(usize, Vec<usize>)>());
    let index_bytes = action_items
        .saturating_add(passive_items)
        .saturating_mul(std::mem::size_of::<usize>());
    // assigned() collects a flat iterator whose Vec may grow geometrically.
    // This covers that capacity including the initial minimum allocation.
    let assigned_bytes = if passive_items == 0 {
        0
    } else {
        passive_items
            .saturating_mul(2)
            .saturating_add(4)
            .saturating_mul(std::mem::size_of::<usize>())
    };
    work.debit(
        2,
        outer_bytes
            .saturating_add(index_bytes)
            .saturating_add(assigned_bytes) as u64,
    )?;
    let mut actions = Vec::with_capacity(plan.actions.len());
    let mut passive_actions = Vec::with_capacity(plan.actions.len());
    for (event, indices) in &plan.actions {
        work.step()?;
        actions.push((*event, indices.clone()));
        if model.passive_events[*event] {
            passive_actions.push((*event, indices.clone()));
        }
    }
    let passive_states = model.assigned(&Selection {
        actions: passive_actions,
        ..Selection::default()
    });
    let mut selection = Selection {
        actions,
        plan: Some(plan),
        ..Selection::default()
    };
    if context.rooted_occurrence() {
        work.debit(
            1,
            model
                .program
                .events
                .len()
                .saturating_mul(std::mem::size_of::<Option<usize>>()) as u64,
        )?;
        selection.procedure_groups = vec![None; model.program.events.len()];
        for &event in events {
            if let Some(owner) = model.program.events[event].procedure_id {
                for &prior in events {
                    work.step()?;
                    if model.program.events[prior].procedure_id == Some(owner) {
                        selection.procedure_groups[event] = Some(prior);
                        break;
                    }
                }
            }
        }
    }
    model.check_selection_writers(&selection)?;
    Ok(Prepared {
        selection,
        states,
        bounds,
        passive_states,
        occurrence,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn passive_procedure_review_equal_float_is_not_common_occurrence_permission() {
        let request: Request =
            serde_json::from_str(include_str!("passive_procedure_two_gates.json")).unwrap();
        let work = crate::transition_source_plan::Work::default();
        let model = EventModel::new_with_procedure_work(
            request.program,
            request.driven,
            request.tolerances,
            work.clone(),
        )
        .unwrap();
        let before = model.initial();
        let bounds = before.iter().copied().map(I::point).collect::<Vec<_>>();
        let proofs = crate::event_value_proof::Proofs::new();
        let mut context =
            Context::candidate_frame(&proofs, model.program.nodes.len(), &before, &[], &work)
                .unwrap();
        // Both raw events have start=0.5. This context carries no certificate
        // that permits their source frames to be grouped into one occurrence.
        context
            .set_candidate_frame(&before, &[], &[2.], false)
            .unwrap();
        assert!(!context.rooted_occurrence());
        let result = prepare(
            &model,
            &[0, 1],
            &[I::ZERO, I::point(2.)],
            &[0., 2.],
            &before,
            &bounds,
            &context,
        );
        assert_eq!(result.err().unwrap().kind, "event_conflict");
        assert_eq!(before, [0., 0.]);
        assert!(work.spent() > 0);
    }
}
