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
            Self::Linear(v) => {
                validate_event_bodies(&v.context.program, v.changes_on_event(), window, events)
            }
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

pub(super) fn validate_event_bodies(
    program: &Program,
    event_dependent: bool,
    window: I,
    events: &[usize],
) -> Result<(), Error> {
    if event_dependent && window.lo != window.hi {
        // Settlement certifies samples/conditions at the representative time,
        // not over the actual event window. This obligation is independent of
        // the continuous solver and of whether a parameter value changes.
        for &id in events {
            let event = &program.events[id];
            if time_sensitive_body(&event.body, program, &event.origin.instance)? {
                return Err(Error::new("event_resolution", "uncertain continuous restart cannot certify event sampling or input-dependent branches over its time window"));
            }
        }
    }
    Ok(())
}

fn time_sensitive_body(
    body: &[crate::ir::Statement],
    program: &Program,
    owner: &str,
) -> Result<bool, Error> {
    let reads_time = |expr| {
        let dependencies = crate::events::affine(expr, program, owner)?;
        Ok::<_, Error>(
            !dependencies.node_dependencies.is_empty()
                || !dependencies.operator_dependencies.is_empty(),
        )
    };
    for statement in body {
        match statement {
            crate::ir::Statement::Assign(a) if reads_time(&a.rhs)? => return Ok(true),
            crate::ir::Statement::If {
                left,
                right,
                then_body,
                else_body,
                ..
            } if reads_time(left)?
                || reads_time(right)?
                || time_sensitive_body(then_body, program, owner)?
                || time_sensitive_body(else_body, program, owner)? =>
            {
                return Ok(true);
            }
            _ => {}
        }
    }
    Ok(false)
}
