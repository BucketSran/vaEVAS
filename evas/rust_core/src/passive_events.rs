//! A structurally isolated observer reads a certified physical event sample.
//! It owns no voltage equation, operator history or physical step control.
use crate::event_conditions::Selection;
use crate::events::EventModel;
use crate::interval::Interval as I;
use crate::ir::{Error, EventTrigger, Program, StateKind};
use std::collections::BTreeSet;

fn state_reads(value: &serde_json::Value, out: &mut BTreeSet<usize>) {
    match value {
        serde_json::Value::Object(fields) => {
            if fields.get("op").and_then(|v| v.as_str()) == Some("state") {
                if let Some(index) = fields.get("state").and_then(|v| v.as_u64()) {
                    out.insert(index as usize);
                }
            }
            for child in fields.values() {
                state_reads(child, out);
            }
        }
        serde_json::Value::Array(items) => {
            for child in items {
                state_reads(child, out);
            }
        }
        _ => {}
    }
}

pub(crate) fn isolated_instances(program: &Program) -> BTreeSet<String> {
    let mut owners: BTreeSet<_> = program
        .events
        .iter()
        .map(|e| e.origin.instance.clone())
        .collect();
    for contribution in &program.contributions {
        owners.remove(&contribution.origin.instance);
        owners.remove(&contribution.branch.instance);
    }
    for operator in &program.operators {
        owners.remove(&operator.origin().instance);
    }
    for bound in &program.step_bounds {
        owners.remove(&bound.origin.instance);
    }
    // Scan original serialized IR trees, including every arm and explicit zero
    // reference. Never infer isolation from the current mode or eliminated rows.
    owners.retain(|owner| {
        let owned: BTreeSet<_> = program
            .states
            .iter()
            .enumerate()
            .filter_map(|(i, s)| (&s.instance == owner).then_some(i))
            .collect();
        let mut read = BTreeSet::new();
        for contribution in &program.contributions {
            state_reads(
                &serde_json::to_value(contribution).expect("IR serialization"),
                &mut read,
            );
        }
        for operator in &program.operators {
            state_reads(
                &serde_json::to_value(operator).expect("IR serialization"),
                &mut read,
            );
        }
        for bound in &program.step_bounds {
            state_reads(
                &serde_json::to_value(bound).expect("IR serialization"),
                &mut read,
            );
        }
        for state in &program.states {
            if &state.instance != owner {
                state_reads(
                    &serde_json::to_value(state).expect("IR serialization"),
                    &mut read,
                );
            }
        }
        for event in &program.events {
            if &event.origin.instance != owner {
                state_reads(
                    &serde_json::to_value(event).expect("IR serialization"),
                    &mut read,
                );
            }
        }
        owned.is_disjoint(&read)
    });
    owners
}

pub(crate) fn classify(program: &Program) -> Result<Vec<bool>, Error> {
    let owners = isolated_instances(program);
    program
        .events
        .iter()
        .map(|event| {
            Ok(owners.contains(&event.origin.instance)
                && !event.trigger.leaves()?.iter().any(|leaf| {
                    matches!(
                        leaf,
                        EventTrigger::InitialStep {} | EventTrigger::Timer { start: 0.0, .. }
                    )
                }))
        })
        .collect()
}

pub(crate) struct Prepared {
    pub(crate) selection: Selection,
    pub(crate) states: Vec<f64>,
    pub(crate) bounds: Vec<I>,
}

