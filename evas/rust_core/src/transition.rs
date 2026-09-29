//! Fixed-delay transition history. Observation queries never mutate an edge.
use crate::interval::Interval as I;
use crate::ir::Error;
use std::collections::VecDeque;

#[derive(Clone, Copy, Debug)]
pub(crate) struct Deadline {
    pub(crate) bounds: I,
    // Exact symbolic sum when available; equal enclosures alone do not prove
    // coincident real deadlines. Interrupted-edge endpoints have no sum key.
    sum: Option<(f64, f64)>,
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
    value: f64,
    value_bounds: I,
    origin: f64,
    origin_bounds: I,
    target: f64,
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
    settled: f64,
    edge: Option<Edge>,
    pending: VecDeque<(Deadline, f64)>,
}

fn invalid(message: &str) -> Error {
    Error::new("event_resolution", message)
}

fn deadline(bounds: I, scale: f64, sum: Option<(f64, f64)>) -> Result<Deadline, Error> {
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
    Ok(Deadline { bounds, sum })
}

impl Transition {
    pub(crate) fn new(initial: f64, delay: f64, rise: f64, fall: f64) -> Result<Self, Error> {
        if ![initial, delay, rise, fall].iter().all(|v| v.is_finite())
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
            settled: initial,
            edge: None,
            pending: VecDeque::new(),
        })
    }

    fn value_bounds(&self, time: f64) -> I {
        match &self.edge {
            Some(edge) if time < edge.end.bounds.hi => {
                let bounds =
                    edge.value_bounds + edge.slope_bounds * (I::point(time) - I::point(edge.start));
                let (low, high) = if edge.target > edge.value {
                    (edge.value_bounds.lo, edge.target)
                } else {
                    (edge.target, edge.value_bounds.hi)
                };
                I {
                    lo: bounds.lo.max(low).min(high),
                    hi: bounds.hi.max(low).min(high),
                }
            }
            Some(edge) => I::point(edge.target),
            None => I::point(self.settled),
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
            .map(|(deadline, _)| *deadline)
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

    fn target(&mut self, time: f64, target: f64) -> Result<(), Error> {
        let value = self.value(time)?;
        let value_bounds = self.value_bounds(time);
        let difference = I::point(target) - value_bounds;
        let direction = difference.sign().ok_or_else(|| {
            invalid("cannot certify transition target relative to current output")
        })?;
        if direction == 0 {
            self.settled = target;
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
                    (edge.target, I::point(edge.target))
                }
            }
            None => (value, value_bounds),
        };
        let duration = if direction > 0 { self.rise } else { self.fall };
        let slope = (target - origin) / duration;
        let slope_bounds = (I::point(target) - origin_bounds) / I::point(duration);
        if slope_bounds.sign() != Some(direction)
            || !slope_bounds.finite()
            || !slope.is_finite()
            || slope == 0.0
        {
            return Err(invalid("cannot certify transition slope"));
        }
        let (end_bounds, sum) = if active.is_none() {
            (I::point(time) + I::point(duration), Some((time, duration)))
        } else {
            let remaining = difference / slope_bounds;
            if !remaining.finite() || remaining.lo <= 0.0 {
                return Err(invalid("cannot certify transition remaining duration"));
            }
            (I::point(time) + remaining, None)
        };
        let end = deadline(end_bounds, duration, sum)?;
        if end.bounds.lo <= time {
            return Err(invalid("transition edge cannot advance representable time"));
        }
        self.edge = Some(Edge {
            start: time,
            value,
            value_bounds,
            origin,
            origin_bounds,
            target,
            slope,
            slope_bounds,
            end,
        });
        Ok(())
    }

    pub(crate) fn advance(&mut self, time: f64, input: f64) -> Result<(), Error> {
        // Called only on a cloned candidate runtime. A failed pop/edge rebuild
        // discards the whole candidate, including all prior queue mutations.
        while self
            .pending
            .front()
            .is_some_and(|(deadline, _)| deadline.bounds.hi <= time)
        {
            let (deadline, target) = self.pending.pop_front().unwrap();
            self.target(deadline.bounds.hi, target)?;
        }
        if self
            .edge
            .as_ref()
            .is_some_and(|edge| edge.end.bounds.hi <= time)
        {
            self.settled = self.edge.take().unwrap().target;
        }
        if !input.is_finite() {
            return Err(invalid("nonfinite transition target"));
        }
        if input != self.input {
            self.input = input;
            if self.delay == 0.0 {
                self.target(time, input)?;
            } else {
                let next = deadline(
                    I::point(time) + I::point(self.delay),
                    self.delay,
                    Some((time, self.delay)),
                )?;
                if next.bounds.lo <= time {
                    return Err(invalid(
                        "transition delay cannot advance representable time",
                    ));
                }
                if self
                    .pending
                    .back()
                    .is_some_and(|(old, _)| old.bounds.hi >= next.bounds.lo)
                {
                    return Err(invalid(
                        "cannot certify ordering of distinct transition target deadlines",
                    ));
                }
                self.pending.push_back((next, input));
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
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
