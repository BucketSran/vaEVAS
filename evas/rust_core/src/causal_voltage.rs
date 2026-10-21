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
fn boxed_paid(e: E, work: Option<&crate::transition_source_plan::Work>) -> Result<Box<E>, Error> {
    if let Some(w) = work {
        w.debit(2, 1)?;
    }
    Ok(Box::new(e))
}
fn scale_paid(
    x: f64,
    e: E,
    work: Option<&crate::transition_source_plan::Work>,
) -> Result<E, Error> {
    if x == 1. {
        return Ok(e);
    }
    Ok(E::Multiply {
        left: boxed_paid(constant(x), work)?,
        right: boxed_paid(e, work)?,
    })
}
pub(crate) fn expand(e: &E, p: &Program, driven: &[String]) -> Result<E, Error> {
    expand_metered(e, p, driven, None)
}
pub(crate) fn expand_paid(
    e: &E,
    p: &Program,
    driven: &[String],
    paid: &crate::transition_source_plan::Work,
) -> Result<E, Error> {
    expand_metered(e, p, driven, Some(paid))
}
fn expand_metered(
    e: &E,
    p: &Program,
    driven: &[String],
    paid: Option<&crate::transition_source_plan::Work>,
) -> Result<E, Error> {
    fn walk(
        e: &E,
        p: &Program,
        driven: &[String],
        active: &mut BTreeSet<usize>,
        work: &mut usize,
        depth: usize,
        paid: Option<&crate::transition_source_plan::Work>,
    ) -> Result<E, Error> {
        if let Some(w) = paid {
            w.step()?;
        }

        if depth > 64 || *work == 0 {
            return Err(Error::new(
                "condition_precision",
                "internal voltage expansion budget exhausted",
            ));
        }
        *work -= 1;
        let mut recurse = |e: &E| walk(e, p, driven, active, work, depth + 1, paid);
        Ok(match e {
            E::Affine { constant: c, terms } => {
                let mut out = constant(*c);
                for term in terms {
                    if let Some(w) = paid {
                        w.step()?;
                    }
                    let n = term.node;
                    if n == 0 {
                        continue;
                    }
                    let is_driven = if let Some(w) = paid {
                        let mut found = false;
                        for name in driven {
                            w.step()?;
                            w.debit(2, name.len().min(p.nodes[n].len()) as u64)?;
                            if name == &p.nodes[n] {
                                found = true;
                                break;
                            }
                        }
                        found
                    } else {
                        driven.contains(&p.nodes[n])
                    };
                    let value = if is_driven {
                        if let Some(w) = paid {
                            w.debit(2, 2)?;
                        }
                        E::Affine {
                            constant: 0.,
                            terms: vec![term.clone()],
                        }
                    } else {
                        if let Some(w) = paid {
                            w.debit(2, 1)?;
                        }
                        if !active.insert(n) {
                            return Err(unsupported());
                        }
                        let mut contributions = Vec::new();
                        for c in &p.contributions {
                            if let Some(w) = paid {
                                w.step()?;
                            }
                            if c.positive == n || c.negative == n {
                                if let Some(w) = paid {
                                    w.debit(2, 1)?;
                                }
                                contributions.push(c);
                            }
                        }
                        let Some(first) = contributions.first() else {
                            return Err(unsupported());
                        };
                        for c in &contributions {
                            if let Some(w) = paid {
                                w.step()?;
                                w.debit(
                                    2,
                                    (c.branch.instance.len()
                                        + c.branch.local_positive.len()
                                        + c.branch.local_negative.len())
                                        as u64,
                                )?;
                            }
                            if c.branch != first.branch {
                                return Err(unsupported());
                            }
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
                            if let Some(w) = paid {
                                w.debit(2, 2)?;
                            }
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
                                paid,
                            )?
                        };
                        for c in contributions {
                            let sign = if c.positive == n { 1. } else { -1. };
                            let rhs = walk(&c.rhs, p, driven, active, work, depth + 1, paid)?;
                            value = E::Add {
                                left: boxed_paid(value, paid)?,
                                right: boxed_paid(scale_paid(sign, rhs, paid)?, paid)?,
                            };
                        }
                        active.remove(&n);
                        scale_paid(term.coefficient, value, paid)?
                    };
                    out = E::Add {
                        left: boxed_paid(out, paid)?,
                        right: boxed_paid(value, paid)?,
                    };
                }
                out
            }
            E::Add { left, right } => E::Add {
                left: boxed_paid(recurse(left)?, paid)?,
                right: boxed_paid(recurse(right)?, paid)?,
            },
            E::Multiply { left, right } => E::Multiply {
                left: boxed_paid(recurse(left)?, paid)?,
                right: boxed_paid(recurse(right)?, paid)?,
            },
            E::Divide { left, right } => E::Divide {
                left: boxed_paid(recurse(left)?, paid)?,
                right: boxed_paid(recurse(right)?, paid)?,
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
                left: boxed_paid(recurse(left)?, paid)?,
                right: boxed_paid(recurse(right)?, paid)?,
                then_value: boxed_paid(recurse(then_value)?, paid)?,
                else_value: boxed_paid(recurse(else_value)?, paid)?,
                origin: {
                    if let Some(w) = paid {
                        w.debit(2, (4 + origin.source.len() + origin.instance.len()) as u64)?;
                        for (label, _) in &origin.expansion {
                            w.step()?;
                            w.debit(2, (label.len() + 1) as u64)?;
                        }
                    }
                    origin.clone()
                },
            },
            E::State { .. } | E::Operator { .. } => e.clone(),
            _ => return Err(unsupported()),
        })
    }
    walk(e, p, driven, &mut BTreeSet::new(), &mut 8192, 0, paid)
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
