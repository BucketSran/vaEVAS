//! A causal continuous subproblem, with original node/operator identities.
//!
//! This first split accepts uniquely defined grounded voltage branches only.
//! The complete circuit is still solved and error-checked at every observation.
//! It does not discard feedback based on a current value, selected arm or zero.
use super::*;

pub(super) fn project(program: &Program, driven: &[String]) -> Result<Option<Program>, Error> {
    if !program
        .operators
        .iter()
        .any(|o| matches!(o, OperatorSpec::Transition { .. }))
        || !program.operators.iter().any(|o| {
            matches!(
                o,
                OperatorSpec::Idt { .. }
                    | OperatorSpec::LaplaceNd { .. }
                    | OperatorSpec::Ddt { .. }
            )
        })
        || program.operators.iter().any(|o| {
            !matches!(
                o,
                OperatorSpec::Idt { .. }
                    | OperatorSpec::LaplaceNd { .. }
                    | OperatorSpec::Ddt { .. }
                    | OperatorSpec::Math { .. }
                    | OperatorSpec::Transition { .. }
            )
        })
    {
        return Ok(None);
    }
    let driven = driven_node_indices(program, driven)?;
    let mut definitions = BTreeMap::<usize, (BranchIdentity, Vec<usize>)>::new();
    for (i, c) in program.contributions.iter().enumerate() {
        let node = match (c.positive, c.negative) {
            (0, n) | (n, 0) if n != 0 && !driven.contains(&n) => n,
            _ => return Ok(None),
        };
        match definitions.get_mut(&node) {
            Some((branch, rows)) if branch == &c.branch => rows.push(i),
            Some(_) => return Ok(None),
            None => {
                definitions.insert(node, (c.branch.clone(), vec![i]));
            }
        }
    }
    let mut pending = Vec::new();
    let mut roots = Vec::new();
    for spec in &program.operators {
        match spec {
            OperatorSpec::Idt {
                input,
                reset,
                origin,
                ..
            } => {
                roots.push((input, &origin.instance));
                if let Some(reset) = reset {
                    roots.push((reset, &origin.instance));
                }
            }
            OperatorSpec::LaplaceNd { input, origin, .. }
            | OperatorSpec::Ddt { input, origin, .. }
            | OperatorSpec::Math { input, origin, .. } => roots.push((input, &origin.instance)),
            _ => {}
        }
    }
    for bound in &program.step_bounds {
        roots.extend([
            (&bound.active, &bound.origin.instance),
            (&bound.value, &bound.origin.instance),
        ]);
    }
    let dependencies = |expr: &Expression, owner: &str| -> Result<Option<BTreeSet<usize>>, Error> {
        let (nodes, _, operators) = integral_dependency_edges(expr, program, owner)?;
        // A transition anywhere in a required equation is a true dependency.
        // The old coupled path decides whether it has a specialized solution.
        if operators
            .iter()
            .any(|&i| matches!(program.operators[i], OperatorSpec::Transition { .. }))
        {
            return Ok(None);
        }
        Ok(Some(nodes))
    };
    for (expr, owner) in roots {
        let Some(nodes) = dependencies(expr, owner)? else {
            return Ok(None);
        };
        pending.extend(nodes);
    }
    let mut seen = BTreeSet::new();
    let mut selected = BTreeSet::new();
    while let Some(node) = pending.pop() {
        if node == 0 || driven.contains(&node) || !seen.insert(node) {
            continue;
        }
        let Some((_, rows)) = definitions.get(&node) else {
            return Ok(None);
        };
        for &i in rows {
            selected.insert(i);
            let c = &program.contributions[i];
            let Some(nodes) = dependencies(&c.rhs, &c.origin.instance)? else {
                return Ok(None);
            };
            pending.extend(nodes);
        }
    }
    let mut projected = program.clone();
    projected.contributions = program
        .contributions
        .iter()
        .enumerate()
        .filter(|(i, _)| selected.contains(i))
        .map(|(_, c)| c.clone())
        .collect();
    Ok(Some(projected))
}
