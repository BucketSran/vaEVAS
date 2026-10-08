//! Optional provenance for autonomous constant-flow integrals, independent of
//! interval rounding. Losing a proof removes this sidecar; it never repairs a
//! numerical seed or changes interval propagation.
use super::*;
use crate::exact_source::{binary, Budget, MAX_POINTS};
use num_rational::BigRational as R;
use num_traits::Zero;

#[derive(Clone, PartialEq)]
pub(super) struct History {
    states: Vec<(R, R)>,
    values: Vec<(R, R)>,
    start: f64,
    end: f64,
}
fn point(value: I) -> Option<R> {
    (value.lo == value.hi).then(|| binary(value.lo)).flatten()
}
fn dot(row: &[I], values: &[(R, R)], budget: &mut Budget) -> Option<(R, R)> {
    let mut result = (R::zero(), R::zero());
    for (&coefficient, (value, slope)) in row.iter().zip(values) {
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
        program: &Program,
        segments: &[Segment],
        start: f64,
        count: usize,
        seed: Option<Vec<R>>,
    ) -> Option<Self> {
        // No reset, filter, feedback or driven-source forcing is certified here.
        if program
            .operators
            .iter()
            .any(|op| !matches!(op, OperatorSpec::Idt { reset: None, .. }))
        {
            return None;
        }
        let segment = segments.first()?;
        if count > MAX_POINTS || segment.initial.len() > MAX_POINTS {
            return None;
        }
        let mut budget = Budget(0);
        let seed = seed.or_else(|| {
            segment.initial[..count]
                .iter()
                .copied()
                .map(point)
                .collect()
        })?;
        if seed.len() != count {
            return None;
        }
        let time = binary(start)?;
        let mut states = Vec::new();
        for (row, value) in segment.matrix[..count].iter().zip(seed) {
            if row[..row.len() - 1].iter().any(|c| !c.zero()) {
                return None;
            }
            let slope = point(*row.last()?)?;
            let shift = budget.check(&slope * &time)?;
            states.push((budget.check(value - shift)?, slope));
        }
        if segments
            .iter()
            .any(|s| s.matrix[..count] != segment.matrix[..count] || s.values != segment.values)
        {
            return None;
        }
        let mut forcing = states.clone();
        forcing.extend(vec![
            (R::zero(), R::zero());
            segment.initial.len() - count - 1
        ]);
        forcing.push((binary(1.)?, R::zero()));
        if segment
            .values
            .iter()
            .any(|row| row[count..row.len() - 1].iter().any(|c| !c.zero()))
        {
            return None;
        }
        let values = segment
            .values
            .iter()
            .map(|row| dot(row, &forcing, &mut budget))
            .collect::<Option<_>>()?;
        Some(Self {
            states,
            values,
            start,
            end: segments.last()?.end,
        })
    }
    pub(super) fn states_at(&self, time: f64) -> Option<Vec<R>> {
        if time < self.start || time > self.end {
            return None;
        }
        let mut budget = Budget(0);
        let time = binary(time)?;
        self.states
            .iter()
            .map(|(value, slope)| {
                let shift = budget.check(slope * &time)?;
                budget.check(value + shift)
            })
            .collect()
    }
    pub(super) fn value(&self, index: usize) -> Option<(R, R)> {
        self.values.get(index).cloned()
    }
}
