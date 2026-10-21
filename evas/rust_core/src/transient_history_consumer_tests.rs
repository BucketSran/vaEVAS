//! Ordinary history predicate deadlines use actual production Controller frames.
use super::*;
use crate::history_consumer_fixture as source_fixture;
fn fixture() -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    fixture_mode(false)
}
fn fixture_mode(late_failure: bool) -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    let mut value = source_fixture::fixture();
    if late_failure {
        value["transient"]["pwl_errors_V"] = serde_json::json!([1e-12]);
        let p = &mut value["program"];
        p["nodes"]
            .as_array_mut()
            .unwrap()
            .push(serde_json::json!("late"));
        let mut origin = p["operators"][0]["origin"].clone();
        origin["column"] = serde_json::json!(2);
        let c = |x: f64| serde_json::json!({"op":"affine","constant":x,"terms":[]});
        p["operators"].as_array_mut().unwrap().push(serde_json::json!({
   "kind":"transition","input":{"op":"select","relation":"gt","left":{"op":"state","state":0},"right":c(1.),
    "then_value":{"op":"select","relation":"gt","left":{"op":"state","state":1},"right":c(0.625),
      "then_value":c(1.),"else_value":c(0.),"origin":origin},"else_value":c(0.),"origin":origin},
   "delay":0.,"rise":0.25,"fall":0.25,"origin":origin}));
        p["contributions"].as_array_mut().unwrap().push(
            serde_json::json!({"positive":6,"negative":0,
   "branch":{"instance":"M","local_positive":"late","local_negative":"zzref","kind":"voltage"},
   "rhs":{"op":"operator","operator":1},"origin":origin}),
        );
    }
    fixture_value(value)
}
fn fixture_value(
    value: serde_json::Value,
) -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    let value = if STAGED_SHAPED_FIXTURE.with(|f| f.get()) {
        staged_shaped_value(value)
    } else {
        value
    };
    let request: Request = serde_json::from_value(value).unwrap();
    let t = Trajectory::new(request.transient.unwrap(), request.driven.len()).unwrap();
    let m = EventModel::new_with_trajectory(
        request.program,
        request.driven,
        request.tolerances,
        Some(&t),
    )
    .unwrap();
    let states = m.initial();
    let calendar = independent_schedule(&m, &t).unwrap();
    let token = m.history_admission.as_ref().unwrap().clone();
    let ops =
        Operators::new_history_consumer(token, &states, prediction_end(&m, &t, calendar.first()))
            .unwrap();
    assert!(std::sync::Arc::ptr_eq(
        ops.source_context.as_ref().unwrap(),
        m.source_context.as_ref().unwrap()
    ));
    let circuit = m
        .circuit_at(&states, &ops.values(0.).unwrap(), &t.value_bounds(0.))
        .unwrap();
    let accepted = Frame {
        value_proofs: Default::default(),
        time_proofs: Default::default(),
        time: 0.,
        state_bounds: states.iter().copied().map(I::point).collect(),
        states,
        solution: circuit.solve(&t.values(0.)).unwrap(),
        circuit,
        operators: ops,
    };
    (
        m,
        t,
        Controller {
            accepted,
            event: 0,
            records: vec![],
            outputs: vec![],
        },
        calendar,
    )
}
#[test]
fn warm_static_controller_schedules_actual_ordinary_history_midpoint() {
    let (m, t, mut c, mut q) = fixture();
    c.accept_changed_events(&m, &t, &mut q, event_acceptance::Strategy::Static)
        .unwrap();
    c.accept_changed_events(&m, &t, &mut q, event_acceptance::Strategy::Static)
        .unwrap();
    assert_eq!(c.accepted.time, 0.5);
    assert_eq!(c.accepted.states, [2., 0.]);
    assert!(std::sync::Arc::ptr_eq(
        c.accepted.operators.source_context.as_ref().unwrap(),
        m.source_context.as_ref().unwrap()
    ));
    let deadline = c
        .accepted
        .operators
        .next_breakpoint_for_event(0.5, q.get(c.event), &m)
        .unwrap();
    assert_eq!(deadline, Some(0.625));
    let root = c
        .accepted
        .operators
        .source_root_at(0.625)
        .unwrap()
        .expect("ordinary guard retained exact root identity");
    assert_eq!(
        root.order(&crate::exact_source::RootTime::point(0.625).unwrap()),
        std::cmp::Ordering::Equal
    );
    assert_eq!(
        c.accepted.operators.source_window_at(0.625),
        Some(I::point(0.625))
    );
}

fn assert_frame_unchanged(actual: &Frame, expected: &Frame) {
    assert_eq!(actual.time, expected.time);
    assert_eq!(actual.states, expected.states);
    assert_eq!(actual.state_bounds, expected.state_bounds);
    assert_eq!(actual.value_proofs, expected.value_proofs);
    assert_eq!(actual.time_proofs, expected.time_proofs);
    assert_eq!(
        serde_json::to_value(&actual.solution).unwrap(),
        serde_json::to_value(&expected.solution).unwrap()
    );
    assert_eq!(
        actual.solution.certified_voltage_bounds,
        expected.solution.certified_voltage_bounds
    );
    assert_eq!(actual.circuit.nodes, expected.circuit.nodes);
    assert!(actual.operators.same_reset_history(&expected.operators));
    assert_eq!(
        actual.operators.test_transition_histories(),
        expected.operators.test_transition_histories(),
        "full held runtime must remain identical, including queue and exact roots"
    );
}
#[test]
fn warm_late_held_target_failure_rolls_back_complete_frame_and_two_retries() {
    let (m, t, mut c, mut q) = fixture_mode(true);
    for _ in 0..2 {
        c.accept_changed_events(&m, &t, &mut q, event_acceptance::Strategy::Static)
            .unwrap();
    }
    assert_eq!(c.accepted.time, 0.5);
    let before = c.accepted.clone();
    let records = serde_json::to_value(&c.records).unwrap();
    let outputs = c.outputs.clone();
    let cursor = c.event;
    let signature = |q: &Vec<ScheduledEvent>| {
        q.iter()
            .map(|e| (e.event, e.time, e.bounds()))
            .collect::<Vec<_>>()
    };
    let calendar = signature(&q);
    for _ in 0..2 {
        let (result, report) = crate::diagnostics::capture(Default::default(), || {
            c.accept_changed_events(&m, &t, &mut q, event_acceptance::Strategy::Static)
        });
        let error = result.unwrap_err();
        assert!(report
            .stages
            .get("history.advance")
            .is_some_and(|stage| stage.calls > 0));
        assert!(
            report
                .counters
                .get("history_held_edge_settles")
                .copied()
                .unwrap_or(0)
                > 0,
            "failure must follow an actual candidate edge settlement"
        );
        println!("late error {}: {}", error.kind, error.message);
        assert_eq!(error.kind, "condition_precision");
        assert_frame_unchanged(&c.accepted, &before);
        assert_eq!(c.event, cursor);
        assert_eq!(signature(&q), calendar);
        assert_eq!(serde_json::to_value(&c.records).unwrap(), records);
        assert_eq!(c.outputs.len(), outputs.len());
        for (a, b) in c.outputs.iter().zip(&outputs) {
            assert_frame_unchanged(a, b)
        }
    }
}

