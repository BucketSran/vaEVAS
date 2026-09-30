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
        })
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

    pub(crate) fn value(&self, time: f64) -> Result<f64, Error> {
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

    pub(crate) fn value_bounds(&self, time: f64) -> Result<I, Error> {
        let index = self.index(time)?;
        let end = &self.knots[index];
        if time == end.time {
            return Ok(end.integral_bounds);
        }
        let start = &self.knots[index - 1];
        let h = I::point(time) - I::point(start.time);
        let half_fraction = I::point(0.5) * (h / (I::point(end.time) - I::point(start.time)));
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

    pub(crate) fn value_minus_linear_boundary_sign(
        &self,
        time: f64,
        offset: f64,
        turn: f64,
        modulus: f64,
    ) -> Result<Option<i8>, Error> {
        if !offset.is_finite() || !turn.is_finite() || !modulus.is_finite() {
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
