//! Bounded expansion of independently forced voltage branches. This is a
//! substitution proof, not a fixed-point iteration over an electrical loop.
use crate::interval::Interval as I;
use crate::ir::{Error, Expression as E, Program};
use std::collections::BTreeSet;

fn unsupported() -> Error {
    Error::new(
        "unsupported_condition",
        "internal conditional voltage requires an acyclic, independently forced grounded branch",
    )
}
fn constant(x: f64) -> E {
    E::Affine {
        constant: x,
        terms: vec![],
    }
}
fn scale(x: f64, e: E) -> E {
    if x == 1. {
        e
    } else {
        E::Multiply {
            left: Box::new(constant(x)),
            right: Box::new(e),
        }
    }
}
pub(crate) fn expand(e: &E, p: &Program, driven: &[String]) -> Result<E, Error> {
    fn walk(
        e: &E,
        p: &Program,
        driven: &[String],
        active: &mut BTreeSet<usize>,
        work: &mut usize,
        depth: usize,
    ) -> Result<E, Error> {
        if depth > 64 || *work == 0 {
            return Err(Error::new(
                "condition_precision",
                "internal voltage expansion budget exhausted",
            ));
        }
        *work -= 1;
        let mut recurse = |e: &E| walk(e, p, driven, active, work, depth + 1);
        Ok(match e {
            E::Affine { constant: c, terms } => {
                let mut out = constant(*c);
                for term in terms {
                    let n = term.node;
                    if n == 0 {
                        continue;
                    }
                    let value = if driven.contains(&p.nodes[n]) {
                        E::Affine {
                            constant: 0.,
                            terms: vec![term.clone()],
                        }
                    } else {
                        if !active.insert(n) {
                            return Err(unsupported());
                        }
                        let contributions: Vec<_> = p
                            .contributions
                            .iter()
                            .filter(|c| c.positive == n || c.negative == n)
                            .collect();
                        let Some(first) = contributions.first() else {
                            return Err(unsupported());
                        };
                        if contributions.iter().any(|c| c.branch != first.branch) {
                            return Err(unsupported());
                        }
                        // V(p,n)=rhs determines either endpoint only after the
                        // other endpoint has independently been determined.
                        // Keep that reference live, including a nonzero rail.
                        // The active set rejects loops; all incident branches
                        // above must still belong to this single constraint.
                        let reference = if first.positive == n {
                            first.negative
                        } else {
                            first.positive
                        };
                        let mut value = if reference == 0 {
                            constant(0.)
                        } else {
                            walk(
                                &E::Affine {
                                    constant: 0.,
                                    terms: vec![crate::ir::Term {
                                        node: reference,
                                        coefficient: 1.,
                                    }],
                                },
                                p,
                                driven,
                                active,
                                work,
                                depth + 1,
                            )?
                        };
                        for c in contributions {
                            let sign = if c.positive == n { 1. } else { -1. };
                            let rhs = walk(&c.rhs, p, driven, active, work, depth + 1)?;
                            value = E::Add {
                                left: Box::new(value),
                                right: Box::new(scale(sign, rhs)),
                            };
                        }
                        active.remove(&n);
                        scale(term.coefficient, value)
                    };
                    out = E::Add {
                        left: Box::new(out),
                        right: Box::new(value),
                    };
                }
                out
            }
            E::Add { left, right } => E::Add {
                left: Box::new(recurse(left)?),
                right: Box::new(recurse(right)?),
            },
            E::Multiply { left, right } => E::Multiply {
                left: Box::new(recurse(left)?),
                right: Box::new(recurse(right)?),
            },
            E::Divide { left, right } => E::Divide {
                left: Box::new(recurse(left)?),
                right: Box::new(recurse(right)?),
            },
            E::Select {
                relation,
                left,
                right,
                then_value,
                else_value,
                origin,
            } => E::Select {
                relation: *relation,
                left: Box::new(recurse(left)?),
                right: Box::new(recurse(right)?),
                then_value: Box::new(recurse(then_value)?),
                else_value: Box::new(recurse(else_value)?),
                origin: origin.clone(),
            },
            E::State { .. } | E::Operator { .. } => e.clone(),
            _ => return Err(unsupported()),
        })
    }
    walk(e, p, driven, &mut BTreeSet::new(), &mut 8192, 0)
}

