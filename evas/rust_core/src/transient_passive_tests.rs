//! Observer state, records and its timer calendar form the physical transaction.
use super::*;
use crate::ir::{Program, Tolerances, TransientInputs};
use serde_json::json;

fn fixture(due: f64) -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    fixture_with_period(due, 0.)
}

fn fixture_with_period(
    due: f64,
    period: f64,
) -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    let physical = json!({"source":"passive.va","line":1,"column":1,"instance":"D"});
    let observer = json!({"source":"passive.va","line":2,"column":1,"instance":"M"});
    let constant = |value: f64| json!({"op":"affine","constant":value,"terms":[]});
    let timer =
        json!({"kind":"timer","start":0.5,"period":0,"time_tolerance":0.001,"enabled":true});
    let voltage = json!({"op":"affine","constant":0,"terms":[{"node":2,"coefficient":1}]});
    let program: Program = serde_json::from_value(json!({
        "schema_version":SCHEMA_VERSION,"nodes":["0","u","y"],"operators":[],
        "states":[{"instance":"D","name":"q","kind":"real","initial":0},
            {"instance":"M","name":"seen","kind":"real","initial":0},
            {"instance":"M","name":"due","kind":"real","initial":2}],
        "contributions":[{"branch":{"instance":"D","local_positive":"out","local_negative":"ref","kind":"voltage"},
            "positive":2,"negative":0,"rhs":{"op":"state","state":0},"origin":physical}],
        "events":[{"origin":physical,"trigger":timer,"body":[{"kind":"assign","state":0,"rhs":constant(1.)}]},
            {"origin":observer,"trigger":timer,"body":[{"kind":"if","relation":"gt","left":voltage,"right":constant(0.5),
                "origin":observer,"then_body":[{"kind":"assign","state":1,"rhs":voltage},
                    {"kind":"assign","state":2,"rhs":constant(due)},
                    {"kind":"display","format":"seen %g","args":[{"op":"state","state":1}],"origin":observer}],"else_body":[]}]},
            {"origin":observer,"trigger":{"kind":"held_timer","start":{"op":"state","state":2},"period":constant(period),"enabled":constant(1.),"time_tolerance":0.001},
                "body":[{"kind":"assign","state":1,"rhs":constant(2.)}]}]
    })).unwrap();
    let model = EventModel::new(program, vec!["u".into()], Tolerances::default()).unwrap();
    let trajectory = Trajectory::new(
        TransientInputs {
            pwl_errors_v: None,
            strobetimes: vec![],
            pwl: vec![vec![[0., 0.], [1., 1.]]],
            output_times: vec![0., 0.25, 1.],
            stop: 1.,
            max_step: 1.,
        },
        1,
    )
    .unwrap();
    let states = model.initial();
    let state_bounds = states.iter().copied().map(I::point).collect::<Vec<_>>();
    let circuit = model.circuit(&states).unwrap();
    let calendar = schedule_held(&model, &trajectory, &state_bounds).unwrap();
    let controller = Controller {
        accepted: Frame {
            value_proofs: Default::default(),
            time_proofs: Default::default(),
            time: 0.,
            solution: circuit.solve(&trajectory.values(0.)).unwrap(),
            circuit,
            states,
            state_bounds,
            operators: Operators::default(),
        },
        event: 0,
        records: vec![],
        outputs: vec![],
    };
    (model, trajectory, controller, calendar)
}

// Negative one-shot deadlines are valid empty calendars. These rollback
// controls instead reach an unsupported periodic negative start only after
// their candidate state, display and (where present) history/proofs exist.
fn assert_negative_candidate_after_display(
    controller: &Controller,
    model: &EventModel,
    trajectory: &Trajectory,
    calendar: &[ScheduledEvent],
) -> Frame {
    let (candidate, records, _) = controller
        .prepare_events(model, trajectory, calendar)
        .unwrap();
    assert_eq!(candidate.time, 0.5);
    assert!(candidate.states[2] < 0.);
    assert!(records
        .iter()
        .any(|record| !record.display_records.is_empty()));
    candidate
}

fn assert_periodic_negative_start(error: crate::ir::Error) {
    assert_eq!(error.kind, "event_resolution");
    assert_eq!(
        error.message,
        "cannot certify dynamic timer start or period regime"
    );
}

