//! Enclose affine guards from the original binary64 IR, including assembly and
//! linear solve roundoff. Prepared once for a state-independent event schedule.
use crate::affine_bounds::affine;
use crate::interval::{equal_products, Interval as I};
use crate::ir::{Error, EventTrigger, Program};
use std::collections::BTreeMap;

pub(crate) fn unresolved(message: &str) -> Error {
    Error::new("event_resolution", message)
}

pub(crate) struct GuardBounds {
    coefficients: Vec<Vec<I>>,
}

impl GuardBounds {
    pub(crate) fn new(program: &Program, driven: &[String]) -> Result<Self, Error> {
        let count = program.nodes.len();
        let variables = count + program.states.len() + program.operators.len();
        let driven: Vec<_> = driven
            .iter()
            .map(|name| program.nodes.iter().position(|n| n == name).unwrap())
            .collect();
        let unknown: Vec<_> = (1..count).filter(|n| !driven.contains(n)).collect();
        let n = unknown.len();
        let width = driven.len() + program.states.len() + program.operators.len() + 1;
        let mut groups = BTreeMap::new();
        for c in &program.contributions {
            let rhs = affine(&c.rhs, program)?;
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
        let rows: Vec<Vec<I>> = groups
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
        let rows = crate::affine_bounds::eliminate(rows, n, width)?;
        let mut nodes = vec![vec![I::ZERO; width]; variables];
        for (k, &node) in driven.iter().enumerate() {
            nodes[node][k] = I::ONE;
        }
        for state in 0..(program.states.len() + program.operators.len()) {
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
                // Keep rows aligned with event indices; timer has no guard.
                let EventTrigger::Cross { guard, .. } = &event.trigger else {
                    return Ok(vec![I::ZERO; width]);
                };
                let guard = affine(guard, program)?;
                Ok((0..width)
                    .map(|k| {
                        let base = if k == width - 1 {
                            guard[variables]
                        } else {
                            I::ZERO
                        };
                        (0..variables).fold(base, |sum, j| sum + guard[j] * nodes[j][k])
                    })
                    .collect::<Vec<_>>())
            })
            .collect::<Result<Vec<_>, Error>>()?;
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

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ir::Expression;

    #[test]
    fn interval_conversion_rejects_products_with_uncertain_variable_coefficients() {
        let program: Program = serde_json::from_value(serde_json::json!({
            "schema_version": crate::ir::SCHEMA_VERSION,
            "nodes": ["0", "u"], "contributions": []
        }))
        .unwrap();
        let leaf = |coefficient| Expression::Affine {
            constant: 0.0,
            terms: vec![crate::ir::Term {
                node: 1,
                coefficient,
            }],
        };
        let expression = Expression::Multiply {
            left: Box::new(Expression::Add {
                left: Box::new(Expression::Add {
                    left: Box::new(leaf(1.0)),
                    right: Box::new(leaf(1e-16)),
                }),
                right: Box::new(leaf(-1.0)),
            }),
            right: Box::new(leaf(1e16)),
        };
        assert_eq!(
            affine(&expression, &program).unwrap_err().kind,
            "event_resolution"
        );
    }
}
