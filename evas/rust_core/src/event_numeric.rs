//! Pure event arithmetic. No operator history and no accepted-state mutation.
use crate::events::{affine, AffineState};
use crate::interval::Interval as I;
use crate::ir::{Error, EventMathFunction as F, Expression as E, Program, Relation};

pub(crate) fn integral(e: &E, p: &Program) -> bool {
    match e {
        E::Affine { constant, terms } => terms.is_empty() && constant.fract() == 0.,
        E::State { state } => p.states[*state].kind == crate::ir::StateKind::Integer,
        E::Add { left, right } | E::Multiply { left, right } => {
            integral(left, p) && integral(right, p)
        }
        E::Power { base, .. } => integral(base, p),
        E::Select {
            then_value,
            else_value,
            ..
        } => integral(then_value, p) && integral(else_value, p),
        E::EventMath { function, args, .. } => {
            !matches!(function, F::Sqrt) && args.iter().all(|e| integral(e, p))
        }
        _ => false,
    }
}

pub(crate) fn contains_operator(e: &E) -> bool {
    match e {
        E::Operator { .. } => true,
        E::EventMath { args, .. } => args.iter().any(contains_operator),
        E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
            contains_operator(left) || contains_operator(right)
        }
        E::Power { base, .. } => contains_operator(base),
        E::Select {
            left,
            right,
            then_value,
            else_value,
            ..
        } => [left, right, then_value, else_value]
            .iter()
            .any(|e| contains_operator(e)),
        _ => false,
    }
}

pub(crate) fn contains_math(e: &E) -> bool {
    match e {
        E::EventMath { .. } => true,
        E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
            contains_math(left) || contains_math(right)
        }
        E::Power { base, .. } => contains_math(base),
        E::Select {
            left,
            right,
            then_value,
            else_value,
            ..
        } => [left, right, then_value, else_value]
            .iter()
            .any(|e| contains_math(e)),
        _ => false,
    }
}

pub(crate) fn dependencies(e: &E, p: &Program, owner: &str) -> Result<AffineState, Error> {
    fn leaves(e: &E, out: &mut Vec<E>) {
        match e {
            E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
                leaves(left, out);
                leaves(right, out);
            }
            E::Power { base, .. } => leaves(base, out),
            E::Select {
                left,
                right,
                then_value,
                else_value,
                ..
            } => {
                for e in [left, right, then_value, else_value] {
                    leaves(e, out);
                }
            }
            E::EventMath { args, .. } => {
                for e in args {
                    leaves(e, out);
                }
            }
            _ => out.push(e.clone()),
        }
    }
    validate(e, p, owner)?;
    let mut refs = Vec::new();
    leaves(e, &mut refs);
    let mut result = affine(
        &E::Affine {
            constant: 0.,
            terms: vec![],
        },
        p,
        owner,
    )?;
    for leaf in refs {
        result.union_dependencies(&affine(&leaf, p, owner)?);
    }
    Ok(result)
}

pub(crate) fn validate(e: &E, p: &Program, owner: &str) -> Result<(), Error> {
    match e {
        E::EventMath {
            function,
            args,
            origin,
        } => {
            let n = if matches!(function, F::Min | F::Max) {
                2
            } else {
                1
            };
            if args.len() != n
                || origin.instance != owner
                || origin.source.is_empty()
                || origin.line == 0
                || origin.column == 0
            {
                return Err(Error::new("invalid_ir", "invalid pure event mathematics"));
            }
            for arg in args {
                validate(arg, p, owner)?;
            }
        }
        E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
            validate(left, p, owner)?;
            validate(right, p, owner)?;
        }
        E::Power { base, exponent } => {
            if !(1..=32).contains(exponent) {
                return Err(Error::new("invalid_ir", "invalid event power exponent"));
            }
            validate(base, p, owner)?;
        }
        E::Select {
            left,
            right,
            then_value,
            else_value,
            origin,
            ..
        } => {
            if origin.instance != owner
                || origin.source.is_empty()
                || origin.line == 0
                || origin.column == 0
            {
                return Err(Error::new("invalid_ir", "invalid event selection origin"));
            }
            for e in [left, right, then_value, else_value] {
                validate(e, p, owner)?;
            }
        }
        E::Operator { .. } => {
            return Err(Error::new(
                "unsupported_transient",
                "operator calls are only allowed in contributions",
            ))
        }
        _ => {
            affine(e, p, owner)?;
        }
    }
    Ok(())
}

/// Bind pure event values, then use the existing compensated expression evaluator.
/// Validation covers both Select arms before numerical evaluation chooses one.
pub(crate) fn value(
    e: &E,
    p: &Program,
    owner: &str,
    nodes: &[f64],
    states: &[f64],
) -> Result<f64, Error> {
    validate(e, p, owner)?;
    let bound = if contains_math(e) {
        bind_math(e, p, owner, nodes, states)?
    } else {
        crate::display::bind(e, p, owner, states)?
    };
    Ok(crate::expression::evaluate(&bound, nodes)?.value)
}

