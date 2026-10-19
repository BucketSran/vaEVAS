//! Real disposable candidate failures at the final provider-binding seam.
use super::*;
use crate::ir::{Expression as E, Program, Tolerances};
use serde_json::json;

fn fixture() -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    fixture_mode(false)
}
fn fixture_mode(shaped: bool) -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    fixture_options(shaped, false)
}
fn fixture_options(
    shaped: bool,
    polynomial: bool,
) -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    let origin = json!({"source":"synthetic_forcing.va","line":1,"column":1,"instance":"dut"});
    let mut p: Program = serde_json::from_value(json!({
        "schema_version":SCHEMA_VERSION,"nodes":["0","u","y","metric"],
        "states":[{"instance":"dut","name":"q","kind":"integer","initial":0}],
        "events":[{"origin":origin,"trigger":{"kind":"timer","start":0.25,"period":0,
            "time_tolerance":1e-12,"enabled":true},"body":[{"kind":"assign","state":0,
            "rhs":{"op":"affine","constant":1,"terms":[]}}]}],
        "operators":[{"kind":"transition","input":{"op":"state","state":0},
            "delay":0,"rise":0.125,"fall":0.125,"origin":origin}],
        "contributions":[
          {"branch":{"instance":"dut","local_positive":"p","local_negative":"r","kind":"voltage"},
            "positive":2,"negative":0,"origin":origin,"rhs":{"op":"forcing","origin":origin,
              "value":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]}}},
          {"branch":{"instance":"dut","local_positive":"m","local_negative":"r","kind":"voltage"},
            "positive":3,"negative":0,"origin":origin,"rhs":{"op":"operator","operator":0}}
        ]
    }))
    .unwrap();
    if polynomial {
        let E::Forcing { value, .. } = &mut p.contributions[0].rhs else {
            unreachable!()
        };
        **value = E::Multiply {
            left: value.clone(),
            right: value.clone(),
        };
        let mut residual = p.contributions[0].clone();
        residual.rhs = E::Operator { operator: 0 };
        p.contributions.push(residual);
    }
    if shaped {
        let E::Forcing { value, .. } = &mut p.contributions[0].rhs else {
            unreachable!()
        };
        **value = serde_json::from_value(json!({"op":"select","relation":"gt",
            "left":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]},
            "right":{"op":"affine","constant":0.5,"terms":[]},
            "then_value":{"op":"affine","constant":0.75,"terms":[]},
            "else_value":{"op":"affine","constant":0.25,"terms":[]},"origin":origin}))
        .unwrap();
    }
    let mut config =
        json!({"pwl":[[[0,0],[1,1]]],"output_times":[0,0.125,0.25,1],"stop":1,"max_step":1});
    if polynomial {
        config["pwl"] = json!([[[0, 0.25], [1, 1.25]]]);
    }
    if shaped {
        config["pwl_errors_V"] = json!([{"voltage_error_bound_V":0.03125,"exact_knots":[
        {"time_numerator":"0","time_denominator":"1","value_V":0},
        {"time_numerator":"1","time_denominator":"1","value_V":0.984375}]}]);
    }
    let t = Trajectory::new(serde_json::from_value(config).unwrap(), 1).unwrap();
    let driven = vec!["u".to_string()];
    let tol = Tolerances {
        absolute: 1e-10,
        relative: 1e-10,
    };
    fixture_from_original(p, t, driven, tol, false)
}
fn fixture_from_original(
    mut p: Program,
    t: Trajectory,
    driven: Vec<String>,
    tol: Tolerances,
    composed: bool,
) -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    let graph = crate::forcing_graph::Graph::partition(&mut p, &t, &driven, &tol)
        .unwrap()
        .unwrap();
    let mut model = if composed {
        EventModel::new_with_forcing(p, driven, tol, &t, graph.prepare_execution().unwrap())
            .unwrap()
    } else {
        EventModel::new(p, driven, tol).unwrap()
    };
    model.forcing = Some(graph.clone());
    let states = model.initial();
    let state_bounds: Vec<_> = states.iter().copied().map(I::point).collect();
    let mut operators = if composed && graph.requires_composed_history() {
        Operators::new_until_with_forcing_execution(
            &model.program,
            &t,
            &model.driven,
            &states,
            if model.typed_transition_targets.is_empty() {
                None
            } else {
                Some(&state_bounds)
            },
            &model.typed_transition_targets,
            1.,
            &model.tolerances,
            graph.prepare_execution().unwrap(),
        )
    } else {
        Operators::new_until_with_source_context(
            &model.program,
            &t,
            &model.driven,
            &states,
            1.,
            &model.tolerances,
            Some(
                graph
                    .source_context(&model.program, &t, &model.driven)
                    .unwrap(),
            ),
        )
    }
    .unwrap();
    operators
        .bind_forcing_context(
            graph
                .source_context(&model.program, &t, &model.driven)
                .unwrap(),
        )
        .unwrap();
    assert!(
        operators.local_epoch().is_none(),
        "admitted forcing has no continuous provider"
    );
    let mut circuit = model
        .circuit_with(&states, &operators.values(0.).unwrap())
        .unwrap();
    let mut solution = circuit.solve(&t.values(0.)).unwrap();
    let inputs = t.value_bounds(0.);
    let (_, boxes) = model
        .certify_observation(
            &model.conditions.select(&[], &inputs).unwrap(),
            &inputs,
            &state_bounds,
            &operators.bounds(0.).unwrap(),
            &solution.voltages,
            &states,
        )
        .unwrap();
    crate::observation::retain_bounds(&mut solution, boxes);
    graph.project(0., &t, &mut solution, &mut circuit).unwrap();
    let accepted = Frame {
        value_proofs: Default::default(),
        time_proofs: Default::default(),
        time: 0.,
        states,
        state_bounds,
        solution,
        circuit,
        operators,
    };
    let calendar = independent_schedule(&model, &t).unwrap();
    let outputs = vec![accepted.clone()];
    (
        model,
        t,
        Controller {
            accepted,
            event: 0,
            records: vec![],
            outputs,
        },
        calendar,
    )
}

fn unchanged_structure(a: &Frame, b: &Frame) {
    assert_eq!(a.time, b.time);
    assert_eq!(a.states, b.states);
    assert_eq!(a.state_bounds, b.state_bounds);
    assert_eq!(a.value_proofs, b.value_proofs);
    assert_eq!(a.time_proofs, b.time_proofs);
    assert_eq!(
        serde_json::to_value(&a.solution).unwrap(),
        serde_json::to_value(&b.solution).unwrap()
    );
    assert_eq!(
        a.circuit.forcing_frame_snapshot(),
        b.circuit.forcing_frame_snapshot()
    );
    assert!(a.operators.same_reset_history(&b.operators));
    assert!(a.operators.same_forcing_frame(&b.operators));
}
fn unchanged(a: &Frame, b: &Frame) {
    unchanged_structure(a, b);
    for t in [0., 0.25, 0.3125, 0.5, 1.] {
        assert_eq!(
            a.operators.values(t).unwrap(),
            b.operators.values(t).unwrap()
        );
        assert_eq!(
            a.operators.bounds(t).unwrap(),
            b.operators.bounds(t).unwrap()
        );
    }
}

