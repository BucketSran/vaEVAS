//! Validate polynomial IR and evaluate its value and exact chain-rule gradient.
use crate::ir::{Error, Expression};
use std::collections::BTreeSet;

pub(crate) fn validate(expr: &Expression, count: usize) -> Result<(), Error> {
    match expr {
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
    }
    Ok(())
}

pub(crate) struct Value {
    pub(crate) value: f64,
    pub(crate) gradient: Vec<f64>,
}

pub(crate) fn evaluate(expr: &Expression, nodes: &[f64]) -> Result<Value, Error> {
    let result = match expr {
        Expression::Affine { constant, terms } => {
            let mut result = Value {
                value: *constant,
                gradient: vec![0.0; nodes.len()],
            };
            for t in terms {
                result.value += t.coefficient * nodes[t.node];
                result.gradient[t.node] = t.coefficient;
            }
            result
        }
        Expression::Add { left, right } | Expression::Multiply { left, right } => {
            let a = evaluate(left, nodes)?;
            let b = evaluate(right, nodes)?;
            let multiply = matches!(expr, Expression::Multiply { .. });
            Value {
                value: if multiply {
                    a.value * b.value
                } else {
                    a.value + b.value
                },
                gradient: a
                    .gradient
                    .iter()
                    .zip(&b.gradient)
                    .map(|(da, db)| {
                        if multiply {
                            da * b.value + a.value * db
                        } else {
                            da + db
                        }
                    })
                    .collect(),
            }
        }
        Expression::Power { base, exponent } => {
            let a = evaluate(base, nodes)?;
            let derivative = f64::from(*exponent) * a.value.powi(*exponent as i32 - 1);
            Value {
                value: a.value.powi(*exponent as i32),
                gradient: a.gradient.iter().map(|d| derivative * d).collect(),
            }
        }
    };
    if !result.value.is_finite() || result.gradient.iter().any(|v| !v.is_finite()) {
        return Err(Error::new(
            "nonfinite_arithmetic",
            "nonfinite polynomial value or derivative",
        ));
    }
    Ok(result)
}

#[cfg(test)]
mod tests {
    use super::*;

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
            assert_eq!(actual.gradient, gradient);
        }
    }
}
