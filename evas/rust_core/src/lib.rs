mod assembly;
pub mod ir;
mod linear;
pub mod solver;

use ir::{Error, Request, Response, SCHEMA_VERSION};
use solver::Circuit;

pub fn run(request: Request) -> Result<Response, Error> {
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
        engine: concat!("evas-affine-", env!("CARGO_PKG_VERSION")).into(),
        schema_version: SCHEMA_VERSION,
        nodes: circuit.nodes,
        solutions,
    })
}
