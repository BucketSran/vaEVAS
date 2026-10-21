//! Paid original-program qualification for acyclic ordinary history predicates.
//! The token is local to one prepared request; no wire flag grants admission.
use crate::interval::Interval as I;
use crate::ir::{Error, Expression as E, OperatorSpec, Program};
use crate::transition_source_plan::{ProofContext, Work};
use std::collections::BTreeSet;
use std::sync::Arc;

pub(crate) struct Admission {
    pub(crate) context: Arc<ProofContext>,
    pub(crate) expanded: Vec<E>,
    pub(crate) dependencies: Vec<BTreeSet<usize>>,
}
fn unsupported(message: &str) -> Error {
    Error::new("unsupported_condition", message)
}
fn charge_tree(e: &E, work: &Work) -> Result<usize, Error> {
    work.step()?;
    let size = match e {
        E::Affine { terms, .. } => {
            work.debit(2, terms.len() as u64)?;
            1 + terms.len() * 2
        }
        E::State { .. } | E::Operator { .. } => 1,
        E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
            1 + charge_tree(left, work)? + charge_tree(right, work)?
        }
        E::Select {
            left,
            right,
            then_value,
            else_value,
            origin,
            ..
        } => {
            let mut n = 1 + origin.source.len() + origin.instance.len();
            for child in [left, right, then_value, else_value] {
                n += charge_tree(child, work)?;
            }
            n
        }
        _ => {
            return Err(unsupported(
                "history relations require affine leaves and constant division",
            ))
        }
    };
    Ok(size)
}
pub(crate) fn charge_expression_copy(e: &E, work: &Work) -> Result<(), Error> {
    work.step()?;
    match e {
        E::Affine { terms, .. } => work.debit(2, terms.len().saturating_mul(2) as u64)?,
        E::State { .. } | E::Operator { .. } => (),
        E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
            work.debit(2, 2)?;
            charge_expression_copy(left, work)?;
            charge_expression_copy(right, work)?;
        }
        E::Select {
            left,
            right,
            then_value,
            else_value,
            origin,
            ..
        } => {
            work.debit(
                2,
                (4 + 4 + origin.instance.len() + origin.source.len()) as u64,
            )?;
            for (label, _) in &origin.expansion {
                work.step()?;
                work.debit(2, (label.len() + 1) as u64)?;
            }
            for child in [left, right, then_value, else_value] {
                charge_expression_copy(child, work)?;
            }
        }
        _ => return Err(unsupported("unsupported expression in a paid history copy")),
    }
    Ok(())
}
pub(crate) fn copy_expression(e: &E, work: &Work) -> Result<E, Error> {
    charge_expression_copy(e, work)?;
    crate::diagnostics::counter("history_expression_copies", 1);
    Ok(e.clone())
}
pub(crate) fn same_expression(a: &E, b: &E, w: &Work) -> Result<bool, Error> {
    w.step()?;
    Ok(match (a, b) {
        (
            E::Affine {
                constant: a,
                terms: at,
            },
            E::Affine {
                constant: b,
                terms: bt,
            },
        ) => {
            if a != b || at.len() != bt.len() {
                false
            } else {
                let mut same = true;
                for (a, b) in at.iter().zip(bt) {
                    w.step()?;
                    if a.node != b.node || a.coefficient != b.coefficient {
                        same = false;
                        break;
                    }
                }
                same
            }
        }
        (E::State { state: a }, E::State { state: b }) => a == b,
        (E::Operator { operator: a }, E::Operator { operator: b }) => a == b,
        (E::Add { left: a, right: b }, E::Add { left: c, right: d })
        | (E::Multiply { left: a, right: b }, E::Multiply { left: c, right: d })
        | (E::Divide { left: a, right: b }, E::Divide { left: c, right: d }) => {
            same_expression(a, c, w)? && same_expression(b, d, w)?
        }
        _ => false,
    })
}
pub(crate) fn same_expression_full(a: &E, b: &E, w: &Work) -> Result<bool, Error> {
    w.debit(2, 0)?;
    w.step()?;
    Ok(match (a, b) {
        (
            E::Affine {
                constant: a,
                terms: at,
            },
            E::Affine {
                constant: b,
                terms: bt,
            },
        ) => {
            if a != b || at.len() != bt.len() {
                false
            } else {
                let mut same = true;
                for (a, b) in at.iter().zip(bt) {
                    w.step()?;
                    if a.node != b.node || a.coefficient != b.coefficient {
                        same = false;
                        break;
                    }
                }
                same
            }
        }
        (E::State { state: a }, E::State { state: b }) => a == b,
        (E::Operator { operator: a }, E::Operator { operator: b }) => a == b,
        (E::Add { left: a, right: b }, E::Add { left: c, right: d })
        | (E::Multiply { left: a, right: b }, E::Multiply { left: c, right: d })
        | (E::Divide { left: a, right: b }, E::Divide { left: c, right: d }) => {
            same_expression_full(a, c, w)? && same_expression_full(b, d, w)?
        }
        (
            E::Select {
                left: a,
                right: b,
                then_value: at,
                else_value: ae,
                relation: ac,
                origin: ao,
            },
            E::Select {
                left: c,
                right: d,
                then_value: bt,
                else_value: be,
                relation: bc,
                origin: bo,
            },
        ) => {
            w.debit(
                2,
                (ao.source.len() + bo.source.len() + ao.instance.len() + bo.instance.len() + 8)
                    as u64,
            )?;
            let mut same = ac == bc
                && ao.source == bo.source
                && ao.instance == bo.instance
                && ao.line == bo.line
                && ao.column == bo.column
                && ao.expansion.len() == bo.expansion.len();
            if same {
                for (a, b) in ao.expansion.iter().zip(&bo.expansion) {
                    w.debit(2, (a.0.len() + b.0.len() + 2) as u64)?;
                    if a != b {
                        same = false;
                        break;
                    }
                }
            }
            same && same_expression_full(a, c, w)?
                && same_expression_full(b, d, w)?
                && same_expression_full(at, bt, w)?
                && same_expression_full(ae, be, w)?
        }
        _ => false,
    })
}
pub(crate) fn affine_paid(
    e: &E,
    p: &Program,
    w: &Work,
) -> Result<Vec<crate::interval::Interval>, Error> {
    use crate::interval::Interval as I;
    w.step()?;
    let n = p.nodes.len() + p.states.len() + p.operators.len();
    w.debit(2, (n + 1) as u64)?;
    let mut row = vec![I::ZERO; n + 1];
    match e {
        E::Affine { constant, terms } => {
            row[n] = I::point(*constant);
            for t in terms {
                w.step()?;
                row[t.node] = I::point(t.coefficient);
            }
        }
        E::State { state } => row[p.nodes.len() + state] = I::ONE,
        E::Operator { operator } => row[p.nodes.len() + p.states.len() + operator] = I::ONE,
        E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
            let a = affine_paid(left, p, w)?;
            let b = affine_paid(right, p, w)?;
            if matches!(e, E::Multiply { .. }) {
                let mut ad = false;
                let mut bd = false;
                for x in &a[..n] {
                    w.step()?;
                    if !x.zero() {
                        ad = true;
                        break;
                    }
                }
                for x in &b[..n] {
                    w.step()?;
                    if !x.zero() {
                        bd = true;
                        break;
                    }
                }
                if ad && bd {
                    return Err(unsupported(
                        "history relations require jointly affine leaves",
                    ));
                }
            }
            if matches!(e, E::Divide { .. }) {
                for x in &b[..n] {
                    w.step()?;
                    if !x.zero() {
                        return Err(unsupported(
                            "history division needs a finite nonzero constant",
                        ));
                    }
                }
                if b[n].lo <= 0. && b[n].hi >= 0. {
                    return Err(unsupported("history division crosses zero"));
                }
            }
            for k in 0..=n {
                w.step()?;
                row[k] = match e {
                    E::Add { .. } => a[k] + b[k],
                    E::Multiply { .. } if k == n => a[n] * b[n],
                    E::Multiply { .. } => a[k] * b[n] + b[k] * a[n],
                    _ => a[k] / b[n],
                };
            }
        }
        _ => {
            return Err(unsupported(
                "history affine leaf contains unsupported arithmetic",
            ))
        }
    }
    for value in &row {
        w.step()?;
        if !value.finite() {
            return Err(unsupported("nonfinite original history affine coefficient"));
        }
    }
    Ok(row)
}
/// Qualification only: coordinate hulls of all old Cartesian affine rows.
/// No caller may bind this envelope as a physical expression or root.
/// Inconclusive arithmetic retains the bounded forms route; Work errors do not.
fn affine_shape(
    e: &E,
    p: &Program,
    w: &Work,
) -> Result<Option<Vec<crate::interval::Interval>>, Error> {
    use crate::interval::Interval as I;
    w.debit(2, 0)?;
    w.step()?;
    match e {
        E::Affine { .. } | E::State { .. } | E::Operator { .. } => Ok(Some(affine_paid(e, p, w)?)),
        E::Select {
            left,
            right,
            then_value,
            else_value,
            ..
        } => {
            // Guard rows are qualified too, even when a value arm is constant.
            let left = affine_shape(left, p, w)?;
            let right = affine_shape(right, p, w)?;
            let a = affine_shape(then_value, p, w)?;
            let b = affine_shape(else_value, p, w)?;
            let (Some(_), Some(_), Some(mut a), Some(b)) = (left, right, a, b) else {
                return Ok(None);
            };
            for (a, b) in a.iter_mut().zip(b) {
                w.step()?;
                *a = I {
                    lo: a.lo.min(b.lo),
                    hi: a.hi.max(b.hi),
                };
            }
            Ok(Some(a))
        }
        E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
            let a = affine_shape(left, p, w)?;
            let b = affine_shape(right, p, w)?;
            let (Some(mut a), Some(b)) = (a, b) else {
                return Ok(None);
            };
            let n = a.len() - 1;
            if matches!(e, E::Multiply { .. } | E::Divide { .. }) {
                let mut ad = false;
                let mut bd = false;
                for k in 0..n {
                    w.step()?;
                    ad |= !a[k].zero();
                    bd |= !b[k].zero();
                }
                if matches!(e, E::Multiply { .. }) && ad && bd {
                    return Ok(None);
                }
                if matches!(e, E::Divide { .. }) && (bd || b[n].lo <= 0. && b[n].hi >= 0.) {
                    return Ok(None);
                }
            }
            // Keep affine_paid's operation order, including its zero summand.
            let ac = a[n];
            for k in 0..=n {
                w.step()?;
                a[k] = match e {
                    E::Add { .. } => a[k] + b[k],
                    E::Multiply { .. } if k == n => ac * b[n],
                    E::Multiply { .. } => a[k] * b[n] + b[k] * ac,
                    _ => a[k] / b[n],
                };
                if !a[k].finite() {
                    return Ok(None);
                }
            }
            Ok(Some(a))
        }
        _ => Ok(None),
    }
}
fn qualify_affine(e: &E, p: &Program, w: &Work) -> Result<(), Error> {
    if affine_shape(e, p, w)?.is_none() {
        for leaf in forms(e, w)? {
            affine_paid(&leaf, p, w)?;
        }
    }
    Ok(())
}
fn qualify_all(e: &E, p: &Program, w: &Work) -> Result<(), Error> {
    w.debit(2, 0)?;
    fn guards(e: &E, p: &Program, w: &Work) -> Result<(), Error> {
        w.step()?;
        match e {
            E::Select {
                left,
                right,
                then_value,
                else_value,
                ..
            } => {
                qualify_affine(left, p, w)?;
                qualify_affine(right, p, w)?;
                for c in [left, right, then_value, else_value] {
                    guards(c, p, w)?;
                }
            }
            E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
                guards(left, p, w)?;
                guards(right, p, w)?;
            }
            _ => (),
        }
        Ok(())
    }
    guards(e, p, w)?;
    qualify_affine(e, p, w)
}
pub(crate) fn forms(e: &E, w: &Work) -> Result<Vec<E>, Error> {
    forms_storage(e, w, false)
}
pub(crate) fn target_forms(e: &E, w: &Work) -> Result<Vec<E>, Error> {
    forms_storage(e, w, true)
}
fn forms_storage(e: &E, w: &Work, storage: bool) -> Result<Vec<E>, Error> {
    w.step()?;
    match e {
        E::Select {
            then_value,
            else_value,
            ..
        } => {
            let mut a = forms_storage(then_value, w, storage)?;
            let mut b = forms_storage(else_value, w, storage)?;
            w.debit(2, b.len() as u64)?;
            if storage {
                if a.len().saturating_add(b.len()) > 8192 {
                    return Err(unsupported("history affine expansion exhausted"));
                }
                crate::history_storage::append(&mut a, &mut b, w)?;
            } else {
                a.extend(b)
            };
            if a.len() > 8192 {
                return Err(unsupported("history affine expansion exhausted"));
            }
            Ok(a)
        }
        E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
            let a = forms_storage(left, w, storage)?;
            let b = forms_storage(right, w, storage)?;
            let mut out = Vec::new();
            for left in &a {
                for right in &b {
                    w.step()?;
                    if out.len() >= 8192 {
                        return Err(unsupported("history affine expansion exhausted"));
                    }
                    w.debit(2, 3)?;
                    let left = Box::new(copy_expression(left, w)?);
                    let right = Box::new(copy_expression(right, w)?);
                    let value = match e {
                        E::Add { .. } => E::Add { left, right },
                        E::Multiply { .. } => E::Multiply { left, right },
                        _ => E::Divide { left, right },
                    };
                    if storage {
                        crate::history_storage::push_vec(&mut out, value, w)?;
                    } else {
                        out.push(value)
                    }
                }
            }
            Ok(out)
        }
        _ => {
            let value = copy_expression(e, w)?;
            w.debit(2, 1)?;
            if storage {
                let mut out = Vec::new();
                crate::history_storage::push_vec(&mut out, value, w)?;
                Ok(out)
            } else {
                Ok(vec![value])
            }
        }
    }
}
fn audit_roles(
    e: &E,
    p: &Program,
    work: &Work,
    parents: &mut BTreeSet<usize>,
) -> Result<(), Error> {
    work.step()?;
    match e {
        E::Operator { operator } => {
            if !matches!(
                p.operators.get(*operator),
                Some(OperatorSpec::Transition { .. })
            ) {
                return Err(unsupported(
                    "ordinary history predicate requires a Transition parent",
                ));
            }
            work.debit(2, 1)?;
            parents.insert(*operator);
        }
        E::Select {
            left,
            right,
            then_value,
            else_value,
            ..
        } => {
            for child in [left, right, then_value, else_value] {
                audit_roles(child, p, work, parents)?;
            }
        }
        E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
            audit_roles(left, p, work, parents)?;
            audit_roles(right, p, work, parents)?;
        }
        E::Affine { .. } | E::State { .. } => (),
        _ => return Err(unsupported("unsupported original history relation leaf")),
    }
    Ok(())
}
fn audit(e: &E, p: &Program, work: &Work, parents: &mut BTreeSet<usize>) -> Result<(), Error> {
    // Keep exhausted retries before the original role/parent walk too.
    work.debit(2, 0)?;
    // Keep the original full role/parent walk before structural qualification.
    audit_roles(e, p, work, parents)?;
    qualify_all(e, p, work)
}
fn audit_storage(
    e: &E,
    p: &Program,
    work: &Work,
    parents: &mut BTreeSet<usize>,
    storage: bool,
) -> Result<(), Error> {
    work.step()?;
    match e {
        E::Operator { operator } => {
            if !matches!(
                p.operators.get(*operator),
                Some(OperatorSpec::Transition { .. })
            ) {
                return Err(unsupported(
                    "ordinary history predicate requires a Transition parent",
                ));
            }
            work.debit(2, 1)?;
            if storage {
                crate::event_value_proof::history::map_edit::<()>(parents.len(), work)?;
            }
            parents.insert(*operator);
        }
        E::Select {
            left,
            right,
            then_value,
            else_value,
            ..
        } => {
            for child in [left, right, then_value, else_value] {
                audit_storage(child, p, work, parents, storage)?;
            }
        }
        E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
            audit_storage(left, p, work, parents, storage)?;
            audit_storage(right, p, work, parents, storage)?;
        }
        E::Affine { .. } | E::State { .. } => (),
        _ => return Err(unsupported("unsupported original history relation leaf")),
    }
    // Every arm is checked, including operands killed by zero multiplication.
    // Affine conversion retains held and history coordinates as dynamic leaves.
    for leaf in if storage {
        target_forms(e, work)?
    } else {
        forms(e, work)?
    } {
        affine_paid(&leaf, p, work)?;
    }
    Ok(())
}
// Composition uses the established paid expansion and every-arm affine proof.
// This grants a legacy footprint role, never a driven source-value role.
pub(crate) fn validate_relation_paid(
    e: &E,
    p: &Program,
    owner: &str,
    w: &Work,
) -> Result<(), Error> {
    let items = charge_tree(e, w)?;
    let dimensions = p
        .nodes
        .len()
        .saturating_add(p.states.len())
        .saturating_add(p.operators.len())
        .saturating_add(1);
    w.debit(
        2,
        items.saturating_mul(dimensions).saturating_mul(16) as u64,
    )?;
    crate::continuous::validate_integral_input(e, p, owner)
}
pub(crate) fn qualify_history_expression(
    e: &E,
    p: &Program,
    w: &Work,
) -> Result<BTreeSet<usize>, Error> {
    let mut parents = BTreeSet::new();
    audit_storage(e, p, w, &mut parents, true)?;
    Ok(parents)
}
pub(crate) fn qualify_forcing_read(
    node: usize,
    p: &Program,
    driven: &[String],
    work: &Work,
) -> Result<(), Error> {
    // Validate every legacy relation before expansion can follow its indices.
    // The old validator allocates dense node/state/operator rows at leaves;
    // reserve their full worst-case work before invoking it.
    for c in &p.contributions {
        work.step()?;
        if matches!(c.rhs, E::Forcing { .. }) {
            continue;
        }
        let items = charge_tree(&c.rhs, work)?;
        let dimensions = p
            .nodes
            .len()
            .saturating_add(p.states.len())
            .saturating_add(p.operators.len())
            .saturating_add(1);
        work.debit(2, items.saturating_mul(dimensions).saturating_mul(8) as u64)?;
        crate::continuous::validate_integral_input(&c.rhs, p, &c.origin.instance)?;
    }
    work.debit(2, 3)?;
    let reference = E::Affine {
        constant: 0.,
        terms: vec![crate::ir::Term {
            node,
            coefficient: 1.,
        }],
    };
    let expanded = crate::causal_voltage::expand_paid(&reference, p, driven, work)?;
    let mut parents = BTreeSet::new();
    audit_storage(&expanded, p, work, &mut parents, true)?;
    if parents.is_empty() {
        return Err(unsupported(
            "forcing internal read requires a certified Transition history",
        ));
    }
    Ok(())
}
impl Admission {
    pub(crate) fn condition_affected(&self, p: &Program) -> Result<Vec<bool>, Error> {
        let w = self.context.borrow_work();
        w.debit(2, p.nodes.len() as u64)?;
        let mut affected = vec![false; p.nodes.len()];
        fn row_state(e: &E, p: &Program, w: &Work) -> Result<bool, Error> {
            if let Some(row) = affine_shape(e, p, w)? {
                for v in &row[p.nodes.len()..p.nodes.len() + p.states.len()] {
                    w.step()?;
                    if !v.zero() {
                        return Ok(true);
                    }
                }
                return Ok(false);
            }
            for leaf in forms(e, w)? {
                let row = affine_paid(&leaf, p, w)?;
                for v in &row[p.nodes.len()..p.nodes.len() + p.states.len()] {
                    w.step()?;
                    if !v.zero() {
                        return Ok(true);
                    }
                }
            }
            Ok(false)
        }
        fn guard_state(e: &E, p: &Program, w: &Work) -> Result<bool, Error> {
            w.step()?;
            Ok(match e {
                E::Select {
                    left,
                    right,
                    then_value,
                    else_value,
                    ..
                } => {
                    row_state(left, p, w)?
                        || row_state(right, p, w)?
                        || guard_state(then_value, p, w)?
                        || guard_state(else_value, p, w)?
                }
                E::Add { left, right }
                | E::Multiply { left, right }
                | E::Divide { left, right } => {
                    guard_state(left, p, w)? || guard_state(right, p, w)?
                }
                _ => false,
            })
        }
        for (c, e) in p.contributions.iter().zip(&self.expanded) {
            w.step()?;
            let node = if c.negative == 0 {
                c.positive
            } else if c.positive == 0 {
                c.negative
            } else {
                return Err(unsupported(
                    "history conditions require grounded affine branches",
                ));
            };
            affected[node] |= row_state(e, p, w)? || guard_state(e, p, w)?;
        }
        Ok(affected)
    }
    pub(crate) fn new(
        p: &Program,
        driven: &[String],
        context: Arc<ProofContext>,
    ) -> Result<Arc<Self>, Error> {
        let work = context.borrow_work();
        work.debit(2, 0)?;
        let (_, trajectory, _) = context.original_binding();
        // This existing paid identity checker compares the complete original
        // Program, physical trajectory and driven names before any new helper.
        crate::event_floor::check_provided_binding(&context, p, trajectory, driven)?;
        // Validate all original indices before following a forward relation.
        // A later contribution cannot hide an invalid coordinate behind an alias.
        for c in &p.contributions {
            charge_tree(&c.rhs, work)?;
            crate::continuous::validate_integral_input(&c.rhs, p, &c.origin.instance)?;
        }
        let mut expanded = Vec::new();
        let mut dependencies = Vec::new();
        for c in &p.contributions {
            let expression = crate::causal_voltage::expand_paid(&c.rhs, p, driven, work)?;
            let mut parents = BTreeSet::new();
            audit(&expression, p, work, &mut parents)?;
            work.debit(2, 2)?;
            expanded.push(expression);
            dependencies.push(parents);
        }
        if dependencies.iter().all(BTreeSet::is_empty) {
            return Err(unsupported(
                "ordinary history admission requires an actual Transition dependency",
            ));
        }
        work.debit(2, 1)?;
        Ok(Arc::new(Self {
            context,
            expanded,
            dependencies,
        }))
    }
    pub(crate) fn resolve(
        &self,
        index: usize,
        nodes: &[crate::interval::Interval],
        states: &[crate::interval::Interval],
        operators: &[crate::interval::Interval],
    ) -> Result<E, Error> {
        // Expanded relations prove dependencies, but their value leaves may
        // belong to another instance reached through a voltage interface.
        // Keep the original electrical RHS; expand only predicates to select it.
        let (program, _, driven) = self.context.original_binding();
        resolve_original_expression(
            &program.contributions[index].rhs,
            program,
            driven,
            nodes,
            states,
            operators,
            self.context.borrow_work(),
        )
    }
}
fn history_bounds(e: &E, nodes: &[I], states: &[I], ops: &[I], w: &Work) -> Result<I, Error> {
    w.step()?;
    let value = match e {
        E::Affine { constant, terms } => {
            let mut v = I::point(*constant);
            for t in terms {
                w.step()?;
                v = v + I::point(t.coefficient)
                    * nodes
                        .get(t.node)
                        .copied()
                        .ok_or_else(|| Error::new("invalid_ir", "missing history node binding"))?
            }
            v
        }
        E::State { state } => states
            .get(*state)
            .copied()
            .ok_or_else(|| Error::new("invalid_ir", "missing history state binding"))?,
        E::Operator { operator } => ops
            .get(*operator)
            .copied()
            .ok_or_else(|| Error::new("invalid_ir", "missing history operator binding"))?,
        E::Add { left, right } => {
            history_bounds(left, nodes, states, ops, w)?
                + history_bounds(right, nodes, states, ops, w)?
        }
        E::Multiply { left, right } => {
            history_bounds(left, nodes, states, ops, w)?
                * history_bounds(right, nodes, states, ops, w)?
        }
        E::Divide { left, right } => {
            let a = history_bounds(left, nodes, states, ops, w)?;
            let b = history_bounds(right, nodes, states, ops, w)?;
            if b.lo <= 0. && b.hi >= 0. {
                return Err(unsupported("history division crosses zero"));
            }
            a / b
        }
        _ => return Err(unsupported("unresolved history predicate")),
    };
    if !value.finite() {
        return Err(unsupported("nonfinite history predicate"));
    }
    Ok(value)
}

