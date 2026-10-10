//! First-order feed-forward filters consume accepted transition history before
//! a new target is installed. Predictions are private and never commit state.
use crate::interval::Interval as I;
use crate::ir::{Error, OperatorSpec, Program};
use crate::transition::Transition;
use std::collections::BTreeSet;
use std::sync::Arc;

#[derive(Clone, Copy, PartialEq)]
pub(crate) struct Projection {
    pub(crate) parent: usize,
    coefficient: I,
    constant: I,
}

/// Structural dependencies are checked before projection. Cancellation must
/// not admit feedback, state forcing or a second history accidentally.
pub(crate) fn projection(program: &Program, driven: &[String], index: usize) -> Option<Projection> {
    let OperatorSpec::LaplaceNd {
        input,
        numerator,
        denominator,
        origin,
    } = &program.operators[index]
    else {
        return None;
    };
    if numerator.len() != 1
        || denominator.len() != 2
        || denominator[0] <= 0.
        || denominator[1] <= 0.
    {
        return None;
    }
    let driven_nodes: BTreeSet<_> = driven
        .iter()
        .filter_map(|n| program.nodes.iter().position(|x| x == n))
        .collect();
    let first = crate::events::affine(input, program, &origin.instance).ok()?;
    if !first.state_dependencies.is_empty() {
        return None;
    }
    let mut pending: Vec<_> = first.node_dependencies.into_iter().collect();
    let mut operators = first.operator_dependencies;
    let mut seen = BTreeSet::new();
    while let Some(node) = pending.pop() {
        if node == 0 || !seen.insert(node) {
            continue;
        }
        if driven_nodes.contains(&node) {
            return None;
        }
        for c in &program.contributions {
            if c.positive == node || c.negative == node {
                let a = crate::events::affine(&c.rhs, program, &c.origin.instance).ok()?;
                if !a.state_dependencies.is_empty() {
                    return None;
                }
                operators.extend(a.operator_dependencies);
                pending.extend(a.node_dependencies);
                pending.extend([c.positive, c.negative]);
            }
        }
    }
    if operators.len() != 1 {
        return None;
    }
    let parent = *operators.iter().next()?;
    if !matches!(program.operators[parent], OperatorSpec::Transition { .. })
        || program.operators[parent].origin().instance != origin.instance
    {
        return None;
    }
    let map = crate::affine_bounds::node_map(program, driven).ok()?;
    let expression = crate::affine_bounds::affine(input, program).ok()?;
    let variables = expression.len() - 1;
    let width = driven.len() + program.states.len() + program.operators.len() + 1;
    let slot = driven.len() + program.states.len() + parent;
    let mut row = vec![I::ZERO; width];
    for k in 0..width {
        let base = if k == width - 1 {
            expression[variables]
        } else {
            I::ZERO
        };
        row[k] = (0..variables).fold(base, |s, j| s + expression[j] * map[j][k]);
        if !row[k].finite() || (k != slot && k != width - 1 && !row[k].zero()) {
            return None;
        }
    }
    Some(Projection {
        parent,
        coefficient: row[slot],
        constant: row[width - 1],
    })
}

#[derive(Clone)]
pub(crate) struct Filter {
    time: f64,
    output: I,
    gain: I,
    tau: I,
    projection: Projection,
    prior: Option<Arc<(Filter, Transition)>>,
    prefix: Option<ActivationPrefix>,
}

/// Conservative history in a callback's physical-to-execution window. Exact
/// timer predicates can observe this window even when a dynamic root cannot.
#[derive(Clone, Copy, PartialEq)]
struct ActivationPrefix {
    start: f64,
    end: f64,
    initial: I,
    forcing: I,
}
impl ActivationPrefix {
    fn bounds(&self, times: I, tau: I) -> Result<I, Error> {
        let h = times - I::point(self.start);
        // Endpoint monotonicity avoids interval dependency in 1-exp(-h/tau).
        let lo = crate::laplace::laplace_weights(I::point(h.lo.max(0.)), tau)?.0;
        let hi = crate::laplace::laplace_weights(I::point(h.hi), tau)?.0;
        let g = I {
            lo: lo.lo.max(0.),
            hi: hi.hi.min(1.),
        };
        Ok(self.initial * (I::ONE - g) + self.forcing * g)
    }
}

