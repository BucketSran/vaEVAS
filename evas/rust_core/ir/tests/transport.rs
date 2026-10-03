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
