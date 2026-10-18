//! Same-time affine state/voltage consistency. Trial evaluation is not a commit.
use crate::events::EventModel;
use crate::interval::Interval as I;
use crate::ir::{Error, Solution, StateKind};
use crate::solver::Circuit;

pub(crate) struct Prepared {
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
    )
}

#[allow(clippy::too_many_arguments)]
pub(crate) fn prepare_with_proofs(
    model: &EventModel,
    events: &[usize],
    inputs: (&[f64], &[I]),
    before: &[f64],
    operators: &[f64],
    before_bounds: &[I],
    operator_bounds: &[I],
    previous: Option<&Circuit>,
    proofs: &crate::event_value_proof::Context<'_>,
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
        Some(proofs),
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
    )
}

#[allow(clippy::too_many_arguments)]
pub(crate) fn prepare_window_with_proofs(
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
) -> Result<Prepared, Error> {
    let (inputs, input_bounds) = inputs;
    let selection = model.conditions.select_with_proofs(
        events_and_roots.0,
        input_bounds,
        events_and_roots.1,
        before_bounds,
        proofs,
    )?;
    model.check_selection_writers(&selection)?;
    model.check_contribution_predicate_updates(&selection)?;
    // A unique voltage solution is required. In particular, a zero-delay loop
    // with multiple fixed points is not accepted merely because iteration stalls.
    // Constant/integer event updates can change mode predicates in this same
    // batch. Evaluate those updates first, retaining voltage-dependent updates
    // as affine unknowns in the actual joint solve.
    // Causal sampled actions read actual driven values even in this preview.
    // Unknown electrical nodes remain placeholders; predicates depending on
    // voltage-assigned states were rejected above and the joint solve owns them.
    let mut predicate_nodes = vec![0.0; model.program.nodes.len()];
    for (name, &value) in model.driven.iter().zip(inputs) {
        let node = model.program.nodes.iter().position(|n| n == name).unwrap();
        predicate_nodes[node] = value;
    }
    let predicate_states = model.apply_with_proofs(&selection, &predicate_nodes, before, proofs)?;
    let predicate_bounds: Vec<_> = predicate_states.iter().copied().map(I::point).collect();
    let selected = model.selected_program_with_parameters(
        &predicate_bounds,
        input_bounds,
        events_and_roots.1,
        operator_bounds,
    )?;
    let mut joint = model.event_circuit_program_with_inputs_and_proofs(
        &selected, &selection, before, operators, inputs, proofs,
    )?;
    if let Some(previous) = previous {
        joint.reuse_affine_factor_from(previous);
    }
    let candidate = joint.solve(inputs)?;
    let states = model.apply_with_proofs(&selection, &candidate.voltages, before, proofs)?;
    let replayed = model.selected_program_with_parameters(
        &states.iter().copied().map(I::point).collect::<Vec<_>>(),
        input_bounds,
        events_and_roots.1,
        operator_bounds,
    )?;
    if replayed
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
    let mut circuit = model.circuit_at(&states, operators, observation_inputs)?;
    if let Some(previous) = previous {
        circuit.reuse_affine_factor_from(previous);
    }
    let mut solution = circuit.solve(inputs)?;
    // Replay the same input/root certificate. A small equation residual
    // cannot certify a branch chosen from rounded representative inputs.
    if model.conditions.select_with_proofs(
        events_and_roots.0,
        input_bounds,
        events_and_roots.1,
        before_bounds,
        proofs,
    )? != selection
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
        let (states, nodes) = model.certify_observation_at_roots_with_proofs(
            &selection,
            events_and_roots.1,
            input_bounds,
            before_bounds,
            operator_bounds,
            &solution.voltages,
            &states,
            proofs,
        )?;
        crate::observation::retain_bounds(&mut solution, nodes);
        states
    } else {
        model.certify_event_states_with_proofs(
            &selection,
            events_and_roots.1,
            input_bounds,
            before_bounds,
            operator_bounds,
            &solution.voltages,
            &states,
            proofs,
        )?
    };
    Ok(Prepared {
        states,
        bounds,
        circuit,
        solution,
        assigned: model.assigned(&selection),
    })
}
