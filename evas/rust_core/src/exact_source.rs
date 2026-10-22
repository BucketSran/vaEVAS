//! Bounded exact binary64 source arithmetic for phase and ordinary conditions.
//! Curves retain original rational knots; rounded clamp knots are never inputs.
mod forcing_point;
pub(crate) mod history_paid;
use crate::interval::Interval as I;
use crate::ir::Expression;
use num_rational::BigRational as R;
use num_traits::{Signed, ToPrimitive, Zero};

pub(crate) const MAX_POINTS: usize = 512;
pub(crate) const MAX_BITS: u64 = 4096;
const MAX_OPS: usize = 200_000;
const MAX_DEPTH: usize = 64;
const MAX_EXPR_NODES: usize = 512;

#[derive(Clone)]
pub(crate) struct Curve(Vec<(R, R)>);
pub(crate) struct Budget(pub(crate) usize);

/// An immutable time proved from original affine source arithmetic. Construction
/// is bounded and must agree with the interval discovery that found the root.
#[derive(Clone, PartialEq, Eq)]
pub(crate) struct RootTime(R, TightCache);

/// Memo of one paid outward binary64 enclosure of the immutable rational.
/// It is not part of the value: equality, ordering and Debug ignore it.
#[derive(Clone, Default)]
pub(crate) struct TightCache(std::sync::OnceLock<Option<I>>);
impl PartialEq for TightCache {
    fn eq(&self, _: &Self) -> bool {
        true
    }
}
impl Eq for TightCache {}
impl std::fmt::Debug for RootTime {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_tuple("RootTime").field(&self.0).finish()
    }
}

pub(crate) struct Crossing {
    pub time: RootTime,
    pub segment: [I; 2],
    pub ends: [I; 2],
    pub slope: I,
}

pub(crate) fn enclosure(value: &R) -> Option<I> {
    let nearest = value.to_f64()?;
    if !nearest.is_finite() {
        return None;
    }
    let represented = binary(nearest)?;
    let bounds = I {
        lo: if represented > *value {
            nearest.next_down()
        } else {
            nearest
        },
        hi: if represented < *value {
            nearest.next_up()
        } else {
            nearest
        },
    };
    (bounds.finite() && binary(bounds.lo)? <= *value && *value <= binary(bounds.hi)?)
        .then_some(bounds)
}

pub(crate) fn affine_range(line: (R, R), time: I) -> Option<I> {
    let (a, b) = line;
    let mut budget = Budget(0);
    let lo = budget.check(&b * binary(time.lo)?)?;
    let hi = budget.check(&b * binary(time.hi)?)?;
    let lo = enclosure(&budget.check(&a + lo)?)?;
    let hi = enclosure(&budget.check(a + hi)?)?;
    Some(lo.hull(hi))
}

fn contains(bounds: I, value: &R) -> bool {
    bounds.finite()
        && binary(bounds.lo).is_some_and(|lo| lo <= *value)
        && binary(bounds.hi).is_some_and(|hi| *value <= hi)
}

pub(crate) type TimeProofs = std::collections::BTreeMap<usize, RootTime>;

impl RootTime {
    pub(crate) fn raw(value: R) -> Self {
        Self(value, TightCache::default())
    }
    pub(crate) fn copy_items(&self) -> usize {
        4 + ((self.0.numer().bits() + self.0.denom().bits()) as usize).div_ceil(8)
    }

    pub(crate) fn rational(&self) -> &R {
        &self.0
    }
    pub(crate) fn point(time: f64) -> Option<Self> {
        Some(Self::raw(binary(time)?))
    }
    /// A bounded real witness, including cells without a binary64 interior.
    /// Callers must separately prove the complete root partition.
    pub(crate) fn between(left: &Self, right: &Self) -> Option<Self> {
        if left.order(right) != std::cmp::Ordering::Less {
            return None;
        }
        let mut budget = Budget(0);
        let sum = budget.check(&left.0 + &right.0)?;
        let middle = budget.check(sum / R::from_integer(2.into()))?;
        (left.0 < middle && middle < right.0).then_some(Self::raw(middle))
    }
    /// Original fixed-clock arithmetic; the proof must fit discovery unchanged.
    pub(crate) fn from_clock(clock: crate::exact_time::Clock, discovery: I) -> Option<Self> {
        if clock.index > crate::schedule::EVENT_BUDGET {
            return None;
        }
        let mut budget = Budget(0);
        let offset = budget.check(binary(clock.period)? * R::from_integer(clock.index.into()))?;
        let time = budget.check(binary(clock.start)? + offset)?;
        contains(discovery, &time).then_some(Self::raw(time))
    }

    pub(crate) fn shifted_fixed(&self, delta: f64, discovery: I) -> Option<Self> {
        let time = Budget(0).check(&self.0 + binary(delta)?)?;
        contains(discovery, &time).then_some(Self::raw(time))
    }

    pub(crate) fn affine(value: R, slope: R, bounds: I) -> Option<Self> {
        if slope.is_zero() {
            return None;
        }
        let root = Budget(0).check(-value / slope)?;
        contains(bounds, &root).then_some(Self::raw(root))
    }

    fn from_affine(segment: [f64; 2], ends: [R; 2], bounds: I) -> Option<Self> {
        let [a, b] = ends;
        if a.is_zero() || a == b {
            return None;
        }
        let mut budget = Budget(0);
        let start = binary(segment[0])?;
        let end = binary(segment[1])?;
        let duration = budget.check(&end - &start)?;
        let change = budget.check(b - &a)?;
        let numerator = budget.check(a * duration)?;
        let shift = budget.check(numerator / change)?;
        let time = budget.check(&start - shift)?;
        (start < time && time <= end && contains(bounds, &time)).then_some(Self::raw(time))
    }

    pub(crate) fn point_ends(segment: [f64; 2], ends: [I; 2], bounds: I) -> Option<Self> {
        let [a, b] = ends;
        if a.lo != a.hi || b.lo != b.hi {
            return None;
        }
        Self::from_affine(segment, [binary(a.lo)?, binary(b.lo)?], bounds)
    }

    pub(crate) fn shifted_clock(&self, clock: crate::exact_time::Clock) -> Option<Self> {
        if clock.index > crate::schedule::EVENT_BUDGET {
            return None;
        }
        let mut budget = Budget(0);
        let offset = budget.check(binary(clock.period)? * R::from_integer(clock.index.into()))?;
        let absolute = budget.check(binary(clock.start)? + offset)?;
        Some(Self::raw(budget.check(&self.0 + absolute)?))
    }

    pub(crate) fn refine(&self, discovery: I) -> Option<I> {
        if !contains(discovery, &self.0) {
            return None;
        }
        let tight = self.bounds()?;
        Some(I {
            lo: discovery.lo.max(tight.lo),
            hi: discovery.hi.min(tight.hi),
        })
    }

    pub(crate) fn bounds(&self) -> Option<I> {
        enclosure(&self.0)
    }

    pub(crate) fn order(&self, other: &Self) -> std::cmp::Ordering {
        self.0.cmp(&other.0)
    }

    fn difference_from_clock(&self, clock: crate::exact_time::Clock) -> Option<R> {
        if clock.index > crate::schedule::EVENT_BUDGET {
            return None;
        }
        let mut budget = Budget(0);
        let offset = budget.check(binary(clock.period)? * R::from_integer(clock.index.into()))?;
        let absolute = budget.check(binary(clock.start)? + offset)?;
        budget.check(&self.0 - absolute)
    }

    pub(crate) fn clock_delta_order(
        &self,
        clock: crate::exact_time::Clock,
        delta: f64,
    ) -> Option<std::cmp::Ordering> {
        let difference = Budget(0).check(self.difference_from_clock(clock)? - binary(delta)?)?;
        Some(difference.cmp(&R::zero()))
    }

    pub(crate) fn local_bounds(&self, clock: crate::exact_time::Clock) -> Option<I> {
        enclosure(&self.difference_from_clock(clock)?)
    }
}
impl Budget {
    pub(crate) fn check(&mut self, value: R) -> Option<R> {
        self.0 = self.0.checked_add(1)?;
        (self.0 <= MAX_OPS && value.numer().bits() <= MAX_BITS && value.denom().bits() <= MAX_BITS)
            .then_some(value)
    }
}
pub(crate) fn binary(x: f64) -> Option<R> {
    R::from_float(x)
}

// A point evaluation proves the original expression tree, without rounding
// scalar products or reconstructing the source from projected clamp knots.
fn evaluate(
    e: &Expression,
    nodes: &[usize],
    sources: &[Option<Curve>],
    time: &R,
    budget: &mut Budget,
    depth: usize,
    count: &mut usize,
) -> Option<R> {
    evaluate_states(
        e,
        nodes,
        sources,
        time,
        budget,
        depth,
        count,
        &Default::default(),
    )
}

#[allow(clippy::too_many_arguments)]
fn evaluate_states(
    e: &Expression,
    nodes: &[usize],
    sources: &[Option<Curve>],
    time: &R,
    budget: &mut Budget,
    depth: usize,
    count: &mut usize,
    states: &crate::exact_source::TimeProofs,
) -> Option<R> {
    *count += 1;
    if depth > MAX_DEPTH || *count > MAX_EXPR_NODES {
        return None;
    }
    match e {
        Expression::State { state } => budget.check(states.get(state)?.0.clone()),
        Expression::Affine { constant, terms } => {
            if terms.len() > MAX_POINTS {
                return None;
            }
            let mut value = binary(*constant)?;
            for term in terms {
                if term.node == 0 {
                    continue;
                }
                let k = nodes.iter().position(|n| *n == term.node)?;
                let v = sources.get(k)?.as_ref()?.value(time, budget)?;
                let product = budget.check(binary(term.coefficient)? * v)?;
                value = budget.check(value + product)?;
            }
            Some(value)
        }
        Expression::Add { left, right }
        | Expression::Multiply { left, right }
        | Expression::Divide { left, right } => {
            let a = evaluate_states(left, nodes, sources, time, budget, depth + 1, count, states)?;
            let b = evaluate_states(
                right,
                nodes,
                sources,
                time,
                budget,
                depth + 1,
                count,
                states,
            )?;
            let result = budget.check(match e {
                Expression::Add { .. } => a + b,
                Expression::Multiply { .. } => a * b,
                Expression::Divide { .. } if !b.is_zero() => a / b,
                _ => return None,
            })?;
            if matches!(e, Expression::Divide { .. }) {
                // A sign certificate must not turn a non-finite selected
                // division into a successful source condition.
                enclosure(&result)?;
            }
            Some(result)
        }
        _ => None,
    }
}

/// Enclose an original source expression at a binary64 time. Missing source
/// provenance or an exceeded arithmetic budget yields no certificate.
pub(crate) fn point_bounds(
    expression: &Expression,
    nodes: &[usize],
    sources: &[Option<Curve>],
    time: f64,
) -> Option<I> {
    let time = binary(time)?;
    let mut budget = Budget(0);
    let mut count = 0;
    enclosure(&evaluate(
        expression,
        nodes,
        sources,
        &time,
        &mut budget,
        0,
        &mut count,
    )?)
}

/// Certify a comparison using the original expression trees and source knots.
pub(crate) fn predicate_sign(
    left: &Expression,
    right: &Expression,
    nodes: &[usize],
    sources: &[Option<Curve>],
    time: f64,
) -> Option<i8> {
    let time = binary(time)?;
    let mut budget = Budget(0);
    let mut count = 0;
    let left = evaluate(left, nodes, sources, &time, &mut budget, 0, &mut count)?;
    let right = evaluate(right, nodes, sources, &time, &mut budget, 0, &mut count)?;
    let difference = budget.check(left - right)?;
    Some(if difference.is_zero() {
        0
    } else if difference.is_positive() {
        1
    } else {
        -1
    })
}

