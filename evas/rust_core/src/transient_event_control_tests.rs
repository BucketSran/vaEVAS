//! Compact event control uses the production selection, replay and commit paths.
use super::*;
use crate::ir::{Program, Tolerances, TransientInputs};
use serde_json::{json, Value};
fn o() -> Value {
    json!({"source":"control.va","line":1,"column":1,"instance":"M"})
}
fn c(x: f64) -> Value {
    json!({"op":"affine","constant":x,"terms":[]})
}
fn s(i: usize) -> Value {
    json!({"op":"state","state":i})
}
fn add(a: Value, b: Value) -> Value {
    json!({"op":"add","left":a,"right":b})
}
fn set(i: usize, rhs: Value) -> Value {
    json!({"kind":"assign","state":i,"rhs":rhs})
}
fn loop_body(count: f64, body: Vec<Value>) -> Value {
    json!({"kind":"loop","initialize":[set(0,c(0.))],"relation":"lt","left":s(0),"right":c(count),"body":body,"update":[set(0,add(s(0),c(1.)))],"origin":o()})
}
fn program(body: Vec<Value>) -> Program {
    serde_json::from_value(json!({"schema_version":SCHEMA_VERSION,"nodes":["0","u"],"contributions":[],"states":[
 {"instance":"M","name":"i","kind":"integer","initial":0},{"instance":"M","name":"q","kind":"integer","initial":0},
 {"instance":"M","name":"a0","kind":"integer","initial":0},{"instance":"M","name":"a1","kind":"integer","initial":0}],
 "events":[{"trigger":{"kind":"timer","start":0.5,"period":0,"enabled":true,"time_tolerance":1e-9},"origin":o(),"body":body}]})).unwrap()
}
fn model(p: Program) -> EventModel {
    EventModel::new(p, vec!["u".into()], Tolerances::default()).unwrap()
}
fn execute(m: &EventModel) -> Result<(Vec<f64>, Vec<crate::ir::DisplayRecord>), Error> {
    let before = m.initial();
    let bounds = before.iter().copied().map(I::point).collect::<Vec<_>>();
    let selected = m
        .passive_conditions
        .select_at_roots(&[0], &[I::ZERO], &[], &bounds)?;
    m.check_selection_writers(&selected)?;
    m.apply_with_displays(&selected, &[0., 0.], &before, 0.5)
}
#[test]
fn runtime_loop_zero_one_sequence_and_total_budget() {
    for n in [0, 1, 3, 4096] {
        let m = model(program(vec![loop_body(
            n as f64,
            vec![set(1, add(s(1), c(1.)))],
        )]));
        let (after, _) = execute(&m).unwrap();
        assert_eq!(after[1], n as f64);
        assert_eq!(after[0], n as f64);
    }
    let m = model(program(vec![
        loop_body(2048., vec![]),
        loop_body(2048., vec![]),
    ]));
    assert!(execute(&m).is_ok());
    let m = model(program(vec![
        loop_body(2048., vec![]),
        loop_body(2049., vec![]),
    ]));
    assert_eq!(execute(&m).unwrap_err().kind, "event_loop_budget");
}
#[test]
fn compact_array_mapping_and_lazy_unselected_index() {
    let read = |index| json!({"op":"array_read","states":[2,3],"first":-1,"last":0,"index":index,"origin":o()});
    let m = model(program(vec![
        json!({"kind":"array_write","states":[2,3],"first":-1,"last":0,"index":c(-1.),"rhs":c(7.),"origin":o()}),
        set(
            1,
            json!({"op":"select","relation":"gt","left":c(1.),"right":c(0.),"then_value":read(c(-1.)),"else_value":read(c(1.)),"origin":o()}),
        ),
    ]));
    let (after, _) = execute(&m).unwrap();
    assert_eq!(after[1..], [7., 7., 0.]);
    for index in [-2., 1.] {
        let m = model(program(vec![set(1, read(c(index)))]));
        assert_eq!(execute(&m).unwrap_err().kind, "array_index_range");
    }
    for slots in [vec![2, 2], vec![2, 999], vec![2]] {
        let p = program(vec![set(
            1,
            json!({"op":"array_read","states":slots,"first":-1,"last":0,"index":c(-1.),"origin":o()}),
        )]);
        assert_eq!(
            EventModel::new(p, vec!["u".into()], Tolerances::default())
                .err()
                .unwrap()
                .kind,
            "invalid_ir"
        );
    }
}
#[test]
fn intermediate_integer_overflow_cannot_be_canceled() {
    let overflow = json!({"op":"checked_integer","value":add(c(2147483647.),c(1.)),"origin":o()});
    let m = model(program(vec![set(1, add(overflow, c(-1.)))]));
    assert_eq!(execute(&m).unwrap_err().kind, "integer_range");
}
#[test]
fn later_array_failure_rolls_back_prefix_displays_and_old_history_then_retries() {
    let mut p = program(vec![]);
    // An independent physical integral ensures a failed observer cannot mutate history.
    p.nodes.push("y".into());
    let mut po = o();
    po["instance"] = json!("P");
    p.operators =
        serde_json::from_value(json!([{"kind":"idt","ic":3,"input":c(1.),"origin":po}])).unwrap();
    p.contributions=serde_json::from_value(json!([{"branch":{"instance":"P","local_positive":"p","local_negative":"r","kind":"voltage"},"positive":2,"negative":0,"rhs":{"op":"operator","operator":0},"origin":po}])).unwrap();
    let display = json!({"kind":"display","format":"q=%d","args":[s(1)],"origin":o()});
    let choose = json!({"op":"select","relation":"gt","left":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]},"right":c(0.5),"then_value":c(3.),"else_value":c(2.),"origin":o()});
    let mut looping = loop_body(
        3.,
        vec![
            json!({"kind":"array_write","states":[2,3],"first":0,"last":1,"index":s(0),"rhs":add(s(1),c(1.)),"origin":o()}),
            set(1, add(s(1), c(1.))),
            display.clone(),
        ],
    );
    looping["right"] = s(4);
    p.states.push(
        serde_json::from_value(json!({"instance":"M","name":"limit","kind":"integer","initial":0}))
            .unwrap(),
    );
    p.events=serde_json::from_value(json!([
 {"trigger":{"kind":"timer","start":0.125,"period":0,"enabled":true,"time_tolerance":1e-9},"origin":o(),"body":[set(1,c(1.)),display]},
 {"trigger":{"kind":"timer","start":0.5,"period":0,"enabled":true,"time_tolerance":1e-9},"origin":o(),"body":[set(4,choose),looping]}])).unwrap();
    let m = model(p);
    let trajectory = |value| {
        Trajectory::new(
            TransientInputs {
                analytic_sources: vec![],
                pwl_errors_v: None,
                strobetimes: vec![],
                pwl: vec![vec![[0., value], [1., value]]],
                output_times: vec![0., 1.],
                stop: 1.,
                max_step: 1.,
            },
            1,
        )
        .unwrap()
    };
    let good = trajectory(0.);
    let bad = trajectory(1.);
    let states = m.initial();
    let state_bounds = states.iter().copied().map(I::point).collect::<Vec<_>>();
    let cal = schedule_held(&m, &good, &state_bounds).unwrap();
    let operators = Operators::new(&m.program, &good, &m.driven, &states).unwrap();
    let circuit = m
        .circuit_with(&states, &operators.values(0.).unwrap())
        .unwrap();
    let solution = circuit.solve(&good.values(0.)).unwrap();
    let mut controller = Controller {
        accepted: Frame {
            value_proofs: Default::default(),
            time_proofs: Default::default(),
            time: 0.,
            states,
            state_bounds,
            solution,
            circuit,
            operators,
        },
        event: 0,
        records: vec![],
        outputs: vec![],
    };
    controller.accept_events(&m, &good, &cal).unwrap();
    let before = controller.accepted.states.clone();
    let physical = controller.accepted.operators.values(0.125).unwrap();
    let old_bounds = controller.accepted.state_bounds.clone();
    let old_records = serde_json::to_string(&controller.records).unwrap();
    assert_eq!(
        controller.accept_events(&m, &bad, &cal).unwrap_err().kind,
        "array_index_range"
    );
    assert_eq!(controller.event, 1);
    assert_eq!(controller.accepted.states, before);
    assert_eq!(controller.accepted.state_bounds, old_bounds);
    assert_eq!(
        serde_json::to_string(&controller.records).unwrap(),
        old_records
    );
    assert_eq!(
        controller.accepted.operators.values(0.125).unwrap(),
        physical
    );
    controller.accept_events(&m, &good, &cal).unwrap();
    assert_eq!(controller.accepted.states[1], 3.);
    assert_eq!(controller.accepted.states[2], 2.);
    assert_eq!(controller.accepted.states[3], 3.);
    assert!((controller.accepted.operators.values(0.5).unwrap()[0] - 3.5).abs() < 1e-10);
    assert_eq!(
        controller
            .records
            .iter()
            .map(|r| r.display_records.len())
            .sum::<usize>(),
        3
    );
}