#[test]
fn natural_default_request_exhaustion_is_shared_and_sticky_before_retries() {
    let (m, t, mut c, mut q) = fixture();
    for _ in 0..2 {
        c.accept_changed_events(&m, &t, &mut q, event_acceptance::Strategy::Static)
            .unwrap();
    }
    let before = c.accepted.clone();
    let records = serde_json::to_value(&c.records).unwrap();
    let calendar = q
        .iter()
        .map(|e| (e.event, e.time, e.bounds()))
        .collect::<Vec<_>>();
    let cursor = c.event;
    let work = m.source_context.as_ref().unwrap().borrow_work();
    assert!(std::sync::Arc::ptr_eq(
        m.source_context.as_ref().unwrap(),
        c.accepted.operators.source_context.as_ref().unwrap()
    ));
    let proof_inputs = t.value_bounds(0.5);
    let proof_root = crate::exact_source::RootTime::point(0.5).unwrap();
    let context = crate::event_value_proof::Context::try_new(
        &m,
        &t,
        &proof_inputs,
        &before.value_proofs,
        Some(&proof_root),
    )
    .unwrap();
    assert!(
        context.floor_work().is_none(),
        "history accounting must not grant Floor role"
    );
    let local = crate::event_value_proof::LocalState::try_with_context(
        &before.state_bounds,
        Some(&context),
    )
    .unwrap();
    assert!(local.floor_work().is_none());
    let selection = m.conditions.select(&[1], &proof_inputs).unwrap();
    let guard_projection = crate::event_accuracy::GuardBounds::for_model(&m, None).unwrap();
    let mut actual = 0;
    loop {
        // Rebuild and solve a real ordinary consumer using this prepared request.
        // No debit, quota override, helper-only owner, or candidate refund occurs here.
        match m.circuit_at(&c.accepted.states, &[0.], &t.value_bounds(0.5)) {
            Ok(circuit) => {
                let solution = circuit.solve(&t.values(0.5)).unwrap();
                assert_eq!(solution.voltages[3], 0.);
                actual += 1;
            }
            Err(error) => {
                assert_eq!(error.kind, "step_budget");
                break;
            }
        }
        assert!(
            actual < 100_000,
            "default quota did not constrain real consumer work"
        );
    }
    println!(
        "actual ordinary consumer solves before default exhaustion={actual}; used={}",
        work.spent()
    );
    assert!(actual > 1);
    assert!(work.spent() > 1_000_000_000);
    let used = work.spent();
    let next_event = q.get(cursor).unwrap().clone();
    let independent_root = crate::exact_source::RootTime::point(0.625).unwrap();
    for _ in 0..2 {
        // Actual history-owner exhaustion must reach all calendar proof accessors.
        // No helper may reconstruct a clock root after the shared request has failed.
        let (result, report) = crate::diagnostics::capture(Default::default(), || {
            event_root(&m, std::slice::from_ref(&next_event))
        });
        assert_eq!(result.unwrap_err().kind, "step_budget");
        assert!(report.counters.is_empty() && report.stages.is_empty());
        assert_eq!(
            event_bounds(&m, &next_event).unwrap_err().kind,
            "step_budget"
        );
        assert_eq!(
            event_order(&m, &t, &next_event, 0.625).unwrap_err().kind,
            "step_budget"
        );
        assert_eq!(
            source_root_bounds(&m, &independent_root).unwrap_err().kind,
            "step_budget"
        );
        assert_eq!(work.spent(), used);
        let (result, report) = crate::diagnostics::capture(Default::default(), || {
            assert_eq!(
                crate::event_accuracy::GuardBounds::for_model(&m, None)
                    .err()
                    .unwrap()
                    .kind,
                "step_budget"
            );
            assert_eq!(
                guard_projection
                    .active_inputs_history(0, work)
                    .unwrap_err()
                    .kind,
                "step_budget"
            );
            assert_eq!(
                independent_schedule(&m, &t).err().unwrap().kind,
                "step_budget"
            );
            assert_eq!(
                crate::schedule::copy_calendar(&q, &m).err().unwrap().kind,
                "step_budget"
            );
            assert_eq!(before.candidate_clone().err().unwrap().kind, "step_budget");
            assert_eq!(
                crate::event_value_proof::apply_charged(
                    &m,
                    &selection,
                    &proof_inputs,
                    &before.state_bounds,
                    &before.state_bounds,
                    &context
                )
                .unwrap_err()
                .kind,
                "step_budget"
            );
            assert_eq!(
                time_provenance::apply_charged(
                    &m,
                    &t,
                    &selection,
                    &before.time_proofs,
                    Some(&proof_root),
                    &before.state_bounds,
                    &before.state_bounds
                )
                .unwrap_err()
                .kind,
                "step_budget"
            );
            assert_eq!(local.try_clone().err().unwrap().kind, "step_budget");
            assert_eq!(
                local
                    .try_value(&crate::ir::Expression::State { state: 0 }, &[])
                    .unwrap_err()
                    .kind,
                "step_budget"
            );
            assert_eq!(
                crate::event_value_proof::history::inputs(&m, &t, 0.5)
                    .unwrap_err()
                    .kind,
                "step_budget"
            );
            assert_eq!(
                crate::event_value_proof::history::input_bounds(&m, &t, 0.5)
                    .unwrap_err()
                    .kind,
                "step_budget"
            );
            assert_eq!(
                crate::event_value_proof::history::input_range(&m, &t, I::point(0.5))
                    .unwrap_err()
                    .kind,
                "step_budget"
            );
            assert_eq!(
                crate::event_value_proof::Context::try_new(
                    &m,
                    &t,
                    &[I::point(0.5)],
                    &before.value_proofs,
                    Some(&independent_root)
                )
                .err()
                .unwrap()
                .kind,
                "step_budget"
            );
            assert_eq!(
                crate::event_value_proof::history::equal(
                    &before.value_proofs,
                    &before.value_proofs,
                    work
                )
                .unwrap_err()
                .kind,
                "step_budget"
            );
            assert_eq!(
                time_provenance::equal_history(&before.time_proofs, &before.time_proofs, work)
                    .unwrap_err()
                    .kind,
                "step_budget"
            );
            assert_eq!(
                before
                    .operators
                    .same_reset_history_paid(&before.operators, work)
                    .unwrap_err()
                    .kind,
                "step_budget"
            );
            Ok(())
        });
        result.unwrap();
        assert!(report.counters.is_empty() && report.stages.is_empty());
        assert_eq!(work.spent(), used);
        let (result, report) = crate::diagnostics::capture(Default::default(), || {
            c.accept_changed_events(&m, &t, &mut q, event_acceptance::Strategy::Static)
        });
        assert_eq!(result.unwrap_err().kind, "step_budget");
        assert!(
            report.counters.is_empty(),
            "retry entered helpers: {:?}",
            report.counters
        );
        assert!(report.stages.is_empty(), "retry prepared a candidate");
        assert_eq!(work.spent(), used);
        assert_frame_unchanged(&c.accepted, &before);
        assert_eq!(c.event, cursor);
        assert_eq!(
            q.iter()
                .map(|e| (e.event, e.time, e.bounds()))
                .collect::<Vec<_>>(),
            calendar
        );
        assert_eq!(serde_json::to_value(&c.records).unwrap(), records);
    }
}

