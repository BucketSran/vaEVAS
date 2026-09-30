//! Rectangular sparse LU with row scaling and full partial pivoting.
//! Dynamic column ordering; only exact zeros are removed, never small entries.
use super::{columns::Columns, Row};
use crate::ir::Error;
use std::collections::{BTreeMap, BTreeSet};

pub(crate) struct Factorization {
    // Compact factors: lower by column for ordered RHS elimination, upper by row.
    lower: Vec<Vec<(usize, f64)>>,
    upper: Vec<Vec<(usize, f64)>>,
    diagonal: Vec<f64>,
    order: Vec<usize>,
    column_order: Option<Vec<usize>>,
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
        // Column counts track the remaining numeric matrix, including new fill.
        // Keep numerical partial pivoting within the chosen column.
        // With at most two entries per row AND column, elimination cannot
        // increase either degree: removing a pivot replaces at most one entry
        // in at most one other row. Natural order already bounds factor fill.
        let reorder =
            rows.iter().any(|row| row.len() > 2) || active.iter().any(|column| column.len() > 2);
        let mut active = Columns::new(active, reorder);
        let mut order: Vec<_> = (0..count).collect();
        let mut position = order.clone();
        let mut column_order = reorder.then(|| Vec::with_capacity(columns));
        let mut lower: Vec<Row> = vec![Vec::new(); columns];
        let mut upper: Vec<Row> = Vec::with_capacity(columns);
        let mut diagonal = Vec::with_capacity(columns);
        let threshold = 64.0 * f64::EPSILON * columns.max(1) as f64;
        for (step, lower_column) in lower.iter_mut().enumerate() {
            let (column, mut candidates) = active.take_next();
            let pivot = candidates
                .iter()
                .copied()
                .max_by(|&a, &b| {
                    rows[a][&column]
                        .abs()
                        .total_cmp(&rows[b][&column].abs())
                        .then_with(|| position[a].cmp(&position[b]))
                })
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
            order.swap(step, old_position);
            position[order[old_position]] = old_position;
            position[pivot] = step;
            if let Some(order) = &mut column_order {
                order.push(column);
            }
            let pivot_value = rows[pivot][&column];
            let pivot_row: Row = std::mem::take(&mut rows[pivot])
                .into_iter()
                .filter(|&(k, _)| k != column)
                .collect();
            // Retire the pivot row. Earlier columns already live in L, so this
            // row contains only later columns, in original-variable numbering.
            for &(k, _) in &pivot_row {
                active.remove(k, pivot);
            }
            candidates.remove(&pivot);
            for id in candidates {
                let multiplier = rows[id].remove(&column).unwrap() / pivot_value;
                if multiplier != 0.0 {
                    lower_column.push((id, multiplier));
                }
                for &(k, value) in &pivot_row {
                    let updated = rows[id].get(&k).copied().unwrap_or(0.0) - multiplier * value;
                    if !updated.is_finite() {
                        return Err(Error::new(
                            "nonfinite_arithmetic",
                            "nonfinite elimination coefficient",
                        ));
                    }
                    if updated == 0.0 {
                        rows[id].remove(&k);
                        active.remove(k, id);
                    } else {
                        rows[id].insert(k, updated);
                        active.insert(k, id);
                    }
                }
            }
            diagonal.push(pivot_value);
            upper.push(pivot_row);
        }
        for column in &mut lower {
            for (id, _) in column {
                *id = position[*id];
            }
        }
        let column_order = column_order.filter(|order| {
            order
                .iter()
                .enumerate()
                .any(|(position, &column)| column != position)
        });
        Ok(Self {
            lower,
            upper,
            diagonal,
            order,
            column_order,
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
            // U keeps original column numbers. Write each solved voltage
            // directly to its node position, without a second vector/scatter.
            let column = self.column_order.as_ref().map_or(row, |order| order[row]);
            x[column] = (b[row] - rest) / self.diagonal[row];
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
