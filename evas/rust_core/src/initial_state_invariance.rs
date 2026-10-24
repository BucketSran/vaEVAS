//! A sufficient all-arm proof that selected held states are unchanged.
//! This chooses the existing initialization path; it never skips event execution
//! or its writer, integer, condition and enclosure checks.
use super::{affine, substitute, I};
use crate::ir::{Expression, Program, Statement};
use std::collections::BTreeSet;

type Row = Option<Vec<I>>;

struct Budget(usize, Option<crate::transition_source_plan::Work>);
impl Budget {
    fn take(&mut self, n: usize) -> Option<()> {
        if let Some(work) = &self.1 {
            work.debit(2, n as u64).ok()?;
        }
        match self.0.checked_sub(n) {
            Some(left) => {
                self.0 = left;
                Some(())
            }
            None => {
                self.0 = 0;
                None
            }
        }
    }
}

fn expression_size(e: &Expression) -> usize {
    // The existing IR validator bounds expression depth. Serialization is not
    // needed here: conservatively account for a row operation at every node.
    match e {
        Expression::Add { left, right } | Expression::Multiply { left, right } => {
            1 + expression_size(left) + expression_size(right)
        }
        // affine rejects all other compound expression families.
        _ => 1,
    }
}

fn transfer(e: &Expression, p: &Program, local: &[Row], budget: &mut Budget) -> Option<Row> {
    let width = p.nodes.len() + p.states.len() + p.operators.len() + 1;
    budget.take(width.checked_mul(expression_size(e))?)?;
    let Ok(row) = affine(e, p) else {
        return Some(None);
    };
    let nodes = p.nodes.len();
    if local
        .iter()
        .enumerate()
        .any(|(k, r)| !row[nodes + k].zero() && r.is_none())
    {
        return Some(None);
    }
    budget.take(width.checked_mul(local.len().max(1))?)?;
    // Unknown rows are substituted only with an exact zero coefficient.
    let known: Vec<_> = local
        .iter()
        .map(|r| r.clone().unwrap_or_else(|| vec![I::ZERO; width]))
        .collect();
    Some(Some(substitute(&row, &known, nodes)))
}

fn body(
    statements: &[Statement],
    p: &Program,
    local: &mut [Row],
    budget: &mut Budget,
) -> Option<()> {
    let width = p.nodes.len() + p.states.len() + p.operators.len() + 1;
    for s in statements {
        budget.take(1)?;
        match s {
            Statement::ArrayWrite { .. } | Statement::Loop { .. } => return None,
            Statement::Assign(a) => local[a.state] = transfer(&a.rhs, p, local, budget)?,
            // This proof concerns state transfer only. Runtime still validates
            // and captures displays through the ordinary/candidate event path.
            Statement::Display { .. } => {}
            Statement::If {
                then_body,
                else_body,
                ..
            } => {
                // No guessed branch and no internal voltage observation.
                budget.take(3usize.checked_mul(width)?.checked_mul(local.len())?)?;
                let mut yes = local.to_vec();
                let mut no = local.to_vec();
                body(then_body, p, &mut yes, budget)?;
                body(else_body, p, &mut no, budget)?;
                for ((out, a), b) in local.iter_mut().zip(yes).zip(no) {
                    *out = if a == b { a } else { None };
                }
            }
        }
    }
    Some(())
}

/// All blocks in a batch see the same old state, as in state_updates.
/// Multiple potential writers are conservatively unknown, even if both rows
/// look equal. The ordinary event path still decides whether they may execute.
fn batch(p: &Program, blocks: &[usize], before: &[Row], budget: &mut Budget) -> Option<Vec<Row>> {
    let width = p.nodes.len() + p.states.len() + p.operators.len() + 1;
    budget.take(width.checked_mul(before.len())?)?;
    let mut after = before.to_vec();
    let mut written = BTreeSet::new();
    for &block in blocks.iter().collect::<BTreeSet<_>>() {
        budget.take(width.checked_mul(before.len())?)?;
        let mut local = before.to_vec();
        body(&p.events[block].body, p, &mut local, budget)?;
        let writers: BTreeSet<_> = p.events[block]
            .assignments()
            .iter()
            .map(|a| a.state)
            .collect();
        for s in writers {
            after[s] = if written.insert(s) {
                local[s].clone()
            } else {
                None
            };
        }
    }
    Some(after)
}

