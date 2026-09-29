mod absdelay;
mod affine_bounds;
mod assembly;
mod event_accuracy;
mod events;
mod expression;
mod interval;
pub mod ir;
mod linear;
mod nonlinear;
mod operators;
mod pwl;
mod schedule;
mod settlement;
mod settlement_bounds;
mod slew;
pub mod solver;
mod transient;
mod transition;

use ir::{Error, Request, Response, SCHEMA_VERSION};
use solver::Circuit;

pub fn run(request: Request) -> Result<Response, Error> {
    if request.transient.is_some() {
        return transient::run(request);
    }
    if !request.program.states.is_empty()
        || !request.program.events.is_empty()
        || !request.program.operators.is_empty()
    {
        return Err(Error::new(
            "unsupported_analysis",
            "state/event program requires transient execution",
        ));
    }
    if request.samples.is_empty() {
        return Err(Error::new(
            "invalid_inputs",
            "at least one sample is required",
        ));
    }
    let circuit = Circuit::new(request.program, &request.driven, request.tolerances)?;
    let solutions = request
        .samples
        .iter()
        .enumerate()
        .map(|(index, inputs)| {
            circuit.solve(inputs).map_err(|mut error| {
                error.sample = Some(index);
                error
            })
        })
        .collect::<Result<_, _>>()?;
    Ok(Response {
        engine: concat!("evas-static-", env!("CARGO_PKG_VERSION")).into(),
        schema_version: SCHEMA_VERSION,
        nodes: circuit.nodes,
        solutions,
        transient: None,
    })
}
