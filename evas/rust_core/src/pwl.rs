//! Continuous PWL inputs and zero arrivals, independent of event state mutation.
use crate::event_accuracy::unresolved;
use crate::interval::{equal_products, sum_products_sign, Interval as I};
use crate::ir::{Error, TransientInputs};

#[derive(Clone)]
pub(crate) struct Root {
    pub bounds: I,
    slope: I,
    segment: [f64; 2],
    ends: [I; 2],
    source_time: Option<crate::exact_source::RootTime>,
}

impl Root {
    pub(crate) fn with_source_time(mut self, curve: Option<&crate::exact_source::Curve>) -> Self {
        if let Some(time) = curve.and_then(|c| c.root_in(self.segment, self.ends, self.bounds)) {
            if let Some(bounds) = time.bounds() {
                self.bounds = I {
                    lo: self.bounds.lo.max(bounds.lo),
                    hi: self.bounds.hi.min(bounds.hi),
                };
                self.source_time = Some(time);
            }
        }
        self
    }

    pub(crate) fn rational_time(&self) -> Option<crate::exact_source::RootTime> {
        self.source_time.clone().or_else(|| {
            crate::exact_source::RootTime::point_ends(self.segment, self.ends, self.bounds)
        })
    }

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

    /// Compare roots using original source proofs or point endpoint guards.
    /// Enclosed projections without either proof retain ambiguity refusal.
    pub(crate) fn exact_order(&self, other: &Self) -> Option<std::cmp::Ordering> {
        if self.source_time.is_some() || other.source_time.is_some() {
            return Some(self.rational_time()?.order(&other.rational_time()?));
        }
        let [a, b] = self.ends;
        let [c, d] = other.ends;
        if [a, b, c, d].iter().any(|v| v.lo != v.hi) || a.lo == b.lo || c.lo == d.lo {
            return None;
        }
        let sign = crate::exact_time::sum_triples_sign(&[
            (a.lo, self.segment[1], c.lo),
            (-a.lo, self.segment[1], d.lo),
            (-b.lo, self.segment[0], c.lo),
            (b.lo, self.segment[0], d.lo),
            (-c.lo, other.segment[1], a.lo),
            (c.lo, other.segment[1], b.lo),
            (d.lo, other.segment[0], a.lo),
            (-d.lo, other.segment[0], b.lo),
        ])?;
        Some(
            (if (a.lo > b.lo) == (c.lo > d.lo) {
                sign
            } else {
                -sign
            })
            .cmp(&0),
        )
    }

