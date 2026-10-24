//! Pre-branch voltage proofs keep actual history boxes and the original owner.
use super::*;
fn model() -> crate::events::EventModel {
    let r: crate::ir::Request = serde_json::from_str(include_str!(
        "../tests/fixtures/ir33_pre_event_voltage.json"
    ))
    .unwrap();
    crate::events::EventModel::new_with_procedure_work(
        r.program,
        r.driven,
        r.tolerances,
        crate::transition_source_plan::Work::default(),
    )
    .unwrap()
}
#[test]
fn pre_event_history_box_selects_without_trial_nodes_and_failed_frames_do_not_publish() {
    let m = model();
    let w = crate::real_expression::work(&m);
    let q = m.program.states.iter().position(|s| s.name == "q").unwrap();
    let s = m.program.states.iter().position(|s| s.name == "s").unwrap();
    let mut before = m.initial();
    before[s] = 1.;
    let original = before.clone();
    let bounds = before.iter().copied().map(I::point).collect::<Vec<_>>();
    let event = m
        .program
        .events
        .iter()
        .position(|e| matches!(e.trigger,EventTrigger::Timer{start,..} if start==0.375))
        .unwrap();
    let proofs = crate::event_value_proof::Proofs::new();
    let nominal = crate::event_value_proof::Context::candidate_frame(
        &proofs,
        m.program.nodes.len(),
        &before,
        &[0.5],
        w,
    )
    .unwrap();
    let stable = nominal.try_with_operators(&[I::point(0.5)]).unwrap();
    let uncertain = nominal
        .try_with_operators(&[I { lo: 0.49, hi: 0.51 }])
        .unwrap();
    for _ in 0..2 {
        assert_eq!(
            m.conditions
                .select_with_proofs(&[event], &[I::ZERO], &[], &bounds, Some(&uncertain))
                .err()
                .unwrap()
                .kind,
            "event_condition"
        );
        assert_eq!(before, original);
        let selected = m
            .conditions
            .select_with_proofs(&[event], &[I::ZERO], &[], &bounds, Some(&stable))
            .unwrap();
        let mut nodes = vec![0.; m.program.nodes.len()];
        for (i, name) in m.program.nodes.iter().enumerate() {
            if name == "y" {
                nodes[i] = 2.;
            }
            if name == "z" || name.ends_with(":z") {
                nodes[i] = 1.5;
            }
        }
        let plan = selected.plan.unwrap();
        let after = plan
            .numeric_states(&m.program, &nodes, &before, Some(&stable), w)
            .unwrap();
        assert_eq!(after[q], 2.);
        plan.certificate(
            &m.program,
            &m.driven,
            m.tolerances.clone(),
            &[I::ZERO],
            &bounds,
            &[I::point(0.5)],
            &nodes,
            &after,
            Some(&stable),
            w,
        )
        .unwrap();
        let mut loose = m.tolerances.clone();
        loose.absolute = 1.;
        loose.relative = 0.;
        assert!(
            plan.certificate(
                &m.program,
                &m.driven,
                loose,
                &[I::ZERO],
                &bounds,
                &[I { lo: 0.49, hi: 0.51 }],
                &nodes,
                &after,
                Some(&uncertain),
                w
            )
            .is_err(),
            "expanded history cannot reuse an old source-position branch proof"
        );
    }
    w.debit(2, 1_000_000_000 - w.spent()).unwrap();
    for _ in 0..2 {
        assert_eq!(
            m.conditions
                .select_with_proofs(&[event], &[I::ZERO], &[], &bounds, Some(&stable))
                .err()
                .unwrap()
                .kind,
            "step_budget"
        );
    }
    assert_eq!(before, original);
}
#[test]
fn pre_event_provider_cannot_erase_assigned_state_even_under_zero_scale() {
    let m = model();
    let w = crate::real_expression::work(&m);
    let q = m.program.states.iter().position(|s| s.name == "q").unwrap();
    let z = m
        .program
        .nodes
        .iter()
        .position(|s| s.ends_with(":z") || s == "z")
        .unwrap();
    let mut p = m.program.clone();
    let row = p
        .contributions
        .iter_mut()
        .find(|c| c.positive == z || c.negative == z)
        .unwrap();
    row.rhs = Expression::Multiply {
        left: Box::new(Expression::Affine {
            constant: 0.,
            terms: vec![],
        }),
        right: Box::new(Expression::State { state: q }),
    };
    let mut nodes = vec![
        I {
            lo: f64::NEG_INFINITY,
            hi: f64::INFINITY
        };
        p.nodes.len()
    ];
    nodes[0] = I::ZERO;
    assert!(crate::causal_event::independent_voltage_bounds(
        &p,
        &m.driven,
        z,
        &nodes,
        &vec![I::ZERO; p.states.len()],
        &[I::point(0.5)],
        &[q].into_iter().collect(),
        Some(w)
    )
    .unwrap()
    .is_none());
}

