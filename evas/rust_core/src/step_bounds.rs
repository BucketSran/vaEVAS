//! Model timestep requests are evaluated only from accepted, certified frames.
use crate::interval::Interval as I;
use crate::ir::{Error, Expression, Program, Solution, Term};

pub(crate) struct Bounds {
    expressions: Vec<(Expression, Expression)>,
}

fn bind(expr: &Expression, p: &Program, owner: &str) -> Result<Expression, Error> {
    let index = match expr {
        Expression::State { state } => {
            if p.states.get(*state).is_none_or(|s| s.instance != owner) {
                return Err(Error::new(
                    "invalid_ir",
                    "invalid $bound_step state reference",
                ));
            }
            Some(p.nodes.len() + state)
        }
        Expression::Operator { operator } => {
            if p.operators
                .get(*operator)
                .is_none_or(|s| s.origin().instance != owner)
            {
                return Err(Error::new(
                    "invalid_ir",
                    "invalid $bound_step operator reference",
                ));
            }
            Some(p.nodes.len() + p.states.len() + operator)
        }
        _ => None,
    };
    if let Some(node) = index {
        return Ok(Expression::Affine {
            constant: 0.,
            terms: vec![Term {
                node,
                coefficient: 1.,
            }],
        });
    }
    Ok(match expr {
        Expression::Add { left, right } => Expression::Add {
            left: Box::new(bind(left, p, owner)?),
            right: Box::new(bind(right, p, owner)?),
        },
        Expression::Multiply { left, right } => Expression::Multiply {
            left: Box::new(bind(left, p, owner)?),
            right: Box::new(bind(right, p, owner)?),
        },
        Expression::Divide { left, right } => Expression::Divide {
            left: Box::new(bind(left, p, owner)?),
            right: Box::new(bind(right, p, owner)?),
        },
        Expression::Power { base, exponent } => Expression::Power {
            base: Box::new(bind(base, p, owner)?),
            exponent: *exponent,
        },
        Expression::Select {
            relation,
            left,
            right,
            then_value,
            else_value,
            origin,
        } => Expression::Select {
            relation: *relation,
            left: Box::new(bind(left, p, owner)?),
            right: Box::new(bind(right, p, owner)?),
            then_value: Box::new(bind(then_value, p, owner)?),
            else_value: Box::new(bind(else_value, p, owner)?),
            origin: origin.clone(),
        },
        Expression::Affine { .. } => {
            // Validate original node references before appending state slots.
            crate::expression::validate(expr, p.nodes.len())?;
            expr.clone()
        }
        _ => unreachable!(),
    })
}

/// Boolean activation controls the numerical mesh, not the physical equation.
/// If either feasible path requests a bound, applying it to both is conservative.
/// Only predicate precision failures qualify; domains and malformed IR propagate.
pub(crate) fn possible_activation(
    expr: &Expression,
    resolve: &impl Fn(&Expression) -> Result<Expression, Error>,
) -> Result<Expression, Error> {
    fn boolean(e: &Expression) -> bool {
        match e {
            Expression::Affine { constant, terms } => {
                terms.is_empty() && (*constant == 0. || *constant == 1.)
            }
            Expression::Select {
                then_value,
                else_value,
                ..
            } => boolean(then_value) && boolean(else_value),
            _ => false,
        }
    }
    match resolve(expr) {
        Ok(value) => Ok(value),
        Err(error) if error.kind == "condition_precision" && boolean(expr) => {
            let Expression::Select {
                then_value,
                else_value,
                ..
            } = expr
            else {
                return Err(error);
            };
            let a = possible_activation(then_value, resolve)?;
            let b = possible_activation(else_value, resolve)?;
            let inactive = |e: &Expression| matches!(e, Expression::Affine { constant: 0., terms } if terms.is_empty());
            Ok(Expression::Affine {
                constant: if inactive(&a) && inactive(&b) { 0. } else { 1. },
                terms: vec![],
            })
        }
        Err(error) => Err(error),
    }
}

impl Bounds {
    pub(crate) fn new(program: &Program) -> Result<Self, Error> {
        let mut expressions = Vec::new();
        for bound in &program.step_bounds {
            let o = &bound.origin;
            if o.source.is_empty() || o.instance.is_empty() || o.line == 0 || o.column == 0 {
                return Err(Error::new("invalid_ir", "invalid $bound_step origin"));
            }
            let active = bind(&bound.active, program, &o.instance)?;
            let value = bind(&bound.value, program, &o.instance)?;
            let count = program.nodes.len() + program.states.len() + program.operators.len();
            crate::expression::validate(&active, count)?;
            crate::expression::validate(&value, count)?;
            expressions.push((active, value));
        }
        Ok(Self { expressions })
    }

