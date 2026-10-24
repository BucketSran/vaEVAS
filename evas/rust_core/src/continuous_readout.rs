//! A causal continuous subproblem, with original node/operator identities.
//!
//! This first split accepts uniquely defined grounded voltage branches only.
//! The complete circuit is still solved and error-checked at every observation.
//! It does not discard feedback based on a current value, selected arm or zero.
use super::*;

/// Parameter identity for the proved causal graph, before any mode is frozen.
/// All arms and explicit zero references remain dependencies. Transition
/// targets belong to the detached readout, not to this continuous subproblem.
pub(super) fn live_parameters(
    program: &Program,
    work: Option<&crate::transition_source_plan::Work>,
) -> Result<BTreeSet<usize>, Error> {
    let mut roots: Vec<_> = program
        .contributions
        .iter()
        .map(|c| (&c.rhs, c.origin.instance.as_str()))
        .collect();
    for spec in &program.operators {
        match spec {
            OperatorSpec::Idt {
                input,
                reset,
                origin,
                ..
            } => {
                roots.push((input, origin.instance.as_str()));
                if let Some(reset) = reset {
                    roots.push((reset, origin.instance.as_str()));
                }
            }
            OperatorSpec::LaplaceNd { input, origin, .. }
            | OperatorSpec::Ddt { input, origin, .. }
            | OperatorSpec::Math { input, origin, .. } => {
                roots.push((input, origin.instance.as_str()));
            }
            OperatorSpec::Transition { .. } => {}
            _ => {
                return Err(Error::new(
                    "invalid_ir",
                    "causal parameter identity lacks a supported operator",
                ))
            }
        }
    }
    for bound in &program.step_bounds {
        roots.extend([
            (&bound.active, bound.origin.instance.as_str()),
            (&bound.value, bound.origin.instance.as_str()),
        ]);
    }
    let mut states = BTreeSet::new();
    for (expr, owner) in roots {
        let (_, dependencies, _) = source_dependency_edges(expr, program, owner, work)?;
        states.extend(dependencies);
    }
    Ok(states)
}

pub(super) fn project(
    program: &Program,
    driven: &[String],
    work: Option<&crate::transition_source_plan::Work>,
) -> Result<Option<Program>, Error> {
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
        let (nodes, _, operators) = source_dependency_edges(expr, program, owner, work)?;
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
    if let Some(work) = work.filter(|_| !program.procedures.is_empty()) {
        let bytes = crate::event_floor::encoded_size(program, work)?;
        work.debit(2, (bytes as u64).saturating_mul(8))?;
        work.debit(2, (program.contributions.len() * 32 + 64) as u64)?;
    }
    let mut projected = program.clone();
    let mut mapping = vec![None; program.contributions.len()];
    for (next, &old) in selected.iter().enumerate() {
        mapping[old] = Some(next);
    }
    projected.contributions = program
        .contributions
        .iter()
        .enumerate()
        .filter(|(i, _)| selected.contains(i))
        .map(|(_, c)| c.clone())
        .collect();
    // The private physical subsystem keeps original source ordinals and all
    // assignments, but its contribution table has new indices. Capture IDs
    // must follow that projection before a source-position Plan can execute.
    fn project_steps(
        steps: &mut Vec<crate::ir::ProcedureStep>,
        mapping: &[Option<usize>],
        work: Option<&crate::transition_source_plan::Work>,
    ) -> Result<(), Error> {
        use crate::ir::{ProcedureAction as A, ProcedureControl as C};
        let mut removed = 0;
        for step in steps.iter_mut() {
            if let Some(work) = work {
                work.debit(2, 32)?;
            }
            match &mut step.action {
                A::Control(C::ContributionCapture { contribution }) => {
                    let mapped = mapping.get(*contribution).ok_or_else(|| {
                        Error::new("invalid_ir", "projected capture index out of range")
                    })?;
                    if let Some(index) = mapped {
                        *contribution = *index;
                    } else {
                        // No valid public index equals mapping.len().
                        *contribution = mapping.len();
                        removed += 1;
                    }
                }
                A::Control(C::ProcedureIf {
                    then_body,
                    else_body,
                    ..
                }) => {
                    project_steps(then_body, mapping, work)?;
                    project_steps(else_body, mapping, work)?;
                }
                A::Control(C::ProcedureLoop {
                    initialize,
                    body,
                    update,
                    ..
                }) => {
                    for body in [initialize, body, update] {
                        project_steps(body, mapping, work)?;
                    }
                }
                _ => {}
            }
        }
        if removed != 0 {
            steps.retain(|step| !matches!(&step.action,
                A::Control(C::ContributionCapture { contribution }) if *contribution == mapping.len()));
        }
        Ok(())
    }
    for procedure in &mut projected.procedures {
        project_steps(&mut procedure.body, &mapping, work)?;
    }
    Ok(Some(projected))
}

