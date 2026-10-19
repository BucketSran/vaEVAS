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
                let a = input_operand(left, driven, work)?;
                let b = input_operand(right, driven, work)?;
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
            E::Power { base, exponent: 1 } => {
                if let Some(w) = work {
                    if crate::event_floor::new_operand_charged(base, w)? {
                        return Ok(None);
                    }
                }
                input_operand(base, driven, work)?
            }
            _ => None,
        };
        Ok(result.filter(|(_, value)| value.is_none_or(f64::is_finite)))
    }
    fn audit(
        v: &serde_json::Value,
        driven: &BTreeSet<usize>,
        work: Option<&crate::transition_source_plan::Work>,
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
                        if input_operand(&value, driven, work)?.is_none() {
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
                        if args.len() != 1 || input_operand(&args[0], driven, work)?.is_none() {
                            return Err(Error::new(
                                "unsupported_floor",
                                "native event floor requires actual driven affine inputs",
                            ));
                        }
                    }
                }
                for child in m.values() {
                    audit(child, driven, work)?;
                }
            }
            serde_json::Value::Array(a) => {
                for child in a {
                    audit(child, driven, work)?;
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
    p.events.iter().enumerate().map(|(index,e)| {
        let body=if let Some(w)=work {
            let bytes=crate::event_floor::admission_bytes(&e.body,w)?;
            crate::event_floor::charge(w,bytes.len().saturating_mul(32),"floor_source_qualification_copy")?;
            serde_json::from_slice(&bytes).map_err(|e|Error::new("invalid_ir",e.to_string()))?
        } else {serde_json::to_value(&e.body).map_err(|e|Error::new("invalid_ir",e.to_string()))?};
        audit(&body,&driven,work)?;
        if passive[index] || (!has_integer(&body,work)? && !admission.floor_event(index) && e.assignments().iter().all(|a| crate::events::affine(&a.rhs,p,&e.origin.instance).is_ok())) {
            return Ok(false);
        }
        // Runtime control and checked integer/array nodes keep their isolated
        // observer contract, as does EventMath anywhere in the original body.
        // Scan predicates and unselected arms too: an unrelated sampled product
        // must not make observer mathematics legal in a physical event.
        fn control(v:&serde_json::Value,work:Option<&crate::transition_source_plan::Work>)->Result<bool,Error>{
            if let Some(w)=work {crate::event_floor::charge(w,1,"floor_source_qualification_scan")?;}
            match v {
                serde_json::Value::Object(m)=>{
                    if m.get("kind").and_then(|v|v.as_str()).is_some_and(|s|matches!(s,"loop"|"array_write")) || m.get("op").and_then(|v|v.as_str()).is_some_and(|s|matches!(s,"array_read"|"checked_integer"|"checked_index")||s=="event_math"&&m.get("function").and_then(|v|v.as_str())!=Some("floor")){return Ok(true)}
                    for child in m.values(){if control(child,work)?{return Ok(true)}}
                },
                serde_json::Value::Array(a)=>{for child in a {if control(child,work)?{return Ok(true)}}},
                _=>{}
            }
            Ok(false)
        }
        if control(&body,work)? {
            return Err(Error::new("unsupported_transient","observer mathematics and control nodes require an isolated observer event"));
        }
        for a in e.assignments() {
            let d=crate::event_numeric::dependencies(&a.rhs,p,&e.origin.instance)?;
            if !d.operator_dependencies.is_empty() || !d.node_dependencies.is_subset(&driven) {
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
    if !selection
        .actions
        .iter()
        .any(|(e, _)| model.causal_numeric[*e])
    {
        return Ok(None);
    }
    let nodes = input_nodes(model, inputs);
    let mut after = before.to_vec();
    for (event, indices) in &selection.actions {
        if model.passive_events[*event] {
            continue;
        }
        let mut local = crate::event_value_proof::LocalState::try_with_context(before, proofs)?;
        for &index in indices {
            let expression = &model.action_expressions[*event][index];
            let dependencies = crate::event_numeric::dependencies(
                expression,
                &model.program,
                &model.program.events[*event].origin.instance,
            )?;
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
