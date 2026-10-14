//! Fixed-delay transition history. Observation queries never mutate an edge.
use crate::interval::Interval as I;
use crate::ir::Error;
use std::collections::VecDeque;

#[derive(Clone, Debug, PartialEq)]
pub(crate) struct Deadline {
    pub(crate) bounds: I,
    // Exact symbolic sum when available; equal enclosures alone do not prove
    // coincident real deadlines. Interrupted-edge endpoints have no sum key.
    sum: Option<[f64; 3]>,
    exact: Option<crate::exact_source::RootTime>,
}
impl Deadline {
    pub(crate) fn coincides(&self, other: &Self) -> bool {
        (self.bounds.lo == self.bounds.hi && self.bounds == other.bounds)
            || (self.sum.is_some() && self.sum == other.sum)
            || self
                .exact
                .as_ref()
                .zip(other.exact.as_ref())
                .is_some_and(|(a, b)| a.order(b) == std::cmp::Ordering::Equal)
    }
    pub(crate) fn overlaps(&self, other: I) -> bool {
        self.bounds.lo <= other.hi && other.lo <= self.bounds.hi
    }
}

#[derive(Clone, Debug, PartialEq)]
struct Edge {
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
}

#[derive(Clone, Debug, PartialEq)]
pub(crate) struct Transition {
    delay: f64,
    rise: f64,
    fall: f64,
    input: f64,
    input_bounds: I,
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
        bounds,
        sum,
        exact: None,
    })
}

impl Transition {
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
        self.input != old.input
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

    pub(crate) fn value_range(&self, times: I) -> Result<I, Error> {
        if !times.finite()
            || times.lo > times.hi
            || self
                .edge
                .as_ref()
                .is_some_and(|edge| times.lo < edge.start_bounds.hi)
            || self
                .pending
                .front()
                .is_some_and(|(deadline, _, _)| deadline.bounds.lo <= times.hi)
        {
            return Err(invalid(
                "cannot certify transition observation across an activation",
            ));
        }
        // The controller rejects overlapping operator deadlines before this
        // query; the complete window belongs to this retained ramp/plateau.
        Ok(self.bounds_at(times))
    }

    fn bounds_at(&self, time: I) -> I {
        match &self.edge {
            Some(edge) if time.lo < edge.end.bounds.hi => {
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
        let time = moment.bounds.hi;
        let value = self.value(time)?;
        let value_bounds = self.bounds_at(moment.bounds);
        let difference = target_bounds - value_bounds;
        let direction = difference.sign().ok_or_else(|| {
            invalid("cannot certify transition target relative to current output")
        })?;
        if direction == 0 {
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
        if slope_bounds.sign() != Some(direction)
            || !slope_bounds.finite()
            || !slope.is_finite()
            || slope == 0.0
            || (slope > 0.0) != (direction > 0)
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
        if active.is_none() {
            end.exact = moment
                .exact
                .as_ref()
                .and_then(|root| root.shifted_fixed(duration, end_bounds));
        }
        if end.bounds.lo <= time {
            return Err(invalid("transition edge cannot advance representable time"));
        }
        self.edge = Some(Edge {
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
        if input == self.input
            && (bounds != self.input_bounds || (may_change && bounds.lo != bounds.hi))
        {
            return Err(invalid("cannot certify unchanged transition input history"));
        }
        if input != self.input {
            self.input = input;
            self.input_bounds = bounds;
            if self.delay == 0.0 {
                self.target(
                    Deadline {
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
        let accepted = Transition::enclosed(1.0, bounds, 0.0, 1.0, 1.0).unwrap();
        let mut held = accepted.clone();
        held.advance_enclosed(0.5, 1.0, bounds, false).unwrap();
        let mut written = accepted.clone();
        assert!(written.advance_enclosed(0.5, 1.0, bounds, true).is_err());
        assert_eq!(accepted.value_bounds(0.5).unwrap(), bounds);
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
    fn fresh_shared_anchor_coincides_but_interrupted_endpoint_does_not_invent_key() {
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
        assert!(a.edge.as_ref().unwrap().end.exact.is_none());
        assert!(a.edge.as_ref().unwrap().end.sum.is_none());
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
