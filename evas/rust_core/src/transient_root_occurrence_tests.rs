use super::*;
fn fixture() -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    let mut raw: serde_json::Value =
        serde_json::from_str(include_str!("../tests/root_occurrence_program.json")).unwrap();
    raw["schema_version"] = serde_json::json!(SCHEMA_VERSION);
    let model = EventModel::new(
        serde_json::from_value(raw).unwrap(),
        vec!["a".into(), "b".into()],
        crate::ir::Tolerances {
            absolute: 1e-12,
            relative: 0.,
        },
    )
    .unwrap();
    let trajectory=Trajectory::new(serde_json::from_value(serde_json::json!({"pwl":[[[0.,-4503599627370496.],[1.,4503599627370497.]],[[0.,-4503599627370497.],[1.,4503599627370498.]]],"stop":1.,"max_step":0.25,"output_times":[0.25,0.75]})).unwrap(),2).unwrap();
    let states = vec![1.];
    let operators = Operators::new(&model.program, &trajectory, &model.driven, &states).unwrap();
    let calendar = independent_schedule(&model, &trajectory).unwrap();
    assert_eq!(calendar.len(), 2);
    assert_eq!(calendar[0].time, calendar[1].time);
    assert_eq!(crate::schedule::batch_end(&calendar, 0, &model).unwrap(), 1);
    let circuit = model.circuit_with(&states, &[]).unwrap();
    let accepted = Frame {
        time: 0.,
        state_bounds: vec![I::point(1.)],
        value_proofs: Default::default(),
        time_proofs: Default::default(),
        states,
        solution: circuit
            .solve(&[-4503599627370496., -4503599627370497.])
            .unwrap(),
        circuit,
        operators,
    };
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
#[test]
fn same_float_distinct_roots_second_candidate_failure_rolls_back_then_retries() {
    let (model, trajectory, mut controller, mut calendar) = fixture();
    let original = calendar
        .iter()
        .map(|e| (e.event, e.time, e.bounds()))
        .collect::<Vec<_>>();
    let calls = std::rc::Rc::new(std::cell::Cell::new(0));
    let counter = calls.clone();
    let error = event_acceptance::test_with_final_candidate(
        move |frame| {
            let n = counter.get() + 1;
            counter.set(n);
            if n == 2 {
                frame.states[0] = f64::NAN;
            }
        },
        || {
            controller.accept_changed_events(
                &model,
                &trajectory,
                &mut calendar,
                event_acceptance::Strategy::Static,
            )
        },
    )
    .unwrap_err();
    assert_eq!(
        calls.get(),
        2,
        "the error must occur after preparing both physical phases"
    );
    assert!(!error.kind.is_empty());
    assert_eq!(controller.accepted.states, vec![1.]);
    assert_eq!(controller.accepted.time, 0.);
    assert_eq!(controller.event, 0);
    assert!(controller.records.is_empty());
    assert!(controller.outputs.is_empty());
    assert_eq!(
        calendar
            .iter()
            .map(|e| (e.event, e.time, e.bounds()))
            .collect::<Vec<_>>(),
        original
    );
    controller
        .accept_changed_events(
            &model,
            &trajectory,
            &mut calendar,
            event_acceptance::Strategy::Static,
        )
        .unwrap();
    assert_eq!(controller.accepted.states, vec![6.]);
    assert_eq!(controller.event, 2);
    assert_eq!(controller.records.len(), 2);
    let (clean_model, clean_trajectory, mut clean, mut clean_calendar) = fixture();
    clean
        .accept_changed_events(
            &clean_model,
            &clean_trajectory,
            &mut clean_calendar,
            event_acceptance::Strategy::Static,
        )
        .unwrap();
    assert_eq!(controller.accepted.states, clean.accepted.states);
    assert_eq!(controller.event, clean.event);
    assert_eq!(
        serde_json::to_value(&controller.records).unwrap(),
        serde_json::to_value(&clean.records).unwrap()
    );
}

