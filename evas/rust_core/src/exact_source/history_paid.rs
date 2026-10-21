//! History consumers borrow the original request owner. Every rational copy,
//! comparison and operation is funded before execution; Budget keeps its old cap.
use super::event_prefix_fees as fees;
use super::*;
use crate::{ir::Error, transition_source_plan::Work};

pub(crate) struct Paid<'a> {
    work: &'a Work,
    local: Budget,
    error: Option<Error>,
}
impl<'a> Paid<'a> {
    pub(crate) fn new(work: &'a Work) -> Self {
        Self {
            work,
            local: Budget(0),
            error: work.debit(2, 0).err(),
        }
    }
    pub(crate) fn finish<T>(self, result: Option<T>) -> Result<Option<T>, Error> {
        match self.error {
            Some(error) => Err(error),
            None => Ok(result),
        }
    }
    pub(crate) fn accept<T>(&mut self, result: Result<T, Error>) -> Option<T> {
        match result {
            Ok(value) => Some(value),
            Err(error) => {
                self.error = Some(error);
                None
            }
        }
    }
    pub(crate) fn pay(&mut self, n: u64) -> Option<()> {
        if self.error.is_some() {
            return None;
        }
        match self.work.debit(2, n) {
            Ok(()) => Some(()),
            Err(error) => {
                self.error = Some(error);
                None
            }
        }
    }
    fn push<T>(&mut self, out: &mut Vec<T>, value: T) -> Option<()> {
        let slots = std::mem::size_of::<T>().div_ceil(std::mem::size_of::<usize>()) as u64;
        if out.len() == out.capacity() {
            let next = out.capacity().max(1).checked_mul(2)?;
            // Explicit capacity policy: pay allocated slots and possible moves
            // of retained elements before reserve_exact can move their storage.
            self.pay(
                (next as u64)
                    .saturating_add(out.len() as u64)
                    .saturating_mul(slots),
            )?;
            out.reserve_exact(next - out.len());
        }
        self.pay(slots)?;
        out.push(value);
        Some(())
    }
    pub(crate) fn copy(&mut self, v: &R) -> Option<R> {
        self.pay(fees::copy(fees::width(v)))?;
        crate::diagnostics::counter("history_exact_rational_copy", 1);
        Some(v.clone())
    }
    pub(crate) fn binary(&mut self, v: f64) -> Option<R> {
        self.pay(1)?;
        if !v.is_finite() {
            return None;
        }
        // Reduced dyadic width, without allocating a rational to determine its fee.
        let raw = v.to_bits();
        let exponent = ((raw >> 52) & 2047) as i64;
        let mantissa = (raw & ((1u64 << 52) - 1)) | if exponent == 0 { 0 } else { 1u64 << 52 };
        let width = if mantissa == 0 {
            1
        } else {
            let shift = mantissa.trailing_zeros() as i64;
            let power = if exponent == 0 {
                -1074
            } else {
                exponent - 1023 - 52
            } + shift;
            ((64 - (mantissa >> shift).leading_zeros()) as i64 + power.max(0))
                .max(1 + (-power).max(0)) as u64
        };
        self.pay(fees::binary(width))?;
        binary(v)
    }
    pub(crate) fn cmp(&mut self, a: &R, b: &R) -> Option<std::cmp::Ordering> {
        if self.error.is_some() {
            return None;
        }
        let result = super::rational_order_with_work(a, b, self.work);
        self.accept(result)
    }
    pub(crate) fn op(&mut self, a: &R, b: &R, op: char) -> Option<R> {
        self.pay(2)?;
        if op == '/' && b.is_zero() {
            return None;
        }
        let bits = fees::width(a)
            .saturating_add(fees::width(b))
            .saturating_add(1);
        self.pay(fees::op(bits))?;
        self.local.check(match op {
            '+' => a + b,
            '-' => a - b,
            '*' => a * b,
            '/' => a / b,
            _ => return None,
        })
    }
    pub(crate) fn checked(&mut self, value: R) -> Option<R> {
        self.pay(1)?;
        self.local.check(value)
    }
    pub(crate) fn floor(&mut self, value: &R) -> Option<R> {
        self.pay(2)?;
        self.pay(fees::op(fees::width(value).saturating_add(1)))?;
        self.local.check(value.floor())
    }
    pub(crate) fn nearest(&mut self, v: &R) -> Option<f64> {
        let limbs = fees::l(fees::width(v).saturating_add(56));
        self.pay(
            limbs
                .saturating_pow(2)
                .saturating_mul(16)
                .saturating_add(limbs.saturating_mul(64))
                .saturating_add(64),
        )?;
        v.to_f64()
    }
    pub(crate) fn enclose(&mut self, v: &R) -> Option<I> {
        if self.error.is_some() {
            return None;
        }
        let result = super::enclosure_with_work(v, self.work);
        self.accept(result)?
    }
    fn lookup(&mut self, nodes: &[usize], node: usize) -> Option<usize> {
        for (i, n) in nodes.iter().enumerate() {
            self.pay(1)?;
            if *n == node {
                return Some(i);
            }
        }
        None
    }
    fn value(&mut self, curve: &Curve, time: &R) -> Option<R> {
        // Explicit paid binary search; std partition_point cannot propagate a debit failure.
        let (mut lo, mut hi) = (0, curve.0.len());
        while lo < hi {
            let m = lo + (hi - lo) / 2;
            if self.cmp(&curve.0[m].0, time)?.is_lt() {
                lo = m + 1
            } else {
                hi = m
            }
        }
        let (end, b) = curve.0.get(lo)?;
        if self.cmp(end, time)?.is_eq() {
            return self.copy(b);
        }
        let (start, a) = curve.0.get(lo.checked_sub(1)?)?;
        let delta = self.op(b, a, '-')?;
        let elapsed = self.op(time, start, '-')?;
        let duration = self.op(end, start, '-')?;
        let fraction = self.op(&elapsed, &duration, '/')?;
        let change = self.op(&delta, &fraction, '*')?;
        self.op(a, &change, '+')
    }
    #[allow(clippy::too_many_arguments)]
    fn eval(
        &mut self,
        e: &Expression,
        nodes: &[usize],
        sources: &[Option<Curve>],
        time: &R,
        states: &TimeProofs,
        depth: usize,
        count: &mut usize,
    ) -> Option<R> {
        self.pay(1)?;
        *count += 1;
        if depth > MAX_DEPTH || *count > MAX_EXPR_NODES {
            return None;
        }
        match e {
            Expression::State { state } => {
                let mut found = None;
                for (i, value) in states {
                    self.pay(1)?;
                    if i == state {
                        found = Some(value);
                        break;
                    }
                }
                self.copy(&found?.0)
            }
            Expression::Affine { constant, terms } => {
                if terms.len() > MAX_POINTS {
                    return None;
                }
                let mut out = self.binary(*constant)?;
                for t in terms {
                    self.pay(1)?;
                    if t.node == 0 {
                        continue;
                    }
                    let k = self.lookup(nodes, t.node)?;
                    let value = self.value(sources.get(k)?.as_ref()?, time)?;
                    let c = self.binary(t.coefficient)?;
                    let product = self.op(&c, &value, '*')?;
                    out = self.op(&out, &product, '+')?;
                }
                Some(out)
            }
            Expression::Add { left, right } | Expression::Multiply { left, right } => {
                let a = self.eval(left, nodes, sources, time, states, depth + 1, count)?;
                let b = self.eval(right, nodes, sources, time, states, depth + 1, count)?;
                self.op(
                    &a,
                    &b,
                    if matches!(e, Expression::Add { .. }) {
                        '+'
                    } else {
                        '*'
                    },
                )
            }
            _ => None,
        }
    }
    fn dependencies(
        &mut self,
        e: &Expression,
        out: &mut Vec<usize>,
        depth: usize,
        count: &mut usize,
    ) -> Option<bool> {
        self.pay(1)?;
        *count += 1;
        if depth > MAX_DEPTH || *count > MAX_EXPR_NODES {
            return None;
        }
        match e {
            Expression::State { .. } => Some(false),
            Expression::Affine { terms, .. } => {
                if terms.len() > MAX_POINTS {
                    return None;
                }
                let mut varying = false;
                for t in terms {
                    self.pay(1)?;
                    if t.node != 0 {
                        self.push(out, t.node)?;
                        varying = true
                    }
                }
                if out.len() > MAX_POINTS {
                    return None;
                }
                Some(varying)
            }
            Expression::Add { left, right } | Expression::Multiply { left, right } => {
                let a = self.dependencies(left, out, depth + 1, count)?;
                let b = self.dependencies(right, out, depth + 1, count)?;
                if matches!(e, Expression::Multiply { .. }) && a && b {
                    None
                } else {
                    Some(a || b)
                }
            }
            _ => None,
        }
    }
    fn sort(&mut self, values: &mut Vec<R>) -> Option<()> {
        // Fallible stable merge sort: comparisons and reference slots are paid;
        // rationals move only after the complete ordering has been funded.
        self.pay(values.len() as u64 * 2)?;
        let mut order: Vec<usize> = (0..values.len()).collect();
        let mut temp = vec![0; values.len()];
        let mut width = 1;
        while width < order.len() {
            let mut start = 0;
            while start < order.len() {
                let mid = (start + width).min(order.len());
                let end = (mid + width).min(order.len());
                let (mut a, mut b) = (start, mid);
                for slot in &mut temp[start..end] {
                    self.pay(1)?;
                    let take = a < mid
                        && (b == end || !self.cmp(&values[order[a]], &values[order[b]])?.is_gt());
                    *slot = if take {
                        let i = order[a];
                        a += 1;
                        i
                    } else {
                        let i = order[b];
                        b += 1;
                        i
                    };
                }
                start = end;
            }
            std::mem::swap(&mut order, &mut temp);
            width = width.checked_mul(2)?;
        }
        let rational_slots = std::mem::size_of::<R>().div_ceil(std::mem::size_of::<usize>()) as u64;
        let option_slots =
            std::mem::size_of::<Option<R>>().div_ceil(std::mem::size_of::<usize>()) as u64;
        self.pay(
            (values.len() as u64)
                .saturating_mul(option_slots.saturating_add(rational_slots.saturating_mul(2))),
        )?;
        let mut old: Vec<Option<R>> = std::mem::take(values).into_iter().map(Some).collect();
        *values = Vec::with_capacity(order.len());
        for i in order {
            values.push(old[i].take()?)
        }
        let mut unique = 0;
        for i in 0..values.len() {
            self.pay(1)?;
            if unique == 0 || !self.cmp(&values[unique - 1], &values[i])?.is_eq() {
                self.pay(rational_slots.saturating_mul(3))?;
                values.swap(unique, i);
                unique += 1
            }
        }
        values.truncate(unique);
        Some(())
    }
    fn expression(
        &mut self,
        e: &Expression,
        nodes: &[usize],
        sources: &[Option<Curve>],
        stop: f64,
        states: &TimeProofs,
    ) -> Option<Curve> {
        let mut deps = Vec::new();
        self.dependencies(e, &mut deps, 0, &mut 0)?;
        let stop = self.binary(stop)?;
        let zero = self.binary(0.)?;
        let stop_copy = self.copy(&stop)?;
        self.pay(2)?;
        let mut knots = vec![zero, stop_copy];
        for node in deps {
            let k = self.lookup(nodes, node)?;
            let curve = sources.get(k)?.as_ref()?;
            for (t, _) in &curve.0 {
                self.pay(1)?;
                if self.cmp(t, &stop)?.is_lt() {
                    let t = self.copy(t)?;
                    self.push(&mut knots, t)?
                }
            }
            if knots.len() > MAX_POINTS * MAX_POINTS {
                return None;
            }
        }
        self.sort(&mut knots)?;
        if knots.len() > MAX_POINTS {
            return None;
        }
        let mut result = Vec::new();
        for t in knots {
            let value = self.eval(e, nodes, sources, &t, states, 0, &mut 0)?;
            self.push(&mut result, (t, value))?
        }
        Some(Curve(result))
    }
}
impl Curve {
    pub(crate) fn at_root_history(&self, root: &RootTime, w: &Work) -> Result<Option<R>, Error> {
        let mut p = Paid::new(w);
        let result = p.value(self, root.rational());
        p.finish(result)
    }
    pub(crate) fn root_in_history(
        &self,
        segment: [f64; 2],
        ends: [I; 2],
        bounds: I,
        w: &Work,
    ) -> Result<Option<RootTime>, Error> {
        let mut p = Paid::new(w);
        let result = (|| {
            let start = p.binary(segment[0])?;
            let end = p.binary(segment[1])?;
            for (t, _) in &self.0 {
                p.pay(1)?;
                if p.cmp(&start, t)?.is_lt() && p.cmp(t, &end)?.is_lt() {
                    return None;
                }
            }
            let a = p.value(self, &start)?;
            let b = p.value(self, &end)?;
            for (bounds, value) in ends.iter().zip([&a, &b]) {
                if !bounds.finite() {
                    return None;
                }
                let lo = p.binary(bounds.lo)?;
                let hi = p.binary(bounds.hi)?;
                if p.cmp(&lo, value)?.is_gt() || p.cmp(value, &hi)?.is_gt() {
                    return None;
                }
            }
            p.pay(1)?;
            if a.is_zero() || p.cmp(&a, &b)?.is_eq() {
                return None;
            }
            let duration = p.op(&end, &start, '-')?;
            let change = p.op(&b, &a, '-')?;
            let numerator = p.op(&a, &duration, '*')?;
            let shift = p.op(&numerator, &change, '/')?;
            let time = p.op(&start, &shift, '-')?;
            if !bounds.finite() || !p.cmp(&start, &time)?.is_lt() || p.cmp(&time, &end)?.is_gt() {
                return None;
            }
            let lo = p.binary(bounds.lo)?;
            let hi = p.binary(bounds.hi)?;
            if p.cmp(&lo, &time)?.is_gt() || p.cmp(&time, &hi)?.is_gt() {
                return None;
            }
            Some(RootTime(time))
        })();
        p.finish(result)
    }
    pub(crate) fn crossings_history(
        &self,
        direction: i8,
        stop: f64,
        w: &Work,
    ) -> Result<Option<Vec<Crossing>>, Error> {
        let mut p = Paid::new(w);
        let result = (|| {
            let stop_value = p.binary(stop)?;
            let zero = p.binary(0.)?;
            let mut out = Vec::new();
            for pair in self.0.windows(2) {
                p.pay(1)?;
                let (a, x) = &pair[0];
                let (b, y) = &pair[1];
                p.pay(4)?;
                if x.is_zero() {
                    continue;
                }
                let sign = if y.is_zero() {
                    if x.is_positive() {
                        -1
                    } else {
                        1
                    }
                } else if x.is_positive() != y.is_positive() {
                    if y.is_positive() {
                        1
                    } else {
                        -1
                    }
                } else {
                    continue;
                };
                if direction != 0 && direction != sign {
                    continue;
                }
                let duration = p.op(b, a, '-')?;
                let change = p.op(y, x, '-')?;
                let numerator = p.op(x, &duration, '*')?;
                let shift = p.op(&numerator, &change, '/')?;
                let time = p.op(a, &shift, '-')?;
                if !p.cmp(&time, &zero)?.is_gt() || p.cmp(&time, &stop_value)?.is_gt() {
                    continue;
                }
                let segment = [p.enclose(a)?, p.enclose(b)?];
                let ends = [p.enclose(x)?, p.enclose(y)?];
                let window = I {
                    lo: p.enclose(&time)?.lo,
                    hi: p.enclose(b)?.hi.min(p.nearest(&stop_value)?),
                };
                // Keep the complete original representative window. It may
                // cross a nonbinary segment corner and need its outgoing slope.
                // The existing staged reader pays actual exact endpoint/pair
                // work on the same ledger instead of a whole-curve reservation.
                let reader = p.accept(StagedRange::new(self, window, w))?;
                let (reader, _) = p.accept(reader.endpoint(false))??;
                let (reader, _) = p.accept(reader.endpoint(true))??;
                let (_, slope) = p.accept(reader.finish())??;
                p.push(
                    &mut out,
                    Crossing {
                        time: RootTime(time),
                        segment,
                        ends,
                        slope,
                    },
                )?;
            }
            Some(out)
        })();
        p.finish(result)
    }
    pub(crate) fn identity_history(&self, w: &Work) -> Result<bool, Error> {
        let mut p = Paid::new(w);
        let result = (|| {
            for (t, v) in &self.0 {
                p.pay(1)?;
                if !p.cmp(t, v)?.is_eq() {
                    return Some(false);
                }
            }
            Some(true)
        })();
        Ok(p.finish(result)?.unwrap_or(false))
    }
    pub(crate) fn expression_history(
        e: &Expression,
        nodes: &[usize],
        sources: &[Option<Curve>],
        stop: f64,
        states: &TimeProofs,
        w: &Work,
    ) -> Result<Option<Self>, Error> {
        let mut p = Paid::new(w);
        let result = p.expression(e, nodes, sources, stop, states);
        p.finish(result)
    }
    pub(crate) fn sign_history(&self, root: &RootTime, w: &Work) -> Result<Option<i8>, Error> {
        let mut p = Paid::new(w);
        let result = (|| {
            let v = p.value(self, &root.0)?;
            p.pay(2)?;
            Some(if v.is_zero() {
                0
            } else if v.is_positive() {
                1
            } else {
                -1
            })
        })();
        p.finish(result)
    }
    pub(crate) fn roots_history(&self, w: &Work) -> Result<Option<Vec<RootTime>>, Error> {
        let mut p = Paid::new(w);
        let result = (|| {
            let mut out = Vec::new();
            for pair in self.0.windows(2) {
                p.pay(1)?;
                let (a, x) = &pair[0];
                let (b, y) = &pair[1];
                if !p.cmp(a, b)?.is_lt() {
                    return None;
                }
                let ac = p.copy(a)?;
                let bc = p.copy(b)?;
                p.push(&mut out, ac)?;
                p.push(&mut out, bc)?;
                p.pay(4)?;
                if x.is_zero() || y.is_zero() || x.is_positive() == y.is_positive() {
                    continue;
                }
                let duration = p.op(b, a, '-')?;
                let delta = p.op(y, x, '-')?;
                let numerator = p.op(x, &duration, '*')?;
                let shift = p.op(&numerator, &delta, '/')?;
                let root = p.op(a, &shift, '-')?;
                if !p.cmp(&root, a)?.is_gt() || !p.cmp(&root, b)?.is_lt() {
                    return None;
                }
                p.enclose(&root)?;
                p.push(&mut out, root)?;
            }
            p.sort(&mut out)?;
            p.pay(out.len() as u64)?;
            Some(out.into_iter().map(RootTime).collect())
        })();
        p.finish(result)
    }
    pub(crate) fn affine_history(&self, time: I, w: &Work) -> Result<Option<(R, R)>, Error> {
        let mut p = Paid::new(w);
        let result = (|| {
            let lo = p.binary(time.lo)?;
            let hi = p.binary(time.hi)?;
            match p.cmp(&lo, &hi)? {
                std::cmp::Ordering::Equal => return Some((p.value(self, &lo)?, p.binary(0.)?)),
                std::cmp::Ordering::Greater => return None,
                _ => (),
            }
            let a = p.value(self, &lo)?;
            let b = p.value(self, &hi)?;
            let duration = p.op(&hi, &lo, '-')?;
            let delta = p.op(&b, &a, '-')?;
            let slope = p.op(&delta, &duration, '/')?;
            let shift = p.op(&slope, &lo, '*')?;
            let intercept = p.op(&a, &shift, '-')?;
            for (t, v) in &self.0 {
                p.pay(1)?;
                if p.cmp(&lo, t)?.is_lt() && p.cmp(t, &hi)?.is_lt() {
                    let product = p.op(&slope, t, '*')?;
                    let value = p.op(&intercept, &product, '+')?;
                    if !p.cmp(&value, v)?.is_eq() {
                        return None;
                    }
                }
            }
            Some((intercept, slope))
        })();
        p.finish(result)
    }
}

