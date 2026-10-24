//! Source-faithful qualification and shared-ledger tests. Numerical behavior
//! remains covered by the unchanged public source requests, not these scans.
use super::*;
use crate::transition_source_plan::Work;

fn request() -> crate::ir::Request {
    serde_json::from_str(include_str!("causal_event_floor_rn_request.json")).unwrap()
}

fn scan(p: &Program, driven: &[String], work: &Work) -> Result<Vec<bool>, Error> {
    let admission = crate::event_control::admit(p, Some(work))?;
    let sources = crate::procedure::dependency_sources(p, work)?;
    classify(p, &vec![false; p.events.len()], driven, &admission, Some(work), Some(&sources))
}

#[test]
fn procedure_source_qualification_borrows_the_original_ledger() {
    let r = request();
    let work = Work::default();
    let retry = work.clone();
    assert!(work.same_owner(&retry));
    let before = work.spent();
    let eligible = scan(&r.program, &r.driven, &work).unwrap();
    assert!(eligible.iter().any(|v| *v));
    assert!(work.spent() > before);
    assert_eq!(work.spent(), retry.spent());
    let again = scan(&r.program, &r.driven, &retry).unwrap();
    assert_eq!(eligible, again);
    assert!(work.spent() > before);
}

#[test]
fn source_rn_nodes_do_not_enter_legacy_nonprocedure_events() {
    let mut r = request();
    for event in &mut r.program.events { event.procedure_id = None; }
    let error = scan(&r.program, &r.driven, &Work::default()).unwrap_err();
    assert_eq!(error.kind, "unsupported_floor");
}

#[test]
fn repeated_original_source_scans_naturally_exhaust_one_billion_and_stay_exhausted() {
    let r = request();
    let work = Work::default();
    let retry = work.clone();
    let mut accepted = 0usize;
    loop {
        match scan(&r.program, &r.driven, &work) {
            Ok(_) => accepted += 1,
            Err(error) => { assert_eq!(error.kind, "step_budget"); break; }
        }
        assert!(accepted < 1_000_000, "original request stopped consuming Work");
    }
    assert!(accepted > 0);
    assert!(work.spent() > 1_000_000_000);
    for _ in 0..2 {
        assert_eq!(scan(&r.program, &r.driven, &retry).unwrap_err().kind, "step_budget");
    }
    assert!(scan(&r.program, &r.driven, &Work::default()).unwrap().iter().any(|v| *v));
    eprintln!("FLOOR_RN_SHARED_WORK accepted={accepted} spent={} sticky_retries=2 fresh_owner=pass", work.spent());
}
