//! Certified cold initialization shared by polynomial ODEs and index-one DAEs.
//! Event restarts bypass this module and retain accepted physical history.
use super::*;
use crate::ir::Tolerances;
use crate::solver::Circuit;

pub(super) struct InitialState {
    pub(super) physical: Vec<I>,
    pub(super) voltages: Vec<I>,
}

pub(super) fn solve(matrix: &[Vec<I>], rhs: &[I]) -> Option<Vec<I>> {
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

pub(super) fn bind(
    expr: &Expression,
    values: &[Expression],
    states: &[Expression],
) -> Result<Expression, Error> {
    Ok(match expr {
        Expression::Operator { operator } => values
            .get(*operator)
            .ok_or_else(|| Error::new("invalid_ir", "operator index out of range"))?
            .clone(),
        Expression::Add { left, right } => Expression::Add {
            left: Box::new(bind(left, values, states)?),
            right: Box::new(bind(right, values, states)?),
        },
        Expression::Multiply { left, right } => Expression::Multiply {
            left: Box::new(bind(left, values, states)?),
            right: Box::new(bind(right, values, states)?),
        },
        Expression::Power { base, exponent } => Expression::Power {
            base: Box::new(bind(base, values, states)?),
            exponent: *exponent,
        },
        Expression::State { state } => states
            .get(*state)
            .ok_or_else(|| Error::new("invalid_ir", "initialization state index out of range"))?
            .clone(),
        Expression::Affine { .. } => expr.clone(),
        _ => {
            return Err(Error::new(
                "unsupported_implicit_dynamics",
                "continuous initialization cannot contain conditional expressions",
            ))
        }
    })
}

// Cold initialization is one polynomial system: original voltage relations,
// explicit integral ICs and d0*h=n0*input for each filter. Keep the original
// coefficients in that equation instead of rounding their DC gain n0/d0.
// The shared root certificate covers internal-node and operator feedback too.
pub(super) fn joint_dc(
    program: &Program,
    driven: &[String],
    trajectory: &Trajectory,
    operators: &[NetworkOperator],
    parameters: &[I],
) -> Result<InitialState, Error> {
    if parameters.len() != program.states.len() {
        return Err(Error::new(
            "invalid_ir",
            "continuous initialization parameter count mismatch",
        ));
    }
    let tolerances = Tolerances {
        absolute: 1e-15,
        relative: 1e-14,
    };
    let mut names = driven.to_vec();
    let mut inputs = trajectory.values(0.0);
    let mut input_bounds = trajectory.value_bounds(0.0);
    let mut frozen = program.clone();
    let mut values = Vec::new();
    let mut instance = "$implicit-dc".to_string();
    while program
        .contributions
        .iter()
        .any(|c| c.origin.instance == instance)
    {
        instance.push('$');
    }
    let mut states = Vec::new();
    for (i, &value) in parameters.iter().enumerate() {
        let mut name = format!("$continuous-state:{i}");
        while frozen.nodes.contains(&name) {
            name.push('$');
        }
        let node = frozen.nodes.len();
        names.push(name.clone());
        frozen.nodes.push(name);
        states.push(Expression::Affine {
            constant: 0.0,
            terms: vec![crate::ir::Term {
                node,
                coefficient: 1.0,
            }],
        });
        inputs.push(point_value(value)?);
        input_bounds.push(value);
    }
    let first_operator = frozen.nodes.len();
    for i in 0..program.operators.len() {
        let mut name = format!("$implicit-history:{i}");
        while frozen.nodes.contains(&name) {
            name.push('$');
        }
        let node = frozen.nodes.len();
        frozen.nodes.push(name);
        values.push(Expression::Affine {
            constant: 0.0,
            terms: vec![crate::ir::Term {
                node,
                coefficient: 1.0,
            }],
        });
    }
    for c in &mut frozen.contributions {
        c.rhs = bind(&c.rhs, &values, &states)?;
    }
    let constant = |value| Expression::Affine {
        constant: value,
        terms: vec![],
    };
    let multiply = |coefficient, value| Expression::Multiply {
        left: Box::new(constant(coefficient)),
        right: Box::new(value),
    };
    let mut filter_inputs = Vec::new();
    for (i, op) in program.operators.iter().enumerate() {
        let node = first_operator + i;
        let rhs = match op {
            OperatorSpec::Idt { ic, .. } => constant(*ic),
            OperatorSpec::LaplaceNd {
                input,
                numerator,
                denominator,
                ..
            } => {
                let input = bind(input, &values, &states)?;
                filter_inputs.push(input.clone());
                // h=h+n0*input-d0*h represents the exact DC equation,
                // including nonlinear inputs and proper feedthrough.
                Expression::Add {
                    left: Box::new(values[i].clone()),
                    right: Box::new(Expression::Add {
                        left: Box::new(multiply(numerator[0], input)),
                        right: Box::new(multiply(-denominator[0], values[i].clone())),
                    }),
                }
            }
            _ => unreachable!(),
        };
        let mut origin = op.origin().clone();
        origin.instance.clone_from(&instance);
        frozen.contributions.push(crate::ir::Contribution {
            branch: BranchIdentity {
                instance: instance.clone(),
                local_positive: frozen.nodes[node].clone(),
                local_negative: "0".into(),
                kind: crate::ir::ContributionKind::Voltage,
            },
            positive: node,
            negative: 0,
            rhs,
            origin,
        });
    }
    frozen.operators.clear();
    frozen.states.clear();
    frozen.events.clear();
    let system = Circuit::new(frozen, &names, tolerances.clone())?;
    let solution = system
        .solve(&inputs)
        .and_then(|solution| {
            system.check_waveform_accuracy(&solution, &input_bounds)?;
            Ok(solution)
        })
        .map_err(|mut error| {
            error.message = format!("continuous DC initialization: {}", error.message);
            error
        })?;
    let mut bounds: Vec<_> = solution
        .voltages
        .iter()
        .map(|&value| {
            let radius = (I::point(tolerances.absolute)
                + I::point(tolerances.relative) * I::point(value.abs()))
            .hi;
            I {
                lo: (value - radius).next_down(),
                hi: (value + radius).next_up(),
            }
        })
        .collect();
    bounds[0] = I::ZERO;
    for (name, &value) in names.iter().zip(&input_bounds) {
        bounds[system.nodes.iter().position(|n| n == name).unwrap()] = value;
    }
    // Integral ICs are exact model inputs, not rounded roots. Filter inputs
    // retain the entire joint root box when constructing physical DC states.
    for (i, op) in program.operators.iter().enumerate() {
        if let OperatorSpec::Idt { ic, .. } = op {
            bounds[first_operator + i] = I::point(*ic);
        }
    }
    let filter_inputs: Vec<I> = filter_inputs
        .iter()
        .map(|expr| crate::solver::interval_expression(expr, &bounds))
        .collect::<Result<_, _>>()?;
    let physical_count = operators
        .iter()
        .flat_map(|op| &op.states)
        .max()
        .map_or(0, |last| last + 1);
    let mut physical = vec![I::ZERO; physical_count];
    let mut dc_inputs = filter_inputs.into_iter();
    for op in operators {
        if let Some(filter) = &op.laplace {
            let input = dc_inputs.next().unwrap();
            let rhs: Vec<_> = filter.b.iter().map(|&b| -b * input).collect();
            let dc = solve(&filter.a, &rhs)
                .ok_or_else(|| unsupported(&op.origin, "cannot enclose joint filter DC state"))?;
            for (&index, value) in op.states.iter().zip(dc) {
                physical[index] = value;
            }
        } else {
            let OperatorSpec::Idt { ic, .. } = &program.operators[op.operator] else {
                unreachable!()
            };
            physical[op.states[0]] = I::point(*ic);
        }
    }
    Ok(InitialState {
        physical,
        voltages: bounds[..program.nodes.len()].to_vec(),
    })
}
