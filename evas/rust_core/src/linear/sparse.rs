//! Rectangular sparse LU with row scaling and full partial pivoting.
//! Natural column order; only exact zeros are removed, never small entries.
use super::Row;
use crate::ir::Error;
use std::collections::{BTreeMap, BTreeSet};

pub(crate) struct Factorization {
    // Compact factors: lower by column for ordered RHS elimination, upper by row.
    lower: Vec<Vec<(usize, f64)>>,
    upper: Vec<Vec<(usize, f64)>>,
    diagonal: Vec<f64>,
    order: Vec<usize>,
    scales: Vec<f64>,
}

impl Factorization {
    pub(super) fn new(rows: Vec<Row>, columns: usize) -> Result<Self, Error> {
        let count = rows.len();
        if count < columns {
            return Err(Error::new(
                "singular_system",
                "fewer voltage constraints than unknown nodes",
            ));
        }
        let mut rows: Vec<BTreeMap<usize, f64>> = rows
            .into_iter()
            .map(|row| row.into_iter().collect())
            .collect();
        let mut active = vec![BTreeSet::new(); columns];
        let mut scales = Vec::with_capacity(count);
        for (id, row) in rows.iter_mut().enumerate() {
            let scale = row.values().fold(0.0_f64, |s, v| s.max(v.abs()));
            scales.push(scale);
            if scale > 0.0 {
                for value in row.values_mut() {
                    *value /= scale;
                }
            }
            row.retain(|_, value| *value != 0.0);
            for &column in row.keys() {
                active[column].insert(id);
            }
        }
        // Stable row IDs keep column memberships valid across pivot swaps.
        let mut order: Vec<_> = (0..count).collect();
        let mut position = order.clone();
        let threshold = 64.0 * f64::EPSILON * columns.max(1) as f64;
        for column in 0..columns {
            let pivot = active[column].iter().copied().max_by(|&a, &b| {
                rows[a][&column]
                    .abs()
                    .total_cmp(&rows[b][&column].abs())
                    .then_with(|| position[a].cmp(&position[b]))
            });
            let pivot = pivot
                .filter(|&id| rows[id][&column].abs() > threshold)
                .ok_or_else(|| {
                    Error::new(
                        "singular_system",
                        format!(
                    "voltage constraints have no numerically unique solution at column {column}"
                ),
                    )
                })?;
            let old_position = position[pivot];
            order.swap(column, old_position);
            position[order[old_position]] = old_position;
            position[pivot] = column;
            let diagonal = rows[pivot][&column];
            let upper: Vec<_> = rows[pivot]
                .range(column + 1..)
                .map(|(&k, &v)| (k, v))
                .collect();
            // Retire the pivot from all future column candidate lists.
            active[column].remove(&pivot);
            for &(k, _) in &upper {
                active[k].remove(&pivot);
            }
            for id in std::mem::take(&mut active[column]) {
                let multiplier = rows[id][&column] / diagonal;
                rows[id].insert(column, multiplier);
                for &(k, value) in &upper {
                    let updated = rows[id].get(&k).copied().unwrap_or(0.0) - multiplier * value;
                    if !updated.is_finite() {
                        return Err(Error::new(
                            "nonfinite_arithmetic",
                            "nonfinite elimination coefficient",
                        ));
                    }
                    if updated == 0.0 {
                        rows[id].remove(&k);
                        active[k].remove(&id);
                    } else {
                        rows[id].insert(k, updated);
                        active[k].insert(id);
                    }
                }
            }
        }
        let mut lower = vec![Vec::new(); columns];
        let mut upper = vec![Vec::new(); columns];
        let mut diagonal = vec![0.0; columns];
        for (position, &id) in order.iter().enumerate() {
            for (&column, &value) in &rows[id] {
                if column < position {
                    if value != 0.0 {
                        lower[column].push((position, value));
                    }
                } else if column == position {
                    diagonal[position] = value;
                } else {
                    upper[position].push((column, value));
                }
            }
        }
        Ok(Self {
            lower,
            upper,
            diagonal,
            order,
            scales,
        })
    }

    pub(super) fn solve(&self, rhs: Vec<f64>) -> Result<Vec<f64>, Error> {
        let mut b: Vec<_> = self
            .order
            .iter()
            .map(|&id| {
                if self.scales[id] > 0.0 {
                    rhs[id] / self.scales[id]
                } else {
                    rhs[id]
                }
            })
            .collect();
        // Includes redundant rows; skipping structural zeros must not hide an
        // overflowing scaled RHS or a nonfinite eliminated redundant equation.
        if b.iter().any(|v| !v.is_finite()) {
            return Err(Error::new(
                "nonfinite_arithmetic",
                "nonfinite linear solution or elimination RHS",
            ));
        }
        for (column, entries) in self.lower.iter().enumerate() {
            for &(row, value) in entries {
                b[row] -= value * b[column];
            }
        }
        let mut x = vec![0.0; self.diagonal.len()];
        for row in (0..x.len()).rev() {
            let rest: f64 = self.upper[row].iter().map(|&(k, v)| v * x[k]).sum();
            x[row] = (b[row] - rest) / self.diagonal[row];
        }
        if x.iter().chain(&b).any(|v| !v.is_finite()) {
            return Err(Error::new(
                "nonfinite_arithmetic",
                "nonfinite linear solution or elimination RHS",
            ));
        }
        Ok(x)
    }

    #[cfg(test)]
    pub(super) fn stored_entries(&self) -> usize {
        self.diagonal.len()
            + self.lower.iter().map(Vec::len).sum::<usize>()
            + self.upper.iter().map(Vec::len).sum::<usize>()
    }
}