#[test]
fn forcing_two_late_provider_failures_preserve_full_frame_then_retry() {
    let (model, t, mut c, mut calendar) = fixture();
    let before = c.accepted.clone();
    let prior = c.outputs.clone();
    let signature = calendar
        .iter()
        .map(|e| (e.event, e.time, e.bounds()))
        .collect::<Vec<_>>();
    // Same valid legacy circuit/calendar, foreign physical request binding:
    // closure, replay, history and reduced solve precede Graph::project.
    let mut config = t.config.clone();
    config.pwl[0][1][1] = 0.5;
    let foreign = Trajectory::new(config, 1).unwrap();
    let graph = model.forcing.as_ref().unwrap();
    let mut paid = graph.work_used();
    for _ in 0..2 {
        let (result, report) = crate::diagnostics::capture(Default::default(), || {
            c.accept_changed_events(
                &model,
                &foreign,
                &mut calendar,
                event_acceptance::Strategy::Static,
            )
        });
        assert_eq!(result.unwrap_err().kind, "unsupported_forcing_scope");
        assert!(
            report
                .stages
                .get("controller.prepare_candidate")
                .unwrap()
                .calls
                > 0
        );
        assert!(
            report
                .counters
                .get("forcing_history_queue_copy")
                .copied()
                .unwrap_or(0)
                > 0
        );
        assert!(graph.work_used() > paid);
        paid = graph.work_used();
        unchanged(&c.accepted, &before);
        assert_eq!(c.event, 0);
        assert!(c.records.is_empty());
        assert_eq!(c.outputs.len(), prior.len());
        for (a, b) in c.outputs.iter().zip(&prior) {
            unchanged(a, b);
        }
        assert_eq!(
            signature,
            calendar
                .iter()
                .map(|e| (e.event, e.time, e.bounds()))
                .collect::<Vec<_>>()
        );
    }
    c.accept_changed_events(
        &model,
        &t,
        &mut calendar,
        event_acceptance::Strategy::Static,
    )
    .unwrap();
    let (clean_model, clean_t, mut clean, mut clean_calendar) = fixture();
    clean
        .accept_changed_events(
            &clean_model,
            &clean_t,
            &mut clean_calendar,
            event_acceptance::Strategy::Static,
        )
        .unwrap();
    assert_eq!(
        signature,
        calendar
            .iter()
            .map(|e| (e.event, e.time, e.bounds()))
            .collect::<Vec<_>>()
    );
    assert_eq!(c.outputs.len(), clean.outputs.len());
    assert_eq!(
        c.outputs.iter().map(|f| f.time).collect::<Vec<_>>(),
        [0.125]
    );
    for (a, b) in c.outputs.iter().zip(&clean.outputs) {
        assert_eq!(a.time, b.time);
        assert_eq!(a.states, b.states);
        assert_eq!(a.state_bounds, b.state_bounds);
        assert_eq!(
            serde_json::to_value(&a.solution).unwrap(),
            serde_json::to_value(&b.solution).unwrap()
        );
        assert!(a.operators.same_reset_history(&b.operators));
    }
    assert_eq!(c.event, clean.event);
    assert_eq!(c.event, 1);
    assert_eq!(c.accepted.states, [1.]);
    assert_eq!(c.accepted.time, 0.25);
    assert_eq!(
        c.accepted.solution.voltages,
        clean.accepted.solution.voltages
    );
    assert_eq!(c.accepted.state_bounds, clean.accepted.state_bounds);
    assert_eq!(c.accepted.value_proofs, clean.accepted.value_proofs);
    assert!(c
        .accepted
        .operators
        .same_reset_history(&clean.accepted.operators));
    assert_eq!(
        serde_json::to_value(&c.records).unwrap(),
        serde_json::to_value(&clean.records).unwrap()
    );
    for t in [0.25, 0.3125, 0.375, 1.] {
        assert_eq!(
            c.accepted.operators.values(t).unwrap(),
            clean.accepted.operators.values(t).unwrap()
        );
        assert_eq!(
            c.accepted.operators.bounds(t).unwrap(),
            clean.accepted.operators.bounds(t).unwrap()
        );
    }
}

#[test]
fn forcing_reduction_token_rejects_any_changed_preserved_execution_identity() {
    let (model, t, _, _) = fixture();
    let graph = model.forcing.as_ref().unwrap();
    let value = serde_json::to_value(&model.program).unwrap();
    for pointer in [
        "/states/0/initial",
        "/events/0/body/0/rhs/constant",
        "/operators/0/rise",
        "/contributions/0/rhs/constant",
    ] {
        let mut foreign = value.clone();
        *foreign.pointer_mut(pointer).unwrap() = json!(0.5);
        let program = serde_json::from_value(foreign).unwrap();
        assert_eq!(
            graph
                .source_context(&program, &t, &model.driven)
                .err()
                .unwrap()
                .kind,
            "unsupported_forcing_scope"
        );
    }
    assert!(graph
        .source_context(&model.program, &t, &model.driven)
        .is_ok());
}

#[test]
fn forcing_shaped_two_late_provider_failures_preserve_full_frame_then_retry() {
    let (model, t, mut c, mut calendar) = fixture_mode(true);
    let before = c.accepted.clone();
    let prior = c.outputs.clone();
    let signature = calendar
        .iter()
        .map(|e| (e.event, e.time, e.bounds()))
        .collect::<Vec<_>>();
    // Same valid legacy circuit/calendar, foreign physical request binding:
    // closure, replay, history and reduced solve precede Graph::project.
    let mut config = t.config.clone();
    let crate::ir::SourceError::Shaped(shape) = &mut config.pwl_errors_v.as_mut().unwrap()[0]
    else {
        unreachable!()
    };
    shape.exact_knots[1].value_v = 0.96875; // Same nominal PWL+stop and band, distinct valid physical curve.
    let foreign = Trajectory::new(config, 1).unwrap();
    let graph = model.forcing.as_ref().unwrap();
    let mut paid = graph.work_used();
    for _ in 0..2 {
        let (result, report) = crate::diagnostics::capture(Default::default(), || {
            c.accept_changed_events(
                &model,
                &foreign,
                &mut calendar,
                event_acceptance::Strategy::Static,
            )
        });
        assert_eq!(result.unwrap_err().kind, "unsupported_forcing_scope");
        assert!(
            report
                .stages
                .get("controller.prepare_candidate")
                .unwrap()
                .calls
                > 0
        );
        assert!(
            report
                .counters
                .get("forcing_history_queue_copy")
                .copied()
                .unwrap_or(0)
                > 0
        );
        assert!(graph.work_used() > paid);
        paid = graph.work_used();
        unchanged(&c.accepted, &before);
        assert_eq!(c.event, 0);
        assert!(c.records.is_empty());
        assert_eq!(c.outputs.len(), prior.len());
        for (a, b) in c.outputs.iter().zip(&prior) {
            unchanged(a, b);
        }
        assert_eq!(
            signature,
            calendar
                .iter()
                .map(|e| (e.event, e.time, e.bounds()))
                .collect::<Vec<_>>()
        );
    }
    c.accept_changed_events(
        &model,
        &t,
        &mut calendar,
        event_acceptance::Strategy::Static,
    )
    .unwrap();
    let (clean_model, clean_t, mut clean, mut clean_calendar) = fixture_mode(true);
    clean
        .accept_changed_events(
            &clean_model,
            &clean_t,
            &mut clean_calendar,
            event_acceptance::Strategy::Static,
        )
        .unwrap();
    assert_eq!(
        signature,
        calendar
            .iter()
            .map(|e| (e.event, e.time, e.bounds()))
            .collect::<Vec<_>>()
    );
    assert_eq!(c.outputs.len(), clean.outputs.len());
    assert_eq!(
        c.outputs.iter().map(|f| f.time).collect::<Vec<_>>(),
        [0.125]
    );
    for (a, b) in c.outputs.iter().zip(&clean.outputs) {
        assert_eq!(a.time, b.time);
        assert_eq!(a.states, b.states);
        assert_eq!(a.state_bounds, b.state_bounds);
        assert_eq!(
            serde_json::to_value(&a.solution).unwrap(),
            serde_json::to_value(&b.solution).unwrap()
        );
        assert!(a.operators.same_reset_history(&b.operators));
    }
    assert_eq!(c.event, clean.event);
    assert_eq!(c.event, 1);
    assert_eq!(c.accepted.states, [1.]);
    assert_eq!(c.accepted.time, 0.25);
    assert_eq!(
        c.accepted.solution.voltages,
        clean.accepted.solution.voltages
    );
    assert_eq!(c.accepted.state_bounds, clean.accepted.state_bounds);
    assert_eq!(c.accepted.value_proofs, clean.accepted.value_proofs);
    assert!(c
        .accepted
        .operators
        .same_reset_history(&clean.accepted.operators));
    assert_eq!(
        serde_json::to_value(&c.records).unwrap(),
        serde_json::to_value(&clean.records).unwrap()
    );
    for t in [0.25, 0.3125, 0.375, 1.] {
        assert_eq!(
            c.accepted.operators.values(t).unwrap(),
            clean.accepted.operators.values(t).unwrap()
        );
        assert_eq!(
            c.accepted.operators.bounds(t).unwrap(),
            clean.accepted.operators.bounds(t).unwrap()
        );
    }
}

