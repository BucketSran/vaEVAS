//! Certified interval propagation for small linear state-space systems.
//!
//! This module is intentionally independent from the transient scheduler.  It
//! encloses `exp(A * t) * x0` with interval arithmetic, using scaling and
//! squaring plus a Taylor series whose matrix tail is bounded in infinity norm.
use crate::interval::Interval;
use crate::ir::Error;

const MAX_DIMENSION: usize = 32;
const MAX_SCALING: usize = 48;
const TAYLOR_TERMS: usize = 40;
const TAYLOR_TARGET_NORM: f64 = 1.0 / 16.0;

type Matrix = Vec<Vec<Interval>>;

pub(crate) fn propagate(
    matrix: &[Vec<Interval>],
    initial: &[Interval],
    elapsed: Interval,
) -> Result<Vec<Interval>, Error> {
    if matrix.len() != initial.len() {
        return Err(Error::new(
            "invalid_state_space",
            "state-space matrix dimension must match the initial state",
        ));
    }
    let transition = exponential(matrix, elapsed)?;
    multiply_matrix_vector(&transition, initial)
}

pub(crate) fn exponential(matrix: &[Vec<Interval>], elapsed: Interval) -> Result<Matrix, Error> {
    validate_matrix(matrix)?;
    if !valid_interval(elapsed) || elapsed.lo < 0.0 {
        return Err(Error::new(
            "invalid_state_space",
            "state-space elapsed time must be a valid finite nonnegative interval",
        ));
    }
    if elapsed.zero() {
        return Ok(identity(matrix.len()));
    }
    let scaled_time = scale_matrix(matrix, elapsed)?;
    exponential_from_scaled_generator(&scaled_time)
}

fn validate_matrix(matrix: &[Vec<Interval>]) -> Result<(), Error> {
    let dimension = matrix.len();
    if dimension > MAX_DIMENSION {
        return Err(Error::new(
            "state_space_limit",
            format!(
                "state-space dimension {dimension} exceeds the supported limit {MAX_DIMENSION}"
            ),
        ));
    }
    for row in matrix {
        if row.len() != dimension {
            return Err(Error::new(
                "invalid_state_space",
                "state-space matrix must be square",
            ));
        }
        if row.iter().any(|value| !valid_interval(*value)) {
            return Err(Error::new(
                "invalid_state_space",
                "state-space matrix entries must be valid finite intervals",
            ));
        }
    }
    Ok(())
}

fn exponential_from_scaled_generator(generator: &Matrix) -> Result<Matrix, Error> {
    let dimension = generator.len();
    let norm = infinity_norm_bound(generator);
    let mut scaling = 0;
    let mut scaled = generator.clone();
    while scaled_norm_upper(norm, scaling)? > TAYLOR_TARGET_NORM {
        scaling += 1;
        if scaling > MAX_SCALING {
            return Err(Error::new(
                "state_space_limit",
                "state-space generator norm exceeds the certified scaling budget",
            ));
        }
    }
    if scaling > 0 {
        let factor = Interval::ONE / Interval::point(scaling_denominator(scaling));
        for row in &mut scaled {
            for value in row {
                *value = *value * factor;
            }
        }
    }

    let mut result = identity(dimension);
    let mut term = identity(dimension);
    for order in 1..=TAYLOR_TERMS {
        term = multiply_matrices(&term, &scaled)?;
        for row in &mut term {
            for value in row {
                *value = *value / Interval::point(order as f64);
            }
        }
        add_assign_matrix(&mut result, &term)?;
    }
    let tail = taylor_tail_bound(infinity_norm_bound(&scaled), TAYLOR_TERMS + 1)?;
    widen_matrix(&mut result, tail)?;

    for _ in 0..scaling {
        result = multiply_matrices(&result, &result)?;
    }
    Ok(result)
}

fn scale_matrix(matrix: &[Vec<Interval>], elapsed: Interval) -> Result<Matrix, Error> {
    let mut out = matrix.to_vec();
    for row in &mut out {
        for value in row {
            *value = *value * elapsed;
            if !value.finite() {
                return Err(Error::new(
                    "nonfinite_arithmetic",
                    "state-space time scaling produced a nonfinite interval",
                ));
            }
        }
    }
    Ok(out)
}

fn identity(dimension: usize) -> Matrix {
    (0..dimension)
        .map(|row| {
            (0..dimension)
                .map(|column| {
                    if row == column {
                        Interval::ONE
                    } else {
                        Interval::ZERO
                    }
                })
                .collect()
        })
        .collect()
}

fn infinity_norm_bound(matrix: &Matrix) -> Interval {
    matrix.iter().fold(Interval::ZERO, |norm, row| {
        norm.hull(row.iter().fold(Interval::ZERO, |sum, value| {
            sum + Interval::point(value.magnitude())
        }))
    })
}

