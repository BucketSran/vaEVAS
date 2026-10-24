//! Certified differential-inclusion history across an isolated source root.
//! The full root certificate is retained even when this epoch ends inside it.
use super::*;

#[derive(Clone, PartialEq)]
struct RootWindow {
    certificate: I,
    parameters: Vec<I>,
    initial: Vec<I>,
    tube: Vec<I>,
    velocity: Vec<I>,
}
#[derive(Clone, PartialEq)]
enum StepKind {
    Taylor(DenseStep),
    Root(RootWindow),
}
#[derive(Clone, PartialEq)]
pub(super) struct HistoryStep {
    pub(super) start: f64,
    pub(super) end: f64,
    kind: StepKind,
}
impl HistoryStep {
    pub(super) fn taylor(step: DenseStep) -> Self {
        Self {
            start: step.start,
            end: step.end,
            kind: StepKind::Taylor(step),
        }
    }
    pub(super) fn is_root(&self) -> bool {
        matches!(self.kind, StepKind::Root(_))
    }
    pub(super) fn root_velocity(&self) -> Option<&[I]> {
        match &self.kind {
            StepKind::Root(r) => Some(&r.velocity),
            _ => None,
        }
    }
    pub(super) fn range(&self, time: I) -> Vec<I> {
        match &self.kind {
            StepKind::Taylor(step) => step.range(time),
            StepKind::Root(root) => {
                // Every physical elapsed time is nonnegative. Outward rounding
                // may give a negative subnormal at an exact zero subtraction.
                let elapsed = time - I::point(self.start);
                let elapsed = I {
                    lo: elapsed.lo.max(0.),
                    hi: elapsed.hi,
                };
                root.initial
                    .iter()
                    .zip(&root.velocity)
                    .map(|(&x, &d)| x + elapsed * d)
                    .collect()
            }
        }
    }
    pub(super) fn centered_range(&self, h: I, tail: bool) -> Option<Vec<CenterValue>> {
        match &self.kind {
            StepKind::Taylor(s) => s.centered_range(h, tail),
            _ => None,
        }
    }
}

/// Accepted steps plus a memo of their pure range evaluations. The memo lives
/// inside the same shared allocation as the steps it describes, so a cached
/// entry can never outlive the step vector it was computed from, and step
/// contents are immutable once shared (callers only append). Entries are keyed
/// by the full bit-level query window, so a hit returns exactly the bytes the
/// direct evaluation would return; the Taylor coefficients are re-evaluated
/// on every miss and never reused across different windows.
/// Step index plus the bit-level query window `[lo, hi]` of a range request.
type RangeKey = (usize, u64, u64);

pub(super) struct StepHistory {
    steps: Vec<HistoryStep>,
    range_memo: std::sync::Mutex<std::collections::HashMap<RangeKey, std::sync::Arc<Vec<I>>>>,
}

impl Clone for StepHistory {
    fn clone(&self) -> Self {
        Self::from_steps(self.steps.clone())
    }
}

impl Default for StepHistory {
    fn default() -> Self {
        Self::from_steps(Vec::new())
    }
}

impl PartialEq for StepHistory {
    fn eq(&self, other: &Self) -> bool {
        // The memo is a transparent pure-function cache, never part of the
        // value identity compared by history-equality checks.
        self.steps == other.steps
    }
}

impl std::ops::Deref for StepHistory {
    type Target = [HistoryStep];
    fn deref(&self) -> &[HistoryStep] {
        &self.steps
    }
}

impl StepHistory {
    pub(super) fn from_steps(steps: Vec<HistoryStep>) -> Self {
        Self {
            steps,
            range_memo: std::sync::Mutex::new(std::collections::HashMap::new()),
        }
    }

    /// A copy of the steps with an empty memo, for copy-on-write histories.
    pub(super) fn cloned_steps(&self) -> Self {
        Self::from_steps(self.steps.clone())
    }

    pub(super) fn push(&mut self, step: HistoryStep) {
        self.steps.push(step);
    }

    pub(super) fn extend(&mut self, steps: impl IntoIterator<Item = HistoryStep>) {
        self.steps.extend(steps);
    }

    /// `steps[index].range(window)` with reuse for repeated identical windows.
    pub(super) fn range(&self, index: usize, window: I) -> Vec<I> {
        let key = (index, window.lo.to_bits(), window.hi.to_bits());
        if let Ok(memo) = self.range_memo.lock() {
            if let Some(hit) = memo.get(&key) {
                crate::diagnostics::counter("nonlinear_range_memo_hits", 1);
                return (**hit).clone();
            }
        }
        crate::diagnostics::counter("nonlinear_range_evaluations", 1);
        let value = std::sync::Arc::new(self.steps[index].range(window));
        if let Ok(mut memo) = self.range_memo.lock() {
            memo.insert(key, value.clone());
        }
        (*value).clone()
    }
}