pub(crate) fn affine_range(line: (R, R), time: I, w: &Work) -> Result<Option<I>, Error> {
    let mut p = Paid::new(w);
    let result = (|| {
        let (a, b) = line;
        let tlo = p.binary(time.lo)?;
        let thi = p.binary(time.hi)?;
        let blo = p.op(&b, &tlo, '*')?;
        let bhi = p.op(&b, &thi, '*')?;
        let vlo = p.op(&a, &blo, '+')?;
        let vhi = p.op(&a, &bhi, '+')?;
        Some(p.enclose(&vlo)?.hull(p.enclose(&vhi)?))
    })();
    p.finish(result)
}
pub(crate) fn affine_root(a: R, b: R, bounds: I, w: &Work) -> Result<Option<RootTime>, Error> {
    let mut p = Paid::new(w);
    let result = (|| {
        let zero = p.binary(0.)?;
        let negative = p.op(&zero, &a, '-')?;
        let root = p.op(&negative, &b, '/')?;
        let lo = p.binary(bounds.lo)?;
        let hi = p.binary(bounds.hi)?;
        if p.cmp(&lo, &root)?.is_gt() || p.cmp(&root, &hi)?.is_gt() {
            return None;
        }
        Some(RootTime(root))
    })();
    p.finish(result)
}

