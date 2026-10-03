//! Index-one polynomial voltage DAEs, reduced by differentiating F(v,z,u)=0.
//! Initial roots are certified before continuation. Interval Gaussian solves
//! must prove F_v invertible throughout every Picard tube and Taylor remainder.
use super::*;
use crate::ir::{Response, Solution, Tolerances, TransientInputs, TransientTrace};
use crate::solver::Circuit;

#[derive(Clone)]
pub(super) struct ImplicitField {
    physical: usize,
    // Derivatives of each original constraint wrt [physical state, voltage, source].
    gradients: Vec<Vec<Polynomial>>,
}

fn solve(matrix: &[Vec<I>], rhs: &[I]) -> Option<Vec<I>> {
    let n = matrix.len();
    if n == 1 {
        let value = rhs[0] / matrix[0][0];
        return value.finite().then_some(vec![value]);
    }
    let rows = matrix
        .iter()
        .zip(rhs)
        .map(|(a, &b)| {
            let mut row = a.clone();
            row.push(b);
            row
        })
        .collect();
    let eliminated = affine_bounds::eliminate(rows, n, 1).ok()?;
    let values = back_substitute_eliminated(&eliminated, n, 1).ok()?;
    let values: Vec<_> = values.into_iter().map(|row| row[0]).collect();
    values.iter().all(|v| v.finite()).then_some(values)
}

impl ImplicitField {
    pub(super) fn jets(
        &self,
        functions: &[Polynomial],
        variables: &[Jet],
        slopes: &[I],
        order: usize,
    ) -> Option<Vec<Jet>> {
        let n = self.gradients.len();
        let physical: Vec<_> = functions[..self.physical]
            .iter()
            .map(|p| p.jet(variables, order))
            .collect();
        let gradients: Vec<Vec<Jet>> = self
            .gradients
            .iter()
            .map(|row| row.iter().map(|p| p.jet(variables, order)).collect())
            .collect();
        let jacobian: Vec<Vec<I>> = gradients
            .iter()
            .map(|row| {
                row[self.physical..self.physical + n]
                    .iter()
                    .map(|v| v[0])
                    .collect()
            })
            .collect();
        // F_v(t) v'(t) = -F_z(t) f(t) - F_u(t) m. Solve
        // J_0 v'_k = b_k - sum_(j=1)^k J_j v'_(k-j).
        let mut voltage = vec![vec![I::ZERO; order + 1]; n];
        for k in 0..=order {
            let rhs: Vec<_> = gradients
                .iter()
                .map(|row| {
                    let mut value = I::ZERO;
                    for (gradient, derivative) in row.iter().take(self.physical).zip(&physical) {
                        for j in 0..=k {
                            value = value - gradient[j] * derivative[k - j];
                        }
                    }
                    for (gradient, &slope) in row.iter().skip(self.physical + n).zip(slopes) {
                        value = value - gradient[k] * slope;
                    }
                    for (gradient, derivative) in
                        row.iter().skip(self.physical).take(n).zip(&voltage)
                    {
                        for j in 1..=k {
                            value = value - gradient[j] * derivative[k - j];
                        }
                    }
                    value
                })
                .collect();
            for (row, value) in voltage.iter_mut().zip(solve(&jacobian, &rhs)?) {
                row[k] = value;
            }
        }
        Some(physical.into_iter().chain(voltage).collect())
    }
}

