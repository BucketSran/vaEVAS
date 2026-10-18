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
    if matches!(f, F::Remainder) && matches!(args.get(1), Some(O::IntegerLiteral { value: 0 })) {
        return Err(Error::new(
            "invalid_ir",
            "typed remainder literal divisor must be nonzero",
        ));
    }
    if matches!(f, F::ShiftRight) && !matches!(args.get(1), Some(O::IntegerLiteral { .. })) {
        return Err(Error::new(
            "invalid_ir",
            "typed logical shift requires an integer literal count",
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
        F::Subtract => a.checked_sub(b),
        F::Remainder => a.checked_rem(b),
        F::BitAnd => Some(a & b),
        F::ShiftRight => {
            let count = b as u32;
            Some(if count >= 32 {
                0
            } else {
                ((a as u32) >> count) as i32
            })
        }
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
    #[test]
    fn runtime_remainder_subtraction_point_boxes_and_sticky_work_owner() {
        let origin = origin();
        let args = vec![
            O::IntegerPrimitive {
                function: F::Subtract,
                args: vec![O::IntegerState { state: 0 }, O::IntegerState { state: 1 }],
                origin: origin.clone(),
            },
            O::IntegerState { state: 2 },
        ];
        let accepted = [I::point(9.), I::point(2.), I::point(4.)];
        let mut work = 0;
        let got = evaluate(
            F::Remainder,
            &args,
            &origin,
            &mut |s| point(accepted[s], &origin),
            &mut || {
                work += 1;
                Ok(())
            },
        )
        .unwrap();
        assert_eq!(got, 3);
        assert_eq!(work, 8); // Every original node, operand visit and operation.
        let mut remaining = work - 1;
        for _ in 0..2 {
            assert_eq!(
                evaluate(
                    F::Remainder,
                    &args,
                    &origin,
                    &mut |s| point(accepted[s], &origin),
                    &mut || {
                        if remaining == 0 {
                            Err(Error::new("resource_budget", "same owner exhausted"))
                        } else {
                            remaining -= 1;
                            Ok(())
                        }
                    }
                )
                .unwrap_err()
                .kind,
                "resource_budget"
            );
            assert_eq!(remaining, 0);
        }
        for state in 0..3 {
            let mut uncertain = accepted;
            uncertain[state].hi += 1.;
            assert_eq!(
                evaluate(
                    F::Remainder,
                    &args,
                    &origin,
                    &mut |s| point(uncertain[s], &origin),
                    &mut || Ok(())
                )
                .unwrap_err()
                .kind,
                "integer_range"
            );
        }
    }
    #[test]
    fn bits29_word_counts_boxes_and_shared_work_are_checked() {
        let origin = origin();
        for (a, count, want) in [
            (-1, 0, -1),
            (-1, 1, 2147483647),
            (-1, 31, 1),
            (-1, 32, 0),
            (-1, 33, 0),
            (-1, -1, 0),
            (i32::MIN, 1, 1073741824),
            (i32::MIN, 31, 1),
        ] {
            let args = [
                O::IntegerState { state: 0 },
                O::IntegerLiteral { value: count },
            ];
            assert_eq!(
                evaluate(
                    F::ShiftRight,
                    &args,
                    &origin,
                    &mut |_| Ok(a),
                    &mut || Ok(())
                )
                .unwrap(),
                want
            );
            assert!(evaluate(
                F::ShiftRight,
                &args,
                &origin,
                &mut |_| point(
                    I {
                        lo: f64::from(a),
                        hi: f64::from(a) + 1.
                    },
                    &origin
                ),
                &mut || Ok(())
            )
            .is_err());
        }
        let args = [
            O::IntegerPrimitive {
                function: F::ShiftRight,
                args: vec![O::IntegerState { state: 0 }, O::IntegerLiteral { value: 1 }],
                origin: origin.clone(),
            },
            O::IntegerState { state: 1 },
        ];
        let mut spent = 0;
        assert_eq!(
            evaluate(
                F::BitAnd,
                &args,
                &origin,
                &mut |s| Ok([-1, 1][s]),
                &mut || {
                    spent += 1;
                    Ok(())
                }
            )
            .unwrap(),
            1
        );
        assert_eq!(spent, 8);
        for uncertain in 0..2 {
            assert!(evaluate(
                F::BitAnd,
                &args,
                &origin,
                &mut |s| {
                    point(
                        if s == uncertain {
                            I { lo: 1., hi: 2. }
                        } else {
                            I::ONE
                        },
                        &origin,
                    )
                },
                &mut || Ok(())
            )
            .is_err());
        }
        let mut remaining = spent - 1;
        for _ in 0..2 {
            assert_eq!(
                evaluate(F::BitAnd, &args, &origin, &mut |_| Ok(1), &mut || {
                    if remaining == 0 {
                        Err(Error::new("resource_budget", "same owner exhausted"))
                    } else {
                        remaining -= 1;
                        Ok(())
                    }
                })
                .unwrap_err()
                .kind,
                "resource_budget"
            );
            assert_eq!(remaining, 0);
        }
    }
}
