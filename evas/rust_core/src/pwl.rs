//! Continuous PWL inputs and zero arrivals, independent of event state mutation.
use crate::event_accuracy::unresolved;
use crate::interval::{equal_products, sum_products_sign, Interval as I};
use crate::ir::{Error, TransientInputs};

pub(crate) struct Root {
    pub bounds: I,
    slope: I,
    segment: [f64; 2],
    ends: [I; 2],
}

impl Root {
    /// Search representable times using an exact sign predicate on the original
    /// numerator a*t1 - a*t + b*t - b*t0. No rounded time differences enter it.
    fn refine_representable(&mut self) {
        let [a, b] = self.ends;
        if a.lo != a.hi || b.lo != b.hi || a.lo == b.lo {
            return;
        }
        let sign = |time| {
            sum_products_sign(&[
                (a.lo, self.segment[1]),
                (-a.lo, time),
                (b.lo, time),
                (-b.lo, self.segment[0]),
            ])
        };
        let guess = self.segment[0] + (a.lo / (a.lo - b.lo)) * (self.segment[1] - self.segment[0]);
        let lower = self.bounds.lo.max(self.segment[0]).max(0.0);
        let upper = self.bounds.hi.min(self.segment[1]);
        if !lower.is_finite() || !upper.is_finite() || lower > upper {
            return;
        }
        for time in [guess, lower, upper] {
            if time.is_finite() && time >= lower && time <= upper && sign(time) == Some(0) {
                self.bounds = I::point(time);
                return;
            }
        }
        // Nonnegative finite binary64 bit patterns are monotonic. At most 64
        // bisections cover every representable time in the certified interval.
        let (mut lo, mut hi) = (lower.to_bits(), upper.to_bits());
        while lo <= hi {
            let mid = lo + (hi - lo) / 2;
            let time = f64::from_bits(mid);
            let Some(value) = sign(time) else {
                return;
            };
            if value == 0 {
                self.bounds = I::point(time);
                return;
            }
            let before_root = if b.lo > a.lo { value < 0 } else { value > 0 };
            if before_root {
                lo = mid + 1;
            } else {
                if mid == 0 {
                    return;
                }
                hi = mid - 1;
            }
        }
    }

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

    pub(crate) fn input_knots(&self, inputs: &[usize]) -> Vec<f64> {
        let mut knots = vec![0.0, self.config.stop];
        for &input in inputs {
            knots.extend(
                self.config.pwl[input]
                    .iter()
                    .map(|p| p[0])
                    .filter(|t| *t < self.config.stop),
            );
        }
        knots.sort_by(f64::total_cmp);
        knots.dedup();
        knots
    }

    pub(crate) fn roots(
        &self,
        knots: &[f64],
        values: &[I],
        direction: i8,
    ) -> Result<Vec<Root>, Error> {
        let mut result = Vec::new();
        if values.iter().any(|v| !v.finite() || v.sign().is_none()) {
            return Err(unresolved(
                "cannot determine cross sign at a PWL knot within arithmetic bounds",
            ));
        }
        for index in 0..values.len() - 1 {
            let (a, b) = (values[index], values[index + 1]);
            let segment = [knots[index], knots[index + 1]];
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
            } else if b.zero() && !a.zero() {
                // Arrival owns an exact zero, including plateau entry and stop.
                // Staying at or departing from zero matches neither branch;
                // only a later nonzero-to-zero arrival can fire again.
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
            if let Some((mut root, sign)) = crossing {
                if direction == 0 || direction == sign {
                    root.refine_representable();
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

#[cfg(test)]
mod tests {
    use super::*;

    fn candidate(a: I, b: I, time: f64) -> Root {
        Root {
            bounds: I {
                lo: time.next_down(),
                hi: time.next_up(),
            },
            slope: I::ONE,
            segment: [0.0, 19.0],
            ends: [a, b],
        }
    }

    #[test]
    fn bisection_certifies_root_when_quotient_and_products_overflow() {
        let mut root = Root {
            bounds: I { lo: 0.0, hi: 4.0 },
            slope: I::ONE,
            segment: [0.0, 4.0],
            ends: [I::point(-1e308), I::point(1e308)],
        };
        root.refine_representable();
        assert_eq!(root.bounds, I::point(2.0));
    }

    #[test]
    fn exact_zero_certificate_does_not_use_rounded_products_or_tolerance() {
        let mut root = candidate(I::point(-8.0), I::point(11.0), 8.0);
        root.refine_representable();
        assert_eq!(root.bounds, I::point(8.0));
        let mut uncertain = candidate(
            I {
                lo: -8.0,
                hi: (-8.0_f64).next_up(),
            },
            I::point(11.0),
            8.0,
        );
        uncertain.refine_representable();
        assert_ne!(uncertain.bounds.lo, uncertain.bounds.hi);
        let mut nonrepresentable = candidate(I::point(-1.0), I::point(2.0), 19.0 / 3.0);
        nonrepresentable.refine_representable();
        assert_ne!(nonrepresentable.bounds.lo, nonrepresentable.bounds.hi);
        // Underflowed products must not make a nonzero weighted sum look zero.
        let tiny = f64::from_bits(1);
        let mut subnormal = Root {
            bounds: I { lo: 0.25, hi: 0.5 },
            slope: I::ONE,
            segment: [0.0, 1.0],
            ends: [I::point(-tiny), I::point(2.0 * tiny)],
        };
        subnormal.refine_representable();
        assert_ne!(subnormal.bounds.lo, subnormal.bounds.hi);
    }
}
