//! Instance/call-site operator histories. Clone with a candidate frame; never
//! derive history from output samples or mutate accepted state during a trial.
use crate::absdelay::AbsDelay;
use crate::continuous::Continuous;
use crate::events::{affine, AffineState};
use crate::idt::Idt;
use crate::idtmod::IdtMod;
use crate::interval::{equal_products, sum_products_sign, Interval as I};
use crate::ir::{Error, Expression, OperatorSpec, Origin, Program, Tolerances};
use crate::laplace::LaplaceNd;
use crate::pwl::Trajectory;
use crate::slew::Slew;
use crate::transition::Transition;
use std::collections::BTreeSet;
use std::sync::Arc;

#[path = "transition_filter.rs"]
pub(crate) mod transition_filter;

#[path = "transition_integral.rs"]
pub(crate) mod transition_integral;

#[path = "direct_derivative.rs"]
pub(crate) mod direct_derivative;

/// Direct physical Laplace inputs do not need a voltage-network projection.
/// Procedure contribution locals remain owned by their current Plan, so an
/// unrelated output capture must not be parsed as a legacy affine equation.
fn procedure_direct_laplace(
    program: &Program,
    trajectory: &Trajectory,
    driven: &[String],
) -> Result<bool, Error> {
    if program.procedures.is_empty() || program.operators.is_empty() || !program.states.is_empty() {
        return Ok(false);
    }
    let work = trajectory.procedure_work().ok_or_else(|| {
        Error::new(
            "invalid_ir",
            "procedure histories lost their execution owner",
        )
    })?;
    work.debit(2, (program.operators.len() + 1) as u64)?;
    for operator in &program.operators {
        work.step()?;
        let OperatorSpec::LaplaceNd {
            input: Expression::Affine { terms, .. },
            numerator,
            denominator,
            ..
        } = operator
        else {
            return Ok(false);
        };
        // The direct builder owns this first-order shape. Higher-order or
        // polynomial feedthrough filters retain their existing network route.
        work.debit(2, 2)?;
        if numerator.len() != 1 || denominator.len() != 2 {
            return Ok(false);
        }
        for term in terms {
            work.step()?;
            let Some(node) = program.nodes.get(term.node) else {
                return Ok(false);
            };
            if term.node == 0 {
                continue;
            }
            let mut found = false;
            for name in driven {
                work.debit(2, (node.len() + name.len() + 1) as u64)?;
                if node == name {
                    found = true;
                    break;
                }
            }
            if !found {
                return Ok(false);
            }
        }
    }
    Ok(true)
}

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
            .zip(trajectory.checked_values(time)?)
            .zip(trajectory.checked_value_bounds(time)?)
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

/// Solve a time-invariant affine voltage input before materializing its PWL.
/// This is algebraic voltage feedback, not feedback through a history state.
fn projected_points(
    input: &Expression,
    program: &Program,
    trajectory: &Trajectory,
    driven: &[String],
    origin: &Origin,
) -> Result<DirectPoints, Error> {
    let driven_nodes: BTreeSet<_> = driven
        .iter()
        .filter_map(|name| program.nodes.iter().position(|n| n == name))
        .collect();
    let dependencies = |expression: &Expression, owner: &str| {
        let bound = affine(expression, program, owner)?;
        if !bound.state_dependencies.is_empty() || !bound.operator_dependencies.is_empty() {
            return Err(Error::new(
                "unsupported_operator",
                format!(
                    "PWL voltage projection cannot depend on event state or operator history at {}",
                    origin.label()
                ),
            ));
        }
        Ok(bound.node_dependencies)
    };
    let nodes = dependencies(input, &origin.instance)?;
    if nodes.iter().all(|n| *n == 0 || driven_nodes.contains(n)) {
        return direct_points(input, program, trajectory, driven, origin);
    }
    let mut pending: Vec<_> = nodes.into_iter().collect();
    let mut seen = BTreeSet::new();
    while let Some(node) = pending.pop() {
        if node == 0 || driven_nodes.contains(&node) || !seen.insert(node) {
            continue;
        }
        for c in &program.contributions {
            if c.positive == node || c.negative == node {
                pending.extend([c.positive, c.negative]);
                pending.extend(dependencies(&c.rhs, &c.origin.instance)?);
            }
        }
    }
    let projection =
        crate::event_accuracy::GuardBounds::expressions(program, driven, &[Some(input)])?;
    let mut points = Vec::new();
    let mut bounds = Vec::new();
    for &time in &trajectory.knots {
        let value = projection.values(&trajectory.checked_value_bounds(time)?)[0];
        // Choose a finite representative inside the original-IR enclosure.
        // Keep a point/subnormal intact; halving both ends would lose it.
        let representative = if value.lo == value.hi {
            value.lo
        } else {
            value.lo * 0.5 + value.hi * 0.5
        };
        points.push((time, representative));
        bounds.push(value);
    }
    Ok((points, bounds))
}

/// Find one same-kind, same-instance unit-alias history dependency. Structural
/// checks precede numerical projection, so cancellation cannot hide feedback.
#[derive(Clone, Copy)]
enum FeedforwardKind {
    Delay,
    Slew,
}
impl FeedforwardKind {
    fn name(self) -> &'static str {
        match self {
            Self::Delay => "absdelay",
            Self::Slew => "slew",
        }
    }
    fn matches(self, spec: &OperatorSpec) -> bool {
        matches!(
            (self, spec),
            (Self::Delay, OperatorSpec::AbsDelay { .. }) | (Self::Slew, OperatorSpec::Slew { .. })
        )
    }
}
fn history_parent(
    input: &Expression,
    program: &Program,
    driven: &[String],
    origin: &Origin,
    kind: FeedforwardKind,
) -> Result<Option<usize>, Error> {
    let driven_nodes: BTreeSet<_> = driven
        .iter()
        .filter_map(|name| program.nodes.iter().position(|n| n == name))
        .collect();
    let initial = affine(input, program, &origin.instance)?;
    if !initial.state_dependencies.is_empty() {
        return Err(Error::new(
            "unsupported_operator",
            format!("{} cannot depend on event state", kind.name()),
        ));
    }
    let mut pending: Vec<_> = initial.node_dependencies.into_iter().collect();
    let mut seen = BTreeSet::new();
    let mut operators = initial.operator_dependencies;
    while let Some(node) = pending.pop() {
        if node == 0 || driven_nodes.contains(&node) || !seen.insert(node) {
            continue;
        }
        for c in &program.contributions {
            if c.positive == node || c.negative == node {
                let bound = affine(&c.rhs, program, &c.origin.instance)?;
                if !bound.state_dependencies.is_empty() {
                    return Err(Error::new(
                        "unsupported_operator",
                        format!("{} cannot depend on event state", kind.name()),
                    ));
                }
                operators.extend(bound.operator_dependencies);
                pending.extend(bound.node_dependencies);
                pending.extend([c.positive, c.negative]);
            }
        }
    }
    if operators.is_empty() {
        return Ok(None);
    }
    if operators.len() != 1 {
        return Err(Error::new(
            "unsupported_operator",
            format!("{} requires exactly one first-stage history", kind.name()),
        ));
    }
    let parent = *operators.iter().next().unwrap();
    if program.operators[parent].origin().instance != origin.instance
        || !kind.matches(&program.operators[parent])
    {
        return Err(Error::new(
            "unsupported_operator",
            format!(
                "{} history must be a same-instance {}",
                kind.name(),
                kind.name()
            ),
        ));
    }
    let map = crate::affine_bounds::node_map(program, driven)?;
    let expression = crate::affine_bounds::affine(input, program)?;
    let variables = expression.len() - 1;
    let width = driven.len() + program.states.len() + program.operators.len() + 1;
    let slot = driven.len() + program.states.len() + parent;
    // node_map rows all have width columns; iterate columns without changing
    // the original per-column accumulation order. Valid IR has a ground node.
    for (k, _) in map[0].iter().enumerate().take(width) {
        let base = if k == width - 1 {
            expression[variables]
        } else {
            I::ZERO
        };
        let coefficient = (0..variables).fold(base, |sum, j| sum + expression[j] * map[j][k]);
        if coefficient != if k == slot { I::ONE } else { I::ZERO } {
            return Err(Error::new(
                "unsupported_operator",
                format!(
                    "second {} input must be a certified unit, zero-offset first-stage alias",
                    kind.name()
                ),
            ));
        }
    }
    Ok(Some(parent))
}

/// Resolve at most two immutable histories independent of contribution order.
/// No cache answers, new IR, accepted-state mutation or third-stage admission.
fn build_delay(
    index: usize,
    program: &Program,
    trajectory: &Trajectory,
    driven: &[String],
    depth: usize,
) -> Result<AbsDelay, Error> {
    if depth > 2 {
        return Err(Error::new(
            "unsupported_operator",
            "absdelay composition is limited to two stages; cycles are unsupported",
        ));
    }
    let OperatorSpec::AbsDelay {
        input,
        delay,
        origin,
    } = &program.operators[index]
    else {
        return Err(Error::new(
            "unsupported_operator",
            "absdelay parent is not a fixed delay",
        ));
    };
    let (points, bounds) = if let Some(parent) =
        history_parent(input, program, driven, origin, FeedforwardKind::Delay)?
    {
        build_delay(parent, program, trajectory, driven, depth + 1)?.shifted_tube()?
    } else {
        projected_points(input, program, trajectory, driven, origin)?
    };
    AbsDelay::enclosed(points, bounds, *delay)
}