#[test]
fn failed_observer_future_rolls_back_physical_state_display_and_timer_then_retries() {
    let (bad, trajectory, mut controller, mut calendar) = fixture_with_period(-1., 1.);
    let signature = |calendar: &Vec<ScheduledEvent>| {
        calendar
            .iter()
            .map(|e| (e.event, e.time, e.bounds()))
            .collect::<Vec<_>>()
    };
    let old = signature(&calendar);
    assert_negative_candidate_after_display(&controller, &bad, &trajectory, &calendar);
    for _ in 0..2 {
        assert_periodic_negative_start(
            controller
                .accept_relocalized(&bad, &trajectory, &mut calendar)
                .unwrap_err(),
        );
        assert_eq!(controller.accepted.time, 0.);
        assert_eq!(controller.accepted.states, [0., 0., 2.]);
        assert_eq!(
            controller.accepted.state_bounds,
            [I::ZERO, I::ZERO, I::point(2.)]
        );
        assert_eq!(controller.accepted.solution.voltages[2], 0.);
        assert_eq!(controller.event, 0);
        assert!(controller.records.is_empty() && controller.outputs.is_empty());
        assert_eq!(signature(&calendar), old);
    }
    let (good, _, mut clean, mut clean_calendar) = fixture(0.75);
    controller
        .accept_relocalized(&good, &trajectory, &mut calendar)
        .unwrap();
    clean
        .accept_relocalized(&good, &trajectory, &mut clean_calendar)
        .unwrap();
    assert_eq!(controller.accepted.states, [1., 1., 0.75]);
    assert_eq!(controller.accepted.states, clean.accepted.states);
    assert_eq!(
        controller.accepted.state_bounds,
        clean.accepted.state_bounds
    );
    assert_eq!(
        serde_json::to_value(&controller.records).unwrap(),
        serde_json::to_value(&clean.records).unwrap()
    );
    assert_eq!(signature(&calendar), signature(&clean_calendar));
    assert!(calendar.iter().any(|e| e.event == 2 && e.time == 0.75));
    controller
        .accept_relocalized(&good, &trajectory, &mut calendar)
        .unwrap();
    assert_eq!(controller.accepted.states, [1., 2., 0.75]);
}

#[test]
fn observer_samples_event_operator_tube_not_the_b_point_bound() {
    let (base, trajectory, _, _) = fixture(0.75);
    let mut value = serde_json::to_value(&base.program).unwrap();
    let origin = value["events"][0]["origin"].clone();
    value["operators"] = json!([{"kind":"idt","input":{"op":"affine","constant":1,"terms":[]},"ic":0,"origin":origin}]);
    value["contributions"][0]["rhs"] =
        json!({"op":"add","left":{"op":"state","state":0},"right":{"op":"operator","operator":0}});
    let model = EventModel::new(
        serde_json::from_value(value).unwrap(),
        base.driven.clone(),
        base.tolerances.clone(),
    )
    .unwrap();
    let states = model.initial();
    let operators = Operators::new(&model.program, &trajectory, &model.driven, &states).unwrap();
    let circuit = model
        .circuit_with(&states, &operators.values(0.).unwrap())
        .unwrap();
    let before = Frame {
        value_proofs: Default::default(),
        time_proofs: Default::default(),
        time: 0.,
        solution: circuit.solve(&trajectory.values(0.)).unwrap(),
        circuit,
        state_bounds: states.iter().copied().map(I::point).collect(),
        states,
        operators,
    };
    let (next, records) = prepare_batch_with_bounds(
        &model,
        &trajectory,
        &before,
        0.51,
        I { lo: 0.49, hi: 0.51 },
        &[0, 1],
    )
    .unwrap();
    assert!(next.state_bounds[1].lo <= 1.49 && next.state_bounds[1].hi >= 1.51);
    assert!(next.state_bounds[1].hi - next.state_bounds[1].lo > 0.019);
    assert!((next.states[1] - 1.51).abs() < 1e-12);
    assert!(
        next.solution.certified_voltage_bounds.as_ref().unwrap()[2][1]
            - next.solution.certified_voltage_bounds.as_ref().unwrap()[2][0]
            < 1e-10
    );
    assert_eq!(records.len(), 2);
    assert_eq!(before.states, [0., 0., 2.]);
}