    pub(crate) fn next_time(
        &self,
        time: f64,
        max_step: f64,
        solution: &Solution,
        states: &[I],
        operators: &[I],
    ) -> Result<f64, Error> {
        if self.expressions.is_empty() {
            return Ok(time + max_step);
        }
        let nodes = solution.certified_voltage_bounds.as_ref().ok_or_else(|| {
            Error::new(
                "bound_step_precision",
                "$bound_step requires certified node bounds",
            )
        })?;
        let values: Vec<_> = nodes
            .iter()
            .map(|b| I { lo: b[0], hi: b[1] })
            .chain(states.iter().copied())
            .chain(operators.iter().copied())
            .collect();
        let evaluate = |expr: &Expression| {
            let resolved = crate::expression::resolve_selects(expr, &values)?;
            crate::solver::interval_expression(&resolved, &values)
        };
        let mut step = max_step;
        for (active, value) in &self.expressions {
            let active =
                possible_activation(active, &|e| crate::expression::resolve_selects(e, &values))?;
            let active = crate::solver::interval_expression(&active, &values)?;
            if active.zero() {
                continue;
            }
            if !active.finite() {
                return Err(Error::new(
                    "bound_step_precision",
                    "nonfinite $bound_step activation",
                ));
            }
            // A finite enclosure containing both zero and nonzero values may
            // activate this request; use its unchanged certified value below.
            let value = evaluate(value)?;
            if !value.finite() || value.lo < 0. {
                return Err(Error::new(
                    "invalid_bound_step",
                    "$bound_step must be certified finite and nonnegative",
                ));
            }
            step = step.min(value.lo);
        }
        // Downward addition cannot exceed the certified bound. The simulator's
        // minimum timestep is the next representable time, also for a zero bound.
        let end = if (time + step).is_finite() {
            (I::point(time) + I::point(step)).lo
        } else {
            f64::INFINITY
        };
        Ok(end.max(time.next_up()))
    }
}

/// The implicit trajectory builder presently accepts only unconditional constants.
/// Its internal integration mesh is capped before construction, never after it.
pub(crate) fn constant_cap(program: &Program, max_step: f64) -> Result<f64, Error> {
    let mut step = max_step;
    for bound in &program.step_bounds {
        let (
            Expression::Affine {
                constant: active,
                terms: a,
            },
            Expression::Affine {
                constant: value,
                terms: v,
            },
        ) = (&bound.active, &bound.value)
        else {
            return Err(Error::new(
                "unsupported_bound_step",
                "implicit dynamics require unconditional constant $bound_step",
            ));
        };
        if !a.is_empty() || !v.is_empty() || *active == 0. || *value <= 0. {
            return Err(Error::new(
                "unsupported_bound_step",
                "implicit dynamics require positive unconditional constant $bound_step",
            ));
        }
        step = step.min(*value);
    }
    Ok(step)
}

/// Preconstructed numerical histories also need the model's constant cap.
/// Dynamic requests cannot yet constrain that separate integration mesh.
pub(crate) fn history_cap(program: &Program, max_step: f64) -> Result<f64, Error> {
    if program.step_bounds.is_empty() {
        return Ok(max_step);
    }
    if let Ok(step) = constant_cap(program, max_step) {
        return Ok(step);
    }
    Ok(max_step)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ir::{Origin, Relation};
    fn constant(value: f64) -> Expression {
        Expression::Affine {
            constant: value,
            terms: vec![],
        }
    }
    fn uncertain_active() -> Expression {
        Expression::Select {
            relation: Relation::Gt,
            left: Box::new(Expression::Affine {
                constant: 0.,
                terms: vec![Term {
                    node: 1,
                    coefficient: 1.,
                }],
            }),
            right: Box::new(constant(0.5)),
            then_value: Box::new(constant(1.)),
            else_value: Box::new(constant(0.)),
            origin: Origin {
                instance: "dut".into(),
                source: "bound.va".into(),
                line: 1,
                column: 1,
                expansion: vec![],
            },
        }
    }
    fn frame() -> Solution {
        Solution {
            voltages: vec![0., 0.5],
            certified_voltage_bounds: Some(vec![[0., 0.], [0.49, 0.51]]),
            max_residual_v: 0.,
            max_residual_ratio: 0.,
            max_scaled_residual_ratio: None,
            max_voltage_correction_v: None,
            max_voltage_correction_ratio: None,
        }
    }
    #[test]
    fn uncertain_boolean_activation_caps_mesh_without_resolving_physical_predicate() {
        let active = uncertain_active();
        let bounds = Bounds {
            expressions: vec![(active.clone(), constant(0.1))],
        };
        let next = bounds.next_time(0., 1., &frame(), &[], &[]).unwrap();
        assert!(next > 0. && next <= 0.1);
        let physical =
            crate::expression::resolve_selects(&active, &[I::ZERO, I { lo: 0.49, hi: 0.51 }]);
        assert_eq!(physical.unwrap_err().kind, "condition_precision");
    }
    #[test]
    fn potentially_active_bound_still_requires_unchanged_numeric_certificate() {
        let active = uncertain_active();
        for value in [
            constant(-0.1),
            Expression::Divide {
                left: Box::new(constant(1.)),
                right: Box::new(constant(0.)),
            },
        ] {
            let bounds = Bounds {
                expressions: vec![(active.clone(), value)],
            };
            assert!(bounds.next_time(0., 1., &frame(), &[], &[]).is_err());
        }
        let mut selected_value = active.clone();
        if let Expression::Select {
            then_value,
            else_value,
            ..
        } = &mut selected_value
        {
            *then_value = Box::new(constant(0.1));
            *else_value = Box::new(constant(0.2));
        }
        let bounds = Bounds {
            expressions: vec![(active.clone(), selected_value)],
        };
        assert_eq!(
            bounds
                .next_time(0., 1., &frame(), &[], &[])
                .unwrap_err()
                .kind,
            "condition_precision"
        );
        let mut invalid_predicate = active;
        if let Expression::Select { left, .. } = &mut invalid_predicate {
            *left = Box::new(Expression::Divide {
                left: Box::new(constant(1.)),
                right: Box::new(constant(0.)),
            });
        }
        assert!(
            possible_activation(&invalid_predicate, &|e| crate::expression::resolve_selects(
                e,
                &[I::ZERO, I::point(0.5)]
            ))
            .is_err()
        );
    }
}
