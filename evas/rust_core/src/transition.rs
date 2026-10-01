//! Fixed-delay transition history. Observation queries never mutate an edge.
use crate::interval::Interval as I;
use crate::ir::Error;
use std::collections::VecDeque;

#[derive(Clone, Copy, Debug)]
pub(crate) struct Deadline {
    pub(crate) bounds: I,
    // Exact symbolic sum when available; equal enclosures alone do not prove
    // coincident real deadlines. Interrupted-edge endpoints have no sum key.
    sum: Option<[f64; 3]>,
}
impl Deadline {
    pub(crate) fn coincides(&self, other: &Self) -> bool {
        (self.bounds.lo == self.bounds.hi && self.bounds == other.bounds)
            || (self.sum.is_some() && self.sum == other.sum)
    }
    pub(crate) fn overlaps(&self, other: I) -> bool {
        self.bounds.lo <= other.hi && other.lo <= self.bounds.hi
    }
}

#[derive(Clone, Debug)]
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

#[derive(Clone, Debug)]
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
    Ok(Deadline { bounds, sum })
}

impl Transition {
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
        if let Some(&(deadline, target, bounds)) = self.pending.front() {
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
            .map(|(deadline, _, _)| *deadline)
            .into_iter()
            .chain(self.edge.as_ref().map(|e| e.end))
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
        let end = deadline(end_bounds, duration, sum)?;
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
                        bounds: I::point(time),
                        sum: Some([time, 0.0, 0.0]),
                    },
                    input,
                    bounds,
                )?;
            } else {
                let next = deadline(
                    I::point(time) + I::point(self.delay),
                    self.delay,
                    Some([time, self.delay, 0.0]),
                )?;
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