fn physical_fixture() -> (EventModel, Trajectory, Controller, Vec<ScheduledEvent>) {
    let raw: serde_json::Value =
        serde_json::from_str(include_str!("../tests/root_epoch_request.json")).unwrap();
    let model = EventModel::new(
        serde_json::from_value(raw["program"].clone()).unwrap(),
        vec!["a".into(), "b".into()],
        crate::ir::Tolerances {
            absolute: 1e-12,
            relative: 0.,
        },
    )
    .unwrap();
    let mut trajectory =
        Trajectory::new(serde_json::from_value(raw["transient"].clone()).unwrap(), 2).unwrap();
    trajectory
        .bind_procedure_work(crate::real_expression::work(&model))
        .unwrap();
    let states = vec![0.];
    let operators = Operators::new(&model.program, &trajectory, &model.driven, &states).unwrap();
    let calendar = independent_schedule(&model, &trajectory).unwrap();
    let values = operators.values(0.).unwrap();
    let circuit = model.circuit_with(&states, &values).unwrap();
    let accepted = Frame {
        time: 0.,
        state_bounds: vec![I::point(0.)],
        value_proofs: Default::default(),
        time_proofs: Default::default(),
        states,
        solution: circuit
            .solve(&[-4503599627370496., -4503599627370497.])
            .unwrap(),
        circuit,
        operators,
    };
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
#[test]
fn physical_idt_second_phase_failure_rolls_back_history_outputs_and_retries() {
    let (model, trajectory, mut controller, mut calendar) = physical_fixture();
    let work = crate::real_expression::work(&model);
    let spent = work.spent();
    let original = calendar
        .iter()
        .map(|e| (e.event, e.time, e.bounds()))
        .collect::<Vec<_>>();
    let before = controller.accepted.operators.values(0.75).unwrap();
    let calls = std::rc::Rc::new(std::cell::Cell::new(0));
    let counter = calls.clone();
    let error = event_acceptance::test_with_final_candidate(
        move |frame| {
            let n = counter.get() + 1;
            counter.set(n);
            if n == 2 {
                frame.states[0] = f64::NAN;
            }
        },
        || {
            controller.accept_changed_events(
                &model,
                &trajectory,
                &mut calendar,
                event_acceptance::Strategy::Static,
            )
        },
    )
    .unwrap_err();
    assert!(!error.kind.is_empty());
    assert_eq!(calls.get(), 2);
    assert!(work.spent() > spent);
    assert_eq!(controller.accepted.time, 0.);
    assert_eq!(controller.accepted.states, vec![0.]);
    assert_eq!(controller.accepted.operators.values(0.75).unwrap(), before);
    assert_eq!(controller.event, 0);
    assert!(controller.records.is_empty());
    assert!(controller.outputs.is_empty());
    assert_eq!(
        calendar
            .iter()
            .map(|e| (e.event, e.time, e.bounds()))
            .collect::<Vec<_>>(),
        original
    );
    controller
        .accept_changed_events(
            &model,
            &trajectory,
            &mut calendar,
            event_acceptance::Strategy::Static,
        )
        .unwrap();
    assert_eq!(controller.accepted.states, vec![0.]);
    assert_eq!(controller.records.len(), 2);
    assert_eq!(controller.event, 2);
    let (clean_model, clean_trajectory, mut clean, mut clean_calendar) = physical_fixture();
    clean
        .accept_changed_events(
            &clean_model,
            &clean_trajectory,
            &mut clean_calendar,
            event_acceptance::Strategy::Static,
        )
        .unwrap();
    assert_eq!(
        controller.accepted.operators.values(0.75).unwrap(),
        clean.accepted.operators.values(0.75).unwrap()
    );
    assert_eq!(
        controller.accepted.operators.bounds(0.75).unwrap(),
        clean.accepted.operators.bounds(0.75).unwrap()
    );
    assert_eq!(
        serde_json::to_value(&controller.records).unwrap(),
        serde_json::to_value(&clean.records).unwrap()
    );
    let values = controller.accepted.operators.values(0.75).unwrap();
    assert!((values[0] * 2f64.powi(106) - 1.).abs() < 1e-12);
}
#[test]
fn physical_epoch_rejects_foreign_owner_and_exhausted_owner_stays_sticky() {
    let (model, trajectory, mut controller, mut calendar) = physical_fixture();
    controller
        .accept_changed_events(
            &model,
            &trajectory,
            &mut calendar,
            event_acceptance::Strategy::Static,
        )
        .unwrap();
    let root = crate::schedule::common_root_with_work(
        &calendar[..1],
        crate::real_expression::work(&model),
    )
    .unwrap()
    .unwrap();

    let (foreign, _, _, _) = physical_fixture();
    assert_eq!(
        controller
            .accepted
            .operators
            .same_reset_history_with_physical_roots(
                &controller.accepted.operators,
                crate::real_expression::work(&foreign)
            )
            .err()
            .unwrap()
            .kind,
        "invalid_ir"
    );
    let work = crate::real_expression::work(&model);
    let spent = work.spent();
    controller
        .accepted
        .operators
        .evaluation_at_root(calendar[0].time, Some(&root), calendar[0].bounds())
        .unwrap();
    assert!(work.spent() > spent);
    work.debit(2, u64::MAX).unwrap_err();
    let spent = work.spent();
    for _ in 0..2 {
        assert_eq!(
            controller
                .accepted
                .operators
                .evaluation_at_root(calendar[0].time, Some(&root), calendar[0].bounds())
                .err()
                .unwrap()
                .kind,
            "step_budget"
        );
        assert_eq!(work.spent(), spent);
    }
}
#[test]
fn root_phase_deferral_requires_immutable_complete_guard_dependencies() {
    let (mut model, trajectory, _, calendar) = physical_fixture();
    let w = crate::real_expression::work(&model).clone();
    assert!(
        root_epoch_phase::pending_before_display(&model, &trajectory, &calendar, 0, 1, &w)
            .unwrap()
            .is_some()
    );
    let index = calendar[1].event;
    if let EventTrigger::Cross { guard, .. } = &mut model.triggers[index].trigger {
        *guard = crate::ir::Expression::State { state: 0 };
    } else {
        panic!()
    }
    assert!(
        root_epoch_phase::pending_before_display(&model, &trajectory, &calendar, 0, 1, &w)
            .unwrap()
            .is_none()
    );
    if let EventTrigger::Cross { guard, .. } = &mut model.triggers[index].trigger {
        *guard = crate::ir::Expression::RealLocal {
            binding: usize::MAX,
        };
    }
    assert!(
        root_epoch_phase::pending_before_display(&model, &trajectory, &calendar, 0, 1, &w)
            .unwrap()
            .is_none()
    );
    if let EventTrigger::Cross { guard, .. } = &mut model.triggers[index].trigger {
        *guard = crate::ir::Expression::Affine {
            constant: 0.,
            terms: vec![crate::ir::Term {
                node: 999,
                coefficient: 1.,
            }],
        };
    }
    assert!(
        root_epoch_phase::pending_before_display(&model, &trajectory, &calendar, 0, 1, &w)
            .unwrap()
            .is_none()
    );
}

#[test]
fn independent_memoryless_observer_preserves_subulp_physical_integral() {
    // Public source: the original two-root integral plus V(z)<+exp(0).
    // The exact root difference and original scale give this independent area.
    let request: crate::ir::Request =
        serde_json::from_str(include_str!("../tests/root_epoch_memoryless_request.json")).unwrap();
    let response = crate::run(request).unwrap();
    let raw = serde_json::to_value(&response).unwrap();
    let expected: num_rational::BigRational =
        "81129638414606681695789005144064/81129638414606717724586024108035"
            .parse()
            .unwrap();
    let bounds = &raw["observation_evidence"]["voltage_bounds_V"][1][3];
    let lo = num_rational::BigRational::from_float(bounds[0].as_f64().unwrap()).unwrap();
    let hi = num_rational::BigRational::from_float(bounds[1].as_f64().unwrap()).unwrap();
    assert!(lo <= expected && expected <= hi);
    assert!((raw["solutions"][1]["voltages"][3].as_f64().unwrap() - 1.).abs() < 1e-12);
    for row in raw["solutions"].as_array().unwrap() {
        assert_eq!(row["voltages"][4].as_f64().unwrap(), 1.);
    }
}
