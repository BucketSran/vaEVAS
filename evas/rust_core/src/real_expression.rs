//! Materialization of binary64 program values. Physical roots remain elsewhere.
use crate::interval::Interval as I;
use crate::ir::{Error, Expression as E, RealOperation};
use crate::real_rounding::{self, Fault, Image, Op};

pub(crate) fn operation(op: RealOperation) -> Op {
    match op {
        RealOperation::Add => Op::Add,
        RealOperation::Subtract => Op::Subtract,
        RealOperation::Multiply => Op::Multiply,
        RealOperation::Divide => Op::Divide,
    }
}
pub(crate) fn fault<T: std::fmt::Debug>(error: Fault<T>) -> Error {
    // Overflow is a nonfinite result of finite operands. Division by zero
    // stays real_arithmetic; callers already lock that kind.
    let kind = match &error {
        Fault::Overflow | Fault::NonFinite => "nonfinite_arithmetic",
        _ => "real_arithmetic",
    };
    Error::new(kind, format!("program-real arithmetic: {error:?}"))
}
pub(crate) fn literal(value: f64) -> E {
    E::Affine {
        constant: value,
        terms: Vec::new(),
    }
}
pub(crate) fn point(op: RealOperation, a: f64, b: f64) -> Result<f64, Error> {
    real_rounding::point(operation(op), a, b).map_err(fault)
}
pub(crate) fn constant(e: &E) -> Option<f64> {
    match e {
        E::Affine { constant, terms } if terms.is_empty() => Some(*constant),
        E::RealBoundary { value, .. } => constant(value),
        E::RealBinary {
            operation,
            left,
            right,
            ..
        } => point(*operation, constant(left)?, constant(right)?).ok(),
        _ => None,
    }
}
/// A consumer without a procedure frame reads only closed binary64 values;
/// constant aliases are inlined before (canonical.rs). Anything else in valid
/// IR is a typed capability limit of that consumer, not invalid IR (H1).
pub(crate) fn materialized(e: &E) -> Result<E, Error> {
    constant(e).map(literal).ok_or_else(|| {
        let at = match e {
            E::RealBinary { origin, .. }
            | E::RealBoundary { origin, .. }
            | E::RealCall { origin, .. }
            | E::UnsupportedSystemCall { origin, .. } => format!(" at {}", origin.label()),
            _ => String::new(),
        };
        Error::new(
            "unsupported_operator",
            format!("procedure-bound real value{at} requires its procedure frame"),
        )
    })
}
/// The same refusal for one binding, naming it; an index outside the
/// binding table stays invalid IR.
pub(crate) fn unbound_local(binding: usize, p: &crate::ir::Program) -> Error {
    match p.real_bindings.get(binding) {
        Some(b) => Error::new(
            "unsupported_operator",
            format!(
                "procedure-bound real {} at {} requires its procedure frame",
                b.name,
                b.origin.label()
            ),
        ),
        None => Error::new("invalid_ir", "real local index out of range"),
    }
}
/// True when an affine reader would need the procedure frame: a local, a
/// call, or rounded arithmetic that is not a closed binary64 constant.
pub(crate) fn needs_frame(e: &E) -> bool {
    match e {
        E::RealLocal { .. } | E::RealCall { .. } | E::UnsupportedSystemCall { .. } => true,
        E::RealBinary { .. } | E::RealBoundary { .. } => constant(e).is_none(),
        E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
            needs_frame(left) || needs_frame(right)
        }
        E::Power { base, .. } => needs_frame(base),
        E::Select {
            left,
            right,
            then_value,
            else_value,
            ..
        } => [left, right, then_value, else_value]
            .iter()
            .any(|e| needs_frame(e)),
        E::EventMath { args, .. } => args.iter().any(needs_frame),
        E::Forcing { value, .. }
        | E::IntegerRound { value, .. }
        | E::CheckedInteger { value, .. } => needs_frame(value),
        E::CheckedIndex { index, .. } | E::ArrayRead { index, .. } => needs_frame(index),
        E::IntegerPrimitive { .. } | E::Operator { .. } | E::State { .. } | E::Affine { .. } => {
            false
        }
    }
}
pub(crate) fn interval(
    value: I,
    work: Option<&crate::transition_source_plan::Work>,
) -> Result<I, Error> {
    if value.lo.to_bits() == value.hi.to_bits() {
        return Ok(value);
    }
    let lo = crate::exact_source::binary(value.lo)
        .ok_or_else(|| Error::new("real_arithmetic", "nonfinite real sample"))?;
    let hi = crate::exact_source::binary(value.hi)
        .ok_or_else(|| Error::new("real_arithmetic", "nonfinite real sample"))?;
    let result = real_rounding::image(&lo, &hi, &mut |n| work.map_or(Ok(()), |w| w.debit(2, n)))
        .map_err(|e| match e {
            Fault::Quota(e) => e,
            other => fault(other),
        })?;
    Ok(I {
        lo: result.lo,
        hi: result.hi,
    })
}
pub(crate) fn binary_interval(
    op: RealOperation,
    a: I,
    b: I,
    work: Option<&crate::transition_source_plan::Work>,
) -> Result<I, Error> {
    let result = real_rounding::binary_image(
        operation(op),
        Image { lo: a.lo, hi: a.hi },
        Image { lo: b.lo, hi: b.hi },
        &mut |n| work.map_or(Ok(()), |w| w.debit(2, n)),
    )
    .map_err(|e| match e {
        Fault::Quota(e) => e,
        other => fault(other),
    })?;
    Ok(I {
        lo: result.lo,
        hi: result.hi,
    })
}

pub(crate) fn work(model: &crate::events::EventModel) -> &crate::transition_source_plan::Work {
    if let Some(owner) = crate::analytic_request::proof_owner(model) {
        return owner.work();
    }
    if let Some(owner) = &model.floor_source {
        return owner.work();
    }
    if let Some(owner) = &model.source_context {
        return owner.borrow_work();
    }
    model
        .mixed_cold_work
        .get_or_init(|| crate::transition_source_plan::Work::for_limit(model.proof_work_limit))
}
