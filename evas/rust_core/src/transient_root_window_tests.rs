//! Real source-window candidates rejected at the final voltage gate on one controller.
use super::*;
use crate::ir::{Program, Tolerances, TransientInputs};
use serde_json::json;

fn fixture() -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    let origin = json!({"source":"root-window-rollback.va","line":1,"column":1,"instance":"dut"});
    let mut second_origin = origin.clone();
    second_origin["line"] = json!(2);
    let constant = |x: f64| json!({"op":"affine","constant":x,"terms":[]});
    let program: Program = serde_json::from_value(json!({
        "schema_version":SCHEMA_VERSION,"nodes":["0","u","y","z"],
        "states":[{"instance":"dut","name":"q","kind":"real","initial":0}],
        "operators":[
            {"kind":"transition","input":{"op":"select","relation":"gt",
                "left":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]},
                "right":constant(0.45),"then_value":constant(0.0),"else_value":{"op":"state","state":0},"origin":origin},
                "delay":0,"rise":0.07,"fall":0.07,"origin":origin},
            {"kind":"transition","input":{"op":"state","state":0},
                "delay":0,"rise":0.07,"fall":0.07,"origin":second_origin}],
        "events":[{"origin":origin,"trigger":{"kind":"timer","start":0.1,"period":0.2,
            "time_tolerance":1e-12,"enabled":true},"body":[{"kind":"assign","state":0,
            "rhs":{"op":"add","left":constant(1.0),"right":{"op":"multiply","left":constant(-1.0),"right":{"op":"state","state":0}}}}]}],
        "contributions":[
            {"branch":{"instance":"dut","local_positive":"p0","local_negative":"r","kind":"voltage"},
             "positive":2,"negative":0,"rhs":{"op":"operator","operator":0},"origin":origin},
            {"branch":{"instance":"dut","local_positive":"p1","local_negative":"r","kind":"voltage"},
             "positive":3,"negative":0,"rhs":{"op":"operator","operator":1},"origin":origin}]
    })).unwrap();
    let model = EventModel::new(program, vec!["u".into()], Tolerances::default()).unwrap();
    let trajectory = Trajectory::new(
        TransientInputs {
            analytic_sources: vec![],
            pwl_errors_v: None,
            pwl: vec![vec![[0., 0.], [0.3, 0.], [0.4, 0.9], [0.8, 0.9]]],
            output_times: vec![0., 0.05, 0.2, 0.325, 0.45, 0.8],
            strobetimes: vec![],
            stop: 0.8,
            max_step: 0.1,
            proof_work_limit: None,
        },
        1,
    )
    .unwrap();
    let states = model.initial();
    let operators = Operators::new(&model.program, &trajectory, &model.driven, &states).unwrap();
    let circuit = model
        .circuit_with(&states, &operators.values(0.).unwrap())
        .unwrap();
    let accepted = Frame {
        value_proofs: Default::default(),
        time_proofs: Default::default(),
        time: 0.,
        state_bounds: states.iter().copied().map(I::point).collect(),
        states,
        solution: circuit.solve(&trajectory.values(0.)).unwrap(),
        circuit,
        operators,
    };
    let calendar = independent_schedule(&model, &trajectory).unwrap();
    (
        model,
        trajectory,
        Controller {
            accepted,
            event: 0,
            records: vec![],
            outputs: vec![],
        },
        calendar,
    )
}

fn same_frame(actual: &Frame, expected: &Frame) {
    assert_eq!(actual.time.to_bits(), expected.time.to_bits());
    assert_eq!(actual.states, expected.states);
    assert_eq!(actual.state_bounds, expected.state_bounds);
    assert_eq!(actual.value_proofs, expected.value_proofs);
    assert_eq!(actual.time_proofs, expected.time_proofs);
    assert_eq!(
        serde_json::to_value(&actual.solution).unwrap(),
        serde_json::to_value(&expected.solution).unwrap()
    );
    // Includes Source.same_epoch: plan identity, target, last root/window and cursor.
    assert!(actual.operators.same_reset_history(&expected.operators));
    for time in [actual.time, 0.2, 0.3, 0.325, 0.45, 0.8] {
        if time >= actual.time {
            assert_eq!(
                actual.operators.values(time).unwrap(),
                expected.operators.values(time).unwrap()
            );
            assert_eq!(
                actual.operators.bounds(time).unwrap(),
                expected.operators.bounds(time).unwrap()
            );
        }
    }
}