pub(crate) fn root(value: R) -> RootTime {
    RootTime(value)
}

// A lexical range read borrows an already validated physical shaped curve and
// its request ledger. Left, right and pair phases share the original local cap.
pub(crate) struct StagedRange<'a> {
    curve: &'a Curve,
    paid: Paid<'a>,
    time: I,
    ends: Option<(R, R)>,
    left: Option<I>,
    right: Option<I>,
    phase: u8,
}
impl<'a> StagedRange<'a> {
    pub(crate) fn new(curve: &'a Curve, time: I, work: &'a Work) -> Result<Self, Error> {
        work.debit(2, 0)?;
        work.debit(
            2,
            (std::mem::size_of::<Self>().div_ceil(std::mem::size_of::<usize>()) + 8) as u64,
        )?;
        Ok(Self {
            curve,
            paid: Paid::new(work),
            time,
            ends: None,
            left: None,
            right: None,
            phase: 0,
        })
    }
    pub(crate) fn endpoint(mut self, right: bool) -> Result<Option<(Self, I)>, Error> {
        let result = (|| {
            self.paid.pay(8)?;
            if self.phase != u8::from(right) {
                return None;
            }
            if !right {
                let lo = self.paid.binary(self.time.lo)?;
                let hi = self.paid.binary(self.time.hi)?;
                if self.paid.cmp(&lo, &hi)?.is_gt() {
                    return None;
                }
                self.ends = Some((lo, hi));
            }
            let ends = self.ends.as_ref()?;
            self.paid.pay(1)?;
            #[cfg(test)]
            crate::diagnostics::counter("strict_range_value_body", 1);
            let v = self
                .paid
                .value(self.curve, if right { &ends.1 } else { &ends.0 })?;
            let bounds = self.paid.enclose(&v)?;
            self.paid.pay(4)?;
            if right {
                self.right = Some(bounds);
            } else {
                self.left = Some(bounds);
            }
            self.phase += 1;
            Some(bounds)
        })();
        match result {
            Some(bounds) => Ok(Some((self, bounds))),
            None => self.paid.finish(None),
        }
    }
    pub(crate) fn finish(mut self) -> Result<Option<(I, I)>, Error> {
        let result = (|| {
            self.paid.pay(8)?;
            if self.phase != 2 {
                return None;
            }
            let (lo, hi) = self.ends.as_ref()?;
            let point = self.paid.cmp(lo, hi)?.is_eq();
            let start = bound(&mut self.paid, self.curve, lo, !point)?
                .checked_sub(1)
                .or_else(|| point.then_some(0))?;
            let end = bound(&mut self.paid, self.curve, hi, point)?
                .min(self.curve.0.len().checked_sub(1)?);
            self.paid.pay(4)?;
            let mut values = self.left?.hull(self.right?);
            let mut slope: Option<I> = None;
            for index in start..end {
                self.paid.pay(8)?;
                #[cfg(test)]
                crate::diagnostics::counter("strict_range_pair_body", 1);
                let (a, x) = &self.curve.0[index];
                let (b, y) = &self.curve.0[index + 1];
                let overlaps = (self.paid.cmp(a, hi)?.is_lt() && self.paid.cmp(b, lo)?.is_gt())
                    || (point && !self.paid.cmp(a, lo)?.is_gt() && !self.paid.cmp(lo, b)?.is_gt());
                if overlaps {
                    let duration = self.paid.op(b, a, '-')?;
                    let change = self.paid.op(y, x, '-')?;
                    let d = self.paid.op(&change, &duration, '/')?;
                    let derivative = self.paid.enclose(&d)?;
                    self.paid.pay(4)?;
                    slope = Some(slope.map_or(derivative, |old| old.hull(derivative)));
                }
                if self.paid.cmp(lo, b)?.is_lt() && self.paid.cmp(b, hi)?.is_lt() {
                    let corner = self.paid.enclose(y)?;
                    self.paid.pay(2)?;
                    values = values.hull(corner);
                }
            }
            Some((values, slope.unwrap_or(I::ZERO)))
        })();
        self.paid.finish(result)
    }
}
fn bound(paid: &mut Paid<'_>, curve: &Curve, time: &R, upper: bool) -> Option<usize> {
    let (mut lo, mut hi) = (0, curve.0.len());
    while lo < hi {
        paid.pay(4)?;
        let mid = lo + (hi - lo) / 2;
        let order = paid.cmp(&curve.0[mid].0, time)?;
        crate::diagnostics::counter("shaped_range_search_compare", 1);
        if order.is_lt() || upper && order.is_eq() {
            lo = mid + 1;
        } else {
            hi = mid;
        }
    }
    Some(lo)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn subnormal_curve_work_is_paid_and_exhausted_retries_do_no_copies() {
        // Same original PWL geometry as the public Standards counterexample.
        let points: Vec<_> = std::iter::once([0., 0.])
            .chain((1..=510).map(|i| [f64::from_bits(i), 0.]))
            .chain(std::iter::once([1., 1.]))
            .collect();
        let sources: Vec<_> = (0..60).map(|_| Curve::source(&points)).collect();
        let nodes: Vec<_> = (1..=60).collect();
        let e = Expression::Affine {
            constant: 0.,
            terms: nodes
                .iter()
                .map(|&node| crate::ir::Term {
                    node,
                    coefficient: 1.,
                })
                .collect(),
        };
        let w = Work::limited([128, 8192, 1_000_000_000]);
        let error = Curve::expression_history(&e, &nodes, &sources, 1., &Default::default(), &w)
            .err()
            .expect("actual rational work exhausts the unchanged default quota");
        assert_eq!(error.kind, "step_budget");
        let used = w.spent();
        assert!(used > 1_000_000_000);
        for _ in 0..2 {
            let (result, report) = crate::diagnostics::capture(Default::default(), || {
                Curve::expression_history(&e, &nodes, &sources, 1., &Default::default(), &w)
            });
            assert_eq!(result.err().unwrap().kind, "step_budget");
            assert_eq!(w.spent(), used);
            assert!(report.counters.is_empty());
            assert!(report.stages.is_empty());
        }
    }
    #[test]
    fn a_copy_is_denied_before_cloning_large_subnormal_storage() {
        let value = binary(f64::from_bits(1)).unwrap();
        let w = Work::limited([128, 8192, 0]);
        let (result, report) = crate::diagnostics::capture(Default::default(), || {
            let mut p = Paid::new(&w);
            let value = p.copy(&value);
            p.finish(value)
        });
        assert_eq!(result.err().unwrap().kind, "step_budget");
        assert!(report.counters.is_empty());
    }
}

