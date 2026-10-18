//! Opt-in independent source forcing beside the unchanged held controller.
//! This first vertical has no Held/History provider masquerading as a source.
//! Each scalar relation is certified inside its disposable Frame before commit.
use crate::interval::Interval as I;
use crate::ir::{
    Error, Expression as E, OperatorSpec, Origin, Program, Relation, Solution, Tolerances,
};
use crate::pwl::Trajectory;
use crate::solver::Circuit;
use crate::transition_source_plan::{ProofContext, Work};
use std::collections::BTreeSet;
use std::io::Write;
use std::sync::Arc;

fn scope() -> Error {
    Error::new("unsupported_forcing_scope", "forcing requires independent grounded source-only outputs beside bare held Transition components")
}
fn zero() -> E {
    E::Affine {
        constant: 0.,
        terms: vec![],
    }
}

// The only mapping lookup seam: reservation and actual comparison cannot be
// separated by callers. Context's later independent lookup retains its owner.
fn lookup_node(nodes: &[String], name: &str, work: &Work) -> Result<usize, Error> {
    // Each possible candidate costs one length comparison plus at most the
    // driven name's byte length. Saturation rejects before position on overflow.
    let cost = nodes.len().saturating_mul(name.len().saturating_add(1));
    crate::diagnostics::counter("forcing_lookup_requested_work", cost);
    work.debit(2, cost as u64)?;
    crate::diagnostics::counter("forcing_lookup_reserved_work", cost);
    nodes
        .iter()
        .position(|node| {
            crate::diagnostics::counter("forcing_lookup_comparisons", 1);
            if node.len() != name.len() {
                return false;
            }
            node.as_bytes().iter().zip(name.as_bytes()).all(|(a, b)| {
                crate::diagnostics::counter("forcing_lookup_byte_comparisons", 1);
                a == b
            })
        })
        .ok_or_else(scope)
}