impl Polynomial {
    fn derivative(&self, variable: usize) -> Self {
        match self {
            Self::Linear(row) => {
                let mut out = vec![I::ZERO; row.len()];
                *out.last_mut().unwrap() = row[variable];
                Self::Linear(out)
            }
            Self::Add(a, b) => Self::Add(
                Box::new(a.derivative(variable)),
                Box::new(b.derivative(variable)),
            ),
            Self::Multiply(a, b) => Self::Add(
                Box::new(Self::Multiply(Box::new(a.derivative(variable)), b.clone())),
                Box::new(Self::Multiply(a.clone(), Box::new(b.derivative(variable)))),
            ),
            Self::Power(a, n) => {
                let power = if *n == 1 {
                    a.derivative(variable)
                } else {
                    Self::Multiply(
                        Box::new(a.derivative(variable)),
                        Box::new(Self::Power(a.clone(), n - 1)),
                    )
                };
                let mut coefficient = vec![I::ZERO; self.width()];
                *coefficient.last_mut().unwrap() = I::point(*n as f64);
                Self::Multiply(Box::new(Self::Linear(coefficient)), Box::new(power))
            }
        }
    }
    fn width(&self) -> usize {
        match self {
            Self::Linear(row) => row.len(),
            Self::Add(a, _) | Self::Multiply(a, _) | Self::Power(a, _) => a.width(),
        }
    }
}

fn bind(expr: &Expression, values: &[Expression]) -> Result<Expression, Error> {
    Ok(match expr {
        Expression::Operator { operator } => values
            .get(*operator)
            .ok_or_else(|| Error::new("invalid_ir", "operator index out of range"))?
            .clone(),
        Expression::Add { left, right } => Expression::Add {
            left: Box::new(bind(left, values)?),
            right: Box::new(bind(right, values)?),
        },
        Expression::Multiply { left, right } => Expression::Multiply {
            left: Box::new(bind(left, values)?),
            right: Box::new(bind(right, values)?),
        },
        Expression::Power { base, exponent } => Expression::Power {
            base: Box::new(bind(base, values)?),
            exponent: *exponent,
        },
        Expression::Affine { .. } => expr.clone(),
        _ => {
            return Err(Error::new(
                "unsupported_implicit_dynamics",
                "implicit polynomial dynamics cannot contain state or conditional expressions",
            ))
        }
    })
}

fn circuit(
    program: &Program,
    driven: &[String],
    operators: &[f64],
    tolerances: &Tolerances,
) -> Result<Circuit, Error> {
    let values: Vec<_> = operators
        .iter()
        .map(|&constant| Expression::Affine {
            constant,
            terms: vec![],
        })
        .collect();
    let mut frozen = program.clone();
    for c in &mut frozen.contributions {
        c.rhs = bind(&c.rhs, &values)?;
    }
    frozen.operators.clear();
    Circuit::new(frozen, driven, tolerances.clone())
}

// Operator histories are uncertain inputs to the initial algebraic root,
// rather than rounded constants. This reuses the voltage root certificate
// and preserves the filter DC enclosure in the selected initial branch.
fn initial_root(
    program: &Program,
    driven: &[String],
    inputs: &[f64],
    input_bounds: &[I],
    operators: &[I],
    tolerances: &Tolerances,
) -> Result<Solution, Error> {
    let mut frozen = program.clone();
    let mut names = driven.to_vec();
    let mut values = Vec::new();
    let mut points = inputs.to_vec();
    let mut bounds = input_bounds.to_vec();
    for (i, &value) in operators.iter().enumerate() {
        let mut name = format!("$implicit-history:{i}");
        while frozen.nodes.contains(&name) {
            name.push('$');
        }
        let node = frozen.nodes.len();
        names.push(name.clone());
        frozen.nodes.push(name);
        values.push(Expression::Affine {
            constant: 0.0,
            terms: vec![crate::ir::Term {
                node,
                coefficient: 1.0,
            }],
        });
        points.push(point_value(value)?);
        bounds.push(value);
    }
    for c in &mut frozen.contributions {
        c.rhs = bind(&c.rhs, &values)?;
    }
    frozen.operators.clear();
    let system = Circuit::new(frozen, &names, tolerances.clone())?;
    let solution = system.solve(&points)?;
    system.check_waveform_accuracy(&solution, &bounds)?;
    Ok(solution)
}