#[test]
fn forcing_shaped_natural_work_exhaustion_then_same_controller_two_retries() {
    let (model, t, mut c, mut calendar) = fixture_mode(true);
    let before = c.accepted.clone();
    let prior = c.outputs.clone();
    let signature = calendar
        .iter()
        .map(|e| (e.event, e.time, e.bounds()))
        .collect::<Vec<_>>();
    let graph = model.forcing.as_ref().unwrap();
    graph.exhaust_physical_reads_for_test();
    for _ in 0..2 {
        let paid = graph.work_used();
        let (result, report) = crate::diagnostics::capture(Default::default(), || {
            c.accept_changed_events(
                &model,
                &t,
                &mut calendar,
                event_acceptance::Strategy::Static,
            )
        });
        assert_eq!(result.unwrap_err().kind, "step_budget");
        assert_eq!(
            report
                .counters
                .get("forcing_curve_actual_point_calls")
                .copied()
                .unwrap_or(0),
            0
        );
        assert_eq!(graph.work_used(), paid);
        unchanged(&before, &c.accepted);
        assert_eq!(c.event, 0);
        assert!(c.records.is_empty());
        assert_eq!(prior.len(), c.outputs.len());
        for (a, b) in prior.iter().zip(&c.outputs) {
            unchanged(a, b);
        }
        assert_eq!(
            signature,
            calendar
                .iter()
                .map(|e| (e.event, e.time, e.bounds()))
                .collect::<Vec<_>>()
        );
    }
}

#[test]
fn forcing_owned_natural_work_exhaustion_then_same_controller_two_retries() {
    let (model, t, mut c, mut calendar) = fixture_mode(true);
    let before = c.accepted.clone();
    let prior = c.outputs.clone();
    let signature = calendar
        .iter()
        .map(|e| (e.event, e.time, e.bounds()))
        .collect::<Vec<_>>();
    let graph = model.forcing.as_ref().unwrap();
    graph.exhaust_physical_reads_at_for_test(0.5);
    for _ in 0..2 {
        let paid = graph.work_used();
        let (result, report) = crate::diagnostics::capture(Default::default(), || {
            c.accept_changed_events(
                &model,
                &t,
                &mut calendar,
                event_acceptance::Strategy::Static,
            )
        });
        assert_eq!(result.unwrap_err().kind, "step_budget");
        assert_eq!(
            report
                .counters
                .get("forcing_curve_actual_point_calls")
                .copied()
                .unwrap_or(0),
            0
        );
        assert_eq!(report.counters.get("forcing_prefix_calendar_root"), None);
        assert_eq!(report.counters.get("forcing_owned_cross_comparisons"), None);
        assert_eq!(
            report.counters.get("forcing_owned_integer_conversions"),
            None
        );
        assert_eq!(report.counters.get("forcing_owned_interpolations"), None);
        assert_eq!(graph.work_used(), paid);
        unchanged(&before, &c.accepted);
        assert_eq!(c.event, 0);
        assert!(c.records.is_empty());
        assert_eq!(prior.len(), c.outputs.len());
        for (a, b) in prior.iter().zip(&c.outputs) {
            unchanged(a, b);
        }
        assert_eq!(
            signature,
            calendar
                .iter()
                .map(|e| (e.event, e.time, e.bounds()))
                .collect::<Vec<_>>()
        );
    }
}

#[test]
fn forcing_actual_calendar_prefix_and_physical_work_share_original_quota_and_retry_frame() {
    let (model, t, mut c, mut calendar) = fixture_mode(true);
    assert!(model.source_context.is_none());
    let graph = model.forcing.as_ref().unwrap();
    let before = c.accepted.clone();
    let outputs = c.outputs.clone();
    let signature = calendar
        .iter()
        .map(|e| (e.event, e.time, e.bounds()))
        .collect::<Vec<_>>();
    let mut actual_prepares = 0;
    let mut exact_clocks = 0;
    let mut physical_reads = 0;
    loop {
        let (result, report) = crate::diagnostics::capture(Default::default(), || {
            c.prepare_events_until(&model, &t, &calendar, None)
        });
        exact_clocks += report
            .counters
            .get("forcing_prefix_clock_helpers")
            .copied()
            .unwrap_or(0);
        physical_reads += report
            .counters
            .get("forcing_curve_actual_point_calls")
            .copied()
            .unwrap_or(0)
            + report
                .counters
                .get("forcing_owned_point_success")
                .copied()
                .unwrap_or(0);
        match result {
            Ok(_) => {
                actual_prepares += 1;
                assert!(actual_prepares < 100_000);
            }
            Err(error) => {
                assert_eq!(error.kind, "step_budget");
                break;
            }
        }
    }
    assert!(
        actual_prepares > 0 && exact_clocks > 0 && physical_reads > 0,
        "prepares={actual_prepares},clocks={exact_clocks},physical_reads={physical_reads}"
    );
    assert!(graph.work_used() > 1_000_000_000);
    println!("natural_combined_calendar_prepares={actual_prepares},clock_helpers={exact_clocks},physical_reads={physical_reads},work={} original_limit=1000000000",graph.work_used());
    for _ in 0..2 {
        let paid = graph.work_used();
        let (result, report) = crate::diagnostics::capture(Default::default(), || {
            c.accept_changed_events(
                &model,
                &t,
                &mut calendar,
                event_acceptance::Strategy::Static,
            )
        });
        assert_eq!(result.unwrap_err().kind, "step_budget");
        assert!(!report
            .counters
            .keys()
            .any(|k| k.starts_with("forcing_prefix_")
                || k.starts_with("forcing_owned_")
                || *k == "forcing_curve_actual_point_calls"));
        assert_eq!(graph.work_used(), paid);
        unchanged(&before, &c.accepted);
        assert_eq!(c.event, 0);
        assert!(c.records.is_empty());
        assert_eq!(outputs.len(), c.outputs.len());
        for (a, b) in outputs.iter().zip(&c.outputs) {
            unchanged(a, b);
        }
        assert_eq!(
            signature,
            calendar
                .iter()
                .map(|e| (e.event, e.time, e.bounds()))
                .collect::<Vec<_>>()
        );
    }
}

