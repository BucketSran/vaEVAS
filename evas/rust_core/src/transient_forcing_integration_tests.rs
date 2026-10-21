//! Original-program binding and conservative mixed-consumer controls.
//! Every check enters the actual request dispatcher.
use crate::diagnostics::{capture, Options};
use crate::ir::{Expression, Request, StateInitial, Tolerances};
use serde_json::{json, Value};

fn constant(x: f64) -> Value {
    json!({"op":"affine","constant":x,"terms":[]})
}
fn origin() -> Value {
    json!({"source":"forcing-integration-control.va","line":1,"column":1,"instance":"D"})
}
fn input() -> Value {
    json!({"op":"affine","constant":0.,"terms":[{"node":1,"coefficient":1.}]})
}
fn request_value() -> Value {
    let o = origin();
    json!({"program":{
        "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","u","y","metric"],
        "states":[{"instance":"D","name":"q","kind":"integer","initial":0.}],
        "events":[{"origin":o,"trigger":{"kind":"timer","start":0.25,"period":0.,"time_tolerance":1e-12,"enabled":true},
          "body":[{"kind":"assign","state":0,"rhs":constant(1.)}]}],
        "operators":[{"kind":"transition","input":{"op":"state","state":0},"delay":0.,"rise":0.125,"fall":0.125,"origin":o}],
        "contributions":[
          {"branch":{"instance":"D","local_positive":"p","local_negative":"r","kind":"voltage"},"positive":2,"negative":0,"origin":o,
           "rhs":{"op":"forcing","origin":o,"value":input()}},
          {"branch":{"instance":"D","local_positive":"m","local_negative":"r","kind":"voltage"},"positive":3,"negative":0,"origin":o,"rhs":{"op":"operator","operator":0}}
        ]},
        "driven":["u"],"samples":[],"transient":{"pwl":[[[0.,0.],[1.,1.]]],"output_times":[0.,0.125,0.25,0.375,1.],"stop":1.,"max_step":1.}})
}
fn request(v: Value) -> Request {
    // Build Request explicitly: preserve actual current request defaults/schema.
    Request {
        program: serde_json::from_value(v["program"].clone()).unwrap(),
        driven: vec!["u".into()],
        samples: vec![],
        transient: Some(serde_json::from_value(v["transient"].clone()).unwrap()),
        tolerances: Tolerances::default(),
    }
}
fn rejects_scope(v: Value) {
    let error = crate::run(request(v))
        .expect_err("raw Forcing scope must reject before publishing a Response");
    assert_eq!(error.kind, "unsupported_forcing_scope", "{error:?}");
}
fn add_floor(v: &mut Value) {
    // Well-defined nonbinary source expression selects the new Floor consumer.
    v["program"]["events"][0]["body"][0]["rhs"] = json!({"op":"event_math","function":"floor","origin":origin(),"args":[
        {"op":"divide","left":input(),"right":constant(3.)}]});
}
fn add_native(v: &mut Value) {
    v["program"]["operators"][0]["input"] = json!({"op":"integer_primitive","function":"bit_and","origin":origin(),"args":[
        {"op":"integer_state","state":0},{"op":"integer_literal","value":1}]});
}
fn add_slew(v: &mut Value) {
    v["program"]["operators"][0] =
        json!({"kind":"slew","rise":1.,"fall":-1.,"input":input(),"origin":origin()});
}

