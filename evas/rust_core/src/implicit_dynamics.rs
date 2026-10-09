//! Index-one polynomial voltage DAEs, reduced by differentiating F(v,z,u)=0.
//! Initial roots are certified before continuation. Interval Gaussian solves
//! must prove F_v invertible throughout every Picard tube and Taylor remainder.
use super::initialization::{bind, joint_dc, solve};
use super::*;
use crate::ir::{Response, Solution, Tolerances, TransientInputs, TransientTrace};
use crate::solver::Circuit;

#[derive(Clone)]
pub(super) struct ImplicitField {
    physical: usize,
    // Derivatives of each original constraint wrt [physical state, voltage, source].
    gradients: Vec<Vec<Polynomial>>,
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
        c.rhs = bind(&c.rhs, &values, &[])?;
    }
    frozen.operators.clear();
    Circuit::new(frozen, driven, tolerances.clone())
}

struct Coordinates {
    physical: usize,
    nodes: Vec<Option<usize>>,
    sources: Vec<Option<usize>>,
    outputs: Vec<Vec<I>>,
    width: usize,
}
impl Coordinates {
    // Freeze only physical history, keeping every live voltage/source term
    // in the same algebraic solve. Coefficient midpoints are Newton inputs;
    // the original interval rows remain authoritative for acceptance below.
    fn point_circuit(
        &self,
        program: &Program,
        driven: &[String],
        state: &[I],
        inputs: &[f64],
        tolerances: &Tolerances,
    ) -> Result<(Circuit, Vec<f64>), Error> {
        let mut frozen = program.clone();
        let mut names = driven.to_vec();
        let mut inputs = inputs.to_vec();
        let mut history = Vec::new();
        for (i, &value) in state[..self.physical].iter().enumerate() {
            let mut name = format!("$implicit-state:{i}");
            while frozen.nodes.contains(&name) {
                name.push('$');
            }
            history.push(frozen.nodes.len());
            names.push(name.clone());
            frozen.nodes.push(name);
            inputs.push(point_value(value)?);
        }
        let mut outputs = Vec::new();
        for row in &self.outputs {
            let mut terms = Vec::new();
            for (&node, &coefficient) in history.iter().zip(row) {
                terms.push(crate::ir::Term {
                    node,
                    coefficient: point_value(coefficient)?,
                });
            }
            for (node, (&voltage, &source)) in
                self.nodes.iter().zip(&self.sources).enumerate().skip(1)
            {
                let index = voltage.or(source).unwrap();
                terms.push(crate::ir::Term {
                    node,
                    coefficient: point_value(row[index])?,
                });
            }
            outputs.push(Expression::Affine {
                constant: point_value(*row.last().unwrap())?,
                terms,
            });
        }
        for c in &mut frozen.contributions {
            c.rhs = bind(&c.rhs, &outputs, &[])?;
        }
        frozen.operators.clear();
        Ok((Circuit::new(frozen, &names, tolerances.clone())?, inputs))
    }

    fn check_original_relations(
        &self,
        program: &Program,
        state: &[I],
        input_bounds: &[I],
        solution: &Solution,
        tolerances: &Tolerances,
    ) -> Result<(), Error> {
        let mut variables: Vec<Jet> = state
            .iter()
            .chain(input_bounds)
            .map(|&value| vec![value])
            .collect();
        for (node, index) in self.nodes.iter().enumerate() {
            if let Some(index) = index {
                variables[*index][0] = I::point(solution.voltages[node]);
            }
        }
        let node_bound = |node: usize| {
            if node == 0 {
                I::ZERO
            } else {
                variables[self.nodes[node].or(self.sources[node]).unwrap()][0]
            }
        };
        let mut branches = BTreeMap::new();
        for c in &program.contributions {
            let rhs = self
                .expression(&c.rhs, program, &c.origin.instance)?
                .jet(&variables, 0)[0];
            let row = branches.entry(&c.branch).or_insert_with(|| {
                (
                    node_bound(c.positive) - node_bound(c.negative),
                    I::ZERO,
                    I::point(tolerances.absolute)
                        + I::point(tolerances.relative)
                            * I::point(
                                (solution.voltages[c.positive] - solution.voltages[c.negative])
                                    .abs(),
                            ),
                    c.origin.label(),
                )
            });
            row.1 = row.1 + rhs;
        }
        for (lhs, rhs, budget, origin) in branches.into_values() {
            let residual = lhs - rhs;
            if !residual.finite() || !budget.finite() || residual.magnitude() > budget.lo {
                return Err(Error::new("waveform_accuracy",format!(
                    "implicit original relation residual [{:e},{:e}] exceeds budget {:e} at {origin}",
                    residual.lo,residual.hi,budget.lo)));
            }
        }
        Ok(())
    }

