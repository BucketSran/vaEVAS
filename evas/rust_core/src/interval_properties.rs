//! Supplemental properties. BigRational is independent of the u128/limb implementation.
use super::{equal_products, sum_products_sign, Interval as I};
use num_rational::BigRational as Q;
use proptest::prelude::*;

fn finite() -> impl Strategy<Value = f64> {
    any::<u64>()
        .prop_map(f64::from_bits)
        .prop_filter("finite", |x| x.is_finite())
}

fn exact(x: f64) -> Q {
    Q::from_float(x).unwrap()
}

fn contains(interval: I, value: &Q) -> bool {
    !interval.lo.is_nan()
        && !interval.hi.is_nan()
        && (interval.lo == f64::NEG_INFINITY || exact(interval.lo) <= *value)
        && (interval.hi == f64::INFINITY || exact(interval.hi) >= *value)
}

proptest! {
    #![proptest_config(ProptestConfig::with_cases(512))]

    #[test]
    fn endpoints_enclose_exact_arithmetic(a in finite(), b in finite(), c in finite(), d in finite()) {
        let left=I {lo:a.min(b), hi:a.max(b)};
        let right=I {lo:c.min(d), hi:c.max(d)};
        for x in [left.lo, left.hi] {
            for y in [right.lo, right.hi] {
                prop_assert!(contains(left+right, &(exact(x)+exact(y))));
                prop_assert!(contains(left-right, &(exact(x)-exact(y))));
                prop_assert!(contains(left*right, &(exact(x)*exact(y))));
                if right.lo > 0.0 || right.hi < 0.0 {
                    prop_assert!(contains(left/right, &(exact(x)/exact(y))));
                }
            }
        }
    }

    #[test]
    fn widening_inputs_cannot_shrink_bounds(mut values in prop::array::uniform4(finite()), c in finite(), d in finite()) {
        values.sort_by(f64::total_cmp);
        let outer=I {lo:values[0], hi:values[3]};
        let inner=I {lo:values[1], hi:values[2]};
        let rhs=I {lo:c.min(d), hi:c.max(d)};
        for (wide, narrow) in [(outer+rhs,inner+rhs),(outer-rhs,inner-rhs),(outer*rhs,inner*rhs),(outer/rhs,inner/rhs)] {
            // Overflow and zero-containing divisors deliberately return a
            // conservative whole interval; only finite bounds promise isotony.
            if wide.finite() && narrow.finite() {
                prop_assert!(wide.lo <= narrow.lo && wide.hi >= narrow.hi);
            }
        }
    }

    #[test]
    fn exactly_representable_points_stay_points(a in -1_000_000i32..1_000_000, b in -1_000_000i32..1_000_000) {
        let (a,b)=(f64::from(a),f64::from(b));
        prop_assert_eq!(I::point(a)+I::point(b), I::point(a+b));
        prop_assert_eq!(I::point(a)*I::point(b), I::point(a*b));
        prop_assert_eq!(I::point(a)/I::point(8.0), I::point(a/8.0));
    }

    #[test]
    fn exact_product_equality_and_sum_sign(values in prop::array::uniform8(finite())) {
        let mut sum=exact(0.0);
        let terms:Vec<_>=values.as_chunks::<2>().0.iter().map(|pair|(pair[0],pair[1])).collect();
        for &(a,b) in &terms { sum += exact(a)*exact(b); }
        let sign=match sum.cmp(&exact(0.0)) {std::cmp::Ordering::Less=>-1,std::cmp::Ordering::Equal=>0,std::cmp::Ordering::Greater=>1};
        prop_assert_eq!(sum_products_sign(&terms), Some(sign));
        prop_assert_eq!(equal_products(values[0],values[1],values[2],values[3]),
                        exact(values[0])*exact(values[1]) == exact(values[2])*exact(values[3]));
        prop_assert!(equal_products(values[0],values[1],values[1],values[0]));
    }
}
