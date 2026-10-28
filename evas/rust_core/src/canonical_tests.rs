//! Constant aliases and constant-zero idt asserts become closed forms (H1).
use super::*;
use serde_json::json;

fn origin() -> serde_json::Value {
    json!({"source":"h1.va","line":1,"column":1,"instance":"dut","expansion":[]})
}

fn constant(value: f64) -> serde_json::Value {
    json!({"op":"affine","constant":value,"terms":[]})
}

fn bind(ordinal: u64, binding: usize, value: serde_json::Value) -> serde_json::Value {
    json!({"expanded_statement_ordinal":ordinal,"action":{"kind":"real_bind","binding":binding,
        "value":{"op":"real_boundary","kind":"snapshot","value":value,"origin":origin()},
        "origin":origin()}})
}

fn gate(ordinal: u64, event: usize) -> serde_json::Value {
    json!({"expanded_statement_ordinal":ordinal,"action":{"kind":"event_gate","event":event}})
}

/// th=0.5*vh (vh=0.1) bound by `steps`; a cross guard V(u)-th; one idt with `reset`.
fn program(steps: Vec<serde_json::Value>, reset: serde_json::Value) -> Program {
    let local = json!({"op":"real_local","binding":0});
    serde_json::from_value(json!({
        "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","u","y"],"states":[],
        "real_bindings":[{"procedure_id":0,"name":"th","origin":origin(),"lifetime":"occurrence"}],
        "procedures":[{"procedure_id":0,"instance":"dut","body":steps}],
        "events":[{"origin":origin(),"body":[],"trigger":{"kind":"cross","direction":1,
            "time_tolerance":1e-12,"expression_tolerance":1e-9,
            "guard":{"op":"add","left":{"op":"affine","constant":0.0,"terms":[{"node":1,"coefficient":1.0}]},
                     "right":{"op":"multiply","left":constant(-1.0),"right":local}}}}],
        "operators":[{"kind":"idt","input":{"op":"affine","constant":0.0,"terms":[{"node":1,"coefficient":1.0}]},
            "ic":0.0,"reset":reset,"origin":origin()}],
        "contributions":[],"step_bounds":[]
    }))
    .unwrap()
}

fn half_of_point_one() -> serde_json::Value {
    json!({"op":"real_binary","operation":"multiply","left":constant(0.5),"right":constant(0.1),
        "origin":origin()})
}

fn guard(p: &Program) -> serde_json::Value {
    let crate::ir::EventTrigger::Cross { guard, .. } = &p.events[0].trigger else {
        panic!("cross")
    };
    serde_json::to_value(guard).unwrap()
}

#[test]
fn constant_alias_before_the_gate_becomes_its_binary64_literal() {
    let mut p = program(
        vec![bind(0, 0, half_of_point_one()), gate(1, 0)],
        constant(1.0),
    );
    request_program(&mut p);
    // RN(0.5*0.1) is the binary64 value 0.05; the guard no longer reads a local.
    assert_eq!(guard(&p)["right"]["right"], constant(0.05));
}

#[test]
fn later_conditional_or_repeated_bindings_stay_procedure_bound() {
    let local = json!({"op":"real_local","binding":0});
    let conditional = json!({"expanded_statement_ordinal":0,"action":{"kind":"procedure_if",
        "relation":"gt","left":constant(1.0),"right":constant(0.0),"origin":origin(),
        "then_body":[bind(1, 0, half_of_point_one())],"else_body":[]}});
    for steps in [
        vec![gate(0, 0), bind(1, 0, half_of_point_one())],
        vec![conditional, gate(2, 0)],
        vec![
            bind(0, 0, half_of_point_one()),
            bind(1, 0, constant(2.0)),
            gate(2, 0),
        ],
        vec![
            bind(
                0,
                0,
                json!({"op":"affine","constant":0.0,"terms":[{"node":1,"coefficient":1.0}]}),
            ),
            gate(1, 0),
        ],
    ] {
        let mut p = program(steps, constant(1.0));
        request_program(&mut p);
        assert_eq!(guard(&p)["right"]["right"], local);
    }
}

#[test]
fn only_a_closed_constant_zero_assert_is_dropped() {
    for (reset, dropped) in [
        (constant(0.0), true),
        (constant(-0.0), true),
        (
            json!({"op":"real_binary","operation":"subtract","left":constant(0.5),"right":constant(0.5),
            "origin":origin()}),
            true,
        ),
        (constant(1.0), false),
        (json!({"op":"state","state":0}), false),
        (
            json!({"op":"affine","constant":0.0,"terms":[{"node":1,"coefficient":0.0}]}),
            false,
        ),
    ] {
        let mut p = program(vec![gate(0, 0)], reset.clone());
        request_program(&mut p);
        let crate::ir::OperatorSpec::Idt { reset: after, .. } = &p.operators[0] else {
            panic!("idt")
        };
        assert_eq!(after.is_none(), dropped, "{reset}");
    }
}