#[test]
fn raw_ir_rejects_foreign_mixed_empty_mapping_and_non_event_roles() {
    let read = || json!({"op":"array_read","states":[2,3],"first":-1,"last":0,"index":c(-1.),"origin":o()});
    for mutation in 0..5 {
        let mut p = program(vec![set(1, read())]);
        match mutation {
            0 => p.states[3].kind = crate::ir::StateKind::Real,
            1 => p.states[3].instance = "foreign".into(),
            2 => {
                if let crate::ir::Statement::Assign(a) = &mut p.events[0].body[0] {
                    if let crate::ir::Expression::ArrayRead { states, .. } = &mut a.rhs {
                        states.clear();
                    }
                }
            }
            3 => {
                if let crate::ir::Statement::Assign(a) = &mut p.events[0].body[0] {
                    if let crate::ir::Expression::ArrayRead { origin, .. } = &mut a.rhs {
                        origin.column = 0;
                    }
                }
            }
            _ => {
                if let crate::ir::Statement::Assign(a) = &mut p.events[0].body[0] {
                    if let crate::ir::Expression::ArrayRead { first, .. } = &mut a.rhs {
                        *first = 1;
                    }
                }
            }
        }
        assert_eq!(
            EventModel::new(p, vec!["u".into()], Tolerances::default())
                .err()
                .unwrap()
                .kind,
            "invalid_ir"
        );
    }
    let checked: crate::ir::Expression =
        serde_json::from_value(json!({"op":"checked_integer","value":c(1.),"origin":o()})).unwrap();
    let mut p = program(vec![]);
    p.states[0].initial = crate::ir::StateInitial::Predicate(checked.clone());
    assert_eq!(
        crate::event_control::validate(&p).unwrap_err().kind,
        "unsupported_analysis"
    );
    let mut p = program(vec![]);
    p.events[0].trigger = crate::ir::EventTrigger::Cross {
        guard: checked,
        direction: 1,
        time_tolerance: 1e-9,
        expression_tolerance: 1e-9,
    };
    assert_eq!(
        crate::event_control::validate(&p).unwrap_err().kind,
        "unsupported_analysis"
    );
    let mut p = program(vec![]);
    p.nodes = vec!["x".into(); 100_000];
    assert_eq!(
        crate::event_control::validate(&p).unwrap_err().kind,
        "resource_budget"
    );
    let mut body = loop_body(0., vec![set(0, c(0.))]);
    let p = program(vec![body.clone()]);
    assert_eq!(
        EventModel::new(p, vec!["u".into()], Tolerances::default())
            .err()
            .unwrap()
            .kind,
        "invalid_ir"
    );
    body["body"] = json!([]);
    body["update"] = json!([set(0, add(s(0), c(-1.)))]);
    let p = program(vec![body]);
    assert_eq!(
        EventModel::new(p, vec!["u".into()], Tolerances::default())
            .err()
            .unwrap()
            .kind,
        "invalid_ir"
    );
}
