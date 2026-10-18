//! Original-source event Floor through the production Controller transaction.
use super::*;
use crate::diagnostics::{capture, Options};
use crate::ir::{Program, Tolerances, TransientInputs};
use serde_json::{json, Value};
fn fixture() -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    let o = json!({"source":"source_floor.va","line":1,"column":1,"instance":"M"});
    let c = |x| json!({"op":"affine","constant":x,"terms":[]});
    let floor = json!({"op":"event_math","function":"floor","origin":o,"args":[{"op":"add","left":{"op":"multiply","left":{"op":"divide","left":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]},"right":c(0.9)},"right":c(15.)},"right":c(0.5)}]});
    let p:Program=serde_json::from_value(json!({"schema_version":SCHEMA_VERSION,"nodes":["0","u","y"],"states":[{"instance":"M","name":"q","kind":"integer","initial":2}],"events":[
        {"trigger":{"kind":"timer","start":0.125,"period":0,"enabled":true,"time_tolerance":1e-9},"origin":o,"body":[{"kind":"assign","state":0,"rhs":c(2.)}]},
        {"trigger":{"kind":"timer","start":0.5,"period":0,"enabled":true,"time_tolerance":1e-9},"origin":o,"body":[{"kind":"assign","state":0,"rhs":floor},{"kind":"display","format":"q=%d","args":[{"op":"state","state":0}],"origin":o}]}],
        "operators":[{"kind":"transition","input":{"op":"state","state":0},"delay":0,"rise":0.125,"fall":0.125,"origin":o}],
        "contributions":[{"branch":{"instance":"M","local_positive":"out","local_negative":"ref","kind":"voltage"},"positive":2,"negative":0,"rhs":{"op":"operator","operator":0},"origin":o}]})).unwrap();
    let t = Trajectory::new(
        TransientInputs {
            pwl_errors_v: None,
            strobetimes: vec![],
            pwl: vec![vec![[0., 0.03], [1., 0.03]]],
            output_times: vec![0., 0.75, 1.],
            stop: 1.,
            max_step: 0.125,
        },
        1,
    )
    .unwrap();
    let m = EventModel::new_with_trajectory(p, vec!["u".into()], Tolerances::default(), Some(&t))
        .unwrap();
    let states = m.initial();
    let bounds = states.iter().copied().map(I::point).collect::<Vec<_>>();
    let calendar = schedule_held(&m, &t, &bounds).unwrap();
    let ops = Operators::new_until_with_source_context(
        &m.program,
        &t,
        &m.driven,
        &states,
        1.,
        &m.tolerances,
        Some(m.floor_source.as_ref().unwrap().source.clone()),
    )
    .unwrap();
    let circuit = m.circuit_with(&states, &ops.values(0.).unwrap()).unwrap();
    let solution = circuit.solve(&t.values(0.)).unwrap();
    let controller = Controller {
        accepted: Frame {
            value_proofs: Default::default(),
            time_proofs: Default::default(),
            time: 0.,
            states,
            state_bounds: bounds,
            solution,
            circuit,
            operators: ops,
        },
        event: 0,
        records: vec![],
        outputs: vec![],
    };
    (m, t, controller, calendar)
}
fn signature(c: &Controller, calendar: &[ScheduledEvent]) -> Value {
    json!({"states":c.accepted.states,"bounds":c.accepted.state_bounds.iter().map(|b|[b.lo,b.hi]).collect::<Vec<_>>(),"value_proofs":format!("{:?}",c.accepted.value_proofs),"time_proofs":format!("{:?}",c.accepted.time_proofs),"time":c.accepted.time,"voltages":c.accepted.solution.voltages,"history":format!("{:?}",c.accepted.operators.test_transition_histories()),"event":c.event,"records":serde_json::to_value(&c.records).unwrap(),"outputs":c.outputs.iter().map(|f|json!({"states":f.states,"time":f.time,"volts":f.solution.voltages})).collect::<Vec<_>>(),"calendar":calendar.iter().map(|e|json!([e.time,e.event,e.bounds().lo,e.bounds().hi,format!("{:?}",crate::schedule::common_root(std::slice::from_ref(e)))])).collect::<Vec<_>>()})
}
#[test]
fn source_floor_actual_controller_late_voltage_failure_twice_then_legal_retry() {
    let (m, t, mut c, mut calendar) = fixture();
    c.accept_changed_events(&m, &t, &mut calendar, event_acceptance::Strategy::Static)
        .unwrap();
    let before = signature(&c, &calendar);
    let history = c.accepted.operators.clone();
    let mut clean = Controller {
        accepted: c.accepted.clone(),
        event: c.event,
        records: c.records.iter().map(copy_record).collect(),
        outputs: c.outputs.clone(),
    };
    let mut clean_calendar = calendar.clone();
    let work = m.floor_source.as_ref().unwrap().work();
    let start = work.spent();
    for _ in 0..2 {
        let (mut candidate, records, end) = c
            .prepare_events_until(&m, &t, &calendar, Some(calendar[c.event].time))
            .unwrap();
        assert_eq!(candidate.states, [0.]);
        assert_eq!(records[0].display_records[0].text, "q=0");

        let pending = calendar[end..].to_vec();
        c.prepare_physical_history(&m, &t, &mut candidate, &calendar[c.event..end], &pending)
            .unwrap();
        assert_ne!(
            candidate.operators.test_transition_histories(),
            history.test_transition_histories()
        );
        // Inject the error only into a fully prepared disposable candidate,
        // then exercise the real final voltage acceptance gate.
        candidate.solution.voltages[2] += 0.01;
        let error = Controller::prepare_final_history(
            &m,
            &t,
            candidate,
            event_acceptance::CalendarPlan::Held(pending),
        )
        .err()
        .unwrap();
        assert_eq!(error.kind, "waveform_accuracy");
        assert_eq!(signature(&c, &calendar), before);
        assert!(c.accepted.operators.same_reset_history(&history));
    }
    assert!(work.spent() > start);
    c.accept_changed_events(&m, &t, &mut calendar, event_acceptance::Strategy::Static)
        .unwrap();
    clean
        .accept_changed_events(
            &m,
            &t,
            &mut clean_calendar,
            event_acceptance::Strategy::Static,
        )
        .unwrap();
    assert_eq!(signature(&c, &calendar), signature(&clean, &clean_calendar));
    assert!(c
        .accepted
        .operators
        .same_reset_history(&clean.accepted.operators));
}
#[test]
fn source_floor_natural_original_owner_exhaustion_and_twice_retry_no_clone_or_helper() {
    let (answer, report) = capture(Options::default(), || {
        let (m, t, mut c, mut calendar) = fixture();
        c.accept_changed_events(&m, &t, &mut calendar, event_acceptance::Strategy::Static)
            .unwrap();
        let before = signature(&c, &calendar);
        let mut tries = 0;
        loop {
            tries += 1;
            match c.prepare_events(&m, &t, &calendar) {
                Ok(_) => {}
                Err(e) => {
                    assert_eq!(e.kind, "step_budget");
                    break;
                }
            }
            assert!(
                tries < 10000,
                "natural accounting never reached original1e9 limit"
            );
        }
        assert!(m.floor_source.as_ref().unwrap().work().spent() > 1_000_000_000);
        let (_, retry) = capture(Options::default(), || {
            for _ in 0..2 {
                assert_eq!(
                    c.prepare_events(&m, &t, &calendar).err().unwrap().kind,
                    "step_budget"
                );
                let work = m.floor_source.as_ref().unwrap().work();
                let spent = work.spent();
                assert_eq!(
                    initialization::prepare(&m, &t).err().unwrap().kind,
                    "step_budget"
                );
                assert_eq!(work.spent(), spent);
            }
            Ok(())
        });
        assert!(!retry.counters.contains_key("floor_source_helper_calls"));
        assert!(!retry.counters.contains_key("floor_source_copy"));
        assert_eq!(signature(&c, &calendar), before);
        eprintln!(
            "floor_source_retry={}",
            serde_json::to_string(&retry.counters).unwrap()
        );
        Ok(tries)
    });
    let tries = answer.unwrap();
    assert_eq!(report.counters.get("floor_source_factory_calls"), Some(&1));
    assert_eq!(report.counters.get("floor_source_owner_created"), Some(&1));
    eprintln!(
        "floor_source_natural_tries={tries} accounting={}",
        serde_json::to_string(&report.counters).unwrap()
    );
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

#[test]
fn source_floor_request_entry_has_one_owner_before_initialization_and_old_route_has_zero_added_proof(
) {
    let (m, t, _, _) = fixture();
    let request = crate::ir::Request {
        program: m.program.clone(),
        driven: m.driven.clone(),
        samples: vec![],
        transient: Some(t.config.clone()),
        tolerances: m.tolerances.clone(),
    };
    let (result, report) = capture(Options::default(), || crate::run(request));
    result.unwrap();
    assert_eq!(report.counters.get("floor_source_factory_calls"), Some(&1));
    assert_eq!(report.counters.get("floor_source_owner_created"), Some(&1));
    assert_eq!(
        report.counters.get("floor_source_before_initialization"),
        Some(&1)
    );
    let mut value = serde_json::to_value(&m.program).unwrap();
    value["events"][1]["body"][0]["rhs"]["args"][0] = json!({"op":"multiply","left":{"op":"affine","constant":8,"terms":[]},"right":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]}});
    let p: Program = serde_json::from_value(value).unwrap();
    let request = crate::ir::Request {
        program: p,
        driven: m.driven.clone(),
        samples: vec![],
        transient: Some(t.config.clone()),
        tolerances: m.tolerances.clone(),
    };
    let (result, old) = capture(Options::default(), || crate::run(request));
    result.unwrap();
    assert!(!old.counters.keys().any(|k| k.starts_with("floor_source_")));
    eprintln!(
        "floor_source_request={}",
        serde_json::to_string(&report.counters).unwrap()
    );
}
#[test]
fn source_floor_provided_owner_matches_original_binding_and_never_creates_a_second_ledger() {
    let (m, t, _, _) = fixture();
    let supplied = m.floor_source.as_ref().unwrap().source.clone();
    let (result, report) = capture(Options::default(), || {
        EventModel::new_with_context(
            m.program.clone(),
            m.driven.clone(),
            m.tolerances.clone(),
            Some(&t),
            Some(supplied.clone()),
        )
    });
    let reused = result.unwrap();
    assert!(std::sync::Arc::ptr_eq(
        &reused.floor_source.as_ref().unwrap().source,
        &supplied
    ));
    assert!(!report.counters.contains_key("floor_source_owner_created"));
    let mut config = t.config.clone();
    config.pwl[0] = vec![[0., 0.09], [1., 0.09]];
    let foreign = Trajectory::new(config, 1).unwrap();
    let (result, rejected) = capture(Options::default(), || {
        EventModel::new_with_context(
            m.program.clone(),
            m.driven.clone(),
            m.tolerances.clone(),
            Some(&foreign),
            Some(supplied),
        )
    });
    assert_eq!(result.err().unwrap().kind, "event_condition");
    assert!(!rejected.counters.contains_key("floor_source_owner_created"));
    assert!(!rejected.counters.contains_key("floor_source_helper_calls"));
}

