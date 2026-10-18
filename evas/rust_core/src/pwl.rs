//! Continuous PWL inputs and zero arrivals, independent of event state mutation.
use crate::event_accuracy::unresolved;
use crate::interval::{equal_products, sum_products_sign, Interval as I};
use crate::ir::{Error, TransientInputs};

#[derive(Clone)]
pub(crate) struct Root {
    pub bounds: I,
    slope: I,
    segment: [f64; 2],
    ends: [I; 2],
    source_time: Option<crate::exact_source::RootTime>,
}

impl Root {
    fn from_physical(crossing: crate::exact_source::Crossing) -> Option<Self> {
        Some(Self {
            bounds: crossing.time.bounds()?,
            slope: crossing.slope,
            segment: [crossing.segment[0].lo, crossing.segment[1].hi],
            ends: crossing.ends,
            source_time: Some(crossing.time),
        })
    }
    pub(crate) fn with_source_time(mut self, curve: Option<&crate::exact_source::Curve>) -> Self {
        if let Some(time) = curve.and_then(|c| c.root_in(self.segment, self.ends, self.bounds)) {
            if let Some(bounds) = time.bounds() {
                self.bounds = I {
                    lo: self.bounds.lo.max(bounds.lo),
                    hi: self.bounds.hi.min(bounds.hi),
                };
                self.source_time = Some(time);
            }
        }
        self
    }

    pub(crate) fn rational_time(&self) -> Option<crate::exact_source::RootTime> {
        self.source_time.clone().or_else(|| {
            crate::exact_source::RootTime::point_ends(self.segment, self.ends, self.bounds)
        })
    }

    /// Search representable times using an exact sign predicate on the original
    /// numerator a*t1 - a*t + b*t - b*t0. No rounded time differences enter it.
    fn refine_representable(&mut self) {
        let [a, b] = self.ends;
        if a.lo != a.hi || b.lo != b.hi || a.lo == b.lo {
            return;
        }
        let sign = |time| {
            sum_products_sign(&[
                (a.lo, self.segment[1]),
                (-a.lo, time),
                (b.lo, time),
                (-b.lo, self.segment[0]),
            ])
        };
        let guess = self.segment[0] + (a.lo / (a.lo - b.lo)) * (self.segment[1] - self.segment[0]);
        let lower = self.bounds.lo.max(self.segment[0]).max(0.0);
        let upper = self.bounds.hi.min(self.segment[1]);
        if !lower.is_finite() || !upper.is_finite() || lower > upper {
            return;
        }
        for time in [guess, lower, upper] {
            if time.is_finite() && time >= lower && time <= upper && sign(time) == Some(0) {
                self.bounds = I::point(time);
                return;
            }
        }
        // Nonnegative finite binary64 bit patterns are monotonic. At most 64
        // bisections cover every representable time in the certified interval.
        let (mut lo, mut hi) = (lower.to_bits(), upper.to_bits());
        while lo <= hi {
            let mid = lo + (hi - lo) / 2;
            let time = f64::from_bits(mid);
            let Some(value) = sign(time) else {
                return;
            };
            if value == 0 {
                self.bounds = I::point(time);
                return;
            }
            let before_root = if b.lo > a.lo { value < 0 } else { value > 0 };
            if before_root {
                lo = mid + 1;
            } else {
                if mid == 0 {
                    return;
                }
                hi = mid - 1;
            }
        }
    }

    /// Compare roots using original source proofs or point endpoint guards.
    /// Enclosed projections without either proof retain ambiguity refusal.
    pub(crate) fn exact_order(&self, other: &Self) -> Option<std::cmp::Ordering> {
        if self.source_time.is_some() || other.source_time.is_some() {
            return Some(self.rational_time()?.order(&other.rational_time()?));
        }
        let [a, b] = self.ends;
        let [c, d] = other.ends;
        if [a, b, c, d].iter().any(|v| v.lo != v.hi) || a.lo == b.lo || c.lo == d.lo {
            return None;
        }
        let sign = crate::exact_time::sum_triples_sign(&[
            (a.lo, self.segment[1], c.lo),
            (-a.lo, self.segment[1], d.lo),
            (-b.lo, self.segment[0], c.lo),
            (b.lo, self.segment[0], d.lo),
            (-c.lo, other.segment[1], a.lo),
            (c.lo, other.segment[1], b.lo),
            (d.lo, other.segment[0], a.lo),
            (-d.lo, other.segment[0], b.lo),
        ])?;
        Some(
            (if (a.lo > b.lo) == (c.lo > d.lo) {
                sign
            } else {
                -sign
            })
            .cmp(&0),
        )
    }

    pub(crate) fn clock_order(
        &self,
        clock: crate::exact_time::Clock,
    ) -> Option<std::cmp::Ordering> {
        self.clock_delta_order(clock, 0.)
    }
    pub(crate) fn local_bounds(&self, clock: crate::exact_time::Clock) -> Option<I> {
        if let Some(time) = &self.source_time {
            return time.local_bounds(clock);
        }
        crate::exact_time::enclose_zero(|delta| {
            self.clock_delta_order(clock, delta).map(|o| match o {
                std::cmp::Ordering::Less => 1,
                std::cmp::Ordering::Equal => 0,
                std::cmp::Ordering::Greater => -1,
            })
        })
    }
    pub(crate) fn clock_delta_order(
        &self,
        clock: crate::exact_time::Clock,
        delta: f64,
    ) -> Option<std::cmp::Ordering> {
        if let Some(time) = &self.source_time {
            return time.clock_delta_order(clock, delta);
        }
        let [a, b] = self.ends;
        if a.lo != a.hi || b.lo != b.hi || a.lo == b.lo {
            return None;
        }
        let sign = crate::exact_time::sum_triples_sign(&[
            (a.lo, self.segment[1], 1.),
            (-a.lo, clock.start, 1.),
            (-a.lo, clock.period, clock.index as f64),
            (b.lo, clock.start, 1.),
            (b.lo, clock.period, clock.index as f64),
            (-b.lo, self.segment[0], 1.),
            (-a.lo, delta, 1.),
            (b.lo, delta, 1.),
        ])?;
        // Increasing guards are positive after their zero; decreasing guards
        // reverse the sign. Return root compared with clock, not vice versa.
        Some((if b.lo > a.lo { -sign } else { sign }).cmp(&0))
    }

