//! Instance/call-site operator histories. Clone with a candidate frame; never
//! derive history from output samples or mutate accepted state during a trial.
use crate::absdelay::AbsDelay;
use crate::continuous::Continuous;
use crate::events::{affine, AffineState};
use crate::idt::Idt;
use crate::idtmod::IdtMod;
use crate::interval::{equal_products, sum_products_sign, Interval as I};
use crate::ir::{Error, Expression, OperatorSpec, Origin, Program};
use crate::laplace::LaplaceNd;
use crate::pwl::Trajectory;
use crate::slew::Slew;
use crate::transition::Transition;
use std::collections::BTreeSet;
use std::sync::Arc;

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
struct DirectInput {
    points: Vec<(f64, f64)>,
    bounds: Vec<I>,
}

impl DirectInput {
    fn range(&self, time: I) -> Result<(I, I), Error> {
        let mut slopes = None;
        for (k, pair) in self.points.windows(2).enumerate() {
            if pair[0].0 < time.hi && pair[1].0 > time.lo
                || time.lo == time.hi && pair[0].0 <= time.lo && time.lo <= pair[1].0
            {
                let slope = (self.bounds[k + 1] - self.bounds[k])
                    / (I::point(pair[1].0) - I::point(pair[0].0));
                slopes = Some(slopes.map_or(slope, |previous: I| previous.hull(slope)));
            }
        }
        // PWL extrema occur at endpoints or included knots. Do not include
        // remote segment endpoints: they would prevent root refinement.
        let mut values_local = self
            .value_bounds(time.lo)?
            .hull(self.value_bounds(time.hi)?);
        for (k, &(t, _)) in self.points.iter().enumerate() {
            if t > time.lo && t < time.hi {
                values_local = values_local.hull(self.bounds[k]);
            }
        }
        Ok((values_local, slopes.unwrap_or(I::ZERO)))
    }
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
        coefficient_bounds: I,
        constant_bounds: I,
    },
}

#[derive(Clone)]
enum Runtime {
    Continuous(usize),
    Idt {
        history: Idt,
        reset: Option<ResetExpression>,
    },
    IdtMod(IdtMod),
    Sin(SinInput),
    AbsDelay(AbsDelay),
    LaplaceNd(LaplaceNd),
    Transition {
        input: AffineState,
        input_bounds: Vec<I>,
        history: Box<Transition>,
    },
    Slew(Slew),
}

const SIN_MAX_MAGNITUDE: f64 = 128.0;
const PI_BITS: u64 = 0x4009_21fb_5444_2d18;
const FRAC_PI_2_BITS: u64 = 0x3ff9_21fb_5444_2d18;

fn sin_operator_bounds(
    input: &Expression,
    program: &Program,
    operator: usize,
) -> Result<(I, I), Error> {
    let row = crate::affine_bounds::affine(input, program)?;
    let operator_base = program.nodes.len() + program.states.len();
    let operator_limit = operator_base + program.operators.len();
    let coefficient_index = operator_base + operator;
    if row[..operator_base].iter().any(|x| !x.zero())
        || row[operator_base..operator_limit]
            .iter()
            .enumerate()
            .any(|(index, x)| index != operator && !x.zero())
    {
        return Err(Error::new(
            "unsupported_operator",
            "sin operator input must have one bounded operator dependency and constants only",
        ));
    }
    let coefficient = row[coefficient_index];
    let constant = *row.last().unwrap();
    if coefficient.zero() || !coefficient.finite() || !constant.finite() {
        return Err(Error::new(
            "unsupported_operator",
            "sin operator input must have finite bounded affine coefficients",
        ));
    }
    Ok((coefficient, constant))
}

fn constant_interval(bits: u64) -> I {
    I {
        lo: f64::from_bits(bits - 1),
        hi: f64::from_bits(bits + 1),
    }
}

fn union(a: I, b: I) -> I {
    I {
        lo: a.lo.min(b.lo),
        hi: a.hi.max(b.hi),
    }
}

fn widen(a: I, epsilon: f64) -> I {
    I {
        lo: (a.lo - epsilon).next_down(),
        hi: (a.hi + epsilon).next_up(),
    }
}

fn interval_power(base: I, exponent: usize) -> I {
    (0..exponent).fold(I::ONE, |product, _| product * base)
}

fn factorial_interval(n: usize) -> I {
    (1..=n).fold(I::ONE, |product, k| product * I::point(k as f64))
}

fn taylor_remainder(radius: f64, start_power: usize) -> f64 {
    let bound = interval_power(I::point(radius), start_power) / factorial_interval(start_power);
    bound.hi.next_up()
}

