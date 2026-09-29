//! Fixed-delay transition history. Observation queries never mutate an edge.
use crate::ir::Error;
use std::collections::VecDeque;

#[derive(Clone, Debug)]
struct Edge {
    start: f64,
    value: f64,
    origin: f64,
    target: f64,
    slope: f64,
    end: f64,
}

#[derive(Clone, Debug)]
pub(crate) struct Transition {
    delay: f64,
    rise: f64,
    fall: f64,
    input: f64,
    settled: f64,
    edge: Option<Edge>,
    pending: VecDeque<(f64, f64)>,
}

fn invalid(message: &str) -> Error {
    Error::new("event_resolution", message)
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

    pub(crate) fn value(&self, time: f64) -> Result<f64, Error> {
        let value = if let Some(edge) = &self.edge {
            if time >= edge.end {
                edge.target
            } else {
                edge.value + edge.slope * (time - edge.start)
            }
        } else {
            self.settled
        };
        if !value.is_finite() {
            return Err(invalid("nonfinite transition value"));
        }
        Ok(value)
    }

    pub(crate) fn next_breakpoint(&self, after: f64) -> Option<f64> {
        self.pending
            .front()
            .map(|(time, _)| *time)
            .into_iter()
            .chain(self.edge.as_ref().map(|e| e.end))
            .filter(|time| *time > after)
            .min_by(f64::total_cmp)
    }

    fn target(&mut self, time: f64, target: f64) -> Result<(), Error> {
        let value = self.value(time)?;
        if target == value {
            self.settled = target;
            self.edge = None;
            return Ok(());
        }
        // A completed edge has no residual historical origin. For an active
        // edge, reversal uses its old target; continuation retains its origin.
        let origin = match &self.edge {
            Some(edge) if time < edge.end => {
                if (target - value).is_sign_positive() == edge.slope.is_sign_positive() {
                    edge.origin
                } else {
                    edge.target
                }
            }
            _ => value,
        };
        let duration = if target > value { self.rise } else { self.fall };
        let slope = (target - origin) / duration;
        let remaining = (target - value) / slope;
        let end = time + remaining;
        if ![slope, remaining, end].iter().all(|v| v.is_finite())
            || slope == 0.0
            || remaining <= 0.0
            || end <= time
        {
            return Err(invalid("transition edge cannot advance representable time"));
        }
        self.edge = Some(Edge {
            start: time,
            value,
            origin,
            target,
            slope,
            end,
        });
        Ok(())
    }

    pub(crate) fn advance(&mut self, time: f64, input: f64) -> Result<(), Error> {
        // Process only semantic deadlines, not the output/max_step mesh.
        while self.pending.front().is_some_and(|(t, _)| *t <= time) {
            let (deadline, target) = self.pending.pop_front().unwrap();
            self.target(deadline, target)?;
        }
        if self.edge.as_ref().is_some_and(|edge| edge.end <= time) {
            self.settled = self.edge.take().unwrap().target;
        }
        if !input.is_finite() {
            return Err(invalid("nonfinite transition target"));
        }
        if input != self.input {
            let deadline = time + self.delay;
            if !deadline.is_finite() || (self.delay > 0.0 && deadline <= time) {
                return Err(invalid(
                    "transition delay cannot advance representable time",
                ));
            }
            if self.pending.back().is_some_and(|(t, _)| *t >= deadline) {
                return Err(invalid(
                    "distinct transition changes have indistinguishable deadlines",
                ));
            }
            self.input = input;
            if self.delay == 0.0 {
                self.target(time, input)?;
            } else {
                self.pending.push_back((deadline, input));
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
        edge.advance(7.0, 0.5).unwrap();
        near(edge.value(100.0).unwrap(), 0.5);
    }
}
