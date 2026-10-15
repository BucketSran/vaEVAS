use super::*;

fn old_multiply(a: f64, b: f64) -> Interval {
    let value = a * b;
    Interval::rounded(value, equal_products(a, b, value, 1.))
}
fn bits(a: Interval) -> (u64, u64) {
    (a.lo.to_bits(), a.hi.to_bits())
}

// Each exponent and both signs, with significands at boundaries and in the
// interior, includes all finite classes and underflow/overflow neighbors.
#[test]
fn exact_zero_product_preserves_old_bits_across_binary64_classes() {
    let fractions = [
        0,
        1,
        2,
        (1_u64 << 51) - 1,
        1_u64 << 51,
        (1_u64 << 52) - 2,
        (1_u64 << 52) - 1,
    ];
    let mut count = 0;
    for sign in [0, 1_u64 << 63] {
        for exponent in 0..=2047_u64 {
            for fraction in fractions {
                let x = f64::from_bits(sign | (exponent << 52) | fraction);
                for zero in [0., -0.] {
                    for (a, b) in [(zero, x), (x, zero)] {
                        assert_eq!(
                            bits(multiply(a, b)),
                            bits(old_multiply(a, b)),
                            "{:x} {:x}",
                            a.to_bits(),
                            b.to_bits()
                        );
                        count += 1;
                    }
                }
            }
        }
    }
    for (a, b) in [
        (f64::from_bits(1), 0.5),
        (1e-300, 1e-300),
        (f64::MAX, 2.),
        (1., 3.),
        (-1., 3.),
    ] {
        assert_eq!(bits(multiply(a, b)), bits(old_multiply(a, b)));
    }
    eprintln!("zero_factor_scalar_comparisons={count}");
}

fn old_interval(a: Interval, b: Interval) -> Interval {
    if !a.finite() || !b.finite() {
        return Interval::WHOLE;
    }
    let v = [
        old_multiply(a.lo, b.lo),
        old_multiply(a.lo, b.hi),
        old_multiply(a.hi, b.lo),
        old_multiply(a.hi, b.hi),
    ];
    Interval {
        lo: v.iter().map(|v| v.lo).fold(f64::INFINITY, f64::min),
        hi: v.iter().map(|v| v.hi).fold(f64::NEG_INFINITY, f64::max),
    }
}
#[test]
fn exact_zero_product_keeps_four_endpoint_hull_and_nonfinite_refusal() {
    let values = [
        f64::NEG_INFINITY,
        -f64::MAX,
        -1.,
        -f64::MIN_POSITIVE,
        -f64::from_bits(1),
        -0.,
        0.,
        f64::from_bits(1),
        f64::MIN_POSITIVE,
        1.,
        f64::MAX,
        f64::INFINITY,
        f64::NAN,
    ];
    let zero_boxes = [
        Interval::point(0.),
        Interval::point(-0.),
        Interval { lo: -0., hi: 0. },
        Interval { lo: 0., hi: -0. },
    ];
    for &lo in &values {
        for &hi in &values {
            if lo > hi {
                continue;
            }
            let a = Interval { lo, hi };
            for b in zero_boxes {
                assert_eq!(bits(a * b), bits(old_interval(a, b)));
                assert_eq!(bits(b * a), bits(old_interval(b, a)));
            }
        }
    }
    assert!(!(Interval::ZERO
        * Interval {
            lo: f64::NEG_INFINITY,
            hi: f64::INFINITY
        })
    .finite());
    assert!(!(Interval::point(f64::from_bits(1)) * Interval::point(0.5)).zero());
}

thread_local! {
    static WORK: std::cell::Cell<(usize,usize)> = const { std::cell::Cell::new((0,0)) };
}
pub(super) fn record(a: f64, b: f64) {
    WORK.with(|w| {
        let (all, zero) = w.get();
        w.set((
            all + 1,
            zero + usize::from((a == 0. || b == 0.) && a.is_finite() && b.is_finite()),
        ));
    });
}
pub(crate) fn reset_work() {
    WORK.with(|w| w.set((0, 0)));
}
pub(crate) fn work() -> (usize, usize) {
    WORK.with(|w| w.get())
}
