//! Fixed transport delay of an immutable, semantic continuous-PWL input.
//!
//! The history is the accepted source segment definition, never output samples.
//! Keeping it immutable also makes a discarded transient candidate a no-op.
use crate::interval::Interval as I;
use crate::ir::Error;
use std::sync::Arc;

type HistoryTube = (Vec<(f64, f64)>, Vec<I>);

#[derive(Clone)]
pub(crate) struct AbsDelay {
    points: Arc<[(f64, f64)]>,
    bounds: Arc<[I]>,
    delay: f64,
    breakpoints: Arc<[f64]>,
}

impl AbsDelay {
    #[cfg(test)]
    pub(crate) fn new(points: Vec<(f64, f64)>, delay: f64) -> Result<Self, Error> {
        let bounds = points.iter().map(|p| I::point(p.1)).collect();
        Self::enclosed(points, bounds, delay)
    }

    pub(crate) fn enclosed(
        points: Vec<(f64, f64)>,
        bounds: Vec<I>,
        delay: f64,
    ) -> Result<Self, Error> {
        if !delay.is_finite() || delay < 0.0 {
            return Err(Error::new(
                "unsupported_operator",
                "absdelay requires a finite, fixed nonnegative delay; zero is an EVAS extension",
            ));
        }
        if bounds.len() != points.len() || bounds.iter().any(|b| !b.finite()) {
            return Err(Error::new(
                "waveform_accuracy",
                "cannot bound absdelay input history",
            ));
        }
        if points.is_empty()
            || points[0].0 != 0.0
            || points.iter().any(|(t, y)| !t.is_finite() || !y.is_finite())
            || points.windows(2).any(|p| p[0].0 >= p[1].0)
        {
            return Err(Error::new(
                "invalid_inputs",
                "absdelay input must be finite continuous PWL starting at zero, with strictly increasing times",
            ));
        }
        // Include the end of the initial held history (0 + delay). The last
        // input knot also matters: after it the input and delayed tail hold.
        let breakpoints: Vec<_> = points.iter().map(|(t, _)| t + delay).collect();
        if breakpoints.iter().any(|t| !t.is_finite())
            || breakpoints.windows(2).any(|p| p[0] >= p[1])
        {
            return Err(Error::new(
                "time_resolution",
                "absdelay shifted input knots overflow or cannot remain distinct in binary64",
            ));
        }
        Ok(Self {
            points: points.into(),
            bounds: bounds.into(),
            delay,
            breakpoints: breakpoints.into(),
        })
    }

    /// Export a pointwise tube, not an assertion that the true shifted corners
    /// occur at the rounded knots. For t between h_i and h_(i+1), map its
    /// fraction to the exact shifted knots s_i: |f(t)-f(tau)| <= L|t-tau|.
    /// Convex interpolation of B_i=A_i+[-L*|s_i-h_i|,L*|s_i-h_i|]
    /// therefore encloses f(t) everywhere, including a displaced true corner.
    /// Only a second delay may consume this tube; it is not a derivative PWL.
    pub(crate) fn shifted_tube(&self) -> Result<HistoryTube, Error> {
        let mut lipschitz: f64 = 0.0;
        for (k, pair) in self.points.windows(2).enumerate() {
            let slope =
                (self.bounds[k + 1] - self.bounds[k]) / (I::point(pair[1].0) - I::point(pair[0].0));
            if !slope.finite() {
                return Err(Error::new(
                    "waveform_accuracy",
                    "cannot certify delayed history slope",
                ));
            }
            lipschitz = lipschitz.max(slope.magnitude());
        }
        let mut points = Vec::new();
        let mut bounds = Vec::new();
        if self.delay > 0.0 {
            points.push((0.0, self.points[0].1));
            bounds.push(self.bounds[0]);
        }
        for (k, &(time, value)) in self.points.iter().enumerate() {
            let shifted = self.breakpoints[k];
            let error = (I::point(time) + I::point(self.delay) - I::point(shifted)).magnitude();
            let margin = (I::point(lipschitz) * I::point(error)).hi;
            let enclosure = self.bounds[k]
                + I {
                    lo: -margin,
                    hi: margin,
                };
            if !enclosure.finite() {
                return Err(Error::new(
                    "waveform_accuracy",
                    "nonfinite delayed history tube",
                ));
            }
            points.push((shifted, value));
            bounds.push(enclosure);
        }
        Ok((points, bounds))
    }

