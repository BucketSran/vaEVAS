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
        validate_projection(&nodes, variables, width)?;
        let mut coefficients = expressions
            .iter()
            .map(|expression| {
                // Keep rows aligned with event indices; timer has no guard.
                let Some(guard) = expression else {
                    return Ok(vec![I::ZERO; width]);
                };
                let guard = affine(guard, program)?;
                project_row(&guard, &nodes, width)
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

    /// Every voltage here is a forcing value certified by the physical stage.
    /// No voltage equation is solved or inferred by this projection.
    pub(crate) fn passive_program(program: &Program) -> (Program, Vec<String>) {
        let mut projected = program.clone();
        projected.contributions.clear();
        // Preserve original global operator columns for every trigger leaf.
        // Operator guards cannot project onto node/state forcing and obtain
        // no passive zero-set match. Dropping these columns can alias op0 to
        // the constant or make later operator IDs index outside the row.
        // This Program is only an expression projection, never a history.

        projected.step_bounds.clear();
        let driven = program.nodes[1..].to_vec();
        (projected, driven)
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

pub(crate) fn validate_projection(
    nodes: &[Vec<I>],
    variables: usize,
    width: usize,
) -> Result<(), Error> {
    if width == 0 || nodes.len() != variables || nodes.iter().any(|row| row.len() != width) {
        return Err(Error::new(
            "invalid_ir",
            "event projection dimensions mismatch",
        ));
    }
    if nodes.iter().flatten().any(|value| !value.finite()) {
        return Err(unresolved("nonfinite event trajectory bounds"));
    }
    Ok(())
}

pub(crate) fn project_row(guard: &[I], nodes: &[Vec<I>], width: usize) -> Result<Vec<I>, Error> {
    if guard.len() != nodes.len() + 1 {
        return Err(Error::new("invalid_ir", "event guard dimensions mismatch"));
    }
    if guard.iter().any(|value| !value.finite()) {
        return Err(unresolved("nonfinite event trajectory bounds"));
    }
    // The caller validates the complete node map; validate every original guard
    // coefficient before omitting products with either finite exact-zero factor.
    // Keep the original j order of every remaining operation. With a +0 base,
    // adding a finite exact-zero product cannot change either endpoint's bits.
    // A -0 constant is the exception: use the original dense fold for that one
    // column, preserving its signed-zero result as well.
    let terms: Vec<_> = guard[..nodes.len()]
        .iter()
        .enumerate()
        .filter(|(_, value)| !value.zero())
        .collect();
    Ok((0..width)
        .map(|column| {
            let base = if column == width - 1 {
                guard[nodes.len()]
            } else {
                I::ZERO
            };
            if [base.lo, base.hi]
                .iter()
                .any(|value| *value == 0.0 && value.is_sign_negative())
            {
                (0..nodes.len()).fold(base, |sum, j| sum + guard[j] * nodes[j][column])
            } else {
                let sum = terms.iter().fold(base, |sum, &(j, value)| {
                    let node = nodes[j][column];
                    if node.zero() {
                        sum
                    } else {
                        sum + *value * node
                    }
                });
                // Overflow may produce a half-infinite interval which a later
                // dense zero addition normalizes to WHOLE. Keep the original
                // fold on this rejected path too, including endpoint bits.
                if !sum.finite() {
                    (0..nodes.len()).fold(base, |sum, j| sum + guard[j] * nodes[j][column])
                } else {
                    sum
                }
            }
        })
        .collect())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ir::Expression;
    use proptest::prelude::*;

    fn same_projection(guard: &[I], nodes: &[Vec<I>], width: usize) {
        validate_projection(nodes, guard.len() - 1, width).unwrap();
        let sparse = project_row(guard, nodes, width).unwrap();
        for (k, actual) in sparse.iter().enumerate() {
            let base = if k == width - 1 {
                guard[nodes.len()]
            } else {
                I::ZERO
            };
            let dense = (0..nodes.len()).fold(base, |sum, j| sum + guard[j] * nodes[j][k]);
            assert_eq!(
                (actual.lo.to_bits(), actual.hi.to_bits()),
                (dense.lo.to_bits(), dense.hi.to_bits())
            );
        }
    }

    #[test]
    fn sparse_projection_preserves_signed_zero_and_rejects_invalid_inputs() {
        let zero = [I::ZERO, I::point(-0.0), I { lo: -0.0, hi: 0.0 }];
        for a in zero {
            for b in zero {
                same_projection(
                    &[a, I::ONE, -I::ONE, b],
                    &[vec![b, I::ONE], vec![a, I::ONE], vec![a, I::ONE]],
                    2,
                );
            }
        }
        assert!(validate_projection(&[vec![I::ONE]], 2, 1).is_err());
        assert!(validate_projection(&[vec![I::ONE]], 1, 2).is_err());
        assert!(validate_projection(&[], 0, 0).is_err());
        assert!(validate_projection(&[vec![I::point(f64::INFINITY)]], 1, 1).is_err());
        assert!(project_row(&[I::ZERO], &[vec![I::ONE]], 1).is_err());
        assert!(project_row(&[I::ZERO, I::point(f64::NAN)], &[vec![I::ONE]], 1).is_err());
    }

    #[test]
    fn sparse_projection_preserves_dense_nonfinite_normalization() {
        same_projection(
            &[
                I {
                    lo: 0.0,
                    hi: f64::MAX,
                },
                I::ZERO,
                I {
                    lo: 0.0,
                    hi: f64::MAX,
                },
            ],
            &[vec![I::ONE], vec![I::ONE]],
            1,
        );
    }

    #[test]
    fn sparse_projection_work_tracks_nonzero_guard_terms() {
        let variables = 1024;
        let width = variables + 1;
        let mut nodes = vec![vec![I::ZERO; width]; variables];
        for (j, row) in nodes.iter_mut().enumerate() {
            row[j] = I::ONE;
        }
        let mut guard = vec![I::ZERO; variables + 1];
        guard[513] = I::ONE;
        crate::interval::zero_product_tests::reset_work();
        let projected = project_row(&guard, &nodes, width).unwrap();
        let (products, _) = crate::interval::zero_product_tests::work();
        assert_eq!(products, 4);
        assert_eq!(projected[513], I::ONE);
        assert_eq!(projected.iter().filter(|x| !x.zero()).count(), 1);
    }

    #[test]
    fn sparse_projection_skips_zero_node_factors_in_dense_guard() {
        let variables = 64;
        let width = variables + 1;
        let mut nodes = vec![vec![I::ZERO; width]; variables];
        for (j, row) in nodes.iter_mut().enumerate() {
            row[j] = I::ONE;
        }
        let mut guard = vec![I::ONE; variables + 1];
        guard[variables] = I::ZERO;
        same_projection(&guard, &nodes, width);
        crate::interval::zero_product_tests::reset_work();
        project_row(&guard, &nodes, width).unwrap();
        let (products, _) = crate::interval::zero_product_tests::work();
        assert_eq!(products, 4 * variables);
    }

    proptest! {
        #![proptest_config(ProptestConfig::with_cases(1024))]
        #[test]
        fn sparse_projection_matches_original_dense_bits(
            values in prop::collection::vec(any::<u64>().prop_map(f64::from_bits).prop_filter("finite", |v| v.is_finite()), 48),
            zeros in prop::collection::vec(any::<bool>(), 6),
            node_zeros in prop::collection::vec(any::<bool>(), 12),
        ) {
            let interval = |a: f64, b: f64| I {lo:a.min(b), hi:a.max(b)};
            let mut guard: Vec<_> = (0..6).map(|j| if zeros[j] {I::ZERO} else {interval(values[j*2], values[j*2+1])}).collect();
            guard.push(interval(values[12], values[13]));
            let nodes: Vec<_> = (0..6).map(|j| (0..2).map(|k| if node_zeros[j*2+k] {I::ZERO} else {interval(values[14+j*4+k*2], values[15+j*4+k*2])}).collect()).collect();
            same_projection(&guard, &nodes, 2);
        }
    }

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
