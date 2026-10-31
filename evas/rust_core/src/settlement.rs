//! Same-time affine state/voltage consistency. Trial evaluation is not a commit.
use crate::events::EventModel;
use crate::interval::Interval as I;
use crate::ir::{Error, Solution, StateKind};
use crate::solver::Circuit;

#[cfg(test)]
type PointCandidateHook = Box<dyn FnMut(&mut Solution)>;

#[cfg(test)]
thread_local! {
    pub(crate) static POINT_CANDIDATE_HOOK: std::cell::RefCell<Option<PointCandidateHook>> = const { std::cell::RefCell::new(None) };
}

pub(crate) struct Prepared {
    // Owned output of this exact execution; consumers may move it, never reconstruct its activation.
    pub(crate) selection: Option<crate::event_conditions::Selection>,
    pub(crate) states: Vec<f64>,
    pub(crate) bounds: Vec<I>,
    pub(crate) circuit: Circuit,
    pub(crate) solution: Solution,
    pub(crate) assigned: Vec<usize>,
}

#[allow(clippy::too_many_arguments)]
pub(crate) fn prepare(
    model: &EventModel,
    events: &[usize],
    inputs: (&[f64], &[I]),
    before: &[f64],
    operators: &[f64],
    before_bounds: &[I],
    operator_bounds: &[I],
    previous: Option<&Circuit>,
) -> Result<Prepared, Error> {
    let mut scratch = None;
    prepare_with_scratch(
        model,
        events,
        inputs,
        before,
        operators,
        before_bounds,
        operator_bounds,
        previous,
        &mut scratch,
    )
}

/// `prepare` sharing one assembly scratch across a window's settlement
/// trials. The scratch holds only candidate-independent structure (nodes,
/// branch grouping, labels); all trial voltages, states, operator values and
/// certificates are recomputed from this call's inputs.
#[allow(clippy::too_many_arguments)]
pub(crate) fn prepare_with_scratch(
    model: &EventModel,
    events: &[usize],
    inputs: (&[f64], &[I]),
    before: &[f64],
    operators: &[f64],
    before_bounds: &[I],
    operator_bounds: &[I],
    previous: Option<&Circuit>,
    scratch: &mut Option<crate::assembly::AssemblyPlan>,
) -> Result<Prepared, Error> {
    prepare_impl(
        model,
        (events, &[]),
        inputs,
        inputs.1,
        before,
        operators,
        before_bounds,
        operator_bounds,
        previous,
        true,
        None,
        None,
        None,
        None,
        Some(scratch),
        None,
    )
}

#[allow(clippy::too_many_arguments)]
pub(crate) fn prepare_with_physical_proofs(
    model: &EventModel,
    // Fired leaves carry the post-root side of point cross roots.
    events_and_roots: (&[usize], &[usize]),
    inputs: (&[f64], &[I]),
    before: &[f64],
    operators: &[f64],
    before_bounds: &[I],
    operator_bounds: &[I],
    previous: Option<&Circuit>,
    proofs: &crate::event_value_proof::Context<'_>,
    source: Option<crate::events::SourcePredicateBinding<'_>>,
    lineage: Option<&crate::transient::point_lineage::PointLineage<'_>>,
    physical: Option<&crate::dc_projection::HeldRampPhysicalContext<'_>>,
    scratch: Option<&mut Option<crate::assembly::AssemblyPlan>>,
    observation: Option<(&crate::pwl::Trajectory, f64)>,
) -> Result<Prepared, Error> {
    prepare_impl(
        model,
        events_and_roots,
        inputs,
        inputs.1,
        before,
        operators,
        before_bounds,
        operator_bounds,
        previous,
        true,
        Some(proofs),
        source,
        lineage,
        physical,
        scratch,
        observation,
    )
}

#[allow(clippy::too_many_arguments)]
pub(crate) fn prepare_window(
    model: &EventModel,
    events_and_roots: (&[usize], &[usize]),
    inputs: (&[f64], &[I]),
    observation_inputs: &[I],
    before: &[f64],
    operators: &[f64],
    before_bounds: &[I],
    operator_bounds: &[I],
    previous: Option<&Circuit>,
) -> Result<Prepared, Error> {
    let mut scratch = None;
    prepare_window_with_scratch(
        model,
        events_and_roots,
        inputs,
        observation_inputs,
        before,
        operators,
        before_bounds,
        operator_bounds,
        previous,
        &mut scratch,
    )
}