    pub fn accepts(&self, time: f64, ttol: f64, etol: f64) -> bool {
        let delay = I::point(time) - self.bounds;
        let expression_error = self.slope * delay;
        time >= self.bounds.hi
            && time <= self.segment[1]
            && delay.finite()
            && delay.hi <= ttol
            && expression_error.finite()
            && expression_error.magnitude() <= etol
    }

    pub fn coincides(&self, other: &Self, identical_guard: bool) -> bool {
        if let Some(order) = self.exact_order(other) {
            return order == std::cmp::Ordering::Equal;
        }
        if self.bounds.lo == self.bounds.hi && self.bounds == other.bounds {
            return true;
        }
        if self.segment != other.segment {
            return false;
        }
        if identical_guard {
            return true;
        }
        let [a, b] = self.ends;
        let [c, d] = other.ends;
        [a, b, c, d].iter().all(|v| v.lo == v.hi) && equal_products(a.lo, d.lo, c.lo, b.lo)
    }
}

#[derive(Clone)]
pub(crate) struct Trajectory {
    pub(crate) config: TransientInputs,
    pub(crate) knots: Vec<f64>,
    pub(crate) solver_points: Vec<f64>,
    source_errors: Vec<f64>,
    pub(crate) exact_sources: Vec<Option<crate::exact_source::Curve>>,
    original_source_count: usize,
}