fn resolve_original_expression(
    expression: &E,
    program: &Program,
    driven: &[String],
    nodes: &[crate::interval::Interval],
    states: &[crate::interval::Interval],
    operators: &[crate::interval::Interval],
    work: &Work,
) -> Result<E, Error> {
    work.step()?;
    let recurse =
        |e: &E| resolve_original_expression(e, program, driven, nodes, states, operators, work);
    Ok(match expression {
        E::Select {
            relation,
            left,
            right,
            then_value,
            else_value,
            ..
        } => {
            let left = crate::causal_voltage::expand_paid(left, program, driven, work)?;
            let right = crate::causal_voltage::expand_paid(right, program, driven, work)?;
            let left = resolve_expression(&left, nodes, states, operators, work)?;
            let right = resolve_expression(&right, nodes, states, operators, work)?;
            let (yes, no) = crate::event_numeric::sign(
                *relation,
                history_bounds(&left, nodes, states, operators, work)?
                    - history_bounds(&right, nodes, states, operators, work)?,
            );
            if !yes && !no {
                return Err(Error::new(
                    "condition_precision",
                    "ordinary history predicate is uncertain",
                ));
            }
            recurse(if yes { then_value } else { else_value })?
        }
        E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
            work.debit(2, 2)?;
            let left = Box::new(recurse(left)?);
            let right = Box::new(recurse(right)?);
            match expression {
                E::Add { .. } => E::Add { left, right },
                E::Multiply { .. } => E::Multiply { left, right },
                E::Divide { .. } => E::Divide { left, right },
                _ => unreachable!(),
            }
        }
        _ => copy_expression(expression, work)?,
    })
}
pub(crate) fn resolve_expression(
    expression: &E,
    nodes: &[crate::interval::Interval],
    states: &[crate::interval::Interval],
    operators: &[crate::interval::Interval],
    work: &Work,
) -> Result<E, Error> {
    use crate::interval::Interval as I;
    fn resolve(e: &E, nodes: &[I], states: &[I], ops: &[I], w: &Work) -> Result<E, Error> {
        w.step()?;
        if matches!(e, E::Add { .. } | E::Multiply { .. } | E::Divide { .. }) {
            w.debit(2, 2)?;
        }
        Ok(match e {
            E::Select {
                relation,
                left,
                right,
                then_value,
                else_value,
                ..
            } => {
                let a = resolve(left, nodes, states, ops, w)?;
                let b = resolve(right, nodes, states, ops, w)?;
                let (yes, no) = crate::event_numeric::sign(
                    *relation,
                    history_bounds(&a, nodes, states, ops, w)?
                        - history_bounds(&b, nodes, states, ops, w)?,
                );
                if !yes && !no {
                    return Err(Error::new(
                        "condition_precision",
                        "ordinary history predicate is uncertain",
                    ));
                }
                return resolve(
                    if yes { then_value } else { else_value },
                    nodes,
                    states,
                    ops,
                    w,
                );
            }
            E::Add { left, right } => E::Add {
                left: Box::new(resolve(left, nodes, states, ops, w)?),
                right: Box::new(resolve(right, nodes, states, ops, w)?),
            },
            E::Multiply { left, right } => E::Multiply {
                left: Box::new(resolve(left, nodes, states, ops, w)?),
                right: Box::new(resolve(right, nodes, states, ops, w)?),
            },
            E::Divide { left, right } => E::Divide {
                left: Box::new(resolve(left, nodes, states, ops, w)?),
                right: Box::new(resolve(right, nodes, states, ops, w)?),
            },
            _ => copy_expression(e, w)?,
        })
    }
    resolve(expression, nodes, states, operators, work)
}

