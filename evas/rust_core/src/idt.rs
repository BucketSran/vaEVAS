//! Explicit-IC integral of an immutable, directly driven continuous-PWL input.
//!
//! Prefix integrals belong to source knots, never accepted solver/output steps.
//! A Frame clone shares this analytic definition; a trial only queries it. A
//! corrected source definition requires a new history, not a time-only cache.
use crate::interval::{sum_products_sign, Interval as I};
use crate::ir::Error;
use std::sync::Arc;

#[derive(Clone, Debug)]
struct Knot {
    time: f64,
    input: f64,
    input_bounds: I,
    integral: f64,
    integral_bounds: I,
}

#[derive(Clone)]
pub(crate) struct Idt {
    knots: Arc<[Knot]>,
    ic: f64,
    reset: Option<ResetState>,
}

#[derive(Clone)]
struct ResetState {
    active: bool,
    release_time: f64,
    release_bounds: I,
}

impl Idt {
    pub(crate) fn enclosed(
        points: Vec<(f64, f64)>,
        bounds: Vec<I>,
        ic: f64,
    ) -> Result<Self, Error> {
        if !ic.is_finite() {
            return Err(Error::new(
                "unsupported_operator",
                "idt requires an explicit finite constant initial condition",
            ));
        }
        if points.len() < 2
            || points[0].0 != 0.0
            || points.iter().any(|(t, u)| !t.is_finite() || !u.is_finite())
            || points.windows(2).any(|p| p[0].0 >= p[1].0)
        {
            return Err(Error::new(
                "invalid_inputs",
                "idt requires finite continuous PWL starting at zero with increasing times",
            ));
        }
        if bounds.len() != points.len() || bounds.iter().any(|b| !b.finite() || b.lo > b.hi) {
            return Err(Error::new(
                "waveform_accuracy",
                "cannot bound idt input history",
            ));
        }
        let mut knots: Vec<Knot> = Vec::with_capacity(points.len());
        let (mut integral, mut integral_bounds) = (ic, I::point(ic));
        for ((time, input), input_bounds) in points.into_iter().zip(bounds) {
            if let Some(previous) = knots.last() {
                let duration = time - previous.time;
                // Exact trapezoid on the semantic source segment. Halve before
                // adding so equal large finite endpoints need not overflow.
                integral += duration * (0.5 * previous.input + 0.5 * input);
                integral_bounds = integral_bounds
                    + (I::point(time) - I::point(previous.time))
                        * (I::point(0.5) * previous.input_bounds + I::point(0.5) * input_bounds);
                if !integral.is_finite() || !integral_bounds.finite() {
                    return Err(Error::new(
                        "waveform_accuracy",
                        "nonfinite idt prefix integral or enclosure",
                    ));
                }
            }
            knots.push(Knot {
                time,
                input,
                input_bounds,
                integral,
                integral_bounds,
            });
        }
        Ok(Self {
            knots: knots.into(),
            ic,
            reset: None,
        })
    }

    pub(crate) fn with_reset(mut self, active: bool) -> Self {
        self.reset = Some(ResetState {
            active,
            release_time: 0.0,
            release_bounds: I::ZERO,
        });
        self
    }

    pub(crate) fn advance_reset(
        &mut self,
        time: f64,
        time_bounds: I,
        active: bool,
    ) -> Result<(), Error> {
        self.index(time)?;
        if !time_bounds.finite() || time_bounds.lo > time_bounds.hi {
            return Err(Error::new(
                "event_resolution",
                "invalid idt reset time bounds",
            ));
        }
        self.index(time_bounds.lo)?;
        self.index(time_bounds.hi)?;
        let Some(reset) = &mut self.reset else {
            return Ok(());
        };
        if reset.active && !active {
            reset.release_time = time;
            reset.release_bounds = time_bounds;
        }
        reset.active = active;
        Ok(())
    }

    pub(crate) fn reset_active(&self) -> bool {
        self.reset.as_ref().is_some_and(|reset| reset.active)
    }

