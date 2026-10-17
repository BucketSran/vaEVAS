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
        scratch,
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
        scratch,
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
    scratch: &mut Option<crate::assembly::AssemblyPlan>,
) -> Result<Prepared, Error> {
    crate::diagnostics::counter("settlement_scratch_calls", 1);
    let (inputs, input_bounds) = inputs;
    let selection = model.conditions.select_at_roots(
        events_and_roots.0,
        input_bounds,
        events_and_roots.1,
        before_bounds,
    )?;
    model.check_selection_writers(&selection)?;
    model.check_contribution_predicate_updates(&selection)?;
    // A unique voltage solution is required. In particular, a zero-delay loop
    // with multiple fixed points is not accepted merely because iteration stalls.
    // Constant/integer event updates can change mode predicates in this same
    // batch. Evaluate those updates first, retaining voltage-dependent updates
    // as affine unknowns in the actual joint solve.
    let predicate_states =
        model.apply(&selection, &vec![0.0; model.program.nodes.len()], before)?;
    let predicate_bounds: Vec<_> = predicate_states.iter().copied().map(I::point).collect();
    let selected =
        model.selected_program_at_roots(&predicate_bounds, input_bounds, events_and_roots.1)?;
    let mut joint = model
        .event_circuit_program_with_scratch(&selected, &selection, before, operators, scratch)?;
    if let Some(previous) = previous {
        joint.reuse_affine_factor_from(previous);
    }
    let candidate = joint.solve(inputs)?;
    let states = model.apply(&selection, &candidate.voltages, before)?;
    let replayed = model.selected_program_at_roots(
        &states.iter().copied().map(I::point).collect::<Vec<_>>(),
        input_bounds,
        events_and_roots.1,
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
    let mut circuit =
        model.circuit_at_with_scratch(&states, operators, observation_inputs, scratch)?;
    if let Some(previous) = previous {
        circuit.reuse_affine_factor_from(previous);
    }
    let mut solution = circuit.solve(inputs)?;
    // Replay the same input/root certificate. A small equation residual
    // cannot certify a branch chosen from rounded representative inputs.
    if model.conditions.select_at_roots(
        events_and_roots.0,
        input_bounds,
        events_and_roots.1,
        before_bounds,
    )? != selection
    {
        return Err(Error::new(
            "event_consistency",
            "condition replay changed the selected path",
        ));
    }
    let replay = model.apply(&selection, &solution.voltages, before)?;
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
        let (states, nodes) = model.certify_observation_at_roots(
            &selection,
            events_and_roots.1,
            input_bounds,
            before_bounds,
            operator_bounds,
            &solution.voltages,
            &states,
        )?;
        crate::observation::retain_bounds(&mut solution, nodes);
        states
    } else {
        model.certify_event_states(
            &selection,
            events_and_roots.1,
            input_bounds,
            before_bounds,
            operator_bounds,
            &solution.voltages,
            &states,
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
