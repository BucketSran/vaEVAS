//! Certified rows for original history/time × exact physical DC supply products.
//! The original Program is never rewritten and keeps ownership and dependencies.
use crate::ir::{Error, Expression as E, Program};
use crate::pwl::Trajectory;
use crate::transition_source_plan::{ProofContext, Work};
use std::sync::Arc;

pub(crate) struct DcProjection {
    pub(crate) source: Arc<ProofContext>,
    entries: Vec<(E, E, usize)>,
    held_ramp: bool,
}
/// A final candidate observation, distinct from the earlier physical event root.
/// Epochs retain their original time proofs; no sampled state seeds a timestamp.
pub(crate) struct HeldRampObservationProof<'a> {
    projection: &'a DcProjection,
    program: &'a Program,
    trajectory: &'a Trajectory,
    driven: &'a [String],
    root: crate::exact_source::RootTime,
    states: &'a [crate::interval::Interval],
    epochs: &'a crate::exact_source::TimeProofs,
}
impl HeldRampObservationProof<'_> {
    pub(crate) fn state_bounds(&self) -> &[crate::interval::Interval] {
        self.states
    }
    pub(crate) fn validate_states(
        &self,
        states: &[crate::interval::Interval],
    ) -> Result<(), Error> {
        let work = self.projection.source.borrow_work();
        self.projection.source.charge(1)?;
        for (&state, epoch) in self.epochs {
            self.projection.source.charge(1)?;
            let Some(bounds) = states.get(state) else {
                return Err(Error::new(
                    "condition_precision",
                    "physical epoch state missing",
                ));
            };
            if epoch.refine_with_work(*bounds, work)?.is_none()
                || epoch.refine_with_work(self.states[state], work)?.is_none()
            {
                return Err(Error::new(
                    "condition_precision",
                    "physical epoch contradicts certified state enclosure",
                ));
            }
        }
        Ok(())
    }
    #[allow(clippy::too_many_arguments)]
    pub(crate) fn sign(
        &self,
        left: &E,
        right: &E,
        owner: &str,
        program: &Program,
        driven: &[String],
        nodes: &[crate::interval::Interval],
        states: &[crate::interval::Interval],
    ) -> Result<Option<i8>, Error> {
        let source = &self.projection.source;
        let work = source.borrow_work();
        source.charge(1)?;
        if !std::ptr::eq(program, self.program)
            || !std::ptr::eq(driven, self.driven)
            || states.len() != self.states.len()
            || nodes.len() != program.nodes.len()
        {
            return Ok(None);
        }
        fn audit(
            e: &E,
            proof: &HeldRampObservationProof<'_>,
            owner: &str,
            nodes: &[crate::interval::Interval],
            states: &[crate::interval::Interval],
        ) -> Result<bool, Error> {
            let source = &proof.projection.source;
            let work = source.borrow_work();
            source.charge(1)?;
            Ok(match e {
                E::Affine { constant, terms } => {
                    let mut valid = constant.is_finite();
                    for term in terms {
                        source.charge(1)?;
                        if DcProjection::ramp_time_node(proof.program, term.node, source)?
                            != Some(true)
                        {
                            valid = false;
                            continue;
                        }
                        let mut found = None;
                        for (index, &node) in source.event_input_nodes().iter().enumerate() {
                            source.charge(1)?;
                            if node == term.node {
                                found = Some(index);
                                break;
                            }
                        }
                        let Some(index) = found else {
                            valid = false;
                            continue;
                        };
                        source.charge(1)?;
                        if proof
                            .trajectory
                            .config
                            .pwl_errors_v
                            .as_ref()
                            .and_then(|errors| errors.get(index))
                            .is_some_and(|error| error.bound() > 0.)
                            || !proof.trajectory.original_identity_history(index, work)?
                        {
                            valid = false;
                            continue;
                        }
                        let Some(bounds) = nodes.get(term.node) else {
                            valid = false;
                            continue;
                        };
                        valid &= proof.root.refine_with_work(*bounds, work)?.is_some();
                        valid &= term.coefficient.is_finite();
                    }
                    valid
                }
                E::State { state } => {
                    let Some(held) = proof.program.states.get(*state) else {
                        return Ok(false);
                    };
                    source.charge(1 + owner.len() + held.instance.len())?;
                    let Some(epoch) = proof.epochs.get(state) else {
                        return Ok(false);
                    };
                    let Some(bounds) = states.get(*state) else {
                        return Ok(false);
                    };
                    held.instance == owner
                        && matches!(held.kind, crate::ir::StateKind::Real)
                        && epoch
                            .refine_with_work(proof.states[*state], work)?
                            .is_some()
                        && epoch.refine_with_work(*bounds, work)?.is_some()
                }
                E::Add { left, right } | E::Multiply { left, right } => {
                    let a = audit(left, proof, owner, nodes, states)?;
                    let b = audit(right, proof, owner, nodes, states)?;
                    a && b
                }
                _ => false,
            })
        }
        let a = audit(left, self, owner, nodes, states)?;
        let b = audit(right, self, owner, nodes, states)?;
        if !a || !b {
            return Ok(None);
        }
        let items = DcProjection::ramp_items(left, source)?
            .saturating_add(DcProjection::ramp_items(right, source)?);
        source.charge(items.saturating_mul(8).saturating_add(32))?;
        let guard = E::Add {
            left: Box::new(left.clone()),
            right: Box::new(E::Multiply {
                left: Box::new(E::Affine {
                    constant: -1.,
                    terms: vec![],
                }),
                right: Box::new(right.clone()),
            }),
        };
        let Some(curve) = self.trajectory.original_guard_curve_history(
            &guard,
            source.event_input_nodes(),
            self.trajectory.config.stop,
            self.epochs,
            work,
        )?
        else {
            return Ok(None);
        };
        let Some(value) = curve.at_root_history(&self.root, work)? else {
            return Ok(None);
        };
        let mut paid = crate::exact_source::history_paid::Paid::new(work);
        let sign = paid
            .binary(0.)
            .and_then(|zero| paid.cmp(&value, &zero))
            .map(|order| match order {
                std::cmp::Ordering::Less => -1,
                std::cmp::Ordering::Equal => 0,
                std::cmp::Ordering::Greater => 1,
            });
        paid.finish(sign)
    }
}
/// The original physical event root and accepted epoch frame. This is never
/// used as an ordinary observation or as the final representative point.
pub(crate) struct HeldRampPhysicalContext<'a> {
    projection: &'a DcProjection,
    model: &'a crate::events::EventModel,
    trajectory: &'a Trajectory,
    root: &'a crate::exact_source::RootTime,
    representative: f64,
    before: &'a [crate::interval::Interval],
    epochs: &'a crate::exact_source::TimeProofs,
}
pub(crate) struct PreparedPhysicalEpochs {
    pub(crate) states: Vec<crate::interval::Interval>,
    pub(crate) epochs: crate::exact_source::TimeProofs,
}
impl HeldRampPhysicalContext<'_> {
    pub(crate) fn prepare(
        &self,
        selection: &crate::event_conditions::Selection,
        inputs: &[crate::interval::Interval],
    ) -> Result<PreparedPhysicalEpochs, Error> {
        use crate::interval::Interval as I;
        let source = &self.projection.source;
        source.charge(
            self.model
                .program
                .nodes
                .len()
                .saturating_mul(2)
                .saturating_add(self.before.len().saturating_mul(8))
                .saturating_add(16),
        )?;
        let mut nodes = vec![
            I {
                lo: f64::NEG_INFINITY,
                hi: f64::INFINITY
            };
            self.model.program.nodes.len()
        ];
        nodes[0] = I::ZERO;
        for (&node, &value) in source.event_input_nodes().iter().zip(inputs) {
            nodes[node] = value;
        }
        let mut after = self.before.to_vec();
        for (event, indices) in &selection.actions {
            source.charge(self.before.len().saturating_mul(2).saturating_add(8))?;
            let mut local = self.before.to_vec();
            let owner = &self.model.program.events[*event].origin.instance;
            fn audit_body(
                items: &[crate::ir::Statement],
                p: &Program,
                owner: &str,
                source: &ProofContext,
            ) -> Result<usize, Error> {
                let mut assignments = 0usize;
                for item in items {
                    source.charge(1)?;
                    match item {
                        crate::ir::Statement::Assign(a) => {
                            DcProjection::held_time(&a.rhs, p, owner, source)?;
                            DcProjection::held_time(
                                &E::State { state: a.state },
                                p,
                                owner,
                                source,
                            )?;
                            assignments = assignments.saturating_add(1);
                        }
                        crate::ir::Statement::If {
                            left,
                            right,
                            then_body,
                            else_body,
                            origin,
                            ..
                        } => {
                            source.charge(1 + owner.len() + origin.instance.len())?;
                            if origin.instance != owner {
                                return Err(Error::new(
                                    "invalid_ir",
                                    "physical preview branch owner mismatch",
                                ));
                            }
                            DcProjection::held_time(left, p, owner, source)?;
                            DcProjection::held_time(right, p, owner, source)?;
                            assignments = assignments
                                .saturating_add(audit_body(then_body, p, owner, source)?)
                                .saturating_add(audit_body(else_body, p, owner, source)?);
                        }
                        _ => {
                            return Err(Error::new(
                                "unsupported_dc_projection",
                                "physical preview requires original time/state Assign/If",
                            ))
                        }
                    }
                }
                Ok(assignments)
            }
            let count = audit_body(
                &self.model.program.events[*event].body,
                &self.model.program,
                owner,
                source,
            )?;
            source.charge(count.saturating_mul(4).saturating_add(8))?;
            let assignments = self.model.program.events[*event].assignments();
            for &index in indices {
                let assignment = &assignments[index];
                // Audit every original operand before interval preview, even
                // a zero coefficient or unselected arithmetic arm.
                DcProjection::held_time(&assignment.rhs, &self.model.program, owner, source)?;
                let held = &self.model.program.states[assignment.state];
                source.charge(1 + owner.len() + held.instance.len())?;
                if held.instance != *owner || !matches!(held.kind, crate::ir::StateKind::Real) {
                    return Err(Error::new(
                        "unsupported_dc_projection",
                        "physical epoch assignment requires original real owner",
                    ));
                }
                let items = DcProjection::ramp_items(&assignment.rhs, source)?;
                source.charge(items.saturating_mul(128).saturating_add(8))?;
                let value = crate::event_numeric::bounds(&assignment.rhs, &nodes, &local)?;
                if !value.finite() {
                    return Err(Error::new(
                        "condition_precision",
                        "physical epoch preview is not finite",
                    ));
                }
                local[assignment.state] = value;
                after[assignment.state] = value;
            }
        }
        let epochs = crate::transient::time_provenance::apply_with_bound_source(
            self.model,
            self.trajectory,
            selection,
            self.epochs,
            self.root,
            self.before,
            &after,
            source,
        )?;
        Ok(PreparedPhysicalEpochs {
            states: after,
            epochs,
        })
    }
    pub(crate) fn representative_proof<'a>(
        &'a self,
        prepared: &'a PreparedPhysicalEpochs,
    ) -> Result<HeldRampObservationProof<'a>, Error> {
        self.projection
            .observation_proof(
                &self.model.program,
                self.trajectory,
                &self.model.driven,
                self.representative,
                &prepared.states,
                &prepared.epochs,
            )?
            .ok_or_else(|| {
                Error::new(
                    "condition_precision",
                    "representative observation proof unavailable",
                )
            })
    }
    pub(crate) fn proof<'a>(
        &'a self,
        prepared: &'a PreparedPhysicalEpochs,
    ) -> Result<HeldRampObservationProof<'a>, Error> {
        Ok(HeldRampObservationProof {
            projection: self.projection,
            program: &self.model.program,
            trajectory: self.trajectory,
            driven: &self.model.driven,
            root: self
                .root
                .clone_with_work(self.projection.source.borrow_work())?,
            states: &prepared.states,
            epochs: &prepared.epochs,
        })
    }
}
impl DcProjection {
    pub(crate) fn is_held_ramp(&self) -> bool {
        self.held_ramp
    }

