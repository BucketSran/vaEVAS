//! Validated polynomial ODE propagation for integral and filter call-site states.
//! A Picard enclosure proves a finite trajectory tube. Order-p interval Taylor
//! coefficients carry accepted uncertainty; order p+1 bounds the remainder.
//! Polynomial ODEs try p=12/24; DAE keeps p=12. Dense queries are immutable.
use super::*;
use crate::ir::Tolerances;

const ORDER: usize = 12;
const MAX_ORDER: usize = 24;
const MAX_STEPS: usize = 16_384;
const TUBE_ATTEMPTS: usize = 16;
const MAX_REFINEMENTS: usize = 64;
const MAX_HISTORY_REFINEMENTS: usize = 8;
type Jet = Vec<I>;

// A rounded binary64 point result lies between its adjacent representable
// values. The exact residual determines which one-sided enclosure to use.
fn directed(value: f64, sign: i8) -> I {
    match sign {
        -1 => I {
            lo: value.next_down(),
            hi: value,
        },
        0 => I::point(value),
        _ => I {
            lo: value,
            hi: value.next_up(),
        },
    }
}

fn point_sum(a: f64, b: f64) -> I {
    let value = a + b;
    let b_virtual = value - a;
    let residual = (a - (value - b_virtual)) + (b - b_virtual);
    if value.is_finite() && residual.is_finite() {
        directed(
            value,
            if residual < 0.0 {
                -1
            } else if residual > 0.0 {
                1
            } else {
                0
            },
        )
    } else {
        I::point(a) + I::point(b)
    }
}

fn point_product(a: f64, b: f64) -> I {
    let value = a * b;
    let residual = a.mul_add(b, -value);
    if value.is_finite() && residual != 0.0 && residual.is_finite() {
        directed(value, if residual < 0.0 { -1 } else { 1 })
    } else if value.is_finite() && crate::interval::equal_products(a, b, value, 1.0) {
        I::point(value)
    } else {
        I::point(a) * I::point(b)
    }
}

fn tight_add(a: I, b: I) -> I {
    I {
        lo: point_sum(a.lo, b.lo).lo,
        hi: point_sum(a.hi, b.hi).hi,
    }
}

fn tight_mul(a: I, b: I) -> I {
    let products =
        [(a.lo, b.lo), (a.lo, b.hi), (a.hi, b.lo), (a.hi, b.hi)].map(|(a, b)| point_product(a, b));
    I {
        lo: products.iter().map(|v| v.lo).fold(f64::INFINITY, f64::min),
        hi: products
            .iter()
            .map(|v| v.hi)
            .fold(f64::NEG_INFINITY, f64::max),
    }
}

fn tight_div_positive(a: I, denominator: f64) -> I {
    let divide = |a: f64| {
        let value = a / denominator;
        let residual = (-value).mul_add(denominator, a);
        if value.is_finite() && residual != 0.0 && residual.is_finite() {
            directed(value, if residual < 0.0 { -1 } else { 1 })
        } else if value.is_finite() && crate::interval::equal_products(value, denominator, a, 1.0) {
            I::point(value)
        } else {
            I::point(a) / I::point(denominator)
        }
    };
    I {
        lo: divide(a.lo).lo,
        hi: divide(a.hi).hi,
    }
}

fn add_mode(a: I, b: I, tight: bool) -> I {
    if tight {
        tight_add(a, b)
    } else {
        a + b
    }
}
fn mul_mode(a: I, b: I, tight: bool) -> I {
    if tight {
        tight_mul(a, b)
    } else {
        a * b
    }
}

#[path = "continuous_initialization.rs"]
mod initialization;

#[path = "implicit_dynamics.rs"]
mod implicit;
pub(crate) use implicit::run as run_implicit;

#[derive(Clone)]
enum Polynomial {
    Linear(Vec<I>),
    Add(Box<Self>, Box<Self>),
    Multiply(Box<Self>, Box<Self>),
    Power(Box<Self>, u32),
}

pub(super) fn validate(expr: &Expression, program: &Program, owner: &str) -> Result<(), Error> {
    match expr {
        Expression::Add { left, right } | Expression::Multiply { left, right } => {
            validate(left, program, owner)?;
            validate(right, program, owner)
        }
        Expression::Power { base, exponent } if (1..=32).contains(exponent) => {
            validate(base, program, owner)
        }
        Expression::Select { .. } | Expression::Power { .. } => Err(Error::new(
            "unsupported_operator",
            "integral input must be a polynomial with powers 1..32",
        )),
        _ => crate::events::affine(expr, program, owner).map(|_| ()),
    }
}

impl Polynomial {
    fn compile(
        expr: &Expression,
        program: &Program,
        system: &AlgebraicSystem,
        mapping: &[Vec<I>],
    ) -> Result<Self, Error> {
        let result = match expr {
            Expression::Add { left, right } => Self::Add(
                Box::new(Self::compile(left, program, system, mapping)?),
                Box::new(Self::compile(right, program, system, mapping)?),
            ),
            Expression::Multiply { left, right } => Self::Multiply(
                Box::new(Self::compile(left, program, system, mapping)?),
                Box::new(Self::compile(right, program, system, mapping)?),
            ),
            Expression::Power { base, exponent } => Self::Power(
                Box::new(Self::compile(base, program, system, mapping)?),
                *exponent,
            ),
            _ => Self::Linear(expand_input(
                &affine_bounds::affine(expr, program)?,
                program,
                system,
                mapping,
            )?),
        };
        Ok(result)
    }

    // Differentiate the polynomial expression before evaluating its Taylor
    // jet. These are derivatives with respect to a state coordinate, not
    // independent derivatives of already rounded coefficient endpoints.
    fn gradient_jet(&self, variables: &[Jet], order: usize, coordinate: usize) -> Jet {
        match self {
            Self::Linear(row) => {
                let mut result = vec![I::ZERO; order + 1];
                result[0] = row[coordinate];
                result
            }
            Self::Add(a, b) => a
                .gradient_jet(variables, order, coordinate)
                .into_iter()
                .zip(b.gradient_jet(variables, order, coordinate))
                .map(|(a, b)| a + b)
                .collect(),
            Self::Multiply(a, b) => {
                let left = multiply(
                    &a.gradient_jet(variables, order, coordinate),
                    &b.jet(variables, order),
                    order,
                );
                let right = multiply(
                    &a.jet(variables, order),
                    &b.gradient_jet(variables, order, coordinate),
                    order,
                );
                left.into_iter().zip(right).map(|(a, b)| a + b).collect()
            }
            Self::Power(a, n) => {
                let values = a.jet(variables, order);
                let mut power = vec![I::ZERO; order + 1];
                power[0] = I::point(*n as f64);
                for _ in 1..*n {
                    power = multiply(&power, &values, order);
                }
                multiply(&power, &a.gradient_jet(variables, order, coordinate), order)
            }
        }
    }

    fn dc_affine(&self, known: &[Option<I>]) -> Option<Vec<I>> {
        match self {
            Self::Linear(row) => {
                let mut row = row.clone();
                for (i, value) in known.iter().enumerate() {
                    if let Some(value) = value {
                        let last = row.len() - 1;
                        row[last] = row[last] + row[i] * *value;
                        row[i] = I::ZERO;
                    }
                }
                Some(row)
            }
            Self::Add(a, b) => Some(
                a.dc_affine(known)?
                    .into_iter()
                    .zip(b.dc_affine(known)?)
                    .map(|(a, b)| a + b)
                    .collect(),
            ),
            Self::Multiply(a, b) => {
                let a = a.dc_affine(known)?;
                let b = b.dc_affine(known)?;
                let constant = |row: &[I]| row[..row.len() - 1].iter().all(|v| v.zero());
                if constant(&a) {
                    Some(b.iter().map(|&v| *a.last().unwrap() * v).collect())
                } else if constant(&b) {
                    Some(a.iter().map(|&v| *b.last().unwrap() * v).collect())
                } else {
                    None
                }
            }
            Self::Power(a, n) => {
                let mut row = a.dc_affine(known)?;
                if *n == 1 {
                    return Some(row);
                }
                if row[..row.len() - 1].iter().any(|v| !v.zero()) {
                    return None;
                }
                let last = row.len() - 1;
                row[last] = (0..*n).fold(I::ONE, |value, _| value * row[last]);
                Some(row)
            }
        }
    }

    fn jet(&self, variables: &[Jet], order: usize) -> Jet {
        self.jet_with(variables, order, false)
    }

    fn jet_with(&self, variables: &[Jet], order: usize, tight: bool) -> Jet {
        match self {
            Self::Linear(row) => {
                let mut out = vec![I::ZERO; order + 1];
                out[0] = *row.last().unwrap();
                for (&coefficient, variable) in row.iter().zip(variables) {
                    for (slot, value) in out.iter_mut().zip(variable) {
                        *slot = add_mode(*slot, mul_mode(coefficient, *value, tight), tight);
                    }
                }
                out
            }
            Self::Add(a, b) => a
                .jet_with(variables, order, tight)
                .into_iter()
                .zip(b.jet_with(variables, order, tight))
                .map(|(x, y)| add_mode(x, y, tight))
                .collect(),
            Self::Multiply(a, b) => multiply_with(
                &a.jet_with(variables, order, tight),
                &b.jet_with(variables, order, tight),
                order,
                tight,
            ),
            Self::Power(a, n) => {
                let a = a.jet_with(variables, order, tight);
                let mut out = vec![I::ZERO; order + 1];
                out[0] = I::ONE;
                for _ in 0..*n {
                    out = multiply_with(&out, &a, order, tight);
                }
                out
            }
        }
    }
}