pub(crate) fn held_input(
    e: &E,
    p: &Program,
    owner: &str,
    bounds: &[crate::interval::Interval],
    w: &Work,
) -> Result<(crate::events::AffineState, Vec<crate::interval::Interval>), Error> {
    use crate::interval::Interval as I;
    fn dependencies(
        e: &E,
        p: &Program,
        owner: &str,
        w: &Work,
        out: &mut BTreeSet<usize>,
    ) -> Result<(), Error> {
        w.step()?;
        match e {
            E::Affine { constant, terms } => {
                if !constant.is_finite() {
                    return Err(unsupported("nonfinite held target constant"));
                }
                for t in terms {
                    w.step()?;
                    if t.node != 0 || !t.coefficient.is_finite() {
                        return Err(unsupported(
                            "ordinary history consumer requires held Transition targets",
                        ));
                    }
                }
            }
            E::State { state } => {
                if p.states.get(*state).is_none_or(|s| s.instance != owner) {
                    return Err(Error::new("invalid_ir", "foreign held target state"));
                }
                w.step()?;
                out.insert(*state);
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
                {
                    return Err(Error::new(
                        "invalid_ir",
                        "invalid held target selection origin",
                    ));
                }
                for child in [left, right, then_value, else_value] {
                    dependencies(child, p, owner, w, out)?;
                }
            }
            E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
                dependencies(left, p, owner, w, out)?;
                dependencies(right, p, owner, w, out)?;
            }
            _ => {
                return Err(unsupported(
                    "ordinary history consumer requires independently held Transition targets",
                ))
            }
        }
        Ok(())
    }
    let mut deps = BTreeSet::new();
    dependencies(e, p, owner, w, &mut deps)?;
    qualify_all(e, p, w)?;
    w.debit(2, (p.nodes.len() + p.operators.len()) as u64)?;
    let selected = resolve_expression(
        e,
        &vec![I::ZERO; p.nodes.len()],
        bounds,
        &vec![I::ZERO; p.operators.len()],
        w,
    )?;
    let row = affine_paid(&selected, p, w)?;
    let input = crate::events::AffineState::held_row(&row, p, deps, w)?;
    w.debit(2, (p.states.len() + 1) as u64)?;
    let coefficients = row[p.nodes.len()..p.nodes.len() + p.states.len()]
        .iter()
        .copied()
        .chain([*row.last().unwrap()])
        .collect();
    Ok((input, coefficients))
}

