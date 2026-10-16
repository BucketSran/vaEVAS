//! Immutable proofs for piecewise-held targets selected by original PWL inputs.
//! This module never advances or publishes accepted transition history.
use crate::events::AffineState;
use crate::exact_source::RootTime;
use crate::interval::Interval as I;
use crate::ir::{Error, Expression, Program, Relation};
use crate::pwl::Trajectory;
use std::collections::BTreeSet;
use std::sync::{
    atomic::{AtomicU64, Ordering},
    Arc, Mutex,
};

fn invalid(message: &str) -> Error {
    Error::new("condition_precision", message)
}
fn unsupported(message: &str) -> Error {
    Error::new("unsupported_operator", message)
}

#[derive(Clone)]
pub(crate) struct Work(Arc<Counters>);
struct Counters {
    plans: AtomicU64,
    cuts: AtomicU64,
    work: AtomicU64,
    limits: [u64; 3],
}
impl Default for Work {
    fn default() -> Self {
        Self::limited([128, 8192, 1_000_000_000])
    }
}
impl Work {
    fn limited(limits: [u64; 3]) -> Self {
        Self(Arc::new(Counters {
            plans: AtomicU64::new(0),
            cuts: AtomicU64::new(0),
            work: AtomicU64::new(0),
            limits,
        }))
    }
    fn debit(&self, slot: usize, amount: u64) -> Result<(), Error> {
        let counter = [&self.0.plans, &self.0.cuts, &self.0.work][slot];
        // Failed reservations remain exhausted; a candidate clone cannot refund
        // proof work already attempted in this request.
        let mut old = counter.load(Ordering::Relaxed);
        loop {
            match counter.compare_exchange_weak(
                old,
                old.saturating_add(amount),
                Ordering::Relaxed,
                Ordering::Relaxed,
            ) {
                Ok(_) => break,
                Err(current) => old = current,
            }
        }
        if old
            .checked_add(amount)
            .is_none_or(|v| v > self.0.limits[slot])
        {
            return Err(Error::new(
                "step_budget",
                format!("source transition proof budget exhausted: slot {slot}, used {old} + {amount} exceeds {}",self.0.limits[slot]),
            ));
        }
        Ok(())
    }
    fn step(&self) -> Result<(), Error> {
        self.debit(2, 1)
    }
    fn exact(&self) -> Result<(), Error> {
        self.debit(2, 200_000)
    }
}

fn constant(value: f64) -> Expression {
    Expression::Affine {
        constant: value,
        terms: vec![],
    }
}

#[cfg(test)]
mod budget_tests {
    use super::Work;

    #[test]
    fn reservations_share_exhaustion_without_refunding_rejected_work() {
        let work = Work::limited([3, u64::MAX, 0]);
        let retry = work.clone();
        work.debit(0, 2).unwrap();
        retry.debit(0, 1).unwrap();
        assert_eq!(work.debit(0, 1).unwrap_err().kind, "step_budget");
        assert_eq!(retry.debit(0, 0).unwrap_err().kind, "step_budget");
        work.debit(1, u64::MAX).unwrap();
        assert_eq!(retry.debit(1, 1).unwrap_err().kind, "step_budget");
        assert_eq!(work.debit(1, 1).unwrap_err().kind, "step_budget");
        work.debit(2, 0).unwrap();
        assert_eq!(retry.debit(2, 1).unwrap_err().kind, "step_budget");
    }
}
fn bind(expr: &Expression, states: &[I], work: &Work) -> Result<Expression, Error> {
    work.step()?;
    Ok(match expr {
        Expression::State { state } => {
            let b = states
                .get(*state)
                .ok_or_else(|| invalid("missing source-target state"))?;
            if !b.finite() || b.lo != b.hi {
                return Err(invalid(
                    "source-target exact proof needs point held operands",
                ));
            }
            constant(b.lo)
        }
        Expression::Add { left, right } => Expression::Add {
            left: Box::new(bind(left, states, work)?),
            right: Box::new(bind(right, states, work)?),
        },
        Expression::Multiply { left, right } => Expression::Multiply {
            left: Box::new(bind(left, states, work)?),
            right: Box::new(bind(right, states, work)?),
        },
        Expression::Divide { left, right } => Expression::Divide {
            left: Box::new(bind(left, states, work)?),
            right: Box::new(bind(right, states, work)?),
        },
        Expression::Power { base, exponent } => Expression::Power {
            base: Box::new(bind(base, states, work)?),
            exponent: *exponent,
        },
        Expression::Select { .. } => return Err(invalid("unresolved source-target selection")),
        _ => expr.clone(),
    })
}