#[test]
fn forcing_polynomial_same_branch_natural_budget_and_two_retries_preserve_full_frame() {
    let (model, t, mut c, mut calendar) = fixture_options(false, true);
    assert!(model.source_context.is_none());
    let graph = model.forcing.as_ref().unwrap();
    let before = c.accepted.clone();
    let outputs = c.outputs.clone();
    let signature = calendar
        .iter()
        .map(|e| (e.event, e.time, e.bounds()))
        .collect::<Vec<_>>();
    let mut actual_prepares = 0;
    let mut exact_clocks = 0;
    let mut physical_reads = 0;
    loop {
        let (result, report) = crate::diagnostics::capture(Default::default(), || {
            c.prepare_events_until(&model, &t, &calendar, None)
        });
        exact_clocks += report
            .counters
            .get("forcing_prefix_clock_helpers")
            .copied()
            .unwrap_or(0);
        physical_reads += report
            .counters
            .get("forcing_project_source_samples")
            .copied()
            .unwrap_or(0);
        match result {
            Ok(_) => {
                actual_prepares += 1;
                assert!(actual_prepares < 100_000);
            }
            Err(error) => {
                assert_eq!(error.kind, "step_budget");
                break;
            }
        }
    }
    assert!(
        actual_prepares > 0 && exact_clocks > 0 && physical_reads > 0,
        "prepares={actual_prepares},clocks={exact_clocks},physical_reads={physical_reads}"
    );
    assert!(graph.work_used() > 1_000_000_000);
    println!("natural_combined_calendar_prepares={actual_prepares},clock_helpers={exact_clocks},physical_reads={physical_reads},work={} original_limit=1000000000",graph.work_used());
    for _ in 0..2 {
        let paid = graph.work_used();
        let (result, report) = crate::diagnostics::capture(Default::default(), || {
            c.accept_changed_events(
                &model,
                &t,
                &mut calendar,
                event_acceptance::Strategy::Static,
            )
        });
        assert_eq!(result.unwrap_err().kind, "step_budget");
        assert!(!report
            .counters
            .keys()
            .any(|k| k.starts_with("forcing_prefix_")
                || k.starts_with("forcing_owned_")
                || *k == "forcing_curve_actual_point_calls"));
        assert_eq!(graph.work_used(), paid);
        unchanged(&before, &c.accepted);
        assert_eq!(c.event, 0);
        assert!(c.records.is_empty());
        assert_eq!(outputs.len(), c.outputs.len());
        for (a, b) in outputs.iter().zip(&c.outputs) {
            unchanged(a, b);
        }
        assert_eq!(
            signature,
            calendar
                .iter()
                .map(|e| (e.event, e.time, e.bounds()))
                .collect::<Vec<_>>()
        );
    }
}

#[test]
fn forcing_polynomial_same_phase_is_idempotent_but_new_state_uses_fresh_circuit() {
    let (model, t, mut controller, _) = fixture_options(false, true);
    let before = controller.accepted.clone();
    let graph = model.forcing.as_ref().unwrap();
    graph
        .project(
            0.,
            &t,
            &mut controller.accepted.solution,
            &mut controller.accepted.circuit,
        )
        .unwrap();
    unchanged(&before, &controller.accepted);
    assert_eq!(controller.accepted.solution.voltages[2], 0.0625);
    // Same timestamp with a changed held state gets a new residual circuit.
    let states = vec![1.];
    let mut circuit = model.circuit_with(&states, &[1.]).unwrap();
    let mut solution = circuit.solve(&t.values(0.)).unwrap();
    let (_, boxes) = model
        .certify_observation(
            &model.conditions.select(&[], &t.value_bounds(0.)).unwrap(),
            &t.value_bounds(0.),
            &[I::ONE],
            &[I::ONE],
            &solution.voltages,
            &states,
        )
        .unwrap();
    crate::observation::retain_bounds(&mut solution, boxes);
    graph.project(0., &t, &mut solution, &mut circuit).unwrap();
    assert_eq!(solution.voltages[2], 1.0625);
    assert_eq!(solution.voltages[3], 1.);
    unchanged(&before, &controller.accepted);
}

#[test]
fn forcing_prepared_execution_preserves_original_owner_and_rejects_rebinding() {
    let (model, t, _, _) = fixture_options(false, true);
    let graph = model.forcing.as_ref().unwrap();
    let prepare = || graph.prepare_execution().unwrap();
    let composed = EventModel::new_with_forcing(
        model.program.clone(),
        model.driven.clone(),
        model.tolerances.clone(),
        &t,
        prepare(),
    )
    .unwrap();
    let original_context = graph
        .source_context(&model.program, &t, &model.driven)
        .unwrap();
    assert!(std::sync::Arc::ptr_eq(
        composed.source_context.as_ref().unwrap(),
        &original_context
    ));
    let mut changed = model.program.clone();
    changed.contributions[0].origin.line += 1;
    let error = EventModel::new_with_forcing(
        changed,
        model.driven.clone(),
        model.tolerances.clone(),
        &t,
        prepare(),
    )
    .err()
    .unwrap();
    assert_eq!(error.kind, "unsupported_forcing_scope");
    let mut other_provider = t.clone();
    other_provider.config.stop = 0.75;
    let error = EventModel::new_with_forcing(
        model.program.clone(),
        model.driven.clone(),
        model.tolerances.clone(),
        &other_provider,
        prepare(),
    )
    .err()
    .unwrap();
    assert_eq!(error.kind, "unsupported_forcing_scope");
    let error = EventModel::new_with_forcing(
        model.program.clone(),
        vec!["metric".into()],
        model.tolerances.clone(),
        &t,
        prepare(),
    )
    .err()
    .unwrap();
    assert_eq!(error.kind, "unsupported_forcing_scope");
    // A source Arc alone is insufficient. The old generic entry must retain
    // exact original-program binding and cannot impersonate this reduction.
    let error = EventModel::new_with_context(
        model.program.clone(),
        model.driven.clone(),
        model.tolerances.clone(),
        Some(&t),
        Some(original_context),
    )
    .err()
    .unwrap();
    assert_eq!(error.kind, "invalid_ir");
}

fn fixture_sampled_history() -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    fixture_sampled_history_mode(false)
}
fn fixture_sampled_history_mode(
    selected: bool,
) -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    let (model, t, _, _) = fixture_options(false, true);
    let context = model
        .forcing
        .as_ref()
        .unwrap()
        .source_context(&model.program, &t, &model.driven)
        .unwrap();
    let mut raw = serde_json::to_value(context.original_binding().0).unwrap();
    raw["states"]
        .as_array_mut()
        .unwrap()
        .push(json!({"instance":"dut","name":"sample","kind":"real","initial":0}));
    let mut target = raw["operators"][0].clone();
    target["input"] = if selected {
        json!({"op":"select","relation":"gt",
        "left":{"op":"affine","constant":0,"terms":[{"node":3,"coefficient":1}]},
        "right":{"op":"affine","constant":0.25,"terms":[]},
        "then_value":{"op":"affine","constant":1,"terms":[]},
        "else_value":{"op":"affine","constant":0,"terms":[]},"origin":target["origin"].clone()})
    } else {
        json!({"op":"state","state":1})
    };
    target["origin"]["line"] = json!(2);
    raw["operators"].as_array_mut().unwrap().push(target);
    let mut event = raw["events"][0].clone();
    event["trigger"]["start"] = json!(0.3125);
    event["origin"]["line"] = json!(3);
    event["body"] = json!([{"kind":"assign","state":1,"rhs":{"op":"affine","constant":0,"terms":[{"node":3,"coefficient":1}]}}]);
    raw["events"].as_array_mut().unwrap().push(event);
    raw["contributions"][0]["rhs"]["checked"] =
        json!([{"op":"affine","constant":0,"terms":[{"node":3,"coefficient":0}]}]);
    raw["contributions"][2]["rhs"] = json!({"op":"operator","operator":1});
    fixture_from_original(
        serde_json::from_value(raw).unwrap(),
        t,
        model.driven,
        model.tolerances,
        true,
    )
}

