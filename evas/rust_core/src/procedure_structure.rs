//! Structural validity is independent of which numeric arm executes. This
//! visitor never evaluates an expression or its numeric domain.
use super::*;
use crate::ir::{IntegerOperand as N, Statement as S};

pub(super) fn source(o: &ir::Origin, owner: &str, w: &Work) -> Result<(), Error> {
    w.debit(2, (o.source.len() + o.instance.len() + 32) as u64)?;
    for (name, _) in &o.expansion {
        w.debit(2, (name.len() + 16) as u64)?;
    }
    origin(o, owner)
}
fn state(index: usize, p: &Program, owner: &str, w: &Work) -> Result<(), Error> {
    w.step()?;
    if p.states.get(index).is_none_or(|s| s.instance != owner) {
        return Err(invalid("procedure state reference/target owner mismatch"));
    }
    Ok(())
}
fn integer(n: &N, p: &Program, owner: &str, w: &Work) -> Result<(), Error> {
    w.step()?;
    match n {
        N::IntegerLiteral { .. } => {}
        N::IntegerState { state: index } => {
            state(*index, p, owner, w)?;
            if p.states[*index].kind != ir::StateKind::Integer {
                return Err(invalid("integer operand requires an integer state"));
            }
        }
        N::IntegerPrimitive { args, origin, .. } => {
            source(origin, owner, w)?;
            if args.len() != 2 {
                return Err(invalid("integer primitive requires two operands"));
            }
            for n in args {
                integer(n, p, owner, w)?;
            }
        }
    }
    Ok(())
}
fn array(
    slots: &[usize],
    first: i32,
    last: i32,
    p: &Program,
    owner: &str,
    w: &Work,
) -> Result<(), Error> {
    if first > last
        || slots.is_empty()
        || slots.len() as u64 != (i64::from(last) - i64::from(first) + 1) as u64
    {
        return Err(invalid("procedure array mapping has invalid bounds"));
    }
    w.debit(
        2,
        (slots
            .len()
            .saturating_mul(slots.len().max(1).ilog2() as usize + 2)
            .saturating_mul(32)) as u64,
    )?;
    let mut unique = BTreeSet::new();
    let mut kind = None;
    for &index in slots {
        state(index, p, owner, w)?;
        let current = &p.states[index].kind;
        if !unique.insert(index) || kind.as_ref().is_some_and(|k| k != current) {
            return Err(invalid(
                "procedure array mapping has duplicate or mixed state slots",
            ));
        }
        kind = Some(current.clone());
    }
    Ok(())
}
pub(super) fn expression(
    e: &E,
    p: &Program,
    procedure: Option<usize>,
    owner: &str,
    w: &Work,
) -> Result<(), Error> {
    w.step()?;
    match e {
        E::RealCall {
            origin,
            body,
            result,
            ..
        } => {
            source(origin, owner, w)?;
            call_steps(body, p, procedure, owner, w)?;
            expression(result, p, procedure, owner, w)?;
        }
        E::UnsupportedSystemCall { args, origin, .. } => {
            source(origin, owner, w)?;
            for e in args {
                expression(e, p, procedure, owner, w)?;
            }
        }
        E::State { state: index } => state(*index, p, owner, w)?,
        E::Operator { operator } => {
            if p.operators
                .get(*operator)
                .is_none_or(|s| s.origin().instance != owner)
            {
                return Err(invalid("procedure operator reference owner mismatch"));
            }
        }
        E::RealLocal { binding } => {
            let b = p
                .real_bindings
                .get(*binding)
                .ok_or_else(|| invalid("real local index out of range"))?;
            if b.origin.instance != owner || procedure.is_some_and(|id| b.procedure_id != id) {
                return Err(invalid("real local belongs to another procedure"));
            }
        }
        E::Affine { terms, .. } => {
            w.debit(
                2,
                (terms
                    .len()
                    .saturating_mul(terms.len().max(1).ilog2() as usize + 2)
                    .saturating_mul(32)) as u64,
            )?;
            crate::expression::validate(e, p.nodes.len())?;
        }
        E::RealBinary {
            left,
            right,
            origin,
            ..
        } => {
            source(origin, owner, w)?;
            expression(left, p, procedure, owner, w)?;
            expression(right, p, procedure, owner, w)?;
        }
        E::RealBoundary { value, origin, .. }
        | E::IntegerRound { value, origin }
        | E::CheckedInteger { value, origin } => {
            source(origin, owner, w)?;
            expression(value, p, procedure, owner, w)?;
        }
        E::CheckedIndex {
            index,
            first,
            last,
            origin,
        } => {
            source(origin, owner, w)?;
            if first > last {
                return Err(invalid("checked index bounds are reversed"));
            }
            expression(index, p, procedure, owner, w)?;
        }
        E::ArrayRead {
            states,
            index,
            first,
            last,
            origin,
        } => {
            source(origin, owner, w)?;
            array(states, *first, *last, p, owner, w)?;
            expression(index, p, procedure, owner, w)?;
        }
        E::IntegerPrimitive { args, origin, .. } => {
            source(origin, owner, w)?;
            if args.len() != 2 {
                return Err(invalid("integer primitive requires two operands"));
            }
            for n in args {
                integer(n, p, owner, w)?;
            }
        }
        E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
            expression(left, p, procedure, owner, w)?;
            expression(right, p, procedure, owner, w)?;
        }
        E::Power { base, exponent } => {
            if !(1..=32).contains(exponent) {
                return Err(invalid("procedure polynomial exponent must be in 1..=32"));
            }
            expression(base, p, procedure, owner, w)?;
        }
        E::Select {
            left,
            right,
            then_value,
            else_value,
            origin,
            ..
        } => {
            source(origin, owner, w)?;
            for e in [left, right, then_value, else_value] {
                expression(e, p, procedure, owner, w)?;
            }
        }
        E::EventMath {
            function,
            args,
            origin,
        } => {
            source(origin, owner, w)?;
            let count = match function {
                ir::EventMathFunction::Min | ir::EventMathFunction::Max => 2,
                _ => 1,
            };
            if args.len() != count {
                return Err(invalid("procedure mathematics arity mismatch"));
            }
            for e in args {
                expression(e, p, procedure, owner, w)?;
            }
        }
        E::Forcing {
            value,
            checked,
            origin,
        } => {
            source(origin, owner, w)?;
            expression(value, p, procedure, owner, w)?;
            for e in checked {
                expression(e, p, procedure, owner, w)?;
            }
        }
    }
    Ok(())
}
pub(super) fn statement(
    s: &S,
    p: &Program,
    procedure: usize,
    owner: &str,
    w: &Work,
) -> Result<(), Error> {
    w.step()?;
    match s {
        S::Assign(a) => {
            state(a.state, p, owner, w)?;
            expression(&a.rhs, p, Some(procedure), owner, w)?;
        }
        S::ArrayWrite {
            states,
            index,
            rhs,
            first,
            last,
            origin,
        } => {
            source(origin, owner, w)?;
            array(states, *first, *last, p, owner, w)?;
            expression(index, p, Some(procedure), owner, w)?;
            expression(rhs, p, Some(procedure), owner, w)?;
        }
        S::Display {
            format,
            args,
            origin,
        } => {
            source(origin, owner, w)?;
            w.debit(2, format.len() as u64)?;
            for e in args {
                expression(e, p, Some(procedure), owner, w)?;
            }
        }
        S::If {
            left,
            right,
            then_body,
            else_body,
            origin,
            ..
        } => {
            source(origin, owner, w)?;
            expression(left, p, Some(procedure), owner, w)?;
            expression(right, p, Some(procedure), owner, w)?;
            for s in then_body.iter().chain(else_body) {
                statement(s, p, procedure, owner, w)?;
            }
        }
        S::Loop {
            initialize,
            left,
            right,
            body,
            update,
            origin,
            ..
        } => {
            source(origin, owner, w)?;
            expression(left, p, Some(procedure), owner, w)?;
            expression(right, p, Some(procedure), owner, w)?;
            for s in initialize.iter().chain(body).chain(update) {
                statement(s, p, procedure, owner, w)?;
            }
        }
    }
    Ok(())
}

fn call_steps(
    steps: &[ProcedureStep],
    p: &Program,
    id: Option<usize>,
    owner: &str,
    w: &Work,
) -> Result<(), Error> {
    for step in steps {
        w.step()?;
        match &step.action {
            A::Control(C::RealBind { value, origin, .. }) => {
                source(origin, owner, w)?;
                expression(value, p, id, owner, w)?;
            }
            A::Control(C::ProcedureIf {
                left,
                right,
                then_body,
                else_body,
                origin,
                ..
            }) => {
                source(origin, owner, w)?;
                expression(left, p, id, owner, w)?;
                expression(right, p, id, owner, w)?;
                call_steps(then_body, p, id, owner, w)?;
                call_steps(else_body, p, id, owner, w)?;
            }
            _ => return Err(invalid("invalid pure call body action")),
        }
    }
    Ok(())
}
