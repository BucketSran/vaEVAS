//! SourceSlew value qualification without Cartesian value assignments.
//! The old guard/root proof and limiter lifecycle are unchanged.
use super::{unsupported, ProofContext, ProvenSign, Work};
use crate::exact_source::RootTime;
use crate::interval::Interval as I;
use crate::ir::{Error, Expression as E, OperatorSpec, Program};
use crate::pwl::Trajectory;
use std::sync::{Arc, Mutex, OnceLock};
type DependencySets = (
    std::collections::BTreeSet<usize>,
    std::collections::BTreeSet<usize>,
    std::collections::BTreeSet<usize>,
);

#[derive(Clone, Copy)]
pub(super) struct Shape {
    pub forms: usize,
    items: usize,
    selected: bool,
    simple_guards: bool,
}
impl Shape {
    pub fn leaf(items: usize) -> Self {
        Self {
            forms: 1,
            items,
            selected: false,
            simple_guards: true,
        }
    }
    pub fn binary(a: Self, b: Self) -> Self {
        Self {
            forms: a.forms.saturating_mul(b.forms).min(8193),
            items: 1 + a.items + b.items,
            selected: a.selected || b.selected,
            simple_guards: a.simple_guards && b.simple_guards,
        }
    }
    pub fn select(a: Self, b: Self, c: Self, d: Self) -> Self {
        Self {
            forms: c.forms.saturating_add(d.forms).min(8193),
            items: 1 + a.items + b.items + c.items + d.items,
            selected: true,
            simple_guards: !a.selected
                && !b.selected
                && a.simple_guards
                && b.simple_guards
                && c.simple_guards
                && d.simple_guards,
        }
    }
}
pub(crate) struct Factor {
    work: Work,
    structural: Arc<Mutex<Option<usize>>>,
    owner: String,
    original_items: usize,
    saturated_forms: usize,
    program: Arc<Program>,
    trajectory: Arc<Trajectory>,
    normalized: OnceLock<E>,
}
impl Factor {
    pub(super) fn new(ctx: &ProofContext, e: &E, owner: &str, shape: Shape) -> Result<Self, Error> {
        // Structural qualification is additional to the source Work already
        // charged by the original DC audit; it cannot refill that Work.
        ctx.work.debit(0, 0)?;
        ctx.work.debit(1, 0)?;
        ctx.work.debit(2, 8)?;
        crate::diagnostics::counter("source_factor_factory_debit", 8);
        crate::diagnostics::counter("source_factor_work_debit", 8);
        let structural = ctx
            .factor_structural
            .get_or_init(|| {
                crate::diagnostics::counter("source_factor_structural_owners", 1);
                Arc::new(Mutex::new(Some(100_000usize)))
            })
            .clone();
        {
            let mut n = structural.lock().unwrap();
            *n = n.and_then(|x| x.checked_sub(shape.items));
            if n.is_none() {
                return Err(Error::new(
                    "resource_budget",
                    "source factor structural audit exhausted",
                ));
            }
        }
        crate::diagnostics::counter("source_factor_admissions", 1);
        let p = &ctx.program;
        if !shape.simple_guards
            || !p.states.is_empty()
            || !p.events.is_empty()
            || p.operators.len() != 1
            || p.contributions.len() != 1
        {
            return Err(unsupported(
                "factorized slew requires one source-only callsite and simple predicates",
            ));
        }
        let f = Self {
            work: ctx.work.clone(),
            structural,
            owner: String::new(),
            original_items: 0,
            saturated_forms: shape.forms,
            program: ctx.program.clone(),
            trajectory: ctx.trajectory.clone(),
            normalized: OnceLock::new(),
        };
        f.charge("source_factor_copy_debit", owner.len() + 1)?;
        let mut f = Self {
            owner: owner.into(),
            ..f
        };
        f.original_items = f.copy_tree(e)?;
        {
            let mut n = f.structural.lock().unwrap();
            *n = n.and_then(|x| x.checked_sub(f.original_items));
            if n.is_none() {
                return Err(Error::new(
                    "resource_budget",
                    "source factor original storage exceeds structural audit",
                ));
            }
        }
        if !matches!(&p.operators[0],OperatorSpec::Slew{input,origin,..} if input==e && origin.instance==owner)
            || p.contributions[0].origin.instance != owner
        {
            return Err(unsupported(
                "factorized slew must retain its original callsite binding",
            ));
        }
        f.dense(&p.contributions[0].rhs, p.nodes.len() + 2)?;
        let affine = crate::events::affine(&p.contributions[0].rhs, p, owner)?;
        if !affine.state_dependencies.is_empty()
            || affine.operator_dependencies.iter().any(|n| *n != 0)
            || affine
                .node_dependencies
                .iter()
                .any(|n| *n != 0 && !ctx.input_nodes.contains(n))
        {
            return Err(unsupported(
                "factorized slew output relation must use source nodes and its callsite",
            ));
        }
        f.charge(
            "source_factor_lookup_debit",
            p.nodes.len().saturating_mul(ctx.driven.len() + 1),
        )?;
        let unknown = (1..p.nodes.len())
            .filter(|n| !ctx.input_nodes.contains(n))
            .collect::<Vec<_>>();
        let c = &p.contributions[0];
        if unknown.len() != 1
            || ![c.positive, c.negative].contains(&unknown[0])
            || c.positive == c.negative
            || ![c.positive, c.negative]
                .iter()
                .all(|n| *n == unknown[0] || *n == 0 || ctx.input_nodes.contains(n))
        {
            return Err(unsupported(
                "factorized slew requires one unknown output and driven reference",
            ));
        }
        if let Some(errors) = &ctx.trajectory.config.pwl_errors_v {
            f.charge("source_factor_audit_visits", errors.len())?;
            if errors.iter().any(|e| e.bound() > 0.) {
                return Err(Error::new(
                    "unsupported_source_uncertainty",
                    "factorized slew requires exact physical sources",
                ));
            }
        }
        Ok(f)
    }
    pub fn charge(&self, kind: &'static str, n: usize) -> Result<(), Error> {
        // No new factor proof/copy can run after any original shared quota
        // failed, including a root/plan reservation rather than only slot2.
        self.work.debit(0, 0)?;
        self.work.debit(1, 0)?;
        if let Err(e) = self.work.debit(2, n as u64) {
            crate::diagnostics::counter("source_factor_exhausted", 1);
            return Err(e);
        }
        crate::diagnostics::counter(kind, n);
        crate::diagnostics::counter("source_factor_work_debit", n);
        Ok(())
    }
    fn structural(&self) -> Result<(), Error> {
        self.charge("source_factor_health_visits", 1)?;
        let mut n = self.structural.lock().unwrap();
        *n = n.and_then(|x| x.checked_sub(1));
        if n.is_none() {
            return Err(Error::new(
                "resource_budget",
                "source factor structural audit exhausted",
            ));
        }
        Ok(())
    }
    /// Count/copy storage before delegated Clone. The counting traversal itself
    /// is charged before examining every node/term, including dormant guards.
    pub fn copy_tree(&self, e: &E) -> Result<usize, Error> {
        self.charge("source_factor_count_visits", 1)?;
        let local = match e {
            E::Affine { terms, .. } => {
                self.charge("source_factor_count_visits", terms.len())?;
                3 + 2 * terms.len()
            }
            E::Add { .. } | E::Multiply { .. } | E::Divide { .. } => 3,
            E::Select { origin, .. } => {
                self.charge("source_factor_count_visits", origin.expansion.len() + 1)?;
                8 + origin.source.len()
                    + origin.instance.len()
                    + origin
                        .expansion
                        .iter()
                        .map(|(s, _)| s.len() + 2)
                        .sum::<usize>()
            }
            E::Operator { .. } => 2,
            _ => return Err(unsupported("invalid factorized source tree")),
        };
        self.charge("source_factor_copy_debit", local)?;
        Ok(local
            + match e {
                E::Add { left, right }
                | E::Multiply { left, right }
                | E::Divide { left, right } => self.copy_tree(left)? + self.copy_tree(right)?,
                E::Select {
                    left,
                    right,
                    then_value,
                    else_value,
                    ..
                } => {
                    self.copy_tree(left)?
                        + self.copy_tree(right)?
                        + self.copy_tree(then_value)?
                        + self.copy_tree(else_value)?
                }
                _ => 0,
            })
    }
    pub(super) fn check_binding(
        &self,
        context: &ProofContext,
        expression: &E,
        owner: &str,
    ) -> Result<(), Error> {
        self.copy_tree(expression)?;
        self.charge("source_factor_lookup_debit", owner.len() + 4)?;
        if !Arc::ptr_eq(&self.program, &context.program)
            || !Arc::ptr_eq(&self.trajectory, &context.trajectory)
            || !Arc::ptr_eq(&self.work.0, &context.work.0)
            || self.owner != owner
            || self.normalized.get().is_none_or(|e| e != expression)
        {
            return Err(unsupported(
                "factor certificate is bound to original AST owner and source context",
            ));
        }
        Ok(())
    }
    pub fn normalization_copy(&self) -> Result<(), Error> {
        self.charge(
            "source_factor_copy_debit",
            self.original_items.saturating_mul(8),
        )
    }
    pub fn resolve_node(&self, e: &E) -> Result<(), Error> {
        let n = match e {
            E::Affine { terms, .. } => 3 + 2 * terms.len(),
            E::Add { .. } | E::Multiply { .. } | E::Divide { .. } => 3,
            _ => 1,
        };
        self.charge("source_factor_resolver_visits", 1)?;
        self.charge("source_factor_copy_debit", n)
    }
    pub fn qualify(&self, e: &E) -> Result<(), Error> {
        fn fold(f: &Factor, e: &E) -> Result<(I, usize), Error> {
            f.structural()?;
            let (v, forms) = match e {
                E::Affine { constant, terms } if terms.is_empty() && constant.is_finite() => {
                    (I::point(*constant), 1)
                }
                E::Add { left, right } | E::Multiply { left, right } => {
                    let (a, na) = fold(f, left)?;
                    let (b, nb) = fold(f, right)?;
                    if matches!(e, E::Multiply { .. }) && na > 1 && nb > 1 {
                        return Err(unsupported("factorized slew permits only scalar products"));
                    }
                    f.charge("source_factor_interval_debit", 1)?;
                    (
                        if matches!(e, E::Add { .. }) {
                            a + b
                        } else {
                            a * b
                        },
                        na.saturating_mul(nb).min(8193),
                    )
                }
                E::Select {
                    then_value,
                    else_value,
                    origin,
                    ..
                } => {
                    if origin.instance != f.owner
                        || origin.source.is_empty()
                        || origin.line == 0
                        || origin.column == 0
                        || !origin.valid_expansion()
                    {
                        return Err(unsupported("invalid factorized source owner"));
                    }
                    let (a, na) = fold(f, then_value)?;
                    let (b, nb) = fold(f, else_value)?;
                    f.charge("source_factor_interval_debit", 1)?;
                    (a.hull(b), na.saturating_add(nb).min(8193))
                }
                _ => {
                    return Err(unsupported(
                        "factorized value leaves must be certified scalar constants",
                    ))
                }
            };
            if !v.finite() {
                return Err(Error::new(
                    "nonfinite_arithmetic",
                    "nonfinite factorized value arm",
                ));
            }
            Ok((v, forms))
        }
        let (_, forms) = fold(self, e)?;
        if forms != self.saturated_forms || forms <= 8192 {
            return Err(unsupported(
                "factorized values cannot replace a legacy small form route",
            ));
        }
        self.copy_tree(e)?;
        self.normalized
            .set(e.clone())
            .map_err(|_| unsupported("factor certificate cannot be rebound"))?;
        crate::diagnostics::counter("source_factor_qualifications", 1);
        Ok(())
    }
    pub fn dense(&self, e: &E, d: usize) -> Result<(), Error> {
        let n = self.copy_tree(e)?;
        self.charge(
            "source_factor_dense_debit",
            n.saturating_mul(d).saturating_mul(d).saturating_mul(16),
        )
    }
    // The retained owner/program are used by every factor-only delegated
    // structural helper, so callers cannot forget its dense prepayment.
    pub fn dependency_edges(&self, e: &E) -> Result<DependencySets, Error> {
        self.dense(e, self.program.nodes.len() + 2)?;
        crate::continuous::integral_dependency_edges(e, &self.program, &self.owner)
    }
    pub fn validate_selection(&self, e: &E, driven: &[String]) -> Result<(), Error> {
        self.dense(e, self.program.nodes.len() + 2)?;
        crate::continuous::validate_selection(e, &self.program, driven, &self.owner)
    }
    pub fn guard_material(&self, left: &E, right: &E, seen: usize) -> Result<(), Error> {
        let n = self.copy_tree(left)? + self.copy_tree(right)? + 8;
        // Single-form guards: forms/bind/constructed guard and seen insertion.
        self.charge("source_factor_copy_debit", n.saturating_mul(8))?;
        self.charge("source_factor_lookup_debit", n.saturating_mul(seen + 1))
    }
    fn root_comparison_cost(a: &RootTime, b: &RootTime) -> usize {
        let bits = [
            a.rational().numer().bits(),
            a.rational().denom().bits(),
            b.rational().numer().bits(),
            b.rational().denom().bits(),
        ]
        .into_iter()
        .max()
        .unwrap_or(1) as usize;
        let bits = bits + 64; // nearest binary64 enclosure may add up to53 significand bits
        let limbs = bits.div_ceil(64).max(1);
        // num-rational0.4.2 Ratio::cmp uses two Euclidean div_mod_floor
        // operations per recursion, not a constant-time rational comparison.
        8usize
            .saturating_mul(bits + 1)
            .saturating_mul(limbs)
            .saturating_mul(limbs)
            .saturating_add(32)
    }
    pub(super) fn find_proof<'a>(
        &self,
        proofs: &'a [ProvenSign],
        owner: &str,
        a: &E,
        b: &E,
        root: Option<&RootTime>,
    ) -> Result<Option<&'a ProvenSign>, Error> {
        let n = self.copy_tree(a)? + self.copy_tree(b)?;
        for p in proofs {
            self.charge("source_factor_lookup_debit", n + owner.len() + 4)?;
            if p.owner != owner || p.left != *a || p.right != *b {
                continue;
            }
            if let (Some(x), Some(y)) = (p.root.as_ref(), root) {
                self.charge("source_factor_root_debit", Self::root_comparison_cost(x, y))?;
            }
            if p.root.as_ref() == root {
                return Ok(Some(p));
            }
        }
        // Owned guard/cache insertion copies occur only on a true miss.
        self.charge(
            "source_factor_copy_debit",
            n.saturating_mul(8) + owner.len() + 16,
        )?;
        if let Some(root) = root {
            self.roots(std::slice::from_ref(root))?;
        }
        Ok(None)
    }
    // In-place fallible heapsort, used only by the >8192 factor route.
    // Each exact comparison retains the existing bit/limb reservation. Unlike
    // the old quadratic worst-case prepayment, only real comparisons execute.
    // RootTime swaps move fixed-size owned headers, never clone BigInt limbs.
    pub fn sort_dedup_roots(&self, roots: &mut Vec<RootTime>) -> Result<(), Error> {
        self.charge("source_factor_sort_steps", 1)?;
        // Own-storage/limb disposal costs, before any vector mutation/drop.
        self.roots(roots)?;
        fn compare(f: &Factor, a: &RootTime, b: &RootTime) -> Result<std::cmp::Ordering, Error> {
            f.charge("source_factor_sort_steps", 8)?;
            f.charge(
                "source_factor_root_debit",
                Factor::root_comparison_cost(a, b),
            )?;
            crate::diagnostics::counter("source_factor_sort_comparisons", 1);
            Ok(a.order(b))
        }
        fn swap(f: &Factor, a: &mut [RootTime], i: usize, j: usize) -> Result<(), Error> {
            f.charge(
                "source_factor_sort_moves",
                3 * std::mem::size_of::<RootTime>(),
            )?;
            a.swap(i, j);
            Ok(())
        }
        fn sift(f: &Factor, a: &mut [RootTime], mut root: usize, end: usize) -> Result<(), Error> {
            loop {
                f.charge("source_factor_sort_steps", 8)?;
                let child = root.saturating_mul(2).saturating_add(1);
                if child >= end {
                    return Ok(());
                }
                let mut largest = child;
                if child + 1 < end
                    && compare(f, &a[child], &a[child + 1])? == std::cmp::Ordering::Less
                {
                    largest = child + 1;
                }
                if compare(f, &a[root], &a[largest])? != std::cmp::Ordering::Less {
                    return Ok(());
                }
                swap(f, a, root, largest)?;
                root = largest;
            }
        }
        let n = roots.len();
        for start in (0..n / 2).rev() {
            self.charge("source_factor_sort_steps", 1)?;
            sift(self, roots, start, n)?;
        }
        for end in (1..n).rev() {
            self.charge("source_factor_sort_steps", 1)?;
            swap(self, roots, 0, end)?;
            sift(self, roots, 0, end)?;
        }
        let mut write = usize::from(n > 0);
        for read in 1..n {
            self.charge("source_factor_sort_steps", 4)?;
            if compare(self, &roots[write - 1], &roots[read])? != std::cmp::Ordering::Equal {
                if write != read {
                    swap(self, roots, write, read)?;
                }
                write += 1;
            }
        }
        self.charge("source_factor_sort_steps", 1)?;
        roots.truncate(write);
        Ok(())
    }
    pub fn search_roots<'a>(
        &self,
        root: &RootTime,
        roots: impl Iterator<Item = &'a RootTime>,
    ) -> Result<(), Error> {
        let mut count = 1usize;
        let mut max = Self::root_comparison_cost(root, root);
        for other in roots {
            self.charge("source_factor_count_visits", 1)?;
            count += 1;
            max = max.max(Self::root_comparison_cost(root, other));
        }
        self.charge("source_factor_root_debit", count.saturating_mul(max))
    }
    pub fn roots(&self, roots: &[RootTime]) -> Result<(), Error> {
        for r in roots {
            self.charge("source_factor_count_visits", 1)?;
            let n = (r.rational().numer().bits().div_ceil(64)
                + r.rational().denom().bits().div_ceil(64)) as usize
                + 4;
            self.charge("source_factor_root_debit", n)?;
        }
        Ok(())
    }
    pub fn cut_lookup(&self, e: &E, entries: usize, _t: &Trajectory) -> Result<(), Error> {
        let n = self.copy_tree(e)?;
        self.charge(
            "source_factor_lookup_debit",
            n.saturating_mul(entries + 8)
                .saturating_add(self.owner.len().saturating_mul(entries + 1)),
        )?;
        Ok(())
    }
}

