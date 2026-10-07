//! Common immutable query and candidate-history interface for continuous solvers.
use super::*;
use crate::ir::Tolerances;

#[derive(Clone)]
pub(crate) enum Continuous {
    Linear(Box<LinearContinuous>),
    Nonlinear(Box<nonlinear::NonlinearContinuous>),
    Anchored(Box<Anchored>),
}

#[derive(Clone)]
pub(crate) struct Anchored {
    pub(crate) clock: crate::exact_time::Clock,
    pub(crate) inner: Continuous,
    prior: Continuous,
    start: f64,
    observation: Option<I>,
    cursor: f64,
}
impl Anchored {
    fn delta(&self, time: I) -> Result<I, Error> {
        let lo = self.clock.delta(time.lo).ok_or_else(|| {
            Error::new(
                "event_resolution",
                "local clock subtraction exceeds exact certificate",
            )
        })?;
        let hi = self.clock.delta(time.hi).ok_or_else(|| {
            Error::new(
                "event_resolution",
                "local clock subtraction exceeds exact certificate",
            )
        })?;
        Ok(I {
            lo: lo.lo,
            hi: hi.hi,
        })
    }
    fn restart(
        &self,
        time: f64,
        states: &[I],
        horizon: f64,
        map: bool,
    ) -> Result<Continuous, Error> {
        let observation = self.observation.ok_or_else(|| {
            Error::new(
                "event_resolution",
                "local event lacks an ordered physical observation certificate",
            )
        })?;
        let mut next = self.clone();
        next.prior = Continuous::Anchored(Box::new(self.clone()));
        next.start = time;
        next.cursor = observation.hi;
        next.observation = None;
        next.inner = if map {
            self.inner
                .mapped_event(observation.hi, observation, states)?
        } else {
            self.inner.restarted(
                observation.hi,
                observation,
                states,
                self.delta(I::point(horizon))?.hi,
            )?
        };
        // A reset observation remains frozen at its physical instant. Future
        // propagation becomes visible only when advanced_until closes the map.
        if map {
            next.observation = Some(observation);
        }
        Ok(Continuous::Anchored(Box::new(next)))
    }
}
impl Continuous {
    pub(crate) fn anchored(
        &self,
        clock: crate::exact_time::Clock,
        start: f64,
        horizon: f64,
    ) -> Result<Self, Error> {
        // Production anchor_event is gated by local_epoch().is_none(); an
        // existing local epoch remains immutable rather than being reanchored.
        if matches!(self, Self::Anchored(_)) {
            return Ok(self.clone());
        }
        let end = clock
            .delta(horizon)
            .ok_or_else(|| Error::new("event_resolution", "local clock horizon is uncertifiable"))?
            .hi;
        let inner = match self {
            Self::Linear(v) => Self::Linear(Box::new(v.local_from_seed(end)?)),
            Self::Nonlinear(v) => Self::Nonlinear(Box::new(v.local_from_seed(end)?)),
            Self::Anchored(_) => unreachable!(),
        };
        Ok(Self::Anchored(Box::new(Anchored {
            clock,
            inner,
            prior: self.clone(),
            start,
            observation: None,
            cursor: 0.,
        })))
    }
    pub(crate) fn has_local_observation(&self) -> bool {
        matches!(self,Self::Anchored(v) if v.observation.is_some())
    }
    pub(crate) fn local_epoch(&self) -> Option<(crate::exact_time::Clock, f64)> {
        let Self::Anchored(v) = self else {
            return None;
        };
        Some((v.clock, v.cursor))
    }
    pub(crate) fn local_range(&self, delta: I) -> Result<(Vec<I>, Vec<I>), Error> {
        let Self::Anchored(v) = self else {
            return Err(Error::new("event_resolution", "no local continuous epoch"));
        };
        Ok((
            v.inner.range_bounds(delta)?,
            v.inner.derivative_bounds(delta)?,
        ))
    }
    pub(crate) fn local_observation(&self, delta: I) -> Result<Self, Error> {
        let Self::Anchored(v) = self else {
            return Err(Error::new(
                "event_resolution",
                "no local physical event epoch",
            ));
        };
        if !delta.finite() || delta.lo < self.local_epoch().unwrap().1 || delta.lo > delta.hi {
            return Err(Error::new(
                "event_resolution",
                "local observation lacks causal order",
            ));
        }
        let mut next = v.clone();
        next.observation = Some(delta);
        Ok(Self::Anchored(next))
    }

