//! Fixed-delay transition history. Observation queries never mutate an edge.
use crate::interval::Interval as I;
use crate::ir::Error;
use std::collections::VecDeque;

#[derive(Clone, Debug, PartialEq)]
pub(crate) struct Deadline {
    continuous_end: bool,
    pub(crate) bounds: I,
    // Exact symbolic sum when available; equal enclosures alone do not prove
    // coincident real deadlines. Interrupted-edge endpoints have no sum key.
    sum: Option<[f64; 3]>,
    exact: Option<crate::exact_source::RootTime>,
}
impl Deadline {
    pub(crate) fn independent_end_checkpoints(&self, other: &Self) -> bool {
        self.continuous_end
            && other.continuous_end
            && self.exact_time().is_some()
            && other.exact_time().is_some()
    }
    pub(crate) fn serial_representatives(&self, other: &Self) -> bool {
        let strictly_after = |later: &Self, earlier: f64| {
            later
                .exact_time()
                .zip(crate::exact_source::RootTime::point(earlier))
                .is_some_and(|(a, b)| a.order(&b) == std::cmp::Ordering::Greater)
        };
        (self.bounds.hi < other.bounds.hi && strictly_after(other, self.bounds.hi))
            || (other.bounds.hi < self.bounds.hi && strictly_after(self, other.bounds.hi))
    }
    fn exact_time(&self) -> Option<crate::exact_source::RootTime> {
        let root = self
            .exact
            .clone()
            .or_else(|| {
                let terms = self.sum?;
                let mut root = crate::exact_source::RootTime::point(terms[0])?;
                for term in &terms[1..] {
                    root = root.shifted_fixed(*term, root.bounds()? + I::point(*term))?;
                }
                Some(root)
            })
            .or_else(|| {
                (self.bounds.lo == self.bounds.hi)
                    .then(|| crate::exact_source::RootTime::point(self.bounds.lo))
                    .flatten()
            })?;
        root.refine(self.bounds)?;
        Some(root)
    }
    pub(crate) fn history_exact_time(
        &self,
        w: &crate::transition_source_plan::Work,
    ) -> Result<Option<crate::exact_source::RootTime>, Error> {
        use crate::exact_source::history_paid::{root, Paid};
        let mut p = Paid::new(w);
        let result = (|| {
            p.pay(1)?;
            let value = if let Some(exact) = &self.exact {
                p.copy(exact.rational())?
            } else if let Some(terms) = self.sum {
                let mut v = p.binary(terms[0])?;
                for term in &terms[1..] {
                    let t = p.binary(*term)?;
                    v = p.op(&v, &t, '+')?
                }
                v
            } else if self.bounds.lo == self.bounds.hi {
                p.binary(self.bounds.lo)?
            } else {
                return None;
            };
            let lo = p.binary(self.bounds.lo)?;
            let hi = p.binary(self.bounds.hi)?;
            if p.cmp(&lo, &value)?.is_gt() || p.cmp(&value, &hi)?.is_gt() {
                return None;
            }
            Some(root(value))
        })();
        p.finish(result)
    }
    pub(crate) fn history_accounted_event(
        &self,
        event: I,
        root: Option<&crate::exact_source::RootTime>,
        w: &crate::transition_source_plan::Work,
    ) -> Result<bool, Error> {
        use crate::exact_source::history_paid::Paid;
        w.step()?;
        if event.lo == event.hi && event == self.bounds {
            return Ok(true);
        }
        let Some(exact) = self.history_exact_time(w)? else {
            return Ok(false);
        };
        if let Some(root) = root {
            if exact.order_with_work(root, w)? == std::cmp::Ordering::Equal {
                return Ok(true);
            }
        }
        let mut p = Paid::new(w);
        let value = (|| {
            let lo = p.binary(event.lo)?;
            let hi = p.binary(event.hi)?;
            Some(p.cmp(exact.rational(), &lo)?.is_lt() || p.cmp(exact.rational(), &hi)?.is_gt())
        })();
        Ok(p.finish(value)?.unwrap_or(false))
    }
    pub(crate) fn history_pair_ordered(
        &self,
        other: &Self,
        w: &crate::transition_source_plan::Work,
    ) -> Result<bool, Error> {
        use crate::exact_source::history_paid::Paid;
        w.debit(2, 8)?;
        if self.bounds.lo == self.bounds.hi && self.bounds == other.bounds {
            return Ok(true);
        }
        if self.sum.is_some() && self.sum == other.sum {
            return Ok(true);
        }
        let a = self.history_exact_time(w)?;
        let b = other.history_exact_time(w)?;
        if let (Some(a), Some(b)) = (&a, &b) {
            if a.order_with_work(b, w)? == std::cmp::Ordering::Equal {
                return Ok(true);
            }
            if self.continuous_end && other.continuous_end {
                return Ok(true);
            }
        }
        let mut p = Paid::new(w);
        let result = (|| {
            if self.bounds.hi < other.bounds.hi {
                let point = p.binary(self.bounds.hi)?;
                return Some(p.cmp(b.as_ref()?.rational(), &point)?.is_gt());
            }
            if other.bounds.hi < self.bounds.hi {
                let point = p.binary(other.bounds.hi)?;
                return Some(p.cmp(a.as_ref()?.rational(), &point)?.is_gt());
            }
            Some(false)
        })();
        Ok(p.finish(result)?.unwrap_or(false))
    }
    pub(crate) fn strictly_ordered_with(&self, event: I) -> bool {
        let proof = self
            .exact
            .clone()
            .or_else(|| {
                let terms = self.sum?;
                let mut root = crate::exact_source::RootTime::point(terms[0])?;
                for term in &terms[1..] {
                    root = root.shifted_fixed(*term, root.bounds()? + I::point(*term))?;
                }
                Some(root)
            })
            .or_else(|| {
                (self.bounds.lo == self.bounds.hi)
                    .then(|| crate::exact_source::RootTime::point(self.bounds.lo))
                    .flatten()
            });
        proof
            .filter(|r| r.refine(self.bounds).is_some())
            .is_some_and(|r| {
                crate::exact_source::RootTime::point(event.lo)
                    .is_some_and(|lo| r.order(&lo) == std::cmp::Ordering::Less)
                    || crate::exact_source::RootTime::point(event.hi)
                        .is_some_and(|hi| r.order(&hi) == std::cmp::Ordering::Greater)
            })
    }
    pub(crate) fn coincides(&self, other: &Self) -> bool {
        (self.bounds.lo == self.bounds.hi && self.bounds == other.bounds)
            || (self.sum.is_some() && self.sum == other.sum)
            || self
                .exact
                .as_ref()
                .zip(other.exact.as_ref())
                .is_some_and(|(a, b)| a.order(b) == std::cmp::Ordering::Equal)
    }
    pub(crate) fn coincides_root(&self, root: &crate::exact_source::RootTime) -> bool {
        let exact = self
            .exact
            .clone()
            .or_else(|| {
                let terms = self.sum?;
                let mut root = crate::exact_source::RootTime::point(terms[0])?;
                for term in &terms[1..] {
                    root = root.shifted_fixed(*term, root.bounds()? + I::point(*term))?;
                }
                root.refine(self.bounds)?;
                Some(root)
            })
            .or_else(|| {
                (self.bounds.lo == self.bounds.hi)
                    .then(|| crate::exact_source::RootTime::point(self.bounds.lo))
                    .flatten()
            });
        exact.is_some_and(|exact| {
            exact.refine(self.bounds).is_some() && exact.order(root) == std::cmp::Ordering::Equal
        })
    }
    pub(crate) fn overlaps(&self, other: I) -> bool {
        self.bounds.lo <= other.hi && other.lo <= self.bounds.hi
    }
    pub(crate) fn ordered_with_point(&self, event: I) -> bool {
        if event.lo != event.hi || !event.finite() {
            return false;
        }
        let proof = || {
            let exact = self
                .sum?
                .into_iter()
                .try_fold(crate::exact_source::binary(0.)?, |sum, term| {
                    Some(sum + crate::exact_source::binary(term)?)
                })?;
            if crate::exact_source::enclosure(&exact)? != self.bounds {
                return None;
            }
            Some(match exact.cmp(&crate::exact_source::binary(event.lo)?) {
                std::cmp::Ordering::Less => self.bounds.hi <= event.lo,
                std::cmp::Ordering::Equal => self.bounds == event,
                std::cmp::Ordering::Greater => self.bounds.hi > event.hi,
            })
        };
        proof().unwrap_or(false)
    }
    /// Root identity plus a usable history representative. In particular an
    /// interrupted edge can have an exact end even without a symbolic sum.
    pub(crate) fn ordered_with_root(&self, root: &crate::exact_source::RootTime) -> bool {
        if !self.continuous_end {
            return false;
        }
        let Some(end) = self.exact_time() else {
            return false;
        };
        let Some(bounds) = root.bounds() else {
            return false;
        };
        match end.order(root) {
            std::cmp::Ordering::Less => bounds.lo == bounds.hi || self.bounds.hi <= bounds.lo,
            std::cmp::Ordering::Greater => crate::exact_source::RootTime::point(bounds.hi)
                .is_some_and(|point| end.order(&point) == std::cmp::Ordering::Greater),
            std::cmp::Ordering::Equal => false,
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
struct Edge {
    exact_line: Option<(num_rational::BigRational, num_rational::BigRational)>,
    exact_start: Option<crate::exact_source::RootTime>,
    prior_slope: I,
    start: f64,
    start_bounds: I,
    value: f64,
    value_bounds: I,
    origin: f64,
    origin_bounds: I,
    exact_origin: Option<num_rational::BigRational>,
    target: f64,
    target_bounds: I,
    exact_target: Option<num_rational::BigRational>,
    slope: f64,
    slope_bounds: I,
    end: Deadline,
    // A settled symmetric retarget has a fixed duration even when old and
    // new level boxes overlap. It does not claim a single signed slope.
    symmetric_blend: Option<f64>,
}

#[derive(Clone, Debug, PartialEq)]
pub(crate) struct Transition {
    delay: f64,
    rise: f64,
    fall: f64,
    input: f64,
    input_bounds: I,
    input_revision: u64,
    settled: f64,
    settled_bounds: I,
    exact_settled: Option<num_rational::BigRational>,
    edge: Option<Edge>,
    pending: VecDeque<(Deadline, f64, I, Option<num_rational::BigRational>)>,
}

fn invalid(message: &str) -> Error {
    Error::new("event_resolution", message)
}

fn deadline(bounds: I, scale: f64, sum: Option<[f64; 3]>) -> Result<Deadline, Error> {
    // Supported-slice time-resolution gate: representative-at-upper-bound
    // displacement must be <= 1% of the declared delay/edge time. This is not
    // a total waveform error bound and does not authorize uncertain ordering.
    let error = I::point(bounds.hi) - bounds;
    let budget = I::point(scale) * I::point(0.01);
    if !bounds.finite() || !error.finite() || error.magnitude() > budget.lo {
        return Err(invalid(
            "transition time resolution exceeds 1% of declared timing",
        ));
    }
    let sum = sum.map(|mut terms| {
        terms.sort_by(f64::total_cmp);
        terms
    });
    Ok(Deadline {
        continuous_end: false,
        bounds,
        sum,
        exact: None,
    })
}

// Optional value provenance augments, but never replaces, inherited bounds.
// A genuinely uncertain box has no exact value without an original certificate.
fn exact_level(
    bounds: I,
    proof: Option<&num_rational::BigRational>,
) -> Option<num_rational::BigRational> {
    use crate::exact_source::{binary, enclosure, Budget};
    proof
        .and_then(|v| Budget(0).check(v.clone()))
        .filter(|v| enclosure(v).is_some_and(|i| bounds.lo <= i.lo && i.hi <= bounds.hi))
        .or_else(|| {
            (bounds.lo == bounds.hi)
                .then(|| binary(bounds.lo))
                .flatten()
        })
}

impl Transition {
    pub(crate) fn charge_forcing_copy(
        &self,
        c: &crate::transition_source_plan::ProofContext,
    ) -> Result<(), Error> {
        fn rational(
            c: &crate::transition_source_plan::ProofContext,
            r: &num_rational::BigRational,
        ) -> Result<(), Error> {
            c.source_charge(
                "forcing_history_limbs",
                4 + (r.numer().bits().div_ceil(64) + r.denom().bits().div_ceil(64)) as usize,
            )
        }
        fn deadline(
            c: &crate::transition_source_plan::ProofContext,
            d: &Deadline,
        ) -> Result<(), Error> {
            c.source_charge("forcing_deadline_copy", 16)?;
            if let Some(r) = &d.exact {
                rational(c, r.rational())?;
            }
            Ok(())
        }
        c.source_charge("forcing_history_queue_copy", 64 + self.pending.len() * 32)?;
        if let Some(r) = &self.exact_settled {
            rational(c, r)?;
        }
        if let Some(e) = &self.edge {
            c.source_charge("forcing_history_edge_copy", 64)?;
            if let Some((a, b)) = &e.exact_line {
                rational(c, a)?;
                rational(c, b)?;
            }
            if let Some(r) = &e.exact_start {
                rational(c, r.rational())?;
            }
            for r in [&e.exact_origin, &e.exact_target].into_iter().flatten() {
                rational(c, r)?;
            }
            deadline(c, &e.end)?;
        }
        for (d, _, _, r) in &self.pending {
            deadline(c, d)?;
            if let Some(r) = r {
                rational(c, r)?;
            }
        }
        Ok(())
    }
    // Copy accounting only; the existing history/transition algorithm is unchanged.
    /// Exact structural equality for history replay; no Rational payload is copied.
    pub(crate) fn same_history_paid(
        &self,
        other: &Self,
        w: &crate::transition_source_plan::Work,
    ) -> Result<bool, Error> {
        use crate::event_value_proof::history::same_rat;
        type R = num_rational::BigRational;
        fn rational(
            a: Option<&R>,
            b: Option<&R>,
            w: &crate::transition_source_plan::Work,
        ) -> Result<bool, Error> {
            w.debit(2, 0)?;
            w.step()?;
            match (a, b) {
                (Some(a), Some(b)) => same_rat(a, b, w),
                (None, None) => Ok(true),
                _ => Ok(false),
            }
        }
        fn deadline(
            a: &Deadline,
            b: &Deadline,
            w: &crate::transition_source_plan::Work,
        ) -> Result<bool, Error> {
            w.debit(2, 8)?;
            Ok(a.continuous_end == b.continuous_end
                && a.bounds == b.bounds
                && a.sum == b.sum
                && rational(
                    a.exact.as_ref().map(|r| r.rational()),
                    b.exact.as_ref().map(|r| r.rational()),
                    w,
                )?)
        }
        w.debit(2, 0)?;
        w.debit(2, 16)?;
        if self.delay != other.delay
            || self.rise != other.rise
            || self.fall != other.fall
            || self.input != other.input
            || self.input_bounds != other.input_bounds
            || self.input_revision != other.input_revision
            || self.settled != other.settled
            || self.settled_bounds != other.settled_bounds
        {
            return Ok(false);
        }
        if !rational(self.exact_settled.as_ref(), other.exact_settled.as_ref(), w)? {
            return Ok(false);
        }
        w.step()?;
        match (&self.edge, &other.edge) {
            (Some(a), Some(b)) => {
                w.step()?;
                match (&a.exact_line, &b.exact_line) {
                    (Some((a, b)), Some((c, d))) => {
                        if !same_rat(a, c, w)? || !same_rat(b, d, w)? {
                            return Ok(false);
                        }
                    }
                    (None, None) => (),
                    _ => return Ok(false),
                }
                if !rational(
                    a.exact_start.as_ref().map(|r| r.rational()),
                    b.exact_start.as_ref().map(|r| r.rational()),
                    w,
                )? {
                    return Ok(false);
                }
                w.debit(2, 32)?;
                if a.prior_slope != b.prior_slope
                    || a.start != b.start
                    || a.start_bounds != b.start_bounds
                    || a.value != b.value
                    || a.value_bounds != b.value_bounds
                    || a.origin != b.origin
                    || a.origin_bounds != b.origin_bounds
                    || a.target != b.target
                    || a.target_bounds != b.target_bounds
                    || a.slope != b.slope
                    || a.slope_bounds != b.slope_bounds
                    || a.symmetric_blend != b.symmetric_blend
                {
                    return Ok(false);
                }
                if !rational(a.exact_origin.as_ref(), b.exact_origin.as_ref(), w)?
                    || !rational(a.exact_target.as_ref(), b.exact_target.as_ref(), w)?
                    || !deadline(&a.end, &b.end, w)?
                {
                    return Ok(false);
                }
            }
            (None, None) => (),
            _ => return Ok(false),
        }
        w.step()?;
        if self.pending.len() != other.pending.len() {
            return Ok(false);
        }
        for ((a, av, ab, ar), (b, bv, bb, br)) in self.pending.iter().zip(&other.pending) {
            w.debit(2, 4)?;
            if av != bv
                || ab != bb
                || !deadline(a, b, w)?
                || !rational(ar.as_ref(), br.as_ref(), w)?
            {
                return Ok(false);
            }
        }
        Ok(true)
    }
    pub(crate) fn charge_held_copy(
        &self,
        charge: &impl Fn(usize) -> Result<(), Error>,
    ) -> Result<(), Error> {
        fn rational(r: &num_rational::BigRational) -> usize {
            4 + ((r.numer().bits() + r.denom().bits()) as usize).div_ceil(8)
        }
        fn deadline(d: &Deadline) -> usize {
            12 + d.exact.as_ref().map_or(0, |r| r.copy_items())
        }
        charge(16 + self.exact_settled.as_ref().map_or(0, rational))?;
        if let Some(e) = &self.edge {
            charge(
                40 + e
                    .exact_line
                    .as_ref()
                    .map_or(0, |(a, b)| rational(a) + rational(b))
                    + e.exact_start.as_ref().map_or(0, |r| r.copy_items())
                    + e.exact_origin.as_ref().map_or(0, rational)
                    + e.exact_target.as_ref().map_or(0, rational)
                    + deadline(&e.end),
            )?;
        }
        for (d, _, _, r) in &self.pending {
            charge(4 + deadline(d) + r.as_ref().map_or(0, rational))?;
        }
        Ok(())
    }

    fn exact_at(&self, time: &crate::exact_source::RootTime) -> Option<num_rational::BigRational> {
        use crate::exact_source::Budget;
        if self.pending.front().is_some_and(|(d, _, _, _)| {
            d.exact_time()
                .is_none_or(|t| t.order(time) != std::cmp::Ordering::Greater)
        }) {
            return None;
        }
        if let Some(edge) = &self.edge {
            if time.order(&edge.end.exact_time()?) != std::cmp::Ordering::Less {
                return edge.exact_target.clone();
            }
            if time.order(edge.exact_start.as_ref()?) == std::cmp::Ordering::Less {
                return None;
            }
            let (a, b) = edge.exact_line.as_ref()?;
            let mut budget = Budget(0);
            let product = budget.check(b * time.rational())?;
            return budget.check(a + product);
        }
        self.exact_settled.clone()
    }

    fn history_exact_at(
        &self,
        time: &crate::exact_source::RootTime,
        w: &crate::transition_source_plan::Work,
    ) -> Result<Option<num_rational::BigRational>, Error> {
        use crate::exact_source::history_paid::Paid;
        let mut p = Paid::new(w);
        let result = (|| {
            p.pay(1)?;
            if let Some((d, _, _, _)) = self.pending.front() {
                let t = p.accept(d.history_exact_time(w))??;
                if !p.cmp(t.rational(), time.rational())?.is_gt() {
                    return None;
                }
            }
            if let Some(edge) = &self.edge {
                let end = p.accept(edge.end.history_exact_time(w))??;
                if !p.cmp(time.rational(), end.rational())?.is_lt() {
                    return p.copy(edge.exact_target.as_ref()?);
                }
                if p.cmp(time.rational(), edge.exact_start.as_ref()?.rational())?
                    .is_lt()
                {
                    return None;
                }
                let (a, b) = edge.exact_line.as_ref()?;
                let product = p.op(b, time.rational(), '*')?;
                return p.op(a, &product, '+');
            }
            p.copy(self.exact_settled.as_ref()?)
        })();
        p.finish(result)
    }
    fn history_exact_point(
        &self,
        time: f64,
        w: &crate::transition_source_plan::Work,
    ) -> Result<Option<(f64, I)>, Error> {
        use crate::exact_source::history_paid::{root, Paid};
        let mut p = Paid::new(w);
        let result = (|| {
            let time = root(p.binary(time)?);
            let value = p.accept(self.history_exact_at(&time, w))??;
            let bounds = p.enclose(&value)?;
            let nearest = p.nearest(&value)?;
            (bounds.lo <= nearest && nearest <= bounds.hi).then_some((nearest, bounds))
        })();
        p.finish(result)
    }
    pub(crate) fn exact_affine_on(
        &self,
        bounds: I,
    ) -> Option<(num_rational::BigRational, num_rational::BigRational)> {
        use crate::exact_source::{binary, RootTime};
        if self
            .pending
            .front()
            .is_some_and(|(d, _, _, _)| d.bounds.lo <= bounds.hi)
        {
            return None;
        }
        if let Some(edge) = &self.edge {
            let lo = RootTime::point(bounds.lo)?;
            let hi = RootTime::point(bounds.hi)?;
            let end = edge.end.exact_time()?;
            if lo.order(&end) != std::cmp::Ordering::Less {
                return Some((edge.exact_target.clone()?, binary(0.)?));
            }
            if lo.order(edge.exact_start.as_ref()?) == std::cmp::Ordering::Less
                || hi.order(&end) == std::cmp::Ordering::Greater
            {
                return None;
            }
            return edge.exact_line.clone();
        }
        Some((self.exact_settled.clone()?, binary(0.)?))
    }
    pub(crate) fn history_exact_affine_on(
        &self,
        bounds: I,
        w: &crate::transition_source_plan::Work,
    ) -> Result<Option<(num_rational::BigRational, num_rational::BigRational)>, Error> {
        use crate::exact_source::history_paid::Paid;
        let mut p = Paid::new(w);
        let result = (|| {
            p.pay(1)?;
            if self
                .pending
                .front()
                .is_some_and(|(d, _, _, _)| d.bounds.lo <= bounds.hi)
            {
                return None;
            }
            if let Some(edge) = &self.edge {
                let lo = p.binary(bounds.lo)?;
                let hi = p.binary(bounds.hi)?;
                let end = p.accept(edge.end.history_exact_time(w))??;
                if !p.cmp(&lo, end.rational())?.is_lt() {
                    return Some((p.copy(edge.exact_target.as_ref()?)?, p.binary(0.)?));
                }
                if p.cmp(&lo, edge.exact_start.as_ref()?.rational())?.is_lt()
                    || p.cmp(&hi, end.rational())?.is_gt()
                {
                    return None;
                }
                let (a, b) = edge.exact_line.as_ref()?;
                return Some((p.copy(a)?, p.copy(b)?));
            }
            Some((p.copy(self.exact_settled.as_ref()?)?, p.binary(0.)?))
        })();
        p.finish(result)
    }
    /// A budget for one future edge is valid only before any active or queued
    /// edge. Return the retained plateau, never a point replacement for it.
    pub(crate) fn idle_level(&self) -> Option<(f64, I, f64)> {
        (self.edge.is_none() && self.pending.is_empty()).then_some((
            self.settled,
            self.settled_bounds,
            self.rise.min(self.fall),
        ))
    }

    pub(crate) fn input_changed_from(&self, old: &Self) -> bool {
        self.input_revision != old.input_revision
    }

    /// Advance a private prediction through queued targets, without changing
    /// the accepted input. Consumers must clone before calling this method.
    pub(crate) fn advance_time(&mut self, time: f64) -> Result<(), Error> {
        self.advance_enclosed(time, self.input, self.input_bounds, false)
    }

    pub(crate) fn history_advance_time(
        &mut self,
        time: f64,
        w: &crate::transition_source_plan::Work,
    ) -> Result<(), Error> {
        w.step()?;
        if !time.is_finite() {
            return Err(invalid("invalid transition event-time enclosure"));
        }
        loop {
            w.step()?;
            if !self
                .pending
                .front()
                .is_some_and(|(deadline, _, _, _)| deadline.bounds.hi <= time)
            {
                break;
            }
            let (deadline, target, bounds, exact) = self.pending.pop_front().unwrap();
            self.history_target(deadline, target, bounds, exact, w)?;
        }
        if self
            .edge
            .as_ref()
            .is_some_and(|edge| edge.end.bounds.hi <= time)
        {
            let edge = self.edge.take().unwrap();
            self.settled = edge.target;
            self.settled_bounds = edge.target_bounds;
            self.exact_settled = edge.exact_target;
        }
        Ok(())
    }

    /// Partition forcing at both sides of uncertain activation/end boxes.
    pub(crate) fn forcing_boundary(&self, after: f64) -> Option<f64> {
        self.deadlines(after)
            .iter()
            .flat_map(|d| [d.bounds.lo, d.bounds.hi])
            .filter(|&t| t > after)
            .min_by(f64::total_cmp)
    }

    pub(crate) fn forcing_uncertain(&self, time: f64) -> bool {
        self.deadlines(time)
            .iter()
            .any(|d| d.bounds.lo <= time && time < d.bounds.hi)
    }

    /// A conservative range also covering delayed activations. Used only for
    /// integration over uncertainty boxes, not to localize cross events.
    pub(crate) fn forcing_range(&self, time: I) -> I {
        let mut result = self.bounds_at(time);
        for (deadline, _, target, _) in &self.pending {
            if deadline.bounds.lo <= time.hi {
                result = result.hull(*target);
            }
        }
        result
    }

    /// Affine forcing before the next deadline's lower bound. The caller
    /// partitions uncertainty boxes separately, so clipping is not smoothed.
    pub(crate) fn forcing_line(&self, time: f64) -> (I, I) {
        match &self.edge {
            Some(edge) if time < edge.end.bounds.lo => (
                edge.value_bounds + edge.slope_bounds * (I::point(time) - edge.start_bounds),
                edge.slope_bounds,
            ),
            Some(edge) => (edge.target_bounds, I::ZERO),
            None => (self.settled_bounds, I::ZERO),
        }
    }
    #[cfg(test)]
    pub(crate) fn new(initial: f64, delay: f64, rise: f64, fall: f64) -> Result<Self, Error> {
        Self::enclosed(initial, I::point(initial), delay, rise, fall)
    }

    pub(crate) fn enclosed(
        initial: f64,
        bounds: I,
        delay: f64,
        rise: f64,
        fall: f64,
    ) -> Result<Self, Error> {
        if ![initial, delay, rise, fall].iter().all(|v| v.is_finite())
            || !bounds.finite()
            || delay < 0.0
            || rise <= 0.0
            || fall <= 0.0
        {
            return Err(Error::new(
                "invalid_ir",
                "invalid transition initial value or timing",
            ));
        }
        Ok(Self {
            delay,
            rise,
            fall,
            input: initial,
            input_bounds: bounds,
            input_revision: 0,
            settled: initial,
            settled_bounds: bounds,
            exact_settled: exact_level(bounds, None),
            edge: None,
            pending: VecDeque::new(),
        })
    }

    pub(crate) fn history_enclosed(
        initial: f64,
        bounds: I,
        delay: f64,
        rise: f64,
        fall: f64,
        w: &crate::transition_source_plan::Work,
    ) -> Result<Self, Error> {
        w.debit(2, 16)?;
        if ![initial, delay, rise, fall].iter().all(|v| v.is_finite())
            || !bounds.finite()
            || delay < 0.0
            || rise <= 0.0
            || fall <= 0.0
        {
            return Err(Error::new(
                "invalid_ir",
                "invalid transition initial value or timing",
            ));
        }
        let mut p = crate::exact_source::history_paid::Paid::new(w);
        let value = if bounds.lo == bounds.hi {
            p.binary(bounds.lo)
        } else {
            None
        };
        let exact = p.finish(value)?;
        Ok(Self {
            delay,
            rise,
            fall,
            input: initial,
            input_bounds: bounds,
            input_revision: 0,
            settled: initial,
            settled_bounds: bounds,
            exact_settled: exact,
            edge: None,
            pending: VecDeque::new(),
        })
    }

    pub(crate) fn history_value(
        &self,
        time: f64,
        w: &crate::transition_source_plan::Work,
    ) -> Result<f64, Error> {
        if !time.is_finite() {
            return Err(invalid("nonfinite transition observation time"));
        }
        if let Some((value, _)) = self.history_exact_point(time, w)? {
            return Ok(value);
        }
        w.debit(2, 16)?;
        let value = match &self.edge {
            Some(edge) if time < edge.end.bounds.hi => {
                let raw = edge.value + edge.slope * (time - edge.start);
                if !raw.is_finite() {
                    return Err(invalid("nonfinite transition value"));
                }
                raw.clamp(edge.value.min(edge.target), edge.value.max(edge.target))
            }
            Some(edge) => edge.target,
            None => self.settled,
        };
        if !value.is_finite() {
            return Err(invalid("nonfinite transition value"));
        }
        Ok(value)
    }
    pub(crate) fn history_value_bounds(
        &self,
        time: f64,
        w: &crate::transition_source_plan::Work,
    ) -> Result<I, Error> {
        if let Some((_, bounds)) = self.history_exact_point(time, w)? {
            return Ok(bounds);
        }
        w.debit(2, 32)?;
        let held = self.bounds_at(I::point(time));
        if self
            .pending
            .front()
            .is_some_and(|(d, _, _, _)| d.bounds.lo < time && time < d.bounds.hi)
        {
            self.charge_held_copy(&|n| w.debit(2, n as u64))?;
            let mut activated = self.clone();
            let (deadline, target, bounds, exact) = activated.pending.pop_front().unwrap();
            activated.history_target(deadline, target, bounds, exact, w)?;
            w.debit(2, 32)?;
            return Ok(held.hull(activated.bounds_at(I::point(time))));
        }
        Ok(held)
    }
    pub(crate) fn history_observation_range(
        &self,
        times: I,
        w: &crate::transition_source_plan::Work,
    ) -> Result<I, Error> {
        w.step()?;
        if !times.finite()
            || times.lo > times.hi
            || self
                .edge
                .as_ref()
                .is_some_and(|e| times.lo < e.start_bounds.lo)
        {
            return Err(invalid("transition observation precedes retained history"));
        }
        self.charge_held_copy(&|n| w.debit(2, n as u64))?;
        let mut candidate = self.clone();
        let mut value = candidate.bounds_at(times);
        loop {
            w.step()?;
            if !candidate
                .pending
                .front()
                .is_some_and(|(d, _, _, _)| d.bounds.lo <= times.hi)
            {
                break;
            }
            let (deadline, target, bounds, exact) = candidate.pending.pop_front().unwrap();
            candidate.history_target(deadline, target, bounds, exact, w)?;
            value = value.hull(candidate.bounds_at(times));
        }
        Ok(value)
    }

    pub(crate) fn value_bounds(&self, time: f64) -> Result<I, Error> {
        // A retained rational line preserves the dependence on its exact start.
        // The nominal value still pays its full error against this enclosure.
        if let Some(bounds) = crate::exact_source::RootTime::point(time)
            .and_then(|time| self.exact_at(&time))
            .and_then(|value| crate::exact_source::enclosure(&value))
        {
            return Ok(bounds);
        }
        let held = self.bounds_at(I::point(time));
        if let Some((deadline, target, bounds, exact)) = self.pending.front().cloned() {
            if deadline.bounds.lo < time && time < deadline.bounds.hi {
                // A sample may fall after the exact activation but before its
                // representative upper time. Enclose both possibilities without
                // installing this preview in accepted history.
                let mut activated = self.clone();
                activated.pending.pop_front();
                activated.target(deadline, target, bounds, exact)?;
                let changed = activated.bounds_at(I::point(time));
                return Ok(I {
                    lo: held.lo.min(changed.lo),
                    hi: held.hi.max(changed.hi),
                });
            }
        }
        Ok(held)
    }

    /// Value observation may cover an activation enclosure. Keep both old
    /// and activated ramps; this supplies no derivative/root certificate.
    pub(crate) fn observation_range(&self, times: I) -> Result<I, Error> {
        if !times.finite()
            || times.lo > times.hi
            || self
                .edge
                .as_ref()
                .is_some_and(|e| times.lo < e.start_bounds.lo)
        {
            return Err(invalid(&format!(
                "transition observation precedes retained history: query={times:?}, edge={:?}",
                self.edge.as_ref().map(|e| e.start_bounds)
            )));
        }
        let mut candidate = self.clone();
        let mut value = candidate.bounds_at(times);
        while let Some((deadline, target, bounds, exact)) = candidate
            .pending
            .front()
            .cloned()
            .filter(|(d, _, _, _)| d.bounds.lo <= times.hi)
        {
            candidate.pending.pop_front();
            candidate.target(deadline, target, bounds, exact)?;
            value = value.hull(candidate.bounds_at(times));
        }
        Ok(value)
    }

    /// One candidate suffices for both range and derivative. Queue entries move
    /// from the paid copy rather than creating a second unmetered history copy.
    pub(crate) fn history_continuous_range(
        &self,
        times: I,
        w: &crate::transition_source_plan::Work,
    ) -> Result<(I, I), Error> {
        w.step()?;
        if !times.finite()
            || times.lo > times.hi
            || self
                .edge
                .as_ref()
                .is_some_and(|e| times.lo < e.start_bounds.lo)
        {
            return Err(invalid("transition observation precedes retained history"));
        }
        self.charge_held_copy(&|n| w.debit(2, n as u64))?;
        let mut candidate = self.clone();
        let slope = |history: &Self| {
            if let Some(edge) = &history.edge {
                let mut slope = edge.slope_bounds;
                if times.lo < edge.start_bounds.hi {
                    slope = slope.hull(edge.prior_slope)
                }
                if times.hi >= edge.end.bounds.lo {
                    slope = slope.hull(I::ZERO)
                }
                slope
            } else {
                I::ZERO
            }
        };
        let mut value = candidate.bounds_at(times);
        let mut derivative = slope(&candidate);
        while candidate
            .pending
            .front()
            .is_some_and(|(d, _, _, _)| d.bounds.lo <= times.hi)
        {
            w.step()?;
            let (deadline, target, bounds, exact) = candidate.pending.pop_front().unwrap();
            candidate.history_target(deadline, target, bounds, exact, w)?;
            value = value.hull(candidate.bounds_at(times));
            derivative = derivative.hull(slope(&candidate));
        }
        Ok((value, derivative))
    }

    pub(crate) fn continuous_range(&self, times: I) -> Result<(I, I), Error> {
        let value = self.observation_range(times)?;
        let slope = |history: &Self| {
            if let Some(edge) = &history.edge {
                let mut slope = edge.slope_bounds;
                if times.lo < edge.start_bounds.hi {
                    slope = slope.hull(edge.prior_slope);
                }
                if times.hi >= edge.end.bounds.lo {
                    slope = slope.hull(I::ZERO);
                }
                slope
            } else {
                I::ZERO
            }
        };
        let mut candidate = self.clone();
        let mut derivative = slope(&candidate);
        while let Some((deadline, target, bounds, exact)) = candidate
            .pending
            .front()
            .cloned()
            .filter(|(d, _, _, _)| d.bounds.lo <= times.hi)
        {
            candidate.pending.pop_front();
            candidate.target(deadline, target, bounds, exact)?;
            derivative = derivative.hull(slope(&candidate));
        }
        Ok((value, derivative))
    }

    fn bounds_at(&self, time: I) -> I {
        match &self.edge {
            Some(edge) if time.lo < edge.end.bounds.hi => {
                if let Some(duration) = edge.symmetric_blend {
                    let elapsed = (time - edge.start_bounds) / I::point(duration);
                    let fraction = I {
                        lo: elapsed.lo.clamp(0., 1.),
                        hi: elapsed.hi.clamp(0., 1.),
                    };
                    let blend =
                        edge.value_bounds + (edge.target_bounds - edge.value_bounds) * fraction;
                    let levels = edge.value_bounds.hull(edge.target_bounds);
                    return I {
                        lo: blend.lo.max(levels.lo),
                        hi: blend.hi.min(levels.hi),
                    };
                }
                let bounds = edge.value_bounds + edge.slope_bounds * (time - edge.start_bounds);
                // Interval extension of the exact monotone clipped ramp. The
                // uncertain delayed start and uncertain target remain in it.
                if edge.slope_bounds.lo > 0.0 {
                    I {
                        lo: bounds
                            .lo
                            .min(edge.target_bounds.lo)
                            .max(edge.value_bounds.lo),
                        hi: bounds
                            .hi
                            .min(edge.target_bounds.hi)
                            .max(edge.value_bounds.hi),
                    }
                } else {
                    I {
                        lo: bounds
                            .lo
                            .max(edge.target_bounds.lo)
                            .min(edge.value_bounds.lo),
                        hi: bounds
                            .hi
                            .max(edge.target_bounds.hi)
                            .min(edge.value_bounds.hi),
                    }
                }
            }
            Some(edge) => edge.target_bounds,
            None => self.settled_bounds,
        }
    }

    pub(crate) fn value(&self, time: f64) -> Result<f64, Error> {
        use num_traits::ToPrimitive;
        if let Some(value) = crate::exact_source::RootTime::point(time)
            .and_then(|time| self.exact_at(&time))
            .and_then(|value| {
                let bounds = crate::exact_source::enclosure(&value)?;
                let nearest = value.to_f64()?;
                (bounds.lo <= nearest && nearest <= bounds.hi).then_some(nearest)
            })
        {
            return Ok(value);
        }
        let value = match &self.edge {
            Some(edge) if time < edge.end.bounds.hi => {
                let raw = edge.value + edge.slope * (time - edge.start);
                if !raw.is_finite() {
                    return Err(invalid("nonfinite transition value"));
                }
                // Scheduling uses an enclosing upper time, while the waveform
                // remains clipped and monotone at every observation in that box.
                raw.clamp(edge.value.min(edge.target), edge.value.max(edge.target))
            }
            Some(edge) => edge.target,
            None => self.settled,
        };
        if !value.is_finite() {
            return Err(invalid("nonfinite transition value"));
        }
        Ok(value)
    }

    pub(crate) fn deadlines(&self, after: f64) -> Vec<Deadline> {
        self.pending
            .front()
            .map(|(deadline, _, _, _)| deadline.clone())
            .into_iter()
            .chain(self.edge.as_ref().map(|e| e.end.clone()))
            .filter(|deadline| deadline.bounds.hi > after)
            .collect()
    }

    pub(crate) fn history_deadlines(
        &self,
        after: f64,
        w: &crate::transition_source_plan::Work,
    ) -> Result<Vec<Deadline>, Error> {
        let mut out = Vec::new();
        for d in self
            .pending
            .front()
            .map(|(d, _, _, _)| d)
            .into_iter()
            .chain(self.edge.as_ref().map(|e| &e.end))
        {
            w.step()?;
            if d.bounds.hi <= after {
                continue;
            }
            w.debit(2, 12)?;
            let exact = d.exact.as_ref().map(|r| r.clone_with_work(w)).transpose()?;
            crate::history_storage::push_vec(
                &mut out,
                Deadline {
                    continuous_end: d.continuous_end,
                    bounds: d.bounds,
                    sum: d.sum,
                    exact,
                },
                w,
            )?;
        }
        Ok(out)
    }
    pub(crate) fn history_boundary(
        &self,
        after: f64,
        both_sides: bool,
        w: &crate::transition_source_plan::Work,
    ) -> Result<Option<f64>, Error> {
        w.debit(2, 0)?;
        let mut next = None;
        for bounds in self
            .pending
            .front()
            .map(|(d, _, _, _)| d.bounds)
            .into_iter()
            .chain(self.edge.as_ref().map(|e| e.end.bounds))
        {
            w.step()?;
            for time in [if both_sides { bounds.lo } else { bounds.hi }, bounds.hi] {
                w.step()?;
                if time > after {
                    next = Some(next.map_or(time, |old: f64| old.min(time)));
                }
            }
        }
        Ok(next)
    }

    pub(crate) fn next_breakpoint(&self, after: f64) -> Option<f64> {
        self.deadlines(after)
            .iter()
            .map(|d| d.bounds.hi)
            .min_by(f64::total_cmp)
    }

    fn target(
        &mut self,
        moment: Deadline,
        target: f64,
        target_bounds: I,
        exact_target: Option<num_rational::BigRational>,
    ) -> Result<(), Error> {
        let exact_start = moment.exact_time();
        let exact_value = exact_start.as_ref().and_then(|t| self.exact_at(t));
        let prior_slope = self.edge.as_ref().map_or(I::ZERO, |e| e.slope_bounds);
        let time = moment.bounds.hi;
        let value = self.value(time)?;
        let value_bounds = self.bounds_at(moment.bounds);
        let difference = target_bounds - value_bounds;
        let symmetric_blend = difference.sign().is_none()
            && self.rise == self.fall
            && self
                .edge
                .as_ref()
                .is_none_or(|edge| edge.end.bounds.hi <= moment.bounds.lo);
        let direction = difference
            .sign()
            .or(symmetric_blend.then_some(0))
            .ok_or_else(|| {
                invalid("cannot certify transition target relative to current output")
            })?;
        if direction == 0 && !symmetric_blend {
            self.settled = target;
            self.settled_bounds = target_bounds;
            self.exact_settled = exact_target;
            self.edge = None;
            return Ok(());
        }
        let active = self.edge.as_ref().filter(|edge| time < edge.end.bounds.hi);
        let (origin, origin_bounds, exact_origin) = match active {
            Some(edge) => {
                let old_direction = edge
                    .slope_bounds
                    .sign()
                    .ok_or_else(|| invalid("cannot certify transition edge direction"))?;
                if direction == old_direction {
                    (edge.origin, edge.origin_bounds, edge.exact_origin.clone())
                } else {
                    (edge.target, edge.target_bounds, edge.exact_target.clone())
                }
            }
            None => (value, value_bounds, exact_value.clone()),
        };
        let duration = if direction > 0 { self.rise } else { self.fall };
        let slope = (target - origin) / duration;
        let slope_bounds = (target_bounds - origin_bounds) / I::point(duration);
        if (!symmetric_blend
            && (slope_bounds.sign() != Some(direction)
                || slope == 0.0
                || (slope > 0.0) != (direction > 0)))
            || !slope_bounds.finite()
            || !slope.is_finite()
        {
            return Err(invalid("cannot certify transition slope"));
        }
        let (end_bounds, sum) = if active.is_none() {
            let sum = moment.sum.and_then(|mut terms| {
                // Source time + fixed delay occupies at most two terms.
                let zero = terms.iter().position(|x| *x == 0.0)?;
                terms[zero] = duration;
                Some(terms)
            });
            (moment.bounds + I::point(duration), sum)
        } else {
            let remaining = difference / slope_bounds;
            if !remaining.finite() || remaining.lo <= 0.0 {
                return Err(invalid("cannot certify transition remaining duration"));
            }
            (moment.bounds + remaining, None)
        };
        let mut end = deadline(end_bounds, duration, sum)?;
        end.continuous_end = true;
        if active.is_none() {
            end.exact = moment
                .exact
                .as_ref()
                .and_then(|root| root.shifted_fixed(duration, end_bounds));
        }
        if end.bounds.lo <= time {
            return Err(invalid("transition edge cannot advance representable time"));
        }
        let exact_line = (|| {
            use crate::exact_source::{binary, Budget};
            let mut budget = Budget(0);
            let delta = budget.check(exact_target.as_ref()? - exact_origin.as_ref()?)?;
            let slope = budget.check(delta / binary(duration)?)?;
            let product = budget.check(&slope * exact_start.as_ref()?.rational())?;
            Some((budget.check(exact_value? - product)?, slope))
        })();
        if let Some((a, b)) = &exact_line {
            let proof = (|| {
                let value = crate::exact_source::Budget(0).check(a - exact_target.as_ref()?)?;
                crate::exact_source::RootTime::affine(value, b.clone(), end.bounds)
            })();
            if end
                .exact
                .as_ref()
                .zip(proof.as_ref())
                .is_some_and(|(a, b)| a.order(b) != std::cmp::Ordering::Equal)
            {
                return Err(invalid(
                    "exact transition end contradicts timing certificate",
                ));
            }
            end.exact = end.exact.or(proof);
        }
        self.edge = Some(Edge {
            exact_line,
            exact_start,
            prior_slope,
            start: time,
            start_bounds: moment.bounds,
            value,
            value_bounds,
            origin,
            origin_bounds,
            exact_origin,
            target,
            target_bounds,
            exact_target,
            slope,
            slope_bounds,
            end,
            symmetric_blend: symmetric_blend.then_some(duration),
        });
        Ok(())
    }

    fn history_target(
        &mut self,
        moment: Deadline,
        target: f64,
        target_bounds: I,
        exact_target: Option<num_rational::BigRational>,
        w: &crate::transition_source_plan::Work,
    ) -> Result<(), Error> {
        use crate::exact_source::history_paid::{affine_root, root, Paid};
        w.debit(2, 64)?;
        let exact_start = moment.history_exact_time(w)?;
        let exact_value = match exact_start.as_ref() {
            Some(t) => self.history_exact_at(t, w)?,
            None => None,
        };
        let prior_slope = self.edge.as_ref().map_or(I::ZERO, |e| e.slope_bounds);
        let time = moment.bounds.hi;
        let value = self.history_value(time, w)?;
        let value_bounds = self.bounds_at(moment.bounds);
        let difference = target_bounds - value_bounds;
        let symmetric_blend = difference.sign().is_none()
            && self.rise == self.fall
            && self
                .edge
                .as_ref()
                .is_none_or(|edge| edge.end.bounds.hi <= moment.bounds.lo);
        let direction = difference
            .sign()
            .or(symmetric_blend.then_some(0))
            .ok_or_else(|| {
                invalid("cannot certify transition target relative to current output")
            })?;
        if direction == 0 && !symmetric_blend {
            self.settled = target;
            self.settled_bounds = target_bounds;
            self.exact_settled = exact_target;
            self.edge = None;
            return Ok(());
        }
        let active = self.edge.as_ref().filter(|edge| time < edge.end.bounds.hi);
        let (origin, origin_bounds, exact_origin) = match active {
            Some(edge) => {
                let old_direction = edge
                    .slope_bounds
                    .sign()
                    .ok_or_else(|| invalid("cannot certify transition edge direction"))?;
                if direction == old_direction {
                    let mut p = Paid::new(w);
                    let v = edge.exact_origin.as_ref().and_then(|v| p.copy(v));
                    (edge.origin, edge.origin_bounds, p.finish(v)?)
                } else {
                    let mut p = Paid::new(w);
                    let v = edge.exact_target.as_ref().and_then(|v| p.copy(v));
                    (edge.target, edge.target_bounds, p.finish(v)?)
                }
            }
            None => {
                let mut p = Paid::new(w);
                let v = exact_value.as_ref().and_then(|v| p.copy(v));
                (value, value_bounds, p.finish(v)?)
            }
        };
        let duration = if direction > 0 { self.rise } else { self.fall };
        let slope = (target - origin) / duration;
        let slope_bounds = (target_bounds - origin_bounds) / I::point(duration);
        if (!symmetric_blend
            && (slope_bounds.sign() != Some(direction)
                || slope == 0.0
                || (slope > 0.0) != (direction > 0)))
            || !slope_bounds.finite()
            || !slope.is_finite()
        {
            return Err(invalid("cannot certify transition slope"));
        }
        let (end_bounds, sum) = if active.is_none() {
            let sum = moment.sum.and_then(|mut terms| {
                // Source time + fixed delay occupies at most two terms.
                let zero = terms.iter().position(|x| *x == 0.0)?;
                terms[zero] = duration;
                Some(terms)
            });
            (moment.bounds + I::point(duration), sum)
        } else {
            let remaining = difference / slope_bounds;
            if !remaining.finite() || remaining.lo <= 0.0 {
                return Err(invalid("cannot certify transition remaining duration"));
            }
            (moment.bounds + remaining, None)
        };
        let mut end = deadline(end_bounds, duration, sum)?;
        end.continuous_end = true;
        if active.is_none() {
            let mut p = Paid::new(w);
            let value = (|| {
                let start = moment.exact.as_ref()?;
                let d = p.binary(duration)?;
                let sum = p.op(start.rational(), &d, '+')?;
                let lo = p.binary(end_bounds.lo)?;
                let hi = p.binary(end_bounds.hi)?;
                if p.cmp(&lo, &sum)?.is_gt() || p.cmp(&sum, &hi)?.is_gt() {
                    return None;
                }
                Some(root(sum))
            })();
            end.exact = p.finish(value)?;
        }
        if end.bounds.lo <= time {
            return Err(invalid("transition edge cannot advance representable time"));
        }
        let mut p = Paid::new(w);
        let line = (|| {
            let delta = p.op(exact_target.as_ref()?, exact_origin.as_ref()?, '-')?;
            let d = p.binary(duration)?;
            let slope = p.op(&delta, &d, '/')?;
            let product = p.op(&slope, exact_start.as_ref()?.rational(), '*')?;
            let intercept = p.op(exact_value.as_ref()?, &product, '-')?;
            Some((intercept, slope))
        })();
        let exact_line = p.finish(line)?;
        if let Some((a, b)) = &exact_line {
            let mut p = Paid::new(w);
            let args = (|| Some((p.op(a, exact_target.as_ref()?, '-')?, p.copy(b)?)))();
            let proof = match p.finish(args)? {
                Some((v, b)) => affine_root(v, b, end.bounds, w)?,
                None => None,
            };
            if let (Some(a), Some(b)) = (end.exact.as_ref(), proof.as_ref()) {
                if a.order_with_work(b, w)? != std::cmp::Ordering::Equal {
                    return Err(invalid(
                        "exact transition end contradicts timing certificate",
                    ));
                }
            }
            end.exact = end.exact.or(proof);
        }
        w.debit(2, 40)?;
        self.edge = Some(Edge {
            exact_line,
            exact_start,
            prior_slope,
            start: time,
            start_bounds: moment.bounds,
            value,
            value_bounds,
            origin,
            origin_bounds,
            exact_origin,
            target,
            target_bounds,
            exact_target,
            slope,
            slope_bounds,
            end,
            symmetric_blend: symmetric_blend.then_some(duration),
        });
        Ok(())
    }

    #[cfg(test)]
    pub(crate) fn advance(&mut self, time: f64, input: f64) -> Result<(), Error> {
        self.advance_enclosed(time, input, I::point(input), false)
    }

    pub(crate) fn advance_enclosed(
        &mut self,
        time: f64,
        input: f64,
        bounds: I,
        may_change: bool,
    ) -> Result<(), Error> {
        self.advance_at(time, I::point(time), input, bounds, may_change)
    }

    /// The event's physical-time enclosure is distinct from its execution
    /// representative. Retain it in every downstream activation and edge.
    pub(crate) fn advance_at(
        &mut self,
        time: f64,
        time_bounds: I,
        input: f64,
        bounds: I,
        may_change: bool,
    ) -> Result<(), Error> {
        self.advance_at_with_exact(time, time_bounds, input, bounds, may_change, None)
    }

    pub(crate) fn advance_at_with_exact(
        &mut self,
        time: f64,
        time_bounds: I,
        input: f64,
        bounds: I,
        may_change: bool,
        exact_root: Option<&crate::exact_source::RootTime>,
    ) -> Result<(), Error> {
        self.advance_at_with_proofs(
            time,
            time_bounds,
            input,
            bounds,
            may_change,
            exact_root,
            None,
        )
    }

    /// Held-state callers may supply a value proved from original arithmetic.
    /// Source-selected plans keep their existing entry point and admission.
    #[allow(clippy::too_many_arguments)]
    pub(crate) fn advance_at_with_proofs(
        &mut self,
        time: f64,
        time_bounds: I,
        input: f64,
        bounds: I,
        may_change: bool,
        exact_root: Option<&crate::exact_source::RootTime>,
        target_proof: Option<&num_rational::BigRational>,
    ) -> Result<(), Error> {
        self.advance_at_with_work(
            time,
            time_bounds,
            input,
            bounds,
            may_change,
            exact_root,
            target_proof,
            None,
        )
    }
    #[allow(clippy::too_many_arguments)]
    pub(crate) fn advance_at_with_history_work(
        &mut self,
        time: f64,
        time_bounds: I,
        input: f64,
        bounds: I,
        may_change: bool,
        exact_root: Option<&crate::exact_source::RootTime>,
        target_proof: Option<&num_rational::BigRational>,
        work: &crate::transition_source_plan::Work,
    ) -> Result<(), Error> {
        self.advance_at_with_work(
            time,
            time_bounds,
            input,
            bounds,
            may_change,
            exact_root,
            target_proof,
            Some(work),
        )
    }
    #[allow(clippy::too_many_arguments)]
    fn advance_at_with_work(
        &mut self,
        time: f64,
        time_bounds: I,
        input: f64,
        bounds: I,
        may_change: bool,
        exact_root: Option<&crate::exact_source::RootTime>,
        target_proof: Option<&num_rational::BigRational>,
        work: Option<&crate::transition_source_plan::Work>,
    ) -> Result<(), Error> {
        if let Some(w) = work {
            w.step()?;
        }

        let root_outside = if let Some(root) = exact_root {
            if let Some(w) = work {
                root.refine_with_work(time_bounds, w)?.is_none()
            } else {
                root.refine(time_bounds).is_none()
            }
        } else {
            false
        };
        if root_outside {
            return Err(invalid("exact transition root is outside event enclosure"));
        }
        if !time_bounds.finite() || time_bounds.lo > time_bounds.hi || time_bounds.hi > time {
            return Err(invalid("invalid transition event-time enclosure"));
        }
        // Called only on a cloned candidate runtime. A failed pop/edge rebuild
        // discards the whole candidate, including all prior queue mutations.
        while self
            .pending
            .front()
            .is_some_and(|(deadline, _, _, _)| deadline.bounds.hi <= time)
        {
            let (deadline, target, target_bounds, exact) = self.pending.pop_front().unwrap();
            if let Some(w) = work {
                self.history_target(deadline, target, target_bounds, exact, w)?;
            } else {
                self.target(deadline, target, target_bounds, exact)?;
            }
        }
        let end_reached = if let Some(edge) = self.edge.as_ref() {
            if let Some(root) = exact_root {
                let end = if let Some(w) = work {
                    edge.end.history_exact_time(w)?
                } else {
                    edge.end.exact_time()
                };
                if let Some(end) = end {
                    if let Some(w) = work {
                        end.order_with_work(root, w)? != std::cmp::Ordering::Greater
                    } else {
                        end.order(root) != std::cmp::Ordering::Greater
                    }
                } else {
                    edge.end.bounds.hi <= time
                }
            } else {
                edge.end.bounds.hi <= time
            }
        } else {
            false
        };
        if end_reached {
            if work.is_some() {
                crate::diagnostics::counter("history_held_edge_settles", 1);
            }
            let edge = self.edge.take().unwrap();
            self.settled = edge.target;
            self.settled_bounds = edge.target_bounds;
            self.exact_settled = edge.exact_target;
        }
        if !input.is_finite() || !bounds.finite() {
            return Err(invalid("nonfinite transition target"));
        }
        if input == self.input && bounds != self.input_bounds && !may_change {
            return Err(invalid("cannot certify unchanged transition input history"));
        }
        let uncertain_write = may_change && (bounds.lo != bounds.hi || bounds != self.input_bounds);
        if input != self.input || uncertain_write {
            let exact_target = if let Some(w) = work {
                use crate::exact_source::history_paid::Paid;
                let mut p = Paid::new(w);
                let value = (|| {
                    if let Some(v) = target_proof {
                        if let Some(i) = p.enclose(v) {
                            if bounds.lo <= i.lo && i.hi <= bounds.hi {
                                return p.copy(v);
                            }
                        }
                    }
                    if bounds.lo == bounds.hi {
                        p.binary(bounds.lo)
                    } else {
                        None
                    }
                })();
                p.finish(value)?
            } else {
                exact_level(bounds, target_proof)
            };
            self.input_revision = self
                .input_revision
                .checked_add(1)
                .ok_or_else(|| invalid("transition input revision budget exceeded"))?;
            self.input = input;
            self.input_bounds = bounds;
            if self.delay == 0.0 {
                let owned_root = if let Some(root) = exact_root {
                    Some(if let Some(w) = work {
                        root.clone_with_work(w)?
                    } else {
                        root.clone()
                    })
                } else {
                    None
                };
                let moment = Deadline {
                    continuous_end: false,
                    bounds: time_bounds,
                    exact: owned_root,
                    sum: (time_bounds.lo == time_bounds.hi).then_some([time_bounds.lo, 0.0, 0.0]),
                };
                if let Some(w) = work {
                    self.history_target(moment, input, bounds, exact_target, w)?;
                } else {
                    self.target(moment, input, bounds, exact_target)?;
                }
            } else {
                let mut next = deadline(
                    time_bounds + I::point(self.delay),
                    self.delay,
                    (time_bounds.lo == time_bounds.hi).then_some([time_bounds.lo, self.delay, 0.0]),
                )?;
                next.exact = if let (Some(exact), Some(w)) = (exact_root, work) {
                    use crate::exact_source::history_paid::{root, Paid};
                    let mut p = Paid::new(w);
                    let value = (|| {
                        let d = p.binary(self.delay)?;
                        let sum = p.op(exact.rational(), &d, '+')?;
                        let lo = p.binary(next.bounds.lo)?;
                        let hi = p.binary(next.bounds.hi)?;
                        if p.cmp(&lo, &sum)?.is_gt() || p.cmp(&sum, &hi)?.is_gt() {
                            return None;
                        }
                        Some(root(sum))
                    })();
                    p.finish(value)?
                } else {
                    exact_root.and_then(|root| root.shifted_fixed(self.delay, next.bounds))
                };
                if next.bounds.lo <= time {
                    return Err(invalid(
                        "transition delay cannot advance representable time",
                    ));
                }
                if self
                    .pending
                    .back()
                    .is_some_and(|(old, _, _, _)| old.bounds.hi >= next.bounds.lo)
                {
                    return Err(invalid(
                        "cannot certify ordering of distinct transition target deadlines",
                    ));
                }
                let pending = (next, input, bounds, exact_target);
                if let Some(w) = work {
                    crate::history_storage::push_deque(&mut self.pending, pending, w)?;
                } else {
                    self.pending.push_back(pending);
                }
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn equal_enclosures_do_not_prove_a_rewritten_target_unchanged() {
        let bounds = I { lo: 0.99, hi: 1.01 };
        let accepted = Transition::enclosed(1.0, bounds, 0.0, 1.0, 2.0).unwrap();
        let mut held = accepted.clone();
        held.advance_enclosed(0.5, 1.0, bounds, false).unwrap();
        let mut written = accepted.clone();
        assert!(written.advance_enclosed(0.5, 1.0, bounds, true).is_err());
        assert_eq!(accepted.value_bounds(0.5).unwrap(), bounds);
    }
    #[test]
    fn settled_symmetric_rewrite_encloses_independent_targets_in_both_directions() {
        let bounds = I { lo: 0.99, hi: 1.01 };
        let accepted = Transition::enclosed(1., bounds, 0., 0.25, 0.25).unwrap();
        let mut next = accepted.clone();
        next.advance_enclosed(0.5, 1., bounds, true).unwrap();
        assert!(next.input_changed_from(&accepted));
        for t in [0.5, 0.5625, 0.625, 0.75, 1.] {
            let got = next.value_bounds(t).unwrap();
            let fraction = ((t - 0.5) / 0.25_f64).clamp(0., 1.);
            for old in [0.99, 1., 1.01] {
                for target in [0.99, 1., 1.01] {
                    let expected = old + (target - old) * fraction;
                    assert!(
                        got.lo <= expected && expected <= got.hi,
                        "{t}: {got:?} excludes {expected}"
                    );
                }
            }
            assert_eq!(next.value(t).unwrap(), 1.);
        }
        // A new uncertain write during an active edge still lacks a proof.
        let mut interrupted = next.clone();
        assert!(interrupted
            .advance_enclosed(0.625, 1., bounds, true)
            .is_err());
        assert_eq!(accepted.value_bounds(0.625).unwrap(), bounds);
    }

    fn near(a: f64, b: f64) {
        assert!((a - b).abs() < 1e-12, "{a} != {b}");
    }
    #[test]
    fn interrupted_edges_preserve_origin_and_reflect() {
        for sign in [1.0, -1.0] {
            let mut edge = Transition::new(
                0.0,
                0.0,
                if sign > 0.0 { 10.0 } else { 20.0 },
                if sign > 0.0 { 20.0 } else { 10.0 },
            )
            .unwrap();
            edge.advance(2.0, sign).unwrap();
            edge.advance(6.0, 0.0).unwrap();
            near(edge.value(6.0).unwrap(), sign * 0.4);
            near(edge.value(10.0).unwrap(), sign * 0.2);
            near(edge.value(14.0).unwrap(), 0.0);
        }
        let mut edge = Transition::new(0.0, 0.0, 10.0, 20.0).unwrap();
        edge.advance(2.0, 1.0).unwrap();
        edge.advance(6.0, 2.0).unwrap();
        near(edge.value(10.0).unwrap(), 1.2);
        near(edge.value(14.0).unwrap(), 2.0);
    }
    #[test]
    fn queue_repeat_and_exact_current_target() {
        let mut edge = Transition::new(0.0, 10.0, 2.0, 2.0).unwrap();
        edge.advance(2.0, 1.0).unwrap();
        edge.advance(3.0, 0.0).unwrap();
        edge.advance(12.0, 0.0).unwrap();
        near(edge.value(12.5).unwrap(), 0.25);
        edge.advance(13.0, 0.0).unwrap();
        near(edge.value(13.5).unwrap(), 0.25);
        edge.advance(14.0, 0.0).unwrap();
        near(edge.value(14.0).unwrap(), 0.0);
        let mut edge = Transition::new(0.0, 0.0, 10.0, 20.0).unwrap();
        edge.advance(2.0, 1.0).unwrap();
        edge.advance(6.0, 1.0).unwrap();
        near(edge.value(10.0).unwrap(), 0.8);
        let mut exact = Transition::new(0.0, 0.0, 8.0, 8.0).unwrap();
        exact.advance(2.0, 1.0).unwrap();
        exact.advance(6.0, 0.5).unwrap();
        near(exact.value(100.0).unwrap(), 0.5);
    }
}

#[cfg(test)]
mod exact_transition_line_tests {
    use super::*;
    use crate::exact_source::{binary, RootTime};
    use num_rational::BigRational as R;

    fn falling_at(root: R) -> (Transition, RootTime) {
        let window = crate::exact_source::enclosure(&root).unwrap();
        let proof = RootTime::affine(-root, binary(1.).unwrap(), window).unwrap();
        let mut history = Transition::new(0.9, 0., 1e-11, 1e-11).unwrap();
        history
            .advance_at_with_exact(window.hi, window, 0., I::ZERO, true, Some(&proof))
            .unwrap();
        (history, proof)
    }

    // Independent physical ramp answer, before any binary64 time representative
    // is selected. Clipping also supplies the exact constant pieces.
    fn falling_answer(root: &RootTime, time: f64) -> R {
        let duration = binary(1e-11).unwrap();
        let remaining = root.rational() + &duration - binary(time).unwrap();
        let level = binary(0.9).unwrap();
        (level.clone() * remaining / duration)
            .max(binary(0.).unwrap())
            .min(level)
    }

    #[test]
    fn proved_nonbinary_start_encloses_independent_point_answer() {
        let root = binary(65e-9).unwrap() + binary(0.11e-9).unwrap();
        let (history, proof) = falling_at(root);
        let time = (65.12e-9_f64).next_down();
        let exact = falling_answer(&proof, time);
        let nominal = history.value(time).unwrap();
        let bounds = history.value_bounds(time).unwrap();
        assert!(binary(bounds.lo).unwrap() <= exact && exact <= binary(bounds.hi).unwrap());
        use num_traits::ToPrimitive;
        assert_eq!(nominal.to_bits(), exact.to_f64().unwrap().to_bits());
        assert!((I::point(nominal) - bounds).magnitude() <= 1e-12);
    }

    #[test]
    fn proved_start_repairs_nominal_displacement_without_relaxing_voltage_budget() {
        let lo = 65.11e-9_f64;
        let root = binary(lo).unwrap()
            + (binary(lo.next_up()).unwrap() - binary(lo).unwrap()) / R::from_integer(100.into());
        let (history, proof) = falling_at(root);
        let time = 65.12e-9;
        let exact = falling_answer(&proof, time);
        let bounds = history.value_bounds(time).unwrap();
        assert!(binary(bounds.lo).unwrap() <= exact && exact <= binary(bounds.hi).unwrap());
        use num_traits::ToPrimitive;
        let nominal = history.value(time).unwrap();
        assert_eq!(nominal.to_bits(), exact.to_f64().unwrap().to_bits());
        assert!((I::point(nominal) - bounds).magnitude() <= 1e-12);
    }

    #[test]
    fn point_proof_encloses_both_sides_of_clipped_end_and_leaves_history_unchanged() {
        let root = binary(65e-9).unwrap() + binary(0.11e-9).unwrap();
        let (history, proof) = falling_at(root);
        let mut rising = Transition::new(0., 0., 1e-11, 1e-11).unwrap();
        let window = proof.bounds().unwrap();
        rising
            .advance_at_with_exact(window.hi, window, 0.9, I::point(0.9), true, Some(&proof))
            .unwrap();
        let saved = (history.clone(), rising.clone());
        let end =
            crate::exact_source::enclosure(&(proof.rational() + binary(1e-11).unwrap())).unwrap();
        for time in [
            proof.bounds().unwrap().hi,
            65.115e-9,
            end.lo,
            end.hi,
            end.hi.next_up(),
        ] {
            let exact = falling_answer(&proof, time);
            let bounds = history.value_bounds(time).unwrap();
            history.value(time).unwrap();
            rising.value(time).unwrap();
            assert!(binary(bounds.lo).unwrap() <= exact && exact <= binary(bounds.hi).unwrap());
            let exact_rising = binary(0.9).unwrap() - exact;
            let bounds_rising = rising.value_bounds(time).unwrap();
            assert!(
                binary(bounds_rising.lo).unwrap() <= exact_rising
                    && exact_rising <= binary(bounds_rising.hi).unwrap()
            );
        }
        assert_eq!((history, rising), saved);
    }

    #[test]
    fn nonbinary_start_proves_the_physical_line_only_on_one_retained_piece() {
        let root = RootTime::affine(
            R::from_integer((-1).into()),
            R::from_integer(3.into()),
            I { lo: 0.3, hi: 0.4 },
        )
        .unwrap();
        let window = root.bounds().unwrap();
        let mut history = Transition::new(0., 0., 0.5, 0.5).unwrap();
        history
            .advance_at_with_exact(window.hi, window, 1., I::ONE, true, Some(&root))
            .unwrap();
        let (a, b) = history.exact_affine_on(I { lo: 0.5, hi: 0.75 }).unwrap();
        assert_eq!(a, R::new((-2).into(), 3.into()));
        assert_eq!(b, binary(2.).unwrap());
        assert!(history.exact_affine_on(I { lo: 0.25, hi: 0.5 }).is_none());
        assert!(history.exact_affine_on(I { lo: 0.75, hi: 1. }).is_none());
        let mut unknown = Transition::enclosed(
            0.,
            I {
                lo: -1e-6,
                hi: 1e-6,
            },
            0.,
            0.5,
            0.5,
        )
        .unwrap();
        unknown
            .advance_at_with_exact(window.hi, window, 1., I::ONE, true, Some(&root))
            .unwrap();
        assert!(unknown.exact_affine_on(I { lo: 0.5, hi: 0.75 }).is_none());
    }

    #[test]
    fn exact_deadline_orders_closed_boxes_without_ordering_unknown_real_times() {
        let root = RootTime::affine(
            R::from_integer((-1).into()),
            R::from_integer(3.into()),
            I { lo: 0.3, hi: 0.4 },
        )
        .unwrap();
        let bounds = root.bounds().unwrap();
        let mut d = deadline(bounds, 1., None).unwrap();
        d.exact = Some(root);
        assert!(d.strictly_ordered_with(I {
            lo: bounds.hi,
            hi: 0.5
        }));
        assert!(d.strictly_ordered_with(I {
            lo: 0.1,
            hi: bounds.lo
        }));
        assert!(!d.strictly_ordered_with(bounds));
        d.exact = None;
        assert!(!d.strictly_ordered_with(I {
            lo: bounds.hi,
            hi: 0.5
        }));
        d.exact = RootTime::point(0.75);
        assert!(!d.strictly_ordered_with(I {
            lo: bounds.hi,
            hi: 0.5
        }));
    }

    #[test]
    fn ordered_real_deadlines_do_not_authorize_a_representative_that_skips_the_next_one() {
        let mut a = deadline(I { lo: 0.3, hi: 0.4 }, 100., None).unwrap();
        a.exact = RootTime::point(0.35);
        let mut b = deadline(I { lo: 0.35, hi: 0.5 }, 100., None).unwrap();
        b.exact = RootTime::point(0.45);
        assert!(a.serial_representatives(&b));
        assert!(b.serial_representatives(&a));
        b.exact = RootTime::point(0.39);
        assert!(!a.serial_representatives(&b));
        b.exact = None;
        assert!(!a.serial_representatives(&b));
        b.exact = RootTime::point(0.45);
        b.bounds.hi = 0.4;
        assert!(!a.serial_representatives(&b));
    }
}

#[cfg(test)]
mod exact_deadline_tests {
    use super::*;
    use crate::exact_source::RootTime;
    use num_rational::BigRational as R;
    use num_traits::One;

    fn root() -> RootTime {
        RootTime::affine(-R::one(), R::from_integer(3.into()), I { lo: 0.3, hi: 0.4 }).unwrap()
    }

    #[test]
    fn fresh_exact_proof_preserves_deadlines_and_improves_only_proved_point_values() {
        let root = root();
        let window = root.bounds().unwrap();
        for delay in [0., 0.125] {
            let mut old = Transition::new(0., delay, 0.125, 0.125).unwrap();
            let mut new = old.clone();
            old.advance_at(window.hi, window, 1., I::ONE, true).unwrap();
            new.advance_at_with_exact(window.hi, window, 1., I::ONE, true, Some(&root))
                .unwrap();
            assert_eq!(old.deadlines(0.)[0].bounds, new.deadlines(0.)[0].bounds);
            assert!(new.deadlines(0.)[0].exact.is_some());
            assert!(!old.deadlines(0.)[0].coincides(&new.deadlines(0.)[0]));
            for t in [window.hi, 0.4, 0.5, 0.6] {
                if delay > 0. {
                    assert_eq!(
                        old.value(t).unwrap().to_bits(),
                        new.value(t).unwrap().to_bits()
                    );
                }
                let broad = old.value_bounds(t).unwrap();
                let tight = new.value_bounds(t).unwrap();
                assert!(broad.lo <= tight.lo && tight.hi <= broad.hi);
                if delay == 0. {
                    // Physical start is 1/3, independently of its upper
                    // execution representative. The rise lasts exactly 1/8.
                    let exact = ((crate::exact_source::binary(t).unwrap()
                        - R::new(1.into(), 3.into()))
                        * R::from_integer(8.into()))
                    .max(R::from_integer(0.into()))
                    .min(R::one());
                    assert!(
                        crate::exact_source::binary(tight.lo).unwrap() <= exact
                            && exact <= crate::exact_source::binary(tight.hi).unwrap()
                    );
                    use num_traits::ToPrimitive;
                    assert_eq!(
                        new.value(t).unwrap().to_bits(),
                        exact.to_f64().unwrap().to_bits()
                    );
                }
            }
            if delay > 0. {
                let time = new.next_breakpoint(0.).unwrap();
                old.advance_at(time, I::point(time), 1., I::ONE, false)
                    .unwrap();
                new.advance_at(time, I::point(time), 1., I::ONE, false)
                    .unwrap();
                assert!(new.edge.as_ref().unwrap().end.exact.is_some());
                assert_eq!(
                    old.edge.as_ref().unwrap().end.bounds,
                    new.edge.as_ref().unwrap().end.bounds
                );
            }
        }
    }

    #[test]
    fn shared_anchor_and_interrupted_line_need_distinct_end_certificates() {
        let root = root();
        let window = root.bounds().unwrap();
        let mut a = Transition::new(0., 0., 0.75, 0.75).unwrap();
        let mut b = a.clone();
        a.advance_at_with_exact(window.hi, window, 1., I::ONE, true, Some(&root))
            .unwrap();
        b.advance_at_with_exact(window.hi, window, 2., I::point(2.), true, Some(&root))
            .unwrap();
        assert!(a
            .edge
            .as_ref()
            .unwrap()
            .end
            .coincides(&b.edge.as_ref().unwrap().end));
        let next = RootTime::from_clock(
            crate::exact_time::Clock {
                start: 0.5,
                period: 0.,
                index: 0,
            },
            I::point(0.5),
        )
        .unwrap();
        a.advance_at_with_exact(0.5, I::point(0.5), 2., I::point(2.), true, Some(&next))
            .unwrap();
        let end = &a.edge.as_ref().unwrap().end;
        let expected = RootTime::affine(
            -R::from_integer(7.into()),
            R::from_integer(6.into()),
            end.bounds,
        )
        .unwrap();
        assert!(end.coincides_root(&expected));
        assert!(a.edge.as_ref().unwrap().end.sum.is_none());
        let mut unknown = Transition::new(0., 0., 0.75, 0.75).unwrap();
        unknown
            .advance_at(window.hi, window, 1., I::ONE, true)
            .unwrap();
        unknown
            .advance_at_with_exact(0.5, I::point(0.5), 2., I::point(2.), true, Some(&next))
            .unwrap();
        assert!(unknown.edge.as_ref().unwrap().end.exact.is_none());
        assert!(unknown.edge.as_ref().unwrap().end.sum.is_none());
    }

    #[test]
    fn split_fixed_arithmetic_is_exact_and_stays_bounded_by_discovery() {
        let root = root();
        let wide = I { lo: 0., hi: 1. };
        let split = root
            .shifted_fixed(0.1, wide)
            .unwrap()
            .shifted_fixed(0.2, wide)
            .unwrap();
        let rounded = root.shifted_fixed(0.1 + 0.2, wide).unwrap();
        assert_ne!(split.order(&rounded), std::cmp::Ordering::Equal);
        assert!(root.shifted_fixed(0.1, I::point(0.5)).is_none());
        assert!(root.shifted_fixed(f64::INFINITY, wide).is_none());
    }
}

#[cfg(test)]
mod exact_deadline_review_tests {
    use super::*;
    use crate::exact_source::RootTime;

    #[test]
    fn mismatched_or_malformed_exact_window_rejects_before_queue_mutation() {
        let root = RootTime::from_clock(
            crate::exact_time::Clock {
                start: 0.5,
                period: 0.,
                index: 0,
            },
            I::point(0.5),
        )
        .unwrap();
        let mut retained = Transition::new(0., 0.125, 0.25, 0.25).unwrap();
        retained
            .advance_at(0.25, I::point(0.25), 1., I::ONE, true)
            .unwrap();
        assert!(!retained.pending.is_empty());
        for window in [
            I::point(0.75),
            I { lo: 0.6, hi: 0.4 },
            I {
                lo: f64::NAN,
                hi: 0.5,
            },
            I {
                lo: 0.,
                hi: f64::INFINITY,
            },
        ] {
            let mut candidate = retained.clone();
            let error = candidate
                .advance_at_with_exact(1., window, 2., I::point(2.), true, Some(&root))
                .unwrap_err();
            assert_eq!(error.kind, "event_resolution");
            assert_eq!(
                error.message,
                "exact transition root is outside event enclosure"
            );
            assert_eq!(candidate, retained);
        }
        let mut valid = retained.clone();
        valid
            .advance_at_with_exact(0.5, I::point(0.5), 2., I::point(2.), true, Some(&root))
            .unwrap();
        assert_ne!(valid, retained);
    }
}

#[cfg(test)]
mod rational_level_tests {
    use super::*;
    use crate::exact_source::{binary, enclosure, RootTime};
    use num_rational::BigRational as R;
    use num_traits::ToPrimitive;

    fn level() -> R {
        binary(0.45).unwrap() * binary(0.16).unwrap()
    }

    fn write(history: &mut Transition, time: f64, value: &R, proved: bool) {
        history
            .advance_at_with_proofs(
                time,
                I::point(time),
                value.to_f64().unwrap(),
                enclosure(value).unwrap(),
                true,
                Some(&RootTime::point(time).unwrap()),
                proved.then_some(value),
            )
            .unwrap();
    }

    fn retarget(scale: i32, proved: bool, target: &R) -> Transition {
        let mut history = Transition::new(0., 0., 0.2, 0.2).unwrap();
        write(
            &mut history,
            0.1,
            &(level() * R::from_integer(scale.into())),
            proved,
        );
        write(&mut history, 0.15, target, proved);
        history
    }

    #[test]
    fn rational_interrupted_scaled_levels_recover_the_same_end_without_changing_boxes() {
        let a = level();
        let half = &a / R::from_integer(2.into());
        let old = retarget(1, false, &half);
        let new = retarget(1, true, &half);
        let twice = retarget(2, true, &a);
        let old_end = &old.edge.as_ref().unwrap().end;
        let new_end = &new.edge.as_ref().unwrap().end;
        assert!(old_end.exact_time().is_none());
        assert_eq!(old_end.bounds, new_end.bounds);
        assert!(new_end.coincides(&twice.edge.as_ref().unwrap().end));
        let expected = binary(0.2).unwrap() + R::from_integer(2.into()) * binary(0.1).unwrap()
            - binary(0.15).unwrap();
        assert_eq!(new_end.exact_time().unwrap().rational(), &expected);
        for t in [0.15, 0.175, 0.2, 0.249, 0.3] {
            let elapsed = binary(t).unwrap() - binary(0.15).unwrap();
            let at_change =
                &a * (binary(0.15).unwrap() - binary(0.1).unwrap()) / binary(0.2).unwrap();
            let oracle = (at_change + &half * elapsed / binary(0.2).unwrap()).min(half.clone());
            assert_eq!(new.exact_at(&RootTime::point(t).unwrap()).unwrap(), oracle);
            let bounds = new.value_bounds(t).unwrap();
            assert!(binary(bounds.lo).unwrap() <= oracle && oracle <= binary(bounds.hi).unwrap());
        }
    }

    #[test]
    fn reversal_keeps_the_old_exact_target_as_the_new_origin() {
        let a = level();
        let target = -&a / R::from_integer(2.into());
        let history = retarget(1, true, &target);
        let edge = history.edge.as_ref().unwrap();
        assert_eq!(edge.exact_origin.as_ref(), Some(&a));
        let slope = (&target - &a) / binary(0.2).unwrap();
        let value = &a * (binary(0.15).unwrap() - binary(0.1).unwrap()) / binary(0.2).unwrap();
        let end = binary(0.15).unwrap() + (&target - value) / slope;
        assert_eq!(edge.end.exact_time().unwrap().rational(), &end);
    }

    #[test]
    fn different_rational_levels_do_not_merge_nearby_end_identities() {
        let a = level();
        let half = &a / R::from_integer(2.into());
        let nearby = &half + &a / R::from_integer((1_u64 << 55).into());
        let first = retarget(1, true, &half);
        let second = retarget(1, true, &nearby);
        let a = &first.edge.as_ref().unwrap().end;
        let b = &second.edge.as_ref().unwrap().end;
        assert!(a.bounds.lo <= b.bounds.hi && b.bounds.lo <= a.bounds.hi);
        assert_ne!(
            a.exact_time().unwrap().order(&b.exact_time().unwrap()),
            std::cmp::Ordering::Equal
        );
        assert!(!a.coincides(b));
    }

    #[test]
    fn missing_mismatched_and_exhausted_proofs_do_not_seed_uncertain_levels() {
        let a = level();
        let bounds = enclosure(&a).unwrap();
        assert_ne!(bounds.lo, bounds.hi);
        assert!(exact_level(bounds, None).is_none());
        assert!(exact_level(bounds, Some(&binary(1.).unwrap())).is_none());
        let huge = R::from_integer(num_traits::One::one())
            / R::from_integer(
                (num_rational::BigRational::from_integer(2.into()).to_integer()
                    << (crate::exact_source::MAX_BITS + 1) as usize)
                    + 1,
            );
        assert!(exact_level(I { lo: 0., hi: 1. }, Some(&huge)).is_none());
        let old = retarget(1, false, &(&a / R::from_integer(2.into())));
        assert!(old.edge.as_ref().unwrap().exact_line.is_none());
        assert!(old.edge.as_ref().unwrap().end.exact_time().is_none());
    }

    #[test]
    fn delayed_queue_owns_its_value_proof_across_later_input_changes() {
        let a = level();
        let b = &a * R::from_integer(2.into());
        let mut history = Transition::new(0., 0.25, 0.2, 0.2).unwrap();
        write(&mut history, 0.1, &a, true);
        write(&mut history, 0.15, &b, true);
        assert_eq!(history.pending[0].3.as_ref(), Some(&a));
        assert_eq!(history.pending[1].3.as_ref(), Some(&b));
        history.advance_time(0.375).unwrap();
        assert_eq!(
            history.edge.as_ref().unwrap().exact_target.as_ref(),
            Some(&a)
        );
        assert_eq!(history.pending.front().unwrap().3.as_ref(), Some(&b));
        history.advance_time(0.425).unwrap();
        assert_eq!(
            history.edge.as_ref().unwrap().exact_target.as_ref(),
            Some(&b)
        );
        assert!(history.edge.as_ref().unwrap().end.exact_time().is_some());
    }

    #[test]
    fn failed_private_candidate_does_not_mutate_retained_rational_history() {
        let a = level();
        let accepted = retarget(1, true, &(&a / R::from_integer(2.into())));
        let snapshot = accepted.clone();
        for _ in 0..2 {
            let mut candidate = accepted.clone();
            assert!(candidate
                .advance_at_with_proofs(
                    0.175,
                    I::point(0.175),
                    0.,
                    I { lo: -1., hi: 1. },
                    true,
                    Some(&RootTime::point(0.175).unwrap()),
                    None,
                )
                .is_err());
            assert_eq!(accepted, snapshot);
        }
        let mut retry = accepted.clone();
        write(&mut retry, 0.175, &a, true);
        let mut clean = snapshot;
        write(&mut clean, 0.175, &a, true);
        assert_eq!(retry, clean);
        assert_eq!(
            accepted.edge.as_ref().unwrap().exact_target.as_ref(),
            Some(&(&a / R::from_integer(2.into())))
        );
    }
}

#[cfg(test)]
mod history_wrapped_queue_tests {
    use super::*;
    #[test]
    fn real_delayed_history_pop_and_push_reaches_wrapped_growth() {
        let w = crate::transition_source_plan::Work::limited([128, 8192, 1_000_000_000]);
        let mut history = Transition::history_enclosed(0., I::ZERO, 10., 1., 1., &w).unwrap();
        let advance = |h: &mut Transition, time: f64, target: f64| {
            h.advance_at_with_history_work(
                time,
                I::point(time),
                target,
                I::point(target),
                true,
                None,
                None,
                &w,
            )
        };
        for i in 1..=4 {
            advance(&mut history, i as f64, i as f64).unwrap();
        }
        let initial_capacity = history.pending.capacity();
        assert_eq!(history.pending.len(), initial_capacity);
        // The first real delayed activation pops the front. The new target then
        // fills that retained buffer from its tail, without cloning/normalizing it.
        advance(&mut history, 11., 5.).unwrap();
        assert_eq!(history.pending.len(), initial_capacity);
        assert!(!history.pending.as_slices().1.is_empty());
        let before = history
            .pending
            .iter()
            .map(|(d, v, b, _)| (d.bounds, *v, *b))
            .collect::<Vec<_>>();
        let (result, report) =
            crate::diagnostics::capture(Default::default(), || advance(&mut history, 11.5, 6.));
        result.unwrap();
        assert!(history.pending.capacity() > initial_capacity);
        assert_eq!(
            &history
                .pending
                .iter()
                .take(before.len())
                .map(|(d, v, b, _)| (d.bounds, *v, *b))
                .collect::<Vec<_>>(),
            &before
        );
        assert_eq!(history.pending.back().unwrap().0.bounds, I::point(21.5));
        assert_eq!(report.counters.get("history_storage_growth"), Some(&1));
        println!("real Transition wrapped growth: old_capacity={initial_capacity}, retained={}, new_capacity={}, used={}",before.len(),history.pending.capacity(),w.spent());
    }
}
