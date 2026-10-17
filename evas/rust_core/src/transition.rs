//! Fixed-delay transition history. Observation queries never mutate an edge.
use crate::interval::Interval as I;
use crate::ir::Error;
use std::collections::VecDeque;

#[derive(Clone, Debug, PartialEq)]
pub(crate) struct Deadline {
    continuous_end: bool,
    pub(crate) bounds: I,
    // Exact symbolic sum when available; equal enclosures alone do not prove
    // coincident real deadlines. Interrupted-edge endpoints have no sum key.
    sum: Option<[f64; 3]>,
    exact: Option<crate::exact_source::RootTime>,
}
impl Deadline {
    pub(crate) fn independent_end_checkpoints(&self, other: &Self) -> bool {
        self.continuous_end
            && other.continuous_end
            && self.exact_time().is_some()
            && other.exact_time().is_some()
    }
    pub(crate) fn serial_representatives(&self, other: &Self) -> bool {
        let strictly_after = |later: &Self, earlier: f64| {
            later
                .exact_time()
                .zip(crate::exact_source::RootTime::point(earlier))
                .is_some_and(|(a, b)| a.order(&b) == std::cmp::Ordering::Greater)
        };
        (self.bounds.hi < other.bounds.hi && strictly_after(other, self.bounds.hi))
            || (other.bounds.hi < self.bounds.hi && strictly_after(self, other.bounds.hi))
    }
    fn exact_time(&self) -> Option<crate::exact_source::RootTime> {
        let root = self
            .exact
            .clone()
            .or_else(|| {
                let terms = self.sum?;
                let mut root = crate::exact_source::RootTime::point(terms[0])?;
                for term in &terms[1..] {
                    root = root.shifted_fixed(*term, root.bounds()? + I::point(*term))?;
                }
                Some(root)
            })
            .or_else(|| {
                (self.bounds.lo == self.bounds.hi)
                    .then(|| crate::exact_source::RootTime::point(self.bounds.lo))
                    .flatten()
            })?;
        root.refine(self.bounds)?;
        Some(root)
    }
    pub(crate) fn strictly_ordered_with(&self, event: I) -> bool {
        let proof = self
            .exact
            .clone()
            .or_else(|| {
                let terms = self.sum?;
                let mut root = crate::exact_source::RootTime::point(terms[0])?;
                for term in &terms[1..] {
                    root = root.shifted_fixed(*term, root.bounds()? + I::point(*term))?;
                }
                Some(root)
            })
            .or_else(|| {
                (self.bounds.lo == self.bounds.hi)
                    .then(|| crate::exact_source::RootTime::point(self.bounds.lo))
                    .flatten()
            });
        proof
            .filter(|r| r.refine(self.bounds).is_some())
            .is_some_and(|r| {
                crate::exact_source::RootTime::point(event.lo)
                    .is_some_and(|lo| r.order(&lo) == std::cmp::Ordering::Less)
                    || crate::exact_source::RootTime::point(event.hi)
                        .is_some_and(|hi| r.order(&hi) == std::cmp::Ordering::Greater)
            })
    }
    pub(crate) fn coincides(&self, other: &Self) -> bool {
        (self.bounds.lo == self.bounds.hi && self.bounds == other.bounds)
            || (self.sum.is_some() && self.sum == other.sum)
            || self
                .exact
                .as_ref()
                .zip(other.exact.as_ref())
                .is_some_and(|(a, b)| a.order(b) == std::cmp::Ordering::Equal)
    }
    pub(crate) fn coincides_root(&self, root: &crate::exact_source::RootTime) -> bool {
        let exact = self
            .exact
            .clone()
            .or_else(|| {
                let terms = self.sum?;
                let mut root = crate::exact_source::RootTime::point(terms[0])?;
                for term in &terms[1..] {
                    root = root.shifted_fixed(*term, root.bounds()? + I::point(*term))?;
                }
                root.refine(self.bounds)?;
                Some(root)
            })
            .or_else(|| {
                (self.bounds.lo == self.bounds.hi)
                    .then(|| crate::exact_source::RootTime::point(self.bounds.lo))
                    .flatten()
            });
        exact.is_some_and(|exact| {
            exact.refine(self.bounds).is_some() && exact.order(root) == std::cmp::Ordering::Equal
        })
    }
    pub(crate) fn overlaps(&self, other: I) -> bool {
        self.bounds.lo <= other.hi && other.lo <= self.bounds.hi
    }
    pub(crate) fn ordered_with_point(&self, event: I) -> bool {
        if event.lo != event.hi || !event.finite() {
            return false;
        }
        let proof = || {
            let exact = self
                .sum?
                .into_iter()
                .try_fold(crate::exact_source::binary(0.)?, |sum, term| {
                    Some(sum + crate::exact_source::binary(term)?)
                })?;
            if crate::exact_source::enclosure(&exact)? != self.bounds {
                return None;
            }
            Some(match exact.cmp(&crate::exact_source::binary(event.lo)?) {
                std::cmp::Ordering::Less => self.bounds.hi <= event.lo,
                std::cmp::Ordering::Equal => self.bounds == event,
                std::cmp::Ordering::Greater => self.bounds.hi > event.hi,
            })
        };
        proof().unwrap_or(false)
    }
}