#[test]
fn nonpoint_exact_history_root_window_does_not_silently_merge_a_timer() {
    let mut value = source_fixture::fixture();
    for event in value["program"]["events"].as_array_mut().unwrap() {
        event["trigger"]["start"] = serde_json::json!(0.1);
        event["trigger"]["period"] = serde_json::json!(0.25);
    }
    value["program"]["operators"][0]["rise"] = serde_json::json!(1.);
    value["program"]["operators"][0]["fall"] = serde_json::json!(1.);
    value["transient"]["stop"] = serde_json::json!(2.);
    value["transient"]["output_times"] = serde_json::json!([0., 2.]);
    value["transient"]["pwl"] = serde_json::json!([[[0., 0.5], [2., 0.5]]]);
    let (m, t, mut c, mut q) = fixture_value(value);
    for _ in 0..3 {
        c.accept_changed_events(&m, &t, &mut q, event_acceptance::Strategy::Static)
            .unwrap();
    }
    let deadline = c
        .accepted
        .operators
        .next_breakpoint(c.accepted.time)
        .expect("actual history predicate deadline");
    let window = c
        .accepted
        .operators
        .source_window_at(deadline)
        .expect("retained predicate window");
    assert!(
        window.lo < window.hi,
        "a nonbinary exact clock must retain its window: {window:?}"
    );
    let root = c
        .accepted
        .operators
        .source_root_at(deadline)
        .unwrap()
        .expect("original exact root identity");
    assert!(root.refine(window).is_some());
    // Consume the retained nonpoint window and its original exact physical root.
    // Strict midpoint comparison observes exactly 1/2, even if the upper binary
    // representative lies to its right; the ordinary gate and clamp stay zero.
    let bounds = c
        .accepted
        .operators
        .event_bounds_at_root(deadline, window, Some(&root))
        .unwrap();
    assert_eq!(bounds, [I::point(0.5)]);
    let view = c
        .accepted
        .operators
        .evaluation_at_root(deadline, Some(&root), window)
        .unwrap();
    assert_eq!(view.values, [0.5]);
    let circuit = m
        .circuit_at(&c.accepted.states, &view.values, &t.value_bounds(deadline))
        .unwrap();
    let sample = circuit.solve(&t.values(deadline)).unwrap();
    assert_eq!(sample.voltages[2], 0.5);
    assert_eq!(sample.voltages[3], 0.);
    assert_eq!(sample.voltages[5], 0.);
    assert!(sample.max_residual_ratio <= 1.);
    println!("successful original nonpoint sample window={window:?}, root={root:?}, history={bounds:?}, residual={}",sample.max_residual_ratio);
    assert_eq!(
        c.accepted
            .operators
            .next_breakpoint_for_event(c.accepted.time, q.get(c.event), &m)
            .unwrap_err()
            .kind,
        "event_resolution"
    );
}

#[test]
fn existing_direct_gate_keeps_the_legacy_none_owner_route() {
    let mut value = source_fixture::fixture();
    value["program"]["contributions"][3]["rhs"] =
        serde_json::json!({"op":"affine","constant":0.,"terms":[{"node":3,"coefficient":1.}]});
    let request: Request = serde_json::from_value(value).unwrap();
    let t = Trajectory::new(request.transient.unwrap(), request.driven.len()).unwrap();
    let model = EventModel::new_with_trajectory(
        request.program,
        request.driven,
        request.tolerances,
        Some(&t),
    )
    .unwrap();
    assert!(model.history_admission.is_none());
    assert!(model.source_context.is_none());
}

