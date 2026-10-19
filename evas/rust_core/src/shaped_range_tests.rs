//! GUARDS: LANG, EVENT-ORDER, TIMED-OPERATOR, COMPOSE.
use super::*;
use crate::transition_source_plan::Work;
fn shaped() -> Trajectory {
    let knots: Vec<_> = (0..85)
        .map(|i| {
            serde_json::json!({
                "time_numerator": i.to_string(), "time_denominator":"1",
                "value_V": if i%2==0 { -1. } else { 1. }
            })
        })
        .collect();
    let config: TransientInputs = serde_json::from_value(serde_json::json!({
        "pwl":[[[0.,0.],[84.,0.]]],
        "pwl_errors_V":[{"voltage_error_bound_V":2., "exact_knots":knots}],
        "output_times":[0.,84.], "stop":84., "max_step":84.
    }))
    .unwrap();
    Trajectory::new(config, 1).unwrap()
}
fn bits(i: I) -> [u64; 2] {
    [i.lo.to_bits(), i.hi.to_bits()]
}
#[test]
fn staged_range_reduces_actual_endpoint_and_pair_bodies() {
    let t = shaped();
    let work = Work::default();
    let (result, report) = crate::diagnostics::capture(Default::default(), || {
        t.history_range(
            I {
                lo: 40.25,
                hi: 40.5,
            },
            &work,
        )
    });
    let (values, slopes) = result.unwrap();
    assert_eq!(bits(values[0]), bits(I { lo: -0.5, hi: 0. }));
    assert_eq!(bits(slopes[0]), bits(I::point(2.)));
    println!(
        "actual range body counters={:?}; original owner used={}",
        report.counters,
        work.spent()
    );
    assert_eq!(
        report.counters.get("strict_range_value_body").copied(),
        Some(2)
    );
    assert_eq!(
        report.counters.get("strict_range_pair_body").copied(),
        Some(1)
    );
    assert!(
        report
            .counters
            .get("shaped_range_search_compare")
            .copied()
            .unwrap_or(0)
            > 0
    );
}

#[test]
fn staged_range_fraction_multicorner_exact_knot_bits_and_subnormal_matrix() {
    let cases: serde_json::Value =
        serde_json::from_str(include_str!("../tests/fixtures/shaped-range-oracle.json")).unwrap();
    for case in cases.as_array().unwrap() {
        let stop = case["stop"].as_f64().unwrap();
        let config: TransientInputs = serde_json::from_value(serde_json::json!({
            "pwl":[[[0.,0.],[stop,0.]]],
            "pwl_errors_V":[{"voltage_error_bound_V":case["error"],"exact_knots":case["knots"]}],
            "output_times":[0.,stop],"stop":stop,"max_step":stop
        }))
        .unwrap();
        let t = Trajectory::new(config, 1).unwrap();
        for query in case["queries"].as_array().unwrap() {
            let time = I {
                lo: query["lo"].as_f64().unwrap(),
                hi: query["hi"].as_f64().unwrap(),
            };
            let old = t.exact_sources[0].as_ref().unwrap().range(time);
            let w = Work::default();
            let (r, d) =
                crate::diagnostics::capture(Default::default(), || t.history_range(time, &w));
            if query["expected"].is_null() {
                assert!(
                    old.is_none(),
                    "legacy mathematical refusal {}",
                    case["name"]
                );
                let e = r.unwrap_err();
                assert_eq!(e.kind, "event_resolution");
                continue;
            }
            let (v, s) = r.unwrap();
            let pair = old.unwrap();
            assert_eq!(
                (bits(v[0]), bits(s[0])),
                (bits(pair.0), bits(pair.1)),
                "legacy bits {}, {time:?}",
                case["name"]
            );
            let expected = &query["expected"];
            for (got, want) in [bits(v[0]), bits(s[0])]
                .into_iter()
                .zip(expected.as_array().unwrap())
            {
                assert_eq!(
                    got,
                    [want[0].as_u64().unwrap(), want[1].as_u64().unwrap()],
                    "Fraction bits {}, {time:?}",
                    case["name"]
                );
            }
            assert_eq!(
                d.counters["strict_range_pair_body"],
                query["pairs"].as_array().unwrap().len() as u64
            );
            println!(
                "Fraction case={} time={time:?} values={:?} slope={:?} actualpairs={} used={}",
                case["name"],
                bits(v[0]),
                bits(s[0]),
                d.counters["strict_range_pair_body"],
                w.spent()
            );
        }
    }
}
#[test]
fn staged_range_invalid_time_and_missing_curve_keep_rejections() {
    let mut t = shaped();
    for time in [
        I { lo: -1., hi: 0. },
        I { lo: 1., hi: 0. },
        I { lo: 0., hi: 85. },
        I::point(f64::INFINITY),
    ] {
        assert_eq!(
            t.history_range(time, &Work::default()).unwrap_err().kind,
            "event_resolution"
        );
    }
    t.exact_sources[0] = None;
    assert_eq!(
        t.history_range(I::point(1.), &Work::default())
            .unwrap_err()
            .kind,
        "event_resolution"
    );
}
#[test]
fn staged_range_natural_default_owner_exhaustion_has_zero_body_retries() {
    let t = shaped();
    let w = Work::default();
    let mut actual = 0;
    loop {
        match t.history_range(
            I {
                lo: 40.25,
                hi: 40.5,
            },
            &w,
        ) {
            Ok(_) => actual += 1,
            Err(e) => {
                assert_eq!(e.kind, "step_budget");
                break;
            }
        }
        assert!(actual < 100_000);
    }
    assert!(actual > 1);
    assert!(w.spent() > 1_000_000_000);
    println!(
        "actual shaped range calls={actual} before natural default exhaustion;used={}",
        w.spent()
    );
    let used = w.spent();
    for _ in 0..2 {
        let (r, d) =
            crate::diagnostics::capture(Default::default(), || t.history_range(I::point(40.5), &w));
        assert_eq!(r.unwrap_err().kind, "step_budget");
        assert!(d.counters.is_empty());
        assert_eq!(w.spent(), used);
    }
}