#[test]
fn observer_only_event_does_not_restart_or_change_physical_history() {
    let (base, trajectory, _, _) = fixture(0.75);
    let mut value = serde_json::to_value(&base.program).unwrap();
    let origin = value["events"][0]["origin"].clone();
    value["operators"] =
        json!([{"kind":"idt","input":{"op":"state","state":0},"ic":0,"origin":origin}]);
    value["contributions"][0]["rhs"] =
        json!({"op":"add","left":{"op":"state","state":0},"right":{"op":"operator","operator":0}});
    let model = EventModel::new(
        serde_json::from_value(value).unwrap(),
        base.driven.clone(),
        base.tolerances.clone(),
    )
    .unwrap();
    let states = model.initial();
    let operators = Operators::new(&model.program, &trajectory, &model.driven, &states).unwrap();
    let circuit = model
        .circuit_with(&states, &operators.values(0.).unwrap())
        .unwrap();
    let before = Frame {
        value_proofs: Default::default(),
        time_proofs: Default::default(),
        time: 0.,
        solution: circuit.solve(&trajectory.values(0.)).unwrap(),
        circuit,
        state_bounds: states.iter().copied().map(I::point).collect(),
        states,
        operators,
    };
    let (first, _) = prepare_batch(&model, &trajectory, &before, 0.5, &[0, 1]).unwrap();
    let observed = prepare_batch(&model, &trajectory, &first, 0.75, &[2])
        .unwrap()
        .0;
    let query = prepare_event(&model, &trajectory, &first, 0.75, &[]).unwrap();
    assert_eq!(observed.states, [1., 2., 0.75]);
    assert_eq!(query.states, [1., 1., 0.75]);
    assert!(observed.operators.same_reset_history(&query.operators));
    for time in [0.75, 0.875, 1.] {
        assert_eq!(
            observed.operators.values(time).unwrap(),
            query.operators.values(time).unwrap()
        );
        assert_eq!(
            observed.operators.bounds(time).unwrap(),
            query.operators.bounds(time).unwrap()
        );
    }
    assert_eq!(observed.solution.voltages, query.solution.voltages);
    assert_eq!(
        observed.solution.certified_voltage_bounds,
        query.solution.certified_voltage_bounds
    );
}