/// No query or intermediate physical closure round can publish observer writes.
pub(crate) fn prepare(
    model: &EventModel,
    events: &[usize],
    fired: &[usize],
    voltages: &[f64],
    nodes: &[I],
    before: &[f64],
    before_bounds: &[I],
) -> Result<Prepared, Error> {
    let passive: Vec<_> = events
        .iter()
        .copied()
        .filter(|&e| model.passive_events[e])
        .collect();
    let selection =
        model
            .passive_conditions
            .select_at_roots(&passive, &nodes[1..], fired, before_bounds)?;
    model.check_selection_writers(&selection)?;
    let states = model.apply(&selection, voltages, before)?;
    let mut bounds = before_bounds.to_vec();
    for (event, indices) in &selection.actions {
        let assignments = model.program.events[*event].assignments();
        let mut local = before_bounds.to_vec();
        let mut local_values = before.to_vec();
        for &index in indices {
            let assignment = assignments[index];
            let row = crate::affine_bounds::affine(&assignment.rhs, &model.program)?;
            let parameters: Vec<_> = nodes
                .iter()
                .chain(&local)
                .copied()
                .chain(std::iter::repeat_n(I::ZERO, model.program.operators.len()))
                .chain([I::ONE])
                .collect();
            let exact = row
                .iter()
                .zip(&parameters)
                .fold(I::ZERO, |sum, (&a, &b)| sum + a * b);
            local_values[assignment.state] = crate::events::affine(
                &assignment.rhs,
                &model.program,
                &model.program.events[*event].origin.instance,
            )?
            .value(voltages, &local_values)?;
            if !exact.finite()
                || (model.program.states[assignment.state].kind == StateKind::Integer
                    && (exact.lo != local_values[assignment.state]
                        || exact.hi != local_values[assignment.state]))
            {
                return Err(Error::new(
                    "event_accuracy",
                    "cannot certify passive event state",
                ));
            }
            local[assignment.state] = exact;
            bounds[assignment.state] = exact;
        }
    }
    Ok(Prepared {
        selection,
        states,
        bounds,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn isolation_scans_zero_terms_and_both_unselected_arms() {
        let physical = json!({"source":"isolation.va","line":1,"column":1,"instance":"D"});
        let observer = json!({"source":"isolation.va","line":2,"column":1,"instance":"M"});
        let zero = json!({"op":"affine","constant":0,"terms":[]});
        let state = json!({"op":"state","state":0});
        let mut value = json!({"schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","y"],"operators":[],
            "states":[{"instance":"M","name":"seen","kind":"real","initial":0}],
            "events":[{"origin":observer,"trigger":{"kind":"timer","start":0.5,"period":0,"time_tolerance":0.001,"enabled":true},"body":[]}],
            "contributions":[{"branch":{"instance":"D","local_positive":"out","local_negative":"ref","kind":"voltage"},
                "positive":1,"negative":0,"rhs":zero,"origin":physical}]});
        let classify_value =
            |v: &serde_json::Value| classify(&serde_json::from_value(v.clone()).unwrap()).unwrap();
        assert_eq!(classify_value(&value), [true]);
        value["contributions"][0]["rhs"] = json!({"op":"multiply","left":zero,"right":state});
        assert_eq!(classify_value(&value), [false]);
        value["contributions"][0]["rhs"] = json!({"op":"select","relation":"gt","left":zero,"right":zero,"then_value":zero,"else_value":state,"origin":physical});
        assert_eq!(classify_value(&value), [false]);
        value["contributions"][0]["rhs"] = zero;
        value["contributions"][0]["origin"]["instance"] = json!("M");
        value["contributions"][0]["branch"]["instance"] = json!("M");
        assert_eq!(classify_value(&value), [false]);
    }
}

#[cfg(test)]
mod operator_projection_tests {
    use super::*;
    use crate::event_conditions::Conditions;
    use serde_json::json;

    #[test]
    fn original_operator_leaf_columns_never_alias_passive_constants_or_overflow() {
        let physical = json!({"source":"operator-root.va","line":1,"column":1,"instance":"D"});
        let observer = json!({"source":"operator-root.va","line":2,"column":1,"instance":"M"});
        let constant = |value: f64| json!({"op":"affine","constant":value,"terms":[]});
        let cross = |operator, threshold| json!({"kind":"cross","guard":{"op":"add","left":{"op":"operator","operator":operator},"right":constant(threshold)},"direction":1,"time_tolerance":0.001,"expression_tolerance":0.001});
        let program: Program = serde_json::from_value(json!({"schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","u"],"contributions":[],
            "states":[{"instance":"M","name":"seen","kind":"real","initial":0}],
            "operators":[{"kind":"idt","input":constant(1.),"ic":0,"origin":physical},
                {"kind":"idt","input":constant(1.),"ic":0,"origin":physical}],
            "events":[{"origin":physical,"trigger":cross(0,-0.5),"body":[{"kind":"if","relation":"gt","left":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]},"right":constant(0.1),"then_body":[],"else_body":[],"origin":physical}]},
                {"origin":physical,"trigger":cross(1,-0.75),"body":[]},
                {"origin":observer,"trigger":{"kind":"timer","start":0.5,"period":0,"enabled":true,"time_tolerance":0.001},
                    "body":[{"kind":"if","relation":"gt","left":constant(1.),"right":constant(0.),"origin":observer,
                        "then_body":[{"kind":"assign","state":0,"rhs":constant(1.)}],
                        "else_body":[{"kind":"assign","state":0,"rhs":constant(-1.)}]}]}]
        })).unwrap();
        let (projected, driven) = crate::event_accuracy::GuardBounds::passive_program(&program);
        assert_eq!(projected.operators.len(), program.operators.len());
        for active in [[false, false, false], [false, false, true]] {
            let mut conditions = Conditions::new(&program).unwrap();
            conditions.restrict_events(&active);
            conditions.prepare(&projected, &driven).unwrap();
            for fired in [0, 1] {
                let selection = conditions
                    .select_at_roots(&[2], &[I::ONE], &[fired], &[I::ZERO])
                    .unwrap();
                if active[2] {
                    assert_eq!(selection.actions, [(2, vec![0])]);
                } else {
                    assert!(selection.actions.is_empty());
                }
            }
        }
    }
}