#[derive(Clone, Debug, PartialEq)]
struct Edge {
    exact_line: Option<(num_rational::BigRational, num_rational::BigRational)>,
    exact_start: Option<crate::exact_source::RootTime>,
    prior_slope: I,
    start: f64,
    start_bounds: I,
    value: f64,
    value_bounds: I,
    origin: f64,
    origin_bounds: I,
    target: f64,
    target_bounds: I,
    slope: f64,
    slope_bounds: I,
    end: Deadline,
    // A settled symmetric retarget has a fixed duration even when old and
    // new level boxes overlap. It does not claim a single signed slope.
    symmetric_blend: Option<f64>,
}

#[derive(Clone, Debug, PartialEq)]
pub(crate) struct Transition {
    delay: f64,
    rise: f64,
    fall: f64,
    input: f64,
    input_bounds: I,
    input_revision: u64,
    settled: f64,
    settled_bounds: I,
    edge: Option<Edge>,
    pending: VecDeque<(Deadline, f64, I)>,
}

fn invalid(message: &str) -> Error {
    Error::new("event_resolution", message)
}

fn deadline(bounds: I, scale: f64, sum: Option<[f64; 3]>) -> Result<Deadline, Error> {
    // Supported-slice time-resolution gate: representative-at-upper-bound
    // displacement must be <= 1% of the declared delay/edge time. This is not
    // a total waveform error bound and does not authorize uncertain ordering.
    let error = I::point(bounds.hi) - bounds;
    let budget = I::point(scale) * I::point(0.01);
    if !bounds.finite() || !error.finite() || error.magnitude() > budget.lo {
        return Err(invalid(
            "transition time resolution exceeds 1% of declared timing",
        ));
    }
    let sum = sum.map(|mut terms| {
        terms.sort_by(f64::total_cmp);
        terms
    });
    Ok(Deadline {
        continuous_end: false,
        bounds,
        sum,
        exact: None,
    })
}

impl Transition {
    fn exact_at(&self, time: &crate::exact_source::RootTime) -> Option<num_rational::BigRational> {
        use crate::exact_source::{binary, Budget};
        if self.pending.front().is_some_and(|(d, _, _)| {
            d.exact_time()
                .is_none_or(|t| t.order(time) != std::cmp::Ordering::Greater)
        }) {
            return None;
        }
        if let Some(edge) = &self.edge {
            if time.order(&edge.end.exact_time()?) != std::cmp::Ordering::Less {
                return (edge.target_bounds.lo == edge.target_bounds.hi)
                    .then(|| binary(edge.target_bounds.lo))
                    .flatten();
            }
            if time.order(edge.exact_start.as_ref()?) == std::cmp::Ordering::Less {
                return None;
            }
            let (a, b) = edge.exact_line.as_ref()?;
            let mut budget = Budget(0);
            let product = budget.check(b * time.rational())?;
            return budget.check(a + product);
        }
        (self.settled_bounds.lo == self.settled_bounds.hi)
            .then(|| binary(self.settled_bounds.lo))
            .flatten()
    }

    pub(crate) fn exact_affine_on(
        &self,
        bounds: I,
    ) -> Option<(num_rational::BigRational, num_rational::BigRational)> {
        use crate::exact_source::{binary, RootTime};
        if self
            .pending
            .front()
            .is_some_and(|(d, _, _)| d.bounds.lo <= bounds.hi)
        {
            return None;
        }
        if let Some(edge) = &self.edge {
            let lo = RootTime::point(bounds.lo)?;
            let hi = RootTime::point(bounds.hi)?;
            let end = edge.end.exact_time()?;
            if lo.order(&end) != std::cmp::Ordering::Less {
                return (edge.target_bounds.lo == edge.target_bounds.hi)
                    .then(|| Some((binary(edge.target_bounds.lo)?, binary(0.)?)))
                    .flatten();
            }
            if lo.order(edge.exact_start.as_ref()?) == std::cmp::Ordering::Less
                || hi.order(&end) == std::cmp::Ordering::Greater
            {
                return None;
            }
            return edge.exact_line.clone();
        }
        (self.settled_bounds.lo == self.settled_bounds.hi)
            .then(|| Some((binary(self.settled_bounds.lo)?, binary(0.)?)))
            .flatten()
    }
    /// A budget for one future edge is valid only before any active or queued
    /// edge. Return the retained plateau, never a point replacement for it.
    pub(crate) fn idle_level(&self) -> Option<(f64, I, f64)> {
        (self.edge.is_none() && self.pending.is_empty()).then_some((
            self.settled,
            self.settled_bounds,
            self.rise.min(self.fall),
        ))
    }

    pub(crate) fn input_changed_from(&self, old: &Self) -> bool {
        self.input_revision != old.input_revision
    }