#[test]
fn branch_review_same_controller_failure_keeps_history_proof_records_then_retries() {
    let o = json!({"source":"branch_rollback.va","line":1,"column":1,"instance":"D"});
    let c = |v: f64| json!({"op":"affine","constant":v,"terms":[]});
    let st = |i: usize| json!({"op":"state","state":i});
    let a = json!([{"kind":"assign","state":0,"rhs":c(1.)}]);
    let p=serde_json::from_value(json!({"schema_version":SCHEMA_VERSION,"nodes":["0","u","y","z"],"states":[{"instance":"D","name":"q","kind":"real","initial":0},{"instance":"D","name":"h","kind":"real","initial":0},{"instance":"D","name":"due","kind":"real","initial":2}],"operators":[{"kind":"idt","input":c(1.),"ic":0.25,"origin":o}],"events":[{"origin":o,"trigger":{"kind":"timer","start":0.5,"period":0,"enabled":true,"time_tolerance":1e-6},"body":[{"kind":"if","relation":"ge","left":st(1),"right":c(0.),"then_body":a,"else_body":a,"origin":o},{"kind":"display","format":"q=%g","args":[st(0)],"origin":o},{"kind":"assign","state":2,"rhs":{"op":"add","left":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]},"right":c(-0.75)}}]},{"origin":o,"trigger":{"kind":"held_timer","start":st(2),"period":c(0.),"enabled":c(1.),"time_tolerance":1e-6},"body":[{"kind":"assign","state":0,"rhs":c(2.)}]}],"contributions":[{"origin":o,"branch":{"instance":"D","local_positive":"out","local_negative":"ref","kind":"voltage"},"positive":2,"negative":0,"rhs":st(0)},{"origin":o,"branch":{"instance":"D","local_positive":"hist","local_negative":"ref","kind":"voltage"},"positive":3,"negative":0,"rhs":{"op":"operator","operator":0}}]})).unwrap();
    let model = EventModel::new(p, vec!["u".into()], Tolerances::default()).unwrap();
    let mut bad_program = serde_json::to_value(&model.program).unwrap();
    bad_program["events"][1]["trigger"]["period"] = c(1.);
    let bad_model = EventModel::new(
        serde_json::from_value(bad_program).unwrap(),
        model.driven.clone(),
        model.tolerances.clone(),
    )
    .unwrap();
    let traj = |points| {
        Trajectory::new(
            TransientInputs {
                pwl_errors_v: None,
                pwl: vec![points],
                strobetimes: vec![],
                output_times: vec![0., 0.25, 0.6, 1.],
                stop: 1.,
                max_step: 0.1,
            },
            1,
        )
        .unwrap()
    };
    let bad = traj(vec![[0., 0.], [1., 1.]]);
    let good = traj(vec![[0., 0.], [0.5, 1.5], [1., 2.]]);
    let make = || {
        let states = model.initial();
        let mut bounds: Vec<_> = states.iter().copied().map(I::point).collect();
        bounds[1] = I {
            lo: -1e-12,
            hi: 1e-12,
        };
        let ops = Operators::new(&model.program, &bad, &model.driven, &states).unwrap();
        let circuit = model
            .circuit_with(&states, &ops.values(0.).unwrap())
            .unwrap();
        let calendar = schedule_held(&model, &bad, &bounds).unwrap();
        let proof = crate::exact_source::RootTime::from_clock(
            crate::exact_time::Clock {
                start: 2.,
                period: 0.,
                index: 0,
            },
            I::point(2.),
        )
        .unwrap();
        (
            Controller {
                accepted: Frame {
                    value_proofs: Default::default(),
                    time_proofs: std::collections::BTreeMap::from([(2, proof)]),
                    time: 0.,
                    solution: circuit.solve(&[0.]).unwrap(),
                    circuit,
                    operators: ops,
                    states,
                    state_bounds: bounds,
                },
                event: 0,
                records: vec![],
                outputs: vec![],
            },
            calendar,
        )
    };
    let (mut tested, mut calendar) = make();
    let accepted = tested.accepted.clone();
    let sig = |v: &Vec<ScheduledEvent>| {
        v.iter()
            .map(|e| (e.event, e.time, e.bounds(), e.physical_order_at(0.75)))
            .collect::<Vec<_>>()
    };
    let old = sig(&calendar);
    let candidate = assert_negative_candidate_after_display(&tested, &bad_model, &bad, &calendar);
    assert!((candidate.operators.values(0.5).unwrap()[0] - 0.75).abs() < 1e-12);
    assert_ne!(candidate.time_proofs, accepted.time_proofs);
    for _ in 0..2 {
        let (r, d) = crate::diagnostics::capture(Default::default(), || {
            tested.accept_relocalized(&bad_model, &bad, &mut calendar)
        });
        assert_periodic_negative_start(r.unwrap_err());
        assert!(d.counters["event_equivalent_branch_proofs"] > 0);
        assert_eq!(tested.accepted.states, accepted.states);
        assert_eq!(tested.accepted.state_bounds, accepted.state_bounds);
        assert_eq!(tested.accepted.time_proofs, accepted.time_proofs);
        assert!(tested
            .accepted
            .operators
            .same_reset_history(&accepted.operators));
        assert!(tested.records.is_empty() && tested.outputs.is_empty());
        assert_eq!(sig(&calendar), old);
        assert_eq!(tested.event, 0);
    }
    let (mut clean, mut clean_calendar) = make();
    tested
        .accept_relocalized(&model, &good, &mut calendar)
        .unwrap();
    clean
        .accept_relocalized(&model, &good, &mut clean_calendar)
        .unwrap();
    assert_eq!(tested.accepted.states, clean.accepted.states);
    assert_eq!(tested.accepted.state_bounds, clean.accepted.state_bounds);
    assert_eq!(tested.accepted.time_proofs, clean.accepted.time_proofs);
    assert!(tested
        .accepted
        .operators
        .same_reset_history(&clean.accepted.operators));
    assert_eq!(
        serde_json::to_value(&tested.records).unwrap(),
        serde_json::to_value(&clean.records).unwrap()
    );
    assert_eq!(sig(&calendar), sig(&clean_calendar));
    assert_eq!(tested.outputs.len(), clean.outputs.len());
    for (x, y) in tested.outputs.iter().zip(&clean.outputs) {
        assert_eq!(x.solution.voltages, y.solution.voltages);
        assert_eq!(x.time_proofs, y.time_proofs);
    }
    tested
        .accept_relocalized(&model, &good, &mut calendar)
        .unwrap();
    clean
        .accept_relocalized(&model, &good, &mut clean_calendar)
        .unwrap();
    assert_eq!(tested.accepted.states, clean.accepted.states);
    assert_eq!(tested.accepted.states[0], 2.);
    assert!((tested.accepted.operators.values(1.).unwrap()[0] - 1.25).abs() < 1e-12);
}

