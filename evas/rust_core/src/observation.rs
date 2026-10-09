//! Preserve already-computed observation certificates, without changing acceptance.
use crate::interval::Interval;
use crate::ir::{
    EffectiveObservationControls, ObservationEvidence, Solution, Tolerances, TransientInputs,
};

pub(crate) fn retain_bounds(solution: &mut Solution, bounds: Vec<Interval>) {
    debug_assert_eq!(bounds.len(), solution.voltages.len());
    solution.certified_voltage_bounds = Some(
        bounds
            .into_iter()
            .zip(&solution.voltages)
            // A certificate encloses the exact root; the returned approximation
            // need not lie inside it. Its hull is still a valid conservative bound.
            .map(|(bound, &value)| [bound.lo.min(value), bound.hi.max(value)])
            .collect(),
    );
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
        },
        sample_origins,
        initial_settled,
        voltage_bounds_v: solutions
            .iter()
            .map(|s| s.certified_voltage_bounds.clone())
            .collect(),
    }
}
