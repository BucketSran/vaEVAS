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