#[test]
fn held_review_proof_display_calendar_failure_rolls_back_and_retries_same_controller() {
    fn proven(
        delta: f64,
        period: f64,
    ) -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
        let (base, t, mut c, cal) = fixture_with_period(delta, period);
        let mut p = serde_json::to_value(&base.program).unwrap();
        p["events"][1]["body"][0]["then_body"][1]["rhs"] = json!({"op":"add","left":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]},"right":{"op":"affine","constant":delta,"terms":[]}});
        let m = EventModel::new(
            serde_json::from_value(p).unwrap(),
            base.driven.clone(),
            base.tolerances.clone(),
        )
        .unwrap();
        let initial = crate::exact_source::RootTime::from_clock(
            crate::exact_time::Clock {
                start: 2.,
                period: 0.,
                index: 0,
            },
            I::point(2.),
        )
        .unwrap();
        c.accepted.time_proofs.insert(2, initial);
        (m, t, c, cal)
    }
    let (bad, t, mut c, mut calendar) = proven(-0.75, 1.);
    let saved = c.accepted.clone();
    let signature = |v: &Vec<ScheduledEvent>| {
        v.iter()
            .map(|e| (e.event, e.time, e.bounds(), e.physical_order_at(0.625)))
            .collect::<Vec<_>>()
    };
    let before = signature(&calendar);
    let candidate = assert_negative_candidate_after_display(&c, &bad, &t, &calendar);
    assert_ne!(candidate.time_proofs, saved.time_proofs);
    assert!(candidate.time_proofs[&2]
        .refine(candidate.state_bounds[2])
        .is_some());
    for _ in 0..2 {
        assert_periodic_negative_start(c.accept_relocalized(&bad, &t, &mut calendar).unwrap_err());
        assert_eq!(c.accepted.time_proofs, saved.time_proofs);
        assert_eq!(c.accepted.states, saved.states);
        assert_eq!(c.accepted.state_bounds, saved.state_bounds);
        assert!(c.accepted.operators.same_reset_history(&saved.operators));
        assert!(c.records.is_empty() && c.outputs.is_empty());
        assert_eq!(signature(&calendar), before);
        assert_eq!(c.event, 0);
    }
    let (good, _, mut clean, mut clean_calendar) = proven(0.125, 0.);
    c.accept_relocalized(&good, &t, &mut calendar).unwrap();
    clean
        .accept_relocalized(&good, &t, &mut clean_calendar)
        .unwrap();
    assert_eq!(c.accepted.time_proofs, clean.accepted.time_proofs);
    assert_ne!(c.accepted.time_proofs, saved.time_proofs);
    assert!(c.accepted.time_proofs[&2]
        .refine(c.accepted.state_bounds[2])
        .is_some());
    assert_eq!(c.accepted.states, clean.accepted.states);
    assert_eq!(c.accepted.state_bounds, clean.accepted.state_bounds);
    assert_eq!(signature(&calendar), signature(&clean_calendar));
    assert_eq!(
        serde_json::to_value(&c.records).unwrap(),
        serde_json::to_value(&clean.records).unwrap()
    );
    assert_eq!(c.outputs.len(), clean.outputs.len());
    for (a, b) in c.outputs.iter().zip(&clean.outputs) {
        assert_eq!(a.time_proofs, b.time_proofs);
        assert_eq!(a.solution.voltages, b.solution.voltages);
        assert_eq!(a.time_proofs, saved.time_proofs);
    }
    c.accept_relocalized(&good, &t, &mut calendar).unwrap();
    clean
        .accept_relocalized(&good, &t, &mut clean_calendar)
        .unwrap();
    assert_eq!(c.accepted.time_proofs, clean.accepted.time_proofs);
    assert_eq!(c.accepted.states, clean.accepted.states);
    assert_eq!(c.accepted.states[1], 2.);
}

