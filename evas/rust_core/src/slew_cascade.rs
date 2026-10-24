//! Two immutable fixed-rate stages. Exact rational knots preserve the first
//! limiter's intersections; no rounded/output grid becomes the second input.
use crate::exact_source::{binary, enclosure, Budget, MAX_POINTS};
use crate::interval::Interval as I;
use crate::ir::Error;
use num_rational::BigRational as R;
use num_traits::{Signed, ToPrimitive, Zero};
use std::sync::Arc;

fn unresolved() -> Error {
    Error::new(
        "waveform_accuracy",
        "cannot certify bounded two-stage slew history",
    )
}

// Fixed-rate limiting is monotone and commutes with a constant voltage shift.
// Thus |input - nominal| <= e, including the initial value, implies
// |slew(input) - slew(nominal)| <= e. The same bound survives both stages.
#[derive(Clone)]
pub(crate) struct Cascade {
    points: Arc<[(R, R)]>,
    breakpoints: Arc<[f64]>,
    input_error: R,
}

fn limit(points: &[(R, R)], rise: &R, fall: &R, budget: &mut Budget) -> Option<Vec<(R, R)>> {
    let mut result = vec![points.first()?.clone()];
    let mut value = points[0].1.clone();
    for pair in points.windows(2) {
        let (start, a) = &pair[0];
        let (end, b) = &pair[1];
        let duration = budget.check(end - start)?;
        let difference = budget.check(b - a)?;
        let slope = budget.check(difference / &duration)?;
        let gap = budget.check(a - &value)?;
        let clip = || slope.clone().max(fall.clone()).min(rise.clone());
        let rate = if gap.is_positive() {
            rise.clone()
        } else if gap.is_negative() {
            fall.clone()
        } else {
            clip()
        };
        let closing = budget.check(&rate - &slope)?;
        let delta = budget.check(&rate * &duration)?;
        let mut end_value = budget.check(&value + delta)?;
        if !gap.is_zero() && gap.signum() == closing.signum() {
            let offset = budget.check(gap / closing)?;
            if offset < duration {
                let time = budget.check(start + &offset)?;
                let change = budget.check(&rate * &offset)?;
                value = budget.check(value + change)?;
                result.push((time, value.clone()));
                let remainder = budget.check(duration - offset)?;
                let change = budget.check(clip() * remainder)?;
                end_value = budget.check(&value + change)?;
            }
        }
        value = end_value;
        result.push((end.clone(), value.clone()));
        if result.len() > 4 * MAX_POINTS {
            return None;
        }
    }
    Some(result)
}

impl Cascade {
    pub(crate) fn new(
        points: Vec<(f64, f64)>,
        bounds: Vec<I>,
        rates: [(f64, f64); 2],
    ) -> Result<Self, Error> {
        if points.len() < 2
            || points.len() > MAX_POINTS
            || bounds.len() != points.len()
            || points[0].0 != 0.
            || points.iter().any(|(t, v)| !t.is_finite() || !v.is_finite())
            || points.windows(2).any(|p| p[0].0 >= p[1].0)
            || bounds.iter().any(|b| !b.finite() || b.lo > b.hi)
        {
            return Err(unresolved());
        }
        if rates
            .iter()
            .any(|(up, down)| !up.is_finite() || *up <= 0. || !down.is_finite() || *down >= 0.)
        {
            return Err(Error::new(
                "invalid_ir",
                "slew needs fixed finite rise > 0 and fall < 0",
            ));
        }
        let build = || -> Option<Self> {
            let mut budget = Budget(0);
            let mut error = R::zero();
            let mut exact = Vec::new();
            for (&(time, value), bound) in points.iter().zip(bounds) {
                let value = binary(value)?;
                error = error
                    .max(budget.check((&value - binary(bound.lo)?).abs())?)
                    .max(budget.check((binary(bound.hi)? - &value).abs())?);
                exact.push((binary(time)?, value));
            }
            for (rise, fall) in rates {
                exact = limit(&exact, &binary(rise)?, &binary(fall)?, &mut budget)?;
            }
            let mut breakpoints = exact
                .iter()
                .skip(1)
                .map(|(t, _)| enclosure(t).map(|b| b.hi))
                .collect::<Option<Vec<_>>>()?;
            breakpoints.dedup();
            Some(Self {
                points: exact.into(),
                breakpoints: breakpoints.into(),
                input_error: error,
            })
        };
        build().ok_or_else(unresolved)
    }