    pub(crate) fn ic(&self) -> f64 {
        self.ic
    }

    fn index(&self, time: f64) -> Result<usize, Error> {
        if !time.is_finite() || time < 0.0 || time > self.knots.last().unwrap().time {
            return Err(Error::new(
                "invalid_inputs",
                "idt query must be within its finite source history",
            ));
        }
        Ok(self.knots.partition_point(|k| k.time < time))
    }

    fn prefix_value(&self, time: f64) -> Result<f64, Error> {
        let index = self.index(time)?;
        let end = &self.knots[index];
        if time == end.time {
            return Ok(end.integral);
        }
        let start = &self.knots[index - 1];
        let h = time - start.time;
        let half_fraction = 0.5 * (h / (end.time - start.time));
        // z0 + a*h + (b-a)*h^2/(2*d), evaluated with a local offset
        // and convex endpoint weights. No global t^2 or rounded slope.
        let value =
            start.integral + h * ((1.0 - half_fraction) * start.input + half_fraction * end.input);
        if !value.is_finite() {
            return Err(Error::new("numerical_failure", "nonfinite idt query"));
        }
        Ok(value)
    }

    fn segment_prefix_bounds(&self, start: &Knot, end: &Knot, h: I) -> Result<I, Error> {
        let duration = I::point(end.time) - I::point(start.time);
        let half_fraction = I::point(0.5) * (h / duration);
        let bound = start.integral_bounds
            + h * ((I::ONE - half_fraction) * start.input_bounds
                + half_fraction * end.input_bounds);
        if !bound.finite() {
            return Err(Error::new(
                "waveform_accuracy",
                "nonfinite idt query enclosure",
            ));
        }
        Ok(bound)
    }

    fn prefix_bounds(&self, time: f64) -> Result<I, Error> {
        let index = self.index(time)?;
        let end = &self.knots[index];
        if time == end.time {
            return Ok(end.integral_bounds);
        }
        let start = &self.knots[index - 1];
        let h = I::point(time) - I::point(start.time);
        self.segment_prefix_bounds(start, end, h)
    }

    fn prefix_range(&self, times: I) -> Result<I, Error> {
        if !times.finite() || times.lo > times.hi {
            return Err(Error::new(
                "event_resolution",
                "invalid idt reset time bounds",
            ));
        }
        self.index(times.lo)?;
        self.index(times.hi)?;
        let mut range: Option<I> = None;
        for pair in self.knots.windows(2) {
            let (start, end) = (&pair[0], &pair[1]);
            let left = times.lo.max(start.time);
            let right = times.hi.min(end.time);
            if left > right {
                continue;
            }
            let h = I {
                lo: left,
                hi: right,
            } - I::point(start.time);
            let segment = self.segment_prefix_bounds(start, end, h)?;
            range = Some(match range {
                Some(current) => current.hull(segment),
                None => segment,
            });
        }
        range
            .map(|value| I {
                lo: value.lo.next_down(),
                hi: value.hi.next_up(),
            })
            .ok_or_else(|| Error::new("event_resolution", "idt reset range has no source segment"))
    }

    pub(crate) fn value(&self, time: f64) -> Result<f64, Error> {
        if let Some(reset) = &self.reset {
            if reset.active {
                self.index(time)?;
                return Ok(self.ic);
            }
            let value =
                self.ic + self.prefix_value(time)? - self.prefix_value(reset.release_time)?;
            if !value.is_finite() {
                return Err(Error::new("numerical_failure", "nonfinite idt query"));
            }
            return Ok(value);
        }
        self.prefix_value(time)
    }

