//! Pure sampled arithmetic may drive the circuit only when every RHS reads
//! held local state and actual driven inputs. Electrical unknowns stay live in
//! the ordinary affine path; nonlinear same-time voltage feedback is refused.
use crate::event_conditions::Selection;
use crate::events::EventModel;
use crate::interval::Interval as I;
use crate::ir::{Error, EventMathFunction as F, Expression as E, Program};
use std::collections::BTreeSet;

pub(crate) fn classify(
    p: &Program,
    passive: &[bool],
    driven: &[String],
    admission: &crate::event_control::Admission<'_>,
    work: Option<&crate::transition_source_plan::Work>,
    source_bindings: Option<&crate::procedure::DependencySources<'_>>,
) -> Result<Vec<bool>, Error> {
    let driven: BTreeSet<_> = p
        .nodes
        .iter()
        .enumerate()
        .filter_map(|(n, name)| (n == 0 || driven.contains(name)).then_some(n))
        .collect();
    fn input_operand(
        e: &E,
        driven: &BTreeSet<usize>,
        work: Option<&crate::transition_source_plan::Work>,
        sources: Option<&crate::procedure::DependencySources<'_>>,
        active: &mut BTreeSet<usize>,
    ) -> Result<Option<(usize, Option<f64>)>, Error> {
        if let Some(w) = work {
            crate::event_floor::charge(w, 1, "floor_source_qualification_ast")?;
        }
        let result = match e {
            E::Affine { constant, terms } => {
                let mut valid = constant.is_finite();
                for t in terms {
                    if let Some(w) = work {
                        crate::event_floor::charge(w, 1, "floor_source_qualification_terms")?;
                    }
                    if !driven.contains(&t.node)
                        || !t.coefficient.is_finite()
                        || work.is_none() && !crate::event_floor::binary_scale(t.coefficient)
                    {
                        valid = false;
                        break;
                    }
                }
                valid.then_some((
                    usize::from(!terms.is_empty()),
                    terms.is_empty().then_some(*constant),
                ))
            }
            E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
                if work.is_none() && (matches!(e,E::Divide{..}) || matches!(e,E::Multiply{..}) && [left.as_ref(),right.as_ref()].iter().any(|v|matches!(v,E::Affine{constant,terms} if terms.is_empty()&&!crate::event_floor::binary_scale(*constant)))) {return Ok(None);}
                let a = input_operand(left, driven, work, sources, active)?;
                let b = input_operand(right, driven, work, sources, active)?;
                match (a, b) {
                    (Some((ad, av)), Some((bd, bv))) => match e {
                        E::Add { .. } => Some((ad.max(bd), av.zip(bv).map(|(a, b)| a + b))),
                        E::Multiply { .. } if ad + bd <= 1 => {
                            Some((ad + bd, av.zip(bv).map(|(a, b)| a * b)))
                        }
                        E::Divide { .. }
                            if bd == 0 && bv.is_some_and(|b| b.is_finite() && b != 0.) =>
                        {
                            Some((ad, av.zip(bv).map(|(a, b)| a / b)))
                        }
                        _ => None,
                    },
                    _ => None,
                }
            }
            // Qualification follows the original source tree only. The Plan
            // still evaluates every Boundary/Real operation at this occurrence;
            // neither a driven-leaf check nor a closed scalar is a domain proof.
            E::RealBoundary { value, .. } if sources.is_some() => {
                input_operand(value, driven, work, sources, active)?
            }
            E::RealBinary {
                operation,
                left,
                right,
                ..
            } if sources.is_some() => {
                use crate::ir::RealOperation as R;
                use crate::real_rounding::{point, Op};
                let a = input_operand(left, driven, work, sources, active)?;
                let b = input_operand(right, driven, work, sources, active)?;
                match (a, b) {
                    (Some((ad, av)), Some((bd, bv))) => {
                        let degree = match operation {
                            R::Add | R::Subtract => Some(ad.max(bd)),
                            R::Multiply if ad + bd <= 1 => Some(ad + bd),
                            R::Divide
                                if bd == 0 && bv.is_some_and(|v| v.is_finite() && v != 0.) =>
                            {
                                Some(ad)
                            }
                            _ => None,
                        };
                        let op = match operation {
                            R::Add => Op::Add,
                            R::Subtract => Op::Subtract,
                            R::Multiply => Op::Multiply,
                            R::Divide => Op::Divide,
                        };
                        // This is only metadata for a closed denominator. Use
                        // actual per-operation IEEE rounding, never reassociate.
                        let value = av.zip(bv).and_then(|(a, b)| point(op, a, b).ok());
                        degree.and_then(|d| (d != 0 || value.is_some()).then_some((d, value)))
                    }
                    _ => None,
                }
            }
            E::RealLocal { binding } if sources.is_some() => {
                let w =
                    work.ok_or_else(|| Error::new("invalid_ir", "floor source ledger absent"))?;
                // Prepay lookup, BTree path comparison/insertion/removal and
                // storage before touching the set. No fresh Work or allowance.
                let height = (active.len().saturating_add(1)).ilog2() as usize + 2;
                crate::event_floor::charge(
                    w,
                    height.saturating_mul(64).saturating_add(64),
                    "floor_source_binding_path",
                )?;
                if !active.insert(*binding) {
                    return Ok(None);
                }
                let result = (|| {
                    crate::event_floor::charge(w, 2, "floor_source_binding_definition")?;
                    match sources
                        .ok_or_else(|| Error::new("invalid_ir", "floor source index absent"))?
                        .single_binding_value(*binding)?
                    {
                        Some(value) => input_operand(value, driven, work, sources, active),
                        None => Ok(None),
                    }
                })();
                active.remove(binding);
                result?
            }
            E::Power { base, exponent: 1 } => {
                if let Some(w) = work {
                    if crate::event_floor::new_operand_charged(base, w)? {
                        return Ok(None);
                    }
                }
                input_operand(base, driven, work, sources, active)?
            }
            _ => None,
        };
        Ok(result.filter(|(_, value)| value.is_none_or(f64::is_finite)))
    }
    fn audit(
        v: &serde_json::Value,
        driven: &BTreeSet<usize>,
        work: Option<&crate::transition_source_plan::Work>,
        sources: Option<&crate::procedure::DependencySources<'_>>,
    ) -> Result<(), Error> {
        if let Some(w) = work {
            crate::event_floor::charge(w, 1, "floor_source_qualification_ast")?;
        }
        match v {
            serde_json::Value::Object(m) => {
                if m.get("op").and_then(|v| v.as_str()) == Some("integer_round") {
                    if let Some(w) = work {
                        let size = crate::event_floor::encoded_size(v, w)?;
                        crate::event_floor::charge(
                            w,
                            size.saturating_mul(8),
                            "integer_round_qualification_copy",
                        )?;
                    }
                    let expr: E = serde_json::from_value(v.clone())
                        .map_err(|e| Error::new("invalid_ir", e.to_string()))?;
                    if let E::IntegerRound { value, .. } = expr {
                        if input_operand(&value, driven, work, sources, &mut BTreeSet::new())?
                            .is_none()
                        {
                            return Err(Error::new(
                                "unsupported_integer_conversion",
                                "integer conversion requires actual driven inputs",
                            ));
                        }
                    }
                }
                if m.get("op").and_then(|v| v.as_str()) == Some("event_math")
                    && m.get("function").and_then(|v| v.as_str()) == Some("floor")
                {
                    if let Some(w) = work {
                        let size = crate::event_floor::encoded_size(v, w)?;
                        crate::event_floor::charge(
                            w,
                            size.saturating_mul(8),
                            "floor_source_qualification_copy",
                        )?;
                    }
                    let expr: E = serde_json::from_value(v.clone())
                        .map_err(|e| Error::new("invalid_ir", e.to_string()))?;
                    if let E::EventMath {
                        function: F::Floor,
                        args,
                        ..
                    } = expr
                    {
                        if args.len() != 1
                            || input_operand(&args[0], driven, work, sources, &mut BTreeSet::new())?
                                .is_none()
                        {
                            return Err(Error::new(
                                "unsupported_floor",
                                "native event floor requires actual driven affine inputs",
                            ));
                        }
                    }
                }
                for child in m.values() {
                    audit(child, driven, work, sources)?;
                }
            }
            serde_json::Value::Array(a) => {
                for child in a {
                    audit(child, driven, work, sources)?;
                }
            }
            _ => (),
        }
        Ok(())
    }
    fn has_integer(
        v: &serde_json::Value,
        work: Option<&crate::transition_source_plan::Work>,
    ) -> Result<bool, Error> {
        if let Some(w) = work {
            crate::event_floor::charge(w, 1, "floor_source_qualification_scan")?;
        }
        match v {
            serde_json::Value::Object(m) => {
                if m.get("op").and_then(|v| v.as_str()) == Some("integer_primitive") {
                    return Ok(true);
                }
                for child in m.values() {
                    if has_integer(child, work)? {
                        return Ok(true);
                    }
                }
            }
            serde_json::Value::Array(a) => {
                for child in a {
                    if has_integer(child, work)? {
                        return Ok(true);
                    }
                }
            }
            _ => {}
        }
        Ok(false)
    }
    // Physical sampled sqrt/ln belong to events of instances whose state the
    // circuit reads. An isolated observer instance keeps the observer
    // contract, including its non-passive zero-time and initial-step events.
    // Computed only when some event body actually uses sampled sqrt/ln.
    let isolated = std::cell::OnceCell::new();
    p.events.iter().enumerate().map(|(index,e)| {
        let body=if let Some(w)=work {
            let bytes=crate::event_floor::admission_bytes(&e.body,w)?;
            crate::event_floor::charge(w,bytes.len().saturating_mul(32),"floor_source_qualification_copy")?;
            serde_json::from_slice(&bytes).map_err(|e|Error::new("invalid_ir",e.to_string()))?
        } else {serde_json::to_value(&e.body).map_err(|e|Error::new("invalid_ir",e.to_string()))?};
        // Only procedure-backed source events execute these nodes through
        // Plan's complete RN graph. Legacy events keep their old admission.
        audit(&body,&driven,work,if e.procedure_id.is_some(){source_bindings}else{None})?;
        if passive[index] || (!has_integer(&body,work)? && !admission.floor_event(index) && e.assignments().iter().all(|a| crate::events::affine(&a.rhs,p,&e.origin.instance).is_ok())) {
            return Ok(false);
        }
        // Runtime control and checked integer/array nodes keep their isolated
        // observer contract, as does EventMath other than floor anywhere in
        // the original body. The one exception is sqrt/ln in a physical
        // sampled position: an assignment value (outside any decision
        // predicate) of an event whose instance is not an isolated observer.
        // There they prove their domain over the complete sampled argument
        // enclosure in event_numeric::bounds. Predicates, displays and indices
        // keep the older contract. Scan predicates and unselected arms too:
        // an unrelated sampled product must not make observer mathematics
        // legal in a physical event.
        fn control(v:&serde_json::Value,sampled:bool,used:&mut bool,work:Option<&crate::transition_source_plan::Work>,procedure:bool)->Result<bool,Error>{
            if let Some(w)=work {crate::event_floor::charge(w,1,"floor_source_qualification_scan")?;}
            match v {
                serde_json::Value::Object(m)=>{
                    let kind=m.get("kind").and_then(|v|v.as_str());
                    let op=m.get("op").and_then(|v|v.as_str());
                    if !procedure && (kind.is_some_and(|s|matches!(s,"loop"|"array_write")) || op.is_some_and(|s|matches!(s,"array_read"|"checked_integer"|"checked_index"))) {return Ok(true)}
                    if op==Some("event_math") {
                        let function=m.get("function").and_then(|v|v.as_str());
                        if !(function==Some("floor") || sampled&&matches!(function,Some("sqrt"|"ln"))) {return Ok(true)}
                        *used |= function!=Some("floor");
                    }
                    for (key,child) in m {
                        // Only an assignment value starts a sampled position;
                        // expression operands inherit it except a decision's
                        // predicate. Statements never inherit it.
                        let inherit=match (kind,op) {
                            (Some("assign"),_) => key=="rhs",
                            (_,Some("select")) => sampled&&matches!(key.as_str(),"then_value"|"else_value"),
                            (None,Some(_)) => sampled,
                            _ => false,
                        };
                        if control(child,inherit,used,work,procedure)?{return Ok(true)}
                    }
                },
                serde_json::Value::Array(a)=>{for child in a {if control(child,sampled,used,work,procedure)?{return Ok(true)}}},
                _=>{}
            }
            Ok(false)
        }
        // An isolated observer instance never has a physical sampled position.
        let mut used=false;
        if control(&body,false,&mut used,work,e.procedure_id.is_some())?
            || used && isolated.get_or_init(|| crate::passive_events::isolated_instances(p)).contains(&e.origin.instance) {
            return Err(Error::new("unsupported_transient","observer mathematics and control nodes require an isolated observer event"));
        }
        for a in e.assignments() {
            let d=if let Some(sources)=source_bindings{crate::procedure::source_dependencies(&a.rhs,p,sources,work.ok_or_else(||Error::new("invalid_ir","source dependency ledger absent"))?)?}else{crate::event_numeric::dependencies(&a.rhs,p,&e.origin.instance)?};
            let operator_supported=d.operator_dependencies.is_empty() || (
                e.procedure_id.is_some() && d.operator_dependencies.iter().all(|&i|matches!(p.operators.get(i),Some(crate::ir::OperatorSpec::Math{..}|crate::ir::OperatorSpec::Sin{..})))
            );
            if !operator_supported || !(
                (e.procedure_id.is_some() && e.assignments().iter().all(|a|!crate::event_numeric::contains_legacy_math(&a.rhs)))
                || d.node_dependencies.is_subset(&driven)
            ) {
                return Err(Error::new("unsupported_transient","nonlinear sampled arithmetic requires state-independent driven voltage inputs"));
            }
        }
        Ok(true)
    }).collect()
}