    pub(crate) fn clock_order(
        &self,
        clock: crate::exact_time::Clock,
    ) -> Option<std::cmp::Ordering> {
        self.clock_delta_order(clock, 0.)
    }
    pub(crate) fn local_bounds(&self, clock: crate::exact_time::Clock) -> Option<I> {
        if let Some(time) = &self.source_time {
            return time.local_bounds(clock);
        }
        crate::exact_time::enclose_zero(|delta| {
            self.clock_delta_order(clock, delta).map(|o| match o {
                std::cmp::Ordering::Less => 1,
                std::cmp::Ordering::Equal => 0,
                std::cmp::Ordering::Greater => -1,
            })
        })
    }
    pub(crate) fn clock_delta_order(
        &self,
        clock: crate::exact_time::Clock,
        delta: f64,
    ) -> Option<std::cmp::Ordering> {
        if let Some(time) = &self.source_time {
            return time.clock_delta_order(clock, delta);
        }
        let [a, b] = self.ends;
        if a.lo != a.hi || b.lo != b.hi || a.lo == b.lo {
            return None;
        }
        let sign = crate::exact_time::sum_triples_sign(&[
            (a.lo, self.segment[1], 1.),
            (-a.lo, clock.start, 1.),
            (-a.lo, clock.period, clock.index as f64),
            (b.lo, clock.start, 1.),
            (b.lo, clock.period, clock.index as f64),
            (-b.lo, self.segment[0], 1.),
            (-a.lo, delta, 1.),
            (b.lo, delta, 1.),
        ])?;
        // Increasing guards are positive after their zero; decreasing guards
        // reverse the sign. Return root compared with clock, not vice versa.
        Some((if b.lo > a.lo { -sign } else { sign }).cmp(&0))
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
        if let Some(order) = self.exact_order(other) {
            return order == std::cmp::Ordering::Equal;
        }
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

#[derive(Clone)]
pub(crate) struct Trajectory {
    pub(crate) config: TransientInputs,
    pub(crate) knots: Vec<f64>,
    pub(crate) solver_points: Vec<f64>,
    source_errors: Vec<f64>,
    pub(crate) exact_sources: Vec<Option<crate::exact_source::Curve>>,
    original_source_count: usize,
}

impl Trajectory {
    // Root-demand slopes apply only to physical PWL inputs, not generated
    // sources whose enclosures may include an independent time-varying error.
    pub(crate) fn has_only_physical_inputs(&self) -> bool {
        self.original_source_count == self.config.pwl.len()
            && self.source_errors.iter().all(|e| *e == 0.)
    }

    pub(crate) fn range(&self, time: I) -> Result<(Vec<I>, Vec<I>), Error> {
        if !time.finite() || time.lo < 0.0 || time.hi > self.config.stop || time.lo > time.hi {
            return Err(Error::new(
                "event_resolution",
                "invalid guard time interval",
            ));
        }
        let left = self.value_bounds(time.lo);
        let right = self.value_bounds(time.hi);
        let mut values: Vec<_> = left.iter().zip(right).map(|(&a, b)| a.hull(b)).collect();
        let mut derivatives = Vec::new();
        for (k, source) in self.config.pwl.iter().enumerate() {
            let mut slope = None;
            for pair in source.windows(2) {
                if pair[0][0] < time.hi && pair[1][0] > time.lo
                    || time.lo == time.hi && pair[0][0] <= time.lo && time.lo <= pair[1][0]
                {
                    let d = (I::point(pair[1][1]) - I::point(pair[0][1]))
                        / (I::point(pair[1][0]) - I::point(pair[0][0]));
                    slope = Some(slope.map_or(d, |previous: I| previous.hull(d)));
                }
            }
            for &[t, v] in source {
                if t > time.lo && t < time.hi {
                    values[k] = values[k].hull(
                        I::point(v)
                            + I {
                                lo: -self.source_errors[k],
                                hi: self.source_errors[k],
                            },
                    );
                }
            }
            derivatives.push(slope.unwrap_or(I::ZERO));
        }
        Ok((values, derivatives))
    }
    pub(crate) fn new(config: TransientInputs, driven_count: usize) -> Result<Self, Error> {
        let invalid = || {
            Error::new("invalid_inputs", "PWL sources must start at 0, strictly increase and cover stop; output times must strictly increase within [0,stop]; stop/max_step must be positive and finite")
        };
        if !config.stop.is_finite()
            || config.stop <= 0.0
            || !config.max_step.is_finite()
            || config.max_step <= 0.0
            || config.pwl.len() != driven_count
            || config.strobetimes.len() > 100_000
            || config
                .strobetimes
                .iter()
                .any(|t| !t.is_finite() || *t < 0.0 || *t > config.stop)
            || config.strobetimes.windows(2).any(|p| p[0] >= p[1])
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
        let source_errors = vec![0.0; config.pwl.len()];
        let exact_sources = config
            .pwl
            .iter()
            .map(|p| crate::exact_source::Curve::source(p))
            .collect();
        let mut solver_points = knots.clone();
        solver_points.extend(&config.strobetimes);
        solver_points.sort_by(f64::total_cmp);
        solver_points.dedup();
        Ok(Self {
            solver_points,
            original_source_count: config.pwl.len(),
            exact_sources,
            config,
            knots,
            source_errors,
        })
    }

    pub(crate) fn add_enclosed_source(
        &mut self,
        points: Vec<[f64; 2]>,
        error: f64,
    ) -> Result<(), Error> {
        if !error.is_finite()
            || error < 0.0
            || points.len() < 2
            || points[0][0] != 0.0
            || points.last().unwrap()[0] < self.config.stop
            || points.iter().flatten().any(|v| !v.is_finite())
            || points.windows(2).any(|p| p[0][0] >= p[1][0])
        {
            return Err(Error::new(
                "waveform_accuracy",
                "invalid enclosed clamp source",
            ));
        }
        self.knots.extend(
            points
                .iter()
                .map(|p| p[0])
                .filter(|t| *t < self.config.stop),
        );
        self.knots.sort_by(f64::total_cmp);
        self.knots.dedup();
        self.solver_points = self.knots.clone();
        self.solver_points.extend(&self.config.strobetimes);
        self.solver_points.sort_by(f64::total_cmp);
        self.solver_points.dedup();
        self.exact_sources.push(if error == 0.0 {
            crate::exact_source::Curve::source(&points)
        } else {
            None
        });
        self.config.pwl.push(points);
        self.source_errors.push(error);
        Ok(())
    }

    /// Only the request's original inputs may establish an event time. A later
    /// generated/clipped source is not made original merely by having a curve.
    pub(crate) fn original_guard_curve(
        &self,
        guard: &crate::ir::Expression,
        input_nodes: &[usize],
    ) -> Option<crate::exact_source::Curve> {
        crate::exact_source::Curve::expression(
            guard,
            input_nodes.get(..self.original_source_count)?,
            &self.exact_sources[..self.original_source_count],
            self.config.stop,
        )
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
                        source_time: None,
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
                        source_time: None,
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
            .zip(&self.source_errors)
            .map(|(source, &error)| {
                let index = source.partition_point(|p| p[0] < time);
                if source[index][0] == time {
                    return I::point(source[index][1])
                        + I {
                            lo: -error,
                            hi: error,
                        };
                }
                let [start, a] = source[index - 1];
                let [end, b] = source[index];
                let fraction =
                    (I::point(time) - I::point(start)) / (I::point(end) - I::point(start));
                I::point(a)
                    + (I::point(b) - I::point(a)) * fraction
                    + I {
                        lo: -error,
                        hi: error,
                    }
            })
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn generated_zero_error_sources_do_not_gain_original_guard_provenance() {
        let points = vec![[0.0, -1.0], [2.0, 1.0]];
        let mut trajectory = Trajectory::new(
            TransientInputs {
                strobetimes: Vec::new(),
                pwl: vec![points.clone()],
                output_times: vec![0.0, 2.0],
                stop: 2.0,
                max_step: 1.0,
            },
            1,
        )
        .unwrap();
        trajectory.add_enclosed_source(points, 0.0).unwrap();
        assert!(trajectory.exact_sources[1].is_some());
        let guard = |node| crate::ir::Expression::Affine {
            constant: 0.0,
            terms: vec![crate::ir::Term {
                node,
                coefficient: 1.0,
            }],
        };
        assert!(trajectory
            .original_guard_curve(&guard(1), &[1, 2])
            .is_some());
        assert!(trajectory
            .original_guard_curve(&guard(2), &[1, 2])
            .is_none());
    }

    #[test]
    fn one_source_time_proof_controls_order_coincidence_and_tolerance() {
        let curve = crate::exact_source::Curve::source(&[[0.0, -1.0], [2.0, 1.0]]).unwrap();
        let root = Root {
            bounds: I { lo: 0.9, hi: 1.1 },
            slope: I::ONE,
            segment: [0.0, 2.0],
            ends: [I { lo: -1.1, hi: -0.9 }, I { lo: 0.9, hi: 1.1 }],
            source_time: None,
        };
        let proved = root.clone().with_source_time(Some(&curve));
        assert_eq!(proved.bounds, I::ONE);
        let point = Root {
            ends: [I::point(-1.0), I::ONE],
            ..root.clone()
        };
        assert_eq!(proved.exact_order(&point), Some(std::cmp::Ordering::Equal));
        assert!(proved.coincides(&point, false));
        assert_eq!(proved.exact_order(&root), None);
        assert!(!proved.coincides(&root, false));
        let later = crate::exact_source::Curve::source(&[[0.0, -1.0], [2.0, 0.9]]).unwrap();
        let later = root.with_source_time(Some(&later));
        assert_eq!(proved.exact_order(&later), Some(std::cmp::Ordering::Less));
        assert!(!proved.coincides(&later, true));
        assert!(proved.accepts(1.0, 0.0, 0.0));
        assert!(!proved.accepts(1.0_f64.next_up(), 0.0, 0.0));
    }

    fn candidate(a: I, b: I, time: f64) -> Root {
        Root {
            bounds: I {
                lo: time.next_down(),
                hi: time.next_up(),
            },
            slope: I::ONE,
            segment: [0.0, 19.0],
            ends: [a, b],
            source_time: None,
        }
    }

    #[test]
    fn bisection_certifies_root_when_quotient_and_products_overflow() {
        let mut root = Root {
            bounds: I { lo: 0.0, hi: 4.0 },
            slope: I::ONE,
            segment: [0.0, 4.0],
            ends: [I::point(-1e308), I::point(1e308)],
            source_time: None,
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
            source_time: None,
        };
        subnormal.refine_representable();
        assert_ne!(subnormal.bounds.lo, subnormal.bounds.hi);
    }
}

#[cfg(test)]
mod exact_mixed_order_tests {
    use super::*;
    use num_rational::BigRational as Q;
    use proptest::prelude::*;
    fn q(v: f64) -> Q {
        Q::from_float(v).unwrap()
    }
    fn finite() -> impl Strategy<Value = f64> {
        any::<u64>()
            .prop_map(f64::from_bits)
            .prop_filter("finite", |v| v.is_finite())
    }
    fn order(value: Q) -> std::cmp::Ordering {
        value.cmp(&q(0.))
    }
    fn root(a: f64, b: f64, t0: f64, t1: f64) -> Root {
        Root {
            bounds: I { lo: 0., hi: 1. },
            slope: I::ONE,
            segment: [t0, t1],
            ends: [I::point(a), I::point(b)],
            source_time: None,
        }
    }
    proptest! {
        #![proptest_config(ProptestConfig::with_cases(512))]
        #[test]
        fn source_clock_and_source_source_signs_use_original_rationals(a in finite(),b in finite(),c in finite(),d in finite(),t0 in finite(),t1 in finite(),s0 in finite(),s1 in finite(),start in finite(),period in finite(),delta in finite(),index in 0usize..1_000_000) {
            prop_assume!(a!=b && c!=d);
            let left=root(a,b,t0,t1);
            let right=root(c,d,s0,s1);
            let clock=crate::exact_time::Clock {start,period,index};
            let left_time=(q(a)*q(t1)-q(b)*q(t0))/(q(a)-q(b));
            let right_time=(q(c)*q(s1)-q(d)*q(s0))/(q(c)-q(d));
            prop_assert_eq!(left.exact_order(&right),Some(order(left_time.clone()-right_time)));
            prop_assert_eq!(left.clock_delta_order(clock,delta),Some(order(left_time-q(start)-q(period)*q(index as f64)-q(delta))));
        }
    }
}
