//! Meaning-preserving request canonicalization for procedure-bound reals (H1).
//!
//! IR33 keeps program reals in procedure bindings. Two closed forms need no
//! procedure frame, so they are made explicit before any consumer runs:
//! - a constant alias read by a cross guard: the single, unconditional,
//!   top-level binding of a closed binary64 constant (as in `th=0.5*vh`),
//!   placed before the guard's event gate in the same procedure, so every
//!   evaluation of the guard reads that constant;
//! - an idt assert that is a closed constant zero: LRM 2.4 4.5.4 Table 4-18
//!   makes `idt(x,ic,0)` equal to `idt(x,ic)` (the assert is never nonzero).
//!
//! A conditional, repeated, later, foreign or nonconstant binding is left
//! unchanged, so its consumer keeps its own typed refusal or IR validation.
use crate::ir::{
    EventTrigger, Expression as E, OperatorSpec, ProcedureAction as A, ProcedureControl as C,
    ProcedureStep, Program,
};
use std::collections::BTreeMap;

/// A constant alias: owning procedure, top-level position and binary64 value.
struct Alias {
    procedure: usize,
    position: usize,
    value: f64,
}

pub(crate) fn request_program(p: &mut Program) {
    let aliases = constant_aliases(p);
    // event -> (procedure, top-level position of its gate)
    let mut gates = BTreeMap::new();
    for procedure in &p.procedures {
        for (position, step) in procedure.body.iter().enumerate() {
            if let A::Control(C::EventGate { event }) = &step.action {
                gates.insert(*event, (procedure.procedure_id, position));
            }
        }
    }
    for (index, event) in p.events.iter_mut().enumerate() {
        let Some(&(procedure, gate)) = gates.get(&index) else {
            continue;
        };
        let lookup = |binding: usize| {
            aliases
                .get(&binding)
                .filter(|a| a.procedure == procedure && a.position < gate)
                .map(|a| a.value)
        };
        inline_trigger(&mut event.trigger, &lookup);
    }
    for spec in &mut p.operators {
        if let OperatorSpec::Idt { reset, .. } = spec {
            if reset
                .as_ref()
                .and_then(crate::real_expression::constant)
                .is_some_and(|value| value == 0.0)
            {
                *reset = None;
            }
        }
    }
}

fn constant_aliases(p: &Program) -> BTreeMap<usize, Alias> {
    fn count(steps: &[ProcedureStep], definitions: &mut BTreeMap<usize, usize>) {
        for step in steps {
            match &step.action {
                A::Control(C::RealBind { binding, .. }) => {
                    *definitions.entry(*binding).or_default() += 1;
                }
                A::Control(C::ProcedureIf {
                    then_body,
                    else_body,
                    ..
                }) => {
                    count(then_body, definitions);
                    count(else_body, definitions);
                }
                A::Control(C::ProcedureLoop {
                    initialize,
                    body,
                    update,
                    ..
                }) => {
                    for part in [initialize, body, update] {
                        count(part, definitions);
                    }
                }
                _ => {}
            }
        }
    }
    let mut definitions = BTreeMap::new();
    for procedure in &p.procedures {
        count(&procedure.body, &mut definitions);
    }
    let mut aliases: BTreeMap<usize, Alias> = BTreeMap::new();
    for procedure in &p.procedures {
        // Source order: an alias of an earlier alias resolves in one pass.
        for (position, step) in procedure.body.iter().enumerate() {
            let A::Control(C::RealBind { binding, value, .. }) = &step.action else {
                continue;
            };
            let owned = p
                .real_bindings
                .get(*binding)
                .is_some_and(|b| b.procedure_id == procedure.procedure_id);
            if !owned || definitions.get(binding) != Some(&1) {
                continue;
            }
            let mut value = value.clone();
            inline(&mut value, &|read: usize| {
                aliases
                    .get(&read)
                    .filter(|a| a.procedure == procedure.procedure_id)
                    .map(|a| a.value)
            });
            if let Some(value) = crate::real_expression::constant(&value) {
                aliases.insert(
                    *binding,
                    Alias {
                        procedure: procedure.procedure_id,
                        position,
                        value,
                    },
                );
            }
        }
    }
    aliases
}

fn inline_trigger(trigger: &mut EventTrigger, lookup: &dyn Fn(usize) -> Option<f64>) {
    match trigger {
        EventTrigger::Cross { guard, .. } => inline(guard, lookup),
        EventTrigger::Or { triggers } => {
            for leaf in triggers {
                inline_trigger(leaf, lookup);
            }
        }
        _ => {}
    }
}

fn inline(e: &mut E, lookup: &dyn Fn(usize) -> Option<f64>) {
    match e {
        E::RealLocal { binding } => {
            if let Some(value) = lookup(*binding) {
                *e = crate::real_expression::literal(value);
            }
        }
        E::RealBinary { left, right, .. }
        | E::Add { left, right }
        | E::Multiply { left, right }
        | E::Divide { left, right } => {
            inline(left, lookup);
            inline(right, lookup);
        }
        E::RealBoundary { value, .. } => inline(value, lookup),
        E::Power { base, .. } => inline(base, lookup),
        E::Select {
            left,
            right,
            then_value,
            else_value,
            ..
        } => {
            for child in [left, right, then_value, else_value] {
                inline(child, lookup);
            }
        }
        // Guards and alias values are continuous or rounded real arithmetic;
        // calls keep their own activation scope and other nodes stay as given.
        _ => {}
    }
}

#[cfg(test)]
#[path = "canonical_tests.rs"]
mod tests;