struct Coordinates {
    nodes: Vec<Option<usize>>,
    sources: Vec<Option<usize>>,
    outputs: Vec<Vec<I>>,
    width: usize,
}
impl Coordinates {
    fn source_input(
        &self,
        expr: &Expression,
        program: &Program,
        origin: &Origin,
    ) -> Result<Vec<I>, Error> {
        let input = affine_for_operator_input(expr, program, origin)?;
        let mut row = vec![I::ZERO; self.width];
        *row.last_mut().unwrap() = *input.last().unwrap();
        for (node, source) in self.sources.iter().enumerate() {
            if let Some(index) = source {
                row[*index] = input[node];
            }
        }
        Ok(row)
    }

    fn expression(
        &self,
        expr: &Expression,
        program: &Program,
        owner: &str,
    ) -> Result<Polynomial, Error> {
        validate(expr, program, owner)?;
        Ok(match expr {
            Expression::Add { left, right } => Polynomial::Add(
                Box::new(self.expression(left, program, owner)?),
                Box::new(self.expression(right, program, owner)?),
            ),
            Expression::Multiply { left, right } => Polynomial::Multiply(
                Box::new(self.expression(left, program, owner)?),
                Box::new(self.expression(right, program, owner)?),
            ),
            Expression::Power { base, exponent } => {
                Polynomial::Power(Box::new(self.expression(base, program, owner)?), *exponent)
            }
            Expression::Operator { operator } => {
                Polynomial::Linear(self.outputs[*operator].clone())
            }
            Expression::Affine { constant, terms } => {
                let mut row = vec![I::ZERO; self.width];
                *row.last_mut().unwrap() = I::point(*constant);
                for term in terms {
                    if term.node == 0 {
                        continue;
                    }
                    let index = self.nodes[term.node]
                        .or(self.sources[term.node])
                        .ok_or_else(|| Error::new("invalid_ir", "missing implicit coordinate"))?;
                    row[index] = row[index] + I::point(term.coefficient);
                }
                Polynomial::Linear(row)
            }
            _ => {
                return Err(Error::new(
                    "unsupported_implicit_dynamics",
                    "implicit continuous expressions must be polynomial",
                ))
            }
        })
    }
}