// Streaming original-tree inspection: no serde Value or full request clone.
// Count every serialized byte before consuming it, including string/zero refs.
struct Scan<'a> {
    work: &'a Work,
    forbidden: &'a BTreeSet<usize>,
    tail: [u8; 7],
    used: usize,
    number: Option<usize>,
    rejected: bool,
    bytes: usize,
    scan_native_bits: bool,
    native_tail: [u8; 32],
    native_bits: bool,
}
impl Write for Scan<'_> {
    fn write(&mut self, data: &[u8]) -> std::io::Result<usize> {
        self.work
            .debit(2, data.len() as u64)
            .map_err(|e| std::io::Error::other(e.message))?;
        // The optional raw-program mixed-scope scan prepays a fixed window
        // rotation plus both complete token comparisons for every input byte.
        if self.scan_native_bits {
            self.work
                .debit(2, (data.len() as u64).saturating_mul(128))
                .map_err(|e| std::io::Error::other(e.message))?;
        }
        self.bytes = self.bytes.saturating_add(data.len());
        for &b in data {
            if self.scan_native_bits {
                self.native_tail.rotate_left(1);
                self.native_tail[31] = b;
                self.native_bits |= self.native_tail.ends_with(b"\"function\":\"shift_right\"")
                    || self.native_tail.ends_with(b"\"function\":\"bit_and\"");
            }
            if let Some(n) = self.number {
                if b.is_ascii_digit() {
                    self.number = n
                        .checked_mul(10)
                        .and_then(|v| v.checked_add((b - b'0') as usize));
                    if self.number.is_none() {
                        self.rejected = true;
                    }
                    continue;
                }
                self.rejected |= self.forbidden.contains(&n);
                self.number = None;
            }
            self.tail.rotate_left(1);
            self.tail[6] = b;
            self.used += 1;
            if self.used >= 7 && &self.tail == b"\"node\":" {
                self.number = Some(0);
            }
        }
        Ok(data.len())
    }
    fn flush(&mut self) -> std::io::Result<()> {
        Ok(())
    }
}
fn inspect_with_bits<T: serde::Serialize>(
    value: &T,
    work: &Work,
    forbidden: &BTreeSet<usize>,
    scan_native_bits: bool,
) -> Result<(usize, bool), Error> {
    work.debit(2, 128)?;
    let mut scan = Scan {
        work,
        forbidden,
        tail: [0; 7],
        used: 0,
        number: None,
        rejected: false,
        bytes: 0,
        scan_native_bits,
        native_tail: [0; 32],
        native_bits: false,
    };
    serde_json::to_writer(&mut scan, value)
        .map_err(|e| Error::new("resource_budget", e.to_string()))?;
    if scan.rejected {
        return Err(scope());
    }
    Ok((scan.bytes, scan.native_bits))
}
fn inspect<T: serde::Serialize>(
    value: &T,
    work: &Work,
    forbidden: &BTreeSet<usize>,
) -> Result<usize, Error> {
    inspect_with_bits(value, work, forbidden, false).map(|(bytes, _)| bytes)
}
fn audit(e: &E, sources: &BTreeSet<usize>, owner: &str, work: &Work) -> Result<bool, Error> {
    work.step()?;
    match e {
        E::Affine { constant, terms } => {
            work.debit(2, terms.len() as u64)?;
            if !constant.is_finite()
                || terms
                    .iter()
                    .any(|t| !t.coefficient.is_finite() || !sources.contains(&t.node))
            {
                return Err(scope());
            }
            Ok(!terms.is_empty())
        }
        E::Add { left, right } | E::Multiply { left, right } => {
            let a = audit(left, sources, owner, work)?;
            let b = audit(right, sources, owner, work)?;
            if matches!(e, E::Multiply { .. }) && a && b {
                return Err(scope());
            }
            Ok(a || b)
        }
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
                return Err(scope());
            }
            audit(left, sources, owner, work)?;
            audit(right, sources, owner, work)?;
            let a = audit(then_value, sources, owner, work)?;
            let b = audit(else_value, sources, owner, work)?;
            Ok(a || b)
        }
        _ => Err(scope()),
    }
}
// Only a predicate may consume a nonzero-band original physical source.
// Numerical reads count even with zero coefficient or in unselected arms.
fn audit_shaped(
    e: &E,
    shaped: &BTreeSet<usize>,
    predicate: bool,
    work: &Work,
) -> Result<(), Error> {
    work.step()?;
    match e {
        E::Affine { terms, .. } => {
            work.debit(
                2,
                (terms.len() as u64).saturating_mul((shaped.len() as u64).saturating_add(1)),
            )?;
            if !predicate && terms.iter().any(|t| shaped.contains(&t.node)) {
                return Err(scope());
            }
        }
        E::Add { left, right } | E::Multiply { left, right } => {
            audit_shaped(left, shaped, predicate, work)?;
            audit_shaped(right, shaped, predicate, work)?;
        }
        E::Select {
            left,
            right,
            then_value,
            else_value,
            ..
        } => {
            audit_shaped(left, shaped, true, work)?;
            audit_shaped(right, shaped, true, work)?;
            audit_shaped(then_value, shaped, predicate, work)?;
            audit_shaped(else_value, shaped, predicate, work)?;
        }
        _ => return Err(scope()),
    }
    Ok(())
}
struct CompareWire<'a> {
    wire: &'a [u8],
    at: usize,
    work: &'a Work,
    mismatch: bool,
}
impl Write for CompareWire<'_> {
    fn write(&mut self, bytes: &[u8]) -> std::io::Result<usize> {
        // Charge serialization + every byte comparison before either consumes data.
        self.work
            .debit(2, (bytes.len().saturating_mul(2)) as u64)
            .map_err(|e| std::io::Error::other(e.message))?;
        let end = self.at.saturating_add(bytes.len());
        self.mismatch |= self.wire.get(self.at..end) != Some(bytes);
        self.at = end;
        Ok(bytes.len())
    }
    fn flush(&mut self) -> std::io::Result<()> {
        Ok(())
    }
}
// An unforgeable private reduction token. Construction below follows the full
// original dependency audit, then changes only isolated contribution RHSs.
// The original proof binding remains in context; this exact execution wire
// binds preserved nodes/states/operators/events/settings and reduced rows.
struct Reduction {
    execution_wire: Vec<u8>,
    driven: Vec<String>,
}
struct Output {
    node: usize,
    positive: usize,
    negative: usize,
    value: E,
    origin: Origin,
}
pub(crate) struct Graph {
    context: Arc<ProofContext>,
    ledger: Work,
    source: Trajectory,
    mapping: Vec<usize>,
    outputs: Vec<Output>,
    dimensions: usize,
    copy_items: usize,
    tolerances: Tolerances,
    reduction: Reduction,
    provider_wire: Vec<u8>,
}
impl Graph {
    pub(crate) fn partition(
        p: &mut Program,
        t: &Trajectory,
        driven: &[String],
        tol: &Tolerances,
    ) -> Result<Option<Arc<Self>>, Error> {
        if !p
            .contributions
            .iter()
            .any(|c| matches!(c.rhs, E::Forcing { .. }))
        {
            return Ok(None);
        }
        crate::diagnostics::counter("forcing_factory_calls", 1);
        let work = Work::default();
        t.charge_source_copy(&work)?;
        let shaped_inputs = t.forcing_shaped_inputs(&work)?;
        let (bytes, native_bits) = inspect_with_bits(p, &work, &BTreeSet::new(), true)?;
        work.debit(
            2,
            (p.nodes.len() + driven.len() + p.contributions.len()) as u64,
        )?;
        let mut sources = BTreeSet::from([0]);
        let mut mapping = Vec::new();
        for name in driven {
            let n = lookup_node(&p.nodes, name, &work)?;
            if !sources.insert(n) {
                return Err(scope());
            }
            mapping.push(n);
        }
        work.debit(
            2,
            shaped_inputs.len().saturating_mul(mapping.len() + 1) as u64,
        )?;
        let shaped_nodes = shaped_inputs
            .iter()
            .map(|&k| mapping[k])
            .collect::<BTreeSet<_>>();
        let mut output_nodes = BTreeSet::new();
        for c in &p.contributions {
            if let E::Forcing {
                value,
                origin,
                checked,
            } = &c.rhs
            {
                if origin != &c.origin || c.branch.instance != origin.instance {
                    return Err(scope());
                }
                let n = match (c.positive, c.negative) {
                    (0, n) | (n, 0) if n != 0 => n,
                    _ => return Err(scope()),
                };
                if n >= p.nodes.len() || sources.contains(&n) || !output_nodes.insert(n) {
                    return Err(scope());
                }
                audit(value, &sources, &origin.instance, &work)?;
                audit_shaped(value, &shaped_nodes, false, &work)?;
                for expression in checked {
                    audit(expression, &sources, &origin.instance, &work)?;
                    audit_shaped(expression, &shaped_nodes, false, &work)?;
                }
            }
        }
        // Every possible legacy read, including display/initial/setting and
        // inactive zero terms, must be disjoint from every forcing output.
        for c in &p.contributions {
            if !matches!(c.rhs, E::Forcing { .. }) {
                if output_nodes.contains(&c.positive) || output_nodes.contains(&c.negative) {
                    return Err(scope());
                }
                inspect(&c.rhs, &work, &output_nodes)?;
            }
        }
        let legacy_unknowns = (0..p.nodes.len())
            .filter(|n| !sources.contains(n))
            .collect();
        inspect(&p.states, &work, &legacy_unknowns)?;
        inspect(&p.events, &work, &legacy_unknowns)?;
        inspect(&p.operators, &work, &output_nodes)?;
        inspect(&p.step_bounds, &work, &legacy_unknowns)?;
        // Both branches must have finite original intermediate domains over
        // the actual finite physical source request before selection/copy.
        t.charge_source_copy(&work)?;
        let range = t.forcing_request_value_bounds(&work)?;
        let mut source_boxes = vec![I::ZERO; p.nodes.len()];
        for (&n, &b) in mapping.iter().zip(&range) {
            source_boxes[n] = b;
        }
        fn health(e: &E, nodes: &[I], w: &Work) -> Result<I, Error> {
            w.step()?;
            let value = match e {
                E::Affine { constant, terms } => {
                    w.debit(2, terms.len() as u64)?;
                    terms.iter().fold(I::point(*constant), |sum, t| {
                        sum + I::point(t.coefficient) * nodes[t.node]
                    })
                }
                E::Add { left, right } => health(left, nodes, w)? + health(right, nodes, w)?,
                E::Multiply { left, right } => health(left, nodes, w)? * health(right, nodes, w)?,
                E::Select {
                    left,
                    right,
                    then_value,
                    else_value,
                    ..
                } => {
                    health(left, nodes, w)?;
                    health(right, nodes, w)?;
                    health(then_value, nodes, w)?.hull(health(else_value, nodes, w)?)
                }
                _ => return Err(scope()),
            };
            if !value.finite() {
                return Err(Error::new(
                    "nonfinite_arithmetic",
                    "forcing original inactive arm or intermediate is nonfinite",
                ));
            }
            Ok(value)
        }
        for c in &p.contributions {
            if let E::Forcing { value, checked, .. } = &c.rhs {
                health(value, &source_boxes, &work)?;
                for expression in checked {
                    health(expression, &source_boxes, &work)?;
                }
            }
        }
        // Admission borrows the very same ledger after the original forcing
        // role and inactive-arm health audits. Metadata identifies unsupported
        // consumers; it is not a new Floor or typed-target proof factory.
        let admission = crate::event_control::admit(p, Some(&work))?;
        if admission.source_floor() || !admission.targets.is_empty() || native_bits {
            return Err(scope());
        }
        drop(admission);
        // This vertical deliberately retains only existing bare held histories.
        if p.operators.is_empty()
            || p.operators.iter().any(|o| {
                !matches!(
                    o,
                    OperatorSpec::Transition {
                        input: E::State { .. },
                        ..
                    }
                )
            })
        {
            return Err(scope());
        }
        // Upper bounds include container/string overhead in actual owned clones.
        let copy_items = bytes.saturating_mul(16).saturating_add(p.nodes.len() * 64);
        let provider = (&t.config.pwl, t.config.stop, &t.config.pwl_errors_v);
        let provider_bytes = inspect(&provider, &work, &BTreeSet::new())?;
        work.debit(2, provider_bytes as u64)?;
        let provider_wire = serde_json::to_vec(&provider)
            .map_err(|e| Error::new("invalid_inputs", e.to_string()))?;
        let ledger = work.clone();
        let context = ProofContext::source_math_with_work(p, t, driven, copy_items, work)?;
        t.charge_source_copy(&ledger)?;
        context.source_charge("forcing_copy_items", copy_items)?;
        let mut outputs = Vec::new();
        for c in &mut p.contributions {
            if let E::Forcing { value, origin, .. } = &c.rhs {
                outputs.push(Output {
                    node: if c.positive == 0 {
                        c.negative
                    } else {
                        c.positive
                    },
                    positive: c.positive,
                    negative: c.negative,
                    value: (**value).clone(),
                    origin: origin.clone(),
                });
                c.rhs = zero(); // Independent reduced row, never an output certificate.
            }
        }
        context.source_charge("forcing_copy_items", copy_items)?;
        context.source_charge("forcing_reduction_token_copy", copy_items)?;
        let reduction = Reduction {
            execution_wire: serde_json::to_vec(p)
                .map_err(|e| Error::new("invalid_ir", e.to_string()))?,
            driven: driven.to_vec(),
        };
        Ok(Some(Arc::new(Self {
            context,
            ledger,
            source: t.clone(),
            mapping,
            outputs,
            dimensions: p.nodes.len(),
            copy_items,
            tolerances: tol.clone(),
            reduction,
            provider_wire,
        })))
    }
    fn provider_matches(&self, t: &Trajectory) -> Result<(), Error> {
        t.charge_source_copy(&self.ledger)?;
        t.forcing_shaped_inputs(&self.ledger)?;
        self.charge("forcing_provider_binding", 64)?;
        let mut compare = CompareWire {
            wire: &self.provider_wire,
            at: 0,
            work: &self.ledger,
            mismatch: false,
        };
        serde_json::to_writer(
            &mut compare,
            &(&t.config.pwl, t.config.stop, &t.config.pwl_errors_v),
        )
        .map_err(|e| Error::new("step_budget", e.to_string()))?;
        if compare.mismatch || compare.at != compare.wire.len() {
            return Err(scope());
        }
        Ok(())
    }
    pub(crate) fn source_context(
        &self,
        p: &Program,
        t: &Trajectory,
        driven: &[String],
    ) -> Result<Arc<ProofContext>, Error> {
        // Validate an audited execution mapping, never pretend reduced==original.
        self.provider_matches(t)?;
        let names = self
            .reduction
            .driven
            .iter()
            .chain(driven)
            .map(|n| n.len().saturating_add(1))
            .fold(0usize, usize::saturating_add);
        self.charge(
            "forcing_provider_name_compare",
            names.saturating_add(driven.len()),
        )?;
        if driven != self.reduction.driven {
            return Err(scope());
        }
        struct Compare<'a> {
            wire: &'a [u8],
            at: usize,
            context: &'a ProofContext,
            mismatch: bool,
        }
        impl Write for Compare<'_> {
            fn write(&mut self, bytes: &[u8]) -> std::io::Result<usize> {
                self.context
                    .source_charge("forcing_reduction_binding", bytes.len())
                    .map_err(|e| std::io::Error::other(e.message))?;
                let end = self.at.saturating_add(bytes.len());
                self.mismatch |= self.wire.get(self.at..end) != Some(bytes);
                self.at = end;
                Ok(bytes.len())
            }
            fn flush(&mut self) -> std::io::Result<()> {
                Ok(())
            }
        }
        self.charge("forcing_reduction_binding", 64 + driven.len())?;
        let mut compare = Compare {
            wire: &self.reduction.execution_wire,
            at: 0,
            context: &self.context,
            mismatch: false,
        };
        serde_json::to_writer(&mut compare, p)
            .map_err(|e| Error::new("step_budget", e.to_string()))?;
        if compare.mismatch || compare.at != compare.wire.len() {
            return Err(scope());
        }
        self.charge(
            "forcing_legacy_factory_copy",
            self.copy_items.saturating_mul(3) + self.dimensions * self.dimensions * 16,
        )?;
        self.charge("forcing_shared_context_copy", 1)?;
        Ok(self.context.clone())
    }
    #[cfg(test)]
    pub(crate) fn exhaust_physical_reads_for_test(&self) {
        self.exhaust_physical_reads_at_for_test(f64::from_bits(1));
    }
    #[cfg(test)]
    pub(crate) fn exhaust_physical_reads_at_for_test(&self, time: f64) {
        let mut calls = 0;
        loop {
            let (result, report) = crate::diagnostics::capture(Default::default(), || {
                self.source.forcing_values_bounds(time, &self.ledger)
            });
            if let Err(error) = result {
                assert_eq!(error.kind, "step_budget");
                assert_eq!(
                    report
                        .counters
                        .get("forcing_curve_actual_point_calls")
                        .copied()
                        .unwrap_or(0),
                    0
                );
                println!("natural_physical_read_exhaustion time={time:?} calls={calls} used={} original_limit=1000000000",self.work_used());
                break;
            }
            calls += 1;
        }
    }
    #[cfg(test)]
    pub(crate) fn work_used(&self) -> u64 {
        self.context.source_work_used()
    }
    pub(crate) fn request_work(&self) -> &Work {
        &self.ledger
    }
    pub(crate) fn charge_event_prefix_storage(&self, count: usize) -> Result<(), Error> {
        // Each deduplication insert has at most log2(N)+1 comparisons, and
        // fixed node/container allocation/copy work, followed by vector output.
        let levels = usize::BITS - count.max(1).leading_zeros();
        self.charge(
            "forcing_event_prefix_storage",
            count
                .saturating_add(1)
                .saturating_mul(levels as usize + 1)
                .saturating_mul(32),
        )
    }
    pub(crate) fn ensure_live(&self) -> Result<(), Error> {
        self.charge("forcing_entry_budget", 0)
    }
    pub(crate) fn legacy_voltage_view(&self, values: &[f64]) -> Result<Vec<f64>, Error> {
        self.charge("forcing_legacy_projection_copy", values.len())?;
        let mut reduced = values.to_vec();
        for o in &self.outputs {
            reduced[o.node] = 0.;
        }
        Ok(reduced)
    }
    pub(crate) fn charge_frame_storage(
        &self,
        states: usize,
        voltages: usize,
        values: &crate::event_value_proof::Proofs,
        times: &std::collections::BTreeMap<usize, crate::exact_source::RootTime>,
    ) -> Result<(), Error> {
        // Bounds cover owned AST/string storage; dense matrices and actual
        // arbitrary-precision certificates are added from the current frame.
        self.charge(
            "forcing_frame_copy",
            self.copy_items + self.dimensions * self.dimensions * 16 + states * 64 + voltages * 16,
        )?;
        for value in values.values() {
            self.charge_rational(value)?;
        }
        for value in times.values() {
            self.charge_rational(value.rational())?;
        }
        Ok(())
    }
    fn charge_rational(&self, r: &num_rational::BigRational) -> Result<(), Error> {
        self.charge(
            "forcing_exact_copy_limbs",
            4 + (r.numer().bits().div_ceil(64) + r.denom().bits().div_ceil(64)) as usize,
        )
    }
    fn charge(&self, kind: &'static str, n: usize) -> Result<(), Error> {
        self.context.source_charge(kind, n)
    }
    fn items(&self, e: &E) -> Result<usize, Error> {
        self.charge("forcing_ast_visits", 1)?;
        Ok(match e {
            E::Affine { terms, .. } => {
                self.charge("forcing_term_visits", terms.len())?;
                1 + terms.len()
            }
            E::Add { left, right } | E::Multiply { left, right } => {
                1 + self.items(left)? + self.items(right)?
            }
            _ => return Err(scope()),
        })
    }
    fn interval(&self, e: &E, nodes: &[I]) -> Result<I, Error> {
        let items = self.items(e)?;
        self.charge("forcing_interval_work", items.saturating_mul(16))?;
        crate::expression::expression_interval(e, nodes)
    }
    fn resolve(&self, e: &E, nodes: &[I], time: f64) -> Result<E, Error> {
        self.charge("forcing_ast_visits", 1)?;
        Ok(match e {
            E::Select {
                relation,
                left,
                right,
                then_value,
                else_value,
                ..
            } => {
                let a = self.resolve(left, nodes, time)?;
                let b = self.resolve(right, nodes, time)?;
                let d = self.interval(&a, nodes)? - self.interval(&b, nodes)?;
                if !d.finite() {
                    return Err(Error::new(
                        "nonfinite_arithmetic",
                        "forcing predicate is nonfinite",
                    ));
                }
                let (yes, no) = match relation {
                    Relation::Lt => (d.hi < 0., d.lo >= 0.),
                    Relation::Le => (d.hi <= 0., d.lo > 0.),
                    Relation::Gt => (d.lo > 0., d.hi <= 0.),
                    Relation::Ge => (d.lo >= 0., d.hi < 0.),
                };
                let select = if yes || no {
                    yes
                } else {
                    let items = self.items(&a)? + self.items(&b)?;
                    self.charge(
                        "forcing_exact_lookup",
                        items
                            .saturating_mul(self.mapping.len() + 1)
                            .saturating_mul(8),
                    )?;
                    self.source
                        .forcing_predicate_reads(&a, &self.mapping, time, &self.ledger)?;
                    self.source
                        .forcing_predicate_reads(&b, &self.mapping, time, &self.ledger)?;
                    let sign = self.context.source_point_sign(&a, &b, time)?;
                    crate::diagnostics::counter("forcing_actual_exact_calls", 1);
                    match relation {
                        Relation::Lt => sign < 0,
                        Relation::Le => sign <= 0,
                        Relation::Gt => sign > 0,
                        Relation::Ge => sign >= 0,
                    }
                };
                return self.resolve(if select { then_value } else { else_value }, nodes, time);
            }
            E::Affine { terms, .. } => {
                self.charge("forcing_copy_items", 32 + terms.len() * 32)?;
                e.clone()
            }
            E::Add { left, right } | E::Multiply { left, right } => {
                self.charge("forcing_copy_items", 64)?;
                let a = Box::new(self.resolve(left, nodes, time)?);
                let b = Box::new(self.resolve(right, nodes, time)?);
                if matches!(e, E::Add { .. }) {
                    E::Add { left: a, right: b }
                } else {
                    E::Multiply { left: a, right: b }
                }
            }
            _ => return Err(scope()),
        })
    }
    pub(crate) fn project(
        &self,
        time: f64,
        actual: &Trajectory,
        solution: &mut Solution,
        circuit: &mut Circuit,
    ) -> Result<(), Error> {
        // Compare the actual execution provider with the original request binding.
        // This scan/copy charge precedes traversal; reduced Program is never
        // offered as an alternative source-proof identity.
        self.provider_matches(actual)?;
        if !time.is_finite() || time < 0. || time > self.source.config.stop {
            return Err(scope());
        }
        self.charge(
            "forcing_prepare_work",
            self.copy_items + self.dimensions * 64,
        )?;
        let (values, boxes) = self.source.forcing_values_bounds(time, &self.ledger)?;
        let mut nominal = vec![0.; self.dimensions];
        let mut nodes = vec![I::ZERO; self.dimensions];
        for ((&n, &v), &b) in self.mapping.iter().zip(&values).zip(&boxes) {
            nominal[n] = v;
            nodes[n] = b;
        }
        self.charge("forcing_copy_items", self.copy_items)?;
        let mut rows = Vec::new();
        for o in &self.outputs {
            let selected = self.resolve(&o.value, &nodes, time)?;
            self.charge(
                "forcing_dense_work",
                self.items(&selected)?
                    .saturating_mul(self.dimensions)
                    .saturating_mul(self.dimensions)
                    .saturating_mul(18),
            )?;
            let value = crate::expression::evaluate(&selected, &nominal)?.value;
            let bound = self.interval(&selected, &nodes)?;
            if !value.is_finite() || !bound.finite() {
                return Err(Error::new(
                    "nonfinite_arithmetic",
                    "forcing output is nonfinite",
                ));
            }
            let error = (value - bound.lo).abs().max((bound.hi - value).abs());
            let allowed = self.tolerances.absolute
                + self.tolerances.relative * value.abs().max(bound.magnitude());
            if error > allowed {
                return Err(Error::new(
                    "waveform_accuracy",
                    "forcing output forward-error box exceeds original voltage tolerance",
                ));
            }
            let sign = if o.positive == 0 { -1. } else { 1. };
            rows.push((
                o.node,
                o.positive,
                o.negative,
                value,
                sign * value,
                if sign > 0. { bound } else { -bound },
                selected,
                o.origin.clone(),
            ));
        }
        // The circuit replaces the provisional row with the original resolved
        // relation and checks its residual before the Frame can be accepted.
        self.charge("forcing_copy_items", self.copy_items.saturating_mul(2))?;
        circuit.install_forcing_phase(Arc::as_ptr(&self.context) as usize, time, solution, rows)
    }
}

