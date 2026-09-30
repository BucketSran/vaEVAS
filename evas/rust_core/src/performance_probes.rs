//! Opt-in local timing, separate from correctness tests and simulator rankings.
use crate::events::EventModel;
use crate::ir::{parse_request, Request};
use crate::operators::Operators;
use crate::pwl::Trajectory;
use crate::solver::Circuit;
use serde_json::{json, Value};
use std::hint::black_box;
use std::time::Instant;

fn measure(action: impl FnOnce()) -> f64 {
    let start = Instant::now();
    action();
    start.elapsed().as_secs_f64()
}

#[test]
#[ignore = "requires frozen EVAS_PROFILE_INPUTS; opt-in local performance probe"]
fn profile_accuracy_components() {
    let path = std::env::var("EVAS_PROFILE_INPUTS").expect("profile input manifest required");
    let inputs: Vec<Value> = serde_json::from_str(&std::fs::read_to_string(path).unwrap()).unwrap();
    for input in inputs {
        let request: Request =
            parse_request(&std::fs::read_to_string(input["path"].as_str().unwrap()).unwrap())
                .unwrap();
        let trajectory =
            Trajectory::new(request.transient.clone().unwrap(), request.driven.len()).unwrap();
        let times = &trajectory.config.output_times;
        // Warm each complete scenario before timing. Parsing/cloning and JSON
        // serialization are outside this in-process kernel measurement.
        crate::run(request.clone()).unwrap();
        for repeat in 0..5 {
            let mut stages = serde_json::Map::new();
            let seconds = measure(|| {
                for &time in times {
                    black_box(trajectory.values(time));
                    black_box(trajectory.value_bounds(time));
                }
            });
            stages.insert("source_values_and_bounds".into(), json!(seconds));
            if request.program.operators.is_empty() {
                let circuit = Circuit::new(
                    request.program.clone(),
                    &request.driven,
                    request.tolerances.clone(),
                )
                .unwrap();
                let sources: Vec<_> = times.iter().map(|&t| trajectory.values(t)).collect();
                let bounds: Vec<_> = times.iter().map(|&t| trajectory.value_bounds(t)).collect();
                let mut solutions = Vec::new();
                let seconds = measure(|| {
                    for values in &sources {
                        let initial = solutions
                            .last()
                            .map(|s: &crate::ir::Solution| s.voltages.as_slice());
                        solutions.push(circuit.solve_with_initial(values, initial).unwrap());
                    }
                });
                stages.insert("nominal_newton".into(), json!(seconds));
                let seconds = measure(|| {
                    for (solution, bounds) in solutions.iter().zip(&bounds) {
                        circuit.check_waveform_accuracy(solution, bounds).unwrap();
                    }
                });
                stages.insert("waveform_certificate".into(), json!(seconds));
            } else {
                let model = EventModel::new(
                    request.program.clone(),
                    request.driven.clone(),
                    request.tolerances.clone(),
                )
                .unwrap();
                let operators =
                    Operators::new(&model.program, &trajectory, &model.driven, &model.initial())
                        .unwrap();
                let seconds = measure(|| {
                    for &time in times {
                        black_box(operators.values(time).unwrap());
                    }
                });
                stages.insert("immutable_operator_values".into(), json!(seconds));
                let seconds = measure(|| {
                    for &time in times {
                        black_box(operators.bounds(time).unwrap());
                    }
                });
                stages.insert("immutable_operator_bounds".into(), json!(seconds));
            }
            let trial = request.clone();
            let start = Instant::now();
            let response = crate::run(trial).unwrap();
            stages.insert(
                "complete_kernel_run".into(),
                json!(start.elapsed().as_secs_f64()),
            );
            assert_eq!(response.solutions.len(), times.len());
            assert!(response
                .solutions
                .iter()
                .all(|s| s.voltages.iter().all(|v| v.is_finite())));
            println!(
                "EVAS_PROFILE {}",
                json!({
                    "case": input["name"], "repeat": repeat, "output_points": times.len(),
                    "stages_s": stages,
                    "response": serde_json::to_value(response).unwrap(),
                })
            );
        }
    }
}
