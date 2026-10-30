use super::*;
use serde_json::json;

#[test]
fn procedure_observation_uses_captured_value_and_rejects_forged_voltage() {
    // Compiled from procedure_observation.va: the contribution sees c before
    // its later overwrite. Reusing the final binding would incorrectly give 0.
    let p: Program =
        serde_json::from_str(include_str!("procedure_observation_request.json")).unwrap();
    let model = EventModel::new(p, vec!["u".into()], Tolerances::default()).unwrap();
    for (input, expected) in [(0.25, 1.), (-0.25, 0.), (0.25, 1.)] {
        let inputs = [I::point(input)];
        let selection = model
            .observation_selection(&inputs, &[], &[], &[], &[])
            .unwrap();
        let good = [0., input, expected];
        let certificate = || model.certify_observation(&selection, &inputs, &[], &[], &good, &[]);
        let (_, bounds) = certificate().unwrap();
        assert!(bounds[2].lo <= expected && expected <= bounds[2].hi);
        let bad = [0., input, 1. - expected];
        assert_eq!(
            model
                .certify_observation(&selection, &inputs, &[], &[], &bad, &[])
                .unwrap_err()
                .kind,
            "waveform_accuracy"
        );
        // Rejected observations do not poison the captured source frame.
        certificate().unwrap();
    }
}

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

fn assert_certificate_bits(
    actual: Result<(Vec<I>, Vec<I>), Error>,
    expected: Result<(Vec<I>, Vec<I>), Error>,
) {
    match (actual, expected) {
        (Ok(actual), Ok(expected)) => {
            assert_eq!(bits(&actual.0), bits(&expected.0));
            assert_eq!(bits(&actual.1), bits(&expected.1));
        }
        (Err(actual), Err(expected)) => {
            assert_eq!(actual.kind, expected.kind);
            assert_eq!(actual.message, expected.message);
        }
        _ => panic!("cached and freshly built certificates disagree"),
    }
}

#[test]
fn sampled_binding_cache_uses_interval_bits_and_rechecks_failed_trials() {
    let model = fixture(true, false);
    let selection = Selection::default();
    let before = [I::point(2.)];
    let initial_map =
        Bounds::for_program_with_operators(&model, &selection, &model.program, &[I::point(0.25)])
            .unwrap();
    assert!(!initial_map.matches_operator_bindings(&[]));
    let cases = [
        (I::point(0.25), 0.5),
        (I::point(0.25), 0.5),
        (I { lo: 0.24, hi: 0.26 }, 0.5),
        (I { lo: 0.24, hi: 0.26 }, 0.5),
        (I::point(0.25), 0.5),
        (I::point(-0.), -0.),
        (I::ZERO, 0.),
        (I::point(f64::INFINITY), 0.),
        (I::point(0.25), 0.5),
    ];
    let expected: Vec<_> = cases
        .iter()
        .map(|&(operator, value)| {
            Bounds::for_program_with_operators(&model, &selection, &model.program, &[operator])
                .and_then(|bounds| {
                    bounds.check_observation(
                        &model,
                        &[I::ZERO],
                        &before,
                        &[operator],
                        &[0., 0., value],
                        &[2.],
                    )
                })
        })
        .collect();
    assert!(expected[2].is_err());
    assert!(expected[3].is_err());
    assert!(expected[7].is_err());
    let (result, report) = crate::diagnostics::capture(Default::default(), || {
        for (&(operator, value), expected) in cases.iter().zip(expected) {
            assert_certificate_bits(
                model.certify_observation_at_roots(
                    &selection,
                    &[],
                    &[I::ZERO],
                    &before,
                    &[operator],
                    &[0., 0., value],
                    &[2.],
                ),
                expected,
            );
            if !operator.finite() {
                assert!(model
                    .certificate
                    .borrow()
                    .as_ref()
                    .is_some_and(|(path, bounds)| {
                        path.same_path(&selection, crate::real_expression::work(&model)).unwrap()
                            && bounds.matches_operator_bindings(&[I::ZERO])
                    }));
            }
        }
        let states = model.certify_event_states(
            &selection,
            &[],
            &[I::ZERO],
            &before,
            &[I::point(0.25)],
            &[0., 0., 0.5],
            &[2.],
        )?;
        assert_eq!(bits(&states), bits(&before));
        Ok(())
    });
    result.unwrap();
    assert_eq!(report.counters["certificate_bounds_builds"], 7);
    assert_eq!(
        report
            .counters
            .get("certificate_cache_hits")
            .copied()
            .unwrap_or(0),
        3
    );
}

