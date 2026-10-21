//! Owned Forcing point reader. Every optional fast proof is paid before work;
//! unproved candidates retain the old strict reader and its unchanged fee.
use super::{binary, Budget, Curve, MAX_BITS};
use crate::{interval::Interval as I, ir::Error, transition_source_plan::Work};
use num_rational::BigRational as R;
use num_traits::ToPrimitive;
use std::cmp::Ordering;

fn pay(w: &Work, n: u64) -> Result<(), Error> {
    crate::diagnostics::counter("forcing_owned_requested_work", n as usize);
    w.debit(2, n)?;
    crate::diagnostics::counter("forcing_owned_reserved_work", n as usize);
    Ok(())
}
fn limbs(b: u64) -> u64 {
    b.div_ceil(64).saturating_add(1)
}
fn mul(b: u64) -> u64 {
    limbs(b).saturating_pow(2).saturating_mul(16)
}
fn div(b: u64) -> u64 {
    limbs(b).saturating_pow(2).saturating_mul(16)
}
fn gcd(b: u64) -> u64 {
    b.saturating_mul(2)
        .saturating_add(2)
        .saturating_mul(limbs(b))
        .saturating_mul(8)
}
fn operation(b: u64) -> u64 {
    gcd(b)
        .saturating_mul(4)
        .saturating_add(div(b).saturating_mul(8))
        .saturating_add(mul(b).saturating_mul(4))
        .saturating_add(limbs(b).saturating_mul(16))
}
fn width(r: &R) -> u64 {
    r.numer().bits().max(r.denom().bits()).max(1)
}
fn float_width(x: f64) -> u64 {
    if x == 0. {
        return 1;
    }
    let e = ((x.to_bits() >> 52) & 2047) as i64;
    let p = if e == 0 { -1074 } else { e - 1023 - 52 };
    (53 + p.max(0)).max(1 + (-p).max(0)) as u64
}
/// Denominators are positive, normalized original rationals or decoded binary
/// pairs. No generic Ratio::cmp or normalization occurs in this comparison.
pub(super) fn cross(a: &R, b: &R, w: &Work) -> Result<Option<Ordering>, Error> {
    pay(w, 32)?;
    let bits = a
        .numer()
        .bits()
        .saturating_add(b.denom().bits())
        .max(b.numer().bits().saturating_add(a.denom().bits()))
        .max(1);
    if bits > MAX_BITS {
        return Ok(None);
    }
    pay(
        w,
        mul(bits)
            .saturating_mul(2)
            .saturating_add(limbs(bits).saturating_mul(32))
            .saturating_add(64),
    )?;
    crate::diagnostics::counter("forcing_owned_cross_comparisons", 1);
    let left = a.numer() * b.denom();
    let right = b.numer() * a.denom();
    Ok(Some(left.cmp(&right)))
}

