//! Opt-in pure held Transition targets. No electrical/continuous derivative API.
use crate::interval::Interval as I;
use crate::ir::{
    Error, Expression as E, IntegerFunction as F, IntegerOperand as O, Origin, Program, Relation,
    StateKind,
};
use crate::transition_source_plan::ProofContext;
use std::collections::BTreeSet;
use std::sync::Arc;

fn refused() -> Error {
    Error::new("unsupported_held_integer_target", "typed Transition requires a pure same-owner integer held target and actual point state bounds")
}

// Also used during cold preparation, before histories exist. No nominal
// evaluation or branch selection can prune these structural dependencies.
pub(crate) fn dependencies(
    e: &E,
    p: &Program,
    owner: &str,
    context: &ProofContext,
) -> Result<BTreeSet<usize>, Error> {
    audit(e, p, owner, &mut |amount| context.charge(amount))
}

/// The old scalar integer Select consumer needs no native bit operation.
/// Its complete structural integer dependency set must still be point-valued.
pub(crate) fn scalar_dependencies(
    e: &E,
    p: &Program,
    owner: &str,
    context: &ProofContext,
) -> Result<BTreeSet<usize>, Error> {
    audit_mode(e, p, owner, &mut |amount| context.charge(amount), false)
}
fn audit(
    e: &E,
    p: &Program,
    owner: &str,
    work: &mut impl FnMut(usize) -> Result<(), Error>,
) -> Result<BTreeSet<usize>, Error> {
    audit_mode(e, p, owner, work, true)
}
fn audit_mode(
    e: &E,
    p: &Program,
    owner: &str,
    work: &mut impl FnMut(usize) -> Result<(), Error>,
    require_bits: bool,
) -> Result<BTreeSet<usize>, Error> {
    fn operand(
        o: &O,
        p: &Program,
        owner: &str,
        ds: &mut BTreeSet<usize>,
        bits: &mut bool,
        w: &mut impl FnMut(usize) -> Result<(), Error>,
    ) -> Result<(), Error> {
        w(1)?;
        match o {
            O::IntegerLiteral { .. } => (),
            O::IntegerState { state } => state_dep(*state, p, owner, ds, w)?,
            O::IntegerPrimitive {
                function,
                args,
                origin,
            } => {
                validate(*function, args, origin, owner, w)?;
                *bits |= matches!(function, F::ShiftRight | F::BitAnd);
                for a in args {
                    operand(a, p, owner, ds, bits, w)?;
                }
            }
        }
        Ok(())
    }
    fn visit(
        e: &E,
        p: &Program,
        owner: &str,
        ds: &mut BTreeSet<usize>,
        bits: &mut bool,
        w: &mut impl FnMut(usize) -> Result<(), Error>,
    ) -> Result<(), Error> {
        w(1)?;
        match e {
            E::Affine { constant, terms } if constant.is_finite() && terms.is_empty() => (),
            E::State { state } => state_dep(*state, p, owner, ds, w)?,
            E::IntegerPrimitive {
                function,
                args,
                origin,
            } => {
                validate(*function, args, origin, owner, w)?;
                *bits |= matches!(function, F::ShiftRight | F::BitAnd);
                for a in args {
                    operand(a, p, owner, ds, bits, w)?;
                }
            }
            E::Add { left, right } => {
                visit(left, p, owner, ds, bits, w)?;
                visit(right, p, owner, ds, bits, w)?;
            }
            E::Multiply { left, right } if constant(left) || constant(right) => {
                visit(left, p, owner, ds, bits, w)?;
                visit(right, p, owner, ds, bits, w)?;
            }
            E::Select {
                left,
                right,
                then_value,
                else_value,
                origin,
                ..
            } => {
                valid_origin(origin, owner, w)?;
                for a in [left, right, then_value, else_value] {
                    visit(a, p, owner, ds, bits, w)?;
                }
            }
            _ => return Err(refused()),
        }
        Ok(())
    }
    let mut ds = BTreeSet::new();
    let mut bits = false;
    visit(e, p, owner, &mut ds, &mut bits, work)?;
    if require_bits && !bits {
        return Err(refused());
    }
    Ok(ds)
}
fn valid_origin(
    o: &Origin,
    owner: &str,
    w: &mut impl FnMut(usize) -> Result<(), Error>,
) -> Result<(), Error> {
    // Prepay the metadata scan, then all variable-length comparisons/name
    // validation. No empty character loop is needed to spend the reservation.
    w(1usize.saturating_add(o.expansion.len()))?;
    let characters = o.expansion.iter().fold(
        o.source.len().saturating_add(o.instance.len()),
        |n, (name, _)| n.saturating_add(name.len()).saturating_add(2),
    );
    w(characters)?;
    if o.instance != owner
        || o.source.is_empty()
        || o.line == 0
        || o.column == 0
        || !o.valid_expansion()
    {
        return Err(refused());
    }
    Ok(())
}
fn validate(
    f: F,
    args: &[O],
    origin: &Origin,
    owner: &str,
    w: &mut impl FnMut(usize) -> Result<(), Error>,
) -> Result<(), Error> {
    valid_origin(origin, owner, w)?;
    if args.len() != 2
        || (f == F::ShiftRight && !matches!(args.get(1), Some(O::IntegerLiteral { .. })))
        || (f == F::Remainder && matches!(args.get(1), Some(O::IntegerLiteral { value: 0 })))
    {
        return Err(refused());
    }
    Ok(())
}
fn constant(e: &E) -> bool {
    matches!(e,E::Affine{constant,terms} if constant.is_finite() && terms.is_empty())
}
// A deliberately conservative bound in logical key/link/header operations.
// A tree with d keys has at most d+1 search/rebalance levels, each touching at
// most d+1 existing or newly inserted entries. Eight units cover a comparison,
// key read/write, link read/write and node allocation/header operations. This
// quadratic upper bound does not assume an unmetered logarithmic constant.
fn collection_auxiliary_bound(d: usize) -> usize {
    let entries = d.saturating_add(1);
    entries.saturating_mul(entries).saturating_mul(8)
}
fn state_dep(
    s: usize,
    p: &Program,
    owner: &str,
    ds: &mut BTreeSet<usize>,
    debit: &mut impl FnMut(usize) -> Result<(), Error>,
) -> Result<(), Error> {
    debit(1)?; // Constant lookup/kind/length reads, before indexing.
    let declaration = p.states.get(s).ok_or_else(refused)?;
    if declaration.kind != StateKind::Integer {
        return Err(refused());
    }
    let compare = declaration
        .instance
        .len()
        .saturating_add(owner.len())
        .saturating_add(1);
    debit(compare.saturating_add(collection_auxiliary_bound(ds.len())))?;
    #[cfg(test)]
    auxiliary_event(0);
    if declaration.instance != owner {
        return Err(refused());
    }
    #[cfg(test)]
    auxiliary_event(1);
    ds.insert(s);
    Ok(())
}

