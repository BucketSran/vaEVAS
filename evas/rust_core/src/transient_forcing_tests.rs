//! Real disposable candidate failures at the final provider-binding seam.
use super::*;
use crate::ir::{Expression as E, Program, Tolerances};
use serde_json::json;

fn fixture() -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    fixture_mode(false)
}
fn fixture_mode(shaped: bool) -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
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
    let graph = crate::forcing_graph::Graph::partition(&mut p, &t, &driven, &tol)
        .unwrap()
        .unwrap();
    let mut model = EventModel::new(p, driven, tol).unwrap();
    model.forcing = Some(graph.clone());
    let states = model.initial();
    let state_bounds: Vec<_> = states.iter().copied().map(I::point).collect();
    let mut operators = Operators::new_until_with_source_context(
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

fn unchanged(a: &Frame, b: &Frame) {
    assert_eq!(a.time, b.time);
    assert_eq!(a.states, b.states);
    assert_eq!(a.state_bounds, b.state_bounds);
    assert_eq!(a.value_proofs, b.value_proofs);
    assert_eq!(a.time_proofs, b.time_proofs);
    assert_eq!(
        serde_json::to_value(&a.solution).unwrap(),
        serde_json::to_value(&b.solution).unwrap()
    );
    assert_eq!(a.circuit.forcing_phase, b.circuit.forcing_phase);
    assert!(a.operators.same_reset_history(&b.operators));
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