impl Curve {
    /// Forcing-only prepayment for the pinned num-rational 0.4.2 / num-bigint
    /// 0.4.6 algorithms. All arithmetic below saturates before the one debit.
    /// `b` bounds numerator/denominator bits including unreduced intermediates.
    /// The named costs count limb scans/products, not elapsed CPU instructions.
    pub(crate) fn charge_forcing_read(
        &self,
        work: &crate::transition_source_plan::Work,
        time: f64,
        range: bool,
    ) -> Result<(), crate::ir::Error> {
        fn linear(b: u64) -> u64 {
            b.div_ceil(64).saturating_add(1)
        }
        fn mul(b: u64) -> u64 {
            linear(b).saturating_pow(2).saturating_mul(16)
        }
        pub(super) fn div(b: u64) -> u64 {
            // Knuth: <=L quotient digits; each digit has <=2 estimate
            // corrections, sub_mul and possible addback, plus normalization.
            linear(b).saturating_pow(2).saturating_mul(16)
        }
        fn gcd(b: u64) -> u64 {
            // Stein: positive operand product halves at least once per
            // iteration, <=2b+2 iterations, <=8 complete limb scans each.
            b.saturating_mul(2)
                .saturating_add(2)
                .saturating_mul(linear(b))
                .saturating_mul(8)
        }
        fn compare(b: u64) -> u64 {
            // Ratio::cmp uses two div_mod_floor calls per Euclidean round,
            // <=2b+2 rounds, with comparisons/clones/sign correction scans.
            b.saturating_mul(2).saturating_add(2).saturating_mul(
                div(b)
                    .saturating_mul(2)
                    .saturating_add(linear(b).saturating_mul(16)),
            )
        }
        fn operation(b: u64) -> u64 {
            // Covers both lcm-based Add/Sub and cross-GCD Mul/Div, including
            // Ratio::new -> reduce, signs, result clones and Budget bit tests.
            gcd(b)
                .saturating_mul(4)
                .saturating_add(div(b).saturating_mul(8))
                .saturating_add(mul(b).saturating_mul(4))
                .saturating_add(linear(b).saturating_mul(16))
        }
        fn enclosure_cost(b: u64) -> u64 {
            // Two to_f64 calls (including at's returned representative):
            // ratio_to_f64 shifts to <=b+56 bits then one div_rem each.
            // Three binary(f64) constructions, each normalize by one GCD and
            // two divisions; four Ratio comparisons certify both endpoints.
            // A nonzero finite b-bit ratio's rounded binary64 has at most
            // b+56 bits (also covers a subnormal/next_{up,down} endpoint).
            let wide = b.saturating_add(56);
            div(wide)
                .saturating_mul(2)
                .saturating_add(linear(wide).saturating_mul(32))
                .saturating_add(
                    gcd(wide)
                        .saturating_add(div(wide).saturating_mul(2))
                        .saturating_mul(3),
                )
                .saturating_add(compare(wide).saturating_mul(4))
        }
        work.debit(2, self.0.len().saturating_add(4) as u64)?;
        let (mut tbits, mut vbits) = (1u64, 1u64);
        for (t, v) in &self.0 {
            tbits = tbits.max(t.numer().bits()).max(t.denom().bits());
            vbits = vbits.max(v.numer().bits()).max(v.denom().bits());
        }
        // Includes smallest subnormal denominator 2^1074 (1075 bits), without
        // allocating a BigRational while deciding whether its work is funded.
        let exponent = ((time.to_bits() >> 52) & 0x7ff) as i64;
        let power = if exponent == 0 {
            -1074
        } else {
            exponent - 1023 - 52
        };
        let q = if time == 0. {
            1
        } else {
            (53 + power.max(0)).max(1 + (-power).max(0)) as u64
        };
        let delta = vbits.saturating_mul(2).saturating_add(1);
        let elapsed = tbits.saturating_add(q).saturating_add(1);
        let duration = tbits.saturating_mul(2).saturating_add(1);
        let fraction = elapsed.saturating_add(duration).saturating_add(1);
        let change = delta.saturating_add(fraction).saturating_add(1);
        let result = vbits.saturating_add(change).saturating_add(1);
        let six = [delta, elapsed, duration, fraction, change, result]
            .into_iter()
            .fold(0u64, |sum, b| sum.saturating_add(operation(b)));
        let n = self.0.len() as u64;
        let searches = (u64::BITS - n.max(1).leading_zeros()) as u64 + 2;
        let point = six
            .saturating_add(enclosure_cost(result))
            .saturating_add(compare(tbits.max(q)).saturating_mul(searches))
            .saturating_add(operation(q)); // binary(time), with spare operations
        let cost = if range {
            // range: two endpoint values and every original pair (all arms),
            // six time comparisons, three derivative operations, derivative
            // enclosure and an optional interior voltage enclosure per pair.
            let derivative = delta.saturating_add(duration).saturating_add(1);
            let pair = compare(tbits.max(q))
                .saturating_mul(6)
                .saturating_add(operation(duration))
                .saturating_add(operation(delta))
                .saturating_add(operation(derivative))
                .saturating_add(enclosure_cost(derivative))
                .saturating_add(enclosure_cost(vbits));
            point
                .saturating_mul(2)
                .saturating_add(pair.saturating_mul(n))
        } else {
            point
        };
        crate::diagnostics::counter("forcing_curve_requested_work", cost as usize);
        work.debit(2, cost)?;
        crate::diagnostics::counter("forcing_curve_reserved_work", cost as usize);
        Ok(())
    }
    pub(crate) fn charge_source_copy(
        &self,
        work: &crate::transition_source_plan::Work,
        names: [&'static str; 3],
    ) -> Result<(), crate::ir::Error> {
        for (t, v) in &self.0 {
            work.debit(2, 1)?;
            crate::diagnostics::counter(names[0], 1);
            crate::diagnostics::counter(names[2], 1);
            let items = 2 + [
                t.numer().bits(),
                t.denom().bits(),
                v.numer().bits(),
                v.denom().bits(),
            ]
            .into_iter()
            .map(|bits| bits.div_ceil(64) as usize)
            .sum::<usize>();
            work.debit(2, items as u64)?;
            crate::diagnostics::counter(names[1], items);
            crate::diagnostics::counter(names[2], items);
        }
        Ok(())
    }

    /// A line is exact only when every original corner in this interval lies
    /// on it. Endpoint secants alone do not establish that fact.
    pub(crate) fn affine_on(&self, time: I) -> Option<(R, R)> {
        let lo = binary(time.lo)?;
        let hi = binary(time.hi)?;
        if lo == hi {
            return Some((self.value(&lo, &mut Budget(0))?, binary(0.)?));
        }
        if lo > hi {
            return None;
        }
        let mut budget = Budget(0);
        let a = self.value(&lo, &mut budget)?;
        let b = self.value(&hi, &mut budget)?;
        let duration = budget.check(&hi - &lo)?;
        let delta = budget.check(b - &a)?;
        let slope = budget.check(delta / duration)?;
        let shift = budget.check(&slope * &lo)?;
        let intercept = budget.check(a - shift)?;
        for (t, v) in self.0.iter().filter(|(t, _)| lo < *t && *t < hi) {
            let product = budget.check(&slope * t)?;
            if budget.check(&intercept + product)? != *v {
                return None;
            }
        }
        Some((intercept, slope))
    }
    /// The supplied physical curve must be covered by the unchanged nominal
    /// voltage band everywhere. On the union of both knot sets their difference
    /// is affine, so checking its endpoints proves the complete time domain.
    pub(crate) fn shaped(
        shape: &crate::ir::ShapedSourceError,
        nominal: &[[f64; 2]],
        stop: f64,
    ) -> Option<Self> {
        if !(2..=MAX_POINTS).contains(&shape.exact_knots.len()) {
            return None;
        }
        let mut budget = Budget(0);
        let mut points: Vec<(R, R)> = Vec::new();
        for knot in &shape.exact_knots {
            // Bound parsing before allocating arbitrary-precision integers.
            if knot.time_numerator.is_empty()
                || knot.time_denominator.is_empty()
                || knot.time_numerator.len() > 1250
                || knot.time_denominator.len() > 1250
                || !knot.time_numerator.bytes().all(|c| c.is_ascii_digit())
                || !knot.time_denominator.bytes().all(|c| c.is_ascii_digit())
            {
                return None;
            }
            let time = budget.check(
                format!("{}/{}", knot.time_numerator, knot.time_denominator)
                    .parse::<R>()
                    .ok()?,
            )?;
            let value = binary(knot.value_v)?;
            if time.is_negative() || points.last().is_some_and(|(last, _)| last >= &time) {
                return None;
            }
            points.push((time, value));
        }
        let stop = binary(stop)?;
        if !points.first()?.0.is_zero() || points.last()?.0 < stop {
            return None;
        }
        let physical = Self(points);
        let nominal = Self::source(nominal)?;
        let error = binary(shape.voltage_error_bound_v)?;
        if error.is_negative() {
            return None;
        }
        let mut knots = vec![R::zero(), stop.clone()];
        for curve in [&physical, &nominal] {
            knots.extend(curve.0.iter().map(|p| p.0.clone()).filter(|t| *t < stop));
        }
        knots.sort();
        knots.dedup();
        for time in knots {
            let difference = budget.check(
                physical.value(&time, &mut Budget(0))? - nominal.value(&time, &mut Budget(0))?,
            )?;
            if difference.abs() > error {
                return None;
            }
        }
        Some(physical)
    }

    /// Values and derivatives of the physical source, including every true
    /// rational corner intersecting the query, rather than rounded knot slopes.
    pub(crate) fn range(&self, time: I) -> Option<(I, I)> {
        let lo = binary(time.lo)?;
        let hi = binary(time.hi)?;
        if lo > hi {
            return None;
        }
        let mut budget = Budget(0);
        let mut values = enclosure(&self.value(&lo, &mut budget)?)?
            .hull(enclosure(&self.value(&hi, &mut budget)?)?);
        let mut slope: Option<I> = None;
        for pair in self.0.windows(2) {
            #[cfg(test)]
            crate::diagnostics::counter("strict_range_pair_body", 1);
            let (a, x) = &pair[0];
            let (b, y) = &pair[1];
            if *a < hi && *b > lo || lo == hi && *a <= lo && lo <= *b {
                let duration = budget.check(b - a)?;
                let change = budget.check(y - x)?;
                let derivative = enclosure(&budget.check(change / duration)?)?;
                slope = Some(slope.map_or(derivative, |old| old.hull(derivative)));
            }
            if lo < *b && *b < hi {
                values = values.hull(enclosure(y)?);
            }
        }
        Some((values, slope.unwrap_or(I::ZERO)))
    }

    pub(crate) fn at_root(&self, root: &RootTime) -> Option<R> {
        self.value(&root.0, &mut Budget(0))
    }

    pub(crate) fn at(&self, time: f64) -> Option<(f64, I)> {
        #[cfg(test)]
        crate::diagnostics::counter("strict_curve_at_body", 1);
        let value = self.value(&binary(time)?, &mut Budget(0))?;
        let bounds = enclosure(&value)?;
        Some((value.to_f64()?, bounds))
    }

    /// Complete zero arrivals on the physical PWL partition. Rounded surrogate
    /// knots cannot safely define this partition when corners have moved.
    pub(crate) fn crossings(&self, direction: i8, stop: f64) -> Option<Vec<Crossing>> {
        let stop = binary(stop)?;
        let mut budget = Budget(0);
        let mut out = Vec::new();
        for pair in self.0.windows(2) {
            let (a, x) = &pair[0];
            let (b, y) = &pair[1];
            if x.is_zero() {
                continue;
            }
            let sign = if y.is_zero() {
                if x.is_positive() {
                    -1
                } else {
                    1
                }
            } else if x.is_positive() != y.is_positive() {
                if y.is_positive() {
                    1
                } else {
                    -1
                }
            } else {
                continue;
            };
            if direction != 0 && direction != sign {
                continue;
            }
            let duration = budget.check(b - a)?;
            let change = budget.check(y - x)?;
            let numerator = budget.check(x * &duration)?;
            let shift = budget.check(numerator / &change)?;
            let time = budget.check(a - shift)?;
            if time <= R::zero() || time > stop {
                continue;
            }
            out.push(Crossing {
                time: RootTime::raw(time.clone()),
                segment: [enclosure(a)?, enclosure(b)?],
                ends: [enclosure(x)?, enclosure(y)?],
                // An upper representative at a nonbinary corner can lie in
                // the outgoing segment. Bound every slope up to the latest
                // representative accepted by Root, including that segment.
                slope: self
                    .range(I {
                        lo: enclosure(&time)?.lo,
                        hi: enclosure(b)?.hi.min(stop.to_f64()?),
                    })?
                    .1,
            });
        }
        Some(out)
    }

    /// Match an already discovered root without bridging an interior source kink.
    /// A redundant interior knot also takes the conservative fallback path.
    pub(crate) fn root_in(&self, segment: [f64; 2], ends: [I; 2], bounds: I) -> Option<RootTime> {
        let start = binary(segment[0])?;
        let end = binary(segment[1])?;
        if self.0.iter().any(|(t, _)| start < *t && *t < end) {
            return None;
        }
        let mut budget = Budget(0);
        let a = self.value(&start, &mut budget)?;
        let b = self.value(&end, &mut budget)?;
        if !contains(ends[0], &a) || !contains(ends[1], &b) {
            return None;
        }
        RootTime::from_affine(segment, [a, b], bounds)
    }

    /// Complete original affine roots and source corners, retaining their real
    /// rational times. Binary64 upper bounds are representatives, not roots.
    pub(crate) fn isolated_zero_times(&self) -> Option<Vec<RootTime>> {
        let mut work = Budget(0);
        let mut out = Vec::new();
        for pair in self.0.windows(2) {
            let (a, x) = &pair[0];
            let (b, y) = &pair[1];
            if a >= b {
                return None;
            }
            out.extend([RootTime::raw(a.clone()), RootTime::raw(b.clone())]);
            if x.is_zero() || y.is_zero() || x.is_positive() == y.is_positive() {
                continue;
            }
            let duration = work.check(b - a)?;
            let delta = work.check(y - x)?;
            let numerator = work.check(x * duration)?;
            let shift = work.check(numerator / delta)?;
            let root = work.check(a - shift)?;
            if root <= *a || root >= *b {
                return None;
            }
            enclosure(&root)?;
            out.push(RootTime::raw(root));
        }
        out.sort_by(RootTime::order);
        out.dedup_by(|a, b| a.order(b) == std::cmp::Ordering::Equal);
        Some(out)
    }
    /// Predicate sign at the original real root. In particular strict and
    /// non-strict comparisons cannot use the upper representative's sign.
    pub(crate) fn sign_at_root(&self, root: &RootTime) -> Option<i8> {
        let value = self.value(&root.0, &mut Budget(0))?;
        Some(if value.is_zero() {
            0
        } else if value.is_positive() {
            1
        } else {
            -1
        })
    }

    pub(crate) fn source(points: &[[f64; 2]]) -> Option<Self> {
        if points.len() > MAX_POINTS {
            return None;
        }
        Some(Self(
            points
                .iter()
                .map(|[t, v]| Some((binary(*t)?, binary(*v)?)))
                .collect::<Option<Vec<_>>>()?,
        ))
    }
    fn value(&self, time: &R, budget: &mut Budget) -> Option<R> {
        #[cfg(test)]
        crate::diagnostics::counter("strict_range_value_body", 1);
        let index = self.0.partition_point(|p| p.0 < *time);
        let (end, b) = self.0.get(index)?;
        if end == time {
            return Some(b.clone());
        }
        let (start, a) = self.0.get(index.checked_sub(1)?)?;
        let delta = budget.check(b - a)?;
        let elapsed = budget.check(time - start)?;
        let duration = budget.check(end - start)?;
        let fraction = budget.check(elapsed / duration)?;
        let change = budget.check(delta * fraction)?;
        budget.check(a + change)
    }
    pub(crate) fn expression(
        expr: &Expression,
        nodes: &[usize],
        sources: &[Option<Self>],
        stop: f64,
    ) -> Option<Self> {
        Self::expression_with_states(expr, nodes, sources, stop, &Default::default())
    }
    pub(crate) fn expression_with_states(
        expr: &Expression,
        nodes: &[usize],
        sources: &[Option<Self>],
        stop: f64,
        states: &crate::exact_source::TimeProofs,
    ) -> Option<Self> {
        // Existing callers validate affinity/ownership first. Recheck degree
        // here as well: endpoint interpolation cannot certify a quadratic.
        fn varying(e: &Expression, depth: usize, count: &mut usize) -> Option<bool> {
            *count += 1;
            if depth > MAX_DEPTH || *count > MAX_EXPR_NODES {
                return None;
            }
            match e {
                Expression::State { .. } => Some(false),
                Expression::Affine { terms, .. } => Some(terms.iter().any(|t| t.node != 0)),
                Expression::Add { left, right } => {
                    let a = varying(left, depth + 1, count)?;
                    let b = varying(right, depth + 1, count)?;
                    Some(a || b)
                }
                Expression::Multiply { left, right } => {
                    let a = varying(left, depth + 1, count)?;
                    let b = varying(right, depth + 1, count)?;
                    if a && b {
                        None
                    } else {
                        Some(a || b)
                    }
                }
                _ => None,
            }
        }
        varying(expr, 0, &mut 0)?;
        // Only referenced sources contribute knots/uncertainty. Ground is exact.
        fn dependencies(
            e: &Expression,
            out: &mut Vec<usize>,
            depth: usize,
            count: &mut usize,
        ) -> Option<()> {
            *count += 1;
            if depth > MAX_DEPTH || *count > MAX_EXPR_NODES {
                return None;
            }
            match e {
                Expression::State { .. } => {}
                Expression::Affine { terms, .. } => {
                    if terms.len() > MAX_POINTS {
                        return None;
                    }
                    out.extend(terms.iter().map(|t| t.node).filter(|n| *n != 0))
                }
                Expression::Add { left, right } | Expression::Multiply { left, right } => {
                    dependencies(left, out, depth + 1, count)?;
                    dependencies(right, out, depth + 1, count)?;
                }
                _ => return None,
            }
            (out.len() <= MAX_POINTS).then_some(())
        }
        let mut deps = Vec::new();
        dependencies(expr, &mut deps, 0, &mut 0)?;
        let mut budget = Budget(0);
        let stop = binary(stop)?;
        let mut knots = vec![R::zero(), stop.clone()];
        for node in deps {
            let k = nodes.iter().position(|n| *n == node)?;
            let curve = sources.get(k)?.as_ref()?;
            knots.extend(curve.0.iter().map(|p| p.0.clone()).filter(|t| *t < stop));
            if knots.len() > MAX_POINTS * MAX_POINTS {
                return None;
            }
        }
        knots.sort();
        knots.dedup();
        if knots.len() > MAX_POINTS {
            return None;
        }
        Some(Self(
            knots
                .into_iter()
                .map(|t| {
                    let value =
                        evaluate_states(expr, nodes, sources, &t, &mut budget, 0, &mut 0, states)?;
                    Some((t, value))
                })
                .collect::<Option<Vec<_>>>()?,
        ))
    }
    pub(crate) fn clipped(&self, lo: f64, hi: f64) -> Option<Self> {
        let lo = binary(lo)?;
        let hi = binary(hi)?;
        let mut budget = Budget(0);
        let mut result = Vec::new();
        for pair in self.0.windows(2) {
            let (start, a) = &pair[0];
            let (end, b) = &pair[1];
            result.push((start.clone(), a.clone().max(lo.clone()).min(hi.clone())));
            let mut roots = Vec::new();
            if a != b {
                for threshold in [&lo, &hi] {
                    if threshold > a.min(b) && threshold < a.max(b) {
                        let delta = budget.check(b - a)?;
                        let duration = budget.check(end - start)?;
                        let numerator = budget.check((threshold - a) * duration)?;
                        let shift = budget.check(numerator / delta)?;
                        let root = budget.check(start + shift)?;
                        roots.push((root, threshold.clone()));
                    }
                }
            }
            roots.sort();
            result.extend(roots);
            if result.len() >= MAX_POINTS {
                return None;
            }
        }
        let (t, v) = self.0.last()?;
        result.push((t.clone(), v.clone().max(lo).min(hi)));
        Some(Self(result))
    }

    pub(crate) fn wrapped(
        &self,
        time: f64,
        ic: f64,
        modulus: f64,
        offset: f64,
    ) -> Option<(f64, I)> {
        let t = binary(time)?;
        let mut total = binary(ic)?;
        let m = binary(modulus)?;
        let off = binary(offset)?;
        if t < self.0.first()?.0 || t > self.0.last()?.0 || m <= R::zero() {
            return None;
        }
        let mut budget = Budget(0);
        for pair in self.0.windows(2) {
            let (start, a) = &pair[0];
            let (end, b) = &pair[1];
            if t <= *start {
                break;
            }
            let until = t.clone().min(end.clone());
            let value = if until == *end {
                b.clone()
            } else {
                self.value(&until, &mut budget)?
            };
            let sum = budget.check(a + value)?;
            let elapsed = budget.check(until - start)?;
            let area = budget.check(sum * elapsed / R::from_integer(2.into()))?;
            total = budget.check(total + area)?;
        }
        let phase = budget.check(total - &off)?;
        let normalized = budget.check(phase.clone() / &m)?;
        let turn = normalized.floor().to_integer();
        // Retain the existing representable turn-count limit.
        if R::from_integer(turn.clone()).abs() > binary(4_503_599_627_370_496.0)? {
            return None;
        }
        let displacement = budget.check(R::from_integer(turn) * &m)?;
        let wrapped = budget.check(&off + phase - displacement)?;
        let upper = budget.check(off.clone() + m)?;
        let mut value = wrapped.to_f64()?;
        if !value.is_finite() {
            return None;
        }
        // Half-open output: a rounded value may land on the excluded upper
        // endpoint even though the exact phase is strictly below it.
        if binary(value)? >= upper {
            value = value.next_down();
        }
        if binary(value)? < off {
            value = value.next_up();
        }
        let converted = binary(value)?;
        if !value.is_finite() || converted < off || converted >= upper {
            return None;
        }
        let bounds = I {
            lo: if converted > wrapped {
                value.next_down()
            } else {
                value
            },
            hi: if converted < wrapped {
                value.next_up()
            } else {
                value
            },
        };
        (bounds.finite() && binary(bounds.lo)? <= wrapped && wrapped <= binary(bounds.hi)?)
            .then_some((value, bounds))
    }
}

#[cfg(test)]
mod tests {
    fn descriptor(points: &[(&str, &str, f64)], error: f64) -> crate::ir::ShapedSourceError {
        crate::ir::ShapedSourceError {
            voltage_error_bound_v: error,
            exact_knots: points
                .iter()
                .map(|(n, d, v)| crate::ir::ExactSourceKnot {
                    time_numerator: (*n).into(),
                    time_denominator: (*d).into(),
                    value_v: *v,
                })
                .collect(),
        }
    }