#[test]
fn source_floor_zero_timer_bootstrap_uses_same_paired_certificate_before_history() {
    let (m, t, _, _) = fixture();
    let mut raw = serde_json::to_value(&m.program).unwrap();
    raw["events"][0]["trigger"]["start"] = json!(0.);
    raw["events"][0]["body"] = raw["events"][1]["body"].clone();
    let p: Program = serde_json::from_value(raw).unwrap();
    let request = crate::ir::Request {
        program: p,
        driven: m.driven.clone(),
        samples: vec![],
        transient: Some(t.config.clone()),
        tolerances: m.tolerances.clone(),
    };
    let (answer, counters) = capture(Options::default(), || crate::run(request));
    let answer = answer.unwrap();
    let raw = serde_json::to_value(answer).unwrap();
    assert!(raw.to_string().contains("q=0"));
    assert_eq!(
        counters.counters.get("floor_source_factory_calls"),
        Some(&1)
    );
    assert_eq!(
        counters.counters.get("floor_source_owner_created"),
        Some(&1)
    );
}

#[test]
fn source_floor_joint_preview_uses_the_same_certified_bin_as_final_apply() {
    let (old, t, _, _) = fixture();
    let mut raw = serde_json::to_value(&old.program).unwrap();
    raw["operators"] = json!([]);
    raw["contributions"][0]["rhs"] = json!({"op":"state","state":0});
    let p: Program = serde_json::from_value(raw).unwrap();
    let m = EventModel::new_with_trajectory(p, vec!["u".into()], Tolerances::default(), Some(&t))
        .unwrap();
    let before = m.initial();
    let bounds = before.iter().copied().map(I::point).collect::<Vec<_>>();
    let inputs = t.value_bounds(0.5);
    let proofs = crate::event_value_proof::Proofs::new();
    let root = crate::exact_source::RootTime::point(0.5);
    let context =
        crate::event_value_proof::Context::try_new(&m, &t, &inputs, &proofs, root.as_ref())
            .unwrap();
    let selection = m
        .conditions
        .select_with_proofs(&[1], &inputs, &[1], &bounds, Some(&context))
        .unwrap();
    let joint = m
        .event_circuit_program_with_inputs_and_proofs(
            &m.program,
            &selection,
            &before,
            &[],
            &t.values(0.5),
            Some(&context),
        )
        .unwrap();
    let solved = joint.solve(&t.values(0.5)).unwrap();
    assert_eq!(solved.voltages[2], 0.);
    assert_eq!(
        m.apply_with_proofs(&selection, &solved.voltages, &before, Some(&context))
            .unwrap(),
        [0.]
    );
}

