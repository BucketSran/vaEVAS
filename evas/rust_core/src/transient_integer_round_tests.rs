//! NearestInteger and original Floor share the production Controller and request Work.
use super::*;
use crate::diagnostics::{capture, Options};
use crate::ir::{Program, Tolerances, TransientInputs};
use serde_json::{json, Value};
fn fixture() -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    let o = json!({"source":"integer_round.va","line":1,"column":1,"instance":"M"});
    let c = |x| json!({"op":"affine","constant":x,"terms":[]});
    let floor = json!({"op":"integer_round","origin":o,"value":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]}});
    let p:Program=serde_json::from_value(json!({"schema_version":SCHEMA_VERSION,"nodes":["0","u","y"],"states":[{"instance":"M","name":"q","kind":"integer","initial":2},{"instance":"M","name":"aux","kind":"integer","initial":0}],"events":[
        {"trigger":{"kind":"timer","start":0.125,"period":0,"enabled":true,"time_tolerance":1e-9},"origin":o,"body":[{"kind":"assign","state":0,"rhs":c(2.)}]},
        {"trigger":{"kind":"timer","start":0.5,"period":0,"enabled":true,"time_tolerance":1e-9},"origin":o,"body":[{"kind":"assign","state":0,"rhs":floor},{"kind":"assign","state":1,"rhs":{"op":"event_math","function":"floor","origin":o,"args":[{"op":"divide","left":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]},"right":c(0.9)}]}},{"kind":"display","format":"q=%d","args":[{"op":"state","state":0}],"origin":o}]}],
        "operators":[{"kind":"transition","input":{"op":"state","state":0},"delay":0,"rise":0.125,"fall":0.125,"origin":o}],
        "contributions":[{"branch":{"instance":"M","local_positive":"out","local_negative":"ref","kind":"voltage"},"positive":2,"negative":0,"rhs":{"op":"operator","operator":0},"origin":o}]})).unwrap();
    let t = Trajectory::new(
        TransientInputs {
            analytic_sources: vec![],
            pwl_errors_v: None,
            strobetimes: vec![],
            pwl: vec![vec![[0., 0.03], [1., 0.03]]],
            output_times: vec![0., 0.75, 1.],
            stop: 1.,
            max_step: 0.125,
            proof_work_limit: None,
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
fn integer_round_actual_controller_late_voltage_failure_twice_then_legal_retry() {
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
        assert_eq!(candidate.states, [0., 0.]);
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
fn integer_round_natural_original_owner_exhaustion_and_twice_retry_no_clone_or_helper() {
    let (answer, report) = capture(Options::default(), || {
        let (m, t, mut c, mut calendar) = fixture();
        // Reuse this physical request's existing Floor+Round owner. New role
        // lookups and existing admission payload copies must debit it before
        // reading target metadata; no fresh ledger belongs to role checking.
        let owner = m.floor_source.as_ref().unwrap().work();
        let entry_spent = owner.spent();
        let (admitted, roles) = capture(Options::default(), || {
            crate::event_control::admit(&m.program, Some(owner)).map(|_| ())
        });
        admitted.unwrap();
        assert_eq!(
            roles.counters.get("integer_round_role_validation"),
            Some(&16)
        );
        assert!(owner.spent() > entry_spent);
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
                    crate::event_control::admit(&m.program, Some(work))
                        .err()
                        .unwrap()
                        .kind,
                    "step_budget"
                );
                assert_eq!(work.spent(), spent);
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
        assert!(!retry.counters.contains_key("integer_round_role_validation"));
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
