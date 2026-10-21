//! Public Rust consumer for the startup history, source gate and clock sample.
use evas_kernel::{
    ir::{Request, SCHEMA_VERSION},
    run,
};
use serde_json::json;
#[path = "../src/history_consumer_fixture.rs"]
mod source_fixture;
use source_fixture::fixture;
#[test]
fn actual_transition_half_edge_and_same_clock_sample() {
    let request: Request = serde_json::from_value(fixture()).unwrap();
    let result =
        run(request).expect("startup history gate must execute through the public Rust consumer");
    assert_eq!(result.solutions.len(), 8);
    let core = [0., 0., 0., 0., 0., 0.625, 0.625, 0.625];
    let sampled = [0., 0., 0., 0., 0., 0., 0.625, 0.625];
    for (i, row) in result.solutions.iter().enumerate() {
        assert!(
            (row.voltages[3] - core[i]).abs() < 1e-9,
            "core at {}: {:?}",
            i,
            row.voltages
        );
        assert!(
            (row.voltages[4] - sampled[i]).abs() < 1e-9,
            "sample at {}: {:?}",
            i,
            row.voltages
        );
        assert!((row.voltages[5] - core[i]).abs() < 1e-9);
    }
}

#[test]
fn history_gate_without_downstream_clamp() {
    let mut value = fixture();
    value["program"]["contributions"][3]["rhs"] =
        json!({"op":"affine","constant":0.,"terms":[{"node":3,"coefficient":1.}]});
    let request: Request = serde_json::from_value(value).unwrap();
    run(request).expect("single source-affine history gate must execute");
}
#[test]
fn history_gate_without_sample_or_clamp() {
    let mut value = fixture();
    value["program"]["events"]
        .as_array_mut()
        .unwrap()
        .truncate(1);
    value["program"]["contributions"][3]["rhs"] =
        json!({"op":"affine","constant":0.,"terms":[{"node":3,"coefficient":1.}]});
    let request: Request = serde_json::from_value(value).unwrap();
    run(request).expect("single history gate without callback sampling must execute");
}

#[test]
fn midpoint_adjacent_floats_preserve_strict_history_comparison() {
    let mut value = fixture();
    let midpoint = 0.625_f64;
    let before = f64::from_bits(midpoint.to_bits() - 1);
    let after = f64::from_bits(midpoint.to_bits() + 1);
    value["transient"]["output_times"] = json!([0., before, midpoint, after, 1.]);
    let result = run(serde_json::from_value(value).unwrap())
        .expect("adjacent queries must not change the physical gate");
    assert_eq!(result.solutions[1].voltages[3], 0.);
    assert_eq!(result.solutions[2].voltages[3], 0.);
    assert!((result.solutions[3].voltages[3] - 0.625).abs() < 1e-10);
}
#[test]
fn invalid_history_graphs_and_masked_domains_are_rejected() {
    for kind in [
        "cycle",
        "double_driver",
        "floating",
        "masked_divisor",
        "bilinear_guard",
        "foreign_state",
        "nonfinite_hidden_arm",
        "unused_non_transition",
    ] {
        let mut value = fixture();
        let node =
            |n: usize| json!({"op":"affine","constant":0.,"terms":[{"node":n,"coefficient":1.}]});
        match kind {
            "cycle" => value["program"]["contributions"][1]["rhs"]["then_value"] = node(5),
            "double_driver" => {
                let mut c = value["program"]["contributions"][1].clone();
                c["branch"]["instance"] = json!("other");
                c["origin"]["instance"] = json!("other");
                c["rhs"] = json!({"op":"affine","constant":1.,"terms":[]});
                value["program"]["contributions"]
                    .as_array_mut()
                    .unwrap()
                    .push(c);
            }
            "floating" => {
                value["program"]["nodes"]
                    .as_array_mut()
                    .unwrap()
                    .push(json!("floating"));
                value["program"]["contributions"][3]["rhs"]["left"] = node(6);
            }
            "masked_divisor" => {
                value["program"]["contributions"][3]["rhs"]["then_value"] = json!({"op":"divide","left":{"op":"affine","constant":1.,"terms":[]},"right":{"op":"affine","constant":0.,"terms":[]}})
            }
            "bilinear_guard" => {
                value["program"]["contributions"][3]["rhs"]["left"] =
                    json!({"op":"multiply","left":node(1),"right":node(2)})
            }
            "nonfinite_hidden_arm" => {
                value["program"]["contributions"][3]["rhs"]["then_value"] = json!({"op":"multiply","left":{"op":"affine","constant":f64::MAX,"terms":[]},"right":{"op":"affine","constant":2.,"terms":[]}})
            }
            "unused_non_transition" => {
                let mut origin = value["program"]["operators"][0]["origin"].clone();
                origin["column"] = json!(2);
                value["program"]["operators"].as_array_mut().unwrap().push(json!({"kind":"abs_delay","input":{"op":"state","state":0},"delay":0.125,"origin":origin}));
            }
            _ => {
                value["program"]["states"]
                    .as_array_mut()
                    .unwrap()
                    .push(json!({"instance":"other","name":"foreign","kind":"real","initial":0.}));
                value["program"]["contributions"][3]["rhs"]["then_value"] =
                    json!({"op":"state","state":2});
            }
        }
        assert!(
            run(serde_json::from_value(value).unwrap()).is_err(),
            "unsupported {kind} was silently admitted"
        );
    }
}