fn copy_record(record: &EventRecord) -> EventRecord {
    EventRecord {
        time: record.time,
        observation_time_bounds: record.observation_time_bounds,
        event: record.event,
        origin: record.origin.clone(),
        kind: record.kind,
        guard_value: record.guard_value,
        fired_triggers: record
            .fired_triggers
            .iter()
            .map(|f| FiredTrigger {
                trigger: f.trigger,
                kind: f.kind,
                guard_value: f.guard_value,
                time_bounds: f.time_bounds,
            })
            .collect(),
        before: record.before.clone(),
        after: record.after.clone(),
        display_records: record.display_records.clone(),
    }
}

fn calendar_signature(calendar: &[ScheduledEvent]) -> Vec<(usize, u64, I, String)> {
    calendar
        .iter()
        .map(|event| {
            (
                event.event,
                event.time.to_bits(),
                event.bounds(),
                format!(
                    "{:?}",
                    crate::schedule::common_root(std::slice::from_ref(event))
                ),
            )
        })
        .collect()
}

#[test]
fn source_root_window_final_voltage_failure_retries_on_the_same_controller() {
    let (model, trajectory, mut controller, mut calendar) = fixture();
    controller
        .accept_changed_events(
            &model,
            &trajectory,
            &mut calendar,
            event_acceptance::Strategy::Static,
        )
        .unwrap();
    assert_eq!(controller.event, 1);
    assert_eq!(controller.accepted.states, [1.]);
    assert!(!controller.outputs.is_empty());
    let before = controller.accepted.clone();
    let outputs = controller.outputs.clone();
    let records = serde_json::to_value(&controller.records).unwrap();
    let original_calendar = calendar_signature(&calendar);
    // Untouched comparison controller owns the same immutable accepted seed.
    // Sharing pure source proof identity permits exact history comparison, not
    // physical mutation: only the tested controller prepares failed candidates.
    let mut clean = Controller {
        accepted: before.clone(),
        event: controller.event,
        records: controller.records.iter().map(copy_record).collect(),
        outputs: outputs.clone(),
    };
    let mut clean_calendar = calendar.clone();
    let root = crate::schedule::common_root(&calendar[1..2]).unwrap();
    let cut = crate::exact_source::RootTime::point(0.3).unwrap();
    assert_eq!(root.order(&cut), std::cmp::Ordering::Greater);
    assert!(calendar[1].bounds().lo <= 0.3 && 0.3 <= calendar[1].bounds().hi);
    for _ in 0..2 {
        let (mut candidate, candidate_records, end) = controller
            .prepare_events_until(
                &model,
                &trajectory,
                &calendar,
                Some(calendar[controller.event].time),
            )
            .unwrap();
        assert_eq!(candidate.states, [0.]);
        assert_eq!(candidate_records.len(), 1);
        assert!(!candidate.operators.same_reset_history(&before.operators));
        let pending = calendar[end..].to_vec();
        controller
            .prepare_physical_history(
                &model,
                &trajectory,
                &mut candidate,
                &calendar[controller.event..end],
                &pending,
            )
            .unwrap();
        // All root-window/source-history preparation above is real. Corrupt
        // only the disposable candidate at the actual final voltage gate.
        candidate.solution.voltages[2] += 0.01;
        let error = Controller::prepare_final_history(
            &model,
            &trajectory,
            candidate,
            event_acceptance::CalendarPlan::Held(pending),
        )
        .err()
        .unwrap();
        assert_eq!(error.kind, "waveform_accuracy");
        assert!(error.message.contains("same-time forward error at y:"));
        same_frame(&controller.accepted, &before);
        assert_eq!(controller.event, 1);
        assert_eq!(serde_json::to_value(&controller.records).unwrap(), records);
        assert_eq!(calendar_signature(&calendar), original_calendar);
        assert_eq!(controller.outputs.len(), outputs.len());
        for (actual, expected) in controller.outputs.iter().zip(&outputs) {
            same_frame(actual, expected);
        }
    }
    // No process/controller restart and no removal of the source corner.
    controller
        .accept_changed_events(
            &model,
            &trajectory,
            &mut calendar,
            event_acceptance::Strategy::Static,
        )
        .unwrap();
    clean
        .accept_changed_events(
            &model,
            &trajectory,
            &mut clean_calendar,
            event_acceptance::Strategy::Static,
        )
        .unwrap();
    same_frame(&controller.accepted, &clean.accepted);
    assert_eq!(controller.accepted.states, [0.]);
    assert_eq!(controller.event, 2);
    assert_eq!(controller.event, clean.event);
    assert_eq!(
        calendar_signature(&calendar),
        calendar_signature(&clean_calendar)
    );
    assert_eq!(
        serde_json::to_value(&controller.records).unwrap(),
        serde_json::to_value(&clean.records).unwrap()
    );
    assert_eq!(controller.outputs.len(), clean.outputs.len());
    for (actual, expected) in controller.outputs.iter().zip(&clean.outputs) {
        same_frame(actual, expected);
    }
}
