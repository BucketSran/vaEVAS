//! Exact physical epochs for independently certified constant-flow Idt states.
//! The binary64 calendar representative is never substituted for this anchor.
use super::*;
use crate::exact_source::history_paid::Paid;
use crate::transition_source_plan::Work;
use num_rational::BigRational as R;

pub(super) struct Epoch {
    anchor: R,
    end: R,
    states: Vec<Option<(R, R)>>,
    values: Vec<Option<Vec<R>>>,
    previous: Option<Arc<Epoch>>,
    owner: Work,
}
impl Drop for Epoch {
    fn drop(&mut self) {
        // A long accepted history must not recursively drop a linked prefix.
        let mut prior = self.previous.take();
        while let Some(value) = prior {
            match Arc::try_unwrap(value) {
                Ok(mut value) => prior = value.previous.take(),
                Err(_) => break,
            }
        }
    }
}
fn binary(value: f64, w: &Work) -> Result<Option<R>, Error> {
    let mut p = Paid::new(w);
    let v = p.binary(value);
    p.finish(v)
}
fn copy(value: &R, w: &Work) -> Result<Option<R>, Error> {
    let mut p = Paid::new(w);
    let v = p.copy(value);
    p.finish(v)
}
fn point(value: I, w: &Work) -> Result<Option<R>, Error> {
    if !value.finite() || value.lo != value.hi {
        return Ok(None);
    }
    binary(value.lo, w)
}
pub(super) fn enclosure(value: &R, w: &Work) -> Result<Option<I>, Error> {
    let mut p = Paid::new(w);
    let b = p.enclose(value);
    p.finish(b)
}
impl Epoch {
    pub(super) fn share(&self, w: &Work) -> Result<(), Error> {
        if !self.owner.same_owner(w) {
            return Err(Error::new(
                "invalid_ir",
                "continuous root epoch belongs to another request",
            ));
        }
        w.debit(2, 16)
    }
    pub(super) fn same(a: &Option<Arc<Self>>, b: &Option<Arc<Self>>) -> bool {
        match (a, b) {
            (None, None) => true,
            (Some(a), Some(b)) => Arc::ptr_eq(a, b),
            _ => false,
        }
    }
    pub(super) fn equal(
        a: &Option<Arc<Self>>,
        b: &Option<Arc<Self>>,
        w: &Work,
    ) -> Result<bool, Error> {
        w.debit(2, 0)?;
        let mut a = a.as_ref();
        let mut b = b.as_ref();
        loop {
            w.step()?;
            let (x, y) = match (a, b) {
                (None, None) => return Ok(true),
                (Some(x), Some(y)) => (x, y),
                _ => return Ok(false),
            };
            x.share(w)?;
            y.share(w)?;
            if Arc::ptr_eq(x, y) {
                return Ok(true);
            }
            if x.states.len() != y.states.len() || x.values.len() != y.values.len() {
                return Ok(false);
            }
            for (a, b) in [(&x.anchor, &y.anchor), (&x.end, &y.end)] {
                let mut p = Paid::new(w);
                let same = p.cmp(a, b);
                if p.finish(same)?.is_none_or(|v| !v.is_eq()) {
                    return Ok(false);
                }
            }
            for (a, b) in x.states.iter().zip(&y.states) {
                w.step()?;
                match (a, b) {
                    (Some((a, ar)), Some((b, br))) => {
                        for (a, b) in [(a, b), (ar, br)] {
                            let mut p = Paid::new(w);
                            let same = p.cmp(a, b);
                            if p.finish(same)?.is_none_or(|v| !v.is_eq()) {
                                return Ok(false);
                            }
                        }
                    }
                    (None, None) => (),
                    _ => return Ok(false),
                }
            }
            for (a, b) in x.values.iter().zip(&y.values) {
                w.step()?;
                match (a, b) {
                    (Some(a), Some(b)) if a.len() == b.len() => {
                        for (a, b) in a.iter().zip(b) {
                            let mut p = Paid::new(w);
                            let same = p.cmp(a, b);
                            if p.finish(same)?.is_none_or(|v| !v.is_eq()) {
                                return Ok(false);
                            }
                        }
                    }
                    (None, None) => (),
                    _ => return Ok(false),
                }
            }
            a = x.previous.as_ref();
            b = y.previous.as_ref();
        }
    }
    pub(super) fn build(
        flow: &LinearContinuous,
        anchor: &R,
        seeds: Option<&[Option<R>]>,
        previous: Option<&Arc<Self>>,
        w: &Work,
    ) -> Result<Option<Arc<Self>>, Error> {
        let Some(segment) = flow.segments.first() else {
            return Ok(None);
        };
        let count = flow.initial.len();
        w.debit(2, (count * 160 + flow.value_count * 32 + 256) as u64)?;
        if let Some(previous) = previous {
            previous.share(w)?;
        }
        let Some(anchor) = copy(anchor, w)? else {
            return Ok(None);
        };
        let Some(end) = binary(flow.stop, w)? else {
            return Ok(None);
        };
        let mut states = Vec::with_capacity(count);
        for index in 0..count {
            w.step()?;
            let row = &segment.matrix[index];
            w.debit(2, (row.len() + flow.segments.len() + 1) as u64)?;
            let mut eligible =
                flow.exact_states[index] && row[..row.len() - 1].iter().all(|c| c.zero());
            for other in flow.segments.iter() {
                w.debit(2, (row.len() + 1) as u64)?;
                if other.matrix[index] != *row {
                    eligible = false;
                }
            }
            let state = if eligible {
                let seed = if let Some(seeds) = seeds {
                    seeds
                        .get(index)
                        .and_then(Option::as_ref)
                        .map(|v| copy(v, w))
                        .transpose()?
                        .flatten()
                } else if flow.initial[index].lo == 0. && flow.initial[index].lo.is_sign_negative()
                {
                    None
                } else {
                    point(flow.initial[index], w)?
                };
                seed.zip(point(*row.last().unwrap(), w)?)
            } else {
                None
            };
            states.push(state);
        }
        if states.iter().all(Option::is_none) {
            return Ok(None);
        }
        let mut values = Vec::with_capacity(flow.value_count);
        for (index, row) in segment.values.iter().enumerate() {
            w.debit(2, (row.len() + flow.segments.len() + 1) as u64)?;
            let mut eligible = row[count..row.len() - 1].iter().all(|c| c.zero());
            for other in flow.segments.iter() {
                w.debit(2, (row.len() + 1) as u64)?;
                if other.values[index] != *row {
                    eligible = false;
                }
            }
            let coefficients = if eligible {
                w.debit(2, ((count + 1) * 64 + 32) as u64)?;
                let mut out = Vec::with_capacity(count + 1);
                let mut complete = true;
                for coefficient in row[..count].iter().chain(row.last()) {
                    w.step()?;
                    if let Some(coefficient) = point(*coefficient, w)? {
                        out.push(coefficient);
                    } else {
                        complete = false;
                        break;
                    }
                }
                complete.then_some(out)
            } else {
                None
            };
            values.push(coefficients);
        }
        Ok(Some(Arc::new(Self {
            anchor,
            end,
            states,
            values,
            previous: previous.cloned(),
            owner: w.clone(),
        })))
    }
    fn at<'a>(&'a self, time: &R, w: &Work) -> Result<Option<&'a Self>, Error> {
        self.share(w)?;
        let mut current = self;
        loop {
            w.step()?;
            let mut p = Paid::new(w);
            let order = p.cmp(time, &current.anchor);
            let Some(order) = p.finish(order)? else {
                return Ok(None);
            };
            if !order.is_lt() {
                let mut p = Paid::new(w);
                let order = p.cmp(time, &current.end);
                return Ok(p.finish(order)?.filter(|o| !o.is_gt()).map(|_| current));
            }
            let Some(prior) = current.previous.as_deref() else {
                return Ok(None);
            };
            current = prior;
        }
    }
    fn local_states(&self, time: &R, w: &Work) -> Result<Option<Vec<Option<R>>>, Error> {
        w.debit(2, (self.states.len() * 64 + 32) as u64)?;
        let mut p = Paid::new(w);
        let d = p.op(time, &self.anchor, '-');
        let Some(d) = p.finish(d)? else {
            return Ok(None);
        };
        let mut out = Vec::with_capacity(self.states.len());
        for state in &self.states {
            w.step()?;
            let value = if let Some((seed, rate)) = state {
                let mut p = Paid::new(w);
                let value = (|| {
                    let shift = p.op(rate, &d, '*')?;
                    p.op(seed, &shift, '+')
                })();
                p.finish(value)?
            } else {
                None
            };
            out.push(value);
        }
        Ok(Some(out))
    }
    pub(super) fn states_at(&self, time: &R, w: &Work) -> Result<Option<Vec<Option<R>>>, Error> {
        let Some(epoch) = self.at(time, w)? else {
            return Ok(None);
        };
        epoch.local_states(time, w)
    }
    pub(super) fn sample(
        &self,
        index: usize,
        time: &R,
        w: &Work,
    ) -> Result<Option<(f64, I)>, Error> {
        let Some(epoch) = self.at(time, w)? else {
            return Ok(None);
        };
        let Some(Some(row)) = epoch.values.get(index) else {
            return Ok(None);
        };
        let Some(states) = epoch.local_states(time, w)? else {
            return Ok(None);
        };
        let mut p = Paid::new(w);
        let value = (|| {
            let mut sum = p.copy(row.last()?)?;
            for (coefficient, state) in row[..row.len() - 1].iter().zip(&states) {
                p.pay(1)?;
                if num_traits::Zero::is_zero(coefficient) {
                    continue;
                }
                let term = p.op(coefficient, state.as_ref()?, '*')?;
                sum = p.op(&sum, &term, '+')?;
            }
            let bound = p.enclose(&sum)?;
            let nominal = p.nearest(&sum)?;
            Some((nominal, bound))
        })();
        p.finish(value)
    }
}