fn multiply(a: &[I], b: &[I], order: usize) -> Jet {
    multiply_with(a, b, order, false)
}

fn multiply_with(a: &[I], b: &[I], order: usize, tight: bool) -> Jet {
    (0..=order)
        .map(|n| {
            (0..=n).fold(I::ZERO, |sum, k| {
                add_mode(sum, mul_mode(a[k], b[n - k], tight), tight)
            })
        })
        .collect()
}

#[derive(Clone, PartialEq)]
struct DenseStep {
    start: f64,
    end: f64,
    coefficients: Vec<Jet>,
    remainder: Vec<I>,
    centered: Option<CenteredPolynomial>,
}

#[derive(Clone, PartialEq)]
struct CenterValue {
    point: f64,
    // Signed deviation from point. Keep it in its own small coordinate,
    // rather than rounding an absolute state box after every accepted step.
    error: I,
}

impl CenterValue {
    fn from_interval(value: I) -> Self {
        let point = value.lo + (value.hi - value.lo) * 0.5;
        Self {
            point,
            error: value - I::point(point),
        }
    }
    fn range(&self) -> I {
        I::point(self.point) + self.error
    }
}

// Enclose the exact residual a*b+c-rounded_fma in the small error coordinate.
// TwoSum gives the exact addition residual; the FMA multiplication residual
// is exact when normal, and enclosed by adjacent subnormals otherwise.
fn fma_error(a: f64, b: f64, c: f64, value: f64) -> I {
    let product = a * b;
    if !product.is_finite() || !value.is_finite() {
        return I {
            lo: f64::NEG_INFINITY,
            hi: f64::INFINITY,
        };
    }
    let residual = a.mul_add(b, -product);
    let product_error = if residual.abs() >= f64::MIN_POSITIVE
        || crate::interval::equal_products(a, b, product, 1.0)
    {
        I::point(residual)
    } else {
        I {
            lo: residual.next_down(),
            hi: residual.next_up(),
        }
    };
    let sum = product + c;
    if !sum.is_finite() {
        return I {
            lo: f64::NEG_INFINITY,
            hi: f64::INFINITY,
        };
    }
    let c_virtual = sum - product;
    let sum_error = (product - (sum - c_virtual)) + (c - c_virtual);
    product_error + I::point(sum_error) + (I::point(sum) - I::point(value))
}

fn center_horner(row: &[I], h: I) -> CenterValue {
    let h = CenterValue::from_interval(h);
    row.iter().rev().fold(
        CenterValue {
            point: 0.0,
            error: I::ZERO,
        },
        |sum, &coefficient| {
            let coefficient = CenterValue::from_interval(coefficient);
            let point = sum.point.mul_add(h.point, coefficient.point);
            let error = sum.error * h.range()
                + I::point(sum.point) * h.error
                + coefficient.error
                + fma_error(sum.point, h.point, coefficient.point, point);
            CenterValue { point, error }
        },
    )
}

#[derive(Clone, PartialEq)]
struct CenteredPolynomial {
    coefficients: Vec<Jet>,
    // [output state][initial state coordinate][Taylor coefficient]
    sensitivities: Vec<Vec<Jet>>,
    offsets: Vec<I>,
}

fn horner(row: &[I], h: I) -> I {
    row.iter().rev().fold(I::ZERO, |sum, &a| sum * h + a)
}

impl DenseStep {
    fn range(&self, time: I) -> Vec<I> {
        let h = time - I::point(self.start);
        let h13 = (0..self.coefficients[0].len()).fold(I::ONE, |v, _| v * h);
        let centered = self.centered_range(h, true);
        self.polynomial_range(h)
            .into_iter()
            .zip(&self.remainder)
            .enumerate()
            .map(|(i, (value, &r))| {
                let ordinary = value + r * h13;
                let Some(centered) = &centered else {
                    return ordinary;
                };
                let centered = centered[i].range();
                let intersection = I {
                    lo: ordinary.lo.max(centered.lo),
                    hi: ordinary.hi.min(centered.hi),
                };
                if centered.finite() && intersection.lo <= intersection.hi {
                    intersection
                } else {
                    ordinary
                }
            })
            .collect()
    }

    fn centered_range(&self, h: I, tail: bool) -> Option<Vec<CenterValue>> {
        let centered = self.centered.as_ref()?;
        let power = (0..self.coefficients[0].len()).fold(I::ONE, |value, _| value * h);
        Some(
            centered
                .coefficients
                .iter()
                .enumerate()
                .map(|(i, row)| {
                    let mut value = center_horner(row, h);
                    for (derivative, &offset) in
                        centered.sensitivities[i].iter().zip(&centered.offsets)
                    {
                        value.error = value.error + horner(derivative, h) * offset;
                    }
                    if tail {
                        value.error = value.error + self.remainder[i] * power;
                    }
                    value
                })
                .collect(),
        )
    }

    fn polynomial_range(&self, h: I) -> Vec<I> {
        let centered = self.centered_range(h, false);
        self.coefficients
            .iter()
            .enumerate()
            .map(|(i, row)| {
                let ordinary = horner(row, h);
                let Some(centered) = &centered else {
                    return ordinary;
                };
                let mean_value = centered[i].range();
                let intersection = I {
                    lo: ordinary.lo.max(mean_value.lo),
                    hi: ordinary.hi.min(mean_value.hi),
                };
                if mean_value.finite() && intersection.lo <= intersection.hi {
                    intersection
                } else {
                    ordinary
                }
            })
            .collect()
    }
}

#[derive(Clone)]
pub(crate) struct NonlinearContinuous {
    context: Arc<Context>,
    parameters: Vec<I>,
    functions: Vec<Polynomial>,
    implicit: Option<implicit::ImplicitField>,
    operators: Vec<NetworkOperator>,
    values: Vec<Vec<I>>,
    accuracy_rows: Vec<Vec<I>>,
    tolerances: Tolerances,
    initial: Vec<I>,
    steps: Vec<DenseStep>,
    start: f64,
    event_dependent: bool,
}

impl NonlinearContinuous {
    #[cfg(test)]
    pub(super) fn new(
        program: &Program,
        trajectory: &Trajectory,
        driven: &[String],
        states: &[f64],
        horizon: f64,
    ) -> Result<Self, Error> {
        Self::new_with_tolerances(
            program,
            trajectory,
            driven,
            states,
            horizon,
            &Tolerances::default(),
        )
    }

    pub(super) fn new_with_tolerances(
        program: &Program,
        trajectory: &Trajectory,
        driven: &[String],
        states: &[f64],
        horizon: f64,
        tolerances: &Tolerances,
    ) -> Result<Self, Error> {
        Self::build(
            Arc::new(Context {
                program: program.clone(),
                trajectory: trajectory.clone(),
                driven: driven.to_vec(),
            }),
            states.iter().copied().map(I::point).collect(),
            0.0,
            None,
            horizon,
            tolerances,
        )
    }

    fn build(
        context: Arc<Context>,
        parameters: Vec<I>,
        start: f64,
        restart: Option<Vec<I>>,
        horizon: f64,
        tolerances: &Tolerances,
    ) -> Result<Self, Error> {
        let mut result = Self::initialized(context, parameters, start, restart, tolerances)?;
        result.propagate_until(horizon)?;
        Ok(result)
    }

