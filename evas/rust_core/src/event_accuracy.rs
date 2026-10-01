//! Enclose affine guards from the original binary64 IR, including assembly and
//! linear solve roundoff. Prepared once for a state-independent event schedule.
use crate::affine_bounds::affine;
use crate::interval::{equal_products, Interval as I};
use crate::ir::{Error, EventTrigger, Expression, Program};

pub(crate) fn unresolved(message: &str) -> Error {
    Error::new("event_resolution", message)
}

pub(crate) struct GuardBounds {
    coefficients: Vec<Vec<I>>,
    driven_count: usize,
}

impl GuardBounds {
    pub(crate) fn new(
        program: &Program,
        driven: &[String],
        dynamic: &[bool],
    ) -> Result<Self, Error> {
        let mut expressions = Vec::new();
        for event in &program.events {
            for trigger in event.trigger.leaves()? {
                expressions.push(match trigger {
                    EventTrigger::Cross { guard, .. } => {
                        (!dynamic[expressions.len()]).then_some(guard)
                    }
                    EventTrigger::Timer { .. } => None,
                    EventTrigger::Or { .. } => unreachable!("validated leaves are not OR groups"),
                });
            }
        }
        Self::expressions(program, driven, &expressions)
    }

    /// Project state-independent affine expressions onto the driven inputs.
    pub(crate) fn expressions(
        program: &Program,
        driven: &[String],
        expressions: &[Option<&Expression>],
    ) -> Result<Self, Error> {
        let count = program.nodes.len();
        let variables = count + program.states.len() + program.operators.len();
        let width = driven.len() + program.states.len() + program.operators.len() + 1;
        let nodes = crate::affine_bounds::node_map(program, driven)?;
        let coefficients = expressions
            .iter()
            .map(|expression| {
                // Keep rows aligned with event indices; timer has no guard.
                let Some(guard) = expression else {
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
        Ok(Self {
            coefficients,
            driven_count: driven.len(),
        })
    }

    /// Only a proven zero coefficient permits ignoring an input breakpoint.
    pub(crate) fn active_inputs(&self, expression: usize) -> Vec<usize> {
        self.coefficients[expression][..self.driven_count]
            .iter()
            .enumerate()
            .filter_map(|(i, coefficient)| (!coefficient.zero()).then_some(i))
            .collect()
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