#[cfg(test)]
pub(crate) mod tests {
    use super::super::{Plan, Spec};
    use super::*;
    use crate::ir::{Expression, Program, SCHEMA_VERSION};
    use serde_json::json;
    use std::sync::Arc;
    pub(crate) fn fixture(n: usize) -> (Program, Trajectory, Vec<String>, Expression) {
        let o = json!({"source":"factor.va","instance":"dut","line":1,"column":1});
        let c = |x: f64| json!({"op":"affine","constant":x,"terms":[]});
        let sel = json!({"op":"select","relation":"gt","left":{"op":"affine","constant":0.,"terms":[{"node":1,"coefficient":1.}]},"right":c(0.5),"then_value":c(1.),"else_value":c(0.),"origin":o});
        let mut e = sel.clone();
        for _ in 1..n {
            e = json!({"op":"add","left":e,"right":sel});
        }
        let input = json!({"op":"multiply","left":c(0.0625),"right":e});
        let p:Program=serde_json::from_value(json!({"schema_version":SCHEMA_VERSION,"nodes":["0","u","y"],"operators":[{"kind":"slew","input":input,"rise":2.,"fall":-2.,"origin":o}],"contributions":[{"branch":{"kind":"voltage","instance":"dut","local_positive":"out","local_negative":"ref"},"positive":2,"negative":0,"rhs":{"op":"operator","operator":0},"origin":o}]})).unwrap();
        let t=Trajectory::new(serde_json::from_value(json!({"pwl":[[[0.,0.],[0.5,1.],[1.,0.]]],"output_times":[0.,0.5,1.],"stop":1.,"max_step":1.})).unwrap(),1).unwrap();
        let OperatorSpec::Slew { input: e, .. } = &p.operators[0] else {
            unreachable!()
        };
        let e = e.clone();
        (p, t, vec!["u".into()], e)
    }
    fn source(n: usize) -> (Arc<ProofContext>, Arc<Spec>, Plan) {
        let (p, t, d, e) = fixture(n);
        let c = ProofContext::new(&p, &t, &d, Work::default()).unwrap();
        let (norm, factor) = c.slew_admission(&e, "dut").unwrap();
        assert!(factor.is_some());
        let spec = Spec::source_slew_with_context(&norm, c.clone(), "dut", factor)
            .unwrap()
            .unwrap();
        let plan = Plan::build_for_slew(spec.clone(), &[]).unwrap();
        (c, spec, plan)
    }
    #[test]
    fn old_8192_boundary_keeps_normalized_tree_and_identical_debit() {
        let (p, t, d, e) = fixture(13);
        let a = ProofContext::new(&p, &t, &d, Work::default()).unwrap();
        let b = ProofContext::new(&p, &t, &d, Work::default()).unwrap();
        let old = a.slew_dc_leaves(&e, "dut").unwrap();
        let (new, factor) = b.slew_admission(&e, "dut").unwrap();
        assert!(factor.is_none());
        assert_eq!(old, new);
        assert_eq!(a.source_work_used(), b.source_work_used());
        assert_eq!(super::super::forms(&old, &a.work).unwrap().len(), 8192);
        let (p, t, d, e) = fixture(14);
        let c = ProofContext::new(&p, &t, &d, Work::default()).unwrap();
        let old = c.slew_dc_leaves(&e, "dut").unwrap();
        assert_eq!(
            super::super::forms(&old, &c.work).unwrap_err().kind,
            "step_budget"
        );
        let (_, _, plan) = source(14);
        assert!(plan.cuts().len() >= 4);
    }
    #[test]
    fn fifteen_selects_use_original_root_partition_and_scalar_answers() {
        let (_, _, plan) = source(15);
        assert_eq!(
            plan.cuts().iter().map(|t| t.time).collect::<Vec<_>>(),
            vec![0., 0.25, 0.5, 0.75, 1.]
        );
        assert_eq!(plan.seed().value, 0.);
        let root = RootTime::point(0.25).unwrap();
        let after = plan.slew_target_after(&root).unwrap();
        assert_eq!(after.value, 15. / 16.);
        assert!(after.bounds.lo <= 15. / 16. && after.bounds.hi >= 15. / 16.);
        let at = plan.points.iter().find(|t| t.value == 0.).unwrap();
        assert_eq!(at.value, 0.);
    }
    #[test]
    fn exact_nonbinary_open_cell_keeps_root_time_branch_identity() {
        let (p, _, d, e) = fixture(15);
        let next = 1.0f64.next_up();
        let t=Trajectory::new(serde_json::from_value(json!({"pwl":[[[0.,0.],[1.,0.],[next,1.],[2.,1.]]],"output_times":[0.,2.],"stop":2.,"max_step":2.})).unwrap(),1).unwrap();
        let c = ProofContext::new(&p, &t, &d, Work::default()).unwrap();
        let (norm, factor) = c.slew_admission(&e, "dut").unwrap();
        let spec = Spec::source_slew_with_context(&norm, c, "dut", factor)
            .unwrap()
            .unwrap();
        let plan = Plan::build_for_slew(spec, &[]).unwrap();
        assert_eq!(plan.cuts().len(), 5);
        // True half-way root and next source corner share a float upper representative.
        assert_eq!(plan.cuts()[2].time, plan.cuts()[3].time);
        assert_eq!(plan.points[2].value, 0.);
        assert_eq!(plan.modes[2].value, 15. / 16.);
        assert_ne!(plan.cuts()[2].exact, plan.cuts()[3].exact);
    }
    #[test]
    fn one_structural_owner_counts_original_storage_before_normalized_clone() {
        let (p, t, d, _) = fixture(15);
        let mut raw = serde_json::to_value(p).unwrap();
        fn large_origins(e: &mut serde_json::Value) {
            if e["op"] == "select" {
                e["origin"]["source"] = json!("x".repeat(10_000));
            }
            if let Some(map) = e.as_object_mut() {
                for (_, v) in map {
                    if v.is_object() {
                        large_origins(v);
                    }
                }
            }
        }
        large_origins(&mut raw["operators"][0]["input"]);
        let p: Program = serde_json::from_value(raw).unwrap();
        let c = ProofContext::new(&p, &t, &d, Work::default()).unwrap();
        let OperatorSpec::Slew { input, .. } = &p.operators[0] else {
            unreachable!()
        };
        assert_eq!(
            c.slew_admission(input, "dut").err().unwrap().kind,
            "resource_budget"
        );
        let used = c.source_work_used();
        for _ in 0..2 {
            assert_eq!(
                c.slew_admission(input, "dut").err().unwrap().kind,
                "resource_budget"
            );
        }
        assert_eq!(c.source_work_used(), used); // no repeated original scan/copy
    }
    #[test]
    fn admission_token_cannot_cross_ast_source_or_shared_quota_owner() {
        let (p, t, d, e) = fixture(15);
        let work = Work::default();
        let a = ProofContext::new(&p, &t, &d, work.clone()).unwrap();
        let b = ProofContext::new(&p, &t, &d, work).unwrap();
        let (norm, factor) = a.slew_admission(&e, "dut").unwrap();
        let f = factor.clone().unwrap();
        assert!(Spec::source_slew_with_context(&norm, b, "dut", factor.clone()).is_err());
        let altered = Expression::Add {
            left: Box::new(norm.clone()),
            right: Box::new(super::super::constant(1.)),
        };
        assert!(Spec::source_slew_with_context(&altered, a.clone(), "dut", factor).is_err());
        assert!(Spec::source_slew_with_context(&norm, a, "dut", Some(f))
            .unwrap()
            .is_some());
    }
    #[test]
    fn full_arms_zero_dependencies_owner_and_overflow_refuse() {
        for bad in [
            json!({"op":"affine","constant":0.,"terms":[{"node":2,"coefficient":0.}]}),
            json!({"op":"state","state":0}),
            json!({"op":"operator","operator":0}),
            json!({"op":"add","left":{"op":"affine","constant":1e308,"terms":[]},"right":{"op":"affine","constant":1e308,"terms":[]}}),
        ] {
            let (p, t, d, _) = fixture(15);
            let mut raw = serde_json::to_value(p).unwrap();
            // Last Select's dormant else arm: the original tree must be audited.
            raw["operators"][0]["input"]["right"]["right"]["else_value"] = bad;
            let p: Program = serde_json::from_value(raw).unwrap();
            let OperatorSpec::Slew { input: e, .. } = &p.operators[0] else {
                unreachable!()
            };
            let c = ProofContext::new(&p, &t, &d, Work::default()).unwrap();
            assert!(c.slew_admission(e, "dut").is_err());
        }
        let (p, t, d, _) = fixture(15);
        let mut raw = serde_json::to_value(p).unwrap();
        raw["operators"][0]["input"]["right"]["right"]["origin"]["instance"] = json!("foreign");
        let p: Program = serde_json::from_value(raw).unwrap();
        let c = ProofContext::new(&p, &t, &d, Work::default()).unwrap();
        let OperatorSpec::Slew { input: e, .. } = &p.operators[0] else {
            unreachable!()
        };
        assert!(c.slew_admission(e, "dut").is_err());
    }
    #[test]
    fn natural_original_plan_root_and_work_limits_are_sticky() {
        // Original128 plan quota, successful cache reuse; no reduced limits.
        let (c, spec, plan) = source(15);
        let before = plan.seed().value;
        let mut plans = 1;
        loop {
            match Plan::build_for_slew(spec.clone(), &[]) {
                Ok(_) => plans += 1,
                Err(e) => {
                    assert_eq!(e.kind, "step_budget");
                    assert!(e.message.contains("slot 0"), "{}", e.message);
                    break;
                }
            }
        }
        assert_eq!(plans, 128);
        for _ in 0..2 {
            assert!(Plan::build_for_slew(spec.clone(), &[]).is_err());
            assert_eq!(plan.seed().value, before);
        }
        println!("factor_plan_limit={plans},work={}", c.source_work_used());
        // Original8192 root quota, materialize the same successful guard proof.
        let (c, spec, plan) = source(15);
        let guard = Expression::Affine {
            constant: -0.5,
            terms: vec![crate::ir::Term {
                node: 1,
                coefficient: 1.,
            }],
        };
        let mut materializations = 0;
        loop {
            match spec.proven_cuts(&guard) {
                Ok(v) => materializations += v.len(),
                Err(e) => {
                    assert_eq!(e.kind, "step_budget");
                    assert!(e.message.contains("slot 1"), "{}", e.message);
                    break;
                }
            }
        }
        let (_, retry) =
            crate::diagnostics::capture(crate::diagnostics::Options::default(), || {
                for _ in 0..2 {
                    assert!(spec.proven_cuts(&guard).is_err());
                    assert_eq!(plan.seed().value, 0.);
                }
                Ok(())
            });
        assert!(!retry.counters.contains_key("source_factor_copy_debit"));
        assert!(!retry.counters.contains_key("source_cut_proof_builds"));
        println!(
            "factor_root_materializations={materializations},work={}",
            c.source_work_used()
        );
        // Original1e9 work quota, distinct true exact helpers rather than a
        // synthetic single debit. Cache lookups and owned evidence are paid.
        let (c, spec, plan) = source(15);
        let mut helpers = 0;
        loop {
            let a = Expression::Affine {
                constant: helpers as f64,
                terms: vec![],
            };
            match spec.proof_sign(&a, &super::super::constant(-1.), None, "test") {
                Ok(_) => helpers += 1,
                Err(e) => {
                    assert_eq!(e.kind, "step_budget");
                    assert!(e.message.contains("slot 2"));
                    break;
                }
            }
        }
        assert!(helpers > 1000);
        let start = c.source_work_used();
        let (_, retry) =
            crate::diagnostics::capture(crate::diagnostics::Options::default(), || {
                for _ in 0..2 {
                    assert!(spec.target(&[], &plan.cuts()[0]).is_err());
                }
                Ok(())
            });
        assert!(!retry.counters.contains_key("source_factor_copy_debit"));
        assert!(!retry.counters.contains_key("source_exact_proof_builds"));
        assert!(c.source_work_used() > start);
        assert_eq!(plan.seed().value, 0.);
        println!(
            "factor_natural_helpers={helpers},work_end={},retry={:?}",
            c.source_work_used(),
            retry.counters
        );
    }
    #[test]
    fn topology19_nonbinary_roots_keep_checked_slew_without_quadratic_reservation() {
        // Independent derived network: fifteen distinct predicates, seventeen
        // full PWL inputs and nineteen nodes. Time/rate rescaling preserves
        // the dyadic control's scalar limiter answers but requires exact
        // nonbinary64 root arithmetic. Original default Work is unchanged.
        let mut q: crate::ir::Request = serde_json::from_str(include_str!(
            "../../../tests/fixtures/factor-topology19-nonbinary-time.json"
        ))
        .unwrap();
        // IR32 preserves this Program shape; its new optional analytic_sources
        // field defaults to empty for this PWL request. Keep the archived IR31.
        assert_eq!(q.program.schema_version, 31);
        assert_eq!(SCHEMA_VERSION, 33, "re-audit the fixture");
        // IR33 legacy transport: retain pre-executed numeric seeds.
        // Do not add an initial gate or procedure to this archived input.
        assert!(q.program.procedures.is_empty());
        assert!(q.program.real_bindings.is_empty());
        assert!(q.program.events.iter().all(|event| event.procedure_id.is_none()
            && event.expanded_statement_ordinal.is_none()));
        assert!(q.program.states.iter().all(|state|
            serde_json::to_value(&state.initial).unwrap().is_number()));
        assert!(q.transient.as_ref().unwrap().analytic_sources.is_empty());
        q.program.schema_version = SCHEMA_VERSION;
        let (result, report) =
            crate::diagnostics::capture(crate::diagnostics::Options::default(), || crate::run(q));
        let response = result.unwrap();
        let raw = serde_json::to_value(response).unwrap();
        let boxes = raw["observation_evidence"]["voltage_bounds_V"]
            .as_array()
            .unwrap();
        assert_eq!(boxes.len(), 878);
        assert_eq!(boxes[0][16], serde_json::json!([0., 0.]));
        // At final time nine of fifteen unit arms are selected:9/16.
        assert_eq!(
            boxes.last().unwrap()[16],
            serde_json::json!([0.5625, 0.5625])
        );
        println!(
            "TOPOLOGY19_COUNTERS {}",
            serde_json::to_string(&report.counters).unwrap()
        );
    }
    #[test]
    fn metered_root_sort_preserves_original_exact_order_and_dedup() {
        let (_, spec, _) = source(15);
        let factor = spec.factor.as_ref().unwrap();
        for n in [0usize, 1, 2, 3, 16, 127, 256] {
            let mut roots: Vec<_> = (0..n)
                .map(|i| RootTime::point(((i * 73) % 31) as f64 * 1e-7).unwrap())
                .collect();
            let mut reference = roots.clone();
            reference.sort_by(RootTime::order);
            reference.dedup_by(|a, b| a.order(b) == std::cmp::Ordering::Equal);
            factor.sort_dedup_roots(&mut roots).unwrap();
            assert_eq!(roots, reference);
        }
    }
    #[test]
    fn metered_root_sort_natural_work_exhaustion_stops_comparisons_and_two_retries() {
        let (context, spec, _) = source(15);
        let factor = spec.factor.as_ref().unwrap();
        let mut roots: Vec<_> = (0..257)
            .rev()
            .map(|k| RootTime::point((k + 1) as f64 * 1e-300).unwrap())
            .collect();
        let (result, first) =
            crate::diagnostics::capture(crate::diagnostics::Options::default(), || {
                factor.sort_dedup_roots(&mut roots)
            });
        let error = result.unwrap_err();
        assert_eq!(error.kind, "step_budget");
        assert!(error.message.contains("slot 2"));
        assert!(first.counters["source_factor_sort_comparisons"] > 0);
        assert!(context.source_work_used() > 1_000_000_000);
        let before = roots.clone();
        let (_, retries) =
            crate::diagnostics::capture(crate::diagnostics::Options::default(), || {
                for _ in 0..2 {
                    assert_eq!(
                        factor.sort_dedup_roots(&mut roots).unwrap_err().kind,
                        "step_budget"
                    );
                    assert_eq!(roots, before);
                }
                Ok(())
            });
        assert_eq!(retries.counters.len(), 1);
        assert_eq!(retries.counters["source_factor_exhausted"], 2);
        println!(
            "ROOT_SORT_NATURAL work={} first={:?} retries={:?}",
            context.source_work_used(),
            first.counters,
            retries.counters
        );
    }
}
