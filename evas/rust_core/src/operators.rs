//! Instance/call-site operator histories. Clone with a candidate frame; never
//! derive history from output samples or mutate accepted state during a trial.
use crate::absdelay::AbsDelay;
use crate::events::{affine, AffineState};
use crate::idt::Idt;
use crate::interval::{equal_products, sum_products_sign, Interval as I};
use crate::ir::{Error, Expression, OperatorSpec, Origin, Program};
use crate::pwl::Trajectory;
use crate::slew::Slew;
use crate::transition::Transition;
use std::collections::BTreeSet;

type DirectPoints = (Vec<(f64, f64)>, Vec<I>);

/// Materialize the accepted continuous input definition at its semantic knots.
/// Dependency validation precedes all numerical binding, so zero coefficients
/// and algebraic cancellation cannot turn an internal input into a direct one.
fn direct_points(
    input: &Expression,
    program: &Program,
    trajectory: &Trajectory,
    driven: &[String],
    origin: &Origin,
) -> Result<DirectPoints, Error> {
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
enum Runtime {
    Idt {
        history: Idt,
        reset: Option<ResetExpression>,
    },
    AbsDelay(AbsDelay),
    Transition {
        input: AffineState,
        input_bounds: Vec<I>,
        history: Box<Transition>,
    },
    Slew(Slew),
}

#[derive(Clone)]
struct ResetExpression {
    expression: Expression,
}

#[derive(Default)]
struct ResetTerms {
    constants: Vec<(f64, bool)>,
    states: Vec<(usize, f64, bool)>,
}

fn exact_add(a: f64, b: f64) -> Option<f64> {
    let value = a + b;
    if !value.is_finite() {
        return None;
    }
    let virtual_b = value - a;
    let error = (a - (value - virtual_b)) + (b - virtual_b); // TwoSum
    (error == 0.0).then_some(value)
}

impl ResetTerms {
    fn scale(mut self, factor: (f64, bool)) -> Result<Self, Error> {
        if !factor.0.is_finite() {
            return Err(Error::new(
                "nonfinite_arithmetic",
                "nonfinite idt reset coefficient",
            ));
        }
        for (value, exact) in &mut self.constants {
            let product = *value * factor.0;
            *exact = *exact && factor.1 && equal_products(*value, factor.0, product, 1.0);
            *value = product;
        }
        for (_, coefficient, exact) in &mut self.states {
            let product = *coefficient * factor.0;
            *exact = *exact && factor.1 && equal_products(*coefficient, factor.0, product, 1.0);
            *coefficient = product;
        }
        if self
            .constants
            .iter()
            .map(|(v, _)| v)
            .chain(self.states.iter().map(|(_, c, _)| c))
            .any(|v| !v.is_finite())
        {
            return Err(Error::new(
                "nonfinite_arithmetic",
                "nonfinite idt reset coefficient",
            ));
        }
        Ok(self)
    }

    fn append(&mut self, mut other: Self) {
        self.constants.append(&mut other.constants);
        self.states.append(&mut other.states);
    }

    fn has_state(&self) -> bool {
        !self.states.is_empty()
    }

    fn constant_value(&self) -> Result<(f64, bool), Error> {
        let mut value = 0.0;
        let mut exact = true;
        for &(constant, constant_exact) in &self.constants {
            if !constant.is_finite() {
                return Err(Error::new(
                    "nonfinite_arithmetic",
                    "nonfinite idt reset constant",
                ));
            }
            match exact_add(value, constant) {
                Some(sum) => value = sum,
                None => {
                    value += constant;
                    exact = false;
                }
            }
            exact &= constant_exact;
        }
        if value.is_finite() {
            Ok((value, exact))
        } else {
            Err(Error::new(
                "nonfinite_arithmetic",
                "nonfinite idt reset constant",
            ))
        }
    }
}

impl ResetExpression {
    fn new(expression: Expression) -> Self {
        Self { expression }
    }

    fn active(&self, states: &[I]) -> Result<bool, Error> {
        let terms = reset_terms(&self.expression)?;
        let bound = match reset_exact_sign(&terms, states)? {
            Some(sign) => sign,
            None => reset_interval(&self.expression, states)?,
        };
        reset_active(bound)
    }
}

fn reset_terms(expr: &Expression) -> Result<ResetTerms, Error> {
    let mut result = ResetTerms::default();
    match expr {
        Expression::Affine { constant, terms } => {
            if !constant.is_finite() || !terms.is_empty() {
                return Err(Error::new(
                    "unsupported_operator",
                    "idt reset must be affine in instance state and constants",
                ));
            }
            result.constants.push((*constant, true));
        }
        Expression::State { state } => result.states.push((*state, 1.0, true)),
        Expression::Operator { .. } => {
            return Err(Error::new(
                "unsupported_operator",
                "idt reset cannot depend on operator history",
            ))
        }
        Expression::Add { left, right } => {
            result = reset_terms(left)?;
            result.append(reset_terms(right)?);
        }
        Expression::Multiply { left, right } => {
            let left_terms = reset_terms(left)?;
            let right_terms = reset_terms(right)?;
            if left_terms.has_state() && right_terms.has_state() {
                return Err(Error::new(
                    "unsupported_operator",
                    "idt reset must be affine in instance state and constants",
                ));
            }
            result = if left_terms.has_state() {
                left_terms.scale(right_terms.constant_value()?)?
            } else {
                right_terms.scale(left_terms.constant_value()?)?
            };
        }
        Expression::Power { .. } | Expression::Select { .. } => {
            return Err(Error::new(
                "unsupported_operator",
                "idt reset must be affine in instance state and constants",
            ))
        }
    }
    Ok(result)
}

fn reset_exact_sign(terms: &ResetTerms, states: &[I]) -> Result<Option<I>, Error> {
    let mut exact_terms: Vec<(f64, f64)> = Vec::new();
    for &(constant, exact) in &terms.constants {
        if !exact {
            return Ok(None);
        }
        exact_terms.push((constant, 1.0));
    }
    for &(state, coefficient, exact) in &terms.states {
        if !exact {
            return Ok(None);
        }
        let Some(value) = states.get(state) else {
            return Err(Error::new(
                "invalid_ir",
                "idt reset state index out of range",
            ));
        };
        if value.lo != value.hi {
            return Ok(None);
        }
        exact_terms.push((coefficient, value.lo));
    }
    if exact_terms.len() > 4 {
        return Ok(None);
    }
    Ok(sum_products_sign(&exact_terms).map(|sign| match sign {
        -1 => I::point(-1.0),
        0 => I::ZERO,
        1 => I::ONE,
        _ => unreachable!(),
    }))
}

fn reset_interval(expr: &Expression, states: &[I]) -> Result<I, Error> {
    let value = match expr {
        Expression::Affine { constant, terms } => {
            if !constant.is_finite() || !terms.is_empty() {
                return Err(Error::new(
                    "unsupported_operator",
                    "idt reset must be affine in instance state and constants",
                ));
            }
            I::point(*constant)
        }
        Expression::State { state } => *states
            .get(*state)
            .ok_or_else(|| Error::new("invalid_ir", "idt reset state index out of range"))?,
        Expression::Operator { .. } => {
            return Err(Error::new(
                "unsupported_operator",
                "idt reset cannot depend on operator history",
            ))
        }
        Expression::Add { left, right } => {
            reset_interval(left, states)? + reset_interval(right, states)?
        }
        Expression::Multiply { left, right } => {
            let left_value = reset_interval(left, states)?;
            let right_value = reset_interval(right, states)?;
            left_value * right_value
        }
        Expression::Power { .. } | Expression::Select { .. } => {
            return Err(Error::new(
                "unsupported_operator",
                "idt reset must be affine in instance state and constants",
            ))
        }
    };
    if value.finite() {
        Ok(value)
    } else {
        Err(Error::new(
            "nonfinite_arithmetic",
            "nonfinite idt reset expression bounds",
        ))
    }
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
                OperatorSpec::Idt {
                    input,
                    ic,
                    reset,
                    origin,
                } => {
                    let (points, bounds) =
                        direct_points(input, program, trajectory, driven, origin)?;
                    let reset = reset
                        .as_ref()
                        .map(|expr| {
                            let reset = affine(expr, program, &origin.instance)?;
                            if !reset.node_dependencies.is_empty()
                                || !reset.operator_dependencies.is_empty()
                            {
                                return Err(Error::new(
                                    "unsupported_operator",
                                    format!(
                                        "idt reset must be affine in instance state and constants at {}",
                                        origin.label()
                                    ),
                                ));
                            }
                            Ok(ResetExpression::new(expr.clone()))
                        })
                        .transpose()?;
                    let mut history = Idt::enclosed(points, bounds, *ic)?;
                    if let Some(reset) = &reset {
                        let state_bounds: Vec<_> = states.iter().copied().map(I::point).collect();
                        history = history.with_reset(reset.active(&state_bounds)?);
                    }
                    entries.push(Runtime::Idt { history, reset });
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
                        history: Box::new(Transition::enclosed(
                            initial, bounds, *delay, *rise, *fall,
                        )?),
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
        self.entries
            .iter()
            .map(|entry| match entry {
                Runtime::Idt { history, .. } => history.value(time),
                Runtime::AbsDelay(history) => history.value(time),
                Runtime::Transition { history, .. } => history.value(time),
                Runtime::Slew(history) => history.value(time),
            })
            .collect()
    }

    pub(crate) fn next_breakpoint(&self, after: f64) -> Option<f64> {
        self.entries
            .iter()
            .filter_map(|entry| match entry {
                Runtime::Idt { history, .. } => history.next_breakpoint(after),
                Runtime::AbsDelay(history) => history.next_breakpoint(after),
                Runtime::Transition { history, .. } => history.next_breakpoint(after),
                Runtime::Slew(history) => history.next_breakpoint(after),
            })
            .min_by(f64::total_cmp)
    }

    pub(crate) fn bounds(&self, time: f64) -> Result<Vec<I>, Error> {
        self.entries
            .iter()
            .map(|entry| match entry {
                Runtime::Idt { history, .. } => history.value_bounds(time),
                Runtime::Slew(history) => Ok(history.value_bounds(time)),
                Runtime::AbsDelay(history) => Ok(history.value_bounds(time)),
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
                Runtime::Idt { .. } => Vec::new(),
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
        time_bounds: I,
        states: &[f64],
        bounds: &[I],
        changed: &[usize],
    ) -> Result<(), Error> {
        for entry in &mut self.entries {
            match entry {
                Runtime::Idt { history, reset } => {
                    if let Some(reset) = reset {
                        history.advance_reset(time, time_bounds, reset.active(bounds)?)?;
                    }
                }
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

    pub(crate) fn same_reset_history(&self, other: &Self) -> bool {
        self.entries.len() == other.entries.len()
            && self
                .entries
                .iter()
                .zip(&other.entries)
                .all(|(a, b)| match (a, b) {
                    (Runtime::Idt { history: a, .. }, Runtime::Idt { history: b, .. }) => {
                        a.same_reset_history(b)
                    }
                    _ => true,
                })
    }

    pub(crate) fn permits_same_time_change(
        &self,
        time: f64,
        previous: &[f64],
    ) -> Result<bool, Error> {
        if previous.len() != self.entries.len() {
            return Ok(false);
        }
        for (entry, &before) in self.entries.iter().zip(previous) {
            let after = match entry {
                Runtime::Idt { history, .. } => history.value(time)?,
                Runtime::AbsDelay(history) => history.value(time)?,
                Runtime::Transition { history, .. } => history.value(time)?,
                Runtime::Slew(history) => history.value(time)?,
            };
            if after == before {
                continue;
            }
            match entry {
                Runtime::Idt {
                    history,
                    reset: Some(_),
                } if history.reset_active() && after == history.ic() => {}
                _ => return Ok(false),
            }
        }
        Ok(true)
    }
}

fn reset_active(value: I) -> Result<bool, Error> {
    match value.sign() {
        Some(0) => Ok(false),
        Some(_) => Ok(true),
        None => Err(Error::new(
            "unsupported_operator",
            "cannot certify idt reset as zero or nonzero",
        )),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn q() -> Expression {
        Expression::State { state: 0 }
    }

    fn constant(value: f64) -> Expression {
        Expression::Affine {
            constant: value,
            terms: Vec::new(),
        }
    }

    fn add(left: Expression, right: Expression) -> Expression {
        Expression::Add {
            left: Box::new(left),
            right: Box::new(right),
        }
    }

    fn multiply(left: Expression, right: Expression) -> Expression {
        Expression::Multiply {
            left: Box::new(left),
            right: Box::new(right),
        }
    }

    #[test]
    fn reset_sign_uses_original_state_expression_terms() {
        let positive = ResetExpression::new(add(
            add(multiply(constant(1e16), q()), q()),
            multiply(constant(-1.0), multiply(constant(1e16), q())),
        ));
        assert!(positive.active(&[I::ONE]).unwrap());
        assert!(!positive.active(&[I::ZERO]).unwrap());

        let negative = ResetExpression::new(add(
            add(
                multiply(constant(-1e16), q()),
                multiply(constant(-1.0), q()),
            ),
            multiply(constant(1e16), q()),
        ));
        assert!(negative.active(&[I::ONE]).unwrap());
        assert!(!negative.active(&[I::ZERO]).unwrap());

        let uncertain = positive.active(&[I { lo: -1.0, hi: 1.0 }]).err().unwrap();
        assert_eq!(uncertain.kind, "unsupported_operator");

        let inexact_product = ResetExpression::new(add(
            multiply(multiply(constant(0.1), q()), constant(0.1)),
            multiply(constant(-0.010000000000000002), q()),
        ));
        let rejected = inexact_product.active(&[I::ONE]).err().unwrap();
        assert_eq!(rejected.kind, "unsupported_operator");
    }
}
