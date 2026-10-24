//! Paid rational enclosures for monotone elementary functions.
//! No floating point approximation, runtime state, or private work allowance.
use num_rational::BigRational as R;
use num_traits::{Signed, Zero};
use std::{cmp::Ordering, marker::PhantomData};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum Function {
    Ln,
    Exp,
}
#[derive(Debug, PartialEq, Eq)]
pub(crate) enum Fault<E> {
    Quota(E),
    Domain,
    NonFinite,
    PrecisionLimit,
}

const MAX_PRECISION: u32 = 4096;
const MAX_WIDTH: u64 = 131072;

fn width(x: &R) -> u64 {
    x.numer().bits().max(x.denom().bits())
}
fn fee(bits: u64) -> u64 {
    let n = bits / 64 + 2;
    64u64.saturating_add(16u64.saturating_mul(n.saturating_mul(n).saturating_mul(n)))
}
struct Calc<'a, E, F: FnMut(u64) -> Result<(), E>> {
    debit: &'a mut F,
    marker: PhantomData<E>,
}
impl<E, F: FnMut(u64) -> Result<(), E>> Calc<'_, E, F> {
    fn pay(&mut self, bits: u64) -> Result<(), Fault<E>> {
        if bits > MAX_WIDTH {
            return Err(Fault::PrecisionLimit);
        }
        (self.debit)(fee(bits)).map_err(Fault::Quota)
    }
    fn constant(&mut self, n: i64) -> Result<R, Fault<E>> {
        self.pay(64)?;
        Ok(R::from_integer(n.into()))
    }
    fn copy(&mut self, x: &R) -> Result<R, Fault<E>> {
        self.pay(width(x))?;
        Ok(x.clone())
    }
    fn cmp(&mut self, a: &R, b: &R) -> Result<Ordering, Fault<E>> {
        self.pay(width(a).saturating_add(width(b)).saturating_add(2))?;
        Ok(a.cmp(b))
    }
    fn add(&mut self, a: &R, b: &R) -> Result<R, Fault<E>> {
        self.pay(
            width(a)
                .saturating_add(width(b))
                .saturating_mul(2)
                .saturating_add(4),
        )?;
        Ok(a + b)
    }
    fn sub(&mut self, a: &R, b: &R) -> Result<R, Fault<E>> {
        self.pay(
            width(a)
                .saturating_add(width(b))
                .saturating_mul(2)
                .saturating_add(4),
        )?;
        Ok(a - b)
    }
    fn mul(&mut self, a: &R, b: &R) -> Result<R, Fault<E>> {
        self.pay(
            width(a)
                .saturating_add(width(b))
                .saturating_mul(2)
                .saturating_add(4),
        )?;
        Ok(a * b)
    }
    fn div(&mut self, a: &R, b: &R) -> Result<R, Fault<E>> {
        if b.is_zero() {
            return Err(Fault::Domain);
        }
        self.pay(
            width(a)
                .saturating_add(width(b))
                .saturating_mul(2)
                .saturating_add(4),
        )?;
        Ok(a / b)
    }
    fn pow2(&mut self, exponent: i32) -> Result<R, Fault<E>> {
        let bits = u64::from(exponent.unsigned_abs()) + 2;
        self.pay(bits)?;
        let one = self.constant(1)?;
        Ok(if exponent >= 0 {
            R::from_integer(one.numer() << exponent as usize)
        } else {
            R::new(
                one.numer().clone(),
                one.numer() << exponent.unsigned_abs() as usize,
            )
        })
    }
    /// Outward dyadic quantization for nonnegative series intermediates.
    fn dyadic(&mut self, x: &R, bits: u32, up: bool) -> Result<R, Fault<E>> {
        self.pay(
            width(x)
                .saturating_add(u64::from(bits))
                .saturating_mul(2)
                .saturating_add(4),
        )?;
        let numerator = x.numer() << bits as usize;
        let mut quotient = &numerator / x.denom();
        if up && !(&numerator % x.denom()).is_zero() {
            quotient += 1;
        }
        let one = self.constant(1)?;
        Ok(R::new(quotient, one.numer() << bits as usize))
    }
    /// ln(r), 1 <= r <= 2. Positive atanh terms and a geometric tail.
    fn log_series(&mut self, r: &R, bits: u32) -> Result<(R, R), Fault<E>> {
        let one = self.constant(1)?;
        let two = self.constant(2)?;
        let numerator = self.sub(r, &one)?;
        if numerator.is_zero() {
            return Ok((self.constant(0)?, self.constant(0)?));
        }
        let denominator = self.add(r, &one)?;
        let t = self.div(&numerator, &denominator)?;
        let square = self.mul(&t, &t)?;
        let complement = self.sub(&one, &square)?;
        // Each positive series operation is rounded outward to a dyadic
        // enclosure. This prevents denominators from growing with the term
        // count. Power widths stay <= 9/4 ulps (ratio <= 1/9), so each
        // sum iteration adds < 5 ulps. With <= 4192 iterations, 32 guard
        // bits cover the doubled sum width and the final tail.
        let working = bits + 32;
        let epsilon = self.pow2(-(working as i32))?;
        let mut power_low = self.dyadic(&t, working, false)?;
        let mut power_high = self.dyadic(&t, working, true)?;
        let mut sum_low = self.constant(0)?;
        let mut sum_high = self.constant(0)?;
        for n in 0..(working + 32) {
            let odd = self.constant(i64::from(2 * n + 1))?;
            let a = self.div(&power_low, &odd)?;
            let b = self.div(&power_high, &odd)?;
            let a = self.add(&sum_low, &a)?;
            let b = self.add(&sum_high, &b)?;
            sum_low = self.dyadic(&a, working, false)?;
            sum_high = self.dyadic(&b, working, true)?;
            let a = self.mul(&power_low, &square)?;
            let b = self.mul(&power_high, &square)?;
            power_low = self.dyadic(&a, working, false)?;
            power_high = self.dyadic(&b, working, true)?;
            let next_odd = self.constant(i64::from(2 * n + 3))?;
            let tail_denominator = self.mul(&next_odd, &complement)?;
            let twice_power = self.mul(&two, &power_high)?;
            let tail = self.div(&twice_power, &tail_denominator)?;
            if self.cmp(&tail, &epsilon)? != Ordering::Greater {
                let low = self.mul(&two, &sum_low)?;
                let high = self.mul(&two, &sum_high)?;
                return Ok((low, self.add(&high, &tail)?));
            }
        }
        Err(Fault::PrecisionLimit)
    }
    fn logarithm(&mut self, x: &R, bits: u32) -> Result<(R, R), Fault<E>> {
        if !x.is_positive() {
            return Err(Fault::Domain);
        }
        let difference = i128::from(x.numer().bits()) - i128::from(x.denom().bits());
        if difference.abs() > 16384 {
            return Err(Fault::PrecisionLimit);
        }
        let mut k = difference as i32;
        let mut scale = self.pow2(k)?;
        if self.cmp(x, &scale)? == Ordering::Less {
            k -= 1;
            scale = self.pow2(k)?;
        }
        let mut reduced = self.div(x, &scale)?;
        let one = self.constant(1)?;
        let two = self.constant(2)?;
        let three = self.constant(3)?;
        let center = self.div(&three, &two)?;
        if self.cmp(&reduced, &center)? == Ordering::Greater {
            reduced = self.div(&reduced, &two)?;
            k += 1;
        }
        // Center around one so near-one inputs avoid cancellation with ln2.
        let below_one = self.cmp(&reduced, &one)? == Ordering::Less;
        if below_one {
            reduced = self.div(&one, &reduced)?;
        }
        let (low, high) = self.log_series(&reduced, bits + 32)?;
        let (low, high) = if below_one {
            let zero = self.constant(0)?;
            (self.sub(&zero, &high)?, self.sub(&zero, &low)?)
        } else {
            (low, high)
        };
        if k == 0 {
            return Ok((low, high));
        }
        let two = self.constant(2)?;
        let (ln2_low, ln2_high) = self.log_series(&two, bits + 32)?;
        let factor = self.constant(i64::from(k))?;
        let (a, b) = if k > 0 {
            (ln2_low, ln2_high)
        } else {
            (ln2_high, ln2_low)
        };
        let a = self.mul(&factor, &a)?;
        let b = self.mul(&factor, &b)?;
        Ok((self.add(&low, &a)?, self.add(&high, &b)?))
    }
    fn exponential(&mut self, x: &R, bits: u32) -> Result<(R, R), Fault<E>> {
        let zero = self.constant(0)?;
        let negative = self.cmp(x, &zero)? == Ordering::Less;
        let magnitude = if negative {
            self.sub(&zero, x)?
        } else {
            self.copy(x)?
        };
        let limit = self.constant(1024)?;
        if self.cmp(&magnitude, &limit)? == Ordering::Greater {
            return Err(Fault::PrecisionLimit);
        }
        let one = self.constant(1)?;
        if magnitude.is_zero() {
            return Ok((self.copy(&one)?, one));
        }
        let two = self.constant(2)?;
        let half = self.div(&one, &two)?;
        let mut reduced = self.copy(&magnitude)?;
        let mut squarings = 0;
        let mut growth_bound = 1u32;
        while self.cmp(&reduced, &half)? == Ordering::Greater {
            reduced = self.div(&reduced, &two)?;
            squarings += 1;
            growth_bound *= 2;
        }
        // Initial U < 2. Squaring amplifies an interval width by at most
        // 2^(k+2^k-1). The initial width is <= (6*N+1) ulps,
        // N <= 6240, and k <= 11. The extra 64 bits cover that factor
        // and every outward quantization. U0 < 7/4 ensures the bound
        // Uj < 2^(2^j) persists even after quantization.
        let working = bits + growth_bound + 64;
        let epsilon = self.pow2(-(working as i32))?;
        let mut term_low = self.copy(&one)?;
        let mut term_high = self.copy(&one)?;
        let mut sum_low = self.copy(&one)?;
        let mut sum_high = self.copy(&one)?;
        let mut enclosure = None;
        for n in 1..(working + 32) {
            let n_ratio = self.constant(i64::from(n))?;
            let a = self.mul(&term_low, &reduced)?;
            let b = self.mul(&term_high, &reduced)?;
            let a = self.div(&a, &n_ratio)?;
            let b = self.div(&b, &n_ratio)?;
            term_low = self.dyadic(&a, working, false)?;
            term_high = self.dyadic(&b, working, true)?;
            let a = self.add(&sum_low, &term_low)?;
            let b = self.add(&sum_high, &term_high)?;
            sum_low = self.dyadic(&a, working, false)?;
            sum_high = self.dyadic(&b, working, true)?;
            let next_n = self.constant(i64::from(n + 1))?;
            let next_product = self.mul(&term_high, &reduced)?;
            let next = self.div(&next_product, &next_n)?;
            // Remaining ratios <= 1/2, hence tail <= 2*next.
            let tail = self.mul(&two, &next)?;
            if self.cmp(&tail, &epsilon)? != Ordering::Greater {
                enclosure = Some((sum_low, self.add(&sum_high, &tail)?));
                break;
            }
        }
        let (mut low, mut high) = enclosure.ok_or(Fault::PrecisionLimit)?;
        for _ in 0..squarings {
            let a = self.mul(&low, &low)?;
            let b = self.mul(&high, &high)?;
            low = self.dyadic(&a, working, false)?;
            high = self.dyadic(&b, working, true)?;
        }
        if negative {
            Ok((self.div(&one, &high)?, self.div(&one, &low)?))
        } else {
            Ok((low, high))
        }
    }
}

