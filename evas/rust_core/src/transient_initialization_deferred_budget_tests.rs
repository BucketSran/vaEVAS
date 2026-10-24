//! The private Work cap accelerates exhaustion of real preparation, without
//! changing the public default cap or manually spending the remaining balance.
use super::*;

#[test]
fn deferred_initial_repeated_prepare_naturally_exhausts_one_owner_and_fresh_owner_succeeds() {
    const PRIVATE_WORK_CAP: u64 = 2_000_000;
    fn make() -> (EventModel, Trajectory, crate::transition_source_plan::Work) {
        let request: Request = serde_json::from_str(include_str!(
            "../tests/fixtures/initial_bootstrap_retry.request.json"
        ))
        .unwrap();
        let trajectory = Trajectory::new(request.transient.unwrap(), request.driven.len()).unwrap();
        // Only this private test uses 2M work units. Production default remains
        // [128, 8192, 1_000_000_000], and all public requests stay unchanged.
        let owner = crate::transition_source_plan::Work::limited([128, 8192, PRIVATE_WORK_CAP]);
        let model = EventModel::new_with_procedure_work(
            request.program,
            request.driven,
            request.tolerances,
            owner.clone(),
        )
        .unwrap();
        (model, trajectory, owner)
    }
    fn check_prepared(ready: Prepared) {
        assert!(ready.deferred_zero);
        assert_eq!(ready.states, vec![0., -1., 0.]);
        assert_eq!(ready.records.len(), 1);
        assert_eq!(ready.records[0].kind, "initial_step");
        assert_eq!(ready.records[0].before, vec![0., 0., 0.]);
        assert_eq!(ready.records[0].after, vec![0., -1., 0.]);
        assert!(ready.future.is_none());
        assert!(ready.zero.is_empty());
    }
    let (model, trajectory, owner) = make();
    let original = serde_json::to_value(&model.program).unwrap();
    assert!(cold_work(&model).same_owner(&owner));
    assert!(crate::real_expression::work(&model).same_owner(&owner));
    let ids: Vec<_> = model
        .triggers
        .iter()
        .enumerate()
        .filter_map(|(id, leaf)| {
            matches!(leaf.trigger, EventTrigger::InitialStep { .. }).then_some(id)
        })
        .collect();
    let blocks: Vec<_> = ids.iter().map(|&id| model.triggers[id].event).collect();
    // This fixture has a non-self-copy zero writer q=0, so it cannot return
    // through the older initial_split path. Its held timer also excludes the
    // no-held shortcut. A successful deferred result reaches deferred_initial.
    assert!(
        super::initial_split::prepare(&model, &trajectory, &ids, &blocks)
            .unwrap()
            .is_none()
    );
    let mut completed = 0;
    loop {
        assert!(
            completed < 10_000,
            "real preparation did not exhaust the private cap"
        );
        let spent = owner.spent();
        match prepare(&model, &trajectory) {
            Ok(Some(ready)) => {
                check_prepared(ready);
                completed += 1;
                assert!(owner.spent() > spent);
            }
            Err(error) => {
                assert_eq!(error.kind, "step_budget");
                assert!(error.message.contains("slot 2"), "{}", error.message);
                assert!(owner.spent() > PRIVATE_WORK_CAP);
                break;
            }
            Ok(None) => panic!("IR33 initial gate was discarded"),
        }
        assert_eq!(serde_json::to_value(&model.program).unwrap(), original);
        assert_eq!(model.initial(), vec![0., 0., 0.]);
        assert!(cold_work(&model).same_owner(&owner));
    }
    assert!(
        completed > 1,
        "need repeated successful preparations before exhaustion"
    );
    for _ in 0..2 {
        let spent = owner.spent();
        assert_eq!(
            prepare(&model, &trajectory).err().unwrap().kind,
            "step_budget"
        );
        assert!(owner.spent() >= spent);
        assert!(cold_work(&model).same_owner(&owner));
        assert!(crate::real_expression::work(&model).same_owner(&owner));
        assert_eq!(serde_json::to_value(&model.program).unwrap(), original);
        assert_eq!(model.initial(), vec![0., 0., 0.]);
    }
    let (fresh, fresh_trajectory, fresh_owner) = make();
    assert!(!fresh_owner.same_owner(&owner));
    check_prepared(prepare(&fresh, &fresh_trajectory).unwrap().unwrap());
    assert!(fresh_owner.spent() < PRIVATE_WORK_CAP);
    assert_eq!(serde_json::to_value(&fresh.program).unwrap(), original);
    eprintln!(
        "deferred_initial natural completed={completed}, private_cap={PRIVATE_WORK_CAP}, exhausted_spent={}, fresh_spent={}",
        owner.spent(), fresh_owner.spent()
    );
}