fn sin_reduced(r: I) -> Result<I, Error> {
    let limit = constant_interval(FRAC_PI_2_BITS).hi;
    if !r.finite() || r.lo < -limit || r.hi > limit {
        return Err(Error::new(
            "waveform_accuracy",
            "reduced sine interval is outside the certified Taylor domain",
        ));
    }
    let r2 = r * r;
    let mut term = r;
    let mut sum = term;
    for (a, b) in [
        (2.0, 3.0),
        (4.0, 5.0),
        (6.0, 7.0),
        (8.0, 9.0),
        (10.0, 11.0),
        (12.0, 13.0),
        (14.0, 15.0),
        (16.0, 17.0),
    ] {
        term = -term * r2 / I::point(a * b);
        sum = sum + term;
    }
    Ok(widen(sum, taylor_remainder(limit, 19)))
}

fn cos_reduced(r: I) -> Result<I, Error> {
    let limit = constant_interval(FRAC_PI_2_BITS).hi;
    if !r.finite() || r.lo < -limit || r.hi > limit {
        return Err(Error::new(
            "waveform_accuracy",
            "reduced cosine interval is outside the certified Taylor domain",
        ));
    }
    let r2 = r * r;
    let mut term = I::ONE;
    let mut sum = term;
    for (a, b) in [
        (1.0, 2.0),
        (3.0, 4.0),
        (5.0, 6.0),
        (7.0, 8.0),
        (9.0, 10.0),
        (11.0, 12.0),
        (13.0, 14.0),
        (15.0, 16.0),
        (17.0, 18.0),
    ] {
        term = -term * r2 / I::point(a * b);
        sum = sum + term;
    }
    Ok(widen(sum, taylor_remainder(limit, 20)))
}

fn sin_point_bounds(x: f64) -> Result<I, Error> {
    if !x.is_finite() || x.abs() > SIN_MAX_MAGNITUDE {
        return Err(Error::new(
            "waveform_accuracy",
            "sine argument exceeds certified finite Taylor domain",
        ));
    }
    let half_pi = constant_interval(FRAC_PI_2_BITS);
    let n = (x / std::f64::consts::FRAC_PI_2).round();
    if n.abs() > 128.0 {
        return Err(Error::new(
            "waveform_accuracy",
            "sine range reduction turn count is outside certified domain",
        ));
    }
    let r = I::point(x) - I::point(n) * half_pi;
    match (n as i64).rem_euclid(4) {
        0 => sin_reduced(r),
        1 => cos_reduced(r),
        2 => Ok(-sin_reduced(r)?),
        _ => Ok(-cos_reduced(r)?),
    }
}

fn overlaps(a: I, b: I) -> bool {
    a.lo <= b.hi && b.lo <= a.hi
}

fn contains_critical(input: I, critical: I, period: I) -> bool {
    let nominal_critical = (critical.lo + critical.hi) / 2.0;
    let nominal_period = (period.lo + period.hi) / 2.0;
    let start = ((input.lo - nominal_critical) / nominal_period).floor() as i64 - 1;
    let end = ((input.hi - nominal_critical) / nominal_period).ceil() as i64 + 1;
    (start..=end).any(|k| overlaps(input, critical + I::point(k as f64) * period))
}

fn sin_bounds(input: I) -> Result<I, Error> {
    if !input.finite() {
        return Err(Error::new(
            "waveform_accuracy",
            "cannot bound nonfinite sine input",
        ));
    }
    if input.lo.abs().max(input.hi.abs()) > SIN_MAX_MAGNITUDE {
        return Err(Error::new(
            "waveform_accuracy",
            "sine argument exceeds certified finite Taylor domain",
        ));
    }
    let two_pi = I::point(2.0) * constant_interval(PI_BITS);
    if input.hi - input.lo >= two_pi.lo {
        return Ok(I { lo: -1.0, hi: 1.0 });
    }
    let mut result = union(sin_point_bounds(input.lo)?, sin_point_bounds(input.hi)?);
    let period = I::point(2.0) * constant_interval(PI_BITS);
    let half_pi = constant_interval(FRAC_PI_2_BITS);
    if contains_critical(input, half_pi, period) {
        result.hi = 1.0;
    }
    if contains_critical(input, -half_pi, period) {
        result.lo = -1.0;
    }
    Ok(I {
        lo: result.lo.max(-1.0),
        hi: result.hi.min(1.0),
    })
}

#[derive(Clone)]
pub(crate) struct ResetExpression {
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
    pub(crate) fn new(expression: Expression) -> Self {
        Self { expression }
    }

    pub(crate) fn active(&self, states: &[I]) -> Result<bool, Error> {
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
    changes_on_advance: Vec<bool>,
    direct: Vec<Option<DirectInput>>,
    continuous: Option<Arc<Continuous>>,
    horizon: f64,
}

// Borrows one immutable history base at one time. Every advanced trial clones
// this same base; cached values cannot escape into a different time or history.
pub(crate) struct Evaluation<'a> {
    base: &'a Operators,
    time: f64,
    pub(crate) values: Vec<f64>,
    pub(crate) bounds: Vec<I>,
}

