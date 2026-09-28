//! Bounded damped Newton solve of the same assembled voltage constraints.
use crate::assembly::Equation;
use crate::expression;
use crate::ir::{Error, Solution, Tolerances};
use crate::linear;

struct Evaluation {
    residuals: Vec<f64>,
    jacobian: Vec<Vec<f64>>,
    bounds: Vec<f64>,
}

fn evaluate(
    equations: &[Equation],
    unknown: &[usize],
    values: &[f64],
    tolerance: &Tolerances,
) -> Result<Evaluation, Error> {
    let mut result = Evaluation {
        residuals: Vec::new(),
        jacobian: Vec::new(),
        bounds: Vec::new(),
    };
    for eq in equations {
        let lhs = values[eq.positive] - values[eq.negative];
        let mut rhs = eq.rhs_constant
            + eq.rhs_terms
                .iter()
                .zip(values)
                .map(|(a, v)| a * v)
                .sum::<f64>();
        let mut derivative = eq.rhs_terms.clone();
        for expr in &eq.nonlinear {
            let evaluated = expression::evaluate(expr, values).map_err(|mut error| {
                error
                    .message
                    .push_str(&format!(" at {}", eq.origins.join(", ")));
                error
            })?;
            rhs += evaluated.value;
            for (a, b) in derivative.iter_mut().zip(evaluated.gradient) {
                *a += b;
            }
        }
        let residual = lhs - rhs;
        let bound = tolerance.absolute + tolerance.relative * lhs.abs().max(rhs.abs());
        let jacobian: Vec<_> = unknown
            .iter()
            .map(|&n| f64::from(n == eq.positive) - f64::from(n == eq.negative) - derivative[n])
            .collect();
        if !residual.is_finite() || !bound.is_finite() || jacobian.iter().any(|v| !v.is_finite()) {
            return Err(Error::new(
                "nonfinite_arithmetic",
                format!(
                    "nonfinite residual or Jacobian at {}",
                    eq.origins.join(", ")
                ),
            ));
        }
        result.residuals.push(residual);
        result.jacobian.push(jacobian);
        result.bounds.push(bound);
    }
    Ok(result)
}

fn merit(residuals: &[f64], bounds: &[f64]) -> f64 {
    residuals
        .iter()
        .zip(bounds)
        .map(|(r, b)| r.abs() / b)
        .fold(0.0, f64::max)
}

pub(crate) fn solve(
    equations: &[Equation],
    unknown: &[usize],
    mut values: Vec<f64>,
    tolerance: &Tolerances,
) -> Result<Solution, Error> {
    let context = || {
        equations
            .iter()
            .flat_map(|eq| eq.origins.iter().cloned())
            .collect::<Vec<_>>()
            .join(", ")
    };
    for iteration in 0..=80 {
        let current = evaluate(equations, unknown, &values, tolerance)?;
        let ratio = merit(&current.residuals, &current.bounds);
        if !ratio.is_finite() {
            return Err(Error::new(
                "nonfinite_arithmetic",
                format!("nonfinite scaled residual at {}", context()),
            ));
        }
        // Check local rank even if the zero initialization already satisfies
        // the equations; an unconstrained unknown must never be accepted.
        let step = linear::solve(
            current.jacobian.clone(),
            current.residuals.iter().map(|r| -r).collect(),
            unknown.len(),
        )
        .map_err(|error| {
            Error::new(
                if error.kind == "singular_system" {
                    "singular_jacobian"
                } else {
                    error.kind
                },
                format!(
                    "iteration {iteration}: {}; constraints: {}",
                    error.message,
                    context()
                ),
            )
        })?;
        if ratio <= 1.0 {
            return Ok(Solution {
                voltages: values,
                max_residual_v: current
                    .residuals
                    .iter()
                    .map(|r| r.abs())
                    .fold(0.0, f64::max),
                max_residual_ratio: ratio,
            });
        }
        if unknown.is_empty() {
            return Err(Error::new(
                "residual_failure",
                format!("driven voltages violate constraints at {}", context()),
            ));
        }
        if iteration == 80 {
            break;
        }
        let mut alpha = 1.0;
        let mut accepted = None;
        for _ in 0..32 {
            let mut trial = values.clone();
            for (&node, delta) in unknown.iter().zip(&step) {
                trial[node] += alpha * delta;
            }
            if trial.iter().all(|v| v.is_finite()) {
                if let Ok(candidate) = evaluate(equations, unknown, &trial, tolerance) {
                    // Keep the current scales fixed during line search: changing
                    // a trial's tolerance must not manufacture an improvement.
                    if merit(&candidate.residuals, &current.bounds) <= (1.0 - 1e-4 * alpha) * ratio
                    {
                        accepted = Some(trial);
                        break;
                    }
                }
            }
            alpha *= 0.5;
        }
        match accepted {
            Some(trial) => values = trial,
            None => {
                return Err(Error::new(
                    "nonconvergence",
                    format!(
                        "line search failed at iteration {iteration}; constraints: {}",
                        context()
                    ),
                ))
            }
        }
    }
    Err(Error::new(
        "nonconvergence",
        format!("80 Newton iterations exhausted; constraints: {}", context()),
    ))
}