#[cfg(test)]
mod crossing_staged_contract_tests {
    use super::*;

    fn fraction(n: i64, d: i64) -> R {
        R::new(n.into(), d.into())
    }
    fn nonbinary_corner() -> Curve {
        Curve(vec![
            (fraction(0, 1), fraction(-1, 1)),
            (fraction(1, 3), fraction(0, 1)),
            (fraction(2, 3), fraction(2, 1)),
            (fraction(1, 1), fraction(-1, 1)),
        ])
    }
    fn assert_same(old: &[Crossing], new: &[Crossing]) {
        assert_eq!(old.len(), new.len());
        for (old, new) in old.iter().zip(new) {
            assert_eq!(old.time, new.time);
            assert_eq!(old.segment, new.segment);
            assert_eq!(old.ends, new.ends);
            assert_eq!(old.slope, new.slope);
        }
    }

    #[test]
    fn staged_crossing_nonbinary_corner_keeps_outgoing_slope_and_every_original_field() {
        let curve = nonbinary_corner();
        let old = curve.crossings(0, 1.).unwrap();
        let work = Work::default();
        let new = curve.crossings_history(0, 1., &work).unwrap().unwrap();
        assert_same(&old, &new);
        // The mathematical roots are1/3 and8/9. Around the first root,
        // binary64's representative window crosses the true corner1/3.
        // The original incoming slope3 and outgoing slope6 must both survive.
        assert_eq!(new[0].time.rational(), &fraction(1, 3));
        assert_eq!(new[1].time.rational(), &fraction(8, 9));
        assert_eq!(new[0].slope, I { lo: 3., hi: 6. });
        assert_eq!(new[1].slope, I::point(-9.));
        assert_eq!(new[0].ends, [I::point(-1.), I::ZERO]);
    }

