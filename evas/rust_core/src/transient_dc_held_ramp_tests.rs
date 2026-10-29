//! Actual mixed held-ramp Controller transaction and late rejection/retry.
use super::*;
use crate::ir::{Program, Tolerances, TransientInputs, SCHEMA_VERSION};
use serde_json::{json, Value};
use std::sync::{
    atomic::{AtomicUsize, Ordering},
    Arc,
};

fn fixture() -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    fixture_with_near_queries(false)
}
fn fixture_with_near_queries(
    near_queries: bool,
) -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    let period = 8e-9;
    let origin = json!({"source":"mixed-controller.va","line":1,"column":1,"instance":"d"});
    let constant = |x: f64| json!({"op":"affine","constant":x,"terms":[]});
    let raw = json!({"op":"add","left":{"op":"affine","constant":0,"terms":[{"node":2,"coefficient":1}]},
        "right":{"op":"multiply","left":constant(-1.),"right":{"op":"state","state":0}}});
    let lower = json!({"op":"select","relation":"lt","left":raw,"right":constant(0.),
        "then_value":constant(0.),"else_value":raw,"origin":origin});
    let phase = json!({"op":"select","relation":"gt","left":lower,"right":constant(period),
        "then_value":constant(period),"else_value":lower,"origin":origin});
    let target = json!({"op":"select","relation":"le","left":phase,"right":constant(1.5e-9),
        "then_value":constant(1.),"else_value":constant(0.),"origin":origin});
    let rail = json!({"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]});
    let p:Program = serde_json::from_value(json!({"schema_version":SCHEMA_VERSION,
        "nodes":["0","rail","$abstime","phase","guard"],
        "states":[{"instance":"d","name":"epoch","kind":"real","initial":0},
            {"instance":"d","name":"due","kind":"real","initial":period}],
        "events":[{"origin":origin,"trigger":{"kind":"held_timer","start":{"op":"state","state":1},
            "period":constant(0.),"enabled":constant(1.),"time_tolerance":1e-12},
            "body":[{"kind":"assign","state":0,"rhs":{"op":"state","state":1}},
                {"kind":"assign","state":1,"rhs":{"op":"add","left":{"op":"state","state":1},"right":constant(period)}}]}],
        "operators":[{"kind":"transition","input":target,"delay":0,"rise":40e-12,"fall":40e-12,"origin":origin}],
        "contributions":[
            {"origin":origin,"branch":{"instance":"d","local_positive":"phase","local_negative":"zref","kind":"voltage"},
                "positive":3,"negative":0,"rhs":{"op":"multiply","left":rail,
                    "right":{"op":"divide","left":phase,"right":constant(period)}}},
            {"origin":origin,"branch":{"instance":"d","local_positive":"guard","local_negative":"zref","kind":"voltage"},
                "positive":4,"negative":0,"rhs":{"op":"multiply","left":rail,"right":{"op":"operator","operator":0}}}
        ],"step_bounds":[]
    })).unwrap();
    let t = Trajectory::new(
        TransientInputs {
            analytic_sources: vec![],
            pwl_errors_v: None,
            pwl: vec![vec![[0., 1.], [34e-9, 1.]], vec![[0., 0.], [34e-9, 34e-9]]],
            output_times: if near_queries {
                vec![
                    0.,
                    (8e-9_f64).next_down(),
                    (16e-9_f64).next_down(),
                    (24e-9_f64).next_down(),
                    28e-9,
                    34e-9,
                ]
            } else {
                vec![0., 7.875e-9, 15.875e-9, 23.875e-9, 28e-9, 34e-9]
            },
            strobetimes: vec![],
            stop: 34e-9,
            max_step: 0.5e-9,
            proof_work_limit: None,
        },
        2,
    )
    .unwrap();
    let driven = vec!["rail".into(), "$abstime".into()];
    let source = crate::transition_source_plan::ProofContext::new(
        &p,
        &t,
        &driven,
        crate::transition_source_plan::Work::default(),
    )
    .unwrap();
    let m = EventModel::new_with_context(
        p,
        driven,
        Tolerances {
            absolute: 1e-12,
            relative: 1e-10,
        },
        Some(&t),
        Some(source.clone()),
    )
    .unwrap();
    assert!(m.dc_projection.as_ref().unwrap().is_held_ramp());
    let states = m.initial();
    let state_bounds = states.iter().copied().map(I::point).collect::<Vec<_>>();
    let calendar = schedule_held(&m, &t, &state_bounds).unwrap();
    let operators = Operators::new_until_with_source_context(
        &m.program,
        &t,
        &m.driven,
        &states,
        prediction_end(&m, &t, calendar.first()),
        &m.tolerances,
        Some(source.clone()),
    )
    .unwrap();
    let circuit = m
        .circuit_at(&states, &operators.values(0.).unwrap(), &t.value_bounds(0.))
        .unwrap();
    let solution = circuit.solve(&t.values(0.)).unwrap();
    let time_proofs = [
        (0, crate::exact_source::RootTime::point(0.).unwrap()),
        (1, crate::exact_source::RootTime::point(period).unwrap()),
    ]
    .into();
    let frame = Frame {
        value_proofs: Default::default(),
        time_proofs,
        time: 0.,
        states,
        state_bounds,
        solution,
        circuit,
        operators,
    };
    assert!(source.borrow_work().same_owner(
        frame
            .operators
            .source_context
            .as_ref()
            .unwrap()
            .borrow_work()
    ));
    let c = Controller {
        outputs: vec![frame.clone()],
        accepted: frame,
        event: 0,
        records: vec![],
    };
    (m, t, c, calendar)
}
fn snapshot(c: &Controller, calendar: &[ScheduledEvent]) -> Value {
    json!({"time":c.accepted.time,"event":c.event,"states":c.accepted.states,
        "state_bounds":c.accepted.state_bounds.iter().map(|b|[b.lo,b.hi]).collect::<Vec<_>>(),
        "solution":c.accepted.solution,"records":c.records,
        "outputs":c.outputs.iter().map(|f|(f.time,&f.states,&f.solution)).collect::<Vec<_>>(),
        "calendar":calendar.iter().map(|event| {
            let bounds=event.bounds();
            let root=crate::schedule::common_root(std::slice::from_ref(event));
            json!({"time":event.time,"event":event.event,"bounds":[bounds.lo,bounds.hi],
                "root":root.map(|root| root.rational().to_string()),
                "order_at_time":format!("{:?}",event.physical_order_at(event.time))})
        }).collect::<Vec<_>>()})
}
fn same_frame(a: &Frame, b: &Frame) {
    assert_eq!(a.time, b.time);
    assert_eq!(a.states, b.states);
    assert_eq!(a.state_bounds, b.state_bounds);
    assert_eq!(a.time_proofs, b.time_proofs);
    assert_eq!(a.value_proofs, b.value_proofs);
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
    // Immutable source proof/cut caches may grow during a rejected candidate.
    // Accepted mutable target/history remains covered by the two comparisons
    // above. Preserve the exact original context, binding, and ledger owner.
    let a_source = a.operators.source_context.as_ref().unwrap();
    let b_source = b.operators.source_context.as_ref().unwrap();
    assert!(Arc::ptr_eq(a_source, b_source));
    assert!(a_source.borrow_work().same_owner(b_source.borrow_work()));
    let (a_program, a_trajectory, a_driven) = a_source.original_binding();
    let (b_program, b_trajectory, b_driven) = b_source.original_binding();
    assert!(std::ptr::eq(a_program, b_program));
    assert!(std::ptr::eq(a_trajectory, b_trajectory));
    assert!(std::ptr::eq(a_driven, b_driven));
}
// Mirror the production controller's ordinary history branch. Consume every
// source/Transition boundary before accepting the next user timer callback.
fn advance_to_next_timer(
    m: &EventModel,
    t: &Trajectory,
    c: &mut Controller,
    calendar: &[ScheduledEvent],
) {
    for _ in 0..1000 {
        let event = &calendar[c.event];
        let mut time = (c.accepted.time + t.config.max_step).min(event.time);
        if let Some(deadline) = c
            .accepted
            .operators
            .next_breakpoint_for_event(c.accepted.time, Some(event), m)
            .unwrap()
        {
            time = time.min(deadline);
        }
        let due = matches!(
            event_order(m, t, event, time).unwrap(),
            Some(std::cmp::Ordering::Less | std::cmp::Ordering::Equal)
        );
        if time >= event.time || due {
            return;
        }
        assert!(time > c.accepted.time);
        let source_root = c.accepted.operators.source_root_at(time).unwrap();
        let source_window = source_root
            .as_ref()
            .map(|root| source_root_bounds(m, root))
            .transpose()
            .unwrap()
            .flatten()
            .or_else(|| c.accepted.operators.source_window_checked(time).unwrap())
            .unwrap_or(I::point(time));
        let next = prepare_root_window(
            m,
            t,
            &c.accepted,
            EventMoment {
                exact_root: source_root.as_ref(),
                occurrence_certified: false,
                representative: time,
                observation: source_window,
                fired_roots: &[],
                prediction_end: prediction_end(m, t, Some(event)),
            },
            &[],
        )
        .unwrap_or_else(|error| panic!(
            "mixed fixture history step refused: accepted={:.17e}; proposed={:.17e}; window={:?}; source_root={:?}; pending_timer={:.17e}; kind={}; message={}",
            c.accepted.time,time,source_window,source_root,event.time,error.kind,error.message,
        ));
        next.operators
            .check_deadline_order_deferred(time, Some(event_bounds(m, event).unwrap()), || {
                event_root(m, std::slice::from_ref(event))
            })
            .unwrap();
        c.accepted = next;
    }
    panic!("fixture failed to reach its next physical timer");
}
#[test]
fn mixed_physical_epoch_late_failure_two_retries_and_corrected_controller_match() {
    let (m, t, mut c, mut calendar) = fixture();
    for index in 0..2 {
        advance_to_next_timer(&m, &t, &mut c, &calendar);
        let accepted_time = c.accepted.time;
        let pending_timer = calendar[c.event].time;
        if let Err(error) =
            c.accept_changed_events(&m, &t, &mut calendar, event_acceptance::Strategy::Held)
        {
            panic!("mixed fixture accept {index} refused: accepted={accepted_time:.17e}; pending_timer={pending_timer:.17e}; kind={}; message={}", error.kind, error.message);
        }
    }
    assert_eq!(c.records.len(), 2);
    assert!(!c.outputs.is_empty());
    assert_eq!(
        c.accepted.operators.values(c.accepted.time).unwrap().len(),
        1
    );
    advance_to_next_timer(&m, &t, &mut c, &calendar);
    let before = snapshot(&c, &calendar);
    let accepted = c.accepted.clone();
    let outputs = c.outputs.clone();
    let work = m.source_context.as_ref().unwrap().borrow_work();
    let source = c.accepted.operators.source_context.as_ref().unwrap();
    assert!(work.same_owner(source.borrow_work()));
    let entered = Arc::new(AtomicUsize::new(0));
    let hook_count = entered.clone();
    event_acceptance::test_with_final_candidate(
        move |candidate| {
            hook_count.fetch_add(1, Ordering::SeqCst);
            assert!(candidate.time > 23e-9 && candidate.time < 25e-9);
            candidate.solution.voltages[3] += 0.01;
        },
        || {
            for _ in 0..3 {
                let spent = work.spent();
                let error = c
                    .accept_changed_events(&m, &t, &mut calendar, event_acceptance::Strategy::Held)
                    .unwrap_err();
                assert_eq!(error.kind, "waveform_accuracy", "{}", error.message);
                assert!(work.spent() > spent);
                assert_eq!(snapshot(&c, &calendar), before);
                same_frame(&c.accepted, &accepted);
                for (a, b) in c.outputs.iter().zip(&outputs) {
                    same_frame(a, b);
                }
            }
        },
    );
    assert_eq!(
        entered.load(Ordering::SeqCst),
        3,
        "failure must reach the late final gate"
    );
    c.accept_changed_events(&m, &t, &mut calendar, event_acceptance::Strategy::Held)
        .unwrap();
    let (cm, ct, mut clean, mut clean_calendar) = fixture();
    for _ in 0..3 {
        advance_to_next_timer(&cm, &ct, &mut clean, &clean_calendar);
        clean
            .accept_changed_events(
                &cm,
                &ct,
                &mut clean_calendar,
                event_acceptance::Strategy::Held,
            )
            .unwrap();
    }
    assert_eq!(snapshot(&c, &calendar), snapshot(&clean, &clean_calendar));
    // Cross-engine comparison excludes allocation identity only. Same-engine
    // failure/retry comparisons above deliberately retain strict same_frame.
    assert_eq!(c.accepted.time_proofs, clean.accepted.time_proofs);
    assert_eq!(c.accepted.value_proofs, clean.accepted.value_proofs);
    let mut circuit = c.accepted.circuit.forcing_frame_snapshot();
    let mut clean_circuit = clean.accepted.circuit.forcing_frame_snapshot();
    circuit
        .as_object_mut()
        .unwrap()
        .remove("affine_factor_identity");
    clean_circuit
        .as_object_mut()
        .unwrap()
        .remove("affine_factor_identity");
    assert_eq!(circuit, clean_circuit);
    for time in [c.accepted.time, 25e-9, 28e-9, 31e-9] {
        assert_eq!(
            c.accepted.operators.values(time).unwrap(),
            clean.accepted.operators.values(time).unwrap()
        );
        assert_eq!(
            c.accepted.operators.bounds(time).unwrap(),
            clean.accepted.operators.bounds(time).unwrap()
        );
    }
}

#[test]
fn mixed_near_epoch_query_preserves_ordinary_clock_precision_refusal() {
    // Retain the independently observed precision frontier. The late rollback
    // fixture uses separated queries solely to reach its final gate; this test
    // does not claim ordinary clock queries one ulp before an epoch are admitted.
    let (m, t, mut c, mut calendar) = fixture_with_near_queries(true);
    advance_to_next_timer(&m, &t, &mut c, &calendar);
    let before = snapshot(&c, &calendar);
    let accepted = c.accepted.clone();
    let outputs = c.outputs.clone();
    let work = m.source_context.as_ref().unwrap().borrow_work();
    assert!(work.same_owner(
        c.accepted
            .operators
            .source_context
            .as_ref()
            .unwrap()
            .borrow_work()
    ));
    let spent = work.spent();
    let result = c.accept_changed_events(&m, &t, &mut calendar, event_acceptance::Strategy::Held);
    let error = result.unwrap_err();
    assert_eq!(error.kind, "condition_precision");
    assert!(error.message.contains("ordinary analog if predicate"));
    assert!(work.spent() > spent);
    assert_eq!(snapshot(&c, &calendar), before);
    same_frame(&c.accepted, &accepted);
    assert_eq!(c.outputs.len(), outputs.len());
    for (actual, original) in c.outputs.iter().zip(&outputs) {
        same_frame(actual, original);
    }
}