    fn build_outputs(
        &self,
        program: &Program,
        operators: &[NetworkOperator],
    ) -> Result<Vec<Vec<I>>, Error> {
        let n = operators.len();
        let mut rows = Vec::new();
        for op in operators {
            let mut row = vec![I::ZERO; n + self.width];
            row[op.operator] = I::ONE;
            if let Some(filter) = &op.laplace {
                for (&state, &coefficient) in op.states.iter().zip(&filter.c) {
                    row[n + state] = coefficient;
                }
                if !filter.d.zero() {
                    let OperatorSpec::LaplaceNd { input, .. } = &program.operators[op.operator]
                    else {
                        unreachable!()
                    };
                    let input = affine_for_operator_input(input, program, &op.origin)?;
                    for (node, &coefficient) in
                        input.iter().take(program.nodes.len()).enumerate().skip(1)
                    {
                        let index = self.nodes[node].or(self.sources[node]).unwrap();
                        row[n + index] = row[n + index] + filter.d * coefficient;
                    }
                    for other in 0..n {
                        row[other] = row[other] - filter.d * input[program.nodes.len() + other];
                    }
                    *row.last_mut().unwrap() = filter.d * *input.last().unwrap();
                }
            } else {
                row[n + op.states[0]] = I::ONE;
            }
            rows.push(row);
        }
        solve_output_rows(rows, n, self.width)
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

fn solve_output_rows(rows: Vec<Vec<I>>, n: usize, width: usize) -> Result<Vec<Vec<I>>, Error> {
    affine_bounds::eliminate(rows, n, width)
        .and_then(|rows| back_substitute_eliminated(&rows, n, width))
        .map_err(|mut error| {
            error.message = format!("implicit operator feedthrough: {}", error.message);
            error
        })
}

fn initialize(
    program: &Program,
    trajectory: &Trajectory,
    driven: &[String],
    tolerances: &Tolerances,
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
            OperatorSpec::Idt {
                input,
                ic,
                reset: None,
                ..
            } => {
                validate(input, program, &origin.instance)?;
                if !ic.is_finite() {
                    return Err(unsupported(origin, "nonfinite implicit integral IC"));
                }
                initial.push(I::point(*ic));
                (ContinuousKind::Idt, None)
            }
            OperatorSpec::LaplaceNd {
                input,
                numerator,
                denominator,
                ..
            } => {
                validate(input, program, &origin.instance)?;
                let filter = laplace_system(numerator, denominator, origin)?;
                if !filter.d.zero() && affine_for_operator_input(input, program, origin).is_err() {
                    return Err(unsupported(origin,
                        "implicit polynomial filter input requires a strictly proper transfer function"));
                }
                // Allocate call-site states first; their joint DC values are
                // filled only after certifying the complete initial root.
                initial.extend(vec![I::ZERO; filter.a.len()]);
                (ContinuousKind::LaplaceNd, Some(filter))
            }
            _ => return Err(unsupported(
                origin,
                "implicit polynomial DAE supports explicit-IC unreset integrals and proper filters",
            )),
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
    let _ = circuit(program, driven, &vec![0.0; operators.len()], tolerances)?;
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
        physical,
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
    coordinates.outputs = coordinates.build_outputs(program, &operators)?;
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
    let root = joint_dc(program, driven, trajectory, &operators, &[])?;
    initial = root.physical;
    for &node in &unknown {
        initial.push(root.voltages[node]);
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
                let input = coordinates.expression(input, program, &op.origin.instance)?;
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
        accuracy_rows: coordinates
            .nodes
            .iter()
            .flatten()
            .map(|&state| {
                let mut row = vec![I::ZERO; count + 2 * input_nodes.len() + 1];
                row[state] = I::ONE;
                row
            })
            .collect(),
        tolerances: tolerances.clone(),
        initial,
        steps: Vec::new(),
        start: 0.0,
        event_dependent: false,
        event_seed: None,
    };
    // The common Picard/Taylor engine validates the rational reduced field;
    // F_v inversion is mandatory even when the resulting derivative is zero.
    flow.propagate_until(trajectory.config.stop)?;
    Ok((flow, coordinates))
}

fn observe(
    program: &Program,
    driven: &[String],
    coordinates: &Coordinates,
    state: &[I],
    inputs: &[f64],
    input_bounds: &[I],
    tolerances: &Tolerances,
) -> Result<Solution, Error> {
    let (circuit, point_inputs) =
        coordinates.point_circuit(program, driven, state, inputs, tolerances)?;
    let mut guess = vec![0.0; circuit.nodes.len()];
    for (node, index) in coordinates.nodes.iter().enumerate() {
        if let Some(i) = index {
            guess[node] = point_value(state[*i])?;
        }
    }
    let mut solution = circuit.solve_with_initial(&point_inputs, Some(&guess))?;
    solution.voltages.truncate(program.nodes.len());
    let mut observation_bounds = Vec::new();
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
        observation_bounds.push(exact);
        let budget =
            I::point(tolerances.absolute) + I::point(tolerances.relative) * I::point(actual.abs());
        let error = I::point(actual) - exact;
        if !exact.finite() || !error.finite() || !budget.finite() || error.magnitude() > budget.lo {
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
    // Recheck the original simultaneous relations against full histories and
    // coefficient enclosures, independently of the approximate point solve.
    coordinates.check_original_relations(program, state, input_bounds, &solution, tolerances)?;
    crate::observation::retain_bounds(&mut solution, observation_bounds);
    Ok(solution)
}

pub(crate) fn run(
    program: Program,
    driven: Vec<String>,
    config: TransientInputs,
    tolerances: Tolerances,
) -> Result<Response, Error> {
    let trajectory = Trajectory::new(config, driven.len())?;
    let (flow, coordinates) = initialize(&program, &trajectory, &driven, &tolerances)?;
    let mut solutions = Vec::<Solution>::new();
    for &time in &trajectory.config.output_times {
        let state = flow.state_bounds(I::point(time))?;
        let inputs = trajectory.values(time);
        let solution = observe(
            &program,
            &driven,
            &coordinates,
            &state,
            &inputs,
            &trajectory.value_bounds(time),
            &tolerances,
        )?;
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
    let observation_evidence = crate::observation::evidence(
        &program.nodes,
        &solutions,
        &trajectory.config,
        &tolerances,
        vec!["implicit_history_evaluation"; solutions.len()],
        true,
        (trace.times.first() == Some(&0.0)).then_some(true),
    );
    Ok(Response {
        strobe_evidence: None,
        portability_advisories: None,
        observation_evidence: Some(observation_evidence),
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
    fn observation_must_solve_live_filter_feedthrough_in_original_relation() {
        let origin = json!({"source":"feedthrough.va","line":1,"column":1,"instance":"dut"});
        let mut second_origin = origin.clone();
        second_origin["column"] = json!(2);
        let program: Program = serde_json::from_value(json!({
            "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","y"],
            "operators":[
                {"kind":"idt","ic":0.75,"input":{"op":"affine","constant":0,"terms":[]},"origin":origin},
                {"kind":"laplace_nd","numerator":[1001,1000],"denominator":[1,1],"origin":second_origin,
                    "input":{"op":"affine","constant":-0.5,"terms":[{"node":1,"coefficient":1}]}}],
            "contributions":[{"branch":{"instance":"dut","local_positive":"p","local_negative":"r","kind":"voltage"},
                "positive":1,"negative":0,"origin":origin,
                "rhs":{"op":"add","left":{"op":"add","left":{"op":"operator","operator":0},"right":{"op":"operator","operator":1}},
                    "right":{"op":"multiply","left":{"op":"affine","constant":-1,"terms":[]},
                        "right":{"op":"power","exponent":2,"base":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]}}}}}]
        })).unwrap();
        // Valid history enclosure of the stationary selected root y=1/2.
        // z=3/4, x=0; h=x+1000*(y-1/2), x'=y-1/2-x.
        // Its asymmetric voltage box is permitted; the midpoint is not history.
        let state = [
            I::point(0.75),
            I::ZERO,
            I {
                lo: 0.5 - 0.5e-10,
                hi: 0.5 + 3.5e-10,
            },
        ];
        let coordinates = Coordinates {
            physical: 2,
            nodes: vec![None, Some(2)],
            sources: vec![None, None],
            width: 4,
            outputs: vec![
                vec![I::ONE, I::ZERO, I::ZERO, I::ZERO],
                vec![I::ZERO, I::ONE, I::point(1000.0), I::point(-500.0)],
            ],
        };
        let solution = observe(
            &program,
            &[],
            &coordinates,
            &state,
            &[],
            &[],
            &Tolerances {
                absolute: 1e-7,
                relative: 0.0,
            },
        )
        .unwrap();
        let y = solution.voltages[1];
        let original_residual = y + y * y - 0.75 - 1000.0 * (y - 0.5);
        assert!(
            original_residual.abs() <= 1e-7,
            "original relation residual {original_residual:e}"
        );
        let mut frozen_output_candidate = solution.clone();
        frozen_output_candidate.voltages[1] = 0.5 + 7.5e-8;
        assert_eq!(
            coordinates
                .check_original_relations(
                    &program,
                    &state,
                    &[],
                    &frozen_output_candidate,
                    &Tolerances {
                        absolute: 1e-7,
                        relative: 0.0
                    }
                )
                .err()
                .unwrap()
                .kind,
            "waveform_accuracy"
        );
    }

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
                strobetimes: Vec::new(),
                pwl: vec![vec![[0.0, 0.0], [0.75, 0.75]]],
                output_times: vec![0.0, 0.75],
                stop: 0.75,
                max_step: 0.75,
            },
            1,
        )
        .unwrap();
        let (flow, coordinates) =
            initialize(&program, &trajectory, &["u".into()], &Tolerances::default()).unwrap();
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
                strobetimes: Vec::new(),
                pwl: vec![vec![[0.0, 2.25], [1.0, 2.25]]],
                output_times: vec![0.0, 1.0],
                stop: 1.0,
                max_step: 1.0,
            },
            1,
        )
        .unwrap();
        let (flow, coordinates) =
            initialize(&program, &trajectory, &["u".into()], &Tolerances::default()).unwrap();
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
