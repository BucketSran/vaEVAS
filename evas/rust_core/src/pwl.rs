//! Continuous PWL inputs and isolated roots, independent of event state mutation.
use crate::event_accuracy::unresolved;
use crate::interval::{equal_products, Interval as I};
use crate::ir::{Error, TransientInputs};

pub(crate) struct Root {
    pub bounds: I,
    slope: I,
    segment: [f64; 2],
    ends: [I; 2],
}

impl Root {
    pub fn accepts(&self, time: f64, ttol: f64, etol: f64) -> bool {
        let delay = I::point(time) - self.bounds;
        let expression_error = self.slope * delay;
        time >= self.bounds.hi
            && time <= self.segment[1]
            && delay.finite()
            && delay.hi <= ttol
            && expression_error.finite()
            && expression_error.magnitude() <= etol
    }

    pub fn coincides(&self, other: &Self, identical_guard: bool) -> bool {
        if self.bounds.lo == self.bounds.hi && self.bounds == other.bounds {
            return true;
        }
        if self.segment != other.segment {
            return false;
        }
        if identical_guard {
            return true;
        }
        let [a, b] = self.ends;
        let [c, d] = other.ends;
        [a, b, c, d].iter().all(|v| v.lo == v.hi) && equal_products(a.lo, d.lo, c.lo, b.lo)
    }
}

pub(crate) struct Trajectory {
    pub(crate) config: TransientInputs,
    pub(crate) knots: Vec<f64>,
}

impl Trajectory {
    pub(crate) fn new(config: TransientInputs, driven_count: usize) -> Result<Self, Error> {
        let invalid = || {
            Error::new("invalid_inputs", "PWL sources must start at 0, strictly increase and cover stop; output times must strictly increase within [0,stop]; stop/max_step must be positive and finite")
        };
        if !config.stop.is_finite()
            || config.stop <= 0.0
            || !config.max_step.is_finite()
            || config.max_step <= 0.0
            || config.pwl.len() != driven_count
            || config.output_times.is_empty()
            || config
                .output_times
                .iter()
                .any(|t| !t.is_finite() || *t < 0.0 || *t > config.stop)
            || config.output_times.windows(2).any(|p| p[0] >= p[1])
        {
            return Err(invalid());
        }
        let mut knots = vec![0.0, config.stop];
        for source in &config.pwl {
            if source.len() < 2
                || source[0][0] != 0.0
                || source.last().unwrap()[0] < config.stop
                || source.iter().flatten().any(|v| !v.is_finite())
                || source.windows(2).any(|p| p[0][0] >= p[1][0])
            {
                return Err(invalid());
            }
            knots.extend(source.iter().map(|p| p[0]).filter(|t| *t < config.stop));
        }
        knots.sort_by(f64::total_cmp);
        knots.dedup();
        Ok(Self { config, knots })
    }

    pub(crate) fn values(&self, time: f64) -> Vec<f64> {
        self.config
            .pwl
            .iter()
            .map(|source| {
                let index = source.partition_point(|p| p[0] < time);
                if source[index][0] == time {
                    return source[index][1];
                }
                let [start, a] = source[index - 1];
                let [end, b] = source[index];
                let fraction = (time - start) / (end - start);
                (1.0 - fraction) * a + fraction * b
            })
            .collect()
    }

    pub(crate) fn roots(&self, values: &[I], direction: i8) -> Result<Vec<Root>, Error> {
        let mut result = Vec::new();
        if values.iter().any(|v| !v.finite() || v.sign().is_none()) {
            return Err(unresolved(
                "cannot determine cross sign at a PWL knot within arithmetic bounds",
            ));
        }
        if values.windows(2).any(|p| p[0].zero() && p[1].zero()) {
            return Err(Error::new(
                "unsupported_cross",
                "zero-valued cross plateau has no isolated root",
            ));
        }
        if values.last().is_some_and(|v| v.zero()) {
            return Err(Error::new(
                "unsupported_cross",
                "zero at stop needs a right-hand continuation to distinguish crossing from touch",
            ));
        }
        for index in 0..values.len() - 1 {
            let (a, b) = (values[index], values[index + 1]);
            let segment = [self.knots[index], self.knots[index + 1]];
            let duration = I::point(segment[1]) - I::point(segment[0]);
            let crossing = if !a.zero() && !b.zero() && a.sign() != b.sign() {
                let bounds = I::point(segment[0]) + (a / (a - b)) * duration;
                if !bounds.finite() || bounds.lo <= segment[0] || bounds.hi >= segment[1] {
                    return Err(unresolved(
                        "cannot enclose cross root strictly inside its PWL interval",
                    ));
                }
                Some((
                    Root {
                        bounds,
                        slope: (b - a) / duration,
                        segment,
                        ends: [a, b],
                    },
                    b.sign().unwrap(),
                ))
            } else if b.zero()
                && index + 2 < values.len()
                && !a.zero()
                && !values[index + 2].zero()
                && a.sign() != values[index + 2].sign()
            {
                Some((
                    Root {
                        bounds: I::point(segment[1]),
                        slope: I::ZERO,
                        segment,
                        ends: [a, b],
                    },
                    -a.sign().unwrap(),
                ))
            } else {
                None
            };
            if let Some((root, sign)) = crossing {
                if direction == 0 || direction == sign {
                    result.push(root);
                }
            }
        }
        Ok(result)
    }

    pub(crate) fn value_bounds(&self, time: f64) -> Vec<I> {
        self.config
            .pwl
            .iter()
            .map(|source| {
                let index = source.partition_point(|p| p[0] < time);
                if source[index][0] == time {
                    return I::point(source[index][1]);
                }
                let [start, a] = source[index - 1];
                let [end, b] = source[index];
                let fraction =
                    (I::point(time) - I::point(start)) / (I::point(end) - I::point(start));
                I::point(a) + (I::point(b) - I::point(a)) * fraction
            })
            .collect()
    }
}