// Cold preparation merges the newly audited dependency set into its existing
// seed set. Prepay the entire merge before traversal or any insertion; the
// same request callback remains exhausted when a candidate is retried.
pub(crate) fn merge_dependencies(
    destination: &mut BTreeSet<usize>,
    dependencies: &BTreeSet<usize>,
    debit: &mut impl FnMut(usize) -> Result<(), Error>,
) -> Result<(), Error> {
    let largest = destination.len().saturating_add(dependencies.len());
    let amount = collection_auxiliary_bound(largest)
        .saturating_add(1)
        .saturating_mul(dependencies.len())
        .saturating_add(1);
    debit(amount)?;
    #[cfg(test)]
    auxiliary_event(2);
    destination.extend(dependencies.iter().copied());
    Ok(())
}
#[cfg(test)]
thread_local! { static AUXILIARY_EVENTS:std::cell::Cell<[usize;3]>=const {std::cell::Cell::new([0;3])}; }
#[cfg(test)]
fn auxiliary_event(which: usize) {
    AUXILIARY_EVENTS.with(|c| {
        let mut v = c.get();
        v[which] += 1;
        c.set(v);
    });
}

pub(crate) struct Spec {
    pub(crate) dependencies: BTreeSet<usize>,
    context: Arc<ProofContext>,
}
// The token cannot outlive or replace the caller's actual Prepared/Frame boxes.
struct HeldPoints<'a> {
    bounds: &'a [I],
}
impl Spec {
    #[cfg(test)]
    pub(crate) fn test_context(&self) -> Arc<ProofContext> {
        self.context.clone()
    }
    pub(crate) fn charge(&self, amount: usize) -> Result<(), Error> {
        self.context.charge(amount)
    }
    pub(crate) fn charge_runtime_copy(&self, e: &E, states: usize) -> Result<(), Error> {
        // Each visit prepays all fields/attachments of that copied variant;
        // origin strings and operand vectors are included before cloning.
        fn operand(o: &O, c: &ProofContext) -> Result<(), Error> {
            c.charge(3)?;
            if let O::IntegerPrimitive { args, origin, .. } = o {
                c.charge(
                    7 + args.len()
                        + origin.instance.len()
                        + origin.source.len()
                        + origin
                            .expansion
                            .iter()
                            .map(|(s, _)| s.len() + 3)
                            .sum::<usize>(),
                )?;
                for a in args {
                    operand(a, c)?;
                }
            }
            Ok(())
        }
        fn expr(e: &E, c: &ProofContext) -> Result<(), Error> {
            c.charge(6)?;
            match e {
                E::Affine { terms, .. } => c.charge(1 + 3 * terms.len())?,
                E::IntegerPrimitive { args, origin, .. } => {
                    c.charge(
                        7 + args.len()
                            + origin.instance.len()
                            + origin.source.len()
                            + origin
                                .expansion
                                .iter()
                                .map(|(s, _)| s.len() + 3)
                                .sum::<usize>(),
                    )?;
                    for a in args {
                        operand(a, c)?;
                    }
                }
                E::Add { left, right } | E::Multiply { left, right } => {
                    expr(left, c)?;
                    expr(right, c)?;
                }
                E::Select {
                    left,
                    right,
                    then_value,
                    else_value,
                    origin,
                    ..
                } => {
                    c.charge(
                        7 + origin.instance.len()
                            + origin.source.len()
                            + origin
                                .expansion
                                .iter()
                                .map(|(s, _)| s.len() + 3)
                                .sum::<usize>(),
                    )?;
                    for a in [left, right, then_value, else_value] {
                        expr(a, c)?;
                    }
                }
                E::State { .. } => (),
                _ => return Err(refused()),
            }
            Ok(())
        }
        expr(e, &self.context)?;
        self.context.charge(8 + states + self.dependencies.len())
    }