// Enumerate all affine candidates before evaluation, including masked arms.
pub(crate) fn forms(expr: &Expression, work: &Work) -> Result<Vec<Expression>, Error> {
    work.step()?;
    match expr {
        Expression::Select {
            then_value,
            else_value,
            ..
        } => {
            let mut out = forms(then_value, work)?;
            out.extend(forms(else_value, work)?);
            if out.len() > 8192 {
                return Err(Error::new(
                    "step_budget",
                    "source-target affine expansion exhausted",
                ));
            }
            Ok(out)
        }
        Expression::Add { left, right }
        | Expression::Multiply { left, right }
        | Expression::Divide { left, right } => {
            let a = forms(left, work)?;
            let b = forms(right, work)?;
            let mut out = Vec::new();
            for l in &a {
                for r in &b {
                    work.step()?;
                    if out.len() >= 8192 {
                        return Err(Error::new(
                            "step_budget",
                            "source-target affine expansion exhausted",
                        ));
                    }
                    let left = Box::new(l.clone());
                    let right = Box::new(r.clone());
                    out.push(match expr {
                        Expression::Add { .. } => Expression::Add { left, right },
                        Expression::Multiply { .. } => Expression::Multiply { left, right },
                        _ => Expression::Divide { left, right },
                    });
                }
            }
            Ok(out)
        }
        _ => Ok(vec![expr.clone()]),
    }
}

struct ProvenSign {
    left: Expression,
    right: Expression,
    root: Option<RootTime>,
    sign: i8,
}