impl Trajectory {
    /// Prepay all storage copied by Clone, including original rational limbs.
    pub(crate) fn charge_source_copy(
        &self,
        work: &crate::transition_source_plan::Work,
    ) -> Result<(), Error> {
        self.charge_source_copy_named(
            work,
            [
                "selected_ln_ast_visits",
                "selected_ln_copy_items",
                "selected_ln_work_debit",
            ],
        )
    }
    pub(crate) fn charge_source_copy_named(
        &self,
        work: &crate::transition_source_plan::Work,
        names: [&'static str; 3],
    ) -> Result<(), Error> {
        let debit = |items: usize| -> Result<(), Error> {
            work.debit(2, items as u64)?;
            crate::diagnostics::counter(names[1], items);
            crate::diagnostics::counter(names[2], items);
            Ok(())
        };
        debit(
            16 + self.knots.len()
                + self.solver_points.len()
                + self.source_errors.len()
                + self.config.strobetimes.len()
                + self.config.output_times.len(),
        )?;
        for points in &self.config.pwl {
            debit(1 + 2 * points.len())?;
        }
        if let Some(errors) = &self.config.pwl_errors_v {
            for error in errors {
                debit(2)?;
                if let Some(shape) = error.shape() {
                    for knot in &shape.exact_knots {
                        debit(3 + knot.time_numerator.len() + knot.time_denominator.len())?;
                    }
                }
            }
        }
        for curve in &self.exact_sources {
            debit(1)?;
            if let Some(curve) = curve {
                curve.charge_source_copy(work, names)?;
            }
        }
        Ok(())
    }

    // Root-demand slopes apply only to physical PWL inputs, not generated
    // sources whose enclosures may include an independent time-varying error.
    pub(crate) fn has_only_physical_inputs(&self) -> bool {
        self.original_source_count == self.config.pwl.len()
            && self.source_errors.iter().all(|e| *e == 0.)
    }

    /// Separate from the slope-demand zero-band predicate. Only validated
    /// original physical curves qualify; appended sources are never providers.
    pub(crate) fn forcing_shaped_inputs(
        &self,
        work: &crate::transition_source_plan::Work,
    ) -> Result<Vec<usize>, Error> {
        work.debit(
            2,
            (4 + self.config.pwl.len() + self.source_errors.len()) as u64,
        )?;
        if self.original_source_count != self.config.pwl.len() {
            return Err(Error::new(
                "unsupported_forcing_scope",
                "forcing provider is not original physical input",
            ));
        }
        let mut shaped = Vec::new();
        for (k, &error) in self.source_errors.iter().enumerate() {
            if error != 0. {
                if !self.is_shaped(k) || self.exact_sources[k].is_none() {
                    return Err(Error::new(
                        "unsupported_forcing_scope",
                        "forcing nonzero band requires validated original exact shape",
                    ));
                }
                shaped.push(k);
            }
        }
        Ok(shaped)
    }
    /// An existing exact predicate helper evaluates every original affine term.
    /// Prepay its shaped Curve::value reads as well as its separate 200k AST
    /// reservation. This is an upper bound even if that helper later fails.
    pub(crate) fn forcing_predicate_reads(
        &self,
        e: &crate::ir::Expression,
        mapping: &[usize],
        time: f64,
        work: &crate::transition_source_plan::Work,
    ) -> Result<(), Error> {
        use crate::ir::Expression as E;
        work.step()?;
        match e {
            E::Affine { terms, .. } => {
                work.debit(
                    2,
                    terms.len().saturating_mul(mapping.len().saturating_add(1)) as u64,
                )?;
                for term in terms {
                    if let Some(k) = mapping.iter().position(|n| *n == term.node) {
                        if self.is_shaped(k) {
                            self.exact_sources[k]
                                .as_ref()
                                .ok_or_else(|| {
                                    unresolved("forcing predicate physical curve missing")
                                })?
                                .charge_forcing_read(work, time, false)?;
                            crate::diagnostics::counter("forcing_predicate_curve_reads_prepaid", 1);
                        }
                    }
                }
            }
            E::Add { left, right } | E::Multiply { left, right } => {
                self.forcing_predicate_reads(left, mapping, time, work)?;
                self.forcing_predicate_reads(right, mapping, time, work)?;
            }
            _ => {
                return Err(unresolved(
                    "forcing predicate not resolved before exact read prepayment",
                ))
            }
        }
        Ok(())
    }
    /// Prepay each actual arbitrary-precision physical-source read. There is
    /// no nominal fallback when an admitted shaped provider lacks a certificate.
    pub(crate) fn forcing_values_bounds(
        &self,
        time: f64,
        work: &crate::transition_source_plan::Work,
    ) -> Result<(Vec<f64>, Vec<I>), Error> {
        work.debit(2, (8 + self.config.pwl.len() * 32) as u64)?;
        let mut values = Vec::new();
        let mut bounds = Vec::new();
        for (k, source) in self.config.pwl.iter().enumerate() {
            if self.is_shaped(k) {
                let curve = self.exact_sources[k]
                    .as_ref()
                    .ok_or_else(|| unresolved("forcing physical curve missing"))?;
                if let Some((v, b)) = curve.try_forcing_point(time, work)? {
                    values.push(v);
                    bounds.push(b);
                    continue;
                }
                crate::diagnostics::counter("forcing_owned_strict_fallback", 1);
                curve.charge_forcing_read(work, time, false)?;
                crate::diagnostics::counter("forcing_curve_actual_point_calls", 1);
                let (v, b) = curve
                    .at(time)
                    .ok_or_else(|| unresolved("forcing physical point has no certificate"))?;
                values.push(v);
                bounds.push(b);
                continue;
            }
            work.debit(2, source.len() as u64)?;
            let j = source.partition_point(|p| p[0] < time);
            if source[j][0] == time {
                values.push(source[j][1]);
                bounds.push(I::point(source[j][1]));
                continue;
            }
            let [start, a] = source[j - 1];
            let [end, b] = source[j];
            let f = (time - start) / (end - start);
            values.push(if a == b { a } else { (1. - f) * a + f * b });
            let fraction = (I::point(time) - I::point(start)) / (I::point(end) - I::point(start));
            bounds.push(I::point(a) + (I::point(b) - I::point(a)) * fraction);
        }
        Ok((values, bounds))
    }
    /// A conservative full-request physical value box, with no slope demand.
    /// Validated PWL segments are convex combinations of their original knot
    /// ordinates. Include every knot, even after stop: this may widen the box
    /// but cannot omit an extremum. This is not a local range certificate.
    pub(crate) fn forcing_request_value_bounds(
        &self,
        work: &crate::transition_source_plan::Work,
    ) -> Result<Vec<I>, Error> {
        self.forcing_shaped_inputs(work)?;
        // Source lookup, Option access, Vec storage and each output copy.
        work.debit(
            2,
            (self.config.pwl.len() as u64)
                .saturating_mul(8)
                .saturating_add(4),
        )?;
        let mut result = Vec::new();
        for (k, source) in self.config.pwl.iter().enumerate() {
            let shape = self
                .config
                .pwl_errors_v
                .as_ref()
                .and_then(|errors| errors[k].shape());
            if shape.is_some() && self.exact_sources[k].is_none() {
                return Err(unresolved(
                    "forcing global box requires validated physical shape",
                ));
            }
            let count = shape.map_or(source.len(), |s| s.exact_knots.len());
            // All knot reads, point construction, min/max and counters are
            // prepaid before reading the first ordinate, including on retry.
            work.debit(2, (count as u64).saturating_mul(8).saturating_add(4))?;
            let mut bounds: Option<I> = None;
            let mut include = |v: f64| {
                crate::diagnostics::counter("forcing_global_value_knots", 1);
                let point = I::point(v);
                bounds = Some(bounds.map_or(point, |old| old.hull(point)));
            };
            if let Some(shape) = shape {
                for knot in &shape.exact_knots {
                    include(knot.value_v);
                }
            } else {
                for knot in source {
                    include(knot[1]);
                }
            }
            result.push(
                bounds.ok_or_else(|| unresolved("forcing global box has no original knots"))?,
            );
        }
        Ok(result)
    }
    // Retain the strict paid local value/slope certificate; the new global
    // value-only consumer deliberately does not request this operation.
    #[cfg_attr(not(test), allow(dead_code))]
    pub(crate) fn forcing_range(
        &self,
        time: I,
        work: &crate::transition_source_plan::Work,
    ) -> Result<(Vec<I>, Vec<I>), Error> {
        if !time.finite() || time.lo < 0.0 || time.hi > self.config.stop || time.lo > time.hi {
            return Err(Error::new(
                "event_resolution",
                "invalid guard time interval",
            ));
        }
        let left = self.forcing_values_bounds(time.lo, work)?.1;
        let right = self.forcing_values_bounds(time.hi, work)?.1;
        let mut values: Vec<_> = left.iter().zip(right).map(|(&a, b)| a.hull(b)).collect();
        let mut derivatives = Vec::new();
        for (k, source) in self.config.pwl.iter().enumerate() {
            work.debit(2, source.len().saturating_add(4) as u64)?;
            if self.is_shaped(k) {
                let curve = self.exact_sources[k]
                    .as_ref()
                    .ok_or_else(|| unresolved("forcing physical curve missing"))?;
                curve.charge_forcing_read(work, time.lo, true)?;
                curve.charge_forcing_read(work, time.hi, true)?;
                crate::diagnostics::counter("forcing_curve_actual_range_calls", 1);
                let (physical_values, physical_slope) = self.exact_sources[k]
                    .as_ref()
                    .and_then(|curve| curve.range(time))
                    .ok_or_else(|| unresolved("cannot bound original source shape"))?;
                values[k] = physical_values;
                derivatives.push(physical_slope);
                continue;
            }
            let mut slope = None;
            for pair in source.windows(2) {
                if pair[0][0] < time.hi && pair[1][0] > time.lo
                    || time.lo == time.hi && pair[0][0] <= time.lo && time.lo <= pair[1][0]
                {
                    let d = (I::point(pair[1][1]) - I::point(pair[0][1]))
                        / (I::point(pair[1][0]) - I::point(pair[0][0]));
                    slope = Some(slope.map_or(d, |previous: I| previous.hull(d)));
                }
            }
            for &[t, v] in source {
                if t > time.lo && t < time.hi {
                    values[k] = values[k].hull(
                        I::point(v)
                            + I {
                                lo: -self.source_errors[k],
                                hi: self.source_errors[k],
                            },
                    );
                }
            }
            derivatives.push(slope.unwrap_or(I::ZERO));
        }
        Ok((values, derivatives))
    }
    pub(crate) fn range(&self, time: I) -> Result<(Vec<I>, Vec<I>), Error> {
        if !time.finite() || time.lo < 0.0 || time.hi > self.config.stop || time.lo > time.hi {
            return Err(Error::new(
                "event_resolution",
                "invalid guard time interval",
            ));
        }
        let left = self.value_bounds(time.lo);
        let right = self.value_bounds(time.hi);
        let mut values: Vec<_> = left.iter().zip(right).map(|(&a, b)| a.hull(b)).collect();
        let mut derivatives = Vec::new();
        for (k, source) in self.config.pwl.iter().enumerate() {
            if self.is_shaped(k) {
                let (physical_values, physical_slope) = self.exact_sources[k]
                    .as_ref()
                    .and_then(|curve| curve.range(time))
                    .ok_or_else(|| unresolved("cannot bound original source shape"))?;
                values[k] = physical_values;
                derivatives.push(physical_slope);
                continue;
            }
            let mut slope = None;
            for pair in source.windows(2) {
                if pair[0][0] < time.hi && pair[1][0] > time.lo
                    || time.lo == time.hi && pair[0][0] <= time.lo && time.lo <= pair[1][0]
                {
                    let d = (I::point(pair[1][1]) - I::point(pair[0][1]))
                        / (I::point(pair[1][0]) - I::point(pair[0][0]));
                    slope = Some(slope.map_or(d, |previous: I| previous.hull(d)));
                }
            }
            for &[t, v] in source {
                if t > time.lo && t < time.hi {
                    values[k] = values[k].hull(
                        I::point(v)
                            + I {
                                lo: -self.source_errors[k],
                                hi: self.source_errors[k],
                            },
                    );
                }
            }
            derivatives.push(slope.unwrap_or(I::ZERO));
        }
        Ok((values, derivatives))
    }
    pub(crate) fn new(config: TransientInputs, driven_count: usize) -> Result<Self, Error> {
        let invalid = || {
            Error::new("invalid_inputs", "PWL sources must start at 0, strictly increase and cover stop; output times must strictly increase within [0,stop]; stop/max_step must be positive and finite")
        };
        if !config.stop.is_finite()
            || config.stop <= 0.0
            || !config.max_step.is_finite()
            || config.max_step <= 0.0
            || config.pwl.len() != driven_count
            || config.strobetimes.len() > 100_000
            || config
                .strobetimes
                .iter()
                .any(|t| !t.is_finite() || *t < 0.0 || *t > config.stop)
            || config.strobetimes.windows(2).any(|p| p[0] >= p[1])
            || config.output_times.is_empty()
            || config
                .output_times
                .iter()
                .any(|t| !t.is_finite() || *t < 0.0 || *t > config.stop)
            || config.output_times.windows(2).any(|p| p[0] >= p[1])
        {
            return Err(invalid());
        }
        let mut knots = vec![0.0, config.stop];
        for source in &config.pwl {
            if source.len() < 2
                || source[0][0] != 0.0
                || source.last().unwrap()[0] < config.stop
                || source.iter().flatten().any(|v| !v.is_finite())
                || source.windows(2).any(|p| p[0][0] >= p[1][0])
            {
                return Err(invalid());
            }
            knots.extend(source.iter().map(|p| p[0]).filter(|t| *t < config.stop));
        }
        knots.sort_by(f64::total_cmp);
        knots.dedup();
        let source_errors = match &config.pwl_errors_v {
            Some(errors)
                if errors.len() == config.pwl.len()
                    && errors
                        .iter()
                        .all(|e| e.bound().is_finite() && e.bound() >= 0.) =>
            {
                errors.iter().map(|e| e.bound()).collect::<Vec<_>>()
            }
            Some(_) => return Err(Error::new(
                "invalid_inputs",
                "pwl_errors_V must match PWL sources and contain nonnegative finite voltage bounds",
            )),
            None => vec![0.0; config.pwl.len()],
        };
        let exact_sources = config
            .pwl
            .iter()
            .zip(&source_errors)
            .enumerate()
            .map(|(index, (p, error))| {
                if let Some(shape) = config
                    .pwl_errors_v
                    .as_ref()
                    .and_then(|errors| errors[index].shape())
                {
                    crate::exact_source::Curve::shaped(shape, p, config.stop)
                        .map(Some)
                        .ok_or_else(|| {
                            Error::new(
                                "invalid_inputs",
                                "invalid source shape or insufficient voltage error bound",
                            )
                        })
                } else if *error == 0. {
                    Ok(crate::exact_source::Curve::source(p))
                } else {
                    Ok(None)
                }
            })
            .collect::<Result<Vec<_>, Error>>()?;
        let mut solver_points = knots.clone();
        solver_points.extend(&config.strobetimes);
        solver_points.sort_by(f64::total_cmp);
        solver_points.dedup();
        Ok(Self {
            solver_points,
            original_source_count: config.pwl.len(),
            exact_sources,
            config,
            knots,
            source_errors,
        })
    }

    fn is_shaped(&self, index: usize) -> bool {
        index < self.original_source_count
            && self
                .config
                .pwl_errors_v
                .as_ref()
                .and_then(|errors| errors.get(index))
                .and_then(|error| error.shape())
                .is_some()
    }

    /// Shape-aware guards must use their complete physical source partition.
    /// Unknown/non-affine source expressions retain a conservative refusal.
    pub(crate) fn shaped_roots(
        &self,
        guard: &crate::ir::Expression,
        projected_guard: Option<&crate::ir::Expression>,
        input_nodes: &[usize],
        active: &[usize],
        direction: i8,
        after: Option<f64>,
    ) -> Result<Option<Vec<Root>>, Error> {
        if !active.iter().any(|&index| self.is_shaped(index)) {
            return Ok(None);
        }
        let curve = self
            .original_guard_curve(guard, input_nodes)
            .or_else(|| self.original_guard_curve(projected_guard?, input_nodes))
            .ok_or_else(|| unresolved("cannot certify guard on shaped original sources"))?;
        let crossings = curve
            .crossings(direction, self.config.stop)
            .ok_or_else(|| unresolved("cannot enumerate physical source crossings"))?;
        let mut roots = Vec::new();
        for crossing in crossings {
            let root = Root::from_physical(crossing)
                .ok_or_else(|| unresolved("cannot enclose physical source crossing"))?;
            if after.is_some_and(|time| root.bounds.hi <= time) {
                continue;
            }
            roots.push(root);
        }
        Ok(Some(roots))
    }

    pub(crate) fn add_enclosed_source(
        &mut self,
        points: Vec<[f64; 2]>,
        error: f64,
    ) -> Result<(), Error> {
        if !error.is_finite()
            || error < 0.0
            || points.len() < 2
            || points[0][0] != 0.0
            || points.last().unwrap()[0] < self.config.stop
            || points.iter().flatten().any(|v| !v.is_finite())
            || points.windows(2).any(|p| p[0][0] >= p[1][0])
        {
            return Err(Error::new(
                "waveform_accuracy",
                "invalid enclosed clamp source",
            ));
        }
        self.knots.extend(
            points
                .iter()
                .map(|p| p[0])
                .filter(|t| *t < self.config.stop),
        );
        self.knots.sort_by(f64::total_cmp);
        self.knots.dedup();
        self.solver_points = self.knots.clone();
        self.solver_points.extend(&self.config.strobetimes);
        self.solver_points.sort_by(f64::total_cmp);
        self.solver_points.dedup();
        self.exact_sources.push(if error == 0.0 {
            crate::exact_source::Curve::source(&points)
        } else {
            None
        });
        self.config.pwl.push(points);
        self.source_errors.push(error);
        Ok(())
    }

    /// Only the request's original inputs may establish an event time. A later
    /// generated/clipped source is not made original merely by having a curve.
    pub(crate) fn original_guard_curve(
        &self,
        guard: &crate::ir::Expression,
        input_nodes: &[usize],
    ) -> Option<crate::exact_source::Curve> {
        self.original_guard_curve_until(guard, input_nodes, self.config.stop)
    }

    /// A local integration horizon may precede a source segment's end. Use the
    /// retained original curve to certify that full segment, without changing
    /// the integration horizon or extrapolating beyond any source's domain.
    pub(crate) fn original_guard_curve_until(
        &self,
        guard: &crate::ir::Expression,
        input_nodes: &[usize],
        end: f64,
    ) -> Option<crate::exact_source::Curve> {
        if !end.is_finite() || end < 0.0 {
            return None;
        }
        crate::exact_source::Curve::expression(
            guard,
            input_nodes.get(..self.original_source_count)?,
            &self.exact_sources[..self.original_source_count],
            end,
        )
    }

    pub(crate) fn original_guard_curve_with_states(
        &self,
        guard: &crate::ir::Expression,
        input_nodes: &[usize],
        end: f64,
        states: &crate::exact_source::TimeProofs,
    ) -> Option<crate::exact_source::Curve> {
        if !end.is_finite() || end < 0.0 {
            return None;
        }
        crate::exact_source::Curve::expression_with_states(
            guard,
            input_nodes.get(..self.original_source_count)?,
            &self.exact_sources[..self.original_source_count],
            end,
            states,
        )
    }

    /// Compare retained original source trees, never rounded/generated nodes.
    pub(crate) fn original_predicate_sign(
        &self,
        left: &crate::ir::Expression,
        right: &crate::ir::Expression,
        input_nodes: &[usize],
        time: f64,
    ) -> Option<i8> {
        if !time.is_finite() || time < 0.0 || time > self.config.stop {
            return None;
        }
        crate::exact_source::predicate_sign(
            left,
            right,
            input_nodes.get(..self.original_source_count)?,
            &self.exact_sources[..self.original_source_count],
            time,
        )
    }

    pub(crate) fn values(&self, time: f64) -> Vec<f64> {
        self.config
            .pwl
            .iter()
            .enumerate()
            .map(|(index, source)| {
                if self.is_shaped(index) {
                    if let Some((value, _)) =
                        self.exact_sources[index].as_ref().and_then(|c| c.at(time))
                    {
                        return value;
                    }
                }
                let index = source.partition_point(|p| p[0] < time);
                if source[index][0] == time {
                    return source[index][1];
                }
                let [start, a] = source[index - 1];
                let [end, b] = source[index];
                // A flat segment is the supplied value itself. Weighted
                // interpolation can move a threshold neighbor by one ULP.
                if a == b {
                    return a;
                }
                let fraction = (time - start) / (end - start);
                (1.0 - fraction) * a + fraction * b
            })
            .collect()
    }

    pub(crate) fn input_knots(&self, inputs: &[usize]) -> Vec<f64> {
        let mut knots = vec![0.0, self.config.stop];
        for &input in inputs {
            knots.extend(
                self.config.pwl[input]
                    .iter()
                    .map(|p| p[0])
                    .filter(|t| *t < self.config.stop),
            );
        }
        knots.sort_by(f64::total_cmp);
        knots.dedup();
        knots
    }

    pub(crate) fn roots(
        &self,
        knots: &[f64],
        values: &[I],
        direction: i8,
    ) -> Result<Vec<Root>, Error> {
        let mut result = Vec::new();
        if values.iter().any(|v| !v.finite() || v.sign().is_none()) {
            return Err(unresolved(
                "cannot determine cross sign at a PWL knot within arithmetic bounds",
            ));
        }
        for index in 0..values.len() - 1 {
            let (a, b) = (values[index], values[index + 1]);
            let segment = [knots[index], knots[index + 1]];
            let duration = I::point(segment[1]) - I::point(segment[0]);
            let crossing = if !a.zero() && !b.zero() && a.sign() != b.sign() {
                let bounds = I::point(segment[0]) + (a / (a - b)) * duration;
                if !bounds.finite() || bounds.lo <= segment[0] || bounds.hi >= segment[1] {
                    return Err(unresolved(
                        "cannot enclose cross root strictly inside its PWL interval",
                    ));
                }
                Some((
                    Root {
                        bounds,
                        slope: (b - a) / duration,
                        segment,
                        ends: [a, b],
                        source_time: None,
                    },
                    b.sign().unwrap(),
                ))
            } else if b.zero() && !a.zero() {
                // Arrival owns an exact zero, including plateau entry and stop.
                // Staying at or departing from zero matches neither branch;
                // only a later nonzero-to-zero arrival can fire again.
                Some((
                    Root {
                        bounds: I::point(segment[1]),
                        slope: I::ZERO,
                        segment,
                        ends: [a, b],
                        source_time: None,
                    },
                    -a.sign().unwrap(),
                ))
            } else {
                None
            };
            if let Some((mut root, sign)) = crossing {
                if direction == 0 || direction == sign {
                    root.refine_representable();
                    result.push(root);
                }
            }
        }
        Ok(result)
    }

    pub(crate) fn value_bounds(&self, time: f64) -> Vec<I> {
        self.config
            .pwl
            .iter()
            .zip(&self.source_errors)
            .enumerate()
            .map(|(index, (source, &error))| {
                if self.is_shaped(index) {
                    if let Some((_, bounds)) =
                        self.exact_sources[index].as_ref().and_then(|c| c.at(time))
                    {
                        return bounds;
                    }
                }
                let index = source.partition_point(|p| p[0] < time);
                if source[index][0] == time {
                    return I::point(source[index][1])
                        + I {
                            lo: -error,
                            hi: error,
                        };
                }
                let [start, a] = source[index - 1];
                let [end, b] = source[index];
                let fraction =
                    (I::point(time) - I::point(start)) / (I::point(end) - I::point(start));
                I::point(a)
                    + (I::point(b) - I::point(a)) * fraction
                    + I {
                        lo: -error,
                        hi: error,
                    }
            })
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn forcing_shape_test(value: f64) -> Trajectory {
        let config = serde_json::from_value(serde_json::json!({"pwl":[[[0,0],[1,value]]],
          "output_times":[0,1],"stop":1,"max_step":1,
          "pwl_errors_V":[{"voltage_error_bound_V":0,"exact_knots":[
            {"time_numerator":"0","time_denominator":"1","value_V":0},
            {"time_numerator":"1","time_denominator":"1","value_V":value}]}]}))
        .unwrap();
        Trajectory::new(config, 1).unwrap()
    }
    #[test]
    fn forcing_global_values_include_interior_and_beyond_stop_physical_extrema() {
        let config = serde_json::from_value(serde_json::json!({"pwl":[[[0,0],[2,0]]],
          "output_times":[0,1],"stop":1,"max_step":1,
          "pwl_errors_V":[{"voltage_error_bound_V":2,"exact_knots":[
            {"time_numerator":"0","time_denominator":"1","value_V":0},
            {"time_numerator":"1","time_denominator":"2","value_V":2},
            {"time_numerator":"2","time_denominator":"1","value_V":-2}]}]}))
        .unwrap();
        let t = Trajectory::new(config, 1).unwrap();
        let work = crate::transition_source_plan::Work::default();
        let (r, d) = crate::diagnostics::capture(Default::default(), || {
            t.forcing_request_value_bounds(&work)
        });
        let b = r.unwrap()[0];
        assert_eq!((b.lo, b.hi), (-2., 2.));
        assert_eq!(d.counters["forcing_global_value_knots"], 3);
        assert_eq!(d.counters.get("forcing_curve_actual_range_calls"), None);
        assert_eq!(d.counters.get("forcing_curve_reserved_work"), None);
        assert!(b.lo <= -2.); // Exterior final knot is retained, not clipped away.
        let work = crate::transition_source_plan::Work::limited([128, 8192, 30]);
        for _ in 0..3 {
            let (r, d) = crate::diagnostics::capture(Default::default(), || {
                t.forcing_request_value_bounds(&work)
            });
            assert_eq!(r.unwrap_err().kind, "step_budget");
            assert_eq!(d.counters.get("forcing_global_value_knots"), None);
        }
    }
    #[test]
    fn forcing_global_values_keep_zero_band_physical_and_nominal_sources() {
        let config = serde_json::from_value(serde_json::json!({"pwl":[[[0,0],[2,2]]],
          "output_times":[0,1],"stop":1,"max_step":1,
          "pwl_errors_V":[{"voltage_error_bound_V":0,"exact_knots":[
            {"time_numerator":"0","time_denominator":"1","value_V":0},
            {"time_numerator":"2","time_denominator":"1","value_V":2}]}]}))
        .unwrap();
        let t = Trajectory::new(config, 1).unwrap();
        let work = crate::transition_source_plan::Work::default();
        let b = t.forcing_request_value_bounds(&work).unwrap()[0];
        assert_eq!((b.lo, b.hi), (0., 2.));
        let (local, d) = crate::diagnostics::capture(Default::default(), || {
            t.forcing_range(I { lo: 0., hi: 1. }, &work)
        });
        let local = local.unwrap().0[0];
        assert!(local.hi < b.hi && local.lo >= b.lo);
        assert_eq!(d.counters["forcing_curve_actual_range_calls"], 1);
        assert!(d.counters["forcing_curve_reserved_work"] > 0);
        let config = serde_json::from_value(serde_json::json!({"pwl":[[[0,0],[0.5,3],[2,-4]]],
          "output_times":[0,1],"stop":1,"max_step":1}))
        .unwrap();
        let t = Trajectory::new(config, 1).unwrap();
        let b = t.forcing_request_value_bounds(&work).unwrap()[0];
        assert_eq!((b.lo, b.hi), (-4., 3.));
    }
    #[test]
    fn forcing_global_values_reject_uncovered_unknown_and_generated_providers() {
        for points in [
            serde_json::json!([[0.1, 0], [1, 1]]),
            serde_json::json!([[0, 0], [0.9, 1]]),
        ] {
            let config = serde_json::from_value(
                serde_json::json!({"pwl":[points],"output_times":[0,1],"stop":1,"max_step":1}),
            )
            .unwrap();
            assert!(Trajectory::new(config, 1).is_err());
        }
        let config=serde_json::from_value(serde_json::json!({"pwl":[[[0,0],[1,1]]],"output_times":[0,1],"stop":1,"max_step":1,"pwl_errors_V":[0.1]})).unwrap();
        let t = Trajectory::new(config, 1).unwrap();
        let work = crate::transition_source_plan::Work::default();
        assert_eq!(
            t.forcing_request_value_bounds(&work).unwrap_err().kind,
            "unsupported_forcing_scope"
        );
        let mut t = forcing_shape_test(1.);
        t.add_enclosed_source(vec![[0., 0.], [1., 1.]], 0.).unwrap();
        assert_eq!(
            t.forcing_request_value_bounds(&work).unwrap_err().kind,
            "unsupported_forcing_scope"
        );
    }
    #[test]
    fn forcing_physical_point_prepays_limbs_subnormal_time_and_sticky_locator() {
        use crate::transition_source_plan::Work;
        let small = forcing_shape_test(1.);
        let large = forcing_shape_test(1e300);
        let measure = |t: &Trajectory| {
            let work = Work::default();
            let (r, d) = crate::diagnostics::capture(Default::default(), || {
                t.forcing_values_bounds(f64::from_bits(1), &work)
            });
            let (_, boxes) = r.unwrap();
            let exact = crate::exact_source::binary(t.config.pwl[0][1][1]).unwrap()
                * crate::exact_source::binary(f64::from_bits(1)).unwrap();
            assert!(
                crate::exact_source::binary(boxes[0].lo).unwrap() <= exact
                    && exact <= crate::exact_source::binary(boxes[0].hi).unwrap()
            );
            d
        };
        let a = measure(&small);
        let b = measure(&large);
        assert_eq!(a.counters["forcing_curve_actual_point_calls"], 1); // Strict conversion-overflow fallback.
        assert_eq!(b.counters["forcing_owned_point_success"], 1);
        assert_eq!(b.counters.get("forcing_curve_actual_point_calls"), None);
        assert!(
            b.counters["forcing_owned_reserved_work"] > a.counters["forcing_owned_reserved_work"]
        );
        println!("forcing_owned_subnormal_limb_cost small_owned={} small_legacy={} large_owned={} large_certified_without_legacy=true",a.counters["forcing_owned_reserved_work"],a.counters["forcing_curve_reserved_work"],b.counters["forcing_owned_reserved_work"]);
        let work = Work::limited([128, 8192, 100]); // Locator only, original1e9 is unchanged.
        for _ in 0..3 {
            let (r, d) = crate::diagnostics::capture(Default::default(), || {
                large.forcing_values_bounds(f64::from_bits(1), &work)
            });
            assert_eq!(r.unwrap_err().kind, "step_budget");
            assert_eq!(d.counters.get("forcing_curve_actual_point_calls"), None);
            assert_eq!(d.counters.get("forcing_owned_time_conversions"), None);
            assert_eq!(d.counters.get("forcing_owned_cross_comparisons"), None);
        }
    }
    #[test]
    fn forcing_provider_refuses_generated_even_zero_error_history() {
        use crate::transition_source_plan::Work;
        let mut t = forcing_shape_test(1.);
        t.add_enclosed_source(vec![[0., 0.], [1., 1.]], 0.).unwrap();
        assert_eq!(
            t.forcing_shaped_inputs(&Work::default()).unwrap_err().kind,
            "unsupported_forcing_scope"
        );
    }
    #[test]
    fn flat_generated_source_keeps_its_enclosure_error() {
        let mut trajectory = Trajectory::new(
            TransientInputs {
                pwl_errors_v: None,
                strobetimes: Vec::new(),
                pwl: vec![vec![[0., 0.], [1., 0.]]],
                output_times: vec![0., 1.],
                stop: 1.,
                max_step: 1.,
            },
            1,
        )
        .unwrap();
        let value = f64::from_bits(0.5_f64.to_bits() - 1);
        trajectory
            .add_enclosed_source(vec![[0., value], [1., value]], 1e-6)
            .unwrap();
        assert_eq!(trajectory.values(0.3)[1].to_bits(), value.to_bits());
        let enclosure = trajectory.value_bounds(0.3)[1];
        assert!(enclosure.lo <= value - 1e-6 && enclosure.hi >= value + 1e-6);
        assert!(!trajectory.has_only_physical_inputs());
    }

    #[test]
    fn generated_zero_error_sources_do_not_gain_original_guard_provenance() {
        let points = vec![[0.0, -1.0], [2.0, 1.0]];
        let mut trajectory = Trajectory::new(
            TransientInputs {
                pwl_errors_v: None,
                strobetimes: Vec::new(),
                pwl: vec![points.clone()],
                output_times: vec![0.0, 2.0],
                stop: 2.0,
                max_step: 1.0,
            },
            1,
        )
        .unwrap();
        trajectory.add_enclosed_source(points, 0.0).unwrap();
        assert!(trajectory.exact_sources[1].is_some());
        let guard = |node| crate::ir::Expression::Affine {
            constant: 0.0,
            terms: vec![crate::ir::Term {
                node,
                coefficient: 1.0,
            }],
        };
        assert!(trajectory
            .original_guard_curve(&guard(1), &[1, 2])
            .is_some());
        assert!(trajectory
            .original_guard_curve(&guard(2), &[1, 2])
            .is_none());
    }

    #[test]
    fn one_source_time_proof_controls_order_coincidence_and_tolerance() {
        let curve = crate::exact_source::Curve::source(&[[0.0, -1.0], [2.0, 1.0]]).unwrap();
        let root = Root {
            bounds: I { lo: 0.9, hi: 1.1 },
            slope: I::ONE,
            segment: [0.0, 2.0],
            ends: [I { lo: -1.1, hi: -0.9 }, I { lo: 0.9, hi: 1.1 }],
            source_time: None,
        };
        let proved = root.clone().with_source_time(Some(&curve));
        assert_eq!(proved.bounds, I::ONE);
        let point = Root {
            ends: [I::point(-1.0), I::ONE],
            ..root.clone()
        };
        assert_eq!(proved.exact_order(&point), Some(std::cmp::Ordering::Equal));
        assert!(proved.coincides(&point, false));
        assert_eq!(proved.exact_order(&root), None);
        assert!(!proved.coincides(&root, false));
        let later = crate::exact_source::Curve::source(&[[0.0, -1.0], [2.0, 0.9]]).unwrap();
        let later = root.with_source_time(Some(&later));
        assert_eq!(proved.exact_order(&later), Some(std::cmp::Ordering::Less));
        assert!(!proved.coincides(&later, true));
        assert!(proved.accepts(1.0, 0.0, 0.0));
        assert!(!proved.accepts(1.0_f64.next_up(), 0.0, 0.0));
    }

    fn candidate(a: I, b: I, time: f64) -> Root {
        Root {
            bounds: I {
                lo: time.next_down(),
                hi: time.next_up(),
            },
            slope: I::ONE,
            segment: [0.0, 19.0],
            ends: [a, b],
            source_time: None,
        }
    }

    #[test]
    fn bisection_certifies_root_when_quotient_and_products_overflow() {
        let mut root = Root {
            bounds: I { lo: 0.0, hi: 4.0 },
            slope: I::ONE,
            segment: [0.0, 4.0],
            ends: [I::point(-1e308), I::point(1e308)],
            source_time: None,
        };
        root.refine_representable();
        assert_eq!(root.bounds, I::point(2.0));
    }

    #[test]
    fn exact_zero_certificate_does_not_use_rounded_products_or_tolerance() {
        let mut root = candidate(I::point(-8.0), I::point(11.0), 8.0);
        root.refine_representable();
        assert_eq!(root.bounds, I::point(8.0));
        let mut uncertain = candidate(
            I {
                lo: -8.0,
                hi: (-8.0_f64).next_up(),
            },
            I::point(11.0),
            8.0,
        );
        uncertain.refine_representable();
        assert_ne!(uncertain.bounds.lo, uncertain.bounds.hi);
        let mut nonrepresentable = candidate(I::point(-1.0), I::point(2.0), 19.0 / 3.0);
        nonrepresentable.refine_representable();
        assert_ne!(nonrepresentable.bounds.lo, nonrepresentable.bounds.hi);
        // Underflowed products must not make a nonzero weighted sum look zero.
        let tiny = f64::from_bits(1);
        let mut subnormal = Root {
            bounds: I { lo: 0.25, hi: 0.5 },
            slope: I::ONE,
            segment: [0.0, 1.0],
            ends: [I::point(-tiny), I::point(2.0 * tiny)],
            source_time: None,
        };
        subnormal.refine_representable();
        assert_ne!(subnormal.bounds.lo, subnormal.bounds.hi);
    }
}

#[cfg(test)]
mod exact_mixed_order_tests {
    use super::*;
    use num_rational::BigRational as Q;
    use proptest::prelude::*;
    fn q(v: f64) -> Q {
        Q::from_float(v).unwrap()
    }
    fn finite() -> impl Strategy<Value = f64> {
        any::<u64>()
            .prop_map(f64::from_bits)
            .prop_filter("finite", |v| v.is_finite())
    }
    fn order(value: Q) -> std::cmp::Ordering {
        value.cmp(&q(0.))
    }
    fn root(a: f64, b: f64, t0: f64, t1: f64) -> Root {
        Root {
            bounds: I { lo: 0., hi: 1. },
            slope: I::ONE,
            segment: [t0, t1],
            ends: [I::point(a), I::point(b)],
            source_time: None,
        }
    }
    proptest! {
        #![proptest_config(ProptestConfig::with_cases(512))]
        #[test]
        fn source_clock_and_source_source_signs_use_original_rationals(a in finite(),b in finite(),c in finite(),d in finite(),t0 in finite(),t1 in finite(),s0 in finite(),s1 in finite(),start in finite(),period in finite(),delta in finite(),index in 0usize..1_000_000) {
            prop_assume!(a!=b && c!=d);
            let left=root(a,b,t0,t1);
            let right=root(c,d,s0,s1);
            let clock=crate::exact_time::Clock {start,period,index};
            let left_time=(q(a)*q(t1)-q(b)*q(t0))/(q(a)-q(b));
            let right_time=(q(c)*q(s1)-q(d)*q(s0))/(q(c)-q(d));
            prop_assert_eq!(left.exact_order(&right),Some(order(left_time.clone()-right_time)));
            prop_assert_eq!(left.clock_delta_order(clock,delta),Some(order(left_time-q(start)-q(period)*q(index as f64)-q(delta))));
        }
    }
}

// borrow original Root metadata, never run rational_time to price it.
impl Root {
    pub(crate) fn rational_time_with_work(
        &self,
        w: &crate::transition_source_plan::Work,
    ) -> Result<Option<crate::exact_source::RootTime>, crate::ir::Error> {
        w.debit(2, 0)?;
        w.debit(2, 32)?;
        if let Some(time) = &self.source_time {
            return time.clone_with_work(w).map(Some);
        }
        crate::exact_source::RootTime::point_ends_with_work(self.segment, self.ends, self.bounds, w)
    }
}

// original Root branches preserved, no projected root substituted.
impl Root {
    pub(crate) fn clock_delta_order_with_work(
        &self,
        clock: crate::exact_time::Clock,
        delta: f64,
        w: &crate::transition_source_plan::Work,
    ) -> Result<Option<std::cmp::Ordering>, Error> {
        w.debit(2, 0)?;
        w.debit(2, 64)?;
        if let Some(time) = &self.source_time {
            return time.clock_delta_order_with_work(clock, delta, w);
        }
        w.debit(2, crate::exact_time::TRIPLE_SIGN_FEE)?;
        Ok(self.clock_delta_order(clock, delta))
    }
    pub(crate) fn local_bounds_with_work(
        &self,
        clock: crate::exact_time::Clock,
        w: &crate::transition_source_plan::Work,
    ) -> Result<Option<I>, Error> {
        w.debit(2, 0)?;
        w.debit(2, 64)?;
        if let Some(time) = &self.source_time {
            return time.local_bounds_with_work(clock, w);
        }
        // The old closure performs only fixed-array clock_delta_order here.
        w.debit(
            2,
            crate::exact_time::ENCLOSE_SIGN_CALLS
                .saturating_mul(crate::exact_time::TRIPLE_SIGN_FEE.saturating_add(64))
                .saturating_add(256),
        )?;
        Ok(self.local_bounds(clock))
    }
    pub(crate) fn exact_order_with_work(
        &self,
        other: &Self,
        w: &crate::transition_source_plan::Work,
    ) -> Result<Option<std::cmp::Ordering>, Error> {
        w.debit(2, 0)?;
        w.debit(2, 96)?;
        if self.source_time.is_some() || other.source_time.is_some() {
            let Some(a) = self.rational_time_with_work(w)? else {
                return Ok(None);
            };
            let Some(b) = other.rational_time_with_work(w)? else {
                return Ok(None);
            };
            return Ok(Some(a.order_with_work(&b, w)?));
        }
        w.debit(2, crate::exact_time::TRIPLE_SIGN_FEE)?;
        Ok(self.exact_order(other))
    }
}
