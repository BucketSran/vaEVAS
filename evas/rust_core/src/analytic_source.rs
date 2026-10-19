//! Finite explicit analytic voltage source values, using the request's ledger.
use crate::interval::Interval as I;
use crate::ir::{AnalyticSource, Error, TransientInputs};
use crate::transition_source_plan::Work;
use std::io::Write;

fn invalid(s: &str) -> Error {
    Error::new("invalid_inputs", s)
}
struct Charge<'a>(&'a Work);
impl Write for Charge<'_> {
    fn write(&mut self, b: &[u8]) -> std::io::Result<usize> {
        // Prepaid byte scan and the following source/config clone's storage.
        self.0
            .debit(2, (b.len() as u64).saturating_mul(8))
            .map_err(|e| std::io::Error::other(e.message))?;
        Ok(b.len())
    }
    fn flush(&mut self) -> std::io::Result<()> {
        Ok(())
    }
}
pub(crate) fn charge_config<T: serde::Serialize + ?Sized>(
    config: &T,
    w: &Work,
) -> Result<(), Error> {
    w.debit(2, 32)?;
    serde_json::to_writer(Charge(w), config).map_err(|e| Error::new("step_budget", e.to_string()))
}
pub(crate) fn validate_config(config: &TransientInputs, w: Option<&Work>) -> Result<(), Error> {
    if config.analytic_sources.is_empty() {
        return Ok(());
    }
    let w = w.ok_or_else(|| invalid("analytic sources require original request work"))?;
    w.debit(2, config.pwl.len().saturating_mul(8) as u64)?;
    if config.analytic_sources.len() != config.pwl.len() {
        return Err(invalid("analytic_sources must match driven source order"));
    }
    for (k, entry) in config.analytic_sources.iter().enumerate() {
        if let Some(source) = entry {
            if !config.pwl[k].is_empty()
                || config.pwl_errors_v.as_ref().is_some_and(|e| {
                    e.get(k)
                        .is_none_or(|x| x.bound() != 0. || x.shape().is_some())
                })
            {
                return Err(invalid("each input must have exactly one physical provider and no analytic PWL error/shape"));
            }
            match source {
                AnalyticSource::Sine {
                    sinedc,
                    ampl,
                    freq,
                    sinephase,
                    source_name,
                    terminals,
                    polarity,
                    parameter_origin,
                } => {
                    w.debit(
                        2,
                        (source_name.len()
                            + terminals[0].len()
                            + terminals[1].len()
                            + parameter_origin.len()
                            + 32) as u64,
                    )?;
                    if ![sinedc, ampl, freq, sinephase]
                        .iter()
                        .all(|x| x.is_finite())
                        || source_name.is_empty()
                        || terminals.iter().any(String::is_empty)
                        || terminals[0] == terminals[1]
                        || *parameter_origin != "explicit-v1"
                        || *polarity
                            != if terminals[1] == "0" || !terminals.contains(&"0".into()) {
                                1
                            } else {
                                -1
                            }
                    {
                        return Err(invalid("invalid explicit sine descriptor"));
                    }
                    if *freq <= 0. {
                        return Err(Error::new(
                            "unsupported_analytic_source",
                            "finite positive sine frequency is the current implementation scope",
                        ));
                    }
                    // Validate the entire request, never just its observed endpoints.
                    range(
                        source,
                        I {
                            lo: 0.,
                            hi: config.stop,
                        },
                        w,
                    )?;
                }
            }
        }
    }
    Ok(())
}
/// Pure interval arithmetic constructs phase before any range reduction.
/// The existing sine implementation is bounded to |phase| <=128. Its two
/// endpoint reductions and extrema scan have fewer than 4096 scalar interval
/// operations. Reserve 8192 before either value or derivative certificate.
pub(crate) fn range(source: &AnalyticSource, time: I, w: &Work) -> Result<(I, I), Error> {
    w.debit(2, 16_384)?;
    if !time.finite() || time.lo > time.hi {
        return Err(invalid("invalid analytic source time interval"));
    }
    match source {
        AnalyticSource::Sine {
            sinedc,
            ampl,
            freq,
            sinephase,
            polarity,
            ..
        } => {
            let pi = I {
                lo: f64::from_bits(0x4009_21fb_5444_2d17),
                hi: f64::from_bits(0x4009_21fb_5444_2d19),
            };
            let omega = I::point(2.) * pi * I::point(*freq);
            let phase = omega * time + pi * (I::point(*sinephase) / I::point(180.));
            let value = (I::point(*sinedc)
                + I::point(*ampl) * crate::operators::sin_bounds(phase)?)
                * I::point(*polarity as f64);
            let derivative = I::point(*ampl)
                * omega
                * crate::operators::sin_bounds(phase + pi / I::point(2.))?
                * I::point(*polarity as f64);
            if !value.finite() || !derivative.finite() {
                return Err(Error::new(
                    "waveform_accuracy",
                    "nonfinite analytic source certificate",
                ));
            }
            Ok((value, derivative))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn sine() -> AnalyticSource {
        serde_json::from_value(serde_json::json!({"kind":"sine","sinedc":0.5,"ampl":0.25,"freq":1.,"sinephase":0.,"source_name":"V","terminals":["x","0"],"polarity":1,"parameter_origin":"explicit-v1"})).unwrap()
    }
    #[test]
    fn irrational_value_and_derivative_are_enclosed_not_chords() {
        let w = Work::default();
        let (v, d) = range(&sine(), I::point(0.125), &w).unwrap();
        // Independent sqrt(2) rational enclosure: 14142135623730950/1e16
        // < sqrt(2) < 14142135623730951/1e16; output .5+sqrt(2)/8.
        assert!(v.lo < 0.6767766952966369 && v.hi > 0.6767766952966368);
        assert!(v.hi - v.lo < 1e-12 && v.lo > 0.67);
        assert!(d.lo < 1.110720734539592 && d.hi > 1.110720734539591);
    }
    #[test]
    fn same_owner_natural_depletion_is_sticky_for_two_retries() {
        let w = Work::limited([128, 8192, 16_384 * 2]);
        let retry = w.clone();
        range(&sine(), I::point(0.), &w).unwrap();
        range(&sine(), I::point(0.125), &w).unwrap();
        for _ in 0..2 {
            assert_eq!(
                range(&sine(), I::point(0.2), &retry).unwrap_err().kind,
                "step_budget"
            );
        }
        assert!(w.spent() > 16_384 * 2);
    }
}

#[cfg(test)]
mod transport_tests {
    use super::*;
    use crate::pwl::Trajectory;
    fn request() -> crate::ir::Request {
        serde_json::from_str(include_str!("../tests/analytic_source_request.json")).unwrap()
    }
    #[test]
    fn typed_descriptor_binding_rejects_every_parameter_and_hidden_dependency_change() {
        let r = request();
        let w = Work::default();
        let t = Trajectory::new_with_work(r.transient.unwrap(), 1, Some(w.clone())).unwrap();
        charge_config(&r.program, &w).unwrap();
        let n = crate::event_floor::encoded_size(&r.program, &w).unwrap();
        let c = crate::transition_source_plan::ProofContext::event_request_with_work(
            &r.program,
            &t,
            &r.driven,
            n,
            w.clone(),
        )
        .unwrap();
        assert!(w.same_owner(c.borrow_work()));
        assert!(w.same_owner(t.analytic_work().unwrap()));
        let cloned = t.clone();
        assert!(w.same_owner(cloned.analytic_work().unwrap()));
        crate::event_floor::check_provided_binding(&c, &r.program, &t, &r.driven).unwrap();
        for field in [
            "freq",
            "ampl",
            "sinedc",
            "sinephase",
            "source_name",
            "parameter_origin",
            "polarity",
        ] {
            let mut wire = serde_json::to_value(&t.config).unwrap();
            let d = &mut wire["analytic_sources"][0];
            d[field] = match field {
                "source_name" => serde_json::json!("changed"),
                "parameter_origin" => serde_json::json!("unknown"),
                "polarity" => serde_json::json!(-1),
                _ => serde_json::json!(7.0),
            };
            let mut changed = t.clone();
            changed.config = serde_json::from_value(wire).unwrap();
            assert_eq!(
                crate::event_floor::check_provided_binding(&c, &r.program, &changed, &r.driven)
                    .unwrap_err()
                    .kind,
                "invalid_ir",
                "{field}"
            );
        }
        let mut changed = r.program.clone();
        // Even an unselected hidden dependency changes the original binding.
        changed.nodes.push("unknown_hidden_arm".into());
        assert_eq!(
            crate::event_floor::check_provided_binding(&c, &changed, &t, &r.driven)
                .unwrap_err()
                .kind,
            "invalid_ir"
        );
    }
    #[test]
    fn typed_provider_range_is_index_aligned_and_not_a_pwl_chord() {
        let r = request();
        let w = Work::default();
        let t = Trajectory::new_with_work(r.transient.unwrap(), 1, Some(w.clone())).unwrap();
        let (v, d) = t
            .history_range(
                I {
                    lo: 0.125,
                    hi: 0.375,
                },
                &w,
            )
            .unwrap();
        assert_eq!(v.len(), 1);
        assert_eq!(d.len(), 1);
        assert!(v[0].hi >= 0.75 && v[0].lo > 0.67);
        assert!(t.exact_sources[0].is_none());
        assert_eq!(t.config.pwl[0].len(), 0);
    }
}

/// Bind the original grounded terminals to the ordered driven-input names.
pub(crate) fn validate_names(
    config: &TransientInputs,
    driven: &[String],
    w: &Work,
) -> Result<(), Error> {
    if config.analytic_sources.len() != driven.len() {
        return Err(invalid(
            "analytic provider count must match ordered driven names",
        ));
    }
    for (k, entry) in config.analytic_sources.iter().enumerate() {
        w.step()?;
        if let Some(AnalyticSource::Sine {
            source_name,
            terminals,
            ..
        }) = entry
        {
            let node = if terminals[1] == "0" {
                &terminals[0]
            } else if terminals[0] == "0" {
                &terminals[1]
            } else {
                return Err(Error::new(
                    "unsupported_analytic_source_consumer",
                    "floating analytic source values require a separate topology certificate",
                ));
            };
            w.debit(2, (node.len() + driven[k].len() + 2) as u64)?;
            if node != &driven[k] {
                return Err(invalid(
                    "analytic source terminals do not match ordered driven input",
                ));
            }
            for previous in &config.analytic_sources[..k] {
                w.step()?;
                if let Some(AnalyticSource::Sine {
                    source_name: other, ..
                }) = previous
                {
                    w.debit(2, (source_name.len() + other.len() + 2) as u64)?;
                    if source_name == other {
                        return Err(invalid("duplicate original analytic source identity"));
                    }
                }
            }
        }
    }
    Ok(())
}