    fn exact_value(&self, time: f64) -> Option<R> {
        let time = binary(time)?;
        if time < self.points[0].0 || time > self.points.last()?.0 {
            return None;
        }
        let index = self.points.partition_point(|(t, _)| *t < time);
        let (end, b) = &self.points[index];
        if time == *end {
            return Some(b.clone());
        }
        let (start, a) = &self.points[index - 1];
        let mut budget = Budget(0);
        let duration = budget.check(end - start)?;
        let offset = budget.check(time - start)?;
        let difference = budget.check(b - a)?;
        let fraction = budget.check(offset / duration)?;
        let change = budget.check(difference * fraction)?;
        budget.check(a + change)
    }

    pub(crate) fn value(&self, time: f64) -> Result<f64, Error> {
        self.exact_value(time)
            .and_then(|v| v.to_f64())
            .filter(|v| v.is_finite())
            .ok_or_else(unresolved)
    }

    pub(crate) fn value_bounds(&self, time: f64) -> Result<I, Error> {
        let result = || -> Option<I> {
            let value = self.exact_value(time)?;
            let mut budget = Budget(0);
            let lo = enclosure(&budget.check(&value - &self.input_error)?)?.lo;
            let hi = enclosure(&budget.check(&value + &self.input_error)?)?.hi;
            Some(I { lo, hi })
        };
        result().ok_or_else(unresolved)
    }

    pub(crate) fn next_breakpoint(&self, after: f64) -> Option<f64> {
        self.breakpoints
            .get(self.breakpoints.partition_point(|t| *t <= after))
            .copied()
    }
}

#[cfg(test)]
mod tests {
    use super::Cascade;
    use crate::interval::Interval as I;

    fn cascade(points: &[(f64, f64)], rates: [(f64, f64); 2]) -> Cascade {
        let bounds = points.iter().map(|(_, value)| I::point(*value)).collect();
        Cascade::new(points.to_vec(), bounds, rates).unwrap()
    }

    #[test]
    fn unit_ramp_outer_quarter_time_queries_do_not_change_history() {
        let history = cascade(&[(0., 0.), (4., 4.)], [(0.5, -0.5), (0.25, -0.25)]);
        for time in [0., 1., 2., 4.] {
            assert_eq!(history.value(time).unwrap(), time / 4.);
        }
        let breakpoint = history.next_breakpoint(0.);
        let bounds = history.value_bounds(2.).unwrap();
        assert_eq!(breakpoint, Some(4.));
        assert_eq!(bounds, I::point(0.5));
        let candidate = history.clone();
        assert_eq!(candidate.value(4.).unwrap(), 1.);
        assert_eq!(candidate.value_bounds(2.).unwrap(), bounds);
        assert_eq!(candidate.next_breakpoint(0.), breakpoint);
        drop(candidate);
        assert_eq!(history.value(2.).unwrap(), 0.5);
        assert_eq!(history.value_bounds(2.).unwrap(), bounds);
        assert_eq!(history.next_breakpoint(0.), breakpoint);

        let wider = cascade(&[(0., 0.), (4., 4.)], [(0.5, -0.5), (0.5, -0.5)]);
        assert_eq!(wider.value(4.).unwrap(), 2.);
        assert_eq!(history.value(4.).unwrap(), 1.);
        assert_eq!(history.next_breakpoint(0.), breakpoint);
    }

    #[test]
    fn outer_chase_keeps_its_corner_and_breakpoint_query_is_stable() {
        let history = cascade(
            &[(0., 0.), (2., 4.), (4., -4.), (24., -4.)],
            [(0.5, -0.5), (0.25, -0.25)],
        );
        assert_eq!(history.value(0.).unwrap(), 0.);
        assert_eq!(history.value(2.).unwrap(), 0.5);
        assert_eq!(history.value(3.).unwrap(), 0.75);
        // Negative control: outer slope flips at the inner corner 8/3.
        assert!((history.value(3.).unwrap() - 7. / 12.).abs() > 1e-10);
        assert!((history.value(4.).unwrap() - 7. / 9.).abs() < 1e-12);
        let turn = history.next_breakpoint(3.).unwrap();
        assert!(turn > 3. && turn < 4.);
        let bounds = history.value_bounds(3.).unwrap();
        assert!(bounds.lo <= 0.75 && bounds.hi >= 0.75);
        let candidate = history.clone();
        assert_eq!(candidate.next_breakpoint(3.), Some(turn));
        assert_eq!(candidate.value_bounds(3.).unwrap(), bounds);
        drop(candidate);
        assert_eq!(history.next_breakpoint(3.), Some(turn));
        assert_eq!(history.value(3.).unwrap(), 0.75);
        assert_eq!(history.value_bounds(3.).unwrap(), bounds);

        let ramp = cascade(&[(0., 0.), (4., 4.)], [(0.5, -0.5), (0.25, -0.25)]);
        assert_eq!(ramp.value(2.).unwrap(), 0.5);
        assert_eq!(history.next_breakpoint(3.), Some(turn));
        assert_eq!(history.value(3.).unwrap(), 0.75);
    }
}
