//! Common immutable query and candidate-history interface for continuous solvers.
use super::*;
use crate::ir::Tolerances;

#[derive(Clone)]
pub(crate) enum Continuous {
    Linear(Box<LinearContinuous>),
    Nonlinear(Box<nonlinear::NonlinearContinuous>),
}

impl Continuous {
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
        }
    }
    pub(crate) fn is_continuous(&self, slot: usize) -> bool {
        match self {
            Self::Linear(v) => v.is_continuous(slot),
            Self::Nonlinear(_) => true,
        }
    }
    pub(crate) fn keeps_value_on_event(&self, slot: usize) -> Result<bool, Error> {
        let spec = match self {
            Self::Linear(v) => &v.context.program.operators[v.slots[slot].operator],
            Self::Nonlinear(v) => v.operator_spec(slot),
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
        }
    }
    pub(crate) fn event_bounds(&self, window: I) -> Result<Vec<I>, Error> {
        match self {
            Self::Linear(v) => v.event_bounds(window),
            Self::Nonlinear(v) => v.event_bounds(window),
        }
    }
    pub(crate) fn values(&self, time: f64) -> Result<Vec<f64>, Error> {
        self.bounds(time)?.into_iter().map(point_value).collect()
    }
    pub(crate) fn bounds(&self, time: f64) -> Result<Vec<I>, Error> {
        match self {
            Self::Linear(v) => v.bounds(time),
            Self::Nonlinear(v) => v.range_bounds(I::point(time)),
        }
    }
    pub(crate) fn range_bounds(&self, time: I) -> Result<Vec<I>, Error> {
        match self {
            Self::Linear(v) => v.range_bounds(time),
            Self::Nonlinear(v) => v.range_bounds(time),
        }
    }
    pub(crate) fn derivative_bounds(&self, time: I) -> Result<Vec<I>, Error> {
        match self {
            Self::Linear(v) => v.derivative_bounds(time),
            Self::Nonlinear(v) => v.derivative_bounds(time),
        }
    }
    pub(crate) fn next_breakpoint(&self, time: f64) -> Option<f64> {
        match self {
            Self::Linear(v) => v.next_breakpoint(time),
            Self::Nonlinear(v) => v.next_breakpoint(time),
        }
    }
    pub(crate) fn same_history(&self, other: &Self) -> bool {
        match (self, other) {
            (Self::Linear(a), Self::Linear(b)) => a.same_history(b),
            (Self::Nonlinear(a), Self::Nonlinear(b)) => a.same_history(b),
            _ => false,
        }
    }
    pub(crate) fn needs_extension(&self, horizon: f64) -> bool {
        match self {
            Self::Linear(_) => false,
            Self::Nonlinear(v) => v.certified_end() < horizon,
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
        }
    }
}