    /// Advance a private prediction through queued targets, without changing
    /// the accepted input. Consumers must clone before calling this method.
    pub(crate) fn advance_time(&mut self, time: f64) -> Result<(), Error> {
        self.advance_enclosed(time, self.input, self.input_bounds, false)
    }

    /// Partition forcing at both sides of uncertain activation/end boxes.
    pub(crate) fn forcing_boundary(&self, after: f64) -> Option<f64> {
        self.deadlines(after)
            .iter()
            .flat_map(|d| [d.bounds.lo, d.bounds.hi])
            .filter(|&t| t > after)
            .min_by(f64::total_cmp)
    }

    pub(crate) fn forcing_uncertain(&self, time: f64) -> bool {
        self.deadlines(time)
            .iter()
            .any(|d| d.bounds.lo <= time && time < d.bounds.hi)
    }

    /// A conservative range also covering delayed activations. Used only for
    /// integration over uncertainty boxes, not to localize cross events.
    pub(crate) fn forcing_range(&self, time: I) -> I {
        let mut result = self.bounds_at(time);
        for (deadline, _, target) in &self.pending {
            if deadline.bounds.lo <= time.hi {
                result = result.hull(*target);
            }
        }
        result
    }

    /// Affine forcing before the next deadline's lower bound. The caller
    /// partitions uncertainty boxes separately, so clipping is not smoothed.
    pub(crate) fn forcing_line(&self, time: f64) -> (I, I) {
        match &self.edge {
            Some(edge) if time < edge.end.bounds.lo => (
                edge.value_bounds + edge.slope_bounds * (I::point(time) - edge.start_bounds),
                edge.slope_bounds,
            ),
            Some(edge) => (edge.target_bounds, I::ZERO),
            None => (self.settled_bounds, I::ZERO),
        }
    }
    #[cfg(test)]
    pub(crate) fn new(initial: f64, delay: f64, rise: f64, fall: f64) -> Result<Self, Error> {
        Self::enclosed(initial, I::point(initial), delay, rise, fall)
    }

    pub(crate) fn enclosed(
        initial: f64,
        bounds: I,
        delay: f64,
        rise: f64,
        fall: f64,
    ) -> Result<Self, Error> {
        if ![initial, delay, rise, fall].iter().all(|v| v.is_finite())
            || !bounds.finite()
            || delay < 0.0
            || rise <= 0.0
            || fall <= 0.0
        {
            return Err(Error::new(
                "invalid_ir",
                "invalid transition initial value or timing",
            ));
        }
        Ok(Self {
            delay,
            rise,
            fall,
            input: initial,
            input_bounds: bounds,
            input_revision: 0,
            settled: initial,
            settled_bounds: bounds,
            edge: None,
            pending: VecDeque::new(),
        })
    }

    pub(crate) fn value_bounds(&self, time: f64) -> Result<I, Error> {
        let held = self.bounds_at(I::point(time));
        if let Some((deadline, target, bounds)) = self.pending.front().cloned() {
            if deadline.bounds.lo < time && time < deadline.bounds.hi {
                // A sample may fall after the exact activation but before its
                // representative upper time. Enclose both possibilities without
                // installing this preview in accepted history.
                let mut activated = self.clone();
                activated.pending.pop_front();
                activated.target(deadline, target, bounds)?;
                let changed = activated.bounds_at(I::point(time));
                return Ok(I {
                    lo: held.lo.min(changed.lo),
                    hi: held.hi.max(changed.hi),
                });
            }
        }
        Ok(held)
    }

    /// Value observation may cover an activation enclosure. Keep both old
    /// and activated ramps; this supplies no derivative/root certificate.
    pub(crate) fn observation_range(&self, times: I) -> Result<I, Error> {
        if !times.finite()
            || times.lo > times.hi
            || self
                .edge
                .as_ref()
                .is_some_and(|e| times.lo < e.start_bounds.lo)
        {
            return Err(invalid(&format!(
                "transition observation precedes retained history: query={times:?}, edge={:?}",
                self.edge.as_ref().map(|e| e.start_bounds)
            )));
        }
        let mut candidate = self.clone();
        let mut value = candidate.bounds_at(times);
        while let Some((deadline, target, bounds)) = candidate
            .pending
            .front()
            .cloned()
            .filter(|(d, _, _)| d.bounds.lo <= times.hi)
        {
            candidate.pending.pop_front();
            candidate.target(deadline, target, bounds)?;
            value = value.hull(candidate.bounds_at(times));
        }
        Ok(value)
    }

    pub(crate) fn continuous_range(&self, times: I) -> Result<(I, I), Error> {
        let value = self.observation_range(times)?;
        let slope = |history: &Self| {
            if let Some(edge) = &history.edge {
                let mut slope = edge.slope_bounds;
                if times.lo < edge.start_bounds.hi {
                    slope = slope.hull(edge.prior_slope);
                }
                if times.hi >= edge.end.bounds.lo {
                    slope = slope.hull(I::ZERO);
                }
                slope
            } else {
                I::ZERO
            }
        };
        let mut candidate = self.clone();
        let mut derivative = slope(&candidate);
        while let Some((deadline, target, bounds)) = candidate
            .pending
            .front()
            .cloned()
            .filter(|(d, _, _)| d.bounds.lo <= times.hi)
        {
            candidate.pending.pop_front();
            candidate.target(deadline, target, bounds)?;
            derivative = derivative.hull(slope(&candidate));
        }
        Ok((value, derivative))
    }