#[test]
fn two_final_candidate_failures_then_legal_retry_match_clean_controller() {
    let (m, t, mut c, mut q) = fixture();
    // A fresh Controller starts from the same immutable prepared request and
    // original owner. It never sees the injected candidates or their mutations.
    let mut clean = Controller {
        accepted: c.accepted.clone(),
        event: 0,
        records: vec![],
        outputs: vec![],
    };
    let mut cq = q.clone();
    for _ in 0..2 {
        c.accept_changed_events(&m, &t, &mut q, event_acceptance::Strategy::Static)
            .unwrap();
        clean
            .accept_changed_events(&m, &t, &mut cq, event_acceptance::Strategy::Static)
            .unwrap();
    }
    let before = c.accepted.clone();
    let records = serde_json::to_value(&c.records).unwrap();
    let outputs = c.outputs.clone();
    let cursor = c.event;
    let signature = |q: &Vec<ScheduledEvent>| {
        q.iter()
            .map(|e| (e.event, e.time, e.bounds()))
            .collect::<Vec<_>>()
    };
    let calendar = signature(&q);
    let owner = m.source_context.as_ref().unwrap();
    let mut used = owner.borrow_work().spent();
    for _ in 0..2 {
        let (result, report) = crate::diagnostics::capture(Default::default(), || {
            event_acceptance::test_with_final_candidate(
                |candidate| {
                    assert_eq!(candidate.time, 0.75);
                    candidate.solution.voltages[3] += 1.;
                },
                || c.accept_changed_events(&m, &t, &mut q, event_acceptance::Strategy::Static),
            )
        });
        let error = result.unwrap_err();
        println!(
            "injected final candidate rejection: {} {}",
            error.kind, error.message
        );
        assert!(report
            .stages
            .get("history.advance")
            .is_some_and(|stage| stage.calls > 0));
        assert!(
            report
                .counters
                .get("history_held_edge_settles")
                .copied()
                .unwrap_or(0)
                > 0
        );
        assert_frame_unchanged(&c.accepted, &before);
        assert_eq!(c.event, cursor);
        assert_eq!(signature(&q), calendar);
        assert_eq!(serde_json::to_value(&c.records).unwrap(), records);
        assert_eq!(c.outputs.len(), outputs.len());
        for (a, b) in c.outputs.iter().zip(&outputs) {
            assert_frame_unchanged(a, b)
        }
        assert!(owner.borrow_work().spent() > used);
        used = owner.borrow_work().spent();
    }
    c.accept_changed_events(&m, &t, &mut q, event_acceptance::Strategy::Static)
        .unwrap();
    clean
        .accept_changed_events(&m, &t, &mut cq, event_acceptance::Strategy::Static)
        .unwrap();
    assert!(std::sync::Arc::ptr_eq(
        c.accepted.operators.source_context.as_ref().unwrap(),
        owner
    ));
    assert_eq!(c.event, clean.event);
    assert_eq!(signature(&q), signature(&cq));
    assert_eq!(
        serde_json::to_value(&c.records).unwrap(),
        serde_json::to_value(&clean.records).unwrap()
    );
    assert_frame_unchanged(&c.accepted, &clean.accepted);
    assert_eq!(c.outputs.len(), clean.outputs.len());
    for (a, b) in c.outputs.iter().zip(&clean.outputs) {
        assert_frame_unchanged(a, b)
    }
    assert!(owner.borrow_work().spent() > used);
}

#[test]
fn history_calendar_proof_accessors_spend_the_original_owner_before_success() {
    let (m, t, c, q) = fixture();
    assert!(m.forcing.is_none() && m.history_admission.is_some());
    let w = m.source_context.as_ref().unwrap().borrow_work();
    let event = &q[0];
    let before = c.accepted.clone();
    let used = w.spent();
    let bounds = event_bounds(&m, event).unwrap();
    assert!(w.spent() > used);
    assert!(bounds.lo <= 0.25 && bounds.hi >= 0.25);
    let used = w.spent();
    let root = event_root(&m, std::slice::from_ref(event))
        .unwrap()
        .unwrap();
    assert!(w.spent() > used);
    assert_eq!(
        root.order(&crate::exact_source::RootTime::point(0.25).unwrap()),
        std::cmp::Ordering::Equal
    );
    let used = w.spent();
    assert_eq!(
        event_order(&m, &t, event, 0.25).unwrap(),
        Some(std::cmp::Ordering::Equal)
    );
    assert!(w.spent() > used);
    let used = w.spent();
    let interval = source_root_bounds(&m, &root).unwrap().unwrap();
    assert!(w.spent() > used);
    assert!(interval.lo <= 0.25 && interval.hi >= 0.25);
    assert_frame_unchanged(&c.accepted, &before);
}

#[test]
fn history_bookkeeping_value_context_debits_original_owner() {
    let (m, t, mut c, mut q) = fixture();
    for _ in 0..2 {
        c.accept_changed_events(&m, &t, &mut q, event_acceptance::Strategy::Static)
            .unwrap();
    }
    assert!(
        !c.accepted.value_proofs.is_empty(),
        "real warm callbacks must generate exact value proofs"
    );
    let work = m.source_context.as_ref().unwrap().borrow_work();
    let used = work.spent();
    let root = crate::exact_source::RootTime::point(c.accepted.time).unwrap();
    let _context = crate::event_value_proof::Context::try_new(
        &m,
        &t,
        &t.value_bounds(c.accepted.time),
        &c.accepted.value_proofs,
        Some(&root),
    )
    .unwrap();
    assert!(work.spent()>used,"history Context::try_new consumed original rational source/state proofs without charging its owner");
}

#[test]
fn history_bookkeeping_identity_time_provenance_debits_original_owner() {
    let mut value = source_fixture::fixture();
    value["transient"]["pwl"] = serde_json::json!([[[0., 0.], [1., 1.]]]);
    value["program"]["states"]
        .as_array_mut()
        .unwrap()
        .push(serde_json::json!({"instance":"M","name":"saved","kind":"real","initial":0.}));
    value["program"]["nodes"]
        .as_array_mut()
        .unwrap()
        .push(serde_json::json!("saved"));
    value["program"]["events"][1]["body"].as_array_mut().unwrap().push(serde_json::json!({"kind":"assign","state":2,"rhs":{"op":"affine","constant":0.,"terms":[{"node":1,"coefficient":1.}]}}));
    let mut output = value["program"]["contributions"][2].clone();
    output["positive"] = serde_json::json!(6);
    output["branch"]["local_positive"] = serde_json::json!("saved");
    output["rhs"] = serde_json::json!({"op":"state","state":2});
    value["program"]["contributions"]
        .as_array_mut()
        .unwrap()
        .push(output);
    let (m, t, mut c, mut q) = fixture_value(value);
    for _ in 0..2 {
        c.accept_changed_events(&m, &t, &mut q, event_acceptance::Strategy::Static)
            .unwrap();
    }
    assert!(
        c.accepted.time_proofs.contains_key(&2),
        "identity PWL real sample must generate an actual time proof"
    );
    let before = c.accepted.clone();
    c.accept_changed_events(&m, &t, &mut q, event_acceptance::Strategy::Static)
        .unwrap();
    assert_eq!(c.accepted.states[2], 0.75);
    assert_eq!(c.accepted.solution.voltages[6], 0.75);
    let selection = m.conditions.select(&[1], &t.value_bounds(0.75)).unwrap();
    let root = crate::exact_source::RootTime::point(0.75).unwrap();
    let work = m.source_context.as_ref().unwrap().borrow_work();
    let used = work.spent();
    let result = time_provenance::apply_charged(
        &m,
        &t,
        &selection,
        &before.time_proofs,
        Some(&root),
        &before.state_bounds,
        &c.accepted.state_bounds,
    )
    .unwrap();
    assert!(result.contains_key(&2));
    assert!(work.spent()>used,"history identity-source time provenance consumed original root/curve proofs without charging its owner");
}

