//! A private rational cell certificate, separate from displayed float bounds.
//! Ignoring RN is used only to propose a root. Acceptance freezes every actual
//! source RN result, solves the physical affine equations exactly, and checks
//! all executed source values on an independent rational neighborhood.
use crate::{
    event_value_proof::LocalState,
    exact_source::history_paid::Paid,
    interval::Interval as I,
    ir::{Error, Expression as E, Program, RealOperation},
    procedure_operations::{Cell, Domain as EvaluationDomain, Operation as O},
    procedure_values::{Fault, Graph, Id},
    source_domain::Domain,
    transition_source_plan::Work,
};
use num_rational::BigRational as R;
use num_traits::Zero;
use std::sync::Arc;

pub(crate) struct Certificate {
    owner: Work,
    inputs: Vec<f64>,
    before: Vec<f64>,
    pub values: Vec<f64>,
    pub states: Vec<f64>,
    // These are the actual uniqueness domain and exact root witness. Neither
    // is reconstructed from the outward float image returned to observers.
    exact_root: Vec<R>,
    original_nodes: usize,
    proof_box: Vec<Arc<Domain>>,
    frozen: Vec<Option<f64>>,
}
impl Certificate {
    #[cfg(test)]
    pub(crate) fn test_witness(&self) -> (&[R], &[Arc<Domain>]) {
        (&self.exact_root, &self.proof_box)
    }
    pub(crate) fn matches(
        &self,
        inputs: &[I],
        before: &[I],
        values: Option<&[f64]>,
        w: &Work,
    ) -> Result<bool, Error> {
        w.debit(2, 0)?;
        if !self.owner.same_owner(w) {
            return Err(Error::new(
                "invalid_ir",
                "RN cell belongs to another request",
            ));
        }
        w.debit(
            2,
            ((inputs.len() + before.len() + self.exact_root.len() + self.frozen.len()) * 4 + 32)
                as u64,
        )?;
        if !self.owner.same_owner(w)
            || inputs.len() != self.inputs.len()
            || before.len() != self.before.len()
        {
            return Ok(false);
        }
        if !inputs
            .iter()
            .zip(&self.inputs)
            .all(|(b, v)| b.lo.to_bits() == v.to_bits() && b.hi.to_bits() == v.to_bits())
            || !before
                .iter()
                .zip(&self.before)
                .all(|(b, v)| b.lo.to_bits() == v.to_bits() && b.hi.to_bits() == v.to_bits())
        {
            return Ok(false);
        }
        if let Some(values) = values {
            if values.len() > self.values.len()
                || !values
                    .iter()
                    .zip(&self.values)
                    .all(|(a, b)| a.to_bits() == b.to_bits())
            {
                return Ok(false);
            }
        }
        for domain in &self.proof_box {
            domain.share_cost(w)?;
        }
        Ok(true)
    }
    pub(crate) fn bounds(&self, n: usize, w: &Work) -> Result<Vec<I>, Error> {
        w.debit(2, 0)?;
        if !self.owner.same_owner(w) {
            return Err(Error::new(
                "invalid_ir",
                "RN cell belongs to another request",
            ));
        }
        if n > self.exact_root.len() {
            return Err(Error::new(
                "invalid_ir",
                "cell enclosure exceeds certified root",
            ));
        }
        w.debit(2, (n * 16 + 32) as u64)?;
        self.exact_root[..n]
            .iter()
            .enumerate()
            .map(|(i, v)| {
                if i < self.original_nodes {
                    Ok(I::point(self.values[i]))
                } else {
                    crate::exact_source::enclosure_with_work(v, w)?.ok_or_else(|| {
                        Error::new(
                            "waveform_accuracy",
                            "cell root has no finite native enclosure",
                        )
                    })
                }
            })
            .collect()
    }
}
fn arena<T>(v: Result<T, Fault<Error>>) -> Result<T, Error> {
    v.map_err(|e| match e {
        Fault::Quota(e) | Fault::Evaluate(e) => e,
        Fault::InvalidId => Error::new("invalid_ir", "cell source graph is invalid"),
    })
}
fn origin_copy_cost(o: &crate::ir::Origin, w: &Work) -> Result<(), Error> {
    w.debit(2, (o.source.len() + o.instance.len() + 96) as u64)?;
    w.debit(
        2,
        (o.expansion.len() * std::mem::size_of::<(String, usize)>() + 32) as u64,
    )?;
    for (name, _) in &o.expansion {
        w.debit(2, (name.len() + 32) as u64)?;
    }
    Ok(())
}
fn expression_copy_cost(e: &E, w: &Work) -> Result<(), Error> {
    // Derived IR Clone allocates one owned enum for every boxed child; this
    // conservative reservation also includes inline/Vec enum storage.
    w.debit(2, (std::mem::size_of::<E>() + 32) as u64)?;
    match e {
        E::Affine { terms, .. } => w.debit(
            2,
            (terms.len() * std::mem::size_of::<crate::ir::Term>() + 32) as u64,
        )?,
        E::RealBoundary { value, origin, .. }
        | E::IntegerRound { value, origin }
        | E::CheckedInteger { value, origin } => {
            origin_copy_cost(origin, w)?;
            expression_copy_cost(value, w)?;
        }
        E::CheckedIndex { index, origin, .. } => {
            origin_copy_cost(origin, w)?;
            expression_copy_cost(index, w)?;
        }
        E::RealBinary {
            left,
            right,
            origin,
            ..
        } => {
            origin_copy_cost(origin, w)?;
            expression_copy_cost(left, w)?;
            expression_copy_cost(right, w)?;
        }
        E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
            expression_copy_cost(left, w)?;
            expression_copy_cost(right, w)?;
        }
        E::Power { base, .. } => expression_copy_cost(base, w)?,
        E::EventMath { args, origin, .. } => {
            origin_copy_cost(origin, w)?;
            w.debit(2, 32)?;
            for arg in args {
                expression_copy_cost(arg, w)?;
            }
        }
        _ => {
            return Err(Error::new(
                "invalid_ir",
                "unexpected leaf in generated RN-cell physical layout",
            ))
        }
    }
    Ok(())
}
pub(crate) fn clone_program(p: &Program, w: &Work) -> Result<Program, Error> {
    w.debit(2, 0)?;
    // The caller supplies the generated circuit layout, never source control.
    if !p.states.is_empty()
        || !p.events.is_empty()
        || !p.operators.is_empty()
        || !p.step_bounds.is_empty()
        || !p.procedures.is_empty()
        || !p.real_bindings.is_empty()
    {
        return Err(Error::new(
            "invalid_ir",
            "RN-cell clone requires a generated physical layout",
        ));
    }
    w.debit(
        2,
        (std::mem::size_of::<Program>()
            + p.nodes.len() * std::mem::size_of::<String>()
            + p.contributions.len() * std::mem::size_of::<crate::ir::Contribution>()
            + 96) as u64,
    )?;
    for node in &p.nodes {
        w.debit(2, (node.len() + 32) as u64)?;
    }
    for c in &p.contributions {
        w.debit(
            2,
            (c.branch.instance.len()
                + c.branch.local_positive.len()
                + c.branch.local_negative.len()
                + 96) as u64,
        )?;
        origin_copy_cost(&c.origin, w)?;
        expression_copy_cost(&c.rhs, w)?;
    }
    Ok(p.clone())
}
fn relax(e: &mut E, w: &Work) -> Result<(), Error> {
    w.step()?;
    let value = std::mem::replace(
        e,
        E::Affine {
            constant: 0.,
            terms: Vec::new(),
        },
    );
    *e = match value {
        E::RealBoundary { value, .. }
        | E::IntegerRound { value, .. }
        | E::CheckedInteger { value, .. } => {
            let mut value = *value;
            relax(&mut value, w)?;
            value
        }
        E::RealBinary {
            operation,
            mut left,
            mut right,
            ..
        } => {
            relax(&mut left, w)?;
            relax(&mut right, w)?;
            match operation {
                RealOperation::Add => E::Add { left, right },
                RealOperation::Multiply => E::Multiply { left, right },
                RealOperation::Divide => E::Divide { left, right },
                RealOperation::Subtract => {
                    w.debit(2, (2 * std::mem::size_of::<E>() + 64) as u64)?;
                    E::Add {
                        left,
                        right: Box::new(E::Multiply {
                            left: Box::new(E::Affine {
                                constant: -1.,
                                terms: Vec::new(),
                            }),
                            right,
                        }),
                    }
                }
            }
        }
        E::Add {
            mut left,
            mut right,
        } => {
            relax(&mut left, w)?;
            relax(&mut right, w)?;
            E::Add { left, right }
        }
        E::Multiply {
            mut left,
            mut right,
        } => {
            relax(&mut left, w)?;
            relax(&mut right, w)?;
            E::Multiply { left, right }
        }
        E::Divide {
            mut left,
            mut right,
        } => {
            relax(&mut left, w)?;
            relax(&mut right, w)?;
            E::Divide { left, right }
        }
        E::Power { mut base, exponent } => {
            relax(&mut base, w)?;
            E::Power { base, exponent }
        }
        other => other,
    };
    Ok(())
}
fn fixed_inputs(e: &mut E, driven: &[usize], inputs: &[f64], w: &Work) -> Result<(), Error> {
    w.step()?;
    match e {
        E::Affine { constant, terms } => {
            w.debit(
                2,
                (terms
                    .len()
                    .saturating_mul(driven.len() + 1)
                    .saturating_mul(2)) as u64,
            )?;
            if !terms.iter().any(|t| driven.contains(&t.node)) {
                return Ok(());
            }
            w.debit(
                2,
                (terms.len().saturating_mul(
                    4 * std::mem::size_of::<E>() + std::mem::size_of::<crate::ir::Term>() + 128,
                ) + 32) as u64,
            )?;
            let mut value = E::Affine {
                constant: *constant,
                terms: Vec::new(),
            };
            for term in std::mem::take(terms) {
                w.step()?;
                let rhs = if let Some(slot) = driven.iter().position(|&n| n == term.node) {
                    // Keep physical multiplication and accumulation exact. A
                    // known binary parameter is not rounded into an affine
                    // coefficient after combining it with other terms.
                    E::Multiply {
                        left: Box::new(E::Affine {
                            constant: term.coefficient,
                            terms: Vec::new(),
                        }),
                        right: Box::new(E::Affine {
                            constant: inputs[slot],
                            terms: Vec::new(),
                        }),
                    }
                } else {
                    E::Affine {
                        constant: 0.,
                        terms: vec![term],
                    }
                };
                value = E::Add {
                    left: Box::new(value),
                    right: Box::new(rhs),
                };
            }
            *e = value;
        }
        E::RealBoundary { value, .. }
        | E::IntegerRound { value, .. }
        | E::CheckedInteger { value, .. } => fixed_inputs(value, driven, inputs, w)?,
        E::RealBinary { left, right, .. }
        | E::Add { left, right }
        | E::Multiply { left, right }
        | E::Divide { left, right } => {
            fixed_inputs(left, driven, inputs, w)?;
            fixed_inputs(right, driven, inputs, w)?;
        }
        E::Power { base, .. } => fixed_inputs(base, driven, inputs, w)?,
        _ => {}
    }
    Ok(())
}
fn solve_affine(
    p: &mut Program,
    driven: &[usize],
    inputs: &[f64],
    w: &Work,
) -> Result<Option<Vec<R>>, Error> {
    w.debit(2, 0)?;
    if driven.len() != inputs.len() {
        return Ok(None);
    }
    for c in &mut p.contributions {
        fixed_inputs(&mut c.rhs, driven, inputs, w)?;
    }
    let Some(projection) = crate::procedure_affine::project(p, driven, w)? else {
        return Ok(None);
    };
    w.debit(2, ((inputs.len() + p.nodes.len()) * 64 + 64) as u64)?;
    let mut values = Vec::with_capacity(inputs.len());
    for &input in inputs {
        let mut paid = Paid::new(w);
        let value = paid.binary(input);
        let Some(value) = paid.finish(value)? else {
            return Ok(None);
        };
        values.push(value);
    }
    let mut result = Vec::with_capacity(p.nodes.len());
    for row in &projection.rows {
        for coefficient in &row[inputs.len()..row.len() - 1] {
            w.step()?;
            if !coefficient.is_zero() {
                return Ok(None);
            }
        }
        let mut paid = Paid::new(w);
        let value = (|| {
            let mut sum = paid.copy(row.last()?)?;
            for (coefficient, input) in row.iter().zip(&values) {
                paid.pay(1)?;
                if coefficient.is_zero() {
                    continue;
                }
                let product = paid.op(coefficient, input, '*')?;
                sum = paid.op(&sum, &product, '+')?;
            }
            Some(sum)
        })();
        let Some(value) = paid.finish(value)? else {
            return Ok(None);
        };
        result.push(value);
    }
    Ok(Some(result))
}
// Actual point values, full rational boxes, accepted state and the original
// request owner are distinct inputs; none can be inferred from a nominal.
type Replay = (Vec<Cell>, Vec<Arc<Domain>>);
#[allow(clippy::too_many_arguments)]
fn replay(
    graph: &Graph<O>,
    count: usize,
    base: &LocalState,
    states: &[Option<f64>],
    before: &[I],
    root: &[R],
    radii: Option<&[f64]>,
    w: &Work,
) -> Result<Option<Replay>, Error> {
    w.debit(2, 0)?;
    w.debit(2, ((root.len() + count) * 64 + 64) as u64)?;
    let mut domains = Vec::with_capacity(root.len());
    let mut bands = Vec::with_capacity(root.len());
    let mut points = Vec::with_capacity(root.len());
    let mut bounds = Vec::with_capacity(root.len());
    for (index, value) in root.iter().enumerate() {
        let domain = if let Some(radii) = radii {
            Domain::band(value, radii[index], w)?
        } else {
            Domain::point(value, w)?
        };
        let Some(domain) = domain else {
            return Ok(None);
        };
        let Some(bound) = domain.native_enclosure(w)? else {
            return Ok(None);
        };
        let mut paid = Paid::new(w);
        let point = paid.nearest(value);
        let Some(point) = paid.finish(point)? else {
            return Ok(None);
        };
        domain.share_cost(w)?;
        bands.push(Some(domain.clone()));
        domains.push(domain);
        points.push(Some(point));
        bounds.push(bound);
    }
    let local = base.try_candidate_domains(bands, w)?;
    let domain = EvaluationDomain {
        nodes: &points,
        node_bounds: &bounds,
        states,
        state_bounds: before,
        operators: &[],
        operator_bounds: &[],
        local: &local,
    };
    let roots = (0..count).collect::<Vec<_>>();
    let values = arena(graph.evaluate(
        &roots,
        &mut |op, args| {
            let result = op.evaluate(args, &domain, w)?;
            if matches!(op, O::IntegerStore(..)) && result.image.is_none() {
                return Err(Error::new(
                    "integer_range",
                    "cell contains an unresolved executed integer store",
                ));
            }
            Ok(result)
        },
        &mut |v: &Cell| v.copy(w),
        &mut |fee| w.debit(2, fee),
    ))?;
    Ok(Some((values, domains)))
}
fn source_round(op: &O) -> bool {
    matches!(
        op,
        O::Real(..) | O::Boundary(..) | O::IntegerRound(..) | O::CheckedInteger(..)
    )
}
fn rounded_values(
    graph: &Graph<O>,
    values: &[Cell],
    w: &Work,
) -> Result<Option<Vec<Option<f64>>>, Error> {
    w.debit(2, (values.len() * 16 + 32) as u64)?;
    let mut result = Vec::with_capacity(values.len());
    for (id, value) in values.iter().enumerate() {
        w.step()?;
        let Some(node) = graph.node(id) else {
            return Ok(None);
        };
        if source_round(&node.operation) {
            let Some(bound) = value.image else {
                return Ok(None);
            };
            if bound.lo.to_bits() != bound.hi.to_bits() {
                return Ok(None);
            }
            result.push(Some(bound.lo));
        } else {
            result.push(None);
        }
    }
    Ok(Some(result))
}
// The source DAG, generated affine layout and complete accepted domains have
// distinct identities. Keep them explicit at this proof boundary.
#[allow(clippy::too_many_arguments)]
pub(crate) fn certify(
    p: &Program,
    driven: &[usize],
    inputs: &[f64],
    original_inputs: usize,
    node_count: usize,
    ids: &[Id],
    graph: &Graph<O>,
    count: usize,
    base: &LocalState,
    states: &[Option<f64>],
    before: &[I],
    updates: &[Id],
    w: &Work,
) -> Result<Option<Arc<Certificate>>, Error> {
    w.debit(2, 0)?;
    w.debit(
        2,
        ((states.len() + before.len() + updates.len()) * 8 + 64) as u64,
    )?;
    for &id in updates {
        w.step()?;
        if !matches!(
            graph.node(id).map(|n| &n.operation),
            Some(
                O::State(_)
                    | O::Literal(_)
                    | O::Boundary(crate::ir::RealBoundaryKind::Store, _)
                    | O::IntegerStore(..)
            )
        ) {
            return Ok(None);
        }
    }
    if states.len() != before.len()
        || !states.iter().zip(before).all(|(v, b)| {
            v.is_some_and(|v| b.lo.to_bits() == v.to_bits() && b.hi.to_bits() == v.to_bits())
        })
    {
        return Ok(None);
    }
    // This first route owns point inputs only. A hidden exact source value
    // different from its display float must keep its existing root consumer.
    for (&node, &value) in driven.iter().zip(inputs).take(original_inputs) {
        if let Some(exact) = base.floor_node(node) {
            let mut paid = Paid::new(w);
            let order = (|| {
                let binary = paid.binary(value)?;
                paid.cmp(exact, &binary)
            })();
            if !paid.finish(order)?.is_some_and(|o| o.is_eq()) {
                return Ok(None);
            }
        } else {
            return Ok(None);
        }
    }
    let mut proposed = clone_program(p, w)?;
    for c in &mut proposed.contributions {
        relax(&mut c.rhs, w)?;
    }
    let Some(mut root) = solve_affine(&mut proposed, driven, inputs, w)? else {
        return Ok(None);
    };
    let mut previous: Option<Vec<Option<f64>>> = None;
    for _ in 0..32 {
        w.step()?;

        let Some((values, _)) = replay(
            graph,
            count,
            base,
            states,
            before,
            &root[..node_count],
            None,
            w,
        )?
        else {
            return Ok(None);
        };
        let Some(frozen) = rounded_values(graph, &values, w)? else {
            return Ok(None);
        };
        if previous.as_ref().is_some_and(|old| {
            old.iter()
                .zip(&frozen)
                .all(|(a, b)| a.map(f64::to_bits) == b.map(f64::to_bits))
        }) {
            // Require a precisely representable original physical root. The
            // rational cell remains independent even though this root image
            // can be published as singleton binary64 coordinates.
            w.debit(2, (root.len() * 8 + 32) as u64)?;
            let mut native = Vec::with_capacity(root.len());
            for (index, value) in root.iter().enumerate() {
                let mut paid = Paid::new(w);
                let point = paid.nearest(value);
                let Some(point) = paid.finish(point)? else {
                    return Ok(None);
                };
                if index < node_count {
                    let mut paid = Paid::new(w);
                    let order = (|| {
                        let binary = paid.binary(point)?;
                        paid.cmp(value, &binary)
                    })();
                    if !paid.finish(order)?.is_some_and(|o| o.is_eq()) {
                        return Ok(None);
                    }
                }
                native.push(point);
            }
            w.debit(2, (node_count * 8 + 32) as u64)?;
            let mut radii = Vec::with_capacity(node_count);
            for (index, &point) in native[..node_count].iter().enumerate() {
                w.debit(2, driven.len() as u64 + 1)?;
                if index == 0 || driven.contains(&index) {
                    radii.push(0.);
                    continue;
                }
                let radius = (point.next_up() - point)
                    .abs()
                    .min((point - point.next_down()).abs())
                    * 0.25;
                if !radius.is_finite() || radius == 0. {
                    return Ok(None);
                }
                radii.push(radius);
            }
            for _ in 0..32 {
                let Some((box_values, domains)) = replay(
                    graph,
                    count,
                    base,
                    states,
                    before,
                    &root[..node_count],
                    Some(&radii),
                    w,
                )?
                else {
                    return Ok(None);
                };
                if let Some(box_round) = rounded_values(graph, &box_values, w)? {
                    if box_round
                        .iter()
                        .zip(&frozen)
                        .all(|(a, b)| a.map(f64::to_bits) == b.map(f64::to_bits))
                    {
                        w.debit(
                            2,
                            ((inputs.len() + states.len() + updates.len()) * 16
                                + std::mem::size_of::<Certificate>()
                                + 32) as u64,
                        )?;
                        let mut after = Vec::with_capacity(updates.len());
                        for &id in updates {
                            w.step()?;
                            after.push(values[id].point()?);
                        }
                        return Ok(Some(Arc::new(Certificate {
                            owner: w.clone(),
                            original_nodes: node_count,
                            inputs: inputs[..original_inputs].to_vec(),
                            before: states.iter().copied().collect::<Option<Vec<_>>>().unwrap(),
                            values: native,
                            states: after,
                            exact_root: root,
                            proof_box: domains,
                            frozen,
                        })));
                    }
                }
                for radius in &mut radii {
                    w.step()?;
                    if *radius > 0. {
                        *radius *= 0.5;
                        if *radius == 0. {
                            return Ok(None);
                        }
                    }
                }
            }
            return Ok(None);
        }
        let mut fixed = clone_program(p, w)?;
        for c in &mut fixed.contributions {
            w.step()?;
            if c.negative == 0 && c.positive >= node_count {
                if let Some(&id) = ids.get(c.positive - node_count) {
                    if let Some(value) = frozen[id] {
                        c.rhs = E::Affine {
                            constant: value,
                            terms: Vec::new(),
                        };
                    }
                }
            }
        }
        let Some(next) = solve_affine(&mut fixed, driven, inputs, w)? else {
            return Ok(None);
        };
        previous = Some(frozen);
        root = next;
    }
    Ok(None)
}