    fn bounds_at(&self, time: I) -> I {
        match &self.edge {
            Some(edge) if time.lo < edge.end.bounds.hi => {
                if let Some(duration) = edge.symmetric_blend {
                    let elapsed = (time - edge.start_bounds) / I::point(duration);
                    let fraction = I {
                        lo: elapsed.lo.clamp(0., 1.),
                        hi: elapsed.hi.clamp(0., 1.),
                    };
                    let blend =
                        edge.value_bounds + (edge.target_bounds - edge.value_bounds) * fraction;
                    let levels = edge.value_bounds.hull(edge.target_bounds);
                    return I {
                        lo: blend.lo.max(levels.lo),
                        hi: blend.hi.min(levels.hi),
                    };
                }
                let bounds = edge.value_bounds + edge.slope_bounds * (time - edge.start_bounds);
                // Interval extension of the exact monotone clipped ramp. The
                // uncertain delayed start and uncertain target remain in it.
                if edge.slope_bounds.lo > 0.0 {
                    I {
                        lo: bounds
                            .lo
                            .min(edge.target_bounds.lo)
                            .max(edge.value_bounds.lo),
                        hi: bounds
                            .hi
                            .min(edge.target_bounds.hi)
                            .max(edge.value_bounds.hi),
                    }
                } else {
                    I {
                        lo: bounds
                            .lo
                            .max(edge.target_bounds.lo)
                            .min(edge.value_bounds.lo),
                        hi: bounds
                            .hi
                            .max(edge.target_bounds.hi)
                            .min(edge.value_bounds.hi),
                    }
                }
            }
            Some(edge) => edge.target_bounds,
            None => self.settled_bounds,
        }
    }

    pub(crate) fn value(&self, time: f64) -> Result<f64, Error> {
        let value = match &self.edge {
            Some(edge) if time < edge.end.bounds.hi => {
                let raw = edge.value + edge.slope * (time - edge.start);
                if !raw.is_finite() {
                    return Err(invalid("nonfinite transition value"));
                }
                // Scheduling uses an enclosing upper time, while the waveform
                // remains clipped and monotone at every observation in that box.
                raw.clamp(edge.value.min(edge.target), edge.value.max(edge.target))
            }
            Some(edge) => edge.target,
            None => self.settled,
        };
        if !value.is_finite() {
            return Err(invalid("nonfinite transition value"));
        }
        Ok(value)
    }

    pub(crate) fn deadlines(&self, after: f64) -> Vec<Deadline> {
        self.pending
            .front()
            .map(|(deadline, _, _)| deadline.clone())
            .into_iter()
            .chain(self.edge.as_ref().map(|e| e.end.clone()))
            .filter(|deadline| deadline.bounds.hi > after)
            .collect()
    }

    pub(crate) fn next_breakpoint(&self, after: f64) -> Option<f64> {
        self.deadlines(after)
            .iter()
            .map(|d| d.bounds.hi)
            .min_by(f64::total_cmp)
    }