    pub(crate) fn value_bounds(&self, time: f64) -> Result<I, Error> {
        if let Some(reset) = &self.reset {
            if reset.active {
                self.index(time)?;
                return Ok(I::point(self.ic));
            }
            let bound = I::point(self.ic) + self.prefix_bounds(time)?
                - self.prefix_range(reset.release_bounds)?;
            if !bound.finite() {
                return Err(Error::new(
                    "waveform_accuracy",
                    "nonfinite idt query enclosure",
                ));
            }
            return Ok(bound);
        }
        self.prefix_bounds(time)
    }

    // This certificate is for the immutable no-reset analytic Idt used inside
    // IdtMod. Resettable transient idt state must not reuse it without carrying
    // the reset segment into the exact boundary expression.
    pub(crate) fn value_minus_linear_boundary_sign(
        &self,
        time: f64,
        offset: f64,
        turn: f64,
        modulus: f64,
    ) -> Result<Option<i8>, Error> {
        if self.reset.is_some() || !offset.is_finite() || !turn.is_finite() || !modulus.is_finite()
        {
            return Ok(None);
        }
        let index = self.index(time)?;
        let end = &self.knots[index];
        let mut terms = Vec::new();
        let push = |terms: &mut Vec<(f64, f64)>, a: f64, b: f64| {
            if a != 0.0 && b != 0.0 {
                terms.push((a, b));
            }
        };
        if time == end.time {
            if end.integral_bounds != I::point(end.integral) {
                return Ok(None);
            }
            push(&mut terms, end.integral, 1.0);
        } else {
            let start = &self.knots[index - 1];
            if start.integral_bounds != I::point(start.integral)
                || start.input_bounds != I::point(start.input)
                || end.input_bounds != I::point(end.input)
                || start.input != end.input
            {
                return Ok(None);
            }
            push(&mut terms, start.integral, 1.0);
            push(&mut terms, time, start.input);
            push(&mut terms, -start.time, start.input);
        }
        push(&mut terms, -offset, 1.0);
        push(&mut terms, -turn, modulus);
        if terms.len() > 4 {
            return Ok(None);
        }
        Ok(sum_products_sign(&terms))
    }

