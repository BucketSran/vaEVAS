//! Outward binary64 bounds for event scheduling. No change to the static solver.
use std::ops::{Add, Div, Mul, Neg, Sub};

#[cfg(test)]
#[path = "interval_properties.rs"]
mod properties;

#[derive(Clone, Copy, Debug, PartialEq)]
pub(crate) struct Interval {
    pub lo: f64,
    pub hi: f64,
}

impl Interval {
    pub const ZERO: Self = Self::point(0.0);
    pub const ONE: Self = Self::point(1.0);
    const WHOLE: Self = Self {
        lo: f64::NEG_INFINITY,
        hi: f64::INFINITY,
    };

    pub const fn point(x: f64) -> Self {
        Self { lo: x, hi: x }
    }
    pub fn finite(self) -> bool {
        self.lo.is_finite() && self.hi.is_finite()
    }
    pub fn zero(self) -> bool {
        self == Self::ZERO
    }
    pub fn magnitude(self) -> f64 {
        self.lo.abs().max(self.hi.abs())
    }
    pub fn sign(self) -> Option<i8> {
        if self.lo > 0.0 {
            Some(1)
        } else if self.hi < 0.0 {
            Some(-1)
        } else if self.zero() {
            Some(0)
        } else {
            None
        }
    }
    pub fn hull(self, other: Self) -> Self {
        Self {
            lo: self.lo.min(other.lo),
            hi: self.hi.max(other.hi),
        }
    }

    fn rounded(value: f64, exact: bool) -> Self {
        if !value.is_finite() {
            Self::WHOLE
        } else if exact {
            Self::point(value)
        } else {
            Self {
                lo: value.next_down(),
                hi: value.next_up(),
            }
        }
    }
}

// Exact binary products fit in 106 significant bits. Comparing canonical
// (sign, odd significand, exponent) also handles subnormals without an FMA
// residual underflow being mistaken for an exact multiplication/division.
fn parts(x: f64) -> (u128, i32) {
    let bits = x.to_bits();
    let exponent = ((bits >> 52) & 2047) as i32;
    let fraction = (bits & ((1_u64 << 52) - 1)) as u128;
    if exponent == 0 {
        (fraction, -1074)
    } else {
        (fraction | (1_u128 << 52), exponent - 1075)
    }
}

fn product(a: f64, b: f64) -> (bool, u128, i32) {
    let (a_bits, a_exp) = parts(a);
    let (b_bits, b_exp) = parts(b);
    let bits = a_bits * b_bits;
    if bits == 0 {
        return (false, 0, 0);
    }
    let shift = bits.trailing_zeros();
    (
        a.is_sign_negative() != b.is_sign_negative(),
        bits >> shift,
        a_exp + b_exp + shift as i32,
    )
}

pub(crate) fn equal_products(a: f64, b: f64, c: f64, d: f64) -> bool {
    [a, b, c, d].iter().all(|x| x.is_finite()) && product(a, b) == product(c, d)
}

/// Exact sign of at most four binary64 products, without rounded differences.
/// Align at 2^-2148: four products need at most 4198 bits, including carries.
pub(crate) fn sum_products_sign(terms: &[(f64, f64)]) -> Option<i8> {
    if terms.len() > 4 || terms.iter().any(|(a, b)| !a.is_finite() || !b.is_finite()) {
        return None;
    }
    let mut sums = [[0_u64; 68]; 2];
    for &(a, b) in terms {
        let (negative, bits, exponent) = product(a, b);
        if bits == 0 {
            continue;
        }
        let shift = (exponent + 2148) as usize;
        let words = [bits as u64, (bits >> 64) as u64];
        for (j, word) in words.into_iter().enumerate() {
            let shifted = (word as u128) << (shift % 64);
            for (k, mut carry) in [shifted as u64, (shifted >> 64) as u64]
                .into_iter()
                .enumerate()
            {
                let mut i = shift / 64 + j + k;
                while carry != 0 {
                    if i == 68 {
                        return None;
                    }
                    let (value, overflow) = sums[negative as usize][i].overflowing_add(carry);
                    sums[negative as usize][i] = value;
                    carry = u64::from(overflow);
                    i += 1;
                }
            }
        }
    }
    Some(match sums[0].iter().rev().cmp(sums[1].iter().rev()) {
        std::cmp::Ordering::Less => -1,
        std::cmp::Ordering::Equal => 0,
        std::cmp::Ordering::Greater => 1,
    })
}

