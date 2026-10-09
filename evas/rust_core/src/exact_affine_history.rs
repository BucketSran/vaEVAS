//! Optional provenance for autonomous constant-flow integrals, independent of
//! interval rounding. Losing a proof removes this sidecar; it never repairs a
//! numerical seed or changes interval propagation.
use super::*;
use crate::exact_source::{binary, Budget, MAX_POINTS};
use num_rational::BigRational as R;
use num_traits::Zero;

#[derive(Clone, PartialEq)]
pub(super) struct History {
    states: Vec<Option<(R, R)>>,
    values: Vec<Option<(R, R)>>,
    start: f64,
    end: f64,
}
fn point(value: I) -> Option<R> {
    (value.lo == value.hi).then(|| binary(value.lo)).flatten()
}
fn dot(row: &[I], values: &[Option<(R, R)>], budget: &mut Budget) -> Option<(R, R)> {
    let mut result = (R::zero(), R::zero());
    for (&coefficient, value) in row.iter().zip(values) {
        if coefficient.zero() {
            continue;
        }
        let (value, slope) = value.as_ref()?;
        let coefficient = point(coefficient)?;
        let term = budget.check(&coefficient * value)?;
        result.0 = budget.check(result.0 + term)?;
        let term = budget.check(&coefficient * slope)?;
        result.1 = budget.check(result.1 + term)?;
    }
    Some(result)
}
impl History {
    pub(super) fn build(
        eligible: &[bool],
        segments: &[Segment],
        start: f64,
        count: usize,
        seed: Option<Vec<Option<R>>>,
    ) -> Option<Self> {
        // Each reset-free integral can carry its own constant-flow proof.
        // Unrelated filters and unproved states keep interval propagation.
        let segment = segments.first()?;
        if eligible.len() != count || count > MAX_POINTS || segment.initial.len() > MAX_POINTS {
            return None;
        }
        let mut budget = Budget(0);
        let seed = seed.unwrap_or_else(|| {
            segment.initial[..count]
                .iter()
                .copied()
                .map(point)
                .collect::<Vec<_>>()
        });
        if seed.len() != count {
            return None;
        }
        let time = binary(start)?;
        let mut states = Vec::new();
        for (index, (row, value)) in segment.matrix[..count].iter().zip(seed).enumerate() {
            let proof = (|| {
                if !eligible[index]
                    || row[..row.len() - 1].iter().any(|c| !c.zero())
                    || segments.iter().any(|s| s.matrix[index] != *row)
                {
                    return None;
                }
                let slope = point(*row.last()?)?;
                let shift = budget.check(&slope * &time)?;
                Some((budget.check(value? - shift)?, slope))
            })();
            states.push(proof);
        }
        if states.iter().all(Option::is_none) {
            return None;
        }
        let mut forcing = states.clone();
        forcing.extend(vec![None; segment.initial.len() - count - 1]);
        forcing.push(Some((binary(1.)?, R::zero())));
        let values = segment
            .values
            .iter()
            .enumerate()
            .map(|(index, row)| {
                if segments.iter().any(|s| s.values[index] != *row) {
                    None
                } else {
                    dot(row, &forcing, &mut budget)
                }
            })
            .collect();
        Some(Self {
            states,
            values,
            start,
            end: segments.last()?.end,
        })
    }
    pub(super) fn states_at(&self, time: f64) -> Option<Vec<Option<R>>> {
        if time < self.start || time > self.end {
            return None;
        }
        let mut budget = Budget(0);
        let time = binary(time)?;
        Some(
            self.states
                .iter()
                .map(|state| {
                    state.as_ref().and_then(|(value, slope)| {
                        let shift = budget.check(slope * &time)?;
                        budget.check(value + shift)
                    })
                })
                .collect::<Vec<_>>(),
        )
    }
    pub(super) fn value(&self, index: usize) -> Option<(R, R)> {
        self.values.get(index)?.clone()
    }
}