    #[test]
    fn physical_partition_encloses_displaced_corner_and_derivative() {
        let shape = descriptor(&[("0", "1", 0.), ("1", "3", 1.), ("1", "1", 1.)], 0.125);
        let curve = Curve::shaped(&shape, &[[0., 0.], [0.3, 1.], [1., 1.]], 1.).unwrap();
        let (value, slope) = curve.range(I { lo: 0.3, hi: 0.4 }).unwrap();
        assert!(contains(
            value,
            &(binary(0.3).unwrap() * R::from_integer(3.into()))
        ));
        assert_eq!(value.hi, 1.);
        assert_eq!(slope, I { lo: 0., hi: 3. });
        let (_, rounded) = curve.at(0.1).unwrap();
        assert!(rounded.lo < rounded.hi);
        assert!(contains(
            rounded,
            &(binary(0.1).unwrap() * R::from_integer(3.into()))
        ));
        // The maximum discrepancy is at the nominal corner, absent from shape.
        assert!(Curve::shaped(
            &descriptor(&[("0", "1", 0.), ("1", "3", 1.), ("1", "1", 1.)], 0.0625),
            &[[0., 0.], [0.3, 1.], [1., 1.]],
            1.
        )
        .is_none());
    }

    #[test]
    fn physical_crossings_own_zero_arrival_and_include_stop_without_departure() {
        let curve = Curve(vec![
            (R::from_integer(0.into()), R::from_integer((-1).into())),
            (R::new(1.into(), 3.into()), R::zero()),
            (R::new(1.into(), 2.into()), R::zero()),
            (R::new(2.into(), 3.into()), R::from_integer(1.into())),
            (R::from_integer(1.into()), R::zero()),
        ]);
        let all = curve.crossings(0, 1.).unwrap();
        assert_eq!(all.len(), 2);
        assert_eq!(all[0].time.0, R::new(1.into(), 3.into()));
        assert_eq!(all[1].time.0, R::from_integer(1.into()));
        assert_eq!(curve.crossings(1, 1.).unwrap().len(), 1);
        assert_eq!(curve.crossings(-1, 1.).unwrap().len(), 1);
    }

