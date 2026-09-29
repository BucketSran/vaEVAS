//! Instance/call-site operator histories. Clone with a candidate frame; never
//! derive history from output samples or mutate accepted state during a trial.
use crate::events::{affine, AffineState};
use crate::interval::Interval as I;
use crate::ir::{Error, OperatorSpec, Program};
use crate::pwl::Trajectory;
use crate::transition::Transition;
use std::collections::BTreeSet;

#[derive(Clone)]
enum Runtime {
    Transition {
        input: AffineState,
        history: Transition,
    },
}

#[derive(Clone, Default)]
pub(crate) struct Operators {
    entries: Vec<Runtime>,
}

impl Operators {
    pub(crate) fn new(
        program: &Program,
        _trajectory: &Trajectory,
        _driven: &[String],
        states: &[f64],
    ) -> Result<Self, Error> {
        let mut identities = BTreeSet::new();
        let mut entries = Vec::new();
        for spec in &program.operators {
            let origin = spec.origin();
            if origin.instance.is_empty()
                || origin.source.is_empty()
                || origin.line == 0
                || origin.column == 0
                || !program
                    .contributions
                    .iter()
                    .any(|c| c.origin.instance == origin.instance)
                || !identities.insert((
                    origin.instance.clone(),
                    origin.source.clone(),
                    origin.line,
                    origin.column,
                ))
            {
                return Err(Error::new(
                    "invalid_ir",
                    "invalid or duplicate operator call-site identity",
                ));
            }
            match spec {
                OperatorSpec::Transition {
                    input,
                    delay,
                    rise,
                    fall,
                    origin,
                } => {
                    let input = affine(input, program, &origin.instance)?;
                    if !input.node_dependencies.is_empty()
                        || !input.operator_dependencies.is_empty()
                    {
                        return Err(Error::new("unsupported_operator", "transition input must be affine in instance state and constants; nesting and voltage inputs are unsupported"));
                    }
                    let initial = input.value(&[], states)?;
                    entries.push(Runtime::Transition {
                        input,
                        history: Transition::new(initial, *delay, *rise, *fall)?,
                    });
                }
            }
        }
        Ok(Self { entries })
    }

    pub(crate) fn values(&self, time: f64) -> Result<Vec<f64>, Error> {
        self.entries
            .iter()
            .map(|entry| match entry {
                Runtime::Transition { history, .. } => history.value(time),
            })
            .collect()
    }

    pub(crate) fn next_breakpoint(&self, after: f64) -> Option<f64> {
        self.entries
            .iter()
            .filter_map(|entry| match entry {
                Runtime::Transition { history, .. } => history.next_breakpoint(after),
            })
            .min_by(f64::total_cmp)
    }

    pub(crate) fn check_deadline_order(
        &self,
        after: f64,
        next_event: Option<I>,
    ) -> Result<(), Error> {
        let deadlines: Vec<_> = self
            .entries
            .iter()
            .flat_map(|entry| match entry {
                Runtime::Transition { history, .. } => history.deadlines(after),
            })
            .collect();
        for (index, deadline) in deadlines.iter().enumerate() {
            if next_event.is_some_and(|event| {
                deadline.overlaps(event) && !(event.lo == event.hi && event == deadline.bounds)
            }) {
                return Err(Error::new(
                    "event_resolution",
                    "cannot certify transition deadline ordering relative to user event",
                ));
            }
            for other in &deadlines[index + 1..] {
                if deadline.overlaps(other.bounds) && !deadline.coincides(other) {
                    return Err(Error::new(
                        "event_resolution",
                        "cannot certify ordering of operator deadlines",
                    ));
                }
            }
        }
        Ok(())
    }

    pub(crate) fn advance(&mut self, time: f64, states: &[f64]) -> Result<(), Error> {
        for entry in &mut self.entries {
            match entry {
                Runtime::Transition { input, history } => {
                    history.advance(time, input.value(&[], states)?)?
                }
            }
        }
        Ok(())
    }
}