pub(crate) fn bounds(e: &E, nodes: &[I], states: &[I], operators: &[I]) -> Result<I, Error> {
    let get = |e| bounds(e, nodes, states, operators);
    let v = match e {
        E::Affine { constant, terms } => terms.iter().fold(I::point(*constant), |v, t| {
            v + I::point(t.coefficient) * nodes[t.node]
        }),
        E::State { state } => *states.get(*state).ok_or_else(unsupported)?,
        E::Operator { operator } => *operators.get(*operator).ok_or_else(unsupported)?,
        E::Add { left, right } => get(left)? + get(right)?,
        E::Multiply { left, right } => get(left)? * get(right)?,
        E::Divide { left, right } => {
            let b = get(right)?;
            if b.lo <= 0. && b.hi >= 0. {
                return Err(unsupported());
            }
            get(left)? / b
        }
        E::Select {
            relation,
            left,
            right,
            then_value,
            else_value,
            ..
        } => {
            let (yes, no) = crate::event_numeric::sign(*relation, get(left)? - get(right)?);
            if yes {
                get(then_value)?
            } else if no {
                get(else_value)?
            } else {
                get(then_value)?.hull(get(else_value)?)
            }
        }
        _ => return Err(unsupported()),
    };
    if !v.finite() {
        return Err(Error::new(
            "condition_precision",
            "nonfinite internal voltage enclosure",
        ));
    }
    Ok(v)
}

pub(crate) fn history_selection(e: &E, p: &Program, driven: &[String]) -> Result<(), Error> {
    fn walk(e: &E, p: &Program, driven: &[String]) -> Result<(), Error> {
        match e {
            E::Select {
                left,
                right,
                then_value,
                else_value,
                ..
            } => {
                for x in [left, right] {
                    let expanded = expand(x, p, driven)?;
                    let row = crate::affine_bounds::affine(&expanded, p)?;
                    for (k, c) in row[p.nodes.len() + p.states.len()..row.len() - 1]
                        .iter()
                        .enumerate()
                    {
                        if !c.zero()
                            && !matches!(p.operators[k], crate::ir::OperatorSpec::Transition { .. })
                        {
                            return Err(unsupported());
                        }
                    }
                }
                for x in [then_value, else_value] {
                    walk(x, p, driven)?;
                }
                Ok(())
            }
            E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
                walk(left, p, driven)?;
                walk(right, p, driven)
            }
            _ => Ok(()),
        }
    }
    walk(e, p, driven)
}

pub(crate) fn resolve(
    e: &E,
    p: &Program,
    driven: &[String],
    nodes: &[I],
    states: &[I],
    operators: &[I],
) -> Result<E, Error> {
    let recurse = |e| resolve(e, p, driven, nodes, states, operators);
    Ok(match e {
        E::Select {
            relation,
            left,
            right,
            then_value,
            else_value,
            ..
        } => {
            let left = expand(left, p, driven)?;
            let right = expand(right, p, driven)?;
            let difference = bounds(&left, nodes, states, operators)?
                - bounds(&right, nodes, states, operators)?;
            let (yes, no) = crate::event_numeric::sign(*relation, difference);
            if !(yes || no) {
                return Err(Error::new(
                    "condition_precision",
                    "internal continuous predicate is uncertain",
                ));
            }
            recurse(if yes { then_value } else { else_value })?
        }
        E::Add { left, right } => E::Add {
            left: Box::new(recurse(left)?),
            right: Box::new(recurse(right)?),
        },
        E::Multiply { left, right } => E::Multiply {
            left: Box::new(recurse(left)?),
            right: Box::new(recurse(right)?),
        },
        E::Divide { left, right } => E::Divide {
            left: Box::new(recurse(left)?),
            right: Box::new(recurse(right)?),
        },
        _ => e.clone(),
    })
}