    #[test]
    fn shape_limits_and_coverage_refuse_before_using_unbounded_geometry() {
        let nominal = [[0., 0.], [1., 1.]];
        for points in [
            vec![("0", "1", 0.)],
            vec![("0", "1", 0.), ("1", "2", 1.)],
            vec![("1", "4", 0.), ("1", "1", 1.)],
            vec![("0", "1", 0.), ("1", "0", 1.)],
            vec![("0", "1", 0.), ("1", "1", f64::INFINITY)],
        ] {
            assert!(Curve::shaped(&descriptor(&points, 1.), &nominal, 1.).is_none());
        }
        let mut shape = descriptor(&[("0", "1", 0.), ("1", "1", 1.)], 1.);
        shape.exact_knots[1].time_numerator = "9".repeat(1250);
        assert!(Curve::shaped(&shape, &nominal, 1.).is_none());
        shape.exact_knots = (0..MAX_POINTS)
            .map(|k| crate::ir::ExactSourceKnot {
                time_numerator: k.to_string(),
                time_denominator: (MAX_POINTS - 1).to_string(),
                value_v: 0.,
            })
            .collect();
        assert!(Curve::shaped(&shape, &[[0., 0.], [1., 0.]], 1.).is_some());
        shape.exact_knots = vec![shape.exact_knots[0].clone(); MAX_POINTS + 1];
        assert!(Curve::shaped(&shape, &nominal, 1.).is_none());
    }

    #[test]
    fn source_cut_keeps_nonbinary_root_and_exact_boundary_sign() {
        let curve = super::Curve::source(&[[0., -0.5], [1., 2.5]]).unwrap();
        let cuts = curve.isolated_zero_times().unwrap();
        assert_eq!(cuts.len(), 3);
        let root = &cuts[1];
        let exact = num_rational::BigRational::new(1.into(), 6.into());
        assert_eq!(root.0, exact);
        let window = root.bounds().unwrap();
        assert!(super::binary(window.lo).unwrap() < exact);
        assert!(super::binary(window.hi).unwrap() > exact);
        assert_eq!(curve.sign_at_root(root), Some(0));
        let representative = super::RootTime::raw(super::binary(window.hi).unwrap());
        assert_eq!(curve.sign_at_root(&representative), Some(1));
    }

    use super::*;

    #[test]
    fn root_proof_retains_subulp_phase_and_local_clock_difference() {
        let threshold = binary(0.7).unwrap();
        let stop = binary(6e-6).unwrap();
        let curve = Curve(vec![
            (R::zero(), -threshold.clone()),
            (stop.clone(), binary(3.0).unwrap() - &threshold),
        ]);
        let query = 1.4e-6_f64;
        let root = curve
            .root_in(
                [0.0, 6e-6],
                [
                    I::point(-0.7),
                    I {
                        lo: 2.3,
                        hi: 2.3_f64.next_up(),
                    },
                ],
                I {
                    lo: query.next_down(),
                    hi: query.next_up(),
                },
            )
            .unwrap();
        let expected = threshold * stop / binary(3.0).unwrap();
        assert_eq!(root.0, expected);
        let clock = crate::exact_time::Clock {
            start: query,
            period: 0.0,
            index: 0,
        };
        assert_eq!(
            root.clock_delta_order(clock, 0.0),
            Some(std::cmp::Ordering::Greater)
        );
        let local = root.local_bounds(clock).unwrap();
        assert!(local.lo > 0.0);
        assert!(contains(local, &(expected - binary(query).unwrap())));
        assert_eq!(
            root.bounds().unwrap(),
            I {
                lo: query,
                hi: query.next_up()
            }
        );
        assert!(root
            .local_bounds(crate::exact_time::Clock {
                index: crate::schedule::EVENT_BUDGET + 1,
                ..clock
            })
            .is_none());
    }

    #[test]
    fn root_proof_requires_matching_segment_endpoints_and_interval() {
        let curve = Curve::source(&[[0.0, -1.0], [2.0, 1.0]]).unwrap();
        let ends = [I::point(-1.0), I::ONE];
        let bounds = I { lo: 0.5, hi: 1.5 };
        assert_eq!(
            curve.root_in([0.0, 2.0], ends, bounds).unwrap().bounds(),
            Some(I::ONE)
        );
        assert!(curve
            .root_in([0.0, 2.0], [I::point(-2.0), I::ONE], bounds)
            .is_none());
        assert!(curve
            .root_in([0.0, 2.0], ends, I { lo: 1.1, hi: 1.5 })
            .is_none());
        let kink = Curve::source(&[[0.0, -1.0], [1.0, 0.5], [2.0, 1.0]]).unwrap();
        assert!(kink.root_in([0.0, 2.0], ends, bounds).is_none());
        // A segment starting on zero must not rediscover an already consumed root.
        assert!(RootTime::point_ends([0.0, 1.0], [I::ZERO, I::ONE], bounds).is_none());
        // No exact source proof: an interval endpoint is not converted to its midpoint.
        assert!(
            RootTime::point_ends([0.0, 2.0], [I { lo: -1.1, hi: -0.9 }, I::ONE], bounds).is_none()
        );
        let huge = R::from_integer(binary(1.0).unwrap().numer().clone() << (MAX_BITS as usize + 1));
        assert!(RootTime::from_affine([0.0, 2.0], [-huge.clone(), huge], bounds).is_none());
    }

    #[test]
    fn ordinary_point_certificate_requires_exact_source_provenance() {
        let input = Expression::Affine {
            constant: 0.0,
            terms: vec![crate::ir::Term {
                node: 1,
                coefficient: 1.0,
            }],
        };
        let threshold = Expression::Affine {
            constant: 0.5,
            terms: vec![],
        };
        let source = Curve::source(&[[0.0, 0.0], [2.0, 1.0]]);
        assert_eq!(
            predicate_sign(&input, &threshold, &[1], &[source], 1.0),
            Some(0)
        );
        // Enclosed/generated sources without exact provenance stay uncertain.
        assert_eq!(predicate_sign(&input, &threshold, &[1], &[None], 1.0), None);
        assert_eq!(predicate_sign(&input, &threshold, &[], &[], 1.0), None);
    }

    #[test]
    fn point_certificate_preserves_nonexact_scalar_products_and_budget() {
        let scalar = |constant| Expression::Affine {
            constant,
            terms: vec![],
        };
        let product = Expression::Multiply {
            left: Box::new(scalar(0.1)),
            right: Box::new(scalar(0.1)),
        };
        // The mathematical product of binary64 0.1 is strictly below the
        // rounded binary64 product. Folding it would incorrectly prove equality.
        assert_eq!(
            predicate_sign(&product, &scalar(0.1 * 0.1), &[], &[], 0.0),
            Some(-1)
        );
        let mut deep = scalar(0.0);
        for _ in 0..=MAX_DEPTH {
            deep = Expression::Add {
                left: Box::new(deep),
                right: Box::new(scalar(0.0)),
            };
        }
        assert_eq!(predicate_sign(&deep, &scalar(0.0), &[], &[], 0.0), None);
    }

    #[test]
    fn point_value_encloses_original_product_at_adjacent_root_queries() {
        let input = Expression::Affine {
            constant: 0.,
            terms: vec![crate::ir::Term {
                node: 1,
                coefficient: 1.,
            }],
        };
        let guard = Expression::Add {
            left: Box::new(Expression::Multiply {
                left: Box::new(input.clone()),
                right: Box::new(input),
            }),
            right: Box::new(Expression::Affine {
                constant: -2.,
                terms: vec![],
            }),
        };
        let source = Curve::source(&[[0., 0.], [3., 3.]]);
        let sources = [source];
        let center = 2_f64.sqrt();
        for query in [center.next_down(), center, center.next_up()] {
            let bounds = point_bounds(&guard, &[1], &sources, query).unwrap();
            let rational = binary(query).unwrap();
            let exact = &rational * &rational - binary(2.).unwrap();
            assert!(contains(bounds, &exact));
            assert_eq!(
                bounds.sign(),
                Some(if exact.is_positive() { 1 } else { -1 })
            );
        }
        assert!(point_bounds(&guard, &[1], &[None], center).is_none());
    }

    #[test]
    fn ground_terms_are_exact_zero_without_a_driven_source() {
        let expr = Expression::Affine {
            constant: 0.25,
            terms: vec![crate::ir::Term {
                node: 0,
                coefficient: 17.0,
            }],
        };
        let curve = Curve::expression(&expr, &[], &[], 1.0).unwrap();
        assert_eq!(
            curve.value(&binary(0.5).unwrap(), &mut Budget(0)),
            binary(0.25)
        );
    }

    #[test]
    fn resource_limits_admit_boundary_and_fall_back_above_it() {
        for count in [MAX_POINTS - 1, MAX_POINTS, MAX_POINTS + 1] {
            let points: Vec<_> = (0..count).map(|i| [i as f64, 1.0]).collect();
            assert_eq!(Curve::source(&points).is_some(), count <= MAX_POINTS);
        }
        for bits in [MAX_BITS - 1, MAX_BITS, MAX_BITS + 1] {
            let value = R::from_integer(
                num_rational::BigRational::from_float(2.0)
                    .unwrap()
                    .numer()
                    .clone()
                    << (bits - 2) as usize,
            );
            assert_eq!(Budget(0).check(value.clone()).is_some(), bits <= MAX_BITS);
            let reciprocal = R::new(1.into(), value.to_integer());
            assert_eq!(Budget(0).check(reciprocal).is_some(), bits <= MAX_BITS);
        }
        for used in [MAX_OPS - 2, MAX_OPS - 1, MAX_OPS] {
            assert_eq!(Budget(used).check(R::zero()).is_some(), used < MAX_OPS);
        }
    }
    #[test]
    fn expression_size_and_depth_limits_have_bounded_fallback() {
        fn scalar() -> Expression {
            Expression::Affine {
                constant: 1.0,
                terms: vec![],
            }
        }
        for depth in [MAX_DEPTH - 1, MAX_DEPTH, MAX_DEPTH + 1] {
            let mut e = scalar();
            for _ in 0..depth {
                e = Expression::Add {
                    left: Box::new(e),
                    right: Box::new(scalar()),
                };
            }
            assert_eq!(
                Curve::expression(&e, &[], &[], 1.0).is_some(),
                depth <= MAX_DEPTH
            );
        }
        fn tree(leaves: usize) -> Expression {
            if leaves == 1 {
                scalar()
            } else {
                Expression::Add {
                    left: Box::new(tree(leaves / 2)),
                    right: Box::new(tree(leaves - leaves / 2)),
                }
            }
        }
        // A binary expression tree has an odd node count: 511 and 513 are
        // the nearest representable sizes on either side of the 512 limit.
        for leaves in [255, 256, 257] {
            assert_eq!(
                Curve::expression(&tree(leaves), &[], &[], 1.0).is_some(),
                2 * leaves - 1 <= MAX_EXPR_NODES
            );
        }
    }

