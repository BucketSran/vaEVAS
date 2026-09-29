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
        input_bounds: Vec<I>,
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
                    // Validate raw state/operator references before interval indexing.
                    let bound_input = affine(input, program, &origin.instance)?;
                    if !bound_input.node_dependencies.is_empty()
                        || !bound_input.operator_dependencies.is_empty()
                    {
                        return Err(Error::new("unsupported_operator", "transition input must be affine in instance state and constants; nesting and voltage inputs are unsupported"));
                    }
                    let row = crate::affine_bounds::affine(input, program)?;
                    let input_bounds: Vec<_> = row
                        [program.nodes.len()..program.nodes.len() + program.states.len()]
                        .iter()
                        .copied()
                        .chain([*row.last().unwrap()])
                        .collect();
                    let input = bound_input;
                    let initial = input.value(&[], states)?;
                    let bounds = input_bounds
                        .iter()
                        .zip(states.iter().copied().map(I::point).chain([I::ONE]))
                        .fold(I::ZERO, |sum, (&a, b)| sum + a * b);
                    entries.push(Runtime::Transition {
                        input,
                        input_bounds,
                        history: Transition::enclosed(initial, bounds, *delay, *rise, *fall)?,
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

    pub(crate) fn bounds(&self, time: f64) -> Result<Vec<I>, Error> {
        self.entries
            .iter()
            .map(|entry| match entry {
                Runtime::Transition { history, .. } => history.value_bounds(time),
            })
            .collect()
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

    pub(crate) fn advance(
        &mut self,
        time: f64,
        states: &[f64],
        bounds: &[I],
        changed: &[usize],
    ) -> Result<(), Error> {
        for entry in &mut self.entries {
            match entry {
                Runtime::Transition {
                    input,
                    input_bounds,
                    history,
                } => {
                    let bounds = input_bounds
                        .iter()
                        .zip(bounds.iter().copied().chain([I::ONE]))
                        .fold(I::ZERO, |sum, (&a, b)| sum + a * b);
                    let may_change = changed.iter().any(|s| input.state_dependencies.contains(s));
                    history.advance_enclosed(time, input.value(&[], states)?, bounds, may_change)?
                }
            }
        }
        Ok(())
    }
}