#[test]
fn staged_range_reader_capacity_and_exhaustion_before_growth() {
    for (n, want_growth) in [(2, 1), (5, 2)] {
        let one = shaped();
        let mut config = one.config.clone();
        config.pwl = vec![config.pwl[0].clone(); n];
        config.pwl_errors_v = Some(vec![config.pwl_errors_v.as_ref().unwrap()[0].clone(); n]);
        let t = Trajectory::new(config, n).unwrap();
        let (r, d) = crate::diagnostics::capture(Default::default(), || {
            t.history_range(I::point(40.5), &Work::default())
        });
        assert_eq!(r.unwrap().0.len(), n);
        assert_eq!(d.counters["history_storage_growth"], want_growth);
    }
    use crate::exact_source::history_paid::StagedRange;
    let slots = std::mem::size_of::<Option<StagedRange<'_>>>()
        .div_ceil(std::mem::size_of::<usize>()) as u64;
    let ctor =
        std::mem::size_of::<StagedRange<'_>>().div_ceil(std::mem::size_of::<usize>()) as u64 + 8;
    let t = shaped();
    // Small limit only checks this individual pre-reserve boundary. Natural
    // default exhaustion is a separate test using the unchanged 1e9 request.
    let w = Work::limited([128, 8192, 3 + ctor + 8 + 4 * slots - 1]);
    for _ in 0..3 {
        let (r, d) =
            crate::diagnostics::capture(Default::default(), || t.history_range(I::point(40.5), &w));
        assert_eq!(r.unwrap_err().kind, "step_budget");
        assert!(
            d.counters.is_empty(),
            "no reserve, endpoint or rational helper may run: {:?}",
            d.counters
        );
    }
}

#[test]
fn staged_range_unshaped_none_route_keeps_exact_original_cost_and_values() {
    let mut spends = Vec::new();
    for error in [None, Some(0.0), Some(0.01)] {
        let mut config: TransientInputs = serde_json::from_value(serde_json::json!({
            "pwl":[[[0.,0.],[1.,1.]]],"output_times":[0.,1.],"stop":1.,"max_step":1.
        }))
        .unwrap();
        config.pwl_errors_v = error.map(|e| vec![crate::ir::SourceError::Voltage(e)]);
        let t = Trajectory::new(config, 1).unwrap();
        let time = I { lo: 0.25, hi: 0.5 };
        let w = Work::default();
        let got = t.history_range(time, &w).unwrap();
        assert_eq!(got, t.range(time).unwrap());
        println!(
            "unshaped original error={error:?}, actual owner spend={}",
            w.spent()
        );
        spends.push(w.spent());
    }
    assert_eq!(spends, [18, 18, 18]);
}

#[test]
fn staged_range_incomplete_or_repeated_phases_cannot_publish_a_certificate() {
    use crate::exact_source::history_paid::StagedRange;
    let t = shaped();
    let c = t.exact_sources[0].as_ref().unwrap();
    let w = Work::default();
    let time = I {
        lo: 40.25,
        hi: 40.5,
    };
    assert!(StagedRange::new(c, time, &w)
        .unwrap()
        .finish()
        .unwrap()
        .is_none());
    assert!(StagedRange::new(c, time, &w)
        .unwrap()
        .endpoint(true)
        .unwrap()
        .is_none());
    let (left, _) = StagedRange::new(c, time, &w)
        .unwrap()
        .endpoint(false)
        .unwrap()
        .unwrap();
    assert!(left.endpoint(false).unwrap().is_none());
    let (left, _) = StagedRange::new(c, time, &w)
        .unwrap()
        .endpoint(false)
        .unwrap()
        .unwrap();
    let (right, _) = left.endpoint(true).unwrap().unwrap();
    assert!(right.finish().unwrap().is_some());
}