#[cfg(test)]
mod shape_admission_tests {
    use super::*;
    use crate::history_consumer_fixture as fixture;
    use serde_json::json;

    #[test]
    fn shape_admission_many_affine_choices_need_no_cartesian_rows() {
        let fixture = fixture::fixture();
        let p: Program = serde_json::from_value(fixture["program"].clone()).unwrap();
        let origin = fixture["program"]["contributions"][0]["origin"].clone();
        let constant = |x: f64| json!({"op":"affine","constant":x,"terms":[]});
        let mut e = constant(0.);
        for _ in 0..14 {
            let choice = json!({"op":"select","relation":"gt",
                "left":{"op":"state","state":0},"right":constant(0.),
                "then_value":{"op":"operator","operator":0},
                "else_value":constant(0.),"origin":origin});
            e = json!({"op":"add","left":e,"right":choice});
        }
        let e: E = serde_json::from_value(e).unwrap();
        let work = Work::default();
        let mut parents = BTreeSet::new();
        let result = audit(&e, &p, &work, &mut parents);
        assert!(
            result.is_ok(),
            "every branch is affine, but got {result:?}; spent {}",
            work.spent()
        );
        assert_eq!(parents, BTreeSet::from([0]));
        assert_eq!(
            forms(&e, &Work::default()).unwrap_err().message,
            "history affine expansion exhausted",
            "the old forms cap stays 8192"
        );
        println!(
            "structural qualification spent={} for 16384 original branch combinations",
            work.spent()
        );
    }
    #[test]
    fn shape_admission_coordinate_bits_match_cartesian_rows() {
        use crate::interval::Interval as I;
        let fixture = fixture::fixture();
        let p: Program = serde_json::from_value(fixture["program"].clone()).unwrap();
        let origin = fixture["program"]["contributions"][0]["origin"].clone();
        let c = |x: f64| json!({"op":"affine","constant":x,"terms":[]});
        let st = json!({"op":"state","state":0});
        let op = json!({"op":"operator","operator":0});
        let sel = |a: serde_json::Value, b: serde_json::Value| json!({"op":"select","relation":"gt","left":st,"right":c(0.),"then_value":a,"else_value":b,"origin":origin});
        let bin = |name: &str, a: serde_json::Value, b: serde_json::Value| json!({"op":name,"left":a,"right":b});
        let tiny = f64::from_bits(1);
        let cases = vec![
            c(-0.),
            sel(c(-0.), c(0.)),
            sel(st.clone(), c(0.)),
            bin("add", st.clone(), bin("multiply", c(-1.), st.clone())),
            bin("add", sel(st.clone(), op.clone()), sel(c(-1.), c(2.))),
            bin("multiply", sel(c(-2.), c(-1.)), sel(st.clone(), op.clone())),
            bin("multiply", c(0.), sel(st.clone(), op.clone())),
            bin("multiply", c(-0.), sel(st.clone(), op.clone())),
            bin(
                "multiply",
                c(0.5),
                json!({"op":"affine","constant":tiny,"terms":[{"node":1,"coefficient":tiny}]}),
            ),
            bin("divide", sel(st.clone(), op.clone()), sel(c(2.), c(3.))),
            bin("divide", sel(st.clone(), op.clone()), sel(c(-3.), c(-2.))),
            bin(
                "add",
                sel(c(1e-300), c(-1e-300)),
                sel(c(1e-300), c(-1e-300)),
            ),
        ];
        for (index, value) in cases.into_iter().enumerate() {
            let e: E = serde_json::from_value(value).unwrap();
            let shape = affine_shape(&e, &p, &Work::default())
                .unwrap()
                .expect("proved shape");
            let w = Work::default();
            let rows = forms(&e, &w).unwrap();
            let mut expected: Option<Vec<I>> = None;
            for leaf in rows {
                let row = affine_paid(&leaf, &p, &w).unwrap();
                if let Some(old) = &mut expected {
                    for (a, b) in old.iter_mut().zip(row) {
                        *a = I {
                            lo: a.lo.min(b.lo),
                            hi: a.hi.max(b.hi),
                        };
                    }
                } else {
                    expected = Some(row)
                }
            }
            for (slot, (a, b)) in shape.iter().zip(expected.unwrap()).enumerate() {
                assert_eq!(
                    (a.lo.to_bits(), a.hi.to_bits()),
                    (b.lo.to_bits(), b.hi.to_bits()),
                    "case{index} slot{slot}"
                );
            }
        }
        let mixed: E =
            serde_json::from_value(bin("divide", st.clone(), sel(c(-1.), c(1.)))).unwrap();
        assert!(affine_shape(&mixed, &p, &Work::default())
            .unwrap()
            .is_none());
        qualify_all(&mixed, &p, &Work::default()).unwrap();
        let overflow: E = serde_json::from_value(bin("multiply", c(f64::MAX), c(2.))).unwrap();
        assert!(affine_shape(&overflow, &p, &Work::default())
            .unwrap()
            .is_none());
        assert!(qualify_all(&overflow, &p, &Work::default()).is_err());
        let hidden: E =
            serde_json::from_value(bin("multiply", c(0.), bin("multiply", st, op))).unwrap();
        assert!(
            qualify_all(&hidden, &p, &Work::default()).is_err(),
            "zero must not hide a jointly dynamic child"
        );
    }

