mod absdelay;
mod affine_bounds;
mod analog;
mod assembly;
mod batch;
mod continuous;
pub mod diagnostics;
mod dynamic_roots;
mod event_accuracy;
mod event_conditions;
mod events;
mod exact_source;
mod exact_time;
mod expression;
mod guard_trajectory;
mod idt;
mod idtmod;
mod initialization;
mod input_clamp;

mod interval;
pub mod ir;
mod laplace;
mod linear;
mod nonlinear;
mod observation;
mod operators;
mod pwl;
mod reset_dependencies;
mod schedule;
mod settlement;
mod settlement_bounds;
mod slew;
pub mod solver;
mod state_space;
mod transient;
mod transition;

#[cfg(test)]
mod performance_probes;

use ir::{Error, Request, Response, SCHEMA_VERSION};
use solver::Circuit;

pub fn run(request: Request) -> Result<Response, Error> {
    run_with_threads(request, 1)
}

/// Independent static samples may run concurrently. Results and errors retain
/// input order; transient state always advances on the serial controller.
pub fn run_with_threads(request: Request, static_threads: usize) -> Result<Response, Error> {
    let _timing = crate::diagnostics::span("kernel.run");
    if !(1..=64).contains(&static_threads) {
        return Err(Error::new(
            "invalid_config",
            "static thread count must be between 1 and 64",
        ));
    }
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
    let solutions = batch::solve(&circuit, &request.samples, static_threads)?;
    Ok(Response {
        observation_evidence: None,
        engine: concat!("evas-static-", env!("CARGO_PKG_VERSION")).into(),
        schema_version: SCHEMA_VERSION,
        nodes: circuit.nodes,
        solutions,
        transient: None,
    })
}

#[cfg(test)]
mod tests {
    #[test]
    fn fuzz_seed_is_a_runnable_independent_affine_reference() {
        let request = crate::ir::parse_request(include_str!("../fuzz/seeds/static.json"))
            .expect("the fuzz seed must use the current IR");
        let response = super::run(request).expect("the fuzz seed must remain runnable");
        // The seed contributes y = 1/8 + u/2 at u = 1/4, so y = 1/4.
        assert_eq!(response.solutions.len(), 1);
        assert_eq!(response.solutions[0].voltages, [0.0, 0.25, 0.25]);
    }
}
