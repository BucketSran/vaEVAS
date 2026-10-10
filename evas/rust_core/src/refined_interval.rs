//! Local, outward dyadic arithmetic for an otherwise unresolved query.
//! Original enclosures are retained. This cannot turn physical uncertainty into
//! a point value. The fixed 160 fractional bits and bounded exponential series
//! are independent of the request's acceptance tolerances.
use crate::exact_source::binary;
use crate::interval::Interval as I;
use num_rational::BigRational as R;
use num_traits::{Signed, Zero};

#[derive(Clone, Debug, PartialEq)]
pub(crate) struct Bounds {
    pub(crate) lo: R,
    pub(crate) hi: R,
}
fn scale() -> R {
    R::from_integer(2.into()).pow(160)
}
impl Bounds {
    pub(crate) fn from_interval(value: I) -> Option<Self> {
        if !value.finite() || value.lo > value.hi {
            return None;
        }
        Some(Self {
            lo: binary(value.lo)?,
            hi: binary(value.hi)?,
        })
    }
    pub(crate) fn point(value: f64) -> Option<Self> {
        Self::from_interval(I::point(value))
    }
    pub(crate) fn rational(value: R) -> Self {
        Self {
            lo: value.clone(),
            hi: value,
        }
    }
    fn rounded(lo: R, hi: R) -> Self {
        let s = scale();
        Self {
            lo: (&lo * &s).floor() / &s,
            hi: (&hi * &s).ceil() / &s,
        }
    }
    pub(crate) fn add(&self, other: &Self) -> Self {
        if self.sign() == Some(0) {
            return other.clone();
        }
        if other.sign() == Some(0) {
            return self.clone();
        }
        Self::rounded(&self.lo + &other.lo, &self.hi + &other.hi)
    }
    pub(crate) fn neg(&self) -> Self {
        Self {
            lo: -&self.hi,
            hi: -&self.lo,
        }
    }
    pub(crate) fn sub(&self, other: &Self) -> Self {
        self.add(&other.neg())
    }
    pub(crate) fn mul(&self, other: &Self) -> Self {
        if self.sign() == Some(0) || other.sign() == Some(0) {
            return Self::point(0.).unwrap();
        }
        if self.lo == self.hi && self.lo == R::from_integer(1.into()) {
            return other.clone();
        }
        if other.lo == other.hi && other.lo == R::from_integer(1.into()) {
            return self.clone();
        }
        let p = [
            &self.lo * &other.lo,
            &self.lo * &other.hi,
            &self.hi * &other.lo,
            &self.hi * &other.hi,
        ];
        Self::rounded(
            p.iter().min().unwrap().clone(),
            p.iter().max().unwrap().clone(),
        )
    }
    pub(crate) fn div(&self, other: &Self) -> Option<Self> {
        if other.sign().is_none_or(|s| s == 0) {
            return None;
        }
        Some(self.mul(&Self::rounded(other.hi.recip(), other.lo.recip())))
    }
    pub(crate) fn intersection(&self, other: &Self) -> Option<Self> {
        let lo = self.lo.clone().max(other.lo.clone());
        let hi = self.hi.clone().min(other.hi.clone());
        (lo <= hi).then_some(Self { lo, hi })
    }
    pub(crate) fn sign(&self) -> Option<i8> {
        if self.lo.is_positive() {
            Some(1)
        } else if self.hi.is_negative() {
            Some(-1)
        } else if self.lo.is_zero() && self.hi.is_zero() {
            Some(0)
        } else {
            None
        }
    }
    /// exp(-x), x >= 0. Range reduction gives x/2^k <= 1/2. An
    /// alternating Taylor series has remainder bounded by its next term;
    /// all intermediate arithmetic and each squaring are outward rounded.
    pub(crate) fn exp_negative(&self) -> Option<Self> {
        fn endpoint(x: &R) -> Option<Bounds> {
            if x.is_negative() {
                return None;
            }
            let mut x = x.clone();
            let mut k = 0;
            let half = R::new(1.into(), 2.into());
            while x > half {
                x /= R::from_integer(2.into());
                k += 1;
                if k > 16 {
                    return None;
                }
            }
            let x = Bounds::rational(x);
            let mut term = Bounds::point(1.)?;
            let mut sum = term.clone();
            for n in 1..=40 {
                term = term.mul(&x).div(&Bounds::point(n as f64)?)?;
                sum = if n % 2 == 0 {
                    sum.add(&term)
                } else {
                    sum.sub(&term)
                };
            }
            let next = term.mul(&x).div(&Bounds::point(41.)?)?;
            sum.lo -= next.hi; // n=40: negative next term, alternating tail.
            for _ in 0..k {
                sum = sum.mul(&sum);
            }
            Some(sum)
        }
        let lower = endpoint(&self.hi)?;
        let upper = endpoint(&self.lo)?;
        Some(Self {
            lo: lower.lo,
            hi: upper.hi,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn cancellation_retains_sub_float_sign_and_real_uncertainty() {
        let one = Bounds::point(1.).unwrap();
        let delta = Bounds::point(1e-25).unwrap();
        assert_eq!(one.add(&delta).sub(&one).sign(), Some(1));
        assert_eq!(
            Bounds::from_interval(I { lo: 1., hi: 1.01 })
                .unwrap()
                .sub(&Bounds::point(1.005).unwrap())
                .sign(),
            None
        );
    }
    #[test]
    fn exponential_encloses_independent_decimal_constants() {
        // Published decimal digits of exp(-1) and exp(-2), bracketed at the
        // last shown digit; these bounds do not use the implementation series.
        for (x, lo) in [
            (1., "3678794411714423215955237701614608674458"),
            (2., "1353352832366126918939994949724844034076"),
        ] {
            let numerator = lo.parse().unwrap();
            let denominator = R::from_integer(10.into()).pow(40).to_integer();
            let lower = R::new(numerator, denominator);
            let upper = &lower + R::new(1.into(), R::from_integer(10.into()).pow(40).to_integer());
            let actual = Bounds::point(x).unwrap().exp_negative().unwrap();
            assert!(actual.lo <= upper && actual.hi >= lower);
            assert!(
                &actual.hi - &actual.lo
                    < R::new(1.into(), R::from_integer(10.into()).pow(43).to_integer())
            );
        }
    }
}
