//! Same-time affine state/voltage consistency. Trial evaluation is not a commit.
use crate::events::EventModel;
use crate::ir::{Error, Solution, StateKind};
use crate::solver::Circuit;

pub(crate) fn prepare(
    model: &EventModel,
    events: &[usize],
    inputs: &[f64],
    before: &[f64],
    operators: &[f64],
) -> Result<(Vec<f64>, Circuit, Solution), Error> {
    // A unique voltage solution is required. In particular, a zero-delay loop
    // with multiple fixed points is not accepted merely because iteration stalls.
    let candidate = model
        .event_circuit(events, before, operators)?
        .solve(inputs)?;
    let states = model.apply(events, &candidate.voltages, before)?;
    // Validate the original, unsubstituted voltage constraints with the replayed
    // state. Substitution roundoff must not replace the physical residual check.
    let circuit = model.circuit_with(&states, operators)?;
    let solution = circuit.solve(inputs)?;
    let replay = model.apply(events, &solution.voltages, before)?;
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
    model.certify(
        events,
        inputs,
        before,
        operators,
        &solution.voltages,
        &states,
    )?;
    Ok((states, circuit, solution))
}