    #[test]
    fn varying_products_are_not_certified_as_linear_curves() {
        let node = Expression::Affine {
            constant: 0.0,
            terms: vec![crate::ir::Term {
                node: 1,
                coefficient: 1.0,
            }],
        };
        let sources = vec![Curve::source(&[[0.0, 0.0], [1.0, 1.0]])];
        let quadratic = Expression::Multiply {
            left: Box::new(node.clone()),
            right: Box::new(node.clone()),
        };
        assert!(Curve::expression(&quadratic, &[1], &sources, 1.0).is_none());
        let scaled = Expression::Multiply {
            left: Box::new(node),
            right: Box::new(Expression::Affine {
                constant: 2.0,
                terms: vec![],
            }),
        };
        assert!(Curve::expression(&scaled, &[1], &sources, 1.0).is_some());
    }
    #[test]
    fn narrow_nonrepresentable_upper_endpoint_keeps_nominal_in_range() {
        let source = Curve::source(&[[0.0, 0.0], [1.0, 0.0]]).unwrap();
        let (value, bounds) = source.wrapped(1.0, 1e16, 0.1, 1e16).unwrap();
        assert_eq!(value, 1e16);
        assert_eq!(bounds, I::point(1e16));
    }
    #[test]
    fn high_side_rounding_stays_inside_half_open_range_and_encloses_exact_value() {
        let tiny = f64::from_bits(1);
        let source = Curve::source(&[[0.0, -tiny], [1.0, -tiny]]).unwrap();
        let (value, bounds) = source.wrapped(1.0, 0.0, 1.0, 0.0).unwrap();
        assert_eq!(value, 1.0_f64.next_down());
        let exact = binary(1.0).unwrap() - binary(tiny).unwrap();
        assert!(binary(bounds.lo).unwrap() <= exact && exact <= binary(bounds.hi).unwrap());
    }
}

// Same-request opt-in event-prefix accounting. Unmarked consumers keep the old APIs.
mod event_prefix_fees {
    use super::{I, R};
    use crate::transition_source_plan::Work;
    pub(super) fn live(w: &Work) -> Result<(), crate::ir::Error> {
        w.debit(2, 0)
    }
    pub(super) fn metadata(w: &Work, n: u64) -> Result<(), crate::ir::Error> {
        live(w)?;
        w.debit(2, n)
    }
    pub(super) fn l(b: u64) -> u64 {
        b.div_ceil(64).saturating_add(1)
    }
    fn mul(b: u64) -> u64 {
        l(b).saturating_pow(2).saturating_mul(16)
    }
    pub(super) fn div(b: u64) -> u64 {
        mul(b)
    }
    fn gcd(b: u64) -> u64 {
        b.saturating_mul(2)
            .saturating_add(2)
            .saturating_mul(l(b))
            .saturating_mul(8)
    }
    pub(super) fn cmp(b: u64) -> u64 {
        b.saturating_mul(2).saturating_add(2).saturating_mul(
            div(b)
                .saturating_mul(2)
                .saturating_add(l(b).saturating_mul(16)),
        )
    }
    pub(super) fn binary(b: u64) -> u64 {
        gcd(b)
            .saturating_add(div(b).saturating_mul(2))
            .saturating_add(l(b).saturating_mul(32))
            .saturating_add(64)
    }
    pub(super) fn op(b: u64) -> u64 {
        gcd(b)
            .saturating_mul(4)
            .saturating_add(div(b).saturating_mul(8))
            .saturating_add(mul(b).saturating_mul(4))
            .saturating_add(l(b).saturating_mul(16))
    }
    pub(super) fn width(v: &R) -> u64 {
        v.numer().bits().max(v.denom().bits()).max(1)
    }
    pub(super) fn float_width(x: f64) -> Option<u64> {
        if !x.is_finite() {
            return None;
        }
        if x == 0.0 {
            return Some(1);
        }
        let e = ((x.to_bits() >> 52) & 2047) as i64;
        let p = if e == 0 { -1074 } else { e - 1023 - 52 };
        Some((53 + p.max(0)).max(1 + (-p).max(0)) as u64)
    }
    pub(super) fn endpoint_widths(v: I) -> Option<(u64, u64)> {
        Some((float_width(v.lo)?, float_width(v.hi)?))
    }
    pub(super) fn copy(b: u64) -> u64 {
        l(b).saturating_mul(4).saturating_add(32)
    }
    pub(super) fn enclosure(b: u64) -> u64 {
        let q = b.saturating_add(56);
        // One ratio_to_f64 (pinned shifted div/scan), three binary() and four Ratio comparisons.
        div(q)
            .saturating_add(l(q).saturating_mul(64))
            .saturating_add(64)
            .saturating_add(binary(q).saturating_mul(3))
            .saturating_add(cmp(q).saturating_mul(4))
            .saturating_add(64)
    }
    pub(super) fn contains(b: u64, lo: u64, hi: u64) -> u64 {
        binary(lo)
            .saturating_add(binary(hi))
            .saturating_add(cmp(b.max(lo)))
            .saturating_add(cmp(b.max(hi)))
            .saturating_add(64)
    }
}

/// The first two branches of pinned num-rational 0.4.2 Ratio::cmp.
/// Fund each BigInt pair scan before inspecting it. Unequal denominators and
/// numerators can use the existing bounded BigInt cross-product proof. Its
/// refusal retains the entire continued-fraction reservation and old body.
pub(crate) fn rational_order_with_work(
    a: &R,
    b: &R,
    w: &crate::transition_source_plan::Work,
) -> Result<std::cmp::Ordering, crate::ir::Error> {
    event_prefix_fees::metadata(w, 32)?;
    let bits = event_prefix_fees::width(a).max(event_prefix_fees::width(b));
    // BigInt equality/order first checks sign/length, then at most one pair
    // of limb reads/comparisons per limb. Sixteen units per pair also cover
    // loop/header checks and the constant sign/zero tests in that branch.
    let scan = event_prefix_fees::l(bits)
        .saturating_mul(16)
        .saturating_add(16);
    w.debit(2, scan)?;
    if a.denom() == b.denom() {
        w.debit(2, scan)?;
        let order = a.numer().cmp(b.numer());
        crate::diagnostics::counter("exact_order_equal_denominator", 1);
        return Ok(if a.denom().is_negative() {
            order.reverse()
        } else {
            order
        });
    }
    w.debit(2, scan)?;
    if a.numer() == b.numer() {
        if a.numer().is_zero() {
            crate::diagnostics::counter("exact_order_equal_numerator", 1);
            return Ok(std::cmp::Ordering::Equal);
        }
        w.debit(2, scan)?;
        let order = a.denom().cmp(b.denom());
        crate::diagnostics::counter("exact_order_equal_numerator", 1);
        return Ok(if a.numer().is_negative() {
            order
        } else {
            order.reverse()
        });
    }
    // The optional reader proves this order by two paid exact BigInt products,
    // without Ratio normalization or recursive division. Its original width
    // cap is unchanged. Nonpositive denominators keep the pinned old boundary.
    event_prefix_fees::metadata(w, 8)?;
    if a.denom().is_positive() && b.denom().is_positive() {
        if let Some(order) = forcing_point::cross(a, b, w)? {
            crate::diagnostics::counter("exact_order_bounded_cross", 1);
            return Ok(order);
        }
    }
    w.debit(2, event_prefix_fees::cmp(bits))?;
    crate::diagnostics::counter("exact_order_generic_fallback", 1);
    Ok(a.cmp(b))
}

/// Leading 64 bits of a nonzero magnitude given as its bit length and its u64
/// digits (least significant first), normalized so bit 63 is set: the
/// magnitude lies in `[top, top + inexact]·2^shift` with `inexact` 0 or 1.
/// Reads at most the two highest limbs.
fn leading_u64(
    bits: u64,
    mut digits: impl DoubleEndedIterator<Item = u64>,
) -> Option<(u64, i64, bool)> {
    let last = digits.next_back()?;
    if bits <= 64 {
        // Exactly one limb: shifting left is exact.
        let zeros = last.leading_zeros();
        return Some((last << zeros, -i64::from(zeros), false));
    }
    let next = digits.next_back()?;
    let zeros = last.leading_zeros();
    let top = if zeros == 0 {
        last
    } else {
        (last << zeros) | (next >> (64 - zeros))
    };
    Some((top, (bits - 64) as i64, true))
}

/// `x·2^e` for a positive normal `x` when the result is normal, exactly.
fn scale_normal(x: f64, e: i64) -> Option<f64> {
    let bits = x.to_bits();
    let biased = ((bits >> 52) & 0x7ff) as i64 + e;
    (x.is_normal() && x > 0. && (1..=2046).contains(&biased))
        .then(|| f64::from_bits((bits & !(0x7ff << 52)) | ((biased as u64) << 52)))
}

/// Tightest binary64 enclosure of a rational that is NOT a binary64 value,
/// from the leading bits of its numerator and denominator. The magnitude lies
/// in `[lo, hi]·2^e` (exact integer division with floor/ceil); when that
/// bracket, rounded outward, spans exactly one float gap, the value is strictly
/// inside the gap and its tightest enclosure is the gap. Otherwise, or outside
/// the normal range, return `None` for the exact generic path. The caller must
/// have excluded binary64 values (the dyadic fast path).
fn leading_bits_enclosure(value: &R) -> Option<I> {
    let (numer, denom) = (value.numer(), value.denom());
    let (n, n_shift, n_inexact) = leading_u64(numer.bits(), numer.iter_u64_digits())?;
    let (d, d_shift, d_inexact) = leading_u64(denom.bits(), denom.iter_u64_digits())?;
    let (n_lo, d_lo) = (u128::from(n), u128::from(d));
    let n_hi = n_lo + u128::from(n_inexact);
    let d_hi = d_lo + u128::from(d_inexact);
    // n in [2^63, 2^64], d in [2^63, 2^64]: both quotients lie in [2^62, 2^64].
    let lo = (n_lo << 63) / d_hi;
    let hi = ((n_hi << 63) + d_lo - 1) / d_lo;
    let e = n_shift - d_shift - 63;
    let down = |x: u128| {
        let f = x as f64;
        if f as u128 > x {
            f.next_down()
        } else {
            f
        }
    };
    let up = |x: u128| {
        let f = x as f64;
        if (f as u128) < x {
            f.next_up()
        } else {
            f
        }
    };
    let below = scale_normal(down(lo), e)?;
    let above = scale_normal(up(hi), e)?;
    if above != below.next_up() || !above.is_normal() {
        return None;
    }
    Some(if value.numer().is_negative() {
        I {
            lo: -above,
            hi: -below,
        }
    } else {
        I {
            lo: below,
            hi: above,
        }
    })
}

/// Result preserves old optional mathematical failure; Work errors are never discarded.
pub(crate) fn enclosure_with_work(
    value: &R,
    w: &crate::transition_source_plan::Work,
) -> Result<Option<I>, crate::ir::Error> {
    // A dyadic with at most53 significant numerator bits and an exponent in
    // binary64's exact range needs no reconstructed endpoint rationals. Pay
    // for both trailing-zero scans before proving that property.
    event_prefix_fees::metadata(w, 32)?;
    let bits = event_prefix_fees::width(value);
    w.debit(2, event_prefix_fees::l(bits).saturating_mul(32))?;
    let numerator = value.numer();
    let denominator = value.denom();
    let denominator_power = denominator.trailing_zeros();
    let exact = if numerator.is_zero() {
        true
    } else if let (Some(nz), Some(dz)) = (numerator.trailing_zeros(), denominator_power) {
        let significant = numerator.bits() - nz;
        let low = i128::from(nz) - i128::from(dz);
        let high = i128::from(numerator.bits()) - 1 - i128::from(dz);
        denominator.bits() == dz + 1 && significant <= 53 && low >= -1074 && high <= 1023
    } else {
        false
    };
    if exact {
        // Same pinned ratio_to_f64 reservation as the first part of enclosure;
        // no binary(endpoint) or rational comparisons are executed on this path.
        let q = bits.saturating_add(56);
        w.debit(
            2,
            event_prefix_fees::div(q)
                .saturating_add(event_prefix_fees::l(q).saturating_mul(64))
                .saturating_add(64),
        )?;
        crate::diagnostics::counter("forcing_exact_dyadic_enclosure", 1);
        return Ok(value.to_f64().filter(|v| v.is_finite()).map(I::point));
    }
    // Not a binary64 value. Its tightest enclosure is unique, so a rigorous
    // leading-bits bracket inside one float gap decides it without full-width
    // arithmetic. Reserve one ratio_to_f64-sized fee first; an undecided
    // bracket falls through to the unchanged generic path below.
    let q = bits.saturating_add(56);
    w.debit(
        2,
        event_prefix_fees::div(q)
            .saturating_add(event_prefix_fees::l(q).saturating_mul(64))
            .saturating_add(64),
    )?;
    if let Some(tight) = leading_bits_enclosure(value) {
        crate::diagnostics::counter("exact_leading_bits_enclosure", 1);
        return Ok(Some(tight));
    }
    // Failed shape recognition spends its work. Execute the original generic
    // enclosure with paid primitives so comparisons use the shared exact
    // implementation rather than reserving a continued-fraction body that
    // this path does not execute.
    crate::diagnostics::counter("forcing_prefix_enclosure_helpers", 1);
    let mut paid = history_paid::Paid::new(w);
    let result = (|| {
        let nearest = paid.nearest(value)?;
        if !nearest.is_finite() {
            return None;
        }
        let represented = paid.binary(nearest)?;
        let order = paid.cmp(&represented, value)?;
        // Preserve the fixed allowance before nextafter/box/finite work.
        paid.pay(64)?;
        let bounds = I {
            lo: if order.is_gt() {
                nearest.next_down()
            } else {
                nearest
            },
            hi: if order.is_lt() {
                nearest.next_up()
            } else {
                nearest
            },
        };
        if !bounds.finite() {
            return None;
        }
        let lo = paid.binary(bounds.lo)?;
        if paid.cmp(&lo, value)?.is_gt() {
            return None;
        }
        let hi = paid.binary(bounds.hi)?;
        if paid.cmp(value, &hi)?.is_gt() {
            return None;
        }
        Some(bounds)
    })();
    paid.finish(result)
}
impl RootTime {
    pub(crate) fn clone_with_work(
        &self,
        w: &crate::transition_source_plan::Work,
    ) -> Result<Self, crate::ir::Error> {
        event_prefix_fees::metadata(w, 32)?;
        w.debit(
            2,
            event_prefix_fees::copy(event_prefix_fees::width(&self.0)),
        )?;
        crate::diagnostics::counter("forcing_prefix_exact_clones", 1);
        Ok(self.clone())
    }
    pub(crate) fn order_with_work(
        &self,
        other: &Self,
        w: &crate::transition_source_plan::Work,
    ) -> Result<std::cmp::Ordering, crate::ir::Error> {
        event_prefix_fees::metadata(w, 64)?;
        let b = event_prefix_fees::width(&self.0).max(event_prefix_fees::width(&other.0));
        w.debit(2, event_prefix_fees::cmp(b))?;
        crate::diagnostics::counter("forcing_prefix_exact_comparisons", 1);
        Ok(self.order(other))
    }
    pub(crate) fn refine_with_work(
        &self,
        discovery: I,
        w: &crate::transition_source_plan::Work,
    ) -> Result<Option<I>, crate::ir::Error> {
        event_prefix_fees::metadata(w, 64)?;
        let Some((lo, hi)) = event_prefix_fees::endpoint_widths(discovery) else {
            return Ok(None);
        };
        // A memoized paid enclosure of this immutable root is tight: the exact
        // point, or two adjacent floats strictly around the value. For binary64
        // endpoints it decides containment exactly, except when an endpoint
        // falls inside it; only that overlap repeats the exact comparison.
        if self.1 .0.get().is_some() {
            event_prefix_fees::metadata(w, 16)?;
            crate::diagnostics::counter("exact_root_enclosure_memo_hits", 1);
            match *self.1 .0.get().unwrap() {
                None => return Ok(None),
                Some(tight) if discovery.lo <= tight.lo && tight.hi <= discovery.hi => {
                    w.debit(2, 64)?;
                    return Ok(Some(tight));
                }
                Some(tight) if tight.hi < discovery.lo || discovery.hi < tight.lo => {
                    return Ok(None)
                }
                Some(_) => {}
            }
        }
        let b = event_prefix_fees::width(&self.0);
        // First query (or an overlapping endpoint): preserve the original
        // containment reservation and refusal before constructing an enclosure.
        w.debit(2, event_prefix_fees::contains(b, lo, hi))?;
        crate::diagnostics::counter("forcing_prefix_exact_refinements", 1);
        if !contains(discovery, &self.0) {
            return Ok(None);
        }
        let tight = match self.1 .0.get() {
            Some(tight) => *tight,
            None => {
                // Same paid enclosure as before; a failure installs nothing.
                let tight = enclosure_with_work(&self.0, w)?;
                let _ = self.1 .0.set(tight);
                tight
            }
        };
        let Some(tight) = tight else {
            return Ok(None);
        };
        w.debit(2, 64)?;
        Ok(Some(I {
            lo: discovery.lo.max(tight.lo),
            hi: discovery.hi.min(tight.hi),
        }))
    }
    pub(crate) fn from_clock_with_work(
        clock: crate::exact_time::Clock,
        discovery: I,
        w: &crate::transition_source_plan::Work,
    ) -> Result<Option<Self>, crate::ir::Error> {
        event_prefix_fees::metadata(w, 96)?;
        if clock.index > crate::schedule::EVENT_BUDGET {
            return Ok(None);
        }
        let Some(s) = event_prefix_fees::float_width(clock.start) else {
            return Ok(None);
        };
        let Some(p) = event_prefix_fees::float_width(clock.period) else {
            return Ok(None);
        };
        let Some((lo, hi)) = event_prefix_fees::endpoint_widths(discovery) else {
            return Ok(None);
        };
        let index_bits = (usize::BITS - clock.index.leading_zeros()).max(1) as u64;
        let offset = p.saturating_add(index_bits).saturating_add(1);
        let result = s.saturating_add(offset).saturating_add(1);
        let fee = event_prefix_fees::binary(s)
            .saturating_add(event_prefix_fees::binary(p))
            .saturating_add(64)
            .saturating_add(event_prefix_fees::l(index_bits).saturating_mul(32))
            .saturating_add(event_prefix_fees::op(offset))
            .saturating_add(event_prefix_fees::op(result))
            .saturating_add(event_prefix_fees::contains(result, lo, hi));
        w.debit(2, fee)?;
        crate::diagnostics::counter("forcing_prefix_clock_helpers", 1);
        Ok(Self::from_clock(clock, discovery))
    }
    pub(crate) fn point_ends_with_work(
        segment: [f64; 2],
        ends: [I; 2],
        discovery: I,
        w: &crate::transition_source_plan::Work,
    ) -> Result<Option<Self>, crate::ir::Error> {
        event_prefix_fees::metadata(w, 128)?;
        if ends.iter().any(|v| v.lo != v.hi) {
            return Ok(None);
        }
        let Some(a) = event_prefix_fees::float_width(ends[0].lo) else {
            return Ok(None);
        };
        let Some(b) = event_prefix_fees::float_width(ends[1].lo) else {
            return Ok(None);
        };
        let Some(s) = event_prefix_fees::float_width(segment[0]) else {
            return Ok(None);
        };
        let Some(e) = event_prefix_fees::float_width(segment[1]) else {
            return Ok(None);
        };
        let Some((lo, hi)) = event_prefix_fees::endpoint_widths(discovery) else {
            return Ok(None);
        };
        let duration = s.saturating_add(e).saturating_add(1);
        let change = b.saturating_add(a).saturating_add(1);
        let numerator = a.saturating_add(duration).saturating_add(1);
        let shift = numerator.saturating_add(change).saturating_add(1);
        let result = s.saturating_add(shift).saturating_add(1);
        let fee = [a, b, s, e]
            .into_iter()
            .fold(0u64, |n, b| n.saturating_add(event_prefix_fees::binary(b)))
            .saturating_add(event_prefix_fees::cmp(a.max(b))) // original generic a==b
            .saturating_add(
                [duration, change, numerator, shift, result]
                    .into_iter()
                    .fold(0u64, |n, b| n.saturating_add(event_prefix_fees::op(b))),
            )
            .saturating_add(event_prefix_fees::cmp(s.max(result)))
            .saturating_add(event_prefix_fees::cmp(result.max(e)))
            .saturating_add(event_prefix_fees::contains(result, lo, hi))
            .saturating_add(128);
        w.debit(2, fee)?;
        crate::diagnostics::counter("forcing_prefix_cross_helpers", 1);
        Ok(Self::point_ends(segment, ends, discovery))
    }
}

#[cfg(test)]
mod event_prefix_accounting_tests {
    use super::*;
    use crate::transition_source_plan::Work;
    #[test]
    fn paid_root_math_retains_independent_small_values_and_sticky_refusal() {
        let work = Work::default();
        for (n, d) in [(0, 1), (1, 3), (-2, 7), (3, 8)] {
            let value = R::new(n.into(), d.into());
            let bounds = enclosure_with_work(&value, &work).unwrap().unwrap();
            assert!(binary(bounds.lo).unwrap() <= value && value <= binary(bounds.hi).unwrap());
            assert_eq!(Some(bounds), enclosure(&value));
        }
        let clock = crate::exact_time::Clock {
            start: 0.125,
            period: 0.25,
            index: 3,
        };
        let root = RootTime::from_clock_with_work(clock, I::point(0.875), &work)
            .unwrap()
            .unwrap();
        assert_eq!(*root.rational(), R::new(7.into(), 8.into()));
        assert_eq!(
            root.refine_with_work(I { lo: 0.8, hi: 0.9 }, &work)
                .unwrap(),
            Some(I::point(0.875))
        );
        let empty = Work::limited([128, 8192, 0]);
        let before = root.clone();
        for _ in 0..2 {
            let (result, report) = crate::diagnostics::capture(Default::default(), || {
                root.refine_with_work(I::point(0.875), &empty)
            });
            assert_eq!(result.unwrap_err().kind, "step_budget");
            assert!(!report
                .counters
                .keys()
                .any(|k| k.starts_with("forcing_prefix_")));
            assert_eq!(root, before);
        }
    }
}

// private field inspection is behind metadata prepayment.
impl RootTime {
    pub(crate) fn bounds_with_work(
        &self,
        w: &crate::transition_source_plan::Work,
    ) -> Result<Option<I>, crate::ir::Error> {
        enclosure_with_work(&self.0, w)
    }
    /// The same paid outward enclosure as `bounds_with_work`, computed at most
    /// once per immutable root. Later reads pay only the lookup. A failed or
    /// exhausted computation installs nothing.
    pub(crate) fn memo_bounds_with_work(
        &self,
        w: &crate::transition_source_plan::Work,
    ) -> Result<Option<I>, crate::ir::Error> {
        event_prefix_fees::metadata(w, 16)?;
        if let Some(bounds) = self.1 .0.get() {
            crate::diagnostics::counter("exact_root_enclosure_memo_hits", 1);
            return Ok(*bounds);
        }
        let bounds = enclosure_with_work(&self.0, w)?;
        let _ = self.1 .0.set(bounds);
        Ok(bounds)
    }
    fn difference_clock_reservation(
        &self,
        clock: crate::exact_time::Clock,
        w: &crate::transition_source_plan::Work,
    ) -> Result<Option<u64>, crate::ir::Error> {
        event_prefix_fees::metadata(w, 128)?;
        if clock.index > crate::schedule::EVENT_BUDGET {
            return Ok(None);
        }
        let Some(s) = event_prefix_fees::float_width(clock.start) else {
            return Ok(None);
        };
        let Some(p) = event_prefix_fees::float_width(clock.period) else {
            return Ok(None);
        };
        let i = (usize::BITS - clock.index.leading_zeros()).max(1) as u64;
        let offset = p.saturating_add(i).saturating_add(1);
        let absolute = s.saturating_add(offset).saturating_add(1);
        let difference = event_prefix_fees::width(&self.0)
            .saturating_add(absolute)
            .saturating_add(1);
        let fee = event_prefix_fees::binary(s)
            .saturating_add(event_prefix_fees::binary(p))
            .saturating_add(event_prefix_fees::l(i).saturating_mul(32))
            .saturating_add(64)
            .saturating_add(event_prefix_fees::op(offset))
            .saturating_add(event_prefix_fees::op(absolute))
            .saturating_add(event_prefix_fees::op(difference));
        w.debit(2, fee)?;
        Ok(Some(difference))
    }
    pub(crate) fn clock_delta_order_with_work(
        &self,
        clock: crate::exact_time::Clock,
        delta: f64,
        w: &crate::transition_source_plan::Work,
    ) -> Result<Option<std::cmp::Ordering>, crate::ir::Error> {
        // A degenerate clock with zero delta is the exact binary64 point
        // `clock.start`. An outward enclosure strictly on one side of it
        // proves the sign of root - start; the memo avoids repeating the
        // rational difference at every query of the same pending root.
        if delta == 0. && (clock.index == 0 || clock.period == 0.) && clock.start.is_finite() {
            if let Some(bounds) = self.memo_bounds_with_work(w)? {
                if bounds.hi < clock.start {
                    return Ok(Some(std::cmp::Ordering::Less));
                }
                if bounds.lo > clock.start {
                    return Ok(Some(std::cmp::Ordering::Greater));
                }
            }
        }
        let Some(difference) = self.difference_clock_reservation(clock, w)? else {
            return Ok(None);
        };
        let Some(d) = event_prefix_fees::float_width(delta) else {
            return Ok(None);
        };
        let result = difference.saturating_add(d).saturating_add(1);
        w.debit(
            2,
            event_prefix_fees::binary(d)
                .saturating_add(event_prefix_fees::op(result))
                .saturating_add(event_prefix_fees::cmp(result))
                .saturating_add(64),
        )?;
        Ok(self.clock_delta_order(clock, delta))
    }
    pub(crate) fn local_bounds_with_work(
        &self,
        clock: crate::exact_time::Clock,
        w: &crate::transition_source_plan::Work,
    ) -> Result<Option<I>, crate::ir::Error> {
        let Some(b) = self.difference_clock_reservation(clock, w)? else {
            return Ok(None);
        };
        w.debit(2, event_prefix_fees::enclosure(b))?;
        Ok(self.local_bounds(clock))
    }
}

#[cfg(test)]
mod dyadic_enclosure_work_controls {
    use super::*;
    use crate::transition_source_plan::Work;