#[test]
fn history_bookkeeping_shaped_input_reads_pay_original_owner() {
    let mut value = source_fixture::fixture();
    value["transient"]["pwl_errors_V"] = serde_json::json!([{"voltage_error_bound_V":0.03125,"exact_knots":[
 {"time_numerator":"0","time_denominator":"1","value_V":0.5},
 {"time_numerator":"1","time_denominator":"1","value_V":0.484375}]}]);
    let (m, t, mut c, mut q) = fixture_value(value);
    assert!(m.history_admission.is_some());
    assert!(m.forcing.is_none());
    c.accept_changed_events(&m, &t, &mut q, event_acceptance::Strategy::Static)
        .unwrap();
    let w = m.source_context.as_ref().unwrap().borrow_work();
    let used = w.spent();
    let b = crate::event_value_proof::history::input_bounds(&m, &t, 0.375).unwrap();
    assert_eq!(b[0], I::point(0.494140625));
    assert!(w.spent() > used);
    let used = w.spent();
    let v = crate::event_value_proof::history::inputs(&m, &t, 0.375).unwrap();
    assert_eq!(v, t.values(0.375));
    assert!(w.spent() > used);
    let used = w.spent();
    let range =
        crate::event_value_proof::history::input_range(&m, &t, I { lo: 0.25, hi: 0.5 }).unwrap();
    assert_eq!(range, t.range(I { lo: 0.25, hi: 0.5 }).unwrap());
    assert!(w.spent() > used);
}

#[test]
fn history_bookkeeping_independent_cross_retains_original_physical_root() {
    for shaped in [false, true] {
        let mut value = source_fixture::fixture();
        value["transient"]["pwl"] = serde_json::json!([[[0., 0.], [1., 1.]]]);
        if shaped {
            value["transient"]["pwl_errors_V"] = serde_json::json!([{"voltage_error_bound_V":0.0625,"exact_knots":[
   {"time_numerator":"0","time_denominator":"1","value_V":0.},
   {"time_numerator":"1","time_denominator":"1","value_V":0.9375}]}]);
        }
        value["program"]["events"][1]["trigger"] = serde_json::json!({"kind":"cross","direction":1,"time_tolerance":1e-10,"expression_tolerance":1e-10,
   "guard":{"op":"add","left":{"op":"affine","constant":0.,"terms":[{"node":1,"coefficient":1.}]},"right":{"op":"affine","constant":-0.375,"terms":[]}}});
        let (m, t, mut c, mut q) = fixture_value(value);
        let w = m.source_context.as_ref().unwrap().borrow_work();
        let used = w.spent();
        let calendar = independent_schedule(&m, &t).unwrap();
        assert!(w.spent() > used);
        let cross = calendar.iter().find(|e| e.event == 1).unwrap();
        let root = event_root(&m, std::slice::from_ref(cross))
            .unwrap()
            .unwrap();
        let expected = if shaped {
            num_rational::BigRational::new(2.into(), 5.into())
        } else {
            num_rational::BigRational::new(3.into(), 8.into())
        };
        assert_eq!(root.rational(), &expected);
        assert!(cross.bounds().lo <= 0.4 && cross.bounds().hi >= 0.375);
        for _ in 0..2 {
            c.accept_changed_events(&m, &t, &mut q, event_acceptance::Strategy::Static)
                .unwrap();
        }
        assert_eq!(c.accepted.states, [1., 0.]);
        assert!(c.accepted.value_proofs.contains_key(&0));
    }
}

