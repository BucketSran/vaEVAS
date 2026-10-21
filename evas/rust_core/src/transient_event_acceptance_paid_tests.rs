//! Actual analytic transaction costs; no new production allowance.
use super::super::analytic_tests::{sampled_transition_fixture, sampled_transition_unchanged};
use super::*;

fn snapshot(c: &Controller, calendar: &[ScheduledEvent]) -> serde_json::Value {
    serde_json::json!({
        "time": c.accepted.time, "event": c.event, "records": c.records,
        "states": c.accepted.states,
        "state_bounds": c.accepted.state_bounds.iter().map(|b| [b.lo,b.hi]).collect::<Vec<_>>(),
        "solution": c.accepted.solution,
        "outputs": c.outputs.iter().map(|f| (f.time, &f.states)).collect::<Vec<_>>(),
        "calendar": calendar.iter().map(ScheduledEvent::analytic_test_snapshot).collect::<Vec<_>>()
    })
}

#[test]
fn unrelated_future_calendar_tail_does_not_repay_phase_product() {
    let cost = |extra: usize| {
        let (m, t, c, mut calendar) = sampled_transition_fixture();
        // Repeated future occurrences retain their original clock/root proof.
        // They are strictly beyond this transaction's .125 timer and its
        // immediate .75 successor, so none belongs to the consumed prefix.
        let successor = calendar.last().unwrap().clone();
        calendar.extend(std::iter::repeat_n(successor, extra));
        let before = snapshot(&c, &calendar);
        let w = m.analytic_request.as_ref().unwrap().work();
        let spent = w.spent();
        let prepared = PreparedEvents::prepare(&c, &m, &t, &calendar, Strategy::Static).unwrap();
        let cost = w.spent() - spent;
        assert_eq!(snapshot(&c, &calendar), before);
        assert_eq!(prepared.frame.time, 0.125);
        cost
    };
    assert_eq!(cost(0), cost(64));
}

#[test]
fn reached_output_query_pays_scan_phase_and_candidate_work() {
    let cost = |query: bool| {
        let (m, mut t, c, calendar) = sampled_transition_fixture();
        // This changes passive sampling only; the token's original physical
        // provider and held target are retained without rebuilding a Work.
        t.config.output_times = if query { vec![0.0625] } else { vec![] };
        let before = snapshot(&c, &calendar);
        let w = m.analytic_request.as_ref().unwrap().work();
        let spent = w.spent();
        let prepared = PreparedEvents::prepare(&c, &m, &t, &calendar, Strategy::Static).unwrap();
        let cost = w.spent() - spent;
        assert_eq!(prepared.outputs.len(), usize::from(query));
        assert_eq!(snapshot(&c, &calendar), before);
        cost
    };
    // One actual output-list visit, one phase and its physical event each pay
    // the unchanged 128 unit. Observation cloning/proof adds further work.
    assert!(cost(true) >= cost(false) + 3 * 128);
}

#[test]
fn paid_candidate_scan_failure_and_two_retries_preserve_original_transaction() {
    let (m, t, mut c, mut calendar) = sampled_transition_fixture();
    let before = snapshot(&c, &calendar);
    let accepted = c.accepted.clone();
    let old_outputs = c.outputs.clone();
    let w = m.analytic_request.as_ref().unwrap().work();
    assert!(w.same_owner(t.analytic_work().unwrap()));
    assert!(w.same_owner(c.accepted.operators.history_copy_work().unwrap()));
    // Deliberate boundary setup, not a claim of natural exhaustion: leave
    // exactly the unchanged entry reservation, so the first real batch scan
    // must fail before any candidate allocation. Never replace/reset the Work.
    w.debit(2, 1_000_000_000 - w.spent() - 16_384).unwrap();
    for attempt in 0..3 {
        let spent = w.spent();
        assert_eq!(
            c.accept_changed_events(&m, &t, &mut calendar, Strategy::Static)
                .unwrap_err()
                .kind,
            "step_budget"
        );
        if attempt == 0 {
            assert!(w.spent() > spent);
            assert!(w.spent() > 1_000_000_000);
        } else {
            // The original shared source owner may reject with charge(0)
            // before returning to prepare. Exhaustion cannot refund work.
            assert!(w.spent() >= spent);
        }
        assert_eq!(snapshot(&c, &calendar), before);
        sampled_transition_unchanged(&c.accepted, &accepted);
        assert_eq!(c.outputs.len(), old_outputs.len());
        for (actual, prior) in c.outputs.iter().zip(&old_outputs) {
            sampled_transition_unchanged(actual, prior);
        }
    }
}
