//! Bounded damped Newton solve of the same assembled voltage constraints.
use crate::assembly::Equation;
use crate::expression;
use crate::ir::{Error, Solution, Tolerances};
use crate::linear;
mod continuation;

struct Evaluation {
    residuals: Vec<f64>,
    jacobian: Vec<linear::Row>,
    bounds: Vec<f64>,
    row_scales: Vec<f64>,
}

fn evaluate(
    equations: &[Equation],
    unknown_columns: &[Option<usize>],
    values: &[f64],
    tolerance: &Tolerances,
) -> Result<Evaluation, Error> {
    let mut result = Evaluation {
        residuals: Vec::new(),
        jacobian: Vec::new(),
        bounds: Vec::new(),
        row_scales: Vec::new(),
    };
    for eq in equations {
        let lhs = values[eq.positive] - values[eq.negative];
        let mut sum = expression::Accumulator::new();
        sum.add_node(eq.positive, 1.0, values[eq.positive]);
        sum.add_node(eq.negative, -1.0, values[eq.negative]);
        sum.add_constant(-eq.rhs_constant);
        for &(node, coefficient) in &eq.rhs_terms {
            sum.add_node(node, -coefficient, values[node]);
        }
        for expr in &eq.nonlinear {
            sum.add_expression(expr, -1.0, values)
                .map_err(|mut error| {
                    error
                        .message
                        .push_str(&format!(" at {}", eq.origins.join(", ")));
                    error
                })?;
        }
        let evaluated = sum.finish().map_err(|mut error| {
            error
                .message
                .push_str(&format!(" at {}", eq.origins.join(", ")));
            error
        })?;
        let residual = evaluated.value;
        let rhs = lhs - residual;
        let bound = tolerance.absolute + tolerance.relative * lhs.abs().max(rhs.abs());
        let jacobian: linear::Row = evaluated
            .gradient
            .into_iter()
            .filter_map(|(node, value)| {
                unknown_columns[node]
                    .filter(|_| value != 0.0)
                    .map(|column| (column, value))
            })
            .collect();
        if !residual.is_finite()
            || !bound.is_finite()
            || jacobian.iter().any(|(_, v)| !v.is_finite())
        {
            return Err(Error::new(
                "nonfinite_arithmetic",
                format!(
                    "nonfinite residual or Jacobian at {}",
                    eq.origins.join(", ")
                ),
            ));
        }
        // Like the linear solver's row scaling, this removes arbitrary local
        // equation gains. Check every row, including redundant constraints.
        // A row independent of unknown voltages retains its physical bound.
        let scale = jacobian.iter().fold(0.0_f64, |s, (_, v)| s.max(v.abs()));
        result
            .row_scales
            .push(if scale > 0.0 { scale } else { 1.0 });
        result.residuals.push(residual);
        result.jacobian.push(jacobian);
        result.bounds.push(bound);
    }
    Ok(result)
}

fn scaled_merit(residuals: &[f64], bounds: &[f64], scales: &[f64]) -> f64 {
    residuals
        .iter()
        .zip(bounds)
        .zip(scales)
        .map(|((r, b), s)| (r.abs() / s) / b)
        .fold(0.0, f64::max)
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
    unknown_columns: &[Option<usize>],
    values: Vec<f64>,
    tolerance: &Tolerances,
) -> Result<Solution, Error> {
    match newton(
        equations,
        unknown,
        unknown_columns,
        values.clone(),
        tolerance,
        None,
    ) {
        Ok(solution) => Ok(solution),
        Err(error) if matches!(error.kind, "nonconvergence" | "singular_jacobian") => {
            continuation::solve(equations, unknown, unknown_columns, values, tolerance).ok_or(error)
        }
        Err(error) => Err(error),
    }
}

fn newton(
    equations: &[Equation],
    unknown: &[usize],
    unknown_columns: &[Option<usize>],
    mut values: Vec<f64>,
    tolerance: &Tolerances,
    path: Option<&continuation::Path<'_>>,
) -> Result<Solution, Error> {
    let evaluate = |values: &[f64]| -> Result<Evaluation, Error> {
        let mut result = evaluate(equations, unknown_columns, values, tolerance)?;
        if let Some(path) = path {
            path.apply(&mut result, values, tolerance)?;
        }
        Ok(result)
    };
    let context = || {
        equations
            .iter()
            .flat_map(|eq| eq.origins.iter().cloned())
            .collect::<Vec<_>>()
            .join(", ")
    };
    let mut current = evaluate(&values)?;
    for iteration in 0..=80 {
        let ratio = merit(&current.residuals, &current.bounds);
        let scaled_ratio = scaled_merit(&current.residuals, &current.bounds, &current.row_scales);
        if !ratio.is_finite() || !scaled_ratio.is_finite() {
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
        let mut correction_ratio = 0.0_f64;
        let mut correction_v = 0.0_f64;
        for (&node, delta) in unknown.iter().zip(&step) {
            let bound = tolerance.absolute + tolerance.relative * values[node].abs();
            if !bound.is_finite() {
                return Err(Error::new(
                    "nonfinite_arithmetic",
                    "nonfinite voltage tolerance",
                ));
            }
            correction_v = correction_v.max(delta.abs());
            correction_ratio = correction_ratio.max(delta.abs() / bound);
        }
        // A damped step can be arbitrarily small far from a root. Test the
        // full Newton correction, and retain both original and scaled rows.
        if ratio <= 1.0 && scaled_ratio <= 1.0 && correction_ratio <= 1.0 {
            return Ok(Solution {
                certified_voltage_bounds: None,
                voltages: values,
                max_residual_v: current
                    .residuals
                    .iter()
                    .map(|r| r.abs())
                    .fold(0.0, f64::max),
                max_residual_ratio: ratio,
                max_scaled_residual_ratio: Some(scaled_ratio),
                max_voltage_correction_v: Some(correction_v),
                max_voltage_correction_ratio: Some(correction_ratio),
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
            if trial == values {
                return Err(Error::new(
                    "nonconvergence",
                    format!(
                        "voltage update stagnated at iteration {iteration}; residual ratio {ratio:e}, scaled residual ratio {scaled_ratio:e}, voltage correction ratio {correction_ratio:e}; constraints: {}",
                        context()
                    ),
                ));
            }
            if trial.iter().all(|v| v.is_finite()) {
                if let Ok(candidate) = evaluate(&trial) {
                    // Freeze both row scales and bounds during line search;
                    // changing a trial's weights must not manufacture descent.
                    if scaled_merit(&candidate.residuals, &current.bounds, &current.row_scales)
                        <= (1.0 - 1e-4 * alpha) * scaled_ratio
                    {
                        // This is the full evaluation at the next iterate, not
                        // an approximation using the previous Jacobian.
                        accepted = Some((trial, candidate));
                        break;
                    }
                }
            }
            alpha *= 0.5;
        }
        match accepted {
            Some((trial, candidate)) => {
                values = trial;
                current = candidate;
            }
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
