use super::*;
use serde_json::json;

fn fixture(dynamic: bool, ordered: bool) -> EventModel {
    let origin = json!({"source":"cache.va","line":1,"column":1,"instance":"dut"});
    let rhs = if dynamic {
        json!({"op":"multiply","left":{"op":"state","state":0},"right":{"op":"operator","operator":0}})
    } else {
        json!({"op":"add","left":{"op":"multiply","left":{"op":"affine","constant":0.5,"terms":[]},"right":{"op":"state","state":0}},"right":{"op":"operator","operator":0}})
    };
    let body = if ordered {
        json!([
            {"kind":"assign","state":0,"rhs":{"op":"affine","constant":0,"terms":[{"node":2,"coefficient":1}]}},
            {"kind":"assign","state":0,"rhs":{"op":"add","left":{"op":"state","state":0},"right":{"op":"affine","constant":1,"terms":[]}}}
        ])
    } else {
        json!([])
    };
    let p: Program = serde_json::from_value(json!({
        "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","u","y"],
        "states":[{"instance":"dut","name":"q","kind":"real","initial":2}],
        "events":[{"origin":origin,"trigger":{"kind":"timer","start":0.5,"period":0,"enabled":true,"time_tolerance":0.001},"body":body}],
        "contributions":[{"origin":origin,"branch":{"instance":"dut","local_positive":"out","local_negative":"ref","kind":"voltage"},"positive":2,"negative":0,"rhs":rhs}],
        "operators":[{"kind":"transition","input":{"op":"affine","constant":1,"terms":[]},"delay":0,"rise":1,"fall":1,"origin":origin}]
    })).unwrap();
    EventModel::new(p, vec!["u".into()], Tolerances::default()).unwrap()
}

fn bits(values: &[I]) -> Vec<(u64, u64)> {
    values
        .iter()
        .map(|v| (v.lo.to_bits(), v.hi.to_bits()))
        .collect()
}

#[test]
fn live_samples_cached_and_old_certificates_match_bit_for_bit() {
    let model = fixture(false, false);
    let selection = Selection::default();
    let (result, report) = crate::diagnostics::capture(Default::default(), || {
        for (lo, hi) in [(0.25, 0.25), (0.5 - 1e-12, 0.5 + 1e-12), (0.75, 0.75)] {
            let operators = [I { lo, hi }];
            let before = [I::point(2.)];
            let voltages = [0., 0., 1. + (lo + hi) * 0.5];
            let old =
                Bounds::for_program_with_operators(&model, &selection, &model.program, &operators)?;
            let expected =
                old.check_observation(&model, &[I::ZERO], &before, &operators, &voltages, &[2.])?;
            let actual = model.certify_observation_at_roots(
                &selection,
                &[],
                &[I::ZERO],
                &before,
                &operators,
                &voltages,
                &[2.],
            )?;
            assert_eq!(bits(&actual.0), bits(&expected.0));
            assert_eq!(bits(&actual.1), bits(&expected.1));
            let states = model.certify_event_states(
                &selection,
                &[],
                &[I::ZERO],
                &before,
                &operators,
                &voltages,
                &[2.],
            )?;
            assert_eq!(bits(&states), bits(&expected.0));
        }
        Ok(())
    });
    result.unwrap();
    // Three explicit old builds plus one cache build; all later checks reuse it.
    assert_eq!(report.counters["certificate_bounds_builds"], 4);
    assert_eq!(report.counters["certificate_cache_hits"], 5);
    // A later, much wider enclosure must still fail; no nominal sample is frozen.
    let operators = [I { lo: 0.4, hi: 0.6 }];
    let old =
        Bounds::for_program_with_operators(&model, &selection, &model.program, &operators).unwrap();
    let expected = old
        .check_observation(
            &model,
            &[I::ZERO],
            &[I::point(2.)],
            &operators,
            &[0., 0., 1.5],
            &[2.],
        )
        .err()
        .unwrap();
    let actual = model
        .certify_observation_at_roots(
            &selection,
            &[],
            &[I::ZERO],
            &[I::point(2.)],
            &operators,
            &[0., 0., 1.5],
            &[2.],
        )
        .err()
        .unwrap();
    assert_eq!(actual.kind, expected.kind);
    assert_eq!(actual.message, expected.message);
}