impl Evaluation<'_> {
    // Reset/instantaneous algebraic map only. It does not install transition
    // targets or propagate the new continuous flow to the representative.
    // Each closure solve observes the same accepted physical history.
    pub(crate) fn observed_after(
        &self,
        time_bounds: I,
        parameters: &[I],
    ) -> Result<(Operators, Vec<f64>, Vec<I>), Error> {
        let mut observed = self.base.clone();
        if let Some(continuous) = &self.base.continuous {
            observed.continuous = Some(Arc::new(continuous.mapped_event(
                self.time,
                time_bounds,
                parameters,
            )?));
        }
        for entry in &mut observed.entries {
            if let Runtime::Idt {
                history,
                reset: Some(reset),
            } = entry
            {
                history.advance_reset(self.time, time_bounds, reset.active(parameters)?)?;
            }
        }
        let mut values = observed.values_reusing(self.time, Some(&self.values))?;
        let mut bounds = observed.event_bounds(self.time, time_bounds)?;
        for (i, entry) in observed.entries.iter().enumerate() {
            match entry {
                Runtime::Continuous(slot)
                    if observed
                        .continuous
                        .as_ref()
                        .unwrap()
                        .keeps_value_on_event(*slot)? =>
                {
                    values[i] = self.values[i];
                    bounds[i] = self.bounds[i];
                }
                Runtime::Idt {
                    history,
                    reset: Some(_),
                } if history.reset_active() => {
                    values[i] = history.ic();
                    bounds[i] = I::point(history.ic());
                }
                Runtime::Idt { .. } => {
                    // Releasing a reset changes future flow, not the sample
                    // at the release instant. Preserve the frozen observation.
                    values[i] = self.values[i];
                    bounds[i] = self.bounds[i];
                }
                Runtime::Sin(SinInput::Operator {
                    operator,
                    coefficient,
                    constant,
                    coefficient_bounds,
                    constant_bounds,
                }) if values[*operator] != self.values[*operator]
                    || bounds[*operator] != self.bounds[*operator] =>
                {
                    values[i] = (*constant + *coefficient * values[*operator]).sin();
                    bounds[i] =
                        sin_bounds(*constant_bounds + *coefficient_bounds * bounds[*operator])?;
                }
                _ => {}
            }
        }
        Ok((observed, values, bounds))
    }

    // Install only future history. Event observations are obtained separately
    // from observed_after; querying a newly installed transition over an old
    // root window would mix the two lifecycle phases.
    #[cfg(test)]
    pub(crate) fn advanced(
        &self,
        time_bounds: I,
        states: &[f64],
        bounds: &[I],
        changed: &[usize],
    ) -> Result<Operators, Error> {
        self.advanced_until(time_bounds, states, bounds, changed, self.base.horizon)
    }

    pub(crate) fn advanced_until(
        &self,
        time_bounds: I,
        states: &[f64],
        bounds: &[I],
        changed: &[usize],
        horizon: f64,
    ) -> Result<Operators, Error> {
        let _timing = crate::diagnostics::span("history.advance_candidate");

        let copying = crate::diagnostics::span("history.clone");
        let mut candidate = self.base.clone();
        drop(copying);
        crate::diagnostics::counter("history_clone_calls", 1);
        crate::diagnostics::counter("history_clone_operator_slots", self.base.entries.len());
        candidate.horizon = horizon;
        candidate.advance(self.time, time_bounds, states, bounds, changed)?;
        Ok(candidate)
    }
}

impl Operators {
    pub(crate) fn event_bounds(&self, time: f64, window: I) -> Result<Vec<I>, Error> {
        if window.lo == window.hi {
            return self.bounds(time);
        }
        let continuous = self
            .continuous
            .as_ref()
            .map(|c| c.event_bounds(window))
            .transpose()?;
        // Value observation has a different contract from a cross guard:
        // it also covers reset histories and need not provide a derivative.
        let mut bounds = Vec::with_capacity(self.entries.len());
        for (index, entry) in self.entries.iter().enumerate() {
            let bound = match entry {
                Runtime::Continuous(slot) => continuous.as_ref().unwrap()[*slot],
                Runtime::Idt { history, .. } => history.value_range(window)?,
                Runtime::LaplaceNd(history) => {
                    history
                        .range(
                            window,
                            self.direct[index].as_ref().unwrap().range(window)?.0,
                        )?
                        .0
                }
                Runtime::Sin(SinInput::Direct(source)) => sin_bounds(source.range(window)?.0)?,
                Runtime::Sin(SinInput::Operator {
                    operator,
                    coefficient_bounds,
                    constant_bounds,
                    ..
                }) => sin_bounds(*constant_bounds + *coefficient_bounds * bounds[*operator])?,
                Runtime::Transition { history, .. } => history.value_range(window)?,
                _ => {
                    return Err(Error::new(
                        "event_resolution",
                        "operator has no certified observation over a nonpoint event window",
                    ))
                }
            };
            if !bound.finite() {
                return Err(Error::new(
                    "waveform_accuracy",
                    "nonfinite event observation range",
                ));
            }
            bounds.push(bound);
        }
        Ok(bounds)
    }