    pub(crate) fn next_breakpoint(&self, after: f64) -> Option<f64> {
        self.knots
            .get(self.knots.partition_point(|k| k.time <= after))
            .map(|k| k.time)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn history(points: Vec<(f64, f64)>, ic: f64) -> Idt {
        let bounds = points.iter().map(|p| I::point(p.1)).collect();
        Idt::enclosed(points, bounds, ic).unwrap()
    }

    #[test]
    fn analytic_values_queries_and_discard_do_not_write_history() {
        let accepted = history(vec![(0.0, 0.0), (2.0, 4.0), (5.0, -2.0), (8.0, -2.0)], 3.0);
        let baseline = accepted.value_bounds(3.0).unwrap();
        let candidate = accepted.clone();
        for (t, z) in [(8.0, 4.0), (1.0, 4.0), (5.0, 10.0), (3.0, 10.0), (0.0, 3.0)] {
            assert_eq!(candidate.value(t).unwrap(), z);
            let b = candidate.value_bounds(t).unwrap();
            assert!(b.lo <= z && b.hi >= z);
        }
        drop(candidate);
        assert_eq!(accepted.value_bounds(3.0).unwrap(), baseline);
        assert_eq!(accepted.next_breakpoint(0.0), Some(2.0));
        assert_eq!(accepted.value(1.0).unwrap(), 4.0);
    }

    #[test]
    fn corrected_source_at_same_query_time_gets_a_new_integral() {
        let accepted = history(vec![(0.0, 0.0), (2.0, 2.0)], 1.0);
        let candidate = history(vec![(0.0, 0.0), (2.0, 4.0)], 1.0);
        assert_eq!(accepted.value(1.0).unwrap(), 1.5);
        assert_eq!(candidate.value(1.0).unwrap(), 2.0);
        drop(candidate);
        assert_eq!(accepted.value(1.0).unwrap(), 1.5);
    }

    #[test]
    fn source_and_prefix_uncertainty_survive_knots() {
        let h = Idt::enclosed(
            vec![(0.0, 1.0), (1.0, 1.0), (2.0, 1.0)],
            vec![I { lo: 0.5, hi: 1.5 }; 3],
            0.0,
        )
        .unwrap();
        assert_eq!(h.value_bounds(1.0).unwrap(), I { lo: 0.5, hi: 1.5 });
        assert_eq!(h.value_bounds(2.0).unwrap(), I { lo: 1.0, hi: 3.0 });
        let fractional = history(vec![(0.0, 0.0), (3.0, 1.0)], 0.0);
        let bound = fractional.value_bounds(1.0).unwrap();
        assert!(bound.lo < 1.0 / 6.0 && bound.hi > 1.0 / 6.0);
    }

    #[test]
    fn reset_release_range_encloses_uncertain_zero_and_knot_crossing() {
        let history = Idt::enclosed(
            vec![(0.0, 0.25), (1.0, -0.75), (2.0, 0.5), (3.0, -0.5)],
            vec![
                I { lo: 0.25, hi: 1.0 },
                I {
                    lo: -1.0,
                    hi: -0.75,
                },
                I { lo: 0.25, hi: 0.75 },
                I {
                    lo: -0.75,
                    hi: -0.25,
                },
            ],
            0.0,
        )
        .unwrap();
        let range = history.prefix_range(I { lo: 0.45, hi: 1.25 }).unwrap();

        // Independent dyadic hand integrals:
        // possible first segment u(0)=1,u(1)=-1 has an interior zero at 0.5,
        // with prefix 1/4.  Another legal history u(0)=1/4,u(1)=-1,
        // u(2)=1/4 has prefix -75/128 at t=1.25.  The reset range must cover
        // both despite the release interval also crossing the source knot at 1.
        assert!(range.lo <= -75.0 / 128.0, "{range:?}");
        assert!(range.hi >= 0.25, "{range:?}");

        let mut reset = history.with_reset(true);
        reset
            .advance_reset(1.0, I { lo: 0.45, hi: 1.25 }, false)
            .unwrap();
        let after_release = reset.value_bounds(1.5).unwrap();
        assert!(after_release.lo < -0.25 && after_release.hi > 0.25);
    }

    #[test]
    fn raw_phase_certificate_cannot_ignore_reset_history() {
        let h = history(vec![(0.0, 1.0), (2.0, 1.0)], 0.0);
        assert_eq!(
            h.value_minus_linear_boundary_sign(1.0, 0.0, 1.0, 1.0)
                .unwrap(),
            Some(0)
        );
        let mut reset = h.with_reset(true);
        assert_eq!(
            reset
                .value_minus_linear_boundary_sign(1.0, 0.0, 1.0, 1.0)
                .unwrap(),
            None
        );
        reset.advance_reset(1.0, I::ONE, false).unwrap();
        assert_eq!(
            reset
                .value_minus_linear_boundary_sign(2.0, 0.0, 1.0, 1.0)
                .unwrap(),
            None
        );
    }

    #[test]
    fn malformed_history_nonfinite_ic_and_query_fail() {
        for points in [
            vec![],
            vec![(0.0, 1.0)],
            vec![(1.0, 0.0), (2.0, 1.0)],
            vec![(0.0, 1.0), (0.0, 2.0)],
            vec![(0.0, 0.0), (f64::INFINITY, 0.0)],
        ] {
            assert!(Idt::enclosed(points, vec![], 0.0).is_err());
        }
        for ic in [f64::NAN, f64::INFINITY, f64::NEG_INFINITY] {
            assert_eq!(
                Idt::enclosed(vec![], vec![], ic).err().unwrap().kind,
                "unsupported_operator"
            );
        }
        let h = history(vec![(0.0, 0.0), (1.0, 1.0)], 0.0);
        for t in [-1.0, 2.0, f64::INFINITY, f64::NAN] {
            assert!(h.value(t).is_err());
            assert!(h.value_bounds(t).is_err());
        }
    }
}
