//! Enclose affine guards from the original binary64 IR, including assembly and
//! linear solve roundoff. Prepared once for a state-independent event schedule.
use crate::interval::{equal_products, Interval as I};
use crate::ir::{Error, Expression, Program};
use std::collections::BTreeMap;

pub(crate) fn unresolved(message: &str) -> Error {
    Error::new("event_resolution", message)
}

// Last entry is the constant. EventModel has already validated joint affinity.
fn affine(expr: &Expression, program: &Program) -> Vec<I> {
    let n = program.nodes.len() + program.states.len();
    let mut result = vec![I::ZERO; n + 1];
    match expr {
        Expression::Affine { constant, terms } => {
            result[n] = I::point(*constant);
            for term in terms {
                result[term.node] = I::point(term.coefficient);
            }
        }
        Expression::State { state } => result[program.nodes.len() + state] = I::ONE,
        Expression::Add { left, right } => {
            result = affine(left, program)
                .iter()
                .zip(affine(right, program))
                .map(|(&a, b)| a + b)
                .collect();
        }
        Expression::Multiply { left, right } => {
            let a = affine(left, program);
            let b = affine(right, program);
            for k in 0..n {
                result[k] = a[k] * b[n] + b[k] * a[n];
            }
            result[n] = a[n] * b[n];
        }
        Expression::Power { .. } => unreachable!("validated affine event model"),
    }
    result
}

pub(crate) struct GuardBounds {
    coefficients: Vec<Vec<I>>,
}

impl GuardBounds {
    pub(crate) fn new(program: &Program, driven: &[String]) -> Result<Self, Error> {
        let count = program.nodes.len();
        let variables = count + program.states.len();
        let driven: Vec<_> = driven
            .iter()
            .map(|name| program.nodes.iter().position(|n| n == name).unwrap())
            .collect();
        let unknown: Vec<_> = (1..count).filter(|n| !driven.contains(n)).collect();
        let n = unknown.len();
        let width = driven.len() + program.states.len() + 1;
        let mut groups = BTreeMap::new();
        for c in &program.contributions {
            let rhs = affine(&c.rhs, program);
            let row = groups.entry(&c.branch).or_insert_with(|| {
                let mut row = vec![I::ZERO; variables + 1];
                row[c.positive] = row[c.positive] + I::ONE;
                row[c.negative] = row[c.negative] - I::ONE;
                row
            });
            for (value, term) in row.iter_mut().zip(rhs) {
                *value = *value - term;
            }
        }
        let mut rows: Vec<Vec<I>> = groups
            .values()
            .map(|row| {
                unknown
                    .iter()
                    .map(|&k| row[k])
                    .chain(driven.iter().map(|&k| -row[k]))
                    .chain((count..variables).map(|k| -row[k]))
                    .chain([-row[variables]])
                    .collect()
            })
            .collect();
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
            for k in col + 1..n + width {
                rows[col][k] = rows[col][k] / divisor;
            }
            rows[col][col] = I::ONE;
            for r in col + 1..rows.len() {
                let factor = rows[r][col];
                for k in col + 1..n + width {
                    rows[r][k] = rows[r][k] - factor * rows[col][k];
                }
                rows[r][col] = I::ZERO;
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
        let mut nodes = vec![vec![I::ZERO; width]; variables];
        for (k, &node) in driven.iter().enumerate() {
            nodes[node][k] = I::ONE;
        }
        for state in 0..program.states.len() {
            nodes[count + state][driven.len() + state] = I::ONE;
        }
        for r in (0..n).rev() {
            for k in 0..width {
                let rest =
                    (r + 1..n).fold(I::ZERO, |sum, c| sum + rows[r][c] * nodes[unknown[c]][k]);
                nodes[unknown[r]][k] = rows[r][n + k] - rest;
            }
        }
        let coefficients = program
            .events
            .iter()
            .map(|event| {
                let guard = affine(&event.guard, program);
                (0..width)
                    .map(|k| {
                        let base = if k == width - 1 {
                            guard[variables]
                        } else {
                            I::ZERO
                        };
                        (0..variables).fold(base, |sum, j| sum + guard[j] * nodes[j][k])
                    })
                    .collect::<Vec<_>>()
            })
            .collect::<Vec<_>>();
        if coefficients.iter().flatten().any(|x| !x.finite()) {
            return Err(unresolved("nonfinite event trajectory bounds"));
        }
        if coefficients
            .iter()
            .any(|row| row[driven.len()..width - 1].iter().any(|x| !x.zero()))
        {
            return Err(unresolved(
                "cannot certify cross guard independence from event state",
            ));
        }
        Ok(Self { coefficients })
    }

    pub(crate) fn values(&self, inputs: &[I]) -> Vec<I> {
        self.coefficients
            .iter()
            .map(|row| {
                row.iter()
                    .zip(inputs)
                    .fold(*row.last().unwrap(), |sum, (&a, &v)| sum + a * v)
            })
            .collect()
    }

    pub(crate) fn same_zero_set(&self, first: usize, second: usize) -> bool {
        let a = &self.coefficients[first];
        let b = &self.coefficients[second];
        if a.iter().chain(b).any(|v| v.lo != v.hi) {
            return false;
        }
        let Some(pivot) = a.iter().position(|v| !v.zero()) else {
            return false;
        };
        !b[pivot].zero()
            && a.iter()
                .zip(b)
                .all(|(x, y)| equal_products(x.lo, b[pivot].lo, y.lo, a[pivot].lo))
    }
}