    #[cfg(test)]
    pub(crate) fn new(
        program: &Program,
        trajectory: &Trajectory,
        driven: &[String],
        states: &[f64],
    ) -> Result<Self, Error> {
        Self::new_until(program, trajectory, driven, states, trajectory.config.stop)
    }

    pub(crate) fn new_until(
        program: &Program,
        trajectory: &Trajectory,
        driven: &[String],
        states: &[f64],
        horizon: f64,
    ) -> Result<Self, Error> {
        let _timing = crate::diagnostics::span("history.prepare");

        let mut identities = BTreeSet::new();
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
            let input = match spec {
                OperatorSpec::Idt { input, .. }
                | OperatorSpec::LaplaceNd { input, .. }
                | OperatorSpec::Ddt { input, .. }
                | OperatorSpec::Sin { input, .. }
                | OperatorSpec::AbsDelay { input, .. }
                | OperatorSpec::Transition { input, .. }
                | OperatorSpec::Slew { input, .. }
                | OperatorSpec::IdtMod { input, .. } => input,
            };
            // Validate raw indices and ownership before any interval indexing.
            // The kernel must not assume a trusted Python producer.
            if matches!(
                spec,
                OperatorSpec::Idt { .. } | OperatorSpec::LaplaceNd { .. }
            ) {
                crate::continuous::validate_integral_input(input, program, &origin.instance)?;
            } else {
                affine(input, program, &origin.instance)?;
            }
        }
        let continuous =
            Continuous::new_until(program, trajectory, driven, states, horizon)?.map(Arc::new);
        let mut entries = Vec::new();
        let mut direct = Vec::new();
        for (index, spec) in program.operators.iter().enumerate() {
            let direct_input = match spec {
                OperatorSpec::Idt { input, origin, .. }
                | OperatorSpec::LaplaceNd { input, origin, .. } => {
                    direct_points(input, program, trajectory, driven, origin)
                        .ok()
                        .map(|(points, bounds)| DirectInput::new(points, bounds))
                }
                _ => None,
            };
            direct.push(direct_input);
            if let Some(slot) = continuous
                .as_ref()
                .and_then(|c| c.operator_value_index(index))
            {
                entries.push(Runtime::Continuous(slot));
                continue;
            }
            match spec {
                OperatorSpec::Ddt { .. } => {
                    return Err(Error::new(
                        "invalid_ir",
                        "ddt is missing its continuous trajectory slot",
                    ))
                }
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
                            || bound_input.operator_dependencies.len() != 1
                            || !bound_input.operator_dependencies.contains(&operator)
                        {
                            return Err(Error::new(
                                "unsupported_operator",
                                "sin operator input must reference exactly one earlier operator with finite affine coefficients",
                            ));
                        }
                        let (coefficient_bounds, constant_bounds) =
                            sin_operator_bounds(input, program, operator)?;
                        SinInput::Operator {
                            operator,
                            coefficient,
                            constant,
                            coefficient_bounds,
                            constant_bounds,
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
                OperatorSpec::LaplaceNd {
                    input,
                    numerator,
                    denominator,
                    origin,
                } => {
                    let (points, bounds) =
                        direct_points(input, program, trajectory, driven, origin)?;
                    entries.push(Runtime::LaplaceNd(LaplaceNd::enclosed(
                        points,
                        bounds,
                        numerator,
                        denominator,
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
        let mut changes_on_advance = Vec::with_capacity(entries.len());
        for entry in &entries {
            let changes = match entry {
                Runtime::Idt { reset: Some(_), .. } | Runtime::Transition { .. } => true,
                Runtime::Sin(SinInput::Operator { operator, .. }) => changes_on_advance[*operator],
                Runtime::Continuous(_) => continuous.as_ref().is_some_and(|c| c.changes_on_event()),
                Runtime::Idt { reset: None, .. }
                | Runtime::IdtMod(_)
                | Runtime::Sin(SinInput::Direct(_))
                | Runtime::AbsDelay(_)
                | Runtime::LaplaceNd(_)
                | Runtime::Slew(_) => false,
            };
            changes_on_advance.push(changes);
        }
        Ok(Self {
            entries,
            changes_on_advance,
            direct,
            continuous,
            horizon,
        })
    }

    pub(crate) fn range(&self, index: usize, time: I) -> Result<(I, I), Error> {
        let entry = self
            .entries
            .get(index)
            .ok_or_else(|| Error::new("invalid_ir", "guard operator index out of range"))?;
        if self.changes_on_advance[index] {
            return Err(Error::new(
                "unsupported_cross",
                "cross cannot depend on event-modified operator history",
            ));
        }
        let result = match entry {
            Runtime::Continuous(slot) => {
                let c = self.continuous.as_ref().unwrap();
                if !c.is_continuous(*slot) {
                    return Err(Error::new(
                        "unsupported_cross",
                        "ddt or its feedthrough can jump at DC/source corners; continuous cross trajectory required",
                    ));
                }
                (
                    c.range_bounds(time)?[*slot],
                    c.derivative_bounds(time)?[*slot],
                )
            }
            Runtime::Idt { history, .. } => {
                let input = self.direct[index].as_ref().unwrap().range(time)?.0;
                (
                    history.value_bounds(time.lo)? + input * (time - I::point(time.lo)),
                    input,
                )
            }
            Runtime::LaplaceNd(history) => {
                history.range(time, self.direct[index].as_ref().unwrap().range(time)?.0)?
            }
            Runtime::Sin(input) => {
                let (value, derivative) = match input {
                    SinInput::Direct(source) => source.range(time)?,
                    SinInput::Operator {
                        operator,
                        coefficient_bounds,
                        constant_bounds,
                        ..
                    } => {
                        let (v, d) = self.range(*operator, time)?;
                        (
                            *constant_bounds + *coefficient_bounds * v,
                            *coefficient_bounds * d,
                        )
                    }
                };
                (
                    sin_bounds(value)?,
                    sin_bounds(value + constant_interval(FRAC_PI_2_BITS))? * derivative,
                )
            }
            _ => {
                return Err(Error::new(
                    "unsupported_cross",
                    "operator guard requires a certified continuous trajectory and derivative",
                ))
            }
        };
        if !result.0.finite() || !result.1.finite() {
            return Err(Error::new(
                "event_resolution",
                "nonfinite dynamic guard history",
            ));
        }
        Ok(result)
    }

    pub(crate) fn values(&self, time: f64) -> Result<Vec<f64>, Error> {
        let _timing = crate::diagnostics::span("history.nominal_query");

        self.values_reusing(time, None)
    }

    pub(crate) fn evaluation(&self, time: f64) -> Result<Evaluation<'_>, Error> {
        Ok(Evaluation {
            base: self,
            time,
            values: self.values(time)?,
            bounds: self.bounds(time)?,
        })
    }

    fn values_reusing(&self, time: f64, previous: Option<&[f64]>) -> Result<Vec<f64>, Error> {
        let continuous = self
            .continuous
            .as_ref()
            .map(|c| c.values(time))
            .transpose()?;
        self.entries.iter().enumerate().try_fold(
            Vec::<f64>::with_capacity(self.entries.len()),
            |mut values, (index, entry)| {
                if let Some(previous) = previous {
                    if !self.changes_on_advance[index] {
                        values.push(previous[index]);
                        return Ok(values);
                    }
                }
                let value = match entry {
                    Runtime::Continuous(slot) => continuous.as_ref().unwrap()[*slot],
                    Runtime::Idt { history, .. } => history.value(time)?,
                    Runtime::LaplaceNd(history) => history.value(time)?,
                    Runtime::IdtMod(history) => history.value(time)?,
                    Runtime::Sin(input) => match input {
                        SinInput::Direct(source) => source.value(time)?.sin(),
                        SinInput::Operator {
                            operator,
                            coefficient,
                            constant,
                            ..
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
                Runtime::Continuous(_) => self.continuous.as_ref().unwrap().next_breakpoint(after),
                Runtime::Idt { history, .. } => history.next_breakpoint(after),
                Runtime::IdtMod(history) => history.next_breakpoint(after),
                Runtime::Sin(SinInput::Direct(source)) => source.next_breakpoint(after),
                Runtime::Sin(SinInput::Operator { .. }) => None,
                Runtime::AbsDelay(history) => history.next_breakpoint(after),
                Runtime::LaplaceNd(history) => history.next_breakpoint(after),
                Runtime::Transition { history, .. } => history.next_breakpoint(after),
                Runtime::Slew(history) => history.next_breakpoint(after),
            })
            .min_by(f64::total_cmp)
    }

    pub(crate) fn bounds(&self, time: f64) -> Result<Vec<I>, Error> {
        let _timing = crate::diagnostics::span("history.bounds_query");

        self.bounds_reusing(time, None)
    }

    fn bounds_reusing(&self, time: f64, previous: Option<&[I]>) -> Result<Vec<I>, Error> {
        let continuous = self
            .continuous
            .as_ref()
            .map(|c| c.bounds(time))
            .transpose()?;
        self.entries.iter().enumerate().try_fold(
            Vec::<I>::with_capacity(self.entries.len()),
            |mut bounds, (index, entry)| {
                if let Some(previous) = previous {
                    if !self.changes_on_advance[index] {
                        bounds.push(previous[index]);
                        return Ok(bounds);
                    }
                }
                let bound = match entry {
                    Runtime::Continuous(slot) => continuous.as_ref().unwrap()[*slot],
                    Runtime::Idt { history, .. } => history.value_bounds(time)?,
                    Runtime::LaplaceNd(history) => history.value_bounds(time)?,
                    Runtime::IdtMod(history) => history.value_bounds(time)?,
                    Runtime::Sin(input) => match input {
                        SinInput::Direct(source) => sin_bounds(source.value_bounds(time)?)?,
                        SinInput::Operator {
                            operator,
                            coefficient_bounds,
                            constant_bounds,
                            ..
                        } => {
                            if let Runtime::IdtMod(history) = &self.entries[*operator] {
                                history
                                    .value_bounds_segments(time)?
                                    .into_iter()
                                    .try_fold(None, |acc, phase| {
                                        let input = *constant_bounds + *coefficient_bounds * phase;
                                        let bound = sin_bounds(input)?;
                                        Ok::<_, Error>(Some(match acc {
                                            Some(previous) => union(previous, bound),
                                            None => bound,
                                        }))
                                    })?
                                    .ok_or_else(|| {
                                        Error::new(
                                            "waveform_accuracy",
                                            "cannot certify sine of empty wrapped phase enclosure",
                                        )
                                    })?
                            } else {
                                let input =
                                    *constant_bounds + *coefficient_bounds * bounds[*operator];
                                sin_bounds(input)?
                            }
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
                Runtime::Continuous(_) => Vec::new(),
                Runtime::Idt { .. } => Vec::new(),
                Runtime::IdtMod(_) => Vec::new(),
                Runtime::Sin(_) => Vec::new(),
                Runtime::AbsDelay(_) => Vec::new(),
                Runtime::LaplaceNd(_) => Vec::new(),
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
        let _timing = crate::diagnostics::span("history.advance");

        if let Some(continuous) = &self.continuous {
            if !changed.is_empty() || continuous.needs_extension(self.horizon) {
                self.continuous = Some(Arc::new(continuous.restarted(
                    time,
                    time_bounds,
                    bounds,
                    self.horizon,
                )?));
            }
        }
        for entry in &mut self.entries {
            match entry {
                Runtime::Continuous(_) => {}
                Runtime::Idt { history, reset } => {
                    if let Some(reset) = reset {
                        history.advance_reset(time, time_bounds, reset.active(bounds)?)?;
                    }
                }
                Runtime::IdtMod(_) => {}
                Runtime::Sin(_) => {}
                Runtime::AbsDelay(_) => {}
                Runtime::LaplaceNd(_) => {}
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
        if self.horizon != other.horizon {
            return false;
        }
        match (&self.continuous, &other.continuous) {
            (Some(a), Some(b)) if !a.same_history(b) => return false,
            _ => {}
        }
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

    pub(crate) fn permits_same_time_change(&self, previous: &[f64], current: &[f64]) -> bool {
        if previous.len() != self.entries.len() || current.len() != self.entries.len() {
            return false;
        }
        let mut permitted_changes = Vec::with_capacity(self.entries.len());
        for ((entry, &before), &after) in self.entries.iter().zip(previous).zip(current) {
            let permitted = match entry {
                Runtime::Continuous(_) => self
                    .continuous
                    .as_ref()
                    .is_some_and(|c| c.changes_on_event()),
                Runtime::Idt {
                    history,
                    reset: Some(_),
                } => history.reset_active() && after == history.ic(),
                // A pure function of an earlier, permitted reset change may
                // change at the same instant. The caller still re-solves and
                // replays every history from the same accepted base.
                Runtime::Sin(SinInput::Operator { operator, .. }) => permitted_changes[*operator],
                _ => false,
            };
            if after != before && !permitted {
                return false;
            }
            permitted_changes.push(after != before && permitted);
        }
        true
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
mod phase_operator_tests {
    use super::*;

    #[test]
    fn joint_candidates_preserve_integral_and_filter_histories_after_reset_failure_and_discard() {
        use serde_json::json;
        for nonlinear in [false, true] {
            let origin =
                |column| json!({"source":"joint.va","line":1,"column":column,"instance":"dut"});
            let z = json!({"op":"affine","constant":0,"terms":[{"node":2,"coefficient":1}]});
            let input = if nonlinear {
                json!({"op":"multiply","left":{"op":"affine","constant":-1,"terms":[]},"right":{"op":"power","base":z,"exponent":2}})
            } else {
                json!({"op":"affine","constant":0,"terms":[{"node":2,"coefficient":-1}]})
            };
            let program:Program=serde_json::from_value(json!({
            "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","u","z","y","filtered"],
            "states":[{"instance":"dut","name":"rst","kind":"integer","initial":0}],
            "operators":[
                {"kind":"idt","input":input,"ic":1,"reset":{"op":"state","state":0},"origin":origin(1)},
                {"kind":"idt","input":z,"ic":0,"origin":origin(2)},
                {"kind":"laplace_nd","input":z,"numerator":[1],"denominator":[1,2,1],"origin":origin(5)}],
            "contributions":[
                {"branch":{"instance":"dut","local_positive":"z","local_negative":"r","kind":"voltage"},"positive":2,"negative":0,"rhs":{"op":"operator","operator":0},"origin":origin(3)},
                {"branch":{"instance":"dut","local_positive":"y","local_negative":"r","kind":"voltage"},"positive":3,"negative":0,"rhs":{"op":"operator","operator":1},"origin":origin(4)},
                {"branch":{"instance":"dut","local_positive":"filtered","local_negative":"r","kind":"voltage"},"positive":4,"negative":0,"rhs":{"op":"operator","operator":2},"origin":origin(6)}]
        })).unwrap();
            let trajectory = Trajectory::new(
                crate::ir::TransientInputs {
                    pwl: vec![vec![[0.0, 0.0], [0.5, 0.0], [2.0, 0.0]]],
                    output_times: vec![0.0, 0.5, 2.0],
                    stop: 2.0,
                    max_step: 2.0,
                },
                1,
            )
            .unwrap();
            let base = Operators::new(&program, &trajectory, &["u".into()], &[0.0]).unwrap();
            let original = base.bounds(1.0).unwrap();
            let frozen = base.evaluation(0.5).unwrap();
            let uncertain = frozen.advanced(
                I {
                    lo: 0.5 - 1e-8,
                    hi: 0.5,
                },
                &[1.0],
                &[I::ONE],
                &[0],
            );
            if nonlinear {
                // A bounded nonlinear flow can cross the source corner. Its
                // candidate must remain disposable and reproducible.
                let candidate = uncertain.unwrap();
                let bounds = candidate.bounds(1.0).unwrap();
                drop(candidate);
                let retry = frozen
                    .advanced(
                        I {
                            lo: 0.5 - 1e-8,
                            hi: 0.5,
                        },
                        &[1.0],
                        &[I::ONE],
                        &[0],
                    )
                    .unwrap();
                assert_eq!(retry.bounds(1.0).unwrap(), bounds);
            } else {
                assert!(uncertain.is_err());
            }
            assert_eq!(base.bounds(1.0).unwrap(), original);
            assert!(frozen
                .advanced(I::point(0.5), &[1.0], &[I { lo: -1.0, hi: 1.0 }], &[0])
                .is_err());
            assert_eq!(base.bounds(1.0).unwrap(), original);
            let discarded = frozen
                .advanced(I::point(0.5), &[1.0], &[I::ONE], &[0])
                .unwrap();
            let expected_outer = frozen.values[1] + 0.5;
            assert!((discarded.values(1.0).unwrap()[1] - expected_outer).abs() < 1e-10);
            let candidate_bounds = discarded.bounds(1.0).unwrap();
            // A reset replaces z, not either physical state of the filter.
            // Reinitializing the filter to the new DC input would give 1.
            assert!(candidate_bounds[2].hi < 1.0);
            if !nonlinear {
                let expected_filter = 1.0 + 2.375 * (-1.0_f64).exp() - 1.5 * (-0.5_f64).exp();
                assert!((discarded.values(1.0).unwrap()[2] - expected_filter).abs() < 1e-10);
            }
            drop(discarded);
            assert_eq!(base.bounds(1.0).unwrap(), original);
            let retry = frozen
                .advanced(I::point(0.5), &[1.0], &[I::ONE], &[0])
                .unwrap();
            assert_eq!(retry.bounds(1.0).unwrap(), candidate_bounds);
            assert!((retry.values(1.0).unwrap()[0] - 1.0).abs() < 1e-10);
            let reset_bound = retry.bounds(1.0).unwrap()[0];
            assert!(reset_bound.lo <= 1.0 && reset_bound.hi >= 1.0);
        }
    }

    #[test]
    fn evaluation_trials_reuse_only_immutable_histories_and_recompute_function_dependents() {
        use crate::ir::{TransientInputs, SCHEMA_VERSION};
        use serde_json::json;

        let origin =
            |line| json!({"instance":"dut", "source":"snapshot.va", "line":line, "column":1});
        let input = json!({"op":"affine", "constant":0, "terms":[{"node":1,"coefficient":1}]});
        let state = json!({"op":"state","state":0});
        let specs = vec![
            json!({"kind":"idt","input":input,"ic":1,"origin":origin(1)}),
            json!({"kind":"idt","input":input,"ic":0.125,"reset":state,"origin":origin(2)}),
            json!({"kind":"sin","input":{"op":"operator","operator":1},"origin":origin(3)}),
            json!({"kind":"idt_mod","input":input,"ic":0.125,"modulus":1,"offset":0,"origin":origin(4)}),
            json!({"kind":"sin","input":{"op":"operator","operator":3},"origin":origin(5)}),
            json!({"kind":"laplace_nd","input":input,"numerator":[1],"denominator":[1,0.5],"origin":origin(6)}),
            json!({"kind":"transition","input":state,"delay":0,"rise":0.25,"fall":0.25,"origin":origin(7)}),
            json!({"kind":"sin","input":{"op":"operator","operator":6},"origin":origin(8)}),
        ];
        let program: Program = serde_json::from_value(json!({
            "schema_version":SCHEMA_VERSION,"nodes":["0","u","y"],
            "states":[{"instance":"dut","name":"q","kind":"integer","initial":0}],
            "contributions":[{"branch":{"instance":"dut","local_positive":"y","local_negative":"r","kind":"voltage"},
                "positive":2,"negative":0,"rhs":{"op":"operator","operator":0},"origin":origin(10)}],
            "operators":specs,
        })).unwrap();
        let trajectory = Trajectory::new(
            TransientInputs {
                pwl: vec![vec![[0.0, 0.25], [4.0, 0.25]]],
                output_times: vec![0.0, 1.0, 4.0],
                stop: 4.0,
                max_step: 4.0,
            },
            1,
        )
        .unwrap();
        let base = Operators::new(&program, &trajectory, &["u".into()], &[0.0]).unwrap();
        let frozen = base.evaluation(1.0).unwrap();
        assert_eq!(frozen.values[0], 1.25);
        assert_eq!(frozen.values[1], 0.375);
        let (_, reset_values, reset_bounds) =
            frozen.observed_after(I::point(1.0), &[I::ONE]).unwrap();
        let reset_trial = frozen
            .advanced(I::point(1.0), &[1.0], &[I::ONE], &[0])
            .unwrap();
        assert_eq!(reset_values[1], 0.125);
        assert_eq!(reset_values[2], 0.125_f64.sin());
        for index in [0, 3, 4, 5] {
            assert_eq!(reset_values[index], frozen.values[index]);
            assert_eq!(reset_bounds[index], frozen.bounds[index]);
        }
        assert_eq!(reset_values, reset_trial.values(1.0).unwrap());
        assert_eq!(reset_bounds, reset_trial.bounds(1.0).unwrap());
        // Discard the reset trial and retry from the borrowed base.
        let (_, retry_values, retry_bounds) =
            frozen.observed_after(I::point(1.0), &[I::ZERO]).unwrap();
        assert_eq!(retry_values, frozen.values);
        assert_eq!(retry_bounds, frozen.bounds);
        assert_eq!(base.values(1.0).unwrap(), frozen.values);
        // A later query creates a new evaluation; transition and its sine
        // dependent must observe the new edge, not the old-time snapshot.
        let later = reset_trial.evaluation(1.125).unwrap();
        let (_, values, bounds) = later.observed_after(I::point(1.125), &[I::ONE]).unwrap();
        assert_eq!(values[6], 0.5);
        assert_eq!(values[7], 0.5_f64.sin());
        assert!(bounds[7].lo <= values[7] && bounds[7].hi >= values[7]);
    }

    #[test]
    fn sine_bounds_cover_critical_points_without_libm_endpoint_trust() {
        let half_pi = constant_interval(FRAC_PI_2_BITS);
        let bounds = sin_bounds(half_pi).unwrap();
        assert!(bounds.lo <= 1.0 && bounds.hi >= 1.0);
        let zero = sin_bounds(I::point(0.0)).unwrap();
        assert!(zero.lo <= 0.0 && zero.hi >= 0.0);
    }

    #[test]
    fn sine_bounds_reject_uncertified_huge_angles() {
        assert_eq!(
            sin_bounds(I::point(129.0)).unwrap_err().kind,
            "waveform_accuracy"
        );
    }
}

#[cfg(test)]
mod reset_operator_tests {
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
