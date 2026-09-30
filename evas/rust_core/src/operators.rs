//! Instance/call-site operator histories. Clone with a candidate frame; never
//! derive history from output samples or mutate accepted state during a trial.
use crate::absdelay::AbsDelay;
use crate::events::{affine, AffineState};
use crate::idt::Idt;
use crate::idtmod::IdtMod;
use crate::interval::Interval as I;
use crate::ir::{Error, Expression, OperatorSpec, Origin, Program};
use crate::pwl::Trajectory;
use crate::slew::Slew;
use crate::transition::Transition;
use std::collections::BTreeSet;

/// Materialize the accepted continuous input definition at its semantic knots.
/// Dependency validation precedes all numerical binding, so zero coefficients
/// and algebraic cancellation cannot turn an internal input into a direct one.
fn direct_points(
    input: &Expression,
    program: &Program,
    trajectory: &Trajectory,
    driven: &[String],
    origin: &Origin,
) -> Result<(Vec<(f64, f64)>, Vec<I>), Error> {
    let expression = input;
    let input = affine(input, program, &origin.instance)?;
    let driven_nodes: Vec<_> = driven
        .iter()
        .map(|name| {
            program
                .nodes
                .iter()
                .position(|node| node == name)
                .ok_or_else(|| Error::new("invalid_inputs", "unknown directly driven node"))
        })
        .collect::<Result<_, _>>()?;
    if !input.state_dependencies.is_empty()
        || !input.operator_dependencies.is_empty()
        || input
            .node_dependencies
            .iter()
            .any(|node| *node != 0 && !driven_nodes.contains(node))
    {
        return Err(Error::new(
            "unsupported_operator",
            format!("waveform input must be affine in directly driven nodes and constants; internal nodes, state, nesting and feedback are unsupported at {}", origin.label()),
        ));
    }
    let coefficients = crate::affine_bounds::affine(expression, program)?;
    let mut nodes = vec![0.0; program.nodes.len()];
    let mut node_bounds = vec![I::ZERO; program.nodes.len()];
    let mut points = Vec::new();
    let mut bounds = Vec::new();
    for &time in &trajectory.knots {
        for ((&node, value), enclosure) in driven_nodes
            .iter()
            .zip(trajectory.values(time))
            .zip(trajectory.value_bounds(time))
        {
            nodes[node] = value;
            node_bounds[node] = enclosure;
        }
        points.push((time, input.value(&nodes, &[])?));
        bounds.push(
            coefficients
                .iter()
                .zip(&node_bounds)
                .filter(|(coefficient, _)| !coefficient.zero())
                .fold(*coefficients.last().unwrap(), |sum, (&a, &b)| sum + a * b),
        );
    }
    Ok((points, bounds))
}

#[derive(Clone)]
struct DirectInput {
    points: Vec<(f64, f64)>,
    bounds: Vec<I>,
}

impl DirectInput {
    fn new(points: Vec<(f64, f64)>, bounds: Vec<I>) -> Self {
        Self { points, bounds }
    }

    fn index(&self, time: f64) -> Result<usize, Error> {
        if !time.is_finite() || time < 0.0 || time > self.points.last().unwrap().0 {
            return Err(Error::new(
                "invalid_inputs",
                "direct function query must be within its finite source history",
            ));
        }
        Ok(self.points.partition_point(|(t, _)| *t < time))
    }

    fn value(&self, time: f64) -> Result<f64, Error> {
        let index = self.index(time)?;
        let (end_t, end_v) = self.points[index];
        if time == end_t {
            return Ok(end_v);
        }
        let (start_t, start_v) = self.points[index - 1];
        let f = (time - start_t) / (end_t - start_t);
        let value = start_v + f * (end_v - start_v);
        if !value.is_finite() {
            return Err(Error::new(
                "numerical_failure",
                "nonfinite direct function query",
            ));
        }
        Ok(value)
    }

