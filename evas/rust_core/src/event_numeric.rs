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
        E::IntegerPrimitive { .. }
        | E::IntegerRound { .. }
        | E::CheckedInteger { .. }
        | E::CheckedIndex { .. } => true,
        E::Affine { constant, terms } => terms.is_empty() && constant.fract() == 0.,
        E::State { state } => p.states[*state].kind == crate::ir::StateKind::Integer,
        E::RealBoundary { value, .. } => integral(value, p),
        E::RealBinary {
            operation,
            left,
            right,
            ..
        } => {
            !matches!(operation, crate::ir::RealOperation::Divide)
                && integral(left, p)
                && integral(right, p)
        }
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
                || !matches!(function, F::Sqrt | F::Ln) && args.iter().all(|e| integral(e, p))
        }
        _ => false,
    }
}

pub(crate) fn contains_operator(e: &E) -> bool {
    match e {
        E::ArrayRead { index, .. }
        | E::CheckedIndex { index, .. }
        | E::IntegerRound { value: index, .. }
        | E::CheckedInteger { value: index, .. } => contains_operator(index),
        E::Operator { .. } => true,
        E::EventMath { args, .. } => args.iter().any(contains_operator),
        E::RealBoundary { value, .. } => contains_operator(value),
        E::RealBinary { left, right, .. }
        | E::Add { left, right }
        | E::Multiply { left, right }
        | E::Divide { left, right } => contains_operator(left) || contains_operator(right),
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
        E::RealCall { .. }
        | E::UnsupportedSystemCall { .. }
        | E::RealBinary { .. }
        | E::RealBoundary { .. }
        | E::RealLocal { .. } => true,
        E::IntegerPrimitive { .. }
        | E::ArrayRead { .. }
        | E::IntegerRound { .. }
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

pub(crate) fn contains_legacy_math(e: &E) -> bool {
    match e {
        E::RealBinary { left, right, .. } => {
            contains_legacy_math(left) || contains_legacy_math(right)
        }
        E::RealBoundary { value, .. } => contains_legacy_math(value),
        E::RealLocal { .. } => false,
        E::IntegerPrimitive { .. }
        | E::ArrayRead { .. }
        | E::IntegerRound { .. }
        | E::CheckedInteger { .. }
        | E::CheckedIndex { .. }
        | E::EventMath { .. } => true,
        E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
            contains_legacy_math(left) || contains_legacy_math(right)
        }
        E::Power { base, .. } => contains_legacy_math(base),
        E::Select {
            left,
            right,
            then_value,
            else_value,
            ..
        } => [left, right, then_value, else_value]
            .iter()
            .any(|e| contains_legacy_math(e)),
        _ => false,
    }
}

pub(crate) fn dependencies(e: &E, p: &Program, owner: &str) -> Result<AffineState, Error> {
    fn leaves(e: &E, out: &mut Vec<E>, p: &Program, seen: &mut std::collections::BTreeSet<usize>) {
        match e {
            E::RealLocal { binding } => {
                if seen.insert(*binding) {
                    for value in crate::procedure::binding_values(p, *binding) {
                        leaves(value, out, p, seen);
                    }
                }
            }
            E::RealBoundary { value, .. } => leaves(value, out, p, seen),
            E::RealBinary { left, right, .. }
            | E::Add { left, right }
            | E::Multiply { left, right }
            | E::Divide { left, right } => {
                leaves(left, out, p, seen);
                leaves(right, out, p, seen);
            }
            E::ArrayRead { states, index, .. } => {
                leaves(index, out, p, seen);
                out.extend(states.iter().map(|&state| E::State { state }));
            }
            E::CheckedIndex { index, .. }
            | E::IntegerRound { value: index, .. }
            | E::CheckedInteger { value: index, .. } => leaves(index, out, p, seen),
            E::Power { base, .. } => leaves(base, out, p, seen),
            E::Select {
                left,
                right,
                then_value,
                else_value,
                ..
            } => {
                for e in [left, right, then_value, else_value] {
                    leaves(e, out, p, seen);
                }
            }
            E::IntegerPrimitive { args, .. } => {
                let mut states = Vec::new();
                crate::integer_primitive::states(args, &mut states);
                out.extend(states.into_iter().map(|state| E::State { state }));
            }
            E::EventMath { args, .. } => {
                for e in args {
                    leaves(e, out, p, seen);
                }
            }
            _ => out.push(e.clone()),
        }
    }
    validate(e, p, owner)?;
    let mut refs = Vec::new();
    leaves(e, &mut refs, p, &mut std::collections::BTreeSet::new());
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
        E::RealCall { origin, .. } | E::UnsupportedSystemCall { origin, .. } => {
            check_real_origin(origin, owner)?;
            crate::procedure::call_children(e, &mut |e| validate(e, p, owner))?;
        }
        E::RealBinary {
            left,
            right,
            origin,
            ..
        } => {
            check_real_origin(origin, owner)?;
            validate(left, p, owner)?;
            validate(right, p, owner)?;
        }
        E::RealBoundary { value, origin, .. } => {
            check_real_origin(origin, owner)?;
            validate(value, p, owner)?;
        }
        E::RealLocal { binding } => {
            if p.real_bindings
                .get(*binding)
                .is_none_or(|b| b.origin.instance != owner)
            {
                return Err(Error::new("invalid_ir", "real local owner mismatch"));
            }
        }
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
        E::IntegerRound { value, origin } => {
            if origin.instance != owner
                || origin.source.is_empty()
                || origin.line == 0
                || origin.column == 0
                || !origin.valid_expansion()
            {
                return Err(Error::new(
                    "invalid_ir",
                    "invalid integer conversion origin",
                ));
            }
            if !matches!(value.as_ref(), E::Affine { constant, terms } if *constant == 0. && terms.len() <= 2 && terms.iter().all(|t| t.coefficient == 1. || t.coefficient == -1.) && (terms.len() < 2 || terms[0].node != terms[1].node && terms[0].coefficient == -terms[1].coefficient))
            {
                return Err(Error::new(
                    "invalid_ir",
                    "integer conversion requires original direct input probe",
                ));
            }
            validate(value, p, owner)?;
        }
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
        E::Operator { operator } => {
            if p.procedures.is_empty()
                || !matches!(p.operators.get(*operator),Some(crate::ir::OperatorSpec::Math{origin,..}|crate::ir::OperatorSpec::Sin{origin,..}) if origin.instance==owner)
            {
                return Err(Error::new(
                    "unsupported_transient",
                    "operator calls are only allowed in contributions",
                ));
            }
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
        E::RealBinary {
            operation,
            left,
            right,
            ..
        } => crate::real_expression::literal(crate::real_expression::point(
            *operation,
            self::value(left, p, owner, nodes, states)?,
            self::value(right, p, owner, nodes, states)?,
        )?),
        E::RealBoundary { value, .. } => {
            crate::real_expression::literal(self::value(value, p, owner, nodes, states)?)
        }
        E::RealCall { .. } | E::UnsupportedSystemCall { .. } | E::RealLocal { .. } => {
            return Err(Error::new(
                "invalid_ir",
                "unexecuted real call/local requires its source frame",
            ))
        }
        E::Forcing { .. } => {
            return Err(Error::new(
                "unsupported_forcing_scope",
                "forcing marker requires its owning independent component dispatcher",
            ))
        }
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
        E::IntegerRound { .. } => {
            return Err(Error::new(
                "event_condition",
                "integer conversion requires bound source proof owner",
            ))
        }
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
                F::InternalSin
                | F::InternalCos
                | F::InternalExp
                | F::InternalLn
                | F::InternalSqrt
                | F::InternalTanh => crate::operators::Function::from_internal(*function)
                    .unwrap()
                    .value(a),
                F::Sqrt => {
                    if a < 0. {
                        return Err(Error::new(
                            "event_domain",
                            "event sqrt requires nonnegative input",
                        ));
                    }
                    a.sqrt()
                }
                F::Ln => {
                    if a.is_nan() || a <= 0. {
                        return Err(Error::new(
                            "event_domain",
                            "event ln requires strictly positive input",
                        ));
                    }
                    a.ln()
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

pub(crate) fn value_with_proofs(
    e: &E,
    p: &Program,
    owner: &str,
    nodes: &[f64],
    states: &[f64],
    context: Option<&crate::event_value_proof::Context<'_>>,
) -> Result<f64, Error> {
    let Some(w) = context.and_then(|c| c.floor_work()) else {
        return value(e, p, owner, nodes, states);
    };
    if !crate::event_floor::contains_charged(e, w)? {
        return value(e, p, owner, nodes, states);
    }
    if let Some(w) = context.and_then(|c| c.floor_work()) {
        crate::event_floor::charge(w, states.len() + nodes.len() + 2, "floor_source_copy")?;
    }
    let state_bounds = states.iter().copied().map(I::point).collect::<Vec<_>>();
    let local = crate::event_value_proof::LocalState::try_with_context(&state_bounds, context)?;
    let node_bounds = nodes.iter().copied().map(I::point).collect::<Vec<_>>();
    let resolved = crate::event_floor::resolve(e, &node_bounds, &local)?;
    if let Some(w) = local.floor_work() {
        // Existing affine replay builds dense node/state rows. Serialized tree
        // length bounds node count; reserve before its traversal/allocations.
        let size = crate::event_floor::encoded_size(&resolved, w)?;
        crate::event_floor::charge(
            w,
            8 * size * (nodes.len() + states.len() + 1).saturating_pow(2),
            "floor_source_dense",
        )?;
    }
    value(&resolved, p, owner, nodes, states)
}

pub(crate) fn bounds(e: &E, nodes: &[I], states: &[I]) -> Result<I, Error> {
    bounds_in(e, nodes, states, None)
}
pub(crate) fn bounds_with_proofs(
    e: &E,
    nodes: &[I],
    states: &crate::event_value_proof::LocalState,
) -> Result<I, Error> {
    let has_floor = if let Some(w) = states.floor_work() {
        crate::event_floor::contains_charged(e, w)?
    } else {
        false
    };
    if has_floor {
        let resolved = crate::event_floor::resolve(e, nodes, states)?;
        bounds_in(&resolved, nodes, states, Some(states))
    } else {
        bounds_in(e, nodes, states, Some(states))
    }
}
fn bounds_in(
    e: &E,
    nodes: &[I],
    states: &[I],
    proofs: Option<&crate::event_value_proof::LocalState>,
) -> Result<I, Error> {
    // This interval visit is distinct from optional rational replay below.
    // Keep old unowned/floor-only callers unchanged and borrow a paid caller's
    // original sticky ledger before inspecting each actually reached node.
    let work = proofs.and_then(|local| local.history_work());
    if let Some(w) = work {
        w.step()?;
    }
    let v = match e {
        E::RealBinary {
            operation,
            left,
            right,
            ..
        } => crate::real_expression::binary_interval(
            *operation,
            bounds_in(left, nodes, states, proofs)?,
            bounds_in(right, nodes, states, proofs)?,
            work,
        )?,
        E::RealBoundary { value, .. } => {
            crate::real_expression::interval(bounds_in(value, nodes, states, proofs)?, work)?
        }
        E::RealCall { .. } | E::UnsupportedSystemCall { .. } | E::RealLocal { .. } => {
            return Err(Error::new(
                "invalid_ir",
                "unexecuted real call/local requires its source frame",
            ))
        }
        E::Forcing { .. } => {
            return Err(Error::new(
                "unsupported_forcing_scope",
                "forcing marker requires its owning independent component dispatcher",
            ))
        }
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
        E::IntegerRound { .. } => {
            return Err(Error::new(
                "event_condition",
                "integer conversion requires bound source proof owner",
            ))
        }
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
        E::Affine { constant, terms } => {
            let mut sum = I::point(*constant);
            for t in terms {
                if let Some(w) = work {
                    w.step()?;
                }
                sum = sum + I::point(t.coefficient) * nodes[t.node];
            }
            sum
        }
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
                        let proved = if let Some(local) = proofs {
                            if local.history_work().is_some() {
                                match local.try_value(e, nodes)? {
                                    Some(v) => local.try_enclosure(&v)?,
                                    None => None,
                                }
                            } else {
                                local
                                    .value(e, nodes)
                                    .as_ref()
                                    .and_then(crate::exact_source::enclosure)
                            }
                        } else {
                            None
                        };
                        proved
                            .filter(|v| v.lo == v.hi && floored.lo <= v.lo && v.hi <= floored.hi)
                            .ok_or_else(|| {
                                Error::new(
                                    "event_condition",
                                    "cannot certify a single native floor bin",
                                )
                            })?
                    }
                }
                F::InternalSin
                | F::InternalCos
                | F::InternalExp
                | F::InternalLn
                | F::InternalSqrt
                | F::InternalTanh => crate::operators::Function::from_internal(*function)
                    .unwrap()
                    .bounds(a)?,
                F::Sqrt => crate::math_functions::sqrt(a)
                    .map_err(|e| Error::new("event_domain", e.message))?,
                // The whole argument enclosure must be strictly positive; a
                // positive representative cannot certify a straddling box.
                F::Ln => {
                    // NaN and non-positive lower bounds both fail here.
                    if a.lo.partial_cmp(&0.) != Some(std::cmp::Ordering::Greater) {
                        return Err(Error::new(
                            "event_domain",
                            "event ln requires strictly positive input enclosure",
                        ));
                    }
                    crate::math_functions::ln(a)
                        .map_err(|e| Error::new("event_domain", e.message))?
                }
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

pub(crate) fn checked_integer(value: I, origin: &crate::ir::Origin) -> Result<I, Error> {
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

/// Monotonic round-to-nearest, ties away from zero, on the complete original enclosure.
pub(crate) fn nearest_box(v: I, origin: &crate::ir::Origin) -> Result<I, Error> {
    if !v.finite() || v.lo > v.hi {
        return Err(Error::new(
            "nonfinite_arithmetic",
            format!(
                "integer conversion requires finite ordered input at {}",
                origin.label()
            ),
        ));
    }
    let a = v.lo.round();
    let b = v.hi.round();
    if a < f64::from(i32::MIN) || b > f64::from(i32::MAX) {
        return Err(Error::new(
            "integer_range",
            format!(
                "original real-to-integer result exceeds signed32 before clamp at {}",
                origin.label()
            ),
        ));
    }
    if a != b {
        return Err(Error::new(
            "event_condition",
            format!(
                "original real-to-integer enclosure spans multiple rounding bins at {}",
                origin.label()
            ),
        ));
    }
    Ok(I::point(a))
}

#[cfg(test)]
mod paid_bounds_visit_tests {
    use super::*;
    use crate::event_value_proof::{history, LocalState};
    use crate::transition_source_plan::Work;
    use serde_json::json;

    fn scalar(value: f64) -> serde_json::Value {
        json!({"op":"affine","constant":value,"terms":[]})
    }
    fn sum() -> E {
        serde_json::from_value(json!({"op":"add",
            "left":{"op":"state","state":0},
            "right":{"op":"affine","constant":0.,
                "terms":[{"node":1,"coefficient":1.}]}}))
        .unwrap()
    }
    fn local(work: &Work) -> LocalState {
        history::points(&[I::point(3.)], work).unwrap()
    }

    #[test]
    fn paid_interval_visits_charge_each_node_and_affine_term() {
        let work = Work::default();
        let local = local(&work);
        assert!(work.same_owner(local.history_work().unwrap()));
        let before = work.spent();
        // Add, State, Affine and its single term are four distinct visits.
        let value = bounds_with_proofs(&sum(), &[I::ZERO, I::point(2.)], &local).unwrap();
        assert_eq!(value, I::point(5.));
        assert_eq!(work.spent() - before, 4);
        let plain = LocalState::new(&[I::point(3.)]);
        let before = work.spent();
        assert_eq!(
            bounds_with_proofs(&sum(), &[I::ZERO, I::point(2.)], &plain).unwrap(),
            I::point(5.)
        );
        assert_eq!(
            work.spent(),
            before,
            "unowned ordinary evaluation keeps its old boundary"
        );
    }

    #[test]
    fn same_owner_term_exhaustion_stays_failed_for_two_retries() {
        // Scaled budget control, not a claim of natural production-1e9 exhaustion.
        let sizing = Work::default();
        let _ = local(&sizing);
        let setup = sizing.spent();
        let work = Work::limited([128, 8192, setup + 3]);
        let local = local(&work);
        assert_eq!(work.spent(), setup);
        assert!(work.same_owner(local.history_work().unwrap()));
        for attempt in 0..3 {
            let before = work.spent();
            let error = bounds_with_proofs(&sum(), &[I::ZERO, I::point(2.)], &local).unwrap_err();
            assert_eq!(error.kind, "step_budget");
            assert!(work.spent() > before);
            assert_eq!(local[0], I::point(3.));
            if attempt == 0 {
                assert_eq!(
                    work.spent() - before,
                    4,
                    "failure occurs before the unpaid term arithmetic"
                );
            }
        }
        assert!(
            history::points(&[I::point(3.)], &work).is_err(),
            "recreating a local proof frame cannot reset the request owner"
        );
    }

    #[test]
    fn paid_select_charges_reached_branch_without_visiting_the_other_arm() {
        let work = Work::default();
        let local = local(&work);
        let expression: E = serde_json::from_value(json!({"op":"select","relation":"gt",
            "left":scalar(1.),"right":scalar(0.),"then_value":scalar(7.),
            "else_value":{"op":"divide","left":scalar(1.),"right":scalar(0.)},
            "origin":{"source":"paid-bounds.va","line":1,"column":1,"instance":"dut"}}))
        .unwrap();
        let before = work.spent();
        assert_eq!(
            bounds_with_proofs(&expression, &[], &local).unwrap(),
            I::point(7.)
        );
        assert_eq!(
            work.spent() - before,
            4,
            "Select, two predicates, selected value only"
        );
    }
}

#[cfg(test)]
mod sampled_math_domain_tests {
    use super::*;
    use serde_json::json;

    fn math(function: &str) -> E {
        serde_json::from_value(json!({"op":"event_math","function":function,
            "args":[{"op":"affine","constant":0.,"terms":[{"node":1,"coefficient":1.}]}],
            "origin":{"source":"m.va","line":1,"column":1,"instance":"M"}}))
        .unwrap()
    }

    #[test]
    fn ln_and_sqrt_enclose_positive_boxes() {
        let x = I { lo: 2., hi: 4. };
        let ln = bounds(&math("ln"), &[I::ZERO, x], &[]).unwrap();
        assert!(ln.lo <= 2f64.ln() && 4f64.ln() <= ln.hi && ln.hi - ln.lo < 0.7);
        let sqrt = bounds(&math("sqrt"), &[I::ZERO, x], &[]).unwrap();
        assert!(sqrt.lo <= 2f64.sqrt() && sqrt.hi >= 2.);
    }

    #[test]
    fn straddling_or_zero_boxes_are_domain_errors_despite_valid_nominal() {
        // The representative 0.25 is valid; the enclosure is not.
        let x = I {
            lo: -0.25,
            hi: 0.75,
        };
        for function in ["ln", "sqrt"] {
            let error = bounds(&math(function), &[I::ZERO, x], &[]).unwrap_err();
            assert_eq!(error.kind, "event_domain", "{function}");
        }
        let error = bounds(&math("ln"), &[I::ZERO, I { lo: 0., hi: 1. }], &[]).unwrap_err();
        assert_eq!(error.kind, "event_domain");
        // sqrt admits an exact zero endpoint; ln does not.
        assert_eq!(
            bounds(&math("sqrt"), &[I::ZERO, I { lo: 0., hi: 0. }], &[]).unwrap(),
            I::ZERO
        );
    }
}

fn check_real_origin(origin: &crate::ir::Origin, owner: &str) -> Result<(), Error> {
    if origin.instance != owner
        || origin.source.is_empty()
        || origin.line == 0
        || origin.column == 0
        || !origin.valid_expansion()
    {
        Err(Error::new("invalid_ir", "invalid real expression origin"))
    } else {
        Ok(())
    }
}