fn rational_cmp(a: &R, b: &R, w: &Work) -> Result<Option<Ordering>, Error> {
    cross(a, b, w)
}
/// Exact unreduced integer pair for a finite binary64. No Ratio::new/GCD.
fn parts(x: f64, w: &Work) -> Result<Option<R>, Error> {
    pay(w, 16)?;
    if !x.is_finite() {
        return Ok(None);
    }
    let raw = x.to_bits();
    let e = ((raw >> 52) & 2047) as i64;
    let mantissa = (raw & ((1u64 << 52) - 1)) | if e == 0 { 0 } else { 1u64 << 52 };
    let power = if mantissa == 0 {
        0
    } else if e == 0 {
        -1074
    } else {
        e - 1023 - 52
    };
    let nb = if mantissa == 0 {
        1
    } else {
        (64 - mantissa.leading_zeros()) as u64
    }
    .saturating_add(power.max(0) as u64);
    let db = 1u64.saturating_add((-power).max(0) as u64);
    if nb.max(db) > MAX_BITS {
        return Ok(None);
    }
    pay(
        w,
        limbs(nb)
            .saturating_add(limbs(db))
            .saturating_mul(64)
            .saturating_add(64),
    )?;
    crate::diagnostics::counter("forcing_owned_binary_pairs", 1);
    let signed = if raw >> 63 != 0 {
        -(mantissa as i64)
    } else {
        mantissa as i64
    };
    // from_integer/into_raw are allocation-only constructors, no GCD/division.
    let (mut n, mut d) = R::from_integer(signed.into()).into_raw();
    if power >= 0 {
        n <<= power as usize;
    } else {
        d <<= (-power) as usize;
    }
    Ok(Some(R::new_raw(n, d)))
}
fn compare_float(r: &R, x: f64, w: &Work) -> Result<Option<Ordering>, Error> {
    match parts(x, w)? {
        Some(pair) => cross(r, &pair, w),
        None => Ok(None),
    }
}
fn certify(value: &R, point_only: bool, w: &Work) -> Result<Option<(f64, I)>, Error> {
    pay(w, 16)?;
    let n = limbs(value.numer().bits());
    let d = limbs(value.denom().bits());
    // high_bits_to_u64 scans every limb, plus sign/exponent/float operations.
    pay(w, n.saturating_add(d).saturating_mul(64).saturating_add(64))?;
    crate::diagnostics::counter("forcing_owned_integer_conversions", 2);
    let (Some(a), Some(b)) = (value.numer().to_f64(), value.denom().to_f64()) else {
        return Ok(None);
    };
    pay(w, 64)?;
    let guess = a / b;
    if !a.is_finite() || !b.is_finite() || b <= 0. {
        return Ok(None);
    }
    certify_guess(value, guess, point_only, w)
}
fn certify_guess(
    value: &R,
    guess: f64,
    point_only: bool,
    w: &Work,
) -> Result<Option<(f64, I)>, Error> {
    pay(w, 16)?;
    if !guess.is_finite() {
        return Ok(None);
    }

    let Some(order) = compare_float(value, guess, w)? else {
        return Ok(None);
    };
    if order == Ordering::Equal {
        let g = if guess == 0. { 0. } else { guess };
        return Ok(Some((g, I::point(g))));
    }
    if point_only {
        return Ok(None);
    }
    pay(w, 64)?;
    let lo = guess.next_down().next_down();
    let hi = guess.next_up().next_up();
    if !lo.is_finite() || !hi.is_finite() {
        return Ok(None);
    }
    let Some(a) = compare_float(value, lo, w)? else {
        return Ok(None);
    };
    let Some(b) = compare_float(value, hi, w)? else {
        return Ok(None);
    };
    if a == Ordering::Less || b == Ordering::Greater {
        return Ok(None);
    }
    Ok(Some((guess, I { lo, hi })))
}
// History has an existing strict-box/representative contract. Preserve the
// optional reader's refusal boundary, then tighten only its nonpoint successes
// using the exact interpolated value and the already-paid strict helpers.
fn certify_history(value: &R, point_only: bool, w: &Work) -> Result<Option<(f64, I)>, Error> {
    let Some(point) = certify(value, point_only, w)? else {
        return Ok(None);
    };
    if point.1.lo == point.1.hi {
        return Ok(Some(point));
    }
    let Some(bounds) = super::enclosure_with_work(value, w)? else {
        return Ok(None);
    };
    let mut paid = super::history_paid::Paid::new(w);
    let nearest = paid.nearest(value);
    paid.finish(nearest.map(|nearest| (nearest, bounds)))
}
impl Curve {
    pub(crate) fn try_forcing_point(&self, time: f64, w: &Work) -> Result<Option<(f64, I)>, Error> {
        self.try_point(time, w, false)
    }
    pub(crate) fn try_history_point(&self, time: f64, w: &Work) -> Result<Option<(f64, I)>, Error> {
        self.try_point(time, w, true)
    }
    fn try_point(
        &self,
        time: f64,
        w: &Work,
        strict_history: bool,
    ) -> Result<Option<(f64, I)>, Error> {
        pay(w, 32)?;
        let certify_point = |value: &R, point_only: bool| {
            if strict_history {
                certify_history(value, point_only, w)
            } else {
                certify(value, point_only, w)
            }
        };
        if !time.is_finite() {
            return Ok(None);
        }
        let qbits = float_width(time);
        pay(w, operation(qbits))?;
        crate::diagnostics::counter("forcing_owned_time_conversions", 1);
        let Some(q) = binary(time) else {
            return Ok(None);
        };
        // All metadata and loop visits paid before inspecting original knots.
        pay(
            w,
            (self.0.len() as u64).saturating_mul(8).saturating_add(16),
        )?;
        let (mut tb, mut vb) = (1u64, 1u64);
        for (t, v) in &self.0 {
            tb = tb.max(width(t));
            vb = vb.max(width(v));
        }
        let (mut lo, mut hi) = (0, self.0.len());
        while lo < hi {
            pay(w, 16)?;
            let mid = lo + (hi - lo) / 2;
            let Some(order) = rational_cmp(&self.0[mid].0, &q, w)? else {
                return Ok(None);
            };
            if order == Ordering::Less {
                lo = mid + 1
            } else {
                hi = mid
            }
        }
        let Some((end, b)) = self.0.get(lo) else {
            return Ok(None);
        };
        let Some(order) = rational_cmp(end, &q, w)? else {
            return Ok(None);
        };
        if order == Ordering::Equal {
            let r = certify_point(b, true)?;
            if r.is_some() {
                crate::diagnostics::counter("forcing_owned_knot_success", 1);
                crate::diagnostics::counter("forcing_owned_point_success", 1);
            }
            return Ok(r);
        }
        let Some((start, a)) = lo.checked_sub(1).and_then(|i| self.0.get(i)) else {
            return Ok(None);
        };
        pay(w, limbs(vb).saturating_mul(64).saturating_add(64))?;
        // Original source/shaped knot values are canonical binary() Ratios.
        // Ratio::eq itself delegates to recursive cmp; compare fields instead.
        if a.numer() == b.numer() && a.denom() == b.denom() {
            let r = certify_point(a, true)?;
            if r.is_some() {
                crate::diagnostics::counter("forcing_owned_plateau_success", 1);
                crate::diagnostics::counter("forcing_owned_point_success", 1);
            }
            return Ok(r);
        }
        let delta = vb.saturating_mul(2).saturating_add(1);
        let elapsed = tb.saturating_add(qbits).saturating_add(1);
        let duration = tb.saturating_mul(2).saturating_add(1);
        let fraction = elapsed.saturating_add(duration).saturating_add(1);
        let change = delta.saturating_add(fraction).saturating_add(1);
        let result = vb.saturating_add(change).saturating_add(1);
        let widths = [delta, elapsed, duration, fraction, change, result];
        if widths.iter().any(|b| *b > MAX_BITS) {
            return Ok(None);
        }
        pay(
            w,
            widths
                .into_iter()
                .fold(0u64, |s, b| s.saturating_add(operation(b))),
        )?;
        crate::diagnostics::counter("forcing_owned_interpolations", 1);
        let mut budget = Budget(0);
        let Some(delta) = budget.check(b - a) else {
            return Ok(None);
        };
        let Some(elapsed) = budget.check(&q - start) else {
            return Ok(None);
        };
        let Some(duration) = budget.check(end - start) else {
            return Ok(None);
        };
        let Some(fraction) = budget.check(elapsed / duration) else {
            return Ok(None);
        };
        let Some(change) = budget.check(delta * fraction) else {
            return Ok(None);
        };
        let Some(value) = budget.check(a + change) else {
            return Ok(None);
        };
        let r = certify_point(&value, false)?;
        if r.is_some() {
            crate::diagnostics::counter("forcing_owned_enclosure_success", 1);
            crate::diagnostics::counter("forcing_owned_point_success", 1);
        }
        Ok(r)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn forcing_owned_exact_cross_and_certified_enclosure_independent_controls() {
        for (a, b) in [
            (R::new(7.into(), 6.into()), R::new((-6).into(), 7.into())),
            (R::new((-5).into(), 3.into()), R::new((-5).into(), 3.into())),
            (R::new(1.into(), 3.into()), R::new(2.into(), 7.into())),
        ] {
            let w = Work::default();
            assert_eq!(rational_cmp(&a, &b, &w).unwrap(), Some(a.cmp(&b)));
        }
        let w = Work::default();
        let r = R::new(1.into(), 3.into());
        let (v, b) = certify(&r, false, &w).unwrap().unwrap();
        assert!(binary(b.lo).unwrap() <= r && r <= binary(b.hi).unwrap() && b.lo <= v && v <= b.hi);
        assert!(certify_guess(&r, 100., false, &w).unwrap().is_none());
        assert!(certify_guess(&r, f64::INFINITY, false, &w)
            .unwrap()
            .is_none());
        let zero = R::from_integer(0.into());
        let (v, b) = certify_guess(&zero, -0., true, &w).unwrap().unwrap();
        assert_eq!(v.to_bits(), 0);
        assert_eq!(b.lo.to_bits(), 0);
    }
    #[test]
    fn forcing_owned_nonbinary_corners_plateau_and_point_certificate() {
        let c = Curve(vec![
            (R::new(0.into(), 1.into()), binary(-0.5).unwrap()),
            (R::new(1.into(), 3.into()), binary(-0.5).unwrap()),
            (R::new(2.into(), 3.into()), binary(0.75).unwrap()),
            (R::new(1.into(), 1.into()), binary(0.75).unwrap()),
        ]);
        let w = Work::default();
        for t in [
            0.,
            0.2,
            1. / 3.,
            (1f64 / 3.).next_up(),
            0.5,
            (2f64 / 3.).next_down(),
            2. / 3.,
            0.9,
            1.,
        ] {
            let (v, b) = c.try_forcing_point(t, &w).unwrap().unwrap();
            let exact = c.value(&binary(t).unwrap(), &mut Budget(0)).unwrap();
            assert!(
                binary(b.lo).unwrap() <= exact
                    && exact <= binary(b.hi).unwrap()
                    && b.lo <= v
                    && v <= b.hi
            );
        }
    }
    #[test]
    fn forcing_owned_width_overflow_conversion_and_sticky_precharge_controls() {
        let w = Work::default();
        let big = R::from_integer(1.into()).into_raw().0 << 4095usize;
        let a = R::new(big.clone(), 3.into());
        let b = R::new(1.into(), big);
        let (r, d) = crate::diagnostics::capture(Default::default(), || rational_cmp(&a, &b, &w));
        assert!(r.unwrap().is_none());
        assert_eq!(d.counters.get("forcing_owned_cross_comparisons"), None);
        let huge = R::new(
            (R::from_integer(1.into()).into_raw().0 << 1500usize) + 1,
            (R::from_integer(1.into()).into_raw().0 << 1499usize) + 3,
        );
        assert!(certify(&huge, false, &w).unwrap().is_none());
        let short = Work::limited([128, 8192, 1]);
        let c = Curve::source(&[[0., 0.], [1., 1.]]).unwrap();
        for _ in 0..3 {
            let (r, d) = crate::diagnostics::capture(Default::default(), || {
                c.try_forcing_point(0.5, &short)
            });
            assert_eq!(r.unwrap_err().kind, "step_budget");
            assert_eq!(d.counters.get("forcing_owned_cross_comparisons"), None);
            assert_eq!(d.counters.get("forcing_owned_time_conversions"), None);
        }
    }
}