#[derive(Clone)]
struct DirectInput {
    // The source definition is immutable across candidate and replay frames.
    points: Arc<[(f64, f64)]>,
    bounds: Arc<[I]>,
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
        Self {
            points: points.into(),
            bounds: bounds.into(),
        }
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

#[derive(Clone, Copy, Debug)]
pub(crate) enum Function {
    Sin,
    Cos,
    Exp,
    Ln,
    Sqrt,
    Tanh,
}
impl From<crate::ir::MathFunction> for Function {
    fn from(value: crate::ir::MathFunction) -> Self {
        match value {
            crate::ir::MathFunction::Cos => Self::Cos,
            crate::ir::MathFunction::Exp => Self::Exp,
            crate::ir::MathFunction::Ln => Self::Ln,
            crate::ir::MathFunction::Sqrt => Self::Sqrt,
            crate::ir::MathFunction::Tanh => Self::Tanh,
        }
    }
}
impl Function {
    pub(crate) fn internal(self) -> crate::ir::EventMathFunction {
        use crate::ir::EventMathFunction as F;
        match self {
            Self::Sin => F::InternalSin,
            Self::Cos => F::InternalCos,
            Self::Exp => F::InternalExp,
            Self::Ln => F::InternalLn,
            Self::Sqrt => F::InternalSqrt,
            Self::Tanh => F::InternalTanh,
        }
    }
    pub(crate) fn from_internal(function: crate::ir::EventMathFunction) -> Option<Self> {
        use crate::ir::EventMathFunction as F;
        Some(match function {
            F::InternalSin => Self::Sin,
            F::InternalCos => Self::Cos,
            F::InternalExp => Self::Exp,
            F::InternalLn => Self::Ln,
            F::InternalSqrt => Self::Sqrt,
            F::InternalTanh => Self::Tanh,
            _ => return None,
        })
    }
    pub(crate) fn value(self, x: f64) -> f64 {
        match self {
            Self::Sin => x.sin(),
            Self::Cos => x.cos(),
            Self::Exp => x.exp(),
            Self::Ln => x.ln(),
            Self::Sqrt => x.sqrt(),
            Self::Tanh => x.tanh(),
        }
    }
    pub(crate) fn bounds(self, x: I) -> Result<I, Error> {
        match self {
            Self::Sin => sin_bounds(x),
            Self::Cos => sin_bounds(x + constant_interval(FRAC_PI_2_BITS)),
            Self::Exp => crate::math_functions::exp(x),
            Self::Ln => crate::math_functions::ln(x),
            Self::Sqrt => crate::math_functions::sqrt(x),
            Self::Tanh => crate::math_functions::tanh(x),
        }
    }
    pub(crate) fn derivative(self, x: I) -> Result<I, Error> {
        match self {
            Self::Sin => sin_bounds(x + constant_interval(FRAC_PI_2_BITS)),
            Self::Cos => Ok(-sin_bounds(x)?),
            Self::Exp => self.bounds(x),
            Self::Tanh => crate::math_functions::tanh_derivative(x),
            Self::Ln => {
                self.bounds(x)?;
                Ok(I::ONE / x)
            }
            Self::Sqrt => {
                let root = self.bounds(x)?;
                if root.lo <= 0.0 {
                    return Err(Error::new(
                        "unsupported_cross",
                        "sqrt derivative is singular at zero",
                    ));
                }
                Ok(I::ONE / (I::point(2.0) * root))
            }
        }
    }
}

#[derive(Clone)]
enum Runtime {
    DirectDerivative(direct_derivative::DirectDerivative),
    Continuous(usize),
    Idt {
        history: Idt,
        reset: Option<ResetExpression>,
    },
    IdtMod(IdtMod),
    Math(Function, SinInput),
    /// No global value exists for a source-position/call-local function.
    /// The owning Plan supplies its selected Elementary graph node instead.
    ProcedureMath,
    AbsDelay(AbsDelay),
    LaplaceNd(LaplaceNd),
    TransitionFilter {
        parent: usize,
        history: Box<transition_filter::Filter>,
    },
    TransitionIntegral {
        parent: usize,
        history: Box<transition_integral::Integral>,
    },
    Transition {
        expression: Expression,
        program: Arc<Program>,
        owner: String,
        source: Option<Box<crate::transition_source_state::Source>>,
        input: AffineState,
        input_bounds: Vec<I>,
        history: Box<Transition>,
    },
    Slew(Slew),
    SourceSlew(crate::source_slew::SourceSlew),
    SlewCascade(crate::slew_cascade::Cascade),
}

/// Structural whitelist for a transition target that reads held event state
/// and constants only. Such a target can change only inside an event body, so
/// its edges never read a node, an operator output or another history.
/// Every other expression form is treated as dependent.
fn reads_held_state_only(expr: &Expression) -> bool {
    match expr {
        Expression::State { .. } => true,
        Expression::Affine { terms, .. } => terms.is_empty(),
        Expression::Add { left, right }
        | Expression::Multiply { left, right }
        | Expression::Divide { left, right } => {
            reads_held_state_only(left) && reads_held_state_only(right)
        }
        Expression::Power { base, .. } => reads_held_state_only(base),
        Expression::Select {
            left,
            right,
            then_value,
            else_value,
            ..
        } => [left, right, then_value, else_value]
            .into_iter()
            .all(|e| reads_held_state_only(e)),
        _ => false,
    }
}

/// A transition whose deadlines cannot read, or be read by, another operator:
/// no continuous source plan and a held-state-only target expression.
fn independent_transition(entry: &Runtime) -> bool {
    matches!(
        entry,
        Runtime::Transition { source: None, expression, .. } if reads_held_state_only(expression)
    )
}

pub(crate) fn bare_real_transition_state(spec: &OperatorSpec, program: &Program) -> Option<usize> {
    let OperatorSpec::Transition {
        input: Expression::State { state },
        origin,
        ..
    } = spec
    else {
        return None;
    };
    program.states.get(*state).and_then(|s| {
        (s.kind == crate::ir::StateKind::Real && s.instance == origin.instance).then_some(*state)
    })
}

fn transition_input(
    expression: &Expression,
    program: &Program,
    states: &[I],
    owner: &str,
) -> Result<(AffineState, Vec<I>), Error> {
    crate::continuous::validate_selection(expression, program, &[], owner)?;
    let (nodes, state_dependencies, operators) =
        crate::continuous::integral_dependency_edges(expression, program, owner)?;
    if nodes.iter().any(|&n| n != 0) || !operators.is_empty() {
        return Err(Error::new(
            "unsupported_operator",
            "transition input must depend only on held instance state and constants",
        ));
    }
    // Audit every value form, including Select nested under arithmetic,
    // before resolving the currently active held branch.
    for form in crate::transition_source_plan::forms(
        expression,
        &crate::transition_source_plan::Work::default(),
    )? {
        affine(&form, program, owner)?;
    }
    let selected = crate::continuous::resolve_selection(
        expression,
        program,
        &[],
        &vec![I::ZERO; program.nodes.len()],
        states,
    )?;
    let mut input = affine(&selected, program, owner)?;
    input.state_dependencies.extend(state_dependencies);
    let row = crate::affine_bounds::affine(&selected, program)?;
    let coefficients = row[program.nodes.len()..program.nodes.len() + program.states.len()]
        .iter()
        .copied()
        .chain([*row.last().unwrap()])
        .collect();
    Ok((input, coefficients))
}

fn transition_input_shared(
    expression: &Expression,
    program: &Program,
    states: &[I],
    owner: &str,
    work: &crate::transition_source_plan::Work,
) -> Result<(AffineState, Vec<I>), Error> {
    crate::history_admission::validate_relation_paid(expression, program, owner, work)?;
    crate::continuous::validate_selection(expression, program, &[], owner)?;
    let (nodes, state_dependencies, operators) =
        crate::continuous::integral_dependency_edges(expression, program, owner)?;
    if nodes.iter().any(|&n| n != 0) || !operators.is_empty() {
        return Err(Error::new(
            "unsupported_operator",
            "transition input must depend only on held instance state and constants",
        ));
    }
    for form in crate::history_admission::target_forms(expression, work)? {
        crate::history_admission::affine_paid(&form, program, work)?;
    }
    work.debit(2, (program.nodes.len() + program.operators.len()) as u64)?;
    let selected = crate::history_admission::resolve_expression(
        expression,
        &vec![I::ZERO; program.nodes.len()],
        states,
        &vec![I::ZERO; program.operators.len()],
        work,
    )?;
    crate::history_admission::validate_relation_paid(&selected, program, owner, work)?;
    let mut input = affine(&selected, program, owner)?;
    input.state_dependencies.extend(state_dependencies);
    let row = crate::history_admission::affine_paid(&selected, program, work)?;
    work.debit(2, (program.states.len() + 1) as u64)?;
    let coefficients = row[program.nodes.len()..program.nodes.len() + program.states.len()]
        .iter()
        .copied()
        .chain([*row.last().unwrap()])
        .collect();
    Ok((input, coefficients))
}

// Evaluate the selected original held expression, never its rounded affine row.
// Admission still belongs to transition_input and its all-arm dependency audit.
fn transition_value_proof(
    expression: &Expression,
    program: &Program,
    bounds: &[I],
    proofs: Option<&crate::event_value_proof::Proofs>,
) -> Result<Option<num_rational::BigRational>, Error> {
    let nodes = vec![I::ZERO; program.nodes.len()];
    let selected = crate::continuous::resolve_selection(expression, program, &[], &nodes, bounds)?;
    Ok(crate::event_value_proof::LocalState::with_proofs(bounds, proofs).value(&selected, &nodes))
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
            "mathematical function input must have one bounded operator dependency and constants only",
        ));
    }
    let coefficient = row[coefficient_index];
    let constant = *row.last().unwrap();
    if coefficient.zero() || !coefficient.finite() || !constant.finite() {
        return Err(Error::new(
            "unsupported_operator",
            "mathematical function input must have finite bounded affine coefficients",
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
    // Lagrange's remainder depends on this certified argument interval,
    // not on the largest argument admitted by the reduction domain.
    Ok(widen(sum, taylor_remainder(r.lo.abs().max(r.hi.abs()), 19)))
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
    Ok(widen(sum, taylor_remainder(r.lo.abs().max(r.hi.abs()), 20)))
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

pub(crate) fn sin_bounds(input: I) -> Result<I, Error> {
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
    captured: Option<I>,
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
        Self {
            expression,
            captured: None,
        }
    }

    pub(crate) fn active(&self, states: &[I]) -> Result<bool, Error> {
        if let Some(value) = self.captured {
            return reset_active(value);
        }
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
        Expression::RealCall { .. }
        | Expression::UnsupportedSystemCall { .. }
        | Expression::RealBinary { .. }
        | Expression::RealBoundary { .. }
        | Expression::RealLocal { .. } => {
            return reset_terms(&crate::real_expression::materialized(expr)?)
        }
        Expression::Forcing { .. } => {
            return Err(Error::new(
                "unsupported_forcing_scope",
                "forcing marker requires its owning independent component dispatcher",
            ))
        }
        Expression::IntegerPrimitive { .. }
        | Expression::ArrayRead { .. }
        | Expression::IntegerRound { .. }
        | Expression::CheckedInteger { .. }
        | Expression::CheckedIndex { .. }
        | Expression::EventMath { .. } => {
            return Err(Error::new(
                "unsupported_operator",
                "pure event mathematics cannot reset physical history",
            ))
        }
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
        Expression::Divide { .. } | Expression::Power { .. } | Expression::Select { .. } => {
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
        Expression::RealCall { .. }
        | Expression::UnsupportedSystemCall { .. }
        | Expression::RealBinary { .. }
        | Expression::RealBoundary { .. }
        | Expression::RealLocal { .. } => return crate::event_numeric::bounds(expr, &[], states),
        Expression::Forcing { .. } => {
            return Err(Error::new(
                "unsupported_forcing_scope",
                "forcing marker requires its owning independent component dispatcher",
            ))
        }
        Expression::IntegerPrimitive { .. }
        | Expression::ArrayRead { .. }
        | Expression::IntegerRound { .. }
        | Expression::CheckedInteger { .. }
        | Expression::CheckedIndex { .. }
        | Expression::EventMath { .. } => {
            return Err(Error::new(
                "unsupported_operator",
                "pure event mathematics cannot reset physical history",
            ))
        }
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
        Expression::Divide { .. } | Expression::Power { .. } | Expression::Select { .. } => {
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
    held_targets: std::collections::BTreeMap<usize, Arc<crate::held_integer_target::Spec>>,
    pub(crate) source_context: Option<Arc<crate::transition_source_plan::ProofContext>>,
    forcing_context: Option<Arc<crate::transition_source_plan::ProofContext>>,
    shared_history: bool,
    // Ordinary typed held targets in an existing history-root calendar. Untyped
    // entries pay copies/advances on the shared owner and typed Specs pay their
    // own copies once; never a history-admission or shared-history capability.
    typed_calendar: bool,
    history_targets: std::collections::BTreeMap<usize, history_target::TargetPlan>,
    history_predicates: Vec<history_target::TargetPlan>,
    history_admission: Option<Arc<crate::history_admission::Admission>>,
    entries: Vec<Runtime>,
    changes_on_advance: Vec<bool>,
    direct: Vec<Option<DirectInput>>,
    continuous: Option<Arc<Continuous>>,
    horizon: f64,
    isolated_parameters: Vec<(usize, f64)>,
}

#[path = "transition_history_target.rs"]
mod history_target;

// Only structurally isolated instance slots are normalized here. The
// Controller retains actual measurement states; physical history never uses
// their changing values as restart/cache keys.
fn physical_parameters<'a, T: Copy>(
    values: &'a [T],
    isolated: &[(usize, f64)],
    forcing: impl Fn(f64) -> T,
) -> std::borrow::Cow<'a, [T]> {
    if isolated.is_empty() {
        return std::borrow::Cow::Borrowed(values);
    }
    let mut physical = values.to_vec();
    for &(index, initial) in isolated {
        physical[index] = forcing(initial);
    }
    std::borrow::Cow::Owned(physical)
}

// Borrows one immutable history base at one time. Every advanced trial clones
// this same base; cached values cannot escape into a different time or history.
pub(crate) struct Evaluation<'a> {
    exact_root: Option<crate::exact_source::RootTime>,
    base: &'a Operators,
    time: f64,
    pub(crate) values: Vec<f64>,
    pub(crate) bounds: Vec<I>,
}

impl Evaluation<'_> {
    // Reset/instantaneous algebraic map only. It does not install transition
    // targets or propagate the new continuous flow to the representative.
    // Each closure solve observes the same accepted physical history.
    #[cfg(test)]
    pub(crate) fn observed_after(
        &self,
        time_bounds: I,
        parameters: &[I],
    ) -> Result<(Operators, Vec<f64>, Vec<I>), Error> {
        self.observed_after_with_time_proofs(time_bounds, parameters, None)
    }

    #[cfg(test)]
    pub(crate) fn observed_after_with_time_proofs(
        &self,
        time_bounds: I,
        parameters: &[I],
        proofs: Option<&crate::exact_source::TimeProofs>,
    ) -> Result<(Operators, Vec<f64>, Vec<I>), Error> {
        self.observed_after_with_callsite_resets(time_bounds, parameters, proofs, None)
    }
    pub(crate) fn observed_after_with_callsite_resets(
        &self,
        time_bounds: I,
        parameters: &[I],
        proofs: Option<&crate::exact_source::TimeProofs>,
        captures: Option<(&[Option<I>], &crate::transition_source_plan::Work)>,
    ) -> Result<(Operators, Vec<f64>, Vec<I>), Error> {
        let physical_proofs = proofs
            .map(|proofs| {
                for (&state, proof) in proofs {
                    if parameters
                        .get(state)
                        .and_then(|b| proof.refine(*b))
                        .is_none()
                    {
                        return Err(Error::new(
                            "event_resolution",
                            "observation time proof outside matching candidate state enclosure",
                        ));
                    }
                }
                let mut physical = proofs.clone();
                for &(state, _) in &self.base.isolated_parameters {
                    physical.remove(&state);
                }
                Ok(physical)
            })
            .transpose()?;
        let parameters = physical_parameters(parameters, &self.base.isolated_parameters, I::point);
        let parameters = parameters.as_ref();
        let mut observed = self.base.candidate_clone()?;
        if let Some((captures, w)) = captures {
            observed.set_callsite_resets(captures, w)?;
        }
        if let Some(continuous) = &self.base.continuous {
            let captured = captures
                .map(|(v, w)| {
                    continuous.captured_resets_at_physical_root(
                        self.time,
                        time_bounds,
                        parameters,
                        v,
                        w,
                        self.exact_root.as_ref(),
                    )
                })
                .transpose()?;
            let continuous = captured.as_ref().unwrap_or(continuous);
            observed.continuous = Some(Arc::new(match &physical_proofs {
                Some(proofs) => continuous.mapped_event_with_proofs_at_physical_root(
                    self.time,
                    time_bounds,
                    parameters,
                    proofs,
                    self.exact_root.as_ref(),
                )?,
                None => continuous.event_at_physical_root(
                    self.time,
                    time_bounds,
                    parameters,
                    self.base.horizon,
                    false,
                    self.exact_root.as_ref(),
                )?,
            }));
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
        let sampling_window = self
            .exact_root
            .as_ref()
            .and_then(|root| root.refine(time_bounds))
            .unwrap_or(time_bounds);
        let mut values = observed.values_at_root(
            self.time,
            self.exact_root.as_ref(),
            sampling_window,
            Some(&self.values),
        )?;
        let mut bounds =
            observed.event_bounds_at_root(self.time, time_bounds, self.exact_root.as_ref())?;
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
                Runtime::Math(
                    function,
                    SinInput::Operator {
                        operator,
                        coefficient,
                        constant,
                        coefficient_bounds,
                        constant_bounds,
                    },
                ) if values[*operator] != self.values[*operator]
                    || bounds[*operator] != self.bounds[*operator] =>
                {
                    values[i] = function.value(*constant + *coefficient * values[*operator]);
                    bounds[i] = function
                        .bounds(*constant_bounds + *coefficient_bounds * bounds[*operator])?;
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

    #[cfg(test)]
    pub(crate) fn advanced_until(
        &self,
        time_bounds: I,
        states: &[f64],
        bounds: &[I],
        changed: &[usize],
        horizon: f64,
    ) -> Result<Operators, Error> {
        self.advanced_until_reusing(time_bounds, states, bounds, changed, horizon, None)
    }

    #[cfg(test)]
    pub(crate) fn advanced_until_reusing(
        &self,
        time_bounds: I,
        states: &[f64],
        bounds: &[I],
        changed: &[usize],
        horizon: f64,
        proven: Option<&Operators>,
    ) -> Result<Operators, Error> {
        self.advanced_until_with_time_proofs(
            time_bounds,
            states,
            bounds,
            changed,
            horizon,
            proven,
            None,
        )
    }

    #[allow(clippy::too_many_arguments)]
    pub(crate) fn advanced_until_with_time_proofs(
        &self,
        time_bounds: I,
        states: &[f64],
        bounds: &[I],
        changed: &[usize],
        horizon: f64,
        proven: Option<&Operators>,
        proofs: Option<&crate::exact_source::TimeProofs>,
    ) -> Result<Operators, Error> {
        self.advanced_until_with_value_proofs(
            time_bounds,
            states,
            bounds,
            changed,
            horizon,
            proven,
            proofs,
            None,
        )
    }

    #[allow(clippy::too_many_arguments)]
    pub(crate) fn advanced_until_with_value_proofs(
        &self,
        time_bounds: I,
        states: &[f64],
        bounds: &[I],
        changed: &[usize],
        horizon: f64,
        proven: Option<&Operators>,
        proofs: Option<&crate::exact_source::TimeProofs>,
        value_proofs: Option<&crate::event_value_proof::Proofs>,
    ) -> Result<Operators, Error> {
        self.advanced_until_with_callsite_resets(
            time_bounds,
            states,
            bounds,
            changed,
            horizon,
            proven,
            proofs,
            value_proofs,
            None,
        )
    }
    #[allow(clippy::too_many_arguments)]
    pub(crate) fn advanced_until_with_callsite_resets(
        &self,
        time_bounds: I,
        states: &[f64],
        bounds: &[I],
        changed: &[usize],
        horizon: f64,
        proven: Option<&Operators>,
        proofs: Option<&crate::exact_source::TimeProofs>,
        value_proofs: Option<&crate::event_value_proof::Proofs>,
        captures: Option<(&[Option<I>], &crate::transition_source_plan::Work)>,
    ) -> Result<Operators, Error> {
        let _timing = crate::diagnostics::span("history.advance_candidate");
        let physical_proofs = proofs
            .map(|proofs| {
                for (&state, proof) in proofs {
                    if bounds.get(state).and_then(|b| proof.refine(*b)).is_none() {
                        return Err(Error::new(
                            "event_resolution",
                            "history time proof outside matching candidate state enclosure",
                        ));
                    }
                }
                let mut physical = proofs.clone();
                for &(state, _) in &self.base.isolated_parameters {
                    physical.remove(&state);
                }
                Ok(physical)
            })
            .transpose()?;
        let proofs = physical_proofs.as_ref();
        let physical_value_proofs = value_proofs
            .map(|values| {
                if !crate::event_value_proof::valid(values, bounds) {
                    return Err(Error::new(
                        "event_resolution",
                        "history value proof outside matching candidate state enclosure",
                    ));
                }
                let mut physical = values.clone();
                for &(state, _) in &self.base.isolated_parameters {
                    physical.remove(&state);
                }
                Ok(physical)
            })
            .transpose()?;
        let value_proofs = physical_value_proofs.as_ref();
        let states = physical_parameters(states, &self.base.isolated_parameters, |value| value);
        let bounds = physical_parameters(bounds, &self.base.isolated_parameters, I::point);
        let states = states.as_ref();
        let bounds = bounds.as_ref();

        let copying = crate::diagnostics::span("history.clone");
        let mut candidate = self.base.candidate_clone()?;
        if let Some((captures, w)) = captures {
            candidate.set_callsite_resets(captures, w)?;
        }
        drop(copying);
        if let Some(proven) = proven {
            if candidate.entries.len() != proven.entries.len() {
                return Err(Error::new(
                    "invalid_ir",
                    "source proof replay slot mismatch",
                ));
            }
            for (entry, evidence) in candidate.entries.iter_mut().zip(&proven.entries) {
                if let (
                    Runtime::Transition {
                        source: Some(source),
                        ..
                    },
                    Runtime::Transition {
                        source: Some(proof),
                        ..
                    },
                ) = (entry, evidence)
                {
                    source.reuse_certificates(proof)?;
                }
            }
        }
        crate::diagnostics::counter("history_clone_calls", 1);
        crate::diagnostics::counter("history_clone_operator_slots", self.base.entries.len());
        candidate.horizon = horizon;
        if let (Some(continuous), Some((v, w))) = (&candidate.continuous, captures) {
            candidate.continuous = Some(Arc::new(continuous.captured_resets_at_physical_root(
                self.time,
                time_bounds,
                bounds,
                v,
                w,
                self.exact_root.as_ref(),
            )?));
        }
        if let Some(continuous) = &candidate.continuous {
            if proofs.is_some() || continuous.has_local_observation() {
                candidate.continuous = Some(Arc::new(match proofs {
                    Some(proofs) => continuous.restarted_with_proofs_at_physical_root(
                        self.time,
                        time_bounds,
                        bounds,
                        horizon,
                        proofs,
                        self.exact_root.as_ref(),
                    )?,
                    None => continuous.event_at_physical_root(
                        self.time,
                        time_bounds,
                        bounds,
                        horizon,
                        true,
                        self.exact_root.as_ref(),
                    )?,
                }));
            }
        }
        candidate.advance_with_exact(
            self.time,
            time_bounds,
            states,
            bounds,
            changed,
            self.exact_root.as_ref(),
            true,
            value_proofs,
            proofs,
        )?;
        Ok(candidate)
    }
}

impl Operators {
    fn set_callsite_resets(
        &mut self,
        captures: &[Option<I>],
        w: &crate::transition_source_plan::Work,
    ) -> Result<(), Error> {
        w.debit(2, (self.entries.len() * 24 + 32) as u64)?;
        if captures.len() != self.entries.len() {
            return Err(Error::new("invalid_ir", "reset call-site count mismatch"));
        }
        for (entry, value) in self.entries.iter_mut().zip(captures) {
            w.step()?;
            if let (
                Runtime::Idt {
                    history,
                    reset: Some(reset),
                },
                Some(value),
            ) = (entry, value)
            {
                w.debit(2, history.reset_probe_cost())?;
                reset_active(*value)?;
                reset.captured = Some(*value);
            }
        }
        Ok(())
    }
    pub(crate) fn install_callsite_resets(
        &mut self,
        time: f64,
        window: I,
        states: &[I],
        captures: &[Option<I>],
        w: &crate::transition_source_plan::Work,
    ) -> Result<(), Error> {
        self.install_callsite_resets_at_physical_root(time, window, states, captures, w, None)
    }
    pub(crate) fn install_callsite_resets_at_physical_root(
        &mut self,
        time: f64,
        window: I,
        states: &[I],
        captures: &[Option<I>],
        w: &crate::transition_source_plan::Work,
        root: Option<&crate::exact_source::RootTime>,
    ) -> Result<(), Error> {
        self.set_callsite_resets(captures, w)?;
        if let Some(continuous) = &self.continuous {
            self.continuous = Some(Arc::new(
                continuous
                    .captured_resets_at_physical_root(time, window, states, captures, w, root)?,
            ));
        }
        for (entry, value) in self.entries.iter_mut().zip(captures) {
            w.step()?;
            if let (
                Runtime::Idt {
                    history,
                    reset: Some(reset),
                },
                Some(_),
            ) = (entry, value)
            {
                w.debit(2, history.reset_probe_cost())?;
                history.advance_reset(time, window, reset.active(&[])?)?;
            }
        }
        Ok(())
    }

    pub(crate) fn bind_forcing_context(
        &mut self,
        c: Arc<crate::transition_source_plan::ProofContext>,
    ) -> Result<(), Error> {
        self.forcing_context = Some(c);
        self.charge_forcing_copy()
    }
    pub(crate) fn charge_forcing_copy(&self) -> Result<(), Error> {
        let Some(c) = &self.forcing_context else {
            return Ok(());
        };
        c.source_charge(
            "forcing_operator_copy",
            32 + self.entries.len() * 64
                + self.direct.len() * 16
                + self.changes_on_advance.len()
                + self.isolated_parameters.len() * 2,
        )?;
        if (!self.shared_history && !self.history_targets.is_empty())
            || self.continuous.is_some()
            || self.direct.iter().any(Option::is_some)
        {
            return Err(Error::new(
                "unsupported_forcing_scope",
                "forcing runtime provider differs from audited bare held graph",
            ));
        }
        if self.shared_history {
            for plan in self.history_targets.values() {
                plan.charge_copy()?;
            }
        }
        for (index, e) in self.entries.iter().enumerate() {
            let Runtime::Transition {
                expression,
                owner,
                input,
                input_bounds,
                history,
                source: None,
                ..
            } = e
            else {
                return Err(Error::new(
                    "unsupported_forcing_scope",
                    "forcing runtime provider differs from audited bare held graph",
                ));
            };
            if !self.shared_history && !matches!(expression, Expression::State { .. }) {
                return Err(Error::new(
                    "unsupported_forcing_scope",
                    "forcing requires bare held provider",
                ));
            }
            if self.shared_history {
                // This is the distinct Runtime-owned AST, not its affine row
                // or a TargetPlan-owned expression. Pay before self.clone().
                if let Some(spec) = self.held_targets.get(&index) {
                    spec.charge_runtime_copy(expression, 0)?;
                } else {
                    crate::history_admission::charge_expression_copy(expression, c.borrow_work())?;
                }
            }
            c.source_charge(
                "forcing_operator_copy",
                owner
                    .len()
                    .saturating_add(input.owned_copy_items())
                    .saturating_add(input_bounds.len())
                    .saturating_add(64),
            )?;
            history.charge_forcing_copy(c)?;
        }
        Ok(())
    }
    pub(crate) fn forcing_clone(&self) -> Result<Self, Error> {
        self.candidate_clone()
    }
    pub(crate) fn history_copy_work(&self) -> Option<&crate::transition_source_plan::Work> {
        self.history_admission
            .as_ref()
            .map(|token| token.context.borrow_work())
            .or_else(|| {
                self.source_context
                    .as_ref()
                    .filter(|c| {
                        self.shared_history
                            || self.typed_calendar
                            || c.original_binding().1.analytic_work().is_some()
                    })
                    .map(|c| c.borrow_work())
            })
    }
    pub(crate) fn candidate_clone(&self) -> Result<Self, Error> {
        // Composed Forcing pays its Runtime AST through charge_forcing_copy,
        // including the native Spec branch. This ordinary history copier only
        // covers the original Admission and the analytic empty-operator role.
        let copy_work = self
            .history_admission
            .as_ref()
            .map(|token| token.context.borrow_work())
            .or_else(|| {
                self.source_context
                    .as_ref()
                    .filter(|c| {
                        self.typed_calendar || c.original_binding().1.analytic_work().is_some()
                    })
                    .map(|c| c.borrow_work())
            });
        if let Some(w) = copy_work {
            w.debit(2, 0)?;
            w.debit(
                2,
                (self.changes_on_advance.len()
                    + self.direct.len()
                    + self.isolated_parameters.len() * 2) as u64,
            )?;
            for (index, entry) in self.entries.iter().enumerate() {
                if self.held_targets.contains_key(&index) {
                    // Typed held targets pay their AST, row and history copy
                    // once through their own Spec below.
                    continue;
                }
                let Runtime::Transition {
                    expression,
                    input,
                    input_bounds,
                    owner,
                    history,
                    source,
                    ..
                } = entry
                else {
                    return Err(Error::new(
                        "invalid_ir",
                        "non-Transition runtime entered a held history consumer",
                    ));
                };
                if source.is_some() {
                    return Err(Error::new(
                        "invalid_ir",
                        "source cursor entered a held history consumer",
                    ));
                }
                crate::history_admission::charge_expression_copy(expression, w)?;
                w.debit(
                    2,
                    (input.owned_copy_items() + input_bounds.len() * 2 + owner.len()) as u64,
                )?;
                history.charge_held_copy(&|n| w.debit(2, n as u64))?;
            }
            for plan in &self.history_predicates {
                plan.charge_copy()?;
            }
        }
        for (&index, spec) in &self.held_targets {
            if let Runtime::Transition {
                expression,
                input,
                input_bounds,
                owner,
                history,
                ..
            } = &self.entries[index]
            {
                spec.charge_runtime_copy(
                    expression,
                    input.states.len() + input.nodes.len() + input_bounds.len() + owner.len(),
                )?;
                history.charge_held_copy(&|amount| spec.charge(amount))?;
            }
        }
        self.charge_forcing_copy()?;
        Ok(self.clone())
    }

    #[allow(clippy::too_many_arguments)]
    fn refresh_history_targets(
        &mut self,
        time: f64,
        window: I,
        states: &[f64],
        bounds: &[I],
        changed: &[usize],
        initial: bool,
        exact_root: Option<&crate::exact_source::RootTime>,
    ) -> Result<(), Error> {
        let shared_work = if self.shared_history {
            let w = self
                .source_context
                .as_ref()
                .ok_or_else(|| Error::new("invalid_ir", "shared target lost source owner"))?
                .borrow_work();
            w.debit(2, 0)?;
            let count = self.history_targets.len().saturating_add(1);
            // Topological metadata scans, BTree comparisons/edits and ordered
            // indices only. AST/parent/curve payloads are charged separately.
            w.debit(
                2,
                count
                    .saturating_mul(count)
                    .saturating_mul(count)
                    .saturating_mul(32)
                    .saturating_add(self.entries.len().saturating_mul(count).saturating_mul(8))
                    as u64,
            )?;
            Some(w.clone())
        } else {
            None
        };
        let mut pending: BTreeSet<_> = self.history_targets.keys().copied().collect();
        let mut ordered = Vec::new();
        while !pending.is_empty() {
            let next = pending
                .iter()
                .copied()
                .find(|i| {
                    self.history_targets[i]
                        .dependencies
                        .iter()
                        .all(|d| !pending.contains(d))
                })
                .ok_or_else(|| {
                    Error::new(
                        "unsupported_operator",
                        "transition target history dependency cycle is unsupported",
                    )
                })?;
            pending.remove(&next);
            ordered.push(next);
        }
        for index in ordered {
            if self.entries.iter().any(|e|matches!(e,Runtime::TransitionFilter{parent,..}|Runtime::TransitionIntegral{parent,..} if *parent==index)) {
                return Err(Error::new("unsupported_operator","integral/filter consumers of history-selected transition targets are unsupported"));
            }
            let old = &self.history_targets[&index];
            if self.horizon <= time {
                if let Runtime::Transition { history, .. } = &mut self.entries[index] {
                    if let Some(w) = &shared_work {
                        history.history_advance_time(time, w)?;
                    } else {
                        history.advance_time(time)?;
                    }
                }
                continue;
            }
            let event_window = if shared_work.is_some() {
                old.window_at_paid(time)?
            } else {
                old.window_at(time)
            }
            .map_or(window, |cut| cut.hull(window));
            let mut until = self.horizon;
            for d in &old.dependencies {
                if let Some(parent) = self.history_targets.get(d) {
                    if let Some(t) = if shared_work.is_some() {
                        parent.next_after_paid(time)?
                    } else {
                        parent.next_after(time)
                    } {
                        until = until.min(t);
                    }
                }
            }
            let plan = old.prepared(time, event_window, bounds, &self.entries, until)?;
            let Runtime::Transition {
                input,
                input_bounds,
                history,
                program,
                owner,
                ..
            } = &mut self.entries[index]
            else {
                unreachable!()
            };
            let (next, row) = if let Some(w) = &shared_work {
                transition_input_shared(&plan.selected, program, bounds, owner, w)?
            } else {
                transition_input(&plan.selected, program, bounds, owner)?
            };
            let level = row
                .iter()
                .zip(bounds.iter().copied().chain([I::ONE]))
                .fold(I::ZERO, |a, (&b, c)| a + b * c);
            let value = next.value(&[], states)?;
            if initial {
                let OperatorSpec::Transition {
                    delay, rise, fall, ..
                } = &program.operators[index]
                else {
                    unreachable!()
                };
                **history = if let Some(w) = &shared_work {
                    Transition::history_enclosed(value, level, *delay, *rise, *fall, w)?
                } else {
                    Transition::enclosed(value, level, *delay, *rise, *fall)?
                };
            } else {
                let same = if let Some(w) = &shared_work {
                    crate::history_admission::same_expression_full(
                        &plan.selected,
                        &old.selected,
                        w,
                    )?
                } else {
                    plan.selected == old.selected
                };
                let may_change =
                    !same || changed.iter().any(|s| next.state_dependencies.contains(s));
                if let Some(w) = &shared_work {
                    let root = if exact_root.is_some() {
                        exact_root
                    } else {
                        old.root_at_paid(time)?
                    };
                    history.advance_at_with_history_work(
                        time,
                        event_window,
                        value,
                        level,
                        may_change,
                        root,
                        None,
                        w,
                    )?;
                } else {
                    history.advance_at_with_exact(
                        time,
                        event_window,
                        value,
                        level,
                        may_change,
                        exact_root.or_else(|| old.root_at(time)),
                    )?;
                }
            }
            *input = next;
            *input_bounds = row;
            self.history_targets.insert(index, plan);
        }
        Ok(())
    }
    pub(crate) fn exact_affine_value(
        &self,
        op: usize,
        local: bool,
        bounds: I,
    ) -> Option<(num_rational::BigRational, num_rational::BigRational)> {
        if !local {
            if let Runtime::Transition { history, .. } = self.entries.get(op)? {
                let mut history = (**history).clone();
                history.advance_time(bounds.lo).ok()?;
                return history.exact_affine_on(bounds);
            }
        }
        self.continuous.as_ref()?.exact_affine_value(op, local)
    }

    pub(crate) fn local_epoch(&self) -> Option<(crate::exact_time::Clock, f64)> {
        self.continuous.as_ref()?.local_epoch()
    }
    pub(crate) fn anchor_event(
        &mut self,
        clock: crate::exact_time::Clock,
        time: f64,
        horizon: f64,
    ) -> Result<(), Error> {
        if let Some(c) = &self.continuous {
            self.continuous = Some(Arc::new(c.anchored(clock, time, horizon)?));
        } else {
            return Err(Error::new(
                "event_resolution",
                "causal closure has no continuous physical flow",
            ));
        }
        Ok(())
    }
    pub(crate) fn history_certificate(&self) -> Option<Arc<Continuous>> {
        self.continuous.clone()
    }
    pub(crate) fn observe_local(
        &mut self,
        observation: crate::schedule::OrderedObservation,
    ) -> Result<(), Error> {
        let c = self.continuous.as_ref().ok_or_else(|| {
            Error::new(
                "event_resolution",
                "local observation lacks continuous history",
            )
        })?;
        if !observation.validate(c) {
            return Err(Error::new(
                "event_resolution",
                "local event certificate does not match the immutable physical mode history",
            ));
        }
        self.continuous = Some(Arc::new(c.local_observation(observation.delta())?));
        Ok(())
    }
    pub(crate) fn local_range(&self, index: usize, delta: I) -> Result<(I, I), Error> {
        self.check_guard(index)?;
        let Runtime::Continuous(slot) = self.entries[index] else {
            return Err(Error::new(
                "event_resolution",
                "local causal guard requires continuous network operators",
            ));
        };
        let (values, derivatives) = self.continuous.as_ref().unwrap().local_range(delta)?;
        Ok((values[slot], derivatives[slot]))
    }

    pub(crate) fn refine_ordinary_phase(&mut self, enabled: bool) {
        for entry in &mut self.entries {
            if let Runtime::IdtMod(history) = entry {
                history.refine_ordinary(enabled);
            }
        }
    }

    pub(crate) fn event_bounds(&self, time: f64, window: I) -> Result<Vec<I>, Error> {
        self.event_bounds_with_root(time, window, None)
    }

    fn event_bounds_with_root(
        &self,
        time: f64,
        window: I,
        root: Option<&crate::exact_source::RootTime>,
    ) -> Result<Vec<I>, Error> {
        let point = (window.lo == window.hi)
            .then(|| self.bounds(time))
            .transpose()?;
        if window.lo == window.hi && root.is_none() {
            return Ok(point.unwrap());
        }
        let transition_window = if let Some(root) = root {
            if let Some(w) = self.history_copy_work() {
                root.refine_with_work(window, w)?.unwrap_or(window)
            } else {
                root.refine(window).unwrap_or(window)
            }
        } else {
            window
        };
        let continuous = self
            .continuous
            .as_ref()
            .filter(|_| point.is_none())
            .map(|c| c.event_bounds(window))
            .transpose()?;
        // Value observation has a different contract from a cross guard:
        // it also covers reset histories and need not provide a derivative.
        if let Some(w) = self.history_copy_work() {
            w.debit(2, (self.entries.len() * 2) as u64)?;
        }
        let mut bounds = Vec::with_capacity(self.entries.len());
        for (index, entry) in self.entries.iter().enumerate() {
            let bound = match entry {
                Runtime::Transition { history, .. } => {
                    if let Some(w) = self.history_copy_work() {
                        history.history_observation_range(transition_window, w)?
                    } else {
                        history.observation_range(transition_window)?
                    }
                }
                Runtime::SourceSlew(history) => history.range(transition_window)?,
                _ if point.is_some() => point.as_ref().unwrap()[index],
                Runtime::ProcedureMath => I {
                    lo: f64::NEG_INFINITY,
                    hi: f64::INFINITY,
                },
                Runtime::DirectDerivative(history) => history.range(window)?,
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
                Runtime::TransitionFilter { parent, history } => {
                    history.range(self.transition(*parent)?, window)?
                }
                Runtime::TransitionIntegral { parent, history } => {
                    history.range(self.transition(*parent)?, window)?
                }
                Runtime::Math(function, SinInput::Direct(source)) => {
                    function.bounds(source.range(window)?.0)?
                }
                Runtime::Math(
                    function,
                    SinInput::Operator {
                        operator,
                        coefficient_bounds,
                        constant_bounds,
                        ..
                    },
                ) => function.bounds(*constant_bounds + *coefficient_bounds * bounds[*operator])?,
                _ => {
                    return Err(Error::new(
                        "event_resolution",
                        "operator has no certified observation over a nonpoint event window",
                    ))
                }
            };
            if !bound.finite() && !matches!(entry, Runtime::ProcedureMath) {
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
    ) -> Result<Self, Error> {
        Self::new_until_with_source_context(
            program, trajectory, driven, states, horizon, tolerances, None,
        )
    }
    #[allow(clippy::too_many_arguments)]
    pub(crate) fn new_until_with_bootstrap_bounds(
        program: &Program,
        trajectory: &Trajectory,
        driven: &[String],
        states: &[f64],
        bounds: &[I],
        horizon: f64,
        tolerances: &Tolerances,
    ) -> Result<Self, Error> {
        Self::new_until_with_seed_bounds(
            program,
            trajectory,
            driven,
            states,
            horizon,
            tolerances,
            None,
            Some(bounds),
            None,
            false,
            None,
        )
    }

    #[allow(clippy::too_many_arguments)]
    pub(crate) fn new_until_with_bootstrap_bounds_and_source(
        program: &Program,
        trajectory: &Trajectory,
        driven: &[String],
        states: &[f64],
        bounds: &[I],
        horizon: f64,
        tolerances: &Tolerances,
        shared: Option<Arc<crate::transition_source_plan::ProofContext>>,
    ) -> Result<Self, Error> {
        if shared.is_none() {
            return Self::new_until_with_bootstrap_bounds(
                program, trajectory, driven, states, bounds, horizon, tolerances,
            );
        }
        Self::new_until_with_seed_bounds(
            program,
            trajectory,
            driven,
            states,
            horizon,
            tolerances,
            shared,
            Some(bounds),
            None,
            false,
            None,
        )
    }
    #[allow(clippy::too_many_arguments)]
    pub(crate) fn new_history_consumer(
        token: Arc<crate::history_admission::Admission>,
        states: &[f64],
        horizon: f64,
    ) -> Result<Self, Error> {
        token.context.borrow_work().debit(2, 1)?;
        let context = token.context.clone();
        let work = context.borrow_work();
        work.debit(2, 0)?;
        let program = context.original_binding().0;
        work.debit(2, (states.len() * 2) as u64)?;
        let bounds: Vec<_> = states.iter().copied().map(I::point).collect();
        let mut entries = Vec::new();
        let mut origins = BTreeSet::new();
        for spec in &program.operators {
            work.step()?;
            let OperatorSpec::Transition {
                input,
                delay,
                rise,
                fall,
                origin,
            } = spec
            else {
                return Err(Error::new(
                    "unsupported_condition",
                    "ordinary history consumer requires held Transition operators only",
                ));
            };
            work.debit(
                2,
                origin
                    .instance
                    .len()
                    .saturating_add(origin.source.len())
                    .saturating_add(origin.expansion.len()) as u64,
            )?;
            if origin.instance.is_empty()
                || origin.source.is_empty()
                || origin.line == 0
                || origin.column == 0
                || !origin.valid_expansion()
                || !origins.insert((
                    &origin.instance,
                    &origin.source,
                    origin.line,
                    origin.column,
                    &origin.expansion,
                ))
            {
                return Err(Error::new(
                    "invalid_ir",
                    "invalid history consumer operator identity",
                ));
            }
            let (affine, row) = crate::history_admission::held_input(
                input,
                program,
                &origin.instance,
                &bounds,
                work,
            )?;
            work.debit(2, states.len() as u64)?;
            let value = affine.value(&[], states)?;
            let mut enclosure = I::ZERO;
            for (&a, b) in row.iter().zip(bounds.iter().copied().chain([I::ONE])) {
                work.step()?;
                enclosure = enclosure + a * b;
            }
            let expression = crate::history_admission::copy_expression(input, work)?;
            let history =
                Transition::history_enclosed(value, enclosure, *delay, *rise, *fall, work)?;
            work.debit(2, (origin.instance.len() + 3) as u64)?;
            entries.push(Runtime::Transition {
                expression,
                program: context.program_arc(),
                owner: origin.instance.clone(),
                source: None,
                input: affine,
                input_bounds: row,
                history: Box::new(history),
            });
        }
        let mut history_predicates = Vec::new();
        for index in 0..token.expanded.len() {
            if let Some(p) = history_target::TargetPlan::predicate_specification(&token, index)? {
                work.debit(2, 1)?;
                history_predicates.push(p)
            }
        }
        work.debit(2, (entries.len() * 2) as u64)?;
        let mut result = Self {
            changes_on_advance: vec![true; entries.len()],
            direct: vec![None; entries.len()],
            entries,
            source_context: Some(context),
            history_predicates,
            history_admission: Some(token),
            horizon,
            ..Self::default()
        };
        result.refresh_history_predicates(0., I::ZERO, &bounds)?;
        Ok(result)
    }
    fn refresh_history_predicates(
        &mut self,
        time: f64,
        window: I,
        bounds: &[I],
    ) -> Result<(), Error> {
        if time >= self.horizon {
            return Ok(());
        }
        for plan in &mut self.history_predicates {
            *plan = plan.prepared(time, window, bounds, &self.entries, self.horizon)?;
        }
        Ok(())
    }
    pub(crate) fn new_until_with_source_context(
        program: &Program,
        trajectory: &Trajectory,
        driven: &[String],
        states: &[f64],
        horizon: f64,
        tolerances: &Tolerances,
        shared: Option<std::sync::Arc<crate::transition_source_plan::ProofContext>>,
    ) -> Result<Self, Error> {
        Self::new_until_with_seed_bounds(
            program, trajectory, driven, states, horizon, tolerances, shared, None, None, false,
            None,
        )
    }

    #[allow(clippy::too_many_arguments)]
    pub(crate) fn new_until_with_held_points(
        program: &Program,
        trajectory: &Trajectory,
        driven: &[String],
        states: &[f64],
        bounds: &[I],
        typed_targets: &BTreeSet<usize>,
        context: Arc<crate::transition_source_plan::ProofContext>,
        horizon: f64,
        tolerances: &Tolerances,
    ) -> Result<Self, Error> {
        if typed_targets.is_empty()
            || program
                .operators
                .iter()
                .any(|s| !matches!(s, OperatorSpec::Transition { .. }))
        {
            return Err(Error::new(
                "unsupported_held_integer_target",
                "held integer targets require an all-Transition independent calendar",
            ));
        }
        Self::new_until_with_seed_bounds(
            program,
            trajectory,
            driven,
            states,
            horizon,
            tolerances,
            Some(context),
            Some(bounds),
            Some(typed_targets),
            false,
            None,
        )
    }

    #[allow(clippy::too_many_arguments)]
    pub(crate) fn new_until_with_typed_calendar(
        program: &Program,
        trajectory: &Trajectory,
        driven: &[String],
        states: &[f64],
        bounds: &[I],
        typed_targets: &BTreeSet<usize>,
        context: Arc<crate::transition_source_plan::ProofContext>,
        horizon: f64,
        tolerances: &Tolerances,
    ) -> Result<Self, Error> {
        crate::event_floor::check_provided_binding(&context, program, trajectory, driven)?;
        context.charge(8 + program.operators.len() * 8 + states.len() * 4)?;
        for (index, operator) in program.operators.iter().enumerate() {
            // Do not admit an electrical/source-selected target or another
            // operator merely because a different target has an integer proof.
            // Typed targets pay through their own Spec; every other target
            // must be an ordinary held Transition of same-owner state and
            // constants (no node, operator or source dependency).
            if typed_targets.contains(&index) {
                continue;
            }
            let held = match operator {
                OperatorSpec::Transition { input, origin, .. } => {
                    bare_real_transition_state(operator, program).is_some()
                        || crate::continuous::integral_dependency_edges(
                            input,
                            program,
                            &origin.instance,
                        )
                        .is_ok_and(|(nodes, _, operators)| nodes.is_empty() && operators.is_empty())
                }
                _ => false,
            };
            if !held {
                return Err(Error::new(
                    "unsupported_held_integer_target",
                    "typed history calendar requires typed integer or held-state Transition targets",
                ));
            }
            if let OperatorSpec::Transition { input, .. } = operator {
                crate::history_admission::charge_expression_copy(input, context.borrow_work())?;
            }
        }
        let mut result = Self::new_until_with_held_points(
            program,
            trajectory,
            driven,
            states,
            bounds,
            typed_targets,
            context,
            horizon,
            tolerances,
        )?;
        result.typed_calendar = true;
        Ok(result)
    }

    #[allow(clippy::too_many_arguments)]
    pub(crate) fn new_until_with_forcing_execution(
        program: &Program,
        trajectory: &Trajectory,
        driven: &[String],
        states: &[f64],
        bounds: Option<&[I]>,
        targets: &BTreeSet<usize>,
        horizon: f64,
        tolerances: &Tolerances,
        execution: crate::forcing_graph::PreparedExecution,
    ) -> Result<Self, Error> {
        let context = execution.context(program, trajectory, driven)?;
        if !execution.requires_composed_history() {
            return Err(Error::new(
                "invalid_ir",
                "shared target entry requires original composed qualification",
            ));
        }
        execution.charge_operator_construction()?;
        let w = context.borrow_work();
        for (index, spec) in program.operators.iter().enumerate() {
            w.step()?;
            if !targets.contains(&index) {
                let OperatorSpec::Transition { input, origin, .. } = spec else {
                    return Err(Error::new(
                        "unsupported_forcing_scope",
                        "shared targets require Transition histories",
                    ));
                };
                crate::history_admission::validate_relation_paid(
                    input,
                    program,
                    &origin.instance,
                    w,
                )?;
            }
        }
        Self::new_until_with_seed_bounds(
            program,
            trajectory,
            driven,
            states,
            horizon,
            tolerances,
            Some(context),
            bounds,
            if targets.is_empty() {
                None
            } else {
                Some(targets)
            },
            true,
            None,
        )
    }
    #[allow(clippy::too_many_arguments)]
    pub(crate) fn new_until_with_analytic_request(
        token: &crate::analytic_request::Request,
        program: &Program,
        trajectory: &Trajectory,
        driven: &[String],
        states: &[f64],
        bounds: Option<&[I]>,
        targets: &BTreeSet<usize>,
        horizon: f64,
        tolerances: &Tolerances,
    ) -> Result<Self, Error> {
        if !token.fixed_timer_held_transitions() {
            return Err(Error::new(
                "unsupported_analytic_source_consumer",
                "sampled operator entry requires its original joint role admission",
            ));
        }
        crate::event_floor::check_provided_binding(token.context(), program, trajectory, driven)?;
        Self::new_until_with_seed_bounds(
            program,
            trajectory,
            driven,
            states,
            horizon,
            tolerances,
            Some(token.context().clone()),
            bounds,
            if targets.is_empty() {
                None
            } else {
                Some(targets)
            },
            false,
            Some(token),
        )
    }
    #[allow(clippy::too_many_arguments)]
    fn new_until_with_seed_bounds(
        program: &Program,
        trajectory: &Trajectory,
        driven: &[String],
        states: &[f64],
        horizon: f64,
        tolerances: &Tolerances,
        shared: Option<std::sync::Arc<crate::transition_source_plan::ProofContext>>,
        initial_bounds: Option<&[I]>,
        typed_targets: Option<&BTreeSet<usize>>,
        shared_history: bool,
        analytic_token: Option<&crate::analytic_request::Request>,
    ) -> Result<Self, Error> {
        let _timing = crate::diagnostics::span("history.prepare");
        if let Some(bounds) = initial_bounds {
            if states.len() != program.states.len()
                || bounds.len() != states.len()
                || states
                    .iter()
                    .zip(bounds)
                    .any(|(&v, &b)| !v.is_finite() || !b.finite() || v < b.lo || v > b.hi)
            {
                return Err(Error::new(
                    "invalid_ir",
                    "invalid bounded bootstrap state enclosure",
                ));
            }
        }
        let owners = crate::passive_events::isolated_instances(program);
        let isolated_parameters = program
            .states
            .iter()
            .enumerate()
            .filter(|(_, state)| owners.contains(&state.instance))
            .map(|(index, state)| state.initial.constant().map(|initial| (index, initial)))
            .collect::<Result<Vec<_>, Error>>()?;
        let physical_states = physical_parameters(states, &isolated_parameters, |value| value);
        let states = physical_states.as_ref();
        let physical_bounds = initial_bounds
            .map(|bounds| physical_parameters(bounds, &isolated_parameters, I::point));
        let initial_bounds = physical_bounds.as_deref();

        let mut identities = BTreeSet::new();
        for (spec_index, spec) in program.operators.iter().enumerate() {
            let origin = spec.origin();
            if origin.instance.is_empty()
                || origin.source.is_empty()
                || origin.line == 0
                || origin.column == 0
                || !origin.valid_expansion()
                || !(program
                    .contributions
                    .iter()
                    .any(|c| c.origin.instance == origin.instance)
                    || matches!(spec, OperatorSpec::Math { .. } | OperatorSpec::Sin { .. })
                        && program
                            .procedures
                            .iter()
                            .any(|p| p.instance == origin.instance))
                || !identities.insert((
                    origin.instance.clone(),
                    origin.source.clone(),
                    origin.line,
                    origin.column,
                    origin.expansion.clone(),
                ))
            {
                return Err(Error::new(
                    "invalid_ir",
                    "invalid or duplicate operator call-site identity",
                ));
            }
            if let Some(actual) = initial_bounds.filter(|_| {
                typed_targets.is_none() && bare_real_transition_state(spec, program).is_none()
            }) {
                let refusal = || {
                    Error::new(
                    "unsupported_initial_history",
                    "bounded bootstrap requires only bare same-owner real-state Transition targets",
                )
                };
                let (Some(context), OperatorSpec::Transition { input, .. }) = (&shared, spec)
                else {
                    return Err(refusal());
                };
                crate::event_floor::check_provided_binding(context, program, trajectory, driven)?;
                let dependencies = crate::held_integer_target::scalar_dependencies(
                    input,
                    program,
                    &origin.instance,
                    context,
                )
                .map_err(|error| {
                    if error.kind == "unsupported_held_integer_target" {
                        refusal()
                    } else {
                        error
                    }
                })?;
                context.charge(4 + 4 * dependencies.len())?;
                if dependencies
                    .iter()
                    .any(|&state| actual[state] != I::point(states[state]))
                {
                    return Err(refusal());
                }
            }
            let input = match spec {
                OperatorSpec::Idt { input, .. }
                | OperatorSpec::LaplaceNd { input, .. }
                | OperatorSpec::Ddt { input, .. }
                | OperatorSpec::Sin { input, .. }
                | OperatorSpec::Math { input, .. }
                | OperatorSpec::AbsDelay { input, .. }
                | OperatorSpec::Transition { input, .. }
                | OperatorSpec::Slew { input, .. }
                | OperatorSpec::IdtMod { input, .. } => input,
            };
            if !program.procedures.is_empty()
                && matches!(spec, OperatorSpec::Math { .. } | OperatorSpec::Sin { .. })
                && (crate::procedure::closed_math_input(
                    input,
                    trajectory.procedure_work().ok_or_else(|| {
                        Error::new("invalid_ir", "procedure math has no execution owner")
                    })?,
                )? || crate::procedure::requires_source_frame(
                    input,
                    program,
                    trajectory.procedure_work().ok_or_else(|| {
                        Error::new("invalid_ir", "procedure math has no execution owner")
                    })?,
                )?)
            {
                // All source refs/owners were audited by the original Plan.
                // No legacy integral admission may execute a call-local input.
                continue;
            }
            if typed_targets.is_some_and(|ids| ids.contains(&spec_index)) {
                crate::held_integer_target::dependencies(
                    input,
                    program,
                    &origin.instance,
                    shared.as_ref().expect("typed owner"),
                )?;
                continue;
            }
            if typed_targets.is_some() {
                // The existing bare-real constructor consumes its actual box.
                // Other untyped targets retain the original point-seed gate;
                // typed targets above still prove their own point dependencies.
                let (_, deps, _) =
                    crate::continuous::integral_dependency_edges(input, program, &origin.instance)?;
                let actual = initial_bounds.expect("held cold frame");
                let nonpoint = deps
                    .iter()
                    .any(|&s| actual.get(s).is_none_or(|b| b.lo != b.hi));
                if nonpoint {
                    shared
                        .as_ref()
                        .expect("typed owner")
                        .charge(16 + origin.instance.len())?;
                    if bare_real_transition_state(spec, program).is_some() {
                        continue;
                    }
                    return Err(Error::new(
                        "unsupported_initial_history",
                        "typed target composition retains the original cold point-seed gate",
                    ));
                }
            }
            // Validate raw indices and ownership before any interval indexing.
            // The kernel must not assume a trusted Python producer.
            if matches!(
                spec,
                OperatorSpec::Idt { .. }
                    | OperatorSpec::LaplaceNd { .. }
                    | OperatorSpec::Ddt { .. }
                    | OperatorSpec::Math { .. }
                    | OperatorSpec::Transition { .. }
                    | OperatorSpec::Slew { .. }
            ) {
                crate::continuous::validate_integral_input(input, program, &origin.instance)?;
            } else {
                affine(input, program, &origin.instance)?;
            }
        }
        let continuous = if procedure_direct_laplace(program, trajectory, driven)? {
            // The existing direct builder below retains PWL enclosures,
            // filter error and call-site history. No RN expression is erased.
            None
        } else {
            Continuous::new_until(program, trajectory, driven, states, horizon, tolerances)?
                .map(Arc::new)
        };
        let needs_source_plan = program.operators.iter().any(|spec| match spec {
            OperatorSpec::Transition { .. } => true,
            OperatorSpec::Slew { input, .. } => crate::source_slew::selected(input),
            _ => false,
        });
        let source_context = if shared.is_some() {
            shared
        } else {
            needs_source_plan
                .then(|| {
                    crate::transition_source_plan::ProofContext::new(
                        program,
                        trajectory,
                        driven,
                        crate::transition_source_plan::Work::default(),
                    )
                })
                .transpose()?
        };
        let history_work = if shared_history {
            let context = source_context.as_ref().ok_or_else(|| {
                Error::new("invalid_ir", "shared target lost original source owner")
            })?;
            context.borrow_work().debit(2, 1)?;
            context.borrow_work().clone()
        } else if let Some(w) = trajectory.analytic_work() {
            // Analytic frames retain their original request ledger. Nonempty
            // frames additionally require the complete sampled-role token;
            // that token does not grant shared_history semantics.
            let context = source_context.as_ref().ok_or_else(|| {
                Error::new("invalid_ir", "analytic operator frame lost original owner")
            })?;
            let qualified = analytic_token.is_some_and(|token| {
                token.fixed_timer_held_transitions() && Arc::ptr_eq(context, token.context())
            });
            if context.original_binding().1.analytic_work().is_none()
                || (!program.operators.is_empty() && !qualified)
            {
                return Err(Error::new(
                    "unsupported_analytic_source_consumer",
                    "analytic operator frame requires its original empty or sampled capability",
                ));
            }
            w.debit(2, 1)?;
            w.clone()
        } else {
            crate::transition_source_plan::Work::limited([8192, 8192, 1_000_000_000])
        };
        let mut entries = Vec::new();
        let mut selected_slew_count = 0usize;
        let mut direct = Vec::new();
        let mut history_targets = std::collections::BTreeMap::new();
        let mut held_targets = std::collections::BTreeMap::new();
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
                OperatorSpec::Ddt { input, .. } => {
                    entries.push(Runtime::DirectDerivative(
                        direct_derivative::DirectDerivative::new(
                            input, program, trajectory, driven,
                        )?,
                    ));
                }
                OperatorSpec::Idt {
                    input,
                    ic,
                    reset,
                    origin,
                } => {
                    if let Some(projection) = transition_filter::projection(program, driven, index)
                    {
                        if !matches!(entries[projection.parent], Runtime::Transition { .. }) {
                            return Err(Error::new(
                                "unsupported_operator",
                                "integral forcing lacks accepted transition history",
                            ));
                        }
                        entries.push(Runtime::TransitionIntegral {
                            parent: projection.parent,
                            history: Box::new(transition_integral::Integral::new(projection, *ic)?),
                        });
                        continue;
                    }
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
                    let driven_nodes: Vec<_> = driven
                        .iter()
                        .map(|name| program.nodes.iter().position(|n| n == name).unwrap())
                        .collect();
                    let exact_source = crate::exact_source::Curve::expression(
                        input,
                        &driven_nodes,
                        &trajectory.exact_sources,
                        trajectory.config.stop,
                    );
                    entries.push(Runtime::IdtMod(
                        IdtMod::enclosed(points, bounds, *ic, *modulus, *offset)?
                            .with_exact_source(exact_source),
                    ));
                }
                OperatorSpec::Sin { input, origin } | OperatorSpec::Math { input, origin, .. } => {
                    let function = match spec {
                        OperatorSpec::Sin { .. } => Function::Sin,
                        OperatorSpec::Math { function, .. } => Function::from(*function),
                        _ => unreachable!(),
                    };
                    if !program.procedures.is_empty()
                        && (crate::procedure::closed_math_input(
                            input,
                            trajectory.procedure_work().ok_or_else(|| {
                                Error::new("invalid_ir", "procedure math has no execution owner")
                            })?,
                        )? || crate::procedure::requires_source_frame(
                            input,
                            program,
                            trajectory.procedure_work().ok_or_else(|| {
                                Error::new("invalid_ir", "procedure math has no execution owner")
                            })?,
                        )?)
                    {
                        entries.push(Runtime::ProcedureMath);
                        continue;
                    }
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
                                "mathematical function input must reference exactly one earlier operator with finite affine coefficients",
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
                    entries.push(Runtime::Math(function, sin_input));
                }
                OperatorSpec::AbsDelay { .. } => {
                    entries.push(Runtime::AbsDelay(build_delay(
                        index, program, trajectory, driven, 1,
                    )?));
                }
                OperatorSpec::LaplaceNd {
                    input,
                    numerator,
                    denominator,
                    origin,
                } => {
                    let live = transition_filter::live_specification(program, driven, index);
                    let projection = transition_filter::projection(program, driven, index);
                    if let Some(parent_index) = projection
                        .map(|p| p.parent)
                        .or_else(|| live.as_ref().map(|p| p.parent))
                    {
                        let OperatorSpec::Transition {
                            input,
                            delay,
                            rise,
                            fall,
                            origin,
                        } = &program.operators[parent_index]
                        else {
                            unreachable!()
                        };
                        let a = affine(input, program, &origin.instance)?;
                        if !a.node_dependencies.is_empty() || !a.operator_dependencies.is_empty() {
                            return Err(Error::new(
                                "unsupported_operator",
                                "transition input must depend only on instance state and constants",
                            ));
                        }
                        let row = crate::affine_bounds::affine(input, program)?;
                        let bound = row
                            [program.nodes.len()..program.nodes.len() + program.states.len()]
                            .iter()
                            .zip(states)
                            .fold(*row.last().unwrap(), |sum, (&a, &s)| sum + a * I::point(s));
                        let parent = Transition::enclosed(
                            a.value(&[], states)?,
                            bound,
                            *delay,
                            *rise,
                            *fall,
                        )?;
                        entries.push(Runtime::TransitionFilter {
                            parent: parent_index,
                            history: Box::new(match projection {
                                Some(projection) => transition_filter::Filter::new(
                                    projection,
                                    &parent,
                                    numerator,
                                    denominator,
                                )?,
                                None => transition_filter::Filter::new_live(
                                    live.unwrap(),
                                    trajectory,
                                    &parent,
                                    numerator,
                                    denominator,
                                )?,
                            }),
                        });
                        continue;
                    }
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
                    if typed_targets.is_some_and(|ids| ids.contains(&index)) {
                        let spec = crate::held_integer_target::Spec::new(
                            input,
                            program,
                            &origin.instance,
                            source_context.as_ref().unwrap().clone(),
                        )?;
                        let (value, bound) = spec.evaluate(
                            input,
                            states,
                            initial_bounds.expect("held target borrows actual cold box"),
                        )?;
                        spec.charge(
                            4 + program.nodes.len()
                                + 2 * program.states.len()
                                + program.operators.len(),
                        )?;
                        let constant = Expression::Affine {
                            constant: value,
                            terms: vec![],
                        };
                        let affine = affine(&constant, program, &origin.instance)?;
                        // Charge the original target copy and stored dependency row
                        // before allocation; Arc Spec itself never copies a tree.
                        spec.charge_runtime_copy(input, program.states.len())?;
                        entries.push(Runtime::Transition {
                            expression: input.clone(),
                            program: source_context.as_ref().unwrap().program_arc(),
                            owner: origin.instance.clone(),
                            source: None,
                            input: affine,
                            input_bounds: initial_bounds.expect("actual cold target box").to_vec(),
                            history: Box::new(Transition::enclosed(
                                value, bound, *delay, *rise, *fall,
                            )?),
                        });
                        held_targets.insert(index, spec);
                        continue;
                    }
                    let plan = if shared_history {
                        history_target::TargetPlan::specification_shared(
                            input,
                            program,
                            driven,
                            &origin.instance,
                            source_context.as_ref().unwrap().clone(),
                        )?
                    } else {
                        history_target::TargetPlan::specification(
                            input,
                            program,
                            trajectory,
                            driven,
                            &origin.instance,
                            history_work.clone(),
                        )?
                    };
                    if let Some(plan) = plan {
                        let (affine, row) = transition_input(
                            &Expression::Affine {
                                constant: 0.,
                                terms: vec![],
                            },
                            program,
                            &states.iter().copied().map(I::point).collect::<Vec<_>>(),
                            &origin.instance,
                        )?;
                        entries.push(Runtime::Transition {
                            input: affine,
                            input_bounds: row,
                            history: Box::new(Transition::enclosed(
                                0.,
                                I::ZERO,
                                *delay,
                                *rise,
                                *fall,
                            )?),
                            expression: input.clone(),
                            program: Arc::new(program.clone()),
                            owner: origin.instance.clone(),
                            source: None,
                        });
                        history_targets.insert(index, plan);
                        continue;
                    }
                    // Reuse the old Spec classification/leaf parsing. It only
                    // requests DC proof when that existing parser finds a
                    // voltage value leaf; old held dispatch spends no extra Work.
                    let (dc_input, source_spec) =
                        crate::transition_source_plan::Spec::transition_with_context(
                            input,
                            source_context.as_ref().unwrap().clone(),
                            &origin.instance,
                        )?;
                    if shared_history && source_spec.is_some() {
                        return Err(Error::new("unsupported_forcing_scope","composed forcing requires held or certified history-selected Transition targets"));
                    }
                    let input = dc_input.as_ref().unwrap_or(input);
                    let expression = input.clone();
                    let point_bounds;
                    let state_bounds = match initial_bounds {
                        Some(bounds) => bounds,
                        None => {
                            point_bounds = states.iter().copied().map(I::point).collect::<Vec<_>>();
                            &point_bounds
                        }
                    };
                    let source = source_spec
                        .map(|spec| {
                            crate::transition_source_state::Source::initialized(spec, state_bounds)
                        })
                        .transpose()?;
                    let (input, input_bounds, history, source) =
                        if let Some((source, point, changed)) = source {
                            let target = source.target();
                            let mut history = Transition::enclosed(
                                point.value,
                                point.bounds,
                                *delay,
                                *rise,
                                *fall,
                            )?;
                            history.advance_at(
                                0.,
                                I::ZERO,
                                target.value,
                                target.bounds,
                                changed,
                            )?;
                            (
                                target.affine.clone(),
                                target.coefficients.clone(),
                                history,
                                Some(Box::new(source)),
                            )
                        } else {
                            let (affine, row) = if shared_history {
                                transition_input_shared(
                                    input,
                                    program,
                                    state_bounds,
                                    &origin.instance,
                                    &history_work,
                                )?
                            } else {
                                transition_input(input, program, state_bounds, &origin.instance)?
                            };
                            let bound = row
                                .iter()
                                .zip(state_bounds.iter().copied().chain([I::ONE]))
                                .fold(I::ZERO, |sum, (&a, b)| sum + a * b);
                            let history = Transition::enclosed(
                                affine.value(&[], states)?,
                                bound,
                                *delay,
                                *rise,
                                *fall,
                            )?;
                            (affine, row, history, None)
                        };
                    entries.push(Runtime::Transition {
                        expression,
                        program: Arc::new(program.clone()),
                        owner: origin.instance.clone(),
                        source,
                        input,
                        input_bounds,
                        history: Box::new(history),
                    });
                }
                OperatorSpec::Slew {
                    input,
                    rise,
                    fall,
                    origin,
                } => {
                    if crate::source_slew::selected(input) {
                        selected_slew_count += 1;
                        if selected_slew_count > 32 {
                            return Err(Error::new(
                                "unsupported_operator",
                                "selected slew is limited to 32 independent call sites",
                            ));
                        }
                        entries.push(Runtime::SourceSlew(crate::source_slew::SourceSlew::new(
                            input,
                            source_context.as_ref().unwrap().clone(),
                            &origin.instance,
                            states,
                            *rise,
                            *fall,
                        )?));
                        continue;
                    }
                    if let Some(parent) =
                        history_parent(input, program, driven, origin, FeedforwardKind::Slew)?
                    {
                        let OperatorSpec::Slew {
                            input,
                            rise: first_rise,
                            fall: first_fall,
                            origin,
                        } = &program.operators[parent]
                        else {
                            unreachable!()
                        };
                        if history_parent(input, program, driven, origin, FeedforwardKind::Slew)?
                            .is_some()
                        {
                            return Err(Error::new(
                                "unsupported_operator",
                                "slew composition is limited to two stages; cycles are unsupported",
                            ));
                        }
                        let (points, bounds) =
                            projected_points(input, program, trajectory, driven, origin)?;
                        entries.push(Runtime::SlewCascade(crate::slew_cascade::Cascade::new(
                            points,
                            bounds,
                            [(*first_rise, *first_fall), (*rise, *fall)],
                        )?));
                    } else {
                        let (points, bounds) =
                            projected_points(input, program, trajectory, driven, origin)?;
                        entries.push(Runtime::Slew(Slew::enclosed(points, bounds, *rise, *fall)?));
                    }
                }
            }
        }
        let mut changes_on_advance = Vec::with_capacity(entries.len());
        for entry in &entries {
            let changes = match entry {
                Runtime::Idt { reset: Some(_), .. }
                | Runtime::Transition { .. }
                | Runtime::TransitionFilter { .. }
                | Runtime::TransitionIntegral { .. } => true,
                Runtime::Math(_, SinInput::Operator { operator, .. }) => {
                    changes_on_advance[*operator]
                }
                Runtime::Continuous(_) => continuous.as_ref().is_some_and(|c| c.changes_on_event()),
                Runtime::ProcedureMath
                | Runtime::DirectDerivative(_)
                | Runtime::Idt { reset: None, .. }
                | Runtime::IdtMod(_)
                | Runtime::Math(_, SinInput::Direct(_))
                | Runtime::AbsDelay(_)
                | Runtime::LaplaceNd(_)
                | Runtime::Slew(_)
                | Runtime::SourceSlew(_)
                | Runtime::SlewCascade(_) => false,
            };
            changes_on_advance.push(changes);
        }
        let mut result = Self {
            held_targets,
            source_context,
            forcing_context: None,
            shared_history,
            typed_calendar: false,
            history_targets,
            history_predicates: vec![],
            history_admission: None,
            entries,
            changes_on_advance,
            direct,
            continuous,
            horizon,
            isolated_parameters,
        };
        result.refresh_history_targets(
            0.,
            I::ZERO,
            states,
            &states.iter().copied().map(I::point).collect::<Vec<_>>(),
            &[],
            true,
            None,
        )?;
        Ok(result)
    }

    pub(crate) fn check_guard(&self, index: usize) -> Result<(), Error> {
        let entry = self
            .entries
            .get(index)
            .ok_or_else(|| Error::new("invalid_ir", "guard operator index out of range"))?;
        if self.changes_on_advance[index]
            && !matches!(entry, Runtime::Continuous(_) | Runtime::Transition { .. })
        {
            return Err(Error::new("unsupported_cross",
                "cross requires a continuous epoch history; reset/transition history is unsupported"));
        }
        if let Runtime::Continuous(slot) = entry {
            if !self.continuous.as_ref().unwrap().is_continuous(*slot) {
                return Err(Error::new("unsupported_cross",
                    "ddt or its feedthrough can jump at DC/source corners; continuous cross trajectory required"));
            }
        }
        match entry {
            Runtime::Continuous(_)
            | Runtime::Idt { .. }
            | Runtime::LaplaceNd(_)
            | Runtime::Transition { .. }
            | Runtime::Math(_, SinInput::Direct(_)) => {}
            Runtime::Math(_, SinInput::Operator { operator, .. }) => self.check_guard(*operator)?,
            _ => {
                return Err(Error::new(
                    "unsupported_cross",
                    "operator guard requires a certified continuous trajectory and derivative",
                ))
            }
        }
        Ok(())
    }

    pub(crate) fn keeps_guard_value(&self, index: usize) -> Result<bool, Error> {
        self.check_guard(index)?;
        match &self.entries[index] {
            Runtime::Transition { .. } => Ok(true),
            Runtime::Continuous(slot) => self
                .continuous
                .as_ref()
                .unwrap()
                .keeps_value_on_event(*slot),
            _ => Ok(!self.changes_on_advance[index]),
        }
    }

    pub(crate) fn range(&self, index: usize, time: I) -> Result<(I, I), Error> {
        self.check_guard(index)?;
        let entry = &self.entries[index];
        let result = match entry {
            Runtime::Transition { history, .. } => {
                // One clone, one payment: a typed Spec pays its own copy (on the
                // same owner ledger), every other entry pays the frame owner.
                if let Some(spec) = self.held_targets.get(&index) {
                    history.charge_held_copy(&|amount| spec.charge(amount))?;
                } else if let Some(w) = self.history_copy_work() {
                    history.charge_held_copy(&|n| w.debit(2, n as u64))?;
                }
                let mut history = (**history).clone();
                if let Some(w) = self.history_copy_work() {
                    history.history_advance_time(time.lo, w)?;
                    history.history_continuous_range(time, w)?
                } else {
                    history.advance_time(time.lo)?;
                    history.continuous_range(time)?
                }
            }
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
            Runtime::Math(function, input) => {
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
                    function.bounds(value)?,
                    function.derivative(value)? * derivative,
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

    fn transition(&self, parent: usize) -> Result<&Transition, Error> {
        match self.entries.get(parent) {
            Some(Runtime::Transition { history, .. }) => Ok(history),
            _ => Err(Error::new(
                "invalid_ir",
                "filter parent is not a transition history",
            )),
        }
    }

    pub(crate) fn evaluation(&self, time: f64) -> Result<Evaluation<'_>, Error> {
        self.evaluation_at_root(time, None, I::point(time))
    }

    fn root_evaluation_work(&self) -> Option<&crate::transition_source_plan::Work> {
        self.history_copy_work().or_else(|| {
            self.continuous
                .as_ref()
                .and_then(|v| v.physical_root_work())
        })
    }
    pub(crate) fn evaluation_at_root(
        &self,
        time: f64,
        exact_root: Option<&crate::exact_source::RootTime>,
        window: I,
    ) -> Result<Evaluation<'_>, Error> {
        let refined = if let Some(root) = exact_root {
            let value = if let Some(w) = self.root_evaluation_work() {
                root.refine_with_work(window, w)?
            } else {
                root.refine(window)
            };
            value.ok_or_else(|| {
                Error::new(
                    "event_resolution",
                    "exact event root is outside observation enclosure",
                )
            })?
        } else {
            window
        };
        let owned = if let Some(root) = exact_root {
            Some(if let Some(w) = self.root_evaluation_work() {
                root.clone_with_work(w)?
            } else {
                root.clone()
            })
        } else {
            None
        };
        // Preserve legacy evaluation bounds for unrelated operator kinds.
        // A certified continuous epoch is evaluated at the physical root,
        // which need not belong to the display-time image.
        let mut bounds = self.bounds(time)?;
        if let (Some(root), Some(w)) = (exact_root, self.root_evaluation_work()) {
            w.debit(2, bounds.len() as u64)?;
            for (index, bound) in bounds.iter_mut().enumerate() {
                if matches!(self.entries.get(index), Some(Runtime::Continuous(_))) {
                    if let Some((_, physical)) =
                        self.root_affine_sample_paid(index, root, refined)?
                    {
                        *bound = physical;
                    }
                }
            }
        }
        Ok(Evaluation {
            exact_root: owned,
            base: self,
            time,
            values: self.values_at_root(time, exact_root, refined, None)?,
            bounds,
        })
    }

    fn values_at_root(
        &self,
        time: f64,
        root: Option<&crate::exact_source::RootTime>,
        window: I,
        previous: Option<&[f64]>,
    ) -> Result<Vec<f64>, Error> {
        let Some(root) = root else {
            return self.values_reusing(time, previous);
        };
        if let Some(w) = self.root_evaluation_work() {
            let valid = root.refine_with_work(window, w)?.is_some();
            if !valid {
                return Err(Error::new(
                    "event_resolution",
                    "operator sample root is outside its proven window",
                ));
            }
            if window.lo == window.hi && time == window.hi {
                return self.values_reusing(time, previous);
            }
        }
        let mut values = self.values_reusing(time, previous)?;
        for index in 0..values.len() {
            if let Some((nominal, _)) = self.root_affine_sample_paid(index, root, window)? {
                values[index] = nominal;
            } else if let Runtime::Math(
                function,
                SinInput::Operator {
                    operator,
                    coefficient,
                    constant,
                    ..
                },
            ) = &self.entries[index]
            {
                // Entries are in dependency order. Recompute downstream math
                // after replacing its parent's representative sample.
                values[index] = function.value(*constant + *coefficient * values[*operator]);
                if !values[index].is_finite() {
                    return Err(Error::new("numerical_failure", "nonfinite operator value"));
                }
            }
        }
        Ok(values)
    }
    fn root_affine_sample_paid(
        &self,
        index: usize,
        root: &crate::exact_source::RootTime,
        window: I,
    ) -> Result<Option<(f64, I)>, Error> {
        if let Some(Runtime::Continuous(slot)) = self.entries.get(index) {
            return self
                .continuous
                .as_ref()
                .ok_or_else(|| Error::new("invalid_ir", "continuous root slot has no history"))?
                .sample_physical_root(*slot, root, window);
        }
        let Some(w) = self.root_evaluation_work() else {
            return Ok(self.root_affine_sample(index, root, window));
        };
        let Some(window) = root.refine_with_work(window, w)? else {
            return Ok(None);
        };
        let Some(Runtime::Transition { history, .. }) = self.entries.get(index) else {
            return Ok(None);
        };
        history.charge_held_copy(&|n| w.debit(2, n as u64))?;
        let mut history = (**history).clone();
        history.history_advance_time(window.lo, w)?;
        let Some((a, b)) = history.history_exact_affine_on(window, w)? else {
            return Ok(None);
        };
        let mut p = crate::exact_source::history_paid::Paid::new(w);
        let result = (|| {
            let product = p.op(&b, root.rational(), '*')?;
            let value = p.op(&a, &product, '+')?;
            let bounds = p.enclose(&value)?;
            let nominal = p.nearest(&value)?;
            (bounds.lo <= nominal && nominal <= bounds.hi).then_some((nominal, bounds))
        })();
        p.finish(result)
    }
    fn root_affine_sample(
        &self,
        index: usize,
        root: &crate::exact_source::RootTime,
        window: I,
    ) -> Option<(f64, I)> {
        let window = root.refine(window)?;
        // Continuous networks retain their own local clock and observation
        // certificates. Only transition histories use this absolute-time form.
        if !matches!(self.entries.get(index)?, Runtime::Transition { .. }) {
            return None;
        }
        use num_traits::ToPrimitive;
        let (a, b) = self.exact_affine_value(index, false, window)?;
        let mut budget = crate::exact_source::Budget(0);
        let product = budget.check(b * root.rational())?;
        let value = budget.check(a + product)?;
        let bounds = crate::exact_source::enclosure(&value)?;
        let nominal = value.to_f64()?;
        (bounds.lo <= nominal && nominal <= bounds.hi).then_some((nominal, bounds))
    }
    pub(crate) fn event_bounds_at_root(
        &self,
        time: f64,
        window: I,
        root: Option<&crate::exact_source::RootTime>,
    ) -> Result<Vec<I>, Error> {
        let outside = if let Some(root) = root {
            if let Some(w) = self.root_evaluation_work() {
                root.refine_with_work(window, w)?.is_none()
            } else {
                root.refine(window).is_none()
            }
        } else {
            false
        };
        if outside {
            return Err(Error::new(
                "event_resolution",
                "operator sample root is outside its proven window",
            ));
        }
        if self.history_admission.is_some() && window.lo == window.hi && time == window.hi {
            return self.bounds(time);
        }
        let mut bounds = self.event_bounds_with_root(time, window, root)?;
        if let Some(root) = root {
            for index in 0..bounds.len() {
                if let Some((_, exact)) =
                    self.root_affine_sample_paid(index, root, window)?
                        .filter(|(_, exact)| {
                            matches!(self.entries.get(index), Some(Runtime::Continuous(_)))
                                || (bounds[index].lo <= exact.lo && exact.hi <= bounds[index].hi)
                        })
                {
                    bounds[index] = exact;
                } else if let Runtime::Math(
                    function,
                    SinInput::Operator {
                        operator,
                        coefficient_bounds,
                        constant_bounds,
                        ..
                    },
                ) = &self.entries[index]
                {
                    bounds[index] = function
                        .bounds(*constant_bounds + *coefficient_bounds * bounds[*operator])?;
                }
            }
        }
        Ok(bounds)
    }

    fn values_reusing(&self, time: f64, previous: Option<&[f64]>) -> Result<Vec<f64>, Error> {
        let continuous = self
            .continuous
            .as_ref()
            .map(|c| c.values(time))
            .transpose()?;
        if let Some(w) = self.history_copy_work() {
            w.debit(2, self.entries.len() as u64)?;
        }
        // Every Transition entry reads the same exact query time.
        let mut observed: Option<crate::transition::ObservedTime> = None;
        self.entries.iter().enumerate().try_fold(
            Vec::<f64>::with_capacity(self.entries.len()),
            |mut values, (index, entry)| {
                if let Some(w) = self.history_copy_work() {
                    w.step()?;
                }
                if let Some(previous) = previous {
                    if !self.changes_on_advance[index] {
                        values.push(previous[index]);
                        return Ok(values);
                    }
                }
                let value = match entry {
                    Runtime::ProcedureMath => f64::NAN,
                    Runtime::DirectDerivative(history) => history.value(time)?,
                    Runtime::Continuous(slot) => continuous.as_ref().unwrap()[*slot],
                    Runtime::Idt { history, .. } => history.value(time)?,
                    Runtime::LaplaceNd(history) => history.value(time)?,
                    Runtime::TransitionFilter { parent, history } => {
                        history.value(self.transition(*parent)?, time)?
                    }
                    Runtime::TransitionIntegral { parent, history } => {
                        history.value(self.transition(*parent)?, time)?
                    }
                    Runtime::IdtMod(history) => history.value(time)?,
                    Runtime::Math(function, input) => match input {
                        SinInput::Direct(source) => function.value(source.value(time)?),
                        SinInput::Operator {
                            operator,
                            coefficient,
                            constant,
                            ..
                        } => function.value(*constant + *coefficient * values[*operator]),
                    },
                    Runtime::AbsDelay(history) => history.value(time)?,
                    Runtime::Transition { history, .. } => {
                        if let Some(w) = self.history_copy_work() {
                            if observed.is_none() {
                                observed = Some(crate::transition::ObservedTime::new(time, w)?);
                            }
                            history.history_value_at(observed.as_ref().unwrap(), w)?
                        } else {
                            history.value(time)?
                        }
                    }
                    Runtime::Slew(history) => history.value(time)?,
                    Runtime::SourceSlew(history) => history.value(time)?,
                    Runtime::SlewCascade(history) => history.value(time)?,
                };
                if !value.is_finite() && !matches!(entry, Runtime::ProcedureMath) {
                    return Err(Error::new("numerical_failure", "nonfinite operator value"));
                }
                values.push(value);
                Ok(values)
            },
        )
    }

    /// Called only on a disposable phase-observation seed. Physical histories,
    /// targets and immutable proofs remain those of the selected event phase.
    pub(crate) fn rebase_source_observation(&mut self, time: f64) -> Result<(), Error> {
        for entry in &mut self.entries {
            if let Runtime::Transition {
                source: Some(source),
                ..
            } = entry
            {
                source.rebase_observation(time)?;
            }
        }
        Ok(())
    }

    fn source_cuts(entry: &Runtime) -> &[crate::transition_source_plan::Cut] {
        match entry {
            Runtime::Transition {
                source: Some(source),
                ..
            } => source.cuts(),
            Runtime::SourceSlew(source) => source.cuts(),
            _ => &[],
        }
    }

    pub(crate) fn source_root_at(
        &self,
        time: f64,
    ) -> Result<Option<crate::exact_source::RootTime>, Error> {
        let mut root: Option<crate::exact_source::RootTime> = None;
        for plan in self
            .history_targets
            .values()
            .chain(self.history_predicates.iter())
        {
            if let Some(r) = plan.root_at_paid(time)? {
                let different = if let Some(old) = root.as_ref() {
                    if let Some(w) = self.history_copy_work() {
                        old.order_with_work(r, w)? != std::cmp::Ordering::Equal
                    } else {
                        old.order(r) != std::cmp::Ordering::Equal
                    }
                } else {
                    false
                };
                if different {
                    return Err(Error::new("event_resolution",format!("distinct history target roots share representative {time:e}: {:?} and {:?}",root,r)));
                }
                root = Some(if let Some(w) = self.history_copy_work() {
                    r.clone_with_work(w)?
                } else {
                    r.clone()
                });
            }
        }
        for entry in &self.entries {
            if let Some(w) = self.history_copy_work() {
                w.step()?;
            }
            {
                let cut = match entry {
                    Runtime::Transition {
                        source: Some(source),
                        ..
                    } => source.cut_at(time),
                    Runtime::SourceSlew(source) => source.cut_at(time),
                    _ => None,
                };
                if let Some(cut) = cut {
                    if root
                        .as_ref()
                        .is_some_and(|root| root.order(&cut.exact) != std::cmp::Ordering::Equal)
                    {
                        return Err(Error::new(
                            "event_resolution",
                            "distinct source roots have the same upper representative",
                        ));
                    }
                    root = Some(cut.exact.clone());
                }
            }
        }
        Ok(root)
    }

    fn physical_breakpoint(&self, after: f64) -> Option<f64> {
        self.entries
            .iter()
            .filter_map(|entry| match entry {
                Runtime::DirectDerivative(history) => history.next_breakpoint(after),
                Runtime::Continuous(_) => self.continuous.as_ref().unwrap().next_breakpoint(after),
                Runtime::Idt { history, .. } => history.next_breakpoint(after),
                Runtime::IdtMod(history) => history.next_breakpoint(after),
                Runtime::Math(_, SinInput::Direct(source)) => source.next_breakpoint(after),
                Runtime::ProcedureMath | Runtime::Math(_, SinInput::Operator { .. }) => None,
                Runtime::AbsDelay(history) => history.next_breakpoint(after),
                Runtime::LaplaceNd(history) => history.next_breakpoint(after),
                Runtime::TransitionFilter { .. } | Runtime::TransitionIntegral { .. } => None,
                Runtime::Transition {
                    history, source, ..
                } => history
                    .next_breakpoint(after)
                    .into_iter()
                    .chain(source.as_ref().and_then(|s| s.next_after(after)))
                    .min_by(f64::total_cmp),
                Runtime::Slew(history) => history.next_breakpoint(after),
                Runtime::SourceSlew(history) => history.next_breakpoint(after),
                Runtime::SlewCascade(history) => history.next_breakpoint(after),
            })
            .min_by(f64::total_cmp)
    }

    fn physical_breakpoint_checked(&self, after: f64) -> Result<Option<f64>, Error> {
        let Some(w) = self.history_copy_work() else {
            return Ok(self.physical_breakpoint(after));
        };
        w.debit(2, 0)?;
        let mut next = None;
        for entry in &self.entries {
            w.step()?;
            let Runtime::Transition {
                history,
                source: None,
                ..
            } = entry
            else {
                return Err(Error::new(
                    "invalid_ir",
                    "invalid held history deadline entry",
                ));
            };
            if let Some(time) = history.history_boundary(after, false, w)? {
                next = Some(next.map_or(time, |old: f64| old.min(time)))
            }
        }
        Ok(next)
    }
    pub(crate) fn next_breakpoint_checked(&self, after: f64) -> Result<Option<f64>, Error> {
        if self.history_admission.is_none() {
            return Ok(self.next_breakpoint(after));
        }
        let mut next = self.physical_breakpoint_checked(after)?;
        for plan in self
            .history_targets
            .values()
            .chain(&self.history_predicates)
        {
            if let Some(time) = plan.next_after_paid(after)? {
                next = Some(next.map_or(time, |old: f64| old.min(time)))
            }
        }
        Ok(next)
    }
    pub(crate) fn source_window_checked(&self, time: f64) -> Result<Option<I>, Error> {
        if self.history_admission.is_none() {
            return Ok(self.source_window_at(time));
        }
        let mut window = None;
        for plan in &self.history_predicates {
            if let Some(value) = plan.window_at_paid(time)? {
                window = Some(window.map_or(value, |old: I| old.hull(value)))
            }
        }
        Ok(window)
    }
    pub(crate) fn next_breakpoint(&self, after: f64) -> Option<f64> {
        self.physical_breakpoint(after)
            .into_iter()
            .chain(
                self.history_targets
                    .values()
                    .chain(self.history_predicates.iter())
                    .filter_map(|p| p.next_after(after)),
            )
            .min_by(f64::total_cmp)
    }

    pub(crate) fn next_breakpoint_for_event(
        &self,
        after: f64,
        event: Option<&crate::schedule::ScheduledEvent>,
        model: &crate::events::EventModel,
    ) -> Result<Option<f64>, Error> {
        let Some(event) = event else {
            return self.next_breakpoint_checked(after);
        };
        let mut target = None;
        for plan in self
            .history_targets
            .values()
            .chain(&self.history_predicates)
        {
            if let Some(time) = plan.next_after_paid(after)? {
                target = Some(target.map_or(time, |old: f64| old.min(time)))
            }
        }
        let Some(target) = target else {
            return self.physical_breakpoint_checked(after);
        };
        let mut aligned = target;
        for plan in self
            .history_targets
            .values()
            .chain(self.history_predicates.iter())
        {
            if let Some(window) = plan.window_at_paid(target)? {
                if window.lo <= event.bounds().hi && event.bounds().lo <= window.hi {
                    let crate::ir::EventTrigger::Cross { guard, .. } =
                        &model.triggers[event.event].trigger
                    else {
                        return Err(Error::new(
                            "event_resolution",
                            "history target cut overlaps an unrelated timer",
                        ));
                    };
                    let same_root = if let Some(a) = plan.root_at_paid(target)? {
                        let common = if let Some(w) = self.history_copy_work() {
                            crate::schedule::common_root_with_work(std::slice::from_ref(event), w)?
                        } else {
                            crate::schedule::common_root(std::slice::from_ref(event))
                        };
                        if let Some(b) = common {
                            if let Some(w) = self.history_copy_work() {
                                a.order_with_work(&b, w)? == std::cmp::Ordering::Equal
                            } else {
                                a.order(&b) == std::cmp::Ordering::Equal
                            }
                        } else {
                            false
                        }
                    } else {
                        false
                    };
                    if !same_root && !plan.coincides(target, guard, &model.driven)? {
                        return Err(Error::new(
                            "event_resolution",
                            "history target cut overlaps an unproved user root",
                        ));
                    }
                    aligned = event.time;
                }
            }
        }
        Ok(self
            .physical_breakpoint_checked(after)?
            .into_iter()
            .chain([aligned])
            .min_by(f64::total_cmp))
    }

    pub(crate) fn source_window_at(&self, time: f64) -> Option<I> {
        self.history_targets
            .values()
            .chain(self.history_predicates.iter())
            .filter_map(|p| p.window_at(time))
            .chain(self.entries.iter().filter_map(|entry| match entry {
                Runtime::SourceSlew(source) => source.cut_at(time).map(|cut| cut.bounds),
                _ => None,
            }))
            .reduce(I::hull)
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
        if let Some(w) = self.history_copy_work() {
            w.debit(2, (self.entries.len() * 2) as u64)?;
        }
        // Every Transition entry reads the same exact query time.
        let mut observed: Option<crate::transition::ObservedTime> = None;
        self.entries.iter().enumerate().try_fold(
            Vec::<I>::with_capacity(self.entries.len()),
            |mut bounds, (index, entry)| {
                if let Some(w)=self.history_copy_work(){w.step()?;}
                if let Some(previous) = previous {
                    if !self.changes_on_advance[index] {
                        bounds.push(previous[index]);
                        return Ok(bounds);
                    }
                }
                let bound = match entry {
                    Runtime::ProcedureMath => I{lo:f64::NEG_INFINITY,hi:f64::INFINITY},
                    Runtime::DirectDerivative(history) => history.bounds(time)?,
                    Runtime::Continuous(slot) => continuous.as_ref().unwrap()[*slot],
                    Runtime::Idt { history, .. } => history.value_bounds(time)?,
                    Runtime::LaplaceNd(history) => history.value_bounds(time)?,
                    Runtime::TransitionFilter { parent, history } => {
                        history.bounds(self.transition(*parent)?, time)?
                    }
                    Runtime::TransitionIntegral { parent, history } => {
                        history.bounds(self.transition(*parent)?, time)?
                    }
                    Runtime::IdtMod(history) => history.value_bounds(time)?,
                    Runtime::Math(function, input) => match input {
                        SinInput::Direct(source) => function.bounds(source.value_bounds(time)?)?,
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
                                        let bound = function.bounds(input)?;
                                        Ok::<_, Error>(Some(match acc {
                                            Some(previous) => union(previous, bound),
                                            None => bound,
                                        }))
                                    })?
                                    .ok_or_else(|| {
                                        Error::new(
                                            "waveform_accuracy",
                                            "cannot certify mathematical function of empty wrapped phase enclosure",
                                        )
                                    })?
                            } else {
                                let input =
                                    *constant_bounds + *coefficient_bounds * bounds[*operator];
                                function.bounds(input)?
                            }
                        }
                    },
                    Runtime::Slew(history) => history.value_bounds(time),
                    Runtime::SourceSlew(history) => history.bounds(time)?,
                    Runtime::SlewCascade(history) => history.value_bounds(time)?,
                    Runtime::AbsDelay(history) => history.value_bounds(time),
                    Runtime::Transition { history, .. } => {
                        if let Some(w) = self.history_copy_work() {
                            if observed.is_none() {
                                observed = Some(crate::transition::ObservedTime::new(time, w)?);
                            }
                            history.history_value_bounds_at(observed.as_ref().unwrap(), w)?
                        } else {
                            history.value_bounds(time)?
                        }
                    }
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
        next_root: Option<crate::exact_source::RootTime>,
    ) -> Result<(), Error> {
        let mut next_root = next_root;
        self.check_deadline_order_deferred(after, next_event, || Ok(next_root.take()))
    }

    /// Evaluate the physical event root only when an ordering consumer needs it.
    /// The provider keeps the original same-request proof owner and errors.
    pub(crate) fn check_deadline_order_deferred(
        &self,
        after: f64,
        next_event: Option<I>,
        mut root: impl FnMut() -> Result<Option<crate::exact_source::RootTime>, Error>,
    ) -> Result<(), Error> {
        let mut next_root = None;
        if let Some(w) = self.history_copy_work() {
            w.debit(2, 0)?;
            let mut deadlines = Vec::new();
            for entry in &self.entries {
                w.step()?;
                let Runtime::Transition { history, .. } = entry else {
                    return Err(Error::new(
                        "unsupported_condition",
                        "history deadline requires held Transition",
                    ));
                };
                let mut next = history.history_deadlines(after, w)?;
                crate::history_storage::append(&mut deadlines, &mut next, w)?;
            }
            for (i, d) in deadlines.iter().enumerate() {
                w.step()?;
                if let Some(event) = next_event {
                    if d.overlaps(event) {
                        if next_root.is_none() {
                            next_root = Some(root()?);
                        }
                        if !d.history_accounted_event(
                            event,
                            next_root.as_ref().and_then(Option::as_ref),
                            w,
                        )? {
                            return Err(Error::new(
                                "event_resolution",
                                "cannot certify history deadline ordering relative to user event",
                            ));
                        }
                    }
                }
                for other in &deadlines[i + 1..] {
                    w.step()?;
                    if d.overlaps(other.bounds) && !d.history_pair_ordered(other, w)? {
                        return Err(Error::new(
                            "event_resolution",
                            "cannot certify ordering of history deadlines",
                        ));
                    }
                }
            }
            return Ok(());
        }
        if let Some(event) = next_event {
            for entry in &self.entries {
                if let Runtime::Transition {
                    source: Some(source),
                    ..
                } = entry
                {
                    if next_root.is_none() {
                        next_root = Some(root()?);
                    }
                    source.check_incoming(after, event, next_root.as_ref().unwrap().as_ref())?;
                } else if let Runtime::SourceSlew(source) = entry {
                    if next_root.is_none() {
                        next_root = Some(root()?);
                    }
                    source.check_incoming(after, event, next_root.as_ref().unwrap().as_ref())?;
                }
            }
        }
        // Each deadline keeps its owner index for the independence rule below.
        let deadlines: Vec<_> = self
            .entries
            .iter()
            .enumerate()
            .flat_map(|(owner, entry)| {
                let deadlines = match entry {
                    Runtime::DirectDerivative(_) => Vec::new(),
                    Runtime::Continuous(_) => Vec::new(),
                    Runtime::Idt { .. } => Vec::new(),
                    Runtime::IdtMod(_) => Vec::new(),
                    Runtime::ProcedureMath | Runtime::Math(_, _) => Vec::new(),
                    Runtime::AbsDelay(_) => Vec::new(),
                    Runtime::LaplaceNd(_) => Vec::new(),
                    Runtime::TransitionFilter { .. } | Runtime::TransitionIntegral { .. } => {
                        Vec::new()
                    }
                    Runtime::Transition { history, .. } => history.deadlines(after),
                    Runtime::Slew(_) | Runtime::SourceSlew(_) | Runtime::SlewCascade(_) => {
                        Vec::new()
                    }
                };
                deadlines.into_iter().map(move |deadline| (owner, deadline))
            })
            .collect();
        for entry in &self.entries {
            {
                for cut in Self::source_cuts(entry)
                    .iter()
                    .filter(|cut| cut.time >= after)
                {
                    let point = cut.bounds;
                    for (_, deadline) in &deadlines {
                        if deadline.overlaps(point)
                            && !deadline.coincides_root(&cut.exact)
                            && !deadline.ordered_with_point(point)
                            && !deadline.ordered_with_root(&cut.exact)
                        {
                            return Err(Error::new("event_resolution","cannot certify transition deadline ordering relative to source-target cut"));
                        }
                    }
                }
            }
        }
        for (index, (owner, deadline)) in deadlines.iter().enumerate() {
            if let Some(event) = next_event {
                let accounted = (event.lo == event.hi && event == deadline.bounds)
                    || deadline.strictly_ordered_with(event);
                if deadline.overlaps(event) && !accounted {
                    if next_root.is_none() {
                        next_root = Some(root()?);
                    }
                    if !next_root
                        .as_ref()
                        .unwrap()
                        .as_ref()
                        .is_some_and(|root| deadline.coincides_root(root))
                    {
                        return Err(Error::new(
                            "event_resolution",
                            format!("cannot certify transition deadline ordering relative to user event: after={after:e}, deadline={deadline:?}, event={next_event:?}, exact={next_root:?}"),
                        ));
                    }
                }
            }
            for (other_owner, other) in &deadlines[index + 1..] {
                if deadline.overlaps(other.bounds)
                    && !deadline.coincides(other)
                    && !deadline.serial_representatives(other)
                    && !deadline.independent_end_checkpoints(other)
                    && !self.independent_proven_order(
                        (*owner, deadline),
                        (*other_owner, other),
                        next_event,
                    )
                {
                    return Err(Error::new(
                        "event_resolution",
                        format!("cannot certify ordering of operator deadlines: {deadline:?} and {other:?}"),
                    ));
                }
            }
        }
        Ok(())
    }

    /// Two deadlines of different independent transitions may share one
    /// representative step when their exact real times are proven distinct,
    /// the earlier one is a continuous edge end and no user event can lie in
    /// the joint enclosure. Neither edge reads the other, and an edge end
    /// starts no trajectory piece that could induce a new event before the
    /// later deadline, so the real order cannot change a target or a state.
    /// An earlier pending activation keeps the old refusal: its new ramp may
    /// induce an event inside the window that the calendar does not yet know.
    fn independent_proven_order(
        &self,
        (owner, deadline): (usize, &crate::transition::Deadline),
        (other_owner, other): (usize, &crate::transition::Deadline),
        next_event: Option<I>,
    ) -> bool {
        let hull = I {
            lo: deadline.bounds.lo.min(other.bounds.lo),
            hi: deadline.bounds.hi.max(other.bounds.hi),
        };
        owner != other_owner
            && independent_transition(&self.entries[owner])
            && independent_transition(&self.entries[other_owner])
            && next_event.is_none_or(|event| !overlaps(event, hull))
            && match deadline.proven_order(other) {
                Some(std::cmp::Ordering::Less) => deadline.continuous_end(),
                Some(std::cmp::Ordering::Greater) => other.continuous_end(),
                _ => false,
            }
    }

    #[cfg(test)]
    pub(crate) fn advance(
        &mut self,
        time: f64,
        time_bounds: I,
        states: &[f64],
        bounds: &[I],
        changed: &[usize],
    ) -> Result<(), Error> {
        self.advance_with_exact(
            time,
            time_bounds,
            states,
            bounds,
            changed,
            None,
            true,
            None,
            None,
        )
    }

    /// Consume accepted histories to the settlement boundary without installing
    /// a source mode before final held closure. The caller owns this candidate.
    pub(crate) fn advance_old(
        &mut self,
        time: f64,
        time_bounds: I,
        states: &[f64],
        bounds: &[I],
        exact_root: Option<&crate::exact_source::RootTime>,
        value_proofs: Option<&crate::event_value_proof::Proofs>,
    ) -> Result<(), Error> {
        self.advance_with_exact(
            time,
            time_bounds,
            states,
            bounds,
            &[],
            exact_root,
            false,
            value_proofs,
            None,
        )
    }

    #[allow(clippy::too_many_arguments)]
    fn advance_with_exact(
        &mut self,
        time: f64,
        time_bounds: I,
        states: &[f64],
        bounds: &[I],
        changed: &[usize],
        exact_root: Option<&crate::exact_source::RootTime>,
        install_source: bool,
        value_proofs: Option<&crate::event_value_proof::Proofs>,
        source_time_proofs: Option<&crate::exact_source::TimeProofs>,
    ) -> Result<(), Error> {
        let _timing = crate::diagnostics::span("history.advance");
        // A typed calendar meters its untyped held entries on the shared owner;
        // typed Specs still pay their own copies (candidate_clone skips them).
        let shared_work = if self.shared_history || self.typed_calendar {
            let w = self
                .source_context
                .as_ref()
                .ok_or_else(|| Error::new("invalid_ir", "shared history lost original owner"))?
                .borrow_work();
            w.debit(2, 0)?;
            w.debit(
                2,
                ((states.len() + bounds.len() + changed.len()).saturating_mul(16)
                    + self
                        .isolated_parameters
                        .len()
                        .saturating_mul(states.len() + 1)) as u64,
            )?;
            Some(w.clone())
        } else {
            None
        };
        let valid = match (value_proofs, shared_work.as_ref()) {
            (Some(proofs), Some(w)) => {
                crate::event_value_proof::valid_with_work(proofs, bounds, w)?
            }
            (Some(proofs), None) => crate::event_value_proof::valid(proofs, bounds),
            _ => true,
        };
        if !valid {
            return Err(Error::new(
                "event_resolution",
                "history value proof outside matching state enclosure",
            ));
        }
        let physical_value_proofs = value_proofs
            .map(|proofs| -> Result<_, Error> {
                if self.isolated_parameters.is_empty() {
                    // Nothing to strip: borrow the validated map, never copy it.
                    return Ok(std::borrow::Cow::Borrowed(proofs));
                }
                let mut physical = if let Some(w) = &shared_work {
                    crate::event_value_proof::history::copy_map(proofs, w)?
                } else {
                    proofs.clone()
                };
                for &(state, _) in &self.isolated_parameters {
                    if let Some(w) = &shared_work {
                        crate::event_value_proof::history::remove(&mut physical, state, w)?;
                    } else {
                        physical.remove(&state);
                    }
                }
                Ok(std::borrow::Cow::Owned(physical))
            })
            .transpose()?;
        let value_proofs = physical_value_proofs.as_deref();
        let physical_states = physical_parameters(states, &self.isolated_parameters, |value| value);
        let physical_bounds = physical_parameters(bounds, &self.isolated_parameters, I::point);
        let states = physical_states.as_ref();
        let bounds = physical_bounds.as_ref();
        let physical_changes: Vec<_> = changed
            .iter()
            .copied()
            .filter(|state| {
                !self
                    .isolated_parameters
                    .iter()
                    .any(|(index, _)| index == state)
            })
            .collect();
        let changed = physical_changes.as_slice();

        // Consume the OLD edge before any candidate target/queue mutation.
        // Compute all predictions first so a failure cannot partially update
        // this collection. The owning frame still controls atomic commit.
        let mut predictions = Vec::new();
        for (i, entry) in self.entries.iter().enumerate() {
            let (parent, reaches_deadline) = match entry {
                Runtime::TransitionFilter { parent, history } => (
                    *parent,
                    history.reaches_deadline(self.transition(*parent)?, time),
                ),
                Runtime::TransitionIntegral { parent, history } => (
                    *parent,
                    history.reaches_deadline(self.transition(*parent)?, time),
                ),
                _ => continue,
            };
            let Runtime::Transition {
                input,
                input_bounds: _,
                history: old,
                expression,
                program,
                owner,
                source,
            } = &self.entries[parent]
            else {
                unreachable!()
            };
            // A parent may settle from an exact root before its loose binary
            // end bound. Commit every child against the OLD ramp first, using
            // that same root/window and original proof-work owner.
            let reaches_deadline = reaches_deadline
                || old.end_reached_at(time, time_bounds, exact_root, shared_work.as_ref())?;
            let (value, target_bounds, may_change, preview_bounds, preview_root) = if let Some(
                source,
            ) = source
            {
                if install_source {
                    let next = source.prepare_with_epochs(
                        time,
                        time_bounds,
                        bounds,
                        exact_root,
                        source_time_proofs,
                    )?;
                    if next.steps.iter().filter(|step| step.changed).count() > 1
                        || next
                            .steps
                            .iter()
                            .any(|step| step.changed && step.root.as_ref() != exact_root)
                    {
                        return Err(Error::new("unsupported_operator", "source-window multiple target phases need a joint filter/integral history certificate"));
                    }
                    (
                        next.target.value,
                        next.target.bounds,
                        next.changed,
                        next.time_bounds,
                        next.exact_root,
                    )
                } else {
                    let (prefix, steps) = source.prepare_prefix(time_bounds, exact_root)?;
                    if steps.iter().any(|step| step.changed) {
                        return Err(Error::new("unsupported_operator", "source-window prefix needs a joint filter/integral history certificate"));
                    }
                    let old = prefix.target();
                    (
                        old.value,
                        old.bounds,
                        false,
                        time_bounds,
                        exact_root.cloned(),
                    )
                }
            } else {
                let may_change = changed.iter().any(|s| input.state_dependencies.contains(s));
                let (input, input_bounds) = transition_input(expression, program, bounds, owner)?;
                let target_bounds = input_bounds
                    .iter()
                    .zip(bounds.iter().copied().chain([I::ONE]))
                    .fold(I::ZERO, |sum, (&a, b)| sum + a * b);
                (
                    input.value(&[], states)?,
                    target_bounds,
                    may_change,
                    time_bounds,
                    exact_root.cloned(),
                )
            };
            if !may_change && !reaches_deadline {
                continue;
            }
            let target_proof = if source.is_none() {
                transition_value_proof(expression, program, bounds, value_proofs)?
            } else {
                None
            };
            let mut preview = old.clone();
            preview.advance_at_with_proofs(
                time,
                preview_bounds,
                value,
                target_bounds,
                may_change,
                preview_root.as_ref(),
                target_proof.as_ref(),
            )?;
            let prediction = match entry {
                Runtime::TransitionFilter { history, .. } => Runtime::TransitionFilter {
                    parent,
                    history: Box::new(history.committed_change(
                        old,
                        &preview,
                        time,
                        time_bounds,
                    )?),
                },
                Runtime::TransitionIntegral { history, .. } => Runtime::TransitionIntegral {
                    parent,
                    history: Box::new(history.committed_change(
                        old,
                        &preview,
                        time,
                        time_bounds,
                    )?),
                },
                _ => unreachable!(),
            };
            predictions.push((i, prediction));
        }
        for (i, prediction) in predictions {
            self.entries[i] = prediction;
        }

        if let Some(continuous) = &self.continuous {
            if !changed.is_empty() || continuous.needs_extension(self.horizon) {
                self.continuous = Some(Arc::new(continuous.event_at_physical_root(
                    time,
                    time_bounds,
                    bounds,
                    self.horizon,
                    true,
                    exact_root,
                )?));
            }
        }
        for (index, entry) in self.entries.iter_mut().enumerate() {
            if self.history_targets.contains_key(&index) {
                if let Runtime::Transition { history, .. } = entry {
                    if let Some(w) = &shared_work {
                        history.history_advance_time(time, w)?;
                    } else {
                        history.advance_time(time)?;
                    }
                }
                continue;
            }
            match entry {
                Runtime::DirectDerivative(_) => {}
                Runtime::Continuous(_) => {}
                Runtime::Idt { history, reset } => {
                    if let Some(reset) = reset {
                        history.advance_reset(time, time_bounds, reset.active(bounds)?)?;
                    }
                }
                Runtime::IdtMod(_) => {}
                Runtime::ProcedureMath | Runtime::Math(_, _) => {}
                Runtime::AbsDelay(_) => {}
                Runtime::LaplaceNd(_) => {}
                Runtime::TransitionFilter { .. } | Runtime::TransitionIntegral { .. } => {}
                Runtime::Transition {
                    input,
                    input_bounds,
                    history,
                    expression,
                    program,
                    owner,
                    source,
                } => {
                    if let Some(current) = source {
                        if !install_source {
                            let (prefix, steps) =
                                current.prepare_prefix(time_bounds, exact_root)?;
                            for step in &steps {
                                history.advance_at_with_exact(
                                    time,
                                    step.window,
                                    step.target.value,
                                    step.target.bounds,
                                    step.changed,
                                    step.root.as_ref(),
                                )?;
                            }
                            let old = prefix.target();
                            history.advance_at_with_exact(
                                time,
                                time_bounds,
                                old.value,
                                old.bounds,
                                false,
                                exact_root,
                            )?;
                            **current = prefix;
                            continue;
                        }
                        let next = current.prepare_with_epochs(
                            time,
                            time_bounds,
                            bounds,
                            exact_root,
                            source_time_proofs,
                        )?;
                        if next.steps.is_empty() {
                            history.advance_at_with_exact(
                                time,
                                next.time_bounds,
                                next.target.value,
                                next.target.bounds,
                                false,
                                next.exact_root.as_ref(),
                            )?;
                        } else {
                            for step in &next.steps {
                                history.advance_at_with_exact(
                                    time,
                                    step.window,
                                    step.target.value,
                                    step.target.bounds,
                                    step.changed,
                                    step.root.as_ref(),
                                )?;
                            }
                        }
                        *input = next.target.affine;
                        *input_bounds = next.target.coefficients;
                        **current = next.source;
                    } else if let Some(spec) = self.held_targets.get(&index) {
                        // Recheck the actual epoch even if a caller reports no
                        // nominal writes. A certificate/box change is relevant.
                        let (value, enclosure) = spec.evaluate(expression, states, bounds)?;
                        let may_change = changed.iter().any(|s| spec.dependencies.contains(s))
                            || spec
                                .dependencies
                                .iter()
                                .any(|&s| input_bounds.get(s) != bounds.get(s));
                        if may_change {
                            spec.charge(1 + bounds.len())?;
                            *input_bounds = bounds.to_vec();
                        }
                        if let Some(w) = &shared_work {
                            history.advance_at_with_history_work(
                                time,
                                time_bounds,
                                value,
                                enclosure,
                                may_change,
                                exact_root,
                                None,
                                w,
                            )?;
                        } else {
                            history.advance_at_with_proofs(
                                time,
                                time_bounds,
                                value,
                                enclosure,
                                may_change,
                                exact_root,
                                None,
                            )?;
                        }
                    } else {
                        let may_change =
                            changed.iter().any(|s| input.state_dependencies.contains(s));
                        if may_change {
                            let (next_input, next_bounds) =
                                if let Some(token) = &self.history_admission {
                                    crate::history_admission::held_input(
                                        expression,
                                        program,
                                        owner,
                                        bounds,
                                        token.context.borrow_work(),
                                    )?
                                } else if let Some(w) = &shared_work {
                                    transition_input_shared(expression, program, bounds, owner, w)?
                                } else {
                                    transition_input(expression, program, bounds, owner)?
                                };
                            *input = next_input;
                            *input_bounds = next_bounds;
                        }
                        if let Some(token) = &self.history_admission {
                            token
                                .context
                                .borrow_work()
                                .debit(2, input_bounds.len().min(bounds.len() + 1) as u64)?;
                        }
                        let enclosure = input_bounds
                            .iter()
                            .zip(bounds.iter().copied().chain([I::ONE]))
                            .fold(I::ZERO, |sum, (&a, b)| sum + a * b);
                        let may_change =
                            changed.iter().any(|s| input.state_dependencies.contains(s));
                        // Pay the nominal target (same amounts as before) before
                        // evaluating it.
                        if let Some(token) = &self.history_admission {
                            token
                                .context
                                .borrow_work()
                                .debit(2, input.states.len().min(states.len()) as u64)?;
                        } else if let Some(w) = &shared_work {
                            w.debit(
                                2,
                                (input.states.len()
                                    + input_bounds.len()
                                    + changed
                                        .len()
                                        .saturating_mul(input.state_dependencies.len() + 1))
                                    as u64,
                            )?;
                        }
                        let nominal = input.value(&[], states)?;
                        // A target proof is read only when the history installs
                        // this target; an unchanged held target never consumes it,
                        // so do not replay (or pay for) a discarded proof.
                        let target_proof =
                            if !history.installs_target(nominal, enclosure, may_change) {
                                None
                            } else if let Some(w) = &shared_work {
                                crate::diagnostics::counter("history_target_proof_replays", 1);
                                crate::event_value_proof::history::held_value(
                                    expression,
                                    program,
                                    bounds,
                                    value_proofs,
                                    w,
                                )?
                            } else if self.history_admission.is_some() {
                                None
                            } else {
                                transition_value_proof(expression, program, bounds, value_proofs)?
                            };
                        if let Some(token) = &self.history_admission {
                            history.advance_at_with_history_work(
                                time,
                                time_bounds,
                                nominal,
                                enclosure,
                                may_change,
                                exact_root,
                                target_proof.as_ref(),
                                token.context.borrow_work(),
                            )?;
                        } else if let Some(w) = &shared_work {
                            history.advance_at_with_history_work(
                                time,
                                time_bounds,
                                nominal,
                                enclosure,
                                may_change,
                                exact_root,
                                target_proof.as_ref(),
                                w,
                            )?;
                        } else {
                            history.advance_at_with_proofs(
                                time,
                                time_bounds,
                                nominal,
                                enclosure,
                                may_change,
                                exact_root,
                                target_proof.as_ref(),
                            )?;
                        }
                    }
                }
                Runtime::Slew(_) | Runtime::SourceSlew(_) | Runtime::SlewCascade(_) => {}
            }
        }
        if install_source {
            self.refresh_history_targets(
                time,
                time_bounds,
                states,
                bounds,
                changed,
                false,
                exact_root,
            )?;
            self.refresh_history_predicates(time, time_bounds, bounds)?;
        }
        Ok(())
    }

    #[cfg(test)]
    pub(crate) fn test_held_contexts(
        &self,
    ) -> Vec<Arc<crate::transition_source_plan::ProofContext>> {
        self.held_targets
            .values()
            .map(|spec| spec.test_context())
            .collect()
    }

    #[cfg(test)]
    pub(crate) fn test_transition_histories(&self) -> Vec<Transition> {
        self.entries
            .iter()
            .filter_map(|e| match e {
                Runtime::Transition { history, .. } => Some(history.as_ref().clone()),
                _ => None,
            })
            .collect()
    }
    pub(crate) fn same_reset_history_paid(
        &self,
        other: &Self,
        w: &crate::transition_source_plan::Work,
    ) -> Result<bool, Error> {
        w.debit(2, 0)?;
        w.debit(2, 6)?;
        if self.shared_history != other.shared_history
            || self.typed_calendar != other.typed_calendar
            || self.horizon != other.horizon
            || self.history_predicates.len() != other.history_predicates.len()
            || self.history_targets.len() != other.history_targets.len()
            || self.entries.len() != other.entries.len()
        {
            return Ok(false);
        }
        for (a, b) in self
            .history_predicates
            .iter()
            .zip(&other.history_predicates)
        {
            w.step()?;
            if !a.same_epoch_paid(b)? {
                return Ok(false);
            }
        }
        for ((a, ap), (b, bp)) in self.history_targets.iter().zip(&other.history_targets) {
            w.step()?;
            if a != b || !ap.same_epoch_paid(bp)? {
                return Ok(false);
            }
        }
        // The original history admission only permits held Transition runtimes.
        // Preserve same_reset_history's meaning: source markers, not target-replay values.
        for (a, b) in self.entries.iter().zip(&other.entries) {
            w.step()?;
            match (a, b) {
                (
                    Runtime::Transition { source: None, .. },
                    Runtime::Transition { source: None, .. },
                ) => (),
                _ => {
                    return Err(Error::new(
                        "event_consistency",
                        "history replay escaped admitted Transition runtimes",
                    ))
                }
            }
        }
        if self.continuous.is_some() || other.continuous.is_some() {
            return Err(Error::new(
                "event_consistency",
                "history replay escaped held histories",
            ));
        }
        Ok(true)
    }
    #[cfg(test)]
    pub(crate) fn same_forcing_frame(&self, other: &Self) -> bool {
        self.shared_history == other.shared_history
            && self.typed_calendar == other.typed_calendar
            && self.changes_on_advance == other.changes_on_advance
            && self.isolated_parameters == other.isolated_parameters
            && self.same_reset_history(other)
            && self.history_targets.iter().all(|(i, p)| {
                other
                    .history_targets
                    .get(i)
                    .is_some_and(|q| p.same_frame(q))
            })
            && self.held_targets.len() == other.held_targets.len()
            && self
                .held_targets
                .iter()
                .all(|(i, p)| other.held_targets.get(i).is_some_and(|q| Arc::ptr_eq(p, q)))
            && self
                .entries
                .iter()
                .zip(&other.entries)
                .all(|(a, b)| match (a, b) {
                    (
                        Runtime::Transition {
                            expression: ae,
                            input: ai,
                            input_bounds: ab,
                            history: ah,
                            owner: ao,
                            ..
                        },
                        Runtime::Transition {
                            expression: be,
                            input: bi,
                            input_bounds: bb,
                            history: bh,
                            owner: bo,
                            ..
                        },
                    ) => ae == be && ai == bi && ab == bb && ah == bh && ao == bo,
                    _ => false,
                })
    }
    pub(crate) fn same_reset_history_with_physical_roots(
        &self,
        other: &Self,
        w: &crate::transition_source_plan::Work,
    ) -> Result<bool, Error> {
        w.debit(2, 0)?;
        let continuous = match (&self.continuous, &other.continuous) {
            (Some(a), Some(b)) => a.same_history_with_physical_roots(b, w)?,
            (None, None) => true,
            _ => false,
        };
        Ok(self.same_reset_history_inner(other, Some(continuous)))
    }
    #[cfg(test)]
    pub(crate) fn same_reset_history(&self, other: &Self) -> bool {
        self.same_reset_history_inner(other, None)
    }
    fn same_reset_history_inner(&self, other: &Self, continuous: Option<bool>) -> bool {
        if self.history_predicates.len() != other.history_predicates.len()
            || self
                .history_predicates
                .iter()
                .zip(&other.history_predicates)
                .any(|(a, b)| !a.same_epoch(b))
        {
            return false;
        }
        if self.history_targets.len() != other.history_targets.len()
            || self.history_targets.iter().any(|(i, p)| {
                !other
                    .history_targets
                    .get(i)
                    .is_some_and(|q| p.same_epoch(q))
            })
        {
            return false;
        }
        if self.horizon != other.horizon {
            return false;
        }
        match (&self.continuous, &other.continuous) {
            (Some(a), Some(b)) if !continuous.unwrap_or_else(|| a.same_history(b)) => return false,
            _ => {}
        }
        self.entries.len() == other.entries.len()
            && self
                .entries
                .iter()
                .zip(&other.entries)
                .all(|(a, b)| match (a, b) {
                    (Runtime::SourceSlew(a), Runtime::SourceSlew(b)) => a.same_history(b),
                    (Runtime::SourceSlew(_), _) | (_, Runtime::SourceSlew(_)) => false,
                    (Runtime::Idt { history: a, .. }, Runtime::Idt { history: b, .. }) => {
                        a.same_reset_history(b)
                    }
                    (
                        Runtime::TransitionFilter { history: a, .. },
                        Runtime::TransitionFilter { history: b, .. },
                    ) => a.same_history(b),
                    (
                        Runtime::TransitionIntegral { history: a, .. },
                        Runtime::TransitionIntegral { history: b, .. },
                    ) => a.same_history(b),
                    (
                        Runtime::Transition { source: a, .. },
                        Runtime::Transition { source: b, .. },
                    ) => match (a, b) {
                        (Some(a), Some(b)) => a.same_epoch(b),
                        (None, None) => true,
                        _ => false,
                    },
                    _ => true,
                })
    }

    /// Unbound procedure slots have no scalar value. NaN is only their
    /// transport sentinel; it is never a numeric observation or a proof.
    pub(crate) fn same_values(&self, previous: &[f64], current: &[f64]) -> bool {
        previous.len() == self.entries.len()
            && current.len() == self.entries.len()
            && self
                .entries
                .iter()
                .zip(previous)
                .zip(current)
                .all(|((entry, a), b)| {
                    if matches!(entry, Runtime::ProcedureMath) {
                        a.is_nan() && b.is_nan()
                    } else {
                        a == b
                    }
                })
    }

    pub(crate) fn permits_same_time_change(&self, previous: &[f64], current: &[f64]) -> bool {
        if previous.len() != self.entries.len() || current.len() != self.entries.len() {
            return false;
        }
        let mut permitted_changes = Vec::with_capacity(self.entries.len());
        for ((entry, &before), &after) in self.entries.iter().zip(previous).zip(current) {
            if matches!(entry, Runtime::ProcedureMath) {
                if !before.is_nan() || !after.is_nan() {
                    return false;
                }
                permitted_changes.push(false);
                continue;
            }
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
                Runtime::Math(_, SinInput::Operator { operator, .. }) => {
                    permitted_changes[*operator]
                }
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

pub(crate) fn reset_active(value: I) -> Result<bool, Error> {
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

    fn uncertain_asymmetric_activation(frozen: &Evaluation<'_>) -> Result<Operators, Error> {
        // Queue insertion is valid. Direction becomes undecidable when this
        // asymmetric target activates; reject that private trial before commit.
        let candidate = frozen.advanced(I::point(1.), &[0.25], &[I { lo: 0.2, hi: 0.3 }], &[0])?;
        candidate.evaluation(1.125)?.advanced(
            I::point(1.125),
            &[0.25],
            &[I { lo: 0.2, hi: 0.3 }],
            &[],
        )
    }

    #[test]
    fn transition_filter_candidates_consume_old_edge_and_rollback_failed_targets() {
        use serde_json::json;
        let origin =
            |column| json!({"source":"chain.va","line":1,"column":column,"instance":"dut"});
        let program:Program=serde_json::from_value(json!({
            "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","u","edge","filtered"],
            "states":[{"instance":"dut","name":"q","kind":"real","initial":0.25}],
            "operators":[
                {"kind":"transition","input":{"op":"state","state":0},"delay":0.125,"rise":0.5,"fall":0.75,"origin":origin(1)},
                {"kind":"laplace_nd","input":{"op":"affine","constant":0,"terms":[{"node":2,"coefficient":1}]},"numerator":[1],"denominator":[1,0.25],"origin":origin(2)}],
            "contributions":[
                {"branch":{"instance":"dut","local_positive":"edge","local_negative":"r","kind":"voltage"},"positive":2,"negative":0,"rhs":{"op":"operator","operator":0},"origin":origin(3)},
                {"branch":{"instance":"dut","local_positive":"filtered","local_negative":"r","kind":"voltage"},"positive":3,"negative":0,"rhs":{"op":"operator","operator":1},"origin":origin(4)}]
        })).unwrap();
        let trajectory = Trajectory::new(
            crate::ir::TransientInputs {
                analytic_sources: vec![],
                pwl_errors_v: None,
                strobetimes: vec![],
                pwl: vec![vec![[0., 0.], [3., 0.]]],
                output_times: vec![0., 3.],
                stop: 3.,
                max_step: 3.,
            },
            1,
        )
        .unwrap();
        let base = Operators::new(&program, &trajectory, &["u".into()], &[0.25]).unwrap();
        assert!(base.single_filter_budget(3.).is_some());
        let original = base.bounds(3.).unwrap();
        let frozen = base.evaluation(1.).unwrap();
        let failed = uncertain_asymmetric_activation(&frozen);
        assert!(failed.is_err());
        assert_eq!(base.bounds(3.).unwrap(), original);
        let candidate = frozen
            .advanced(I::point(1.), &[1.25], &[I::point(1.25)], &[0])
            .unwrap();
        let clean = frozen
            .advanced(I::point(1.), &[1.25], &[I::point(1.25)], &[0])
            .unwrap();
        assert!(candidate.same_reset_history(&clean));
        let at = candidate.bounds(1.625).unwrap()[1];
        let expected = 0.25 + (0.5 - 0.25 * (1. - (-2.0_f64).exp())) / 0.5;
        assert!(at.lo <= expected && expected <= at.hi);
        assert_eq!(
            candidate.bounds(0.5).unwrap()[1],
            base.bounds(0.5).unwrap()[1]
        );
        assert_eq!(base.bounds(3.).unwrap(), original);
    }

    #[test]
    fn live_transition_filter_candidates_consume_old_edge_and_rollback_failed_targets() {
        use serde_json::json;
        let origin =
            |column| json!({"source":"chain.va","line":1,"column":column,"instance":"dut"});
        let program:Program=serde_json::from_value(json!({
            "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","u","edge","filtered"],
            "states":[{"instance":"dut","name":"q","kind":"real","initial":0.25}],
            "operators":[
                {"kind":"transition","input":{"op":"state","state":0},"delay":0.125,"rise":0.5,"fall":0.75,"origin":origin(1)},
                {"kind":"laplace_nd","input":{"op":"affine","constant":0,"terms":[{"node":2,"coefficient":1}]},"numerator":[1],"denominator":[1,0.25],"origin":origin(2)}],
            "contributions":[
                {"branch":{"instance":"dut","local_positive":"edge","local_negative":"r","kind":"voltage"},"positive":2,"negative":0,"rhs":{"op":"multiply","left":{"op":"affine","constant":2,"terms":[{"node":1,"coefficient":1}]},"right":{"op":"operator","operator":0}},"origin":origin(3)},
                {"branch":{"instance":"dut","local_positive":"filtered","local_negative":"r","kind":"voltage"},"positive":3,"negative":0,"rhs":{"op":"operator","operator":1},"origin":origin(4)}]
        })).unwrap();
        let trajectory = Trajectory::new(
            crate::ir::TransientInputs {
                analytic_sources: vec![],
                pwl_errors_v: None,
                strobetimes: vec![],
                pwl: vec![vec![[0., 0.], [3., 3.]]],
                output_times: vec![0., 3.],
                stop: 3.,
                max_step: 3.,
            },
            1,
        )
        .unwrap();
        let base = Operators::new(&program, &trajectory, &["u".into()], &[0.25]).unwrap();
        assert!(base.single_filter_budget(3.).is_none());
        // Two operators and a currently zero coefficient are still live forcing.
        let mut zero_initial = program.clone();
        if let Expression::Multiply { left, .. } = &mut zero_initial.contributions[0].rhs {
            if let Expression::Affine { constant, .. } = left.as_mut() {
                *constant = 0.;
            }
        }
        let zero_base = Operators::new(&zero_initial, &trajectory, &["u".into()], &[0.25]).unwrap();
        assert!(zero_base.single_filter_budget(0.).is_none());
        assert!(zero_base.bounds(1.).unwrap()[1].hi > 0.);
        let original = base.bounds(3.).unwrap();
        let frozen = base.evaluation(1.).unwrap();
        let failed = uncertain_asymmetric_activation(&frozen);
        assert!(failed.is_err());
        assert_eq!(base.bounds(3.).unwrap(), original);
        let candidate = frozen
            .advanced(I::point(1.), &[1.25], &[I::point(1.25)], &[0])
            .unwrap();
        let clean = frozen
            .advanced(I::point(1.), &[1.25], &[I::point(1.25)], &[0])
            .unwrap();
        assert!(candidate.same_reset_history(&clean));
        let at = candidate.bounds(1.625).unwrap()[1];
        // Before the edge starts at 1.125, input=.25*(2+t).
        // At start, the slope becomes .25 + 2*(2+1.125), then p2=2.
        let tau = 0.25;
        let first = |t: f64| 0.5 + 0.25 * (t - tau) + 0.25 * tau * (-t / tau).exp();
        let p0 = 0.25 * (2. + 1.125);
        let p1 = 0.25 + 2. * (2. + 1.125);
        let p2 = 2.;
        let h = 0.5;
        let q0 = p0 - tau * p1 + 2. * tau * tau * p2;
        let qh = p0 + p1 * h + p2 * h * h - tau * (p1 + 2. * p2 * h) + 2. * tau * tau * p2;
        let expected = qh + (first(1.125) - q0) * (-h / tau).exp();
        assert!((0.5 * (at.lo + at.hi) - expected).abs() < 1e-11);
        assert!(at.hi - at.lo < 1e-10);
        assert_eq!(
            candidate.bounds(0.5).unwrap()[1],
            base.bounds(0.5).unwrap()[1]
        );
        assert_eq!(base.bounds(3.).unwrap(), original);
        let accepted = candidate;
        let accepted_before = accepted.bounds(2.5).unwrap();
        let retry_base = accepted.evaluation(1.5).unwrap();
        let failed = retry_base
            .advanced(I::point(1.5), &[1.25], &[I { lo: 1.2, hi: 1.3 }], &[0])
            .and_then(|candidate| {
                candidate.evaluation(1.625)?.advanced(
                    I::point(1.625),
                    &[1.25],
                    &[I { lo: 1.2, hi: 1.3 }],
                    &[],
                )
            });
        assert!(failed.is_err());
        assert_eq!(accepted.bounds(2.5).unwrap(), accepted_before);
        let retry = retry_base
            .advanced(I::point(1.5), &[-0.25], &[I::point(-0.25)], &[0])
            .unwrap();
        let direct = retry_base
            .advanced(I::point(1.5), &[-0.25], &[I::point(-0.25)], &[0])
            .unwrap();
        assert!(retry.same_reset_history(&direct));
        assert_eq!(retry.bounds(2.5).unwrap(), direct.bounds(2.5).unwrap());
        assert_eq!(
            retry.bounds(1.25).unwrap()[1],
            accepted.bounds(1.25).unwrap()[1]
        );
    }

    #[test]
    fn transition_integral_candidates_consume_old_edge_and_retry_failed_targets() {
        use serde_json::json;
        let origin =
            |column| json!({"source":"chain.va","line":1,"column":column,"instance":"dut"});
        let program:Program=serde_json::from_value(json!({
            "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","u","edge","filtered"],
            "states":[{"instance":"dut","name":"q","kind":"real","initial":0.25}],
            "operators":[
                {"kind":"transition","input":{"op":"state","state":0},"delay":0.125,"rise":0.5,"fall":0.75,"origin":origin(1)},
                {"kind":"idt","input":{"op":"affine","constant":0,"terms":[{"node":2,"coefficient":1}]},"ic":0.1,"origin":origin(2)}],
            "contributions":[
                {"branch":{"instance":"dut","local_positive":"edge","local_negative":"r","kind":"voltage"},"positive":2,"negative":0,"rhs":{"op":"operator","operator":0},"origin":origin(3)},
                {"branch":{"instance":"dut","local_positive":"filtered","local_negative":"r","kind":"voltage"},"positive":3,"negative":0,"rhs":{"op":"operator","operator":1},"origin":origin(4)}]
        })).unwrap();
        let trajectory = Trajectory::new(
            crate::ir::TransientInputs {
                analytic_sources: vec![],
                pwl_errors_v: None,
                strobetimes: vec![],
                pwl: vec![vec![[0., 0.], [3., 0.]]],
                output_times: vec![0., 3.],
                stop: 3.,
                max_step: 3.,
            },
            1,
        )
        .unwrap();
        let base = Operators::new(&program, &trajectory, &["u".into()], &[0.25]).unwrap();
        let original = base.bounds(3.).unwrap();
        let frozen = base.evaluation(1.).unwrap();
        let failed = uncertain_asymmetric_activation(&frozen);
        assert!(failed.is_err());
        assert_eq!(base.bounds(3.).unwrap(), original);
        let candidate = frozen
            .advanced(I::point(1.), &[1.25], &[I::point(1.25)], &[0])
            .unwrap();
        let clean = frozen
            .advanced(I::point(1.), &[1.25], &[I::point(1.25)], &[0])
            .unwrap();
        assert!(candidate.same_reset_history(&clean));
        let at = candidate.bounds(1.625).unwrap()[1];
        let expected = 0.1 + 0.25 * 1.625 + 0.25;
        assert!(at.lo <= expected && expected <= at.hi);
        assert_eq!(
            candidate.bounds(0.5).unwrap()[1],
            base.bounds(0.5).unwrap()[1]
        );
        assert_eq!(base.bounds(3.).unwrap(), original);
    }

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
                    analytic_sources: vec![],
                    pwl_errors_v: None,
                    strobetimes: Vec::new(),
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
            {
                // Both bounded flows can cross the source corner. Their
                // candidates must remain disposable and reproducible.
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
                analytic_sources: vec![],
                pwl_errors_v: None,
                strobetimes: Vec::new(),
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

#[cfg(test)]
mod exact_deadline_review_tests {
    use super::*;
    use crate::exact_source::RootTime;

    #[test]
    fn exact_endpoint_child_commit_retries_after_rejected_window_without_losing_old_ramp() {
        let origin =
            serde_json::json!({"source":"endpoint.va","line":1,"column":1,"instance":"dut"});
        let integral_origin =
            serde_json::json!({"source":"endpoint.va","line":2,"column":1,"instance":"dut"});
        let filter_origin =
            serde_json::json!({"source":"endpoint.va","line":3,"column":1,"instance":"dut"});
        let program: Program = serde_json::from_value(serde_json::json!({
            "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","y"],
            "states":[{"instance":"dut","name":"q","kind":"real","initial":0.5}],
            "operators":[
                {"kind":"transition","input":{"op":"state","state":0},"delay":0,"rise":2.5e-7,"fall":2.5e-7,"origin":origin},
                {"kind":"idt","input":{"op":"operator","operator":0},"ic":0,"origin":integral_origin},
                {"kind":"laplace_nd","input":{"op":"operator","operator":0},"numerator":[1],"denominator":[1,2e-7],"origin":filter_origin}
            ],"contributions":[{"branch":{"instance":"dut","local_positive":"y","local_negative":"r","kind":"voltage"},"positive":1,"negative":0,"rhs":{"op":"operator","operator":0},"origin":origin}],"events":[]
        })).unwrap();
        let trajectory = Trajectory::new(
            crate::ir::TransientInputs {
                analytic_sources: vec![],
                pwl_errors_v: None,
                strobetimes: vec![],
                pwl: vec![],
                output_times: vec![0., 3e-6],
                stop: 3e-6,
                max_step: 3.125e-8,
            },
            0,
        )
        .unwrap();
        let mut base = Operators::new(&program, &trajectory, &[], &[0.5]).unwrap();
        let start = 2e-6;
        base.advance_with_exact(
            start,
            I::point(start),
            &[-0.5],
            &[I::point(-0.5)],
            &[0],
            RootTime::point(start).as_ref(),
            false,
            None,
            None,
        )
        .unwrap();
        let retained = base.clone();
        let tick = 2.25e-6;
        let root = RootTime::point(tick).unwrap();
        // This is the mechanism detector: exact ordering ends the parent even
        // though its old enclosing upper deadline is after the representative.
        assert!(base.transition(0).unwrap().next_breakpoint(start).unwrap() > tick);
        assert!(base
            .transition(0)
            .unwrap()
            .end_reached_at(tick, I::point(tick), Some(&root), None)
            .unwrap());
        for _ in 0..2 {
            let bad = tick.next_up();
            let error = base
                .advance_with_exact(
                    bad,
                    I::point(bad),
                    &[-0.5],
                    &[I::point(-0.5)],
                    &[],
                    Some(&root),
                    false,
                    None,
                    None,
                )
                .unwrap_err();
            assert_eq!(error.kind, "event_resolution");
            assert!(base.same_reset_history(&retained));
        }
        let discarded = base
            .evaluation_at_root(tick, Some(&root), I::point(tick))
            .unwrap()
            .advanced(I::point(tick), &[-0.5], &[I::point(-0.5)], &[])
            .unwrap();
        assert!(base.same_reset_history(&retained));
        let mut clean = retained.clone();
        for candidate in [&mut base, &mut clean] {
            candidate
                .advance_with_exact(
                    tick,
                    I::point(tick),
                    &[-0.5],
                    &[I::point(-0.5)],
                    &[],
                    Some(&root),
                    false,
                    None,
                    None,
                )
                .unwrap();
        }
        for time in [tick, 2.5e-6] {
            let actual = base.values(time).unwrap();
            let duration: f64 = 2.5e-7;
            let tau: f64 = 2e-7;
            let at_end = 0.5 - (duration - tau * (1. - (-duration / tau).exp())) / duration;
            let filtered = -0.5 + (at_end + 0.5) * (-(time - start - duration) / tau).exp();
            let area = 1e-6 - 0.5 * (time - start - duration);
            assert!((actual[1] - area).abs() < 2e-14);
            assert!((actual[2] - filtered).abs() < 1e-9);
            assert_eq!(actual, clean.values(time).unwrap());
            assert_eq!(actual, discarded.values(time).unwrap());
        }
    }

    #[test]
    fn evaluation_rejects_incompatible_exact_window_without_changing_history() {
        let origin = serde_json::json!({"source":"evaluation_review.va","line":1,"column":1,"instance":"dut"});
        let program:Program=serde_json::from_value(serde_json::json!({
            "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","y"],
            "states":[{"instance":"dut","name":"q","kind":"real","initial":0}],
            "operators":[{"kind":"transition","input":{"op":"state","state":0},"delay":0.125,"rise":0.25,"fall":0.25,"origin":origin}],
            "contributions":[{"branch":{"instance":"dut","local_positive":"y","local_negative":"r","kind":"voltage"},
                "positive":1,"negative":0,"rhs":{"op":"operator","operator":0},"origin":origin}]
        })).unwrap();
        let trajectory = Trajectory::new(
            crate::ir::TransientInputs {
                analytic_sources: vec![],
                pwl_errors_v: None,
                strobetimes: vec![],
                pwl: vec![],
                output_times: vec![0., 2.],
                stop: 2.,
                max_step: 0.125,
            },
            0,
        )
        .unwrap();
        let mut base = Operators::new(&program, &trajectory, &[], &[0.]).unwrap();
        base.advance(0.25, I::point(0.25), &[1.], &[I::ONE], &[0])
            .unwrap();
        let retained = base.clone();
        let root = RootTime::from_clock(
            crate::exact_time::Clock {
                start: 0.5,
                period: 0.,
                index: 0,
            },
            I::point(0.5),
        )
        .unwrap();
        for window in [
            I::point(0.75),
            I { lo: 0.6, hi: 0.4 },
            I {
                lo: f64::NAN,
                hi: 0.5,
            },
            I {
                lo: 0.,
                hi: f64::INFINITY,
            },
        ] {
            let error = base
                .evaluation_at_root(1., Some(&root), window)
                .err()
                .unwrap();
            assert_eq!(error.kind, "event_resolution");
            assert_eq!(
                error.message,
                "exact event root is outside observation enclosure"
            );
            assert!(base.same_reset_history(&retained));
            for time in [0.3, 0.4, 0.5, 1.] {
                assert_eq!(base.values(time).unwrap(), retained.values(time).unwrap());
                assert_eq!(base.bounds(time).unwrap(), retained.bounds(time).unwrap());
            }
        }
        let valid = base
            .evaluation_at_root(0.5, Some(&root), I::point(0.5))
            .unwrap();
        assert_eq!(
            valid.exact_root.as_ref().unwrap().order(&root),
            std::cmp::Ordering::Equal
        );
    }
}

#[cfg(test)]
mod held_nested_select_audit_tests {
    use super::*;

    fn fixture() -> (Program, Expression) {
        let program: Program = serde_json::from_value(serde_json::json!({
            "schema_version": crate::ir::SCHEMA_VERSION,
            "nodes": ["0", "y"],
            "states": [{"instance":"dut","name":"q","kind":"integer","initial":1}],
            "contributions": []
        }))
        .unwrap();
        let constant = |v| {
            Box::new(Expression::Affine {
                constant: v,
                terms: vec![],
            })
        };
        let branch = Expression::Select {
            relation: crate::ir::Relation::Gt,
            left: Box::new(Expression::State { state: 0 }),
            right: constant(0.),
            then_value: constant(1.),
            else_value: constant(0.),
            origin: serde_json::from_value(serde_json::json!({
                "source":"held-audit.va","line":1,"column":1,"instance":"dut"
            }))
            .unwrap(),
        };
        (program, branch)
    }

    #[test]
    fn unselected_nested_forms_cannot_hide_nonlinearity_or_voltage_dependency() {
        let (p, mut branch) = fixture();
        if let Expression::Select { else_value, .. } = &mut branch {
            **else_value = Expression::Multiply {
                left: Box::new(Expression::State { state: 0 }),
                right: Box::new(Expression::State { state: 0 }),
            };
        }
        let wrapped = Expression::Add {
            left: Box::new(Expression::State { state: 0 }),
            right: Box::new(branch),
        };
        let states = vec![I::ONE; p.states.len()];
        assert_eq!(
            transition_input(&wrapped, &p, &states, "dut")
                .err()
                .unwrap()
                .kind,
            "unsupported_transient"
        );
        let (p, mut branch) = fixture();
        if let Expression::Select { else_value, .. } = &mut branch {
            **else_value = Expression::Multiply {
                left: Box::new(Expression::Affine {
                    constant: 0.,
                    terms: vec![],
                }),
                right: Box::new(Expression::Affine {
                    constant: 0.,
                    terms: vec![crate::ir::Term {
                        node: 1,
                        coefficient: 1.,
                    }],
                }),
            };
        }
        let wrapped = Expression::Add {
            left: Box::new(Expression::State { state: 0 }),
            right: Box::new(branch),
        };
        assert_eq!(
            transition_input(&wrapped, &p, &states, "dut")
                .err()
                .unwrap()
                .kind,
            "unsupported_operator"
        );
    }

    #[test]
    fn nested_held_forms_retain_original_expansion_cap() {
        let (p, branch) = fixture();
        let mut expression = branch.clone();
        for _ in 1..14 {
            expression = Expression::Add {
                left: Box::new(expression),
                right: Box::new(branch.clone()),
            };
        }
        let error = transition_input(&expression, &p, &[I::ONE], "dut")
            .err()
            .unwrap();
        assert_eq!(error.kind, "step_budget");
        assert!(error.message.contains("affine expansion exhausted"));
    }

    #[test]
    fn accepted_nested_edge_survives_late_uncertain_target_and_retry() {
        let (p, mut select) = fixture();
        if let Expression::Select {
            relation,
            right,
            then_value,
            else_value,
            ..
        } = &mut select
        {
            *relation = crate::ir::Relation::Lt;
            **right = Expression::Affine {
                constant: 2.,
                terms: vec![],
            };
            **then_value = Expression::Affine {
                constant: 0.,
                terms: vec![],
            };
            **else_value = Expression::Affine {
                constant: 1.,
                terms: vec![],
            };
        }
        let input = Expression::Add {
            left: Box::new(Expression::State { state: 0 }),
            right: Box::new(Expression::Multiply {
                left: Box::new(Expression::Affine {
                    constant: -2.,
                    terms: vec![],
                }),
                right: Box::new(select),
            }),
        };
        let mut value = serde_json::to_value(p).unwrap();
        value["operators"] = serde_json::json!([{
            "kind":"transition", "input":input, "delay":0., "rise":0.25, "fall":0.25,
            "origin":{"source":"held-retry.va","line":1,"column":1,"instance":"dut"}
        }]);
        value["contributions"] = serde_json::json!([{
            "branch":{"instance":"dut","local_positive":"y","local_negative":"r","kind":"voltage"},
            "positive":1,"negative":0,"rhs":{"op":"operator","operator":0},
            "origin":{"source":"held-retry.va","line":1,"column":2,"instance":"dut"}
        }]);
        let program: Program = serde_json::from_value(value).unwrap();
        let trajectory = Trajectory::new(
            crate::ir::TransientInputs {
                analytic_sources: vec![],
                pwl_errors_v: None,
                strobetimes: vec![],
                pwl: vec![],
                output_times: vec![0., 3.25],
                stop: 3.25,
                max_step: 0.01,
            },
            0,
        )
        .unwrap();
        let mut accepted = Operators::new(&program, &trajectory, &[], &[0.]).unwrap();
        accepted
            .advance(1., I::point(1.), &[1.], &[I::ONE], &[0])
            .unwrap();
        let prefix = accepted.bounds(3.25).unwrap();
        let first_midpoint = accepted.bounds(1.125).unwrap()[0];
        assert!(first_midpoint.lo <= 0.5 && 0.5 <= first_midpoint.hi);
        let clean = accepted.clone();
        for _ in 0..2 {
            let failed = accepted.evaluation(2.).unwrap().advanced(
                I::point(2.),
                &[2.],
                &[I { lo: 1., hi: 3. }],
                &[0],
            );
            assert!(failed.is_err());
            assert_eq!(accepted.bounds(3.25).unwrap(), prefix);
            assert_eq!(accepted.bounds(0.5).unwrap()[0], I::ZERO);
        }
        let mut retry = accepted;
        let mut clean = clean;
        for history in [&mut retry, &mut clean] {
            history
                .advance(2., I::point(2.), &[2.], &[I::point(2.)], &[0])
                .unwrap();
            let second_midpoint = history.bounds(2.125).unwrap()[0];
            assert!(second_midpoint.lo <= 0.5 && 0.5 <= second_midpoint.hi);
            history
                .advance(3., I::point(3.), &[3.], &[I::point(3.)], &[0])
                .unwrap();
        }
        // An Operators frame owns its current edge, not earlier controller frames.
        for time in [3., 3.125, 3.25] {
            assert_eq!(retry.bounds(time).unwrap(), clean.bounds(time).unwrap());
            let clip = |t: f64| (4. * t).clamp(0., 1.);
            let exact = clip(time - 1.) - clip(time - 2.) + clip(time - 3.);
            let bounds = retry.bounds(time).unwrap()[0];
            assert!(bounds.lo <= exact && exact <= bounds.hi);
        }
    }
    #[test]
    fn dc_target_keeps_accepted_history_after_failed_trial_and_retry() {
        let (mut p, mut input) = fixture();
        p.nodes.push("u".into());
        if let Expression::Select { then_value, .. } = &mut input {
            **then_value = Expression::Affine {
                constant: 0.,
                terms: vec![crate::ir::Term {
                    node: 2,
                    coefficient: 1.,
                }],
            };
        }
        let mut value = serde_json::to_value(p).unwrap();
        value["operators"] = serde_json::json!([{
            "kind":"transition", "input":input, "delay":0., "rise":0.25, "fall":0.25,
            "origin":{"source":"dc-retry.va","line":1,"column":1,"instance":"dut"}
        }]);
        value["contributions"] = serde_json::json!([{
            "branch":{"instance":"dut","local_positive":"y","local_negative":"r","kind":"voltage"},
            "positive":1,"negative":0,"rhs":{"op":"operator","operator":0},
            "origin":{"source":"dc-retry.va","line":1,"column":2,"instance":"dut"}
        }]);
        let program: Program = serde_json::from_value(value).unwrap();
        let trajectory = Trajectory::new(
            crate::ir::TransientInputs {
                analytic_sources: vec![],
                pwl_errors_v: None,
                strobetimes: vec![],
                pwl: vec![vec![[0., 1.], [4., 1.]]],
                output_times: vec![0., 4.],
                stop: 4.,
                max_step: 4.,
            },
            1,
        )
        .unwrap();
        let mut accepted = Operators::new(&program, &trajectory, &["u".into()], &[0.]).unwrap();
        accepted
            .advance(1., I::point(1.), &[1.], &[I::ONE], &[0])
            .unwrap();
        let clean = accepted.clone();
        let prefix = accepted.bounds(2.25).unwrap();
        for _ in 0..2 {
            let failed = accepted.evaluation(2.).unwrap().advanced(
                I::point(2.),
                &[0.],
                &[I { lo: -1., hi: 1. }],
                &[0],
            );
            assert!(failed.is_err());
            assert!(accepted.same_reset_history(&clean));
            assert_eq!(accepted.bounds(2.25).unwrap(), prefix);
        }
        let mut retry = accepted;
        let mut clean = clean;
        for history in [&mut retry, &mut clean] {
            history
                .advance(2., I::point(2.), &[0.], &[I::ZERO], &[0])
                .unwrap();
        }
        for time in [2., 2.125, 2.25] {
            assert_eq!(retry.bounds(time).unwrap(), clean.bounds(time).unwrap());
            let exact = 1. - (4. * (time - 2.)).clamp(0., 1.);
            let bounds = retry.bounds(time).unwrap()[0];
            assert!(bounds.lo <= exact && exact <= bounds.hi);
        }
    }
}

#[cfg(test)]
mod deferred_deadline_proof_controls {
    use super::*;
    fn held() -> Operators {
        let origin =
            serde_json::json!({"source":"deadline.va","line":1,"column":1,"instance":"dut"});
        let p:Program=serde_json::from_value(serde_json::json!({
          "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","y"],
          "states":[{"instance":"dut","name":"q","kind":"real","initial":0}],
          "operators":[{"kind":"transition","input":{"op":"state","state":0},"delay":0.125,"rise":0.25,"fall":0.25,"origin":origin}],
          "contributions":[{"branch":{"instance":"dut","local_positive":"y","local_negative":"r","kind":"voltage"},"positive":1,"negative":0,"rhs":{"op":"operator","operator":0},"origin":origin}]})).unwrap();
        let t = Trajectory::new(
            crate::ir::TransientInputs {
                analytic_sources: vec![],
                pwl_errors_v: None,
                strobetimes: vec![],
                pwl: vec![],
                output_times: vec![0., 2.],
                stop: 2.,
                max_step: 0.125,
            },
            0,
        )
        .unwrap();
        let mut o = Operators::new(&p, &t, &[], &[0.]).unwrap();
        o.advance(0.25, I::point(0.25), &[1.], &[I::ONE], &[0])
            .unwrap();
        o
    }
    #[test]
    fn separated_event_does_not_request_an_unused_exact_root() {
        let o = held();
        o.check_deadline_order_deferred(0.25, Some(I { lo: 1., hi: 1.1 }), || {
            panic!("separated deadline consumed an unnecessary proof")
        })
        .unwrap();
        o.check_deadline_order_deferred(0.25, None, || {
            panic!("no pending event has no exact proof")
        })
        .unwrap();
    }
    #[test]
    fn overlapping_event_still_requires_the_original_exact_identity() {
        let o = held();
        let window = I {
            lo: 0.374,
            hi: 0.376,
        };
        let mut calls = 0;
        o.check_deadline_order_deferred(0.25, Some(window), || {
            calls += 1;
            Ok(crate::exact_source::RootTime::point(0.375))
        })
        .unwrap();
        assert_eq!(calls, 1);
        let error = o
            .check_deadline_order_deferred(0.25, Some(window), || {
                Ok(crate::exact_source::RootTime::point(0.4))
            })
            .unwrap_err();
        assert_eq!(error.kind, "event_resolution");
        let error = o
            .check_deadline_order_deferred(0.25, Some(window), || Ok(None))
            .unwrap_err();
        assert_eq!(error.kind, "event_resolution");
    }
    #[test]
    fn exhausted_original_proof_owner_propagates_and_leaves_history_unchanged() {
        let o = held();
        let before = o.clone();
        let w = crate::transition_source_plan::Work::limited([128, 8192, 0]);
        let mut helpers = 0;
        for _ in 0..2 {
            let error = o
                .check_deadline_order_deferred(
                    0.25,
                    Some(I {
                        lo: 0.374,
                        hi: 0.376,
                    }),
                    || {
                        w.debit(2, 1)?;
                        helpers += 1;
                        Ok(crate::exact_source::RootTime::point(0.375))
                    },
                )
                .unwrap_err();
            assert_eq!(error.kind, "step_budget");
            assert_eq!(helpers, 0);
            assert!(o.same_reset_history(&before));
            for t in [0.25, 0.375, 0.5, 0.625, 1.] {
                assert_eq!(o.values(t).unwrap(), before.values(t).unwrap());
                assert_eq!(o.bounds(t).unwrap(), before.bounds(t).unwrap());
            }
        }
        assert_eq!(w.spent(), 2);
    }
}

#[cfg(test)]
mod independent_proven_order_controls {
    use super::*;
    use std::cmp::Ordering;
    // y ends at 0.25+0.1+0.7 and z starts at 0.25+0.8. The exact sums differ
    // by less than one ULP at 1.05: no binary64 time separates the two real
    // deadlines, and the exact rationals prove that y ends first.
    fn pair() -> Operators {
        pair_with(0.7, 0.8)
    }
    // y ends at 0.25+0.1+0.2, z starts at 0.25+0.3: here the exact start is
    // the earlier deadline, by about 2.8e-17.
    fn start_first() -> Operators {
        pair_with(0.2, 0.3)
    }
    fn pair_with(rise: f64, delay: f64) -> Operators {
        let origin = |column: u32| serde_json::json!({"source":"pair.va","line":1,"column":column,"instance":"dut"});
        let p:Program=serde_json::from_value(serde_json::json!({
          "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","y","z"],
          "states":[{"instance":"dut","name":"q","kind":"real","initial":0},
                    {"instance":"dut","name":"p","kind":"real","initial":0}],
          "operators":[
            {"kind":"transition","input":{"op":"state","state":0},"delay":0.1,"rise":rise,"fall":rise,"origin":origin(1)},
            {"kind":"transition","input":{"op":"state","state":1},"delay":delay,"rise":0.05,"fall":0.05,"origin":origin(2)}],
          "contributions":[
            {"branch":{"instance":"dut","local_positive":"y","local_negative":"r","kind":"voltage"},"positive":1,"negative":0,"rhs":{"op":"operator","operator":0},"origin":origin(3)},
            {"branch":{"instance":"dut","local_positive":"z","local_negative":"r","kind":"voltage"},"positive":2,"negative":0,"rhs":{"op":"operator","operator":1},"origin":origin(4)}]})).unwrap();
        let t = Trajectory::new(
            crate::ir::TransientInputs {
                analytic_sources: vec![],
                pwl_errors_v: None,
                strobetimes: vec![],
                pwl: vec![],
                output_times: vec![0., 1.5],
                stop: 1.5,
                max_step: 0.125,
            },
            0,
        )
        .unwrap();
        let mut o = Operators::new(&p, &t, &[], &[0., 0.]).unwrap();
        o.advance(0.25, I::point(0.25), &[1., 1.], &[I::ONE, I::ONE], &[0, 1])
            .unwrap();
        // Consume y's start so that its edge end becomes a pending deadline.
        let Runtime::Transition { history, .. } = &o.entries[0] else {
            unreachable!()
        };
        let start = history.deadlines(0.25).remove(0).bounds;
        o.advance(start.hi, start, &[1., 1.], &[I::ONE, I::ONE], &[])
            .unwrap();
        o
    }
    fn deadlines(o: &Operators) -> (crate::transition::Deadline, crate::transition::Deadline) {
        let get = |index: usize| {
            let Runtime::Transition { history, .. } = &o.entries[index] else {
                unreachable!()
            };
            history.deadlines(0.5)
        };
        let end = get(0).pop().unwrap();
        let start = get(1).into_iter().next().unwrap();
        (end, start)
    }
    fn refuse(o: &Operators, event: Option<I>) {
        let error = o
            .check_deadline_order_deferred(0.5, event, || Ok(None))
            .unwrap_err();
        assert_eq!(error.kind, "event_resolution");
        assert!(error.message.contains("ordering of operator deadlines"));
    }
    #[test]
    fn independent_end_and_start_with_proven_order_share_one_representative() {
        let o = pair();
        let (end, start) = deadlines(&o);
        // Every older rule refuses this pair; only the new proof admits it.
        assert!(end.overlaps(start.bounds));
        assert!(!end.coincides(&start));
        assert!(!end.serial_representatives(&start));
        assert!(!end.independent_end_checkpoints(&start));
        assert_eq!(end.proven_order(&start), Some(Ordering::Less));
        o.check_deadline_order_deferred(0.5, None, || Ok(None))
            .unwrap();
        o.check_deadline_order_deferred(0.5, Some(I { lo: 1.2, hi: 1.3 }), || Ok(None))
            .unwrap();
    }
    #[test]
    fn an_earlier_pending_activation_keeps_the_refusal() {
        let o = start_first();
        let (end, start) = deadlines(&o);
        assert!(end.overlaps(start.bounds) && !end.serial_representatives(&start));
        assert_eq!(start.proven_order(&end), Some(Ordering::Less));
        assert!(!o.independent_proven_order((0, &end), (1, &start), None));
        refuse(&o, None);
    }
    #[test]
    fn event_inside_the_joint_enclosure_keeps_the_refusal() {
        let o = pair();
        let (end, start) = deadlines(&o);
        let hi = end.bounds.hi.max(start.bounds.hi);
        // Each deadline alone is strictly before this point event, so only
        // the joint-window rule refuses it.
        assert!(end.strictly_ordered_with(I::point(hi)));
        assert!(start.strictly_ordered_with(I::point(hi)));
        refuse(&o, Some(I::point(hi)));
    }
    #[test]
    fn a_target_that_reads_another_output_or_node_is_dependent() {
        for expression in [
            Expression::Operator { operator: 0 },
            Expression::Affine {
                constant: 0.,
                terms: vec![crate::ir::Term {
                    node: 1,
                    coefficient: 1.,
                }],
            },
            Expression::Add {
                left: Box::new(Expression::State { state: 1 }),
                right: Box::new(Expression::Operator { operator: 0 }),
            },
        ] {
            let mut o = pair();
            let Runtime::Transition { expression: e, .. } = &mut o.entries[1] else {
                unreachable!()
            };
            *e = expression;
            refuse(&o, None);
        }
    }
    #[test]
    fn same_owner_equal_or_unproven_times_are_not_admitted() {
        let o = pair();
        let (end, start) = deadlines(&o);
        assert!(o.independent_proven_order((0, &end), (1, &start), None));
        assert!(!o.independent_proven_order((0, &end), (0, &start), None));
        assert!(!o.independent_proven_order((0, &end), (1, &end), None));
        let unproven = crate::transition::Deadline::unproven_for_tests(end.bounds);
        assert_eq!(unproven.proven_order(&start), None);
        assert!(!o.independent_proven_order((0, &unproven), (1, &start), None));
    }
}

#[cfg(test)]
impl Operators {
    pub(crate) fn analytic_empty_snapshot(&self) -> serde_json::Value {
        // This lane cannot acquire any history/operator/forcing capability.
        assert!(
            self.entries.is_empty()
                && self.held_targets.is_empty()
                && self.history_targets.is_empty()
                && self.history_predicates.is_empty()
        );
        assert!(
            self.history_admission.is_none()
                && self.forcing_context.is_none()
                && self.continuous.is_none()
        );
        assert!(
            self.direct.is_empty()
                && self.changes_on_advance.is_empty()
                && self.isolated_parameters.is_empty()
        );
        serde_json::json!({"entries":0,"held_targets":0,"history_targets":0,"history_predicates":0,"history_admission":false,"forcing_context":false,"continuous":false,"direct":0,"changes_on_advance":0,"isolated_parameters":0,"horizon":self.horizon,"source_context":self.source_context.as_ref().map(|c|Arc::as_ptr(c) as usize)})
    }
}

#[cfg(test)]
#[path = "operator_procedure_direct_tests.rs"]
mod operator_procedure_direct_tests;
