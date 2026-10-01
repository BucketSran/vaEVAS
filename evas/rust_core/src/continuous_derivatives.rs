//! Reduce affine input derivatives to a certified algebraic mass relation.
//!
//! First expose derivative outputs as independent parameters d. The remaining
//! voltage/filter network gives x=Pz+Qu+Rd+c, z'=Az+Bu+Ed+b. If a derivative
//! input is r=Lz+Mu+c (no direct d or PWL-slope dependence), then
//! d=Lz'+Mu' and (I-LE)d=LAz+LBu+Mu'+Lb. An invertible mass relation preserves
//! the existing state variables; higher-index derivative chains are rejected.
use super::*;

pub(super) fn transient_rows(
    program: &Program,
    operators: &[NetworkOperator],
    system: &AlgebraicSystem,
) -> Result<Vec<Vec<I>>, Error> {
    let differentiated: Vec<_> = operators
        .iter()
        .enumerate()
        .filter(|(_, op)| op.kind == ContinuousKind::Ddt)
        .collect();
    if differentiated.is_empty() {
        return Ok(system.rows.clone());
    }
    let count = differentiated.len();
    let base = system.rows.len() - operators.len();
    let removed: BTreeSet<_> = differentiated.iter().map(|(i, _)| base + i).collect();
    let common: Vec<_> = system
        .rows
        .iter()
        .enumerate()
        .filter(|(i, _)| !removed.contains(i))
        .map(|(_, row)| row.clone())
        .collect();
    let mut auxiliary = system.clone();
    auxiliary.state_count += count;
    auxiliary.width += count;
    auxiliary.rows = common
        .iter()
        .map(|row| {
            let mut row = row.clone();
            row.splice(
                system.x_count + system.state_count..system.x_count + system.state_count,
                vec![I::ZERO; count],
            );
            row
        })
        .collect();
    for (j, (_, op)) in differentiated.iter().enumerate() {
        let mut row = vec![I::ZERO; system.x_count + auxiliary.width];
        row[system.operator_columns[op.operator].unwrap()] = I::ONE;
        row[system.x_count + system.state_count + j] = I::ONE;
        auxiliary.rows.push(row);
    }
    let reduced =
        affine_bounds::eliminate(auxiliary.rows.clone(), auxiliary.x_count, auxiliary.width)?;
    let mapping = back_substitute_eliminated(&reduced, auxiliary.x_count, auxiliary.width)?;
    let state_derivatives = build_state_derivatives(program, operators, &auxiliary, &mapping)?;
    let source_count = system.source_columns.iter().filter(|c| c.is_some()).count();
    let mut rows = common;
    for (_, op) in &differentiated {
        let OperatorSpec::Ddt {
            input: original, ..
        } = &program.operators[op.operator]
        else {
            unreachable!()
        };
        validate_continuous_input(
            original,
            program,
            &op.origin,
            &system.source_columns,
            &mut BTreeSet::new(),
        )?;
        let input = expand_input(op.input.as_ref().unwrap(), program, &auxiliary, &mapping)?;
        if input[system.state_count..auxiliary.state_count]
            .iter()
            .any(|c| !c.zero())
            || input[auxiliary.state_count + source_count..auxiliary.state_count + 2 * source_count]
                .iter()
                .any(|c| !c.zero())
        {
            return Err(unsupported(&op.origin,
                "ddt input has a direct derivative/slope dependency; higher-index DAE or impulse semantics required"));
        }
        let mut derivative = vec![I::ZERO; auxiliary.width];
        for (state, coefficient) in input.iter().copied().take(system.state_count).enumerate() {
            for (target, value) in derivative.iter_mut().zip(&state_derivatives[state]) {
                *target = *target + coefficient * *value;
            }
        }
        for source in 0..source_count {
            let slope = auxiliary.state_count + source_count + source;
            derivative[slope] = derivative[slope] + input[auxiliary.state_count + source];
        }
        let mut row = vec![I::ZERO; system.x_count + system.width];
        row[system.operator_columns[op.operator].unwrap()] = I::ONE;
        for (j, (_, other)) in differentiated.iter().enumerate() {
            let column = system.operator_columns[other.operator].unwrap();
            row[column] = row[column] - derivative[system.state_count + j];
        }
        row[system.x_count..system.x_count + system.state_count]
            .copy_from_slice(&derivative[..system.state_count]);
        row[system.x_count + system.state_count..]
            .copy_from_slice(&derivative[auxiliary.state_count..]);
        rows.push(row);
    }
    Ok(rows)
}

fn validate_continuous_input(
    expr: &Expression,
    program: &Program,
    origin: &Origin,
    sources: &[Option<usize>],
    seen: &mut BTreeSet<usize>,
) -> Result<(), Error> {
    let dependencies = structural_affine(expr, program, origin)?;
    let reject = || {
        unsupported(origin, "ddt input can jump through event state, reset or derivative feedthrough; impulse semantics required")
    };
    if !dependencies.state_dependencies.is_empty() {
        return Err(reject());
    }
    for node in dependencies.node_dependencies {
        if node == 0 || sources[node].is_some() || !seen.insert(node) {
            continue;
        }
        for c in &program.contributions {
            if c.positive == node || c.negative == node {
                validate_continuous_input(&c.rhs, program, &c.origin, sources, seen)?;
            }
        }
    }
    for operator in dependencies.operator_dependencies {
        match &program.operators[operator] {
            OperatorSpec::Idt { reset: None, .. } => {}
            OperatorSpec::LaplaceNd {
                input,
                numerator,
                denominator,
                origin,
            } => {
                if numerator.len() == denominator.len() && *numerator.last().unwrap() != 0.0 {
                    validate_continuous_input(input, program, origin, sources, seen)?;
                }
            }
            _ => return Err(reject()),
        }
    }
    Ok(())
}
