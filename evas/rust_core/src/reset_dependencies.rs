//! Conservative structural checks for event/reset feedback. Value and first
//! derivative dependencies are distinct: differentiation can expose a flow
//! input without making the underlying physical state discontinuous.
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
    let direct_filters: Vec<_> = program
        .operators
        .iter()
        .enumerate()
        .filter_map(|(i, op)| match op {
            OperatorSpec::LaplaceNd {
                numerator,
                denominator,
                ..
            } if numerator.len() == denominator.len()
                && numerator.last().is_some_and(|&v| v != 0.0) =>
            {
                Some(i)
            }
            _ => None,
        })
        .collect();
    if direct_filters.is_empty()
        && !program
            .operators
            .iter()
            .any(|op| matches!(op, OperatorSpec::Ddt { .. }))
        && !program
            .operators
            .iter()
            .any(|op| matches!(op, OperatorSpec::Idt { reset: Some(_), .. }))
    {
        return Ok(());
    }
    let states = program.nodes.len();
    let operators = states + program.states.len();
    let mut edges = vec![Vec::new(); operators + program.operators.len()];
    // A second graph layer represents first derivatives. Event assignments
    // connect only values; they are not time-differential equations.
    let width = edges.len();
    let mut instantaneous = vec![Vec::new(); 2 * width];
    // Electrical equation connectivity is deliberately conservative. Use all
    // contributions to a branch; numerical cancellation cannot erase an edge.
    for (group, equation) in groups.iter().zip(&assembled.equations) {
        for &node in group {
            edges[node].extend(group.iter().copied().filter(|&other| other != node));
            instantaneous[width + node].extend(
                group
                    .iter()
                    .copied()
                    .filter(|&other| other != node)
                    .map(|other| width + other),
            );
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
                instantaneous[width + operators + operator]
                    .extend(group.iter().map(|node| width + node));
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
    instantaneous[..width].clone_from_slice(&edges);
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
        for (expression_index, expr) in expressions.into_iter().enumerate() {
            let (nodes, state_dependencies, operator_dependencies) =
                crate::continuous::integral_dependency_edges(
                    expr,
                    program,
                    &spec.origin().instance,
                )?;
            let dependencies: Vec<_> = nodes
                .into_iter()
                .chain(state_dependencies.into_iter().map(|state| states + state))
                .chain(
                    operator_dependencies
                        .into_iter()
                        .map(|operator| operators + operator),
                )
                .collect();
            let output = operators + index;
            for &source in &dependencies {
                edges[source].push(output);
            }
            // Each pair is (differentiate input, differentiate output).
            // z'=u: input value reaches the integral's derivative, not z.
            // y=Cx+Du: y'=CAx+CBu+Du'. Only relative degree <=1
            // can expose u in y'; a second-order low-pass retains a state.
            let connections: Vec<(bool, bool)> = if expression_index > 0 {
                vec![(false, false), (false, true)]
            } else {
                match spec {
                    OperatorSpec::Idt { .. } => vec![(false, true)],
                    OperatorSpec::Ddt { .. } => vec![(true, false)],
                    OperatorSpec::LaplaceNd {
                        numerator,
                        denominator,
                        ..
                    } => {
                        let direct = direct_filters.contains(&index);
                        let relative_one = denominator
                            .len()
                            .checked_sub(2)
                            .and_then(|i| numerator.get(i))
                            .is_some_and(|&v| v != 0.0);
                        let mut paths = Vec::new();
                        if direct {
                            paths.extend([(false, false), (true, true)]);
                        }
                        if direct || relative_one {
                            paths.push((false, true));
                        }
                        paths
                    }
                    OperatorSpec::Sin { .. } => vec![(false, false), (false, true), (true, true)],
                    _ => Vec::new(),
                }
            };
            for (input_derivative, output_derivative) in connections {
                for &source in &dependencies {
                    instantaneous[source + usize::from(input_derivative) * width]
                        .push(output + usize::from(output_derivative) * width);
                }
            }
        }
    }
    // A stationary iterate is not a uniqueness certificate for an event
    // loop through a direct filter or derivative-exposed input. Reject this
    // structural slice; do not attempt to solve it by repeated observations.
    for index in direct_filters.into_iter().chain(
        program
            .operators
            .iter()
            .enumerate()
            .filter_map(|(i, op)| matches!(op, OperatorSpec::Ddt { .. }).then_some(i)),
    ) {
        let root = operators + index;
        let mut seen = vec![[false; 2]; instantaneous.len()];
        let mut pending: Vec<_> = instantaneous[root].iter().map(|&n| (n, false)).collect();
        while let Some((node, crossed_state)) = pending.pop() {
            let crossed_state = crossed_state || (states..operators).contains(&node);
            if node == root && crossed_state {
                return Err(Error::new(
                    "unsupported_operator",
                    format!(
                        "instantaneous event feedback through direct or derivative feedthrough at {}",
                        program.operators[index].origin().label()
                    ),
                ));
            }
            let flag = usize::from(crossed_state);
            if !seen[node][flag] {
                seen[node][flag] = true;
                pending.extend(instantaneous[node].iter().map(|&n| (n, crossed_state)));
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