    pub(crate) fn value(&self, time: f64) -> Result<f64, Error> {
        if !time.is_finite() || time < 0.0 {
            return Err(Error::new(
                "invalid_inputs",
                "absdelay evaluation time must be finite and nonnegative",
            ));
        }
        // Error-free subtraction keeps the low part of the history time. At
        // t=2^54+4 and delay=3, rounding t-delay first would erase one whole
        // quarter of a four-unit ramp. Compare the expansion to source knots,
        // then interpolate using a local offset rather than that rounded time.
        let (query, remainder) = self.query(time);
        let index = self
            .points
            .partition_point(|(t, _)| *t < query || (*t == query && remainder > 0.0));
        if index == self.points.len() {
            return Ok(self.points.last().unwrap().1);
        }
        let (end, b) = self.points[index];
        if query == end && remainder == 0.0 {
            return Ok(b);
        }
        let (start, a) = self.points[index - 1];
        let fraction = ((query - start) + remainder) / (end - start);
        // A convex form avoids overflowing b-a for large opposite values.
        let value = (1.0 - fraction) * a + fraction * b;
        if !value.is_finite() {
            return Err(Error::new(
                "numerical_failure",
                "absdelay interpolation produced a non-finite value",
            ));
        }
        Ok(value)
    }

    fn query(&self, time: f64) -> (f64, f64) {
        if time <= self.delay {
            (0.0, 0.0)
        } else {
            let high = time - self.delay;
            let virtual_delay = time - high;
            let low = (time - (high + virtual_delay)) + (virtual_delay - self.delay);
            (high, low)
        }
    }

    pub(crate) fn value_bounds(&self, time: f64) -> I {
        let (query, remainder) = self.query(time);
        let index = self
            .points
            .partition_point(|(t, _)| *t < query || (*t == query && remainder > 0.0));
        if index == self.points.len() {
            return *self.bounds.last().unwrap();
        }
        let (end, _) = self.points[index];
        if query == end && remainder == 0.0 {
            return self.bounds[index];
        }
        let (start, _) = self.points[index - 1];
        // Keep the subtraction expansion until after removing the local
        // source origin. Enclosing t-delay first would lose that precision.
        let fraction = ((I::point(query) - I::point(start)) + I::point(remainder))
            / (I::point(end) - I::point(start));
        (I::ONE - fraction) * self.bounds[index - 1] + fraction * self.bounds[index]
    }

    pub(crate) fn next_breakpoint(&self, after: f64) -> Option<f64> {
        self.breakpoints
            .get(self.breakpoints.partition_point(|t| *t <= after))
            .copied()
    }
}

#[cfg(test)]
mod tests {
    use super::AbsDelay;

    fn ramp(delay: f64) -> AbsDelay {
        AbsDelay::new(vec![(0.0, -1.0), (4.0, 1.0), (10.0, 1.0)], delay).unwrap()
    }

    #[test]
    fn independent_ad_ramp_and_zero_identity() {
        let delayed = ramp(3.0);
        for (time, expected) in [
            (0.0, -1.0),
            (3.0, -1.0),
            (5.0, 0.0),
            (7.0, 1.0),
            (10.0, 1.0),
        ] {
            assert_eq!(delayed.value(time).unwrap(), expected);
        }
        let identity = ramp(0.0);
        for (time, expected) in [(0.0, -1.0), (2.0, 0.0), (4.0, 1.0), (10.0, 1.0)] {
            assert_eq!(identity.value(time).unwrap(), expected);
        }
    }

    #[test]
    fn shifted_knots_include_initial_history_and_terminal_hold() {
        let delayed = ramp(3.0);
        assert_eq!(delayed.next_breakpoint(0.0), Some(3.0));
        assert_eq!(delayed.next_breakpoint(3.0), Some(7.0));
        assert_eq!(delayed.next_breakpoint(7.0), Some(13.0));
        assert_eq!(delayed.next_breakpoint(13.0), None);
        assert_eq!(delayed.value(100.0).unwrap(), 1.0);
        assert_eq!(ramp(100.0).value(10.0).unwrap(), -1.0);
        assert_eq!(ramp(0.0).next_breakpoint(0.0), Some(4.0));
    }