#[test]
fn failed_observer_math_discards_records_states_and_calendar_then_retries() {
    let (base, trajectory, mut controller, mut calendar) = fixture(0.75);
    let mut payload = serde_json::to_value(&base.program).unwrap();
    let origin = payload["events"][1]["origin"].clone();
    let value = |x: f64| json!({"op":"affine","constant":x,"terms":[]});
    let mut actions = payload["events"][1]["body"][0]["then_body"]
        .as_array()
        .unwrap()
        .clone();
    // The domain failure follows both a state write and a display candidate.
    actions.push(json!({"kind":"assign","state":1,"rhs":{"op":"event_math","function":"sqrt","args":[value(-1.)],"origin":origin}}));
    payload["events"][1]["body"][0]["then_body"] = json!(actions);
    let bad = EventModel::new(
        serde_json::from_value(payload.clone()).unwrap(),
        base.driven.clone(),
        base.tolerances.clone(),
    )
    .unwrap();
    let signature = |c: &Vec<ScheduledEvent>| {
        c.iter()
            .map(|e| (e.event, e.time, e.bounds()))
            .collect::<Vec<_>>()
    };
    let old = signature(&calendar);
    for _ in 0..2 {
        let err = controller
            .accept_relocalized(&bad, &trajectory, &mut calendar)
            .unwrap_err();
        assert_eq!(err.kind, "event_domain");
        assert_eq!(controller.accepted.time, 0.);
        assert_eq!(controller.accepted.states, [0., 0., 2.]);
        assert_eq!(
            controller.accepted.state_bounds,
            [I::ZERO, I::ZERO, I::point(2.)]
        );
        assert!(controller.records.is_empty() && controller.outputs.is_empty());
        assert_eq!(controller.event, 0);
        assert_eq!(signature(&calendar), old);
    }
    let last = payload["events"][1]["body"][0]["then_body"]
        .as_array()
        .unwrap()
        .len()
        - 1;
    payload["events"][1]["body"][0]["then_body"][last]["rhs"]["args"] = json!([value(4.)]);
    let good = EventModel::new(
        serde_json::from_value(payload).unwrap(),
        base.driven,
        base.tolerances,
    )
    .unwrap();
    let (_, _, mut clean, mut clean_calendar) = fixture(0.75);
    controller
        .accept_relocalized(&good, &trajectory, &mut calendar)
        .unwrap();
    clean
        .accept_relocalized(&good, &trajectory, &mut clean_calendar)
        .unwrap();
    assert_eq!(controller.accepted.states, [1., 2., 0.75]);
    assert_eq!(controller.accepted.states, clean.accepted.states);
    assert_eq!(
        controller.accepted.state_bounds,
        clean.accepted.state_bounds
    );
    assert_eq!(
        serde_json::to_value(&controller.records).unwrap(),
        serde_json::to_value(&clean.records).unwrap()
    );
    assert_eq!(signature(&calendar), signature(&clean_calendar));
}

fn source_fixture(due: f64) -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    source_fixture_with_period(due, 0.)
}

