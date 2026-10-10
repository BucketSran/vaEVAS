//! Optional source provenance for local transition/filter query refinement.
//! This sidecar never supplies scheduled times, accepted voltages or state.
//! Failure loses the extra proof and leaves ordinary interval acceptance intact.
use super::{Operators, Runtime};
use crate::events::EventModel;
use crate::exact_source::{binary, Budget};
use crate::interval::Interval as I;
use crate::pwl::Trajectory;
use crate::refined_interval::Bounds as B;
use crate::schedule::ScheduledEvent;
use num_rational::BigRational as R;
use std::sync::Arc;

const LIMIT: usize = 512;
#[derive(Clone, PartialEq)]
pub(super) struct Provenance {
    states: Vec<B>,
    chains: Vec<Option<Chain>>,
}
#[derive(Clone, PartialEq)]
struct Chain {
    initial: B,
    delay: f64,
    rise: f64,
    fall: f64,
    targets: Arc<Vec<(R, B)>>,
}
fn dot(row: &[I], values: &[B]) -> Option<B> {
    if row.len() != values.len() || row.len() > LIMIT {
        return None;
    }
    row.iter()
        .zip(values)
        .try_fold(B::point(0.)?, |s, (&c, v)| {
            Some(s.add(&B::from_interval(c)?.mul(v)))
        })
}
impl Provenance {
    pub(super) fn new(
        entries: &[Runtime],
        states: &[f64],
        program: &crate::ir::Program,
    ) -> Option<Self> {
        if !entries
            .iter()
            .any(|e| matches!(e, Runtime::TransitionFilter { .. }))
            || states.len() + entries.len() > LIMIT
        {
            return None;
        }
        let states = states
            .iter()
            .copied()
            .map(B::point)
            .collect::<Option<Vec<_>>>()?;
        let values: Vec<_> = states.iter().cloned().chain([B::point(1.)?]).collect();
        let chains = entries
            .iter()
            .zip(&program.operators)
            .map(|(entry, spec)| {
                if let (
                    Runtime::Transition { input_bounds, .. },
                    crate::ir::OperatorSpec::Transition {
                        delay, rise, fall, ..
                    },
                ) = (entry, spec)
                {
                    Some(Chain {
                        initial: dot(input_bounds, &values)?,
                        delay: *delay,
                        rise: *rise,
                        fall: *fall,
                        targets: Arc::new(Vec::new()),
                    })
                } else {
                    None
                }
            })
            .collect();
        Some(Self { states, chains })
    }
    pub(super) fn updated(
        &self,
        model: &EventModel,
        trajectory: &Trajectory,
        before: &Operators,
        after: &Operators,
        batch: &[ScheduledEvent],
        ordinary_states: &[I],
    ) -> Option<Self> {
        let first = batch.first()?;
        let time = first.time;
        let window = batch.iter().fold(I::point(time), |b, e| b.hull(e.bounds()));
        let exact = first
            .rational_time()
            .filter(|r| batch.iter().all(|e| e.rational_time().as_ref() == Some(r)));
        let inputs = trajectory.range(window).ok()?.0;
        let leaves: Vec<_> = batch.iter().map(|e| e.event).collect();
        let blocks: Vec<_> = leaves
            .iter()
            .map(|&i| model.triggers[i].event)
            .collect::<std::collections::BTreeSet<_>>()
            .into_iter()
            .collect();
        let selection = model
            .conditions
            .select_at_roots(&blocks, &inputs, &leaves)
            .ok()?;
        let mut budget = Budget(0);
        let precise_inputs = inputs
            .iter()
            .enumerate()
            .map(|(i, &bound)| {
                let original = B::from_interval(bound)?;
                if let Some(value) = exact.as_ref().and_then(|t| {
                    trajectory
                        .exact_sources
                        .get(i)?
                        .as_ref()?
                        .value(t, &mut budget)
                }) {
                    original.intersection(&B::rational(value))
                } else {
                    Some(original)
                }
            })
            .collect::<Option<Vec<_>>>()?;
        let map = crate::settlement_bounds::Bounds::new(model, &selection).ok()?;
        if ordinary_states.len() != self.states.len() {
            return None;
        }
        let states = map
            .refined_states(
                &precise_inputs,
                &self.states,
                model.program.operators.len(),
                ordinary_states,
            )?
            .into_iter()
            .zip(ordinary_states)
            .map(|(v, &b)| v.intersection(&B::from_interval(b)?))
            .collect::<Option<Vec<_>>>()?;
        let values: Vec<_> = states.iter().cloned().chain([B::point(1.)?]).collect();
        let mut next = self.clone();
        for (i, chain) in next.chains.iter_mut().enumerate() {
            let (
                Runtime::Transition { history: old, .. },
                Runtime::Transition {
                    history: new,
                    input_bounds,
                    ..
                },
            ) = (&before.entries[i], &after.entries[i])
            else {
                continue;
            };
            if !new.input_changed_from(old) {
                continue;
            }
            *chain = (|| {
                let mut c = chain.clone()?;
                if c.targets.len() >= LIMIT {
                    return None;
                }
                let t = exact.clone()?;
                let value = dot(input_bounds, &values)?;
                Arc::make_mut(&mut c.targets).push((t, value));
                Some(c)
            })();
        }
        next.states = states;
        Some(next)
    }
    pub(super) fn filter(
        &self,
        parent: usize,
        time: f64,
        gain: I,
        tau: I,
        coefficient: I,
        constant: I,
    ) -> Option<B> {
        self.chains
            .get(parent)?
            .as_ref()?
            .filtered(time, gain, tau, coefficient, constant)
    }
}