#[test]
fn sampled_binding_cache_keeps_linear_operator_forcing_live() {
    for same_rhs in [false, true] {
        let base = fixture(true, false);
        let mut program = base.program.clone();
        program.operators.push(program.operators[0].clone());
        let mut linear = program.contributions[0].clone();
        linear.rhs = Expression::Operator { operator: 1 };
        if same_rhs {
            program.contributions[0].rhs = Expression::Add {
                left: Box::new(program.contributions[0].rhs.clone()),
                right: Box::new(linear.rhs),
            };
        } else {
            program.contributions.push(linear);
        }
        let model = EventModel::new(program, base.driven, base.tolerances).unwrap();
        let selection = Selection::default();
        let before = [I::point(2.)];
        let cases = [
            (I::point(0.5), 1.),
            (I::point(0.75), 1.25),
            (I { lo: 0.4, hi: 0.6 }, 1.),
        ];
        let expected: Vec<_> = cases
            .iter()
            .map(|&(linear, value)| {
                let operators = [I::point(0.25), linear];
                Bounds::for_program_with_operators(&model, &selection, &model.program, &operators)
                    .and_then(|bounds| {
                        bounds.check_observation(
                            &model,
                            &[I::ZERO],
                            &before,
                            &operators,
                            &[0., 0., value],
                            &[2.],
                        )
                    })
            })
            .collect();
        assert!(expected[2].is_err());
        let (result, report) = crate::diagnostics::capture(Default::default(), || {
            for (&(linear, value), expected) in cases.iter().zip(expected) {
                assert_certificate_bits(
                    model.certify_observation_at_roots(
                        &selection,
                        &[],
                        &[I::ZERO],
                        &before,
                        &[I::point(0.25), linear],
                        &[0., 0., value],
                        &[2.],
                    ),
                    expected,
                );
            }
            Ok(())
        });
        result.unwrap();
        // The fallback binds every Operator it reads in one failed-affine RHS.
        // A separate affine RHS instead keeps operator1 as live forcing.
        assert_eq!(
            report.counters["certificate_bounds_builds"],
            if same_rhs { 3 } else { 1 }
        );
        assert_eq!(
            report
                .counters
                .get("certificate_cache_hits")
                .copied()
                .unwrap_or(0),
            if same_rhs { 0 } else { 2 }
        );
    }
}

#[test]
fn resolved_graph_bypasses_binding_cache() {
    let base = fixture(false, false);
    let mut program = base.program.clone();
    let original = program.contributions[0].rhs.clone();
    program.contributions[0].rhs = Expression::Select {
        relation: crate::ir::Relation::Gt,
        left: Box::new(Expression::Affine {
            constant: 0.,
            terms: vec![Term {
                node: 1,
                coefficient: 1.,
            }],
        }),
        right: Box::new(Expression::Affine {
            constant: 0.,
            terms: vec![],
        }),
        then_value: Box::new(original),
        else_value: Box::new(Expression::State { state: 0 }),
        origin: program.contributions[0].origin.clone(),
    };
    let model = EventModel::new(program, base.driven, base.tolerances).unwrap();
    let selection = Selection::default();
    let (result, report) = crate::diagnostics::capture(Default::default(), || {
        for _ in 0..2 {
            model.certify_observation_at_roots(
                &selection,
                &[],
                &[I::ONE],
                &[I::point(2.)],
                &[I::point(0.25)],
                &[0., 1., 1.25],
                &[2.],
            )?;
        }
        Ok(())
    });
    result.unwrap();
    assert_eq!(report.counters["certificate_bounds_builds"], 2);
    assert!(!report.counters.contains_key("certificate_cache_hits"));
    assert!(model.certificate.borrow().is_none());
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
        .is_some_and(|(s, _)| s.same_path(&selection, crate::real_expression::work(&model)).unwrap()));
}

