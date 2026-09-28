use super::{dense, sparse, Factorization, Row};

fn rows(matrix: &[Vec<f64>]) -> Vec<Row> {
    matrix
        .iter()
        .map(|row| {
            row.iter()
                .copied()
                .enumerate()
                .filter(|(_, value)| *value != 0.0)
                .collect()
        })
        .collect()
}

#[test]
fn seeded_rectangular_systems_match_constructed_roots_and_dense() {
    // Construct b=A*x from independent roots, not from either solver's output.
    // Row shuffling defeats diagonal preference; distant edges produce fill.
    let mut seed = 290929_u64;
    let mut random = || {
        seed = seed.wrapping_mul(6364136223846793005).wrapping_add(1);
        (seed >> 32) as usize
    };
    for size in [1, 3, 8, 32, 64] {
        for _ in 0..12 {
            let mut matrix = vec![vec![0.0; size]; size];
            for (i, row) in matrix.iter_mut().enumerate() {
                for _ in 0..4 {
                    row[random() % size] += (random() % 17) as f64 / 32.0 - 0.25;
                }
                row[i] += 4.0;
            }
            matrix.push(matrix[size / 2].iter().map(|v| 2.0 * v).collect());
            matrix.push(vec![0.0; size]);
            for i in 0..matrix.len() {
                let scale = [1e-13, 1e6, 1e-3, 1.0][i % 4];
                for value in &mut matrix[i] {
                    *value *= scale;
                }
                let target = random() % matrix.len();
                matrix.swap(i, target);
            }
            let sparse = sparse::Factorization::new(rows(&matrix), size).unwrap();
            let dense = dense::Factorization::new(matrix.clone(), size).unwrap();
            for shift in [-0.5, 2.0, -0.5] {
                let root: Vec<_> = (0..size).map(|i| (i % 7) as f64 / 8.0 + shift).collect();
                let rhs: Vec<_> = matrix
                    .iter()
                    .map(|row| row.iter().zip(&root).map(|(a, x)| a * x).sum())
                    .collect();
                let actual = sparse.solve(rhs.clone()).unwrap();
                let reference = dense.solve(rhs).unwrap();
                for ((a, d), x) in actual.iter().zip(reference).zip(root) {
                    assert!((a - x).abs() < 1e-11, "n={size}: {a} != {x}");
                    assert!((a - d).abs() < 1e-11);
                }
            }
        }
    }
}

#[test]
fn fill_in_and_redundant_pivot_are_retained() {
    let matrix = vec![
        vec![0.0, 0.0, 0.0],
        vec![0.0, 2.0, 1.0],
        vec![1.0, 0.0, 3.0],
        vec![4.0, 1.0, 0.0],
    ];
    let factor = sparse::Factorization::new(rows(&matrix), 3).unwrap();
    assert!(factor.stored_entries() > 6); // elimination creates absent entries
    for (x, expected) in factor
        .solve(vec![0.0, -3.5, 2.5, 2.0])
        .unwrap()
        .iter()
        .zip([1.0, -2.0, 0.5])
    {
        assert!((x - expected).abs() < 1e-12);
    }
    assert_eq!(
        factor
            .solve(vec![f64::INFINITY, -3.5, 2.5, 2.0])
            .unwrap_err()
            .kind,
        "nonfinite_arithmetic"
    );
    let result = factor.solve(vec![0.0, 8.0, 5.5, 1.0]).unwrap();
    for (x, expected) in result.iter().zip([-0.5, 3.0, 2.0]) {
        assert!((x - expected).abs() < 1e-12);
    }
}

#[test]
fn tiny_nonzero_coefficients_are_not_dropped() {
    // The tiny off-diagonal contributes one volt; an absolute drop tolerance
    // would silently change the answer even though the diagonal stays sound.
    let factor = sparse::Factorization::new(rows(&[vec![1.0, 1e-20], vec![0.0, 1.0]]), 2).unwrap();
    assert_eq!(factor.solve(vec![3.0, 1e20]).unwrap(), vec![2.0, 1e20]);
}