    #[test]
    fn shape_admission_paid_failures_stay_sticky_before_scan_or_clone() {
        let fixture = fixture::fixture();
        let p: Program = serde_json::from_value(fixture["program"].clone()).unwrap();
        let e = E::State { state: 0 };
        let w = Work::limited([128, 8192, 2]);
        assert!(affine_shape(&e, &p, &w).is_err());
        let before = w.spent();
        for _ in 0..2 {
            assert!(affine_shape(&e, &p, &w).is_err());
            assert!(qualify_all(&e, &p, &w).is_err());
            assert!(audit(&e, &p, &w, &mut BTreeSet::new()).is_err());
            assert_eq!(w.spent(), before);
        }
    }
    #[test]
    fn shape_admission_hidden_roles_and_zero_products_are_audited() {
        let fixture = fixture::fixture();
        let p: Program = serde_json::from_value(fixture["program"].clone()).unwrap();
        let zero = || E::Affine {
            constant: 0.,
            terms: vec![],
        };
        let hidden = E::Multiply {
            left: Box::new(zero()),
            right: Box::new(E::Operator { operator: 1 }),
        };
        assert!(audit(&hidden, &p, &Work::default(), &mut BTreeSet::new()).is_err());
        let valid = E::Multiply {
            left: Box::new(zero()),
            right: Box::new(E::Operator { operator: 0 }),
        };
        let mut parents = BTreeSet::new();
        audit(&valid, &p, &Work::default(), &mut parents).unwrap();
        assert_eq!(parents, BTreeSet::from([0]));
        assert!(affine_shape(&valid, &p, &Work::default())
            .unwrap()
            .unwrap()
            .iter()
            .all(|v| v.zero()));
    }