pub(crate) struct Spec {
    expression: Expression,
    program: Arc<Program>,
    trajectory: Arc<Trajectory>,
    input_nodes: Vec<usize>,
    owner: String,
    pub(crate) dependencies: BTreeSet<usize>,
    pub(crate) predicate_dependencies: BTreeSet<usize>,
    work: Work,
    // Pure exact results belong to this original program/source context, never
    // to the shared Work or an accepted target/cursor. Each insertion already
    // reserved 200_000 work; the request's 1e9 limit permits at most 5000.
    proofs: Mutex<Vec<ProvenSign>>,
}
impl Spec {
    /// None means the old held-only implementation owns this input.
    pub(crate) fn new(
        expression: &Expression,
        program: &Program,
        trajectory: &Trajectory,
        driven: &[String],
        owner: &str,
        work: Work,
    ) -> Result<Option<Arc<Self>>, Error> {
        work.step()?;
        let (nodes, dependencies, operators) =
            crate::continuous::integral_dependency_edges(expression, program, owner)?;
        if nodes.iter().all(|n| *n == 0) {
            return Ok(None);
        }
        crate::continuous::validate_selection(expression, program, driven, owner)?;
        fn exact_domain(e: &Expression, w: &Work) -> Result<(), Error> {
            w.step()?;
            match e {
                Expression::Select{left,right,then_value,else_value,..}=>{
                    for x in [left,right,then_value,else_value]{exact_domain(x,w)?;}
                },
                Expression::Add{left,right}|Expression::Multiply{left,right}=>{
                    exact_domain(left,w)?;exact_domain(right,w)?;
                },
                Expression::EventMath{..}|Expression::Divide{..}|Expression::Power{..}=>return Err(unsupported(
                    "source-target exact arithmetic currently supports sums and constant products; division and powers are unsupported")),
                _=>{},
            }
            Ok(())
        }
        exact_domain(expression, &work)?;

        if !operators.is_empty() {
            return Err(unsupported(
                "source-target predicates cannot read histories",
            ));
        }
        let input_nodes = driven
            .iter()
            .map(|n| {
                program
                    .nodes
                    .iter()
                    .position(|v| v == n)
                    .ok_or_else(|| Error::new("invalid_inputs", "unknown source-target input"))
            })
            .collect::<Result<Vec<_>, _>>()?;
        for leaf in forms(expression, &work)? {
            let a = crate::events::affine(&leaf, program, owner)?;
            if a.node_dependencies.iter().any(|n| *n != 0) || !a.operator_dependencies.is_empty() {
                return Err(unsupported(
                    "transition value leaves must use held state and constants only",
                ));
            }
        }
        fn predicate_deps(
            e: &Expression,
            p: &Program,
            o: &str,
            out: &mut BTreeSet<usize>,
            w: &Work,
        ) -> Result<(), Error> {
            w.step()?;
            match e {
                Expression::Select {
                    left,
                    right,
                    then_value,
                    else_value,
                    ..
                } => {
                    for x in [left, right] {
                        out.extend(crate::continuous::integral_dependency_edges(x, p, o)?.1);
                    }
                    for x in [left, right, then_value, else_value] {
                        predicate_deps(x, p, o, out, w)?;
                    }
                }
                Expression::Add { left, right }
                | Expression::Multiply { left, right }
                | Expression::Divide { left, right } => {
                    predicate_deps(left, p, o, out, w)?;
                    predicate_deps(right, p, o, out, w)?;
                }
                Expression::Power { base, .. } => predicate_deps(base, p, o, out, w)?,
                _ => {}
            }
            Ok(())
        }
        let mut predicate_dependencies = BTreeSet::new();
        predicate_deps(
            expression,
            program,
            owner,
            &mut predicate_dependencies,
            &work,
        )?;
        Ok(Some(Arc::new(Self {
            expression: expression.clone(),
            program: Arc::new(program.clone()),
            trajectory: Arc::new(trajectory.clone()),
            input_nodes,
            owner: owner.into(),
            dependencies,
            predicate_dependencies,
            work,
            proofs: Mutex::new(Vec::new()),
        })))
    }
    pub(crate) fn equal_targets(&self, a: &Target, b: &Target) -> Result<bool, Error> {
        a.proven_equal(b, self)
    }
    fn proof_sign(
        &self,
        left: &Expression,
        right: &Expression,
        root: Option<&RootTime>,
        failure: &str,
    ) -> Result<i8, Error> {
        let mut proofs = self.proofs.lock().unwrap();
        if let Some(proof) = proofs
            .iter()
            .find(|p| p.left == *left && p.right == *right && p.root.as_ref() == root)
        {
            // Equality has no bind/step of its own. Even a pure proof hit must
            // refuse once another shared reservation exhausted this request.
            self.work.debit(2, 0)?;
            crate::diagnostics::counter("source_exact_proof_hits", 1);
            return Ok(proof.sign);
        }
        self.work.exact()?;
        crate::diagnostics::counter("source_exact_proof_builds", 1);
        let sign = match root {
            Some(root) => {
                let guard = Expression::Add {
                    left: Box::new(left.clone()),
                    right: Box::new(Expression::Multiply {
                        left: Box::new(constant(-1.)),
                        right: Box::new(right.clone()),
                    }),
                };
                self.trajectory
                    .original_guard_curve(&guard, &self.input_nodes)
                    .and_then(|curve| curve.sign_at_root(root))
            }
            None => crate::exact_source::predicate_sign(left, right, &[], &[], 0.),
        }
        .ok_or_else(|| invalid(failure))?;
        if proofs.len() < 5000 {
            proofs.push(ProvenSign {
                left: left.clone(),
                right: right.clone(),
                root: root.cloned(),
                sign,
            });
        }
        Ok(sign)
    }
    fn sign(
        &self,
        left: &Expression,
        right: &Expression,
        states: &[I],
        time: &Cut,
    ) -> Result<i8, Error> {
        let left = bind(left, states, &self.work)?;
        let right = bind(right, states, &self.work)?;
        crate::diagnostics::counter("source_predicate_sign_calls", 1);
        self.proof_sign(
            &left,
            &right,
            Some(&time.exact),
            "cannot prove source-target predicate at original real root",
        )
    }
    fn resolve(&self, e: &Expression, states: &[I], time: &Cut) -> Result<Expression, Error> {
        self.work.step()?;
        Ok(match e {
            Expression::Select {
                relation,
                left,
                right,
                then_value,
                else_value,
                ..
            } => {
                let left = self.resolve(left, states, time)?;
                let right = self.resolve(right, states, time)?;
                let sign = self.sign(&left, &right, states, time)?;
                let yes = match relation {
                    Relation::Lt => sign < 0,
                    Relation::Le => sign <= 0,
                    Relation::Gt => sign > 0,
                    Relation::Ge => sign >= 0,
                };
                return self.resolve(if yes { then_value } else { else_value }, states, time);
            }
            Expression::Add { left, right } => Expression::Add {
                left: Box::new(self.resolve(left, states, time)?),
                right: Box::new(self.resolve(right, states, time)?),
            },
            Expression::Multiply { left, right } => Expression::Multiply {
                left: Box::new(self.resolve(left, states, time)?),
                right: Box::new(self.resolve(right, states, time)?),
            },
            Expression::Divide { left, right } => Expression::Divide {
                left: Box::new(self.resolve(left, states, time)?),
                right: Box::new(self.resolve(right, states, time)?),
            },
            _ => e.clone(),
        })
    }
    fn collect(&self, e: &Expression, states: &[I], cuts: &mut Vec<RootTime>) -> Result<(), Error> {
        self.work.step()?;
        match e {
            Expression::Select {
                left,
                right,
                then_value,
                else_value,
                ..
            } => {
                for x in [left, right, then_value, else_value] {
                    self.collect(x, states, cuts)?;
                }
                for left in forms(left, &self.work)? {
                    for right in forms(right, &self.work)? {
                        self.work.step()?;
                        let (mut nodes, _, _) = crate::continuous::integral_dependency_edges(
                            &left,
                            &self.program,
                            &self.owner,
                        )?;
                        nodes.extend(
                            crate::continuous::integral_dependency_edges(
                                &right,
                                &self.program,
                                &self.owner,
                            )?
                            .0,
                        );
                        if nodes.iter().all(|n| *n == 0) {
                            continue;
                        }
                        let guard = Expression::Add {
                            left: Box::new(bind(&left, states, &self.work)?),
                            right: Box::new(Expression::Multiply {
                                left: Box::new(constant(-1.)),
                                right: Box::new(bind(&right, states, &self.work)?),
                            }),
                        };
                        self.work.exact()?;
                        let curve = self
                            .trajectory
                            .original_guard_curve(&guard, &self.input_nodes)
                            .ok_or_else(|| {
                                invalid("cannot prove complete source-target affine curve")
                            })?;
                        self.work.exact()?;
                        let found = curve.isolated_zero_times().ok_or_else(|| {
                            invalid("source-target original affine cuts are unproved")
                        })?;
                        self.work.debit(1, found.len() as u64)?;
                        cuts.extend(found);
                    }
                }
            }
            Expression::Add { left, right }
            | Expression::Multiply { left, right }
            | Expression::Divide { left, right } => {
                self.collect(left, states, cuts)?;
                self.collect(right, states, cuts)?;
            }
            _ => {}
        }
        Ok(())
    }
    fn target(&self, states: &[I], time: &Cut) -> Result<Target, Error> {
        let selected = self.resolve(&self.expression, states, time)?;
        let affine = crate::events::affine(&selected, &self.program, &self.owner)?;
        let proof = bind(&selected, states, &self.work)?;
        crate::diagnostics::counter("source_leaf_proof_calls", 1);
        self.proof_sign(
            &proof,
            &constant(0.),
            None,
            "cannot prove source-target leaf arithmetic",
        )?;
        let row = crate::affine_bounds::affine(&selected, &self.program)?;
        let coefficients: Vec<I> = row
            [self.program.nodes.len()..self.program.nodes.len() + self.program.states.len()]
            .iter()
            .copied()
            .chain([*row.last().unwrap()])
            .collect();
        let bounds = coefficients
            .iter()
            .zip(states.iter().copied().chain([I::ONE]))
            .fold(I::ZERO, |sum, (&a, b)| sum + a * b);
        let values: Vec<f64> = states.iter().map(|b| b.lo).collect();
        let value = affine.value(&[], &values)?;
        if !value.is_finite() || !bounds.finite() {
            return Err(invalid("nonfinite source-target leaf"));
        }
        Ok(Target {
            value,
            bounds,
            proof,
            affine,
            coefficients,
        })
    }
}