fn add(a: f64, b: f64) -> Interval {
    let value = a + b;
    let virtual_b = value - a;
    let error = (a - (value - virtual_b)) + (b - virtual_b); // TwoSum
    Interval::rounded(value, error == 0.0)
}

fn multiply(a: f64, b: f64) -> Interval {
    let value = a * b;
    Interval::rounded(value, equal_products(a, b, value, 1.0))
}

fn divide(a: f64, b: f64) -> Interval {
    let value = a / b;
    Interval::rounded(value, equal_products(value, b, a, 1.0))
}

impl Add for Interval {
    type Output = Self;
    fn add(self, other: Self) -> Self {
        if !self.finite() || !other.finite() {
            return Self::WHOLE;
        }
        Self {
            lo: add(self.lo, other.lo).lo,
            hi: add(self.hi, other.hi).hi,
        }
    }
}
impl Neg for Interval {
    type Output = Self;
    fn neg(self) -> Self {
        Self {
            lo: -self.hi,
            hi: -self.lo,
        }
    }
}
impl Sub for Interval {
    type Output = Self;
    fn sub(self, other: Self) -> Self {
        self + -other
    }
}
impl Mul for Interval {
    type Output = Self;
    fn mul(self, other: Self) -> Self {
        if !self.finite() || !other.finite() {
            return Self::WHOLE;
        }
        let bounds = [
            multiply(self.lo, other.lo),
            multiply(self.lo, other.hi),
            multiply(self.hi, other.lo),
            multiply(self.hi, other.hi),
        ];
        Self {
            lo: bounds.iter().map(|v| v.lo).fold(f64::INFINITY, f64::min),
            hi: bounds
                .iter()
                .map(|v| v.hi)
                .fold(f64::NEG_INFINITY, f64::max),
        }
    }
}
impl Div for Interval {
    type Output = Self;
    fn div(self, other: Self) -> Self {
        if !self.finite() || !other.finite() || (other.lo <= 0.0 && other.hi >= 0.0) {
            return Self::WHOLE;
        }
        let bounds = [
            divide(self.lo, other.lo),
            divide(self.lo, other.hi),
            divide(self.hi, other.lo),
            divide(self.hi, other.hi),
        ];
        Self {
            lo: bounds.iter().map(|v| v.lo).fold(f64::INFINITY, f64::min),
            hi: bounds
                .iter()
                .map(|v| v.hi)
                .fold(f64::NEG_INFINITY, f64::max),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn exact_cancellation_and_underflow_are_distinguished() {
        assert!(
            (Interval::point(1.0) - Interval::point(1.0 - 2_f64.powi(-50))).lo == 2_f64.powi(-50)
        );
        let tiny = f64::from_bits(1);
        let bound = Interval::point(tiny) * Interval::point(0.5);
        assert!(bound.lo <= 0.0 && bound.hi >= tiny);
        assert!(!bound.zero());
        let third = Interval::ONE / Interval::point(3.0);
        assert!(third.lo < 1.0 / 3.0 && third.hi > 1.0 / 3.0);
        assert!(!(Interval::ONE / Interval::ZERO).finite());
    }
    #[test]
    fn products_compare_exactly_even_when_float_products_underflow() {
        assert!(!equal_products(1e-300, 1e-300, 0.0, 1.0));
        assert!(equal_products(3.0, 0.5, 1.5, 1.0));
        assert!(!equal_products(0.1, 0.1, 0.01, 1.0));
    }
}
