//! Exact physical relations before a source procedure executes. Each RHS that
//! is not plain physical affine arithmetic owns a separate opaque parameter.
//! This prevents cancellation of different source-position state captures.
use crate::exact_source::history_paid::Paid;
use crate::ir::{Error, Expression as E, Program};
use crate::transition_source_plan::Work;
use num_rational::BigRational as R;
use num_traits::{One, Zero};

pub(crate) struct Projection {
    pub owner: Work,
    pub rows: Vec<Vec<R>>,
    pub driven: Vec<usize>,
    pub opaque_start: usize,
}
fn zeros(n: usize, w: &Work) -> Result<Vec<R>, Error> {
    w.debit(2, (n as u64).saturating_mul(64).saturating_add(32))?;
    Ok(vec![R::zero(); n])
}
fn op(a: &R, b: &R, operation: char, w: &Work) -> Result<Option<R>, Error> {
    let mut paid = Paid::new(w);
    let value = paid.op(a, b, operation);
    paid.finish(value)
}
fn binary(a: f64, w: &Work) -> Result<Option<R>, Error> {
    let mut paid = Paid::new(w);
    let value = paid.binary(a);
    paid.finish(value)
}
fn copy(a: &R, w: &Work) -> Result<Option<R>, Error> {
    let mut paid = Paid::new(w);
    let value = paid.copy(a);
    paid.finish(value)
}
fn constant(row: &[R], w: &Work) -> Result<bool, Error> {
    for value in &row[..row.len() - 1] {
        w.step()?;
        if !value.is_zero() {
            return Ok(false);
        }
    }
    Ok(true)
}
fn affine(e: &E, n: usize, w: &Work) -> Result<Option<Vec<R>>, Error> {
    w.step()?;
    match e {
        E::Affine { constant, terms } => {
            let mut row = zeros(n + 1, w)?;
            let Some(value) = binary(*constant, w)? else {
                return Ok(None);
            };
            row[n] = value;
            for term in terms {
                w.step()?;
                if term.node == 0 || term.coefficient == 0. {
                    continue;
                }
                if term.node >= n {
                    return Ok(None);
                }
                let Some(value) = binary(term.coefficient, w)? else {
                    return Ok(None);
                };
                let Some(sum) = op(&row[term.node], &value, '+', w)? else {
                    return Ok(None);
                };
                row[term.node] = sum;
            }
            Ok(Some(row))
        }
        E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
            let Some(mut a) = affine(left, n, w)? else {
                return Ok(None);
            };
            let Some(b) = affine(right, n, w)? else {
                return Ok(None);
            };
            if matches!(e, E::Add { .. }) {
                for (a, b) in a.iter_mut().zip(&b) {
                    let Some(value) = op(a, b, '+', w)? else {
                        return Ok(None);
                    };
                    *a = value;
                }
                return Ok(Some(a));
            }
            if matches!(e, E::Divide { .. }) {
                if !constant(&b, w)? || b[n].is_zero() {
                    return Ok(None);
                }
                for a in &mut a {
                    let Some(value) = op(a, &b[n], '/', w)? else {
                        return Ok(None);
                    };
                    *a = value;
                }
                return Ok(Some(a));
            }
            if constant(&b, w)? {
                for a in &mut a {
                    let Some(value) = op(a, &b[n], '*', w)? else {
                        return Ok(None);
                    };
                    *a = value;
                }
                Ok(Some(a))
            } else if constant(&a, w)? {
                let mut row = zeros(n + 1, w)?;
                for (entry, b) in row.iter_mut().zip(&b) {
                    let Some(value) = op(&a[n], b, '*', w)? else {
                        return Ok(None);
                    };
                    *entry = value;
                }
                Ok(Some(row))
            } else {
                Ok(None)
            }
        }
        E::Power { base, exponent: 1 } => affine(base, n, w),
        E::Power { exponent: 0, .. } => {
            let mut row = zeros(n + 1, w)?;
            row[n] = R::one();
            Ok(Some(row))
        }
        // Program RN, snapshots, state, operators and branch selection are not
        // physical affine substitutions, even if their nominal value is known.
        _ => Ok(None),
    }
}
/// A map valid for every independent RHS parameter. It makes no assertion that
/// an opaque source expression is executable, finite, or a unique RN value.
pub(crate) fn project(
    p: &Program,
    driven: &[usize],
    w: &Work,
) -> Result<Option<Projection>, Error> {
    use crate::ir::{ProcedureAction as A, ProcedureControl as C};
    if !p.procedures.is_empty() {
        w.debit(2, (p.contributions.len() * 8 + 32) as u64)?;
        let mut unconditional = vec![false; p.contributions.len()];
        for procedure in &p.procedures {
            for step in &procedure.body {
                w.step()?;
                if let A::Control(C::ContributionCapture { contribution }) = &step.action {
                    if let Some(value) = unconditional.get_mut(*contribution) {
                        *value = true;
                    }
                }
            }
        }
        if unconditional.iter().any(|v| !v) {
            return Ok(None);
        }
    }
    let n = p.nodes.len();
    let width = n + driven.len() + p.contributions.len() + 1;
    w.debit(2, ((p.contributions.len() + n) * 48 + 64) as u64)?;
    let mut groups: Vec<(usize, Vec<R>)> = Vec::with_capacity(p.contributions.len());
    for (index, c) in p.contributions.iter().enumerate() {
        w.step()?;
        let mut group = None;
        for (k, (prior, _)) in groups.iter().enumerate() {
            let old = &p.contributions[*prior].branch;
            w.debit(
                2,
                (old.instance.len()
                    + old.local_positive.len()
                    + old.local_negative.len()
                    + c.branch.instance.len()
                    + c.branch.local_positive.len()
                    + c.branch.local_negative.len()
                    + 4) as u64,
            )?;
            if old == &c.branch {
                group = Some(k);
                break;
            }
        }
        let k = if let Some(k) = group {
            k
        } else {
            let mut row = zeros(width, w)?;
            if c.positive >= n || c.negative >= n {
                return Ok(None);
            }
            row[c.positive] = R::one();
            let Some(value) = op(&row[c.negative], &R::one(), '-', w)? else {
                return Ok(None);
            };
            row[c.negative] = value;
            groups.push((index, row));
            groups.len() - 1
        };
        let row = &mut groups[k].1;
        if let Some(rhs) = affine(&c.rhs, n, w)? {
            for (a, b) in row[..n].iter_mut().zip(&rhs[..n]) {
                let Some(v) = op(a, b, '-', w)? else {
                    return Ok(None);
                };
                *a = v;
            }
            let Some(value) = op(&row[width - 1], &rhs[n], '-', w)? else {
                return Ok(None);
            };
            row[width - 1] = value;
        } else {
            row[n + driven.len() + index] = -R::one();
        }
    }
    let mut unknown = Vec::with_capacity(n);
    for node in 1..n {
        w.debit(2, driven.len() as u64 + 1)?;
        if !driven.contains(&node) {
            unknown.push(node);
        }
    }
    let mut rank = 0;
    for &column in &unknown {
        let mut pivot = None;
        for (index, (_, row)) in groups.iter().enumerate().skip(rank) {
            w.step()?;
            if !row[column].is_zero() {
                pivot = Some(index);
                break;
            }
        }
        let Some(pivot) = pivot else { return Ok(None) };
        groups.swap(rank, pivot);
        let Some(divisor) = copy(&groups[rank].1[column], w)? else {
            return Ok(None);
        };
        for value in &mut groups[rank].1 {
            let Some(v) = op(value, &divisor, '/', w)? else {
                return Ok(None);
            };
            *value = v;
        }
        for r in 0..groups.len() {
            w.step()?;
            if r == rank || groups[r].1[column].is_zero() {
                continue;
            }
            let Some(factor) = copy(&groups[r].1[column], w)? else {
                return Ok(None);
            };
            for c in 0..width {
                let Some(product) = op(&factor, &groups[rank].1[c], '*', w)? else {
                    return Ok(None);
                };
                let Some(value) = op(&groups[r].1[c], &product, '-', w)? else {
                    return Ok(None);
                };
                groups[r].1[c] = value;
            }
        }
        rank += 1;
    }
    for (_, row) in groups.iter().skip(rank) {
        for value in row.iter().skip(1) {
            w.step()?;
            if !value.is_zero() {
                return Ok(None);
            }
        }
    }
    let out_width = driven.len() + p.contributions.len() + 1;
    w.debit(2, (n * 32 + driven.len() * 8 + 64) as u64)?;
    let mut rows = Vec::with_capacity(n);
    for _ in 0..n {
        rows.push(zeros(out_width, w)?);
    }
    for (index, &node) in driven.iter().enumerate() {
        if node == 0 || node >= n {
            return Ok(None);
        }
        rows[node][index] = R::one();
    }
    for (r, &node) in unknown.iter().enumerate() {
        for (index, &driven_node) in driven.iter().enumerate() {
            let Some(value) = op(&R::zero(), &groups[r].1[driven_node], '-', w)? else {
                return Ok(None);
            };
            rows[node][index] = value;
        }
        for (index, slot) in rows[node].iter_mut().enumerate().skip(driven.len()) {
            let c = if index == out_width - 1 {
                width - 1
            } else {
                n + index
            };
            let Some(value) = op(&R::zero(), &groups[r].1[c], '-', w)? else {
                return Ok(None);
            };
            *slot = value;
        }
    }
    w.debit(2, 16)?;
    Ok(Some(Projection {
        owner: w.clone(),
        rows,
        driven: driven.to_vec(),
        opaque_start: driven.len(),
    }))
}