struct Edge {
    start: B,
    value: B,
    origin: B,
    target: B,
    slope: B,
    end: B,
}
impl Chain {
    /// Slope-change convolution of the affine transition polygon. The same
    /// interruption rule is used as the ordinary transition contract: retain
    /// the old origin on a continued ramp, the old destination on reversal.
    fn filtered(&self, time: f64, gain: I, tau: I, coefficient: I, constant: I) -> Option<B> {
        let query = B::point(time)?;
        let tau = B::from_interval(tau)?;
        let gain = B::from_interval(gain)?;
        let coefficient = B::from_interval(coefficient)?;
        let mut output = gain.mul(
            &coefficient
                .mul(&self.initial)
                .add(&B::from_interval(constant)?),
        );
        let mut settled = self.initial.clone();
        let mut active: Option<Edge> = None;
        let mut old_slope = B::point(0.)?;
        let mut contribute = |start: &B, slope: &B| -> Option<()> {
            let h = query.sub(start);
            if h.lo < binary(0.)? {
                return None;
            }
            let g = B::point(1.)?.sub(&h.div(&tau)?.exp_negative()?);
            let weight = h.sub(&tau.mul(&g));
            output = output.add(
                &gain
                    .mul(&coefficient)
                    .mul(&slope.sub(&old_slope))
                    .mul(&weight),
            );
            old_slope = slope.clone();
            Some(())
        };
        for (source, target) in self.targets.iter() {
            let activation = B::rational(source + binary(self.delay)?);
            if activation.lo > query.hi {
                break;
            }
            if activation.hi > query.lo {
                return None;
            }
            if let Some(edge) = &active {
                if edge.end.hi <= activation.lo {
                    contribute(&edge.end, &B::point(0.)?)?;
                    settled = edge.target.clone();
                    active = None;
                } else if edge.end.lo <= activation.hi {
                    return None;
                }
            }
            let value = match &active {
                Some(edge) => edge
                    .value
                    .add(&edge.slope.mul(&activation.sub(&edge.start))),
                None => settled.clone(),
            };
            let difference = target.sub(&value);
            let direction = difference.sign()?;
            if direction == 0 {
                contribute(&activation, &B::point(0.)?)?;
                settled = target.clone();
                active = None;
                continue;
            }
            let origin = match &active {
                Some(edge) if edge.slope.sign()? == direction => edge.origin.clone(),
                Some(edge) => edge.target.clone(),
                None => value.clone(),
            };
            let duration = B::point(if direction > 0 { self.rise } else { self.fall })?;
            let slope = target.sub(&origin).div(&duration)?;
            if slope.sign() != Some(direction) {
                return None;
            }
            let remaining = difference.div(&slope)?;
            if remaining.sign() != Some(1) {
                return None;
            }
            let end = activation.add(&remaining);
            contribute(&activation, &slope)?;
            active = Some(Edge {
                start: activation,
                value,
                origin,
                target: target.clone(),
                slope,
                end,
            });
        }
        if let Some(edge) = active {
            if edge.end.hi <= query.lo {
                contribute(&edge.end, &B::point(0.)?)?;
            } else if edge.end.lo <= query.hi {
                return None;
            }
        }
        Some(output)
    }
}

#[cfg(test)]
impl Provenance {
    pub(super) fn test_states(&self) -> Vec<B> {
        self.states.clone()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use num_traits::ToPrimitive;
    fn chain(targets: &[(f64, f64)]) -> Chain {
        Chain {
            initial: B::point(0.).unwrap(),
            delay: 0.,
            rise: 8.,
            fall: 8.,
            targets: Arc::new(
                targets
                    .iter()
                    .map(|&(t, v)| (binary(t).unwrap(), B::point(v).unwrap()))
                    .collect(),
            ),
        }
    }
    #[test]
    fn target_equal_to_active_ramp_value_stops_the_ramp() {
        let c = chain(&[(2., 1.), (6., 0.5)]);
        let actual = c.filtered(10., I::ONE, I::ONE, I::ONE, I::ZERO).unwrap();
        // Integrate y'+y=(t-2)/8 on [2,6], then constant 1/2.
        let y6 = 0.375 + (-4_f64).exp() / 8.;
        let expected = 0.5 + (y6 - 0.5) * (-4_f64).exp();
        let lo = actual.lo.to_f64().unwrap();
        let hi = actual.hi.to_f64().unwrap();
        assert!((lo - expected).abs() < 1e-15 && (hi - expected).abs() < 1e-15);
        assert!(hi < 0.5);
    }
    #[test]
    fn stored_uncertainty_cannot_be_replaced_with_a_midpoint() {
        let mut c = chain(&[(2., 1.)]);
        Arc::make_mut(&mut c.targets)[0].1 = B::from_interval(I { lo: 0.99, hi: 1.01 }).unwrap();
        let actual = c.filtered(6., I::ONE, I::ONE, I::ONE, I::ZERO).unwrap();
        let center = 0.375 + (-4_f64).exp() / 8.;
        assert_eq!(actual.sub(&B::point(center).unwrap()).sign(), None);
    }
    #[test]
    fn independent_instances_keep_separate_source_histories() {
        let original = chain(&[(2., 1.)]);
        let mut candidate = original.clone();
        Arc::make_mut(&mut candidate.targets).push((binary(6.).unwrap(), B::point(0.5).unwrap()));
        let old = original
            .filtered(10., I::ONE, I::ONE, I::ONE, I::ZERO)
            .unwrap();
        let new = candidate
            .filtered(10., I::ONE, I::ONE, I::ONE, I::ZERO)
            .unwrap();
        assert!(new.hi < old.lo);
        assert_eq!(original.targets.len(), 1);
    }
}