    #[allow(clippy::too_many_arguments)]
    pub(crate) fn physical_context<'a>(
        &'a self,
        model: &'a crate::events::EventModel,
        trajectory: &'a Trajectory,
        root: &'a crate::exact_source::RootTime,
        window: crate::interval::Interval,
        representative: f64,
        before: &'a [crate::interval::Interval],
        epochs: &'a crate::exact_source::TimeProofs,
    ) -> Result<Option<HeldRampPhysicalContext<'a>>, Error> {
        self.source.charge(1)?;
        if !self.held_ramp
            || before.len() != model.program.states.len()
            || !representative.is_finite()
            || representative < window.lo
            || representative > window.hi
            || root
                .refine_with_work(window, self.source.borrow_work())?
                .is_none()
        {
            return Ok(None);
        }
        crate::event_floor::check_provided_binding(
            &self.source,
            &model.program,
            trajectory,
            &model.driven,
        )?;
        Ok(Some(HeldRampPhysicalContext {
            projection: self,
            model,
            trajectory,
            root,
            representative,
            before,
            epochs,
        }))
    }

    pub(crate) fn observation_proof<'a>(
        &'a self,
        program: &'a Program,
        trajectory: &'a Trajectory,
        driven: &'a [String],
        time: f64,
        states: &'a [crate::interval::Interval],
        epochs: &'a crate::exact_source::TimeProofs,
    ) -> Result<Option<HeldRampObservationProof<'a>>, Error> {
        self.source.charge(1)?;
        if !self.held_ramp
            || !time.is_finite()
            || time < 0.
            || time > trajectory.config.stop
            || states.len() != program.states.len()
        {
            return Ok(None);
        }
        crate::event_floor::check_provided_binding(&self.source, program, trajectory, driven)?;
        let mut paid = crate::exact_source::history_paid::Paid::new(self.source.borrow_work());
        let root = paid
            .binary(time)
            .map(crate::exact_source::history_paid::root);
        let Some(root) = paid.finish(root)? else {
            return Ok(None);
        };
        Ok(Some(HeldRampObservationProof {
            projection: self,
            program,
            trajectory,
            driven,
            root,
            states,
            epochs,
        }))
    }

    /// Cheap dispatch hint only. A source factor is still proved on the complete
    /// physical request by with_source, never by a node name or initial value.
    pub(crate) fn held_ramp_candidate(p: &Program) -> bool {
        fn factor(e: &E) -> bool {
            matches!(e, E::Affine { terms, .. } if !terms.is_empty())
        }
        fn scalar(e: &E) -> bool {
            matches!(e, E::Affine { constant, terms } if terms.is_empty() && constant.is_finite())
        }
        fn elapsed_hint(
            e: &E,
            time: usize,
            remaining: &mut usize,
            flags: &mut (bool, bool),
        ) -> bool {
            if flags.0 && flags.1 {
                return true;
            }
            if *remaining == 0 {
                return false;
            }
            *remaining -= 1;
            match e {
                E::Affine { terms, .. } => {
                    for term in terms {
                        if *remaining == 0 {
                            return false;
                        }
                        *remaining -= 1;
                        flags.0 |= term.node == time;
                    }
                }
                E::State { .. } => flags.1 = true,
                E::Add { left, right }
                | E::Multiply { left, right }
                | E::Divide { left, right } => {
                    if elapsed_hint(left, time, remaining, flags) {
                        return true;
                    }
                    return elapsed_hint(right, time, remaining, flags);
                }
                E::Select {
                    left,
                    right,
                    then_value,
                    else_value,
                    ..
                } => {
                    for child in [left, right, then_value, else_value] {
                        if elapsed_hint(child, time, remaining, flags) {
                            return true;
                        }
                    }
                }
                // Do not inspect an Operator's input to infer a held-time
                // contribution. Pure legacy Transition products stay legacy.
                _ => {}
            }
            flags.0 && flags.1
        }
        fn product(e: &E, time: usize, remaining: &mut usize) -> bool {
            if *remaining == 0 {
                return false;
            }
            *remaining -= 1;
            match e {
                E::Multiply { left, right } if scalar(left) => product(right, time, remaining),
                E::Multiply { left, right } if scalar(right) => product(left, time, remaining),
                E::Divide { left, right }
                    if matches!(right.as_ref(), E::Affine { constant, terms }
                        if terms.is_empty() && constant.is_finite() && *constant != 0.) =>
                {
                    product(left, time, remaining)
                }
                E::Multiply { left, right } => {
                    let source_shape = |x: &E| factor(x) || matches!(x, E::Add { .. });
                    (source_shape(left)
                        && elapsed_hint(right, time, remaining, &mut (false, false)))
                        || (source_shape(right)
                            && elapsed_hint(left, time, remaining, &mut (false, false)))
                }
                E::Add { left, right } => {
                    product(left, time, remaining) || product(right, time, remaining)
                }
                _ => false,
            }
        }
        let Some(time) = p.nodes.iter().position(|n| n == "$abstime") else {
            return false;
        };
        // One total hint allowance, including both sides and all outputs.
        // Full original-tree qualification is mandatory after this hint.
        let mut remaining = 32;
        !p.states.is_empty()
            && p.operators
                .iter()
                .all(|o| matches!(o, crate::ir::OperatorSpec::Transition { .. }))
            && p.contributions
                .iter()
                .any(|c| product(&c.rhs, time, &mut remaining))
    }

    /// Pure time/held-state selected-affine operands. Structural dependencies
    /// survive even at zero weight. No state is replaced by a sampled value.
    fn held_time(
        e: &E,
        p: &Program,
        owner: &str,
        source: &ProofContext,
    ) -> Result<(bool, bool), Error> {
        source.charge(1)?;
        let unsupported = || {
            Error::new(
                "unsupported_dc_projection",
                "DC held ramp requires selected-affine time and same-owner held state only",
            )
        };
        let merge = |a: (bool, bool), b: (bool, bool)| (a.0 || b.0, a.1 || b.1);
        match e {
            E::Affine { terms, .. } => {
                source.charge(terms.len())?;
                for term in terms {
                    if Self::ramp_time_node(p, term.node, source)? != Some(true) {
                        return Err(unsupported());
                    }
                }
                Ok((!terms.is_empty(), false))
            }
            E::State { state } => {
                let held = p.states.get(*state).ok_or_else(|| {
                    Error::new(
                        "invalid_ir",
                        "DC held ramp state must belong to its instance",
                    )
                })?;
                source.charge(
                    owner
                        .len()
                        .saturating_add(held.instance.len())
                        .saturating_add(1),
                )?;
                if held.instance != owner {
                    return Err(Error::new(
                        "invalid_ir",
                        "DC held ramp state must belong to its instance",
                    ));
                }
                Ok((false, true))
            }
            E::Add { left, right } => Ok(merge(
                Self::held_time(left, p, owner, source)?,
                Self::held_time(right, p, owner, source)?,
            )),
            E::Multiply { left, right } | E::Divide { left, right } => {
                let a = Self::held_time(left, p, owner, source)?;
                let b = Self::held_time(right, p, owner, source)?;
                let scalar = |x: &E| matches!(x, E::Affine { constant, terms } if terms.is_empty() && constant.is_finite());
                if matches!(e, E::Divide { .. }) {
                    if !matches!(right.as_ref(), E::Affine { constant, terms } if terms.is_empty() && constant.is_finite() && *constant != 0.)
                    {
                        return Err(unsupported());
                    }
                } else if !scalar(left) && !scalar(right) {
                    return Err(unsupported());
                }
                Ok(merge(a, b))
            }
            E::Select {
                left,
                right,
                then_value,
                else_value,
                ..
            } => {
                let mut flags = (false, false);
                for child in [left, right, then_value, else_value] {
                    flags = merge(flags, Self::held_time(child, p, owner, source)?);
                }
                Ok(flags)
            }
            _ => Err(unsupported()),
        }
    }

    fn transition_leaf(
        e: &E,
        p: &Program,
        owner: &str,
        source: &ProofContext,
    ) -> Result<(), Error> {
        source.charge(1)?;
        let E::Operator { operator } = e else {
            return Err(Error::new(
                "unsupported_dc_projection",
                "DC mixed view requires a bare Transition leaf",
            ));
        };
        let spec = p
            .operators
            .get(*operator)
            .ok_or_else(|| Error::new("invalid_ir", "DC mixed view operator index is invalid"))?;
        source.charge(
            1usize
                .saturating_add(owner.len())
                .saturating_add(spec.origin().instance.len()),
        )?;
        if spec.origin().instance != owner {
            return Err(Error::new(
                "invalid_ir",
                "DC mixed view Transition must belong to its original instance",
            ));
        }
        if !matches!(spec, crate::ir::OperatorSpec::Transition { .. }) {
            return Err(Error::new(
                "unsupported_dc_projection",
                "DC mixed view supports existing Transition history only",
            ));
        }
        Ok(())
    }

    fn ramp_view(e: &E, p: &Program, owner: &str, source: &ProofContext) -> Result<E, Error> {
        source.charge(1)?;
        let scalar = |x: &E| matches!(x, E::Affine { constant, terms } if terms.is_empty() && constant.is_finite());
        match e {
            E::Multiply { left, right } => {
                if scalar(left) || scalar(right) {
                    return Ok(E::Multiply {
                        left: Box::new(Self::ramp_view(left, p, owner, source)?),
                        right: Box::new(Self::ramp_view(right, p, owner, source)?),
                    });
                }
                let a = Self::ramp_supply(left, p, source)?;
                let b = Self::ramp_supply(right, p, source)?;
                if a != Some(true) && b != Some(true) {
                    if !scalar(left) && !scalar(right) {
                        return Err(Error::new(
                            "unsupported_dc_projection",
                            "DC held ramp rejects products of time, held state or varying inputs",
                        ));
                    }
                    return Ok(E::Multiply {
                        left: Box::new(Self::ramp_view(left, p, owner, source)?),
                        right: Box::new(Self::ramp_view(right, p, owner, source)?),
                    });
                }
                let (supply, elapsed, swapped) = if a == Some(true) {
                    (left, right, false)
                } else {
                    (right, left, true)
                };
                if matches!(elapsed.as_ref(), E::Operator { .. }) {
                    Self::transition_leaf(elapsed, p, owner, source)?;
                } else {
                    let flags = Self::held_time(elapsed, p, owner, source)?;
                    if flags != (true, true) {
                        return Err(Error::new("unsupported_dc_projection", "DC held ramp product requires both physical time and a retained held state"));
                    }
                }
                // The complete original source expression is proved without
                // merging coefficients or taking a nominal t=0 sample.
                let value = E::Affine {
                    constant: source.exact_dc_expression(supply, owner)?,
                    terms: vec![],
                };
                let count = Self::ramp_items(elapsed, source)?;
                source.charge(count)?;
                let elapsed = elapsed.as_ref().clone();
                Ok(if swapped {
                    E::Multiply {
                        left: Box::new(elapsed),
                        right: Box::new(value),
                    }
                } else {
                    E::Multiply {
                        left: Box::new(value),
                        right: Box::new(elapsed),
                    }
                })
            }
            E::Add { left, right } => Ok(E::Add {
                left: Box::new(Self::ramp_view(left, p, owner, source)?),
                right: Box::new(Self::ramp_view(right, p, owner, source)?),
            }),
            E::Divide { left, right } if matches!(right.as_ref(), E::Affine { constant, terms } if terms.is_empty() && constant.is_finite() && *constant != 0.) => {
                Ok(E::Divide {
                    left: Box::new(Self::ramp_view(left, p, owner, source)?),
                    right: Box::new(Self::ramp_view(right, p, owner, source)?),
                })
            }
            E::Operator { .. } => {
                Self::transition_leaf(e, p, owner, source)?;
                Ok(e.clone())
            }
            E::Affine { terms, .. } => {
                source.charge(terms.len())?;
                Ok(e.clone())
            }
            _ => {
                Self::held_time(e, p, owner, source)?;
                let count = Self::ramp_items(e, source)?;
                source.charge(count)?;
                Ok(e.clone())
            }
        }
    }
    fn ramp_items(e: &E, source: &ProofContext) -> Result<usize, Error> {
        source.charge(1)?;
        Ok(match e {
            E::Affine { terms, .. } => {
                source.charge(terms.len())?;
                1 + terms.len()
            }
            E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
                1 + Self::ramp_items(left, source)? + Self::ramp_items(right, source)?
            }
            E::Select {
                left,
                right,
                then_value,
                else_value,
                origin,
                ..
            } => {
                source.charge(origin.expansion.len())?;
                let metadata = origin
                    .source
                    .len()
                    .saturating_add(origin.instance.len())
                    .saturating_add(origin.expansion.iter().fold(0usize, |n, (name, _)| {
                        n.saturating_add(name.len()).saturating_add(1)
                    }));
                1usize
                    .saturating_add(metadata)
                    .saturating_add(Self::ramp_items(left, source)?)
                    .saturating_add(Self::ramp_items(right, source)?)
                    .saturating_add(Self::ramp_items(then_value, source)?)
                    .saturating_add(Self::ramp_items(else_value, source)?)
            }
            _ => 1,
        })
    }
    fn ramp_time_node(
        p: &Program,
        node: usize,
        source: &ProofContext,
    ) -> Result<Option<bool>, Error> {
        source.charge(1)?;
        let Some(name) = p.nodes.get(node) else {
            return Ok(None);
        };
        // Equality against the fixed eight-byte reserved name reads at most
        // eight content bytes; charge the length test and that upper bound.
        source.charge(1 + name.len().min("$abstime".len()))?;
        Ok(Some(name == "$abstime"))
    }
    fn ramp_supply(e: &E, p: &Program, source: &ProofContext) -> Result<Option<bool>, Error> {
        source.charge(1)?;
        Ok(match e {
            E::Affine { terms, .. } => {
                source.charge(terms.len())?;
                for term in terms {
                    if Self::ramp_time_node(p, term.node, source)? != Some(false) {
                        return Ok(None);
                    }
                }
                Some(!terms.is_empty())
            }
            E::Add { left, right } => match (
                Self::ramp_supply(left, p, source)?,
                Self::ramp_supply(right, p, source)?,
            ) {
                (Some(a), Some(b)) => Some(a || b),
                _ => None,
            },
            E::Multiply { left, right } => {
                let scalar = |x: &E| matches!(x, E::Affine { constant, terms } if terms.is_empty() && constant.is_finite());
                if scalar(left) {
                    Self::ramp_supply(right, p, source)?
                } else if scalar(right) {
                    Self::ramp_supply(left, p, source)?
                } else {
                    None
                }
            }
            _ => None,
        })
    }

    pub(crate) fn new(p: &Program, t: &Trajectory, driven: &[String]) -> Result<Arc<Self>, Error> {
        if Self::held_ramp_candidate(p) {
            return Err(Error::new(
                "invalid_ir",
                "DC held ramp requires its original prepared source context",
            ));
        }
        let source = ProofContext::new(p, t, driven, Work::for_trajectory(t))?;
        Self::with_source(p, source)
    }
    pub(crate) fn with_source(p: &Program, source: Arc<ProofContext>) -> Result<Arc<Self>, Error> {
        let held_ramp = Self::held_ramp_candidate(p);
        if held_ramp {
            let (_, physical, driven) = source.original_binding();
            crate::event_floor::check_provided_binding(&source, p, physical, driven)?;
        }
        fn audit(
            e: &E,
            p: &Program,
            owner: &str,
            source: &ProofContext,
            priced_owner: bool,
        ) -> Result<(), Error> {
            source.charge(1)?;
            let invalid = || {
                Error::new(
                    "invalid_ir",
                    "DC projection original reference/Origin must belong to its instance",
                )
            };
            match e {
                E::Affine { terms, .. } => {
                    source.charge(terms.len())?;
                    crate::expression::validate(e, p.nodes.len())?;
                }
                E::State { state } => {
                    if priced_owner {
                        if let Some(held) = p.states.get(*state) {
                            source.charge(
                                1usize
                                    .saturating_add(owner.len())
                                    .saturating_add(held.instance.len()),
                            )?;
                        }
                    }
                    if p.states.get(*state).is_none_or(|s| s.instance != owner) {
                        return Err(invalid());
                    }
                }
                E::Operator { operator } => {
                    if priced_owner {
                        if let Some(spec) = p.operators.get(*operator) {
                            source.charge(
                                1usize
                                    .saturating_add(owner.len())
                                    .saturating_add(spec.origin().instance.len()),
                            )?;
                        }
                    }
                    if p.operators
                        .get(*operator)
                        .is_none_or(|o| o.origin().instance != owner)
                    {
                        return Err(invalid());
                    }
                }
                E::Add { left, right }
                | E::Multiply { left, right }
                | E::Divide { left, right } => {
                    audit(left, p, owner, source, priced_owner)?;
                    audit(right, p, owner, source, priced_owner)?;
                }
                E::Power { base, .. } => audit(base, p, owner, source, priced_owner)?,
                E::Select {
                    left,
                    right,
                    then_value,
                    else_value,
                    origin,
                    ..
                } => {
                    if priced_owner {
                        source.charge(origin.expansion.len())?;
                        let bytes = owner
                            .len()
                            .saturating_add(origin.instance.len())
                            .saturating_add(origin.source.len())
                            .saturating_add(
                                origin.expansion.iter().fold(0usize, |n, (name, _)| {
                                    n.saturating_add(name.len()).saturating_add(1)
                                }),
                            );
                        source.charge(bytes.saturating_add(1))?;
                    }
                    if origin.instance != owner
                        || origin.source.is_empty()
                        || origin.line == 0
                        || origin.column == 0
                        || !origin.valid_expansion()
                    {
                        return Err(invalid());
                    }
                    for child in [left, right, then_value, else_value] {
                        audit(child, p, owner, source, priced_owner)?;
                    }
                }
                _ => {
                    return Err(Error::new(
                        "unsupported_dc_projection",
                        "DC projection original history syntax is unsupported",
                    ))
                }
            }
            Ok(())
        }
        // Audit every original history arm before requesting any physical fact.
        // This walk has no dense coefficient vectors and charges each node/term.
        for op in &p.operators {
            source.charge(1)?;
            if let crate::ir::OperatorSpec::Transition { input, origin, .. } = op {
                if held_ramp {
                    source.charge(origin.expansion.len())?;
                    let bytes = origin
                        .instance
                        .len()
                        .saturating_add(origin.source.len())
                        .saturating_add(origin.expansion.iter().fold(0usize, |n, (name, _)| {
                            n.saturating_add(name.len()).saturating_add(1)
                        }));
                    source.charge(bytes.saturating_add(1))?;
                }
                if origin.instance.is_empty()
                    || origin.source.is_empty()
                    || origin.line == 0
                    || origin.column == 0
                    || !origin.valid_expansion()
                {
                    return Err(Error::new(
                        "invalid_ir",
                        "invalid DC projection history Origin",
                    ));
                }
                audit(input, p, &origin.instance, &source, held_ramp)?;
            } else {
                return Err(Error::new(
                    "unsupported_dc_projection",
                    "DC projection only supports Transition history",
                ));
            }
        }
        for c in &p.contributions {
            audit(&c.rhs, p, &c.origin.instance, &source, held_ramp)?;
        }
        fn nodes(e: &E, source: &ProofContext) -> Result<usize, Error> {
            source.charge(1)?;
            Ok(match e {
                E::Affine { terms, .. } => {
                    source.charge(terms.len())?;
                    1 + terms.len()
                }
                E::Add { left, right } | E::Multiply { left, right } => {
                    1 + nodes(left, source)? + nodes(right, source)?
                }
                _ => 1,
            })
        }
        fn walk(e: &E, owner: &str, source: &ProofContext) -> Result<E, Error> {
            source.charge(1)?;
            Ok(match e {
                E::Multiply { left, right } => {
                    fn supply(e: &E, source: &ProofContext) -> Result<Option<bool>, Error> {
                        source.charge(1)?;
                        Ok(match e {
                            E::Affine { terms, .. } => {
                                source.charge(terms.len())?;
                                Some(!terms.is_empty())
                            }
                            E::Add { left, right } | E::Multiply { left, right } => {
                                match (supply(left, source)?, supply(right, source)?) {
                                    (Some(a), Some(b)) => Some(a || b),
                                    _ => None,
                                }
                            }
                            _ => None,
                        })
                    }
                    let scalar = |e: &E| -> Result<E, Error> {
                        Ok(E::Affine {
                            constant: source.exact_dc_affine(e, owner)?,
                            terms: vec![],
                        })
                    };
                    if supply(left, source)? == Some(true) {
                        E::Multiply {
                            left: Box::new(scalar(left)?),
                            right: Box::new(walk(right, owner, source)?),
                        }
                    } else if supply(right, source)? == Some(true) {
                        E::Multiply {
                            left: Box::new(walk(left, owner, source)?),
                            right: Box::new(scalar(right)?),
                        }
                    } else {
                        E::Multiply {
                            left: Box::new(walk(left, owner, source)?),
                            right: Box::new(walk(right, owner, source)?),
                        }
                    }
                }
                E::Add { left, right } => E::Add {
                    left: Box::new(walk(left, owner, source)?),
                    right: Box::new(walk(right, owner, source)?),
                },
                E::Affine { terms, .. } => {
                    source.charge(terms.len())?;
                    e.clone()
                }
                E::State { .. } | E::Operator { .. } => e.clone(),
                _ => {
                    return Err(Error::new(
                        "unsupported_dc_projection",
                        "DC projection requires original sums and supply products",
                    ))
                }
            })
        }
        let mut entries = Vec::new();
        for c in &p.contributions {
            let count = if held_ramp {
                Self::ramp_items(&c.rhs, &source)?
            } else {
                nodes(&c.rhs, &source)?
            };
            source.charge(count)?; // retained original tree copy
            let view = if held_ramp {
                Self::ramp_view(&c.rhs, p, &c.origin.instance, &source)?
            } else {
                walk(&c.rhs, &c.origin.instance, &source)?
            };
            // Existing matrix construction checks the view's joint affinity;
            // no speculative matrix pass or fallback owner is introduced here.
            entries.push((c.rhs.clone(), view, count));
        }
        Ok(Arc::new(Self {
            source,
            entries,
            held_ramp,
        }))
    }
    pub(crate) fn view<'a>(&'a self, e: &'a E) -> Result<&'a E, Error> {
        for (original, view, count) in &self.entries {
            self.source.charge(*count)?; // every original-tree comparison
            if original == e {
                return Ok(view);
            }
        }
        Ok(e)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::interval::Interval as I;
    fn fixture(limit: u64) -> (Program, Trajectory, Arc<ProofContext>, E) {
        let p:Program=serde_json::from_value(serde_json::json!({
            "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","a","b","y"],
            "states":[{"instance":"d","name":"s","kind":"real","initial":0}],
            "operators":[{"kind":"transition","input":{"op":"select","relation":"gt","left":{"op":"state","state":0},"right":{"op":"affine","constant":0,"terms":[]},"then_value":{"op":"affine","constant":1,"terms":[]},"else_value":{"op":"affine","constant":0,"terms":[]},"origin":{"source":"dc-retry.va","line":1,"column":3,"instance":"d"}},"delay":0,"rise":0.25,"fall":0.25,
                "origin":{"source":"dc-retry.va","line":1,"column":1,"instance":"d"}}],
            "contributions":[{"branch":{"instance":"d","local_positive":"y","local_negative":"b","kind":"voltage"},
                "positive":3,"negative":2,"rhs":{"op":"multiply","left":{"op":"operator","operator":0},
                    "right":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1},{"node":2,"coefficient":-1}]}},
                "origin":{"source":"dc-retry.va","line":1,"column":2,"instance":"d"}}]
        })).unwrap();
        let t = Trajectory::new(
            crate::ir::TransientInputs {
                analytic_sources: vec![],
                pwl_errors_v: None,
                strobetimes: vec![],
                pwl: vec![vec![[0., 0.75], [2., 0.75]], vec![[0., 0.25], [2., 0.25]]],
                output_times: vec![0., 2.],
                stop: 2.,
                max_step: 1.,
                proof_work_limit: None,
            },
            2,
        )
        .unwrap();
        let source = ProofContext::new(
            &p,
            &t,
            &["a".into(), "b".into()],
            Work::limited([128, 8192, limit]),
        )
        .unwrap();
        let supply = if let E::Multiply { right, .. } = &p.contributions[0].rhs {
            *right.clone()
        } else {
            unreachable!()
        };
        (p, t, source, supply)
    }
    fn ramp_fixture(
        limit: u64,
        unknown_zero_weight: bool,
    ) -> (Program, Trajectory, Arc<ProofContext>) {
        let mut terms = vec![serde_json::json!({"node":1,"coefficient":1.})];
        if unknown_zero_weight {
            terms.push(serde_json::json!({"node":4,"coefficient":0.}));
        }
        let p: Program = serde_json::from_value(serde_json::json!({
            "schema_version":crate::ir::SCHEMA_VERSION,
            "nodes":["0","rail","$abstime","y","unknown"],
            "states":[{"instance":"d","name":"epoch","kind":"real","initial":0}],
            "operators":[],
            "contributions":[{
                "branch":{"instance":"d","local_positive":"y","local_negative":"0","kind":"voltage"},
                "positive":3,"negative":0,
                "rhs":{"op":"multiply",
                    "left":{"op":"affine","constant":0,"terms":terms},
                    "right":{"op":"add",
                        "left":{"op":"affine","constant":0,"terms":[{"node":2,"coefficient":1}]},
                        "right":{"op":"multiply","left":{"op":"affine","constant":-1,"terms":[]},"right":{"op":"state","state":0}}}},
                "origin":{"source":"dc-ramp-budget.va","line":1,"column":1,"instance":"d"}}]
        })).unwrap();
        let t = Trajectory::new(
            crate::ir::TransientInputs {
                analytic_sources: vec![],
                pwl_errors_v: None,
                strobetimes: vec![],
                pwl: vec![vec![[0., 1.], [16., 1.]], vec![[0., 0.], [16., 16.]]],
                output_times: vec![0., 16.],
                stop: 16.,
                max_step: 16.,
                proof_work_limit: None,
            },
            2,
        )
        .unwrap();
        let source = ProofContext::new(
            &p,
            &t,
            &["rail".into(), "$abstime".into()],
            Work::limited([128, 8192, limit]),
        )
        .unwrap();
        (p, t, source)
    }

    #[test]
    fn held_ramp_naturally_exhausts_shared_work_and_refuses_both_retries() {
        let (p, _, source) = ramp_fixture(500_000, false);
        let first = DcProjection::with_source(&p, source.clone()).unwrap();
        assert!(first.is_held_ramp());
        assert!(first.source.borrow_work().same_owner(source.borrow_work()));
        assert!(first.view(&p.contributions[0].rhs).is_ok());
        // Each actual physical DC proof costs 400k plus audited structure.
        // A second preparation naturally exhausts this same 500k ledger.
        assert_eq!(
            DcProjection::with_source(&p, source.clone())
                .err()
                .unwrap()
                .kind,
            "step_budget"
        );
        for _ in 0..2 {
            assert_eq!(
                DcProjection::with_source(&p, source.clone())
                    .err()
                    .unwrap()
                    .kind,
                "step_budget"
            );
            assert_eq!(
                first.view(&p.contributions[0].rhs).err().unwrap().kind,
                "step_budget"
            );
        }
    }

    #[test]
    fn held_ramp_rejects_a_different_original_program_with_the_same_source_owner() {
        let (mut p, _, source) = ramp_fixture(1_000_000_000, false);
        p.states[0].initial = 1.0.into();
        let error = DcProjection::with_source(&p, source).err().unwrap();
        assert_eq!(error.kind, "invalid_ir");
        assert!(error.message.contains("different original binding"));
    }

    #[test]
    fn held_ramp_audits_original_unknown_source_even_at_zero_weight() {
        let (p, _, source) = ramp_fixture(1_000_000_000, true);
        let error = DcProjection::with_source(&p, source).err().unwrap();
        assert_eq!(error.kind, "unsupported_operator");
        assert!(error.message.contains("original driven nodes"));
    }

    #[test]
    fn held_ramp_rejects_foreign_state_even_with_a_matching_original_binding() {
        let (mut p, t, _) = ramp_fixture(1_000_000_000, false);
        p.states[0].instance = "foreign".into();
        let source =
            ProofContext::new(&p, &t, &["rail".into(), "$abstime".into()], Work::default())
                .unwrap();
        let error = DcProjection::with_source(&p, source).err().unwrap();
        assert_eq!(error.kind, "invalid_ir");
        assert!(error.message.contains("belong to its instance"));
    }

    #[test]
    fn held_ramp_long_owner_comparison_exhausts_its_actual_work_before_reading() {
        let (mut p, t, _) = ramp_fixture(1_000_000_000, false);
        let owner = "d".repeat(1024);
        p.states[0].instance = owner.clone();
        let source = ProofContext::new(
            &p,
            &t,
            &["rail".into(), "$abstime".into()],
            Work::limited([128, 8192, 32]),
        )
        .unwrap();
        // Isolate the new proof's comparison from the earlier complete binding
        // serializer. One node visit fits; the actual long comparison does not.
        let error =
            DcProjection::held_time(&E::State { state: 0 }, &p, &owner, &source).unwrap_err();
        assert_eq!(error.kind, "step_budget");
        assert!(source.borrow_work().spent() > 32);
        for _ in 0..2 {
            assert_eq!(
                DcProjection::held_time(&E::State { state: 0 }, &p, &owner, &source)
                    .unwrap_err()
                    .kind,
                "step_budget"
            );
        }
    }

    #[test]
    fn held_ramp_canonical_branch_sign_keeps_the_same_physical_ramp() {
        for reversed in [false, true] {
            let (mut p, t, _) = ramp_fixture(1_000_000_000, false);
            if reversed {
                let c = &mut p.contributions[0];
                std::mem::swap(&mut c.positive, &mut c.negative);
                std::mem::swap(&mut c.branch.local_positive, &mut c.branch.local_negative);
                c.rhs = E::Multiply {
                    left: Box::new(E::Affine {
                        constant: -1.,
                        terms: vec![],
                    }),
                    right: Box::new(c.rhs.clone()),
                };
            }
            assert!(DcProjection::held_ramp_candidate(&p));
            let source =
                ProofContext::new(&p, &t, &["rail".into(), "$abstime".into()], Work::default())
                    .unwrap();
            let projection = DcProjection::with_source(&p, source).unwrap();
            let view = projection.view(&p.contributions[0].rhs).unwrap();
            let row = crate::events::affine(view, &p, "d").unwrap();
            let orientation = if reversed { -1. } else { 1. };
            // V(y)=time-epoch independently in either branch direction.
            assert_eq!(orientation * row.nodes[2], 1.);
            assert_eq!(orientation * row.states[0], -1.);
            assert_eq!(row.constant, 0.);
        }
    }

    #[test]
    fn held_ramp_constant_division_wrapper_does_not_hide_the_candidate() {
        let (mut p, t, _) = ramp_fixture(1_000_000_000, false);
        p.contributions[0].rhs = E::Divide {
            left: Box::new(p.contributions[0].rhs.clone()),
            right: Box::new(E::Affine {
                constant: 8.,
                terms: vec![],
            }),
        };
        assert!(DcProjection::held_ramp_candidate(&p));
        let source =
            ProofContext::new(&p, &t, &["rail".into(), "$abstime".into()], Work::default())
                .unwrap();
        let projection = DcProjection::with_source(&p, source).unwrap();
        let row = crate::events::affine(projection.view(&p.contributions[0].rhs).unwrap(), &p, "d")
            .unwrap();
        assert_eq!(row.nodes[2], 0.125);
        assert_eq!(row.states[0], -0.125);
    }

    #[test]
    fn held_ramp_dispatch_hint_has_one_total_branch_visit_allowance() {
        let (mut p, _, _) = ramp_fixture(1_000_000_000, false);
        let target = p.contributions[0].rhs.clone();
        let mut prefix = E::Affine {
            constant: 0.,
            terms: vec![],
        };
        for _ in 0..32 {
            prefix = E::Add {
                left: Box::new(prefix),
                right: Box::new(E::Affine {
                    constant: 0.,
                    terms: vec![],
                }),
            };
        }
        p.contributions[0].rhs = E::Add {
            left: Box::new(prefix),
            right: Box::new(target),
        };
        assert!(!DcProjection::held_ramp_candidate(&p));
    }

    #[test]
    fn held_ramp_does_not_create_a_new_default_work_owner() {
        let (p, t, _) = ramp_fixture(1_000_000_000, false);
        let error = DcProjection::new(&p, &t, &["rail".into(), "$abstime".into()])
            .err()
            .unwrap();
        assert_eq!(error.kind, "invalid_ir");
        assert!(error.message.contains("original prepared source context"));
    }

    fn mixed_fixture(limit: u64) -> (Program, Trajectory, Arc<ProofContext>) {
        let (mut p, t, _) = ramp_fixture(limit, false);
        p.nodes.push("guard".into());
        p.operators.push(
            serde_json::from_value(serde_json::json!({
                "kind":"transition","input":{"op":"state","state":0},
                "delay":0,"rise":0.25,"fall":0.25,
                "origin":{"source":"dc-ramp-mixed.va","line":1,"column":1,"instance":"d"}
            }))
            .unwrap(),
        );
        let mut guard = p.contributions[0].clone();
        guard.positive = p.nodes.len() - 1;
        guard.branch.local_positive = "guard".into();
        guard.rhs = E::Multiply {
            left: Box::new(E::Affine {
                constant: 0.,
                terms: vec![crate::ir::Term {
                    node: 1,
                    coefficient: 1.,
                }],
            }),
            right: Box::new(E::Operator { operator: 0 }),
        };
        p.contributions.push(guard);
        let source = ProofContext::new(
            &p,
            &t,
            &["rail".into(), "$abstime".into()],
            Work::limited([128, 8192, limit]),
        )
        .unwrap();
        (p, t, source)
    }

    #[test]
    fn mixed_held_ramp_keeps_transition_and_time_state_as_distinct_columns() {
        let (p, _, source) = mixed_fixture(1_000_000_000);
        assert!(DcProjection::held_ramp_candidate(&p));
        let view = DcProjection::with_source(&p, source.clone()).unwrap();
        assert!(view.is_held_ramp());
        assert!(view.source.borrow_work().same_owner(source.borrow_work()));
        let phase =
            crate::events::affine(view.view(&p.contributions[0].rhs).unwrap(), &p, "d").unwrap();
        let guard =
            crate::events::affine(view.view(&p.contributions[1].rhs).unwrap(), &p, "d").unwrap();
        // Independent relations: phase=time-epoch; guard=Transition output.
        assert_eq!(phase.nodes[2], 1.);
        assert_eq!(phase.states[0], -1.);
        assert_eq!(phase.value_with(&[0., 1., 4.], &[1.], &[0.]).unwrap(), 3.);
        assert_eq!(phase.value_with(&[0., 1., 4.], &[1.], &[0.75]).unwrap(), 3.);
        assert_eq!(
            guard.value_with(&[0., 1., 4.], &[1.], &[0.25]).unwrap(),
            0.25
        );
        assert!(guard.states.iter().all(|&x| x == 0.));
        assert_eq!(guard.nodes[2], 0.);
    }

    #[test]
    fn mixed_held_ramp_pure_transition_with_time_metadata_stays_legacy() {
        let (mut p, t, _) = mixed_fixture(1_000_000_000);
        p.contributions.remove(0);
        assert!(!DcProjection::held_ramp_candidate(&p));
        // Legacy Transition DC projection may still construct its original
        // owner. Only an actual time×held-state output needs prepared context.
        let view = DcProjection::new(&p, &t, &["rail".into(), "$abstime".into()]).unwrap();
        assert!(!view.is_held_ramp());
        let guard =
            crate::events::affine(view.view(&p.contributions[0].rhs).unwrap(), &p, "d").unwrap();
        assert_eq!(
            guard.value_with(&[0., 1., 4.], &[1.], &[0.25]).unwrap(),
            0.25
        );
        assert_eq!(
            guard.value_with(&[0., 1., 4.], &[1.], &[0.75]).unwrap(),
            0.75
        );
    }

    #[test]
    fn mixed_held_ramp_rejects_foreign_transition_leaf_with_matching_binding() {
        let (mut p, t, _) = mixed_fixture(1_000_000_000);
        if let crate::ir::OperatorSpec::Transition { input, origin, .. } = &mut p.operators[0] {
            origin.instance = "foreign".into();
            *input = E::Affine {
                constant: 0.,
                terms: vec![],
            };
        }
        let source =
            ProofContext::new(&p, &t, &["rail".into(), "$abstime".into()], Work::default())
                .unwrap();
        let error = DcProjection::with_source(&p, source).err().unwrap();
        assert_eq!(error.kind, "invalid_ir");
        assert!(
            error.message.contains("belong to its instance")
                || error.message.contains("original instance")
        );
    }

    #[test]
    fn mixed_held_ramp_audits_foreign_state_in_unselected_original_target_arm() {
        let (mut p, t, _) = mixed_fixture(1_000_000_000);
        p.states.push(
            serde_json::from_value(
                serde_json::json!({"instance":"foreign","name":"hidden","kind":"real","initial":0}),
            )
            .unwrap(),
        );
        if let crate::ir::OperatorSpec::Transition { input, origin, .. } = &mut p.operators[0] {
            *input = E::Select {
                relation: crate::ir::Relation::Gt,
                left: Box::new(E::Affine {
                    constant: 1.,
                    terms: vec![],
                }),
                right: Box::new(E::Affine {
                    constant: 0.,
                    terms: vec![],
                }),
                then_value: Box::new(E::State { state: 0 }),
                else_value: Box::new(E::State { state: 1 }),
                origin: origin.clone(),
            };
        }
        let source =
            ProofContext::new(&p, &t, &["rail".into(), "$abstime".into()], Work::default())
                .unwrap();
        let error = DcProjection::with_source(&p, source).err().unwrap();
        assert_eq!(error.kind, "invalid_ir");
        assert!(error.message.contains("belong to its instance"));
    }

    #[test]
    fn mixed_held_ramp_does_not_admit_time_times_transition() {
        let (mut p, t, _) = mixed_fixture(1_000_000_000);
        p.contributions[1].rhs = E::Multiply {
            left: Box::new(E::Affine {
                constant: 0.,
                terms: vec![crate::ir::Term {
                    node: 2,
                    coefficient: 1.,
                }],
            }),
            right: Box::new(E::Operator { operator: 0 }),
        };
        assert!(DcProjection::held_ramp_candidate(&p));
        let source =
            ProofContext::new(&p, &t, &["rail".into(), "$abstime".into()], Work::default())
                .unwrap();
        assert_eq!(
            DcProjection::with_source(&p, source).err().unwrap().kind,
            "unsupported_dc_projection"
        );
    }

    #[test]
    fn mixed_held_ramp_two_real_dc_proofs_exhaust_one_owner_without_refund() {
        let (p, _, source) = mixed_fixture(900_000);
        let first = DcProjection::with_source(&p, source.clone()).unwrap();
        assert!(first.view(&p.contributions[0].rhs).is_ok());
        assert!(first.view(&p.contributions[1].rhs).is_ok());
        assert!(first.source.borrow_work().same_owner(source.borrow_work()));
        assert_eq!(
            DcProjection::with_source(&p, source.clone())
                .err()
                .unwrap()
                .kind,
            "step_budget"
        );
        for _ in 0..2 {
            assert_eq!(
                DcProjection::with_source(&p, source.clone())
                    .err()
                    .unwrap()
                    .kind,
                "step_budget"
            );
            assert_eq!(
                first.view(&p.contributions[1].rhs).err().unwrap().kind,
                "step_budget"
            );
        }
    }

    #[test]
    fn scalar_fact_work_is_shared_and_sticky() {
        let (_, _, source, supply) = fixture(650_000);
        assert_eq!(source.exact_dc_affine(&supply, "d").unwrap(), 0.5);
        let retry = source.clone();
        assert_eq!(
            retry.exact_dc_affine(&supply, "d").unwrap_err().kind,
            "step_budget"
        );
        assert_eq!(
            source.exact_dc_affine(&supply, "d").unwrap_err().kind,
            "step_budget"
        );
    }
    #[test]
    fn projected_source_history_rejects_trial_without_mutating_accepted_engine() {
        let (p, t, _, _) = fixture(1_000_000_000);
        let projection = DcProjection::new(&p, &t, &["a".into(), "b".into()]).unwrap();
        let mut accepted = crate::operators::Operators::new_until_with_source_context(
            &p,
            &t,
            &["a".into(), "b".into()],
            &[0.],
            2.,
            &crate::ir::Tolerances::default(),
            Some(projection.source.clone()),
        )
        .unwrap();
        accepted
            .advance(0.25, I::point(0.25), &[1.], &[I::ONE], &[0])
            .unwrap();
        let clean = accepted.clone();
        for _ in 0..2 {
            assert!(accepted
                .evaluation(0.75)
                .unwrap()
                .advanced(I::point(0.75), &[0.], &[I { lo: -1., hi: 1. }], &[0])
                .is_err());
            assert!(accepted.same_reset_history(&clean));
            assert_eq!(accepted.bounds(1.).unwrap(), clean.bounds(1.).unwrap());
        }
        let mut retry = accepted;
        let mut clean = clean;
        for h in [&mut retry, &mut clean] {
            h.advance(0.75, I::point(0.75), &[0.], &[I::ZERO], &[0])
                .unwrap();
        }
        for time in [0.75, 0.875, 1.] {
            assert_eq!(retry.bounds(time).unwrap(), clean.bounds(time).unwrap());
        }
    }
    #[test]
    fn retained_projection_comparison_uses_the_same_exhausted_owner() {
        let (p, _, source, _) = fixture(650_000);
        let projection = DcProjection::with_source(&p, source.clone()).unwrap();
        assert!(projection.view(&p.contributions[0].rhs).is_ok());
        assert_eq!(source.charge(650_000).unwrap_err().kind, "step_budget");
        assert_eq!(
            projection.view(&p.contributions[0].rhs).unwrap_err().kind,
            "step_budget"
        );
        assert_eq!(
            projection.view(&p.contributions[0].rhs).unwrap_err().kind,
            "step_budget"
        );
    }
    fn observation_predicate(p: &Program, relation: crate::ir::Relation) -> E {
        E::Select {
            relation,
            left: Box::new(E::Add {
                left: Box::new(E::Affine {
                    constant: 0.,
                    terms: vec![crate::ir::Term {
                        node: 2,
                        coefficient: 1.,
                    }],
                }),
                right: Box::new(E::Multiply {
                    left: Box::new(E::Affine {
                        constant: -1.,
                        terms: vec![],
                    }),
                    right: Box::new(E::State { state: 0 }),
                }),
            }),
            right: Box::new(E::Affine {
                constant: 0.,
                terms: vec![],
            }),
            then_value: Box::new(E::Affine {
                constant: 11.,
                terms: vec![],
            }),
            else_value: Box::new(E::Affine {
                constant: 22.,
                terms: vec![],
            }),
            origin: p.contributions[0].origin.clone(),
        }
    }
    #[test]
    fn final_observation_exact_epoch_distinguishes_adjacent_point_and_strict_relation() {
        use crate::interval::Interval as I;
        use crate::ir::Relation;
        let (p, t, source) = mixed_fixture(1_000_000_000);
        let view = DcProjection::with_source(&p, source).unwrap();
        let driven = vec!["rail".into(), "$abstime".into()];
        let states = vec![I::point(8.)];
        let epochs = [(0, crate::exact_source::RootTime::point(8.).unwrap())].into();
        let mut nodes = vec![I::ZERO; p.nodes.len()];
        nodes[1] = I::ONE;
        nodes[2] = I {
            lo: 8_f64.next_down(),
            hi: 8_f64.next_up(),
        };
        // Exact rational oracle: at t=8, t-epoch=0; at the adjacent
        // representable time it is strictly positive, even with the same box.
        for (time, relation, expected) in [
            (8., Relation::Lt, 22.),
            (8., Relation::Le, 11.),
            (8_f64.next_up(), Relation::Le, 22.),
            (8_f64.next_up(), Relation::Gt, 11.),
        ] {
            let proof = view
                .observation_proof(&p, &t, &driven, time, &states, &epochs)
                .unwrap()
                .unwrap();
            let exact = |left: &E, right: &E, owner: &str| {
                proof.sign(left, right, owner, &p, &driven, &nodes, &states)
            };
            let result = crate::continuous::resolve_selection_with_source_sign(
                &observation_predicate(&p, relation),
                &p,
                &driven,
                &nodes,
                &states,
                &exact,
            )
            .unwrap();
            assert!(
                matches!(result, E::Affine { constant, terms } if constant == expected && terms.is_empty())
            );
        }
    }
    #[test]
    fn final_observation_missing_or_incompatible_epoch_cannot_seed_from_point_state() {
        use crate::interval::Interval as I;
        let (p, t, source) = mixed_fixture(1_000_000_000);
        let view = DcProjection::with_source(&p, source).unwrap();
        let driven = vec!["rail".into(), "$abstime".into()];
        let states = vec![I::point(8.)];
        let mut nodes = vec![I::ZERO; p.nodes.len()];
        nodes[2] = I {
            lo: 8_f64.next_down(),
            hi: 8_f64.next_up(),
        };
        for epochs in [
            crate::exact_source::TimeProofs::new(),
            [(0, crate::exact_source::RootTime::point(9.).unwrap())].into(),
        ] {
            let proof = view
                .observation_proof(&p, &t, &driven, 8., &states, &epochs)
                .unwrap()
                .unwrap();
            let E::Select { left, right, .. } = observation_predicate(&p, crate::ir::Relation::Lt)
            else {
                unreachable!()
            };
            assert_eq!(
                proof
                    .sign(&left, &right, "d", &p, &driven, &nodes, &states)
                    .unwrap(),
                None
            );
        }
    }
    #[test]
    fn final_observation_rejects_foreign_binding_and_uncontained_time_box() {
        use crate::interval::Interval as I;
        let (p, t, source) = mixed_fixture(1_000_000_000);
        let view = DcProjection::with_source(&p, source).unwrap();
        let driven = vec!["rail".into(), "$abstime".into()];
        let states = vec![I::point(8.)];
        let epochs = [(0, crate::exact_source::RootTime::point(8.).unwrap())].into();
        let proof = view
            .observation_proof(&p, &t, &driven, 8., &states, &epochs)
            .unwrap()
            .unwrap();
        let E::Select { left, right, .. } = observation_predicate(&p, crate::ir::Relation::Lt)
        else {
            unreachable!()
        };
        let mut nodes = vec![I::ZERO; p.nodes.len()];
        nodes[2] = I::point(7.);
        assert_eq!(
            proof
                .sign(&left, &right, "d", &p, &driven, &nodes, &states)
                .unwrap(),
            None
        );
        nodes[2] = I::point(8.);
        assert_eq!(
            proof
                .sign(&left, &right, "foreign", &p, &driven, &nodes, &states)
                .unwrap(),
            None
        );
        assert_eq!(
            proof
                .sign(&left, &right, "d", &p.clone(), &driven, &nodes, &states)
                .unwrap(),
            None
        );
    }
    #[test]
    fn final_observation_does_not_erase_unknown_zero_weight_operand() {
        use crate::interval::Interval as I;
        let (p, t, source) = mixed_fixture(1_000_000_000);
        let view = DcProjection::with_source(&p, source).unwrap();
        let driven = vec!["rail".into(), "$abstime".into()];
        let states = vec![I::point(8.)];
        let epochs = [(0, crate::exact_source::RootTime::point(8.).unwrap())].into();
        let proof = view
            .observation_proof(&p, &t, &driven, 8., &states, &epochs)
            .unwrap()
            .unwrap();
        let mut nodes = vec![I::ZERO; p.nodes.len()];
        nodes[2] = I::point(8.);
        let left = E::Affine {
            constant: 0.,
            terms: vec![
                crate::ir::Term {
                    node: 2,
                    coefficient: 1.,
                },
                crate::ir::Term {
                    node: 4,
                    coefficient: 0.,
                },
            ],
        };
        assert_eq!(
            proof
                .sign(
                    &left,
                    &E::State { state: 0 },
                    "d",
                    &p,
                    &driven,
                    &nodes,
                    &states
                )
                .unwrap(),
            None
        );
    }
    #[test]
    fn final_observation_repeated_proofs_exhaust_original_work_and_retries() {
        use crate::interval::Interval as I;
        let (p, t, source) = mixed_fixture(2_000_000);
        let view = DcProjection::with_source(&p, source.clone()).unwrap();
        let driven = vec!["rail".into(), "$abstime".into()];
        let states = vec![I::point(8.)];
        let epochs = [(0, crate::exact_source::RootTime::point(8.).unwrap())].into();
        let proof = view
            .observation_proof(&p, &t, &driven, 8., &states, &epochs)
            .unwrap()
            .unwrap();
        let E::Select { left, right, .. } = observation_predicate(&p, crate::ir::Relation::Lt)
        else {
            unreachable!()
        };
        let mut nodes = vec![I::ZERO; p.nodes.len()];
        nodes[2] = I::point(8.);
        let mut exhausted = false;
        for _ in 0..10_000 {
            match proof.sign(&left, &right, "d", &p, &driven, &nodes, &states) {
                Ok(value) => assert_eq!(value, Some(0)),
                Err(error) => {
                    assert_eq!(error.kind, "step_budget");
                    exhausted = true;
                    break;
                }
            }
        }
        assert!(exhausted);
        assert!(view.source.borrow_work().same_owner(source.borrow_work()));
        for _ in 0..2 {
            assert_eq!(
                proof
                    .sign(&left, &right, "d", &p, &driven, &nodes, &states)
                    .unwrap_err()
                    .kind,
                "step_budget"
            );
        }
    }
    fn physical_fixture(
        reverse: bool,
    ) -> (crate::events::EventModel, Trajectory, Arc<DcProjection>) {
        let (mut p, t, _) = mixed_fixture(1_000_000_000);
        // Canonical local names; retain the original global orientation/RHS.
        for contribution in &mut p.contributions {
            contribution.branch.local_negative = "zref".into();
        }
        p.states.push(
            serde_json::from_value(serde_json::json!({
                "instance":"d","name":"due","kind":"real","initial":8e-9
            }))
            .unwrap(),
        );
        let mut body = vec![
            serde_json::json!({"kind":"assign","state":0,"rhs":{"op":"state","state":1}}),
            serde_json::json!({"kind":"assign","state":1,"rhs":{"op":"add","left":{"op":"state","state":1},"right":{"op":"affine","constant":8e-9,"terms":[]}}}),
        ];
        if reverse {
            body.reverse();
        }
        p.events.push(serde_json::from_value(serde_json::json!({
            "origin":{"source":"physical-epoch.va","line":1,"column":1,"instance":"d"},
            "trigger":{"kind":"timer","start":0,"period":0,"enabled":true,"time_tolerance":1e-12},
            "body":body
        })).unwrap());
        let driven = vec!["rail".into(), "$abstime".into()];
        let source = ProofContext::new(&p, &t, &driven, Work::default()).unwrap();
        let view = DcProjection::with_source(&p, source.clone()).unwrap();
        let m = crate::events::EventModel::new_with_context(
            p,
            driven,
            crate::ir::Tolerances::default(),
            Some(&t),
            Some(source),
        )
        .unwrap();
        (m, t, view)
    }
    #[test]
    fn physical_epoch_nonbinary_third_root_and_callback_order_are_exact() {
        use crate::interval::Interval as I;
        let period = crate::exact_source::binary(8e-9).unwrap();
        let root = crate::exact_source::history_paid::root(
            &period * num_rational::BigRational::from_integer(3.into()),
        );
        let previous = crate::exact_source::history_paid::root(
            &period * num_rational::BigRational::from_integer(2.into()),
        );
        let window = root.bounds().unwrap();
        assert_ne!(window.lo, window.hi, "third epoch is not a binary64 point");
        for reverse in [false, true] {
            let (m, t, view) = physical_fixture(reverse);
            let before = vec![previous.bounds().unwrap(), window];
            let epochs = [(0, previous.clone()), (1, root.clone())].into();
            let context = view
                .physical_context(&m, &t, &root, window, window.hi, &before, &epochs)
                .unwrap()
                .unwrap();
            let selection = crate::event_conditions::Selection {
                actions: vec![(0, vec![0, 1])],
                ..Default::default()
            };
            let preview = context.prepare(&selection, &[I::ONE, window]).unwrap();
            let physical = context.proof(&preview).unwrap();
            let representative = context.representative_proof(&preview).unwrap();
            let E::Select { left, right, .. } =
                observation_predicate(&m.program, crate::ir::Relation::Lt)
            else {
                unreachable!()
            };
            let mut nodes = vec![I::ZERO; m.program.nodes.len()];
            nodes[1] = I::ONE;
            nodes[2] = window;
            // Before increment: epoch=3P so physical phase=0. Reversed
            // assignment reads incremented due=4P, so physical phase=-P.
            assert_eq!(
                physical
                    .sign(
                        &left,
                        &right,
                        "d",
                        &m.program,
                        &m.driven,
                        &nodes,
                        &preview.states
                    )
                    .unwrap(),
                Some(if reverse { -1 } else { 0 })
            );
            if !reverse {
                assert_eq!(
                    representative
                        .sign(
                            &left,
                            &right,
                            "d",
                            &m.program,
                            &m.driven,
                            &nodes,
                            &preview.states
                        )
                        .unwrap(),
                    Some(1)
                );
                let mut contradiction = preview.states.clone();
                contradiction[0] = I::point(window.hi);
                assert_eq!(
                    physical.validate_states(&contradiction).unwrap_err().kind,
                    "condition_precision"
                );
            }
        }
    }
    #[test]
    fn physical_epoch_lost_before_proof_and_wrong_root_window_refuse() {
        use crate::interval::Interval as I;
        let (m, t, view) = physical_fixture(false);
        let root = crate::exact_source::RootTime::point(8.).unwrap();
        let before = vec![I::ZERO, I::point(8.)];
        let empty = crate::exact_source::TimeProofs::new();
        assert!(view
            .physical_context(&m, &t, &root, I::point(7.), 7., &before, &empty)
            .unwrap()
            .is_none());
        let context = view
            .physical_context(&m, &t, &root, I::point(8.), 8., &before, &empty)
            .unwrap()
            .unwrap();
        let selection = crate::event_conditions::Selection {
            actions: vec![(0, vec![0, 1])],
            ..Default::default()
        };
        let preview = context
            .prepare(&selection, &[I::ONE, I::point(8.)])
            .unwrap();
        assert!(
            !preview.epochs.contains_key(&0),
            "point due is not a timestamp seed"
        );
    }
    #[test]
    fn observation_constructor_rejects_changed_trajectory_and_driven_binding() {
        use crate::interval::Interval as I;
        let (p, mut t, source) = mixed_fixture(1_000_000_000);
        let view = DcProjection::with_source(&p, source).unwrap();
        let driven = vec!["rail".into(), "$abstime".into()];
        let states = vec![I::point(8.)];
        let epochs = [(0, crate::exact_source::RootTime::point(8.).unwrap())].into();
        let wrong = vec!["$abstime".into(), "rail".into()];
        assert_eq!(
            view.observation_proof(&p, &t, &wrong, 8., &states, &epochs)
                .err()
                .unwrap()
                .kind,
            "invalid_ir"
        );
        t.config.pwl[0][1][1] = 2.;
        assert_eq!(
            view.observation_proof(&p, &t, &driven, 8., &states, &epochs)
                .err()
                .unwrap()
                .kind,
            "invalid_ir"
        );
    }
}
