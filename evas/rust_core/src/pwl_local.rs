//! Preserve original PWL forcing when a certified clock becomes local time zero.
use super::*;
use crate::exact_source::{binary, enclosure, Budget, MAX_POINTS};
use crate::exact_time::Clock;
use num_rational::BigRational as R;
use num_traits::ToPrimitive;

impl Trajectory {
    pub(crate) fn at_clock(&self, clock: Clock, horizon: f64) -> Result<Self, Error> {
        let refuse = || {
            Error::new(
                "event_resolution",
                "local PWL clock translation is not certifiable",
            )
        };
        if clock.index > crate::schedule::EVENT_BUDGET
            || self.local_vertices.is_some()
            || !horizon.is_finite()
            || horizon <= 0.
        {
            return Err(refuse());
        }
        let mut budget = Budget(0);
        let epoch = budget
            .check(
                binary(clock.start).ok_or_else(refuse)?
                    + binary(clock.period).ok_or_else(refuse)?
                        * R::from_integer(clock.index.into()),
            )
            .ok_or_else(refuse)?;
        if epoch < R::from_integer(0.into())
            || epoch > binary(self.config.stop).ok_or_else(refuse)?
            || horizon > clock.delta(self.config.stop).ok_or_else(refuse)?.hi
        {
            return Err(refuse());
        }
        let end = budget
            .check(&epoch + binary(horizon).ok_or_else(refuse)?)
            .ok_or_else(refuse)?;
        let mut next = self.clone();
        next.config.stop = horizon;
        next.config.output_times = vec![0., horizon];
        next.config.strobetimes.clear(); // The caller still refuses strobe in local closure.
        next.config.pwl.clear();
        next.knots = vec![0., horizon];
        let mut vertices = Vec::new();
        for (k, source) in self.config.pwl.iter().enumerate() {
            if source.len() > MAX_POINTS {
                return Err(refuse());
            }
            let mut points = vec![(0., epoch.clone())];
            for &[time, _] in source {
                let absolute = binary(time).ok_or_else(refuse)?;
                if absolute > epoch && absolute < end {
                    let local = clock.delta(time).ok_or_else(refuse)?;
                    if local.lo != local.hi {
                        return Err(refuse());
                    }
                    points.push((local.lo, absolute));
                }
            }
            points.push((horizon, end.clone()));
            let mut waveform = Vec::new();
            let mut bounds = Vec::new();
            for (time, absolute) in points {
                // The final local enclosure may extend fractionally beyond
                // stop; extend the last affine piece only to enclose that edge.
                let i = source
                    .partition_point(|p| binary(p[0]).unwrap() < absolute)
                    .max(1)
                    .min(source.len() - 1);
                let [a, u] = source[i - 1];
                let [b, v] = source[i];
                let ratio = budget
                    .check(
                        (&absolute - binary(a).unwrap())
                            / (binary(b).unwrap() - binary(a).unwrap()),
                    )
                    .ok_or_else(refuse)?;
                let value = budget
                    .check(binary(u).unwrap() + (binary(v).unwrap() - binary(u).unwrap()) * ratio)
                    .ok_or_else(refuse)?;
                let range = enclosure(&value).ok_or_else(refuse)?
                    + I {
                        lo: -self.source_errors[k],
                        hi: self.source_errors[k],
                    };
                waveform.push([time, value.to_f64().ok_or_else(refuse)?]);
                bounds.push(range);
                next.knots.push(time);
            }
            next.config.pwl.push(waveform);
            vertices.push(bounds);
        }
        next.knots.sort_by(f64::total_cmp);
        next.knots.dedup();
        next.solver_points = next.knots.clone();
        // Enclosures do not establish exact original-source root provenance.
        next.exact_sources = vec![None; self.config.pwl.len()];
        next.local_vertices = Some(vertices);
        Ok(next)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn input(corner: f64, stop: f64) -> Trajectory {
        Trajectory::new(
            TransientInputs {
                pwl: vec![vec![[0., 2.], [corner, -1.], [stop, 3.]]],
                stop,
                max_step: stop,
                output_times: vec![0., stop],
                strobetimes: vec![],
            },
            1,
        )
        .unwrap()
    }

    #[test]
    fn exact_clock_shift_contains_original_rational_input_and_source_error() {
        let mut original = input(0.305, 0.31);
        original.source_errors[0] = 1e-12;
        let clock = Clock {
            start: 0.1,
            period: 0.2,
            index: 1,
        };
        let horizon = clock.delta(original.config.stop).unwrap().hi;
        let mut local = original.at_clock(clock, horizon).unwrap();
        let epoch = binary(0.1).unwrap() + binary(0.2).unwrap();
        for t in [0., 1e-18, 0.001, 0.005, 0.008, horizon] {
            let absolute = &epoch + binary(t).unwrap();
            let source = &original.config.pwl[0];
            let i = source
                .partition_point(|p| binary(p[0]).unwrap() < absolute)
                .max(1)
                .min(source.len() - 1);
            let [a, u] = source[i - 1];
            let [b, v] = source[i];
            let exact = binary(u).unwrap()
                + (binary(v).unwrap() - binary(u).unwrap()) * (absolute - binary(a).unwrap())
                    / (binary(b).unwrap() - binary(a).unwrap());
            let range = local.value_bounds(t)[0];
            assert!(binary(range.lo).unwrap() <= &exact - binary(1e-12).unwrap());
            assert!(binary(range.hi).unwrap() >= &exact + binary(1e-12).unwrap());
        }
        assert!(local.exact_sources[0].is_none());
        // Local interpolation data cannot mint absolute-time root certificates
        // or be extended by the initialization-only source lowerer.
        assert!(local
            .roots(&[0., horizon], &[I::point(-1.), I::point(1.)], 1)
            .is_err());
        assert!(local
            .add_enclosed_source(vec![[0., 0.], [horizon, 0.]], 0.)
            .is_err());
        assert!(local.at_clock(clock, 0.01).is_err());
    }

    #[test]
    fn unrepresentable_local_corner_and_invalid_horizon_refuse() {
        let clock = Clock {
            start: 0.1,
            period: 0.2,
            index: 1,
        };
        let original = input(0.9, 1.);
        assert!(original.at_clock(clock, 0.7).is_err());
        for horizon in [0., -1., 1., f64::INFINITY, f64::NAN] {
            assert!(original.at_clock(clock, horizon).is_err());
        }
        for start in [-0.1, 1.1] {
            assert!(original
                .at_clock(
                    Clock {
                        start,
                        period: 0.,
                        index: 0
                    },
                    0.01
                )
                .is_err());
        }
    }
}
