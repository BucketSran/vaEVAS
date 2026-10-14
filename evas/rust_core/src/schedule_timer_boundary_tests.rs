//! Full-window ordering and current leaf-consumption certificates.
use super::*;
fn model() -> EventModel {
    let origin =
        serde_json::json!({"source":"timer_boundary.va","line":1,"column":1,"instance":"dut"});
    let program=serde_json::from_value(serde_json::json!({
        "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","y"],
        "states":[{"instance":"dut","name":"b","kind":"real","initial":0.75}],
        "events":[{"origin":origin,"trigger":{"kind":"timer","start":0.125,"period":0.,"time_tolerance":1e-12,"enabled":true},"body":[]},
            {"origin":origin,"trigger":{"kind":"or","triggers":[
                {"kind":"timer","start":0.5,"period":0.,"time_tolerance":1e-12,"enabled":true},
                {"kind":"held_timer","start":{"op":"state","state":0},"period":{"op":"affine","constant":0.,"terms":[]},"enabled":{"op":"affine","constant":1.,"terms":[]},"time_tolerance":0.001}]},"body":[]}],
        "contributions":[{"branch":{"instance":"dut","local_positive":"p","local_negative":"r","kind":"voltage"},"positive":1,"negative":0,"rhs":{"op":"state","state":0},"origin":origin}]
    })).unwrap();
    EventModel::new(
        program,
        vec![],
        crate::ir::Tolerances {
            absolute: 1e-8,
            relative: 0.,
        },
    )
    .unwrap()
}
fn fixed(clock: Clock, time: f64) -> ScheduledEvent {
    ScheduledEvent {
        time,
        event: 1,
        moment: Moment::Timer {
            bounds: clock.bounds().unwrap(),
            start: clock.start,
            period: clock.period,
            index: clock.index,
        },
        fixed_predecessor: None,
    }
}
fn held(clock: Option<Clock>, bounds: I, time: f64) -> ScheduledEvent {
    ScheduledEvent {
        time,
        event: 2,
        moment: Moment::HeldTimer {
            bounds,
            index: clock.map_or(0, |c| c.index),
            clock,
        },
        fixed_predecessor: None,
    }
}
fn point(t: f64) -> Clock {
    Clock {
        start: t,
        period: 0.,
        index: 0,
    }
}
fn check_exact_anchor_orders_both_sides_without_consuming_equal_new_leaf() {
    let m = model();
    let c = Clock {
        start: 0.1,
        period: 0.2,
        index: 1,
    };
    let b = c.bounds().unwrap();
    assert!(b.lo < b.hi);
    let batch = [fixed(c, b.hi)];
    let boundary = TimerBoundary::new(&m, b.hi, &batch).unwrap();
    // Exact .1+.2 is strictly between .3 and next_up(.3), independent of
    // shared enclosure endpoints. These are ordering proofs, not consumption.
    assert_eq!(c.order(point(b.lo)), Some(std::cmp::Ordering::Greater));
    assert_eq!(c.order(point(b.hi)), Some(std::cmp::Ordering::Less));
    assert!(boundary
        .already_past_or_consumed(2, I::point(b.lo), Some(point(b.lo)))
        .unwrap());
    assert!(!boundary
        .already_past_or_consumed(2, I::point(b.hi), Some(point(b.hi)))
        .unwrap());
    assert_eq!(
        boundary
            .already_past_or_consumed(2, b, Some(c))
            .unwrap_err()
            .kind,
        "event_resolution"
    );
}
fn check_fixed_or_leaf_never_authorizes_held_sibling() {
    let m = model();
    assert_eq!(m.triggers[1].event, m.triggers[2].event);
    let batch = [fixed(point(0.5), 0.5)];
    let boundary = TimerBoundary::new(&m, 0.5, &batch).unwrap();
    assert_eq!(
        boundary
            .already_past_or_consumed(2, I::point(0.5), Some(point(0.5)))
            .unwrap_err()
            .kind,
        "event_resolution"
    );
    let old = Clock {
        start: 0.,
        period: 0.5,
        index: 1,
    };
    let new = Clock {
        start: 0.,
        period: 0.25,
        index: 2,
    };
    let batch = [fixed(point(0.5), 0.5), held(Some(old), I::point(0.5), 0.5)];
    let boundary = TimerBoundary::new(&m, 0.5, &batch).unwrap();
    assert!(boundary
        .already_past_or_consumed(2, I::point(0.5), Some(new))
        .unwrap());
}
fn check_equal_uncertain_boxes_do_not_prove_consumed_clock_identity() {
    let m = model();
    let b = I { lo: 0.4, hi: 0.6 };
    let batch = [held(None, b, 0.6)];
    let boundary = TimerBoundary::new(&m, 0.6, &batch).unwrap();
    assert_eq!(
        boundary
            .already_past_or_consumed(2, b, None)
            .unwrap_err()
            .kind,
        "event_resolution"
    );
    assert_eq!(
        boundary
            .already_past_or_consumed(2, I::point(0.5), Some(point(0.5)))
            .unwrap_err()
            .kind,
        "event_resolution"
    );
}
fn check_mixed_moments_with_shared_representative_have_no_common_anchor() {
    let m = model();
    let c = Clock {
        start: 0.1,
        period: 0.2,
        index: 1,
    };
    let b = c.bounds().unwrap();
    let batch = [
        fixed(c, b.hi),
        held(Some(point(b.lo)), I::point(b.lo), b.hi),
    ];
    let boundary = TimerBoundary::new(&m, b.hi, &batch).unwrap();
    assert!(boundary.common_moment.is_none());
    // Candidate at upper endpoint is not proved future against whole batch.
    assert_eq!(
        boundary
            .already_past_or_consumed(2, I::point(b.hi), Some(point(b.hi)))
            .unwrap_err()
            .kind,
        "event_resolution"
    );
}
fn check_stale_or_duplicate_consumption_is_not_a_valid_batch() {
    let m = model();
    let old = held(Some(point(0.5)), I::point(0.5), 0.5);
    assert!(TimerBoundary::new(&m, 0.75, std::slice::from_ref(&old)).is_err());
    assert!(TimerBoundary::new(&m, 0.5, &[old.clone(), old]).is_err());
}

#[test]
fn exact_anchor_orders_clocks_but_does_not_consume_a_different_leaf() {
    check_exact_anchor_orders_both_sides_without_consuming_equal_new_leaf();
    check_fixed_or_leaf_never_authorizes_held_sibling();
}

#[test]
fn ambiguous_moments_do_not_prove_clock_identity_or_common_anchor() {
    check_equal_uncertain_boxes_do_not_prove_consumed_clock_identity();
    check_mixed_moments_with_shared_representative_have_no_common_anchor();
}

#[test]
fn stale_or_duplicate_consumption_cannot_authorize_rescheduling() {
    check_stale_or_duplicate_consumption_is_not_a_valid_batch();
}