#[derive(Clone)]
pub(crate) struct Target {
    pub(crate) value: f64,
    pub(crate) bounds: I,
    proof: Expression,
    pub(crate) affine: AffineState,
    pub(crate) coefficients: Vec<I>,
}
impl Target {
    fn proven_equal(&self, other: &Self, spec: &Spec) -> Result<bool, Error> {
        crate::diagnostics::counter("source_target_equality_calls", 1);
        spec.proof_sign(
            &self.proof,
            &other.proof,
            None,
            "cannot compare source-target boundary values",
        )
        .map(|v| v == 0)
    }
    pub(crate) fn same_certificate(&self, other: &Self) -> bool {
        self.value == other.value
            && self.bounds == other.bounds
            && self.proof == other.proof
            && self.coefficients == other.coefficients
    }
}

#[derive(Clone, Debug, PartialEq)]
pub(crate) struct Cut {
    pub(crate) time: f64,
    pub(crate) bounds: I,
    pub(crate) exact: RootTime,
}
impl Cut {
    fn new(exact: RootTime) -> Result<Self, Error> {
        let bounds = exact
            .bounds()
            .ok_or_else(|| invalid("cannot enclose source root"))?;
        Ok(Self {
            time: bounds.hi,
            bounds,
            exact,
        })
    }
    fn point(time: f64) -> Result<Self, Error> {
        Self::new(RootTime::point(time).ok_or_else(|| invalid("invalid source point"))?)
    }
}

