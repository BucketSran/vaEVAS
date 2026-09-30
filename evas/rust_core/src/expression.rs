//! Validate polynomial IR and evaluate its value and exact chain-rule gradient.
use crate::interval::{sum_products_sign, Interval as I};
use crate::ir::{Error, Expression, Relation};
use std::collections::{BTreeSet, HashSet};

pub(crate) fn validate(expr: &Expression, count: usize) -> Result<(), Error> {
    match expr {
        Expression::State { .. } | Expression::Operator { .. } => {
            return Err(Error::new(
                "unsupported_analysis",
                "state requires transient execution",
            ))
        }
        Expression::Affine { constant, terms } => {
            let mut seen = BTreeSet::new();
            if !constant.is_finite()
                || terms
                    .iter()
                    .any(|t| t.node >= count || !t.coefficient.is_finite() || !seen.insert(t.node))
            {
                return Err(Error::new(
                    "invalid_ir",
                    "invalid affine constant or duplicate/out-of-range term",
                ));
            }
        }
        Expression::Add { left, right } | Expression::Multiply { left, right } => {
            validate(left, count)?;
            validate(right, count)?;
        }
        Expression::Power { base, exponent } => {
            if !(1..=32).contains(exponent) {
                return Err(Error::new("invalid_ir", "power exponent must be in [1,32]"));
            }
            validate(base, count)?;
        }
        Expression::Select {
            left,
            right,
            then_value,
            else_value,
            origin,
            ..
        } => {
            if origin.instance.is_empty()
                || origin.source.is_empty()
                || origin.line == 0
                || origin.column == 0
            {
                return Err(Error::new("invalid_ir", "invalid select source identity"));
            }
            validate(left, count)?;
            validate(right, count)?;
            validate(then_value, count)?;
            validate(else_value, count)?;
        }
    }
    Ok(())
}

fn predicate_nodes(expr: &Expression, nodes: &mut BTreeSet<usize>) {
    match expr {
        Expression::Affine { terms, .. } => {
            nodes.extend(terms.iter().map(|t| t.node));
        }
        Expression::Add { left, right } | Expression::Multiply { left, right } => {
            predicate_nodes(left, nodes);
            predicate_nodes(right, nodes);
        }
        Expression::Power { base, .. } => predicate_nodes(base, nodes),
        Expression::Select {
            left,
            right,
            then_value,
            else_value,
            ..
        } => {
            predicate_nodes(left, nodes);
            predicate_nodes(right, nodes);
            predicate_nodes(then_value, nodes);
            predicate_nodes(else_value, nodes);
        }
        Expression::State { .. } | Expression::Operator { .. } => {}
    }
}

pub(crate) fn validate_select_predicates(
    expr: &Expression,
    allowed_nodes: &HashSet<usize>,
) -> Result<(), Error> {
    match expr {
        Expression::Select {
            left,
            right,
            then_value,
            else_value,
            origin,
            ..
        } => {
            let mut nodes = BTreeSet::new();
            predicate_nodes(left, &mut nodes);
            predicate_nodes(right, &mut nodes);
            if !nodes.iter().all(|node| allowed_nodes.contains(node)) {
                return Err(Error::new(
                    "unsupported_condition",
                    format!(
                        "ordinary analog if predicate depends on an undriven voltage at {}",
                        origin.label()
                    ),
                ));
            }
            validate_select_predicates(left, allowed_nodes)?;
            validate_select_predicates(right, allowed_nodes)?;
            validate_select_predicates(then_value, allowed_nodes)?;
            validate_select_predicates(else_value, allowed_nodes)?;
        }
        Expression::Add { left, right } | Expression::Multiply { left, right } => {
            validate_select_predicates(left, allowed_nodes)?;
            validate_select_predicates(right, allowed_nodes)?;
        }
        Expression::Power { base, .. } => validate_select_predicates(base, allowed_nodes)?,
        Expression::Affine { .. } | Expression::State { .. } | Expression::Operator { .. } => {}
    }
    Ok(())
}

pub(crate) struct Value {
    pub(crate) value: f64,
    pub(crate) gradient: Vec<(usize, f64)>,
}

/// Neumaier summation retains small terms when large additive terms cancel.
#[derive(Clone, Default)]
struct Sum {
    value: f64,
    correction: f64,
}

impl Sum {
    fn add(&mut self, term: f64) {
        let next = self.value + term;
        self.correction += if self.value.abs() >= term.abs() {
            (self.value - next) + term
        } else {
            (term - next) + self.value
        };
        self.value = next;
    }

    fn total(self) -> f64 {
        self.value + self.correction
    }
}

/// Accumulate a signed expression sum before rounding its value/gradient.
/// In particular, lhs - (lhs - s*f) must not round to zero before s*f is
/// examined. Only sums and constant factors are flattened, not polynomials.
pub(crate) struct Accumulator {
    value: Sum,
    gradient: Vec<(usize, Sum)>,
}

