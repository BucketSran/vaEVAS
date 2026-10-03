//! Dense factorization and RHS solves for the bounded voltage-equation slice.
//! Extra rows are retained for the caller's original-equation residual check.
use crate::ir::Error;

pub(crate) struct Factorization {
    lu: Vec<Vec<f64>>,
    scales: Vec<f64>,
    pivots: Vec<usize>,
}

impl Factorization {
    pub(super) fn new(mut a: Vec<Vec<f64>>, columns: usize) -> Result<Self, Error> {
        let _timing = crate::diagnostics::span("factor.dense");

        if a.len() < columns {
            return Err(Error::new(
                "singular_system",
                "fewer voltage constraints than unknown nodes",
            ));
        }
        // Scale rows before partial pivoting so very small, but well-conditioned,
        // coefficients are not mistaken for a zero row merely due to their units.
        let mut scales = Vec::with_capacity(a.len());
        for row in &mut a {
            let scale = row.iter().fold(0.0_f64, |s, x| s.max(x.abs()));
            scales.push(scale);
            if scale > 0.0 {
                for x in row {
                    *x /= scale;
                }
            }
        }
        let threshold = 64.0 * f64::EPSILON * (columns.max(1) as f64);
        let mut pivots = Vec::with_capacity(columns);
        for col in 0..columns {
            let pivot = (col..a.len())
                .max_by(|&i, &j| a[i][col].abs().total_cmp(&a[j][col].abs()))
                .unwrap();
            if !a[pivot][col].is_finite() {
                return Err(Error::new(
                    "nonfinite_arithmetic",
                    "nonfinite elimination pivot",
                ));
            }
            if a[pivot][col].abs() <= threshold {
                return Err(Error::new(
                    "singular_system",
                    format!(
                        "voltage constraints have no numerically unique solution at column {col}"
                    ),
                ));
            }
            a.swap(col, pivot);
            pivots.push(pivot);
            let (leading, remaining) = a.split_at_mut(col + 1);
            let pivot_row = &leading[col];
            for row in remaining {
                let factor = row[col] / pivot_row[col];
                // Keep the multiplier below the diagonal. Subsequent row swaps
                // also move earlier multipliers, as in a rectangular LU factor.
                row[col] = factor;
                for (value, &pivot_value) in row[col + 1..columns]
                    .iter_mut()
                    .zip(&pivot_row[col + 1..columns])
                {
                    *value -= factor * pivot_value;
                }
            }
        }
        Ok(Self {
            lu: a,
            scales,
            pivots,
        })
    }

    pub(super) fn solve(&self, mut b: Vec<f64>) -> Result<Vec<f64>, Error> {
        let columns = self.pivots.len();
        for (rhs, &scale) in b.iter_mut().zip(&self.scales) {
            if scale > 0.0 {
                *rhs /= scale;
            }
        }
        for (col, &pivot) in self.pivots.iter().enumerate() {
            b.swap(col, pivot);
        }
        // Each RHS receives the same ordered subtracts as the original elimination;
        // only their row locations have been permuted ahead of time.
        for col in 0..columns {
            for row in col + 1..b.len() {
                b[row] -= self.lu[row][col] * b[col];
            }
        }
        let mut x = vec![0.0; columns];
        for row in (0..columns).rev() {
            let rest: f64 = (row + 1..columns).map(|k| self.lu[row][k] * x[k]).sum();
            x[row] = (b[row] - rest) / self.lu[row][row];
        }
        if x.iter().chain(b.iter()).any(|v| !v.is_finite()) {
            return Err(Error::new(
                "nonfinite_arithmetic",
                "nonfinite linear solution or elimination RHS",
            ));
        }
        Ok(x)
    }
}