    #[test]
    fn immutable_history_survives_discarded_candidate_and_query_order() {
        let accepted = ramp(3.0);
        let candidate = accepted.clone();
        assert_eq!(candidate.value(12.0).unwrap(), 1.0);
        assert_eq!(candidate.value(6.0).unwrap(), 0.5);
        drop(candidate);
        assert_eq!(accepted.next_breakpoint(0.0), Some(3.0));
        assert_eq!(accepted.value(4.0).unwrap(), -0.5);
        assert_eq!(accepted.value(0.0).unwrap(), -1.0);
        let other = ramp(1.0);
        assert_eq!(other.value(4.0).unwrap(), 0.5);
        assert_eq!(accepted.value(4.0).unwrap(), -0.5);
    }

    #[test]
    fn large_absolute_time_preserves_local_delayed_offset() {
        let offset = 2.0_f64.powi(54);
        let delayed = AbsDelay::new(
            vec![
                (0.0, 0.0),
                (offset, 0.0),
                (offset + 4.0, 1.0),
                (offset + 8.0, 1.0),
            ],
            3.0,
        )
        .unwrap();
        assert_eq!(delayed.value(offset + 4.0).unwrap(), 0.25);
        // The subtraction rounds up here; retaining its negative remainder
        // keeps a query just before the knot in the preceding segment.
        let falling = AbsDelay::new(
            vec![
                (0.0, 0.0),
                (offset, 0.0),
                (offset + 4.0, 1.0),
                (offset + 8.0, 0.0),
            ],
            1.0,
        )
        .unwrap();
        assert_eq!(falling.value(offset + 4.0).unwrap(), 0.75);
    }

    #[test]
    fn shifted_tube_encloses_displaced_true_corner_through_second_delay() {
        let a = 2.0_f64.powi(54);
        let first = AbsDelay::new(
            vec![(0.0, 0.0), (a, 0.0), (a + 4.0, 1.0), (a + 8.0, 1.0)],
            3.0,
        )
        .unwrap();
        let (points, bounds) = first.shifted_tube().unwrap();
        let second = AbsDelay::enclosed(points, bounds, 3.0).unwrap();
        // Exact-rational physical answer: x((A+8)-3-3)=x(A+2)=1/2.
        // This must remain inside the tube despite rounded exported corners.
        let bound = second.value_bounds(a + 8.0);
        assert!(bound.lo <= 0.5 && bound.hi >= 0.5);
        assert_ne!(second.value(a + 8.0).unwrap(), 0.5);
        let accepted = second.clone();
        let candidate = accepted.clone();
        let saved = accepted.value_bounds(a + 8.0);
        candidate.value(a + 4.0).unwrap();
        drop(candidate);
        assert_eq!(accepted.value_bounds(a + 8.0), saved);
    }

    #[test]
    fn invalid_history_and_unrepresentable_shift_fail_explicitly() {
        for points in [
            vec![],
            vec![(1.0, 1.0)],
            vec![(0.0, 0.0), (0.0, 1.0)],
            vec![(0.0, 0.0), (f64::NAN, 1.0)],
            vec![(0.0, f64::INFINITY)],
        ] {
            assert!(AbsDelay::new(points, 1.0).is_err());
        }
        for delay in [-1.0, f64::NAN, f64::INFINITY] {
            assert!(AbsDelay::new(vec![(0.0, 0.0), (1.0, 1.0)], delay).is_err());
        }
        let collapsed = AbsDelay::new(vec![(0.0, 0.0), (1.0, 1.0)], 1e20);
        assert_eq!(collapsed.err().unwrap().kind, "time_resolution");
        let overflow = AbsDelay::new(vec![(0.0, 0.0), (f64::MAX, 1.0)], f64::MAX);
        assert_eq!(overflow.err().unwrap().kind, "time_resolution");
        for time in [-1.0, f64::NAN, f64::INFINITY] {
            assert!(ramp(3.0).value(time).is_err());
        }
    }
}
