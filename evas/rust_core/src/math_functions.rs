//! Elementary maps with outward arithmetic and explicit domain/remainder checks.
//! Platform libm supplies representatives, never the enclosure proof.
use crate::{
    interval::{sum_products_sign, Interval as I},
    ir::Error,
};

fn domain(message: &str) -> Error {
    Error::new("waveform_accuracy", message)
}

fn exp_positive(x: f64) -> Result<I, Error> {
    if !x.is_finite() || !(0.0..=512.0).contains(&x) {
        return Err(domain("exp requires a finite argument no greater than 512"));
    }
    let mut r = I::point(x);
    let mut squares = 0;
    while r.hi > 0.5 {
        r = r * I::point(0.5);
        squares += 1;
    }
    let mut term = I::ONE;
    let mut sum = term;
    for n in 1..=24 {
        term = term * r / I::point(n as f64);
        sum = sum + term;
    }
    // For 0 <= r <= 1/2, successive omitted terms have ratio <= 1/52.
    // Twice the first omitted term therefore bounds the complete positive tail.
    let tail = (term * r / I::point(25.0) * I::point(2.0)).hi;
    sum = sum + I { lo: 0.0, hi: tail };
    for _ in 0..squares {
        sum = sum * sum;
    }
    if !sum.finite() {
        return Err(domain("nonfinite exp enclosure"));
    }
    Ok(sum)
}

fn exp_point(x: f64) -> Result<I, Error> {
    if x.is_finite() && x < -512.0 {
        // Monotonicity gives a certified absolute tail beyond range reduction.
        // No platform underflow result participates in this enclosure proof.
        let boundary = I::ONE / exp_positive(512.0)?;
        return Ok(I {
            lo: 0.0,
            hi: boundary.hi,
        });
    }
    if x < 0.0 {
        Ok(I::ONE / exp_positive(-x)?)
    } else {
        exp_positive(x)
    }
}

pub(crate) fn exp(input: I) -> Result<I, Error> {
    if !input.finite() {
        return Err(domain("nonfinite exp input"));
    }
    Ok(I {
        lo: exp_point(input.lo)?.lo,
        hi: exp_point(input.hi)?.hi,
    })
}

fn log_mantissa(m: I) -> I {
    let z = (m - I::ONE) / (m + I::ONE);
    let z2 = z * z;
    let mut term = z;
    let mut sum = term;
    for n in 1..40 {
        term = term * z2;
        sum = sum + term / I::point((2 * n + 1) as f64);
    }
    let tail = I::point(2.0) * term * z2 / I::point(81.0) / (I::ONE - z2);
    I::point(2.0) * sum
        + I {
            lo: -tail.magnitude(),
            hi: tail.magnitude(),
        }
}

fn log_point(x: f64) -> Result<I, Error> {
    if !x.is_finite() || x <= 0.0 {
        return Err(domain("ln requires strictly positive finite input"));
    }
    // Multiplication by 2^52 is exact for a positive subnormal. Normal bit
    // decomposition then avoids constructing overflowing 2^1074 factors.
    let (normal, correction) = if x < f64::MIN_POSITIVE {
        (x * 4503599627370496.0, -52)
    } else {
        (x, 0)
    };
    let bits = normal.to_bits();
    let exponent = ((bits >> 52) & 2047) as i32 - 1023 + correction;
    let m = f64::from_bits((bits & ((1_u64 << 52) - 1)) | (1023_u64 << 52));
    let result =
        log_mantissa(I::point(m)) + I::point(exponent as f64) * log_mantissa(I::point(2.0));
    if !result.finite() {
        return Err(domain("nonfinite ln enclosure"));
    }
    Ok(result)
}

pub(crate) fn ln(input: I) -> Result<I, Error> {
    if !input.finite() {
        return Err(domain("nonfinite ln input"));
    }
    Ok(I {
        lo: log_point(input.lo)?.lo,
        hi: log_point(input.hi)?.hi,
    })
}