    #[test]
    fn shape_admission_held_consumer_keeps_selected_rows_and_dependencies() {
        use crate::interval::Interval as I;
        let fixture = fixture::fixture();
        let p: Program = serde_json::from_value(fixture["program"].clone()).unwrap();
        let origin = fixture["program"]["contributions"][0]["origin"].clone();
        let c = |x: f64| json!({"op":"affine","constant":x,"terms":[]});
        let st = json!({"op":"state","state":0});
        let choice = json!({"op":"select","relation":"gt","left":st,"right":c(0.),"then_value":st,"else_value":c(0.),"origin":origin});
        let mut e = c(0.);
        for _ in 0..14 {
            e = json!({"op":"add","left":e,"right":choice});
        }
        let e: E = serde_json::from_value(e).unwrap();
        for (state, expected) in [(0., 0.), (1., 14.)] {
            let bounds = [I::point(state), I::ZERO];
            let (_, row) = held_input(&e, &p, "M", &bounds, &Work::default()).unwrap();
            assert_eq!(row, [I::point(expected), I::ZERO, I::ZERO]);
        }
    }
}

#[cfg(test)]
mod owner_contract_tests {
    use super::*;
    use crate::interval::Interval as I;
    use crate::pwl::Trajectory;
    use serde_json::json;

