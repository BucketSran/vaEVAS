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

fn bind(expr: &Expression, values: &[f64]) -> Result<Expression, Error> {
    Ok(match expr {
        Expression::Operator { operator } => Expression::Affine {
            constant: *values
                .get(*operator)
                .ok_or_else(|| Error::new("invalid_ir", "operator index out of range"))?,
            terms: vec![],
        },
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
    let mut frozen = program.clone();
    for c in &mut frozen.contributions {
        c.rhs = bind(&c.rhs, operators)?;
    }
    frozen.operators.clear();
    Circuit::new(frozen, driven, tolerances.clone())
}

struct Coordinates {
    physical: usize,
    nodes: Vec<Option<usize>>,
    sources: Vec<Option<usize>>,
    width: usize,
}
impl Coordinates {
    fn variable(&self, index: usize) -> Polynomial {
        let mut row = vec![I::ZERO; self.width];
        row[index] = I::ONE;
        Polynomial::Linear(row)
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
            Expression::Operator { operator } => self.variable(*operator),
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
    for (i, op) in program.operators.iter().enumerate() {
        let OperatorSpec::Idt {
            input,
            ic,
            reset: None,
            origin,
        } = op
        else {
            return Err(unsupported(
                op.origin(),
                "implicit polynomial DAE requires explicit-IC unreset integrals",
            ));
        };
        if origin.instance.is_empty()
            || origin.source.is_empty()
            || origin.line == 0
            || origin.column == 0
            || !program
                .contributions
                .iter()
                .any(|c| c.origin.instance == origin.instance)
        {
            return Err(Error::new("invalid_ir", "invalid implicit operator origin"));
        }
        if !ic.is_finite() {
            return Err(unsupported(origin, "nonfinite implicit integral IC"));
        }
        if !identities.insert((
            origin.instance.clone(),
            origin.source.clone(),
            origin.line,
            origin.column,
        )) {
            return Err(Error::new(
                "invalid_ir",
                "duplicate implicit operator call-site identity",
            ));
        }
        validate(input, program, &origin.instance)?;
        initial.push(I::point(*ic));
        operators.push(NetworkOperator {
            operator: i,
            kind: ContinuousKind::Idt,
            origin: origin.clone(),
            states: vec![i],
            input: None,
            laplace: None,
            held_reset: false,
        });
    }
    // Validate original node/branch indices before building any coordinate row.
    let ic: Vec<_> = initial.iter().map(|v| v.lo).collect();
    let root_tolerances = Tolerances {
        absolute: 1e-15,
        relative: 1e-14,
    };
    let initial_circuit = circuit(program, driven, &ic, &root_tolerances)?;
    let physical = initial.len();
    let input_nodes = driven_node_indices(program, driven)?;
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
        physical,
        nodes: vec![None; program.nodes.len()],
        sources: vec![None; program.nodes.len()],
        width: count + input_nodes.len() + 1,
    };
    for (i, &node) in unknown.iter().enumerate() {
        coordinates.nodes[node] = Some(physical + i);
    }
    for (i, &node) in input_nodes.iter().enumerate() {
        coordinates.sources[node] = Some(count + i);
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
    let solution = initial_circuit.solve(&trajectory.values(0.0))?;
    initial_circuit.check_waveform_accuracy(&solution, &trajectory.value_bounds(0.0))?;
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
    let functions = program
        .operators
        .iter()
        .map(|op| {
            let OperatorSpec::Idt { input, origin, .. } = op else {
                unreachable!()
            };
            coordinates.expression(input, program, &origin.instance)
        })
        .collect::<Result<Vec<_>, _>>()?;
    let values = (0..physical)
        .map(|i| {
            let mut row = vec![I::ZERO; count + 2 * input_nodes.len() + 1];
            row[i] = I::ONE;
            row
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
        let op: Vec<_> = state[..coordinates.physical]
            .iter()
            .map(|&v| point_value(v))
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
}