    fn value_bounds(&self, time: f64) -> Result<I, Error> {
        let index = self.index(time)?;
        let (end_t, _) = self.points[index];
        if time == end_t {
            return Ok(self.bounds[index]);
        }
        let (start_t, _) = self.points[index - 1];
        let f = (I::point(time) - I::point(start_t)) / (I::point(end_t) - I::point(start_t));
        let bound = (I::ONE - f) * self.bounds[index - 1] + f * self.bounds[index];
        if !bound.finite() {
            return Err(Error::new(
                "waveform_accuracy",
                "nonfinite direct function enclosure",
            ));
        }
        Ok(bound)
    }

    fn next_breakpoint(&self, after: f64) -> Option<f64> {
        self.points
            .get(self.points.partition_point(|(t, _)| *t <= after))
            .map(|(t, _)| *t)
    }
}

#[derive(Clone)]
enum SinInput {
    Direct(DirectInput),
    Operator {
        operator: usize,
        coefficient: f64,
        constant: f64,
    },
}

#[derive(Clone)]
enum Runtime {
    Idt(Idt),
    IdtMod(IdtMod),
    Sin(SinInput),
    AbsDelay(AbsDelay),
    Transition {
        input: AffineState,
        input_bounds: Vec<I>,
        history: Transition,
    },
    Slew(Slew),
}

fn sin_bounds(input: I) -> Result<I, Error> {
    if !input.finite() {
        return Err(Error::new(
            "waveform_accuracy",
            "cannot bound nonfinite sine input",
        ));
    }
    let two_pi = 2.0 * std::f64::consts::PI;
    if input.hi - input.lo >= two_pi {
        return Ok(I { lo: -1.0, hi: 1.0 });
    }
    let mut lo = input.lo.sin().min(input.hi.sin()).next_down();
    let mut hi = input.lo.sin().max(input.hi.sin()).next_up();
    for (critical, value) in [
        (std::f64::consts::FRAC_PI_2, 1.0),
        (-std::f64::consts::FRAC_PI_2, -1.0),
    ] {
        let start = ((input.lo - critical) / two_pi).ceil() as i64;
        let end = ((input.hi - critical) / two_pi).floor() as i64;
        if start <= end {
            if value > 0.0 {
                hi = 1.0;
            } else {
                lo = -1.0;
            }
        }
    }
    Ok(I { lo, hi })
}

#[derive(Clone, Default)]
pub(crate) struct Operators {
    entries: Vec<Runtime>,
}