    pub(crate) fn new(
        e: &E,
        p: &Program,
        owner: &str,
        context: Arc<ProofContext>,
    ) -> Result<Arc<Self>, Error> {
        let dependencies = audit(e, p, owner, &mut |amount| context.charge(amount))?;
        context.charge(1 + dependencies.len())?;
        Ok(Arc::new(Self {
            dependencies,
            context,
        }))
    }
    fn points<'a>(&self, states: &[f64], bounds: &'a [I]) -> Result<HeldPoints<'a>, Error> {
        for &s in &self.dependencies {
            self.context.charge(1)?;
            let b = *bounds.get(s).ok_or_else(refused)?;
            if states.get(s).copied() != Some(b.lo)
                || b.lo != b.hi
                || !b.finite()
                || b.lo.fract() != 0.
                || b.lo < f64::from(i32::MIN)
                || b.lo > f64::from(i32::MAX)
            {
                return Err(refused());
            }
        }
        Ok(HeldPoints { bounds })
    }
    pub(crate) fn evaluate(&self, e: &E, states: &[f64], bounds: &[I]) -> Result<(f64, I), Error> {
        #[cfg(test)]
        self.context.charge(0)?;
        let token = self.points(states, bounds)?;
        #[cfg(test)]
        crate::diagnostics::counter("native29_actual_evaluate_calls", 1);
        self.value(e, &token)
    }
    fn value(&self, e: &E, token: &HeldPoints<'_>) -> Result<(f64, I), Error> {
        self.context.charge(1)?;
        let (v, b) = match e {
            E::Affine { constant, terms } if terms.is_empty() => (*constant, I::point(*constant)),
            E::State { state } => (token.bounds[*state].lo, token.bounds[*state]),
            E::IntegerPrimitive {
                function,
                args,
                origin,
            } => {
                let v = crate::integer_primitive::evaluate(
                    *function,
                    args,
                    origin,
                    &mut |s| {
                        self.context.charge(1)?;
                        crate::integer_primitive::point(token.bounds[s], origin)
                    },
                    &mut || self.context.charge(1),
                )?;
                (f64::from(v), I::point(f64::from(v)))
            }
            E::Add { left, right } => {
                let (a, ab) = self.value(left, token)?;
                let (b, bb) = self.value(right, token)?;
                (a + b, ab + bb)
            }
            E::Multiply { left, right } => {
                let (a, ab) = self.value(left, token)?;
                let (b, bb) = self.value(right, token)?;
                (a * b, ab * bb)
            }
            E::Select {
                relation,
                left,
                right,
                then_value,
                else_value,
                ..
            } => {
                let (a, ab) = self.value(left, token)?;
                let (b, bb) = self.value(right, token)?;
                let select = match relation {
                    Relation::Lt => {
                        if ab.hi < bb.lo {
                            Some(true)
                        } else if ab.lo >= bb.hi {
                            Some(false)
                        } else {
                            None
                        }
                    }
                    Relation::Le => {
                        if ab.hi <= bb.lo {
                            Some(true)
                        } else if ab.lo > bb.hi {
                            Some(false)
                        } else {
                            None
                        }
                    }
                    Relation::Gt => {
                        if ab.lo > bb.hi {
                            Some(true)
                        } else if ab.hi <= bb.lo {
                            Some(false)
                        } else {
                            None
                        }
                    }
                    Relation::Ge => {
                        if ab.lo >= bb.hi {
                            Some(true)
                        } else if ab.hi < bb.lo {
                            Some(false)
                        } else {
                            None
                        }
                    }
                }
                .ok_or_else(|| {
                    Error::new(
                        "event_resolution",
                        "held target predicate lacks a certified decision",
                    )
                })?;
                let _ = (a, b);
                self.value(if select { then_value } else { else_value }, token)?
            }
            _ => return Err(refused()),
        };
        if !v.is_finite() || !b.finite() || v < b.lo || v > b.hi {
            return Err(Error::new(
                "nonfinite_arithmetic",
                "held target forward enclosure",
            ));
        }
        Ok((v, b))
    }
}