/// `prepare_window` sharing one assembly scratch across a window's trials.
#[allow(clippy::too_many_arguments)]
pub(crate) fn prepare_window_with_scratch(
    model: &EventModel,
    events_and_roots: (&[usize], &[usize]),
    inputs: (&[f64], &[I]),
    observation_inputs: &[I],
    before: &[f64],
    operators: &[f64],
    before_bounds: &[I],
    operator_bounds: &[I],
    previous: Option<&Circuit>,
    scratch: &mut Option<crate::assembly::AssemblyPlan>,
) -> Result<Prepared, Error> {
    prepare_impl(
        model,
        events_and_roots,
        inputs,
        observation_inputs,
        before,
        operators,
        before_bounds,
        operator_bounds,
        previous,
        false,
        None,
        None,
        None,
        None,
        Some(scratch),
        None,
    )
}

#[allow(clippy::too_many_arguments)]
pub(crate) fn prepare_window_with_physical_proofs(
    model: &EventModel,
    events_and_roots: (&[usize], &[usize]),
    inputs: (&[f64], &[I]),
    observation_inputs: &[I],
    before: &[f64],
    operators: &[f64],
    before_bounds: &[I],
    operator_bounds: &[I],
    previous: Option<&Circuit>,
    proofs: &crate::event_value_proof::Context<'_>,
    source: Option<crate::events::SourcePredicateBinding<'_>>,
    lineage: Option<&crate::transient::point_lineage::PointLineage<'_>>,
    physical: Option<&crate::dc_projection::HeldRampPhysicalContext<'_>>,
    scratch: Option<&mut Option<crate::assembly::AssemblyPlan>>,
    observation: Option<(&crate::pwl::Trajectory, f64)>,
) -> Result<Prepared, Error> {
    prepare_impl(
        model,
        events_and_roots,
        inputs,
        observation_inputs,
        before,
        operators,
        before_bounds,
        operator_bounds,
        previous,
        false,
        Some(proofs),
        source,
        lineage,
        physical,
        scratch,
        observation,
    )
}

