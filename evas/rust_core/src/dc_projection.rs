//! Certified rows for original Transition × exact physical DC supply products.
//! The original Program is never rewritten and keeps ownership and dependencies.
use crate::ir::{Error, Expression as E, Program};
use crate::pwl::Trajectory;
use crate::transition_source_plan::{ProofContext, Work};
use std::sync::Arc;

pub(crate) struct DcProjection {
    pub(crate) source: Arc<ProofContext>,
    entries: Vec<(E, E, usize)>,
}
impl DcProjection {
    pub(crate) fn new(p: &Program, t: &Trajectory, driven: &[String]) -> Result<Arc<Self>, Error> {
        let source = ProofContext::new(p, t, driven, Work::default())?;
        Self::with_source(p, source)
    }
    fn with_source(p: &Program, source: Arc<ProofContext>) -> Result<Arc<Self>, Error> {
        fn audit(e: &E, p: &Program, owner: &str, source: &ProofContext) -> Result<(), Error> {
            source.charge(1)?;
            let invalid = || {
                Error::new(
                    "invalid_ir",
                    "DC projection original reference/Origin must belong to its instance",
                )
            };
            match e {
                E::Affine { terms, .. } => {
                    source.charge(terms.len())?;
                    crate::expression::validate(e, p.nodes.len())?;
                }
                E::State { state } => {
                    if p.states.get(*state).is_none_or(|s| s.instance != owner) {
                        return Err(invalid());
                    }
                }
                E::Operator { operator } => {
                    if p.operators
                        .get(*operator)
                        .is_none_or(|o| o.origin().instance != owner)
                    {
                        return Err(invalid());
                    }
                }
                E::Add { left, right }
                | E::Multiply { left, right }
                | E::Divide { left, right } => {
                    audit(left, p, owner, source)?;
                    audit(right, p, owner, source)?;
                }
                E::Power { base, .. } => audit(base, p, owner, source)?,
                E::Select {
                    left,
                    right,
                    then_value,
                    else_value,
                    origin,
                    ..
                } => {
                    if origin.instance != owner
                        || origin.source.is_empty()
                        || origin.line == 0
                        || origin.column == 0
                        || !origin.valid_expansion()
                    {
                        return Err(invalid());
                    }
                    for child in [left, right, then_value, else_value] {
                        audit(child, p, owner, source)?;
                    }
                }
                _ => {
                    return Err(Error::new(
                        "unsupported_dc_projection",
                        "DC projection original history syntax is unsupported",
                    ))
                }
            }
            Ok(())
        }
        // Audit every original history arm before requesting any physical fact.
        // This walk has no dense coefficient vectors and charges each node/term.
        for op in &p.operators {
            source.charge(1)?;
            if let crate::ir::OperatorSpec::Transition { input, origin, .. } = op {
                if origin.instance.is_empty()
                    || origin.source.is_empty()
                    || origin.line == 0
                    || origin.column == 0
                    || !origin.valid_expansion()
                {
                    return Err(Error::new(
                        "invalid_ir",
                        "invalid DC projection history Origin",
                    ));
                }
                audit(input, p, &origin.instance, &source)?;
            } else {
                return Err(Error::new(
                    "unsupported_dc_projection",
                    "DC projection only supports Transition history",
                ));
            }
        }
        for c in &p.contributions {
            audit(&c.rhs, p, &c.origin.instance, &source)?;
        }
        fn nodes(e: &E, source: &ProofContext) -> Result<usize, Error> {
            source.charge(1)?;
            Ok(match e {
                E::Affine { terms, .. } => {
                    source.charge(terms.len())?;
                    1 + terms.len()
                }
                E::Add { left, right } | E::Multiply { left, right } => {
                    1 + nodes(left, source)? + nodes(right, source)?
                }
                _ => 1,
            })
        }
        fn walk(e: &E, owner: &str, source: &ProofContext) -> Result<E, Error> {
            source.charge(1)?;
            Ok(match e {
                E::Multiply { left, right } => {
                    fn supply(e: &E, source: &ProofContext) -> Result<Option<bool>, Error> {
                        source.charge(1)?;
                        Ok(match e {
                            E::Affine { terms, .. } => {
                                source.charge(terms.len())?;
                                Some(!terms.is_empty())
                            }
                            E::Add { left, right } | E::Multiply { left, right } => {
                                match (supply(left, source)?, supply(right, source)?) {
                                    (Some(a), Some(b)) => Some(a || b),
                                    _ => None,
                                }
                            }
                            _ => None,
                        })
                    }
                    let scalar = |e: &E| -> Result<E, Error> {
                        Ok(E::Affine {
                            constant: source.exact_dc_affine(e, owner)?,
                            terms: vec![],
                        })
                    };
                    if supply(left, source)? == Some(true) {
                        E::Multiply {
                            left: Box::new(scalar(left)?),
                            right: Box::new(walk(right, owner, source)?),
                        }
                    } else if supply(right, source)? == Some(true) {
                        E::Multiply {
                            left: Box::new(walk(left, owner, source)?),
                            right: Box::new(scalar(right)?),
                        }
                    } else {
                        E::Multiply {
                            left: Box::new(walk(left, owner, source)?),
                            right: Box::new(walk(right, owner, source)?),
                        }
                    }
                }
                E::Add { left, right } => E::Add {
                    left: Box::new(walk(left, owner, source)?),
                    right: Box::new(walk(right, owner, source)?),
                },
                E::Affine { terms, .. } => {
                    source.charge(terms.len())?;
                    e.clone()
                }
                E::State { .. } | E::Operator { .. } => e.clone(),
                _ => {
                    return Err(Error::new(
                        "unsupported_dc_projection",
                        "DC projection requires original sums and supply products",
                    ))
                }
            })
        }
        let mut entries = Vec::new();
        for c in &p.contributions {
            let count = nodes(&c.rhs, &source)?;
            source.charge(count)?; // retained original tree copy
            let view = walk(&c.rhs, &c.origin.instance, &source)?;
            // Existing matrix construction checks the view's joint affinity;
            // no speculative matrix pass or fallback owner is introduced here.
            entries.push((c.rhs.clone(), view, count));
        }
        Ok(Arc::new(Self { source, entries }))
    }
    pub(crate) fn view<'a>(&'a self, e: &'a E) -> Result<&'a E, Error> {
        for (original, view, count) in &self.entries {
            self.source.charge(*count)?; // every original-tree comparison
            if original == e {
                return Ok(view);
            }
        }
        Ok(e)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::interval::Interval as I;
    fn fixture(limit: u64) -> (Program, Trajectory, Arc<ProofContext>, E) {
        let p:Program=serde_json::from_value(serde_json::json!({
            "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","a","b","y"],
            "states":[{"instance":"d","name":"s","kind":"real","initial":0}],
            "operators":[{"kind":"transition","input":{"op":"select","relation":"gt","left":{"op":"state","state":0},"right":{"op":"affine","constant":0,"terms":[]},"then_value":{"op":"affine","constant":1,"terms":[]},"else_value":{"op":"affine","constant":0,"terms":[]},"origin":{"source":"dc-retry.va","line":1,"column":3,"instance":"d"}},"delay":0,"rise":0.25,"fall":0.25,
                "origin":{"source":"dc-retry.va","line":1,"column":1,"instance":"d"}}],
            "contributions":[{"branch":{"instance":"d","local_positive":"y","local_negative":"b","kind":"voltage"},
                "positive":3,"negative":2,"rhs":{"op":"multiply","left":{"op":"operator","operator":0},
                    "right":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1},{"node":2,"coefficient":-1}]}},
                "origin":{"source":"dc-retry.va","line":1,"column":2,"instance":"d"}}]
        })).unwrap();
        let t = Trajectory::new(
            crate::ir::TransientInputs {
                analytic_sources: vec![],
                pwl_errors_v: None,
                strobetimes: vec![],
                pwl: vec![vec![[0., 0.75], [2., 0.75]], vec![[0., 0.25], [2., 0.25]]],
                output_times: vec![0., 2.],
                stop: 2.,
                max_step: 1.,
            },
            2,
        )
        .unwrap();
        let source = ProofContext::new(
            &p,
            &t,
            &["a".into(), "b".into()],
            Work::limited([128, 8192, limit]),
        )
        .unwrap();
        let supply = if let E::Multiply { right, .. } = &p.contributions[0].rhs {
            *right.clone()
        } else {
            unreachable!()
        };
        (p, t, source, supply)
    }
    #[test]
    fn scalar_fact_work_is_shared_and_sticky() {
        let (_, _, source, supply) = fixture(650_000);
        assert_eq!(source.exact_dc_affine(&supply, "d").unwrap(), 0.5);
        let retry = source.clone();
        assert_eq!(
            retry.exact_dc_affine(&supply, "d").unwrap_err().kind,
            "step_budget"
        );
        assert_eq!(
            source.exact_dc_affine(&supply, "d").unwrap_err().kind,
            "step_budget"
        );
    }
    #[test]
    fn projected_source_history_rejects_trial_without_mutating_accepted_engine() {
        let (p, t, _, _) = fixture(1_000_000_000);
        let projection = DcProjection::new(&p, &t, &["a".into(), "b".into()]).unwrap();
        let mut accepted = crate::operators::Operators::new_until_with_source_context(
            &p,
            &t,
            &["a".into(), "b".into()],
            &[0.],
            2.,
            &crate::ir::Tolerances::default(),
            Some(projection.source.clone()),
        )
        .unwrap();
        accepted
            .advance(0.25, I::point(0.25), &[1.], &[I::ONE], &[0])
            .unwrap();
        let clean = accepted.clone();
        for _ in 0..2 {
            assert!(accepted
                .evaluation(0.75)
                .unwrap()
                .advanced(I::point(0.75), &[0.], &[I { lo: -1., hi: 1. }], &[0])
                .is_err());
            assert!(accepted.same_reset_history(&clean));
            assert_eq!(accepted.bounds(1.).unwrap(), clean.bounds(1.).unwrap());
        }
        let mut retry = accepted;
        let mut clean = clean;
        for h in [&mut retry, &mut clean] {
            h.advance(0.75, I::point(0.75), &[0.], &[I::ZERO], &[0])
                .unwrap();
        }
        for time in [0.75, 0.875, 1.] {
            assert_eq!(retry.bounds(time).unwrap(), clean.bounds(time).unwrap());
        }
    }
    #[test]
    fn retained_projection_comparison_uses_the_same_exhausted_owner() {
        let (p, _, source, _) = fixture(650_000);
        let projection = DcProjection::with_source(&p, source.clone()).unwrap();
        assert!(projection.view(&p.contributions[0].rhs).is_ok());
        assert_eq!(source.charge(650_000).unwrap_err().kind, "step_budget");
        assert_eq!(
            projection.view(&p.contributions[0].rhs).unwrap_err().kind,
            "step_budget"
        );
        assert_eq!(
            projection.view(&p.contributions[0].rhs).unwrap_err().kind,
            "step_budget"
        );
    }
}
