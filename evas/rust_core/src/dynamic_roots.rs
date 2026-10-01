//! Certified zero isolation for continuous event guards.
//!
//! The caller supplies interval extensions of the guard trajectory and its time
//! derivative. A root is reported only after an interval proof: either an exact
//! non-initial arrival at a segment endpoint, or a strict-monotone bracket whose
//! final upper bound is a representative time at or after the mathematical root.
use crate::interval::Interval as I;
use crate::ir::Error;

const MAX_BOXES: usize = 4096;
const MAX_BISECTIONS: usize = 256;
const MAX_DEPTH: usize = 128;

#[derive(Clone, Copy, Debug, PartialEq)]
pub(crate) struct CertifiedRoot {
    pub(crate) bounds: I,
    pub(crate) derivative: I,
}

fn unresolved(message: &str) -> Error {
    Error::new("event_resolution", message)
}

fn valid_direction(direction: i8) -> bool {
    matches!(direction, -1..=1)
}

fn root_matches(direction: i8, crossing: i8) -> bool {
    direction == 0 || direction == crossing
}

fn strict_sign(value: I, label: &str) -> Result<i8, Error> {
    if !value.finite() {
        return Err(unresolved("nonfinite dynamic cross guard bounds"));
    }
    match value.sign() {
        Some(-1) => Ok(-1),
        Some(0) => Ok(0),
        Some(1) => Ok(1),
        _ => Err(unresolved(label)),
    }
}

fn ordered(value: I, label: &str) -> Result<I, Error> {
    if !value.finite() || value.lo > value.hi {
        return Err(unresolved(label));
    }
    Ok(value)
}

fn range_bounds(bounds: I, range: &mut impl FnMut(I) -> Result<I, Error>) -> Result<I, Error> {
    ordered(bounds, "invalid dynamic cross guard query interval")?;
    ordered(range(bounds)?, "invalid dynamic cross guard bounds")
}

fn endpoint_value(time: f64, range: &mut impl FnMut(I) -> Result<I, Error>) -> Result<I, Error> {
    range_bounds(I::point(time), range)
}

fn derivative_bounds(
    bounds: I,
    derivative: &mut impl FnMut(I) -> Result<I, Error>,
) -> Result<I, Error> {
    ordered(bounds, "invalid dynamic cross derivative query interval")?;
    ordered(
        derivative(bounds)?,
        "invalid dynamic cross derivative bounds",
    )
}

fn accepted_width(bounds: I, slope: I, ttol: f64, etol: f64) -> bool {
    if bounds.lo == bounds.hi {
        return true;
    }
    let width = I::point(bounds.hi) - I::point(bounds.lo);
    width.finite()
        && width.lo >= 0.0
        && width.hi <= ttol
        && (slope * width).finite()
        && (slope * width).magnitude() <= etol
}

fn certified_root(bounds: I, slope: I, ttol: f64, etol: f64) -> Result<CertifiedRoot, Error> {
    if accepted_width(bounds, slope, ttol, etol) {
        Ok(CertifiedRoot {
            bounds,
            derivative: slope,
        })
    } else {
        Err(unresolved(
            "dynamic cross root cannot be localized within time and expression tolerances",
        ))
    }
}

fn push_root(roots: &mut Vec<CertifiedRoot>, root: CertifiedRoot) {
    if roots.iter().any(|old| {
        old.bounds.lo == old.bounds.hi
            && root.bounds.lo == root.bounds.hi
            && old.bounds.lo == root.bounds.lo
    }) {
        return;
    }
    roots.push(root);
}

pub(crate) fn dedup_exact_roots(roots: &mut Vec<CertifiedRoot>) {
    roots.sort_by(|a, b| a.bounds.lo.total_cmp(&b.bounds.lo));
    roots.dedup_by(|a, b| {
        a.bounds.lo == a.bounds.hi && b.bounds.lo == b.bounds.hi && a.bounds.lo == b.bounds.lo
    });
}

