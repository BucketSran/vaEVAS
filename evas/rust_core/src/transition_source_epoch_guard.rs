//! Guard-only source epochs. Numeric target leaves retain the old point gate.
use super::*;
use crate::exact_source::TimeProofs;

struct Guard<'a> {
    spec: &'a Spec,
    states: &'a [I],
    epochs: &'a TimeProofs,
}
impl Guard<'_> {
    fn predicate(&self, e: &Expression) -> Result<(), Error> {
        self.spec.work.step()?;
        match e {
            Expression::Affine { constant, terms } => {
                if !constant.is_finite() {
                    return Err(invalid("epoch guard constant is not finite"));
                }
                for term in terms {
                    self.spec.work.step()?;
                    let name = self
                        .spec
                        .program
                        .nodes
                        .get(term.node)
                        .ok_or_else(|| invalid("epoch guard node missing"))?;
                    self.spec.work.debit(2, (1 + name.len().min(8)) as u64)?;
                    if name != "$abstime" || !term.coefficient.is_finite() {
                        return Err(invalid("epoch guard requires original time input"));
                    }
                    self.spec
                        .work
                        .debit(2, self.spec.input_nodes.len() as u64 + 1)?;
                    let index = self
                        .spec
                        .input_nodes
                        .iter()
                        .position(|&n| n == term.node)
                        .ok_or_else(|| invalid("epoch guard input mapping missing"))?;
                    if self
                        .spec
                        .trajectory
                        .config
                        .pwl_errors_v
                        .as_ref()
                        .and_then(|v| v.get(index))
                        .is_some_and(|v| v.bound() > 0.)
                        || !self
                            .spec
                            .trajectory
                            .original_identity_history(index, &self.spec.work)?
                    {
                        return Err(invalid(
                            "epoch guard needs original zero-error time identity",
                        ));
                    }
                }
            }
            Expression::State { state } => {
                let held = self
                    .spec
                    .program
                    .states
                    .get(*state)
                    .ok_or_else(|| invalid("epoch guard state missing"))?;
                self.spec.work.debit(
                    2,
                    (1 + held.instance.len() + self.spec.owner.len() + self.epochs.len()) as u64,
                )?;
                if held.instance != self.spec.owner || held.kind != crate::ir::StateKind::Real {
                    return Err(invalid("epoch guard state owner mismatch"));
                }
                let epoch = self
                    .epochs
                    .get(state)
                    .ok_or_else(|| invalid("epoch guard timestamp proof missing"))?;
                if epoch
                    .refine_with_work(self.states[*state], &self.spec.work)?
                    .is_none()
                {
                    return Err(invalid("epoch guard timestamp contradicts state box"));
                }
            }
            Expression::Add { left, right } => {
                self.predicate(left)?;
                self.predicate(right)?;
            }
            Expression::Multiply { left, right } => {
                let scalar = |e: &Expression| matches!(e,Expression::Affine { constant,terms } if terms.is_empty() && constant.is_finite());
                self.predicate(left)?;
                self.predicate(right)?;
                if !scalar(left) && !scalar(right) {
                    return Err(invalid("epoch guard multiplication needs literal scale"));
                }
            }
            Expression::Select {
                left,
                right,
                then_value,
                else_value,
                origin,
                ..
            } => {
                self.spec.work.debit(
                    2,
                    (1 + origin.instance.len() + self.spec.owner.len()) as u64,
                )?;
                if origin.instance != self.spec.owner {
                    return Err(invalid("epoch guard branch owner mismatch"));
                }
                for child in [left, right, then_value, else_value] {
                    self.predicate(child)?;
                }
            }
            _ => {
                return Err(invalid(
                    "epoch guard excludes history and unproved arithmetic",
                ))
            }
        }
        Ok(())
    }
    fn target_role(&self, e: &Expression) -> Result<(), Error> {
        self.spec.work.step()?;
        match e {
            Expression::Affine { constant, terms }
                if terms.is_empty() && (*constant == 0. || *constant == 1.) =>
            {
                Ok(())
            }
            Expression::Select {
                left,
                right,
                then_value,
                else_value,
                origin,
                ..
            } => {
                self.spec.work.debit(
                    2,
                    (1 + origin.instance.len() + self.spec.owner.len()) as u64,
                )?;
                if origin.instance != self.spec.owner {
                    return Err(invalid("epoch target branch owner mismatch"));
                }
                self.predicate(left)?;
                self.predicate(right)?;
                self.target_role(then_value)?;
                self.target_role(else_value)
            }
            _ => Err(invalid(
                "epoch source proof only grants held zero/one target leaves",
            )),
        }
    }
    fn guard_tree(&self, left: &Expression, right: &Expression) -> Result<Expression, Error> {
        // The admitted source expression is bounded by original qualification.
        // Pay complete copies, including hidden arms and zero dependencies.
        crate::history_admission::charge_expression_copy(left, &self.spec.work)?;
        crate::history_admission::charge_expression_copy(right, &self.spec.work)?;
        self.spec.work.debit(2, 32)?;
        Ok(Expression::Add {
            left: Box::new(left.clone()),
            right: Box::new(Expression::Multiply {
                left: Box::new(constant(-1.)),
                right: Box::new(right.clone()),
            }),
        })
    }
    fn sign(&self, left: &Expression, right: &Expression, time: &Cut) -> Result<i8, Error> {
        self.spec.work.exact()?; // retain the old exact proof reservation
        let guard = self.guard_tree(left, right)?;
        let curve = self
            .spec
            .trajectory
            .original_guard_curve_history(
                &guard,
                &self.spec.input_nodes,
                self.spec.trajectory.config.stop,
                self.epochs,
                &self.spec.work,
            )?
            .ok_or_else(|| invalid("epoch guard original curve unavailable"))?;
        curve
            .sign_history(&time.exact, &self.spec.work)?
            .ok_or_else(|| invalid("epoch guard exact sign unavailable"))
    }
    fn resolve(&self, e: &Expression, time: &Cut) -> Result<Expression, Error> {
        self.spec.work.step()?;
        Ok(match e {
            Expression::Select {
                relation,
                left,
                right,
                then_value,
                else_value,
                ..
            } => {
                let left = self.resolve(left, time)?;
                let right = self.resolve(right, time)?;
                let sign = self.sign(&left, &right, time)?;
                let yes = match relation {
                    Relation::Lt => sign < 0,
                    Relation::Le => sign <= 0,
                    Relation::Gt => sign > 0,
                    Relation::Ge => sign >= 0,
                };
                return self.resolve(if yes { then_value } else { else_value }, time);
            }
            Expression::Add { left, right } => {
                self.spec.work.debit(
                    2,
                    (2 * std::mem::size_of::<Expression>().div_ceil(std::mem::size_of::<usize>()))
                        as u64,
                )?;
                Expression::Add {
                    left: Box::new(self.resolve(left, time)?),
                    right: Box::new(self.resolve(right, time)?),
                }
            }
            Expression::Multiply { left, right } => {
                self.spec.work.debit(
                    2,
                    (2 * std::mem::size_of::<Expression>().div_ceil(std::mem::size_of::<usize>()))
                        as u64,
                )?;
                Expression::Multiply {
                    left: Box::new(self.resolve(left, time)?),
                    right: Box::new(self.resolve(right, time)?),
                }
            }
            _ => crate::history_admission::copy_expression(e, &self.spec.work)?,
        })
    }
    fn target(&self, time: &Cut) -> Result<Target, Error> {
        let selected = self.resolve(&self.spec.expression, time)?;
        let Expression::Affine {
            constant: value,
            terms,
        } = &selected
        else {
            return Err(invalid("epoch guard target is not a held leaf"));
        };
        if !terms.is_empty() || (*value != 0. && *value != 1.) {
            return Err(invalid("epoch guard target is not zero/one"));
        }
        self.spec.work.debit(
            2,
            ((self.spec.program.nodes.len()
                + self.states.len()
                + self.spec.program.operators.len()
                + 4)
                * 8) as u64,
        )?;
        let affine = crate::events::affine(&selected, &self.spec.program, &self.spec.owner)?;
        // State-free value equality may use the existing cache. Guard/cut
        // proofs above never enter caches keyed only by the raw source tree.
        self.spec.proof_sign(
            &selected,
            &constant(0.),
            None,
            "cannot certify held epoch target",
        )?;
        let mut coefficients = Vec::with_capacity(self.states.len() + 1);
        coefficients.resize(self.states.len(), I::ZERO);
        crate::history_storage::push_vec(&mut coefficients, I::point(*value), &self.spec.work)?;
        Ok(Target {
            value: *value,
            bounds: I::point(*value),
            proof: selected,
            affine,
            coefficients,
        })
    }
    fn collect(
        &self,
        e: &Expression,
        cuts: &mut Vec<RootTime>,
        seen: &mut Vec<Expression>,
    ) -> Result<(), Error> {
        self.spec.work.step()?;
        match e {
            Expression::Select {
                left,
                right,
                then_value,
                else_value,
                ..
            } => {
                for child in [left, right, then_value, else_value] {
                    self.collect(child, cuts, seen)?;
                }
                for left in forms(left, &self.spec.work)? {
                    for right in forms(right, &self.spec.work)? {
                        let guard = self.guard_tree(&left, &right)?;
                        let mut repeated = false;
                        for old in seen.iter() {
                            if crate::history_admission::same_expression_full(
                                old,
                                &guard,
                                &self.spec.work,
                            )? {
                                repeated = true;
                                break;
                            }
                        }
                        if repeated {
                            continue;
                        }
                        self.spec.work.exact()?;
                        let curve = self
                            .spec
                            .trajectory
                            .original_guard_curve_history(
                                &guard,
                                &self.spec.input_nodes,
                                self.spec.trajectory.config.stop,
                                self.epochs,
                                &self.spec.work,
                            )?
                            .ok_or_else(|| invalid("epoch cut original curve unavailable"))?;
                        self.spec.work.exact()?;
                        let mut roots = curve
                            .roots_history(&self.spec.work)?
                            .ok_or_else(|| invalid("epoch cut roots unavailable"))?;
                        self.spec.work.debit(1, roots.len() as u64)?;
                        crate::history_storage::append(cuts, &mut roots, &self.spec.work)?;
                        crate::history_storage::push_vec(seen, guard, &self.spec.work)?;
                    }
                }
            }
            Expression::Add { left, right } | Expression::Multiply { left, right } => {
                self.collect(left, cuts, seen)?;
                self.collect(right, cuts, seen)?;
            }
            _ => (),
        }
        Ok(())
    }
}
impl Plan {
    pub(crate) fn same_epoch_context(
        &self,
        states: &[I],
        epochs: Option<&TimeProofs>,
    ) -> Result<bool, Error> {
        Self::check_states(&self.spec, states)?;
        let Some(key) = &self.epoch_guard else {
            return self.same_context(states);
        };
        let Some(epochs) = epochs else {
            return Ok(false);
        };
        for &state in &self.spec.dependencies {
            self.spec.work.debit(2, (key.len() + 2) as u64)?;
            if states[state] != self.states[state] || !key.contains_key(&state) {
                return Ok(false);
            }
        }
        for (&state, root) in key.iter() {
            self.spec.work.debit(2, (epochs.len() + 2) as u64)?;
            let Some(other) = epochs.get(&state) else {
                return Ok(false);
            };
            if states[state] != self.states[state]
                || root
                    .refine_with_work(states[state], &self.spec.work)?
                    .is_none()
                || root.order_with_work(other, &self.spec.work)? != std::cmp::Ordering::Equal
            {
                return Ok(false);
            }
        }
        Ok(true)
    }
    pub(crate) fn rebind_with_epochs(
        &self,
        states: &[I],
        epochs: Option<&TimeProofs>,
    ) -> Result<Self, Error> {
        Self::check_states(&self.spec, states)?;
        if self.epoch_guard.is_none() {
            // Preserve every old successful interval-held route, with or
            // without an optional timestamp map. Only the precise old point
            // binder refusal can request the narrower new epoch role.
            match self.rebind(states) {
                Ok(plan) => return Ok(plan),
                Err(error)
                    if epochs.is_some()
                        && error.kind == "condition_precision"
                        && error.message
                            == "source-target exact proof needs point held operands" => {}
                Err(error) => return Err(error),
            }
        }
        let epochs = epochs.ok_or_else(|| invalid("source epoch timestamp proofs are required"))?;
        // This bridge belongs only to the already qualified joint DC/ramp
        // request, not every source-selected binary Transition in the engine.
        if !crate::dc_projection::DcProjection::held_ramp_candidate(&self.spec.program) {
            return Err(invalid(
                "source epoch guard requires original joint held-ramp contract",
            ));
        }
        let projection = crate::dc_projection::DcProjection::with_source(
            &self.spec.program,
            self.spec.context.clone(),
        )?;
        if !projection.is_held_ramp() {
            return Err(invalid(
                "source epoch guard requires qualified joint held-ramp contract",
            ));
        }
        self.spec
            .work
            .debit(2, (self.spec.predicate_dependencies.len() * 8 + 16) as u64)?;
        let mut key = TimeProofs::new();
        for &state in &self.spec.predicate_dependencies {
            self.spec.work.debit(2, (epochs.len() + 2) as u64)?;
            let root = epochs
                .get(&state)
                .ok_or_else(|| invalid("source epoch timestamp proof missing"))?;
            if root
                .refine_with_work(states[state], &self.spec.work)?
                .is_none()
            {
                return Err(invalid("source epoch proof outside state enclosure"));
            }
            let copy = root.clone_with_work(&self.spec.work)?;
            crate::event_value_proof::history::insert(&mut key, state, copy, &self.spec.work)?;
        }
        let guard = Guard {
            spec: &self.spec,
            states,
            epochs: &key,
        };
        if self.spec.factor.is_some() {
            return Err(invalid("epoch guards do not grant source slew capability"));
        }
        guard.target_role(&self.spec.expression)?;
        self.spec.work.debit(0, 1)?;
        self.spec.work.debit(1, 2)?;
        let mut paid = crate::exact_source::history_paid::Paid::new(&self.spec.work);
        let begin = paid.binary(0.).map(crate::exact_source::history_paid::root);
        let end = paid
            .binary(self.spec.trajectory.config.stop)
            .map(crate::exact_source::history_paid::root);
        let Some((begin, end)) = paid.finish(begin.zip(end))? else {
            return Err(invalid("epoch endpoint proof unavailable"));
        };
        let mut roots = Vec::new();
        crate::history_storage::push_vec(&mut roots, begin, &self.spec.work)?;
        crate::history_storage::push_vec(&mut roots, end, &self.spec.work)?;
        guard.collect(&self.spec.expression, &mut roots, &mut Vec::new())?;
        // Paid insertion sort/dedup keeps budget errors visible.
        for index in 1..roots.len() {
            let mut j = index;
            while j > 0 {
                if roots[j - 1].order_with_work(&roots[j], &self.spec.work)?
                    != std::cmp::Ordering::Greater
                {
                    break;
                }
                self.spec.work.step()?;
                roots.swap(j - 1, j);
                j -= 1;
            }
        }
        self.spec.work.debit(
            2,
            (roots.len() * std::mem::size_of::<Cut>().div_ceil(std::mem::size_of::<usize>()))
                as u64,
        )?;
        let mut cuts = Vec::with_capacity(roots.len());
        for root in roots {
            if cuts
                .last()
                .map(|last: &Cut| last.exact.order_with_work(&root, &self.spec.work))
                .transpose()?
                .is_some_and(|o| o == std::cmp::Ordering::Equal)
            {
                continue;
            }
            let bounds = root
                .bounds_with_work(&self.spec.work)?
                .ok_or_else(|| invalid("epoch cut enclosure unavailable"))?;
            crate::history_storage::push_vec(
                &mut cuts,
                Cut {
                    time: bounds.hi,
                    bounds,
                    exact: root,
                },
                &self.spec.work,
            )?;
        }
        self.spec
            .work
            .debit(2, (cuts.len() * 16 + states.len() * 2 + 16) as u64)?;
        self.spec.work.debit(
            2,
            (cuts.len().saturating_mul(2).saturating_mul(
                std::mem::size_of::<Target>().div_ceil(std::mem::size_of::<usize>()),
            )) as u64,
        )?;
        let mut points = Vec::with_capacity(cuts.len());
        let mut modes = Vec::with_capacity(cuts.len().saturating_sub(1));
        for cut in &cuts {
            let target = guard.target(cut)?;
            crate::history_storage::push_vec(&mut points, target, &self.spec.work)?;
        }
        for pair in cuts.windows(2) {
            let target = guard.target(&Cut::between(&pair[0], &pair[1], &self.spec.work)?)?;
            crate::history_storage::push_vec(&mut modes, target, &self.spec.work)?;
        }
        for index in 1..cuts.len() - 1 {
            if !points[index].proven_equal(&modes[index - 1], &self.spec)?
                && !points[index].proven_equal(&modes[index], &self.spec)?
            {
                return Err(invalid(
                    "isolated epoch target point or third boundary value",
                ));
            }
        }
        Ok(Self {
            spec: self.spec.clone(),
            states: states.to_vec(),
            cuts: Arc::new(cuts),
            points,
            modes,
            epoch_guard: Some(Arc::new(key)),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    fn fixture() -> (Arc<Spec>, Plan) {
        let origin = json!({"source":"epoch-guard.va","line":1,"column":1,"instance":"d"});
        let raw = json!({"op":"add","left":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]},
            "right":{"op":"multiply","left":{"op":"affine","constant":-1,"terms":[]},"right":{"op":"state","state":0}}});
        let target = json!({"op":"select","relation":"le","left":raw,"right":{"op":"affine","constant":1.5e-9,"terms":[]},
            "then_value":{"op":"affine","constant":1,"terms":[]},"else_value":{"op":"affine","constant":0,"terms":[]},"origin":origin});
        let p:Program=serde_json::from_value(json!({"schema_version":crate::ir::SCHEMA_VERSION,
            "nodes":["0","$abstime","rail","guard","phase"],
            "states":[{"instance":"d","name":"epoch","kind":"real","initial":0}],"events":[],
            "operators":[{"kind":"transition","input":target,"delay":0,"rise":40e-12,"fall":40e-12,"origin":origin}],
            "contributions":[
                {"origin":origin,"branch":{"instance":"d","local_positive":"guard","local_negative":"zref","kind":"voltage"},"positive":3,"negative":0,"rhs":{"op":"operator","operator":0}},
                {"origin":origin,"branch":{"instance":"d","local_positive":"phase","local_negative":"zref","kind":"voltage"},"positive":4,"negative":0,"rhs":{"op":"multiply","left":{"op":"affine","constant":0,"terms":[{"node":2,"coefficient":1}]},"right":raw}}
            ],"step_bounds":[]})).unwrap();
        let t = Trajectory::new(
            crate::ir::TransientInputs {
                analytic_sources: vec![],
                pwl_errors_v: None,
                pwl: vec![vec![[0., 0.], [64e-9, 64e-9]], vec![[0., 1.], [64e-9, 1.]]],
                output_times: vec![0., 64e-9],
                strobetimes: vec![],
                stop: 64e-9,
                max_step: 1e-9,
            },
            2,
        )
        .unwrap();
        let context =
            ProofContext::new(&p, &t, &["$abstime".into(), "rail".into()], Work::default())
                .unwrap();
        let crate::ir::OperatorSpec::Transition { input, .. } = &p.operators[0] else {
            unreachable!()
        };
        let (_, spec) = Spec::transition_with_context(input, context, "d").unwrap();
        let spec = spec.unwrap();
        let plan = Plan::build(spec.clone(), &[I::ZERO]).unwrap();
        (spec, plan)
    }
    fn third_epoch() -> RootTime {
        crate::exact_source::history_paid::root(
            crate::exact_source::binary(8e-9).unwrap()
                * num_rational::BigRational::from_integer(3.into()),
        )
    }
    #[test]
    fn epoch_guard_nonbinary_cuts_and_exact_cache_key() {
        let (spec, old) = fixture();
        let root = third_epoch();
        let bounds = root.bounds().unwrap();
        assert_ne!(bounds.lo, bounds.hi);
        let epochs = [(0, root.clone())].into();
        let plan = old.rebind_with_epochs(&[bounds], Some(&epochs)).unwrap();
        let expected = crate::exact_source::history_paid::root(
            root.rational() + crate::exact_source::binary(1.5e-9).unwrap(),
        );
        assert!(plan
            .cuts
            .iter()
            .any(|cut| cut.exact.order(&expected) == std::cmp::Ordering::Equal));
        assert!(plan.same_epoch_context(&[bounds], Some(&epochs)).unwrap());
        assert!(!plan.same_epoch_context(&[bounds], None).unwrap());
        assert!(plan.rebind(&[bounds]).is_err());
        // Distinct rationals in the same binary box must not reuse this plan.
        let other = crate::exact_source::history_paid::root(
            (root.rational() + crate::exact_source::binary(bounds.hi).unwrap())
                / num_rational::BigRational::from_integer(2.into()),
        );
        assert_ne!(root, other);
        let changed = [(0, other.clone())].into();
        assert!(!plan.same_epoch_context(&[bounds], Some(&changed)).unwrap());
        let other_plan = plan.rebind_with_epochs(&[bounds], Some(&changed)).unwrap();
        let other_cut = crate::exact_source::history_paid::root(
            other.rational() + crate::exact_source::binary(1.5e-9).unwrap(),
        );
        assert!(other_plan
            .cuts
            .iter()
            .any(|cut| cut.exact.order(&other_cut) == std::cmp::Ordering::Equal));
        assert!(!plan.same_proof(&other_plan));
        // The new guard bypasses tree-only shared caches. Constant leaf
        // proofs may still use the old state-free proof cache.
        assert!(Arc::ptr_eq(&plan.spec, &spec));
        let before = Cut::new(root.clone()).unwrap();
        let after = Cut::point(bounds.hi).unwrap();
        let guard = Guard {
            spec: &spec,
            states: &[bounds],
            epochs: &epochs,
        };
        let left = Expression::Add {
            left: Box::new(Expression::Affine {
                constant: 0.,
                terms: vec![crate::ir::Term {
                    node: 1,
                    coefficient: 1.,
                }],
            }),
            right: Box::new(Expression::Multiply {
                left: Box::new(constant(-1.)),
                right: Box::new(Expression::State { state: 0 }),
            }),
        };
        assert_eq!(guard.sign(&left, &constant(0.), &before).unwrap(), 0);
        assert_eq!(guard.sign(&left, &constant(0.), &after).unwrap(), 1);
    }
    #[test]
    fn epoch_guard_missing_mismatch_owner_and_numeric_leaf_refuse() {
        let (spec, old) = fixture();
        let root = third_epoch();
        let bounds = root.bounds().unwrap();
        assert!(old.rebind_with_epochs(&[bounds], None).is_err());
        let empty = TimeProofs::new();
        assert!(old.rebind_with_epochs(&[bounds], Some(&empty)).is_err());
        let bad = [(0, RootTime::point(8.).unwrap())].into();
        assert!(old.rebind_with_epochs(&[bounds], Some(&bad)).is_err());
        let epochs = [(0, root)].into();
        let guard = Guard {
            spec: &spec,
            states: &[bounds],
            epochs: &epochs,
        };
        assert!(
            guard.target_role(&Expression::State { state: 0 }).is_err(),
            "timestamp proof must not grant numeric target leaf"
        );
        let foreign = Expression::Select {
            relation: Relation::Lt,
            left: Box::new(Expression::State { state: 0 }),
            right: Box::new(constant(0.)),
            then_value: Box::new(constant(1.)),
            else_value: Box::new(constant(0.)),
            origin: crate::ir::Origin {
                instance: "foreign".into(),
                ..spec.program.contributions[0].origin.clone()
            },
        };
        assert!(guard.target_role(&foreign).is_err());
        let zero_unknown = Expression::Affine {
            constant: 0.,
            terms: vec![crate::ir::Term {
                node: 3,
                coefficient: 0.,
            }],
        };
        assert!(guard.predicate(&zero_unknown).is_err());
    }
    #[test]
    fn epoch_guard_same_owner_work_exhaustion_retries() {
        let (spec, old) = fixture();
        let root = third_epoch();
        let bounds = root.bounds().unwrap();
        let epochs = [(0, root)].into();
        let mut exhausted = false;
        for _ in 0..1000 {
            match old.rebind_with_epochs(&[bounds], Some(&epochs)) {
                Ok(plan) => assert!(plan.same_epoch_context(&[bounds], Some(&epochs)).unwrap()),
                Err(error) => {
                    assert_eq!(error.kind, "step_budget", "{}", error.message);
                    exhausted = true;
                    break;
                }
            }
        }
        assert!(
            exhausted,
            "actual proof work must exhaust original1e9 owner"
        );
        for _ in 0..2 {
            assert_eq!(
                old.rebind_with_epochs(&[bounds], Some(&epochs))
                    .err()
                    .unwrap()
                    .kind,
                "step_budget"
            );
        }
        assert!(spec.work.same_owner(spec.context.borrow_work()));
    }
    #[test]
    fn epoch_source_new_certificate_requires_explicit_proof_at_prepare_entry() {
        let (spec, _) = fixture();
        let source = crate::transition_source_state::Source::initialized(spec, &[I::ZERO])
            .unwrap()
            .0;
        let pulse = RootTime::point(1.5e-9).unwrap();
        let source = source
            .prepare(1.5e-9, I::point(1.5e-9), &[I::ZERO], Some(&pulse))
            .unwrap()
            .source;
        let root = third_epoch();
        let window = root.bounds().unwrap();
        let epochs = [(0, root.clone())].into();
        let source = source
            .prepare_with_epochs(window.hi, window, &[window], Some(&root), Some(&epochs))
            .unwrap()
            .source;
        assert_eq!(
            source
                .prepare(window.hi, I::point(window.hi), &[window], None)
                .err()
                .unwrap()
                .kind,
            "condition_precision"
        );
        assert!(source
            .prepare_with_epochs(
                window.hi,
                I::point(window.hi),
                &[window],
                None,
                Some(&epochs)
            )
            .is_ok());
    }
}
