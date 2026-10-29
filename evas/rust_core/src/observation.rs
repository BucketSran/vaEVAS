//! Preserve already-computed observation certificates, without changing acceptance.
use crate::interval::Interval;
use crate::ir::{
    EffectiveObservationControls, ObservationEvidence, Solution, Tolerances, TransientInputs,
};

pub(crate) fn retain_bounds(solution: &mut Solution, bounds: Vec<Interval>) {
    let representatives = &solution.voltages;
    solution.certified_voltage_bounds = Some(hull_bounds(bounds, representatives));
}
pub(crate) fn retain_residual_bounds(
    solution: &mut Solution,
    bounds: Vec<Interval>,
    representatives: &[f64],
) {
    solution.certified_voltage_bounds = Some(hull_bounds(bounds, representatives));
}
fn hull_bounds(bounds: Vec<Interval>, representatives: &[f64]) -> Vec<[f64; 2]> {
    debug_assert_eq!(bounds.len(), representatives.len());
    bounds
        .into_iter()
        .zip(representatives)
        // A certificate encloses the exact root; the returned approximation
        // need not lie inside it. Its hull is still a valid conservative bound.
        .map(|(bound, &value)| [bound.lo.min(value), bound.hi.max(value)])
        .collect()
}

pub(crate) fn evidence(
    nodes: &[String],
    solutions: &[Solution],
    config: &TransientInputs,
    tolerances: &Tolerances,
    sample_origins: Vec<&'static str>,
    max_step_applied: bool,
    initial_settled: Option<bool>,
) -> ObservationEvidence {
    debug_assert_eq!(solutions.len(), sample_origins.len());
    ObservationEvidence {
        schema_version: 1,
        nodes: nodes.to_vec(),
        effective_controls: EffectiveObservationControls {
            absolute_v: tolerances.absolute,
            relative: tolerances.relative,
            stop_s: config.stop,
            max_step_s: config.max_step,
            max_step_applied,
            proof_work_limit: config.effective_proof_work_limit(),
        },
        sample_origins,
        initial_settled,
        voltage_bounds_v: solutions
            .iter()
            .map(|s| s.certified_voltage_bounds.clone())
            .collect(),
    }
}

#[cfg(test)]
mod echo_tests {
    use super::*;

    fn config(limit: Option<u64>) -> TransientInputs {
        TransientInputs {
            analytic_sources: vec![],
            pwl_errors_v: None,
            strobetimes: vec![],
            pwl: vec![],
            output_times: vec![0.0],
            stop: 1.0,
            max_step: 1.0,
            proof_work_limit: limit,
        }
    }

    #[test]
    fn effective_controls_echo_the_requested_and_the_default_proof_limit() {
        for (requested, expected) in [
            (None, 1_000_000_000u64),
            (Some(1_000_000_000), 1_000_000_000),
            (Some(2_000_000_000_000), 2_000_000_000_000),
        ] {
            let evidence = evidence(
                &["0".to_string()],
                &[],
                &config(requested),
                &Tolerances::default(),
                vec![],
                false,
                None,
            );
            assert_eq!(evidence.effective_controls.proof_work_limit, expected);
            let wire = serde_json::to_value(&evidence).unwrap();
            assert_eq!(wire["effective_controls"]["proof_work_limit"], expected);
        }
    }
}
