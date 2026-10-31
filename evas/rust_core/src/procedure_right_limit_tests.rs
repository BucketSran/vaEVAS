//! Source-order cross bodies read the post-root side of an exact zero (#281).
use super::*;
use crate::event_conditions::PostRootSides;

fn model(case: &str) -> crate::events::EventModel {
    let fixture: serde_json::Value = serde_json::from_str(include_str!(
        "../tests/fixtures/ir33_cross_right_limit.json"
    ))
    .unwrap();
    let case = &fixture["cases"][case];
    crate::events::EventModel::new_with_procedure_work(
        serde_json::from_value(case["program"].clone()).unwrap(),
        serde_json::from_value(case["driven"].clone()).unwrap(),
        crate::ir::Tolerances::default(),
        Work::default(),
    )
    .unwrap()
}

fn node(m: &crate::events::EventModel, name: &str) -> usize {
    m.program.nodes.iter().position(|n| n == name).unwrap()
}

/// The cross body and its calendar leaf (leaves are numbered in event order).
fn cross(m: &crate::events::EventModel) -> (usize, usize) {
    let event = m
        .program
        .events
        .iter()
        .position(|e| matches!(e.trigger, ir::EventTrigger::Cross { .. }))
        .unwrap();
    let leaf = m.program.events[..event]
        .iter()
        .map(|e| e.trigger.leaves().unwrap().len())
        .sum();
    (event, leaf)
}

/// Executed assignment of the cross body (0: then arm q=2, 1: else arm q=3)
/// with the inputs at the root, or the refusal kind.
fn arm(m: &crate::events::EventModel, inputs: &[I]) -> Result<Vec<usize>, String> {
    let (event, leaf) = cross(m);
    let before = vec![I::ZERO; m.program.states.len()];
    m.conditions
        .select_at_roots(&[event], inputs, &[leaf], &before)
        .map(|s| {
            s.actions
                .iter()
                .find(|(e, _)| *e == event)
                .map(|(_, a)| a.clone())
                .unwrap()
        })
        .map_err(|e| e.kind.to_string())
}

#[test]
fn fired_guard_side_decides_an_exact_zero_without_derivatives() {
    // Paid contexts install the leaf sides only: no derivative, no window.
    let m = model("guard");
    let (event, leaf) = cross(&m);
    let at = [I::point(0.5)];
    let with = |sides: Vec<(usize, i8)>| {
        let _scope = PostRootSides::install(sides, Vec::new(), vec![event], None);
        arm(&m, &at)
    };
    // u>0.5: true after a rising root, false after a falling one or on a plateau.
    assert_eq!(with(vec![(leaf, 1)]), Ok(vec![0]));
    assert_eq!(with(vec![(leaf, -1)]), Ok(vec![1]));
    assert_eq!(with(vec![(leaf, 0)]), Ok(vec![1]));
    // Inconsistent sides are no proof; neither is a missing side.
    for sides in [vec![], vec![(leaf, 1), (leaf, -1)]] {
        assert_eq!(with(sides).unwrap_err(), "event_condition");
    }
    // A body that is not a tau+ reader keeps the exact-time comparison.
    let _scope = PostRootSides::install(Vec::new(), Vec::new(), Vec::new(), None);
    assert_eq!(arm(&m, &at), Ok(vec![1]));
}

#[test]
fn unfired_input_needs_its_own_derivative() {
    let m = model("unfired");
    let (event, leaf) = cross(&m);
    let at = [I::point(0.5), I::point(0.5)];
    // w is exactly 0.5 at tau and not a fired guard: the guard side is no proof.
    {
        let _scope = PostRootSides::install(vec![(leaf, 1)], Vec::new(), vec![event], None);
        assert_eq!(arm(&m, &at).unwrap_err(), "event_condition");
    }
    for (slope, expected) in [(1.0, 0), (-1.0, 1), (0.0, 1)] {
        let mut slopes = vec![None; m.program.nodes.len()];
        slopes[node(&m, "u")] = Some(I::ONE);
        slopes[node(&m, "w")] = Some(I::point(slope));
        let _scope = PostRootSides::install(vec![(leaf, 1)], Vec::new(), vec![event], None)
            .with_input_slopes(crate::event_conditions::InputSlopes {
                by_node: slopes,
                driven: m.driven.clone(),
            });
        assert_eq!(arm(&m, &at), Ok(vec![expected]), "slope {slope}");
    }
}

#[test]
fn identical_arms_continue_without_a_side() {
    // Without any certificate the distinct arms are refused, identical ones run.
    let m = model("guard");
    let (event, _) = cross(&m);
    let _scope = PostRootSides::install(Vec::new(), Vec::new(), vec![event], None);
    assert_eq!(arm(&m, &[I::point(0.5)]).unwrap_err(), "event_condition");
    let m = model("arms");
    assert_eq!(arm(&m, &[I::point(0.5)]), Ok(vec![0]));
}

#[test]
fn certificate_work_exhaustion_is_a_budget_error() {
    let m = model("guard");
    let (event, leaf) = cross(&m);
    let w = crate::real_expression::work(&m);
    let _scope = PostRootSides::install(vec![(leaf, 1)], Vec::new(), vec![event], None);
    assert_eq!(arm(&m, &[I::point(0.5)]), Ok(vec![0]));
    w.debit(2, 1_000_000_000 - w.spent()).unwrap();
    for _ in 0..2 {
        assert_eq!(arm(&m, &[I::point(0.5)]).unwrap_err(), "step_budget");
    }
}