/// Enclose the full mathematical image, never a nominal point surrogate.
/// `precision_bits` controls endpoint error, not the width of the input image.
pub(crate) fn bounds<E>(
    function: Function,
    lo: &R,
    hi: &R,
    precision_bits: u32,
    debit: &mut impl FnMut(u64) -> Result<(), E>,
) -> Result<(R, R), Fault<E>> {
    let mut c = Calc {
        debit,
        marker: PhantomData,
    };
    c.pay(64)?;
    if precision_bits == 0 || precision_bits > MAX_PRECISION {
        return Err(Fault::PrecisionLimit);
    }
    if !lo.denom().is_positive() || !hi.denom().is_positive() {
        return Err(Fault::NonFinite);
    }
    if c.cmp(lo, hi)? == Ordering::Greater {
        return Err(Fault::Domain);
    }
    let low = match function {
        Function::Ln => c.logarithm(lo, precision_bits)?,
        Function::Exp => c.exponential(lo, precision_bits)?,
    };
    if c.cmp(lo, hi)? == Ordering::Equal {
        return Ok(low);
    }
    let high = match function {
        Function::Ln => c.logarithm(hi, precision_bits)?,
        Function::Exp => c.exponential(hi, precision_bits)?,
    };
    Ok((low.0, high.1))
}