#[test]
fn forcing_sampled_history_natural_budget_two_retries_preserve_full_frame() {
    sampled_history_budget(false);
}

#[test]
fn forcing_selected_history_natural_budget_two_retries_preserve_full_frame() {
    sampled_history_budget(true);
}
fn sampled_history_budget(selected: bool) {
    let (model, t, mut c, mut calendar) = fixture_sampled_history_mode(selected);
    let graph = model.forcing.as_ref().unwrap();
    assert!(std::sync::Arc::ptr_eq(
        model.source_context.as_ref().unwrap(),
        &graph
            .source_context(&model.program, &t, &model.driven)
            .unwrap()
    ));
    // Accept the parent change, then repeatedly prepare the physical mid-ramp
    // sampling event on disposable candidates under this same original Work.
    c.accept_changed_events(
        &model,
        &t,
        &mut calendar,
        event_acceptance::Strategy::Static,
    )
    .unwrap();
    assert_eq!(c.accepted.states, [1., 0.]);
    let before = c.accepted.clone();
    let outputs = c.outputs.clone();
    let event = c.event;
    let records = serde_json::to_value(&c.records).unwrap();
    let signature: Vec<_> = calendar
        .iter()
        .map(|e| (e.event, e.time, e.bounds()))
        .collect();
    let mut prepares = 0;
    let mut samples = 0;
    let exhausted = loop {
        let (result, report) = crate::diagnostics::capture(Default::default(), || {
            c.prepare_events_until(&model, &t, &calendar, None)
        });
        samples += report
            .counters
            .get("forcing_project_source_samples")
            .copied()
            .unwrap_or(0);
        match result {
            Ok((next, _, _)) => {
                assert_eq!(next.states, [1., 0.5]);
                assert!(next.state_bounds[1].lo <= 0.5 && next.state_bounds[1].hi >= 0.5);
                prepares += 1;
                assert!(prepares < 100_000);
            }
            Err(error) => {
                assert_eq!(error.kind, "step_budget");
                break error.message;
            }
        }
    };
    assert!(prepares > 0 && samples > 0);
    assert!(
        ["exceeds 128", "exceeds 8192", "exceeds 1000000000"]
            .iter()
            .any(|limit| exhausted.contains(limit)),
        "{exhausted}"
    );
    println!("natural_original_limit={exhausted}");
    println!("sampled_history_selected={selected},prepares={prepares},source_samples={samples},work={} original_limit=1000000000",graph.work_used());
    for _ in 0..2 {
        let used = graph.work_used();
        let error = c
            .accept_changed_events(
                &model,
                &t,
                &mut calendar,
                event_acceptance::Strategy::Static,
            )
            .unwrap_err();
        assert_eq!(error.kind, "step_budget");
        // A plan-slot failure remains in that original counter. Retrying
        // may pay frame scans in work-slot 2 before revisiting the failed plan.
        if selected {
            assert!(graph.work_used() >= used);
        } else {
            assert_eq!(graph.work_used(), used);
        }
        unchanged_structure(&before, &c.accepted);
        assert_eq!(c.event, event);
        assert_eq!(serde_json::to_value(&c.records).unwrap(), records);
        assert_eq!(c.outputs.len(), outputs.len());
        for (a, b) in c.outputs.iter().zip(&outputs) {
            unchanged_structure(a, b)
        }
        assert_eq!(
            calendar
                .iter()
                .map(|e| (e.event, e.time, e.bounds()))
                .collect::<Vec<_>>(),
            signature
        );
    }
}

#[test]
fn forcing_sampled_history_late_provider_two_retries_then_recovery() {
    let (model, t, mut c, mut calendar) = fixture_sampled_history();
    c.accept_changed_events(
        &model,
        &t,
        &mut calendar,
        event_acceptance::Strategy::Static,
    )
    .unwrap();
    let before = c.accepted.clone();
    let outputs = c.outputs.clone();
    let event = c.event;
    let records = serde_json::to_value(&c.records).unwrap();
    let signature: Vec<_> = calendar
        .iter()
        .map(|e| (e.event, e.time, e.bounds()))
        .collect();
    let mut config = t.config.clone();
    config.pwl[0][1][1] = 0.5;
    let foreign = Trajectory::new(config, 1).unwrap();
    let graph = model.forcing.as_ref().unwrap();
    for _ in 0..2 {
        let used = graph.work_used();
        let (result, report) = crate::diagnostics::capture(Default::default(), || {
            c.accept_changed_events(
                &model,
                &foreign,
                &mut calendar,
                event_acceptance::Strategy::Static,
            )
        });
        assert_eq!(result.unwrap_err().kind, "unsupported_forcing_scope");
        assert!(report.stages["controller.prepare_candidate"].calls > 0);
        assert!(graph.work_used() > used);
        unchanged(&before, &c.accepted);
        assert_eq!(c.event, event);
        assert_eq!(serde_json::to_value(&c.records).unwrap(), records);
        assert_eq!(c.outputs.len(), outputs.len());
        for (a, b) in c.outputs.iter().zip(&outputs) {
            unchanged(a, b)
        }
        assert_eq!(
            calendar
                .iter()
                .map(|e| (e.event, e.time, e.bounds()))
                .collect::<Vec<_>>(),
            signature
        );
    }
    c.accept_changed_events(
        &model,
        &t,
        &mut calendar,
        event_acceptance::Strategy::Static,
    )
    .unwrap();
    assert_eq!(c.accepted.states, [1., 0.5]);
    assert!(c.accepted.state_bounds[1].lo <= 0.5 && c.accepted.state_bounds[1].hi >= 0.5);
    assert_eq!(c.accepted.operators.values(0.4375).unwrap(), [1., 0.5]);
    let (clean_model, clean_t, mut clean, mut clean_calendar) = fixture_sampled_history();
    for _ in 0..2 {
        clean
            .accept_changed_events(
                &clean_model,
                &clean_t,
                &mut clean_calendar,
                event_acceptance::Strategy::Static,
            )
            .unwrap();
    }
    assert_eq!(c.accepted.states, clean.accepted.states);
    assert_eq!(c.accepted.state_bounds, clean.accepted.state_bounds);
    assert_eq!(
        serde_json::to_value(&c.accepted.solution).unwrap(),
        serde_json::to_value(&clean.accepted.solution).unwrap()
    );
    assert_eq!(
        serde_json::to_value(&c.records).unwrap(),
        serde_json::to_value(&clean.records).unwrap()
    );
}