#[cfg(test)]
mod auxiliary_budget_tests {
    use super::*;
    fn fixture(owner: &str, leaves: usize) -> (Program, E) {
        let mut raw: serde_json::Value = serde_json::from_str(include_str!(
            "../../tests/fixtures/held-integer29-target-retry.json"
        ))
        .unwrap();
        fn rename(v: &mut serde_json::Value, owner: &str) {
            match v {
                serde_json::Value::Object(m) => {
                    for (k, v) in m {
                        if k == "instance" {
                            *v = serde_json::Value::String(owner.into());
                        } else {
                            rename(v, owner);
                        }
                    }
                }
                serde_json::Value::Array(a) => {
                    for v in a {
                        rename(v, owner);
                    }
                }
                _ => (),
            }
        }
        rename(&mut raw, owner);
        let p: Program = serde_json::from_value(raw).unwrap();
        let origin = Origin {
            source: "auxiliary.va".into(),
            line: 1,
            column: 1,
            instance: owner.into(),
            expansion: vec![],
        };
        fn tree(n: usize) -> E {
            if n == 1 {
                E::State { state: 0 }
            } else {
                E::Add {
                    left: Box::new(tree(n / 2)),
                    right: Box::new(tree(n - n / 2)),
                }
            }
        }
        let bits = E::IntegerPrimitive {
            function: F::BitAnd,
            args: vec![O::IntegerState { state: 0 }, O::IntegerLiteral { value: 1 }],
            origin,
        };
        (
            p,
            E::Add {
                left: Box::new(tree(leaves)),
                right: Box::new(bits),
            },
        )
    }
    #[test]
    fn many_bare_state_leaves_pay_repeated_long_owner_comparisons() {
        let owner = "owner".repeat(1024);
        let (p, e) = fixture(&owner, 128);
        let mut paid = 0usize;
        let dependencies = audit(&e, &p, &owner, &mut |amount| {
            paid += amount;
            Ok(())
        })
        .unwrap();
        assert_eq!(dependencies, BTreeSet::from([0]));
        assert!(
            paid >= 129 * owner.len(),
            "paid {paid}, original equal-owner byte comparisons require {}",
            129 * owner.len()
        );
    }
    fn context(p: &Program, limit: u64) -> Arc<ProofContext> {
        let trajectory = crate::pwl::Trajectory::new(
            crate::ir::TransientInputs {
                analytic_sources: vec![],
                pwl_errors_v: None,
                strobetimes: vec![],
                pwl: vec![],
                output_times: vec![0., 1.],
                stop: 1.,
                max_step: 0.1,
            },
            0,
        )
        .unwrap();
        let copy_items = crate::event_control::validate(p).unwrap().copy_items;
        ProofContext::source_math_with_work(
            p,
            &trajectory,
            &[],
            copy_items,
            crate::transition_source_plan::Work::limited([128, 8192, limit]),
        )
        .unwrap()
    }
    fn counters() -> [usize; 3] {
        AUXILIARY_EVENTS.with(|c| c.get())
    }
    fn reset() {
        AUXILIARY_EVENTS.with(|c| c.set([0; 3]));
    }
    #[test]
    fn actual_long_owner_auxiliary_uses_one_work_and_stops_before_rejected_operations() {
        let owner = "owner".repeat(1024);
        let (mut p, e) = fixture(&owner, 128);
        if let crate::ir::OperatorSpec::Transition { input, .. } = &mut p.operators[0] {
            *input = e.clone();
        }
        let full = context(&p, 1_000_000_000);
        reset();
        let mut paid = 0usize;
        let ds = audit(&e, &p, &owner, &mut |amount| {
            paid = paid.saturating_add(amount);
            full.charge(amount)
        })
        .unwrap();
        assert_eq!(counters(), [129, 129, 0]);
        assert_eq!(ds.len(), 1);
        assert!(paid >= 129 * owner.len());
        let limited = context(&p, 100000);
        reset();
        let err = audit(&e, &p, &owner, &mut |amount| limited.charge(amount)).unwrap_err();
        assert_eq!(err.kind, "step_budget");
        let accepted = counters();
        assert!(accepted[0] > 0 && accepted[0] < 129);
        assert_eq!(accepted[0], accepted[1]);
        for _ in 0..2 {
            assert_eq!(
                audit(&e, &p, &owner, &mut |amount| limited.charge(amount))
                    .unwrap_err()
                    .kind,
                "step_budget"
            );
            assert_eq!(
                counters(),
                accepted,
                "no owner compare/insert may run after a failed reservation"
            );
        }
        eprintln!("long-owner: {} bare/typed state comparisons, owner_bytes={}, paid={paid}; limited auxiliary before refusal={accepted:?}",129,owner.len());
    }
    #[test]
    fn actual_dependency_merge_is_prepaid_and_retries_cannot_mutate_destination() {
        let (p, _) = fixture("dut", 1);
        let full = context(&p, 1_000_000_000);
        let mut destination: BTreeSet<_> = (0..64).collect();
        let additional: BTreeSet<_> = (64..128).collect();
        reset();
        merge_dependencies(&mut destination, &additional, &mut |amount| {
            full.charge(amount)
        })
        .unwrap();
        assert_eq!(destination.len(), 128);
        assert_eq!(counters(), [0, 0, 1]);
        let limited = context(&p, 100000);
        let mut destination: BTreeSet<_> = (0..64).collect();
        let original = destination.clone();
        reset();
        for _ in 0..3 {
            assert_eq!(
                merge_dependencies(&mut destination, &additional, &mut |amount| limited
                    .charge(amount))
                .unwrap_err()
                .kind,
                "step_budget"
            );
            assert_eq!(destination, original);
            assert_eq!(counters(), [0; 3]);
        }
    }
    #[test]
    fn collection_reservation_dominates_observed_standard_tree_comparisons() {
        thread_local! {static COMPARED:std::cell::Cell<usize>=const {std::cell::Cell::new(0)};}
        #[derive(Clone, PartialEq, Eq)]
        struct Key(usize);
        impl PartialOrd for Key {
            fn partial_cmp(&self, o: &Self) -> Option<std::cmp::Ordering> {
                Some(self.cmp(o))
            }
        }
        impl Ord for Key {
            fn cmp(&self, o: &Self) -> std::cmp::Ordering {
                COMPARED.with(|c| c.set(c.get() + 1));
                self.0.cmp(&o.0)
            }
        }
        let compared = || COMPARED.with(|c| c.get());
        let mut set = BTreeSet::new();
        let mut reserved = 0usize;
        for key in (0..256).rev().chain(0..256) {
            let before = compared();
            let bound = collection_auxiliary_bound(set.len());
            reserved += bound;
            set.insert(Key(key));
            assert!(compared() - before <= bound);
        }
        eprintln!("actual standard BTreeSet comparisons={}, conservative auxiliary reservation={reserved}",compared());
    }
}