    #[test]
    fn staged_crossing_direction_stop_clip_and_point_boundary_preserve_old_range() {
        let curve = nonbinary_corner();
        let lower = (1.0_f64 / 3.0).next_down();
        let nearest = 1.0_f64 / 3.0;
        let upper = nearest.next_up();
        for stop in [lower, nearest, upper, 0.5, 1.] {
            for direction in [-1, 0, 1] {
                let old = curve.crossings(direction, stop).unwrap();
                let new = curve
                    .crossings_history(direction, stop, &Work::default())
                    .unwrap()
                    .unwrap();
                assert_same(&old, &new);
                assert!(new
                    .iter()
                    .all(|c| c.time.rational() <= &binary(stop).unwrap()));
            }
        }
        assert!(curve
            .crossings_history(1, nearest, &Work::default())
            .unwrap()
            .unwrap()
            .is_empty());
        let point = Curve(vec![
            (fraction(0, 1), fraction(-1, 1)),
            (fraction(1, 2), fraction(0, 1)),
            (fraction(1, 1), fraction(2, 1)),
        ]);
        let old = point.crossings(1, 0.5).unwrap();
        let new = point
            .crossings_history(1, 0.5, &Work::default())
            .unwrap()
            .unwrap();
        assert_same(&old, &new);
        assert_eq!(new[0].time.rational(), &fraction(1, 2));
        // At an exact point, the old range contract includes both sides.
        assert_eq!(new[0].slope, I { lo: 2., hi: 4. });
    }

