//! Small dense solve for the bounded voltage-equation slice.
//! Extra rows are retained for the caller's original-equation residual check.
use crate::ir::Error;

pub(crate) fn solve(
    mut a: Vec<Vec<f64>>,
    mut b: Vec<f64>,
    columns: usize,
) -> Result<Vec<f64>, Error> {
    if a.len() < columns {
        return Err(Error::new(
            "singular_system",
            "fewer voltage constraints than unknown nodes",
        ));
    }
    // Scale rows before partial pivoting so very small, but well-conditioned,
    // coefficients are not mistaken for a zero row merely due to their units.
    for (row, rhs) in a.iter_mut().zip(&mut b) {
        let scale = row.iter().fold(0.0_f64, |s, x| s.max(x.abs()));
        if scale > 0.0 {
            for x in row {
                *x /= scale;
            }
            *rhs /= scale;
        }
    }
    let threshold = 64.0 * f64::EPSILON * (columns.max(1) as f64);
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
                format!("voltage constraints have no numerically unique solution at column {col}"),
            ));
        }
        a.swap(col, pivot);
        b.swap(col, pivot);
        for row in col + 1..a.len() {
            let factor = a[row][col] / a[col][col];
            a[row][col] = 0.0;
            for k in col + 1..columns {
                a[row][k] -= factor * a[col][k];
            }
            b[row] -= factor * b[col];
        }
    }
    let mut x = vec![0.0; columns];
    for row in (0..columns).rev() {
        let rest: f64 = (row + 1..columns).map(|k| a[row][k] * x[k]).sum();
        x[row] = (b[row] - rest) / a[row][row];
    }
    if x.iter().chain(b.iter()).any(|v| !v.is_finite()) {
        return Err(Error::new(
            "nonfinite_arithmetic",
            "nonfinite linear solution or elimination RHS",
        ));
    }
    Ok(x)
}
