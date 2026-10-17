//! Pure sampled arithmetic may drive the circuit only when every RHS reads
//! held local state and actual driven inputs. Electrical unknowns stay live in
//! the ordinary affine path; nonlinear same-time voltage feedback is refused.
use crate::event_conditions::Selection;
use crate::events::EventModel;
use crate::interval::Interval as I;
use crate::ir::{Error, Program};
use std::collections::BTreeSet;

pub(crate) fn classify(
    p: &Program,
    passive: &[bool],
    driven: &[String],
) -> Result<Vec<bool>, Error> {
    let driven: BTreeSet<_> = p
        .nodes
        .iter()
        .enumerate()
        .filter_map(|(n, name)| (n == 0 || driven.contains(name)).then_some(n))
        .collect();
    p.events.iter().enumerate().map(|(index,e)| {
        if passive[index] || e.assignments().iter().all(|a| crate::events::affine(&a.rhs,p,&e.origin.instance).is_ok()) {
            return Ok(false);
        }
        // Runtime control and checked integer/array nodes keep their isolated
        // observer contract, as does EventMath anywhere in the original body.
        // Scan predicates and unselected arms too: an unrelated sampled product
        // must not make observer mathematics legal in a physical event.
        fn control(v: &serde_json::Value) -> bool {
            match v {
                serde_json::Value::Object(m) => m.get("kind").and_then(|v|v.as_str()).is_some_and(|s|matches!(s,"loop"|"array_write"))
                    || m.get("op").and_then(|v|v.as_str()).is_some_and(|s|matches!(s,"event_math"|"array_read"|"checked_integer"|"checked_index"))
                    || m.values().any(control),
                serde_json::Value::Array(a) => a.iter().any(control), _=>false,
            }
        }
        if control(&serde_json::to_value(&e.body).map_err(|e|Error::new("invalid_ir",e.to_string()))?) {
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
        let mut local = crate::event_value_proof::LocalState::new(before);
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
            let value = crate::event_numeric::bounds(expression, &nodes, &local)?;
            let state = model.program.events[*event].assignments()[index].state;
            local.assign(state, expression, &nodes, value);
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