fn bind_math(e: &E, p: &Program, owner: &str, nodes: &[f64], states: &[f64]) -> Result<E, Error> {
    Ok(match e {
        E::Affine { .. } => e.clone(),
        E::State { state } => E::Affine {
            constant: states[*state],
            terms: vec![],
        },
        E::Add { left, right } => E::Add {
            left: Box::new(bind_math(left, p, owner, nodes, states)?),
            right: Box::new(bind_math(right, p, owner, nodes, states)?),
        },
        E::Multiply { left, right } => E::Multiply {
            left: Box::new(bind_math(left, p, owner, nodes, states)?),
            right: Box::new(bind_math(right, p, owner, nodes, states)?),
        },
        E::Divide { left, right } => E::Divide {
            left: Box::new(bind_math(left, p, owner, nodes, states)?),
            right: Box::new(bind_math(right, p, owner, nodes, states)?),
        },
        E::Power { base, exponent } => E::Power {
            base: Box::new(bind_math(base, p, owner, nodes, states)?),
            exponent: *exponent,
        },
        E::Select {
            relation,
            left,
            right,
            then_value,
            else_value,
            ..
        } => {
            let left = bind_math(left, p, owner, nodes, states)?;
            let right = bind_math(right, p, owner, nodes, states)?;
            let yes = crate::expression::select_predicate(*relation, &left, &right, nodes)?;
            bind_math(
                if yes { then_value } else { else_value },
                p,
                owner,
                nodes,
                states,
            )?
        }
        E::EventMath { function, args, .. } => {
            let a = value(&args[0], p, owner, nodes, states)?;
            let result = match function {
                F::Sqrt => {
                    if a < 0. {
                        return Err(Error::new(
                            "event_domain",
                            "event sqrt requires nonnegative input",
                        ));
                    }
                    a.sqrt()
                }
                F::Abs => a.abs(),
                F::Min => a.min(value(&args[1], p, owner, nodes, states)?),
                F::Max => a.max(value(&args[1], p, owner, nodes, states)?),
            };
            if !result.is_finite() {
                return Err(Error::new(
                    "nonfinite_arithmetic",
                    "nonfinite event arithmetic",
                ));
            }
            E::Affine {
                constant: result,
                terms: vec![],
            }
        }
        E::Operator { .. } => {
            return Err(Error::new(
                "unsupported_transient",
                "event operator read is unsupported",
            ))
        }
    })
}

pub(crate) fn bounds(e: &E, nodes: &[I], states: &[I]) -> Result<I, Error> {
    let v = match e {
        E::Affine { constant, terms } => terms.iter().fold(I::point(*constant), |sum, t| {
            sum + I::point(t.coefficient) * nodes[t.node]
        }),
        E::State { state } => states[*state],
        E::Add { left, right } => bounds(left, nodes, states)? + bounds(right, nodes, states)?,
        E::Multiply { left, right } => bounds(left, nodes, states)? * bounds(right, nodes, states)?,
        E::Divide { left, right } => {
            let a = bounds(left, nodes, states)?;
            let b = bounds(right, nodes, states)?;
            if b.lo <= 0. && b.hi >= 0. {
                return Err(Error::new(
                    "event_domain",
                    "event division denominator enclosure contains zero",
                ));
            }
            a / b
        }
        E::Power { base, exponent } => {
            let a = bounds(base, nodes, states)?;
            let mut v = I::ONE;
            for _ in 0..*exponent {
                v = v * a;
            }
            v
        }
        E::Select {
            relation,
            left,
            right,
            then_value,
            else_value,
            ..
        } => {
            let d = bounds(left, nodes, states)? - bounds(right, nodes, states)?;
            let (yes, no) = sign(*relation, d);
            if yes {
                bounds(then_value, nodes, states)?
            } else if no {
                bounds(else_value, nodes, states)?
            } else {
                return Err(Error::new(
                    "event_condition",
                    "cannot certify event expression selection",
                ));
            }
        }
        E::EventMath { function, args, .. } => {
            let a = bounds(&args[0], nodes, states)?;
            match function {
                F::Sqrt => crate::math_functions::sqrt(a)
                    .map_err(|e| Error::new("event_domain", e.message))?,
                F::Abs => I {
                    lo: if a.lo <= 0. && a.hi >= 0. {
                        0.
                    } else {
                        a.lo.abs().min(a.hi.abs())
                    },
                    hi: a.magnitude(),
                },
                F::Min | F::Max => {
                    let b = bounds(&args[1], nodes, states)?;
                    if matches!(function, F::Min) {
                        I {
                            lo: a.lo.min(b.lo),
                            hi: a.hi.min(b.hi),
                        }
                    } else {
                        I {
                            lo: a.lo.max(b.lo),
                            hi: a.hi.max(b.hi),
                        }
                    }
                }
            }
        }
        E::Operator { .. } => {
            return Err(Error::new(
                "unsupported_transient",
                "event operator read is unsupported",
            ))
        }
    };
    if !v.finite() {
        return Err(Error::new(
            "event_accuracy",
            "nonfinite event expression enclosure",
        ));
    }
    Ok(v)
}
pub(crate) fn sign(relation: Relation, v: I) -> (bool, bool) {
    match relation {
        Relation::Lt => (v.hi < 0., v.lo >= 0.),
        Relation::Le => (v.hi <= 0., v.lo > 0.),
        Relation::Gt => (v.lo > 0., v.hi <= 0.),
        Relation::Ge => (v.lo >= 0., v.hi < 0.),
    }
}