// Two certificates: assignments at tau and output voltages at representative b.
#[allow(clippy::too_many_arguments)]
fn prepare_impl(
    model: &EventModel,
    events_and_roots: (&[usize], &[usize]),
    inputs: (&[f64], &[I]),
    observation_inputs: &[I],
    before: &[f64],
    operators: &[f64],
    before_bounds: &[I],
    operator_bounds: &[I],
    previous: Option<&Circuit>,
    check_voltages: bool,
    proofs: Option<&crate::event_value_proof::Context<'_>>,
    source: Option<crate::events::SourcePredicateBinding<'_>>,
    lineage: Option<&crate::transient::point_lineage::PointLineage<'_>>,
    physical: Option<&crate::dc_projection::HeldRampPhysicalContext<'_>>,
    scratch: Option<&mut Option<crate::assembly::AssemblyPlan>>,
    observation: Option<(&crate::pwl::Trajectory, f64)>,
) -> Result<Prepared, Error> {
    crate::diagnostics::counter("settlement_scratch_calls", 1);
    let mut scratch = scratch;
    let (inputs, input_bounds) = inputs;
    let selection = model.conditions.select_with_proofs(
        events_and_roots.0,
        input_bounds,
        events_and_roots.1,
        before_bounds,
        proofs,
    )?;
    model.check_selection_writers(&selection)?;
    model.check_contribution_predicate_updates(&selection, source)?;
    // A unique voltage solution is required. In particular, a zero-delay loop
    // with multiple fixed points is not accepted merely because iteration stalls.
    // Constant/integer event updates can change mode predicates in this same
    // batch. Evaluate those updates first, retaining voltage-dependent updates
    // as affine unknowns in the actual joint solve.
    // Causal sampled actions read actual driven values even in this preview.
    // Unknown electrical nodes remain placeholders and retain the old refusal.
    // The paid source-only exception reads actual driven values here; later
    // state/source-box replay must still certify the selected contribution arm.
    let mut predicate_nodes = vec![0.0; model.program.nodes.len()];
    for (name, &value) in model.driven.iter().zip(inputs) {
        let node = model.program.nodes.iter().position(|n| n == name).unwrap();
        predicate_nodes[node] = value;
    }
    // Selection is already fixed from original before/input boxes. This
    // preview only replays its actions and cannot choose a different callback.
    let physical_preview = physical
        .map(|context| context.prepare(&selection, input_bounds))
        .transpose()?;
    let physical_proof = physical
        .zip(physical_preview.as_ref())
        .map(|(context, preview)| context.proof(preview))
        .transpose()?;
    let representative_proof = physical
        .zip(physical_preview.as_ref())
        .map(|(context, preview)| context.representative_proof(preview))
        .transpose()?;
    let predicate_states = if selection.plan.is_some() {
        before.to_vec()
    } else {
        model.apply_with_proofs(&selection, &predicate_nodes, before, proofs)?
    };
    let predicate_bounds: Vec<_> = predicate_states.iter().copied().map(I::point).collect();
    let selected = model.selected_program_with_observation_proof(
        physical_proof
            .as_ref()
            .map_or(predicate_bounds.as_slice(), |proof| proof.state_bounds()),
        input_bounds,
        events_and_roots.1,
        operator_bounds,
        lineage,
        physical_proof.as_ref(),
    )?;
    let mut joint = model.event_circuit_with_inputs_proofs_and_scratch(
        &selected,
        &selection,
        before,
        operators,
        inputs,
        proofs,
        scratch.as_deref_mut(),
    )?;
    if let Some(previous) = previous {
        joint.reuse_affine_factor_from(previous);
    }
    let candidate = joint.solve(inputs)?;
    let states = model.apply_with_proofs(&selection, &candidate.voltages, before, proofs)?;
    let nominal_replay: Vec<_> = states.iter().copied().map(I::point).collect();
    let replayed = model.selected_program_with_observation_proof(
        physical_proof
            .as_ref()
            .map_or(nominal_replay.as_slice(), |proof| proof.state_bounds()),
        input_bounds,
        events_and_roots.1,
        operator_bounds,
        lineage,
        physical_proof.as_ref(),
    )?;
    // The procedure circuit already replaces each contribution with this
    // activation's source-position capture. Its complete certificate below
    // verifies that captured equation and the state update together. Legacy
    // before/post expression selection is a different relation, and must not
    // reselect a source capture from the final state.
    if let Some(plan) = &selection.plan {
        let work = crate::real_expression::work(model);
        work.debit(2, (before.len() * 8 + 32) as u64)?;
        let view = joint.procedure_view().ok_or_else(|| {
            Error::new(
                "event_consistency",
                "procedure contribution circuit lost its source activation",
            )
        })?;
        if !std::sync::Arc::ptr_eq(&view.plan.graph, &plan.graph)
            || !std::sync::Arc::ptr_eq(&view.plan.base, &plan.base)
            || !view.plan.work.same_owner(work)
            || !plan.work.same_owner(work)
            || view.node_count != model.program.nodes.len()
            || view.before.len() != before.len()
            || !view
                .before
                .iter()
                .zip(before)
                .all(|(a, b)| a.to_bits() == b.to_bits())
        {
            return Err(Error::new(
                "event_consistency",
                "procedure contribution circuit does not retain its original source activation",
            ));
        }
    } else if replayed
        .contributions
        .iter()
        .zip(&selected.contributions)
        .any(|(a, b)| a.rhs != b.rhs)
    {
        return Err(Error::new(
            "unsupported_condition",
            "same-time contribution predicate depends on a voltage-assigned state",
        ));
    }
    // Validate the original, unsubstituted voltage constraints with the replayed
    // state. Substitution roundoff must not replace the physical residual check.
    let mut circuit = if selection.plan.is_some() {
        joint
    } else if let Some(proof) = &representative_proof {
        model.circuit_at_with_observation_proof(&states, operators, observation_inputs, proof)?
    } else {
        model.circuit_at_with_lineage_and_scratch(
            &states,
            operators,
            observation_inputs,
            lineage,
            scratch,
        )?
    };
    if let Some(previous) = previous {
        circuit.reuse_affine_factor_from(previous);
    }
    let mut solution = circuit.solve(inputs)?;
    #[cfg(test)]
    POINT_CANDIDATE_HOOK.with(|slot| {
        if let Some(hook) = slot.borrow_mut().as_mut() {
            hook(&mut solution);
        }
    });
    // Replay the same input/root certificate. A small equation residual
    // cannot certify a branch chosen from rounded representative inputs.
    if !model
        .conditions
        .select_with_proofs(
            events_and_roots.0,
            input_bounds,
            events_and_roots.1,
            before_bounds,
            proofs,
        )?
        .same_path(&selection, crate::real_expression::work(model))?
    {
        return Err(Error::new(
            "event_consistency",
            "condition replay changed the selected path",
        ));
    }
    let replay = model.apply_with_proofs(&selection, &solution.voltages, before, proofs)?;
    for ((&state, &checked), spec) in states.iter().zip(&replay).zip(&model.program.states) {
        let bound = if spec.kind == StateKind::Integer {
            0.0
        } else {
            model.tolerances.relative * state.abs().max(checked.abs())
        };
        if !bound.is_finite() || (state - checked).abs() > bound {
            return Err(Error::new(
                "event_consistency",
                format!(
                    "same-time state replay does not agree at {}:{}",
                    spec.instance, spec.name
                ),
            ));
        }
    }
    let bounds = if check_voltages {
        let (states, nodes) = model.certify_observation_with_context(
            &selection,
            events_and_roots.1,
            input_bounds,
            before_bounds,
            operator_bounds,
            &solution.voltages,
            &states,
            proofs,
            lineage,
            physical_proof.as_ref(),
        )?;
        crate::observation::retain_bounds(&mut solution, nodes);
        states
    } else {
        model.certify_event_states_with_observation_proof(
            &selection,
            events_and_roots.1,
            input_bounds,
            before_bounds,
            operator_bounds,
            &solution.voltages,
            &states,
            proofs,
            lineage,
            physical_proof.as_ref(),
        )?
    };
    if let Some(proof) = &physical_proof {
        proof.validate_states(&bounds)?;
    }
    // A committed event plan must never be replayed at a later observation.
    // The occurrence solution/certificates above retain its source snapshots;
    // future evaluations execute the ordinary procedure with every gate off.
    let same_clock_combinational = if selection.plan.is_some()
        && model.program.states.is_empty()
        && model.program.events.is_empty()
    {
        crate::real_expression::work(model).debit(2, (model.program.operators.len() + 1) as u64)?;
        model.program.operators.iter().all(|operator| {
            matches!(
                operator,
                crate::ir::OperatorSpec::Math { .. } | crate::ir::OperatorSpec::Sin { .. }
            )
        })
    } else {
        false
    };
    // A stateless memoryless source pass already is the ordinary evaluation at
    // this query clock. Replaying it without its exact source context would
    // discard a certified sample/branch. Each later query builds a fresh Plan.
    // Stateful/event/history paths still need their separate ordinary refresh.
    if selection.plan.is_some() && !same_clock_combinational {
        let mut ordinary = if let Some((trajectory, time)) = observation {
            model.circuit_at_procedure_observation(
                &states,
                &bounds,
                operators,
                operator_bounds,
                observation_inputs,
                trajectory,
                time,
            )?
        } else {
            model.circuit_at(&states, operators, observation_inputs)?
        };
        ordinary.retain_procedure_occurrence(&circuit);
        circuit = ordinary;
    }
    Ok(Prepared {
        states,
        bounds,
        circuit,
        solution,
        assigned: model.assigned(&selection),
        selection: Some(selection),
    })
}