#[derive(Clone)]
pub(crate) struct Plan {
    spec: Arc<Spec>,
    states: Vec<I>,
    cuts: Arc<Vec<Cut>>,
    points: Vec<Target>,
    modes: Vec<Target>,
}
impl Plan {
    fn check_states(spec: &Spec, states: &[I]) -> Result<(), Error> {
        if states.len() != spec.program.states.len()
            || states.iter().any(|b| !b.finite() || b.lo > b.hi)
        {
            return Err(Error::new(
                "invalid_ir",
                "source-target state dimensions or enclosures are invalid",
            ));
        }
        if spec
            .predicate_dependencies
            .iter()
            .any(|&k| states[k].lo != states[k].hi)
        {
            return Err(invalid(
                "all source-target predicate state must be point-valued",
            ));
        }
        Ok(())
    }
    pub(crate) fn build(spec: Arc<Spec>, states: &[I]) -> Result<Self, Error> {
        crate::diagnostics::counter("source_plan_build_calls", 1);
        Self::check_states(&spec, states)?;
        spec.work.debit(0, 1)?;
        let mut cuts = vec![
            RootTime::point(0.).unwrap(),
            RootTime::point(spec.trajectory.config.stop).unwrap(),
        ];
        spec.work.debit(1, 2)?;
        spec.collect(&spec.expression, states, &mut cuts)?;
        cuts.sort_by(RootTime::order);
        cuts.dedup_by(|a, b| a.order(b) == std::cmp::Ordering::Equal);
        let cuts = cuts
            .into_iter()
            .map(Cut::new)
            .collect::<Result<Vec<_>, _>>()?;
        Self::with_cuts(spec, states, Arc::new(cuts))
    }
    fn with_cuts(spec: Arc<Spec>, states: &[I], cuts: Arc<Vec<Cut>>) -> Result<Self, Error> {
        crate::diagnostics::counter("source_plan_context_calls", 1);
        let mut points = Vec::new();
        let mut modes = Vec::new();
        for t in cuts.iter() {
            points.push(spec.target(states, t)?);
        }
        for pair in cuts.windows(2) {
            spec.work.step()?;
            let t = pair[0].bounds.hi + (pair[1].bounds.lo - pair[0].bounds.hi) / 2.;
            if !(pair[0].bounds.hi < t && t < pair[1].bounds.lo) {
                return Err(invalid("source cuts have no representable interior"));
            }
            modes.push(spec.target(states, &Cut::point(t)?)?);
        }
        // This preliminary check uses one frozen held epoch. The runtime must
        // additionally call prepare with OLD accepted target after settlement.
        for k in 1..cuts.len() - 1 {
            if !points[k].proven_equal(&modes[k - 1], &spec)?
                && !points[k].proven_equal(&modes[k], &spec)?
            {
                return Err(invalid(
                    "isolated source-target point or third boundary value",
                ));
            }
        }
        Ok(Self {
            spec,
            states: states.to_vec(),
            cuts,
            points,
            modes,
        })
    }
    /// Reuse immutable source cuts when only target values changed. Unchanged
    /// relevant held operands require no proof work or new plan reservation.
    pub(crate) fn rebind(&self, states: &[I]) -> Result<Self, Error> {
        Self::check_states(&self.spec, states)?;
        if self
            .spec
            .dependencies
            .iter()
            .all(|&k| states[k] == self.states[k])
        {
            return Ok(self.clone());
        }
        if self
            .spec
            .predicate_dependencies
            .iter()
            .any(|&k| states[k] != self.states[k])
        {
            return Self::build(self.spec.clone(), states);
        }
        self.spec.work.debit(0, 1)?;
        Self::with_cuts(self.spec.clone(), states, self.cuts.clone())
    }
    /// Reuse only a successful proof in this immutable Spec and original
    /// source trajectory. All structural state dependencies participate.
    pub(crate) fn same_context(&self, states: &[I]) -> Result<bool, Error> {
        Self::check_states(&self.spec, states)?;
        self.spec.work.step()?;
        Ok(self
            .spec
            .dependencies
            .iter()
            .all(|&k| states[k] == self.states[k]))
    }
    pub(crate) fn seed(&self) -> Target {
        self.points[0].clone()
    }
    pub(crate) fn cuts(&self) -> &[Cut] {
        &self.cuts
    }
    pub(crate) fn next_after(&self, time: f64) -> Option<f64> {
        self.cuts.iter().find(|t| t.time > time).map(|cut| cut.time)
    }
    pub(crate) fn due_at(&self, time: f64) -> bool {
        self.cut_at(time).is_some()
    }
    pub(crate) fn cut_at(&self, time: f64) -> Option<&Cut> {
        self.cuts
            .binary_search_by(|x| x.time.total_cmp(&time))
            .ok()
            .map(|i| &self.cuts[i])
    }
    pub(crate) fn check_incoming(
        &self,
        _after: f64,
        time_bounds: I,
        root: Option<&RootTime>,
    ) -> Result<(), Error> {
        if !time_bounds.finite() || time_bounds.lo > time_bounds.hi {
            return Err(invalid("invalid source-target event time"));
        }
        if time_bounds.lo < 0. || time_bounds.hi > self.spec.trajectory.config.stop {
            return Err(invalid("source-target time outside proven domain"));
        }
        for cut in self.cuts.iter() {
            if cut.bounds.lo <= time_bounds.hi && time_bounds.lo <= cut.bounds.hi {
                // A requested binary64 point at the lower endpoint is still
                // strictly before a nonpoint real cut. Enclosure contact is
                // not an event coincidence or a target change.
                if time_bounds.lo == time_bounds.hi
                    && time_bounds.hi < cut.time
                    && RootTime::point(time_bounds.hi)
                        .is_some_and(|point| point.order(&cut.exact) == std::cmp::Ordering::Less)
                {
                    continue;
                }
                let same =
                    root.is_some_and(|root| root.order(&cut.exact) == std::cmp::Ordering::Equal);
                if !same && time_bounds != cut.bounds {
                    return Err(Error::new(
                        "event_resolution",
                        format!("user event overlaps an unproved source-target boundary: incoming [{:.17e},{:.17e}], cut [{:.17e},{:.17e}], root order {:?}",time_bounds.lo,time_bounds.hi,cut.bounds.lo,cut.bounds.hi,root.map(|root|root.order(&cut.exact))),
                    ));
                }
                if !same && cut.bounds.lo != cut.bounds.hi {
                    return Err(Error::new(
                        "event_resolution",
                        "nonpoint source boundary requires the original root identity",
                    ));
                }
            }
        }
        Ok(())
    }
    /// Called only after final settlement. The caller commits this target and
    /// cursor atomically with old-history consumption and downstream histories.
    pub(crate) fn prepare(&self, time: f64, old: &Target) -> Result<Target, Error> {
        let k = self.cuts.partition_point(|t| t.time <= time);
        if k == 0 || time > self.cuts.last().unwrap().time {
            return Err(invalid("source-target time outside proven domain"));
        }
        let i = k - 1;
        let point = if self.cuts[i].time == time {
            &self.points[i]
        } else {
            &self.modes[i]
        };
        let right = if i < self.modes.len() {
            &self.modes[i]
        } else {
            point
        };
        if !point.proven_equal(old, &self.spec)? && !point.proven_equal(right, &self.spec)? {
            return Err(invalid(
                "final source-target point is neither old nor right target",
            ));
        }
        // At stop there is no proven right-hand interval. A held update may
        // still select the new epoch's already proved left mode. An isolated
        // endpoint value remains rejected; no source extrapolation is used.
        if i == self.modes.len()
            && !point.proven_equal(old, &self.spec)?
            && !match self.modes.last() {
                Some(left) => point.proven_equal(left, &self.spec)?,
                None => false,
            }
        {
            return Err(invalid("unproved terminal source-target change"));
        }
        Ok(right.clone())
    }
    pub(crate) fn same_proof(&self, other: &Self) -> bool {
        Arc::ptr_eq(&self.spec, &other.spec)
            && self.states == other.states
            && self.cuts == other.cuts
            && self.points.len() == other.points.len()
            && self.modes.len() == other.modes.len()
            && self
                .points
                .iter()
                .zip(&other.points)
                .all(|(a, b)| a.same_certificate(b))
            && self
                .modes
                .iter()
                .zip(&other.modes)
                .all(|(a, b)| a.same_certificate(b))
    }
}

