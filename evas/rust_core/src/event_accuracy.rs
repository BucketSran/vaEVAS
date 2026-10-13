//! Enclose affine guards from the original binary64 IR, including assembly and
//! linear solve roundoff. Held-state projections are rebuilt only after an
//! accepted event changes a relevant state enclosure.
use crate::affine_bounds::affine;
use crate::interval::{equal_products, Interval as I};
use crate::ir::{Error, EventTrigger, Expression, Program};

pub(crate) fn unresolved(message: &str) -> Error {
    Error::new("event_resolution", message)
}

pub(crate) struct GuardBounds {
    coefficients: Vec<Vec<I>>,
    state_coefficients: Vec<Vec<I>>,
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
                    EventTrigger::Timer { .. }
                    | EventTrigger::HeldTimer { .. }
                    | EventTrigger::FinalStep { .. }
                    | EventTrigger::InitialStep { .. } => None,
                    EventTrigger::Or { .. } => unreachable!("validated leaves are not OR groups"),
                });
            }
        }
        Self::expressions(program, driven, &expressions)
    }

    pub(crate) fn held(
        program: &Program,
        driven: &[String],
        dynamic: &[bool],
        states: &[I],
    ) -> Result<Self, Error> {
        let mut expressions = Vec::new();
        for event in &program.events {
            for trigger in event.trigger.leaves()? {
                expressions.push(match trigger {
                    EventTrigger::Cross { guard, .. } => {
                        (!dynamic[expressions.len()]).then_some(guard)
                    }
                    _ => None,
                });
            }
        }
        Self::project(program, driven, &expressions, Some(states), false)
    }

    /// Project state-independent affine expressions onto the driven inputs.
    pub(crate) fn expressions(
        program: &Program,
        driven: &[String],
        expressions: &[Option<&Expression>],
    ) -> Result<Self, Error> {
        Self::project(program, driven, expressions, None, false)
    }

    /// Keep accepted/local held states as certified forcing columns.
    pub(crate) fn stateful_expressions(
        program: &Program,
        driven: &[String],
        expressions: &[Option<&Expression>],
    ) -> Result<Self, Error> {
        Self::project(program, driven, expressions, None, true)
    }

    fn project(
        program: &Program,
        driven: &[String],
        expressions: &[Option<&Expression>],
        states: Option<&[I]>,
        keep_states: bool,
    ) -> Result<Self, Error> {
        let count = program.nodes.len();
        let variables = count + program.states.len() + program.operators.len();
        let width = driven.len() + program.states.len() + program.operators.len() + 1;
        // Direct driven/state predicates do not need unrelated output equations.
        // In particular an analog Select elsewhere cannot change a supplied input.
        let driven_nodes: Vec<_> = driven
            .iter()
            .map(|name| {
                program
                    .nodes
                    .iter()
                    .position(|node| node == name)
                    .ok_or_else(|| Error::new("invalid_inputs", "unknown driven node"))
            })
            .collect::<Result<_, _>>()?;
        let direct = expressions
            .iter()
            .flatten()
            .map(|expression| affine(expression, program))
            .collect::<Result<Vec<_>, _>>()?
            .iter()
            .all(|row| (1..count).all(|node| row[node].zero() || driven_nodes.contains(&node)));
        let nodes = if direct {
            let mut nodes = vec![vec![I::ZERO; width]; variables];
            for (column, &node) in driven_nodes.iter().enumerate() {
                nodes[node][column] = I::ONE;
            }
            for index in 0..program.states.len() + program.operators.len() {
                nodes[count + index][driven.len() + index] = I::ONE;
            }
            nodes
        } else {
            crate::affine_bounds::node_map(program, driven)?
        };
        let mut coefficients = expressions
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
        let state_coefficients = coefficients
            .iter()
            .map(|row| row[driven.len()..driven.len() + program.states.len()].to_vec())
            .collect();
        if let Some(states) = states {
            if states.len() != program.states.len() {
                return Err(Error::new(
                    "invalid_ir",
                    "held state bounds length mismatch",
                ));
            }
            for row in &mut coefficients {
                for (index, state) in states.iter().enumerate() {
                    row[width - 1] = row[width - 1] + row[driven.len() + index] * *state;
                    row[driven.len() + index] = I::ZERO;
                }
            }
        }
        if coefficients.iter().flatten().any(|x| !x.finite()) {
            return Err(unresolved("nonfinite event trajectory bounds"));
        }
        if coefficients.iter().any(|row| {
            row[driven.len() + if keep_states { program.states.len() } else { 0 }..width - 1]
                .iter()
                .any(|x| !x.zero())
        }) {
            return Err(unresolved(
                "cannot certify cross guard independence from event state",
            ));
        }
        Ok(Self {
            coefficients,
            state_coefficients,
            driven_count: driven.len(),
        })
    }

    pub(crate) fn changed_by(&self, before: &[I], after: &[I]) -> Vec<bool> {
        self.state_coefficients
            .iter()
            .map(|row| {
                row.iter()
                    .enumerate()
                    .any(|(i, c)| !c.zero() && before[i] != after[i])
            })
            .collect()
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

    pub(crate) fn value_with_states(&self, expression: usize, inputs: &[I], states: &[I]) -> I {
        let row = &self.coefficients[expression];
        row[..self.driven_count]
            .iter()
            .zip(inputs)
            .chain(self.state_coefficients[expression].iter().zip(states))
            .fold(*row.last().unwrap(), |sum, (&coefficient, &value)| {
                sum + coefficient * value
            })
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