// The source AST is deliberately large while its held affine row stays small.
// Constructor and prior frame costs are excluded from each measured clone.
fn fixture_owned_expression(
    leaves: usize,
) -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    fixture_owned_expression_mode(leaves, false)
}
fn fixture_owned_expression_mode(
    leaves: usize,
    padded: bool,
) -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    let (model, t, _, _) = fixture_options(false, true);
    let context = model
        .forcing
        .as_ref()
        .unwrap()
        .source_context(&model.program, &t, &model.driven)
        .unwrap();
    let mut raw = serde_json::to_value(context.original_binding().0).unwrap();
    fn tree(leaves: usize, state: bool, padded: bool) -> serde_json::Value {
        if leaves == 1 {
            return if state {
                json!({"op":"state","state":0})
            } else {
                json!({"op":"affine","constant":0,"terms":if padded {vec![json!({"node":0,"coefficient":0})]}else{vec![]}})
            };
        }
        json!({"op":"add","left":tree(leaves/2,state,padded),"right":tree(leaves-leaves/2,false,padded)})
    }
    raw["operators"][0]["input"] = tree(leaves, true, padded);
    raw["states"]
        .as_array_mut()
        .unwrap()
        .push(json!({"instance":"observer","name":"observer","kind":"real","initial":0}));
    let mut passive = raw["events"][0].clone();
    passive["trigger"]["start"] = json!(0.5);
    passive["origin"]["line"] = json!(8);
    passive["origin"]["instance"] = json!("observer");
    passive["body"] =
        json!([{"kind":"assign","state":1,"rhs":{"op":"affine","constant":1,"terms":[]}}]);
    raw["events"].as_array_mut().unwrap().push(passive);
    fixture_from_original(
        serde_json::from_value(raw).unwrap(),
        t,
        model.driven,
        model.tolerances,
        true,
    )
}
fn actual_passive_phases(
    model: &EventModel,
    t: &Trajectory,
    c: &mut Controller,
    calendar: &mut Vec<ScheduledEvent>,
) -> Vec<(Frame, Vec<ScheduledEvent>)> {
    let physical = vec![calendar[0].clone()];
    c.accept_changed_events(model, t, calendar, event_acceptance::Strategy::Static)
        .unwrap();
    let first = c.accepted.clone();
    let passive = vec![calendar[c.event].clone()];
    assert!(event_acceptance::passive_batch(model, &passive));
    c.accept_changed_events(model, t, calendar, event_acceptance::Strategy::Static)
        .unwrap();
    assert_eq!(first.states, [1., 0.]);
    assert_eq!(c.accepted.states, [1., 1.]);
    vec![(first, physical), (c.accepted.clone(), passive)]
}
#[test]
fn forcing_owned_runtime_expression_standalone_clone_prices_actual_ast() {
    let mut costs = vec![];
    for leaves in [8, 4096] {
        let (model, _, c, _) = fixture_owned_expression(leaves);
        let g = model.forcing.as_ref().unwrap();
        let before = g.work_used();
        let copy = c.accepted.operators.forcing_clone().unwrap();
        costs.push(g.work_used() - before);
        assert!(copy.same_forcing_frame(&c.accepted.operators));
    }
    println!("standalone_actual_ast_clone_costs={costs:?}");
    assert!(
        costs[1] > costs[0] + 8192,
        "distinct 8191-node owned AST must be prepaid on every clone"
    );
}
#[test]
fn forcing_owned_runtime_expression_actual_passive_observation_prices_second_clone() {
    let mut extra = vec![];
    for leaves in [8, 4096] {
        let (model, t, mut c, mut calendar) = fixture_owned_expression(leaves);
        let phases = actual_passive_phases(&model, &t, &mut c, &mut calendar);
        let g = model.forcing.as_ref().unwrap();
        let before = g.work_used();
        event_acceptance::test_observation_seed(&model, &phases, 0, 0.4375).unwrap();
        let physical_cost = g.work_used() - before;
        let before = g.work_used();
        event_acceptance::test_observation_seed(&model, &phases, 1, 0.4375).unwrap();
        let passive_cost = g.work_used() - before;
        extra.push(passive_cost - physical_cost);
    }
    println!("passive_actual_second_clone_extra_costs={extra:?}");
    assert!(
        extra[1] > extra[0] + 8192,
        "passive suffix replacement owns a separate runtime AST copy"
    );
}

#[test]
fn forcing_owned_runtime_expression_standalone_natural_budget_two_retry_full_frame() {
    owned_expression_exhaustion(false);
}
#[test]
fn forcing_owned_runtime_expression_passive_natural_budget_two_retry_full_frame() {
    owned_expression_exhaustion(true);
}
fn owned_expression_exhaustion(passive: bool) {
    let (model, t, mut c, mut calendar) = fixture_owned_expression_mode(4096, true);
    let phases = actual_passive_phases(&model, &t, &mut c, &mut calendar);
    let graph = model.forcing.as_ref().unwrap();
    let before = c.accepted.clone();
    let outputs = c.outputs.clone();
    let records = serde_json::to_value(&c.records).unwrap();
    let event = c.event;
    let signature: Vec<_> = calendar
        .iter()
        .map(|e| (e.event, e.time, e.bounds()))
        .collect();
    let mut copies = 0;
    loop {
        let result = if passive {
            event_acceptance::test_observation_seed(&model, &phases, 1, 0.4375).map(|_| ())
        } else {
            c.accepted.operators.forcing_clone().map(|_| ())
        };
        match result {
            Ok(()) => {
                copies += 1;
                assert!(copies < 1_000_000);
            }
            Err(error) => {
                assert_eq!(error.kind, "step_budget");
                assert!(error.message.contains("exceeds 1000000000"));
                break;
            }
        }
    }
    assert!(copies > 0);
    assert!(graph.work_used() > 1_000_000_000);
    println!("owned_runtime_ast_natural passive={passive},actual_copies={copies},work={},original_limit=1000000000",graph.work_used());
    for _ in 0..2 {
        let used = graph.work_used();
        let error = if passive {
            event_acceptance::test_observation_seed(&model, &phases, 1, 0.4375)
                .err()
                .unwrap()
        } else {
            c.accepted.operators.forcing_clone().err().unwrap()
        };
        assert_eq!(error.kind, "step_budget");
        assert!(graph.work_used() >= used);
        assert!(error.message.contains("exceeds 1000000000"));
        unchanged_structure(&before, &c.accepted);
        assert_eq!(event, c.event);
        assert_eq!(serde_json::to_value(&c.records).unwrap(), records);
        assert_eq!(outputs.len(), c.outputs.len());
        for (a, b) in outputs.iter().zip(&c.outputs) {
            unchanged_structure(a, b);
        }
        assert_eq!(
            calendar
                .iter()
                .map(|e| (e.event, e.time, e.bounds()))
                .collect::<Vec<_>>(),
            signature
        );
        unchanged_structure(&phases[1].0, &c.accepted);
    }
}

#[test]
fn forcing_point_bundle_executes_one_actual_strict_body_and_preserves_bits() {
    let (model, t, _, _) = fixture_mode(true);
    let w = model.forcing.as_ref().unwrap().request_work();
    let time = 0.3125;
    let expected_values = t.history_values(time, w).unwrap();
    let expected_bounds = t.history_value_bounds(time, w).unwrap();
    let (result, report) =
        crate::diagnostics::capture(Default::default(), || t.history_point_bundle(time, w));
    let (values, bounds) = result.unwrap();
    assert_eq!(
        values.iter().map(|x| x.to_bits()).collect::<Vec<_>>(),
        expected_values
            .iter()
            .map(|x| x.to_bits())
            .collect::<Vec<_>>()
    );
    assert_eq!(bounds, expected_bounds);
    assert_eq!(values, vec![0.3076171875]);
    assert!(bounds[0].lo <= values[0] && values[0] <= bounds[0].hi);
    assert_eq!(report.counters.get("strict_curve_at_body"), Some(&1));
}

