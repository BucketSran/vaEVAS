//! Bounded first-order `laplace_nd` for immutable, directly driven PWL input.
//!
//! Coefficients use Verilog-A ascending polynomial order. This slice accepts
//! `laplace_nd(u, '{b0}, '{d0,d1})` with finite d0,d1 > 0. The initial value is
//! the DC equilibrium `(b0/d0) * u(0)` for the compiled binary64 input.
use crate::interval::Interval as I;
use crate::ir::Error;
use std::sync::Arc;

#[derive(Clone, Debug)]
struct Knot {
    time: f64,
    input: f64,
    input_bounds: I,
    output: f64,
    output_bounds: I,
}

#[derive(Clone)]
pub(crate) struct LaplaceNd {
    knots: Arc<[Knot]>,
    gain: f64,
    tau: f64,
    gain_bounds: I,
    tau_bounds: I,
}

impl LaplaceNd {
    pub(crate) fn enclosed(
        points: Vec<(f64, f64)>,
        bounds: Vec<I>,
        numerator: &[f64],
        denominator: &[f64],
    ) -> Result<Self, Error> {
        if numerator.len() != 1 || denominator.len() != 2 {
            return Err(Error::new(
                "unsupported_operator",
                "laplace_nd supports only one numerator coefficient and a first-order denominator",
            ));
        }
        let (b0, d0, d1) = (numerator[0], denominator[0], denominator[1]);
        if !b0.is_finite() || !d0.is_finite() || !d1.is_finite() || d0 <= 0.0 || d1 <= 0.0 {
            return Err(Error::new(
                "unsupported_operator",
                "laplace_nd requires finite coefficients with positive first-order denominator",
            ));
        }
        let gain = b0 / d0;
        let tau = d1 / d0;
        let gain_bounds = I::point(b0) / I::point(d0);
        let tau_bounds = I::point(d1) / I::point(d0);
        if !gain.is_finite()
            || !tau.is_finite()
            || tau <= 0.0
            || !gain_bounds.finite()
            || !tau_bounds.finite()
            || tau_bounds.lo <= 0.0
        {
            return Err(Error::new(
                "unsupported_operator",
                "laplace_nd coefficient scale is nonfinite, underflowed or unstable",
            ));
        }
        if points.len() < 2
            || points[0].0 != 0.0
            || points.iter().any(|(t, u)| !t.is_finite() || !u.is_finite())
            || points.windows(2).any(|p| p[0].0 >= p[1].0)
        {
            return Err(Error::new(
                "invalid_inputs",
                "laplace_nd requires finite continuous PWL starting at zero with increasing times",
            ));
        }
        if bounds.len() != points.len() || bounds.iter().any(|b| !b.finite() || b.lo > b.hi) {
            return Err(Error::new(
                "waveform_accuracy",
                "cannot bound laplace_nd input history",
            ));
        }
        let mut knots: Vec<Knot> = Vec::with_capacity(points.len());
        for ((time, input), input_bounds) in points.into_iter().zip(bounds) {
            let (output, output_bounds) = if let Some(previous) = knots.last() {
                let duration = time - previous.time;
                let duration_bounds = interval_delta(previous.time, time)?;
                let output = segment_value(
                    previous.output,
                    previous.input,
                    input,
                    duration,
                    duration,
                    gain,
                    tau,
                )?;
                let output_bounds = segment_bounds(
                    previous.output_bounds,
                    previous.input_bounds,
                    input_bounds,
                    duration_bounds,
                    duration_bounds,
                    gain_bounds,
                    tau_bounds,
                )?;
                (output, output_bounds)
            } else {
                let output = gain * input;
                let output_bounds = expand(gain_bounds * input_bounds);
                (output, output_bounds)
            };
            if !output.is_finite() || !output_bounds.finite() {
                return Err(Error::new(
                    "waveform_accuracy",
                    "nonfinite laplace_nd prefix value or enclosure",
                ));
            }
            knots.push(Knot {
                time,
                input,
                input_bounds,
                output,
                output_bounds,
            });
        }
        Ok(Self {
            knots: knots.into(),
            gain,
            tau,
            gain_bounds,
            tau_bounds,
        })
    }

    fn index(&self, time: f64) -> Result<usize, Error> {
        if !time.is_finite() || time < 0.0 || time > self.knots.last().unwrap().time {
            return Err(Error::new(
                "invalid_inputs",
                "laplace_nd query must be within its finite source history",
            ));
        }
        Ok(self.knots.partition_point(|k| k.time < time))
    }

