//! Fixed-rate slew of a continuous, directly driven PWL signal.
//!
//! Build semantic segments once. Queries neither accumulate integration error
//! nor change history. Interval predicates certify mode/root ordering for the
//! binary64 input points; returned voltages remain binary64 approximations.
use crate::event_accuracy::unresolved;
use crate::interval::Interval as I;
use crate::ir::Error;
use std::sync::Arc;

#[derive(Clone, Debug)]
enum Line {
    Input {
        start: f64,
        end: f64,
        a: f64,
        b: f64,
        a_bounds: I,
        b_bounds: I,
    },
    Limited {
        start: f64,
        offset: f64,
        offset_bounds: I,
        value: f64,
        value_bounds: I,
        rate: f64,
    },
}

impl Line {
    fn value(&self, time: f64) -> f64 {
        match *self {
            Self::Input {
                start, end, a, b, ..
            } => {
                if time == start {
                    a
                } else if time == end {
                    b
                } else {
                    let fraction = (time - start) / (end - start);
                    (1.0 - fraction) * a + fraction * b
                }
            }
            Self::Limited {
                start,
                offset,
                value,
                rate,
                ..
            } => rate.mul_add((time - start) - offset, value),
        }
    }

    fn bounds(&self, time: f64) -> I {
        match *self {
            Self::Input {
                start,
                end,
                a_bounds,
                b_bounds,
                ..
            } => {
                if time == start {
                    return a_bounds;
                }
                if time == end {
                    return b_bounds;
                }
                let fraction =
                    (I::point(time) - I::point(start)) / (I::point(end) - I::point(start));
                (I::ONE - fraction) * a_bounds + fraction * b_bounds
            }
            Self::Limited {
                start,
                offset_bounds,
                value_bounds,
                rate,
                ..
            } => {
                value_bounds + I::point(rate) * ((I::point(time) - I::point(start)) - offset_bounds)
            }
        }
    }
}

#[derive(Clone, Debug)]
struct Segment {
    start: f64,
    offset: f64,
    offset_bounds: I,
    line: Line,
}

#[derive(Clone, Debug)]
pub(crate) struct Slew {
    segments: Arc<[Segment]>,
    breakpoints: Arc<[f64]>,
    stop: f64,
    final_value: f64,
    final_bounds: I,
}

fn finite(value: f64) -> Result<f64, Error> {
    if value.is_finite() {
        Ok(value)
    } else {
        Err(unresolved("slew arithmetic overflow"))
    }
}

fn bounded(value: I) -> Result<I, Error> {
    if value.finite() {
        Ok(value)
    } else {
        Err(unresolved("cannot bound slew arithmetic"))
    }
}

fn sign(value: I) -> Result<i8, Error> {
    value
        .sign()
        .ok_or_else(|| unresolved("cannot determine slew mode within arithmetic bounds"))
}

// None denotes exact tracking; Some(rate) denotes a saturated derivative.
fn clipped(slope: I, rise: f64, fall: f64) -> Result<Option<f64>, Error> {
    if sign(slope - I::point(rise))? == 1 {
        Ok(Some(rise))
    } else if sign(slope - I::point(fall))? == -1 {
        Ok(Some(fall))
    } else {
        Ok(None)
    }
}

impl Slew {
    #[cfg(test)]
    pub(crate) fn new(points: Vec<(f64, f64)>, rise: f64, fall: f64) -> Result<Self, Error> {
        let bounds = points.iter().map(|p| I::point(p.1)).collect();
        Self::enclosed(points, bounds, rise, fall)
    }