#[cfg(test)]
fn unchanged(p: &Program, stages: &[Vec<usize>], required: &BTreeSet<usize>) -> bool {
    prove(p, stages, required, false, &mut Budget(2_000_000, None)).unwrap_or(false)
        || prove(p, stages, required, true, &mut Budget(2_000_000, None)).unwrap_or(false)
}

fn prove(
    p: &Program,
    stages: &[Vec<usize>],
    required: &BTreeSet<usize>,
    concrete: bool,
    budget: &mut Budget,
) -> Option<bool> {
    let width = p
        .nodes
        .len()
        .checked_add(p.states.len())?
        .checked_add(p.operators.len())?
        .checked_add(1)?;
    budget.take(width.checked_mul(p.states.len())?)?;
    let initial_values = p
        .states
        .iter()
        .map(|s| s.initial.constant())
        .collect::<Result<Vec<_>, _>>()
        .ok()?;
    let initial: Vec<Row> = (0..p.states.len())
        .map(|s| {
            let mut row = vec![I::ZERO; width];
            if concrete {
                row[width - 1] = I::point(initial_values[s]);
            } else {
                row[p.nodes.len() + s] = I::ONE;
            }
            Some(row)
        })
        .collect();
    let mut after = initial.clone();
    for stage in stages {
        after = batch(p, stage, &after, budget)?;
    }
    Some(
        required
            .iter()
            .all(|&s| after[s].as_ref() == initial[s].as_ref()),
    )
}

/// Preserve both legacy attempts and their individual caps. Input-aware replay
/// may spend only the unused balance of the second attempt, never a third cap.
pub(crate) fn unchanged_with_inputs(
    model: &crate::events::EventModel,
    stages: &[Vec<usize>],
    required: &BTreeSet<usize>,
    trajectory: &crate::pwl::Trajectory,
) -> bool {
    unchanged_with_inputs_using(model, stages, required, trajectory, None)
}

/// The same bounded proof, charged before every existing row/copy operation.
/// A failed request reservation stays exhausted across both attempts and retries.
pub(crate) fn unchanged_with_inputs_charged(
    model: &crate::events::EventModel,
    stages: &[Vec<usize>],
    required: &BTreeSet<usize>,
    trajectory: &crate::pwl::Trajectory,
    work: &crate::transition_source_plan::Work,
) -> Result<bool, crate::ir::Error> {
    work.debit(2, 0)?;
    let result = unchanged_with_inputs_using(model, stages, required, trajectory, Some(work));
    work.debit(2, 0)?;
    Ok(result)
}

fn unchanged_with_inputs_using(
    model: &crate::events::EventModel,
    stages: &[Vec<usize>],
    required: &BTreeSet<usize>,
    trajectory: &crate::pwl::Trajectory,
    work: Option<&crate::transition_source_plan::Work>,
) -> bool {
    let p = &model.program;
    let Some(mut budget) = legacy_remaining_using(p, stages, required, 2_000_000, work) else {
        return true;
    };
    let mut prove = || -> Option<bool> {
        // The preparer supplies initial blocks followed by zero-timer blocks.
        // Shared OR bodies cannot be replayed as two independently executed stages.
        let [initial, zero] = stages else {
            return None;
        };
        budget.take(initial.len().checked_mul(zero.len())?)?;
        if initial.iter().any(|block| zero.contains(block)) {
            return None;
        }
        // Precharge all newly introduced input/state allocation and lookup work.
        // Old successful attempts return above before any of this work occurs.
        let width = p
            .nodes
            .len()
            .checked_add(p.states.len())?
            .checked_add(p.operators.len())?
            .checked_add(1)?;
        budget.take(
            width.checked_mul(p.states.len())?.checked_add(
                p.nodes
                    .len()
                    .checked_mul(model.driven.len().checked_add(1)?)?,
            )?,
        )?;
        // value_bounds(0) visits every supplied source, including generated
        // ones. Validated nominal/shaped curves start at zero, so each lookup
        // needs at most two word-bounded binary searches plus a bounded knot
        // copy/enclosure, with no interpolation. Reserve that work before the
        // query instead of treating its internal searches as free.
        budget.take(
            trajectory
                .config
                .pwl
                .len()
                .checked_mul(2 * usize::BITS as usize + 16)?,
        )?;
        let before: Vec<_> = model.initial().into_iter().map(I::point).collect();
        let mut nodes = vec![
            I {
                lo: f64::NEG_INFINITY,
                hi: f64::INFINITY
            };
            p.nodes.len()
        ];
        nodes[0] = I::ZERO;
        for (name, bounds) in model
            .driven
            .iter()
            .zip(trajectory.checked_value_bounds(0.).ok()?)
        {
            nodes[p.nodes.iter().position(|node| node == name)?] = bounds;
        }
        Some(prove_at_inputs(
            p,
            stages,
            required,
            &nodes,
            &before,
            &mut budget,
        ))
    };
    prove().unwrap_or(false)
}