    pub(crate) fn value(&self, time: f64) -> Result<f64, Error> {
        let index = self.index(time)?;
        let end = &self.knots[index];
        if time == end.time {
            return Ok(end.output);
        }
        let start = &self.knots[index - 1];
        segment_value(
            start.output,
            start.input,
            end.input,
            time - start.time,
            end.time - start.time,
            self.gain,
            self.tau,
        )
    }

    pub(crate) fn value_bounds(&self, time: f64) -> Result<I, Error> {
        let index = self.index(time)?;
        let end = &self.knots[index];
        if time == end.time {
            return Ok(end.output_bounds);
        }
        let start = &self.knots[index - 1];
        segment_bounds(
            start.output_bounds,
            start.input_bounds,
            end.input_bounds,
            interval_delta(start.time, time)?,
            interval_delta(start.time, end.time)?,
            self.gain_bounds,
            self.tau_bounds,
        )
    }

    pub(crate) fn next_breakpoint(&self, after: f64) -> Option<f64> {
        self.knots
            .get(self.knots.partition_point(|k| k.time <= after))
            .map(|k| k.time)
    }
}

fn segment_value(
    y0: f64,
    u0: f64,
    u1: f64,
    h: f64,
    duration: f64,
    gain: f64,
    tau: f64,
) -> Result<f64, Error> {
    let g = one_minus_exp_decay(h, tau);
    let b = lag_term(h, tau) / tau;
    let slope = (u1 - u0) / duration;
    let value = y0 + (gain * u0 - y0) * g + gain * slope * tau * b;
    if !value.is_finite() {
        return Err(Error::new(
            "numerical_failure",
            "laplace_nd evaluation produced a non-finite value",
        ));
    }
    Ok(value)
}

fn segment_bounds(y0: I, u0: I, u1: I, h: I, duration: I, gain: I, tau: I) -> Result<I, Error> {
    if !duration.finite() || duration.lo <= 0.0 || !gain.finite() || !tau.finite() || tau.lo <= 0.0
    {
        return Err(Error::new(
            "waveform_accuracy",
            "cannot bound laplace_nd coefficient or time scale",
        ));
    }
    let (g, b) = laplace_weights(h, tau)?;
    let slope = (u1 - u0) / duration;
    let bound = y0 + (gain * u0 - y0) * g + gain * slope * tau * b;
    if !bound.finite() {
        return Err(Error::new(
            "waveform_accuracy",
            "nonfinite laplace_nd query enclosure",
        ));
    }
    Ok(expand(bound))
}

fn one_minus_exp_decay(h: f64, tau: f64) -> f64 {
    -(-h / tau).exp_m1()
}

fn lag_term(h: f64, tau: f64) -> f64 {
    let x = h / tau;
    if x.abs() < 1e-5 {
        tau * x * x * (0.5 + x * (-1.0 / 6.0 + x / 24.0))
    } else {
        h + tau * (-x).exp_m1()
    }
}

fn laplace_weights(h: I, tau: I) -> Result<(I, I), Error> {
    if h.zero() {
        return Ok((I::ZERO, I::ZERO));
    }
    if !h.finite() || h.lo < 0.0 || !tau.finite() || tau.lo <= 0.0 {
        return Err(Error::new(
            "waveform_accuracy",
            "cannot bound laplace_nd exponential argument",
        ));
    }
    let x = h / tau;
    if !x.finite() || x.lo < 0.0 {
        return Err(Error::new(
            "waveform_accuracy",
            "cannot bound laplace_nd exponential argument",
        ));
    }
    if x.lo >= 1024.0 {
        let g = I {
            lo: 1.0_f64.next_down(),
            hi: 1.0,
        };
        return Ok((g, x - g));
    }
    let mut reduced = x;
    let mut halvings = 0;
    while reduced.hi > 1.0 / 16.0 {
        reduced = reduced / I::point(2.0);
        halvings += 1;
        if halvings > 64 || !reduced.finite() {
            return Err(Error::new(
                "waveform_accuracy",
                "cannot reduce laplace_nd exponential argument",
            ));
        }
    }
    let (mut g, mut b) = small_weights(reduced)?;
    for _ in 0..halvings {
        b = expand(I::point(2.0) * b + g * g);
        g = expand(g * (I::point(2.0) - g));
        if !g.finite() || !b.finite() {
            return Err(Error::new(
                "waveform_accuracy",
                "nonfinite laplace_nd exponential weight enclosure",
            ));
        }
    }
    Ok((g, b))
}