fn initialize(
    program: &Program,
    trajectory: &Trajectory,
    driven: &[String],
) -> Result<(NonlinearContinuous, Coordinates), Error> {
    if !program.states.is_empty() || !program.events.is_empty() {
        return Err(Error::new(
            "unsupported_implicit_dynamics",
            "index-one polynomial DAE currently requires an event-free network",
        ));
    }
    let mut initial = Vec::new();
    let mut operators = Vec::new();
    let mut identities = BTreeSet::new();
    let input_nodes = driven_node_indices(program, driven)?;
    let source_bounds = trajectory.value_bounds(0.0);
    for (i, op) in program.operators.iter().enumerate() {
        let origin = op.origin();
        if origin.instance.is_empty()
            || origin.source.is_empty()
            || origin.line == 0
            || origin.column == 0
            || !origin.valid_expansion()
            || !program
                .contributions
                .iter()
                .any(|c| c.origin.instance == origin.instance)
        {
            return Err(Error::new("invalid_ir", "invalid implicit operator origin"));
        }
        if !identities.insert((
            origin.instance.clone(),
            origin.source.clone(),
            origin.line,
            origin.column,
            origin.expansion.clone(),
        )) {
            return Err(Error::new(
                "invalid_ir",
                "duplicate implicit operator call-site identity",
            ));
        }
        let start = initial.len();
        let (kind, laplace) = match op {
            OperatorSpec::Idt { input, ic, reset: None, .. } => {
                validate(input, program, &origin.instance)?;
                if !ic.is_finite() {
                    return Err(unsupported(origin, "nonfinite implicit integral IC"));
                }
                initial.push(I::point(*ic));
                (ContinuousKind::Idt, None)
            }
            OperatorSpec::LaplaceNd { input, numerator, denominator, .. } => {
                let dependencies = crate::events::affine(input, program, &origin.instance)?;
                if !dependencies.operator_dependencies.is_empty()
                    || !dependencies.state_dependencies.is_empty()
                    || dependencies.node_dependencies.iter()
                        .any(|node| *node != 0 && !input_nodes.contains(node)) {
                    return Err(unsupported(origin,
                        "implicit DAE filter DC initialization currently requires a direct PWL affine input"));
                }
                let row = affine_for_operator_input(input, program, origin)?;
                let mut dc = *row.last().unwrap();
                for (&node, &value) in input_nodes.iter().zip(&source_bounds) {
                    dc = dc + row[node] * value;
                }
                let filter = laplace_system(numerator, denominator, origin)?;
                let rhs: Vec<_> = filter.b.iter().map(|&b| -b * dc).collect();
                let state = solve(&filter.a, &rhs).ok_or_else(|| unsupported(origin,
                    "cannot enclose implicit filter DC state"))?;
                initial.extend(state);
                (ContinuousKind::LaplaceNd, Some(filter))
            }
            _ => return Err(unsupported(origin,
                "implicit polynomial DAE supports explicit-IC unreset integrals and direct PWL proper filters")),
        };
        operators.push(NetworkOperator {
            operator: i,
            kind,
            origin: origin.clone(),
            states: (start..initial.len()).collect(),
            input: None,
            laplace,
            held_reset: false,
        });
    }
    // Validate original node/branch indices before building any coordinate row.
    let root_tolerances = Tolerances {
        absolute: 1e-15,
        relative: 1e-14,
    };
    let _ = circuit(
        program,
        driven,
        &vec![0.0; operators.len()],
        &root_tolerances,
    )?;
    let physical = initial.len();
    let unknown: Vec<_> = (1..program.nodes.len())
        .filter(|node| !input_nodes.contains(node))
        .collect();
    let count = physical + unknown.len();
    if count + 2 * input_nodes.len() + 1 > 32 {
        return Err(Error::new(
            "waveform_accuracy",
            "implicit state/source dimension exceeds 32",
        ));
    }
    let mut coordinates = Coordinates {
        nodes: vec![None; program.nodes.len()],
        sources: vec![None; program.nodes.len()],
        outputs: vec![vec![]; operators.len()],
        width: count + input_nodes.len() + 1,
    };
    for (i, &node) in unknown.iter().enumerate() {
        coordinates.nodes[node] = Some(physical + i);
    }
    for (i, &node) in input_nodes.iter().enumerate() {
        coordinates.sources[node] = Some(count + i);
    }
    for op in &operators {
        let mut row = vec![I::ZERO; coordinates.width];
        if let Some(filter) = &op.laplace {
            for (&state, &coefficient) in op.states.iter().zip(&filter.c) {
                row[state] = coefficient;
            }
            let OperatorSpec::LaplaceNd { input, .. } = &program.operators[op.operator] else {
                unreachable!()
            };
            let input = coordinates.source_input(input, program, &op.origin)?;
            for (slot, value) in row.iter_mut().zip(input) {
                *slot = *slot + filter.d * value;
            }
        } else {
            row[op.states[0]] = I::ONE;
        }
        coordinates.outputs[op.operator] = row;
    }
    let mut constraints = BTreeMap::new();
    for c in &program.contributions {
        let rhs = coordinates.expression(&c.rhs, program, &c.origin.instance)?;
        let row = constraints.entry(c.branch.clone()).or_insert_with(|| {
            let mut row = vec![I::ZERO; coordinates.width];
            for (node, sign) in [(c.positive, 1.0), (c.negative, -1.0)] {
                if node != 0 {
                    if let Some(index) = coordinates.nodes[node].or(coordinates.sources[node]) {
                        row[index] = row[index] + I::point(sign);
                    }
                }
            }
            Polynomial::Linear(row)
        });
        let mut minus = vec![I::ZERO; coordinates.width];
        *minus.last_mut().unwrap() = -I::ONE;
        *row = Polynomial::Add(
            Box::new(row.clone()),
            Box::new(Polynomial::Multiply(
                Box::new(Polynomial::Linear(minus)),
                Box::new(rhs),
            )),
        );
    }
    if constraints.len() != unknown.len() {
        return Err(Error::new(
            "unsupported_implicit_dynamics",
            "index-one DAE requires one independent voltage constraint per unknown voltage",
        ));
    }
    // Newton selects the local initial branch; this separate certificate proves
    // a root within its box. The full box, not the point, enters dynamic history.
    let forcing: Vec<_> = initial
        .iter()
        .copied()
        .chain(vec![I::ZERO; unknown.len()])
        .chain(source_bounds.iter().copied())
        .chain([I::ONE])
        .collect();
    let output_bounds: Vec<_> = coordinates
        .outputs
        .iter()
        .map(|row| dot(row, &forcing, "implicit initial history"))
        .collect::<Result<_, _>>()?;
    let solution = initial_root(
        program,
        driven,
        &trajectory.values(0.0),
        &source_bounds,
        &output_bounds,
        &root_tolerances,
    )?;
    for &node in &unknown {
        let value = solution.voltages[node];
        let radius = (I::point(root_tolerances.absolute)
            + I::point(root_tolerances.relative) * I::point(value.abs()))
        .hi;
        initial.push(I {
            lo: (value - radius).next_down(),
            hi: (value + radius).next_up(),
        });
    }
    let gradients = constraints
        .into_values()
        .map(|constraint| {
            (0..count + input_nodes.len())
                .map(|i| constraint.derivative(i))
                .collect()
        })
        .collect();
    let mut functions = Vec::new();
    for op in &operators {
        match &program.operators[op.operator] {
            OperatorSpec::Idt { input, .. } => {
                functions.push(coordinates.expression(input, program, &op.origin.instance)?);
            }
            OperatorSpec::LaplaceNd { input, .. } => {
                let input =
                    Polynomial::Linear(coordinates.source_input(input, program, &op.origin)?);
                let filter = op.laplace.as_ref().unwrap();
                for (local, matrix_row) in filter.a.iter().enumerate() {
                    let mut row = vec![I::ZERO; coordinates.width];
                    for (&state, &coefficient) in op.states.iter().zip(matrix_row) {
                        row[state] = coefficient;
                    }
                    let mut gain = vec![I::ZERO; coordinates.width];
                    *gain.last_mut().unwrap() = filter.b[local];
                    functions.push(Polynomial::Add(
                        Box::new(Polynomial::Linear(row)),
                        Box::new(Polynomial::Multiply(
                            Box::new(Polynomial::Linear(gain)),
                            Box::new(input.clone()),
                        )),
                    ));
                }
            }
            _ => unreachable!(),
        }
    }
    let values = coordinates
        .outputs
        .iter()
        .map(|row| {
            let mut extended = row[..row.len() - 1].to_vec();
            extended.extend(vec![I::ZERO; input_nodes.len()]);
            extended.push(*row.last().unwrap());
            extended
        })
        .collect();
    let mut flow = NonlinearContinuous {
        context: Arc::new(Context {
            program: program.clone(),
            trajectory: trajectory.clone(),
            driven: driven.to_vec(),
        }),
        parameters: vec![],
        functions,
        implicit: Some(ImplicitField {
            physical,
            gradients,
        }),
        operators,
        values,
        initial,
        steps: Vec::new(),
        start: 0.0,
        event_dependent: false,
    };
    // The common Picard/Taylor engine validates the rational reduced field;
    // F_v inversion is mandatory even when the resulting derivative is zero.
    flow.propagate_until(trajectory.config.stop)?;
    Ok((flow, coordinates))
}