fn source_fixture_with_period(
    due: f64,
    period: f64,
) -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    let (base, trajectory, _, _) = fixture_with_period(due, period);
    let mut value = serde_json::to_value(&base.program).unwrap();
    let origin = value["events"][0]["origin"].clone();
    let observer = value["events"][1]["origin"].clone();
    let mut integral_origin = origin.clone();
    integral_origin["column"] = json!(2);
    value["nodes"] = json!(["0", "u", "y", "h"]);
    value["states"][0]["initial"] = json!(1);
    value["operators"] = json!([
        {"kind":"transition","origin":origin,"delay":0,"rise":1,"fall":1,
         "input":{"op":"select","relation":"gt","origin":origin,
          "left":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]},
          "right":{"op":"affine","constant":0.25,"terms":[]},
          "then_value":{"op":"state","state":0},"else_value":{"op":"affine","constant":0,"terms":[]}}},
        {"kind":"idt","origin":integral_origin,"input":{"op":"affine","constant":1,"terms":[]},"ic":0.25}]);
    value["contributions"][0]["rhs"] = json!({"op":"multiply",
        "left":{"op":"affine","constant":0,"terms":[{"node":3,"coefficient":1}]},
        "right":{"op":"operator","operator":0}});
    value["contributions"].as_array_mut().unwrap().push(
        json!({"positive":3,"negative":0,"origin":origin,
        "branch":{"instance":"D","local_positive":"h","local_negative":"ref","kind":"voltage"},
        "rhs":{"op":"operator","operator":1}}),
    );
    value["events"][0]["body"][0]["rhs"] = json!({"op":"affine","constant":0,"terms":[]});
    value["events"][1]["body"] = json!([
        {"kind":"assign","state":1,"rhs":{"op":"affine","constant":0,"terms":[{"node":2,"coefficient":1}]}},
        {"kind":"assign","state":2,"rhs":{"op":"affine","constant":due,"terms":[]}},
        {"kind":"display","format":"source %g","args":[{"op":"state","state":1}],"origin":observer}]);
    let model = EventModel::new(
        serde_json::from_value(value).unwrap(),
        base.driven,
        base.tolerances,
    )
    .unwrap();
    let states = model.initial();
    let bounds = states.iter().copied().map(I::point).collect::<Vec<_>>();
    let operators = Operators::new(&model.program, &trajectory, &model.driven, &states).unwrap();
    let circuit = model
        .circuit_with(&states, &operators.values(0.).unwrap())
        .unwrap();
    let mut controller = Controller {
        accepted: Frame {
            time: 0.,
            value_proofs: Default::default(),
            time_proofs: Default::default(),
            solution: circuit.solve(&trajectory.values(0.)).unwrap(),
            circuit,
            states,
            state_bounds: bounds,
            operators,
        },
        event: 0,
        records: vec![],
        outputs: vec![],
    };
    let root = crate::exact_source::RootTime::point(0.25).unwrap();
    let next = prepare_root_window(
        &model,
        &trajectory,
        &controller.accepted,
        EventMoment {
            exact_root: Some(&root),
            representative: 0.25,
            observation: I::point(0.25),
            fired_roots: &[],
            prediction_end: 0.5,
        },
        &[],
    )
    .unwrap();
    controller.commit_events(next, vec![], 0);
    let calendar = schedule_held(&model, &trajectory, &controller.accepted.state_bounds).unwrap();
    (model, trajectory, controller, calendar)
}

