//! Select a dense or sparse rectangular LU without changing voltage acceptance.
use crate::ir::Error;
mod columns;
mod dense;
mod refinement;
mod sparse;
pub(crate) use refinement::residual as refinement_residual;

/// Internal rows have sorted unique in-range columns and finite nonzero values.
pub(crate) type Row = Vec<(usize, f64)>;

pub(crate) enum Factorization {
    Dense(dense::Factorization),
    Sparse(sparse::Factorization),
}

impl Factorization {
    pub(crate) fn new(rows: Vec<Row>, columns: usize) -> Result<Self, Error> {
        let _timing = crate::diagnostics::span("factor.total");
        crate::diagnostics::counter("factorizations", 1);
        crate::diagnostics::counter("matrix_rows", rows.len());
        crate::diagnostics::counter("matrix_columns", columns);
        // A conservative crossover, not a guarantee for every sparsity pattern.
        // Keep the small-system path and avoid tree overhead on dense matrices.
        let nonzeros: usize = rows.iter().map(Row::len).sum();
        crate::diagnostics::counter("matrix_input_nnz", nonzeros);
        if columns >= 32 && nonzeros as f64 <= 0.1 * rows.len() as f64 * columns as f64 {
            sparse::Factorization::new(rows, columns).map(Self::Sparse)
        } else {
            let matrix = rows
                .into_iter()
                .map(|row| {
                    let mut values = vec![0.0; columns];
                    for (column, value) in row {
                        values[column] = value;
                    }
                    values
                })
                .collect();
            dense::Factorization::new(matrix, columns).map(Self::Dense)
        }
    }

    pub(crate) fn solve(&self, rhs: Vec<f64>) -> Result<Vec<f64>, Error> {
        let _timing = crate::diagnostics::span("factor.back_substitution");
        crate::diagnostics::counter("linear_rhs_solves", 1);
        match self {
            Self::Dense(factor) => factor.solve(rhs),
            Self::Sparse(factor) => factor.solve(rhs),
        }
    }
}

pub(crate) fn solve(a: Vec<Row>, b: Vec<f64>, columns: usize) -> Result<Vec<f64>, Error> {
    Factorization::new(a, columns)?.solve(b)
}

#[cfg(test)]
mod tests {
    use super::dense::Factorization;

    #[test]
    fn multiple_pivots_and_row_scales_preserve_two_known_solutions() {
        for scales in [[1.0; 3], [1e-13, 1e6, 1e-3]] {
            let matrix = [[0.0, 2.0, 1.0], [1.0, 0.0, 3.0], [4.0, 1.0, 0.0]];
            let factor = Factorization::new(
                matrix
                    .iter()
                    .zip(scales)
                    .map(|(row, s)| row.iter().map(|v| v * s).collect())
                    .collect(),
                3,
            )
            .unwrap();
            for (rhs, expected) in [
                ([-3.5, 2.5, 2.0], [1.0, -2.0, 0.5]),
                ([8.0, 5.5, 1.0], [-0.5, 3.0, 2.0]),
                ([-3.5, 2.5, 2.0], [1.0, -2.0, 0.5]),
            ] {
                let actual = factor
                    .solve(rhs.iter().zip(scales).map(|(v, s)| v * s).collect())
                    .unwrap();
                for (a, b) in actual.iter().zip(expected) {
                    assert!((a - b).abs() < 1e-12);
                }
            }
        }
    }

    #[test]
    fn redundant_rows_can_supply_pivots_and_survive_failed_rhs() {
        let factor =
            Factorization::new(vec![vec![0.0, 0.0], vec![0.0, 2.0], vec![4.0, 1.0]], 2).unwrap();
        assert_eq!(factor.solve(vec![0.0, -4.0, 2.0]).unwrap(), vec![1.0, -2.0]);
        assert_eq!(
            factor
                .solve(vec![f64::INFINITY, -4.0, 2.0])
                .unwrap_err()
                .kind,
            "nonfinite_arithmetic"
        );
        assert_eq!(factor.solve(vec![0.0, 6.0, 1.0]).unwrap(), vec![-0.5, 3.0]);
    }

    #[test]
    fn zero_unknowns_still_check_all_rhs_values() {
        let factor = Factorization::new(vec![vec![], vec![]], 0).unwrap();
        assert!(factor.solve(vec![1.0, -1.0]).unwrap().is_empty());
        assert_eq!(
            factor.solve(vec![0.0, f64::NAN]).unwrap_err().kind,
            "nonfinite_arithmetic"
        );
    }

    #[test]
    fn missing_constraints_and_numerical_rank_failure_still_reject() {
        for matrix in [vec![vec![1.0, 0.0]], vec![vec![1.0, 2.0], vec![2.0, 4.0]]] {
            assert!(
                matches!(Factorization::new(matrix, 2), Err(error) if error.kind == "singular_system")
            );
        }
    }
}

#[cfg(test)]
mod sparse_tests;

#[cfg(test)]
mod properties;