impl Operators {
    pub(crate) fn new(
        program: &Program,
        trajectory: &Trajectory,
        driven: &[String],
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
                OperatorSpec::Idt { input, ic, origin } => {
                    let (points, bounds) =
                        direct_points(input, program, trajectory, driven, origin)?;
                    entries.push(Runtime::Idt(Idt::enclosed(points, bounds, *ic)?));
                }
                OperatorSpec::IdtMod {
                    input,
                    ic,
                    modulus,
                    offset,
                    origin,
                } => {
                    let (points, bounds) =
                        direct_points(input, program, trajectory, driven, origin)?;
                    entries.push(Runtime::IdtMod(IdtMod::enclosed(
                        points, bounds, *ic, *modulus, *offset,
                    )?));
                }
                OperatorSpec::Sin { input, origin } => {
                    let bound_input = affine(input, program, &origin.instance)?;
                    let sin_input = if let Some((operator, coefficient, constant)) =
                        bound_input.single_operator_form()
                    {
                        if operator >= entries.len()
                            || coefficient == 0.0
                            || !coefficient.is_finite()
                            || !constant.is_finite()
                        {
                            return Err(Error::new(
                                "unsupported_operator",
                                "sin operator input must reference one earlier operator with finite affine coefficients",
                            ));
                        }
                        SinInput::Operator {
                            operator,
                            coefficient,
                            constant,
                        }
                    } else {
                        let (points, bounds) =
                            direct_points(input, program, trajectory, driven, origin)?;
                        SinInput::Direct(DirectInput::new(points, bounds))
                    };
                    entries.push(Runtime::Sin(sin_input));
                }
                OperatorSpec::AbsDelay {
                    input,
                    delay,
                    origin,
                } => {
                    let (points, bounds) =
                        direct_points(input, program, trajectory, driven, origin)?;
                    entries.push(Runtime::AbsDelay(AbsDelay::enclosed(
                        points, bounds, *delay,
                    )?));
                }
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
                OperatorSpec::Slew {
                    input,
                    rise,
                    fall,
                    origin,
                } => {
                    let (points, bounds) =
                        direct_points(input, program, trajectory, driven, origin)?;
                    entries.push(Runtime::Slew(Slew::enclosed(points, bounds, *rise, *fall)?));
                }
            }
        }
        Ok(Self { entries })
    }

    pub(crate) fn values(&self, time: f64) -> Result<Vec<f64>, Error> {
        self.entries.iter().try_fold(
            Vec::<f64>::with_capacity(self.entries.len()),
            |mut values, entry| {
                let value = match entry {
                    Runtime::Idt(history) => history.value(time)?,
                    Runtime::IdtMod(history) => history.value(time)?,
                    Runtime::Sin(input) => match input {
                        SinInput::Direct(source) => source.value(time)?.sin(),
                        SinInput::Operator {
                            operator,
                            coefficient,
                            constant,
                        } => (*constant + *coefficient * values[*operator]).sin(),
                    },
                    Runtime::AbsDelay(history) => history.value(time)?,
                    Runtime::Transition { history, .. } => history.value(time)?,
                    Runtime::Slew(history) => history.value(time)?,
                };
                if !value.is_finite() {
                    return Err(Error::new("numerical_failure", "nonfinite operator value"));
                }
                values.push(value);
                Ok(values)
            },
        )
    }

    pub(crate) fn next_breakpoint(&self, after: f64) -> Option<f64> {
        self.entries
            .iter()
            .filter_map(|entry| match entry {
                Runtime::Idt(history) => history.next_breakpoint(after),
                Runtime::IdtMod(history) => history.next_breakpoint(after),
                Runtime::Sin(SinInput::Direct(source)) => source.next_breakpoint(after),
                Runtime::Sin(SinInput::Operator { .. }) => None,
                Runtime::AbsDelay(history) => history.next_breakpoint(after),
                Runtime::Transition { history, .. } => history.next_breakpoint(after),
                Runtime::Slew(history) => history.next_breakpoint(after),
            })
            .min_by(f64::total_cmp)
    }

    pub(crate) fn bounds(&self, time: f64) -> Result<Vec<I>, Error> {
        self.entries.iter().try_fold(
            Vec::<I>::with_capacity(self.entries.len()),
            |mut bounds, entry| {
                let bound = match entry {
                    Runtime::Idt(history) => history.value_bounds(time)?,
                    Runtime::IdtMod(history) => history.value_bounds(time)?,
                    Runtime::Sin(input) => match input {
                        SinInput::Direct(source) => sin_bounds(source.value_bounds(time)?)?,
                        SinInput::Operator {
                            operator,
                            coefficient,
                            constant,
                        } => {
                            let input = match &self.entries[*operator] {
                                Runtime::IdtMod(history) => {
                                    I::point(*constant)
                                        + I::point(*coefficient) * history.raw_value_bounds(time)?
                                }
                                _ => {
                                    I::point(*constant) + I::point(*coefficient) * bounds[*operator]
                                }
                            };
                            sin_bounds(input)?
                        }
                    },
                    Runtime::Slew(history) => history.value_bounds(time),
                    Runtime::AbsDelay(history) => history.value_bounds(time),
                    Runtime::Transition { history, .. } => history.value_bounds(time)?,
                };
                bounds.push(bound);
                Ok(bounds)
            },
        )
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
                Runtime::Idt(_) => Vec::new(),
                Runtime::IdtMod(_) => Vec::new(),
                Runtime::Sin(_) => Vec::new(),
                Runtime::AbsDelay(_) => Vec::new(),
                Runtime::Transition { history, .. } => history.deadlines(after),
                Runtime::Slew(_) => Vec::new(),
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
                Runtime::Idt(_) => {}
                Runtime::IdtMod(_) => {}
                Runtime::Sin(_) => {}
                Runtime::AbsDelay(_) => {}
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
                Runtime::Slew(_) => {}
            }
        }
        Ok(())
    }
}