    #[cfg(test)]
    pub(crate) fn new(
        program: &Program,
        trajectory: &Trajectory,
        driven: &[String],
        states: &[f64],
    ) -> Result<Option<Self>, Error> {
        Self::new_until(
            program,
            trajectory,
            driven,
            states,
            trajectory.config.stop,
            &Tolerances::default(),
        )
    }

    pub(crate) fn new_until(
        program: &Program,
        trajectory: &Trajectory,
        driven: &[String],
        states: &[f64],
        horizon: f64,
        tolerances: &Tolerances,
    ) -> Result<Option<Self>, Error> {
        if program.operators.iter().any(|op| matches!(op, OperatorSpec::Idt { input, .. } | OperatorSpec::LaplaceNd { input, .. } if affine_bounds::affine(input, program).is_err())) {
            return nonlinear::NonlinearContinuous::new_with_tolerances(program, trajectory, driven, states, horizon, tolerances).map(|v| Some(Self::Nonlinear(Box::new(v))));
        }
        LinearContinuous::new(program, trajectory, driven, states)
            .map(|v| v.map(|v| Self::Linear(Box::new(v))))
    }
    pub(crate) fn operator_value_index(&self, op: usize) -> Option<usize> {
        match self {
            Self::Linear(v) => v.operator_value_index(op),
            Self::Nonlinear(v) => v.operator_value_index(op),
            Self::Anchored(v) => v.inner.operator_value_index(op),
        }
    }
    pub(crate) fn is_continuous(&self, slot: usize) -> bool {
        match self {
            Self::Linear(v) => v.is_continuous(slot),
            Self::Nonlinear(_) => true,
            Self::Anchored(v) => v.inner.is_continuous(slot),
        }
    }
    pub(crate) fn keeps_value_on_event(&self, slot: usize) -> Result<bool, Error> {
        let spec = match self {
            Self::Linear(v) => &v.context.program.operators[v.slots[slot].operator],
            Self::Nonlinear(v) => v.operator_spec(slot),
            Self::Anchored(v) => return v.inner.keeps_value_on_event(slot),
        };
        Ok(match spec {
            OperatorSpec::Idt { reset, .. } => match self {
                Self::Linear(v) => !reset
                    .as_ref()
                    .map(|expression| {
                        crate::operators::ResetExpression::new(expression.clone())
                            .active(&v.parameters)
                    })
                    .transpose()?
                    .unwrap_or(false),
                Self::Nonlinear(v) => !v.reset_active(slot),
                Self::Anchored(_) => unreachable!(),
            },
            OperatorSpec::LaplaceNd {
                numerator,
                denominator,
                ..
            } => numerator.len() < denominator.len() || *numerator.last().unwrap() == 0.0,
            _ => false,
        })
    }
    pub(crate) fn changes_on_event(&self) -> bool {
        match self {
            Self::Linear(v) => v.changes_on_event(),
            Self::Nonlinear(v) => v.changes_on_event(),
            Self::Anchored(v) => v.inner.changes_on_event(),
        }
    }
    pub(crate) fn event_bounds(&self, window: I) -> Result<Vec<I>, Error> {
        match self {
            Self::Linear(v) => v.event_bounds(window),
            Self::Nonlinear(v) => v.event_bounds(window),
            Self::Anchored(v) => {
                if let Some(delta) = v.observation {
                    v.inner.event_bounds(delta)
                } else {
                    self.range_bounds(window)
                }
            }
        }
    }
    pub(crate) fn values(&self, time: f64) -> Result<Vec<f64>, Error> {
        self.bounds(time)?.into_iter().map(point_value).collect()
    }
    pub(crate) fn bounds(&self, time: f64) -> Result<Vec<I>, Error> {
        match self {
            Self::Linear(v) => v.bounds(time),
            Self::Nonlinear(v) => v.range_bounds(I::point(time)),
            Self::Anchored(v) => {
                if let Some(delta) = v.observation {
                    v.inner.event_bounds(delta)
                } else {
                    self.range_bounds(I::point(time))
                }
            }
        }
    }
    pub(crate) fn range_bounds(&self, time: I) -> Result<Vec<I>, Error> {
        match self {
            Self::Linear(v) => v.range_bounds(time),
            Self::Nonlinear(v) => v.range_bounds(time),
            Self::Anchored(v) => {
                let delta = v.delta(time)?;
                if delta.hi < v.cursor {
                    return v.prior.range_bounds(time);
                }
                if delta.lo < v.cursor {
                    return Err(Error::new(
                        "event_resolution",
                        "root query spans a local physical mode change",
                    ));
                }
                v.inner.range_bounds(delta)
            }
        }
    }
    pub(crate) fn derivative_bounds(&self, time: I) -> Result<Vec<I>, Error> {
        match self {
            Self::Linear(v) => v.derivative_bounds(time),
            Self::Nonlinear(v) => v.derivative_bounds(time),
            Self::Anchored(v) => {
                let delta = v.delta(time)?;
                if delta.hi < v.cursor {
                    return v.prior.derivative_bounds(time);
                }
                if delta.lo < v.cursor {
                    return Err(Error::new(
                        "event_resolution",
                        "derivative query spans a local physical mode change",
                    ));
                }
                v.inner.derivative_bounds(delta)
            }
        }
    }
    pub(crate) fn next_breakpoint(&self, time: f64) -> Option<f64> {
        match self {
            Self::Linear(v) => v.next_breakpoint(time),
            Self::Nonlinear(v) => v.next_breakpoint(time),
            Self::Anchored(_) => None,
        }
    }
    pub(crate) fn same_history(&self, other: &Self) -> bool {
        match (self, other) {
            (Self::Linear(a), Self::Linear(b)) => a.same_history(b),
            (Self::Nonlinear(a), Self::Nonlinear(b)) => a.same_history(b),
            (Self::Anchored(a), Self::Anchored(b)) => {
                a.clock == b.clock
                    && a.start == b.start
                    && a.cursor == b.cursor
                    && a.observation == b.observation
                    && a.inner.same_history(&b.inner)
                    && a.prior.same_history(&b.prior)
            }
            _ => false,
        }
    }
    pub(crate) fn needs_extension(&self, horizon: f64) -> bool {
        match self {
            Self::Linear(_) => false,
            Self::Nonlinear(v) => v.certified_end() < horizon,
            Self::Anchored(v) => v
                .delta(I::point(horizon))
                .map_or(true, |d| v.inner.needs_extension(d.hi)),
        }
    }
    pub(crate) fn restarted(
        &self,
        time: f64,
        bounds: I,
        states: &[I],
        horizon: f64,
    ) -> Result<Self, Error> {
        match self {
            Self::Linear(v) => v
                .restarted(time, bounds, states)
                .map(|v| Self::Linear(Box::new(v))),
            Self::Nonlinear(v) => v
                .restarted(time, bounds, states, horizon)
                .map(|v| Self::Nonlinear(Box::new(v))),
            Self::Anchored(v) => {
                // Without an event observation this is output replay or
                // horizon extension: states are held mode parameters, not
                // ODE initial conditions. Restart from the retained cursor.
                if v.observation.is_none() {
                    let mut next = v.clone();
                    let end = v.delta(I::point(horizon))?.hi;
                    let start = self.local_epoch().unwrap().1;
                    next.inner = v.inner.restarted(start, I::point(start), states, end)?;
                    return Ok(Self::Anchored(next));
                }
                v.restart(time, states, horizon, false)
            }
        }
    }
    pub(crate) fn mapped_event(&self, time: f64, bounds: I, states: &[I]) -> Result<Self, Error> {
        match self {
            Self::Linear(v) => v
                .mapped_event(time, bounds, states)
                .map(|v| Self::Linear(Box::new(v))),
            Self::Nonlinear(v) => v
                .mapped_event(time, bounds, states)
                .map(|v| Self::Nonlinear(Box::new(v))),
            Self::Anchored(v) => {
                // Actual event batches install observe_local permission
                // before reset closure. None here is an immutable output
                // replay, which must not apply a second physical reset.
                if v.observation.is_none() {
                    Ok(self.clone())
                } else {
                    v.restart(time, states, time, true)
                }
            }
        }
    }
}