impl LinearContinuous {
    pub(super) fn physical_epoch(&self, w: &Work) -> Result<Option<Arc<Epoch>>, Error> {
        if let Some(epoch) = &self.root_epoch {
            epoch.share(w)?;
            return Ok(Some(epoch.clone()));
        }
        let Some(start) = binary(self.start, w)? else {
            return Ok(None);
        };
        Epoch::build(self, &start, None, None, w)
    }
    pub(super) fn install_physical_display(
        &mut self,
        epoch: &Arc<Epoch>,
        w: &Work,
    ) -> Result<(), Error> {
        epoch.share(w)?;
        let mut storage = (self.segments.len() * 96 + self.initial.len() * 16 + 128) as u64;
        for segment in self.segments.iter() {
            w.step()?;
            storage = storage.saturating_add((segment.initial.len() * 16 + 64) as u64);
            for rows in [&segment.matrix, &segment.values, &segment.derivatives] {
                storage = storage.saturating_add((rows.len() * 32 + 32) as u64);
                for row in rows {
                    w.step()?;
                    storage = storage.saturating_add((row.len() * 16 + 32) as u64);
                }
            }
        }
        w.debit(2, storage)?;
        let mut segments = Vec::with_capacity(self.segments.len());
        for segment in self.segments.iter() {
            w.step()?;
            let mut segment = segment.clone();
            let Some(time) = binary(segment.start, w)? else {
                return Err(Error::new(
                    "event_resolution",
                    "root epoch display time unavailable",
                ));
            };
            if let Some(states) = epoch.states_at(&time, w)? {
                for (slot, state) in segment.initial.iter_mut().zip(states) {
                    w.step()?;
                    if let Some(state) = state {
                        if let Some(bound) = enclosure(&state, w)? {
                            *slot = bound;
                        }
                    }
                }
            }
            segments.push(segment);
        }
        self.initial = segments[0].initial[..self.initial.len()].to_vec();
        self.segments = Arc::new(segments);
        Ok(())
    }
    pub(super) fn sample_physical_root(
        &self,
        index: usize,
        root: &crate::exact_source::RootTime,
    ) -> Result<Option<(f64, I)>, Error> {
        let Some(w) = self.context.trajectory.procedure_work() else {
            return Ok(None);
        };
        let Some(epoch) = self.physical_epoch(w)? else {
            return Ok(None);
        };
        epoch.sample(index, root.rational(), w)
    }
}

