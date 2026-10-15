mod absdelay;
mod accuracy;
mod affine_bounds;
mod analog;
mod assembly;
mod batch;
mod continuous;
pub mod diagnostics;
mod display;
mod dynamic_roots;
mod event_accuracy;
mod event_conditions;
mod event_control;
mod event_numeric;
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
mod passive_events;
mod portability;
mod pwl;
mod reset_dependencies;
mod schedule;
mod settlement;
mod settlement_bounds;
mod slew;
mod slew_cascade;
pub mod solver;
mod state_space;
mod step_bounds;
mod strobe;
mod transient;
mod transition;
mod transition_source_plan;
mod transition_source_state;

#[cfg(test)]
mod performance_probes;

use ir::{Error, Request, Response, SCHEMA_VERSION};
use solver::Circuit;

pub fn run(request: Request) -> Result<Response, Error> {
    run_with_threads(request, 1)
}

/// Independent static samples may run concurrently. Results and errors retain
/// input order; transient state always advances on the serial controller.
pub fn run_with_threads(mut request: Request, static_threads: usize) -> Result<Response, Error> {
    let _timing = crate::diagnostics::span("kernel.run");
    ir::check_schema_version(u64::from(request.program.schema_version))?;
    event_control::validate(&request.program)?;
    step_bounds::Bounds::new(&request.program)?;
    if let Some(config) = &request.transient {
        if let Some(errors) = &config.pwl_errors_v {
            if errors.len() != request.driven.len()
                || errors.len() != config.pwl.len()
                || errors.iter().any(|e| !e.is_finite() || *e < 0.)
            {
                return Err(Error::new("invalid_inputs", "pwl_errors_V must match driven PWL sources and contain nonnegative finite voltage bounds"));
            }
            if errors.iter().any(|e| *e > 0.) {
                let derivative_event =
                    request
                        .program
                        .events
                        .iter()
                        .try_fold(false, |found, event| {
                            Ok::<_, Error>(
                                found
                                    || event.trigger.leaves()?.iter().any(|trigger| {
                                        matches!(
                                            trigger,
                                            ir::EventTrigger::Cross { .. }
                                                | ir::EventTrigger::HeldTimer { .. }
                                        )
                                    }),
                            )
                        })?;
                if !request.program.operators.is_empty() || derivative_event {
                    return Err(Error::new("unsupported_source_uncertainty", "source voltage uncertainty currently supports algebraic voltage relations and fixed timer sampling only; operators, cross and held timers require additional time-shape bounds"));
                }
            }
        }
    }
    // The compiler reserves this unspellable VA identifier for physical time.
    // It is a driven quantity, so event samples retain their root-time enclosure.
    if request.program.nodes.iter().any(|n| n == "$abstime") {
        if request.driven.iter().any(|n| n == "$abstime") {
            return Err(Error::new(
                "invalid_inputs",
                "absolute time cannot be externally driven",
            ));
        }
        request.driven.push("$abstime".into());
        if let Some(transient) = &mut request.transient {
            if let Some(errors) = &mut transient.pwl_errors_v {
                errors.push(0.);
            }
            transient
                .pwl
                .push(vec![[0.0, 0.0], [transient.stop, transient.stop]]);
        } else {
            for sample in &mut request.samples {
                sample.push(0.0);
            }
        }
    }
    if !(1..=64).contains(&static_threads) {
        return Err(Error::new(
            "invalid_config",
            "static thread count must be between 1 and 64",
        ));
    }
    if request.transient.is_some() {
        let modulo_sources = portability::modulo_sources(&request.program);
        let mut response = transient::run(request)?;
        response.portability_advisories = portability::collect(
            response.transient.as_ref(),
            response
                .strobe_evidence
                .as_ref()
                .map(|s| s.times.as_slice()),
            &modulo_sources,
        );
        return Ok(response);
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
        strobe_evidence: None,
        portability_advisories: None,
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

mod math_functions;