#[test]
fn ordered_feedback_selection_changes_the_cache_key() {
    let model = fixture(false, true);
    let empty = Selection::default();
    model
        .certify_observation_at_roots(
            &empty,
            &[],
            &[I::ZERO],
            &[I::ZERO],
            &[I::point(0.5)],
            &[0., 0., 0.5],
            &[0.],
        )
        .unwrap();
    let selection = model.conditions.select(&[0], &[I::ZERO]).unwrap();
    assert_eq!(selection.actions, vec![(0, vec![0, 1])]);
    let operators = [I::point(0.5)];
    let old =
        Bounds::for_program_with_operators(&model, &selection, &model.program, &operators).unwrap();
    let expected = old
        .check_observation(
            &model,
            &[I::ZERO],
            &[I::ZERO],
            &operators,
            &[0., 0., 2.],
            &[3.],
        )
        .unwrap();
    let actual = model
        .certify_observation_at_roots(
            &selection,
            &[],
            &[I::ZERO],
            &[I::ZERO],
            &operators,
            &[0., 0., 2.],
            &[3.],
        )
        .unwrap();
    assert_eq!(bits(&actual.0), bits(&expected.0));
    assert_eq!(bits(&actual.1), bits(&expected.1));
    assert!(model
        .certificate
        .borrow()
        .as_ref()
        .is_some_and(|(s, _)| s == &selection));
}

#[test]
fn sampled_product_is_not_cached_even_if_hidden_by_exact_zero() {
    let model = fixture(true, false);
    let selection = Selection::default();
    assert!(!Bounds::sample_independent(&model, &selection).unwrap());
    let (result, report) = crate::diagnostics::capture(Default::default(), || {
        for sample in [0.25, 0.75] {
            model.certify_observation_at_roots(
                &selection,
                &[],
                &[I::ZERO],
                &[I::point(2.)],
                &[I::point(sample)],
                &[0., 0., 2. * sample],
                &[2.],
            )?;
        }
        Ok(())
    });
    result.unwrap();
    assert_eq!(report.counters["certificate_bounds_builds"], 2);
    assert!(!report.counters.contains_key("certificate_cache_hits"));
    assert!(model.certificate.borrow().is_none());
    let mut hidden = model.program.clone();
    hidden.contributions[0].rhs = Expression::Multiply {
        left: Box::new(Expression::Affine {
            constant: 0.,
            terms: vec![],
        }),
        right: Box::new(hidden.contributions[0].rhs.clone()),
    };
    // Probe the original expression tree, without eliminating zero references.
    let model = EventModel::new(hidden, vec!["u".into()], Tolerances::default()).unwrap();
    assert!(!Bounds::sample_independent(&model, &selection).unwrap());
}

#[test]
fn branch_review_cache_distinguishes_ambiguous_equivalent_and_proved_no_selections() {
    let o = json!({"source":"branch_cache.va","line":1,"column":1,"instance":"D"});
    let c = |v: f64| json!({"op":"affine","constant":v,"terms":[]});
    let assign = json!([{"kind":"assign","state":0,"rhs":c(1.)}]);
    let p=serde_json::from_value(json!({"schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","u","y"],"states":[{"instance":"D","name":"q","kind":"real","initial":0}],"operators":[],"events":[{"origin":o,"trigger":{"kind":"timer","start":0.5,"period":0,"enabled":true,"time_tolerance":1e-9},"body":[{"kind":"if","relation":"ge","left":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]},"right":c(0.),"then_body":assign,"else_body":assign,"origin":o}]}],"contributions":[{"origin":o,"branch":{"instance":"D","local_positive":"out","local_negative":"ref","kind":"voltage"},"positive":2,"negative":0,"rhs":{"op":"state","state":0}}]})).unwrap();
    let model = EventModel::new(p, vec!["u".into()], Tolerances::default()).unwrap();
    let wide = I {
        lo: -1e-14,
        hi: 1e-14,
    };
    let ambiguous = model.conditions.select(&[0], &[wide]).unwrap();
    let no = model.conditions.select(&[0], &[I::point(-0.5)]).unwrap();
    assert_ne!(ambiguous.actions, no.actions);
    assert_ne!(ambiguous.decisions, no.decisions);
    assert_eq!(ambiguous.decisions, vec![(0, true), (0, false)]);
    for (selection, input, sample) in [
        (&ambiguous, wide, 0.),
        (&no, I::point(-0.5), -0.5),
        (&ambiguous, wide, 0.),
    ] {
        let old =
            Bounds::for_program_with_operators(&model, selection, &model.program, &[]).unwrap();
        let expected = old
            .check_observation(&model, &[input], &[I::ZERO], &[], &[0., sample, 1.], &[1.])
            .unwrap();
        let actual = model
            .certify_observation_at_roots(
                selection,
                &[],
                &[input],
                &[I::ZERO],
                &[],
                &[0., sample, 1.],
                &[1.],
            )
            .unwrap();
        assert_eq!(bits(&actual.0), bits(&expected.0));
        assert_eq!(bits(&actual.1), bits(&expected.1));
        assert!(model
            .certificate
            .borrow()
            .as_ref()
            .is_some_and(|(s, _)| s == selection));
        assert!(model
            .certify_observation_at_roots(
                selection,
                &[],
                &[input],
                &[I::ZERO],
                &[],
                &[0., sample, 0.],
                &[0.]
            )
            .is_err());
        assert!(model
            .certify_observation_at_roots(
                selection,
                &[],
                &[input],
                &[I::ZERO],
                &[],
                &[0., sample, 1.],
                &[1.]
            )
            .is_ok());
    }
}