pub(super) fn compatible(a: &NonlinearContinuous, b: &NonlinearContinuous, seed: &[I]) -> bool {
    a.implicit.is_none()
        && b.implicit.is_none()
        && a.initial == seed
        && b.initial == seed
        && a.parameters == b.parameters
        && a.context.driven == b.context.driven
        && a.functions.len() == seed.len()
        && b.functions.len() == seed.len()
        && a.values == b.values
        && a.accuracy_rows == b.accuracy_rows
        && a.math_outputs == b.math_outputs
        && a.operators.len() == b.operators.len()
        && a.operators.iter().zip(&b.operators).all(|(a, b)| {
            a.operator == b.operator
                && a.kind == b.kind
                && a.origin == b.origin
                && a.states == b.states
                && a.held_reset == b.held_reset
                && match (&a.laplace, &b.laplace) {
                    (None, None) => true,
                    (Some(a), Some(b)) => a.a == b.a && a.b == b.b && a.c == b.c && a.d == b.d,
                    _ => false,
                }
        })
}
impl NonlinearContinuous {
    pub(super) fn switched_enclosure(
        fields: &[&Self],
        seed: &[I],
        source: &[I],
        span: I,
        elapsed: I,
        remaining_work: &mut usize,
        work_limit: usize,
    ) -> Result<(Vec<I>, Vec<I>), Error> {
        let fail = |s| Error::new("condition_precision", s);
        if fields.is_empty() || fields.len() > 32 || elapsed.lo < 0. || !elapsed.finite() {
            return Err(fail(
                "switched enclosure requires a complete bounded field set",
            ));
        }
        let mut evaluate = |state: &[I]| -> Result<Vec<I>, Error> {
            let variables: Vec<_> = state.iter().chain(source).map(|&v| vec![v]).collect();
            let mut derivatives = Vec::new();
            for mode in fields {
                Self::charge_trial(remaining_work, span.lo, span.hi, work_limit)?;
                let rows = mode.actual_derivatives(&variables, &[])?;
                if rows.iter().any(|r| r.is_empty() || !r[0].finite()) {
                    return Err(fail("root-window field is nonfinite"));
                }
                derivatives.push(rows.into_iter().map(|r| r[0]).collect::<Vec<_>>());
            }
            let mut result = derivatives.remove(0);
            for field in derivatives {
                for (x, d) in result.iter_mut().zip(field) {
                    *x = x.hull(d);
                }
            }
            Ok(result)
        };
        let mut velocity = evaluate(seed)?;
        let mut previous = seed.to_vec();
        let mut proof = None;
        for _ in 0..TUBE_ATTEMPTS {
            let tube: Vec<_> = seed
                .iter()
                .zip(&velocity)
                .zip(&previous)
                .map(|((&x, &d), &prior)| {
                    let radius =
                        (I::point(elapsed.hi) * I::point(d.magnitude().max(1e-15)) * I::point(2.))
                            .hi;
                    let z = (x + I {
                        lo: -radius,
                        hi: radius,
                    })
                    .hull(prior);
                    I {
                        lo: z.lo.next_down(),
                        hi: z.hi.next_up(),
                    }
                })
                .collect();
            if tube.iter().any(|v| !v.finite()) {
                break;
            }
            velocity = evaluate(&tube)?;
            let image: Vec<_> = seed
                .iter()
                .zip(&velocity)
                .map(|(&x, &d)| x + elapsed * d)
                .collect();
            if image
                .iter()
                .zip(&tube)
                .all(|(x, z)| x.finite() && x.lo > z.lo && x.hi < z.hi)
            {
                proof = Some(tube);
                break;
            }
            previous = tube.iter().zip(image).map(|(&z, x)| z.hull(x)).collect();
        }
        let tube =
            proof.ok_or_else(|| fail("switched differential inclusion has no certified tube"))?;
        Ok((tube, velocity))
    }
    pub(super) fn root_window_mode(
        &self,
        root: I,
        span: I,
        seed: &[I],
        remaining_work: &mut usize,
    ) -> Result<Self, Error> {
        let fail = |s| Error::new("condition_precision", s);
        let [left, right] =
            selection::isolated_root_witnesses(&self.context, &self.parameters, root)?;
        if !root.finite()
            || root.lo >= root.hi
            || !span.finite()
            || span.lo >= span.hi
            || span.lo < root.lo
            || span.hi > root.hi
            || left < 0.
            || right > self.context.trajectory.config.stop
        {
            return Err(fail("root window lacks physical two-sided witnesses"));
        }
        let compile = |time| {
            Self::initialized(
                selection::freeze_context(&self.context, &self.parameters, time)?,
                self.parameters.clone(),
                span.lo,
                Some(seed.to_vec()),
                &self.tolerances,
            )
        };
        let mut old = compile(left)?;
        let post = compile(right)?;
        if !compatible(&old, &post, seed) {
            return Err(fail(
                "root-window modes do not share state and output coordinates",
            ));
        }
        let source = self.context.trajectory.range(span)?.0;
        // Keep the same source-domain checks as an ordinary Taylor step.
        let coordinates = |sources: Vec<I>| {
            seed.iter()
                .copied()
                .chain(sources)
                .map(|v| vec![v])
                .collect::<Vec<_>>()
        };
        let source_left = coordinates(self.context.trajectory.value_bounds(span.lo));
        let source_right = coordinates(self.context.trajectory.value_bounds(span.hi));
        let source_tube = coordinates(source.clone());
        for field in [&old, &post] {
            for f in field.functions.iter() {
                f.certify_source_denominators(
                    seed.len(),
                    &source_left,
                    &source_right,
                    &source_tube,
                )?;
            }
        }
        let elapsed = I {
            lo: 0.,
            hi: (I::point(span.hi) - I::point(span.lo)).hi,
        };
        let (tube, velocity) = Self::switched_enclosure(
            &[&old, &post],
            seed,
            &source,
            span,
            elapsed,
            remaining_work,
            self.step_budget(),
        )?;
        let variables: Vec<_> = tube.iter().chain(&source).map(|&v| vec![v]).collect();
        let mut cap = self.context.trajectory.config.max_step;
        for field in [&old, &post] {
            for (active, value) in &field.step_bounds {
                let active = active.jet(&variables, 0)[0];
                if !active.finite() {
                    return Err(fail("root-window timestep activation is not finite"));
                }
                if active.zero() {
                    continue;
                }
                let bound = value.jet(&variables, 0)[0];
                if !bound.finite() || bound.lo < 0. {
                    return Err(Error::new(
                        "invalid_bound_step",
                        "root-window timestep request is negative or nonfinite",
                    ));
                }
                cap = cap.min(bound.lo);
            }
        }
        if elapsed.hi > cap {
            return Err(Error::new(
                "waveform_accuracy",
                "root-window span exceeds the certified timestep cap",
            ));
        }
        // The interval extension is retained for every dense query, not only
        // the restart seed. Do not intersect an empty box or choose a side.
        let step = HistoryStep {
            start: span.lo,
            end: span.hi,
            kind: StepKind::Root(RootWindow {
                certificate: root,
                parameters: self.parameters.clone(),
                initial: seed.to_vec(),
                tube,
                velocity,
            }),
        };
        let endpoint = step.range(I::point(span.hi));
        if old.accuracy_ratio(
            &endpoint,
            &old.context.trajectory.value_bounds(span.hi),
            false,
        ) > 1.
        {
            return Err(Error::new(
                "waveform_accuracy",
                "root-window endpoint exceeds the unchanged voltage budget",
            ));
        }
        old.steps = Arc::new(StepHistory::from_steps(vec![step]));
        Ok(old)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn history() -> StepHistory {
        // One certified Taylor step over [0, 0.25] with a remainder.
        let step = DenseStep {
            start: 0.0,
            end: 0.25,
            coefficients: vec![vec![
                I::point(1.0),
                I::point(-0.5),
                I {
                    lo: 0.124,
                    hi: 0.126,
                },
            ]],
            remainder: vec![I { lo: 1e-6, hi: 2e-6 }],
            rounding_defect: None,
            centered: None,
        };
        StepHistory::from_steps(vec![HistoryStep::taylor(step)])
    }

    #[test]
    fn repeated_range_queries_return_the_step_evaluation_bit_for_bit() {
        let steps = history();
        let window = I {
            lo: 0.0625,
            hi: 0.1875,
        };
        let first = steps.range(0, window);
        // A repeated query hits the memo and must match both the memoized
        // value and a direct evaluation on the underlying step.
        assert_eq!(steps.range(0, window), first);
        assert_eq!(steps[0].range(window), first);
        // A different window is a different key and recomputes.
        let other = I {
            lo: 0.125,
            hi: 0.25,
        };
        assert_ne!(steps.range(0, other), first);
        assert_eq!(steps.range(0, other), steps[0].range(other));
    }

    #[test]
    fn memo_and_copy_on_write_clone_are_not_part_of_history_identity() {
        let queried = history();
        let window = I { lo: 0.0, hi: 0.25 };
        let _ = queried.range(0, window);
        assert!(queried == history());
        let copied = queried.cloned_steps();
        assert!(copied == queried);
        assert_eq!(copied.range(0, window), queried.range(0, window));
    }
}
