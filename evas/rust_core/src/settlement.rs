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
        before,
        operators,
        before_bounds,
        operator_bounds,
        previous,
        true,
    )
}

#[allow(clippy::too_many_arguments)]
pub(crate) fn prepare_window(
    model: &EventModel,
    events_and_roots: (&[usize], &[usize]),
    inputs: (&[f64], &[I]),
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
        before,
        operators,
        before_bounds,
        operator_bounds,
        previous,
        false,
    )
}

// Two certificates: assignments at tau and output voltages at representative b.
#[allow(clippy::too_many_arguments)]
fn prepare_impl(
    model: &EventModel,
    events_and_roots: (&[usize], &[usize]),
    inputs: (&[f64], &[I]),
    before: &[f64],
    operators: &[f64],
    before_bounds: &[I],
    operator_bounds: &[I],
    previous: Option<&Circuit>,
    check_voltages: bool,
) -> Result<Prepared, Error> {
    let (inputs, input_bounds) = inputs;
    let selection =
        model
            .conditions
            .select_at_roots(events_and_roots.0, input_bounds, events_and_roots.1)?;
    model.check_selection_writers(&selection)?;
    // A unique voltage solution is required. In particular, a zero-delay loop
    // with multiple fixed points is not accepted merely because iteration stalls.
    let mut joint = model.event_circuit(&selection, before, operators)?;
    if let Some(previous) = previous {
        joint.reuse_affine_factor_from(previous);
    }
    let candidate = joint.solve(inputs)?;
    let states = model.apply(&selection, &candidate.voltages, before)?;
    // Validate the original, unsubstituted voltage constraints with the replayed
    // state. Substitution roundoff must not replace the physical residual check.
    let mut circuit = model.circuit_with(&states, operators)?;
    if let Some(previous) = previous {
        circuit.reuse_affine_factor_from(previous);
    }
    let solution = circuit.solve(inputs)?;
    // Replay the same input/root certificate. A small equation residual
    // cannot certify a branch chosen from rounded representative inputs.
    if model
        .conditions
        .select_at_roots(events_and_roots.0, input_bounds, events_and_roots.1)?
        != selection
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
    let certify = if check_voltages {
        EventModel::certify
    } else {
        EventModel::certify_event_states
    };
    let bounds = certify(
        model,
        &selection,
        input_bounds,
        before_bounds,
        operator_bounds,
        &solution.voltages,
        &states,
    )?;
    Ok(Prepared {
        states,
        bounds,
        circuit,
        solution,
        assigned: model.assigned(&selection),
    })
}