fn multiply_matrices(left: &Matrix, right: &Matrix) -> Result<Matrix, Error> {
    let n = left.len();
    let mut out = vec![vec![Interval::ZERO; n]; n];
    for i in 0..n {
        for k in 0..n {
            let a = left[i][k];
            if a.zero() {
                continue;
            }
            for j in 0..n {
                out[i][j] = out[i][j] + a * right[k][j];
            }
        }
    }
    ensure_finite_matrix(
        out,
        "state-space matrix multiplication produced a nonfinite interval",
    )
}

fn multiply_matrix_vector(matrix: &Matrix, vector: &[Interval]) -> Result<Vec<Interval>, Error> {
    if vector.iter().any(|value| !valid_interval(*value)) {
        return Err(Error::new(
            "invalid_state_space",
            "state-space initial values must be valid finite intervals",
        ));
    }
    let mut out = vec![Interval::ZERO; matrix.len()];
    for (i, row) in matrix.iter().enumerate() {
        for (a, x) in row.iter().zip(vector) {
            out[i] = out[i] + *a * *x;
        }
    }
    if out.iter().any(|value| !value.finite()) {
        return Err(Error::new(
            "nonfinite_arithmetic",
            "state-space propagation produced a nonfinite interval",
        ));
    }
    Ok(out)
}

fn add_assign_matrix(accumulator: &mut Matrix, term: &Matrix) -> Result<(), Error> {
    for (out_row, term_row) in accumulator.iter_mut().zip(term) {
        for (out, value) in out_row.iter_mut().zip(term_row) {
            *out = *out + *value;
            if !out.finite() {
                return Err(Error::new(
                    "nonfinite_arithmetic",
                    "state-space Taylor sum produced a nonfinite interval",
                ));
            }
        }
    }
    Ok(())
}

fn widen_matrix(matrix: &mut Matrix, radius: f64) -> Result<(), Error> {
    if !radius.is_finite() {
        return Err(Error::new(
            "state_space_limit",
            "state-space Taylor remainder exceeded the finite certification budget",
        ));
    }
    let bound = Interval {
        lo: -radius,
        hi: radius,
    };
    for row in matrix {
        for value in row {
            *value = *value + bound;
            if !value.finite() {
                return Err(Error::new(
                    "nonfinite_arithmetic",
                    "state-space Taylor remainder produced a nonfinite interval",
                ));
            }
        }
    }
    Ok(())
}

fn ensure_finite_matrix(matrix: Matrix, message: &'static str) -> Result<Matrix, Error> {
    if matrix
        .iter()
        .flat_map(|row| row.iter())
        .any(|value| !value.finite())
    {
        Err(Error::new("nonfinite_arithmetic", message))
    } else {
        Ok(matrix)
    }
}

fn taylor_tail_bound(norm: Interval, first_omitted: usize) -> Result<f64, Error> {
    if !valid_interval(norm) {
        return Err(Error::new(
            "state_space_limit",
            "state-space Taylor norm is invalid",
        ));
    }
    if norm.hi == 0.0 {
        return Ok(0.0);
    }
    let ratio = norm / Interval::point(first_omitted as f64 + 1.0);
    if !valid_interval(ratio) || ratio.hi >= 1.0 {
        return Err(Error::new(
            "state_space_limit",
            "state-space Taylor tail cannot be certified with the configured order",
        ));
    }
    let mut term = Interval::ONE;
    for divisor in 1..=first_omitted {
        term = (term * norm) / Interval::point(divisor as f64);
        if !valid_interval(term) {
            return Err(Error::new(
                "state_space_limit",
                "state-space Taylor tail exceeded the finite certification budget",
            ));
        }
    }
    let denominator = Interval::ONE - ratio;
    if denominator.lo <= 0.0 {
        return Err(Error::new(
            "state_space_limit",
            "state-space Taylor tail has nonpositive geometric denominator",
        ));
    }
    let tail = term / denominator;
    if !valid_interval(tail) {
        return Err(Error::new(
            "state_space_limit",
            "state-space Taylor tail exceeded the finite certification budget",
        ));
    }
    Ok(tail.hi.next_up())
}

fn scaled_norm_upper(norm: Interval, scaling: usize) -> Result<f64, Error> {
    let scaled = norm / Interval::point(scaling_denominator(scaling));
    if !valid_interval(scaled) {
        return Err(Error::new(
            "state_space_limit",
            "state-space generator norm exceeded the finite scaling budget",
        ));
    }
    Ok(scaled.hi)
}

fn scaling_denominator(scaling: usize) -> f64 {
    2.0_f64.powi(scaling as i32)
}

fn valid_interval(value: Interval) -> bool {
    value.finite() && value.lo <= value.hi
}

#[cfg(test)]
mod tests {
    use super::*;

    fn point_matrix(rows: &[[f64; 2]; 2]) -> Matrix {
        rows.iter()
            .map(|row| row.iter().map(|value| Interval::point(*value)).collect())
            .collect()
    }

    fn contains(value: Interval, expected: f64) {
        assert!(
            value.lo <= expected && expected <= value.hi,
            "{value:?} does not contain {expected}"
        );
    }