pub(crate) fn input_nodes(model: &EventModel, inputs: &[I]) -> Vec<I> {
    let mut nodes = vec![
        I {
            lo: f64::NEG_INFINITY,
            hi: f64::INFINITY
        };
        model.program.nodes.len()
    ];
    nodes[0] = I::ZERO;
    for (name, &v) in model.driven.iter().zip(inputs) {
        nodes[model.program.nodes.iter().position(|n| n == name).unwrap()] = v;
    }
    nodes
}

type StateVoltageBounds = (Vec<I>, Vec<I>);

/// Same-time value of an internal node forced, through acyclic independent
/// grounded branches, only by driven inputs, states not assigned in this batch
/// and positive-edge Transition outputs. Such a Transition is continuous at the
/// event time, so its observed output does not depend on new batch targets.
/// Anything else stays a joint voltage assignment (None).
fn continuous_provider(
    model: &EventModel,
    node: usize,
    nodes: &[I],
    states: &[I],
    operators: &[I],
    assigned: &BTreeSet<usize>,
) -> Result<Option<I>, Error> {
    independent_voltage_bounds(
        &model.program,
        &model.driven,
        node,
        nodes,
        states,
        operators,
        assigned,
        None,
    )
}

/// The same acyclic continuous provider, available before a procedure chooses
/// a branch. Assigned-state loops remain unknown; no trial solution is used.
#[allow(clippy::too_many_arguments)]
pub(crate) fn independent_voltage_bounds(
    p: &Program,
    driven: &[String],
    node: usize,
    nodes: &[I],
    states: &[I],
    operators: &[I],
    assigned: &BTreeSet<usize>,
    work: Option<&crate::transition_source_plan::Work>,
) -> Result<Option<I>, Error> {
    if let Some(w) = work {
        if !crate::procedure::unconditional_contributions(p, w)? {
            return Ok(None);
        }
    }
    let probe = E::Affine {
        constant: 0.,
        terms: vec![crate::ir::Term {
            node,
            coefficient: 1.,
        }],
    };
    let expanded = match work {
        Some(w) => crate::causal_voltage::expand_paid(&probe, p, driven, w),
        None => crate::causal_voltage::expand(&probe, p, driven),
    };
    let expanded = match expanded {
        Ok(value) => value,
        Err(error) if error.kind == "unsupported_condition" => return Ok(None),
        Err(error) => return Err(error),
    };
    if let Some(w) = work {
        let bytes = crate::event_floor::encoded_size(&expanded, w)?;
        w.debit(2, (bytes as u64).saturating_mul(8))?;
    }
    // `expand` returns only affine leaves, State, Operator and arithmetic or
    // Select over them; every leaf, including zero weights and unselected
    // arms, must satisfy the provider rule.
    fn admitted(
        e: &E,
        p: &Program,
        nodes: &[I],
        operators: &[I],
        assigned: &BTreeSet<usize>,
    ) -> bool {
        let go = |e: &E| admitted(e, p, nodes, operators, assigned);
        match e {
            E::Affine { terms, .. } => terms.iter().all(|t| nodes[t.node].finite()),
            E::State { state } => !assigned.contains(state),
            E::Operator { operator } => {
                *operator < operators.len()
                    && matches!(
                        p.operators.get(*operator),
                        Some(crate::ir::OperatorSpec::Transition { rise, fall, .. })
                            if *rise > 0. && *fall > 0.
                    )
            }
            E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
                go(left) && go(right)
            }
            E::Select {
                left,
                right,
                then_value,
                else_value,
                ..
            } => go(left) && go(right) && go(then_value) && go(else_value),
            _ => false,
        }
    }
    if !admitted(&expanded, p, nodes, operators, assigned) {
        return Ok(None);
    }
    crate::causal_voltage::bounds(&expanded, nodes, states, operators).map(Some)
}