#[test]
fn forcing_point_bundle_rebuilds_requests_and_stages_range_independently() {
    let (model, t, _, _) = fixture_mode(true);
    let w = model.forcing.as_ref().unwrap().request_work();
    let mut config = t.config.clone();
    let crate::ir::SourceError::Shaped(shape) = &mut config.pwl_errors_v.as_mut().unwrap()[0]
    else {
        unreachable!()
    };
    shape.exact_knots[1].value_v = 0.96875;
    let foreign = Trajectory::new(config, 1).unwrap();
    let (result, report) = crate::diagnostics::capture(Default::default(), || {
        let a = t.history_point_bundle(0.3125, w)?;
        let again = t.history_point_bundle(0.3125, w)?;
        let b = foreign.history_point_bundle(0.3125, w)?;
        assert_eq!(a, again);
        assert_eq!(a.0, vec![0.3076171875]);
        assert_eq!(b.0, vec![0.302734375]);
        assert_ne!(a.0, b.0);
        Ok(())
    });
    result.unwrap();
    assert_eq!(report.counters.get("strict_curve_at_body"), Some(&3));
    assert_eq!(
        report.counters.get("history_point_bundle_strict_reuse"),
        Some(&3)
    );
    let (result, report) = crate::diagnostics::capture(Default::default(), || {
        t.history_range(I { lo: 0.25, hi: 0.5 }, w)
    });
    let (range, slopes) = result.unwrap();
    assert!(range[0].lo <= 0.24609375 && range[0].hi >= 0.4921875);
    // The physical segment is (63/64)*t. The independent staged range
    // evaluates its two endpoints without a point-bundle cache entry.
    assert!(slopes[0].lo <= 0.984375 && slopes[0].hi >= 0.984375);
    assert_eq!(report.counters.get("strict_range_value_body"), Some(&2));
    assert!(!report.counters.contains_key("strict_curve_at_body"));
    assert!(!report
        .counters
        .contains_key("history_point_bundle_strict_reuse"));
}

#[test]
fn forcing_point_bundle_unshaped_preserves_original_work_exactly() {
    let (model, t, _, _) = fixture();
    let graph = model.forcing.as_ref().unwrap();
    let w = graph.request_work();
    let before = graph.work_used();
    let a = (
        t.history_values(0.3125, w).unwrap(),
        t.history_value_bounds(0.3125, w).unwrap(),
    );
    let first = graph.work_used() - before;
    let before = graph.work_used();
    let b = t.history_point_bundle(0.3125, w).unwrap();
    assert_eq!(a, b);
    assert_eq!(graph.work_used() - before, first);
}

fn fixture_point_bundle_sampled() -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    let (model, t, _, _) = fixture_sampled_history();
    let context = model
        .forcing
        .as_ref()
        .unwrap()
        .source_context(&model.program, &t, &model.driven)
        .unwrap();
    let mut p = context.original_binding().0.clone();
    let clock = p.nodes.len();
    p.nodes.push("clock".to_owned());
    p.events[0].trigger = serde_json::from_value(json!({"kind":"cross","direction":1,
        "time_tolerance":1e-12,"expression_tolerance":1e-12,
        "guard":{"op":"affine","constant":-0.25,"terms":[{"node":clock,"coefficient":1}]}}))
    .unwrap();
    let mut config = serde_json::to_value(&t.config).unwrap();
    config["pwl"]
        .as_array_mut()
        .unwrap()
        .push(json!([[0, 0], [1, 0.984375]]));
    config["pwl_errors_V"] = json!([0,{"voltage_error_bound_V":0.03125,"exact_knots":[
        {"time_numerator":"0","time_denominator":"1","value_V":0},
        {"time_numerator":"1","time_denominator":"1","value_V":1}]}]);
    let t = Trajectory::new(serde_json::from_value(config).unwrap(), 2).unwrap();
    let mut driven = model.driven;
    driven.push("clock".to_owned());
    fixture_from_original(p, t, driven, model.tolerances, true)
}

#[test]
fn forcing_point_bundle_sampled_natural_budget_two_retries_full_frame() {
    let selected = false;
    let (model, t, mut c, mut calendar) = fixture_point_bundle_sampled();
    let graph = model.forcing.as_ref().unwrap();
    assert!(std::sync::Arc::ptr_eq(
        model.source_context.as_ref().unwrap(),
        &graph
            .source_context(&model.program, &t, &model.driven)
            .unwrap()
    ));
    // Accept the parent change, then repeatedly prepare the physical mid-ramp
    // sampling event on disposable candidates under this same original Work.
    c.accept_changed_events(
        &model,
        &t,
        &mut calendar,
        event_acceptance::Strategy::Static,
    )
    .unwrap();
    assert_eq!(c.accepted.states, [1., 0.]);
    let before = c.accepted.clone();
    let outputs = c.outputs.clone();
    let event = c.event;
    let records = serde_json::to_value(&c.records).unwrap();
    let signature: Vec<_> = calendar
        .iter()
        .map(|e| (e.event, e.time, e.bounds()))
        .collect();
    let mut prepares = 0;
    let mut samples = 0;
    let exhausted = loop {
        let (result, report) = crate::diagnostics::capture(Default::default(), || {
            c.prepare_events_until(&model, &t, &calendar, None)
        });
        samples += report
            .counters
            .get("forcing_project_source_samples")
            .copied()
            .unwrap_or(0);
        match result {
            Ok((next, _, _)) => {
                assert_eq!(next.states, [1., 0.5]);
                assert!(next.state_bounds[1].lo <= 0.5 && next.state_bounds[1].hi >= 0.5);
                prepares += 1;
                assert!(prepares < 100_000);
            }
            Err(error) => {
                assert_eq!(error.kind, "step_budget");
                break error.message;
            }
        }
    };
    assert!(prepares > 0 && samples > 0);
    assert!(
        ["exceeds 128", "exceeds 8192", "exceeds 1000000000"]
            .iter()
            .any(|limit| exhausted.contains(limit)),
        "{exhausted}"
    );
    println!("natural_original_limit={exhausted}");
    println!("sampled_history_selected={selected},prepares={prepares},source_samples={samples},work={} original_limit=1000000000",graph.work_used());
    for _ in 0..2 {
        let used = graph.work_used();
        let error = c
            .accept_changed_events(
                &model,
                &t,
                &mut calendar,
                event_acceptance::Strategy::Static,
            )
            .unwrap_err();
        assert_eq!(error.kind, "step_budget");
        // A plan-slot failure remains in that original counter. Retrying
        // may pay frame scans in work-slot 2 before revisiting the failed plan.
        if selected {
            assert!(graph.work_used() >= used);
        } else {
            assert_eq!(graph.work_used(), used);
        }
        unchanged_structure(&before, &c.accepted);
        assert_eq!(c.event, event);
        assert_eq!(serde_json::to_value(&c.records).unwrap(), records);
        assert_eq!(c.outputs.len(), outputs.len());
        for (a, b) in c.outputs.iter().zip(&outputs) {
            unchanged_structure(a, b)
        }
        assert_eq!(
            calendar
                .iter()
                .map(|e| (e.event, e.time, e.bounds()))
                .collect::<Vec<_>>(),
            signature
        );
    }
}
#[test]
fn forcing_point_bundle_late_provider_two_retries_then_clean_recovery() {
    let (model, t, mut c, mut calendar) = fixture_point_bundle_sampled();
    c.accept_changed_events(
        &model,
        &t,
        &mut calendar,
        event_acceptance::Strategy::Static,
    )
    .unwrap();
    let before = c.accepted.clone();
    let outputs = c.outputs.clone();
    let event = c.event;
    let records = serde_json::to_value(&c.records).unwrap();
    let signature: Vec<_> = calendar
        .iter()
        .map(|e| (e.event, e.time, e.bounds()))
        .collect();
    let mut config = t.config.clone();
    config.pwl[0][1][1] = 0.5;
    let foreign = Trajectory::new(config, 2).unwrap();
    let graph = model.forcing.as_ref().unwrap();
    for _ in 0..2 {
        let used = graph.work_used();
        let (result, report) = crate::diagnostics::capture(Default::default(), || {
            c.accept_changed_events(
                &model,
                &foreign,
                &mut calendar,
                event_acceptance::Strategy::Static,
            )
        });
        assert_eq!(result.unwrap_err().kind, "unsupported_forcing_scope");
        assert!(report.stages["controller.prepare_candidate"].calls > 0);
        assert!(graph.work_used() > used);
        unchanged(&before, &c.accepted);
        assert_eq!(c.event, event);
        assert_eq!(serde_json::to_value(&c.records).unwrap(), records);
        assert_eq!(c.outputs.len(), outputs.len());
        for (a, b) in c.outputs.iter().zip(&outputs) {
            unchanged(a, b)
        }
        assert_eq!(
            calendar
                .iter()
                .map(|e| (e.event, e.time, e.bounds()))
                .collect::<Vec<_>>(),
            signature
        );
    }
    c.accept_changed_events(
        &model,
        &t,
        &mut calendar,
        event_acceptance::Strategy::Static,
    )
    .unwrap();
    assert_eq!(c.accepted.states, [1., 0.5]);
    assert!(c.accepted.state_bounds[1].lo <= 0.5 && c.accepted.state_bounds[1].hi >= 0.5);
    assert_eq!(c.accepted.operators.values(0.4375).unwrap(), [1., 0.5]);
    let (clean_model, clean_t, mut clean, mut clean_calendar) = fixture_point_bundle_sampled();
    for _ in 0..2 {
        clean
            .accept_changed_events(
                &clean_model,
                &clean_t,
                &mut clean_calendar,
                event_acceptance::Strategy::Static,
            )
            .unwrap();
    }
    assert_eq!(c.accepted.states, clean.accepted.states);
    assert_eq!(c.accepted.state_bounds, clean.accepted.state_bounds);
    assert_eq!(
        serde_json::to_value(&c.accepted.solution).unwrap(),
        serde_json::to_value(&clean.accepted.solution).unwrap()
    );
    assert_eq!(
        serde_json::to_value(&c.records).unwrap(),
        serde_json::to_value(&clean.records).unwrap()
    );
}