#[cfg(test)]
mod proof_cache_tests {
    use super::*;
    use crate::ir::{Term, TransientInputs, SCHEMA_VERSION};
    use serde_json::json;

    fn source() -> Expression {
        Expression::Affine {
            constant: 0.,
            terms: vec![Term {
                node: 1,
                coefficient: 1.,
            }],
        }
    }
    fn selected(yes: Expression, no: Expression) -> Expression {
        serde_json::from_value(json!({
            "op":"select", "relation":"gt", "left":source(), "right":constant(0.5),
            "then_value":yes, "else_value":no,
            "origin":{"source":"proof.va","line":1,"column":1,"instance":"M"}
        }))
        .unwrap()
    }
    fn spec(expression: Expression, values: [f64; 2], work: Work) -> Arc<Spec> {
        let program: Program = serde_json::from_value(json!({
            "schema_version":SCHEMA_VERSION, "nodes":["0","u"], "contributions":[],
            "states":[{"instance":"M","name":"q","kind":"real","initial":2}]
        }))
        .unwrap();
        let trajectory = Trajectory::new(
            TransientInputs {
                pwl_errors_v: None,
                strobetimes: vec![],
                pwl: vec![vec![[0., values[0]], [1., values[1]]]],
                output_times: vec![0., 1.],
                stop: 1.,
                max_step: 1.,
            },
            1,
        )
        .unwrap();
        Spec::new(&expression, &program, &trajectory, &["u".into()], "M", work)
            .unwrap()
            .unwrap()
    }
    fn used(work: &Work) -> u64 {
        work.0.work.load(Ordering::Relaxed)
    }