#[test]
fn raw_forcing_public_entry_accepts_bare_held_transition_control() {
    // Independent values: y(t)=u(t)=t; q steps at .25 and the held Transition
    // reaches one at .375. Check the independent relation and settled endpoints;
    // adoption can add certified-box assertions against the final evidence API.
    let response = crate::run(request(request_value())).unwrap();
    let trace = response.transient.as_ref().unwrap();
    assert_eq!(trace.times.len(), response.solutions.len());
    for (&time, solution) in trace.times.iter().zip(&response.solutions) {
        assert!(
            (solution.voltages[2] - time).abs() <= 1e-10,
            "independent y=t at {time}"
        );
        if time == 0. {
            assert_eq!(solution.voltages[3], 0.);
        }
        if time >= 0.375 {
            assert!((solution.voltages[3] - 1.).abs() <= 1e-10);
        }
        assert!(solution.max_residual_ratio <= 1.);
    }
    for required in [0., 0.125, 0.25, 0.375, 1.] {
        assert!(trace.times.contains(&required));
    }
}
#[test]
fn raw_forcing_rejects_floor_before_shared_owner_or_initialization() {
    let mut v = request_value();
    add_floor(&mut v);
    rejects_scope(v);
}
#[test]
fn raw_forcing_certifies_typed_native_target_with_same_numeric_transition_values() {
    let mut v = request_value();
    add_native(&mut v);
    let result = crate::run(request(v)).unwrap();
    for (row, &time) in result
        .solutions
        .iter()
        .zip(&result.transient.as_ref().unwrap().times)
    {
        assert_eq!(row.voltages[2], time);
        if time == 0. {
            assert_eq!(row.voltages[3], 0.);
        }
        if time >= 0.375 {
            assert_eq!(row.voltages[3], 1.);
        }
    }
}
#[test]
fn raw_forcing_rejects_slew_instead_of_silently_selecting_other_dispatch() {
    let mut v = request_value();
    add_slew(&mut v);
    rejects_scope(v);
}
#[test]
fn raw_forcing_rejects_joint_floor_native_and_slew() {
    let mut v = request_value();
    add_floor(&mut v);
    add_native(&mut v);
    // Preserve native use in Transition; append Slew on another output.
    v["program"]["nodes"]
        .as_array_mut()
        .unwrap()
        .push(json!("slewed"));
    v["program"]["operators"]
        .as_array_mut()
        .unwrap()
        .push(json!({"kind":"slew","rise":1.,"fall":-1.,"input":input(),"origin":origin()}));
    let mut branch = v["program"]["contributions"][1].clone();
    branch["positive"] = json!(4);
    branch["branch"]["local_positive"] = json!("s");
    branch["rhs"] = json!({"op":"operator","operator":1});
    v["program"]["contributions"]
        .as_array_mut()
        .unwrap()
        .push(branch);
    rejects_scope(v);
}
#[test]
fn raw_predicate_initial_resolved_to_same_zero_still_changes_wire_identity() {
    let mut r = request(request_value());
    r.program.states[0].initial = StateInitial::Predicate(Expression::Affine {
        constant: 0.,
        terms: vec![],
    });
    // Semantic initial value is exactly 0 both before/after resolution. Its raw
    // serialized Predicate is nevertheless different from Numeric(0); no
    // prepared-program normalization may erase this source identity mismatch.
    let before = serde_json::to_value(&r.program).unwrap();
    let prepared = crate::initialization::resolve(
        r.program.clone(),
        &r.driven,
        &[crate::interval::Interval::point(0.)],
    )
    .unwrap();
    assert_ne!(before, serde_json::to_value(&prepared).unwrap());
    let error = crate::run(r).expect_err("changed prepared wire must reject");
    assert_eq!(error.kind, "unsupported_forcing_scope");
}
#[test]
fn nonlinear_sibling_cannot_dispatch_around_raw_forcing_health_gate() {
    let mut v = request_value();
    v["program"]["contributions"][1]["rhs"] = json!({"op":"multiply","left":{"op":"operator","operator":0},"right":{"op":"operator","operator":0}});
    // Multiplying a held operator by itself is deliberate nonlinear early-route
    // bait. It is outside the permitted bare-held sibling contract, even though
    // q=0/1 makes its settled values agree with an ordinary Transition output.
    rejects_scope(v);
}
#[test]
fn raw_unused_zero_term_in_predicate_initial_is_not_erased_before_health_audit() {
    let mut r = request(request_value());
    r.program.states[0].initial = StateInitial::Predicate(Expression::Affine {
        constant: 0.,
        terms: vec![crate::ir::Term {
            node: 2,
            coefficient: 0.,
        }],
    });
    // A raw reference to forcing y is forbidden even with zero coefficient and
    // even if initialization would simplify it to the same scalar zero.
    let e = crate::run(r).expect_err("raw role audit must retain zero reference");
    assert_eq!(e.kind, "unsupported_forcing_scope");
}
#[test]
fn unmarked_legacy_public_route_has_no_new_forcing_factory_lookup_or_curve_work() {
    let mut v = request_value();
    v["program"]["contributions"][0]["rhs"] = input();
    let (result, report) = capture(Options::default(), || crate::run(request(v)));
    result.unwrap();
    assert!(
        !report.counters.keys().any(|k| k.starts_with("forcing_")),
        "{:?}",
        report.counters
    );
}

fn event_only_bits() -> Value {
    json!({"op":"integer_primitive","function":"bit_and","origin":origin(),"args":[
        {"op":"integer_primitive","function":"shift_right","origin":origin(),"args":[
            {"op":"integer_literal","value":3},{"op":"integer_literal","value":1}]},
        {"op":"integer_literal","value":1}]})
}
fn bit_assignment() -> Value {
    json!({"kind":"assign","state":0,"rhs":event_only_bits()})
}
#[test]
fn forcing_rejects_eventbody_bits_while_transition_input_is_bare_state() {
    let mut v = request_value();
    v["program"]["events"][0]["body"] = json!([bit_assignment()]);
    assert_eq!(
        v["program"]["operators"][0]["input"],
        json!({"op":"state","state":0})
    );
    // (3 >> 1) & 1 = 1, exactly the legal control's event value. The rejection
    // concerns raw mixed capability scope, not changed numerical behavior.
    rejects_scope(v);
}
#[test]
fn forcing_rejects_eventbody_bits_in_raw_never_selected_arm() {
    let mut v = request_value();
    v["program"]["events"][0]["body"] = json!([{"kind":"if","relation":"gt",
        "left":constant(0.),"right":constant(1.),"then_body":[bit_assignment()],
        "else_body":[{"kind":"assign","state":0,"rhs":constant(1.)}],"origin":origin()}]);
    // All-runtime paths select the legal else arm. Whole raw tree admission
    // must nevertheless reject the hidden typed capability before simplification.
    rejects_scope(v);
}
#[test]
fn forcing_rejects_eventbody_bits_in_raw_zero_trip_loop() {
    let mut v = request_value();
    v["program"]["events"][0]["body"] = json!([
        {"kind":"loop","initialize":[],"relation":"lt","left":constant(0.),"right":constant(0.),
         "body":[bit_assignment()],"update":[],"origin":origin()},
        {"kind":"assign","state":0,"rhs":constant(1.)}]);
    // The loop cannot execute even once; raw capability/role health cannot be
    // inferred from the selected runtime path or post-elaboration event body.
    rejects_scope(v);
}