#[test]
fn source_floor_without_zero_writes_does_not_prepare_bootstrap_proofs() {
    let (model, trajectory, _, _) = fixture();
    let work = model.floor_source.as_ref().unwrap().work();
    let before = work.spent();
    let (answer, report) = capture(Options::default(), || {
        initialization::prepare(&model, &trajectory)
    });
    assert!(answer.unwrap().is_none());
    assert_eq!(work.spent(), before);
    assert_eq!(
        report
            .counters
            .get("floor_source_bootstrap_dependency_calls")
            .copied()
            .unwrap_or(0),
        0
    );
}

#[test]
fn source_floor_context_reuses_actual_point_certificate_but_preserves_nonpoint_inputs() {
    let (model, trajectory, _, _) = fixture();
    let proofs = crate::event_value_proof::Proofs::new();
    let root = crate::exact_source::RootTime::point(0.5).unwrap();
    for bounds in [I::point(0.03), I { lo: 0.02, hi: 0.04 }] {
        let (answer, report) = capture(Options::default(), || {
            crate::event_value_proof::Context::try_new(
                &model,
                &trajectory,
                &[bounds],
                &proofs,
                Some(&root),
            )
        });
        let context = answer.unwrap();
        let local =
            crate::event_value_proof::LocalState::try_with_context(&[I::point(2.)], Some(&context))
                .unwrap();
        assert_eq!(local.floor_bound(1), Some(bounds));
        assert_eq!(
            local.floor_node(1),
            crate::exact_source::binary(0.03).as_ref()
        );
        let expected = u64::from(bounds.lo != bounds.hi);
        assert_eq!(
            report
                .counters
                .get("floor_source_helper_calls")
                .copied()
                .unwrap_or(0),
            expected
        );
        assert_eq!(
            report
                .counters
                .get("floor_source_helper_reservations")
                .copied()
                .unwrap_or(0),
            expected * 200000
        );
    }
}

