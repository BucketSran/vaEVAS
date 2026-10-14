//! Feed-forward integration of accepted piecewise affine transition history.
//! Queries predict on private clones; commits retain the forcing for past queries.
use super::transition_filter::Projection;
use crate::interval::Interval as I;
use crate::ir::Error;
use crate::transition::Transition;
use std::sync::Arc;

#[derive(Clone)]
pub(crate) struct Integral {
    time: f64,
    output: I,
    projection: Projection,
    prior: Option<Arc<(Integral, Transition)>>,
    prefix: Option<ActivationPrefix>,
}

#[derive(Clone, Copy, PartialEq)]
struct ActivationPrefix {
    start: f64,
    end: f64,
    initial: I,
    forcing: I,
}

impl ActivationPrefix {
    fn bounds(&self, times: I) -> I {
        self.initial + self.forcing * (times - I::point(self.start))
    }
}

impl Integral {
    pub(crate) fn reinitialized(&self, ic: f64) -> Result<Self, Error> {
        Self::new(self.projection, ic)
    }

    pub(crate) fn new(projection: Projection, ic: f64) -> Result<Self, Error> {
        if !ic.is_finite() {
            return Err(Error::new(
                "invalid_ir",
                "nonfinite transition integral initial value",
            ));
        }
        Ok(Self {
            time: 0.,
            output: I::point(ic),
            projection,
            prior: None,
            prefix: None,
        })
    }

    pub(crate) fn reaches_deadline(&self, parent: &Transition, time: f64) -> bool {
        parent.next_breakpoint(self.time).is_some_and(|t| t <= time)
    }

    fn predicted(&self, parent: &Transition, time: f64) -> Result<Self, Error> {
        if !time.is_finite() || time < self.time {
            return Err(Error::new(
                "event_resolution",
                "integral query precedes its accepted history",
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
            let p = next.projection;
            let area = if forcing.forcing_uncertain(next.time) {
                (p.coefficient
                    * forcing.forcing_range(I {
                        lo: next.time,
                        hi: end,
                    })
                    + p.constant)
                    * h
            } else {
                let (input, slope) = forcing.forcing_line(next.time);
                (p.coefficient * input + p.constant) * h
                    + p.coefficient * slope * h * h * I::point(0.5)
            };
            next.output = next.output + area;
            if !next.output.finite() {
                return Err(Error::new(
                    "waveform_accuracy",
                    "nonfinite transition/integral history",
                ));
            }
            next.time = end;
            forcing.advance_time(end)?;
        }
        Ok(next)
    }

    fn committed(&self, parent: &Transition, time: f64) -> Result<Self, Error> {
        if time == self.time {
            return Ok(self.clone());
        }
        let mut next = self.predicted(parent, time)?;
        next.prior = Some(Arc::new((self.clone(), parent.clone())));
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
                    "transition/integral activation overlaps committed history",
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
                forcing: p.coefficient * old.forcing_range(times).hull(new.forcing_range(times))
                    + p.constant,
            };
            next.output = prefix.bounds(I::point(time));
            if !next.output.finite() {
                return Err(Error::new(
                    "waveform_accuracy",
                    "nonfinite integral activation prefix",
                ));
            }
            next.prefix = Some(prefix);
        }
        Ok(next)
    }