    #[test]
    fn staged_crossing_actual_work_exhaustion_stays_on_same_owner_for_two_retries() {
        let curve = nonbinary_corner();
        let work = Work::limited([128, 8192, 20_000_000]);
        let retry = work.clone();
        let mut complete = 0;
        loop {
            match curve.crossings_history(0, 1., &work) {
                Ok(Some(_)) => complete += 1,
                Ok(None) => panic!("valid exact curve must not lose its certificate"),
                Err(error) => {
                    assert_eq!(error.kind, "step_budget");
                    break;
                }
            }
        }
        assert!(complete > 0);
        let mut spent = work.spent();
        for _ in 0..2 {
            assert_eq!(
                curve.crossings_history(0, 1., &retry).err().unwrap().kind,
                "step_budget"
            );
            assert!(work.same_owner(&retry));
            assert!(work.spent() >= spent);
            spent = work.spent();
        }
    }
}

#[cfg(test)]
mod paid_fast_contract_tests {
    use super::*;
    use std::cmp::Ordering;

    fn raw(n: i64, d: i64) -> R {
        R::new_raw(n.into(), d.into())
    }
    #[test]
    fn paid_fast_order_matches_pinned_sign_negative_denominator_and_zero_branches() {
        for (a, b, expected, key) in [
            (
                raw(1, 3),
                raw(2, 3),
                Ordering::Less,
                "exact_order_equal_denominator",
            ),
            (
                raw(-1, 3),
                raw(-2, 3),
                Ordering::Greater,
                "exact_order_equal_denominator",
            ),
            (
                raw(1, -3),
                raw(2, -3),
                Ordering::Greater,
                "exact_order_equal_denominator",
            ),
            (
                raw(-1, -3),
                raw(-2, -3),
                Ordering::Less,
                "exact_order_equal_denominator",
            ),
            (
                raw(1, 3),
                raw(1, 5),
                Ordering::Greater,
                "exact_order_equal_numerator",
            ),
            (
                raw(-1, 3),
                raw(-1, 5),
                Ordering::Less,
                "exact_order_equal_numerator",
            ),
            (
                raw(1, -3),
                raw(1, -5),
                Ordering::Less,
                "exact_order_equal_numerator",
            ),
            (
                raw(-1, -3),
                raw(-1, -5),
                Ordering::Greater,
                "exact_order_equal_numerator",
            ),
            (
                raw(0, 3),
                raw(0, -5),
                Ordering::Equal,
                "exact_order_equal_numerator",
            ),
            (
                raw(0, 3),
                raw(-1, 3),
                Ordering::Greater,
                "exact_order_equal_denominator",
            ),
        ] {
            let w = Work::default();
            let (result, report) = crate::diagnostics::capture(Default::default(), || {
                super::super::rational_order_with_work(&a, &b, &w)
            });
            assert_eq!(result.unwrap(), expected);
            assert_eq!(expected, a.cmp(&b));
            assert_eq!(report.counters.get(key), Some(&1));
            assert_eq!(report.counters.get("exact_order_generic_fallback"), None);
            assert!(w.spent() > 0);
        }
    }
    #[test]
    fn paid_fast_order_adjacent_third_uses_paid_exact_cross() {
        let a = raw(1, 3);
        let b = binary(1. / 3.).unwrap();
        let w = Work::default();
        let (result, report) = crate::diagnostics::capture(Default::default(), || {
            let mut p = Paid::new(&w);
            let answer = p.cmp(&a, &b);
            p.finish(answer)
        });
        assert_eq!(result.unwrap(), Some(Ordering::Greater));
        assert_eq!(a.cmp(&b), Ordering::Greater);
        assert_eq!(report.counters.get("exact_order_bounded_cross"), Some(&1));
        assert_eq!(
            report.counters.get("forcing_owned_cross_comparisons"),
            Some(&1)
        );
        assert_eq!(report.counters.get("exact_order_generic_fallback"), None);
    }
    #[test]
    fn paid_fast_enclose_retains_tight_subnormal_boxes_and_old_none() {
        let tiny = f64::from_bits(1);
        for value in [
            raw(0, 1),
            raw(-1, 4),
            raw(1, 3),
            raw(-1, 3),
            binary(tiny).unwrap(),
            binary(-tiny).unwrap(),
            binary(f64::MAX).unwrap(),
            binary(tiny).unwrap() / raw(2, 1),
            R::from_integer(raw(1, 1).numer() << 2048usize),
        ] {
            let old = enclosure(&value);
            let w = Work::default();
            let mut p = Paid::new(&w);
            let answer = p.enclose(&value);
            assert_eq!(p.finish(answer).unwrap(), old);
        }
        let w = Work::default();
        let (_, report) = crate::diagnostics::capture(Default::default(), || {
            let mut p = Paid::new(&w);
            let answer = p.enclose(&raw(-1, 4));
            p.finish(answer)
        });
        assert_eq!(
            report.counters.get("forcing_exact_dyadic_enclosure"),
            Some(&1)
        );
    }
    #[test]
    fn paid_fast_order_and_enclose_share_actual_exhaustion_and_sticky_retries() {
        for comparator in [false, true] {
            let w = Work::limited([128, 8192, 2_000_000]);
            let alias = w.clone();
            let a = raw(1, 3);
            let b = binary(1. / 3.).unwrap();
            let mut successful = 0;
            loop {
                let mut p = Paid::new(&w);
                let result = if comparator {
                    p.cmp(&a, &b).map(|_| ())
                } else {
                    p.enclose(&a).map(|_| ())
                };
                match p.finish(result) {
                    Ok(Some(())) => successful += 1,
                    Err(e) => {
                        assert_eq!(e.kind, "step_budget");
                        break;
                    }
                    _ => panic!("finite fixture must produce a comparison/box"),
                }
            }
            assert!(successful > 0);
            let mut spent = w.spent();
            for _ in 0..2 {
                let mut p = Paid::new(&w);
                let result = if comparator {
                    p.cmp(&a, &b).map(|_| ())
                } else {
                    p.enclose(&a).map(|_| ())
                };
                assert_eq!(p.finish(result).unwrap_err().kind, "step_budget");
                assert!(w.same_owner(&alias));
                assert!(w.spent() >= spent);
                spent = w.spent();
            }
        }
    }
}