#[test]
fn source_floor_context_reserves_only_actual_nonpoint_physical_reads() {
    let (old, old_trajectory, _, _) = fixture();
    let mut program = old.program.clone();
    program.nodes.push("supply".into());
    let mut config = old_trajectory.config.clone();
    config.pwl.push(vec![[0., 0.9], [1., 0.9]]);
    let trajectory = Trajectory::new(config, 2).unwrap();
    let model = EventModel::new_with_trajectory(
        program,
        vec!["u".into(), "supply".into()],
        old.tolerances,
        Some(&trajectory),
    )
    .unwrap();
    let inputs = [I { lo: 0.02, hi: 0.04 }, I::point(0.9)];
    let proofs = crate::event_value_proof::Proofs::new();
    let root = crate::exact_source::RootTime::point(0.5).unwrap();
    let (answer, report) = capture(Options::default(), || {
        crate::event_value_proof::Context::try_new(
            &model,
            &trajectory,
            &inputs,
            &proofs,
            Some(&root),
        )
    });
    let context = answer.unwrap();
    assert_eq!(report.counters.get("floor_source_helper_calls"), Some(&1));
    assert_eq!(
        report.counters.get("floor_source_helper_reservations"),
        Some(&200000)
    );
    let local =
        crate::event_value_proof::LocalState::try_with_context(&[I::point(2.)], Some(&context))
            .unwrap();
    assert_eq!(local.floor_bound(1), Some(inputs[0]));
    assert_eq!(local.floor_bound(3), Some(inputs[1]));
    assert_eq!(
        local.floor_node(1),
        crate::exact_source::binary(0.03).as_ref()
    );
    assert_eq!(
        local.floor_node(3),
        crate::exact_source::binary(0.9).as_ref()
    );
}

