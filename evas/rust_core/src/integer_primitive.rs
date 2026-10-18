//! Source-typed event integer trees. No real arithmetic or history ownership.
use crate::interval::Interval as I;
use crate::ir::{Error, IntegerFunction as F, IntegerOperand as O, Origin, Program, StateKind};

pub(crate) fn validate(
    f: F,
    args: &[O],
    origin: &Origin,
    p: &Program,
    owner: &str,
) -> Result<(), Error> {
    if origin.instance != owner
        || origin.source.is_empty()
        || origin.line == 0
        || origin.column == 0
        || !origin.valid_expansion()
        || args.len() != 2
    {
        return Err(Error::new(
            "invalid_ir",
            "invalid typed integer origin or arity",
        ));
    }
    if matches!(f, F::Remainder)
        && !matches!(args.get(1),Some(O::IntegerLiteral{value}) if *value != 0)
    {
        return Err(Error::new(
            "invalid_ir",
            "typed remainder requires a nonzero integer literal divisor",
        ));
    }
    for arg in args {
        match arg {
            O::IntegerLiteral { .. } => (),
            O::IntegerState { state } => {
                if !p
                    .states
                    .get(*state)
                    .is_some_and(|s| s.kind == StateKind::Integer && s.instance == owner)
                {
                    return Err(Error::new(
                        "invalid_ir",
                        "typed integer state requires a same-owner integer declaration",
                    ));
                }
            }
            O::IntegerPrimitive {
                function,
                args,
                origin,
            } => validate(*function, args, origin, p, owner)?,
        }
    }
    Ok(())
}

pub(crate) fn states(args: &[O], out: &mut Vec<usize>) {
    for arg in args {
        match arg {
            O::IntegerState { state } => out.push(*state),
            O::IntegerPrimitive { args, .. } => states(args, out),
            O::IntegerLiteral { .. } => (),
        }
    }
}

pub(crate) fn point(v: I, origin: &Origin) -> Result<i32, Error> {
    if v.lo != v.hi
        || !v.lo.is_finite()
        || v.lo.fract() != 0.
        || v.lo < f64::from(i32::MIN)
        || v.lo > f64::from(i32::MAX)
    {
        return Err(Error::new(
            "integer_range",
            format!(
                "{}: typed integer requires a point signed32 operand",
                origin.label()
            ),
        ));
    }
    Ok(v.lo as i32)
}

pub(crate) fn evaluate<S: FnMut(usize) -> Result<i32, Error>, W: FnMut() -> Result<(), Error>>(
    f: F,
    args: &[O],
    origin: &Origin,
    state: &mut S,
    work: &mut W,
) -> Result<i32, Error> {
    work()?;
    if args.len() != 2 {
        return Err(Error::new("invalid_ir", "typed integer arity"));
    }
    let mut operand = |arg: &O| -> Result<i32, Error> {
        work()?;
        match arg {
            O::IntegerLiteral { value } => Ok(*value),
            O::IntegerState { state: index } => state(*index),
            O::IntegerPrimitive {
                function,
                args,
                origin,
            } => evaluate(*function, args, origin, state, work),
        }
    };
    let a = operand(&args[0])?;
    let b = operand(&args[1])?;
    work()?;
    let value = match f {
        F::Add => a.checked_add(b),
        F::Remainder => a.checked_rem(b),
    };
    value.ok_or_else(|| {
        Error::new(
            "integer_range",
            format!(
                "{}: source integer operation is outside signed32 or divides by zero",
                origin.label()
            ),
        )
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    fn origin() -> Origin {
        serde_json::from_value(
            serde_json::json!({"source":"typed.va","line":1,"column":1,"instance":"dut"}),
        )
        .unwrap()
    }
    #[test]
    fn point_and_box_use_identical_checked_source_operations() {
        let origin = origin();
        let args = vec![O::IntegerState { state: 0 }, O::IntegerLiteral { value: 8 }];
        assert_eq!(
            evaluate(
                F::Remainder,
                &args,
                &origin,
                &mut |_| point(I::point(-9.), &origin),
                &mut || Ok(())
            )
            .unwrap(),
            -1
        );
        assert!(evaluate(
            F::Remainder,
            &args,
            &origin,
            &mut |_| point(I { lo: 7., hi: 8. }, &origin),
            &mut || Ok(())
        )
        .is_err());
        let nested = vec![
            O::IntegerPrimitive {
                function: F::Add,
                args: vec![O::IntegerState { state: 0 }, O::IntegerLiteral { value: 1 }],
                origin: origin.clone(),
            },
            O::IntegerLiteral { value: 8 },
        ];
        assert!(evaluate(
            F::Remainder,
            &nested,
            &origin,
            &mut |_| Ok(i32::MAX),
            &mut || Ok(())
        )
        .is_err());
        assert!(evaluate(
            F::Remainder,
            &[
                O::IntegerState { state: 0 },
                O::IntegerLiteral { value: -1 }
            ],
            &origin,
            &mut |_| Ok(i32::MIN),
            &mut || Ok(())
        )
        .is_err());
        let mut allowance = 2;
        for _ in 0..2 {
            assert!(
                evaluate(F::Remainder, &nested, &origin, &mut |_| Ok(1), &mut || {
                    if allowance == 0 {
                        Err(Error::new("resource_budget", "exhausted"))
                    } else {
                        allowance -= 1;
                        Ok(())
                    }
                })
                .is_err()
            );
            assert_eq!(allowance, 0);
        }
    }
}
