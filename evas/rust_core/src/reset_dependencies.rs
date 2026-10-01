//! Conservative structural check for event-state / idt-reset feedback.
//! Fixed drives and ground are excluded by the existing voltage groups.
use crate::assembly::AssembledCircuit;
use crate::events::{affine, AffineState};
use crate::ir::{Error, OperatorSpec, Program};

pub(crate) fn check(
    program: &Program,
    rhs: &[AffineState],
    actions: &[Vec<(usize, AffineState)>],
    groups: &[Vec<usize>],
    assembled: &AssembledCircuit,
) -> Result<(), Error> {
    if !program
        .operators
        .iter()
        .any(|op| matches!(op, OperatorSpec::Idt { reset: Some(_), .. }))
    {
        return Ok(());
    }
    let states = program.nodes.len();
    let operators = states + program.states.len();
    let mut edges = vec![Vec::new(); operators + program.operators.len()];
    // Electrical equation connectivity is deliberately conservative. Use all
    // contributions to a branch; numerical cancellation cannot erase an edge.
    for (group, equation) in groups.iter().zip(&assembled.equations) {
        for &node in group {
            edges[node].extend(group.iter().copied().filter(|&other| other != node));
        }
        for (contribution, expression) in program.contributions.iter().zip(rhs) {
            if contribution.branch != equation.branch {
                continue;
            }
            for &state in &expression.state_dependencies {
                edges[states + state].extend(group);
            }
            for &operator in &expression.operator_dependencies {
                edges[operators + operator].extend(group);
            }
        }
    }
    for body in actions {
        for (target, expression) in body {
            for &node in &expression.node_dependencies {
                edges[node].push(states + target);
            }
            for &state in &expression.state_dependencies {
                edges[states + state].push(states + target);
            }
        }
    }
    let mut resets = Vec::new();
    for (index, spec) in program.operators.iter().enumerate() {
        let input = match spec {
            OperatorSpec::Ddt { input, .. }
            | OperatorSpec::Idt { input, .. }
            | OperatorSpec::Transition { input, .. }
            | OperatorSpec::AbsDelay { input, .. }
            | OperatorSpec::Slew { input, .. }
            | OperatorSpec::LaplaceNd { input, .. }
            | OperatorSpec::IdtMod { input, .. }
            | OperatorSpec::Sin { input, .. } => input,
        };
        let mut expressions = vec![input];
        if let OperatorSpec::Idt {
            reset: Some(reset), ..
        } = spec
        {
            expressions.push(reset);
            let expression = affine(reset, program, &spec.origin().instance)?;
            resets.push((
                operators + index,
                expression.state_dependencies,
                spec.origin(),
            ));
        }
        for expr in expressions {
            let (nodes, state_dependencies, operator_dependencies) =
                crate::continuous::integral_dependency_edges(
                    expr,
                    program,
                    &spec.origin().instance,
                )?;
            for node in nodes {
                edges[node].push(operators + index);
            }
            for state in state_dependencies {
                edges[states + state].push(operators + index);
            }
            for operator in operator_dependencies {
                edges[operators + operator].push(operators + index);
            }
        }
    }
    for (reset, predicates, origin) in resets {
        let mut seen = vec![false; edges.len()];
        let mut pending = edges[reset].clone();
        while let Some(next) = pending.pop() {
            // A continuous voltage/integral feedback loop is legitimate. A
            // reset loop exists only if its output can affect a discrete state
            // actually used by the reset predicate; that needs a separate
            // same-event reset fixed-point contract.
            if next >= states && next < operators && predicates.contains(&(next - states)) {
                return Err(Error::new(
                    "unsupported_operator",
                    format!(
                        "idt reset feedback through event state or voltage network at {}",
                        origin.label()
                    ),
                ));
            }
            if !seen[next] {
                seen[next] = true;
                pending.extend(&edges[next]);
            }
        }
    }
    Ok(())
}