// P2 bootstrap/input-map regressions. The pre-fix static findings were fixed at
// 49ae/daa66 by the root review. These tests have not been executed on an old
// instrumented kernel, so they do not supply a claimed old-runtime red result.
fn long_named_zero_floor_fixture() -> (EventModel, Trajectory) {
    const DRIVEN: usize = 32;
    let prefix = format!("floor_bootstrap_{}", "x".repeat(1024));
    let names: Vec<_> = (0..DRIVEN).map(|i| format!("{prefix}_{i:03}")).collect();
    let mut nodes = vec!["0".to_owned()];
    nodes.extend(names.iter().cloned());
    nodes.push("y".to_owned());
    // Reverse the driven order so a positional or Cartesian name-map mistake
    // cannot accidentally agree with the Program's node order.
    let driven: Vec<_> = names.into_iter().rev().collect();
    let pwl: Vec<_> = (0..DRIVEN)
        .map(|k| {
            let node = DRIVEN - k;
            let value = if node == 1 { 0.03 } else { node as f64 / 1000. };
            vec![[0., value], [1., value]]
        })
        .collect();
    let o = json!({"source":"long-floor-bootstrap.va","line":1,"column":1,"instance":"M"});
    let c = |x| json!({"op":"affine","constant":x,"terms":[]});
    let floor = json!({"op":"event_math","function":"floor","origin":o,"args":[
        {"op":"add","left":{"op":"multiply","left":{"op":"divide",
        "left":{"op":"affine","constant":0.,"terms":[{"node":1,"coefficient":1.}]},
        "right":c(0.9)},"right":c(15.)},"right":c(0.5)}]});
    let program: Program = serde_json::from_value(json!({
        "schema_version":SCHEMA_VERSION,"nodes":nodes,
        "states":[{"instance":"M","name":"q","kind":"integer","initial":2.}],
        "events":[{"origin":o,"trigger":{"kind":"timer","start":0.,"period":0.,
            "enabled":true,"time_tolerance":1e-12},"body":[
            {"kind":"assign","state":0,"rhs":floor},
            {"kind":"display","format":"q=%d","args":[{"op":"state","state":0}],"origin":o}]}],
        "operators":[{"kind":"transition","input":{"op":"state","state":0},
            "delay":0.,"rise":0.125,"fall":0.125,"origin":o}],
        "contributions":[{"branch":{"instance":"M","local_positive":"out","local_negative":"ref","kind":"voltage"},
            "positive":DRIVEN+1,"negative":0,"rhs":{"op":"operator","operator":0},"origin":o}]
    })).unwrap();
    let trajectory = Trajectory::new(
        TransientInputs {
            pwl_errors_v: None,
            strobetimes: vec![],
            pwl,
            output_times: vec![0., 1.],
            stop: 1.,
            max_step: 0.125,
        },
        DRIVEN,
    )
    .unwrap();
    let model =
        EventModel::new_with_trajectory(program, driven, Tolerances::default(), Some(&trajectory))
            .unwrap();
    assert!(std::sync::Arc::ptr_eq(
        model.source_context.as_ref().unwrap(),
        &model.floor_source.as_ref().unwrap().source
    ));
    (model, trajectory)
}
fn no_floor_actual_bootstrap_helpers(report: &crate::diagnostics::Report) {
    for key in [
        "floor_source_bootstrap_numeric_calls",
        "floor_source_bootstrap_dependency_calls",
        "floor_source_helper_calls",
    ] {
        assert_eq!(report.counters.get(key).copied().unwrap_or(0), 0, "{key}");
    }
}
fn no_floor_added_retry_work(report: &crate::diagnostics::Report) {
    no_floor_actual_bootstrap_helpers(report);
    for key in [
        "floor_source_input_map_calls",
        "floor_source_copy",
        "floor_source_work_debit",
        "floor_source_owner_created",
        "floor_source_factory_calls",
    ] {
        assert_eq!(report.counters.get(key).copied().unwrap_or(0), 0, "{key}");
    }
}