/// Rebuild the same pre-activation proof domains during selection and final
/// parameter certification. Solved nominal voltages are never proof inputs.
#[allow(clippy::too_many_arguments)]
pub(crate) fn fill_independent_pre_event_nodes(
    p: &Program,
    driven: &[String],
    fired: &[usize],
    nodes: &mut [I],
    before: &[I],
    operators: &[I],
    w: &crate::transition_source_plan::Work,
) -> Result<bool, Error> {
    if fired.is_empty() {
        return Ok(false);
    }
    w.debit(
        2,
        ((p.states.len() + p.nodes.len() + driven.len()) * 64 + 64) as u64,
    )?;
    let assigned = crate::procedure::activation_writes(p, fired, w)?;
    let mut provided = false;
    for node in 1..nodes.len() {
        w.step()?;
        if !nodes[node].finite() {
            if let Some(band) = independent_voltage_bounds(
                p,
                driven,
                node,
                nodes,
                before,
                operators,
                &assigned,
                Some(w),
            )? {
                nodes[node] = band;
                provided = true;
            }
        }
    }
    Ok(provided)
}

#[allow(clippy::too_many_arguments)]
pub(crate) fn certificate(
    model: &EventModel,
    selection: &Selection,
    selected: &Program,
    fired: &[usize],
    inputs: &[I],
    before: &[I],
    operators: &[I],
    voltages: &[f64],
    states: &[f64],
    check_voltages: bool,
    proofs: Option<&crate::event_value_proof::Context<'_>>,
) -> Result<Option<StateVoltageBounds>, Error> {
    if let Some(plan) = &selection.plan {
        if !plan.has_observation() && !check_voltages {
            let nodes = input_nodes(model, inputs);
            return Ok(Some((
                plan.state_bounds(&nodes, before, proofs, crate::real_expression::work(model))?,
                Vec::new(),
            )));
        }
        let (bounds, nodes) = plan.certificate(
            &model.program,
            &model.driven,
            model.tolerances.clone(),
            inputs,
            before,
            operators,
            voltages,
            states,
            proofs,
            crate::real_expression::work(model),
        )?;
        return Ok(Some((
            bounds,
            if check_voltages { nodes } else { Vec::new() },
        )));
    }
    if !selection
        .actions
        .iter()
        .any(|(e, _)| model.causal_numeric[*e])
    {
        return Ok(None);
    }
    let mut nodes = input_nodes(model, inputs);
    let assigned: BTreeSet<usize> = selection
        .actions
        .iter()
        .filter(|(event, _)| !model.passive_events[*event])
        .flat_map(|(event, indices)| {
            let assignments = model.program.events[*event].assignments();
            indices
                .iter()
                .filter_map(move |&index| assignments.get(index).map(|a| a.state))
                .collect::<Vec<_>>()
        })
        .collect();
    let mut after = before.to_vec();
    let mut frames =
        crate::procedure_frames::Frames::new(selection, proofs.and_then(|p| p.execution_work()))?;
    for (event, indices) in &selection.actions {
        if model.passive_events[*event] {
            continue;
        }
        let mut local = match frames.take(*event) {
            Some(v) => v,
            None => crate::event_value_proof::LocalState::try_with_context(before, proofs)?,
        };
        for &index in indices {
            let expression = &model.action_expressions[*event][index];
            let dependencies = crate::event_numeric::dependencies(
                expression,
                &model.program,
                &model.program.events[*event].origin.instance,
            )?;
            if dependencies.operator_dependencies.is_empty() {
                for &n in &dependencies.node_dependencies {
                    if !nodes[n].finite() {
                        if let Some(bounds) =
                            continuous_provider(model, n, &nodes, before, operators, &assigned)?
                        {
                            nodes[n] = bounds;
                        }
                    }
                }
            }
            if !dependencies.operator_dependencies.is_empty()
                || dependencies
                    .node_dependencies
                    .iter()
                    .any(|&n| !nodes[n].finite())
            {
                return Err(Error::new(
                    "unsupported_cross",
                    "nonlinear sampled batch cannot include a joint voltage assignment",
                ));
            }
            let value = crate::event_numeric::bounds_with_proofs(expression, &nodes, &local)?;
            let state = model.program.events[*event].assignments()[index].state;
            local.try_assign(state, expression, &nodes, value)?;
            after[state] = local[state];
        }
        frames.put(*event, local);
    }
    // State transfer was certified from the original expression trees above.
    // Project the voltage equations with those new state boxes as forcing;
    // never substitute dependency-only placeholders for nonlinear assignments.
    let map = crate::settlement_bounds::Bounds::for_program_with_operators(
        model,
        &Selection::default(),
        selected,
        operators,
    )?;
    let result = if check_voltages {
        map.check_observation(model, inputs, &after, operators, voltages, states)?
    } else {
        (
            map.check_states(model, inputs, &after, operators, voltages, states)?,
            Vec::new(),
        )
    };
    let replay = model.selected_program_with_parameters(&result.0, inputs, fired, operators)?;
    if replay
        .contributions
        .iter()
        .zip(&selected.contributions)
        .any(|(a, b)| a.rhs != b.rhs)
    {
        return Err(Error::new(
            "event_condition",
            "causal state enclosure changes contribution selection",
        ));
    }
    Ok(Some(result))
}

#[cfg(test)]
#[path = "causal_event_floor_rn_tests.rs"]
mod floor_rn_tests;