#[cfg(test)]
mod activation_selection_owner_tests {
    use super::*;
    #[test]
    fn activation_selection_result_owns_only_this_context_and_occurrence_plan() {
        let mut program: crate::ir::Program =
            serde_json::from_str(include_str!("testdata/real_call_activation.json")).unwrap();
        for event in &mut program.events {
            event.body.clear();
        }
        program.real_bindings.clear();
        program.operators.clear();
        let model =
            EventModel::new(program, vec!["u".into()], crate::ir::Tolerances::default()).unwrap();
        let work = crate::real_expression::work(&model);
        let mut prior: Option<std::sync::Arc<crate::procedure::Plan>> = None;
        for point in [0.1, 0.1, 0.2] {
            let states = [point, 0., 2.];
            let bounds = states.map(I::point);
            let proofs = crate::event_value_proof::Proofs::new();
            let context = crate::event_value_proof::Context::candidate_frame(
                &proofs,
                model.program.nodes.len(),
                &states,
                &[],
                work,
            )
            .unwrap();
            let mut prepared = prepare_with_physical_proofs(
                &model,
                (&[0], &[]),
                (&[1.], &[I::ONE]),
                &states,
                &[],
                &bounds,
                &[],
                None,
                &context,
                None,
                None,
                None,
                None,
                None,
            )
            .unwrap();
            let selection = prepared.selection.take().unwrap();
            assert!(prepared.selection.is_none());
            let plan = selection.plan.as_ref().unwrap();
            assert!(plan.work.same_owner(work));
            let occurrence = prepared.circuit.procedure_occurrence().unwrap();
            assert!(std::sync::Arc::ptr_eq(plan, &occurrence.plan));
            assert_eq!(prepared.states[0].to_bits(), point.to_bits());
            assert_eq!(prepared.solution.voltages[2].to_bits(), point.to_bits());
            if let Some(previous) = &prior {
                assert!(!std::sync::Arc::ptr_eq(previous, plan));
            }
            prior = selection.plan;
        }
    }
}