#[cfg(test)]
mod lookup_tests {
    use super::*;
    fn names() -> Vec<String> {
        let prefix = "p".repeat(250);
        (0..64).map(|i| format!("{prefix}{i:04}")).collect()
    }
    #[test]
    fn forcing_lookup_long_common_prefix_multiple_drivers_prepays_actual_byte_work() {
        let nodes = names();
        let work = Work::default();
        let (result, report) = crate::diagnostics::capture(Default::default(), || {
            for i in 32..64 {
                assert_eq!(lookup_node(&nodes, &nodes[i], &work)?, i);
            }
            Ok(())
        });
        result.unwrap();
        println!(
            "lookup_default_cost {}",
            serde_json::to_string(&report.counters).unwrap()
        );
        let comparisons: u64 = (32..64).map(|j| j + 1).sum();
        // All names have250 common p bytes and two common leading decimal0s.
        // The tens digit is always visited; equal tens also visit ones.
        let bytes: u64 = (32..64)
            .map(|j| {
                (0..=j)
                    .map(|i| 253 + u64::from(i / 10 == j / 10))
                    .sum::<u64>()
            })
            .sum();
        let bound = 32 * 64 * 255;
        assert_eq!(report.counters["forcing_lookup_comparisons"], comparisons);
        assert_eq!(report.counters["forcing_lookup_byte_comparisons"], bytes);
        assert_eq!(report.counters["forcing_lookup_reserved_work"], bound);
        assert!(comparisons + bytes <= bound);
    }
    #[test]
    fn forcing_lookup_short_budget_and_two_retries_reject_before_any_compare() {
        let nodes = names();
        let required = 64 * 255;
        // Deliberately reduced unit-test limit locates prepayment ordering.
        // This is NOT evidence of natural exhaustion of the default1e9 cap.
        let work = Work::limited([128, 8192, required - 1]);
        let mut results = Vec::new();
        let (_, report) = crate::diagnostics::capture(Default::default(), || {
            results.push(lookup_node(&nodes, &nodes[63], &work));
            for _ in 0..2 {
                results.push(lookup_node(&nodes, "x", &work));
            }
            Ok(())
        });
        println!(
            "lookup_short_limit {limit} {}",
            serde_json::to_string(&report.counters).unwrap(),
            limit = required - 1
        );
        assert_eq!(results.len(), 3);
        for result in results {
            assert_eq!(result.err().unwrap().kind, "step_budget");
        }
        assert_eq!(
            report
                .counters
                .get("forcing_lookup_comparisons")
                .copied()
                .unwrap_or(0),
            0
        );
        assert_eq!(
            report
                .counters
                .get("forcing_lookup_byte_comparisons")
                .copied()
                .unwrap_or(0),
            0
        );
        assert_eq!(
            report
                .counters
                .get("forcing_lookup_reserved_work")
                .copied()
                .unwrap_or(0),
            0
        );
        assert_eq!(
            report.counters["forcing_lookup_requested_work"],
            required + 2 * 64 * 2
        );
    }
}