    fn target(&mut self, moment: Deadline, target: f64, target_bounds: I) -> Result<(), Error> {
        let exact_start = moment.exact_time();
        let exact_value = exact_start.as_ref().and_then(|t| self.exact_at(t));
        let prior_slope = self.edge.as_ref().map_or(I::ZERO, |e| e.slope_bounds);
        let time = moment.bounds.hi;
        let value = self.value(time)?;
        let value_bounds = self.bounds_at(moment.bounds);
        let difference = target_bounds - value_bounds;
        let symmetric_blend = difference.sign().is_none()
            && self.rise == self.fall
            && self
                .edge
                .as_ref()
                .is_none_or(|edge| edge.end.bounds.hi <= moment.bounds.lo);
        let direction = difference
            .sign()
            .or(symmetric_blend.then_some(0))
            .ok_or_else(|| {
                invalid("cannot certify transition target relative to current output")
            })?;
        if direction == 0 && !symmetric_blend {
            self.settled = target;
            self.settled_bounds = target_bounds;
            self.edge = None;
            return Ok(());
        }
        let active = self.edge.as_ref().filter(|edge| time < edge.end.bounds.hi);
        let (origin, origin_bounds) = match active {
            Some(edge) => {
                let old_direction = edge
                    .slope_bounds
                    .sign()
                    .ok_or_else(|| invalid("cannot certify transition edge direction"))?;
                if direction == old_direction {
                    (edge.origin, edge.origin_bounds)
                } else {
                    (edge.target, edge.target_bounds)
                }
            }
            None => (value, value_bounds),
        };
        let duration = if direction > 0 { self.rise } else { self.fall };
        let slope = (target - origin) / duration;
        let slope_bounds = (target_bounds - origin_bounds) / I::point(duration);
        if (!symmetric_blend
            && (slope_bounds.sign() != Some(direction)
                || slope == 0.0
                || (slope > 0.0) != (direction > 0)))
            || !slope_bounds.finite()
            || !slope.is_finite()
        {
            return Err(invalid("cannot certify transition slope"));
        }
        let (end_bounds, sum) = if active.is_none() {
            let sum = moment.sum.and_then(|mut terms| {
                // Source time + fixed delay occupies at most two terms.
                let zero = terms.iter().position(|x| *x == 0.0)?;
                terms[zero] = duration;
                Some(terms)
            });
            (moment.bounds + I::point(duration), sum)
        } else {
            let remaining = difference / slope_bounds;
            if !remaining.finite() || remaining.lo <= 0.0 {
                return Err(invalid("cannot certify transition remaining duration"));
            }
            (moment.bounds + remaining, None)
        };
        let mut end = deadline(end_bounds, duration, sum)?;
        end.continuous_end = true;
        if active.is_none() {
            end.exact = moment
                .exact
                .as_ref()
                .and_then(|root| root.shifted_fixed(duration, end_bounds));
        }
        if end.bounds.lo <= time {
            return Err(invalid("transition edge cannot advance representable time"));
        }
        let exact_line = (|| {
            use crate::exact_source::{binary, Budget};
            if target_bounds.lo != target_bounds.hi || origin_bounds.lo != origin_bounds.hi {
                return None;
            }
            let mut budget = Budget(0);
            let delta = budget.check(binary(target_bounds.lo)? - binary(origin_bounds.lo)?)?;
            let slope = budget.check(delta / binary(duration)?)?;
            let product = budget.check(&slope * exact_start.as_ref()?.rational())?;
            Some((budget.check(exact_value? - product)?, slope))
        })();
        if let Some((a, b)) = &exact_line {
            let proof = (|| {
                let value = crate::exact_source::Budget(0)
                    .check(a - crate::exact_source::binary(target_bounds.lo)?)?;
                crate::exact_source::RootTime::affine(value, b.clone(), end.bounds)
            })();
            if end
                .exact
                .as_ref()
                .zip(proof.as_ref())
                .is_some_and(|(a, b)| a.order(b) != std::cmp::Ordering::Equal)
            {
                return Err(invalid(
                    "exact transition end contradicts timing certificate",
                ));
            }
            end.exact = end.exact.or(proof);
        }
        self.edge = Some(Edge {
            exact_line,
            exact_start,
            prior_slope,
            start: time,
            start_bounds: moment.bounds,
            value,
            value_bounds,
            origin,
            origin_bounds,
            target,
            target_bounds,
            slope,
            slope_bounds,
            end,
            symmetric_blend: symmetric_blend.then_some(duration),
        });
        Ok(())
    }

    #[cfg(test)]
    pub(crate) fn advance(&mut self, time: f64, input: f64) -> Result<(), Error> {
        self.advance_enclosed(time, input, I::point(input), false)
    }

    pub(crate) fn advance_enclosed(
        &mut self,
        time: f64,
        input: f64,
        bounds: I,
        may_change: bool,
    ) -> Result<(), Error> {
        self.advance_at(time, I::point(time), input, bounds, may_change)
    }

    /// The event's physical-time enclosure is distinct from its execution
    /// representative. Retain it in every downstream activation and edge.
    pub(crate) fn advance_at(
        &mut self,
        time: f64,
        time_bounds: I,
        input: f64,
        bounds: I,
        may_change: bool,
    ) -> Result<(), Error> {
        self.advance_at_with_exact(time, time_bounds, input, bounds, may_change, None)
    }