    pub(crate) fn enclosed(
        points: Vec<(f64, f64)>,
        input_bounds: Vec<I>,
        rise: f64,
        fall: f64,
    ) -> Result<Self, Error> {
        if !rise.is_finite() || rise <= 0.0 || !fall.is_finite() || fall >= 0.0 {
            return Err(Error::new(
                "invalid_ir",
                "slew needs fixed finite rise > 0 and fall < 0",
            ));
        }
        if points.len() < 2
            || points[0].0 != 0.0
            || points.iter().any(|(t, v)| !t.is_finite() || !v.is_finite())
            || points.windows(2).any(|p| p[0].0 >= p[1].0)
        {
            return Err(Error::new(
                "invalid_inputs",
                "slew input must be a finite continuous PWL starting at zero",
            ));
        }
        if input_bounds.len() != points.len() || input_bounds.iter().any(|v| !v.finite()) {
            return Err(unresolved("cannot bound slew input history"));
        }
        let mut segments = Vec::new();
        let mut breakpoints = Vec::new();
        let mut value = points[0].1;
        let mut bounds = input_bounds[0];
        // A tracked endpoint is algebraically the input endpoint. Remembering
        // this identity avoids mistaking accumulated outward bounds for a lag.
        let mut tracking = true;
        for (pair, bound_pair) in points.windows(2).zip(input_bounds.windows(2)) {
            let (start, a) = pair[0];
            let (end, b) = pair[1];
            let duration = bounded(I::point(end) - I::point(start))?;
            let (a_bounds, b_bounds) = (bound_pair[0], bound_pair[1]);
            let slope = bounded((b_bounds - a_bounds) / duration)?;
            let input = Line::Input {
                start,
                end,
                a,
                b,
                a_bounds,
                b_bounds,
            };
            let gap = if tracking {
                0
            } else {
                sign(a_bounds - bounds)?
            };
            let rate = match gap {
                1 => Some(rise),
                -1 => Some(fall),
                _ => clipped(slope, rise, fall)?,
            };
            let Some(rate) = rate else {
                segments.push(Segment {
                    start,
                    offset: 0.0,
                    offset_bounds: I::ZERO,
                    line: input,
                });
                value = b;
                bounds = b_bounds;
                tracking = true;
                breakpoints.push(end);
                continue;
            };
            let line = Line::Limited {
                start,
                offset: 0.0,
                offset_bounds: I::ZERO,
                value,
                value_bounds: bounds,
                rate,
            };
            segments.push(Segment {
                start,
                offset: 0.0,
                offset_bounds: I::ZERO,
                line: line.clone(),
            });
            // While separated, continue pursuing the input even after an input
            // slope reversal. Switch modes only at an actual intersection.
            let closing = bounded(I::point(rate) - slope)?;
            let closing_sign = sign(closing)?;
            let can_catch = gap != 0 && closing_sign == gap;
            if !can_catch {
                value = finite(line.value(end))?;
                bounds = bounded(bounds + I::point(rate) * duration)?;
                tracking = false;
                breakpoints.push(end);
                continue;
            }
            // Check the endpoint before dividing. A tiny closing speed may
            // imply a root far beyond stop whose quotient would overflow;
            // no quotient is needed when the endpoint still has the same lag.
            let end_bounds = bounded(bounds + I::point(rate) * duration)?;
            let end_gap = sign(b_bounds - end_bounds)?;
            if end_gap == gap {
                value = finite(line.value(end))?;
                bounds = end_bounds;
                tracking = false;
            } else if end_gap == 0 {
                // Exact coincidence belongs to the input corner. The following
                // interval chooses its new mode from y=u, with no duplicate root.
                value = b;
                bounds = b_bounds;
                tracking = true;
            } else {
                let offset = bounded((a_bounds - bounds) / closing)?;
                if offset.lo <= 0.0 {
                    return Err(unresolved(
                        "slew catchup cannot be separated from its input knot",
                    ));
                }
                let root = bounded(I::point(start) + offset)?;
                if root.lo <= start || root.hi >= end {
                    return Err(unresolved(
                        "cannot order slew catchup inside its input segment",
                    ));
                }
                let nominal_slope = finite((b - a) / (end - start))?;
                let local = finite((a - value) / (rate - nominal_slope))?;
                if local <= 0.0 || local >= end - start || local < offset.lo || local > offset.hi {
                    return Err(unresolved("slew catchup has no usable representable time"));
                }
                // Only the scheduler uses an absolute representative. History
                // keeps the local root so adding a large epoch cannot move the
                // outgoing line or select the wrong mode at a rounded root.
                breakpoints.push(root.hi);
                match clipped(slope, rise, fall)? {
                    None => {
                        segments.push(Segment {
                            start,
                            offset: local,
                            offset_bounds: offset,
                            line: input,
                        });
                        value = b;
                        bounds = b_bounds;
                        tracking = true;
                    }
                    Some(next_rate) => {
                        let at_value = finite(nominal_slope.mul_add(local, a))?;
                        let at_bounds = bounded(a_bounds + slope * offset)?;
                        let next = Line::Limited {
                            start,
                            offset: local,
                            offset_bounds: offset,
                            value: at_value,
                            value_bounds: at_bounds,
                            rate: next_rate,
                        };
                        value = finite(next.value(end))?;
                        bounds = bounded(at_bounds + I::point(next_rate) * (duration - offset))?;
                        segments.push(Segment {
                            start,
                            offset: local,
                            offset_bounds: offset,
                            line: next,
                        });
                        tracking = false;
                    }
                }
            }
            breakpoints.push(end);
        }
        Ok(Self {
            segments: segments.into(),
            breakpoints: breakpoints.into(),
            stop: points.last().unwrap().0,
            final_value: value,
            final_bounds: bounds,
        })
    }