#[test]
fn sampled_binding_cache_tracks_hidden_zero_coefficients() {
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
    assert!(model.certificate.borrow().is_some());
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
    let (result, report) = crate::diagnostics::capture(Default::default(), || {
        for sample in [0.25, 0.75, 0.75] {
            model.certify_observation_at_roots(
                &selection,
                &[],
                &[I::ZERO],
                &[I::point(2.)],
                &[I::point(sample)],
                &[0., 0., 0.],
                &[2.],
            )?;
        }
        Ok(())
    });
    result.unwrap();
    assert_eq!(report.counters["certificate_bounds_builds"], 2);
    assert_eq!(
        report
            .counters
            .get("certificate_cache_hits")
            .copied()
            .unwrap_or(0),
        1
    );
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
            .is_some_and(|(s, _)| s.same_path(selection, crate::real_expression::work(&model)).unwrap()));
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

#[test]
fn direct_circuit_program_matches_clone_clear_with_borrowed_and_owned_selection() {
    for dynamic in [false, true] {
        for selected in [false, true] {
            let base = fixture(dynamic, false);
            let mut program = base.program.clone();
            let origin = program.contributions[0].origin.clone();
            program.step_bounds.push(crate::ir::StepBound {
                value: Expression::Affine {
                    constant: 0.125,
                    terms: vec![],
                },
                active: Expression::Affine {
                    constant: 1.,
                    terms: vec![],
                },
                origin: origin.clone(),
            });
            if selected {
                program.contributions[0].rhs = Expression::Select {
                    relation: crate::ir::Relation::Gt,
                    left: Box::new(Expression::Affine {
                        constant: 0.,
                        terms: vec![Term {
                            node: 1,
                            coefficient: 1.,
                        }],
                    }),
                    right: Box::new(Expression::Affine {
                        constant: 0.5,
                        terms: vec![],
                    }),
                    then_value: Box::new(Expression::State { state: 0 }),
                    else_value: Box::new(Expression::Multiply {
                        left: Box::new(Expression::Affine {
                            constant: -1.,
                            terms: vec![],
                        }),
                        right: Box::new(Expression::State { state: 0 }),
                    }),
                    origin,
                };
            }
            let model = EventModel::new(program, base.driven, base.tolerances).unwrap();
            for input in [0., 1.] {
                let states = [2.];
                let operators = [0.25];
                let inputs = [I::point(input)];
                let selection = model
                    .selected_program_at_roots(&[I::point(2.)], &inputs, &[])
                    .unwrap();
                assert_eq!(matches!(selection, std::borrow::Cow::Owned(_)), selected);
                let mut old = model.selected_program(&[I::point(2.)], &inputs).unwrap();
                let rhs = old
                    .contributions
                    .iter()
                    .map(|c| {
                        affine(
                            &freeze_operators(&c.rhs, &operators),
                            &old,
                            &c.origin.instance,
                        )
                    })
                    .collect::<Result<Vec<_>, _>>()
                    .unwrap();
                old.states.clear();
                old.events.clear();
                old.operators.clear();
                for (c, rhs) in old.contributions.iter_mut().zip(&rhs) {
                    c.rhs = rhs.bind(&states, &operators).unwrap();
                }
                let actual = model
                    .bound_circuit_program_at(&states, &operators, &inputs)
                    .unwrap();
                assert_eq!(
                    serde_json::to_value(&actual).unwrap(),
                    serde_json::to_value(&old).unwrap()
                );
                let old_solution = Circuit::new(old, &model.driven, model.tolerances.clone())
                    .unwrap()
                    .solve(&[input])
                    .unwrap();
                let actual_solution = model
                    .circuit_at(&states, &operators, &inputs)
                    .unwrap()
                    .solve(&[input])
                    .unwrap();
                assert_eq!(
                    serde_json::to_value(&actual_solution).unwrap(),
                    serde_json::to_value(&old_solution).unwrap()
                );
            }
        }
    }
}