#[cfg(test)]
mod tests {
    use super::*;
    fn fixture() -> Program {
        serde_json::from_value(serde_json::json!({
            "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","u","y","z"],
            "contributions":[
                {"branch":{"instance":"dut","local_positive":"y","local_negative":"0","kind":"voltage"},"positive":2,"negative":0,"rhs":{"op":"state","state":0},"origin":{"source":"physical.va","line":1,"column":1,"instance":"dut"}},
                {"branch":{"instance":"dut","local_positive":"y","local_negative":"0","kind":"voltage"},"positive":2,"negative":0,"rhs":{"op":"multiply","left":{"op":"affine","constant":-1,"terms":[]},"right":{"op":"state","state":0}},"origin":{"source":"physical.va","line":1,"column":2,"instance":"dut"}},
                {"branch":{"instance":"dut","local_positive":"z","local_negative":"0","kind":"voltage"},"positive":3,"negative":0,"rhs":{"op":"affine","constant":-0.25,"terms":[{"node":1,"coefficient":2}]},"origin":{"source":"physical.va","line":1,"column":3,"instance":"dut"}}
            ]
        })).unwrap()
    }
    #[test]
    fn independent_voltage_relation_does_not_cancel_distinct_captures() {
        let p = fixture();
        let owner = Work::default();
        let map = project(&p, &[1], &owner).unwrap().unwrap();
        assert_eq!(map.rows[3][0], R::from_integer(2.into()));
        assert_eq!(map.rows[3].last().unwrap(), &R::new((-1).into(), 4.into()));
        assert!(map.rows[3][1..4].iter().all(Zero::is_zero));
        // These syntactically state-equal RHSs can capture different source
        // positions, so their coefficients remain independent unknowns.
        assert_eq!(map.rows[2][1], R::one());
        assert_eq!(map.rows[2][2], R::one());
    }
    #[test]
    fn exact_matrix_and_copies_keep_the_same_sticky_request_budget() {
        let p = fixture();
        let full = Work::default();
        assert!(project(&p, &[1], &full).unwrap().is_some());
        let owner = Work::limited([128, 8192, full.spent() / 2]);
        assert_eq!(project(&p, &[1], &owner).err().unwrap().kind, "step_budget");
        let spent = owner.spent();
        assert_eq!(project(&p, &[1], &owner).err().unwrap().kind, "step_budget");
        assert!(owner.spent() > spent);
    }
    #[test]
    fn public_source_reads_the_independent_physical_voltage_at_both_timer_roots() {
        let request: crate::ir::Request =
            serde_json::from_str(include_str!("testdata/independent_voltage_sample.json")).unwrap();
        let response = crate::run(request).unwrap();
        let response = serde_json::to_value(response).unwrap();
        assert_eq!(
            response["transient"]["states"],
            serde_json::json!([[0.], [2.], [2.]])
        );
        assert_eq!(response["solutions"][1]["voltages"][1], 0.75);
        assert_eq!(response["solutions"][2]["voltages"][1], 1.75);
    }
    #[test]
    fn complete_uncertain_source_is_not_replaced_with_its_center() {
        let mut request: serde_json::Value =
            serde_json::from_str(include_str!("testdata/independent_voltage_sample.json")).unwrap();
        request["transient"]["pwl_errors_V"] = serde_json::json!([0.01]);
        let request: crate::ir::Request = serde_json::from_value(request).unwrap();
        let model = crate::events::EventModel::new(
            request.program.clone(),
            request.driven.clone(),
            request.tolerances.clone(),
        )
        .unwrap();
        let mut trajectory =
            crate::pwl::Trajectory::new(request.transient.clone().unwrap(), 1).unwrap();
        trajectory
            .bind_procedure_work(crate::real_expression::work(&model))
            .unwrap();
        let proofs = crate::event_value_proof::Proofs::new();
        let root = crate::exact_source::RootTime::point(0.5).unwrap();
        let bounds = trajectory.checked_value_bounds(0.5).unwrap();
        let context = crate::event_value_proof::Context::try_new(
            &model,
            &trajectory,
            &bounds,
            &proofs,
            Some(&root),
        )
        .unwrap();
        let local = crate::event_value_proof::LocalState::try_with_context(
            &[crate::interval::Interval::ZERO],
            Some(&context),
        )
        .unwrap();
        assert!(
            local.floor_node(1).is_none(),
            "uncertain input cannot yield a point proof for z"
        );
        // The complete output voltage error already exceeds the original
        // request's accuracy budget before the first event.
        assert_eq!(crate::run(request).err().unwrap().kind, "waveform_accuracy");
    }
}