    pub(crate) fn value(&self, time: f64) -> Result<f64, Error> {
        if !time.is_finite() || time < 0.0 || time > self.stop {
            return Err(Error::new(
                "invalid_inputs",
                "slew query outside its input history",
            ));
        }
        if time == self.stop {
            return Ok(self.final_value);
        }
        let index = self.segments.partition_point(|segment| {
            segment.start <= time && time - segment.start >= segment.offset
        }) - 1;
        finite(self.segments[index].line.value(time))
    }

    pub(crate) fn value_bounds(&self, time: f64) -> I {
        if time == self.stop {
            return self.final_bounds;
        }
        // Locate the last mode certain to have begun, then include each mode
        // whose root interval contains the query. A nominal mode decision is
        // never mistaken for an exact decision in the voltage certificate.
        let index = self.segments.partition_point(|s| {
            s.start <= time && (I::point(time) - I::point(s.start)).lo >= s.offset_bounds.hi
        }) - 1;
        let mut bounds = self.segments[index].line.bounds(time);
        for segment in &self.segments[index + 1..] {
            if segment.start > time
                || (I::point(time) - I::point(segment.start)).hi < segment.offset_bounds.lo
            {
                break;
            }
            let next = segment.line.bounds(time);
            bounds = I {
                lo: bounds.lo.min(next.lo),
                hi: bounds.hi.max(next.hi),
            };
        }
        bounds
    }

    pub(crate) fn next_breakpoint(&self, after: f64) -> Option<f64> {
        self.breakpoints
            .get(self.breakpoints.partition_point(|time| *time <= after))
            .copied()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn catches_platform_and_tracks_without_query_history() {
        let slew = Slew::new(vec![(0., 0.), (2., 4.), (8., 4.)], 1., -2.).unwrap();
        for (t, y) in [(8., 4.), (2., 2.), (3., 3.), (4., 4.), (0., 0.)] {
            assert_eq!(slew.value(t).unwrap(), y);
        }
        assert_eq!(slew.next_breakpoint(2.), Some(4.));
        assert_eq!(slew.next_breakpoint(4.), Some(8.));
    }

    #[test]
    fn reversed_input_keeps_chasing_until_intersection() {
        let slew = Slew::new(vec![(0., 0.), (2., 4.), (4., -4.), (8., -4.)], 1., -2.).unwrap();
        for (t, expected) in [
            (2., 2.),
            (2.25, 2.25),
            (2.4, 2.4),
            (3., 1.2),
            (4., -0.8),
            (5.6, -4.),
        ] {
            assert!((slew.value(t).unwrap() - expected).abs() < 4e-15);
        }
        assert!(slew.next_breakpoint(2.).unwrap() >= 12. / 5.);
        assert!(slew.next_breakpoint(4.).unwrap() >= 28. / 5.);
    }

    #[test]
    fn exact_corner_coincidence_and_equal_limit_track() {
        let slew = Slew::new(vec![(0., 0.), (2., 4.), (4., 4.), (6., 2.)], 1., -2.).unwrap();
        assert_eq!(slew.value(4.).unwrap(), 4.);
        assert_eq!(slew.value(5.).unwrap(), 3.);
        assert_eq!(slew.next_breakpoint(2.), Some(4.));
        let linear = Slew::new(vec![(0., 0.), (1., 1.), (2., -1.)], 1., -2.).unwrap();
        assert_eq!(linear.value(0.5).unwrap(), 0.5);
        assert_eq!(linear.value(1.5).unwrap(), 0.);
    }

    #[test]
    fn invalid_and_unresolved_geometry_fail_explicitly() {
        assert!(Slew::new(vec![(0., 0.), (1., 1.)], 0., -1.).is_err());
        assert!(Slew::new(vec![(0., 0.), (1., 1.)], 1., 1.).is_err());
        assert!(Slew::new(vec![(0., 0.), (0., 1.)], 1., -1.).is_err());
        let extreme = Slew::new(vec![(0., -f64::MAX), (1., f64::MAX)], 1., -1.);
        assert_eq!(extreme.unwrap_err().kind, "event_resolution");
        // The true catchup is too close to a corner to order using the carried
        // arithmetic bounds; do not classify it by an arbitrary epsilon.
        let uncertain = Slew::new(vec![(0., 0.), (2., 4.), (4., -4.), (5.6, -4.)], 1., -2.);
        assert_eq!(uncertain.unwrap_err().kind, "event_resolution");
    }

    #[test]
    fn unreachable_catchup_does_not_require_an_overflowing_quotient() {
        let slew = Slew::new(vec![(0., 0.), (1., 1e308), (2., 1e308)], 1e-308, -1e-308).unwrap();
        assert_eq!(slew.value(2.).unwrap(), 2e-308);
        assert_eq!(slew.next_breakpoint(1.), Some(2.));
    }
}