#[allow(clippy::too_many_arguments)]
fn bisect_monotone(
    mut lo: f64,
    mut hi: f64,
    mut lo_sign: i8,
    mut hi_sign: i8,
    range: &mut impl FnMut(I) -> Result<I, Error>,
    derivative: &mut impl FnMut(I) -> Result<I, Error>,
    direction: i8,
    ttol: f64,
    etol: f64,
) -> Result<Option<CertifiedRoot>, Error> {
    if lo_sign == 0 || hi_sign == 0 || lo_sign == hi_sign {
        return Err(unresolved(
            "dynamic cross monotone bracket is not sign-changing",
        ));
    }
    if !root_matches(direction, hi_sign) {
        return Ok(None);
    }
    for _ in 0..MAX_BISECTIONS {
        let bounds = I { lo, hi };
        let slope = derivative_bounds(bounds, derivative)?;
        if slope.sign().is_none() || slope.sign() == Some(0) {
            return Err(unresolved(
                "dynamic cross derivative is not strictly signed on the root bracket",
            ));
        }
        if accepted_width(bounds, slope, ttol, etol) {
            return Ok(Some(CertifiedRoot {
                bounds,
                derivative: slope,
            }));
        }
        let mid = lo + (hi - lo) * 0.5;
        if mid <= lo || mid >= hi {
            return Err(unresolved(
                "dynamic cross root bisection stalled at time resolution",
            ));
        }
        let mid_value = endpoint_value(mid, range)?;
        let mid_sign = strict_sign(
            mid_value,
            "cannot determine dynamic cross sign at bisection midpoint",
        )?;
        if mid_sign == 0 {
            let point = I::point(mid);
            let slope = derivative_bounds(point, derivative)?;
            return Ok(Some(certified_root(point, slope, ttol, etol)?));
        }
        if mid_sign == lo_sign {
            lo = mid;
            lo_sign = mid_sign;
        } else if mid_sign == hi_sign {
            hi = mid;
            hi_sign = mid_sign;
        } else {
            return Err(unresolved("inconsistent dynamic cross midpoint sign"));
        }
    }
    Err(unresolved(
        "dynamic cross root isolation exceeded bisection budget",
    ))
}