#[cfg(test)]
mod paid_cross_contract_tests {
    use super::*;
    use std::cmp::Ordering;
    fn raw(n: i64, d: i64) -> R {
        R::new_raw(n.into(), d.into())
    }
    #[test]
    fn paid_cross_generic_signs_and_different_equal_representations_are_exact() {
        for (a, b, expected) in [
            (raw(1, 3), binary(1. / 3.).unwrap(), Ordering::Greater),
            (raw(-1, 3), binary(-1. / 3.).unwrap(), Ordering::Less),
            (raw(-1, 3), raw(2, 5), Ordering::Less),
            (raw(1, 3), raw(-2, 5), Ordering::Greater),
            (raw(2, 6), raw(3, 9), Ordering::Equal),
            (raw(-2, 6), raw(-3, 9), Ordering::Equal),
        ] {
            let w = Work::default();
            let (result, report) = crate::diagnostics::capture(Default::default(), || {
                super::super::rational_order_with_work(&a, &b, &w)
            });
            assert_eq!(result.unwrap(), expected);
            assert_eq!(expected, a.cmp(&b));
            assert_eq!(report.counters.get("exact_order_bounded_cross"), Some(&1));
            assert_eq!(report.counters.get("exact_order_generic_fallback"), None);
        }
    }
    #[test]
    fn paid_cross_original_width_cap_retains_full_generic_fallback() {
        for (power, cross) in [(2047usize, true), (2048usize, false)] {
            let m = raw(1, 1).numer() << power;
            let n = &m + 2;
            let a = R::new_raw(&m + 1, &m - 1);
            let b = R::new_raw(&n + 1, &n - 1);
            let w = Work::default();
            let (result, report) = crate::diagnostics::capture(Default::default(), || {
                super::super::rational_order_with_work(&a, &b, &w)
            });
            // (m+1)/(m-1) = 1+2/(m-1), strictly larger for smaller m.
            assert_eq!(result.unwrap(), Ordering::Greater);
            assert_eq!(a.cmp(&b), Ordering::Greater);
            assert_eq!(
                report
                    .counters
                    .get("exact_order_bounded_cross")
                    .copied()
                    .unwrap_or(0),
                u64::from(cross)
            );
            assert_eq!(
                report
                    .counters
                    .get("exact_order_generic_fallback")
                    .copied()
                    .unwrap_or(0),
                u64::from(!cross)
            );
            if !cross {
                assert!(w.spent() >= fees::cmp(fees::width(&a).max(fees::width(&b))));
            }
        }
    }
    #[test]
    fn paid_cross_nonpositive_denominators_keep_pinned_old_boundary() {
        for (a, b) in [
            (raw(1, -3), raw(2, 5)),
            (raw(-1, -3), raw(2, -5)),
            (raw(1, 0), raw(2, 1)),
            (raw(1, 0), raw(2, 0)),
        ] {
            let w = Work::default();
            let (result, report) = crate::diagnostics::capture(Default::default(), || {
                // new_raw zero denominators are not legal source rationals.
                // Preserve even the pinned library's panic boundary privately.
                Ok((
                    std::panic::catch_unwind(|| super::super::rational_order_with_work(&a, &b, &w)),
                    std::panic::catch_unwind(|| a.cmp(&b)),
                ))
            });
            let (actual, old) = result.unwrap();
            match (actual, old) {
                (Ok(actual), Ok(old)) => assert_eq!(actual.unwrap(), old),
                (Err(_), Err(_)) => (),
                _ => panic!("nonpositive denominator boundary changed"),
            }
            assert_eq!(report.counters.get("exact_order_bounded_cross"), None);
            assert_eq!(report.counters.get("forcing_owned_cross_comparisons"), None);
        }
    }
    #[test]
    fn paid_cross_reservation_failure_precedes_products_and_retries_stay_rejected() {
        let a = raw(1, 3);
        let b = binary(1. / 3.).unwrap();
        let w = Work::limited([128, 8192, 300]);
        let alias = w.clone();
        let mut spent = 0;
        for _ in 0..3 {
            let (result, report) = crate::diagnostics::capture(Default::default(), || {
                super::super::rational_order_with_work(&a, &b, &w)
            });
            assert_eq!(result.unwrap_err().kind, "step_budget");
            assert_eq!(report.counters.get("forcing_owned_cross_comparisons"), None);
            assert_eq!(report.counters.get("exact_order_bounded_cross"), None);
            assert!(w.same_owner(&alias));
            assert!(w.spent() >= spent);
            spent = w.spent();
        }
        // Natural exhaustion through repeated successful real comparisons is
        // independently retained in paid_fast_order_and_enclose_share_actual_exhaustion_and_sticky_retries.
    }
}