impl Accumulator {
    pub(crate) fn new() -> Self {
        Self {
            value: Sum::default(),
            gradient: Vec::new(),
        }
    }

    fn add_derivative(&mut self, node: usize, value: f64) {
        let index = match self.gradient.binary_search_by_key(&node, |&(node, _)| node) {
            Ok(index) => index,
            Err(index) => {
                self.gradient.insert(index, (node, Sum::default()));
                index
            }
        };
        self.gradient[index].1.add(value);
    }

    pub(crate) fn add_constant(&mut self, value: f64) {
        self.value.add(value);
    }

    pub(crate) fn add_node(&mut self, node: usize, coefficient: f64, voltage: f64) {
        self.value.add(coefficient * voltage);
        self.add_derivative(node, coefficient);
    }

    pub(crate) fn add_expression(
        &mut self,
        expr: &Expression,
        factor: f64,
        nodes: &[f64],
    ) -> Result<(), Error> {
        match expr {
            Expression::State { .. } | Expression::Operator { .. } => {
                return Err(Error::new(
                    "unsupported_analysis",
                    "unbound state in static expression",
                ))
            }
            Expression::Affine { constant, terms } => {
                self.add_constant(factor * constant);
                for t in terms {
                    self.add_node(t.node, factor * t.coefficient, nodes[t.node]);
                }
            }
            Expression::Add { left, right } => {
                self.add_expression(left, factor, nodes)?;
                self.add_expression(right, factor, nodes)?;
            }
            Expression::Multiply { left, right } => {
                for (scalar, other) in [(left, right), (right, left)] {
                    if let Expression::Affine { constant, terms } = scalar.as_ref() {
                        if terms.is_empty() {
                            return self.add_expression(other, factor * constant, nodes);
                        }
                    }
                }
                let a = evaluate(left, nodes)?;
                let b = evaluate(right, nodes)?;
                self.value.add(factor * (a.value * b.value));
                for (node, da) in a.gradient {
                    self.add_derivative(node, factor * da * b.value);
                }
                for (node, db) in b.gradient {
                    self.add_derivative(node, factor * a.value * db);
                }
            }
            Expression::Power { base, exponent } => {
                let a = evaluate(base, nodes)?;
                self.value.add(factor * a.value.powi(*exponent as i32));
                let derivative = factor * f64::from(*exponent) * a.value.powi(*exponent as i32 - 1);
                for (node, da) in a.gradient {
                    self.add_derivative(node, derivative * da);
                }
            }
            Expression::Select {
                relation,
                left,
                right,
                then_value,
                else_value,
                origin,
            } => {
                let selected =
                    if select_predicate(*relation, left, right, nodes).map_err(|mut error| {
                        error.message.push_str(&format!(" at {}", origin.label()));
                        error
                    })? {
                        then_value
                    } else {
                        else_value
                    };
                self.add_expression(selected, factor, nodes)?;
            }
        }
        Ok(())
    }

    pub(crate) fn finish(self) -> Result<Value, Error> {
        let result = Value {
            value: self.value.total(),
            gradient: self
                .gradient
                .into_iter()
                .map(|(node, sum)| (node, sum.total()))
                .collect(),
        };
        if !result.value.is_finite() || result.gradient.iter().any(|(_, v)| !v.is_finite()) {
            return Err(Error::new(
                "nonfinite_arithmetic",
                "nonfinite polynomial value or derivative",
            ));
        }
        Ok(result)
    }
}

impl Relation {
    fn selects_sign(self, sign: i8) -> bool {
        match self {
            Self::Lt => sign < 0,
            Self::Le => sign <= 0,
            Self::Gt => sign > 0,
            Self::Ge => sign >= 0,
        }
    }
}

fn affine_product_terms(
    expr: &Expression,
    factor: f64,
    nodes: &[f64],
    terms: &mut Vec<(f64, f64)>,
) -> Result<bool, Error> {
    if !factor.is_finite() {
        return Ok(false);
    }
    match expr {
        Expression::Affine {
            constant,
            terms: affine_terms,
        } => {
            terms.push((factor, *constant));
            for term in affine_terms {
                terms.push((factor * term.coefficient, nodes[term.node]));
            }
            Ok(true)
        }
        Expression::Add { left, right } => Ok(affine_product_terms(left, factor, nodes, terms)?
            && affine_product_terms(right, factor, nodes, terms)?),
        Expression::Select {
            relation,
            left,
            right,
            then_value,
            else_value,
            origin,
        } => {
            let selected =
                if select_predicate(*relation, left, right, nodes).map_err(|mut error| {
                    error.message.push_str(&format!(" at {}", origin.label()));
                    error
                })? {
                    then_value
                } else {
                    else_value
                };
            affine_product_terms(selected, factor, nodes, terms)
        }
        _ => Ok(false),
    }
}