#[allow(clippy::too_many_arguments)]
fn isolate_box(
    start: f64,
    end: f64,
    range: &mut impl FnMut(I) -> Result<I, Error>,
    derivative: &mut impl FnMut(I) -> Result<I, Error>,
    direction: i8,
    ttol: f64,
    etol: f64,
    depth: usize,
    boxes: &mut usize,
    roots: &mut Vec<CertifiedRoot>,
) -> Result<(), Error> {
    *boxes += 1;
    if *boxes > MAX_BOXES {
        return Err(unresolved(
            "dynamic cross root isolation exceeded subdivision budget",
        ));
    }
    if depth > MAX_DEPTH {
        return Err(unresolved(
            "dynamic cross root isolation exceeded subdivision depth",
        ));
    }
    let interval = I { lo: start, hi: end };
    let values = range_bounds(interval, range)?;
    if values.sign().is_some() && values.sign() != Some(0) {
        return Ok(());
    }

    let start_value = endpoint_value(start, range)?;
    let end_value = endpoint_value(end, range)?;
    let start_sign = strict_sign(
        start_value,
        "cannot determine dynamic cross sign at interval start",
    )?;
    let end_sign = strict_sign(
        end_value,
        "cannot determine dynamic cross sign at interval end",
    )?;
    let slope = derivative_bounds(interval, derivative)?;
    let slope_sign = slope.sign();

    if start_sign == 0 {
        if end_sign == 0 {
            return Err(unresolved(
                "dynamic cross plateau or repeated endpoint zero is not a unique event",
            ));
        }
        if slope_sign.is_some() && slope_sign != Some(0) {
            return Ok(());
        }
    }
    if end_sign == 0 && start_sign != 0 {
        let point_slope = derivative_bounds(I::point(end), derivative)?;
        let Some(crossing) = point_slope.sign().filter(|sign| *sign != 0) else {
            return Err(unresolved(
                "dynamic cross endpoint zero lacks transverse derivative proof",
            ));
        };
        if root_matches(direction, crossing) {
            push_root(
                roots,
                certified_root(I::point(end), point_slope, ttol, etol)?,
            );
        }
        if slope_sign.is_some() && slope_sign != Some(0) {
            return Ok(());
        }
    }
    if slope_sign.is_some() && slope_sign != Some(0) {
        if start_sign != end_sign {
            if let Some(root) = bisect_monotone(
                start, end, start_sign, end_sign, range, derivative, direction, ttol, etol,
            )? {
                push_root(roots, root);
            }
            return Ok(());
        }
        if values.sign().is_none() {
            // The box is monotone but too wide for the supplied interval range to
            // exclude zero. Refine before deciding; never declare no-root from
            // endpoint signs alone.
        } else {
            return Err(unresolved(
                "dynamic cross monotone range is inconsistent with endpoint signs",
            ));
        }
    }

    let mid = start + (end - start) * 0.5;
    if mid <= start || mid >= end {
        return Err(unresolved(
            "dynamic cross interval subdivision stalled at time resolution",
        ));
    }
    isolate_box(
        start,
        mid,
        range,
        derivative,
        direction,
        ttol,
        etol,
        depth + 1,
        boxes,
        roots,
    )?;
    isolate_box(
        mid,
        end,
        range,
        derivative,
        direction,
        ttol,
        etol,
        depth + 1,
        boxes,
        roots,
    )
}