    pub(crate) fn bounds(&self, parent: &Transition, time: f64) -> Result<I, Error> {
        if let Some(prefix) = &self.prefix {
            if time >= prefix.start && time <= prefix.end {
                return Ok(prefix.bounds(I::point(time)));
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
                let mut result = prefix.bounds(I {
                    lo: time.lo.max(prefix.start),
                    hi: time.hi.min(prefix.end),
                });
                if time.lo < prefix.start {
                    let prior = self.prior.as_ref().ok_or_else(|| {
                        Error::new(
                            "event_resolution",
                            "integral activation prefix has no prior history",
                        )
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
                    "integral observation precedes retained history",
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
        Ok(initial + input * (time - I::point(time.lo)))
    }

    pub(crate) fn same_history(&self, other: &Self) -> bool {
        self.time == other.time
            && self.output == other.output
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

    fn projection(coefficient: f64, constant: f64) -> Projection {
        Projection {
            parent: 0,
            coefficient: I::point(coefficient),
            constant: I::point(constant),
        }
    }

    #[test]
    fn interrupted_area_preserves_original_fall_slope_and_past_history() {
        let idle = Transition::new(0., 0., 0.5, 1.).unwrap();
        let initial = Integral::new(projection(1., 0.), 0.1).unwrap();
        let mut rising = idle.clone();
        rising.advance(1., 1.).unwrap();
        let at_rise = initial
            .committed_change(&idle, &rising, 1., I::point(1.))
            .unwrap();
        let mut falling = rising.clone();
        falling.advance(1.25, 0.).unwrap();
        let at_fall = at_rise
            .committed_change(&rising, &falling, 1.25, I::point(1.25))
            .unwrap();
        let final_history = at_fall.committed(&falling, 2.).unwrap();
        for time in [1.75, 2., 3.] {
            let area = final_history.bounds(&falling, time).unwrap();
            // Triangle areas are .5*.25*.5 and .5*.5*.5.
            assert!(area.lo <= 0.2875 && 0.2875 <= area.hi, "{area:?}");
            assert!(area.hi - area.lo < 1e-12);
        }
        for time in [0., 1., 1.125, 1.25] {
            assert_eq!(
                at_fall.bounds(&falling, time).unwrap(),
                final_history.bounds(&falling, time).unwrap()
            );
        }
        assert!(at_fall.same_history(&at_fall.clone()));
        let mut changed_prior = at_fall.clone();
        changed_prior.prior = Some(Arc::new((
            Integral::new(projection(1., 0.), 0.2).unwrap(),
            idle,
        )));
        assert!(!at_fall.same_history(&changed_prior));
    }

    #[test]
    fn physical_to_execution_prefix_propagates_signed_area_without_reset() {
        for coefficient in [-2., 0.5] {
            let idle = Transition::new(0., 0., 0.5, 1.).unwrap();
            let initial = Integral::new(projection(coefficient, 0.125), 0.1).unwrap();
            let window = I { lo: 1., hi: 1.001 };
            let execution = 1.002;
            let mut rising = idle.clone();
            rising
                .advance_at(execution, window, 1., I::ONE, true)
                .unwrap();
            let history = initial
                .committed_change(&idle, &rising, execution, window)
                .unwrap();
            let later = history.committed(&rising, 1.75).unwrap();
            for time in [1., 1.0005, 1.001, execution, 1.25, 1.75, 2.] {
                let area = history.bounds(&rising, time).unwrap();
                let after_commit = later.bounds(&rising, time).unwrap();
                if time <= 1.75 {
                    assert_eq!(area, after_commit);
                }
                for root in [window.lo, (window.lo + window.hi) * 0.5, window.hi] {
                    let h = (time - root).max(0.);
                    let ramp_area = if h <= 0.5 { h * h } else { h - 0.25 };
                    let expected = 0.1 + 0.125 * time + coefficient * ramp_area;
                    assert!(
                        area.lo <= expected && expected <= area.hi,
                        "time {time}, root {root}: {area:?} vs {expected}"
                    );
                    assert!(after_commit.lo <= expected && expected <= after_commit.hi);
                    let range = history.range(&rising, I { lo: 1., hi: 2. }).unwrap();
                    assert!(range.lo <= expected && expected <= range.hi);
                }
            }
            let clone = history.clone();
            assert!(history
                .committed_change(
                    &rising,
                    &idle,
                    1.8,
                    I {
                        lo: execution - 0.001,
                        hi: 1.8
                    }
                )
                .is_err());
            assert!(clone.same_history(&history));
        }
    }

    #[test]
    fn uncertain_target_and_delayed_activation_are_retained_in_future_area() {
        let mut parent =
            Transition::enclosed(0.25, I { lo: 0.24, hi: 0.26 }, 0.10005, 0.5, 0.5).unwrap();
        let initial = Integral::new(projection(-2., 0.125), 0.1).unwrap();
        let history = initial.committed(&parent, 1e6).unwrap();
        parent
            .advance_enclosed(1e6, 0.75, I { lo: 0.74, hi: 0.76 }, true)
            .unwrap();
        let onset = parent.deadlines(1e6)[0].bounds;
        for time in [onset.lo, onset.hi, 1e6 + 0.3, 1e6 + 0.7] {
            let area = history.bounds(&parent, time).unwrap();
            for start in [onset.lo, onset.hi] {
                for u0 in [0.24, 0.26] {
                    for u1 in [0.74, 0.76] {
                        let elapsed = (time - start).max(0.);
                        let h = elapsed.min(0.5);
                        let input_area =
                            u0 * time + (u1 - u0) * h * h + (u1 - u0) * (elapsed - 0.5).max(0.);
                        let expected = 0.1 + 0.125 * time - 2. * input_area;
                        assert!(
                            area.lo <= expected && expected <= area.hi,
                            "{area:?} vs {expected}"
                        );
                    }
                }
            }
        }
    }
}
