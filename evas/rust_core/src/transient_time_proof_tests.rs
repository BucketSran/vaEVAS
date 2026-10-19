//! Time certificates belong to the same accepted/candidate state epoch.
use super::*;
use crate::ir::{Program, Tolerances, TransientInputs};
use serde_json::json;

fn fixture() -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    fixture_impl(false)
}
fn fixture_impl(nonlinear: bool) -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    let constant = |v: f64| json!({"op":"affine","constant":v,"terms":[]});
    let time = json!({"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]});
    let guard = json!({"op":"affine","constant":-0.5,"terms":[{"node":2,"coefficient":1}]});
    let origins: Vec<_> = (0..2)
        .map(|k| json!({"source":"clock.va","line":1,"column":1,"instance":format!("C{k}")}))
        .collect();
    let mut program: Program = serde_json::from_value(json!({
        "schema_version":SCHEMA_VERSION,"nodes":["0","time","ctrl","h0","h1"],
        "states":[{"instance":"C0","name":"captured","kind":"real","initial":0},
                  {"instance":"C1","name":"captured","kind":"real","initial":0}],
        "operators":(0..2).map(|k| json!({"kind":"idt","ic":0,"origin":origins[k],
            "input":{"op":"select","relation":"lt","origin":origins[k],
                "left":{"op":"add","left":time,"right":{"op":"multiply","left":constant(-1.),"right":{"op":"state","state":k}}},
                "right":constant(0.25),"then_value":constant(1.),"else_value":constant(-1.)}})).collect::<Vec<_>>(),
        "contributions":(0..2).map(|k|json!({"positive":3+k,"negative":0,"origin":origins[k],
            "branch":{"instance":format!("C{k}"),"local_positive":"h","local_negative":"ref","kind":"voltage"},
            "rhs":{"op":"operator","operator":k}})).collect::<Vec<_>>(),
        "events":(0..2).map(|k|json!({"origin":origins[k],
            "trigger":{"kind":"cross","guard":guard,"direction":1,"time_tolerance":1e-12,"expression_tolerance":1e-10},
            "body":[{"kind":"assign","state":k,"rhs":time}]})).collect::<Vec<_>>()
    })).unwrap();
    if nonlinear {
        // dh/dt = selected_sign - h^2 forces the production nonlinear route.
        // The selected source stays +1 throughout this fixture, h(t)=tanh(t).
        // Its time/held-state predicate still owns the root proof context.
        let mut data = serde_json::to_value(&program).unwrap();
        for k in 0..2 {
            let mut input = data["operators"][k]["input"].clone();
            input["right"] = constant(2.25);
            data["operators"][k]["input"] = json!({"op":"add","left":input,
                "right":{"op":"multiply","left":constant(-1.),
                    "right":{"op":"power","base":{"op":"affine","constant":0,"terms":[{"node":3+k,"coefficient":1}]},"exponent":2}}});
        }
        for event in data["events"].as_array_mut().unwrap() {
            event["trigger"] = json!({"kind":"timer","start":0.125,"period":0.,"enabled":true,"time_tolerance":1e-12});
        }
        program = serde_json::from_value(data).unwrap();
    }
    let model = EventModel::new(
        program,
        vec!["time".into(), "ctrl".into()],
        Tolerances::default(),
    )
    .unwrap();
    let trajectory = Trajectory::new(
        TransientInputs {
            analytic_sources: vec![],
            pwl_errors_v: None,
            pwl: vec![vec![[0., 0.], [1., 1.]], vec![[0., 0.], [1., 3.]]],
            output_times: vec![0., 1.],
            stop: 1.,
            max_step: 1. / 64.,
            strobetimes: vec![],
        },
        2,
    )
    .unwrap();
    let states = model.initial();
    let bounds: Vec<_> = states.iter().copied().map(I::point).collect();
    let operators = Operators::new(&model.program, &trajectory, &model.driven, &states).unwrap();
    let circuit = model
        .circuit_with(&states, &operators.values(0.).unwrap())
        .unwrap();
    let calendar = schedule_held(&model, &trajectory, &bounds).unwrap();
    let controller = Controller {
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
    (model, trajectory, controller, calendar)
}

#[test]
fn invalid_accepted_time_certificate_is_rejected_before_candidate_or_calendar_commit() {
    let (model, trajectory, mut controller, mut calendar) = fixture();
    controller
        .accepted
        .time_proofs
        .insert(0, crate::exact_source::RootTime::point(0.5).unwrap());
    let before = calendar
        .iter()
        .map(|e| (e.event, e.time, e.bounds()))
        .collect::<Vec<_>>();
    assert!(controller
        .accept_relocalized(&model, &trajectory, &mut calendar)
        .is_err());
    assert_eq!(controller.accepted.time, 0.);
    assert_eq!(controller.accepted.states, [0., 0.]);
    assert!(controller.records.is_empty() && controller.outputs.is_empty());
    assert_eq!(
        before,
        calendar
            .iter()
            .map(|e| (e.event, e.time, e.bounds()))
            .collect::<Vec<_>>()
    );
}

#[test]
fn same_numeric_state_enclosure_with_a_different_real_time_proof_cannot_reuse_flow() {
    use num_rational::BigRational as R;
    let (model, trajectory, mut controller, mut calendar) = fixture();
    controller
        .accept_relocalized(&model, &trajectory, &mut calendar)
        .unwrap();
    let original = controller.accepted.time_proofs[&0].clone();
    assert_eq!(original, controller.accepted.time_proofs[&1]);
    let r = R::new(1.into(), 6.into()) + R::new(1.into(), (1u64 << 60).into());
    let different = crate::exact_source::RootTime::affine(
        -r,
        R::from_integer(1.into()),
        controller.accepted.state_bounds[0],
    )
    .unwrap();
    assert_ne!(original, different);
    assert_eq!(original.bounds(), different.bounds());
    let states = controller.accepted.states.clone();
    let bounds = controller.accepted.state_bounds.clone();
    controller.accepted.time_proofs.insert(0, different);
    let old = controller.accepted.operators.clone();
    let error = prepare_root_window(
        &model,
        &trajectory,
        &controller.accepted,
        EventMoment {
            exact_root: None,
            representative: 0.2,
            observation: I::point(0.2),
            fired_roots: &[],
            prediction_end: 1.,
        },
        &[],
    )
    .err()
    .unwrap();
    assert_eq!(error.kind, "condition_precision");
    assert_eq!(controller.accepted.states, states);
    assert_eq!(controller.accepted.state_bounds, bounds);
    assert!(controller.accepted.operators.same_reset_history(&old));
}

#[test]
fn nonlinear_time_proof_removal_or_update_preserves_physical_history_and_discarded_candidate() {
    use num_rational::BigRational as R;
    let (model, trajectory, mut controller, mut calendar) = fixture_impl(true);
    controller
        .accept_relocalized(&model, &trajectory, &mut calendar)
        .unwrap();
    let original = controller.accepted.clone();
    let original_flow = original.operators.history_certificate().unwrap();
    let bounds = vec![
        I {
            lo: 0.125_f64.next_down(),
            hi: 0.125_f64.next_up()
        };
        2
    ];
    let proofs: crate::exact_source::TimeProofs = (0..2)
        .map(|k| (k, crate::exact_source::RootTime::point(0.125).unwrap()))
        .collect();
    let flow = original_flow
        .restarted_with_time_proofs(0.25, I::point(0.25), &bounds, 0.5, &proofs)
        .unwrap();
    assert!(matches!(&flow, crate::continuous::Continuous::Nonlinear(_)));
    let prefix = flow.bounds(0.4).unwrap();
    let r = R::new(1.into(), 8.into()) + R::new(1.into(), (1u64 << 60).into());
    let shifted =
        crate::exact_source::RootTime::affine(-r, R::from_integer(1.into()), bounds[0]).unwrap();
    assert_ne!(shifted, proofs[&0]);
    for changed in [None, Some(shifted)] {
        let mut changed_proofs = proofs.clone();
        if let Some(proof) = changed {
            changed_proofs.insert(0, proof);
        } else {
            changed_proofs.remove(&0);
        }
        let mapped = flow
            .mapped_event_with_time_proofs(0.4, I::point(0.4), &bounds, &changed_proofs)
            .unwrap();
        // A changed proof map creates a new seed. A stale flow clone would
        // incorrectly retain pre-map queries from its earlier proof epoch.
        assert_eq!(mapped.bounds(0.3).err().unwrap().kind, "event_resolution");
        for value in mapped.bounds(0.4).unwrap() {
            let want = 0.4_f64.tanh();
            assert!(value.lo <= want && value.hi >= want);
        }
        let restarted = mapped
            .restarted_with_time_proofs(0.4, I::point(0.4), &bounds, 0.41, &changed_proofs)
            .unwrap();
        for value in restarted.bounds(0.41).unwrap() {
            let want = 0.41_f64.tanh();
            assert!(value.lo <= want && value.hi >= want);
        }
        drop(restarted);
        drop(mapped);
        assert_eq!(flow.bounds(0.4).unwrap(), prefix);
        assert_eq!(controller.accepted.time_proofs, original.time_proofs);
        assert_eq!(controller.accepted.value_proofs, original.value_proofs);
        assert_eq!(controller.accepted.states, original.states);
    }
}

#[test]
fn nonlinear_new_time_proof_failed_candidate_retries_in_same_controller_without_history_mutation() {
    let (model, trajectory, mut controller, mut calendar) = fixture_impl(true);
    let prefix = controller.accepted.operators.bounds(0.1).unwrap();
    let before = calendar
        .iter()
        .map(|e| (e.event, e.time, e.bounds()))
        .collect::<Vec<_>>();
    // First complete ordinary settlement and prove the event's new time
    // certificate is already installed. Only then corrupt its observation to
    // exercise the shared final certification gate, after history extension.
    let (mut candidate, _records, end) = controller
        .prepare_events_until(&model, &trajectory, &calendar, Some(0.125))
        .unwrap();
    assert!(controller.accepted.time_proofs.is_empty());
    assert_eq!(candidate.time_proofs.len(), 2);
    for state in 0..2 {
        assert_eq!(
            candidate.time_proofs[&state].bounds(),
            Some(I::point(0.125))
        );
    }
    assert!(matches!(
        candidate.operators.history_certificate().unwrap().as_ref(),
        crate::continuous::Continuous::Nonlinear(_)
    ));
    let expected = 0.125_f64.tanh();
    assert!((candidate.solution.voltages[3] - expected).abs() < 1e-11);
    candidate.solution.voltages[3] += 0.01;
    let error = Controller::prepare_final_history(
        &model,
        &trajectory,
        candidate,
        event_acceptance::CalendarPlan::Held(calendar[end..].to_vec()),
    )
    .err()
    .unwrap();
    assert_eq!(error.kind, "waveform_accuracy");
    assert!(error.message.contains("same-time forward error at h0:"));
    assert_eq!(controller.accepted.time, 0.);
    assert!(controller.accepted.time_proofs.is_empty());
    assert_eq!(controller.accepted.operators.bounds(0.1).unwrap(), prefix);
    assert_eq!(
        before,
        calendar
            .iter()
            .map(|e| (e.event, e.time, e.bounds()))
            .collect::<Vec<_>>()
    );
    assert!(controller.records.is_empty());
    controller
        .accept_relocalized(&model, &trajectory, &mut calendar)
        .unwrap();
    let (clean_model, clean_trajectory, mut clean, mut clean_calendar) = fixture_impl(true);
    clean
        .accept_relocalized(&clean_model, &clean_trajectory, &mut clean_calendar)
        .unwrap();
    assert_eq!(controller.accepted.time_proofs, clean.accepted.time_proofs);
    assert_eq!(controller.accepted.states, clean.accepted.states);
    assert_eq!(
        controller.accepted.operators.bounds(0.4).unwrap(),
        clean.accepted.operators.bounds(0.4).unwrap()
    );
    for value in controller.accepted.operators.bounds(0.4).unwrap() {
        let want = 0.4_f64.tanh();
        assert!(value.lo <= want && value.hi >= want);
    }
}

#[test]
fn invalid_numeric_value_proof_preserves_controller_and_calendar_then_retries() {
    use num_rational::BigRational as R;
    let (model, trajectory, mut tested, mut calendar) = fixture();
    tested
        .accepted
        .value_proofs
        .insert(0, R::new(1.into(), 2.into()));
    let old = tested.accepted.clone();
    let keys = calendar
        .iter()
        .map(|e| (e.event, e.time, e.bounds()))
        .collect::<Vec<_>>();
    assert!(tested
        .accept_relocalized(&model, &trajectory, &mut calendar)
        .is_err());
    assert_eq!(tested.accepted.value_proofs, old.value_proofs);
    assert_eq!(tested.accepted.states, old.states);
    assert!(tested.accepted.operators.same_reset_history(&old.operators));
    assert!(tested.records.is_empty() && tested.outputs.is_empty());
    assert_eq!(
        calendar
            .iter()
            .map(|e| (e.event, e.time, e.bounds()))
            .collect::<Vec<_>>(),
        keys
    );
    tested.accepted.value_proofs.clear();
    let (clean_model, clean_trajectory, mut clean, mut clean_calendar) = fixture();
    tested
        .accept_relocalized(&model, &trajectory, &mut calendar)
        .unwrap();
    clean
        .accept_relocalized(&clean_model, &clean_trajectory, &mut clean_calendar)
        .unwrap();
    assert_eq!(tested.accepted.value_proofs, clean.accepted.value_proofs);
    assert_eq!(tested.accepted.states, clean.accepted.states);
    assert_eq!(tested.accepted.state_bounds, clean.accepted.state_bounds);
    assert!(tested
        .accepted
        .operators
        .same_reset_history(&clean.accepted.operators));
}