fn small_weights(x: I) -> Result<(I, I), Error> {
    if !x.finite() || x.lo < 0.0 || x.hi > 1.0 / 16.0 {
        return Err(Error::new(
            "waveform_accuracy",
            "laplace_nd small exponential range is invalid",
        ));
    }
    let n = 24;
    let mut term = x;
    let mut g = term;
    for k in 2..=n {
        term = term * x / I::point(k as f64);
        g = if k % 2 == 0 { g - term } else { g + term };
    }
    term = term * x / I::point((n + 1) as f64);
    let g = expand(g + symmetric(term.magnitude()));

    let mut term = x;
    let mut b = I::ZERO;
    for k in 2..=n {
        term = term * x / I::point(k as f64);
        b = if k % 2 == 0 { b + term } else { b - term };
    }
    term = term * x / I::point((n + 1) as f64);
    let b = expand(b + symmetric(term.magnitude()));
    Ok((g, b))
}

fn interval_delta(start: f64, end: f64) -> Result<I, Error> {
    let delta = I::point(end) - I::point(start);
    if !delta.finite() || delta.lo < 0.0 {
        return Err(Error::new(
            "waveform_accuracy",
            "cannot bound laplace_nd time interval",
        ));
    }
    Ok(delta)
}

fn symmetric(radius: f64) -> I {
    I {
        lo: -radius.abs(),
        hi: radius.abs(),
    }
}

fn expand(value: I) -> I {
    I {
        lo: value.lo.next_down(),
        hi: value.hi.next_up(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn history(points: Vec<(f64, f64)>, tau: f64) -> LaplaceNd {
        let bounds = points.iter().map(|p| I::point(p.1)).collect();
        LaplaceNd::enclosed(points, bounds, &[1.0], &[1.0, tau]).unwrap()
    }

    #[test]
    fn step_starts_at_dc_equilibrium_and_relaxes() {
        let h = history(
            vec![(0.0, 2.0), (1.0, 2.0), (1.0_f64.next_up(), 4.0), (5.0, 4.0)],
            0.5,
        );
        assert_eq!(h.value(0.0).unwrap(), 2.0);
        let y = h.value(2.0).unwrap();
        assert!((y - (4.0 - 2.0 * (-2.0_f64).exp())).abs() < 1e-14);
    }

    #[test]
    fn ramp_query_is_read_only_and_uses_new_source_definition() {
        let accepted = history(vec![(0.0, 0.0), (2.0, 2.0)], 1.0);
        let candidate = history(vec![(0.0, 0.0), (2.0, 4.0)], 1.0);
        let old = accepted.value(1.0).unwrap();
        assert_ne!(old, candidate.value(1.0).unwrap());
        drop(candidate);
        assert_eq!(accepted.value(1.0).unwrap(), old);
        assert_eq!(accepted.next_breakpoint(0.0), Some(2.0));
    }

    #[test]
    fn rejects_non_first_order_and_unstable_coefficients() {
        let points = vec![(0.0, 0.0), (1.0, 1.0)];
        let bounds = vec![I::ZERO, I::ONE];
        for (num, den) in [
            (&[1.0, 2.0][..], &[1.0, 1.0][..]),
            (&[1.0][..], &[1.0][..]),
            (&[1.0][..], &[1.0, -1.0][..]),
            (&[1.0][..], &[0.0, 1.0][..]),
            (&[1.0][..], &[1.0e308, 1.0e-308][..]),
        ] {
            assert!(LaplaceNd::enclosed(points.clone(), bounds.clone(), num, den).is_err());
        }
    }

    #[test]
    fn coefficient_and_time_bounds_keep_nonexact_arithmetic() {
        let points = vec![(0.0, 1.0), (1.0e16, 2.0)];
        let bounds = points.iter().map(|p| I::point(p.1)).collect();
        let history = LaplaceNd::enclosed(points, bounds, &[1.0], &[3.0, 3.0]).unwrap();
        assert!(history.gain_bounds.lo < history.gain);
        assert!(history.gain < history.gain_bounds.hi);
        let duration = interval_delta(1.0, 1.0e16).unwrap();
        assert!(duration.lo < 1.0e16);
        assert!(1.0e16 < duration.hi);
    }

    #[test]
    fn proved_weights_enclose_tiny_ordinary_and_large_arguments() {
        for x in [1e-12, 1e-4, 0.25, 4.0, 100.0, 1024.0] {
            let (g, b) = laplace_weights(I::point(x), I::ONE).unwrap();
            let exact_g = -(-x).exp_m1();
            let exact_b = if x < 0.5 {
                let mut term = x;
                let mut sum = 0.0;
                for k in 2..=40 {
                    term *= x / k as f64;
                    sum += if k % 2 == 0 { term } else { -term };
                }
                sum
            } else {
                x - exact_g
            };
            assert!(
                g.lo <= exact_g && exact_g <= g.hi,
                "g({x}) = {exact_g:?} not in {g:?}"
            );
            assert!(
                b.lo <= exact_b && exact_b <= b.hi,
                "b({x}) = {exact_b:?} not in {b:?}"
            );
        }
    }
}