#[cfg(test)]
mod source_frame_tests {
    use super::*;
    use crate::transition_source_plan::Work;
    use serde_json::json;

    fn observation() -> Program {
        serde_json::from_str(include_str!("procedure_observation_request.json")).unwrap()
    }
    fn readout() -> Program {
        serde_json::from_str(include_str!("procedure_readout_request.json")).unwrap()
    }
    #[test]
    fn source_dependencies_keep_all_definitions_and_zero_roots_without_evaluation() {
        let mut value = serde_json::to_value(observation()).unwrap();
        let origin = value["real_bindings"][0]["origin"].clone();
        value["states"] = json!([{"instance":"dut","name":"q","kind":"real","initial":0}]);
        value["operators"] = json!([{"kind":"transition","input":{"op":"state","state":0},"delay":0,"rise":1,"fall":1,"origin":origin}]);
        // This definition is numerically inactive and would divide by zero if
        // a metadata scan accidentally entered the expression evaluator.
        value["procedures"][0]["body"][2]["action"]["value"] = json!({
            "op":"select","relation":"gt","left":{"op":"affine","constant":0,"terms":[]},
            "right":{"op":"affine","constant":1,"terms":[]},"origin":origin,
            "then_value":{"op":"real_binary","operation":"divide","origin":origin,
                "left":{"op":"operator","operator":0},"right":{"op":"affine","constant":0,"terms":[]}},
            "else_value":{"op":"multiply","left":{"op":"state","state":0},
                "right":{"op":"affine","constant":0,"terms":[{"node":2,"coefficient":0}]}}});
        let p: Program = serde_json::from_value(value).unwrap();
        let expr = Expression::RealLocal { binding: 0 };
        let work = Work::default();
        let (nodes, states, ops) = source_dependency_edges(&expr, &p, "dut", Some(&work)).unwrap();
        assert_eq!(nodes, [0, 1, 2].into_iter().collect());
        assert_eq!(states, [0].into_iter().collect());
        assert_eq!(ops, [0].into_iter().collect());
        assert!(work.spent() > 0);
        assert_eq!(
            source_dependency_edges(&expr, &p, "dut", None)
                .unwrap_err()
                .kind,
            "invalid_ir"
        );
        let limited = Work::limited([128, 8192, work.spent() - 1]);
        let retry = limited.clone();
        for _ in 0..2 {
            let before = limited.spent();
            assert_eq!(
                source_dependency_edges(&expr, &p, "dut", Some(&retry))
                    .unwrap_err()
                    .kind,
                "step_budget"
            );
            assert!(limited.spent() > before);
        }
        source_dependency_edges(&expr, &p, "dut", Some(&Work::default())).unwrap();
    }
    #[test]
    fn private_readout_reindexes_nested_captures_and_preserves_original_on_failure() {
        let mut value = serde_json::to_value(readout()).unwrap();
        let mut body = value["procedures"][0]["body"].take();
        // Cover both nested arms and the loop's initialization/body/update
        // containers without executing an artificial loop or changing roots.
        let origin = value["contributions"][0]["origin"].clone();
        let one = json!({"op":"affine","constant":1,"terms":[]});
        let zero = json!({"op":"affine","constant":0,"terms":[]});
        let a = body.as_array_mut().unwrap();
        let bound = a.pop().unwrap();
        let integral = a.pop().unwrap();
        let timed = a.pop().unwrap();
        assert!(a.is_empty());
        value["procedures"][0]["body"] = json!([{
            "expanded_statement_ordinal":0,"action":{"kind":"procedure_if","relation":"gt","left":one,"right":zero,"origin":origin,
            "then_body":[{"expanded_statement_ordinal":1,"action":{"kind":"procedure_loop","relation":"gt","left":zero,"right":one,"origin":origin,
            "initialize":[timed],"body":[integral],"update":[bound]}}],"else_body":[]}}]);
        // Assign distinct source ordinals in syntax order, as public admission
        // requires, and retain them exactly through the private projection.
        fn ordinals(v: &mut serde_json::Value, next: &mut u64) {
            if let Some(m) = v.as_object_mut() {
                if m.contains_key("expanded_statement_ordinal") {
                    m.insert("expanded_statement_ordinal".into(), json!(*next));
                    *next += 1;
                }
                for key in [
                    "action",
                    "initialize",
                    "body",
                    "update",
                    "then_body",
                    "else_body",
                ] {
                    if let Some(x) = m.get_mut(key) {
                        ordinals(x, next);
                    }
                }
            } else if let Some(a) = v.as_array_mut() {
                for x in a {
                    ordinals(x, next);
                }
            }
        }
        ordinals(&mut value["procedures"][0]["body"], &mut 0);
        let p: Program = serde_json::from_value(value).unwrap();
        let before = serde_json::to_value(&p).unwrap();
        crate::procedure::validate(&p, &Work::default()).unwrap();
        let work = Work::default();
        let projected = project(&p, &["u".into()], Some(&work)).unwrap().unwrap();
        assert_eq!(projected.contributions.len(), 1);
        assert_eq!(
            serde_json::to_value(&projected.contributions[0]).unwrap(),
            serde_json::to_value(&p.contributions[1]).unwrap()
        );
        crate::procedure::validate(&projected, &Work::default()).unwrap();
        let after = serde_json::to_value(&projected).unwrap();
        let loop_action = &after["procedures"][0]["body"][0]["action"]["then_body"][0]["action"];
        assert_eq!(loop_action["initialize"], json!([]));
        assert_eq!(loop_action["body"][0]["action"]["contribution"], json!(0));
        assert_eq!(
            loop_action["body"][0]["expanded_statement_ordinal"],
            json!(3)
        );
        assert_eq!(
            loop_action["update"][0]["action"]["kind"],
            json!("step_bound_capture")
        );
        assert_eq!(serde_json::to_value(&p).unwrap(), before);
        let limited = Work::limited([128, 8192, work.spent() - 1]);
        for _ in 0..2 {
            assert_eq!(
                project(&p, &["u".into()], Some(&limited)).unwrap_err().kind,
                "step_budget"
            );
            assert_eq!(serde_json::to_value(&p).unwrap(), before);
        }
        project(&p, &["u".into()], Some(&Work::default())).unwrap();
    }
    #[test]
    fn source_dependencies_include_guard_only_roots_of_constant_assignments() {
        let mut value = serde_json::to_value(observation()).unwrap();
        let origin = value["real_bindings"][0]["origin"].clone();
        let zero = json!({"op":"affine","constant":0,"terms":[]});
        let one = json!({"op":"affine","constant":1,"terms":[]});
        value["states"] = json!([{"instance":"dut","name":"mode","kind":"real","initial":0}]);
        value["operators"] =
            json!([{"kind":"transition","input":zero,"delay":0,"rise":1,"fall":1,"origin":origin}]);
        value["procedures"][0]["body"] = json!([{
            "expanded_statement_ordinal":0,"action":{"kind":"procedure_if","relation":"gt",
            "left":{"op":"state","state":0},"right":{"op":"operator","operator":0},"origin":origin,
            "then_body":[{"expanded_statement_ordinal":1,"action":{"kind":"procedure_loop","relation":"gt",
                "initialize":[],"left":{"op":"affine","constant":0,"terms":[{"node":2,"coefficient":0}]},
                "right":zero,"origin":origin,"body":[{"expanded_statement_ordinal":2,
                    "action":{"kind":"real_bind","binding":0,"value":one,"origin":origin}}],"update":[]}}],
            "else_body":[]}}]);
        let p: Program = serde_json::from_value(value).unwrap();
        let expr = Expression::RealLocal { binding: 0 };
        let work = Work::default();
        let (nodes, states, ops) = source_dependency_edges(&expr, &p, "dut", Some(&work)).unwrap();
        assert_eq!(nodes, [2].into_iter().collect());
        assert_eq!(states, [0].into_iter().collect());
        assert_eq!(ops, [0].into_iter().collect());
        let sources = crate::procedure::dependency_sources(&p, &work).unwrap();
        assert!(sources.single_binding_value(0).unwrap().is_none());
        let limited = Work::limited([128, 8192, work.spent() / 2]);
        for _ in 0..2 {
            assert_eq!(
                source_dependency_edges(&expr, &p, "dut", Some(&limited))
                    .unwrap_err()
                    .kind,
                "step_budget"
            );
        }
        source_dependency_edges(&expr, &p, "dut", Some(&Work::default())).unwrap();
    }
}