pub(crate) fn isolate(
    start: f64,
    end: f64,
    range: &mut impl FnMut(I) -> Result<I, Error>,
    derivative: &mut impl FnMut(I) -> Result<I, Error>,
    direction: i8,
    ttol: f64,
    etol: f64,
) -> Result<Vec<CertifiedRoot>, Error> {
    if !start.is_finite()
        || !end.is_finite()
        || start >= end
        || !valid_direction(direction)
        || !ttol.is_finite()
        || ttol < 0.0
        || !etol.is_finite()
        || etol < 0.0
    {
        return Err(Error::new(
            "invalid_inputs",
            "dynamic cross isolation requires finite start < end, direction in {-1,0,1}, and nonnegative finite tolerances",
        ));
    }
    let mut roots = Vec::new();
    let mut boxes = 0;
    isolate_box(
        start, end, range, derivative, direction, ttol, etol, 0, &mut boxes, &mut roots,
    )?;
    dedup_exact_roots(&mut roots);
    Ok(roots)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn iv(lo: f64, hi: f64) -> I {
        I { lo, hi }
    }

    fn square_shift_range(time: I, center: f64, offset: f64) -> I {
        let left = time.lo - center;
        let right = time.hi - center;
        let max = left.abs().max(right.abs()).powi(2) + offset;
        let min = if left <= 0.0 && right >= 0.0 {
            offset
        } else {
            left.abs().min(right.abs()).powi(2) + offset
        };
        iv(min, max)
    }

    fn endpoint_zero_with_interior_root_range(time: I) -> I {
        fn value(t: f64) -> f64 {
            (t - 0.5) * (t - 2.0)
        }
        let mut lo = value(time.lo).min(value(time.hi));
        let mut hi = value(time.lo).max(value(time.hi));
        let vertex = 1.25;
        if time.lo <= vertex && vertex <= time.hi {
            lo = lo.min(value(vertex));
            hi = hi.max(value(vertex));
        }
        iv(lo, hi)
    }

    #[test]
    fn same_sign_endpoint_polynomial_is_not_missed() {
        let mut range = |time: I| Ok(square_shift_range(time, 1.0, -0.25));
        let mut derivative = |time: I| Ok(iv(2.0 * (time.lo - 1.0), 2.0 * (time.hi - 1.0)));
        let roots = isolate(0.0, 2.0, &mut range, &mut derivative, 0, 1e-9, 1e-9).unwrap();
        assert_eq!(roots.len(), 2);
        assert!(roots[0].bounds.lo <= 0.5 && roots[0].bounds.hi >= 0.5);
        assert!(roots[1].bounds.lo <= 1.5 && roots[1].bounds.hi >= 1.5);
    }

    #[test]
    fn tangent_root_is_reported_as_unresolved_not_silent_no_root() {
        let mut range = |time: I| Ok(square_shift_range(time, 1.0, 0.0));
        let mut derivative = |time: I| Ok(iv(2.0 * (time.lo - 1.0), 2.0 * (time.hi - 1.0)));
        let error = isolate(0.0, 2.0, &mut range, &mut derivative, 0, 1e-9, 1e-9).unwrap_err();
        assert_eq!(error.kind, "event_resolution");
    }

    #[test]
    fn endpoint_zero_does_not_hide_an_earlier_root() {
        let mut range = |time: I| Ok(endpoint_zero_with_interior_root_range(time));
        let mut derivative = |time: I| Ok(iv(2.0 * time.lo - 2.5, 2.0 * time.hi - 2.5));
        let roots = isolate(0.0, 2.0, &mut range, &mut derivative, 0, 1e-9, 1e-9).unwrap();
        assert_eq!(roots.len(), 2);
        assert!(roots[0].bounds.lo <= 0.5 && roots[0].bounds.hi >= 0.5);
        assert_eq!(roots[1].bounds, I::point(2.0));
    }

    #[test]
    fn wrong_direction_endpoint_does_not_skip_earlier_matching_root() {
        let mut range = |time: I| Ok(endpoint_zero_with_interior_root_range(time));
        let mut derivative = |time: I| Ok(iv(2.0 * time.lo - 2.5, 2.0 * time.hi - 2.5));
        let roots = isolate(0.0, 2.0, &mut range, &mut derivative, -1, 1e-9, 1e-9).unwrap();
        assert_eq!(roots.len(), 1);
        assert!(roots[0].bounds.lo <= 0.5 && roots[0].bounds.hi >= 0.5);
    }

    #[test]
    fn exponential_root_is_enclosed_at_log_two() {
        let mut range = |time: I| Ok(iv(time.lo.exp() - 2.0, time.hi.exp() - 2.0));
        let mut derivative = |time: I| Ok(iv(time.lo.exp(), time.hi.exp()));
        let roots = isolate(0.0, 1.0, &mut range, &mut derivative, 0, 1e-10, 1e-10).unwrap();
        assert_eq!(roots.len(), 1);
        let expected = 2.0_f64.ln();
        assert!(roots[0].bounds.lo <= expected);
        assert!(roots[0].bounds.hi >= expected);
        assert!(roots[0].bounds.hi - roots[0].bounds.lo <= 1e-10);
    }

    #[test]
    fn direction_filters_falling_and_rising_roots() {
        let mut falling_range = |time: I| Ok(square_shift_range(time, 1.0, -0.25));
        let mut falling_derivative = |time: I| Ok(iv(2.0 * (time.lo - 1.0), 2.0 * (time.hi - 1.0)));
        let falling = isolate(
            0.0,
            2.0,
            &mut falling_range,
            &mut falling_derivative,
            -1,
            1e-9,
            1e-9,
        )
        .unwrap();
        assert_eq!(falling.len(), 1);
        assert!(falling[0].bounds.lo <= 0.5 && falling[0].bounds.hi >= 0.5);

        let mut rising_range = |time: I| Ok(square_shift_range(time, 1.0, -0.25));
        let mut rising_derivative = |time: I| Ok(iv(2.0 * (time.lo - 1.0), 2.0 * (time.hi - 1.0)));
        let rising = isolate(
            0.0,
            2.0,
            &mut rising_range,
            &mut rising_derivative,
            1,
            1e-9,
            1e-9,
        )
        .unwrap();
        assert_eq!(rising.len(), 1);
        assert!(rising[0].bounds.lo <= 1.5 && rising[0].bounds.hi >= 1.5);
    }

    #[test]
    fn endpoint_semantics_match_arrival_not_initial_or_departure() {
        let mut arrival_range = |time: I| Ok(iv(time.lo - 1.0, time.hi - 1.0));
        let mut arrival_derivative = |_time: I| Ok(I::ONE);
        let arrival = isolate(
            0.0,
            1.0,
            &mut arrival_range,
            &mut arrival_derivative,
            1,
            1e-12,
            1e-12,
        )
        .unwrap();
        assert_eq!(arrival.len(), 1);
        assert_eq!(arrival[0].bounds, I::point(1.0));

        let mut departure_range = |time: I| Ok(time);
        let mut departure_derivative = |_time: I| Ok(I::ONE);
        let departure = isolate(
            0.0,
            1.0,
            &mut departure_range,
            &mut departure_derivative,
            1,
            1e-12,
            1e-12,
        )
        .unwrap();
        assert!(departure.is_empty());
    }

    #[test]
    fn adjacent_large_times_fail_when_requested_tolerance_is_unrepresentable() {
        let start: f64 = 1.0e16;
        let end = start.next_up();
        let mut range = |time: I| {
            if time.lo == time.hi && time.lo == start {
                Ok(I::point(-1.0))
            } else if time.lo == time.hi && time.lo == end {
                Ok(I::point(1.0))
            } else {
                Ok(iv(-1.0, 1.0))
            }
        };
        let mut derivative = |_time: I| Ok(I::ONE);
        let error = isolate(start, end, &mut range, &mut derivative, 0, 1e-12, 1e-12).unwrap_err();
        assert_eq!(error.kind, "event_resolution");
    }

    #[test]
    fn uncertain_range_is_refused_when_no_certificate_exists() {
        let mut range = |time: I| {
            if time.lo == time.hi {
                Ok(I::point(1.0))
            } else {
                Ok(iv(-1.0, 1.0))
            }
        };
        let mut derivative = |_time: I| Ok(I::ONE);
        let error = isolate(0.0, 1.0, &mut range, &mut derivative, 0, 1e-9, 1e-9).unwrap_err();
        assert_eq!(error.kind, "event_resolution");
    }

    #[test]
    fn callback_bounds_must_be_ordered() {
        let mut range = |_time: I| Ok(iv(1.0, -1.0));
        let mut derivative = |_time: I| Ok(I::ONE);
        let error = isolate(0.0, 1.0, &mut range, &mut derivative, 0, 1e-9, 1e-9).unwrap_err();
        assert_eq!(error.kind, "event_resolution");

        let mut range = |time: I| Ok(iv(time.lo - 0.5, time.hi - 0.5));
        let mut derivative = |_time: I| Ok(iv(1.0, -1.0));
        let error = isolate(0.0, 1.0, &mut range, &mut derivative, 0, 1e-9, 1e-9).unwrap_err();
        assert_eq!(error.kind, "event_resolution");
    }

    #[test]
    fn exact_roots_can_be_deduplicated_across_source_segments() {
        let root = CertifiedRoot {
            bounds: I::point(1.0),
            derivative: I::ONE,
        };
        let mut roots = vec![
            CertifiedRoot {
                bounds: iv(1.5, 1.5_f64.next_up()),
                derivative: I::ONE,
            },
            root,
            root,
        ];
        dedup_exact_roots(&mut roots);
        assert_eq!(roots.len(), 2);
        assert_eq!(roots[0].bounds, I::point(1.0));
    }
}