#[test]
fn source_floor_long_named_zero_timer_naturally_refuses_default_bootstrap_before_helpers_twice_retry(
) {
    let (model, trajectory) = long_named_zero_floor_fixture();
    let source = model.floor_source.as_ref().unwrap().source.clone();
    let work = model.floor_source.as_ref().unwrap().work();
    assert!(work.spent() < 1_000_000_000);
    // No Work::limited, manual debit or unrelated loop: the actual zero-timer
    // initialization asks the new bootstrap helper to reserve its real bound.
    let (answer, report) = capture(Options::default(), || {
        initialization::prepare(&model, &trajectory)
    });
    let error = answer
        .err()
        .expect("the default bootstrap reservation must reject");
    assert_eq!(error.kind, "step_budget");
    assert!(error.message.contains("slot 2"), "{}", error.message);
    assert!(work.spent() > 1_000_000_000);
    no_floor_actual_bootstrap_helpers(&report);
    eprintln!(
        "long_bootstrap_default spent={} counters={:?}",
        work.spent(),
        report.counters
    );
    for retry in 0..2 {
        let spent = work.spent();
        let (answer, report) = capture(Options::default(), || {
            initialization::prepare(&model, &trajectory)
        });
        assert_eq!(answer.err().unwrap().kind, "step_budget");
        assert_eq!(work.spent(), spent);
        no_floor_added_retry_work(&report);
        assert!(std::sync::Arc::ptr_eq(
            &source,
            &model.floor_source.as_ref().unwrap().source
        ));
        eprintln!(
            "long_bootstrap_retry={retry} spent={spent} counters={:?}",
            report.counters
        );
    }
}

#[test]
fn source_floor_long_named_context_maps_actual_nodes_then_same_exhausted_owner_refuses_twice() {
    let (model, trajectory) = long_named_zero_floor_fixture();
    let source = model.floor_source.as_ref().unwrap().source.clone();
    let work = model.floor_source.as_ref().unwrap().work();
    let proofs = crate::event_value_proof::Proofs::new();
    let inputs = trajectory.value_bounds(0.);
    let root = crate::exact_source::RootTime::point(0.);
    let (answer, report) = capture(Options::default(), || {
        crate::event_value_proof::Context::try_new(
            &model,
            &trajectory,
            &inputs,
            &proofs,
            root.as_ref(),
        )
    });
    let context = answer.unwrap();
    assert_eq!(
        report.counters.get("floor_source_input_map_calls"),
        Some(&1)
    );
    let states = model.initial();
    let state_bounds: Vec<_> = states.iter().copied().map(I::point).collect();
    let local =
        crate::event_value_proof::LocalState::try_with_context(&state_bounds, Some(&context))
            .unwrap();
    let mut volts = vec![0.; model.program.nodes.len()];
    for (k, &value) in trajectory.values(0.).iter().enumerate() {
        let node = model.driven.len() - k;
        volts[node] = value;
        assert_eq!(model.program.nodes[node], model.driven[k]);
        assert_eq!(local.floor_bound(node), Some(I::point(value)));
        assert_eq!(
            local.floor_node(node),
            crate::exact_source::binary(value).as_ref()
        );
    }
    let rhs = match &model.program.events[0].body[0] {
        crate::ir::Statement::Assign(a) => &a.rhs,
        _ => panic!("fixture requires an original Floor assignment"),
    };
    assert_eq!(
        crate::event_numeric::value_with_proofs(
            rhs,
            &model.program,
            "M",
            &volts,
            &states,
            Some(&context)
        )
        .unwrap(),
        0.
    );
    let boxes: Vec<_> = volts.iter().copied().map(I::point).collect();
    assert_eq!(
        crate::event_numeric::bounds_with_proofs(rhs, &boxes, &local).unwrap(),
        I::point(0.)
    );
    drop(local);
    drop(context);
    // Exhaust this SAME default owner through the real bootstrap request, not
    // millions of cheap Context calls and not an artificial Work reservation.
    let (answer, exhausted) = capture(Options::default(), || {
        initialization::prepare(&model, &trajectory)
    });
    assert_eq!(answer.err().unwrap().kind, "step_budget");
    assert!(work.spent() > 1_000_000_000);
    no_floor_actual_bootstrap_helpers(&exhausted);
    for retry in 0..2 {
        let spent = work.spent();
        let (answer, report) = capture(Options::default(), || {
            crate::event_value_proof::Context::try_new(
                &model,
                &trajectory,
                &inputs,
                &proofs,
                root.as_ref(),
            )
        });
        assert_eq!(answer.err().unwrap().kind, "step_budget");
        assert_eq!(work.spent(), spent);
        no_floor_added_retry_work(&report);
        assert!(std::sync::Arc::ptr_eq(
            &source,
            &model.floor_source.as_ref().unwrap().source
        ));
        eprintln!(
            "long_context_retry={retry} spent={spent} counters={:?}",
            report.counters
        );
    }
}