#[test]
fn guard_only_provider_replays_even_without_circuit_parameters() {
    let original = model();
    let mut p = original.program.clone();
    p.operators.clear();
    let u = p.nodes.iter().position(|s| s == "u").unwrap();
    let z = p
        .nodes
        .iter()
        .position(|s| s == "z" || s.ends_with(":z"))
        .unwrap();
    let q = p.states.iter().position(|s| s.name == "q").unwrap();
    for row in &mut p.contributions {
        let sign = if row.positive == 0 { -1. } else { 1. };
        row.rhs = Expression::Affine {
            constant: 0.,
            terms: vec![crate::ir::Term {
                node: u,
                coefficient: sign,
            }],
        };
    }
    let event = p
        .events
        .iter()
        .position(|e| matches!(e.trigger,EventTrigger::Timer{start,..}if start==0.375))
        .unwrap();
    let Statement::If { right, .. } = &mut p.events[event].body[0] else {
        unreachable!()
    };
    **right = Expression::Affine {
        constant: 0.5,
        terms: vec![],
    };
    let m = crate::events::EventModel::new_with_procedure_work(
        p,
        original.driven.clone(),
        original.tolerances.clone(),
        crate::transition_source_plan::Work::default(),
    )
    .unwrap();
    let w = crate::real_expression::work(&m);
    let before = m.initial();
    let bounds = before.iter().copied().map(I::point).collect::<Vec<_>>();
    let selected = m
        .conditions
        .select_with_proofs(&[event], &[I::point(0.5)], &[], &bounds, None)
        .unwrap();
    let plan = selected.plan.unwrap();
    let mut nodes = vec![0.5; m.program.nodes.len()];
    nodes[0] = 0.;
    nodes[u] = 0.5;
    nodes[z] = 0.5;
    let after = plan
        .numeric_states(&m.program, &nodes, &before, None, w)
        .unwrap();
    assert_eq!(after[q], 2.);
    plan.certificate(
        &m.program,
        &m.driven,
        m.tolerances.clone(),
        &[I::point(0.5)],
        &bounds,
        &[],
        &nodes,
        &after,
        None,
        w,
    )
    .unwrap();
    let mut loose = m.tolerances.clone();
    loose.absolute = 1.;
    loose.relative = 0.;
    assert!(
        plan.certificate(
            &m.program,
            &m.driven,
            loose,
            &[I { lo: 0.49, hi: 0.51 }],
            &bounds,
            &[],
            &nodes,
            &after,
            None,
            w
        )
        .is_err(),
        "guard proof is required even when no sampled parameter reaches a voltage contribution"
    );
}

#[test]
fn raw_array_choices_recertify_read_and_write_slots_without_voltage_parameters() {
    for read in [false, true] {
        let original = model();
        let mut p = original.program.clone();
        p.operators.clear();
        let u = p.nodes.iter().position(|s| s == "u").unwrap();
        let z = p
            .nodes
            .iter()
            .position(|s| s == "z" || s.ends_with(":z"))
            .unwrap();
        let event = p
            .events
            .iter()
            .position(|e| matches!(e.trigger,EventTrigger::Timer{start,..}if start==0.375))
            .unwrap();
        let origin = p.events[event].origin.clone();
        for row in &mut p.contributions {
            row.rhs = Expression::Affine {
                constant: 0.,
                terms: vec![crate::ir::Term {
                    node: u,
                    coefficient: if row.positive == 0 { -1. } else { 1. },
                }],
            };
        }
        let index = Box::new(Expression::Affine {
            constant: 0.,
            terms: vec![crate::ir::Term {
                node: z,
                coefficient: 1.,
            }],
        });
        p.events[event].body = if read {
            vec![Statement::Assign(crate::ir::Assignment {
                state: 1,
                rhs: Expression::ArrayRead {
                    states: vec![0, 1],
                    index,
                    first: 0,
                    last: 1,
                    origin,
                },
            })]
        } else {
            vec![Statement::ArrayWrite {
                states: vec![0, 1],
                index,
                rhs: Expression::Affine {
                    constant: 2.,
                    terms: vec![],
                },
                first: 0,
                last: 1,
                origin,
            }]
        };
        let w = crate::real_expression::work(&original);
        let before = vec![I::point(2.), I::point(3.)];
        let boxes = vec![I::ZERO; p.nodes.len()];
        let plan = std::sync::Arc::new(
            crate::procedure::execute(&p, &[event], &boxes, &before, None, w).unwrap(),
        );
        let nodes = vec![0.; p.nodes.len()];
        let after = plan.numeric_states(&p, &nodes, &[2., 3.], None, w).unwrap();
        plan.certificate(
            &p,
            &original.driven,
            original.tolerances.clone(),
            &[I::ZERO],
            &before,
            &[],
            &nodes,
            &after,
            None,
            w,
        )
        .unwrap();
        let mut loose = original.tolerances.clone();
        loose.absolute = 2.;
        loose.relative = 0.;
        for changed in [I { lo: 0., hi: 1. }, I::point(1.)] {
            assert!(
                plan.certificate(
                    &p,
                    &original.driven,
                    loose.clone(),
                    &[changed],
                    &before,
                    &[],
                    &nodes,
                    &after,
                    None,
                    w
                )
                .is_err(),
                "raw array {read} cannot reuse a different or ambiguous slot"
            );
        }
    }
}