    #[test]
    fn successful_leaf_and_equality_reuse_recomputes_current_target() {
        let work = Work::default();
        let spec = spec(
            selected(Expression::State { state: 0 }, constant(2.)),
            [0., 1.],
            work.clone(),
        );
        let states = [I::point(2.)];
        let late = Cut::point(1.).unwrap();
        spec.sign(&source(), &constant(0.5), &states, &late)
            .unwrap();
        let literal = spec.target(&states, &Cut::point(0.).unwrap()).unwrap();
        let before = used(&work);
        let held = spec.target(&states, &late).unwrap();
        assert_eq!(literal.proof, held.proof);
        assert_eq!(literal.value, held.value);
        assert_ne!(literal.coefficients, held.coefficients);
        assert!(
            used(&work) - before < 200_000,
            "same closed leaf must reuse only its exact proof"
        );
        assert!(spec.equal_targets(&literal, &held).unwrap());
        let before = used(&work);
        assert!(spec.equal_targets(&literal, &held).unwrap());
        assert_eq!(
            used(&work),
            before,
            "successful equality should not reserve exact arithmetic again"
        );
        let changed = spec.target(&[I::point(3.)], &late).unwrap();
        assert_eq!(changed.value, 3.);
        assert!(changed.bounds.lo <= 3. && 3. <= changed.bounds.hi);
        assert!(!spec.equal_targets(&literal, &changed).unwrap());
        for state in [
            I { lo: 2., hi: 3. },
            I::point(f64::INFINITY),
            I::point(f64::NAN),
        ] {
            assert_eq!(
                spec.target(&[state], &late).err().unwrap().kind,
                "condition_precision"
            );
        }
    }

    #[test]
    fn nominally_equal_targets_keep_distinct_exact_expression_proofs() {
        let exact_plus_one = Expression::Add {
            left: Box::new(constant(1e16)),
            right: Box::new(constant(1.)),
        };
        let spec = spec(
            selected(exact_plus_one, constant(1e16)),
            [0., 1.],
            Work::default(),
        );
        let a = spec.target(&[I::ZERO], &Cut::point(0.).unwrap()).unwrap();
        let b = spec.target(&[I::ZERO], &Cut::point(1.).unwrap()).unwrap();
        assert_eq!(a.value, b.value);
        assert!(!spec.equal_targets(&a, &b).unwrap());
        assert!(!spec.equal_targets(&a, &b).unwrap());
        assert!(!spec.equal_targets(&b, &a).unwrap());
    }

    #[test]
    fn sign_reuse_rebinds_threshold_and_preserves_operand_order() {
        let work = Work::default();
        let spec = spec(selected(constant(1.), constant(0.)), [0., 1.], work.clone());
        let cut = Cut::point(0.5).unwrap();
        let held = Expression::State { state: 0 };
        assert_eq!(
            spec.sign(&source(), &held, &[I::point(0.5)], &cut).unwrap(),
            0
        );
        let before = used(&work);
        assert_eq!(
            spec.sign(&source(), &held, &[I::point(0.5)], &cut).unwrap(),
            0
        );
        assert!(
            used(&work) - before < 200_000,
            "same bound expressions and original root should hit"
        );
        let threshold = I::point(0.5_f64.next_up());
        assert_eq!(spec.sign(&source(), &held, &[threshold], &cut).unwrap(), -1);
        assert_eq!(spec.sign(&held, &source(), &[threshold], &cut).unwrap(), 1);
        for states in [
            vec![I {
                lo: 0.5,
                hi: threshold.hi,
            }],
            vec![I::point(f64::INFINITY)],
            vec![I::point(f64::NAN)],
            vec![],
        ] {
            assert_eq!(
                spec.sign(&source(), &held, &states, &cut).unwrap_err().kind,
                "condition_precision"
            );
        }
    }