#[cfg(test)]
fn legacy_remaining(
    p: &Program,
    stages: &[Vec<usize>],
    required: &BTreeSet<usize>,
    limit: usize,
) -> Option<Budget> {
    legacy_remaining_using(p, stages, required, limit, None)
}

fn legacy_remaining_using(
    p: &Program,
    stages: &[Vec<usize>],
    required: &BTreeSet<usize>,
    limit: usize,
    work: Option<&crate::transition_source_plan::Work>,
) -> Option<Budget> {
    if prove(
        p,
        stages,
        required,
        false,
        &mut Budget(limit, work.cloned()),
    )
    .unwrap_or(false)
    {
        return None;
    }
    let mut concrete = Budget(limit, work.cloned());
    if prove(p, stages, required, true, &mut concrete).unwrap_or(false) {
        return None;
    }
    Some(concrete)
}

#[cfg(test)]
fn unchanged_with_limit(
    p: &Program,
    stages: &[Vec<usize>],
    required: &BTreeSet<usize>,
    inputs: Option<(&[I], &[I])>,
    limit: usize,
) -> bool {
    let Some(mut concrete) = legacy_remaining(p, stages, required, limit) else {
        return true;
    };
    inputs.is_some_and(|(nodes, before)| {
        prove_at_inputs(p, stages, required, nodes, before, &mut concrete)
    })
}

