//! Local throughput probe, not a simulator comparison or correctness suite.
use evas_kernel::{ir::SCHEMA_VERSION, solver::Circuit};
use serde_json::{json, Value};
use std::hint::black_box;
use std::time::Instant;

fn circuit(kind: &str, size: usize) -> Circuit {
    let mut nodes = vec!["0".to_string(), "u".to_string()];
    nodes.extend((0..size).map(|i| format!("v{i}")));
    let contributions: Vec<_> = (0..size)
        .map(|i| {
            let mut terms = vec![json!({"node": 1, "coefficient": 1.0})];
            match kind {
                "chain" if i > 0 => {
                    terms.push(json!({"node": i + 1, "coefficient": 0.25}));
                }
                "ring" => {
                    terms.push(json!({"node": (i + 1) % size + 2, "coefficient": 0.25}));
                }
                "dense" => {
                    terms.extend(
                        (0..size)
                            .map(|j| json!({"node": j + 2, "coefficient": 0.25 / size as f64})),
                    );
                }
                _ => {}
            }
            let mut rhs = json!({"op": "affine", "constant": 0.0, "terms": terms});
            if kind == "cubic" {
                rhs = json!({"op": "add", "left": rhs, "right": {
                    "op": "multiply",
                    "left": {"op": "affine", "constant": -1.0, "terms": []},
                    "right": {"op": "power", "exponent": 3, "base": {
                        "op": "affine", "constant": 0.0,
                        "terms": [{"node": i + 2, "coefficient": 1.0}]
                    }}
                }});
            }
            json!({
                "branch": {"instance": format!("cell{i:05}"), "local_positive": "a",
                           "local_negative": "r", "kind": "voltage"},
                "positive": i + 2, "negative": 0, "rhs": rhs,
                "origin": {"source": "synthetic", "line": i + 1,
                           "column": 1, "instance": format!("cell{i:05}")}
            })
        })
        .collect();
    let program = serde_json::from_value(json!({
        "schema_version": SCHEMA_VERSION, "nodes": nodes, "contributions": contributions
    }))
    .unwrap();
    Circuit::new(program, &["u".into()], Default::default()).unwrap()
}

fn check(circuit: &Circuit, kind: &str, size: usize, input: f64) {
    let solved = circuit.solve(&[input]).unwrap();
    let mut previous = 0.0;
    for i in 0..size {
        let expected = match kind {
            "chain" => input + 0.25 * previous,
            "dense" | "ring" => input / 0.75,
            "cubic" => {
                let (mut low, mut high) = (-1.0_f64, 1.0_f64);
                for _ in 0..60 {
                    let middle = (low + high) / 2.0;
                    if middle + middle.powi(3) < input {
                        low = middle;
                    } else {
                        high = middle;
                    }
                }
                (low + high) / 2.0
            }
            _ => unreachable!(),
        };
        assert!((solved.voltages[i + 2] - expected).abs() <= 1e-9);
        previous = expected;
    }
}

fn main() {
    let filter = std::env::var("EVAS_BENCH_CASE").unwrap_or_default();
    let samples = std::env::var("EVAS_BENCH_SAMPLES")
        .map(|v| v.parse::<usize>().unwrap())
        .unwrap_or(512);
    assert!(samples > 0);
    let mut records: Vec<Value> = Vec::new();
    for (kind, size) in [
        ("chain", 1),
        ("chain", 16),
        ("chain", 32),
        ("chain", 64),
        ("chain", 128),
        ("chain", 256),
        ("chain", 1024),
        ("ring", 256),
        ("dense", 64),
        ("cubic", 1),
        ("cubic", 16),
        ("cubic", 64),
        ("cubic", 128),
    ] {
        let name = format!("{kind}-{size}");
        if !filter.is_empty() && filter != name {
            continue;
        }
        let model = circuit(kind, size);
        for input in [0.125, -0.25, 0.5, 0.75] {
            check(&model, kind, size, input);
        }
        let mut trials = Vec::new();
        let mut prepare_us = Vec::new();
        let mut first_solve_us = Vec::new();
        for _ in 0..5 {
            // Preparation includes synthetic IR generation/decoding and Circuit::new.
            let start = Instant::now();
            let model = circuit(kind, size);
            prepare_us.push(start.elapsed().as_secs_f64() * 1e6);
            let start = Instant::now();
            black_box(model.solve(black_box(&[0.5])).unwrap());
            first_solve_us.push(start.elapsed().as_secs_f64() * 1e6);
            let start = Instant::now();
            for i in 0..samples {
                let input = [0.125, -0.25, 0.5, 0.75][i % 4];
                black_box(model.solve(black_box(&[input])).unwrap());
            }
            trials.push(start.elapsed().as_secs_f64() * 1e6 / samples as f64);
        }
        records.push(json!({"case": name, "samples_per_trial": samples,
            "prepare_us": prepare_us, "first_solve_us": first_solve_us,
            "solve_us_per_sample": trials}));
    }
    assert!(!records.is_empty(), "unknown EVAS_BENCH_CASE");
    println!(
        "{}",
        json!({"engine_version": env!("CARGO_PKG_VERSION"), "records": records})
    );
}