fn projection_fixture() -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    let mut value = source_fixture::fixture();
    value["transient"]["pwl"] = serde_json::json!([[[0., 0.], [1., 1.]]]);
    value["program"]["events"][1]["trigger"] = serde_json::json!({"kind":"cross","direction":1,"time_tolerance":1e-10,"expression_tolerance":1e-10,
  "guard":{"op":"add","left":{"op":"affine","constant":0.,"terms":[{"node":1,"coefficient":1.}]},"right":{"op":"affine","constant":-0.375,"terms":[]}}});
    fixture_value(value)
}
#[test]
fn bookkeeping_r2_guard_projection_charges_original_owner() {
    let (m, _t, _c, _q) = projection_fixture();
    let w = m.source_context.as_ref().unwrap().borrow_work();
    let used = w.spent();
    let bounds = crate::event_accuracy::GuardBounds::for_model(&m, None).unwrap();
    assert_eq!(bounds.active_inputs(1), [0]);
    assert!(w.spent()>used,"admitted independent Cross guard projection allocated/scanned after owner without any debit");
}
#[test]
fn bookkeeping_r2_active_inputs_charge_original_owner() {
    let (m, _t, _c, _q) = projection_fixture();
    let bounds = crate::event_accuracy::GuardBounds::for_model(&m, None).unwrap();
    let w = m.source_context.as_ref().unwrap().borrow_work();
    let used = w.spent();
    assert_eq!(bounds.active_inputs_history(1, w).unwrap(), [0]);
    assert!(
        w.spent() > used,
        "admitted independent Cross active-input scan/Vec allocation without any debit"
    );
}
#[test]
fn bookkeeping_r2_equivalent_branches_charge_created_rational_comparison() {
    let mut value = source_fixture::fixture();
    value["transient"]["pwl_errors_V"] = serde_json::json!([1e-12]);
    value["program"]["states"]
        .as_array_mut()
        .unwrap()
        .push(serde_json::json!({"instance":"M","name":"phase","kind":"integer","initial":0.}));
    let origin = value["program"]["events"][1]["origin"].clone();
    let c = |v: f64| serde_json::json!({"op":"affine","constant":v,"terms":[]});
    let state = |i: usize| serde_json::json!({"op":"state","state":i});
    let write = serde_json::json!({"kind":"assign","state":1,"rhs":{"op":"divide","left":c(f64::MIN_POSITIVE*16.),"right":c(3.)}});
    value["program"]["events"][1]["body"] = serde_json::json!([
 {"kind":"if","origin":origin,"relation":"lt","left":state(2),"right":c(3.),
  "then_body":[{"kind":"assign","state":1,"rhs":{"op":"affine","constant":0.,"terms":[{"node":3,"coefficient":1.}]}}],
  "else_body":[{"kind":"if","origin":origin,"relation":"gt","left":{"op":"affine","constant":0.,"terms":[{"node":1,"coefficient":1.}]},"right":c(0.5),"then_body":[write.clone()],"else_body":[write]}]},
 {"kind":"if","origin":origin,"relation":"ge","left":state(1),"right":c(0.),
  "then_body":[{"kind":"assign","state":2,"rhs":{"op":"add","left":state(2),"right":c(1.)}}],
  "else_body":[{"kind":"assign","state":2,"rhs":{"op":"add","left":state(2),"right":c(1.)}}]}]);
    let (m, t, mut controller, mut calendar) = fixture_value(value);
    for _ in 0..3 {
        controller
            .accept_changed_events(&m, &t, &mut calendar, event_acceptance::Strategy::Static)
            .unwrap();
    }
    assert_eq!(controller.accepted.states[2], 3.);
    assert!(!controller.accepted.value_proofs.contains_key(&1));
    assert!(controller.accepted.state_bounds[1].lo < controller.accepted.state_bounds[1].hi);
    let inputs = t.value_bounds(1.);
    let context = crate::event_value_proof::Context::try_new(
        &m,
        &t,
        &inputs,
        &controller.accepted.value_proofs,
        None,
    )
    .unwrap();
    let (result, report) = crate::diagnostics::capture(Default::default(), || {
        m.conditions.select_with_proofs(
            &[1],
            &inputs,
            &[],
            &controller.accepted.state_bounds,
            Some(&context),
        )
    });
    let selection = result.unwrap();
    assert!(!selection.actions.is_empty());
    assert_eq!(report.counters.get("event_branch_proof_attempts"), Some(&2));
    let limbs = report
        .counters
        .get("history_local_comparison_limb_items")
        .copied()
        .unwrap_or(0);
    println!("actual branch-created Rational equality funded limb items={limbs}, expected>=34");
    assert_eq!(
        report.counters.get("history_merge_large_pairs"),
        Some(&1),
        "the actual merge must compare two branch-created large rationals"
    );
    assert!(limbs>=34,"the compared yes/no branch-produced normal 16*MIN_POSITIVE/3 rationals need 34 numerator/denominator limbs; original exact=None cannot price this equality");
    // Efficient exact comparisons may let any particular candidate succeed.
    // Reprepare the same pending batch with its original default Work until real
    // paid preparation exhausts it; never publish, refund, or inject a debit.
    let before = controller.accepted.clone();
    let records = serde_json::to_value(&controller.records).unwrap();
    let outputs = controller.outputs.clone();
    let cursor = controller.event;
    let pending_time = calendar[cursor].time;
    let probes = [
        f64::from_bits(pending_time.to_bits() - 1),
        pending_time,
        f64::from_bits(pending_time.to_bits() + 1),
    ];
    let signature = |q: &[ScheduledEvent]| {
        q.iter()
            .map(|e| {
                (
                    e.analytic_test_snapshot(),
                    probes.map(|time| e.physical_order_at(time)),
                )
            })
            .collect::<Vec<_>>()
    };
    let prior_calendar = signature(&calendar);
    let source = m.source_context.as_ref().unwrap();
    let work = source.borrow_work();
    let assert_complete_frame = |actual: &Frame, expected: &Frame| {
        assert_frame_unchanged(actual, expected);
        assert_eq!(
            actual.circuit.forcing_frame_snapshot(),
            expected.circuit.forcing_frame_snapshot()
        );
        assert!(actual.operators.same_forcing_frame(&expected.operators));
        assert!(std::sync::Arc::ptr_eq(
            actual.operators.source_context.as_ref().unwrap(),
            source
        ));
        assert!(work.same_owner(actual.operators.history_copy_work().unwrap()));
    };
    let assert_accepted = |actual: &Controller, q: &[ScheduledEvent]| {
        assert_complete_frame(&actual.accepted, &before);
        assert_eq!(actual.event, cursor);
        assert_eq!(signature(q), prior_calendar);
        assert_eq!(serde_json::to_value(&actual.records).unwrap(), records);
        assert_eq!(actual.outputs.len(), outputs.len());
        for (a, b) in actual.outputs.iter().zip(&outputs) {
            assert_complete_frame(a, b);
        }
        assert!(work.same_owner(source.borrow_work()));
    };
    assert_accepted(&controller, &calendar);
    // Independent exact oracle: 16*MIN_POSITIVE/3 = 2^-1018/3.
    let three = num_rational::BigRational::from_integer(3.into());
    let expected = num_rational::BigRational::new(1.into(), three.numer() << 1018usize);
    let mut attempts = 0;
    let mut successes = 0;
    let mut history_advances = 0;
    loop {
        attempts += 1;
        // A safety limit is only a failing guard, never an exhaustion oracle.
        assert!(attempts <= 100_000, "real default Work did not exhaust");
        let prior_used = work.spent();
        let (result, report) = crate::diagnostics::capture(Default::default(), || {
            event_acceptance::test_prepare_discard_changed_events(
                &controller,
                &m,
                &t,
                &calendar,
                event_acceptance::Strategy::Static,
                |candidate| {
                    assert_eq!(candidate.states[2], 4.);
                    assert_eq!(candidate.value_proofs.get(&1), Some(&expected));
                    let bounds = candidate.state_bounds[1];
                    assert!(bounds.lo < bounds.hi);
                    assert!(bounds.lo <= candidate.states[1] && candidate.states[1] <= bounds.hi);
                    assert!(num_rational::BigRational::from_float(bounds.lo).unwrap() <= expected);
                    assert!(expected <= num_rational::BigRational::from_float(bounds.hi).unwrap());
                    assert!(std::sync::Arc::ptr_eq(
                        candidate.operators.source_context.as_ref().unwrap(),
                        source
                    ));
                    assert!(work.same_owner(candidate.operators.history_copy_work().unwrap()));
                },
            )
        });
        history_advances += report.stages.get("history.advance").map_or(0, |s| s.calls);
        assert!(
            work.spent() > prior_used,
            "full preparation must pay real work"
        );
        assert_accepted(&controller, &calendar);
        match result {
            Ok(()) => successes += 1,
            Err(error) => {
                assert_eq!(error.kind, "step_budget");
                break;
            }
        }
    }
    assert!(
        successes > 0,
        "exercise and inspect an unpublished full candidate"
    );
    assert!(
        history_advances > 0,
        "real prepare sequence must advance history"
    );
    let used = work.spent();
    assert!(used > 1_000_000_000);
    println!("actual large-branch default exhaustion: attempts={attempts}, successes={successes}, history_advances={history_advances}, used={used}");
    for _ in 0..2 {
        // The normal entry must reject at its original source.charge(0), before
        // cloning or running another helper; these retries must not spend work.
        let (result, report) = crate::diagnostics::capture(Default::default(), || {
            controller.accept_changed_events(
                &m,
                &t,
                &mut calendar,
                event_acceptance::Strategy::Static,
            )
        });
        assert_eq!(result.unwrap_err().kind, "step_budget");
        assert!(report.counters.is_empty() && report.stages.is_empty());
        assert_eq!(work.spent(), used);
        assert_accepted(&controller, &calendar);
    }
}