    #[test]
    fn repeated_exact_binary_values_fit_the_same_owned_small_work_allowance() {
        let work = Work::limited([128, 8192, 1_000_000]);
        // 3/2 is exactly binary64. No endpoint reconstruction/comparison is
        // needed after a paid exact-representability proof.
        let value = R::new(3.into(), 2.into());
        for _ in 0..64 {
            assert_eq!(
                enclosure_with_work(&value, &work).unwrap(),
                Some(I::point(1.5))
            );
        }
        assert!(work.spent() > 0 && work.spent() <= 1_000_000);
    }
    #[test]
    fn independent_binary_extremes_and_nonbinary_enclosures_are_preserved() {
        let work = Work::default();
        let power = |n: usize| R::from_integer(1.into()).numer().clone() << n;
        let exact = [
            (R::new(3.into(), 2.into()), 1.5),
            (R::new(1.into(), power(1074)), f64::from_bits(1)),
            (R::from_integer((power(53) - 1u8) << 971), f64::MAX),
            (R::new(power(53) - 1u8, power(53)), 1f64.next_down()),
            (R::from_integer(power(1023)), 2f64.powi(1023)),
            (R::zero(), 0.),
        ];
        for (q, x) in exact {
            assert_eq!(enclosure_with_work(&q, &work).unwrap(), Some(I::point(x)));
            assert_eq!(
                enclosure_with_work(&(-q), &work).unwrap(),
                Some(I::point(-x))
            );
        }
        for (q, expected) in [
            (
                R::new(1.into(), 3.into()),
                I {
                    lo: 1. / 3.,
                    hi: (1f64 / 3.).next_up(),
                },
            ),
            (
                R::new(1.into(), power(1075)),
                I {
                    lo: 0.,
                    hi: f64::from_bits(1),
                },
            ),
            (
                R::from_integer(power(53) + 1u8),
                I {
                    lo: 9_007_199_254_740_992.,
                    hi: 9_007_199_254_740_994.,
                },
            ),
        ] {
            assert_eq!(enclosure_with_work(&q, &work).unwrap(), Some(expected));
            assert_eq!(
                enclosure_with_work(&(-q), &work).unwrap(),
                Some(I {
                    lo: -expected.hi,
                    hi: -expected.lo
                })
            );
        }
    }
    #[test]
    fn small_owner_exhaustion_is_sticky_before_any_dyadic_or_fallback_body() {
        let work = Work::limited([128, 8192, 0]);
        for q in [R::new(3.into(), 2.into()), R::new(1.into(), 3.into())] {
            for _ in 0..2 {
                let before = work.spent();
                let (result, report) = crate::diagnostics::capture(Default::default(), || {
                    enclosure_with_work(&q, &work)
                });
                assert_eq!(result.unwrap_err().kind, "step_budget");
                assert_eq!(
                    report.counters.get("forcing_prefix_enclosure_helpers"),
                    None
                );
                assert_eq!(report.counters.get("forcing_exact_dyadic_enclosure"), None);
                assert!(work.spent() >= before);
            }
        }
    }
}

#[cfg(test)]
mod refine_reuse_tests {
    use super::*;
    use crate::transition_source_plan::Work;