pub(crate) fn run(
    program: Program,
    driven: Vec<String>,
    config: TransientInputs,
    tolerances: Tolerances,
) -> Result<Response, Error> {
    let trajectory = Trajectory::new(config, driven.len())?;
    let (flow, coordinates) = initialize(&program, &trajectory, &driven)?;
    let mut solutions = Vec::<Solution>::new();
    for &time in &trajectory.config.output_times {
        let state = flow.state_bounds(I::point(time))?;
        let inputs = trajectory.values(time);
        let mut guess = vec![0.0; program.nodes.len()];
        for (node, index) in coordinates.nodes.iter().enumerate() {
            if let Some(i) = index {
                guess[node] = point_value(state[*i])?;
            }
        }
        let op: Vec<_> = flow
            .range_bounds(I::point(time))?
            .into_iter()
            .map(point_value)
            .collect::<Result<_, _>>()?;
        let circuit = circuit(&program, &driven, &op, &tolerances)?;
        let solution = circuit.solve_with_initial(&inputs, Some(&guess))?;
        let input_bounds = trajectory.value_bounds(time);
        for (node, &actual) in solution.voltages.iter().enumerate() {
            let exact = if node == 0 {
                I::ZERO
            } else if let Some(i) = coordinates.nodes[node] {
                state[i]
            } else {
                input_bounds[driven
                    .iter()
                    .position(|name| *name == program.nodes[node])
                    .unwrap()]
            };
            let budget = I::point(tolerances.absolute)
                + I::point(tolerances.relative) * I::point(actual.abs());
            let error = I::point(actual) - exact;
            if !exact.finite()
                || !error.finite()
                || !budget.finite()
                || error.magnitude() > budget.lo
            {
                return Err(Error::new(
                    "waveform_accuracy",
                    format!(
                        "implicit dynamic forward error at {}: bound {:e}, budget {:e}",
                        program.nodes[node],
                        error.magnitude(),
                        budget.lo
                    ),
                ));
            }
        }
        // Circuit solve checks the original (operator-bound) contribution
        // residuals. Forward history error is checked independently above.
        solutions.push(solution);
    }
    let trace = TransientTrace {
        times: trajectory.config.output_times.clone(),
        state_names: vec![],
        states: vec![vec![]; solutions.len()],
        events: vec![],
        accepted_steps: flow.steps.len(),
        discarded_trials: 0,
    };
    Ok(Response {
        engine: concat!("evas-implicit-", env!("CARGO_PKG_VERSION")).into(),
        schema_version: crate::ir::SCHEMA_VERSION,
        nodes: program.nodes,
        solutions,
        transient: Some(trace),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn singular_implicit_field_rejects_even_zero_flow_and_retry_is_unchanged() {
        // F=y+y^2-z, z'=0. At y=-1/2, F_y=0: a zero derivative
        // numerator must not conceal that index-one continuation is unproved.
        let variable = |i| {
            let mut row = vec![I::ZERO; 3];
            row[i] = I::ONE;
            Polynomial::Linear(row)
        };
        let constant = |c| Polynomial::Linear(vec![I::ZERO, I::ZERO, I::point(c)]);
        let field = ImplicitField {
            physical: 1,
            gradients: vec![vec![
                constant(-1.0),
                Polynomial::Add(
                    Box::new(constant(1.0)),
                    Box::new(Polynomial::Multiply(
                        Box::new(constant(2.0)),
                        Box::new(variable(1)),
                    )),
                ),
            ]],
        };
        let functions = vec![constant(0.0)];
        let invalid = vec![vec![I::point(-0.25)], vec![I::point(-0.5)]];
        assert!(field.jets(&functions, &invalid, &[], 0).is_none());
        let valid = vec![vec![I::ZERO], vec![I::ZERO]];
        let original = field.jets(&functions, &valid, &[], 0).unwrap();
        assert!(original.iter().all(|jet| jet[0].zero()));
        assert!(field.jets(&functions, &invalid, &[], 0).is_none());
        assert_eq!(field.jets(&functions, &valid, &[], 0).unwrap(), original);
    }

    #[test]
    fn rational_voltage_enclosure_contains_exact_half_without_query_mutation() {
        let origin = json!({"source":"implicit.va","line":1,"column":1,"instance":"dut"});
        let program:Program=serde_json::from_value(json!({
            "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","u","y"],
            "operators":[{"kind":"idt","ic":0,"input":{"op":"affine","constant":0,"terms":[]},"origin":origin}],
            "contributions":[{"branch":{"instance":"dut","local_positive":"p","local_negative":"r","kind":"voltage"},"positive":2,"negative":0,"origin":origin,
                "rhs":{"op":"add","left":{"op":"add","left":{"op":"operator","operator":0},"right":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]}},
                    "right":{"op":"multiply","left":{"op":"affine","constant":-1,"terms":[]},"right":{"op":"power","exponent":2,"base":{"op":"affine","constant":0,"terms":[{"node":2,"coefficient":1}]}}}}}]
        })).unwrap();
        let trajectory = Trajectory::new(
            TransientInputs {
                pwl: vec![vec![[0.0, 0.0], [0.75, 0.75]]],
                output_times: vec![0.0, 0.75],
                stop: 0.75,
                max_step: 0.75,
            },
            1,
        )
        .unwrap();
        let (flow, coordinates) = initialize(&program, &trajectory, &["u".into()]).unwrap();
        let index = coordinates.nodes[2].unwrap();
        let original = flow.state_bounds(I::point(0.75)).unwrap();
        // At u=3/4, y+y^2=3/4 has the exact selected root y=1/2.
        assert!(original[index].lo <= 0.5 && original[index].hi >= 0.5);
        let _ = flow.state_bounds(I { lo: 0.125, hi: 0.5 }).unwrap();
        assert_eq!(flow.state_bounds(I::point(0.75)).unwrap(), original);
    }

    #[test]
    fn filter_dc_enclosure_enters_implicit_root_and_failed_query_is_pure() {
        let origin = json!({"source":"filter.va","line":1,"column":1,"instance":"dut"});
        let program: Program = serde_json::from_value(json!({
            "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","u","y"],
            "operators":[{"kind":"laplace_nd","numerator":[1],"denominator":[3,1],
                "input":{"op":"add","left":{"op":"affine","constant":1,"terms":[]},
                    "right":{"op":"affine","constant":-1,"terms":[{"node":1,"coefficient":1},{"node":0,"coefficient":-1}]}},"origin":origin}],
            "contributions":[{"branch":{"instance":"dut","local_positive":"p","local_negative":"r","kind":"voltage"},"positive":2,"negative":0,"origin":origin,
                "rhs":{"op":"add","left":{"op":"operator","operator":0},
                    "right":{"op":"multiply","left":{"op":"affine","constant":-1,"terms":[]},
                        "right":{"op":"power","exponent":2,"base":{"op":"affine","constant":0,"terms":[{"node":2,"coefficient":1}]}}}}}]
        })).unwrap();
        let trajectory = Trajectory::new(
            TransientInputs {
                pwl: vec![vec![[0.0, 2.25], [1.0, 2.25]]],
                output_times: vec![0.0, 1.0],
                stop: 1.0,
                max_step: 1.0,
            },
            1,
        )
        .unwrap();
        let (flow, coordinates) = initialize(&program, &trajectory, &["u".into()]).unwrap();
        // f(0)=9/4 / 3=3/4 and y+y^2=3/4 has the selected exact root 1/2.
        let voltage = coordinates.nodes[2].unwrap();
        let initial = flow.state_bounds(I::ZERO).unwrap();
        assert!(initial[voltage].lo <= 0.5 && initial[voltage].hi >= 0.5);
        let output = flow.range_bounds(I::ZERO).unwrap()[0];
        assert!(output.lo <= 0.75 && output.hi >= 0.75);
        let original = flow.state_bounds(I::ONE).unwrap();
        assert!(flow.state_bounds(I::point(2.0)).is_err());
        assert_eq!(flow.state_bounds(I::ONE).unwrap(), original);
    }
}