    // Compile the new mode and apply reset before propagating. A candidate
    // restart must first enclose its uncertain event-to-representative flow.
    fn initialized(
        context: Arc<Context>,
        parameters: Vec<I>,
        start: f64,
        restart: Option<Vec<I>>,
        tolerances: &Tolerances,
    ) -> Result<Self, Error> {
        let program = &context.program;
        let driven = driven_node_indices(program, &context.driven)?;
        let mut sources = vec![None; program.nodes.len()];
        for (i, &node) in driven.iter().enumerate() {
            sources[node] = Some(i);
        }
        let mut operators = Vec::new();
        let mut state_count = 0;
        let mut event_dependent = false;
        for (i, spec) in program.operators.iter().enumerate() {
            let origin = spec.origin();
            let (kind, input, states, laplace, held_reset) = match spec {
                OperatorSpec::Idt { input, ic, reset, .. } => {
                    validate(input, program, &origin.instance)?;
                    if !ic.is_finite() {
                        return Err(unsupported(origin, "nonfinite nonlinear integral IC"));
                    }
                    let held = if let Some(reset) = reset {
                        let dependencies = crate::events::affine(reset, program, &origin.instance)?;
                        if !dependencies.node_dependencies.is_empty()
                            || !dependencies.operator_dependencies.is_empty()
                        {
                            return Err(unsupported(origin,
                                "nonlinear integral reset must depend on event state and constants"));
                        }
                        event_dependent = true;
                        crate::operators::ResetExpression::new(reset.clone()).active(&parameters)?
                    } else { false };
                    let state = state_count;
                    state_count += 1;
                    (ContinuousKind::Idt, input, vec![state], None, held)
                }
                OperatorSpec::LaplaceNd { input, numerator, denominator, .. } => {
                    validate(input, program, &origin.instance)?;
                    let filter = laplace_system(numerator, denominator, origin)?;
                    if !filter.d.zero() && affine_for_operator_input(input, program, origin).is_err() {
                        return Err(unsupported(origin, "polynomial filter input requires a strictly proper transfer function"));
                    }
                    let states = (state_count..state_count + filter.a.len()).collect();
                    state_count += filter.a.len();
                    (ContinuousKind::LaplaceNd, input, states, Some(filter), false)
                }
                _ => return Err(unsupported(origin,
                    "polynomial continuous network supports explicit-IC integrals and affine-input proper filters; derivative/function coupling needs a certified reduction")),
            };
            event_dependent |=
                history_event_dependency(input, program, origin, &driven, &mut BTreeSet::new());
            let mut structural =
                vec![
                    I::ZERO;
                    program.nodes.len() + program.states.len() + program.operators.len() + 1
                ];
            if let Ok(row) = affine_for_operator_input(input, program, origin) {
                structural = row;
            } else {
                collect_structure(input, program, &origin.instance, &mut structural)?;
            }
            operators.push(NetworkOperator {
                operator: i,
                kind,
                origin: origin.clone(),
                states,
                input: Some(structural),
                laplace,
                held_reset,
            });
        }
        if state_count + 2 * driven.len() + 1 > 32 {
            return Err(Error::new(
                "waveform_accuracy",
                "nonlinear state/source dimension exceeds 32",
            ));
        }
        let system = AlgebraicSystem::new(
            program,
            &operators,
            &driven,
            &sources,
            state_count,
            driven.len(),
            &parameters,
        )?;
        let rows = affine_bounds::eliminate(system.rows.clone(), system.x_count, system.width)?;
        let mapping = back_substitute_eliminated(&rows, system.x_count, system.width)?;
        let values = build_value_rows(&operators, &system, &mapping)?;
        // Include every solved voltage, including high-gain aliases, rather
        // than applying a state-magnitude budget to the operator values alone.
        let accuracy_rows = system
            .node_columns
            .iter()
            .flatten()
            .map(|&column| mapping[column].clone())
            .collect();
        let mut functions = vec![Polynomial::Linear(vec![I::ZERO; system.width]); state_count];
        for op in &operators {
            match &program.operators[op.operator] {
                OperatorSpec::Idt { input, .. } if !op.held_reset => {
                    functions[op.states[0]] =
                        Polynomial::compile(input, program, &system, &mapping)?;
                }
                OperatorSpec::LaplaceNd { input, .. } => {
                    let input = Polynomial::compile(input, program, &system, &mapping)?;
                    let filter = op.laplace.as_ref().unwrap();
                    for (local, &state) in op.states.iter().enumerate() {
                        let mut row = vec![I::ZERO; system.width];
                        for (&other, &coefficient) in op.states.iter().zip(&filter.a[local]) {
                            row[other] = row[other] + coefficient;
                        }
                        let mut gain = vec![I::ZERO; system.width];
                        *gain.last_mut().unwrap() = filter.b[local];
                        functions[state] = Polynomial::Add(
                            Box::new(Polynomial::Linear(row)),
                            Box::new(Polynomial::Multiply(
                                Box::new(Polynomial::Linear(gain)),
                                Box::new(input.clone()),
                            )),
                        );
                    }
                }
                _ => {}
            }
        }
        let mut initial = if let Some(state) = restart {
            // Restart is an IVP with accepted physical history. It must not
            // impose a new DC equilibrium on the event's future vector field.
            state
        } else {
            // Only cold initialization needs filter DC equations. Integral
            // states pin their IC, not their derivative to zero.
            let mut dc_derivatives = vec![vec![I::ZERO; system.width]; state_count];
            let mut known = vec![None; system.width - 1];
            for op in &operators {
                if let OperatorSpec::Idt { ic, .. } = &program.operators[op.operator] {
                    known[op.states[0]] = Some(I::point(*ic));
                }
            }
            for (slot, value) in known[state_count..]
                .iter_mut()
                .zip(context.trajectory.value_bounds(0.0))
            {
                *slot = Some(value);
            }
            for slot in &mut known[state_count + driven.len()..] {
                *slot = Some(I::ZERO);
            }
            let affine_dc = operators
                .iter()
                .filter(|op| op.kind == ContinuousKind::LaplaceNd)
                .flat_map(|op| &op.states)
                .all(|&state| {
                    if let Some(row) = functions[state].dc_affine(&known) {
                        dc_derivatives[state] = row;
                        true
                    } else {
                        false
                    }
                });
            if affine_dc {
                initial_state(
                    program,
                    &operators,
                    &system,
                    &dc_derivatives,
                    &context.trajectory,
                )?
            } else {
                // This is still one cold root system, with held parameters
                // kept as uncertain inputs. Never use it for event restarts.
                initialization::joint_dc(
                    program,
                    &context.driven,
                    &context.trajectory,
                    &operators,
                    &parameters,
                )?
                .physical
            }
        };
        for op in &operators {
            if op.held_reset {
                let OperatorSpec::Idt { ic, .. } = &program.operators[op.operator] else {
                    unreachable!()
                };
                initial[op.states[0]] = I::point(*ic);
            }
        }
        Ok(Self {
            context,
            parameters,
            functions,
            implicit: None,
            operators,
            values,
            accuracy_rows,
            tolerances: tolerances.clone(),
            initial,
            steps: Vec::new(),
            start,
            event_dependent,
        })
    }

    fn derivative_jets(&self, variables: &[Jet], slopes: &[I], order: usize) -> Option<Vec<Jet>> {
        if let Some(field) = &self.implicit {
            field.jets(&self.functions, variables, slopes, order)
        } else {
            Some(
                self.functions
                    .iter()
                    .map(|f| f.jet(variables, order))
                    .collect(),
            )
        }
    }

    fn jets(&self, state: &[I], source: &[I], slopes: &[I], order: usize) -> Option<Vec<Jet>> {
        self.jets_mode(state, source, slopes, order, false)
    }

    fn jets_mode(
        &self,
        state: &[I],
        source: &[I],
        slopes: &[I],
        order: usize,
        tight: bool,
    ) -> Option<Vec<Jet>> {
        let mut variables: Vec<_> = state
            .iter()
            .chain(source)
            .map(|&v| {
                let mut row = vec![I::ZERO; order + 1];
                row[0] = v;
                row
            })
            .collect();
        for (variable, &slope) in variables[state.len()..].iter_mut().zip(slopes) {
            if order > 0 {
                variable[1] = slope;
            }
        }
        for n in 0..order {
            let derivatives = if tight {
                self.functions
                    .iter()
                    .map(|f| f.jet_with(&variables, n, true))
                    .collect()
            } else {
                self.derivative_jets(&variables, slopes, n)?
            };
            let derivatives: Vec<_> = derivatives
                .into_iter()
                .map(|row| {
                    if tight {
                        tight_div_positive(row[n], (n + 1) as f64)
                    } else {
                        row[n] / I::point((n + 1) as f64)
                    }
                })
                .collect();
            for (variable, value) in variables.iter_mut().zip(derivatives) {
                variable[n + 1] = value;
            }
        }
        Some(variables[..state.len()].to_vec())
    }

    fn centered_polynomial(
        &self,
        state: &[I],
        source: &[I],
        slopes: &[I],
        coefficients: &[Jet],
        centers: Option<&[CenterValue]>,
    ) -> Option<CenteredPolynomial> {
        // The implicit rational field needs its own derivative proof. Its
        // existing interval propagation remains unchanged here.
        if self.implicit.is_some() {
            return None;
        }
        let centers: Vec<_> = centers.map_or_else(
            || {
                state
                    .iter()
                    .copied()
                    .map(CenterValue::from_interval)
                    .collect()
            },
            |values| values.to_vec(),
        );
        let center: Vec<_> = centers.iter().map(|value| I::point(value.point)).collect();
        if center.iter().any(|value| !value.finite()) {
            return None;
        }
        let order = coefficients[0].len() - 1;
        let center_coefficients = self.jets_mode(&center, source, slopes, order, true)?;
        let mut variables = coefficients.to_vec();
        variables.extend(source.iter().zip(slopes).map(|(&value, &slope)| {
            let mut row = vec![I::ZERO; order + 1];
            row[0] = value;
            row[1] = slope;
            row
        }));
        let count = state.len();
        let mut sensitivities = vec![vec![vec![I::ZERO; order + 1]; count]; count];
        for (i, row) in sensitivities.iter_mut().enumerate() {
            row[i][0] = I::ONE;
        }
        // Differentiate the Taylor recurrence by the chain rule. Evaluation
        // uses the entire original initial box, and unmodified source boxes.
        for n in 0..order {
            let gradients: Vec<Vec<Jet>> = self
                .functions
                .iter()
                .map(|function| {
                    (0..count)
                        .map(|k| function.gradient_jet(&variables, n, k))
                        .collect()
                })
                .collect();
            for i in 0..count {
                let derivatives: Vec<_> = (0..count)
                    .map(|j| {
                        let derivative = (0..count).fold(I::ZERO, |sum, k| {
                            sum + multiply(&gradients[i][k], &sensitivities[k][j], n)[n]
                        });
                        derivative / I::point((n + 1) as f64)
                    })
                    .collect();
                for (row, derivative) in sensitivities[i].iter_mut().zip(derivatives) {
                    row[n + 1] = derivative;
                }
            }
        }
        Some(CenteredPolynomial {
            coefficients: center_coefficients,
            sensitivities,
            offsets: centers.into_iter().map(|value| value.error).collect(),
        })
    }