#[test]
fn failed_source_target_epoch_and_memo_roll_back_then_same_controller_retries() {
    let (bad, trajectory, mut controller, mut calendar) = source_fixture_with_period(-1., 1.);
    let before = controller.accepted.operators.clone();
    let states = controller.accepted.states.clone();
    let bounds = controller.accepted.state_bounds.clone();
    let signature = |c: &Vec<ScheduledEvent>| {
        c.iter()
            .map(|e| (e.event, e.time, e.bounds()))
            .collect::<Vec<_>>()
    };
    let queue = signature(&calendar);
    assert_negative_candidate_after_display(&controller, &bad, &trajectory, &calendar);
    for _ in 0..2 {
        let (result, proof_work) =
            crate::diagnostics::capture(crate::diagnostics::Options::default(), || {
                controller.accept_relocalized(&bad, &trajectory, &mut calendar)
            });
        assert_periodic_negative_start(result.unwrap_err());
        // A failed complete candidate cannot publish its new q=0 proof. The
        // second attempt must certify that context again from accepted q=1.
        assert_eq!(
            proof_work.counters.get("source_plan_context_calls"),
            Some(&1)
        );
        assert_eq!(controller.accepted.time, 0.25);
        assert_eq!(controller.accepted.states, states);
        assert_eq!(controller.accepted.state_bounds, bounds);
        assert!(controller.accepted.operators.same_reset_history(&before));
        assert!(controller.records.is_empty() && controller.outputs.is_empty());
        assert_eq!(signature(&calendar), queue);
    }
    let (good, _, mut clean, mut clean_calendar) = source_fixture(0.9);
    let (result, proof_work) =
        crate::diagnostics::capture(crate::diagnostics::Options::default(), || {
            controller.accept_relocalized(&good, &trajectory, &mut calendar)
        });
    result.unwrap();
    // Certify q=0 once. Frozen-history replay may share that immutable proof
    // but must still replay its old cursor/edge and compare the whole result.
    assert_eq!(
        proof_work.counters.get("source_plan_context_calls"),
        Some(&1)
    );
    clean
        .accept_relocalized(&good, &trajectory, &mut clean_calendar)
        .unwrap();
    assert_eq!(controller.accepted.states, [0., 0.1875, 0.9]);
    assert_eq!(controller.accepted.states, clean.accepted.states);
    assert_eq!(
        controller.accepted.state_bounds,
        clean.accepted.state_bounds
    );
    assert_eq!(
        serde_json::to_value(&controller.records).unwrap(),
        serde_json::to_value(&clean.records).unwrap()
    );
    assert_eq!(signature(&calendar), signature(&clean_calendar));
    for t in [0.5, 0.625, 0.75, 0.9, 1.] {
        assert_eq!(
            controller.accepted.operators.values(t).unwrap(),
            clean.accepted.operators.values(t).unwrap()
        );
        assert_eq!(
            controller.accepted.operators.bounds(t).unwrap(),
            clean.accepted.operators.bounds(t).unwrap()
        );
    }
    // q changed from 1 to 0: keeping the old successful Plan would leave a
    // positive edge here. The newly certified target must have reversed it.
    assert_eq!(controller.accepted.operators.values(0.9).unwrap()[0], 0.);
}

#[test]
fn native_floor_crossbin_failure_preserves_controller_then_retries_exact_source() {
    let (base, trajectory, mut controller, mut calendar) = fixture(0.75);
    let mut payload = serde_json::to_value(&base.program).unwrap();
    let origin = payload["events"][1]["origin"].clone();
    payload["events"][1]["body"][0]["then_body"].as_array_mut().unwrap().push(json!({
        "kind":"assign","state":1,"rhs":{"op":"event_math","function":"floor",
        "args":[{"op":"affine","constant":0.,"terms":[{"node":1,"coefficient":2.}]}],"origin":origin}}));
    let model = EventModel::new(
        serde_json::from_value(payload).unwrap(),
        base.driven,
        base.tolerances,
    )
    .unwrap();
    let mut config = trajectory.config.clone();
    config.pwl_errors_v = Some(serde_json::from_value(json!([1e-12])).unwrap());
    let uncertain = Trajectory::new(config, 1).unwrap();
    let snapshot = |c: &Controller, cal: &Vec<ScheduledEvent>| {
        (
            c.accepted.time,
            c.accepted.states.clone(),
            c.accepted.state_bounds.clone(),
            c.accepted.value_proofs.clone(),
            c.accepted.time_proofs.clone(),
            c.event,
            serde_json::to_string(&c.records).unwrap(),
            c.outputs
                .iter()
                .map(|f| (f.time, f.states.clone(), f.state_bounds.clone()))
                .collect::<Vec<_>>(),
            cal.iter()
                .map(|e| (e.event, e.time, e.bounds()))
                .collect::<Vec<_>>(),
        )
    };
    let old = snapshot(&controller, &calendar);
    for _ in 0..2 {
        let error = controller
            .accept_relocalized(&model, &uncertain, &mut calendar)
            .unwrap_err();
        assert_eq!(error.kind, "event_condition");
        assert!(error.message.contains("floor bin"));
        assert_eq!(snapshot(&controller, &calendar), old);
    }
    let (_, _, mut clean, mut clean_calendar) = fixture(0.75);
    controller
        .accept_relocalized(&model, &trajectory, &mut calendar)
        .unwrap();
    clean
        .accept_relocalized(&model, &trajectory, &mut clean_calendar)
        .unwrap();
    assert_eq!(
        snapshot(&controller, &calendar),
        snapshot(&clean, &clean_calendar)
    );
    assert_eq!(controller.accepted.states, [1., 1., 0.75]);
}
