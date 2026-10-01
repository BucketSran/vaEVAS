//! Common immutable query and candidate-history interface for continuous solvers.
use super::*;

#[derive(Clone)]
pub(crate) enum Continuous {
    Linear(Box<LinearContinuous>),
    Nonlinear(Box<nonlinear::NonlinearContinuous>),
}

impl Continuous {
    pub(crate) fn new(
        program: &Program,
        trajectory: &Trajectory,
        driven: &[String],
        states: &[f64],
    ) -> Result<Option<Self>, Error> {
        if program.operators.iter().any(|op| matches!(op, OperatorSpec::Idt { input, .. } if affine_bounds::affine(input, program).is_err())) {
            return nonlinear::NonlinearContinuous::new(program, trajectory, driven, states).map(|v| Some(Self::Nonlinear(Box::new(v))));
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
    pub(crate) fn changes_on_event(&self) -> bool {
        match self {
            Self::Linear(v) => v.changes_on_event(),
            Self::Nonlinear(v) => v.changes_on_event(),
        }
    }
    pub(crate) fn validate_event_window(&self, window: I, events: &[usize]) -> Result<(), Error> {
        match self {
            Self::Linear(_) => Ok(()),
            Self::Nonlinear(v) => v.validate_event_window(window, events),
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
    pub(crate) fn restarted(&self, time: f64, bounds: I, states: &[I]) -> Result<Self, Error> {
        match self {
            Self::Linear(v) => v
                .restarted(time, bounds, states)
                .map(|v| Self::Linear(Box::new(v))),
            Self::Nonlinear(v) => v
                .restarted(time, bounds, states)
                .map(|v| Self::Nonlinear(Box::new(v))),
        }
    }
}
