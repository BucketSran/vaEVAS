//! Raw-transport ownership admission uses the original request Work ledger.
use super::*;
fn raw() -> Program {
    serde_json::from_str::<ir::Request>(include_str!("raw_event_owner_request.json"))
        .unwrap()
        .program
}
fn owned() -> Program {
    let mut p = raw();
    p.events[0].procedure_id = Some(0);
    p.events[0].expanded_statement_ordinal = Some(1);
    let gate: ProcedureStep = serde_json::from_value(serde_json::json!({
        "expanded_statement_ordinal":1,"action":{"kind":"event_gate","event":0}
    }))
    .unwrap();
    p.procedures[0].body.push(gate);
    p
}
#[test]
fn raw_owner_missing_metadata_must_reject() {
    assert_eq!(
        validate(&raw(), &Work::default()).unwrap_err().kind,
        "invalid_ir"
    );
}
#[test]
fn raw_owner_matching_gate_and_empty_legacy_remain_valid() {
    validate(&owned(), &Work::default()).unwrap();
    let mut legacy = raw();
    legacy.procedures.clear();
    validate(&legacy, &Work::default()).unwrap();
    legacy.events[0].expanded_statement_ordinal = Some(0);
    assert_eq!(
        validate(&legacy, &Work::default()).unwrap_err().kind,
        "invalid_ir"
    );
}
#[test]
fn raw_owner_missing_gate_partial_metadata_and_cross_instance_reject() {
    for mutation in 0..6 {
        let mut p = owned();
        match mutation {
            0 => {
                p.procedures[0].body.pop();
            }
            1 => p.events[0].procedure_id = None,
            2 => p.events[0].expanded_statement_ordinal = None,
            3 => p.events[0].origin.instance = "other".into(),
            4 => p.events[0].procedure_id = Some(9),
            _ => {
                p.procedures.clear();
            }
        }
        assert_eq!(
            validate(&p, &Work::default()).unwrap_err().kind,
            "invalid_ir",
            "mutation {mutation}"
        );
    }
}
#[test]
fn raw_owner_duplicate_in_hidden_branch_rejects() {
    let mut p = owned();
    let branch: ProcedureStep = serde_json::from_value(serde_json::json!({
        "expanded_statement_ordinal":2,"action":{"kind":"procedure_if", "relation":"gt",
        "left":{"op":"affine","constant":0,"terms":[]},
        "right":{"op":"affine","constant":1,"terms":[]},
        "then_body":[{"expanded_statement_ordinal":3,"action":{"kind":"event_gate","event":0}}],
        "else_body":[],"origin":{"source":"raw.va","line":1,"column":1,"instance":"dut"}}
    }))
    .unwrap();
    // This branch is never numerically selected; validation must still inspect it.
    p.procedures[0].body.push(branch.clone());
    assert_eq!(
        validate(&p, &Work::default()).unwrap_err().kind,
        "invalid_ir"
    );
    p.procedures[0].body.remove(1);
    p.events[0].expanded_statement_ordinal = Some(3);
    validate(&p, &Work::default()).unwrap();
    p.events[0].procedure_id = None;
    assert_eq!(
        validate(&p, &Work::default()).unwrap_err().kind,
        "invalid_ir"
    );
}
#[test]
fn raw_owner_validation_spends_original_budget_and_retry_is_sticky() {
    let p = owned();
    let measured = Work::default();
    validate(&p, &measured).unwrap();
    let cap = measured.spent() - 1;
    let work = Work::limited([128, 8192, cap]);
    let retry = work.clone();
    assert!(work.same_owner(&retry));
    for _ in 0..2 {
        let before = work.spent();
        assert_eq!(validate(&p, &retry).unwrap_err().kind, "step_budget");
        assert!(work.spent() > before);
    }
    validate(&p, &Work::default()).unwrap();
    eprintln!(
        "RAW_EVENT_OWNER_WORK measured={} cap={} sticky_retries=2 fresh_owner=pass",
        measured.spent(),
        cap
    );
}