    #[cfg(test)]
    fn trial(
        &self,
        start: f64,
        end: f64,
        state: &[I],
        source: &[I],
        slopes: &[I],
    ) -> Option<DenseStep> {
        self.trial_order(start, end, state, source, slopes, ORDER, None)
    }

    #[allow(clippy::too_many_arguments)]
    fn trial_order(
        &self,
        start: f64,
        end: f64,
        state: &[I],
        source: &[I],
        slopes: &[I],
        order: usize,
        centers: Option<&[CenterValue]>,
    ) -> Option<DenseStep> {
        let state: Vec<_> = state
            .iter()
            .enumerate()
            .map(|(i, &value)| {
                centers.map_or(value, |centers| value.hull(I::point(centers[i].point)))
            })
            .collect();
        let state = state.as_slice();
        let duration = I::point(end) - I::point(start);
        let elapsed = I {
            lo: 0.0,
            hi: duration.hi,
        };
        let source_tube: Vec<_> = source
            .iter()
            .zip(slopes)
            .map(|(&u, &m)| u + elapsed * m)
            .collect();
        let (tube, _) = self.picard_enclosure(state, &source_tube, slopes, elapsed)?;
        let coefficients = self.jets(state, source, slopes, order)?;
        let remainder: Vec<_> = self
            .jets(&tube, &source_tube, slopes, order + 1)?
            .into_iter()
            .map(|row| row[order + 1])
            .collect();
        let centered = self.centered_polynomial(state, source, slopes, &coefficients, centers);
        let step = DenseStep {
            start,
            end,
            coefficients,
            remainder,
            centered,
        };
        let tail_power = (0..=order).fold(I::ONE, |v, _| v * duration);
        let values = step.range(I::point(end));
        if values.iter().any(|v| !v.finite())
            || step.remainder.iter().any(|&r| !(r * tail_power).finite())
        {
            return None;
        }
        Some(step)
    }

    // Reserve one eighth of each voltage budget for local truncation, with
    // h/stop allocation independent of requested observations and candidate
    // horizons. Full interval states carry all previously accumulated error.
    // This is a refinement target, never a replacement for voltage acceptance.
    fn truncation_fits(
        &self,
        step: &DenseStep,
        source: &[I],
        slopes: &[I],
        refinement: f64,
    ) -> Result<bool, Error> {
        let duration = I::point(step.end) - I::point(step.start);
        let power = (0..step.coefficients[0].len()).fold(I::ONE, |v, _| v * duration);
        let tail: Vec<_> = step
            .remainder
            .iter()
            .map(|&r| (r * power).magnitude())
            .collect();
        if self.implicit.is_some() {
            // The rational DAE field retains its existing local stability
            // ceiling. User budgets may tighten it, never remove this guard.
            let endpoint = step.range(I::point(step.end));
            if tail
                .iter()
                .zip(&endpoint)
                .any(|(&error, value)| error > 1e-16 * (1.0 + value.magnitude()))
            {
                return Ok(false);
            }
        }
        let elapsed = I {
            lo: 0.0,
            hi: duration.hi,
        };
        let state = step.range(elapsed + I::point(step.start));
        let forcing: Vec<_> = state
            .into_iter()
            .chain(source.iter().zip(slopes).map(|(&u, &m)| u + elapsed * m))
            .chain(vec![I::ZERO; source.len()])
            .chain([I::ONE])
            .collect();
        // Remove only the current truncation tail to measure how much of the
        // endpoint budget is already consumed by propagated history, sources
        // and coefficient rounding. Earlier tails remain in the coefficients.
        let endpoint: Vec<_> = step
            .polynomial_range(duration)
            .into_iter()
            .chain(source.iter().zip(slopes).map(|(&u, &m)| u + duration * m))
            .chain(vec![I::ZERO; source.len()])
            .chain([I::ONE])
            .collect();
        let mut fits = true;
        for row in &self.accuracy_rows {
            let voltage = dot(row, &forcing, "nonlinear accuracy target")?;
            let inherited = dot(row, &endpoint, "nonlinear accumulated accuracy")?;
            // The lower magnitude of the whole step makes relative targets
            // valid even when an amplified output crosses or approaches zero.
            let lower = if voltage.lo <= 0.0 && voltage.hi >= 0.0 {
                0.0
            } else {
                voltage.lo.abs().min(voltage.hi.abs())
            };
            // An affine offset can cancel the state contribution in a later
            // mode. Preserve an absolute tail allowance before accepting that
            // prefix; suffix refinement cannot recover its earlier truncation.
            // This is a conservative step-selection heuristic, not a proof of
            // future output accuracy; the full enclosure still certifies it.
            let budget = if !row.last().unwrap().zero() {
                self.tolerances.absolute
            } else {
                self.tolerances.absolute + self.tolerances.relative * lower
            };
            let end_lower = if inherited.lo <= 0.0 && inherited.hi >= 0.0 {
                0.0
            } else {
                inherited.lo.abs().min(inherited.hi.abs())
            };
            let end_budget = I::point(self.tolerances.absolute)
                + I::point(self.tolerances.relative) * I::point(end_lower);
            let inherited_radius =
                (I::point(inherited.hi) - I::point(inherited.lo)) * I::point(0.5);
            let remaining = end_budget - inherited_radius;
            let mut local = budget
                * ((step.end - step.start) / self.context.trajectory.config.stop)
                * 0.125
                * refinement;
            if remaining.lo > 0.0 {
                local = local.min(remaining.lo * 0.125);
            } else if !row[..tail.len()].iter().all(|gain| gain.zero()) {
                // A valid uncertain trajectory must remain queryable, including
                // event-window propagation. Do not reject its enclosure here or
                // confuse inherited error with the currently shrinkable tail.
                // The unchanged final voltage certificate rejects any sample
                // whose full history enclosure exceeds the user requirement.
                crate::diagnostics::counter("nonlinear_history_budget_exhausted", 1);
                crate::diagnostics::record("nonlinear_accuracy", "inherited_budget_exhausted",
                    Some(step.start), Some(step.end), 1,
                    Some("accumulated history/source/coefficient rounding already consumes the endpoint voltage budget"));
            }
            let error = row.iter().zip(&tail).fold(I::ZERO, |sum, (&gain, &error)| {
                sum + I::point(gain.magnitude()) * I::point(error)
            });
            fits &= error.finite() && error.hi <= local;
        }
        Ok(fits)
    }

    // Relative budgets use the lower magnitude so a midpoint cannot hide
    // cancellation. Full state intervals include accumulated truncation.
    fn accuracy_ratio(&self, state: &[I], source: &[I], source_only: bool) -> f64 {
        let forcing: Vec<_> = state
            .iter()
            .copied()
            .chain(source.iter().copied())
            .chain(vec![I::ZERO; source.len()])
            .chain([I::ONE])
            .collect();
        self.accuracy_rows.iter().fold(0.0_f64, |worst, row| {
            let Ok(voltage) = dot(row, &forcing, "nonlinear history accuracy") else {
                return f64::INFINITY;
            };
            let lower = if voltage.lo <= 0.0 && voltage.hi >= 0.0 {
                0.0
            } else {
                voltage.lo.abs().min(voltage.hi.abs())
            };
            let budget = self.tolerances.absolute + self.tolerances.relative * lower;
            let radius = if source_only {
                row[state.len()..state.len() + source.len()]
                    .iter()
                    .zip(source)
                    .fold(I::ZERO, |sum, (&gain, &value)| {
                        sum + I::point(gain.magnitude())
                            * (I::point(value.hi) - I::point(value.lo))
                            * I::point(0.5)
                    })
                    .hi
            } else {
                ((I::point(voltage.hi) - I::point(voltage.lo)) * I::point(0.5)).hi
            };
            worst.max(if radius == 0.0 { 0.0 } else { radius / budget })
        })
    }