    #[test]
    fn scalar_decay_matches_independent_exp() {
        let matrix = vec![vec![Interval::point(-2.0)]];
        let out = propagate(&matrix, &[Interval::point(3.0)], Interval::point(0.5)).unwrap();
        contains(out[0], 3.0 * (-1.0_f64).exp());
        assert!(out[0].hi - out[0].lo < 1e-10);
    }

    #[test]
    fn scalar_growth_uses_enclosed_reciprocal_taylor_factors() {
        let matrix = vec![vec![Interval::ONE]];
        let elapsed = Interval::ONE / Interval::point(3.0);
        let transition = exponential(&matrix, elapsed).unwrap();
        contains(transition[0][0], (1.0_f64 / 3.0).exp());
        assert!(transition[0][0].hi - transition[0][0].lo < 1e-10);
    }

    #[test]
    fn jordan_block_keeps_polynomial_factor() {
        let matrix = point_matrix(&[[2.0, 1.0], [0.0, 2.0]]);
        let transition = exponential(&matrix, Interval::point(0.25)).unwrap();
        let e = 0.5_f64.exp();
        contains(transition[0][0], e);
        contains(transition[1][1], e);
        contains(transition[0][1], 0.25 * e);
        contains(transition[1][0], 0.0);
    }

    #[test]
    fn rotation_encloses_sine_and_cosine() {
        let matrix = point_matrix(&[[0.0, -3.0], [3.0, 0.0]]);
        let transition = exponential(&matrix, Interval::point(0.2)).unwrap();
        contains(transition[0][0], 0.6_f64.cos());
        contains(transition[0][1], -0.6_f64.sin());
        contains(transition[1][0], 0.6_f64.sin());
        contains(transition[1][1], 0.6_f64.cos());
    }

    #[test]
    fn zero_time_returns_initial_interval() {
        let matrix = point_matrix(&[[4.0, -7.0], [2.0, 9.0]]);
        let initial = [Interval { lo: 1.0, hi: 1.25 }, Interval::point(-2.0)];
        let out = propagate(&matrix, &initial, Interval::ZERO).unwrap();
        assert_eq!(out, initial);
    }

    #[test]
    fn time_and_coefficient_uncertainty_widen_but_keep_nominal_solution() {
        let matrix = vec![vec![Interval {
            lo: -1.01,
            hi: -0.99,
        }]];
        let out = propagate(
            &matrix,
            &[Interval::point(2.0)],
            Interval { lo: 0.49, hi: 0.51 },
        )
        .unwrap();
        contains(out[0], 2.0 * (-0.5_f64).exp());
        assert!(out[0].lo < out[0].hi);
    }

    #[test]
    fn coefficient_and_time_intervals_enclose_all_scalar_corners() {
        let matrix = vec![vec![Interval { lo: -1.1, hi: -0.9 }]];
        let elapsed = Interval { lo: 0.4, hi: 0.6 };
        let out = propagate(&matrix, &[Interval::point(2.0)], elapsed).unwrap();
        for coefficient in [-1.1_f64, -0.9] {
            for time in [0.4_f64, 0.6] {
                contains(out[0], 2.0 * (coefficient * time).exp());
            }
        }
    }

    #[test]
    fn rejects_invalid_dimensions_and_nonfinite_inputs() {
        let matrix = vec![vec![Interval::ONE, Interval::ZERO]];
        assert_eq!(
            exponential(&matrix, Interval::point(1.0)).unwrap_err().kind,
            "invalid_state_space"
        );
        let matrix = vec![vec![Interval::ONE]];
        assert_eq!(
            propagate(&matrix, &[], Interval::point(1.0))
                .unwrap_err()
                .kind,
            "invalid_state_space"
        );
        assert_eq!(
            exponential(&matrix, Interval { lo: -0.1, hi: 0.2 })
                .unwrap_err()
                .kind,
            "invalid_state_space"
        );
        let inverted = Interval { lo: 1.0, hi: 0.0 };
        assert_eq!(
            exponential(&[vec![inverted]], Interval::point(1.0))
                .unwrap_err()
                .kind,
            "invalid_state_space"
        );
        assert_eq!(
            exponential(&[vec![Interval::ONE]], inverted)
                .unwrap_err()
                .kind,
            "invalid_state_space"
        );
        assert_eq!(
            propagate(&[vec![Interval::ONE]], &[inverted], Interval::point(1.0))
                .unwrap_err()
                .kind,
            "invalid_state_space"
        );
    }

    #[test]
    fn rejects_overflow_and_resource_exhaustion() {
        let matrix = vec![vec![Interval::point(f64::MAX)]];
        assert_eq!(
            exponential(&matrix, Interval::point(2.0)).unwrap_err().kind,
            "nonfinite_arithmetic"
        );
        let huge = vec![vec![Interval::point(1.0e20)]];
        assert_eq!(
            exponential(&huge, Interval::point(1.0)).unwrap_err().kind,
            "state_space_limit"
        );
        let too_large = vec![vec![Interval::ZERO; MAX_DIMENSION + 1]; MAX_DIMENSION + 1];
        assert_eq!(
            exponential(&too_large, Interval::point(0.0))
                .unwrap_err()
                .kind,
            "state_space_limit"
        );
    }
}
