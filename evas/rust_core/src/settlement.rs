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

pub(crate) fn prepare(
    model: &EventModel,
    events: &[usize],
    inputs: (&[f64], &[I]),
    before: &[f64],
    operators: &[f64],
    before_bounds: &[I],
    operator_bounds: &[I],
) -> Result<Prepared, Error> {
    let (inputs, input_bounds) = inputs;
    let selection = model.conditions.select(events, input_bounds)?;
    // A unique voltage solution is required. In particular, a zero-delay loop
    // with multiple fixed points is not accepted merely because iteration stalls.
    let candidate = model
        .event_circuit(&selection, before, operators)?
        .solve(inputs)?;
    let states = model.apply(&selection, &candidate.voltages, before)?;
    // Validate the original, unsubstituted voltage constraints with the replayed
    // state. Substitution roundoff must not replace the physical residual check.
    let circuit = model.circuit_with(&states, operators)?;
    let solution = circuit.solve(inputs)?;
    // Recheck control flow at the representative time. A small equation
    // residual cannot certify a branch chosen from rounded input values.
    if model.conditions.select(events, input_bounds)? != selection {
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
    let bounds = model.certify(
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