#[test]
fn singular_zero_unknown_and_nonfinite_rhs_contracts() {
    for matrix in [
        vec![vec![1.0, 0.0]],
        vec![vec![1.0, 2.0], vec![2.0, 4.0]],
        vec![vec![1.0, 1.0], vec![1.0, 1.0 + 1e-15]],
    ] {
        assert!(matches!(sparse::Factorization::new(rows(&matrix), 2),
            Err(error) if error.kind == "singular_system"));
    }
    let empty = sparse::Factorization::new(vec![Row::new(); 2], 0).unwrap();
    assert!(empty.solve(vec![1.0, -1.0]).unwrap().is_empty());
    assert_eq!(
        empty.solve(vec![0.0, f64::NAN]).unwrap_err().kind,
        "nonfinite_arithmetic"
    );
    let factor = sparse::Factorization::new(rows(&[vec![1e-300], vec![1e-300]]), 1).unwrap();
    assert_eq!(
        factor.solve(vec![1e-300, 1e300]).unwrap_err().kind,
        "nonfinite_arithmetic"
    );
    assert_eq!(factor.solve(vec![1e-300, 1e-300]).unwrap(), vec![1.0]);
    let redundant = sparse::Factorization::new(rows(&[vec![1.0], vec![1.0]]), 1).unwrap();
    assert_eq!(
        redundant.solve(vec![1e308, -1e308]).unwrap_err().kind,
        "nonfinite_arithmetic"
    );
}

#[test]
fn large_chain_storage_is_linear_and_dispatch_keeps_dense_cases() {
    let size = 10_000;
    let matrix: Vec<Row> = (0..size)
        .map(|i| {
            let mut row = Row::from([(i, 1.0)]);
            if i > 0 {
                row.insert(0, (i - 1, -0.25));
            }
            row
        })
        .collect();
    let Factorization::Sparse(factor) = Factorization::new(matrix, size).unwrap() else {
        panic!("large sparse matrix took dense path");
    };
    assert_eq!(factor.stored_entries(), 2 * size - 1);
    let result = factor.solve(vec![0.75; size]).unwrap();
    let mut previous = 0.0;
    for value in result {
        let expected = 0.75 + 0.25 * previous;
        assert!((value - expected).abs() < 1e-13);
        previous = expected;
    }
    assert!(matches!(
        Factorization::new(vec![Row::from([(0, 1.0)])], 1).unwrap(),
        Factorization::Dense(_)
    ));
    let matrix: Vec<Row> = (0..64)
        .map(|i| {
            (0..64)
                .map(|j| (j, if i == j { 2.0 } else { 0.01 }))
                .collect()
        })
        .collect();
    assert!(matches!(
        Factorization::new(matrix, 64).unwrap(),
        Factorization::Dense(_)
    ));
}

#[test]
fn column_ordering_avoids_star_fill_and_restores_original_voltages() {
    let size = 128;
    // Change both row order and the center's original column number. Distinct
    // roots catch a missing inverse column permutation that uniform roots hide.
    for center in [0, 37, size - 1] {
        let mut matrix: Vec<Row> = (0..size)
            .map(|i| {
                if i == center {
                    (0..size)
                        .map(|j| {
                            (
                                j,
                                if j == i {
                                    1.0
                                } else {
                                    -0.25 / (size - 1) as f64
                                },
                            )
                        })
                        .collect()
                } else {
                    let mut row = vec![(i, 1.0), (center, -0.25)];
                    row.sort_unstable_by_key(|&(j, _)| j);
                    row
                }
            })
            .collect();
        // A redundant row must still participate in pivoting and RHS checks.
        matrix.push(matrix[(center + 1) % size].clone());
        matrix.reverse();
        for (i, row) in matrix.iter_mut().enumerate() {
            for (_, value) in row {
                *value *= [1e-13, 1e6, 1.0][i % 3];
            }
        }
        let factor = sparse::Factorization::new(matrix.clone(), size).unwrap();
        assert!(
            factor.stored_entries() <= 3 * size,
            "star generated dense fill"
        );
        for shift in [-0.75, 1.25, -0.75] {
            let expected: Vec<_> = (0..size).map(|i| (i % 17) as f64 / 32.0 + shift).collect();
            let rhs: Vec<_> = matrix
                .iter()
                .map(|row| row.iter().map(|&(j, a)| a * expected[j]).sum())
                .collect();
            let solved = factor.solve(rhs).unwrap();
            for (actual, expected) in solved.iter().zip(expected) {
                assert!((actual - expected).abs() < 1e-11);
            }
        }
    }
}

#[test]
fn ordering_handles_both_fill_creation_and_exact_cancellation() {
    // This creates a new entry and cancels an existing one during elimination;
    // stale column counts or row memberships can break later pivot selection.
    let matrix = vec![
        vec![1.0, 1.0, 0.0, 0.0],
        vec![1.0, 1.0, 1.0, 0.0],
        vec![0.0, 1.0, 1.0, 1.0],
        vec![0.0, 0.0, 1.0, 2.0],
    ];
    let factor = sparse::Factorization::new(rows(&matrix), 4).unwrap();
    // A*[1,-2,3,-4] by hand.
    let solved = factor.solve(vec![-1.0, 2.0, -3.0, -5.0]).unwrap();
    for (actual, expected) in solved.iter().zip([1.0, -2.0, 3.0, -4.0]) {
        assert!((actual - expected).abs() < 1e-12);
    }
}