#[cfg(test)]
mod tests {
    #[test]
    fn rn_cell_layout_clone_prepays_deep_origin_and_sticky_retry() {
        let request: crate::ir::Request =
            serde_json::from_str(include_str!("testdata/rn_cell_gain_two.json")).unwrap();
        let mut p = request.program;
        p.states.clear();
        p.events.clear();
        p.operators.clear();
        p.procedures.clear();
        p.real_bindings.clear();
        p.step_bounds.clear();
        for c in &mut p.contributions {
            c.rhs = super::E::Affine {
                constant: 0.,
                terms: Vec::new(),
            };
        }
        let small = super::Work::default();
        super::clone_program(&p, &small).unwrap();
        p.contributions[0].origin.source = "x".repeat(1024 * 1024);
        let large = super::Work::default();
        let copied = super::clone_program(&p, &large).unwrap();
        assert_eq!(copied.contributions[0].origin.source.len(), 1024 * 1024);
        assert!(large.spent() > small.spent() + 1024 * 1024 - 1024);
        let limited = super::Work::limited([128, 8192, 10_000]);
        assert_eq!(
            super::clone_program(&p, &limited).err().unwrap().kind,
            "step_budget"
        );
        let spent = limited.spent();
        assert_eq!(
            super::clone_program(&p, &limited.clone())
                .err()
                .unwrap()
                .kind,
            "step_budget"
        );
        assert_eq!(limited.spent(), spent);
    }
    #[test]
    fn rn_cell_public_binary_roots_and_scaled_states_match_independent_rn_answers() {
        let fixtures = [
            (
                include_str!("testdata/rn_cell_gain_two.json"),
                vec![2., -2.],
            ),
            (
                include_str!("testdata/rn_cell_scale_small.json"),
                vec![2_f64.powi(-79)],
            ),
            (
                include_str!("testdata/rn_cell_scale_large.json"),
                vec![2_f64.powi(81)],
            ),
            (
                include_str!("testdata/rn_cell_coupled17.json"),
                vec![-0.09523809523809534, 1.619047619047619],
            ),
            (
                include_str!("testdata/rn_cell_coupled18.json"),
                vec![0.72, 1.24],
            ),
        ];
        for (source, expected) in fixtures {
            let response = crate::run(serde_json::from_str(source).unwrap()).unwrap();
            let response = serde_json::to_value(response).unwrap();
            assert_eq!(
                response["transient"]["states"]
                    .as_array()
                    .unwrap()
                    .last()
                    .unwrap(),
                &serde_json::json!(expected)
            );
        }
    }
    #[test]
    fn rn_cell_exact_matrix_uses_original_work_and_retry_does_not_refund() {
        let request: crate::ir::Request =
            serde_json::from_str(include_str!("testdata/rn_cell_gain_two.json")).unwrap();
        let mut p = request.program;
        p.nodes = vec!["0".into(), "y".into()];
        p.states.clear();
        p.events.clear();
        p.procedures.clear();
        p.real_bindings.clear();
        p.contributions.truncate(1);
        p.contributions[0].positive = 1;
        p.contributions[0].negative = 0;
        p.contributions[0].rhs = super::E::Add {
            left: Box::new(super::E::Multiply {
                left: Box::new(super::E::Affine {
                    constant: 0.5,
                    terms: Vec::new(),
                }),
                right: Box::new(super::E::Affine {
                    constant: 0.,
                    terms: vec![crate::ir::Term {
                        node: 1,
                        coefficient: 1.,
                    }],
                }),
            }),
            right: Box::new(super::E::Affine {
                constant: 1.,
                terms: Vec::new(),
            }),
        };
        let full = super::Work::default();
        let root = super::solve_affine(&mut p, &[], &[], &full)
            .unwrap()
            .unwrap();
        assert_eq!(root[1], num_rational::BigRational::from_integer(2.into()));
        let owner = super::Work::limited([128, 8192, full.spent() - 1]);
        assert_eq!(
            super::solve_affine(&mut p, &[], &[], &owner)
                .err()
                .unwrap()
                .kind,
            "step_budget"
        );
        let spent = owner.spent();
        assert_eq!(
            super::solve_affine(&mut p, &[], &[], &owner.clone())
                .err()
                .unwrap()
                .kind,
            "step_budget"
        );
        assert_eq!(owner.spent(), spent);
    }
    #[test]
    fn rn_cell_negative_gain_binary_two_cycle_has_no_certified_root() {
        let error = crate::run(
            serde_json::from_str(include_str!("testdata/rn_cell_no_float_root.json")).unwrap(),
        )
        .err()
        .unwrap();
        assert_eq!(error.kind, "waveform_accuracy");
    }
}