    // Bounds all flows starting anywhere in `initial`, with any source value
    // in `source`, over any duration in [0, elapsed.hi]. This needs no PWL
    // slope assumption and is therefore also valid across a source corner.
    fn picard_enclosure(
        &self,
        initial: &[I],
        source: &[I],
        slopes: &[I],
        elapsed: I,
    ) -> Option<(Vec<I>, Vec<I>)> {
        let evaluate = |state: &[I]| {
            let variables: Vec<_> = state.iter().chain(source).map(|&v| vec![v]).collect();
            self.derivative_jets(&variables, slopes, 0)
                .map(|rows| rows.into_iter().map(|row| row[0]).collect::<Vec<_>>())
        };
        let mut derivative = evaluate(initial)?;
        for _ in 0..TUBE_ATTEMPTS {
            let tube: Vec<_> = initial
                .iter()
                .zip(&derivative)
                .map(|(&v, &d)| {
                    let radius =
                        (I::point(elapsed.hi) * I::point(d.magnitude().max(1e-15)) * I::point(2.0))
                            .hi;
                    let expanded = v + I {
                        lo: -radius,
                        hi: radius,
                    };
                    // Even zero flows and sub-ulp durations require a strict
                    // tube around every possible initial value.
                    I {
                        lo: expanded.lo.next_down(),
                        hi: expanded.hi.next_up(),
                    }
                })
                .collect();
            if tube.iter().any(|v| !v.finite()) {
                return None;
            }
            derivative = evaluate(&tube)?;
            let image: Vec<_> = initial
                .iter()
                .zip(&derivative)
                .map(|(&v, &d)| v + elapsed * d)
                .collect();
            if image
                .iter()
                .zip(&tube)
                .all(|(v, z)| v.finite() && v.lo > z.lo && v.hi < z.hi)
            {
                return Some((tube, image));
            }
        }
        None
    }

    pub(super) fn certified_end(&self) -> f64 {
        self.steps.last().map_or(self.start, |step| step.end)
    }

    // Extend only a disposable candidate; retained dense steps and their
    // endpoint enclosures stay unchanged when an event leaves the mode intact.
    fn propagate_until(&mut self, horizon: f64) -> Result<(), Error> {
        let base = self.clone();
        let mut refinement = 1.0;
        // Count valid attempted steps across discarded suffixes too. Otherwise
        // eight retries would multiply the documented integration-work limit.
        let mut remaining_work = MAX_STEPS.saturating_sub(base.steps.len());
        for _ in 0..MAX_HISTORY_REFINEMENTS {
            let mut candidate = base.clone();
            if candidate.propagate_once(horizon, refinement, &mut remaining_work)? {
                *self = candidate;
                return Ok(());
            }
            crate::diagnostics::counter("nonlinear_history_refinements", 1);
            // Refining only the latest step cannot recover earlier candidate
            // tails. Rebuild the disposable suffix; keep the accepted prefix.
            refinement /= 256.0;
        }
        Err(Error::new("waveform_accuracy",
            "nonlinear accumulated history accuracy could not be certified within 8 suffix refinements"))
    }

    fn propagate_once(
        &mut self,
        horizon: f64,
        refinement: f64,
        remaining_work: &mut usize,
    ) -> Result<bool, Error> {
        let _timing = crate::diagnostics::span("history.nonlinear_propagate");

        let trajectory = &self.context.trajectory;
        if !horizon.is_finite() || horizon < self.start || horizon > trajectory.config.stop {
            return Err(Error::new(
                "event_resolution",
                "invalid nonlinear prediction horizon",
            ));
        }
        let start = self.certified_end();
        if horizon <= start {
            return Ok(true);
        }
        let mut state = self.steps.last().map_or_else(
            || self.initial.clone(),
            |step| step.range(I::point(step.end)),
        );
        let mut centers = self
            .steps
            .last()
            .and_then(|step| step.centered_range(I::point(step.end) - I::point(step.start), true));
        let refine_history =
            self.accuracy_ratio(&state, &trajectory.value_bounds(start), false) < 0.875;
        let mut knots = vec![start];
        knots.extend(
            trajectory
                .knots
                .iter()
                .copied()
                .filter(|t| *t > start && *t < horizon),
        );
        knots.push(horizon);
        for segment in knots.windows(2) {
            let (a, b) = (segment[0], segment[1]);
            let slopes: Vec<_> = trajectory
                .value_bounds(b)
                .iter()
                .zip(trajectory.value_bounds(a))
                .map(|(&v, u)| (v - u) / (I::point(b) - I::point(a)))
                .collect();
            let mut start = a;
            while start < b {
                if self.steps.len() >= MAX_STEPS {
                    return Err(Error::new(
                        "waveform_accuracy",
                        "validated nonlinear integration exceeded 16384 stored internal steps",
                    ));
                }
                if *remaining_work == 0 {
                    return Err(Error::new(
                        "waveform_accuracy",
                        "validated nonlinear integration exhausted the cumulative 16384 candidate-step work limit",
                    ));
                }
                let source = trajectory.value_bounds(start);
                let mut end = (start + 0.125_f64.min(trajectory.config.max_step)).min(b);
                let mut accepted = None;
                for _ in 0..MAX_REFINEMENTS {
                    if end <= start {
                        break;
                    }
                    if let Some(step) = self.trial_order(
                        start,
                        end,
                        &state,
                        &source,
                        &slopes,
                        ORDER,
                        centers.as_deref(),
                    ) {
                        if self.truncation_fits(&step, &source, &slopes, refinement)? {
                            accepted = Some(step);
                            break;
                        }
                        crate::diagnostics::counter("nonlinear_accuracy_refinements", 1);
                        // Increase polynomial order before reducing the step:
                        // repeated endpoint quantization can dominate a small
                        // tail. Rational DAE propagation retains order 12.
                        if self.implicit.is_none() {
                            crate::diagnostics::counter("nonlinear_order_refinements", 1);
                            if let Some(step) = self.trial_order(
                                start,
                                end,
                                &state,
                                &source,
                                &slopes,
                                MAX_ORDER,
                                centers.as_deref(),
                            ) {
                                if self.truncation_fits(&step, &source, &slopes, refinement)? {
                                    accepted = Some(step);
                                    break;
                                }
                            }
                        }
                    }
                    crate::diagnostics::record(
                        "nonlinear_candidate",
                        "rejected",
                        Some(start),
                        Some(end),
                        1,
                        Some("tube or user-budget Taylor remainder not certified"),
                    );
                    crate::diagnostics::counter("nonlinear_rejected_trials", 1);
                    end = start + (end - start) * 0.5;
                }
                let step = accepted.ok_or_else(|| {
                    Error::new(
                        "waveform_accuracy",
                        "cannot refine nonlinear trajectory within 64 trials: tube or user-budget Taylor remainder not certified",
                    )
                })?;
                *remaining_work -= 1;
                crate::diagnostics::counter("nonlinear_validated_work_steps", 1);
                state = step.range(I::point(step.end));
                centers = step.centered_range(I::point(step.end) - I::point(step.start), true);
                let endpoint_source = trajectory.value_bounds(step.end);
                if refine_history
                    && self.accuracy_ratio(&state, &endpoint_source, true) < 0.875
                    && self.accuracy_ratio(&state, &endpoint_source, false) > 0.875
                {
                    let h = I::point(step.end) - I::point(step.start);
                    let tail_power =
                        (0..step.coefficients[0].len()).fold(I::ONE, |value, _| value * h);
                    let tail = step
                        .remainder
                        .iter()
                        .map(|&r| (r * tail_power).magnitude())
                        .fold(0.0_f64, f64::max);
                    let radius = state
                        .iter()
                        .map(|value| (value.hi - value.lo) * 0.5)
                        .fold(0.0_f64, f64::max);
                    let center_width = centers.as_ref().map_or(f64::NAN, |values| {
                        values
                            .iter()
                            .map(|value| (value.error.hi - value.error.lo) * 0.5)
                            .fold(0.0_f64, f64::max)
                    });
                    let reason = format!("state_radius={radius:e}; center_error_radius={center_width:e}; current_tail={tail:e}; target_scale={refinement:e}; suffix_steps={}", self.steps.len());
                    crate::diagnostics::record(
                        "nonlinear_accuracy",
                        "suffix_budget_exhausted",
                        Some(step.start),
                        Some(step.end),
                        1,
                        Some(&reason),
                    );
                    return Ok(false);
                }
                start = step.end;
                self.steps.push(step);
                crate::diagnostics::counter("nonlinear_certified_candidate_steps", 1);
                crate::diagnostics::record(
                    "nonlinear_candidate",
                    "certified",
                    Some(self.steps.last().unwrap().start),
                    Some(start),
                    1,
                    None,
                );
            }
        }
        Ok(true)
    }

