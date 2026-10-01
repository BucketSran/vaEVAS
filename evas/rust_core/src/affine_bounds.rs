//! Outward affine arithmetic shared by event timing and same-time certification.
use crate::event_accuracy::unresolved;
use crate::interval::Interval as I;
use crate::ir::{Error, Expression, Program};
use std::collections::BTreeMap;

/// Original affine circuit projected onto driven inputs, event states,
/// operator outputs and one constant. Shared by affine/dynamic event timing.
pub(crate) fn node_map(program: &Program, driven: &[String]) -> Result<Vec<Vec<I>>, Error> {
    let count = program.nodes.len();
    let parameters = program.states.len() + program.operators.len();
    let variables = count + parameters;
    let driven: Vec<_> = driven
        .iter()
        .map(|name| {
            program
                .nodes
                .iter()
                .position(|n| n == name)
                .ok_or_else(|| Error::new("invalid_inputs", "unknown driven node"))
        })
        .collect::<Result<_, _>>()?;
    let unknown: Vec<_> = (1..count).filter(|n| !driven.contains(n)).collect();
    let n = unknown.len();
    let width = driven.len() + parameters + 1;
    let mut groups = BTreeMap::new();
    for c in &program.contributions {
        let rhs = affine(&c.rhs, program)?;
        let row = groups.entry(&c.branch).or_insert_with(|| {
            let mut row = vec![I::ZERO; variables + 1];
            row[c.positive] = row[c.positive] + I::ONE;
            row[c.negative] = row[c.negative] - I::ONE;
            row
        });
        for (v, term) in row.iter_mut().zip(rhs) {
            *v = *v - term;
        }
    }
    let rows = groups
        .values()
        .map(|row: &Vec<I>| {
            unknown
                .iter()
                .map(|&k| row[k])
                .chain(driven.iter().map(|&k| -row[k]))
                .chain((count..variables).map(|k| -row[k]))
                .chain([-row[variables]])
                .collect()
        })
        .collect();
    let rows = eliminate(rows, n, width)?;
    let mut values = vec![vec![I::ZERO; width]; variables];
    for (k, &node) in driven.iter().enumerate() {
        values[node][k] = I::ONE;
    }
    for k in 0..parameters {
        values[count + k][driven.len() + k] = I::ONE;
    }
    for r in (0..n).rev() {
        for k in 0..width {
            let rest = (r + 1..n).fold(I::ZERO, |sum, c| sum + rows[r][c] * values[unknown[c]][k]);
            values[unknown[r]][k] = rows[r][n + k] - rest;
        }
    }
    if values.iter().flatten().any(|v| !v.finite()) {
        return Err(unresolved("nonfinite affine network projection"));
    }
    Ok(values)
}

// Last entry is the constant. Recheck affinity before dropping product terms,
// even though EventModel also checks the original expression's structure.
pub(crate) fn affine(expr: &Expression, program: &Program) -> Result<Vec<I>, Error> {
    let n = program.nodes.len() + program.states.len() + program.operators.len();
    let mut result = vec![I::ZERO; n + 1];
    match expr {
        Expression::Affine { constant, terms } => {
            result[n] = I::point(*constant);
            for term in terms {
                result[term.node] = I::point(term.coefficient);
            }
        }
        Expression::State { state } => result[program.nodes.len() + state] = I::ONE,
        Expression::Operator { operator } => {
            result[program.nodes.len() + program.states.len() + operator] = I::ONE;
        }
        Expression::Add { left, right } => {
            result = affine(left, program)?
                .iter()
                .zip(affine(right, program)?)
                .map(|(&a, b)| a + b)
                .collect();
        }
        Expression::Multiply { left, right } => {
            let a = affine(left, program)?;
            let b = affine(right, program)?;
            if a[..n].iter().any(|x| !x.zero()) && b[..n].iter().any(|x| !x.zero()) {
                return Err(unresolved("cannot certify jointly affine event expression"));
            }
            for k in 0..n {
                result[k] = a[k] * b[n] + b[k] * a[n];
            }
            result[n] = a[n] * b[n];
        }
        Expression::Power { .. } => {
            return Err(unresolved("cannot bound a polynomial event expression"));
        }
        Expression::Select { .. } => {
            return Err(unresolved(
                "cannot bound an ordinary analog conditional in an event expression",
            ));
        }
    }
    Ok(result)
}

pub(crate) fn eliminate(
    mut rows: Vec<Vec<I>>,
    n: usize,
    width: usize,
) -> Result<Vec<Vec<I>>, Error> {
    if rows.len() < n {
        return Err(unresolved("cannot bound an underdetermined event network"));
    }
    // Interval elimination is deliberately conservative. A pivot containing
    // zero cannot prove a unique solution; never borrow a residual tolerance.
    for col in 0..n {
        let pivot = (col..rows.len())
            .filter(|&k| matches!(rows[k][col].sign(), Some(-1 | 1)))
            .max_by(|&a, &b| {
                rows[a][col]
                    .magnitude()
                    .total_cmp(&rows[b][col].magnitude())
            })
            .ok_or_else(|| unresolved("cannot certify event network pivot away from zero"))?;
        rows.swap(col, pivot);
        let divisor = rows[col][col];
        let (leading, remaining) = rows.split_at_mut(col + 1);
        let pivot_row = &mut leading[col];
        for value in &mut pivot_row[col + 1..n + width] {
            *value = *value / divisor;
        }
        pivot_row[col] = I::ONE;
        for row in remaining {
            let factor = row[col];
            for (value, &pivot_value) in row[col + 1..n + width]
                .iter_mut()
                .zip(&pivot_row[col + 1..n + width])
            {
                *value = *value - factor * pivot_value;
            }
            row[col] = I::ZERO;
        }
    }
    // A redundant constraint must be identically satisfied over all inputs.
    // Otherwise a residual-tolerated static solution has no certified affine
    // trajectory; accepting it would attach a time guarantee to no exact root.
    if rows
        .iter()
        .skip(n)
        .any(|row| row[n..].iter().any(|x| !x.zero()))
    {
        return Err(unresolved(
            "cannot certify redundant event constraints as identities",
        ));
    }
    Ok(rows)
}