fn expression_interval(expr: &Expression, nodes: &[f64]) -> Result<I, Error> {
    match expr {
        Expression::State { .. } | Expression::Operator { .. } => Err(Error::new(
            "unsupported_analysis",
            "unbound state in static expression",
        )),
        Expression::Affine { constant, terms } => {
            let mut value = I::point(*constant);
            for term in terms {
                value = value + I::point(term.coefficient) * I::point(nodes[term.node]);
            }
            Ok(value)
        }
        Expression::Add { left, right } => {
            Ok(expression_interval(left, nodes)? + expression_interval(right, nodes)?)
        }
        Expression::Multiply { left, right } => {
            Ok(expression_interval(left, nodes)? * expression_interval(right, nodes)?)
        }
        Expression::Power { base, exponent } => {
            let base = expression_interval(base, nodes)?;
            if *exponent == 0 {
                return Ok(I::ONE);
            }
            let mut value = base;
            for _ in 1..*exponent {
                value = value * base;
            }
            Ok(value)
        }
        Expression::Select {
            relation,
            left,
            right,
            then_value,
            else_value,
            origin,
        } => {
            let selected =
                if select_predicate(*relation, left, right, nodes).map_err(|mut error| {
                    error.message.push_str(&format!(" at {}", origin.label()));
                    error
                })? {
                    then_value
                } else {
                    else_value
                };
            expression_interval(selected, nodes)
        }
    }
}

fn predicate_sign(left: &Expression, right: &Expression, nodes: &[f64]) -> Result<i8, Error> {
    let mut terms = Vec::new();
    let affine = affine_product_terms(left, 1.0, nodes, &mut terms)?
        && affine_product_terms(right, -1.0, nodes, &mut terms)?;
    if affine {
        terms.retain(|(a, b)| *a != 0.0 && *b != 0.0);
        if let Some(sign) = sum_products_sign(&terms) {
            return Ok(sign);
        }
    }
    let interval = expression_interval(left, nodes)? - expression_interval(right, nodes)?;
    if let Some(sign) = interval.sign() {
        return Ok(sign);
    }
    Err(Error::new(
        "condition_precision",
        "ordinary analog if predicate cannot be certified at binary64 precision",
    ))
}

fn select_predicate(
    relation: Relation,
    left: &Expression,
    right: &Expression,
    nodes: &[f64],
) -> Result<bool, Error> {
    Ok(relation.selects_sign(predicate_sign(left, right, nodes)?))
}

pub(crate) fn evaluate(expr: &Expression, nodes: &[f64]) -> Result<Value, Error> {
    let mut sum = Accumulator::new();
    sum.add_expression(expr, 1.0, nodes)?;
    sum.finish()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn signed_sum_preserves_small_residual_and_derivative() {
        let rhs: Expression = serde_json::from_str(
            r#"{"op":"add",
                "left":{"op":"affine","constant":0,"terms":[{"node":0,"coefficient":1}]},
                "right":{"op":"multiply",
                    "left":{"op":"affine","constant":-1e-13,"terms":[]},
                    "right":{"op":"add",
                        "left":{"op":"affine","constant":-1,"terms":[{"node":0,"coefficient":1}]},
                        "right":{"op":"power","exponent":3,"base":
                            {"op":"affine","constant":0,"terms":[{"node":0,"coefficient":1}]}}}}}"#,
        )
        .unwrap();
        let mut residual = Accumulator::new();
        residual.add_node(0, 1.0, 0.5);
        residual.add_expression(&rhs, -1.0, &[0.5]).unwrap();
        let result = residual.finish().unwrap();
        // s*(x+x^3-1) and s*(1+3x^2) at x=.5, independently by hand.
        assert!((result.value - (-0.375e-13)).abs() < 1e-28);
        assert!((result.gradient[0].1 - 1.75e-13).abs() < 1e-28);
    }

    #[test]
    fn coupled_product_gradient_has_independent_hand_answers() {
        // f(x,z)=(x+2z)^3*(x-z); includes both product-rule terms and
        // derivatives through a shared, multi-node power base.
        let expr: Expression = serde_json::from_str(
            r#"{
            "op":"multiply",
            "left":{"op":"power","exponent":3,"base":{"op":"affine","constant":0,
                "terms":[{"node":0,"coefficient":1},{"node":1,"coefficient":2}]}},
            "right":{"op":"affine","constant":0,
                "terms":[{"node":0,"coefficient":1},{"node":1,"coefficient":-1}]}
        }"#,
        )
        .unwrap();
        for (nodes, value, gradient) in [
            ([2.0, -0.5], 2.5, [8.5, 14.0]),
            ([0.0, 0.0], 0.0, [0.0, 0.0]),
            ([-1.0, 0.5], 0.0, [0.0, 0.0]),
            ([1.0, 1.0], 0.0, [27.0, -27.0]),
        ] {
            let actual = evaluate(&expr, &nodes).unwrap();
            assert_eq!(actual.value, value);
            assert_eq!(
                actual
                    .gradient
                    .iter()
                    .map(|&(_, value)| value)
                    .collect::<Vec<_>>(),
                gradient
            );
        }
    }
}