#[test]
fn shape_admission_duplicate_predicates_keep_physical_history_deadline() {
    use serde_json::{json, Value};
    fn sum(mut values: Vec<Value>) -> Value {
        if values.len() == 1 {
            return values.pop().unwrap();
        }
        let right = values.split_off(values.len() / 2);
        json!({"op":"add","left":sum(values),"right":sum(right)})
    }
    let mut value = source_fixture::fixture();
    let origin = value["program"]["contributions"][0]["origin"].clone();
    let choice = json!({"op":"select","relation":"gt","left":{"op":"operator","operator":0},
        "right":{"op":"affine","constant":0.5,"terms":[]},
        "then_value":{"op":"affine","constant":1.,"terms":[]},
        "else_value":{"op":"affine","constant":0.,"terms":[]},"origin":origin});
    let mut choices = vec![choice; 140];
    choices.push(value["program"]["contributions"][3]["rhs"].clone());
    value["program"]["contributions"][3]["rhs"] = sum(choices);
    let (m, t, mut c, mut q) = fixture_value(value);
    for _ in 0..2 {
        c.accept_changed_events(&m, &t, &mut q, event_acceptance::Strategy::Static)
            .unwrap();
    }
    assert_eq!(c.accepted.time, 0.5);
    assert_eq!(
        c.accepted
            .operators
            .next_breakpoint_for_event(0.5, q.get(c.event), &m)
            .unwrap(),
        Some(0.625)
    );
    assert!(c
        .accepted
        .operators
        .source_root_at(0.625)
        .unwrap()
        .is_some());
}

#[test]
fn shape_admission_129_distinct_predicates_preserve_original_refusal() {
    use serde_json::{json, Value};
    fn sum(mut values: Vec<Value>) -> Value {
        if values.len() == 1 {
            return values.pop().unwrap();
        }
        let right = values.split_off(values.len() / 2);
        json!({"op":"add","left":sum(values),"right":sum(right)})
    }
    let mut value = source_fixture::fixture();
    let origin = value["program"]["contributions"][0]["origin"].clone();
    let mut choices: Vec<_> = (0..129)
        .map(|i| {
            json!({"op":"select","relation":"gt",
        "left":{"op":"operator","operator":0},
        "right":{"op":"affine","constant":0.125+(i as f64)/256.,"terms":[]},
        "then_value":{"op":"affine","constant":1.,"terms":[]},
        "else_value":{"op":"affine","constant":0.,"terms":[]},"origin":origin})
        })
        .collect();
    choices.push(value["program"]["contributions"][3]["rhs"].clone());
    value["program"]["contributions"][3]["rhs"] = sum(choices);
    let request: Request = serde_json::from_value(value).unwrap();
    let trajectory = Trajectory::new(request.transient.unwrap(), request.driven.len()).unwrap();
    let model = EventModel::new_with_trajectory(
        request.program,
        request.driven,
        request.tolerances,
        Some(&trajectory),
    )
    .unwrap();
    let token = model.history_admission.as_ref().unwrap().clone();
    let error = Operators::new_history_consumer(token, &model.initial(), 1.)
        .err()
        .expect("129 distinct guards must retain the 128 limit");
    assert_eq!(error.kind, "condition_precision");
    assert_eq!(error.message, "history target predicate budget exhausted");
}

// GUARDS: LANG, EVENT-ORDER, TIMED-OPERATOR, COMPOSE.
thread_local! { static STAGED_SHAPED_FIXTURE: std::cell::Cell<bool> = const { std::cell::Cell::new(false) }; }
fn staged_shaped_value(mut value: serde_json::Value) -> serde_json::Value {
    let stop = value["transient"]["stop"].as_f64().unwrap();
    assert!(stop == 1. || stop == 2.);
    let knots:Vec<_>=(0..85).map(|i|serde_json::json!({
        "time_numerator":(i * stop as usize).to_string(),"time_denominator":"84","value_V":0.5
    })).collect();
    value["transient"]["pwl_errors_V"] =
        serde_json::json!([{"voltage_error_bound_V":1e-12,"exact_knots":knots}]);
    value
}
fn with_staged_shape(f: impl FnOnce()) {
    struct Reset;
    impl Drop for Reset {
        fn drop(&mut self) {
            STAGED_SHAPED_FIXTURE.with(|x| x.set(false));
        }
    }
    STAGED_SHAPED_FIXTURE.with(|x| x.set(true));
    let _reset = Reset;
    let (r, d) = crate::diagnostics::capture(Default::default(), || {
        f();
        Ok(())
    });
    r.unwrap();
    assert!(
        d.counters
            .get("shaped_range_search_compare")
            .copied()
            .unwrap_or(0)
            > 0
    );
    println!("Controller shaped actual range counters={:?}", d.counters);
}
#[test]
fn staged_shaped_controller_p5_nonpoint_and_overlap_refusal() {
    with_staged_shape(nonpoint_exact_history_root_window_does_not_silently_merge_a_timer);
}
#[test]
fn staged_shaped_controller_p6_two_late_failures_legal_retry_clean_full_frame() {
    with_staged_shape(two_final_candidate_failures_then_legal_retry_match_clean_controller);
}
#[test]
fn staged_shaped_controller_actual_history_root_and_sample() {
    with_staged_shape(warm_static_controller_schedules_actual_ordinary_history_midpoint);
}

