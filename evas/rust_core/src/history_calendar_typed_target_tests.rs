//! Work accounting of one typed history calendar holding typed integer targets
//! (operators 1 and 2), a bare real target (0) and an ordinary integer-select
//! target (3). Every copy and advance is paid exactly once on the shared owner.
use super::*;
use crate::ir::{Program, Tolerances, TransientInputs};
use crate::transition_source_plan::Work;

fn trajectory() -> Trajectory {
    Trajectory::new(
        TransientInputs {
            analytic_sources: vec![],
            pwl_errors_v: None,
            strobetimes: vec![],
            pwl: vec![],
            output_times: vec![0., 0.5, 1., 2.5],
            stop: 2.5,
            max_step: 0.125,
            proof_work_limit: None,
        },
        0,
    )
    .unwrap()
}

fn calendar(t: &Trajectory) -> (EventModel, Operators, Work) {
    // test_group_event_calendar.HELD_SOURCE compiled by the Python frontend.
    let program: Program = serde_json::from_str(include_str!(
        "../../tests/fixtures/typed-calendar-mixed-held.json"
    ))
    .unwrap();
    let model =
        EventModel::new_with_trajectory(program, vec![], Tolerances::default(), Some(t)).unwrap();
    assert_eq!(
        model
            .typed_transition_targets
            .iter()
            .copied()
            .collect::<Vec<_>>(),
        vec![1, 2]
    );
    let (operators, _) = initialize(&model, t, &model.initial(), None).unwrap();
    let w = operators
        .history_copy_work()
        .expect("a typed calendar meters its ordinary entries")
        .clone();
    assert!(w.same_owner(model.source_context.as_ref().unwrap().borrow_work()));
    (model, operators, w)
}

fn replays(run: impl FnOnce() -> Result<(), Error>) -> u64 {
    let (result, report) = crate::diagnostics::capture(Default::default(), run);
    result.unwrap();
    report
        .counters
        .get("history_target_proof_replays")
        .copied()
        .unwrap_or(0)
}

#[test]
fn mixed_calendar_pays_copies_and_advances_and_replays_only_installed_targets() {
    let t = trajectory();
    let (model, operators, w) = calendar(&t);
    let states = model.initial();
    let bounds: Vec<_> = states.iter().copied().map(I::point).collect();

    let before = w.spent();
    let mut candidate = operators.candidate_clone().unwrap();
    assert!(w.spent() > before, "a candidate copy must be metered");

    // No write: every history advances (and pays), no target is installed,
    // so no exact target proof is replayed.
    let before = w.spent();
    let quiet = replays(|| candidate.advance(0.5, I::point(0.5), &states, &bounds, &[]));
    assert!(w.spent() > before, "an advance must be metered");
    assert_eq!(quiet, 0);

    // Writing k installs exactly one new ordinary target (operator 3).
    let k = 3;
    let mut written = states.clone();
    written[k] = 1.;
    let written_bounds: Vec<_> = written.iter().copied().map(I::point).collect();
    let before = w.spent();
    let installed =
        replays(|| candidate.advance(1., I::point(1.), &written, &written_bounds, &[k]));
    assert!(w.spent() > before);
    assert_eq!(installed, 1);
}

#[test]
fn typed_entry_range_pays_its_history_copy_once() {
    let t = trajectory();
    let (_, operators, w) = calendar(&t);
    let time = I {
        lo: 0.25,
        hi: 0.375,
    };
    for index in [1, 2] {
        // Expected fee: one held-history copy plus the paid query itself,
        // replayed on a private ledger.
        let history = operators.test_transition_histories()[index].clone();
        let copy = std::cell::Cell::new(0u64);
        history
            .charge_held_copy(&|n| {
                copy.set(copy.get() + n as u64);
                Ok(())
            })
            .unwrap();
        let scratch = Work::limited([u64::MAX; 3]);
        let mut probe = history.clone();
        probe.history_advance_time(time.lo, &scratch).unwrap();
        probe.history_continuous_range(time, &scratch).unwrap();
        let before = w.spent();
        operators.range(index, time).unwrap();
        assert_eq!(
            w.spent() - before,
            copy.get() + scratch.spent(),
            "operator {index}"
        );
    }
}