    #[test]
    fn paid_refinement_preserves_old_and_independent_tight_boxes() {
        let power = |n: usize| R::from_integer(1.into()).numer().clone() << n;
        for (value, discovery, expected) in [
            (
                R::new(3.into(), 2.into()),
                I { lo: 1., hi: 2. },
                I::point(1.5),
            ),
            (
                R::new(1.into(), 3.into()),
                I { lo: 0., hi: 1. },
                I {
                    lo: 1. / 3.,
                    hi: (1f64 / 3.).next_up(),
                },
            ),
            (
                R::new(1.into(), power(1074)),
                I {
                    lo: 0.,
                    hi: f64::from_bits(2),
                },
                I::point(f64::from_bits(1)),
            ),
            (
                R::new(1.into(), power(1075)),
                I {
                    lo: 0.,
                    hi: f64::from_bits(2),
                },
                I {
                    lo: 0.,
                    hi: f64::from_bits(1),
                },
            ),
        ] {
            let root = RootTime::raw(value);
            let work = Work::default();
            let result = root.refine_with_work(discovery, &work).unwrap();
            assert_eq!(result, Some(expected));
            assert_eq!(result, root.refine(discovery));
        }
    }

    #[test]
    fn incompatible_discovery_pays_contains_without_running_enclosure() {
        let root = RootTime::raw(R::new(3.into(), 2.into()));
        let discovery = I { lo: 0., hi: 1. };
        let (lo, hi) = event_prefix_fees::endpoint_widths(discovery).unwrap();
        let containment =
            event_prefix_fees::contains(event_prefix_fees::width(root.rational()), lo, hi);
        let work = Work::limited([128, 8192, 64 + containment]);
        assert_eq!(root.refine_with_work(discovery, &work).unwrap(), None);
        assert_eq!(root.refine(discovery), None);
        assert_eq!(work.spent(), 64 + containment);
        // Reversed finite and nonfinite discoveries also retain old refusal.
        for discovery in [
            I { lo: 2., hi: 1. },
            I {
                lo: f64::NEG_INFINITY,
                hi: 2.,
            },
        ] {
            let work = Work::default();
            assert_eq!(
                root.refine_with_work(discovery, &work).unwrap(),
                root.refine(discovery)
            );
        }
    }

    #[test]
    fn enclosure_reservation_failure_is_sticky_for_two_retries() {
        let root = RootTime::raw(R::new(3.into(), 2.into()));
        let discovery = I { lo: 1., hi: 2. };
        let (lo, hi) = event_prefix_fees::endpoint_widths(discovery).unwrap();
        let containment =
            event_prefix_fees::contains(event_prefix_fees::width(root.rational()), lo, hi);
        // An independently scaled boundary: contains fits exactly, so only
        // the subsequent real enclosure metadata reservation must exhaust.
        let limit = 64 + containment;
        let work = Work::limited([128, 8192, limit]);
        assert_eq!(
            root.refine_with_work(discovery, &work).unwrap_err().kind,
            "step_budget"
        );
        assert_eq!(work.spent(), limit + 32);
        for _ in 0..2 {
            let spent = work.spent();
            assert_eq!(
                root.refine_with_work(discovery, &work).unwrap_err().kind,
                "step_budget"
            );
            assert!(work.spent() >= spent);
            assert_eq!(root.refine(discovery), Some(I::point(1.5)));
        }
    }

    #[test]
    fn memoized_refinement_is_the_exact_refinement_without_repeated_containment() {
        let third = 1f64 / 3.;
        for (value, discoveries) in [
            (
                R::new(3.into(), 2.into()),
                vec![
                    I { lo: 1., hi: 2. },
                    I { lo: 0., hi: 1. },
                    I::point(1.5),
                    I {
                        lo: 1.5,
                        hi: 1.5f64.next_up(),
                    },
                ],
            ),
            (
                R::new(1.into(), 3.into()),
                vec![
                    I { lo: 0., hi: 1. },
                    I { lo: 0.5, hi: 1. },
                    // Endpoints inside the adjacent-float enclosure: the
                    // exact value lies strictly between them, so both refuse.
                    I {
                        lo: third.next_up(),
                        hi: 1.,
                    },
                    I { lo: 0., hi: third },
                    I {
                        lo: third,
                        hi: third.next_up(),
                    },
                ],
            ),
        ] {
            let root = RootTime::raw(value);
            let first = Work::default();
            // The first query keeps the original fee sequence and installs
            // the enclosure; later queries read it.
            let _ = root
                .refine_with_work(I { lo: -4., hi: 4. }, &first)
                .unwrap();
            for discovery in discoveries {
                let expected = root.refine(discovery);
                let work = Work::default();
                assert_eq!(root.refine_with_work(discovery, &work).unwrap(), expected);
                let tight = root.bounds().unwrap();
                let decided = (discovery.lo <= tight.lo && tight.hi <= discovery.hi)
                    || tight.hi < discovery.lo
                    || discovery.hi < tight.lo;
                if decided {
                    // metadata + memo lookup (+ the result box), no containment.
                    let result = if expected.is_some() { 64 } else { 0 };
                    assert_eq!(work.spent(), 64 + 16 + result, "{discovery:?}");
                }
            }
        }
    }
}

#[cfg(test)]
mod generic_enclosure_paid_tests {
    use super::*;
    use crate::transition_source_plan::Work;