fn sqrt_point(x: f64) -> Result<I, Error> {
    if !x.is_finite() || x < 0.0 {
        return Err(domain(
            "sqrt and half-power require nonnegative finite input",
        ));
    }
    if x == 0.0 {
        return Ok(I::ZERO);
    }
    let nominal = x.sqrt();
    let square_sign = |r| sum_products_sign(&[(r, r), (-x, 1.0)]);
    let mut lo = nominal;
    let mut hi = nominal;
    // Verify both selected endpoints with exact binary product comparisons.
    // No assumption about the platform's sqrt rounding is needed.
    for _ in 0..8 {
        let a = square_sign(lo);
        let b = square_sign(hi);
        if matches!(a, Some(-1 | 0)) && matches!(b, Some(0 | 1)) {
            return Ok(I { lo, hi });
        }
        if a == Some(1) {
            lo = lo.next_down();
        }
        if b == Some(-1) {
            hi = hi.next_up();
        }
    }
    Err(domain(
        "platform sqrt representative could not be bracketed",
    ))
}

pub(crate) fn sqrt(input: I) -> Result<I, Error> {
    if !input.finite() {
        return Err(domain("nonfinite sqrt input"));
    }
    Ok(I {
        lo: sqrt_point(input.lo)?.lo,
        hi: sqrt_point(input.hi)?.hi,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn exact_identities_and_domains() {
        assert_eq!(exp(I::ZERO).unwrap(), I::ONE);
        assert_eq!(ln(I::ONE).unwrap(), I::ZERO);
        assert_eq!(sqrt(I::ZERO).unwrap(), I::ZERO);
        assert_eq!(sqrt(I::point(4.0)).unwrap(), I::point(2.0));
        assert!(sqrt(I {
            lo: -f64::from_bits(1),
            hi: 0.0
        })
        .is_err());
        assert!(ln(I::ZERO).is_err());
        assert!(exp(I::point(513.0)).is_err());
    }
    #[test]
    fn negative_exp_tail_has_a_positive_analytic_upper_bound() {
        // The first five series terms give e > 8/3 and hence e^3 > 16.
        // Therefore e^-600 < 2^-800.
        // The deliberately coarser endpoint at -512 must enclose that bound.
        let upper = 2.0_f64.powi(-800);
        for x in [-600., -1000., -f64::MAX] {
            let enclosure = exp(I::point(x)).unwrap();
            assert_eq!(enclosure.lo, 0.);
            assert!(enclosure.hi >= upper && enclosure.hi < 1e-220);
        }
        let crossing = exp(I {
            lo: -1000.,
            hi: -500.,
        })
        .unwrap();
        assert_eq!(crossing.lo, 0.);
        assert_eq!(crossing.hi, exp(I::point(-500.)).unwrap().hi);
        assert!(exp(I::point(513.)).is_err());
        assert!(exp(I::point(f64::NEG_INFINITY)).is_err());
    }

    #[test]
    fn sqrt_endpoints_are_proved_even_at_extremes() {
        for x in [f64::from_bits(1), f64::MIN_POSITIVE, 1e-12, 2.0, f64::MAX] {
            let r = sqrt(I::point(x)).unwrap();
            assert!(sum_products_sign(&[(r.lo, r.lo), (-x, 1.0)]).unwrap() <= 0);
            assert!(sum_products_sign(&[(r.hi, r.hi), (-x, 1.0)]).unwrap() >= 0);
        }
    }
    #[test]
    fn monotone_endpoints_and_subnormal_log() {
        for f in [exp as fn(I) -> Result<I, Error>, ln, sqrt] {
            let a = f(I::point(0.25)).unwrap();
            let b = f(I::point(4.0)).unwrap();
            assert_eq!(
                f(I { lo: 0.25, hi: 4.0 }).unwrap(),
                I { lo: a.lo, hi: b.hi }
            );
        }
        assert!(ln(I::point(f64::from_bits(1))).unwrap().finite());
    }
}
