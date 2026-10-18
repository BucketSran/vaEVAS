//! Bounded exact binary64 source arithmetic for phase and ordinary conditions.
//! Curves retain original rational knots; rounded clamp knots are never inputs.
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
#[derive(Clone, Debug, PartialEq, Eq)]
pub(crate) struct RootTime(R);

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
    pub(crate) fn rational(&self) -> &R {
        &self.0
    }
    pub(crate) fn point(time: f64) -> Option<Self> {
        Some(Self(binary(time)?))
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
        (left.0 < middle && middle < right.0).then_some(Self(middle))
    }
    /// Original fixed-clock arithmetic; the proof must fit discovery unchanged.
    pub(crate) fn from_clock(clock: crate::exact_time::Clock, discovery: I) -> Option<Self> {
        if clock.index > crate::schedule::EVENT_BUDGET {
            return None;
        }
        let mut budget = Budget(0);
        let offset = budget.check(binary(clock.period)? * R::from_integer(clock.index.into()))?;
        let time = budget.check(binary(clock.start)? + offset)?;
        contains(discovery, &time).then_some(Self(time))
    }

    pub(crate) fn shifted_fixed(&self, delta: f64, discovery: I) -> Option<Self> {
        let time = Budget(0).check(&self.0 + binary(delta)?)?;
        contains(discovery, &time).then_some(Self(time))
    }

    pub(crate) fn affine(value: R, slope: R, bounds: I) -> Option<Self> {
        if slope.is_zero() {
            return None;
        }
        let root = Budget(0).check(-value / slope)?;
        contains(bounds, &root).then_some(Self(root))
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
        (start < time && time <= end && contains(bounds, &time)).then_some(Self(time))
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
        Some(Self(budget.check(&self.0 + absolute)?))
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
    pub(crate) fn charge_source_copy(
        &self,
        work: &crate::transition_source_plan::Work,
    ) -> Result<(), crate::ir::Error> {
        for (t, v) in &self.0 {
            work.debit(2, 1)?;
            crate::diagnostics::counter("selected_ln_ast_visits", 1);
            crate::diagnostics::counter("selected_ln_work_debit", 1);
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
            crate::diagnostics::counter("selected_ln_copy_items", items);
            crate::diagnostics::counter("selected_ln_work_debit", items);
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
                time: RootTime(time.clone()),
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
            out.extend([RootTime(a.clone()), RootTime(b.clone())]);
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
            out.push(RootTime(root));
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
        let representative = super::RootTime(super::binary(window.hi).unwrap());
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