    pub(super) fn operator_value_index(&self, op: usize) -> Option<usize> {
        self.operators.iter().position(|slot| slot.operator == op)
    }
    pub(super) fn operator_spec(&self, slot: usize) -> &OperatorSpec {
        &self.context.program.operators[self.operators[slot].operator]
    }
    pub(super) fn reset_active(&self, slot: usize) -> bool {
        self.operators[slot].held_reset
    }
    pub(super) fn changes_on_event(&self) -> bool {
        self.event_dependent
    }
    pub(super) fn same_history(&self, other: &Self) -> bool {
        self.start == other.start
            && self.certified_end() == other.certified_end()
            && self.initial == other.initial
            && self.parameters == other.parameters
            && self.steps == other.steps
    }
    pub(super) fn next_breakpoint(&self, time: f64) -> Option<f64> {
        self.context
            .trajectory
            .knots
            .iter()
            .copied()
            .find(|t| *t > time)
    }
    fn state_bounds(&self, time: I) -> Result<Vec<I>, Error> {
        if !time.finite()
            || time.lo < self.start
            || time.hi > self.certified_end()
            || time.lo > time.hi
        {
            return Err(Error::new(
                "event_resolution",
                "nonlinear history query outside accepted trajectory",
            ));
        }
        let mut result: Vec<_> = self
            .initial
            .iter()
            .map(|&v| (time.lo == self.start).then_some(v))
            .collect();
        for step in &self.steps {
            let range = I {
                lo: time.lo.max(step.start),
                hi: time.hi.min(step.end),
            };
            if range.lo > range.hi {
                continue;
            }
            for (slot, value) in result.iter_mut().zip(step.range(range)) {
                *slot = Some(slot.map_or(value, |v| v.hull(value)));
            }
        }
        result
            .into_iter()
            .map(|v| {
                v.ok_or_else(|| {
                    Error::new(
                        "event_resolution",
                        "nonlinear trajectory query has no certified step",
                    )
                })
            })
            .collect()
    }
    pub(super) fn range_bounds(&self, time: I) -> Result<Vec<I>, Error> {
        let state = self.state_bounds(time)?;
        let source = self.source_bounds(time);
        let forcing: Vec<_> = state
            .into_iter()
            .chain(source.iter().copied())
            .chain(vec![I::ZERO; source.len()])
            .chain([I::ONE])
            .collect();
        self.values
            .iter()
            .map(|row| dot(row, &forcing, "nonlinear operator output"))
            .collect()
    }
    pub(super) fn derivative_bounds(&self, time: I) -> Result<Vec<I>, Error> {
        let state = self.state_bounds(time)?;
        let (source, slopes) = self.context.trajectory.range(time)?;
        let variables: Vec<_> = state.iter().chain(&source).map(|&v| vec![v]).collect();
        let forcing: Vec<_> = self
            .derivative_jets(&variables, &slopes, 0)
            .ok_or_else(|| Error::new("waveform_accuracy", "cannot certify implicit derivative"))?
            .into_iter()
            .map(|row| row[0])
            .chain(slopes)
            .chain(vec![I::ZERO; source.len()])
            .chain([I::ZERO])
            .collect();
        self.values
            .iter()
            .map(|row| dot(row, &forcing, "nonlinear operator derivative"))
            .collect()
    }
    fn source_bounds(&self, time: I) -> Vec<I> {
        let trajectory = &self.context.trajectory;
        let mut source = trajectory.value_bounds(time.lo);
        for t in std::iter::once(time.hi).chain(
            trajectory
                .knots
                .iter()
                .copied()
                .filter(|t| *t > time.lo && *t < time.hi),
        ) {
            for (u, v) in source.iter_mut().zip(trajectory.value_bounds(t)) {
                *u = u.hull(v);
            }
        }
        source
    }
    pub(super) fn event_bounds(&self, window: I) -> Result<Vec<I>, Error> {
        if window.lo < self.start && window.hi == self.start {
            // Candidate initial already encloses R(z(tau)) and the new flow
            // to b. Include the full source window for direct filter paths.
            let source = self.source_bounds(window);
            let forcing: Vec<_> = self
                .initial
                .iter()
                .copied()
                .chain(source.iter().copied())
                .chain(vec![I::ZERO; source.len()])
                .chain([I::ONE])
                .collect();
            self.values
                .iter()
                .map(|row| dot(row, &forcing, "nonlinear event sample"))
                .collect()
        } else {
            self.range_bounds(window)
        }
    }

    pub(super) fn restarted(
        &self,
        time: f64,
        window: I,
        parameters: &[I],
        horizon: f64,
    ) -> Result<Self, Error> {
        let mut next = self.mapped_event(time, window, parameters)?;
        if !self.event_dependent || self.parameters == parameters {
            next.propagate_until(horizon)?;
            return Ok(next);
        }
        if window.lo != window.hi {
            let elapsed = I {
                lo: 0.0,
                hi: (I::point(time) - I::point(window.lo)).hi,
            };
            let (_, image) = next
                .picard_enclosure(&next.initial, &self.source_bounds(window), &[], elapsed)
                .ok_or_else(|| {
                    Error::new(
                        "event_resolution",
                        "cannot certify nonlinear event-to-representative trajectory tube",
                    )
                })?;
            next.initial = image;
        }
        next.propagate_until(horizon)?;
        Ok(next)
    }

    pub(super) fn mapped_event(
        &self,
        time: f64,
        window: I,
        parameters: &[I],
    ) -> Result<Self, Error> {
        if !self.event_dependent || self.parameters == parameters {
            return Ok(self.clone());
        }
        if !time.is_finite() || !window.finite() || window.hi != time {
            return Err(Error::new(
                "event_resolution",
                "nonlinear event representative must be the upper endpoint of its time enclosure",
            ));
        }
        Self::initialized(
            self.context.clone(),
            parameters.to_vec(),
            time,
            Some(self.state_bounds(window)?),
            &self.tolerances,
        )
    }
}