impl Filter {
    pub(crate) fn reaches_deadline(&self, parent: &Transition, time: f64) -> bool {
        parent.next_breakpoint(self.time).is_some_and(|t| t <= time)
    }
    pub(crate) fn new(
        projection: Projection,
        parent: &Transition,
        numerator: &[f64],
        denominator: &[f64],
    ) -> Result<Self, Error> {
        let gain = I::point(numerator[0]) / I::point(denominator[0]);
        let tau = I::point(denominator[1]) / I::point(denominator[0]);
        let output =
            gain * (projection.coefficient * parent.value_bounds(0.)? + projection.constant);
        if !gain.finite() || !tau.finite() || tau.lo <= 0. || !output.finite() {
            return Err(Error::new(
                "unsupported_operator",
                "invalid transition/filter coefficient scale",
            ));
        }
        Ok(Self {
            time: 0.,
            output,
            gain,
            tau,
            projection,
            prior: None,
            prefix: None,
        })
    }

    pub(crate) fn predicted(&self, parent: &Transition, time: f64) -> Result<Self, Error> {
        if !time.is_finite() || time < self.time {
            return Err(Error::new(
                "event_resolution",
                "filter query precedes its accepted history",
            ));
        }
        let mut next = self.clone();
        next.prefix = None;
        let mut forcing = parent.clone();
        forcing.advance_time(self.time)?;
        while next.time < time {
            let end = forcing
                .forcing_boundary(next.time)
                .unwrap_or(time)
                .min(time);
            let h = I::point(end) - I::point(next.time);
            let (g, b) = crate::laplace::laplace_weights(h, next.tau)?;
            let p = next.projection;
            next.output = if forcing.forcing_uncertain(next.time) {
                // Positive exponential kernel bounds every forcing trajectory
                // in this range. Never connect endpoints across an activation.
                let input = p.coefficient
                    * forcing.forcing_range(I {
                        lo: next.time,
                        hi: end,
                    })
                    + p.constant;
                next.output * (I::ONE - g) + next.gain * input * g
            } else {
                let (input, slope) = forcing.forcing_line(next.time);
                let input = p.coefficient * input + p.constant;
                let slope = p.coefficient * slope;
                next.output * (I::ONE - g)
                    + next.gain * input * g
                    + next.gain * slope * next.tau * b
            };
            if !next.output.finite() {
                return Err(Error::new(
                    "waveform_accuracy",
                    "nonfinite transition/filter history",
                ));
            }
            next.time = end;
            forcing.advance_time(end)?;
        }
        Ok(next)
    }