    fn fixture() -> (Program, Trajectory, Vec<String>) {
        let mut f = crate::history_consumer_fixture::fixture();
        // The existing producer M owns state0. Its physical core voltage is
        // q/8. The consumer C owns no producer state and reads that voltage.
        f["program"]["contributions"][1]["rhs"] = json!({"op":"multiply",
            "left":{"op":"state","state":0},
            "right":{"op":"affine","constant":0.125,"terms":[]}});
        let consumer = &mut f["program"]["contributions"][3];
        consumer["origin"]["instance"] = json!("C");
        consumer["branch"]["instance"] = json!("C");
        let node = || {
            json!({"op":"affine","constant":0.,
            "terms":[{"node":3,"coefficient":1.}]})
        };
        consumer["rhs"] = json!({"op":"select","relation":"gt",
            "left":node(),"right":{"op":"affine","constant":0.0625,"terms":[]},
            "then_value":{"op":"add","left":node(),
                "right":{"op":"affine","constant":0.5,"terms":[]}},
            "else_value":{"op":"affine","constant":0.,"terms":[]},
            "origin":consumer["origin"].clone()});
        let p = serde_json::from_value(f["program"].clone()).unwrap();
        let t =
            Trajectory::new(serde_json::from_value(f["transient"].clone()).unwrap(), 1).unwrap();
        (p, t, vec!["temp".into()])
    }