#[test]
fn staged_shaped_controller_default_range_exhaustion_and_full_frame_sticky_retries() {
    let (m, t, mut c, mut q) = fixture_value(staged_shaped_value(source_fixture::fixture()));
    for _ in 0..2 {
        c.accept_changed_events(&m, &t, &mut q, event_acceptance::Strategy::Static)
            .unwrap();
    }
    let before = c.accepted.clone();
    let records = serde_json::to_value(&c.records).unwrap();
    let calendar = q
        .iter()
        .map(|e| (e.event, e.time, e.bounds()))
        .collect::<Vec<_>>();
    let cursor = c.event;
    let work = m.source_context.as_ref().unwrap().borrow_work();
    assert!(std::sync::Arc::ptr_eq(
        m.source_context.as_ref().unwrap(),
        c.accepted.operators.source_context.as_ref().unwrap()
    ));
    let proof_inputs = t.value_bounds(0.5);
    let proof_root = crate::exact_source::RootTime::point(0.5).unwrap();
    let context = crate::event_value_proof::Context::try_new(
        &m,
        &t,
        &proof_inputs,
        &before.value_proofs,
        Some(&proof_root),
    )
    .unwrap();
    assert!(
        context.floor_work().is_none(),
        "history accounting must not grant Floor role"
    );
    let local = crate::event_value_proof::LocalState::try_with_context(
        &before.state_bounds,
        Some(&context),
    )
    .unwrap();
    assert!(local.floor_work().is_none());
    let selection = m.conditions.select(&[1], &proof_inputs).unwrap();
    let guard_projection = crate::event_accuracy::GuardBounds::for_model(&m, None).unwrap();
    let mut actual = 0;
    loop {
        // Rebuild and solve a real ordinary consumer using this prepared request.
        // No debit, quota override, helper-only owner, or candidate refund occurs here.
        match crate::event_value_proof::history::input_range(&m, &t, I { lo: 0.5, hi: 0.625 }) {
            Ok((values, slopes)) => {
                assert_eq!(values, [I::point(0.5)]);
                assert_eq!(slopes, [I::ZERO]);
                actual += 1;
            }
            Err(error) => {
                assert_eq!(error.kind, "step_budget");
                break;
            }
        }
        assert!(
            actual < 100_000,
            "default quota did not constrain real consumer work"
        );
    }
    println!(
        "actual shaped range reads before default exhaustion={actual}; used={}",
        work.spent()
    );
    assert!(actual > 1);
    assert!(work.spent() > 1_000_000_000);
    let used = work.spent();
    let next_event = q.get(cursor).unwrap().clone();
    let independent_root = crate::exact_source::RootTime::point(0.625).unwrap();
    for _ in 0..2 {
        // Actual history-owner exhaustion must reach all calendar proof accessors.
        // No helper may reconstruct a clock root after the shared request has failed.
        let (result, report) = crate::diagnostics::capture(Default::default(), || {
            event_root(&m, std::slice::from_ref(&next_event))
        });
        assert_eq!(result.unwrap_err().kind, "step_budget");
        assert!(report.counters.is_empty() && report.stages.is_empty());
        assert_eq!(
            event_bounds(&m, &next_event).unwrap_err().kind,
            "step_budget"
        );
        assert_eq!(
            event_order(&m, &t, &next_event, 0.625).unwrap_err().kind,
            "step_budget"
        );
        assert_eq!(
            source_root_bounds(&m, &independent_root).unwrap_err().kind,
            "step_budget"
        );
        assert_eq!(work.spent(), used);
        let (result, report) = crate::diagnostics::capture(Default::default(), || {
            assert_eq!(
                crate::event_accuracy::GuardBounds::for_model(&m, None)
                    .err()
                    .unwrap()
                    .kind,
                "step_budget"
            );
            assert_eq!(
                guard_projection
                    .active_inputs_history(0, work)
                    .unwrap_err()
                    .kind,
                "step_budget"
            );
            assert_eq!(
                independent_schedule(&m, &t).err().unwrap().kind,
                "step_budget"
            );
            assert_eq!(
                crate::schedule::copy_calendar(&q, &m).err().unwrap().kind,
                "step_budget"
            );
            assert_eq!(before.candidate_clone().err().unwrap().kind, "step_budget");
            assert_eq!(
                crate::event_value_proof::apply_charged(
                    &m,
                    &selection,
                    &proof_inputs,
                    &before.state_bounds,
                    &before.state_bounds,
                    &context
                )
                .unwrap_err()
                .kind,
                "step_budget"
            );
            assert_eq!(
                time_provenance::apply_charged(
                    &m,
                    &t,
                    &selection,
                    &before.time_proofs,
                    Some(&proof_root),
                    &before.state_bounds,
                    &before.state_bounds
                )
                .unwrap_err()
                .kind,
                "step_budget"
            );
            assert_eq!(local.try_clone().err().unwrap().kind, "step_budget");
            assert_eq!(
                local
                    .try_value(&crate::ir::Expression::State { state: 0 }, &[])
                    .unwrap_err()
                    .kind,
                "step_budget"
            );
            assert_eq!(
                crate::event_value_proof::history::inputs(&m, &t, 0.5)
                    .unwrap_err()
                    .kind,
                "step_budget"
            );
            assert_eq!(
                crate::event_value_proof::history::input_bounds(&m, &t, 0.5)
                    .unwrap_err()
                    .kind,
                "step_budget"
            );
            assert_eq!(
                crate::event_value_proof::history::input_range(&m, &t, I::point(0.5))
                    .unwrap_err()
                    .kind,
                "step_budget"
            );
            assert_eq!(
                crate::event_value_proof::Context::try_new(
                    &m,
                    &t,
                    &[I::point(0.5)],
                    &before.value_proofs,
                    Some(&independent_root)
                )
                .err()
                .unwrap()
                .kind,
                "step_budget"
            );
            assert_eq!(
                crate::event_value_proof::history::equal(
                    &before.value_proofs,
                    &before.value_proofs,
                    work
                )
                .unwrap_err()
                .kind,
                "step_budget"
            );
            assert_eq!(
                time_provenance::equal_history(&before.time_proofs, &before.time_proofs, work)
                    .unwrap_err()
                    .kind,
                "step_budget"
            );
            assert_eq!(
                before
                    .operators
                    .same_reset_history_paid(&before.operators, work)
                    .unwrap_err()
                    .kind,
                "step_budget"
            );
            Ok(())
        });
        result.unwrap();
        assert!(report.counters.is_empty() && report.stages.is_empty());
        assert_eq!(work.spent(), used);
        let (result, report) = crate::diagnostics::capture(Default::default(), || {
            c.accept_changed_events(&m, &t, &mut q, event_acceptance::Strategy::Static)
        });
        assert_eq!(result.unwrap_err().kind, "step_budget");
        assert!(
            report.counters.is_empty(),
            "retry entered helpers: {:?}",
            report.counters
        );
        assert!(report.stages.is_empty(), "retry prepared a candidate");
        assert_eq!(work.spent(), used);
        assert_frame_unchanged(&c.accepted, &before);
        assert_eq!(c.event, cursor);
        assert_eq!(
            q.iter()
                .map(|e| (e.event, e.time, e.bounds()))
                .collect::<Vec<_>>(),
            calendar
        );
        assert_eq!(serde_json::to_value(&c.records).unwrap(), records);
    }
}