    pub(crate) fn advance_at_with_exact(
        &mut self,
        time: f64,
        time_bounds: I,
        input: f64,
        bounds: I,
        may_change: bool,
        exact_root: Option<&crate::exact_source::RootTime>,
    ) -> Result<(), Error> {
        if exact_root.is_some_and(|root| root.refine(time_bounds).is_none()) {
            return Err(invalid("exact transition root is outside event enclosure"));
        }
        if !time_bounds.finite() || time_bounds.lo > time_bounds.hi || time_bounds.hi > time {
            return Err(invalid("invalid transition event-time enclosure"));
        }
        // Called only on a cloned candidate runtime. A failed pop/edge rebuild
        // discards the whole candidate, including all prior queue mutations.
        while self
            .pending
            .front()
            .is_some_and(|(deadline, _, _)| deadline.bounds.hi <= time)
        {
            let (deadline, target, target_bounds) = self.pending.pop_front().unwrap();
            self.target(deadline, target, target_bounds)?;
        }
        if self
            .edge
            .as_ref()
            .is_some_and(|edge| edge.end.bounds.hi <= time)
        {
            let edge = self.edge.take().unwrap();
            self.settled = edge.target;
            self.settled_bounds = edge.target_bounds;
        }
        if !input.is_finite() || !bounds.finite() {
            return Err(invalid("nonfinite transition target"));
        }
        if input == self.input && bounds != self.input_bounds && !may_change {
            return Err(invalid("cannot certify unchanged transition input history"));
        }
        let uncertain_write = may_change && (bounds.lo != bounds.hi || bounds != self.input_bounds);
        if input != self.input || uncertain_write {
            self.input_revision = self
                .input_revision
                .checked_add(1)
                .ok_or_else(|| invalid("transition input revision budget exceeded"))?;
            self.input = input;
            self.input_bounds = bounds;
            if self.delay == 0.0 {
                self.target(
                    Deadline {
                        continuous_end: false,
                        bounds: time_bounds,
                        exact: exact_root.cloned(),
                        sum: (time_bounds.lo == time_bounds.hi).then_some([
                            time_bounds.lo,
                            0.0,
                            0.0,
                        ]),
                    },
                    input,
                    bounds,
                )?;
            } else {
                let mut next = deadline(
                    time_bounds + I::point(self.delay),
                    self.delay,
                    (time_bounds.lo == time_bounds.hi).then_some([time_bounds.lo, self.delay, 0.0]),
                )?;
                next.exact =
                    exact_root.and_then(|root| root.shifted_fixed(self.delay, next.bounds));
                if next.bounds.lo <= time {
                    return Err(invalid(
                        "transition delay cannot advance representable time",
                    ));
                }
                if self
                    .pending
                    .back()
                    .is_some_and(|(old, _, _)| old.bounds.hi >= next.bounds.lo)
                {
                    return Err(invalid(
                        "cannot certify ordering of distinct transition target deadlines",
                    ));
                }
                self.pending.push_back((next, input, bounds));
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn equal_enclosures_do_not_prove_a_rewritten_target_unchanged() {
        let bounds = I { lo: 0.99, hi: 1.01 };
        let accepted = Transition::enclosed(1.0, bounds, 0.0, 1.0, 2.0).unwrap();
        let mut held = accepted.clone();
        held.advance_enclosed(0.5, 1.0, bounds, false).unwrap();
        let mut written = accepted.clone();
        assert!(written.advance_enclosed(0.5, 1.0, bounds, true).is_err());
        assert_eq!(accepted.value_bounds(0.5).unwrap(), bounds);
    }
    #[test]
    fn settled_symmetric_rewrite_encloses_independent_targets_in_both_directions() {
        let bounds = I { lo: 0.99, hi: 1.01 };
        let accepted = Transition::enclosed(1., bounds, 0., 0.25, 0.25).unwrap();
        let mut next = accepted.clone();
        next.advance_enclosed(0.5, 1., bounds, true).unwrap();
        assert!(next.input_changed_from(&accepted));
        for t in [0.5, 0.5625, 0.625, 0.75, 1.] {
            let got = next.value_bounds(t).unwrap();
            let fraction = ((t - 0.5) / 0.25_f64).clamp(0., 1.);
            for old in [0.99, 1., 1.01] {
                for target in [0.99, 1., 1.01] {
                    let expected = old + (target - old) * fraction;
                    assert!(
                        got.lo <= expected && expected <= got.hi,
                        "{t}: {got:?} excludes {expected}"
                    );
                }
            }
            assert_eq!(next.value(t).unwrap(), 1.);
        }
        // A new uncertain write during an active edge still lacks a proof.
        let mut interrupted = next.clone();
        assert!(interrupted
            .advance_enclosed(0.625, 1., bounds, true)
            .is_err());
        assert_eq!(accepted.value_bounds(0.625).unwrap(), bounds);
    }

    fn near(a: f64, b: f64) {
        assert!((a - b).abs() < 1e-12, "{a} != {b}");
    }
    #[test]
    fn interrupted_edges_preserve_origin_and_reflect() {
        for sign in [1.0, -1.0] {
            let mut edge = Transition::new(
                0.0,
                0.0,
                if sign > 0.0 { 10.0 } else { 20.0 },
                if sign > 0.0 { 20.0 } else { 10.0 },
            )
            .unwrap();
            edge.advance(2.0, sign).unwrap();
            edge.advance(6.0, 0.0).unwrap();
            near(edge.value(6.0).unwrap(), sign * 0.4);
            near(edge.value(10.0).unwrap(), sign * 0.2);
            near(edge.value(14.0).unwrap(), 0.0);
        }
        let mut edge = Transition::new(0.0, 0.0, 10.0, 20.0).unwrap();
        edge.advance(2.0, 1.0).unwrap();
        edge.advance(6.0, 2.0).unwrap();
        near(edge.value(10.0).unwrap(), 1.2);
        near(edge.value(14.0).unwrap(), 2.0);
    }
    #[test]
    fn queue_repeat_and_exact_current_target() {
        let mut edge = Transition::new(0.0, 10.0, 2.0, 2.0).unwrap();
        edge.advance(2.0, 1.0).unwrap();
        edge.advance(3.0, 0.0).unwrap();
        edge.advance(12.0, 0.0).unwrap();
        near(edge.value(12.5).unwrap(), 0.25);
        edge.advance(13.0, 0.0).unwrap();
        near(edge.value(13.5).unwrap(), 0.25);
        edge.advance(14.0, 0.0).unwrap();
        near(edge.value(14.0).unwrap(), 0.0);
        let mut edge = Transition::new(0.0, 0.0, 10.0, 20.0).unwrap();
        edge.advance(2.0, 1.0).unwrap();
        edge.advance(6.0, 1.0).unwrap();
        near(edge.value(10.0).unwrap(), 0.8);
        let mut exact = Transition::new(0.0, 0.0, 8.0, 8.0).unwrap();
        exact.advance(2.0, 1.0).unwrap();
        exact.advance(6.0, 0.5).unwrap();
        near(exact.value(100.0).unwrap(), 0.5);
    }
}

#[cfg(test)]
mod exact_transition_line_tests {
    use super::*;
    use crate::exact_source::{binary, RootTime};
    use num_rational::BigRational as R;

    #[test]
    fn nonbinary_start_proves_the_physical_line_only_on_one_retained_piece() {
        let root = RootTime::affine(
            R::from_integer((-1).into()),
            R::from_integer(3.into()),
            I { lo: 0.3, hi: 0.4 },
        )
        .unwrap();
        let window = root.bounds().unwrap();
        let mut history = Transition::new(0., 0., 0.5, 0.5).unwrap();
        history
            .advance_at_with_exact(window.hi, window, 1., I::ONE, true, Some(&root))
            .unwrap();
        let (a, b) = history.exact_affine_on(I { lo: 0.5, hi: 0.75 }).unwrap();
        assert_eq!(a, R::new((-2).into(), 3.into()));
        assert_eq!(b, binary(2.).unwrap());
        assert!(history.exact_affine_on(I { lo: 0.25, hi: 0.5 }).is_none());
        assert!(history.exact_affine_on(I { lo: 0.75, hi: 1. }).is_none());
        let mut unknown = Transition::enclosed(
            0.,
            I {
                lo: -1e-6,
                hi: 1e-6,
            },
            0.,
            0.5,
            0.5,
        )
        .unwrap();
        unknown
            .advance_at_with_exact(window.hi, window, 1., I::ONE, true, Some(&root))
            .unwrap();
        assert!(unknown.exact_affine_on(I { lo: 0.5, hi: 0.75 }).is_none());
    }

    #[test]
    fn exact_deadline_orders_closed_boxes_without_ordering_unknown_real_times() {
        let root = RootTime::affine(
            R::from_integer((-1).into()),
            R::from_integer(3.into()),
            I { lo: 0.3, hi: 0.4 },
        )
        .unwrap();
        let bounds = root.bounds().unwrap();
        let mut d = deadline(bounds, 1., None).unwrap();
        d.exact = Some(root);
        assert!(d.strictly_ordered_with(I {
            lo: bounds.hi,
            hi: 0.5
        }));
        assert!(d.strictly_ordered_with(I {
            lo: 0.1,
            hi: bounds.lo
        }));
        assert!(!d.strictly_ordered_with(bounds));
        d.exact = None;
        assert!(!d.strictly_ordered_with(I {
            lo: bounds.hi,
            hi: 0.5
        }));
        d.exact = RootTime::point(0.75);
        assert!(!d.strictly_ordered_with(I {
            lo: bounds.hi,
            hi: 0.5
        }));
    }

    #[test]
    fn ordered_real_deadlines_do_not_authorize_a_representative_that_skips_the_next_one() {
        let mut a = deadline(I { lo: 0.3, hi: 0.4 }, 100., None).unwrap();
        a.exact = RootTime::point(0.35);
        let mut b = deadline(I { lo: 0.35, hi: 0.5 }, 100., None).unwrap();
        b.exact = RootTime::point(0.45);
        assert!(a.serial_representatives(&b));
        assert!(b.serial_representatives(&a));
        b.exact = RootTime::point(0.39);
        assert!(!a.serial_representatives(&b));
        b.exact = None;
        assert!(!a.serial_representatives(&b));
        b.exact = RootTime::point(0.45);
        b.bounds.hi = 0.4;
        assert!(!a.serial_representatives(&b));
    }
}

#[cfg(test)]
mod exact_deadline_tests {
    use super::*;
    use crate::exact_source::RootTime;
    use num_rational::BigRational as R;
    use num_traits::One;

    fn root() -> RootTime {
        RootTime::affine(-R::one(), R::from_integer(3.into()), I { lo: 0.3, hi: 0.4 }).unwrap()
    }

    #[test]
    fn fresh_exact_proof_changes_no_time_or_waveform_bits() {
        let root = root();
        let window = root.bounds().unwrap();
        for delay in [0., 0.125] {
            let mut old = Transition::new(0., delay, 0.125, 0.125).unwrap();
            let mut new = old.clone();
            old.advance_at(window.hi, window, 1., I::ONE, true).unwrap();
            new.advance_at_with_exact(window.hi, window, 1., I::ONE, true, Some(&root))
                .unwrap();
            assert_eq!(old.deadlines(0.)[0].bounds, new.deadlines(0.)[0].bounds);
            assert!(new.deadlines(0.)[0].exact.is_some());
            assert!(!old.deadlines(0.)[0].coincides(&new.deadlines(0.)[0]));
            for t in [window.hi, 0.4, 0.5, 0.6] {
                assert_eq!(
                    old.value(t).unwrap().to_bits(),
                    new.value(t).unwrap().to_bits()
                );
                assert_eq!(old.value_bounds(t).unwrap(), new.value_bounds(t).unwrap());
            }
            if delay > 0. {
                let time = new.next_breakpoint(0.).unwrap();
                old.advance_at(time, I::point(time), 1., I::ONE, false)
                    .unwrap();
                new.advance_at(time, I::point(time), 1., I::ONE, false)
                    .unwrap();
                assert!(new.edge.as_ref().unwrap().end.exact.is_some());
                assert_eq!(
                    old.edge.as_ref().unwrap().end.bounds,
                    new.edge.as_ref().unwrap().end.bounds
                );
            }
        }
    }

    #[test]
    fn shared_anchor_and_interrupted_line_need_distinct_end_certificates() {
        let root = root();
        let window = root.bounds().unwrap();
        let mut a = Transition::new(0., 0., 0.75, 0.75).unwrap();
        let mut b = a.clone();
        a.advance_at_with_exact(window.hi, window, 1., I::ONE, true, Some(&root))
            .unwrap();
        b.advance_at_with_exact(window.hi, window, 2., I::point(2.), true, Some(&root))
            .unwrap();
        assert!(a
            .edge
            .as_ref()
            .unwrap()
            .end
            .coincides(&b.edge.as_ref().unwrap().end));
        let next = RootTime::from_clock(
            crate::exact_time::Clock {
                start: 0.5,
                period: 0.,
                index: 0,
            },
            I::point(0.5),
        )
        .unwrap();
        a.advance_at_with_exact(0.5, I::point(0.5), 2., I::point(2.), true, Some(&next))
            .unwrap();
        let end = &a.edge.as_ref().unwrap().end;
        let expected = RootTime::affine(
            -R::from_integer(7.into()),
            R::from_integer(6.into()),
            end.bounds,
        )
        .unwrap();
        assert!(end.coincides_root(&expected));
        assert!(a.edge.as_ref().unwrap().end.sum.is_none());
        let mut unknown = Transition::new(0., 0., 0.75, 0.75).unwrap();
        unknown
            .advance_at(window.hi, window, 1., I::ONE, true)
            .unwrap();
        unknown
            .advance_at_with_exact(0.5, I::point(0.5), 2., I::point(2.), true, Some(&next))
            .unwrap();
        assert!(unknown.edge.as_ref().unwrap().end.exact.is_none());
        assert!(unknown.edge.as_ref().unwrap().end.sum.is_none());
    }

    #[test]
    fn split_fixed_arithmetic_is_exact_and_stays_bounded_by_discovery() {
        let root = root();
        let wide = I { lo: 0., hi: 1. };
        let split = root
            .shifted_fixed(0.1, wide)
            .unwrap()
            .shifted_fixed(0.2, wide)
            .unwrap();
        let rounded = root.shifted_fixed(0.1 + 0.2, wide).unwrap();
        assert_ne!(split.order(&rounded), std::cmp::Ordering::Equal);
        assert!(root.shifted_fixed(0.1, I::point(0.5)).is_none());
        assert!(root.shifted_fixed(f64::INFINITY, wide).is_none());
    }
}

#[cfg(test)]
mod exact_deadline_review_tests {
    use super::*;
    use crate::exact_source::RootTime;

    #[test]
    fn mismatched_or_malformed_exact_window_rejects_before_queue_mutation() {
        let root = RootTime::from_clock(
            crate::exact_time::Clock {
                start: 0.5,
                period: 0.,
                index: 0,
            },
            I::point(0.5),
        )
        .unwrap();
        let mut retained = Transition::new(0., 0.125, 0.25, 0.25).unwrap();
        retained
            .advance_at(0.25, I::point(0.25), 1., I::ONE, true)
            .unwrap();
        assert!(!retained.pending.is_empty());
        for window in [
            I::point(0.75),
            I { lo: 0.6, hi: 0.4 },
            I {
                lo: f64::NAN,
                hi: 0.5,
            },
            I {
                lo: 0.,
                hi: f64::INFINITY,
            },
        ] {
            let mut candidate = retained.clone();
            let error = candidate
                .advance_at_with_exact(1., window, 2., I::point(2.), true, Some(&root))
                .unwrap_err();
            assert_eq!(error.kind, "event_resolution");
            assert_eq!(
                error.message,
                "exact transition root is outside event enclosure"
            );
            assert_eq!(candidate, retained);
        }
        let mut valid = retained.clone();
        valid
            .advance_at_with_exact(0.5, I::point(0.5), 2., I::point(2.), true, Some(&root))
            .unwrap();
        assert_ne!(valid, retained);
    }
}
