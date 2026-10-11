//! Kernel-only timings; known answers are checked outside each timed region.
use evas_kernel::{
    ir::{Request, SCHEMA_VERSION},
    run,
};
use serde_json::{json, Value};
use std::{hint::black_box, time::Instant};

fn affine(constant: f64, terms: &[(usize, f64)]) -> Value {
    json!({"op":"affine","constant":constant,
           "terms":terms.iter().map(|&(node,coefficient)|json!({"node":node,"coefficient":coefficient})).collect::<Vec<_>>()})
}

fn request(kind: &str, observations: usize) -> Request {
    let origin = json!({"source":"transient-bench","line":1,"column":1,"instance":"dut"});
    let input = affine(0.0, &[(1, 1.0)]);
    let state = json!({"op":"state","state":0});
    let op = json!({"op":"operator","operator":0});
    let mut program = json!({"schema_version":SCHEMA_VERSION,"nodes":["0","u","y"],"contributions":[{
        "branch":{"instance":"dut","local_positive":"a","local_negative":"r","kind":"voltage"},
        "positive":2,"negative":0,"rhs":input,"origin":origin}]});
    let mut pwl = json!([[[0.0, 0.0], [1.0, 1.0]]]);
    match kind {
        "pwl" => {}
        "idt" | "pwl_idt" | "nonlinear_idt" => {
            if kind == "pwl_idt" {
                // A repeated triangular input exposes immutable source-copy
                // costs. Keep half-segment observations, not just zero areas.
                let segments = (observations - 1) / 2;
                assert!(observations == 2 * segments + 1);
                assert!(segments >= 4 && segments.is_power_of_two());
                pwl = json!([(0..=segments)
                    .map(|i| [i as f64 / segments as f64, [0., 1., 0., -1.][i % 4]])
                    .collect::<Vec<_>>()]);
            }
            let (rhs, ic) = if kind != "nonlinear_idt" {
                (input, 0.0)
            } else {
                (
                    json!({"op":"multiply","left":affine(-1.0,&[]),"right":{
                    "op":"power","exponent":2,"base":affine(0.0,&[(2,1.0)])}}),
                    1.0,
                )
            };
            program["contributions"][0]["rhs"] = op;
            program["operators"] = json!([{"kind":"idt","input":rhs,"ic":ic,"origin":origin}]);
        }
        "timer" | "cross" => {
            program["states"] =
                json!([{"instance":"dut","name":"n","kind":"integer","initial":0.0}]);
            program["contributions"][0]["rhs"] = state.clone();
            let trigger = if kind == "timer" {
                json!({"kind":"timer","start":0.125,"period":0.125,"time_tolerance":1e-12,"enabled":true})
            } else {
                pwl = json!([[
                    [0.0, -1.0],
                    [0.25, 1.0],
                    [0.5, -1.0],
                    [0.75, 1.0],
                    [1.0, -1.0]
                ]]);
                json!({"kind":"cross","guard":input,"direction":0,"time_tolerance":1e-12,"expression_tolerance":1e-10})
            };
            program["events"] = json!([{"trigger":trigger,"body":[{"kind":"assign","state":0,
                "rhs":{"op":"add","left":state,"right":affine(1.0,&[])}}],"origin":origin}]);
        }
        _ => unreachable!(),
    }
    serde_json::from_value(json!({"program":program,"driven":["u"],"samples":[],
        "transient":{"pwl":pwl,"output_times":(0..observations).map(|i|i as f64/(observations-1) as f64).collect::<Vec<_>>(),
                     "stop":1.0,"max_step":0.125}})).unwrap()
}

fn main() {
    let count = std::env::var("EVAS_BENCH_OUTPUTS")
        .map(|s| s.parse::<usize>().unwrap())
        .unwrap_or(129);
    assert!(count >= 2);
    let mut records = Vec::new();
    let selected = std::env::var("EVAS_BENCH_CASE").ok();
    let kinds = selected.as_deref().map_or_else(
        || vec!["pwl", "idt", "nonlinear_idt", "timer", "cross"],
        |kind| vec![kind],
    );
    for kind in kinds {
        if let Ok(directory) = std::env::var("EVAS_BENCH_REQUESTS") {
            std::fs::write(
                std::path::Path::new(&directory).join(format!("{kind}-{count}.json")),
                serde_json::to_vec(&request(kind, count)).unwrap(),
            )
            .unwrap();
        }
        let mut trials = Vec::new();
        for _ in 0..5 {
            let input = request(kind, count);
            let start = Instant::now();
            let result = run(input).unwrap();
            trials.push(start.elapsed().as_secs_f64() * 1e6);
            for (i, solution) in result.solutions.iter().enumerate() {
                let t = i as f64 / (count - 1) as f64;
                let expected = match kind {
                    "pwl" => t,
                    "idt" => 0.5 * t * t,
                    "pwl_idt" => {
                        // Integral of one triangle, then its sign reversal.
                        // Each complete four-segment period has zero area.
                        let segments = (count - 1) / 2;
                        let phase = (i % 8) as f64 / 2.;
                        let area = if phase <= 1. {
                            phase * phase / 2.
                        } else if phase <= 3. {
                            1. - (phase - 2.).powi(2) / 2.
                        } else {
                            (phase - 4.).powi(2) / 2.
                        };
                        area / segments as f64
                    }
                    "nonlinear_idt" => 1.0 / (1.0 + t),
                    "timer" => (8.0 * t).floor(),
                    "cross" => [0.125, 0.375, 0.625, 0.875]
                        .iter()
                        .filter(|&&event| event <= t)
                        .count() as f64,
                    _ => unreachable!(),
                };
                assert!(
                    (solution.voltages[2] - expected).abs() < 1e-9,
                    "{kind} at {t}"
                );
            }
            black_box(result);
        }
        records.push(json!({"case":kind,"observations":count,"run_us":trials}));
    }
    println!(
        "{}",
        json!({"engine_version":env!("CARGO_PKG_VERSION"),"records":records})
    );
}