    pub(crate) fn committed(&self, parent: &Transition, time: f64) -> Result<Self, Error> {
        if time == self.time {
            return Ok(self.clone());
        }
        let mut next = self.predicted(parent, time)?;
        if time > self.time {
            next.prior = Some(Arc::new((self.clone(), parent.clone())));
        }
        Ok(next)
    }
    pub(crate) fn committed_change(
        &self,
        old: &Transition,
        new: &Transition,
        time: f64,
        window: I,
    ) -> Result<Self, Error> {
        let mut next = self.committed(old, time)?;
        if new.input_changed_from(old) && window.lo < time {
            if window.lo < self.time {
                return Err(Error::new(
                    "event_resolution",
                    "transition/filter activation overlaps committed history",
                ));
            }
            let times = I {
                lo: window.lo,
                hi: time,
            };
            let p = self.projection;
            let prefix = ActivationPrefix {
                start: window.lo,
                end: time,
                initial: self.bounds(old, window.lo)?,
                forcing: self.gain
                    * (p.coefficient * old.forcing_range(times).hull(new.forcing_range(times))
                        + p.constant),
            };
            next.output = prefix.bounds(I::point(time), self.tau)?;
            next.prefix = Some(prefix);
        }
        Ok(next)
    }
    pub(crate) fn bounds(&self, parent: &Transition, time: f64) -> Result<I, Error> {
        if let Some(prefix) = &self.prefix {
            if time >= prefix.start && time <= prefix.end {
                return prefix.bounds(I::point(time), self.tau);
            }
        }
        if time < self.time {
            if let Some(prior) = &self.prior {
                return prior.0.bounds(&prior.1, time);
            }
        }
        Ok(self.predicted(parent, time)?.output)
    }
    pub(crate) fn value(&self, parent: &Transition, time: f64) -> Result<f64, Error> {
        let b = self.bounds(parent, time)?;
        Ok(if b.lo == b.hi {
            b.lo
        } else {
            b.lo * 0.5 + b.hi * 0.5
        })
    }
    pub(crate) fn range(&self, parent: &Transition, time: I) -> Result<I, Error> {
        if let Some(prefix) = &self.prefix {
            if time.lo <= prefix.end && time.hi >= prefix.start {
                let mut result = prefix.bounds(
                    I {
                        lo: time.lo.max(prefix.start),
                        hi: time.hi.min(prefix.end),
                    },
                    self.tau,
                )?;
                if time.lo < prefix.start {
                    let prior = self.prior.as_ref().ok_or_else(|| {
                        Error::new("event_resolution", "activation prefix has no prior history")
                    })?;
                    result = result.hull(prior.0.range(
                        &prior.1,
                        I {
                            lo: time.lo,
                            hi: prefix.start,
                        },
                    )?);
                }
                if time.hi > prefix.end {
                    let mut after = self.clone();
                    after.prefix = None;
                    result = result.hull(after.range(
                        parent,
                        I {
                            lo: prefix.end,
                            hi: time.hi,
                        },
                    )?);
                }
                return Ok(result);
            }
        }
        if time.lo < self.time {
            let prior = self.prior.as_ref().ok_or_else(|| {
                Error::new(
                    "event_resolution",
                    "filter observation precedes retained history",
                )
            })?;
            let old = prior.0.range(
                &prior.1,
                I {
                    lo: time.lo,
                    hi: time.hi.min(self.time),
                },
            )?;
            return if time.hi <= self.time {
                Ok(old)
            } else {
                Ok(old.hull(self.range(
                    parent,
                    I {
                        lo: self.time,
                        hi: time.hi,
                    },
                )?))
            };
        }
        let initial = self.bounds(parent, time.lo)?;
        let input =
            self.projection.coefficient * parent.forcing_range(time) + self.projection.constant;
        let hull = initial.hull(self.gain * input);
        let derivative = (self.gain * input - hull) / self.tau;
        let local = initial + derivative * (time - I::point(time.lo));
        Ok(I {
            lo: hull.lo.max(local.lo),
            hi: hull.hi.min(local.hi),
        })
    }
    pub(crate) fn same_history(&self, other: &Self) -> bool {
        self.time == other.time
            && self.output == other.output
            && self.gain == other.gain
            && self.tau == other.tau
            && self.projection == other.projection
            && self.prefix == other.prefix
            && match (&self.prior, &other.prior) {
                (None, None) => true,
                (Some(a), Some(b)) => Arc::ptr_eq(a, b) || (a.0.same_history(&b.0) && a.1 == b.1),
                _ => false,
            }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn zero_delay_event_retains_filter_integral_before_execution_representative() {
        let old = Transition::new(0., 0., 0.5, 0.5).unwrap();
        let initial = Filter::new(
            Projection {
                parent: 0,
                coefficient: I::ONE,
                constant: I::ZERO,
            },
            &old,
            &[1.],
            &[1., 0.25],
        )
        .unwrap();
        let window = I { lo: 1., hi: 1.001 };
        let mut changed = old.clone();
        changed
            .advance_at(window.hi, window, 1., I::ONE, true)
            .unwrap();
        let committed = initial
            .committed_change(&old, &changed, window.hi, window)
            .unwrap();
        let actual = committed.bounds(&changed, window.hi).unwrap();
        // Independent ramp response if the event occurred at the lower bound.
        let h = window.hi - window.lo;
        let expected = (h + 0.25 * (-h / 0.25).exp_m1()) / 0.5;
        assert!(expected > 0.);
        assert!(
            actual.lo <= expected && expected <= actual.hi,
            "missing pre-representative integral: {actual:?} vs {expected}"
        );
    }

    #[test]
    fn activation_prefix_encloses_signed_interrupted_ramps_and_past_queries() {
        for coefficient in [-2., 0.5] {
            for gain in [-1., 1.] {
                let mut old = Transition::new(0., 0., 2., 2.).unwrap();
                let initial = Filter::new(
                    Projection {
                        parent: 0,
                        coefficient: I::point(coefficient),
                        constant: I::point(0.125),
                    },
                    &old,
                    &[gain],
                    &[1., 0.25],
                )
                .unwrap();
                let history = initial.committed(&old, 0.5).unwrap();
                old.advance(0.5, 0.8).unwrap();
                let window = I { lo: 1., hi: 1.001 };
                let b = 1.002; // Execution can be later than the root bracket.
                let mut changed = old.clone();
                changed
                    .advance_at(b, window, -0.5, I::point(-0.5), true)
                    .unwrap();
                let committed = history.committed_change(&old, &changed, b, window).unwrap();
                let later = committed.committed(&changed, 1.25).unwrap();
                for t in [1., 1.0005, 1.001, b] {
                    let actual = committed.bounds(&changed, t).unwrap();
                    assert_eq!(actual, later.bounds(&changed, t).unwrap());
                    let range = committed.range(&changed, I { lo: 1., hi: b }).unwrap();
                    for tau in [window.lo, (window.lo + window.hi) / 2., window.hi] {
                        let before = t.min(tau) - 0.5;
                        let y0 = 0.4 * (before + 0.25 * (-before / 0.25).exp_m1());
                        let h = (t - tau).max(0.);
                        let g = -(-h / 0.25).exp_m1();
                        let y = y0 * (1. - g) + 0.4 * (tau - 0.5) * g - 0.65 * (h - 0.25 * g);
                        let expected = gain * (coefficient * y + 0.125);
                        assert!(
                            actual.lo <= expected && expected <= actual.hi,
                            "prefix at {t}, root {tau}: {actual:?} vs {expected}"
                        );
                        assert!(range.lo <= expected && expected <= range.hi);
                    }
                }
                let clone = committed.clone();
                let mut missing_prefix = committed.clone();
                missing_prefix.prefix = None;
                assert!(!clone.same_history(&missing_prefix));
                assert!(clone.same_history(&committed));
                assert!(committed
                    .committed_change(
                        &changed,
                        &old,
                        b + 0.01,
                        I {
                            lo: b - 0.001,
                            hi: b + 0.01
                        }
                    )
                    .is_err());
                assert!(clone.same_history(&committed));
            }
        }
    }

    #[test]
    fn delayed_edge_enclosure_covers_activation_rounding_and_uncertain_targets() {
        let mut parent = Transition::enclosed(
            0.25,
            I {
                lo: 0.25 - 1e-8,
                hi: 0.25 + 1e-8,
            },
            0.10005,
            0.5,
            0.5,
        )
        .unwrap();
        let initial = Filter::new(
            Projection {
                parent: 0,
                coefficient: I::ONE,
                constant: I::ZERO,
            },
            &parent,
            &[1.],
            &[1., 0.25],
        )
        .unwrap();
        let accepted = initial.committed(&parent, 1e6).unwrap();
        parent
            .advance_enclosed(
                1e6,
                0.75,
                I {
                    lo: 0.75 - 1e-8,
                    hi: 0.75 + 1e-8,
                },
                true,
            )
            .unwrap();
        let onset = parent.deadlines(1e6)[0].bounds;
        for time in [onset.lo, onset.hi, 1e6 + 0.3, 1e6 + 0.7] {
            let actual = accepted.bounds(&parent, time).unwrap();
            for start in [onset.lo, onset.hi] {
                for u0 in [0.25 - 1e-8, 0.25 + 1e-8] {
                    for u1 in [0.75 - 1e-8, 0.75 + 1e-8] {
                        let elapsed = (time - start).max(0.);
                        let h = elapsed.min(0.5);
                        let ramp = u0 + (u1 - u0) * (h + 0.25 * (-h / 0.25).exp_m1()) / 0.5;
                        let expected = if elapsed <= 0.5 {
                            ramp
                        } else {
                            u1 + (ramp - u1) * (-(elapsed - 0.5) / 0.25).exp()
                        };
                        assert!(
                            actual.lo <= expected && expected <= actual.hi,
                            "{time}: {actual:?}, {expected}"
                        );
                    }
                }
            }
        }
    }

    #[test]
    fn history_equivalence_includes_past_observation_state() {
        let parent = Transition::new(0.25, 0.125, 0.5, 0.5).unwrap();
        let initial = Filter::new(
            Projection {
                parent: 0,
                coefficient: I::ONE,
                constant: I::ZERO,
            },
            &parent,
            &[1.],
            &[1., 0.25],
        )
        .unwrap();
        let a = initial.committed(&parent, 1.).unwrap();
        let mut b = a.clone();
        let mut different_prior = initial.clone();
        different_prior.output = I::point(0.5);
        b.prior = Some(Arc::new((different_prior, parent.clone())));
        assert!(!a.same_history(&b));
        assert_ne!(
            a.bounds(&parent, 0.).unwrap(),
            b.bounds(&parent, 0.).unwrap()
        );
        assert!(a.same_history(&initial.committed(&parent, 1.).unwrap()));
    }
}
