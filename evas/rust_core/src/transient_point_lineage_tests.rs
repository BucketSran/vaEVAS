//! Direct consumers distinguish proof identity from coincident interval values.
use super::super::{Controller, EventMoment, EventRecord, FiredTrigger, ScheduledEvent};
use super::*;
use crate::diagnostics::{capture, Options};
use crate::ir::{Program, Tolerances, TransientInputs};
use crate::transition_source_plan::ProofContext;
use num_rational::BigRational as R;
use num_traits::Signed;
use serde_json::{json, Value};

fn fixture() -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    let o = json!({"source":"proven-lineage-point-query.va","line":1,"column":1,"instance":"M"});
    // The independent public VA has two distinct transition call sites:
    // line11 column8 reads q; line12 column8 reads the unrelated held s.
    let q_origin =
        json!({"source":"proven-lineage-point-query.va","line":11,"column":8,"instance":"M"});
    let s_origin =
        json!({"source":"proven-lineage-point-query.va","line":12,"column":8,"instance":"M"});
    let constant = |x| json!({"op":"affine","constant":x,"terms":[]});
    let p:Program=serde_json::from_value(json!({
        "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","u","y","h","z","w"],
        "states":[{"instance":"M","name":"q","kind":"real","initial":0},{"instance":"M","name":"s","kind":"real","initial":0}],
        "events":[
            {"trigger":{"kind":"timer","start":0.25,"period":0,"enabled":true,"time_tolerance":1e-9},"origin":o,"body":[{"kind":"assign","state":0,"rhs":{"op":"affine","constant":0.25,"terms":[{"node":1,"coefficient":1}]}}]},
            {"trigger":{"kind":"timer","start":0.5,"period":0,"enabled":true,"time_tolerance":1e-9},"origin":o,"body":[{"kind":"assign","state":1,"rhs":constant(1.)}]}],
        "operators":[
            {"kind":"transition","input":{"op":"state","state":0},"delay":0,"rise":0.125,"fall":0.125,"origin":q_origin},
            {"kind":"transition","input":{"op":"state","state":1},"delay":0,"rise":0.25,"fall":0.25,"origin":s_origin}],
        "contributions":[
            {"branch":{"instance":"M","local_positive":"out_y","local_negative":"ref","kind":"voltage"},"positive":2,"negative":0,"rhs":{"op":"select","relation":"gt","left":{"op":"add","left":{"op":"state","state":0},"right":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":-1}]}},"right":constant(0.125),"then_value":constant(1.),"else_value":constant(0.),"origin":o},"origin":o},
            {"branch":{"instance":"M","local_positive":"out_h","local_negative":"ref","kind":"voltage"},"positive":3,"negative":0,"rhs":{"op":"state","state":0},"origin":o},
            {"branch":{"instance":"M","local_positive":"out_z","local_negative":"ref","kind":"voltage"},"positive":4,"negative":0,"rhs":{"op":"operator","operator":0},"origin":o},
            {"branch":{"instance":"M","local_positive":"out_w","local_negative":"ref","kind":"voltage"},"positive":5,"negative":0,"rhs":{"op":"operator","operator":1},"origin":o}]
    })).unwrap();
    let t = Trajectory::new(
        TransientInputs {
            analytic_sources: vec![],
            pwl_errors_v: None,
            strobetimes: vec![],
            pwl: vec![vec![[0., 0.], [2., 0.2]]],
            output_times: vec![0., 0.125, 0.375, 0.625, 1.5, 2.],
            stop: 2.,
            max_step: 0.125,
        },
        1,
    )
    .unwrap();
    let m = EventModel::new_with_trajectory(p, vec!["u".into()], Tolerances::default(), Some(&t))
        .unwrap();
    let states = m.initial();
    let (ops, mut calendar) = super::super::history_calendar::initialize(&m, &t, &states).unwrap();
    let inputs = t.values(0.);
    let circuit = m
        .circuit_at(&states, &ops.values(0.).unwrap(), &t.value_bounds(0.))
        .unwrap();
    let solution = circuit.solve(&inputs).unwrap();
    let mut c = Controller {
        accepted: Frame {
            value_proofs: Default::default(),
            time_proofs: Default::default(),
            time: 0.,
            state_bounds: states.iter().copied().map(I::point).collect(),
            states,
            solution,
            circuit,
            operators: ops,
        },
        event: 0,
        records: vec![],
        outputs: vec![],
    };
    for _ in 0..2 {
        c.accept_changed_events(
            &m,
            &t,
            &mut calendar,
            super::super::event_acceptance::Strategy::Static,
        )
        .unwrap();
    }
    assert!(!c.records.is_empty());
    assert!(!c.outputs.is_empty());
    assert!(c.accepted.state_bounds[0].lo < c.accepted.state_bounds[0].hi);
    (m, t, c, calendar)
}
fn pair() -> (Expression, Expression) {
    (serde_json::from_value(json!({"op":"add","left":{"op":"state","state":0},"right":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":-1}]}})).unwrap(),
     serde_json::from_value(json!({"op":"affine","constant":0.125,"terms":[]})).unwrap())
}
fn nodes(m: &EventModel, t: &Trajectory, time: f64) -> Vec<I> {
    let mut n = vec![I::ZERO; m.program.nodes.len()];
    n[1] = t.value_bounds(time)[0];
    n
}
#[allow(clippy::too_many_arguments)] // Deliberately vary Frame, query and supplied boxes independently.
fn direct(
    m: &EventModel,
    t: &Trajectory,
    f: &Frame,
    context: &Context<'_>,
    window: I,
    ordinary: bool,
    left: &Expression,
    right: &Expression,
) -> Result<Option<i8>, Error> {
    let lineage = PointLineage::new(f, m, t, context, window.hi, window, ordinary);
    lineage.sign(
        left,
        right,
        "M",
        &m.program,
        &m.driven,
        &nodes(m, t, window.hi),
        &f.state_bounds,
    )
}
#[test]
fn point_lineage_direct_valid_nonpoint_and_wrong_frame_two_rationals_same_box() {
    let (m, t, c, _) = fixture();
    let f = &c.accepted;
    let (left, right) = pair();
    let ctx = Context::new(&m, &t, &t.value_bounds(1.5), &f.value_proofs, None);
    assert_eq!(
        direct(&m, &t, f, &ctx, I::point(1.5), true, &left, &right).unwrap(),
        Some(-1)
    );
    let actual = crate::exact_source::binary(0.2).unwrap() / R::from_integer(8.into())
        + crate::exact_source::binary(0.25).unwrap();
    assert_eq!(f.value_proofs[&0], actual);
    let alternate = crate::exact_source::binary(f.states[0]).unwrap();
    assert_ne!(actual, alternate);
    let mut wrong = f.clone();
    wrong.value_proofs.insert(0, alternate.clone());
    assert!(crate::event_value_proof::valid(
        &wrong.value_proofs,
        &f.state_bounds
    ));
    let current_u = crate::exact_source::binary(0.2).unwrap() * R::new(3.into(), 4.into());
    assert!((actual - &current_u - crate::exact_source::binary(0.125).unwrap()).is_negative());
    assert!((alternate - current_u - crate::exact_source::binary(0.125).unwrap()).is_positive());
    let wrong_ctx = Context::new(&m, &t, &t.value_bounds(1.5), &wrong.value_proofs, None);
    assert_eq!(
        direct(&m, &t, f, &wrong_ctx, I::point(1.5), true, &left, &right).unwrap(),
        None
    );
}
#[test]
fn point_lineage_direct_missing_out_of_box_and_singleton_state_are_not_proof() {
    let (m, t, c, _) = fixture();
    let (left, right) = pair();
    let mut missing = c.accepted.clone();
    missing.value_proofs.remove(&0);
    // A forged singleton cannot replace the absent accepted lineage.
    missing.state_bounds[0] = I::point(missing.states[0]);
    let ctx = Context::new(&m, &t, &t.value_bounds(1.5), &missing.value_proofs, None);
    assert_eq!(
        direct(&m, &t, &missing, &ctx, I::point(1.5), true, &left, &right).unwrap(),
        None
    );
    let mut outside = c.accepted.clone();
    outside.value_proofs.insert(0, R::from_integer(2.into()));
    let ctx = Context::new(&m, &t, &t.value_bounds(1.5), &outside.value_proofs, None);
    assert_eq!(
        direct(&m, &t, &outside, &ctx, I::point(1.5), true, &left, &right).unwrap(),
        None
    );
}
#[test]
fn point_lineage_direct_binding_nonpoint_and_physical_batch_are_refused() {
    let (m, t, c, _) = fixture();
    let (left, right) = pair();
    let f = &c.accepted;
    let ctx = Context::new(&m, &t, &t.value_bounds(1.5), &f.value_proofs, None);
    assert_eq!(
        direct(
            &m,
            &t,
            f,
            &ctx,
            I { lo: 1.49, hi: 1.5 },
            true,
            &left,
            &right
        )
        .unwrap(),
        None
    );
    assert_eq!(
        direct(&m, &t, f, &ctx, I::point(1.5), false, &left, &right).unwrap(),
        None
    );
    let mut config = t.config.clone();
    config.pwl[0][1][1] = 0.4;
    let other = Trajectory::new(config, 1).unwrap();
    let err = direct(&m, &other, f, &ctx, I::point(1.5), true, &left, &right)
        .err()
        .unwrap();
    assert_eq!(err.kind, "invalid_ir");
}
#[test]
fn point_lineage_direct_true_error_unknown_singleton_source_and_internal_zero_are_refused() {
    let (m, t, c, _) = fixture();
    let (left, right) = pair();
    let owner = c.accepted.operators.source_context.as_ref().unwrap();
    let mut config = serde_json::to_value(&t.config).unwrap();
    config["pwl_errors_V"] = json!([1e-4]);
    let bad = Trajectory::new(serde_json::from_value(config).unwrap(), 1).unwrap();
    let mut frame = c.accepted.clone();
    // Bypass the old outer refusal only in this direct internal fixture.
    // The supplied original source owner matches the true-error configuration
    // and borrows the exact same existing Work, so this tests the new consumer.
    frame.operators.source_context = Some(
        ProofContext::event_request_with_work(
            &m.program,
            &bad,
            &m.driven,
            0,
            owner.borrow_work().clone(),
        )
        .unwrap(),
    );
    let ctx = Context::new(&m, &bad, &bad.value_bounds(1.5), &frame.value_proofs, None);
    assert_eq!(
        direct(&m, &bad, &frame, &ctx, I::point(1.5), true, &left, &right).unwrap(),
        None
    );
    // The existing shaped-provider contract certifies an exact original
    // waveform; its nonzero projection band is not unknown physical noise.
    let mut config = serde_json::to_value(&t.config).unwrap();
    config["pwl_errors_V"] = json!([{"voltage_error_bound_V":1e-4,"exact_knots":[
        {"time_numerator":"0","time_denominator":"1","value_V":0.},
        {"time_numerator":"2","time_denominator":"1","value_V":0.2}
    ]}]);
    let shaped = Trajectory::new(serde_json::from_value(config).unwrap(), 1).unwrap();
    let mut shaped_frame = c.accepted.clone();
    shaped_frame.operators.source_context = Some(
        ProofContext::event_request_with_work(
            &m.program,
            &shaped,
            &m.driven,
            0,
            owner.borrow_work().clone(),
        )
        .unwrap(),
    );
    let shaped_ctx = Context::new(
        &m,
        &shaped,
        &shaped.value_bounds(1.5),
        &shaped_frame.value_proofs,
        None,
    );
    assert_eq!(
        direct(
            &m,
            &shaped,
            &shaped_frame,
            &shaped_ctx,
            I::point(1.5),
            true,
            &left,
            &right
        )
        .unwrap(),
        Some(-1)
    );
    let mut unknown = t.clone();
    unknown.exact_sources[0] = None;
    let mut frame = c.accepted.clone();
    frame.operators.source_context = Some(
        ProofContext::event_request_with_work(
            &m.program,
            &unknown,
            &m.driven,
            0,
            owner.borrow_work().clone(),
        )
        .unwrap(),
    );
    assert_eq!(
        unknown.value_bounds(2.)[0].lo,
        unknown.value_bounds(2.)[0].hi
    );
    let ctx = Context::new(
        &m,
        &unknown,
        &unknown.value_bounds(2.),
        &frame.value_proofs,
        None,
    );
    assert_eq!(
        direct(
            &m,
            &unknown,
            &frame,
            &ctx,
            I::point(2.),
            true,
            &left,
            &right
        )
        .unwrap(),
        None
    );
    let internal: Expression = serde_json::from_value(
        json!({"op":"affine","constant":0,"terms":[{"node":3,"coefficient":0}]}),
    )
    .unwrap();
    let ctx = Context::new(&m, &t, &t.value_bounds(1.5), &c.accepted.value_proofs, None);
    assert_eq!(
        direct(
            &m,
            &t,
            &c.accepted,
            &ctx,
            I::point(1.5),
            true,
            &internal,
            &right
        )
        .unwrap(),
        None
    );
}
fn query(m: &EventModel, t: &Trajectory, c: &Controller) -> Result<Frame, Error> {
    super::super::prepare_root_window(
        m,
        t,
        &c.accepted,
        EventMoment {
            exact_root: None,
            representative: 1.5,
            observation: I::point(1.5),
            fired_roots: &[],
            prediction_end: 2.,
        },
        &[],
    )
}
fn frame(f: &Frame) -> Value {
    json!({"time":f.time,"states":f.states,"bounds":f.state_bounds.iter().map(|b|[b.lo,b.hi]).collect::<Vec<_>>(),"value_proofs":format!("{:?}",f.value_proofs),"time_proofs":format!("{:?}",f.time_proofs),"solution":f.solution,"certified_voltage_bounds":f.solution.certified_voltage_bounds,"circuit":f.circuit.forcing_frame_snapshot(),"transitions":format!("{:?}",f.operators.test_transition_histories()),"source_owner":f.operators.source_context.as_ref().map(|c|std::sync::Arc::as_ptr(c)as usize)})
}
fn signature(c: &Controller, calendar: &[ScheduledEvent]) -> Value {
    json!({"accepted":frame(&c.accepted),"event":c.event,"records":c.records,"outputs":c.outputs.iter().map(frame).collect::<Vec<_>>(),"calendar":calendar.iter().map(ScheduledEvent::analytic_test_snapshot).collect::<Vec<_>>()})
}
fn normalize(mut value: Value) -> Value {
    fn walk(v: &mut Value) {
        match v {
            Value::Object(m) => {
                if let Some(x) = m.get_mut("affine_factor_identity") {
                    if !x.is_null() {
                        *x = json!(0);
                    }
                }
                for child in m.values_mut() {
                    walk(child);
                }
            }
            Value::Array(a) => {
                for child in a {
                    walk(child);
                }
            }
            _ => {}
        }
    }
    walk(&mut value);
    value
}
fn copy_record(r: &EventRecord) -> EventRecord {
    EventRecord {
        time: r.time,
        observation_time_bounds: r.observation_time_bounds,
        event: r.event,
        origin: r.origin.clone(),
        kind: r.kind,
        guard_value: r.guard_value,
        fired_triggers: r
            .fired_triggers
            .iter()
            .map(|f| FiredTrigger {
                trigger: f.trigger,
                kind: f.kind,
                guard_value: f.guard_value,
                time_bounds: f.time_bounds,
            })
            .collect(),
        before: r.before.clone(),
        after: r.after.clone(),
        display_records: r.display_records.clone(),
    }
}
#[test]
fn point_lineage_same_controller_two_late_failures_then_legal_retry_full_nonempty_frame() {
    let (m, t, mut c, calendar) = fixture();
    let before = signature(&c, &calendar);
    let seed = c.accepted.clone();
    let outputs = c.outputs.clone();
    let mut clean = Controller {
        accepted: c.accepted.clone(),
        event: c.event,
        records: c.records.iter().map(copy_record).collect(),
        outputs: c.outputs.clone(),
    };
    let owner = c
        .accepted
        .operators
        .source_context
        .as_ref()
        .unwrap()
        .clone();
    let start = owner.borrow_work().spent();
    struct Reset;
    impl Drop for Reset {
        fn drop(&mut self) {
            crate::settlement::POINT_CANDIDATE_HOOK.with(|h| *h.borrow_mut() = None);
        }
    }
    for _ in 0..2 {
        crate::settlement::POINT_CANDIDATE_HOOK
            .with(|h| *h.borrow_mut() = Some(Box::new(|solution| solution.voltages[2] += 0.01)));
        let reset = Reset;
        let error = query(&m, &t, &c).err().unwrap();
        drop(reset);
        assert_eq!(error.kind, "waveform_accuracy");
        assert_eq!(signature(&c, &calendar), before);
        assert!(c.accepted.operators.same_reset_history(&seed.operators));
        for (a, b) in c.outputs.iter().zip(&outputs) {
            assert!(a.operators.same_reset_history(&b.operators));
        }
    }
    assert!(owner.borrow_work().spent() > start);
    c.accepted = query(&m, &t, &c).unwrap();
    clean.accepted = query(&m, &t, &clean).unwrap();
    assert!(seed.state_bounds[0].lo < seed.state_bounds[0].hi);
    assert_eq!(
        c.accepted.state_bounds, seed.state_bounds,
        "ordinary exact mode selection must retain every original old-state box"
    );
    assert_eq!(clean.accepted.state_bounds, seed.state_bounds);
    assert_eq!(c.accepted.solution.voltages[2], 0.);
    assert!(std::sync::Arc::ptr_eq(
        c.accepted.operators.source_context.as_ref().unwrap(),
        &owner
    ));
    assert_eq!(
        normalize(signature(&c, &calendar)),
        normalize(signature(&clean, &calendar))
    );
    assert!(c
        .accepted
        .operators
        .same_reset_history(&clean.accepted.operators));
}
#[test]
fn point_lineage_natural_same_request_work_exhaustion_and_two_sticky_retries() {
    let (result, report) = capture(Options::default(), || {
        let (m, t, c, calendar) = fixture();
        let before = signature(&c, &calendar);
        let seed = c.accepted.clone();
        let outputs = c.outputs.clone();
        let owner = c
            .accepted
            .operators
            .source_context
            .as_ref()
            .unwrap()
            .clone();
        let work = owner.borrow_work();
        let mut tries = 0;
        loop {
            tries += 1;
            match query(&m, &t, &c) {
                Ok(_) => {}
                Err(e) => {
                    assert_eq!(e.kind, "step_budget");
                    break;
                }
            }
            assert!(tries < 100_000);
        }
        assert!(work.spent() > 1_000_000_000);
        let spent = work.spent();
        let (_, retry) = capture(Options::default(), || {
            for _ in 0..2 {
                assert_eq!(query(&m, &t, &c).err().unwrap().kind, "step_budget");
                assert_eq!(work.spent(), spent);
                assert_eq!(signature(&c, &calendar), before);
                assert!(c.accepted.operators.same_reset_history(&seed.operators));
                for (a, b) in c.outputs.iter().zip(&outputs) {
                    assert!(a.operators.same_reset_history(&b.operators));
                }
            }
            Ok(())
        });
        assert!(!retry
            .counters
            .contains_key("point_lineage_certified_predicates"));
        let ctx = Context::new(&m, &t, &t.value_bounds(2.), &c.accepted.value_proofs, None);
        let lineage = PointLineage::new(&c.accepted, &m, &t, &ctx, 2., I::point(2.), true);
        let left:Expression=serde_json::from_value(json!({"op":"add","left":{"op":"state","state":0},"right":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":0.1}]}})).unwrap();
        let right = Expression::Affine {
            constant: 0.295,
            terms: vec![],
        };
        let singleton_states = c
            .accepted
            .states
            .iter()
            .copied()
            .map(I::point)
            .collect::<Vec<_>>();
        let mut singleton_nodes = vec![I::ZERO; m.program.nodes.len()];
        singleton_nodes[1] = I::point(0.2);
        let rounded_difference =
            (I::point(c.accepted.states[0]) + I::point(0.1) * I::point(0.2)) - I::point(0.295);
        assert!(
            rounded_difference.lo <= 0. && rounded_difference.hi >= 0.,
            "control must reach the original exact fallback"
        );
        let probe = Expression::Select {
            relation: crate::ir::Relation::Gt,
            left: Box::new(left),
            right: Box::new(right),
            then_value: Box::new(Expression::Affine {
                constant: 1.,
                terms: vec![],
            }),
            else_value: Box::new(Expression::Affine {
                constant: 0.,
                terms: vec![],
            }),
            origin: m.program.contributions[0].origin.clone(),
        };
        let (legacy, legacy_report) = capture(Options::default(), || {
            crate::continuous::resolve_selection_with_lineage(
                &probe,
                &m.program,
                &m.driven,
                &singleton_nodes,
                &singleton_states,
                Some(&lineage),
            )
        });
        assert_eq!(
            legacy.unwrap(),
            Expression::Affine {
                constant: 1.,
                terms: vec![]
            }
        );
        assert_eq!(
            work.spent(),
            spent,
            "old successful exact fallback must not debit exhausted source Work"
        );
        assert!(
            !legacy_report.counters.contains_key("point_lineage_demands"),
            "old successful fallback invoked new helper"
        );
        eprintln!(
            "point_lineage_natural_tries={tries} sticky={}",
            serde_json::to_string(&retry.counters).unwrap()
        );
        Ok(())
    });
    result.unwrap();
    assert!(
        report
            .counters
            .get("point_lineage_certified_predicates")
            .copied()
            .unwrap_or(0)
            > 0
    );
    eprintln!(
        "point_lineage_work={}",
        serde_json::to_string(&report.counters).unwrap()
    );
}
