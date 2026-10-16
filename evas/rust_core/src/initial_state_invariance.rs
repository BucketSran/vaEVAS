//! A sufficient all-arm proof that selected held states are unchanged.
//! This chooses the existing initialization path; it never skips event execution
//! or its writer, integer, condition and enclosure checks.
use super::{affine, substitute, I};
use crate::ir::{Expression, Program, Statement};
use std::collections::BTreeSet;

type Row = Option<Vec<I>>;

struct Budget(usize);
impl Budget {
    fn take(&mut self, n: usize) -> Option<()> {
        self.0 = self.0.checked_sub(n)?;
        Some(())
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

pub(crate) fn unchanged(p: &Program, stages: &[Vec<usize>], required: &BTreeSet<usize>) -> bool {
    prove(p, stages, required, false).unwrap_or(false)
        || prove(p, stages, required, true).unwrap_or(false)
}

fn prove(
    p: &Program,
    stages: &[Vec<usize>],
    required: &BTreeSet<usize>,
    concrete: bool,
) -> Option<bool> {
    let width = p
        .nodes
        .len()
        .checked_add(p.states.len())?
        .checked_add(p.operators.len())?
        .checked_add(1)?;
    let mut budget = Budget(2_000_000);
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
        after = batch(p, stage, &after, &mut budget)?;
    }
    Some(
        required
            .iter()
            .all(|&s| after[s].as_ref() == initial[s].as_ref()),
    )
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
}
