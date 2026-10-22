//! Pure event arithmetic. No operator history and no accepted-state mutation.
use crate::events::{affine, AffineState};
use crate::interval::Interval as I;
use crate::ir::{Error, EventMathFunction as F, Expression as E, Program, Relation};

pub(crate) fn integral(e: &E, p: &Program) -> bool {
    match e {
        E::ArrayRead { states, .. } => states
            .first()
            .and_then(|i| p.states.get(*i))
            .is_some_and(|s| s.kind == crate::ir::StateKind::Integer),
        E::IntegerPrimitive { .. } | E::CheckedInteger { .. } | E::CheckedIndex { .. } => true,
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
            matches!(function, F::Floor)
                || !matches!(function, F::Sqrt) && args.iter().all(|e| integral(e, p))
        }
        _ => false,
    }
}

pub(crate) fn contains_operator(e: &E) -> bool {
    match e {
        E::ArrayRead { index, .. }
        | E::CheckedIndex { index, .. }
        | E::CheckedInteger { value: index, .. } => contains_operator(index),
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
        E::IntegerPrimitive { .. }
        | E::ArrayRead { .. }
        | E::CheckedInteger { .. }
        | E::CheckedIndex { .. }
        | E::EventMath { .. } => true,
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
            E::ArrayRead { states, index, .. } => {
                leaves(index, out);
                out.extend(states.iter().map(|&state| E::State { state }));
            }
            E::CheckedIndex { index, .. } | E::CheckedInteger { value: index, .. } => {
                leaves(index, out)
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
            E::IntegerPrimitive { args, .. } => {
                let mut states = Vec::new();
                crate::integer_primitive::states(args, &mut states);
                out.extend(states.into_iter().map(|state| E::State { state }));
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
        E::ArrayRead {
            states,
            index,
            first,
            last,
            origin,
        } => validate_array(states, index, *first, *last, origin, p, owner)?,
        E::IntegerPrimitive {
            function,
            args,
            origin,
        } => crate::integer_primitive::validate(*function, args, origin, p, owner)?,
        E::CheckedInteger { value, origin } => {
            if origin.instance != owner
                || origin.source.is_empty()
                || origin.line == 0
                || origin.column == 0
                || !origin.valid_expansion()
            {
                return Err(Error::new("invalid_ir", "invalid checked integer origin"));
            }
            validate(value, p, owner)?;
            if !integral(value, p) {
                return Err(Error::new(
                    "invalid_ir",
                    "checked integer requires integral arithmetic",
                ));
            }
        }
        E::CheckedIndex {
            index,
            first,
            last,
            origin,
        } => {
            if first > last
                || origin.instance != owner
                || origin.source.is_empty()
                || origin.line == 0
                || origin.column == 0
                || !origin.valid_expansion()
            {
                return Err(Error::new(
                    "invalid_ir",
                    "invalid checked array index origin/bounds",
                ));
            }
            validate(index, p, owner)?;
            if !integral(index, p) {
                return Err(Error::new(
                    "invalid_ir",
                    "checked array index must have integer type",
                ));
            }
        }
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
                || !origin.valid_expansion()
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
        E::ArrayRead {
            states: index_states,
            index,
            first,
            last,
            origin,
        } => {
            let v = self::value(index, p, owner, nodes, states)?;
            checked_index(I::point(v), *first, *last, origin)?;
            E::Affine {
                constant: states[index_states[(v - f64::from(*first)) as usize]],
                terms: vec![],
            }
        }
        E::IntegerPrimitive {
            function,
            args,
            origin,
        } => E::Affine {
            constant: f64::from(crate::integer_primitive::evaluate(
                *function,
                args,
                origin,
                &mut |state| crate::integer_primitive::point(I::point(states[state]), origin),
                &mut || Ok(()),
            )?),
            terms: vec![],
        },
        E::CheckedInteger { value, origin } => {
            let v = self::value(value, p, owner, nodes, states)
                .map_err(|e| checked_error(e, "integer_range", origin))?;
            checked_integer(I::point(v), origin)?;
            E::Affine {
                constant: v,
                terms: vec![],
            }
        }
        E::CheckedIndex {
            index,
            first,
            last,
            origin,
        } => {
            let v = value(index, p, owner, nodes, states)
                .map_err(|e| checked_error(e, "array_index_range", origin))?;
            checked_index(I::point(v), *first, *last, origin)?;
            E::Affine {
                constant: v,
                terms: vec![],
            }
        }
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
                F::Floor => a.floor(),
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
    bounds_in(e, nodes, states, None)
}
pub(crate) fn bounds_with_proofs(
    e: &E,
    nodes: &[I],
    states: &crate::event_value_proof::LocalState,
) -> Result<I, Error> {
    bounds_in(e, nodes, states, Some(states))
}
fn bounds_in(
    e: &E,
    nodes: &[I],
    states: &[I],
    proofs: Option<&crate::event_value_proof::LocalState>,
) -> Result<I, Error> {
    let v = match e {
        E::ArrayRead {
            states: slots,
            index,
            first,
            last,
            origin,
        } => {
            let v = checked_index(
                bounds_in(index, nodes, states, proofs)
                    .map_err(|e| checked_error(e, "array_index_range", origin))?,
                *first,
                *last,
                origin,
            )?;
            states[slots[(v.lo - f64::from(*first)) as usize]]
        }
        E::IntegerPrimitive {
            function,
            args,
            origin,
        } => I::point(f64::from(crate::integer_primitive::evaluate(
            *function,
            args,
            origin,
            &mut |state| crate::integer_primitive::point(states[state], origin),
            &mut || Ok(()),
        )?)),
        E::CheckedInteger { value, origin } => checked_integer(
            bounds_in(value, nodes, states, proofs)
                .map_err(|e| checked_error(e, "integer_range", origin))?,
            origin,
        )?,
        E::CheckedIndex {
            index,
            first,
            last,
            origin,
        } => checked_index(
            bounds_in(index, nodes, states, proofs)
                .map_err(|e| checked_error(e, "array_index_range", origin))?,
            *first,
            *last,
            origin,
        )?,
        E::Affine { constant, terms } => terms.iter().fold(I::point(*constant), |sum, t| {
            sum + I::point(t.coefficient) * nodes[t.node]
        }),
        E::State { state } => states[*state],
        E::Add { left, right } => {
            bounds_in(left, nodes, states, proofs)? + bounds_in(right, nodes, states, proofs)?
        }
        E::Multiply { left, right } => {
            bounds_in(left, nodes, states, proofs)? * bounds_in(right, nodes, states, proofs)?
        }
        E::Divide { left, right } => {
            let a = bounds_in(left, nodes, states, proofs)?;
            let b = bounds_in(right, nodes, states, proofs)?;
            if b.lo <= 0. && b.hi >= 0. {
                return Err(Error::new(
                    "event_domain",
                    "event division denominator enclosure contains zero",
                ));
            }
            a / b
        }
        E::Power { base, exponent } => {
            let a = bounds_in(base, nodes, states, proofs)?;
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
            let d =
                bounds_in(left, nodes, states, proofs)? - bounds_in(right, nodes, states, proofs)?;
            let (yes, no) = sign(*relation, d);
            if yes {
                bounds_in(then_value, nodes, states, proofs)?
            } else if no {
                bounds_in(else_value, nodes, states, proofs)?
            } else {
                return Err(Error::new(
                    "event_condition",
                    "cannot certify event expression selection",
                ));
            }
        }
        E::EventMath { function, args, .. } => {
            let a = bounds_in(&args[0], nodes, states, proofs)?;
            match function {
                F::Floor => {
                    let floored = I {
                        lo: a.lo.floor(),
                        hi: a.hi.floor(),
                    };
                    if floored.lo == floored.hi {
                        floored
                    } else {
                        proofs
                            .and_then(|s| s.value(e, nodes))
                            .as_ref()
                            .and_then(crate::exact_source::enclosure)
                            .filter(|v| v.lo == v.hi && floored.lo <= v.lo && v.hi <= floored.hi)
                            .ok_or_else(|| {
                                Error::new(
                                    "event_condition",
                                    "cannot certify a single native floor bin",
                                )
                            })?
                    }
                }
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
                    let b = bounds_in(&args[1], nodes, states, proofs)?;
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

pub(crate) fn checked_index(
    value: I,
    first: i32,
    last: i32,
    origin: &crate::ir::Origin,
) -> Result<I, Error> {
    if !value.finite()
        || value.lo != value.hi
        || value.lo.fract() != 0.
        || value.lo < f64::from(first)
        || value.hi > f64::from(last)
    {
        return Err(Error::new(
            "array_index_range",
            format!(
                "array index [{:e},{:e}] must be integral in [{first},{last}] at {}",
                value.lo,
                value.hi,
                origin.label()
            ),
        ));
    }
    Ok(value)
}

fn checked_integer(value: I, origin: &crate::ir::Origin) -> Result<I, Error> {
    checked_index(value, i32::MIN, i32::MAX, origin)
        .map_err(|e| Error::new("integer_range", e.message))
}

pub(crate) fn validate_array(
    slots: &[usize],
    index: &E,
    first: i32,
    last: i32,
    origin: &crate::ir::Origin,
    p: &Program,
    owner: &str,
) -> Result<(), Error> {
    let invalid = || Error::new("invalid_ir", "invalid event array mapping/index/origin");
    if first > last
        || slots.len() as i64 != i64::from(last) - i64::from(first) + 1
        || slots.is_empty()
        || origin.instance != owner
        || origin.source.is_empty()
        || origin.line == 0
        || origin.column == 0
        || !origin.valid_expansion()
    {
        return Err(invalid());
    }
    let mut unique = std::collections::BTreeSet::new();
    let first_state = p.states.get(slots[0]).ok_or_else(invalid)?;
    for i in slots {
        let state = p.states.get(*i).ok_or_else(invalid)?;
        if state.instance != owner || state.kind != first_state.kind || !unique.insert(*i) {
            return Err(invalid());
        }
    }
    validate(index, p, owner)?;
    if !integral(index, p) {
        return Err(invalid());
    }
    Ok(())
}

fn checked_error(e: Error, kind: &'static str, origin: &crate::ir::Origin) -> Error {
    if e.kind == "nonfinite_arithmetic"
        || (e.kind == "event_accuracy" && e.message.contains("nonfinite"))
    {
        Error::new(kind, format!("{} at {}", e.message, origin.label()))
    } else {
        e
    }
}