// Time-valued measurement states do not rebind the physical clock. The old
// selection context uses proofs only in physical Select guards; prove their
// absence before skipping an irrelevant proof-context reconstruction.
pub(super) fn no_time_selection(context: &Context, w: &Work) -> Result<bool, Error> {
    fn plain(e: &Expression, w: &Work) -> Result<bool, Error> {
        w.step()?;
        Ok(match e {
            Expression::Affine { .. } | Expression::State { .. } | Expression::Operator { .. } => {
                true
            }
            Expression::Add { left, right }
            | Expression::Multiply { left, right }
            | Expression::Divide { left, right } => {
                let a = plain(left, w)?;
                let b = plain(right, w)?;
                a && b
            }
            Expression::Power { base, .. } => plain(base, w)?,
            _ => false,
        })
    }
    for op in &context.program.operators {
        w.step()?;
        match op {
            OperatorSpec::Idt {
                input, reset: None, ..
            } => {
                if !plain(input, w)? {
                    return Ok(false);
                }
            }
            _ => return Ok(false),
        }
    }
    for c in &context.program.contributions {
        w.step()?;
        if !plain(&c.rhs, w)? {
            return Ok(false);
        }
    }
    for b in &context.program.step_bounds {
        w.step()?;
        if !plain(&b.active, w)? || !plain(&b.value, w)? {
            return Ok(false);
        }
    }
    Ok(true)
}