#[test]
fn bilinear_guard_over_live_nodes_is_not_a_readout_output() {
    // Regression control for the readout row route: contributions[3] targets
    // the unread grounded node "top", but its predicate is the product of two
    // live circuit nodes and reads no held state or operator sample. The row
    // route must not own it, so the original refusal must stand.
    let node = |n: usize| json!({"op":"affine","constant":0.,"terms":[{"node":n,"coefficient":1.}]});
    let mut value = fixture();
    value["program"]["contributions"][3]["rhs"]["left"] =
        json!({"op":"multiply","left":node(1),"right":node(2)});
    let error = run(serde_json::from_value(value).unwrap())
        .expect_err("bilinear guard without a held leaf must not be admitted");
    assert!(
        error.message.contains("readout")
            || error.message.contains("affine")
            || error.message.contains("predicate"),
        "unexpected error: {error:?}"
    );
}

#[test]
fn paid_delayed_transition_queue_reaches_the_ordinary_consumer() {
    let mut value = fixture();
    value["program"]["operators"][0]["delay"] = json!(0.0625);
    value["transient"]["output_times"] = json!([0., 0.5, 0.5625, 0.625, 0.6875, 0.71875, 0.75, 1.]);
    let (result, report) = evas_kernel::diagnostics::capture(Default::default(), || {
        run(serde_json::from_value(value).unwrap())
    });
    let result = result.expect("paid held delay queue must preserve physical startup timing");
    let startup = [0., 0., 0., 0.25, 0.5, 0.625, 0.75, 1.];
    let core = [0., 0., 0., 0., 0., 0.625, 0.625, 0.625];
    let sampled = [0., 0., 0., 0., 0., 0., 0.625, 0.625];
    for (i, row) in result.solutions.iter().enumerate() {
        assert_eq!(row.voltages[2], startup[i]);
        assert_eq!(row.voltages[3], core[i]);
        assert_eq!(row.voltages[4], sampled[i]);
        assert_eq!(row.voltages[5], core[i]);
        assert!(row.max_residual_ratio <= 1.);
    }
    assert!(
        report
            .counters
            .get("history_storage_growth")
            .copied()
            .unwrap_or(0)
            > 0
    );
}

// GUARDS: LANG, EVENT-ORDER, TIMED-OPERATOR, COMPOSE.
fn shaped_request() -> serde_json::Value {
    let mut v = fixture();
    let knots: Vec<_> = (0..85)
        .map(|i| json!({"time_numerator":i.to_string(),"time_denominator":"84","value_V":0.5}))
        .collect();
    v["transient"]["pwl_errors_V"] = json!([{"voltage_error_bound_V":1e-12,"exact_knots":knots}]);
    v
}
#[test]
fn public_shaped_range_keeps_actual_history_and_same_clock_sample() {
    let (r, d) = evas_kernel::diagnostics::capture(Default::default(), || {
        run(serde_json::from_value(shaped_request()).unwrap())
    });
    let r = r.unwrap();
    for (i, row) in r.solutions.iter().enumerate() {
        let core = if i >= 5 { 0.625 } else { 0. };
        let sampled = if i >= 6 { 0.625 } else { 0. };
        assert!((row.voltages[3] - core).abs() < 1e-9);
        assert!((row.voltages[4] - sampled).abs() < 1e-9);
        assert!((row.voltages[5] - core).abs() < 1e-9);
        assert!(row.max_residual_ratio <= 1.);
    }
    assert!(d.counters["shaped_range_search_compare"] > 0);
}
#[test]
fn public_shaped_range_preserves_strict_midpoint_adjacent_queries() {
    let mut v = shaped_request();
    let mid = 0.625f64;
    v["transient"]["output_times"] = json!([0., mid.next_down(), mid, mid.next_up(), 1.]);
    let r = run(serde_json::from_value(v).unwrap()).unwrap();
    assert_eq!(r.solutions[1].voltages[3], 0.);
    assert_eq!(r.solutions[2].voltages[3], 0.);
    assert!((r.solutions[3].voltages[3] - 0.625).abs() < 1e-10);
}