    fn assert_bits(actual: Option<I>, expected: Option<I>) {
        assert_eq!(
            actual.map(|b| [b.lo.to_bits(), b.hi.to_bits()]),
            expected.map(|b| [b.lo.to_bits(), b.hi.to_bits()])
        );
    }

    #[test]
    fn independent_signed_thirds_half_subnormal_and_extremes_keep_old_boxes() {
        let power = |n: usize| R::from_integer(1.into()).numer().clone() << n;
        let third = 1f64 / 3.;
        let tiny = f64::from_bits(1);
        let cases = [
            (
                R::new(1.into(), 3.into()),
                I {
                    lo: third,
                    hi: third.next_up(),
                },
            ),
            (
                R::new((-1).into(), 3.into()),
                I {
                    lo: (-third).next_down(),
                    hi: -third,
                },
            ),
            (R::new(3.into(), 2.into()), I::point(1.5)),
            (R::new(1.into(), power(1074)), I::point(tiny)),
            (R::new(1.into(), power(1075)), I { lo: 0., hi: tiny }),
            (
                R::new((-1).into(), power(1075)),
                I {
                    lo: -tiny,
                    hi: -0.0,
                },
            ),
            (
                R::from_integer(power(53) + 1u8),
                I {
                    lo: 9_007_199_254_740_992.,
                    hi: 9_007_199_254_740_994.,
                },
            ),
            (binary(f64::MAX).unwrap(), I::point(f64::MAX)),
            (binary(-f64::MAX).unwrap(), I::point(-f64::MAX)),
        ];
        for (value, expected) in cases {
            let work = Work::default();
            let actual = enclosure_with_work(&value, &work).unwrap();
            assert_bits(actual, Some(expected));
            assert_bits(actual, enclosure(&value));
            let bounds = actual.unwrap();
            assert!(binary(bounds.lo).unwrap() <= value && value <= binary(bounds.hi).unwrap());
        }
    }

    #[test]
    fn rationals_on_both_sides_of_adjacent_midpoint_keep_one_ulp_box() {
        let low = 1f64;
        let high = low.next_up();
        let a = binary(low).unwrap();
        let b = binary(high).unwrap();
        // Both sides of the midpoint have different rounded nearest values,
        // but the same mathematically necessary adjacent enclosing endpoints.
        for weight in [1, 2, 3] {
            let value = (&a * R::from_integer((4 - weight).into())
                + &b * R::from_integer(weight.into()))
                / R::from_integer(4.into());
            for (value, expected) in [
                (value.clone(), I { lo: low, hi: high }),
                (
                    -value,
                    I {
                        lo: -high,
                        hi: -low,
                    },
                ),
            ] {
                let actual = enclosure_with_work(&value, &Work::default()).unwrap();
                assert_bits(actual, Some(expected));
                assert_bits(actual, enclosure(&value));
            }
        }
    }

    #[test]
    fn overflow_and_nonfinite_rational_conversion_preserve_old_none() {
        let max = binary(f64::MAX).unwrap();
        for value in [
            &max * R::from_integer(2.into()),
            -&max * R::from_integer(2.into()),
            R::new_raw(1.into(), 0.into()),
            R::new_raw((-1).into(), 0.into()),
            R::new_raw(0.into(), 0.into()),
        ] {
            assert_eq!(enclosure(&value), None);
            assert_eq!(enclosure_with_work(&value, &Work::default()).unwrap(), None);
        }
    }

    #[test]
    fn repeated_generic_reads_exhaust_original_owner_and_two_retries_stay_failed() {
        // A scaled independent Work boundary, not the production 1e9 cap.
        // Every debit below comes from an actual enclosure read; no manual
        // drain or fresh Work is used to make the failure occur.
        let work = Work::limited([128, 8192, 1_000_000]);
        let value = R::new(1.into(), 3.into());
        let expected = I {
            lo: 1. / 3.,
            hi: (1f64 / 3.).next_up(),
        };
        let mut succeeded = 0;
        loop {
            match enclosure_with_work(&value, &work) {
                Ok(bounds) => {
                    assert_bits(bounds, Some(expected));
                    succeeded += 1;
                    assert!(succeeded < 10_000);
                }
                Err(error) => {
                    assert_eq!(error.kind, "step_budget");
                    break;
                }
            }
        }
        assert!(succeeded > 0 && work.spent() > 1_000_000);
        for _ in 0..2 {
            let spent = work.spent();
            // A fresh Paid wrapper must not restore its borrowed Work owner.
            let mut paid = history_paid::Paid::new(&work);
            let result = paid.enclose(&value);
            assert_eq!(paid.finish(result).unwrap_err().kind, "step_budget");
            assert!(work.spent() >= spent);
        }
    }

    fn rational(numer: &[u64], denom: &[u64], negative: bool) -> R {
        let digits = |d: &[u64]| {
            d.iter()
                .rev()
                .fold(R::from_integer(0.into()).numer().clone(), |acc, &x| {
                    (acc << 64usize) + x
                })
        };
        let n = digits(numer);
        R::new(if negative { -n } else { n }, digits(denom))
    }

    /// The leading-bits bracket either equals the exact old enclosure bit for
    /// bit or abstains; it never decides a binary64 value.
    fn agrees(value: &R) -> bool {
        let fast = leading_bits_enclosure(value);
        let exact = enclosure(value);
        let float = exact.is_some_and(|b| b.lo == b.hi);
        if let Some(fast) = fast {
            assert!(!float, "decided a binary64 value {value}");
            assert_bits(Some(fast), exact);
        }
        // The paid entry point returns the old box whichever path decides.
        assert_bits(enclosure_with_work(value, &Work::default()).unwrap(), exact);
        fast.is_some()
    }

    #[test]
    fn leading_bits_enclosure_equals_the_exact_box_or_abstains() {
        let third = R::new(1.into(), 3.into());
        let power = |n: usize| R::from_integer(1.into()).numer().clone() << n;
        // Wide event-time style rationals, both signs, and the narrow cases.
        let mut decided = 0;
        for (numer, denom) in [
            (vec![1], vec![3]),
            (vec![7], vec![10]),
            (vec![u64::MAX, 3], vec![5]),
            (vec![12345, 6789, 1], vec![987654321, 2]),
            (vec![1, 2, 3, 4, 5], vec![6, 7, 8, 9]),
            (vec![u64::MAX; 6], vec![u64::MAX - 2; 5]),
            (vec![3], vec![u64::MAX, u64::MAX, 1]),
        ] {
            for negative in [false, true] {
                decided += usize::from(agrees(&rational(&numer, &denom, negative)));
            }
        }
        assert!(decided >= 10, "fast path decided only {decided}");
        // Within a few bits of a float (bracket may straddle), exact floats
        // and dyadics wider than 53 bits, and range edges.
        let eps = R::new(1.into(), power(80));
        for value in [
            binary(0.73).unwrap() + &eps,
            binary(0.73).unwrap() - &eps,
            binary(1.5).unwrap(),
            R::from_integer(power(53) + 1u8),
            binary(f64::MAX).unwrap() + &third,
            binary(f64::MIN_POSITIVE).unwrap() * &third,
            R::new(1.into(), power(1074)) * &third,
        ] {
            agrees(&value);
        }
        // Deterministic sweep of wide rationals: nearly all are decided.
        let mut state = 0x9e37_79b9_7f4a_7c15u64;
        let mut next = || {
            state ^= state << 13;
            state ^= state >> 7;
            state ^= state << 17;
            state
        };
        let (mut total, mut fast) = (0, 0);
        for _ in 0..4000 {
            let n: Vec<u64> = (0..1 + next() % 5).map(|_| next()).collect();
            let d: Vec<u64> = (0..1 + next() % 5).map(|_| next() | 1).collect();
            let negative = next() & 1 == 1;
            total += 1;
            fast += usize::from(agrees(&rational(&n, &d, negative)));
        }
        assert!(fast * 100 >= total * 95, "decided {fast} of {total}");
    }

    proptest::proptest! {
        #[test]
        fn leading_bits_enclosure_matches_exact_on_random_wide_rationals(
            numer in proptest::collection::vec(proptest::prelude::any::<u64>(), 1..6),
            denom in proptest::collection::vec(proptest::prelude::any::<u64>(), 1..6),
            negative in proptest::prelude::any::<bool>(),
        ) {
            proptest::prop_assume!(denom.iter().any(|&d| d != 0) && numer.iter().any(|&n| n != 0));
            agrees(&rational(&numer, &denom, negative));
        }
    }
}

#[cfg(test)]
mod memo_clock_order_controls {
    use super::*;
    use crate::exact_time::Clock;
    use crate::transition_source_plan::Work;

    fn point(start: f64) -> Clock {
        Clock {
            start,
            period: 0.,
            index: 0,
        }
    }

    #[test]
    fn repeated_point_queries_reuse_one_paid_enclosure_with_exact_answers() {
        // 1/3 is not dyadic: the uncached route pays a rational difference
        // and comparison for every query of the same pending root.
        let root = RootTime::raw(R::new(1.into(), 3.into()));
        let near = root.bounds().unwrap();
        let queries = [0.25, 0.5, near.lo, near.hi, 1e-300, 1.];
        let memo = Work::default();
        for &t in &queries {
            assert_eq!(
                root.clock_delta_order_with_work(point(t), 0., &memo)
                    .unwrap(),
                root.clock_delta_order(point(t), 0.),
            );
        }
        let separated = [0.25, 0.5, 1e-300, 1.];
        let first = memo.spent();
        for &t in &separated {
            root.clock_delta_order_with_work(point(t), 0., &memo)
                .unwrap();
        }
        let repeated = memo.spent() - first;
        // Lower bound of the uncached route: its reservation alone.
        let fresh = Work::default();
        for &t in &separated {
            RootTime::raw(R::new(1.into(), 3.into()))
                .difference_clock_reservation(point(t), &fresh)
                .unwrap();
        }
        assert!(repeated < fresh.spent(), "{repeated} vs {}", fresh.spent());
    }

    #[test]
    fn coincident_or_nonpoint_clocks_keep_the_exact_rational_route() {
        let work = Work::default();
        // The enclosure of an exact binary point touches the query: only the
        // rational difference may decide equality.
        let root = RootTime::raw(R::new(3.into(), 2.into()));
        assert_eq!(
            root.clock_delta_order_with_work(point(1.5), 0., &work)
                .unwrap(),
            Some(std::cmp::Ordering::Equal)
        );
        // A periodic clock or nonzero delta is not the binary64 start.
        let clock = Clock {
            start: 0.5,
            period: 0.5,
            index: 2,
        };
        assert_eq!(
            root.clock_delta_order_with_work(clock, 0., &work).unwrap(),
            Some(std::cmp::Ordering::Equal)
        );
        assert_eq!(
            root.clock_delta_order_with_work(point(1.), 0.5, &work)
                .unwrap(),
            Some(std::cmp::Ordering::Equal)
        );
        // An exhausted owner installs no memo and still refuses.
        let empty = Work::limited([128, 8192, 0]);
        let fresh = RootTime::raw(R::new(1.into(), 3.into()));
        assert_eq!(
            fresh
                .clock_delta_order_with_work(point(0.5), 0., &empty)
                .unwrap_err()
                .kind,
            "step_budget"
        );
        assert!(fresh.1 .0.get().is_none());
    }
}