#[test]
fn forcing_point_bundle_same_nominal_distinct_root_bounds_and_phase_rebuilds() {
    let (model, t, mut c, mut calendar) = fixture_point_bundle_sampled();
    c.accept_changed_events(
        &model,
        &t,
        &mut calendar,
        event_acceptance::Strategy::Static,
    )
    .unwrap();
    let before = c.accepted.clone();
    let time: f64 = 0.3125;
    let a = crate::exact_source::RootTime::point(time).unwrap();
    let left = crate::exact_source::RootTime::point(time.next_down()).unwrap();
    let b = crate::exact_source::RootTime::between(&left, &a).unwrap();
    assert_ne!(a, b);
    let windows = [
        I::point(time),
        I {
            lo: time.next_down(),
            hi: time,
        },
    ];
    for (root, window) in [
        (Some(&a), windows[0]),
        (Some(&a), windows[1]),
        (Some(&b), windows[1]),
        (None, windows[1]),
    ] {
        let (result, report) = crate::diagnostics::capture(Default::default(), || {
            prepare_root_window_impl(
                &model,
                &t,
                &c.accepted,
                EventMoment {
                    exact_root: root,
                    representative: time,
                    observation: window,
                    fired_roots: &[],
                    prediction_end: 1.,
                },
                &[],
                false,
            )
        });
        let next = result.unwrap();
        assert_eq!(
            report.counters.get("history_point_bundle_strict_reuse"),
            Some(&1)
        );
        assert!(next.state_bounds[1].lo <= 0. && next.state_bounds[1].hi >= 0.);
        assert_eq!(next.states, [1., 0.]);
        unchanged_structure(&before, &c.accepted);
    }
    c.accept_changed_events(
        &model,
        &t,
        &mut calendar,
        event_acceptance::Strategy::Static,
    )
    .unwrap();
    assert_eq!(c.accepted.states, [1., 0.5]);
    let (result, report) = crate::diagnostics::capture(Default::default(), || {
        prepare_root_window_impl(
            &model,
            &t,
            &c.accepted,
            EventMoment {
                exact_root: Some(&a),
                representative: time,
                observation: I::point(time),
                fired_roots: &[],
                prediction_end: 1.,
            },
            &[],
            false,
        )
    });
    assert_eq!(result.unwrap().states, [1., 0.5]);
    assert_eq!(
        report.counters.get("history_point_bundle_strict_reuse"),
        Some(&1)
    );
}

#[test]
fn forcing_point_bundle_wide_rational_keeps_first_strict_fee_and_enclosure() {
    let (model, t, _, _) = fixture_mode(true);
    let graph = model.forcing.as_ref().unwrap();
    let w = graph.request_work();
    let before = graph.work_used();
    t.history_point_bundle(0.3125, w).unwrap();
    let simple = graph.work_used() - before;
    let mut config = t.config.clone();
    let crate::ir::SourceError::Shaped(shape) = &mut config.pwl_errors_v.as_mut().unwrap()[0]
    else {
        unreachable!()
    };
    shape.exact_knots[1].time_numerator = "36893488147419103233".into();
    shape.exact_knots[1].time_denominator = "36893488147419103232".into();
    let wide = Trajectory::new(config, 1).unwrap();
    let before = graph.work_used();
    let old = (
        wide.history_values(0.3125, w).unwrap(),
        wide.history_value_bounds(0.3125, w).unwrap(),
    );
    let old_fee = graph.work_used() - before;
    let before = graph.work_used();
    let (result, report) =
        crate::diagnostics::capture(Default::default(), || wide.history_point_bundle(0.3125, w));
    let new = result.unwrap();
    let new_fee = graph.work_used() - before;
    assert_eq!(old, new);
    assert_eq!(report.counters.get("strict_curve_at_body"), Some(&1));
    assert!(new_fee > simple && new_fee < old_fee);
    let numerator: num_rational::BigRational = "315".parse().unwrap();
    let scale: num_rational::BigRational = "36893488147419103232".parse().unwrap();
    let divisor: num_rational::BigRational = "36893488147419103233".parse().unwrap();
    let wanted =
        numerator * scale / (divisor * num_rational::BigRational::from_integer(1024.into()));
    let low = crate::exact_source::RootTime::point(new.1[0].lo).unwrap();
    let high = crate::exact_source::RootTime::point(new.1[0].hi).unwrap();
    assert!(low.rational() <= &wanted && &wanted <= high.rational());
    println!("point_bundle_wide_rational simple={simple} first_plus_storage={new_fee} legacy_twice={old_fee}");
}
