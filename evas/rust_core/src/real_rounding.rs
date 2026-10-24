//! Binary64 nearest/ties-even images of program-real arithmetic.
//!
//! This module owns no proof allowance or simulator state. Every allocating
//! integer/rational helper is prepaid through the caller's fallible debit.
//! Returned endpoints are rounded values, never an unrounded rational lineage.
use num_rational::BigRational as R;
use num_traits::{Signed, ToPrimitive, Zero};
use std::convert::Infallible;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum Op {
    Add,
    Subtract,
    Multiply,
    Divide,
}

#[derive(Debug, PartialEq, Eq)]
pub(crate) enum Fault<E> {
    NonFinite,
    DivisionByZero,
    DivisionAcrossZero,
    Overflow,
    InvalidBounds,
    Quota(E),
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub(crate) struct Image {
    pub lo: f64,
    pub hi: f64,
}

impl Image {
    /// Mixed zero signs are two IEEE outcomes, even though numerically equal.
    /// A rational exact zero is assigned +0 unless round_ratio receives a hint.
    pub(crate) fn singleton(self) -> Option<f64> {
        (self.lo.is_finite() && self.lo.to_bits() == self.hi.to_bits()).then_some(self.lo)
    }
}

fn pay<E>(debit: &mut impl FnMut(u64) -> Result<(), E>, amount: u64) -> Result<(), Fault<E>> {
    debit(amount).map_err(Fault::Quota)
}

fn words(bits: u64) -> u64 {
    (bits / 64)
        .saturating_add(u64::from(!bits.is_multiple_of(64)))
        .saturating_add(1)
}

fn linear(bits: u64) -> u64 {
    16_u64.saturating_add(8_u64.saturating_mul(words(bits)))
}

// Covers temporary storage, schoolbook multiply/divide and Euclidean
// normalization/continued-fraction comparison inside one Ratio helper. The
// bound uses the maximum temporary width, not merely the returned value size.
fn rational_fee(bits: u64) -> u64 {
    let n = words(bits);
    64_u64.saturating_add(16_u64.saturating_mul(n.saturating_mul(n).saturating_mul(n)))
}

fn width(value: &R) -> u64 {
    value.numer().bits().max(value.denom().bits())
}

fn valid_ratio(value: &R) -> bool {
    // BigRational::new_raw can bypass the usual positive denominator invariant.
    value.denom().is_positive()
}

/// One actual IEEE operation. No reassociation, reciprocal replacement or FMA.
pub(crate) fn point(op: Op, a: f64, b: f64) -> Result<f64, Fault<Infallible>> {
    if !a.is_finite() || !b.is_finite() {
        return Err(Fault::NonFinite);
    }
    if op == Op::Divide && b == 0.0 {
        return Err(Fault::DivisionByZero);
    }
    let value = match op {
        Op::Add => a + b,
        Op::Subtract => a - b,
        Op::Multiply => a * b,
        Op::Divide => a / b,
    };
    if value.is_finite() {
        Ok(value)
    } else {
        Err(Fault::Overflow)
    }
}

/// Round an exact finite rational once. Nonzero negative underflow retains -0;
/// a rational zero uses the explicit hint because Rational cannot store a sign.
pub(crate) fn round_ratio<E>(
    value: &R,
    negative_zero: bool,
    debit: &mut impl FnMut(u64) -> Result<(), E>,
) -> Result<f64, Fault<E>> {
    pay(debit, 16)?;
    if !valid_ratio(value) {
        return Err(Fault::InvalidBounds);
    }
    if value.is_zero() {
        return Ok(f64::from_bits(u64::from(negative_zero) << 63));
    }
    let negative = value.is_negative();
    let sign = u64::from(negative) << 63;
    let nb = value.numer().bits();
    let db = value.denom().bits();
    let difference = i128::from(nb) - i128::from(db);
    // These decisions use bit lengths only. They avoid allocating a huge shift
    // for values already beyond the finite or underflow rounding boundaries.
    if difference > 1024 {
        return Err(Fault::Overflow);
    }
    if difference < -1075 {
        return Ok(f64::from_bits(sign));
    }
    pay(debit, linear(nb))?;
    let n = value.numer().abs();
    let d = value.denom();
    let less_than_power = if difference >= 0 {
        let shift = difference as usize;
        pay(debit, linear(db.saturating_add(shift as u64)))?;
        let shifted = d << shift;
        pay(debit, linear(nb.max(shifted.bits())))?;
        n < shifted
    } else {
        let shift = (-difference) as usize;
        pay(debit, linear(nb.saturating_add(shift as u64)))?;
        let shifted = &n << shift;
        pay(debit, linear(db.max(shifted.bits())))?;
        shifted < *d
    };
    let mut exponent = difference as i32 - i32::from(less_than_power);
    if exponent > 1023 {
        return Err(Fault::Overflow);
    }
    if exponent < -1075 {
        return Ok(f64::from_bits(sign));
    }
    let quantum = (exponent - 52).max(-1074);
    let (scaled_n, scaled_d) = if quantum >= 0 {
        pay(
            debit,
            linear(db.saturating_add(quantum as u64)).saturating_add(linear(nb)),
        )?;
        (n, d << quantum as usize)
    } else {
        pay(
            debit,
            linear(nb.saturating_add((-quantum) as u64)).saturating_add(linear(db)),
        )?;
        (&n << (-quantum) as usize, d.clone())
    };
    pay(debit, rational_fee(scaled_n.bits().max(scaled_d.bits())))?;
    let quotient = &scaled_n / &scaled_d;
    pay(
        debit,
        rational_fee(quotient.bits().saturating_add(scaled_d.bits())),
    )?;
    let product = &quotient * &scaled_d;
    pay(debit, linear(scaled_n.bits().max(product.bits())))?;
    let remainder = scaled_n - product;
    pay(debit, linear(remainder.bits().saturating_add(1)))?;
    let twice = remainder << 1_usize;
    pay(debit, linear(twice.bits().max(scaled_d.bits())))?;
    let ordering = twice.cmp(&scaled_d);
    pay(debit, linear(quotient.bits()))?;
    let mut significand = quotient.to_u64().ok_or(Fault::Overflow)?;
    if ordering.is_gt() || (ordering.is_eq() && significand & 1 != 0) {
        significand += 1;
    }
    if significand == 0 {
        return Ok(f64::from_bits(sign));
    }
    let payload = if exponent < -1022 {
        // A carry to 2^52 is exactly the minimum normal encoding.
        significand
    } else {
        if significand == 1_u64 << 53 {
            significand >>= 1;
            exponent += 1;
        }
        if exponent > 1023 {
            return Err(Fault::Overflow);
        }
        (((exponent + 1023) as u64) << 52) | (significand - (1_u64 << 52))
    };
    Ok(f64::from_bits(sign | payload))
}

/// Monotonic RN image of the complete exact domain. A nonpoint domain wholly
/// within one rounding cell legitimately has a singleton rounded image.
pub(crate) fn image<E>(
    lo: &R,
    hi: &R,
    debit: &mut impl FnMut(u64) -> Result<(), E>,
) -> Result<Image, Fault<E>> {
    pay(debit, 16)?;
    if !valid_ratio(lo) || !valid_ratio(hi) {
        return Err(Fault::InvalidBounds);
    }
    pay(debit, rational_fee(width(lo).saturating_add(width(hi))))?;
    if lo > hi {
        return Err(Fault::InvalidBounds);
    }
    Ok(Image {
        lo: round_ratio(lo, false, debit)?,
        hi: round_ratio(hi, false, debit)?,
    })
}

fn from_binary<E>(value: f64, debit: &mut impl FnMut(u64) -> Result<(), E>) -> Result<R, Fault<E>> {
    // Zero has a one-bit reduced ratio, independently of its IEEE sign bit.
    // It must not reserve a 1075-bit subnormal conversion it never performs.
    if value == 0. {
        pay(debit, 64)?;
        return Ok(R::zero());
    }
    let exponent = ((value.to_bits() >> 52) & 2047) as i32;
    let bits = if exponent == 0 {
        1075
    } else {
        (exponent - 1023).unsigned_abs() as u64 + 54
    };
    pay(debit, rational_fee(bits))?;
    R::from_float(value).ok_or(Fault::NonFinite)
}

fn corner<E>(
    op: Op,
    a: f64,
    b: f64,
    debit: &mut impl FnMut(u64) -> Result<(), E>,
) -> Result<f64, Fault<E>> {
    pay(debit, 8)?;
    // Rational has no signed zero. IEEE exact cancellation gives +0, except
    // adding two negative zeros or subtracting +0 from -0. Products and
    // quotients use the operand sign XOR. Nonzero underflow uses the exact sign.
    let zero_sign = match op {
        Op::Add => a == 0.0 && b == 0.0 && a.is_sign_negative() && b.is_sign_negative(),
        Op::Subtract => a == 0.0 && b == 0.0 && a.is_sign_negative() && !b.is_sign_negative(),
        Op::Multiply | Op::Divide => a.is_sign_negative() != b.is_sign_negative(),
    };
    let left = from_binary(a, debit)?;
    let right = from_binary(b, debit)?;
    pay(
        debit,
        rational_fee(width(&left).saturating_add(width(&right)).saturating_add(2)),
    )?;
    let exact = match op {
        Op::Add => &left + &right,
        Op::Subtract => &left - &right,
        Op::Multiply => &left * &right,
        Op::Divide => &left / &right,
    };
    round_ratio(&exact, zero_sign, debit)
}

/// Arithmetic on already-rounded program-real domains. Four corners include
/// signed-zero alternatives; a divisor containing zero is never sampled at its
/// nominal value. Correlation refinement belongs to the caller.
pub(crate) fn binary_image<E>(
    op: Op,
    left: Image,
    right: Image,
    debit: &mut impl FnMut(u64) -> Result<(), E>,
) -> Result<Image, Fault<E>> {
    pay(debit, 16)?;
    if ![left.lo, left.hi, right.lo, right.hi]
        .iter()
        .all(|x| x.is_finite())
    {
        return Err(Fault::NonFinite);
    }
    if left.lo > left.hi || right.lo > right.hi {
        return Err(Fault::InvalidBounds);
    }
    if op == Op::Divide && right.lo <= 0.0 && right.hi >= 0.0 {
        return Err(if right.lo == 0.0 && right.hi == 0.0 {
            Fault::DivisionByZero
        } else {
            Fault::DivisionAcrossZero
        });
    }
    if let Some((a, b)) = left.singleton().zip(right.singleton()) {
        // Each operand is one already-rounded IEEE value. Reuse the same
        // single native operation as point(); no reassociation or FMA occurs.
        // Intervals and mixed signed-zero domains still use all four corners.
        pay(debit, 32)?;
        let value = point(op, a, b).map_err(|error| match error {
            Fault::NonFinite => Fault::NonFinite,
            Fault::DivisionByZero => Fault::DivisionByZero,
            Fault::DivisionAcrossZero => Fault::DivisionAcrossZero,
            Fault::Overflow => Fault::Overflow,
            Fault::InvalidBounds => Fault::InvalidBounds,
            Fault::Quota(never) => match never {},
        })?;
        return Ok(Image {
            lo: value,
            hi: value,
        });
    }
    let mut result: Option<Image> = None;
    for a in [left.lo, left.hi] {
        for b in [right.lo, right.hi] {
            let value = corner(op, a, b, debit)?;
            result = Some(match result {
                None => Image {
                    lo: value,
                    hi: value,
                },
                Some(old) => Image {
                    lo: if value.total_cmp(&old.lo).is_lt() {
                        value
                    } else {
                        old.lo
                    },
                    hi: if value.total_cmp(&old.hi).is_gt() {
                        value
                    } else {
                        old.hi
                    },
                },
            });
        }
    }
    Ok(result.unwrap())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn unlimited(_: u64) -> Result<(), Infallible> {
        Ok(())
    }

    #[test]
    fn singleton_ieee_image_uses_original_small_budget_and_preserves_bits() {
        use crate::transition_source_plan::Work;
        for (op, a, b, bits) in [
            (
                Op::Add,
                9007199254740992.,
                1.,
                9007199254740992_f64.to_bits(),
            ),
            (Op::Divide, 3., 10., 0x3fd3333333333333),
            (Op::Multiply, f64::from_bits(1), 0.5, 0),
            (Op::Multiply, -f64::from_bits(1), 0.5, (-0_f64).to_bits()),
            (Op::Subtract, -0., 0., (-0_f64).to_bits()),
        ] {
            let work = Work::limited([128, 8192, 64]);
            let result = binary_image(
                op,
                Image { lo: a, hi: a },
                Image { lo: b, hi: b },
                &mut |n| work.debit(2, n),
            )
            .unwrap();
            assert_eq!(result.singleton().unwrap().to_bits(), bits);
            assert!(work.spent() <= 64);
        }
        let work = Work::limited([128, 8192, 47]);
        let retry = work.clone();
        for _ in 0..2 {
            let before = work.spent();
            let result = binary_image(
                Op::Add,
                Image { lo: 1., hi: 1. },
                Image { lo: 2., hi: 2. },
                &mut |n| retry.debit(2, n),
            );
            assert!(matches!(result,Err(Fault::Quota(e)) if e.kind=="step_budget"));
            assert!(work.spent() > before);
        }
    }

    #[test]
    fn zero_signs_follow_operations_and_domains_do_not_invent_a_sign() {
        for (op, a, b, bits) in [
            (Op::Add, -0., -0., (-0_f64).to_bits()),
            (Op::Add, -1., 1., 0),
            (Op::Subtract, -0., 0., (-0_f64).to_bits()),
            (Op::Multiply, 0., -1., (-0_f64).to_bits()),
            (Op::Divide, -0., -1., 0),
        ] {
            assert_eq!(point(op, a, b).unwrap().to_bits(), bits);
            let result = binary_image(
                op,
                Image { lo: a, hi: a },
                Image { lo: b, hi: b },
                &mut unlimited,
            )
            .unwrap();
            assert_eq!(result.singleton().unwrap().to_bits(), bits);
        }
        assert_eq!(Image { lo: -0., hi: 0. }.singleton(), None);
        assert_eq!(
            round_ratio(&R::zero(), true, &mut unlimited)
                .unwrap()
                .to_bits(),
            (-0_f64).to_bits()
        );
    }

    #[test]
    fn zero_divisor_and_domain_crossing_remain_distinct() {
        let one = Image { lo: 1., hi: 1. };
        assert_eq!(
            binary_image(Op::Divide, one, Image { lo: 0., hi: 0. }, &mut unlimited),
            Err(Fault::DivisionByZero)
        );
        for denominator in [Image { lo: -1., hi: 1. }, Image { lo: 0., hi: 1. }] {
            assert_eq!(
                binary_image(Op::Divide, one, denominator, &mut unlimited),
                Err(Fault::DivisionAcrossZero)
            );
        }
    }

    #[test]
    fn callback_failure_is_returned_before_big_integer_work_and_never_refunded() {
        let value = R::from_integer(3.into()) / R::from_integer(10.into());
        let mut used = 0_u64;
        let mut debit = |amount: u64| {
            used = used.saturating_add(amount);
            if used > 16 {
                Err("original-owner-exhausted")
            } else {
                Ok(())
            }
        };
        assert_eq!(
            round_ratio(&value, false, &mut debit),
            Err(Fault::Quota("original-owner-exhausted"))
        );
        assert_eq!(
            round_ratio(&value, false, &mut debit),
            Err(Fault::Quota("original-owner-exhausted"))
        );
        assert!(round_ratio(&value, false, &mut unlimited).is_ok());
    }

    #[test]
    fn late_quota_failures_share_the_caller_owner_and_preserve_inputs() {
        let left = Image { lo: 0.3, hi: 0.6 };
        let right = Image { lo: -0.9, hi: -0.7 };
        let mut fees = Vec::new();
        let clean = binary_image(Op::Divide, left, right, &mut |amount| {
            fees.push(amount);
            Ok::<_, Infallible>(())
        })
        .unwrap();
        let total: u64 = fees.iter().sum();
        for limit in [fees[0], fees[..fees.len() / 2].iter().sum(), total - 1] {
            let mut used = 0_u64;
            let mut debit = |amount: u64| {
                used = used.saturating_add(amount);
                if used > limit {
                    Err(limit)
                } else {
                    Ok(())
                }
            };
            assert_eq!(
                binary_image(Op::Divide, left, right, &mut debit),
                Err(Fault::Quota(limit))
            );
            assert_eq!(
                binary_image(Op::Divide, left, right, &mut debit),
                Err(Fault::Quota(limit))
            );
            assert!(used > limit);
        }
        assert_eq!(
            binary_image(Op::Divide, left, right, &mut unlimited).unwrap(),
            clean
        );
    }

    #[test]
    fn prepayment_tracks_operand_width_instead_of_only_api_calls() {
        let small = R::new(3.into(), 10.into());
        let large = R::from_integer(1.into())
            + R::new(1.into(), R::from_integer(2.into()).numer() << 4000_usize);
        let mut totals = [0_u64; 2];
        for (index, value) in [&small, &large].into_iter().enumerate() {
            let result = round_ratio(value, false, &mut |fee| {
                totals[index] += fee;
                Ok::<_, Infallible>(())
            })
            .unwrap();
            assert_eq!(result, if index == 0 { 0.3 } else { 1.0 });
        }
        assert!(totals[1] > 100 * totals[0]);
    }

    #[test]
    fn malformed_and_nonfinite_domains_refuse_without_a_nominal_fallback() {
        assert_eq!(point(Op::Add, f64::INFINITY, 1.), Err(Fault::NonFinite));
        assert_eq!(point(Op::Multiply, f64::MAX, 2.), Err(Fault::Overflow));
        assert_eq!(
            round_ratio(&R::new_raw(1.into(), 0.into()), false, &mut unlimited),
            Err(Fault::InvalidBounds)
        );
        let one = R::from_integer(1.into());
        let two = R::from_integer(2.into());
        assert_eq!(image(&two, &one, &mut unlimited), Err(Fault::InvalidBounds));
        assert_eq!(
            binary_image(
                Op::Add,
                Image { lo: 2., hi: 1. },
                Image { lo: 0., hi: 0. },
                &mut unlimited
            ),
            Err(Fault::InvalidBounds)
        );
        assert_eq!(
            binary_image(
                Op::Add,
                Image {
                    lo: 0.,
                    hi: f64::INFINITY
                },
                Image { lo: 0., hi: 0. },
                &mut unlimited
            ),
            Err(Fault::NonFinite)
        );
    }
}