    #[test]
    fn sign_reuse_requires_exact_root_even_when_enclosures_match() {
        let work = Work::default();
        let spec = spec(selected(constant(1.), constant(0.)), [0., 3.], work.clone());
        let enclosure = I {
            lo: 1. / 6.,
            hi: (1. / 6.0_f64).next_up(),
        };
        let root = RootTime::affine(
            num_rational::BigRational::from_integer((-1).into()),
            num_rational::BigRational::from_integer(6.into()),
            enclosure,
        )
        .unwrap();
        let later = root.shifted_fixed(2.0_f64.powi(-60), enclosure).unwrap();
        assert_ne!(root, later);
        let a = Cut::new(root).unwrap();
        let b = Cut::new(later).unwrap();
        assert_eq!(a.bounds, b.bounds);
        assert_eq!(a.time.to_bits(), b.time.to_bits());
        assert_eq!(
            spec.sign(&source(), &constant(0.5), &[I::ZERO], &a)
                .unwrap(),
            0
        );
        assert_eq!(
            spec.sign(&source(), &constant(0.5), &[I::ZERO], &b)
                .unwrap(),
            1
        );
        assert_eq!(
            spec.sign(&constant(0.5), &source(), &[I::ZERO], &b)
                .unwrap(),
            -1
        );
        let before = used(&work);
        assert_eq!(
            spec.sign(&source(), &constant(0.5), &[I::ZERO], &a)
                .unwrap(),
            0
        );
        assert!(used(&work) - before < 200_000);
    }

    #[test]
    fn exact_failures_are_retried_and_failed_reservations_are_not_refunded() {
        let work = Work::default();
        let spec = spec(selected(constant(1.), constant(0.)), [0., 1.], work.clone());
        let cut = Cut::point(0.5).unwrap();
        for _ in 0..2 {
            let before = used(&work);
            assert_eq!(
                spec.sign(&source(), &constant(f64::INFINITY), &[I::ZERO], &cut)
                    .unwrap_err()
                    .kind,
                "condition_precision"
            );
            assert_eq!(used(&work) - before, 200_002);
        }
        let before = used(&work);
        assert_eq!(
            work.debit(2, 1_000_000_000).unwrap_err().kind,
            "step_budget"
        );
        assert_eq!(used(&work), before + 1_000_000_000);
        assert_eq!(
            spec.sign(&source(), &constant(0.), &[I::ZERO], &cut)
                .unwrap_err()
                .kind,
            "step_budget"
        );
        assert_eq!(used(&work), before + 1_000_000_001);

        let work = Work::limited([128, 8192, 200_100]);
        let spec = self::spec(selected(constant(1.), constant(0.)), [0., 1.], work.clone());
        spec.sign(&source(), &constant(0.), &[I::ZERO], &cut)
            .unwrap();
        let before = used(&work);
        assert_eq!(
            spec.sign(&source(), &constant(1.), &[I::ZERO], &cut)
                .unwrap_err()
                .kind,
            "step_budget"
        );
        assert_eq!(
            used(&work) - before,
            200_002,
            "failed exact reservation stays charged"
        );
    }

    #[test]
    fn cached_equality_still_refuses_after_shared_work_exhaustion() {
        let work = Work::default();
        let spec = spec(selected(constant(1.), constant(0.)), [0., 1.], work.clone());
        let a = spec.target(&[I::ZERO], &Cut::point(0.).unwrap()).unwrap();
        assert!(spec.equal_targets(&a, &a).unwrap());
        let before = used(&work);
        assert!(spec.equal_targets(&a, &a).unwrap());
        assert_eq!(used(&work), before);
        assert_eq!(
            work.debit(2, 1_000_000_000).unwrap_err().kind,
            "step_budget"
        );
        let exhausted = used(&work);
        assert_eq!(spec.equal_targets(&a, &a).unwrap_err().kind, "step_budget");
        assert_eq!(
            used(&work),
            exhausted,
            "a hit must check sticky exhaustion without a new reservation"
        );
    }

    #[test]
    fn independent_specs_keep_trajectory_proofs_separate_and_share_work() {
        let work = Work::default();
        let expression = selected(constant(1.), constant(0.));
        let positive = spec(expression.clone(), [1., 2.], work.clone());
        let negative = spec(expression.clone(), [-1., -2.], work.clone());
        let same_source_new_spec = spec(expression, [1., 2.], work.clone());
        let cut = Cut::point(0.5).unwrap();
        assert_eq!(
            positive
                .sign(&source(), &constant(0.), &[I::ZERO], &cut)
                .unwrap(),
            1
        );
        let before = used(&work);
        assert_eq!(
            negative
                .sign(&source(), &constant(0.), &[I::ZERO], &cut)
                .unwrap(),
            -1
        );
        assert_eq!(used(&work) - before, 200_002);
        let before = used(&work);
        assert_eq!(
            same_source_new_spec
                .sign(&source(), &constant(0.), &[I::ZERO], &cut)
                .unwrap(),
            1
        );
        assert_eq!(used(&work) - before, 200_002);
        let before = used(&work);
        assert_eq!(
            positive
                .sign(&source(), &constant(0.), &[I::ZERO], &cut)
                .unwrap(),
            1
        );
        assert_eq!(used(&work) - before, 2);
    }
}
