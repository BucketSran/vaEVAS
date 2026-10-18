//! Immutable proofs for piecewise-held targets selected by original PWL inputs.
//! This module never advances or publishes accepted transition history.
use crate::events::AffineState;
use crate::exact_source::RootTime;
use crate::interval::Interval as I;
use crate::ir::{Error, Expression, Program, Relation};
use crate::pwl::Trajectory;
use num_traits::Zero;
use std::collections::{BTreeMap, BTreeSet};
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
    pub(crate) fn limited(limits: [u64; 3]) -> Self {
        Self(Arc::new(Counters {
            plans: AtomicU64::new(0),
            cuts: AtomicU64::new(0),
            work: AtomicU64::new(0),
            limits,
        }))
    }
    pub(crate) fn debit(&self, slot: usize, amount: u64) -> Result<(), Error> {
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
    pub(crate) fn step(&self) -> Result<(), Error> {
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

fn binary_dc_value(
    value: &num_rational::BigRational,
    slope: &num_rational::BigRational,
) -> Result<f64, Error> {
    let bounds = crate::exact_source::enclosure(value)
        .ok_or_else(|| invalid("cannot enclose source slew DC value"))?;
    if !slope.is_zero() || bounds.lo != bounds.hi {
        return Err(unsupported(
            "source slew DC source must be constant and exactly binary64 representable",
        ));
    }
    Ok(bounds.lo)
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
    owner: String,
    left: Expression,
    right: Expression,
    root: Option<RootTime>,
    sign: i8,
}

struct ProvenCuts {
    owner: String,
    guard: Expression,
    cuts: Vec<RootTime>,
}

/// One immutable original Program/Trajectory binding. Sharing is explicit and
/// never follows Work alone: unrelated source contexts may share a quota pool.
/// No accepted target, cursor, or history is stored in this proof context.
pub(crate) struct ProofContext {
    program: Arc<Program>,
    trajectory: Arc<Trajectory>,
    driven: Vec<String>,
    input_nodes: Vec<usize>,
    work: Work,
    proofs: Mutex<Vec<ProvenSign>>,
    cuts: Mutex<Vec<ProvenCuts>>,
}
impl ProofContext {
    /// Only rate-limited targets may replace whole-domain physical DC leaves.
    /// Predicates keep their original curves and real-root partition. Audit the
    /// original tree first, including masked operands and zero-weight sources.
    pub(crate) fn slew_dc_leaves(
        &self,
        expression: &Expression,
        owner: &str,
    ) -> Result<Expression, Error> {
        fn audit(e: &Expression, context: &ProofContext) -> Result<(), Error> {
            context.work.step()?;
            match e {
                Expression::Affine { constant, terms } => {
                    if !constant.is_finite() {
                        return Err(invalid("nonfinite source slew target"));
                    }
                    if terms.len() > crate::exact_source::MAX_POINTS {
                        return Err(unsupported(
                            "source slew affine terms exceed exact source limits",
                        ));
                    }
                    for term in terms {
                        context.work.step()?;
                        if !term.coefficient.is_finite()
                            || term.node != 0 && !context.input_nodes.contains(&term.node)
                        {
                            return Err(unsupported(
                                "source slew targets require original driven nodes",
                            ));
                        }
                    }
                }
                Expression::Select {
                    left,
                    right,
                    then_value,
                    else_value,
                    ..
                } => {
                    for child in [left, right, then_value, else_value] {
                        audit(child, context)?;
                    }
                }
                Expression::Add { left, right } | Expression::Multiply { left, right } => {
                    audit(left, context)?;
                    audit(right, context)?;
                }
                _ => {
                    return Err(unsupported(
                        "source slew DC targets require source-only sums and constant products",
                    ))
                }
            }
            Ok(())
        }
        fn normalize(
            e: &Expression,
            context: &ProofContext,
            constants: &mut BTreeMap<usize, f64>,
        ) -> Result<Expression, Error> {
            context.work.step()?;
            Ok(match e {
                Expression::Select {
                    relation,
                    left,
                    right,
                    then_value,
                    else_value,
                    origin,
                } => Expression::Select {
                    relation: *relation,
                    left: left.clone(),
                    right: right.clone(),
                    then_value: Box::new(normalize(then_value, context, constants)?),
                    else_value: Box::new(normalize(else_value, context, constants)?),
                    origin: origin.clone(),
                },
                Expression::Add { left, right } => Expression::Add {
                    left: Box::new(normalize(left, context, constants)?),
                    right: Box::new(normalize(right, context, constants)?),
                },
                Expression::Multiply { left, right } => Expression::Multiply {
                    left: Box::new(normalize(left, context, constants)?),
                    right: Box::new(normalize(right, context, constants)?),
                },
                Expression::Affine {
                    constant: value,
                    terms,
                } => {
                    let mut result = constant(*value);
                    for term in terms {
                        context.work.step()?;
                        let dc = if term.node == 0 {
                            0.
                        } else if let Some(value) = constants.get(&term.node) {
                            *value
                        } else {
                            context.work.exact()?;
                            let node = Expression::Affine {
                                constant: 0.,
                                terms: vec![crate::ir::Term {
                                    node: term.node,
                                    coefficient: 1.,
                                }],
                            };
                            let (value, slope) = context
                                .trajectory
                                .original_guard_curve(&node, &context.input_nodes)
                                .and_then(|curve| {
                                    curve.affine_on(I {
                                        lo: 0.,
                                        hi: context.trajectory.config.stop,
                                    })
                                })
                                .ok_or_else(|| {
                                    unsupported(
                                        "source slew leaf needs a whole-domain physical DC source",
                                    )
                                })?;
                            let dc = binary_dc_value(&value, &slope)?;
                            constants.insert(term.node, dc);
                            dc
                        };
                        // Preserve every product and sum. Rounding the complete
                        // leaf here would erase forward error under later gain.
                        result = Expression::Add {
                            left: Box::new(result),
                            right: Box::new(Expression::Multiply {
                                left: Box::new(constant(term.coefficient)),
                                right: Box::new(constant(dc)),
                            }),
                        };
                    }
                    result
                }
                _ => return Err(unsupported("invalid source slew DC target")),
            })
        }
        audit(expression, self)?;
        crate::continuous::validate_selection(expression, &self.program, &self.driven, owner)?;
        normalize(expression, self, &mut BTreeMap::new())
    }

    pub(crate) fn new(
        program: &Program,
        trajectory: &Trajectory,
        driven: &[String],
        work: Work,
    ) -> Result<Arc<Self>, Error> {
        let input_nodes = driven
            .iter()
            .map(|name| {
                program
                    .nodes
                    .iter()
                    .position(|n| n == name)
                    .ok_or_else(|| Error::new("invalid_inputs", "unknown source-target input"))
            })
            .collect::<Result<Vec<_>, _>>()?;
        Ok(Arc::new(Self {
            program: Arc::new(program.clone()),
            trajectory: Arc::new(trajectory.clone()),
            driven: driven.to_vec(),
            input_nodes,
            work,
            proofs: Mutex::new(Vec::new()),
            cuts: Mutex::new(Vec::new()),
        }))
    }
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
    // Pure results are scoped to the complete immutable source identity. Each
    // insertion has paid the original exact reservation and cut quota.
    context: Arc<ProofContext>,
}
impl Spec {
    /// Independent source contexts remain available to direct proof tests.
    #[cfg(test)]
    pub(crate) fn new(
        expression: &Expression,
        program: &Program,
        trajectory: &Trajectory,
        driven: &[String],
        owner: &str,
        work: Work,
    ) -> Result<Option<Arc<Self>>, Error> {
        Self::new_with_context(
            expression,
            ProofContext::new(program, trajectory, driven, work)?,
            owner,
        )
    }
    pub(crate) fn new_with_context(
        expression: &Expression,
        context: Arc<ProofContext>,
        owner: &str,
    ) -> Result<Option<Arc<Self>>, Error> {
        let program = context.program.as_ref();
        let driven = context.driven.as_slice();
        let work = context.work.clone();
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
            program: context.program.clone(),
            trajectory: context.trajectory.clone(),
            input_nodes: context.input_nodes.clone(),
            owner: owner.into(),
            dependencies,
            predicate_dependencies,
            work,
            context,
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
        let mut proofs = self.context.proofs.lock().unwrap();
        if let Some(proof) = proofs.iter().find(|p| {
            p.owner == self.owner && p.left == *left && p.right == *right && p.root.as_ref() == root
        }) {
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
                owner: self.owner.clone(),
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
    /// A held-only guard is constant throughout this epoch. Certify the
    /// relation over its whole enclosure, never a representative state value.
    /// Source-dependent guards retain the original exact-root/cut proof path.
    fn held_decision(
        &self,
        left: &Expression,
        right: &Expression,
        relation: &Relation,
        states: &[I],
    ) -> Result<Option<bool>, Error> {
        self.work.step()?;
        let (mut nodes, mut dependencies, mut operators) =
            crate::continuous::integral_dependency_edges(left, &self.program, &self.owner)?;
        let (rn, rs, ro) =
            crate::continuous::integral_dependency_edges(right, &self.program, &self.owner)?;
        nodes.extend(rn);
        dependencies.extend(rs);
        operators.extend(ro);
        if !dependencies.iter().any(|&k| states[k].lo != states[k].hi)
            || nodes.iter().any(|&k| k != 0)
            || !operators.is_empty()
        {
            return Ok(None);
        }
        let a = crate::affine_bounds::affine(left, &self.program)?;
        let b = crate::affine_bounds::affine(right, &self.program)?;
        let start = self.program.nodes.len();
        let mut enclosure = *a.last().unwrap() - *b.last().unwrap();
        for (k, state) in states.iter().enumerate() {
            self.work.step()?;
            enclosure = enclosure + (a[start + k] - b[start + k]) * *state;
        }
        if !enclosure.finite() {
            return Err(invalid("nonfinite held source-target predicate enclosure"));
        }
        let decision = match relation {
            Relation::Lt if enclosure.hi < 0. => Some(true),
            Relation::Lt if enclosure.lo >= 0. => Some(false),
            Relation::Le if enclosure.hi <= 0. => Some(true),
            Relation::Le if enclosure.lo > 0. => Some(false),
            Relation::Gt if enclosure.lo > 0. => Some(true),
            Relation::Gt if enclosure.hi <= 0. => Some(false),
            Relation::Ge if enclosure.lo >= 0. => Some(true),
            Relation::Ge if enclosure.hi < 0. => Some(false),
            _ => None,
        };
        decision.map(Some).ok_or_else(|| {
            invalid("held source-target predicate is indeterminate over its enclosure")
        })
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
                let yes = match self.held_decision(&left, &right, relation, states)? {
                    Some(yes) => yes,
                    None => {
                        let sign = self.sign(&left, &right, states, time)?;
                        match relation {
                            Relation::Lt => sign < 0,
                            Relation::Le => sign <= 0,
                            Relation::Gt => sign > 0,
                            Relation::Ge => sign >= 0,
                        }
                    }
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
    fn proven_cuts(&self, guard: &Expression) -> Result<Vec<RootTime>, Error> {
        let mut cache = self.context.cuts.lock().unwrap();
        if let Some(proof) = cache
            .iter()
            .find(|p| p.owner == self.owner && p.guard == *guard)
        {
            // Previously exhausted reservations stay sticky on cache hits.
            self.work.debit(2, 0)?;
            // The proof is shared, but this caller materializes its own roots.
            // Reserve every root entry before cloning into another plan.
            self.work.debit(1, proof.cuts.len() as u64)?;
            crate::diagnostics::counter("source_cut_proof_hits", 1);
            crate::diagnostics::counter("source_cut_materialized_roots", proof.cuts.len());
            return Ok(proof.cuts.clone());
        }
        self.work.exact()?;
        let curve = self
            .trajectory
            .original_guard_curve(guard, &self.input_nodes)
            .ok_or_else(|| invalid("cannot prove complete source-target affine curve"))?;
        self.work.exact()?;
        let cuts = curve
            .isolated_zero_times()
            .ok_or_else(|| invalid("source-target original affine cuts are unproved"))?;
        self.work.debit(1, cuts.len() as u64)?;
        crate::diagnostics::counter("source_cut_proof_builds", 1);
        // Each successful entry reserved 400000 work. The unchanged 1e9
        // request quota permits at most 2500 such entries before exhaustion.
        if cache.len() < 2500 {
            // The immutable certificate owns an additional root vector, too.
            // Charge its actual storage separately before making that copy.
            self.work.debit(1, cuts.len() as u64)?;
            cache.push(ProvenCuts {
                owner: self.owner.clone(),
                guard: guard.clone(),
                cuts: cuts.clone(),
            });
            crate::diagnostics::counter("source_cut_certificate_roots", cuts.len());
        }
        crate::diagnostics::counter("source_cut_materialized_roots", cuts.len());
        Ok(cuts)
    }
    fn collect(&self, e: &Expression, states: &[I], cuts: &mut Vec<RootTime>) -> Result<(), Error> {
        self.collect_once(e, states, cuts, &mut Vec::new())
    }
    fn collect_once(
        &self,
        e: &Expression,
        states: &[I],
        cuts: &mut Vec<RootTime>,
        seen: &mut Vec<Expression>,
    ) -> Result<(), Error> {
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
                    self.collect_once(x, states, cuts, seen)?;
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
                        // All original structure above was still visited. A
                        // repeated bound guard has exactly the same complete
                        // root set in this plan; do not materialize it twice.
                        if !seen.iter().any(|previous| previous == &guard) {
                            cuts.extend(self.proven_cuts(&guard)?);
                            seen.push(guard);
                        }
                    }
                }
            }
            Expression::Add { left, right }
            | Expression::Multiply { left, right }
            | Expression::Divide { left, right } => {
                self.collect_once(left, states, cuts, seen)?;
                self.collect_once(right, states, cuts, seen)?;
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
    fn between(left: &Self, right: &Self, work: &Work) -> Result<Self, Error> {
        work.step()?;
        let t = left.bounds.hi + (right.bounds.lo - left.bounds.hi) / 2.;
        if left.bounds.hi < t && t < right.bounds.lo {
            Self::point(t)
        } else {
            work.exact()?;
            Self::new(
                RootTime::between(&left.exact, &right.exact)
                    .ok_or_else(|| invalid("cannot prove source open-cell witness"))?,
            )
        }
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
        Ok(())
    }
    pub(crate) fn build(spec: Arc<Spec>, states: &[I]) -> Result<Self, Error> {
        Self::build_with_point_policy(spec, states, true)
    }
    /// A rate limiter follows open-cell targets continuously. An isolated
    /// positive-time target value has no duration; t=0 still supplies the seed.
    pub(crate) fn build_for_slew(spec: Arc<Spec>, states: &[I]) -> Result<Self, Error> {
        fn held_or_history(expression: &Expression) -> bool {
            match expression {
                Expression::State { .. } | Expression::Operator { .. } => true,
                Expression::Select {
                    left,
                    right,
                    then_value,
                    else_value,
                    ..
                } => [left, right, then_value, else_value]
                    .iter()
                    .any(|e| held_or_history(e)),
                Expression::Add { left, right }
                | Expression::Multiply { left, right }
                | Expression::Divide { left, right } => {
                    held_or_history(left) || held_or_history(right)
                }
                Expression::Power { base, .. } => held_or_history(base),
                _ => false,
            }
        }
        if !spec.dependencies.is_empty() || held_or_history(&spec.expression) {
            return Err(unsupported(
                "source slew plans cannot depend on held state or history",
            ));
        }
        Self::build_with_point_policy(spec, states, false)
    }
    fn build_with_point_policy(
        spec: Arc<Spec>,
        states: &[I],
        strict_points: bool,
    ) -> Result<Self, Error> {
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
        Self::with_point_policy(spec, states, Arc::new(cuts), strict_points)
    }
    fn with_cuts(spec: Arc<Spec>, states: &[I], cuts: Arc<Vec<Cut>>) -> Result<Self, Error> {
        Self::with_point_policy(spec, states, cuts, true)
    }
    fn with_point_policy(
        spec: Arc<Spec>,
        states: &[I],
        cuts: Arc<Vec<Cut>>,
        strict_points: bool,
    ) -> Result<Self, Error> {
        crate::diagnostics::counter("source_plan_context_calls", 1);
        let mut points = Vec::new();
        let mut modes = Vec::new();
        for t in cuts.iter() {
            points.push(spec.target(states, t)?);
        }
        for pair in cuts.windows(2) {
            let witness = Cut::between(&pair[0], &pair[1], &spec.work)?;
            modes.push(spec.target(states, &witness)?);
        }
        // This preliminary check uses one frozen held epoch. The runtime must
        // additionally call prepare with OLD accepted target after settlement.
        for k in 1..cuts.len() - 1 {
            if strict_points
                && !points[k].proven_equal(&modes[k - 1], &spec)?
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
        if self
            .spec
            .dependencies
            .iter()
            .all(|&k| states[k] == self.states[k])
        {
            return Ok(true);
        }
        // Reuse one immutable target partition when only a held-only guard
        // changes its enclosure, and every selected target certificate stays
        // identical. This performs the proof again; it does not reserve a new
        // plan or pretend the old state enclosure contains the new one.
        let unchanged = |dependencies: &BTreeSet<usize>| {
            dependencies.iter().all(|&k| states[k] == self.states[k])
        };
        fn fixed_cuts(e: &Expression, p: &Plan, states: &[I]) -> Result<bool, Error> {
            p.spec.work.step()?;
            match e {
                Expression::Select {
                    left,
                    right,
                    then_value,
                    else_value,
                    ..
                } => {
                    let (mut nodes, mut held, _) = crate::continuous::integral_dependency_edges(
                        left,
                        &p.spec.program,
                        &p.spec.owner,
                    )?;
                    let (rn, rh, _) = crate::continuous::integral_dependency_edges(
                        right,
                        &p.spec.program,
                        &p.spec.owner,
                    )?;
                    nodes.extend(rn);
                    held.extend(rh);
                    if nodes.iter().any(|&n| n != 0)
                        && held.iter().any(|&k| states[k] != p.states[k])
                    {
                        return Ok(false);
                    }
                    for x in [left, right, then_value, else_value] {
                        if !fixed_cuts(x, p, states)? {
                            return Ok(false);
                        }
                    }
                }
                Expression::Add { left, right }
                | Expression::Multiply { left, right }
                | Expression::Divide { left, right } => {
                    return Ok(fixed_cuts(left, p, states)? && fixed_cuts(right, p, states)?);
                }
                _ => {}
            }
            Ok(true)
        }
        if !fixed_cuts(&self.spec.expression, self, states)? {
            return Ok(false);
        }
        for leaf in forms(&self.spec.expression, &self.spec.work)? {
            if !unchanged(
                &crate::continuous::integral_dependency_edges(
                    &leaf,
                    &self.spec.program,
                    &self.spec.owner,
                )?
                .1,
            ) {
                return Ok(false);
            }
        }
        for (cut, old) in self.cuts.iter().zip(&self.points) {
            match self.spec.target(states, cut) {
                Ok(target) if target.same_certificate(old) => {}
                Ok(_) => return Ok(false),
                Err(e) if e.kind == "condition_precision" => return Ok(false),
                Err(e) => return Err(e),
            }
        }
        for (pair, old) in self.cuts.windows(2).zip(&self.modes) {
            let cut = Cut::between(&pair[0], &pair[1], &self.spec.work)?;
            match self.spec.target(states, &cut) {
                Ok(target) if target.same_certificate(old) => {}
                Ok(_) => return Ok(false),
                Err(e) if e.kind == "condition_precision" => return Ok(false),
                Err(e) => return Err(e),
            }
        }
        Ok(true)
    }
    pub(crate) fn seed(&self) -> Target {
        self.points[0].clone()
    }
    pub(crate) fn cuts(&self) -> &[Cut] {
        &self.cuts
    }
    /// Return only the certified open-right mode at an original cut. At stop,
    /// no right interval exists, so retain the certified incoming mode.
    pub(crate) fn slew_target_after(&self, root: &RootTime) -> Result<Target, Error> {
        self.spec.work.debit(2, 0)?;
        let index = self
            .cuts
            .binary_search_by(|cut| cut.exact.order(root))
            .map_err(|_| invalid("source slew target requires an original cut identity"))?;
        self.modes
            .get(index)
            .or_else(|| self.modes.last())
            .cloned()
            .ok_or_else(|| invalid("source slew has no proven open-cell target"))
    }
    pub(crate) fn next_after(&self, time: f64) -> Option<f64> {
        self.cuts.iter().find(|t| t.time > time).map(|cut| cut.time)
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
        if root.is_some_and(|r| r.refine(time_bounds).is_none()) {
            return Err(invalid(
                "source-target incoming root is outside its event window",
            ));
        }
        if time_bounds.lo < 0. || time_bounds.hi > self.spec.trajectory.config.stop {
            return Err(invalid("source-target time outside proven domain"));
        }
        for cut in self.cuts.iter() {
            if cut.bounds.lo <= time_bounds.hi && time_bounds.lo <= cut.bounds.hi {
                self.spec.work.step()?;
                // The source boundary is already at/before the lower endpoint,
                // while the proved physical event is strictly later. Closed
                // enclosure contact cannot reverse this exact ordering.
                if cut.bounds.hi <= time_bounds.lo
                    && root.is_some_and(|r| r.order(&cut.exact) == std::cmp::Ordering::Greater)
                {
                    continue;
                }
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
                    // This is a phase certificate over a complete immutable
                    // cut partition, not permission to choose by representative.
                    // Source::prepare consumes old/new held epochs in this
                    // exact order and hands every target change to history.
                    if root.is_some() {
                        continue;
                    }
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
        self.prepare_root(
            &RootTime::point(time).ok_or_else(|| invalid("invalid source point"))?,
            old,
        )
    }
    pub(crate) fn prepare_root(&self, root: &RootTime, old: &Target) -> Result<Target, Error> {
        self.spec.work.step()?;
        let k = self
            .cuts
            .partition_point(|t| t.exact.order(root) != std::cmp::Ordering::Greater);
        if k == 0 || root.order(&self.cuts.last().unwrap().exact) == std::cmp::Ordering::Greater {
            return Err(invalid("source-target time outside proven domain"));
        }
        let i = k - 1;
        let point = if self.cuts[i].exact.order(root) == std::cmp::Ordering::Equal {
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
    pub(crate) fn debit_boundary(&self) -> Result<(), Error> {
        self.spec.work.step()
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
    #[test]
    fn dc_target_binary_gate_rejects_nonrepresentable_rational_and_nonzero_slope() {
        use num_rational::BigRational as R;
        let zero = R::from_integer(0.into());
        assert!(binary_dc_value(&R::new(1.into(), 3.into()), &zero).is_err());
        assert!(binary_dc_value(&zero, &R::new(1.into(), 3.into())).is_err());
        assert_eq!(
            binary_dc_value(&R::new(3.into(), 4.into()), &zero).unwrap(),
            0.75
        );
    }

    #[test]
    fn dc_normalization_audits_hidden_dependencies_before_replacement() {
        let base = spec(
            selected(constant(1.), constant(0.)),
            [1., 1.],
            Work::default(),
        );
        let context = &base.context;
        let hidden = |e| Expression::Multiply {
            left: Box::new(constant(0.)),
            right: Box::new(e),
        };
        for bad in [
            Expression::State { state: 0 },
            Expression::Operator { operator: 0 },
            Expression::Affine {
                constant: 0.,
                terms: vec![Term {
                    node: 2,
                    coefficient: 0.,
                }],
            },
        ] {
            assert_eq!(
                context
                    .slew_dc_leaves(&selected(constant(1.), hidden(bad)), "M")
                    .unwrap_err()
                    .kind,
                "unsupported_operator"
            );
        }
        let normalized = context
            .slew_dc_leaves(&selected(source(), constant(0.)), "M")
            .unwrap();
        assert!(Spec::new_with_context(&normalized, context.clone(), "M")
            .unwrap()
            .is_some());
        // The old Transition entry remains strict for the same source leaf.
        assert!(
            Spec::new_with_context(&selected(source(), constant(0.)), context.clone(), "M")
                .is_err()
        );
    }

    #[test]
    fn dc_leaf_source_box_is_not_erased_under_zero_weight() {
        let base = spec(
            selected(constant(1.), constant(0.)),
            [1., 1.],
            Work::default(),
        );
        let mut config = base.trajectory.config.clone();
        config.pwl_errors_v = Some(vec![crate::ir::SourceError::Voltage(1e-9)]);
        let trajectory = Trajectory::new(config, 1).unwrap();
        let context =
            ProofContext::new(&base.program, &trajectory, &["u".into()], Work::default()).unwrap();
        let masked = Expression::Multiply {
            left: Box::new(constant(0.)),
            right: Box::new(source()),
        };
        let error = context
            .slew_dc_leaves(&selected(constant(1.), masked), "M")
            .unwrap_err();
        assert_eq!(error.kind, "unsupported_operator");
        assert!(error.message.contains("whole-domain physical DC"));
    }

    #[test]
    fn dc_leaf_private_proof_uses_physical_not_nominal_shape() {
        let base = spec(
            selected(constant(1.), constant(0.)),
            [1., 1.],
            Work::default(),
        );
        let mut config = base.trajectory.config.clone();
        config.pwl_errors_v = Some(vec![serde_json::from_value(json!({
          "voltage_error_bound_V":0.25,"exact_knots":[
            {"time_numerator":"0","time_denominator":"1","value_V":0.75},
            {"time_numerator":"1","time_denominator":"1","value_V":0.75}]}))
        .unwrap()]);
        let trajectory = Trajectory::new(config, 1).unwrap();
        let context =
            ProofContext::new(&base.program, &trajectory, &["u".into()], Work::default()).unwrap();
        let normalized = context
            .slew_dc_leaves(&selected(source(), constant(0.)), "M")
            .unwrap();
        let spec = Spec::new_with_context(&normalized, context, "M")
            .unwrap()
            .unwrap();
        let plan = Plan::build_for_slew(spec, &[I::point(2.)]).unwrap();
        assert_eq!(plan.seed().value, 0.75);
        assert_eq!(plan.seed().bounds, I::point(0.75));
        // Public source-error/operator admission remains outside this proof API.
    }

    #[test]
    fn dc_proof_reservations_share_sticky_request_exhaustion() {
        let base = spec(
            selected(constant(1.), constant(0.)),
            [1., 1.],
            Work::limited([128, 8192, 200_000]),
        );
        let expression = selected(source(), constant(0.));
        for _ in 0..2 {
            assert_eq!(
                base.context
                    .slew_dc_leaves(&expression, "M")
                    .unwrap_err()
                    .kind,
                "step_budget"
            );
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
    fn compare(relation: &str, threshold: f64, yes: Expression, no: Expression) -> Expression {
        serde_json::from_value(json!({
            "op":"select", "relation":relation, "left":source(), "right":constant(threshold),
            "then_value":yes, "else_value":no,
            "origin":{"source":"slew.va","line":1,"column":1,"instance":"M"}
        }))
        .unwrap()
    }
    fn isolated(threshold: f64) -> Expression {
        compare(
            "le",
            threshold,
            compare("ge", threshold, constant(1.), constant(0.)),
            constant(0.),
        )
    }
    #[test]
    fn slew_isolated_point_has_no_duration_but_transition_still_refuses() {
        let expression = isolated(0.5);
        let strict = spec(expression.clone(), [0., 1.], Work::default());
        assert_eq!(
            Plan::build(strict, &[I::ZERO]).err().unwrap().kind,
            "condition_precision"
        );
        let plan =
            Plan::build_for_slew(spec(expression, [0., 1.], Work::default()), &[I::ZERO]).unwrap();
        assert_eq!(plan.seed().value, 0.);
        assert_eq!(
            plan.slew_target_after(&RootTime::point(0.5).unwrap())
                .unwrap()
                .value,
            0.
        );
        // The old settlement entry point retains its point-value obligation.
        assert_eq!(
            plan.prepare_root(&RootTime::point(0.5).unwrap(), &plan.seed())
                .err()
                .unwrap()
                .kind,
            "condition_precision"
        );
    }
    #[test]
    fn slew_seed_stop_and_third_point_use_distinct_certificates() {
        let start = Plan::build_for_slew(spec(isolated(0.), [0., 1.], Work::default()), &[I::ZERO])
            .unwrap();
        assert_eq!(start.seed().value, 1.);
        assert_eq!(
            start
                .slew_target_after(&RootTime::point(0.).unwrap())
                .unwrap()
                .value,
            0.
        );
        let stop = Plan::build_for_slew(spec(isolated(1.), [0., 1.], Work::default()), &[I::ZERO])
            .unwrap();
        assert_eq!(stop.seed().value, 0.);
        assert_eq!(
            stop.slew_target_after(&RootTime::point(1.).unwrap())
                .unwrap()
                .value,
            0.
        );
        let third = Expression::Add {
            left: Box::new(compare("gt", 0.5, constant(2.), constant(0.))),
            right: Box::new(compare("lt", 0.5, constant(1.), constant(0.))),
        };
        assert!(Plan::build(spec(third.clone(), [0., 1.], Work::default()), &[I::ZERO]).is_err());
        let third =
            Plan::build_for_slew(spec(third, [0., 1.], Work::default()), &[I::ZERO]).unwrap();
        assert_eq!(third.seed().value, 1.);
        assert_eq!(
            third
                .slew_target_after(&RootTime::point(0.5).unwrap())
                .unwrap()
                .value,
            2.
        );
    }
    #[test]
    fn slew_requires_exact_cut_identity_and_preserves_sticky_exhaustion() {
        let work = Work::default();
        let plan = Plan::build_for_slew(
            spec(
                compare("gt", 1., constant(1.), constant(0.)),
                [0., 3.],
                work.clone(),
            ),
            &[I::ZERO],
        )
        .unwrap();
        let cut = plan
            .cuts()
            .iter()
            .find(|c| c.time > 0. && c.time < 1.)
            .unwrap();
        assert_eq!(plan.slew_target_after(&cut.exact).unwrap().value, 1.);
        assert_eq!(
            plan.slew_target_after(&RootTime::point(cut.time).unwrap())
                .err()
                .unwrap()
                .kind,
            "condition_precision",
            "upper binary64 representative is not the real one-third cut"
        );
        for time in [
            f64::from_bits(cut.time.to_bits() - 1),
            f64::from_bits(cut.time.to_bits() + 1),
        ] {
            assert!(plan
                .slew_target_after(&RootTime::point(time).unwrap())
                .is_err());
        }
        assert!(work.debit(2, 1_000_000_000).is_err());
        assert_eq!(
            plan.slew_target_after(&cut.exact).err().unwrap().kind,
            "step_budget"
        );
    }
    #[test]
    fn slew_rejects_held_dependencies_even_when_zero_weighted() {
        let expression = selected(
            Expression::Multiply {
                left: Box::new(constant(0.)),
                right: Box::new(Expression::State { state: 0 }),
            },
            constant(0.),
        );
        assert_eq!(
            Plan::build_for_slew(spec(expression, [0., 1.], Work::default()), &[I::ZERO])
                .err()
                .unwrap()
                .kind,
            "unsupported_operator"
        );
    }
    #[test]
    fn explicit_context_shares_successful_signs_across_operators_without_history() {
        let work = Work::default();
        let first = spec(selected(constant(1.), constant(0.)), [0., 1.], work.clone());
        let second = Spec::new_with_context(
            &selected(constant(2.), constant(0.)),
            first.context.clone(),
            "M",
        )
        .unwrap()
        .unwrap();
        let root = Cut::point(0.25).unwrap();
        assert_eq!(
            first
                .sign(&source(), &constant(0.5), &[I::ZERO], &root)
                .unwrap(),
            -1
        );
        let before = used(&work);
        assert_eq!(
            second
                .sign(&source(), &constant(0.5), &[I::ZERO], &root)
                .unwrap(),
            -1
        );
        assert_eq!(
            used(&work) - before,
            2,
            "a shared success pays binding work but no new exact reservation"
        );
        let a = first.target(&[I::ZERO], &Cut::point(1.).unwrap()).unwrap();
        let b = second.target(&[I::ZERO], &Cut::point(1.).unwrap()).unwrap();
        assert_eq!(a.value, 1.);
        assert_eq!(
            b.value, 2.,
            "only arithmetic proofs may be shared, never the selected target"
        );
        work.debit(2, 1_000_000_000).unwrap_err();
        assert_eq!(
            second
                .proof_sign(&source(), &constant(0.5), Some(&root.exact), "unused")
                .unwrap_err()
                .kind,
            "step_budget"
        );
    }
    #[test]
    fn repeated_guards_pay_cut_proofs_once_but_keep_each_plan_reservation() {
        let work = Work::default();
        let expression = selected(constant(1.), constant(0.));
        let first = spec(
            Expression::Add {
                left: Box::new(expression.clone()),
                right: Box::new(expression),
            },
            [0., 1.],
            work.clone(),
        );
        let a = Plan::build(first.clone(), &[I::ZERO]).unwrap();
        assert_eq!(a.cuts().len(), 3);
        assert_eq!(
            work.0.cuts.load(Ordering::Relaxed),
            8,
            "two endpoints, three materialized roots and three cached certificate roots"
        );
        assert_eq!(first.context.cuts.lock().unwrap().len(), 1);
        let next = Spec::new_with_context(
            &selected(constant(3.), constant(0.)),
            first.context.clone(),
            "M",
        )
        .unwrap()
        .unwrap();
        let b = Plan::build(next, &[I::ZERO]).unwrap();
        assert_eq!(b.cuts().len(), 3);
        assert_eq!(
            work.0.cuts.load(Ordering::Relaxed),
            13,
            "another plan reserves endpoints and all materialized root entries"
        );
        assert_eq!(work.0.plans.load(Ordering::Relaxed), 2);
        assert_eq!(first.context.cuts.lock().unwrap().len(), 1);
        work.debit(1, 8192).unwrap_err();
        let guard = first.context.cuts.lock().unwrap()[0].guard.clone();
        assert_eq!(first.proven_cuts(&guard).err().unwrap().kind, "step_budget");
    }
    #[test]
    fn cached_cuts_still_reserve_each_plans_materialized_storage() {
        // A guard that never crosses has the two original source endpoints.
        // The first plan pays two endpoints, two collected roots and two
        // cached certificate roots. A second plan must fail at ten entries
        // under limit9, even though its expensive proof is a cache hit.
        let work = Work::limited([128, 9, 1_000_000_000]);
        let first = spec(selected(constant(1.), constant(0.)), [1., 2.], work.clone());
        Plan::build(first.clone(), &[I::ZERO]).unwrap();
        assert_eq!(work.0.cuts.load(Ordering::Relaxed), 6);
        let second = Spec::new_with_context(
            &selected(constant(2.), constant(0.)),
            first.context.clone(),
            "M",
        )
        .unwrap()
        .unwrap();
        let before = used(&work);
        assert_eq!(
            Plan::build(second, &[I::ZERO]).err().unwrap().kind,
            "step_budget"
        );
        assert!(
            used(&work) - before < 200_000,
            "a cached proof saves exact work but not root storage quota"
        );
        assert_eq!(work.0.cuts.load(Ordering::Relaxed), 10);
        assert_eq!(
            first.context.cuts.lock().unwrap().len(),
            1,
            "only one expensive proof was built"
        );
    }
    #[test]
    fn cut_cache_keys_include_bound_held_values_and_failed_reservations_stay_failed() {
        let work = Work::default();
        let mut expression = selected(constant(1.), constant(0.));
        if let Expression::Select { right, .. } = &mut expression {
            **right = Expression::State { state: 0 };
        }
        let first = spec(expression, [0., 1.], work.clone());
        let a = Plan::build(first.clone(), &[I::point(0.25)]).unwrap();
        let b = Plan::build(first.clone(), &[I::point(0.75)]).unwrap();
        assert!(a.cuts().iter().any(|cut| cut.time == 0.25));
        assert!(b.cuts().iter().any(|cut| cut.time == 0.75));
        assert_eq!(first.context.cuts.lock().unwrap().len(), 2);
        let limited = Work::limited([128, 2, 1_000_000_000]);
        let failed = spec(
            selected(constant(1.), constant(0.)),
            [0., 1.],
            limited.clone(),
        );
        let mut cuts = Vec::new();
        assert_eq!(
            failed
                .collect(&failed.expression, &[I::ZERO], &mut cuts)
                .unwrap_err()
                .kind,
            "step_budget"
        );
        assert!(failed.context.cuts.lock().unwrap().is_empty());
        assert_eq!(
            failed
                .collect(&failed.expression, &[I::ZERO], &mut cuts)
                .unwrap_err()
                .kind,
            "step_budget"
        );
        assert!(
            failed.context.cuts.lock().unwrap().is_empty(),
            "unsuccessful proofs cannot be installed by retries"
        );
        // Enough room for the returned vector but not its certificate copy:
        // the second storage reservation is also sticky and installs nothing.
        let copy_limit = Work::limited([128, 3, 1_000_000_000]);
        let failed_copy = spec(
            selected(constant(1.), constant(0.)),
            [1., 2.],
            copy_limit.clone(),
        );
        let mut cuts = Vec::new();
        assert_eq!(
            failed_copy
                .collect(&failed_copy.expression, &[I::ZERO], &mut cuts)
                .unwrap_err()
                .kind,
            "step_budget"
        );
        assert_eq!(copy_limit.0.cuts.load(Ordering::Relaxed), 4);
        assert!(cuts.is_empty());
        assert!(failed_copy.context.cuts.lock().unwrap().is_empty());
        assert_eq!(
            failed_copy
                .collect(&failed_copy.expression, &[I::ZERO], &mut cuts)
                .unwrap_err()
                .kind,
            "step_budget"
        );
        assert!(failed_copy.context.cuts.lock().unwrap().is_empty());
    }
    #[test]
    fn shared_work_never_shares_a_proof_with_an_unrelated_or_uncertain_trajectory() {
        let work = Work::default();
        let first = spec(selected(constant(1.), constant(0.)), [0., 1.], work.clone());
        let a = Plan::build(first.clone(), &[I::ZERO]).unwrap();
        assert_eq!(a.cuts().len(), 3);
        let other = spec(selected(constant(1.), constant(0.)), [1., 0.], work.clone());
        let before = used(&work);
        assert_eq!(
            other
                .sign(
                    &source(),
                    &constant(0.5),
                    &[I::ZERO],
                    &Cut::point(0.25).unwrap()
                )
                .unwrap(),
            1
        );
        assert_eq!(
            used(&work) - before,
            200_002,
            "different immutable sources need an independent exact proof"
        );
        let noisy = Trajectory::new(
            TransientInputs {
                pwl_errors_v: Some(vec![crate::ir::SourceError::Voltage(0.01)]),
                strobetimes: vec![],
                pwl: vec![vec![[0., 0.], [1., 1.]]],
                output_times: vec![0., 1.],
                stop: 1.,
                max_step: 1.,
            },
            1,
        )
        .unwrap();
        let context = ProofContext::new(&first.program, &noisy, &["u".into()], work).unwrap();
        let noisy = Spec::new_with_context(&selected(constant(1.), constant(0.)), context, "M")
            .unwrap()
            .unwrap();
        assert_eq!(
            Plan::build(noisy.clone(), &[I::ZERO]).err().unwrap().kind,
            "condition_precision"
        );
        assert!(noisy.context.cuts.lock().unwrap().is_empty());
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

    fn held_selected(relation: &str, threshold: f64) -> Expression {
        serde_json::from_value(json!({
            "op":"select", "relation":relation,
            "left":Expression::State { state: 0 }, "right":constant(threshold),
            "then_value":constant(1.), "else_value":constant(0.),
            "origin":{"source":"held.va","line":1,"column":1,"instance":"M"}
        }))
        .unwrap()
    }

    #[test]
    fn held_interval_relations_certify_endpoints_and_refuse_straddles() {
        let spec = spec(
            selected(constant(1.), constant(0.)),
            [0., 1.],
            Work::default(),
        );
        let state = Expression::State { state: 0 };
        for (relation, bounds, expected) in [
            (Relation::Gt, I { lo: 1., hi: 2. }, true),
            (Relation::Gt, I { lo: -1., hi: 0. }, false),
            (Relation::Ge, I { lo: 0., hi: 1. }, true),
            (Relation::Ge, I { lo: -2., hi: -1. }, false),
            (Relation::Lt, I { lo: -2., hi: -1. }, true),
            (Relation::Lt, I { lo: 0., hi: 1. }, false),
            (Relation::Le, I { lo: -1., hi: 0. }, true),
            (Relation::Le, I { lo: 1., hi: 2. }, false),
        ] {
            assert_eq!(
                spec.held_decision(&state, &constant(0.), &relation, &[bounds])
                    .unwrap(),
                Some(expected)
            );
            assert_eq!(
                spec.held_decision(&state, &constant(0.), &relation, &[I { lo: -1., hi: 1. }])
                    .unwrap_err()
                    .kind,
                "condition_precision"
            );
        }
        // Contact with zero is ambiguous only for the relation whose truth
        // changes between that endpoint and the interval's interior.
        for (relation, bounds) in [
            (Relation::Gt, I { lo: 0., hi: 1. }),
            (Relation::Ge, I { lo: -1., hi: 0. }),
            (Relation::Lt, I { lo: -1., hi: 0. }),
            (Relation::Le, I { lo: 0., hi: 1. }),
        ] {
            assert_eq!(
                spec.held_decision(&state, &constant(0.), &relation, &[bounds])
                    .unwrap_err()
                    .kind,
                "condition_precision"
            );
        }
    }

    #[test]
    fn held_interval_rebind_changes_decision_and_failed_rebind_preserves_plan() {
        let spec = spec(
            selected(held_selected("gt", 0.5), constant(0.)),
            [1., 1.],
            Work::default(),
        );
        let old = Plan::build(spec, &[I { lo: 0.1, hi: 0.2 }]).unwrap();
        let before = old.clone();
        assert_eq!(old.seed().value, 0.);
        let changed = old.rebind(&[I { lo: 0.8, hi: 0.9 }]).unwrap();
        assert_eq!(changed.seed().value, 1.);
        assert!(!old.same_context(&[I { lo: 0.8, hi: 0.9 }]).unwrap());
        assert_eq!(
            old.rebind(&[I { lo: 0.4, hi: 0.6 }]).err().unwrap().kind,
            "condition_precision"
        );
        assert!(old.same_proof(&before));
        assert!(old
            .rebind(&[I { lo: 0.1, hi: 0.2 }])
            .unwrap()
            .same_proof(&before));
    }

    #[test]
    fn held_guard_contexts_reuse_one_partition_without_raising_plan_budget() {
        let work = Work::limited([1, 8192, 1_000_000_000]);
        let spec = spec(
            selected(held_selected("gt", 0.5), constant(0.)),
            [1., 1.],
            work.clone(),
        );
        let plan = Plan::build(spec, &[I { lo: 0.8, hi: 0.9 }]).unwrap();
        for k in 0..200 {
            let q = 1. + k as f64;
            assert!(plan.same_context(&[I { lo: q, hi: q + 0.1 }]).unwrap());
        }
        assert_eq!(work.0.plans.load(Ordering::Relaxed), 1);
        assert!(!plan.same_context(&[I { lo: 0.1, hi: 0.2 }]).unwrap());
        assert!(!plan.same_context(&[I { lo: 0.4, hi: 0.6 }]).unwrap());
    }

    #[test]
    fn unrepresentable_source_cell_has_a_strict_rational_witness() {
        let a = Cut::point(0.5).unwrap();
        let b = Cut::point(0.5_f64.next_up()).unwrap();
        let work = Work::default();
        let middle = Cut::between(&a, &b, &work).unwrap();
        assert_eq!(a.exact.order(&middle.exact), std::cmp::Ordering::Less);
        assert_eq!(middle.exact.order(&b.exact), std::cmp::Ordering::Less);
        assert_eq!(
            middle.bounds,
            I {
                lo: 0.5,
                hi: 0.5_f64.next_up()
            }
        );
        assert!(RootTime::between(&b.exact, &a.exact).is_none());
        assert!(RootTime::between(&a.exact, &a.exact).is_none());
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
