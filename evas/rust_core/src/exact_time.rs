//! Bounded exact binary-rational predicates for causal event time coordinates.
//! Eight products of three finite binary64 operands need fewer than 6300 bits.
//! No floating product, time subtraction, or nominal-clock rounding enters a sign.
use crate::interval::Interval as I;

pub(crate) fn sum_triples_sign(terms: &[(f64, f64, f64)]) -> Option<i8> {
    if terms.len() > 8
        || terms
            .iter()
            .any(|(a, b, c)| !a.is_finite() || !b.is_finite() || !c.is_finite())
    {
        return None;
    }
    let mut sums = [[0_u64; 100]; 2];
    for &(a, b, c) in terms {
        let mut words = [1_u64, 0, 0];
        let mut exponent = 0_i32;
        let mut negative = false;
        for value in [a, b, c] {
            let raw = value.to_bits();
            let encoded = ((raw >> 52) & 2047) as i32;
            let mantissa = (raw & ((1_u64 << 52) - 1)) | if encoded == 0 { 0 } else { 1_u64 << 52 };
            exponent += if encoded == 0 { -1074 } else { encoded - 1075 };
            negative ^= value.is_sign_negative();
            let mut carry = 0_u128;
            for word in &mut words {
                let product = *word as u128 * mantissa as u128 + carry;
                *word = product as u64;
                carry = product >> 64;
            }
            if carry != 0 {
                return None;
            }
        }
        let shift = (exponent + 3222) as usize;
        for (j, word) in words.into_iter().enumerate() {
            let shifted = (word as u128) << (shift % 64);
            for (k, mut carry) in [shifted as u64, (shifted >> 64) as u64]
                .into_iter()
                .enumerate()
            {
                let mut i = shift / 64 + j + k;
                while carry != 0 {
                    if i >= 100 {
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

#[derive(Clone, Copy, Debug, PartialEq)]
pub(crate) struct Clock {
    pub(crate) start: f64,
    pub(crate) period: f64,
    pub(crate) index: usize,
}
impl Clock {
    pub(crate) fn order(self, other: Self) -> Option<std::cmp::Ordering> {
        if self.index > crate::schedule::EVENT_BUDGET || other.index > crate::schedule::EVENT_BUDGET
        {
            return None;
        }
        crate::interval::sum_products_sign(&[
            (self.start, 1.),
            (self.period, self.index as f64),
            (-other.start, 1.),
            (-other.period, other.index as f64),
        ])
        .map(|s| s.cmp(&0))
    }
    /// Tight enclosure of `time - (start + index*period)`. Searching the local
    /// result avoids the cancellation in subtracting a rounded absolute clock.
    pub(crate) fn delta(self, time: f64) -> Option<I> {
        if self.index > crate::schedule::EVENT_BUDGET || !time.is_finite() {
            return None;
        }
        let sign = |value| {
            crate::interval::sum_products_sign(&[
                (value, 1.),
                (-time, 1.),
                (self.start, 1.),
                (self.period, self.index as f64),
            ])
        };
        enclose_zero(sign)
    }
    pub(crate) fn difference(self, other: Self) -> Option<I> {
        if self.index > crate::schedule::EVENT_BUDGET || other.index > crate::schedule::EVENT_BUDGET
        {
            return None;
        }
        enclose_zero(|value| {
            sum_triples_sign(&[
                (value, 1., 1.),
                (-self.start, 1., 1.),
                (-self.period, self.index as f64, 1.),
                (other.start, 1., 1.),
                (other.period, other.index as f64, 1.),
            ])
        })
    }
}

pub(crate) fn enclose_zero(sign: impl Fn(f64) -> Option<i8>) -> Option<I> {
    let rank = |value: f64| {
        if value.is_sign_negative() {
            !value.to_bits()
        } else {
            value.to_bits() | (1_u64 << 63)
        }
    };
    let from_rank = |value: u64| {
        f64::from_bits(if value >> 63 == 0 {
            !value
        } else {
            value & !(1_u64 << 63)
        })
    };
    let mut lo = rank(-f64::MAX);
    let mut hi = rank(f64::MAX);
    if sign(-f64::MAX)? > 0 || sign(f64::MAX)? < 0 {
        return None;
    }
    while lo <= hi {
        let mid = lo + (hi - lo) / 2;
        let value = from_rank(mid);
        match sign(value)? {
            0 => return Some(I::point(value)),
            -1 => lo = mid + 1,
            _ => hi = mid - 1,
        }
    }
    Some(I {
        lo: from_rank(hi),
        hi: from_rank(lo),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use num_rational::BigRational as Q;
    use proptest::prelude::*;
    fn q(v: f64) -> Q {
        Q::from_float(v).unwrap()
    }
    fn finite() -> impl Strategy<Value = f64> {
        any::<u64>()
            .prop_map(f64::from_bits)
            .prop_filter("finite", |v| v.is_finite())
    }
    proptest! {
        #![proptest_config(ProptestConfig::with_cases(512))]
        #[test]
        fn triple_sign_matches_independent_rational(values in prop::array::uniform24(finite())) {
            let terms:Vec<_> = values.as_chunks::<3>().0.iter().map(|v|(v[0],v[1],v[2])).collect();
            let exact = terms.iter().fold(q(0.), |s,&(a,b,c)|s+q(a)*q(b)*q(c));
            prop_assert_eq!(sum_triples_sign(&terms),Some(match exact.cmp(&q(0.)) {std::cmp::Ordering::Less=>-1,std::cmp::Ordering::Equal=>0,std::cmp::Ordering::Greater=>1}));
        }
        #[test]
        fn clock_difference_is_tight(a in finite(),p in finite(),b in finite(),qv in finite(),k in 0usize..1_000_000,l in 0usize..1_000_000) {
            let left=Clock {start:a,period:p,index:k};
            let right=Clock {start:b,period:qv,index:l};
            let exact=q(a)+q(p)*q(k as f64)-q(b)-q(qv)*q(l as f64);
            if let Some(bound)=left.difference(right) {
                prop_assert!(q(bound.lo)<=exact && exact<=q(bound.hi));
                prop_assert!(bound.lo==bound.hi || bound.lo.next_up()==bound.hi);
            } else {prop_assert!(exact<q(-f64::MAX) || exact>q(f64::MAX));}
        }
        #[test]
        fn local_delta_is_tight(a in finite(), p in finite(), t in finite(), index in 0usize..1_000_000) {
            let exact = q(t)-q(a)-q(p)*q(index as f64);
            if let Some(bound)= (Clock {start:a,period:p,index}).delta(t) {
                prop_assert!(q(bound.lo)<=exact && exact<=q(bound.hi));
                prop_assert!(bound.lo==bound.hi || bound.lo.next_up()==bound.hi);
            } else {
                prop_assert!(exact < q(-f64::MAX) || exact > q(f64::MAX));
            }
        }
    }
    #[test]
    fn near_clock_delta_keeps_sub_ulp_coordinate() {
        let clock = Clock {
            start: 0.1,
            period: 0.2,
            index: 1,
        };
        let delta = clock.delta(0.30000000000000004).unwrap();
        assert_eq!(delta.lo, delta.hi);
        assert_eq!(q(delta.lo), q(0.30000000000000004) - q(0.1) - q(0.2));
        assert!(delta.lo > 1e-18);
        assert_eq!(
            sum_triples_sign(&[
                (f64::MAX, f64::MAX, f64::MAX),
                (-f64::MAX, f64::MAX, f64::MAX)
            ]),
            Some(0)
        );
        assert_eq!(sum_triples_sign(&[(1., 1., 1.); 9]), None);
    }
}
