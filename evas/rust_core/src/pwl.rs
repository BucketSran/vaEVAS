//! Continuous PWL inputs and isolated roots, independent of event state mutation.
use crate::ir::{Error, TransientInputs};

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

    pub(crate) fn roots(
        &self,
        values: &[f64],
        direction: i8,
    ) -> Result<Vec<(f64, i8, f64)>, Error> {
        let mut result = Vec::new();
        if values.windows(2).any(|p| p[0] == 0.0 && p[1] == 0.0) {
            return Err(Error::new(
                "unsupported_cross",
                "zero-valued cross plateau has no isolated root",
            ));
        }
        if values.last() == Some(&0.0) {
            return Err(Error::new(
                "unsupported_cross",
                "zero at stop needs a right-hand continuation to distinguish crossing from touch",
            ));
        }
        for index in 0..values.len() - 1 {
            let (a, b) = (values[index], values[index + 1]);
            let crossing = if a != 0.0 && b != 0.0 && a.is_sign_positive() != b.is_sign_positive() {
                let scale = a.abs().max(b.abs());
                let fraction = (a.abs() / scale) / (a.abs() / scale + b.abs() / scale);
                let time =
                    self.knots[index] + fraction * (self.knots[index + 1] - self.knots[index]);
                if time <= self.knots[index] || time >= self.knots[index + 1] {
                    return Err(Error::new(
                        "event_resolution",
                        "cross root is not representable inside its interval",
                    ));
                }
                Some((time, if b > a { 1 } else { -1 }, self.knots[index + 1]))
            } else if b == 0.0
                && index + 2 < values.len()
                && a != 0.0
                && values[index + 2] != 0.0
                && a.is_sign_positive() != values[index + 2].is_sign_positive()
            {
                Some((
                    self.knots[index + 1],
                    if a < 0.0 { 1 } else { -1 },
                    self.knots[index + 1],
                ))
            } else {
                None
            };
            if let Some((time, sign, right)) = crossing {
                if direction == 0 || direction == sign {
                    result.push((time, sign, right));
                }
            }
        }
        Ok(result)
    }
}