fn collect_structure(
    expr: &Expression,
    program: &Program,
    owner: &str,
    row: &mut [I],
) -> Result<(), Error> {
    match expr {
        Expression::Add { left, right } | Expression::Multiply { left, right } => {
            collect_structure(left, program, owner, row)?;
            collect_structure(right, program, owner, row)
        }
        Expression::Power { base, .. } => collect_structure(base, program, owner, row),
        _ => {
            let deps = crate::events::affine(expr, program, owner)?;
            for node in deps.node_dependencies {
                row[node] = I::ONE;
            }
            for op in deps.operator_dependencies {
                row[program.nodes.len() + program.states.len() + op] = I::ONE;
            }
            Ok(())
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn nonlinear_cold_root_uncertainty_and_failed_restart_preserve_history() {
        let origin = serde_json::json!({"source":"dc.va","line":1,"column":1,"instance":"dut"});
        let program: Program = serde_json::from_value(serde_json::json!({
            "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","y"],
            "states":[{"instance":"dut","name":"q","kind":"real","initial":0.75}],
            "operators":[{"kind":"laplace_nd","numerator":[1],"denominator":[1,1],"origin":origin,
                "input":{"op":"add","left":{"op":"state","state":0},
                    "right":{"op":"multiply","left":{"op":"affine","constant":0.25,"terms":[]},
                        "right":{"op":"power","exponent":2,"base":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]}}}}}],
            "contributions":[{"branch":{"instance":"dut","local_positive":"r","local_negative":"y","kind":"voltage"},
                "positive":0,"negative":1,"origin":origin,
                "rhs":{"op":"multiply","left":{"op":"affine","constant":-1,"terms":[]},"right":{"op":"operator","operator":0}}}]
        })).unwrap();
        let trajectory = Trajectory::new(
            crate::ir::TransientInputs {
                pwl: vec![],
                output_times: vec![0.0, 0.5],
                stop: 0.5,
                max_step: 0.5,
            },
            0,
        )
        .unwrap();
        let accepted =
            NonlinearContinuous::new(&program, &trajectory, &[], &[0.75], 0.125).unwrap();
        let original = accepted.range_bounds(I::point(0.125)).unwrap();
        // At q=3/4 the selected root y=1 and its stationary trajectory
        // are exact. A midpoint-only parameter proof would accept this box.
        assert!(original[0].lo <= 1.0 && original[0].hi >= 1.0);
        let uncertain = NonlinearContinuous::initialized(
            accepted.context.clone(),
            vec![I {
                lo: 0.7499999,
                hi: 0.7500001,
            }],
            0.0,
            None,
            &accepted.tolerances,
        );
        assert_eq!(uncertain.err().unwrap().kind, "waveform_accuracy");
        let failed = accepted.restarted(0.125, I::point(0.125), &[I::point(1e300)], 0.5);
        assert!(failed.is_err());
        assert_eq!(accepted.range_bounds(I::point(0.125)).unwrap(), original);
        assert_eq!(accepted.certified_end(), 0.125);
        let retry = accepted
            .restarted(0.125, I::point(0.125), &[I::point(0.75)], 0.5)
            .unwrap();
        let clean = NonlinearContinuous::new(&program, &trajectory, &[], &[0.75], 0.5).unwrap();
        assert_eq!(
            retry.range_bounds(I::point(0.5)).unwrap(),
            clean.range_bounds(I::point(0.5)).unwrap()
        );
    }

    fn scalar(quadratic_sign: f64) -> NonlinearContinuous {
        let program = serde_json::from_value(serde_json::json!({
            "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0"],
            "contributions":[]
        }))
        .unwrap();
        let trajectory = Trajectory::new(
            crate::ir::TransientInputs {
                pwl: vec![],
                output_times: vec![0.0, 0.125],
                stop: 0.125,
                max_step: 0.125,
            },
            0,
        )
        .unwrap();
        NonlinearContinuous {
            context: Arc::new(Context {
                program,
                trajectory,
                driven: vec![],
            }),
            parameters: vec![],
            implicit: None,
            initial: vec![I::ONE],
            steps: vec![],
            start: 0.0,
            event_dependent: false,
            operators: Vec::new(),
            values: vec![vec![I::ONE, I::ZERO]],
            accuracy_rows: vec![vec![I::ONE, I::ZERO]],
            tolerances: Tolerances::default(),
            functions: vec![Polynomial::Multiply(
                Box::new(Polynomial::Linear(vec![I::ZERO, I::point(quadratic_sign)])),
                Box::new(Polynomial::Power(
                    Box::new(Polynomial::Linear(vec![I::ONE, I::ZERO])),
                    2,
                )),
            )],
        }
    }

    #[test]
    fn candidate_horizon_extension_preserves_prefix_and_rejected_retry() {
        let mut accepted = scalar(-1.0);
        accepted.propagate_until(0.05).unwrap();
        let prefix = accepted.range_bounds(I::point(0.05)).unwrap();
        assert_eq!(
            accepted.range_bounds(I::point(0.125)).err().unwrap().kind,
            "event_resolution"
        );
        let mut failed = accepted.clone();
        assert_eq!(
            failed.propagate_until(0.25).err().unwrap().kind,
            "event_resolution"
        );
        assert_eq!(accepted.certified_end(), 0.05);
        assert_eq!(accepted.range_bounds(I::point(0.05)).unwrap(), prefix);
        let mut discarded = accepted.clone();
        discarded.propagate_until(0.125).unwrap();
        let future = discarded.range_bounds(I::point(0.125)).unwrap();
        assert_eq!(discarded.range_bounds(I::point(0.05)).unwrap(), prefix);
        assert!(!accepted.same_history(&discarded));
        drop(discarded);
        let mut retry = accepted.clone();
        retry.propagate_until(0.125).unwrap();
        assert_eq!(retry.range_bounds(I::point(0.125)).unwrap(), future);
        let mut uninterrupted = scalar(-1.0);
        uninterrupted.propagate_until(0.125).unwrap();
        // Equal modes and end times do not identify dense history once
        // horizons can split a certified step into different prefixes.
        assert!(!uninterrupted.same_history(&retry));
        // y(1/8)=8/9. Exact products establish containment without
        // blessing the floating-point division as an exact oracle.
        assert!(
            crate::interval::sum_products_sign(&[(future[0].lo, 9.0), (-8.0, 1.0)]).unwrap() <= 0
        );
        assert!(
            crate::interval::sum_products_sign(&[(future[0].hi, 9.0), (-8.0, 1.0)]).unwrap() >= 0
        );
    }

    #[test]
    fn bounded_refinement_failure_preserves_accepted_history() {
        let accepted = scalar(1e300);
        let prefix = accepted.initial.clone();
        let mut candidate = accepted.clone();
        let (result, report) =
            crate::diagnostics::capture(Default::default(), || candidate.propagate_until(0.125));
        let error = result.unwrap_err();
        assert_eq!(error.kind, "waveform_accuracy");
        assert!(error.message.contains("64 trials"));
        assert_eq!(
            report.counters["nonlinear_rejected_trials"],
            MAX_REFINEMENTS as u64
        );
        assert_eq!(accepted.initial, prefix);
        assert_eq!(accepted.certified_end(), 0.0);
        assert!(accepted.steps.is_empty());
    }

    #[test]
    fn accumulated_roundoff_has_a_bounded_suffix_refinement_refusal() {
        let mut candidate = scalar(-1.0);
        candidate.tolerances = Tolerances {
            absolute: 1e-20,
            relative: 0.0,
        };
        let accepted = candidate.clone();
        let (result, report) =
            crate::diagnostics::capture(Default::default(), || candidate.propagate_until(0.125));
        let error = result.unwrap_err();
        assert_eq!(error.kind, "waveform_accuracy");
        assert!(error.message.contains("8 suffix refinements"));
        assert_eq!(
            report.counters["nonlinear_history_refinements"],
            MAX_HISTORY_REFINEMENTS as u64
        );
        assert!(report.counters["nonlinear_history_budget_exhausted"] > 0);
        assert!(candidate.same_history(&accepted));
    }

    #[test]
    fn internal_step_resource_limit_is_explicit() {
        let mut candidate = scalar(-1.0);
        candidate.functions[0] = Polynomial::Linear(vec![I::ZERO, I::ZERO]);
        Arc::get_mut(&mut candidate.context)
            .unwrap()
            .trajectory
            .config
            .max_step = 2_f64.powi(-20);
        let error = candidate.propagate_until(0.125).unwrap_err();
        assert_eq!(error.kind, "waveform_accuracy");
        assert!(error.message.contains("16384 stored internal steps"));
        assert!(candidate.steps.is_empty());
        assert_eq!(candidate.certified_end(), 0.0);
    }

    #[test]
    fn discarded_candidates_share_the_remaining_work_limit() {
        let mut candidate = scalar(-1.0);
        let accepted = candidate.clone();
        // A previously discarded suffix has already consumed this call's
        // work allowance; no step may be validated in the next attempt.
        let error = candidate.propagate_once(0.125, 1.0, &mut 0).unwrap_err();
        assert!(error
            .message
            .contains("cumulative 16384 candidate-step work limit"));
        assert!(candidate.same_history(&accepted));
    }

    #[test]
    fn directed_center_arithmetic_encloses_exact_binary_operations() {
        use num_rational::BigRational;
        let rational = |value| BigRational::from_float(value).unwrap();
        let contains = |bound: I, exact: BigRational| {
            assert!(!bound.lo.is_nan() && !bound.hi.is_nan());
            assert!(!bound.lo.is_finite() || rational(bound.lo) <= exact);
            assert!(!bound.hi.is_finite() || exact <= rational(bound.hi));
        };
        let values = [
            0.0,
            f64::from_bits(1),
            f64::MIN_POSITIVE,
            1.0,
            1.0_f64.next_up(),
            1e100,
            1e-100,
            -0.5,
        ];
        for a in values.into_iter().chain(values.map(|a| -a)) {
            for b in values.into_iter().chain(values.map(|b| -b)) {
                contains(point_sum(a, b), rational(a) + rational(b));
                contains(point_product(a, b), rational(a) * rational(b));
                for c in [0.0, 0.5, -1.0] {
                    let value = a.mul_add(b, c);
                    contains(
                        fma_error(a, b, c, value),
                        rational(a) * rational(b) + rational(c) - rational(value),
                    );
                }
            }
            for denominator in [1.0, 3.0, 13.0, 25.0] {
                contains(
                    tight_div_positive(I::point(a), denominator),
                    rational(a) / rational(denominator),
                );
            }
        }
        let coefficients = [
            I::point(1.0),
            I::point(-1e100),
            I::point(1e100),
            I {
                lo: 0.1,
                hi: 0.1_f64.next_up(),
            },
        ];
        for h in [-0.125, 0.0, 0.125, 1.0] {
            let bound = center_horner(&coefficients, I::point(h)).range();
            for mask in 0..16 {
                let exact =
                    coefficients
                        .iter()
                        .enumerate()
                        .fold(rational(0.0), |sum, (i, value)| {
                            let coefficient = if mask & (1 << i) == 0 {
                                value.lo
                            } else {
                                value.hi
                            };
                            sum + rational(coefficient) * rational(h).pow(i as i32)
                        });
                contains(bound, exact);
            }
        }
    }

    #[test]
    fn twosum_and_fma_error_enclose_gradual_underflow_boundary_cases() {
        use num_rational::BigRational;
        let rational = |value| BigRational::from_float(value).unwrap();
        let contains = |bound: I, exact: BigRational, operands: (f64, f64, f64)| {
            assert!(bound.finite(), "nonfinite bound for {operands:?}");
            assert!(
                rational(bound.lo) <= exact && exact <= rational(bound.hi),
                "bound {bound:?} excludes exact result for {operands:?}"
            );
        };
        let tiny = f64::from_bits(1);
        let normal = f64::MIN_POSITIVE;
        // A fixed corpus straddles both the subnormal/normal boundary and
        // the next binade, with small corrections, cancellation, and large
        // magnitude differences. Both signs and operand orders are covered.
        let positive = [
            0.0,
            tiny,
            2.0 * tiny,
            3.0 * tiny,
            normal.next_down().next_down(),
            normal.next_down(),
            normal,
            normal.next_up(),
            normal.next_up().next_up().next_up(),
            (2.0 * normal).next_down(),
            2.0 * normal,
            (2.0 * normal).next_up(),
            1.0,
        ];
        let values: Vec<_> = positive.into_iter().chain(positive.map(|v| -v)).collect();
        for &a in &values {
            for &c in &values {
                contains(point_sum(a, c), rational(a) + rational(c), (a, 1.0, c));
                // Half-unit products exercise an exact residual smaller
                // than the least subnormal; near-one factors mix normal
                // products with subnormal addition corrections.
                for b in [0.5, 1.0, 1.0_f64.next_up(), 1.5, -1.0] {
                    let value = a.mul_add(b, c);
                    contains(
                        fma_error(a, b, c, value),
                        rational(a) * rational(b) + rational(c) - rational(value),
                        (a, b, c),
                    );
                }
            }
        }
    }

    #[test]
    fn finite_fma_with_overflowing_unfused_sum_has_safe_error_fallback() {
        let a = f64::from_bits(0x7fb745d1745d1745);
        let b = 11.0;
        let c = 2.0_f64.powi(970);
        assert!((a * b).is_finite());
        assert!(!(a * b + c).is_finite());
        let value = a.mul_add(b, c);
        assert!(value.is_finite());
        let error = fma_error(a, b, c, value);
        assert_eq!(error.lo, f64::NEG_INFINITY);
        assert_eq!(error.hi, f64::INFINITY);
    }

    #[test]
    fn centered_flow_encloses_states_when_nominal_center_is_outside_state_box() {
        use num_rational::BigRational;
        let flow = scalar(-1.0);
        let state = I {
            lo: 0.99,
            hi: 0.991,
        };
        let center = CenterValue {
            point: 1.0,
            error: state - I::ONE,
        };
        let step = flow
            .trial_order(0.0, 1.0 / 32.0, &[state], &[], &[], ORDER, Some(&[center]))
            .unwrap();
        let bound = step.range(I::point(1.0 / 32.0))[0];
        let rational = |value| BigRational::from_float(value).unwrap();
        for x in [state.lo, state.hi] {
            let exact = rational(x) / (rational(1.0) + rational(x) * rational(1.0 / 32.0));
            assert!(rational(bound.lo) <= exact && exact <= rational(bound.hi));
        }
    }

    #[test]
    fn centered_taylor_keeps_source_uncertainty() {
        use num_rational::BigRational;
        let mut flow = scalar(-1.0);
        // x'=u*x², x(0)=1 gives x=1/(1-u*t). The source box
        // remains uncertain even when the initial state is a point.
        flow.functions[0] = Polynomial::Multiply(
            Box::new(Polynomial::Linear(vec![I::ZERO, I::ONE, I::ZERO])),
            Box::new(Polynomial::Power(
                Box::new(Polynomial::Linear(vec![I::ONE, I::ZERO, I::ZERO])),
                2,
            )),
        );
        let step = flow
            .trial(
                0.0,
                1.0 / 32.0,
                &[I::ONE],
                &[I { lo: -1.0, hi: 0.0 }],
                &[I::ZERO],
            )
            .unwrap();
        let bound = step.range(I::point(1.0 / 32.0))[0];
        let rational = |value| BigRational::from_float(value).unwrap();
        for u in [-1.0, -0.5, 0.0] {
            let exact = rational(1.0) / (rational(1.0) - rational(u) * rational(1.0 / 32.0));
            assert!(rational(bound.lo) <= exact && exact <= rational(bound.hi));
        }
        assert!(bound.hi - bound.lo > 0.03);
    }

    #[test]
    fn centered_taylor_flow_encloses_initial_box_and_contracts_decay_uncertainty() {
        use num_rational::BigRational;
        let flow = scalar(-1.0);
        let initial = I {
            lo: 1.0 - 1e-8,
            hi: 1.0 + 1e-8,
        };
        let step = flow.trial(0.0, 1.0 / 32.0, &[initial], &[], &[]).unwrap();
        let rational = |value| BigRational::from_float(value).unwrap();
        for t in [0.0, 1.0 / 64.0, 1.0 / 32.0] {
            let bound = step.range(I::point(t))[0];
            for x in [initial.lo, 1.0, initial.hi] {
                let exact = rational(x) / (rational(1.0) + rational(x) * rational(t));
                assert!(rational(bound.lo) <= exact && exact <= rational(bound.hi));
            }
        }
        let h = I::point(1.0 / 32.0);
        let endpoint = step.range(h)[0];
        let ordinary = horner(&step.coefficients[0], h)
            + step.remainder[0] * (0..=ORDER).fold(I::ONE, |v, _| v * h);
        assert!(endpoint.hi - endpoint.lo < initial.hi - initial.lo);
        assert!(endpoint.hi - endpoint.lo < ordinary.hi - ordinary.lo);
        let before = step.clone();
        let _ = step.range(I {
            lo: 0.0,
            hi: 1.0 / 32.0,
        });
        assert!(step == before);
    }

    #[test]
    fn taylor_remainder_encloses_exact_rational_decay_without_query_mutation() {
        let flow = scalar(-1.0);
        let step = flow.trial(0.0, 1.0 / 32.0, &[I::ONE], &[], &[]).unwrap();
        let at_end = step.range(I::point(1.0 / 32.0))[0];
        // Exact real answer is 32/33. Compare exact products, not a rounded
        // division oracle; the enclosure must contain that rational itself.
        assert!(
            crate::interval::sum_products_sign(&[(at_end.lo, 33.0), (-32.0, 1.0)]).unwrap() <= 0
        );
        assert!(
            crate::interval::sum_products_sign(&[(at_end.hi, 33.0), (-32.0, 1.0)]).unwrap() >= 0
        );
        let whole = step.range(I {
            lo: 0.0,
            hi: 1.0 / 32.0,
        })[0];
        assert!(whole.lo <= at_end.lo && whole.hi >= 1.0);
        let _ = step.range(I::point(1.0 / 64.0));
        assert_eq!(step.range(I::point(1.0 / 32.0))[0], at_end);
    }

    #[test]
    fn trajectory_tube_failure_is_rejected_and_initial_uncertainty_survives() {
        let flow = scalar(1.0);
        assert!(flow.trial(0.0, 1.0, &[I::ONE], &[], &[]).is_none());
        let uncertain = I {
            lo: 1.0,
            hi: 1.0 + 1e-10,
        };
        let step = flow.trial(0.0, 1.0 / 32.0, &[uncertain], &[], &[]).unwrap();
        let at_start = step.range(I::ZERO)[0];
        assert!(at_start.lo <= uncertain.lo && at_start.hi >= uncertain.hi);
        let at_end = step.range(I::point(1.0 / 32.0))[0];
        assert!(at_end.hi - at_end.lo >= uncertain.hi - uncertain.lo);
    }

    #[test]
    fn uncertain_restart_encloses_new_flow_across_source_corner_without_mutating_base() {
        use serde_json::json;
        let origin = json!({"source":"window.va","line":1,"column":1,"instance":"dut"});
        let program: Program = serde_json::from_value(json!({
            "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","u","y"],
            "states":[{"instance":"dut","name":"q","kind":"integer","initial":0}],
            "operators":[{"kind":"idt","ic":0,"origin":origin,
                "input":{"op":"multiply","left":{"op":"state","state":0},
                    "right":{"op":"power","exponent":2,"base":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]}}}}],
            "contributions":[{"branch":{"instance":"dut","local_positive":"y","local_negative":"r","kind":"voltage"},
                "positive":2,"negative":0,"rhs":{"op":"operator","operator":0},"origin":origin}]
        })).unwrap();
        let trajectory = Trajectory::new(
            crate::ir::TransientInputs {
                pwl: vec![vec![[0.0, 0.0], [0.5, 1.0], [1.0, 0.0]]],
                output_times: vec![0.0, 1.0],
                stop: 1.0,
                max_step: 1.0,
            },
            1,
        )
        .unwrap();
        let base = NonlinearContinuous::new(
            &program,
            &trajectory,
            &["u".into()],
            &[0.0],
            trajectory.config.stop,
        )
        .unwrap();
        let original = base.range_bounds(I::point(0.75)).unwrap();
        let window = I {
            lo: 0.5 - 1.0 / 1024.0,
            hi: 0.5 + 1.0 / 1024.0,
        };
        // Interior representatives still require a separate timing contract.
        let failure = base
            .restarted(window.lo, window, &[I::point(2.0)], trajectory.config.stop)
            .err()
            .unwrap();
        assert_eq!(failure.kind, "event_resolution");
        assert_eq!(base.range_bounds(I::point(0.75)).unwrap(), original);
        let candidate = base
            .restarted(window.hi, window, &[I::point(2.0)], trajectory.config.stop)
            .unwrap();
        let at_start = candidate.range_bounds(I::point(window.hi)).unwrap()[0];
        // q switches from 0 to 2 at any tau in the window, u is a triangle.
        // At tau=lo, integral(tau..hi) 2*u^2 is exactly numerator/denominator.
        // Including the interior source maximum u(.5)=1 is essential here.
        let numerator = (2_u64 * (1 << 30) - 16 * 511_u64.pow(3)) as f64;
        let denominator = (3_u64 * (1 << 30)) as f64;
        assert!(at_start.lo <= 0.0);
        assert!(
            crate::interval::sum_products_sign(&[(at_start.hi, denominator), (-numerator, 1.0)])
                .unwrap()
                >= 0
        );
        let future = candidate.range_bounds(I::point(0.75)).unwrap();
        assert_eq!(base.range_bounds(I::point(0.75)).unwrap(), original);
        drop(candidate);
        let retry = base
            .restarted(window.hi, window, &[I::point(2.0)], trajectory.config.stop)
            .unwrap();
        assert_eq!(retry.range_bounds(I::point(0.75)).unwrap(), future);
    }
}