    fn boxes(p: &Program, q: I) -> (Vec<I>, Vec<I>, Vec<I>) {
        let mut nodes = vec![I::ZERO; p.nodes.len()];
        nodes[1] = I::point(0.5);
        nodes[3] = q * I::point(0.125);
        let mut states = vec![I::ZERO; p.states.len()];
        states[0] = q;
        (nodes, states, vec![I::ZERO; p.operators.len()])
    }

    #[test]
    fn original_voltage_interface_survives_foreign_owner_resolution() {
        let (p, t, driven) = fixture();
        let context = ProofContext::new_held(&p, &t, &driven, 0).unwrap();
        let admission = Admission::new(&p, &driven, context).unwrap();
        for q in [1., 3.] {
            let (nodes, states, operators) = boxes(&p, I::point(q));
            let resolved = admission.resolve(3, &nodes, &states, &operators).unwrap();
            let row = crate::events::affine(&resolved, &p, "C")
                .expect("a consumer keeps its original voltage read, not M's raw state");
            // Independent equation y = V(core) + 1/2; the producer state
            // coefficient must remain zero in the consumer-owned affine row.
            assert_eq!(row.nodes[3], 1.);
            assert_eq!(row.constant, 0.5);
            assert!(row.states.iter().all(|v| *v == 0.));
        }
    }

    #[test]
    fn foreign_raw_state_and_wrong_original_binding_remain_rejected() {
        let (p, t, driven) = fixture();
        assert_eq!(
            crate::events::affine(&E::State { state: 0 }, &p, "C")
                .err()
                .unwrap()
                .kind,
            "invalid_ir"
        );
        let context = ProofContext::new_held(&p, &t, &driven, 0).unwrap();
        let mut wrong_owner = p.clone();
        wrong_owner.states[0].instance = "C".into();
        assert_eq!(
            Admission::new(&wrong_owner, &driven, context.clone())
                .err()
                .unwrap()
                .kind,
            "invalid_ir"
        );
        let mut later_epoch = t.clone();
        later_epoch.config.stop = 2.;
        assert_eq!(
            crate::event_floor::check_provided_binding(&context, &p, &later_epoch, &driven)
                .err()
                .unwrap()
                .kind,
            "invalid_ir"
        );
    }

    #[test]
    fn failed_resolution_retries_in_same_admission_without_mutating_binding() {
        let (p, t, driven) = fixture();
        let original = serde_json::to_value(&p).unwrap();
        let context = ProofContext::new_held(&p, &t, &driven, 0).unwrap();
        let admission = Admission::new(&p, &driven, context.clone()).unwrap();
        // The original guard q/8 > 1/16 cannot be selected for q in[0,1].
        let (n, s, o) = boxes(&p, I { lo: 0., hi: 1. });
        assert_eq!(
            admission.resolve(3, &n, &s, &o).err().unwrap().kind,
            "condition_precision"
        );
        let spent = context.borrow_work().spent();
        let (n, s, o) = boxes(&p, I::point(3.));
        let resolved = admission.resolve(3, &n, &s, &o).unwrap();
        let row = crate::events::affine(&resolved, &p, "C").unwrap();
        assert_eq!((row.nodes[3], row.constant), (1., 0.5));
        assert!(context.borrow_work().spent() > spent);
        assert_eq!(serde_json::to_value(&p).unwrap(), original);
        assert_eq!(
            serde_json::to_value(context.original_binding().0).unwrap(),
            original
        );
    }

    #[test]
    fn actual_resolution_work_exhaustion_stays_sticky_for_two_retries() {
        let (p, t, driven) = fixture();
        let work = Work::limited([128, 8192, 200_000]);
        let context =
            ProofContext::event_request_with_work(&p, &t, &driven, 0, work.clone()).unwrap();
        let admission = Admission::new(&p, &driven, context.clone()).unwrap();
        let (n, s, o) = boxes(&p, I::point(3.));
        // Spend by repeatedly executing the real resolver, never by a synthetic
        // direct debit. A rejected traversal cannot create a fresh ledger.
        loop {
            match admission.resolve(3, &n, &s, &o) {
                Ok(_) => (),
                Err(e) => {
                    assert_eq!(e.kind, "step_budget");
                    break;
                }
            }
        }
        let mut spent = work.spent();
        for _ in 0..2 {
            assert_eq!(
                admission.resolve(3, &n, &s, &o).err().unwrap().kind,
                "step_budget"
            );
            assert!(work.same_owner(context.borrow_work()));
            // Failed reservations may charge their attempted traversal. They
            // must never refund prior work or turn the same ledger usable.
            assert!(work.spent() >= spent);
            spent = work.spent();
        }
    }
}
