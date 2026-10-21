use evas_ir::{parse_request, SCHEMA_VERSION};
use serde_json::json;

#[test]
fn requests_round_trip_without_changing_defaults() {
    let value = json!({"program":{"schema_version":SCHEMA_VERSION,"nodes":["0"],"contributions":[]},
                       "driven":[],"samples":[[]]});
    let request = parse_request(&value.to_string()).unwrap();
    let encoded = serde_json::to_string(&request).unwrap();
    let decoded = parse_request(&encoded).unwrap();
    assert_eq!(decoded.program.schema_version, SCHEMA_VERSION);
    assert_eq!(decoded.samples, vec![Vec::<f64>::new()]);
    assert_eq!(decoded.tolerances.absolute, 1e-12);
    assert!(decoded.transient.is_none());
}

#[test]
fn version_precedes_shape_and_duplicate_fields_still_fail() {
    let old = r#"{"program":{"schema_version":1,"contributions":"old shape"}}"#;
    assert_eq!(
        parse_request(old).unwrap_err().kind,
        "unsupported_ir_version"
    );
    let duplicate = format!(
        r#"{{"program":{{"schema_version":{SCHEMA_VERSION},"nodes":["0"],"nodes":["0"],"contributions":[]}},"driven":[],"samples":[[]]}}"#
    );
    assert_eq!(
        parse_request(&duplicate).unwrap_err().kind,
        "invalid_request"
    );
}

#[test]
fn typed_integer_wire_roundtrip_and_distinct_operand_types() {
    let mut value = serde_json::json!({"program":{"schema_version":SCHEMA_VERSION,"nodes":["0"],"contributions":[],
        "states":[{"instance":"dut","name":"n","kind":"integer","initial":0}],
        "events":[{"origin":{"source":"wire.va","line":1,"column":1,"instance":"dut"},"trigger":{"kind":"timer","start":1,"period":1,"time_tolerance":1e-12,"enabled":true},
        "body":[{"kind":"assign","state":0,"rhs":{"op":"integer_primitive","function":"remainder",
        "args":[{"op":"integer_state","state":0},{"op":"integer_literal","value":8}],"origin":{"source":"wire.va","line":1,"column":1,"instance":"dut"}}}]}]},"driven":[],"samples":[]});
    let parsed = parse_request(&value.to_string()).unwrap();
    let again = serde_json::to_value(parsed).unwrap();
    let decoded = parse_request(&again.to_string()).unwrap();
    assert_eq!(serde_json::to_value(decoded).unwrap(), again);
    value["program"]["events"][0]["body"][0]["rhs"]["args"][0] =
        serde_json::json!({"op":"affine","constant":1,"terms":[]});
    assert!(parse_request(&value.to_string()).is_err());
}

#[test]
fn integer28_dynamic_rhs_and_subtract_round_trip_while_ir27_is_rejected() {
    let origin = json!({"source":"wire28.va","line":1,"column":1,"instance":"dut"});
    let operation = json!({"op":"integer_primitive","function":"remainder","origin":origin,
        "args":[{"op":"integer_primitive","function":"subtract","origin":origin,
            "args":[{"op":"integer_state","state":0},{"op":"integer_literal","value":1}]},
            {"op":"integer_state","state":1}]});
    let mut value = json!({"program":{"schema_version":SCHEMA_VERSION,"nodes":["0"],"contributions":[],
        "events":[{"origin":origin,"trigger":{"kind":"initial_step"},"body":[{"kind":"assign","state":0,"rhs":operation}]}]},"driven":[],"samples":[]});
    let parsed = parse_request(&value.to_string()).unwrap();
    let again = serde_json::to_value(parsed).unwrap();
    assert_eq!(again["program"]["events"][0]["body"][0]["rhs"], operation);
    value["program"]["schema_version"] = json!(27);
    assert_eq!(
        parse_request(&value.to_string()).unwrap_err().kind,
        "unsupported_ir_version"
    );
}

#[test]
fn bits29_nested_wire_keeps_source_children_and_rejects_ir28() {
    let origin = json!({"source":"wire29.va","line":1,"column":1,"instance":"dut"});
    let input = json!({"op":"integer_primitive","function":"bit_and","origin":origin,
        "args":[{"op":"integer_primitive","function":"shift_right","origin":origin,
            "args":[{"op":"integer_primitive","function":"add","origin":origin,
                "args":[{"op":"integer_state","state":0},{"op":"integer_literal","value":1}]},
                {"op":"integer_literal","value":-1}]},{"op":"integer_literal","value":0}]});
    let mut v = json!({"program":{"schema_version":SCHEMA_VERSION,"nodes":["0"],"contributions":[],
        "events":[{"origin":origin,"trigger":{"kind":"initial_step"},
            "body":[{"kind":"assign","state":0,"rhs":input}]}]},"driven":[],"samples":[]});
    let parsed = parse_request(&v.to_string()).unwrap();
    assert_eq!(
        serde_json::to_value(parsed).unwrap()["program"]["events"][0]["body"][0]["rhs"],
        input
    );
    v["program"]["schema_version"] = json!(28);
    assert_eq!(
        parse_request(&v.to_string()).unwrap_err().kind,
        "unsupported_ir_version"
    );
}

#[test]
fn forcing30_checked_roles_round_trip_and_old_ir29_is_rejected() {
    // Transport only: this does not grant runtime composition/admission.
    let origin = json!({"source":"wire30.va","line":1,"column":1,"instance":"dut"});
    let forcing = json!({"op":"forcing","origin":origin,
        "value":{"op":"affine","constant":0.,"terms":[{"node":1,"coefficient":1.}]},
        "checked":[{"op":"affine","constant":0.,"terms":[{"node":1,"coefficient":0.}]}]});
    let value = json!({"program":{"schema_version":SCHEMA_VERSION,"nodes":["0","u","y"],
        "contributions":[{"branch":{"instance":"dut","local_positive":"out","local_negative":"ref","kind":"voltage"},
            "positive":2,"negative":0,"rhs":forcing,"origin":origin}]},"driven":["u"],"samples":[[0.25]]});
    let parsed = parse_request(&value.to_string()).unwrap();
    let again = serde_json::to_value(parsed).unwrap();
    assert_eq!(again["program"]["contributions"][0]["rhs"], forcing);
    let decoded = parse_request(&again.to_string()).unwrap();
    assert_eq!(serde_json::to_value(decoded).unwrap(), again);
    let mut old = value.clone();
    old["program"]["schema_version"] = json!(29);
    assert_eq!(
        parse_request(&old.to_string()).unwrap_err().kind,
        "unsupported_ir_version"
    );
    let mut malformed = value;
    malformed["program"]["contributions"][0]["rhs"]["unknown"] = json!(true);
    assert_eq!(
        parse_request(&malformed.to_string()).unwrap_err().kind,
        "invalid_request"
    );
}