/// A sufficient t=0 proof using the supplied input/state boxes. This only
/// chooses ordinary event execution; it does not execute, consume or publish a
/// callback. Unknown internal/history values remain unknown, including zero
/// coefficients. Unknown predicates join both original arms.
fn prove_at_inputs(
    p: &Program,
    stages: &[Vec<usize>],
    required: &BTreeSet<usize>,
    nodes: &[I],
    before: &[I],
    budget: &mut Budget,
) -> bool {
    fn reads(
        e: &Expression,
        budget: &mut Budget,
        width: usize,
        out: &mut BTreeSet<usize>,
    ) -> Option<()> {
        // Charge before visiting or allocating for each original node/term.
        budget.take(width)?;
        match e {
            Expression::State { state } => {
                out.insert(*state);
            }
            Expression::Affine { terms, .. } => {
                budget.take(terms.len())?;
            }
            Expression::Operator { .. } => {}
            Expression::Add { left, right }
            | Expression::Multiply { left, right }
            | Expression::Divide { left, right } => {
                reads(left, budget, width, out)?;
                reads(right, budget, width, out)?;
            }
            Expression::Power { base, .. } => reads(base, budget, width, out)?,
            Expression::Select {
                left,
                right,
                then_value,
                else_value,
                ..
            } => {
                for child in [left, right, then_value, else_value] {
                    reads(child, budget, width, out)?;
                }
            }
            // Unsupported exact forms never obtain a bootstrap certificate.
            _ => return None,
        }
        Some(())
    }
    fn body_reads(
        body: &[Statement],
        budget: &mut Budget,
        width: usize,
        out: &mut BTreeSet<usize>,
        writes: &mut BTreeSet<usize>,
    ) -> Option<()> {
        for statement in body {
            budget.take(1)?;
            match statement {
                Statement::Assign(a) => {
                    budget.take(width)?;
                    writes.insert(a.state);
                    reads(&a.rhs, budget, width, out)?;
                }
                Statement::Display { args, .. } => {
                    for e in args {
                        reads(e, budget, width, out)?;
                    }
                }
                Statement::If {
                    left,
                    right,
                    then_body,
                    else_body,
                    ..
                } => {
                    reads(left, budget, width, out)?;
                    reads(right, budget, width, out)?;
                    body_reads(then_body, budget, width, out, writes)?;
                    body_reads(else_body, budget, width, out, writes)?;
                }
                Statement::ArrayWrite { .. } | Statement::Loop { .. } => return None,
            }
        }
        Some(())
    }
    fn replay(
        body: &[Statement],
        local: &mut crate::event_value_proof::LocalState,
        nodes: &[I],
        budget: &mut Budget,
        width: usize,
    ) -> Option<()> {
        for statement in body {
            budget.take(1)?;
            match statement {
                Statement::Assign(a) => {
                    reads(&a.rhs, budget, width, &mut BTreeSet::new())?;
                    local
                        .assign_proof_with_work(a.state, &a.rhs, nodes, &mut || budget.take(1))
                        .ok()?;
                }
                // Ordinary execution still checks/captures the complete display.
                Statement::Display { .. } => {}
                Statement::If {
                    relation,
                    left,
                    right,
                    then_body,
                    else_body,
                    ..
                } => {
                    reads(left, budget, width, &mut BTreeSet::new())?;
                    reads(right, budget, width, &mut BTreeSet::new())?;
                    let known = local
                        .value_with_work(left, nodes, &mut || budget.take(1))
                        .ok()?
                        .zip(
                            local
                                .value_with_work(right, nodes, &mut || budget.take(1))
                                .ok()?,
                        )
                        .map(|(a, b)| {
                            use crate::ir::Relation;
                            match relation {
                                Relation::Lt => a < b,
                                Relation::Le => a <= b,
                                Relation::Gt => a > b,
                                Relation::Ge => a >= b,
                            }
                        });
                    if let Some(yes) = known {
                        replay(
                            if yes { then_body } else { else_body },
                            local,
                            nodes,
                            budget,
                            width,
                        )?;
                    } else {
                        budget.take(3usize.checked_mul(width)?.checked_mul(local.len())?)?;
                        let mut yes = local.clone();
                        let mut no = local.clone();
                        replay(then_body, &mut yes, nodes, budget, width)?;
                        replay(else_body, &mut no, nodes, budget, width)?;
                        local.merge(yes, &no);
                    }
                }
                Statement::ArrayWrite { .. } | Statement::Loop { .. } => return None,
            }
        }
        Some(())
    }
    let mut prove = || -> Option<bool> {
        if nodes.len() != p.nodes.len() || before.len() != p.states.len() {
            return None;
        }
        let width = p
            .nodes
            .len()
            .checked_add(p.states.len())?
            .checked_add(p.operators.len())?
            .checked_add(1)?;
        budget.take(2usize.checked_mul(width)?.checked_mul(before.len())?)?;
        let initial = crate::event_value_proof::LocalState::new(before);
        let mut local = initial.clone();
        for stage in stages {
            budget.take(1)?;
            let mut blocks = BTreeSet::new();
            for &block in stage {
                budget.take(width.checked_add(usize::BITS as usize)?)?;
                blocks.insert(block);
            }
            let mut writes = Vec::new();
            let mut references = Vec::new();
            for &block in &blocks {
                let event = p.events.get(block)?;
                budget.take(width)?;
                let mut state_reads = BTreeSet::new();
                let mut state_writes = BTreeSet::new();
                body_reads(
                    &event.body,
                    budget,
                    width,
                    &mut state_reads,
                    &mut state_writes,
                )?;
                writes.push(state_writes);
                references.push(state_reads);
            }
            // Independent blocks may be replayed serially only when every
            // explicit state read still sees the shared old frame. Otherwise
            // decline this optional proof and retain the prior diagnostic.
            for i in 0..writes.len() {
                for j in 0..i {
                    budget.take(3usize.checked_mul(width)?)?;
                    if !writes[i].is_disjoint(&writes[j])
                        || !writes[i].is_disjoint(&references[j])
                        || !writes[j].is_disjoint(&references[i])
                    {
                        return None;
                    }
                }
            }
            for block in blocks {
                replay(&p.events[block].body, &mut local, nodes, budget, width)?;
            }
        }
        for &state in required {
            budget.take(width)?;
            let e = Expression::State { state };
            let old = initial
                .value_with_work(&e, nodes, &mut || budget.take(1))
                .ok()??;
            if local
                .value_with_work(&e, nodes, &mut || budget.take(1))
                .ok()?
                .as_ref()
                != Some(&old)
            {
                return Some(false);
            }
        }
        Some(true)
    };
    prove().unwrap_or(false)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::{json, Value};
    fn state(s: usize) -> Value {
        json!({"op":"state","state":s})
    }
    fn c(v: f64) -> Value {
        json!({"op":"affine","constant":v,"terms":[]})
    }
    fn add(a: Value, b: Value) -> Value {
        json!({"op":"add","left":a,"right":b})
    }
    fn assign(s: usize, e: Value) -> Value {
        json!({"kind":"assign","state":s,"rhs":e})
    }
    fn program(blocks: Vec<Vec<Value>>) -> Program {
        let origin = json!({"source":"proof.va","line":1,"column":1,"instance":"dut"});
        let events:Vec<_>=blocks.into_iter().map(|body|json!({
            "origin":origin,"trigger":{"kind":"timer","start":0,"period":0,"time_tolerance":0,"enabled":true},"body":body
        })).collect();
        serde_json::from_value(json!({"schema_version":crate::ir::SCHEMA_VERSION,
            "nodes":["0","z"],"states":[
            {"instance":"dut","name":"q","kind":"real","initial":1},
            {"instance":"dut","name":"a","kind":"real","initial":0}],
            "events":events,"operators":[],"contributions":[]}))
        .unwrap()
    }
    fn required() -> BTreeSet<usize> {
        BTreeSet::from([0])
    }
    #[test]
    fn identity_and_affine_restoration() {
        for body in [
            vec![assign(0, state(0))],
            vec![assign(1, state(0)), assign(0, state(1))],
            vec![
                assign(0, add(state(0), c(1.))),
                assign(0, add(state(0), c(-1.))),
            ],
        ] {
            assert!(unchanged(&program(vec![body]), &[vec![0]], &required()));
        }
    }
    #[test]
    fn final_identity_is_not_whole_body_identity() {
        assert!(!unchanged(
            &program(vec![vec![
                assign(0, add(state(0), c(1.))),
                assign(0, state(0))
            ]]),
            &[vec![0]],
            &required()
        ));
    }
    #[test]
    fn formal_internal_read_can_only_flow_to_unrelated_state() {
        let v = json!({"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]});
        assert!(unchanged(
            &program(vec![vec![assign(0, state(0)), assign(1, v.clone())]]),
            &[vec![0]],
            &required()
        ));
        assert!(!unchanged(
            &program(vec![vec![assign(0, state(1)), assign(1, v)]]),
            &[vec![0]],
            &required()
        ));
    }
    #[test]
    fn independent_blocks_share_old_state_not_each_others_updates() {
        let p = program(vec![vec![assign(1, state(0))], vec![assign(0, state(1))]]);
        assert!(!unchanged(&p, &[vec![0, 1]], &required()));
        assert!(unchanged(&p, &[vec![0], vec![1]], &required()));
    }
    #[test]
    fn duplicate_trigger_ids_do_not_execute_a_body_twice() {
        let p = program(vec![vec![assign(0, state(0))]]);
        assert!(unchanged(&p, &[vec![0, 0]], &required()));
    }
    #[test]
    fn ambiguous_writers_do_not_gain_a_proof() {
        let p = program(vec![vec![assign(0, state(0))], vec![assign(0, state(0))]]);
        assert!(!unchanged(&p, &[vec![0, 1]], &required()));
    }
    #[test]
    fn all_arm_join_requires_identical_complete_rows() {
        let origin = json!({"source":"proof.va","line":1,"column":1,"instance":"dut"});
        for (other, expected) in [(state(0), true), (add(state(0), c(1.)), false)] {
            let branch = json!({"kind":"if","relation":"gt","left":state(1),"right":c(0.),
                "then_body":[assign(0,state(0))],"else_body":[assign(0,other)],"origin":origin});
            assert_eq!(
                unchanged(&program(vec![vec![branch]]), &[vec![0]], &required()),
                expected
            );
        }
    }
    #[test]
    fn unknown_nonlinear_unrelated_state_does_not_poison_identity() {
        let nonlinear = json!({"op":"multiply","left":state(1),"right":state(1)});
        for related in [false, true] {
            let mut body = vec![assign(1, nonlinear.clone()), assign(0, state(0))];
            if related {
                body.push(assign(0, state(1)));
            }
            assert_eq!(
                unchanged(&program(vec![body]), &[vec![0]], &required()),
                !related
            );
        }
    }

    #[test]
    fn actual_initial_constants_can_prove_unrelated_read_safe() {
        let v = json!({"op":"affine","constant":0.,"terms":[{"node":1,"coefficient":1.}]});
        let p = program(vec![vec![assign(0, c(1.)), assign(1, v.clone())]]);
        assert!(unchanged(&p, &[vec![0]], &required()));
        let changed = program(vec![vec![assign(0, c(2.)), assign(1, v)]]);
        assert!(!unchanged(&changed, &[vec![0]], &required()));
    }
    fn at_input(
        p: &Program,
        stages: &[Vec<usize>],
        required: &BTreeSet<usize>,
        input: I,
        states: &[I],
    ) -> bool {
        prove_at_inputs(
            p,
            stages,
            required,
            &[I::ZERO, input],
            states,
            &mut Budget(2_000_000, None),
        )
    }
    #[test]
    fn input_aware_proof_uses_the_whole_source_box_and_unknown_state_box() {
        let origin = json!({"source":"proof.va","line":1,"column":1,"instance":"dut"});
        let v = json!({"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]});
        let branch = json!({"kind":"if","relation":"gt","left":v,"right":c(0.),
            "then_body":[assign(0,c(1.))],"else_body":[assign(0,c(2.))],"origin":origin});
        let p = program(vec![vec![branch]]);
        let states = [I::ONE, I::ZERO];
        assert!(at_input(&p, &[vec![0]], &required(), I::ONE, &states));
        assert!(!at_input(
            &p,
            &[vec![0]],
            &required(),
            I { lo: -1., hi: 1. },
            &states
        ));
        assert!(!at_input(
            &p,
            &[vec![0]],
            &required(),
            I {
                lo: f64::NEG_INFINITY,
                hi: f64::INFINITY
            },
            &states
        ));
        let mut uncertain = states;
        uncertain[0] = I { lo: 0.9, hi: 1.1 };
        assert!(!at_input(&p, &[vec![0]], &required(), I::ONE, &uncertain));
    }
    #[test]
    fn unknown_nonseed_predicates_join_and_cannot_flow_back_into_a_seed() {
        let origin = json!({"source":"proof.va","line":1,"column":1,"instance":"dut"});
        let v = json!({"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]});
        let branch = json!({"kind":"if","relation":"gt","left":v,"right":c(0.),
            "then_body":[assign(1,c(1.))],"else_body":[assign(1,c(2.))],"origin":origin});
        let unknown = I {
            lo: f64::NEG_INFINITY,
            hi: f64::INFINITY,
        };
        let states = [I::ONE, I::ZERO];
        let p = program(vec![vec![branch.clone(), assign(0, c(1.))]]);
        assert!(at_input(&p, &[vec![0]], &required(), unknown, &states));
        let p = program(vec![vec![branch, assign(0, state(1))]]);
        assert!(!at_input(&p, &[vec![0]], &required(), unknown, &states));
        let p = program(vec![vec![assign(1, v), assign(0, c(1.))]]);
        assert!(at_input(&p, &[vec![0]], &required(), unknown, &states));
        assert!(!at_input(
            &p,
            &[vec![0]],
            &BTreeSet::from([0, 1]),
            unknown,
            &states
        ));
    }
    #[test]
    fn input_aware_proof_does_not_turn_unknown_zero_coefficients_into_a_value() {
        let v = json!({"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]});
        let zero = json!({"op":"multiply","left":c(0.),"right":v});
        let p = program(vec![vec![assign(0, add(c(1.), zero))]]);
        assert!(!at_input(
            &p,
            &[vec![0]],
            &required(),
            I {
                lo: f64::NEG_INFINITY,
                hi: f64::INFINITY
            },
            &[I::ONE, I::ZERO]
        ));
    }
    #[test]
    fn input_aware_blocks_keep_shared_old_state_and_existing_resource_limit() {
        let p = program(vec![vec![assign(1, state(0))], vec![assign(0, state(1))]]);
        let states = [I::ONE, I::ZERO];
        assert!(!at_input(&p, &[vec![0, 1]], &required(), I::ZERO, &states));
        assert!(at_input(
            &p,
            &[vec![0], vec![1]],
            &required(),
            I::ZERO,
            &states
        ));
        let p = program(vec![vec![assign(0, state(0))], vec![assign(0, state(0))]]);
        assert!(!at_input(&p, &[vec![0, 1]], &required(), I::ZERO, &states));
        let p = program(vec![vec![assign(0, state(0))]]);
        assert!(!at_input(
            &p,
            &vec![vec![0]; 200_000],
            &required(),
            I::ZERO,
            &states
        ));
    }
    #[test]
    fn budget_exhaustion_is_sticky_and_cannot_fund_input_replay() {
        let mut b = Budget(3, None);
        assert!(b.take(4).is_none());
        assert_eq!(b.0, 0);
        assert!(b.take(1).is_none());
        let p = program(vec![vec![assign(0, c(1.))]]);
        let nodes = [I::ZERO, I::ONE];
        let states = [I::ONE, I::ZERO];
        // Input replay is valid with its full cap, but cannot create a fresh
        // cap after the concrete attempt exhausted its inherited balance.
        assert!(prove_at_inputs(
            &p,
            &[vec![0]],
            &required(),
            &nodes,
            &states,
            &mut Budget(200, None)
        ));
        assert!(!prove_at_inputs(
            &p,
            &[vec![0]],
            &required(),
            &nodes,
            &states,
            &mut b
        ));
        assert!(!unchanged_with_limit(
            &p,
            &[vec![0]],
            &required(),
            Some((&nodes, &states)),
            9
        ));
    }
    #[test]
    fn exact_power_work_consumes_the_inherited_initialization_allowance() {
        // Three exponent-32 nodes perform at least 96 exact multiplications
        // per assignment. 300 assignments need 28_800 operations, exceeding
        // this scaled 20_000 allowance even before scans and legacy attempts.
        // The small accepted case distinguishes accounting from disabling proof.
        let mut rhs = state(1);
        for _ in 0..3 {
            rhs = json!({"op":"power","base":rhs,"exponent":32});
        }
        for (copies, accepted) in [(1, true), (300, false)] {
            let mut body = vec![assign(1, rhs.clone()); copies];
            body.push(assign(
                0,
                json!({"op":"affine","constant":0.,
                "terms":[{"node":1,"coefficient":1.}]}),
            ));
            let p = program(vec![body]);
            assert_eq!(
                unchanged_with_limit(
                    &p,
                    &[vec![0]],
                    &required(),
                    Some((&[I::ZERO, I::ONE], &[I::ONE, I::ZERO])),
                    20_000
                ),
                accepted
            );
        }
    }

    #[test]
    fn both_legacy_successes_keep_their_original_per_attempt_cap() {
        for rhs in [state(0), c(1.)] {
            let p = program(vec![vec![assign(0, rhs)]]);
            for limit in 0..150 {
                let old = prove(&p, &[vec![0]], &required(), false, &mut Budget(limit, None))
                    .unwrap_or(false)
                    || prove(&p, &[vec![0]], &required(), true, &mut Budget(limit, None))
                        .unwrap_or(false);
                // No input fallback: exact compatibility over every boundary.
                assert_eq!(
                    unchanged_with_limit(&p, &[vec![0]], &required(), None, limit),
                    old
                );
            }
        }
    }
    #[test]
    fn input_scan_and_stage_dedup_charge_before_work() {
        let p = program(vec![vec![assign(0, c(1.))]]);
        let nodes = [I::ZERO, I::ONE];
        let states = [I::ONE, I::ZERO];
        let mut budget = Budget(21, None); // 20 frame units, then stage; no block insertion.
        assert!(!prove_at_inputs(
            &p,
            &[vec![0; 10000]],
            &required(),
            &nodes,
            &states,
            &mut budget
        ));
        assert_eq!(budget.0, 0);
        let mut budget = Budget(100, None);
        let many = program(vec![vec![assign(1, state(0)); 10000]]);
        assert!(!prove_at_inputs(
            &many,
            &[vec![0]],
            &required(),
            &nodes,
            &states,
            &mut budget
        ));
        assert_eq!(budget.0, 0);
    }
}
