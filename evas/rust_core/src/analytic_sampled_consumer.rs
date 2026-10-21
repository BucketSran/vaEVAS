//! Private joint role proof for fixed-timer scalar samples and held Transitions.
//! This token grants no continuous target, history read or observer mathematics.
use super::scope;
use crate::ir::{
    Error, EventTrigger, Expression as E, OperatorSpec, Origin, Program, StateKind, Statement,
};
use crate::transition_source_plan::{ProofContext, Work};
use std::sync::Arc;

pub(super) struct Admission;

fn origin(value: &Origin, owner: &str, w: &Work) -> Result<(), Error> {
    w.debit(
        2,
        (value.instance.len() + owner.len() + value.source.len() + 4) as u64,
    )?;
    // Pay the frame-length scan before collecting its character bound, then
    // reserve valid_expansion's frame and ASCII checks as a separate traversal.
    w.debit(2, value.expansion.len().saturating_mul(2) as u64)?;
    let expansion_characters = value
        .expansion
        .iter()
        .fold(0usize, |total, (name, _)| total.saturating_add(name.len()));
    w.debit(2, expansion_characters.saturating_mul(4) as u64)?;
    if value.instance != owner
        || owner.is_empty()
        || value.source.is_empty()
        || value.line == 0
        || value.column == 0
        || !value.valid_expansion()
    {
        return Err(scope(
            "sampled Transition requires a valid same-owner original Origin",
        ));
    }
    Ok(())
}

fn state(index: usize, owner: &str, p: &Program, w: &Work) -> Result<(), Error> {
    w.step()?;
    let value = p
        .states
        .get(index)
        .ok_or_else(|| scope("unknown sampled state"))?;
    w.debit(2, (value.instance.len() + owner.len() + 2) as u64)?;
    if value.instance != owner {
        return Err(scope(
            "sampled Transition cannot read or write a foreign state",
        ));
    }
    Ok(())
}

fn integer_guard(e: &E, owner: &str, p: &Program, w: &Work) -> Result<(), Error> {
    w.step()?;
    match e {
        E::State { state: index } => {
            state(*index, owner, p, w)?;
            if p.states[*index].kind != StateKind::Integer {
                return Err(scope(
                    "held Select guard requires a declared same-owner integer state",
                ));
            }
        }
        E::Affine { constant, terms }
            if terms.is_empty()
                && constant.is_finite()
                && constant.fract() == 0.
                && *constant >= f64::from(i32::MIN)
                && *constant <= f64::from(i32::MAX) => {}
        _ => {
            return Err(scope(
                "held Select guard requires an integer state or signed32 integer literal",
            ))
        }
    }
    Ok(())
}

fn scalar(e: &E, owner: &str, p: &Program, inputs: &[usize], w: &Work) -> Result<(), Error> {
    w.step()?;
    match e {
        E::Affine { constant, terms } => {
            if !constant.is_finite() {
                return Err(scope("nonfinite sampled scalar constant"));
            }
            for (j, term) in terms.iter().enumerate() {
                w.debit(2, (inputs.len() + j + 2) as u64)?;
                if !term.coefficient.is_finite() || term.node >= p.nodes.len()
                    || terms[..j].iter().any(|other| other.node == term.node)
                    || term.node != 0 && !inputs.contains(&term.node)
                {
                    return Err(scope("sampled scalar requires original driven dependencies"));
                }
            }
        }
        E::State { state: index } => state(*index, owner, p, w)?,
        E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
            scalar(left, owner, p, inputs, w)?;
            scalar(right, owner, p, inputs, w)?;
        }
        _ => return Err(scope("sampled scalar excludes history, control nodes and observer mathematics; hidden arms are audited")),
    }
    Ok(())
}

fn body(
    items: &[Statement],
    owner: &str,
    p: &Program,
    inputs: &[usize],
    w: &Work,
) -> Result<(), Error> {
    for item in items {
        w.step()?;
        match item {
            Statement::Assign(a) => {
                state(a.state, owner, p, w)?;
                scalar(&a.rhs, owner, p, inputs, w)?;
            }
            Statement::If {
                left,
                right,
                then_body,
                else_body,
                origin: site,
                ..
            } => {
                origin(site, owner, w)?;
                scalar(left, owner, p, inputs, w)?;
                scalar(right, owner, p, inputs, w)?;
                body(then_body, owner, p, inputs, w)?;
                body(else_body, owner, p, inputs, w)?;
            }
            _ => {
                return Err(scope(
                    "sampled Transition event bodies require scalar Assign/If only",
                ))
            }
        }
    }
    Ok(())
}

/// Return whether a held affine leaf uses state. Select preserves every arm.
fn held(e: &E, owner: &str, p: &Program, w: &Work) -> Result<bool, Error> {
    w.step()?;
    match e {
        E::Affine { constant, terms } => {
            if !constant.is_finite() {
                return Err(scope("nonfinite held Transition constant"));
            }
            for term in terms {
                w.step()?;
                if term.node != 0 || !term.coefficient.is_finite() {
                    return Err(scope(
                        "sampled Transition targets must be held, not continuous inputs",
                    ));
                }
            }
            Ok(false)
        }
        E::State { state: index } => {
            state(*index, owner, p, w)?;
            Ok(true)
        }
        E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
            let a = held(left, owner, p, w)?;
            let b = held(right, owner, p, w)?;
            if matches!(e, E::Multiply { .. }) && a && b || matches!(e, E::Divide { .. }) && b {
                return Err(scope(
                    "sampled Transition target leaves require affine held state",
                ));
            }
            Ok(a || b)
        }
        E::Select {
            left,
            right,
            then_value,
            else_value,
            origin: site,
            ..
        } => {
            origin(site, owner, w)?;
            integer_guard(left, owner, p, w)?;
            integer_guard(right, owner, p, w)?;
            let yes = held(then_value, owner, p, w)?;
            let no = held(else_value, owner, p, w)?;
            let predicate_state = matches!(left.as_ref(), E::State { .. })
                || matches!(right.as_ref(), E::State { .. });
            Ok(predicate_state || yes || no)
        }
        _ => Err(scope(
            "sampled Transition target excludes history and unknown original roles",
        )),
    }
}

/// Original output may contain at most one live operator per product. Physical
/// source leaves are proved DC on the entire request, before any projection.
fn output(e: &E, owner: &str, p: &Program, source: &ProofContext) -> Result<bool, Error> {
    let w = source.borrow_work();
    w.step()?;
    match e {
        E::Affine { constant, terms } => {
            w.debit(2, terms.len() as u64)?;
            if !constant.is_finite() || terms.iter().any(|t| !t.coefficient.is_finite()) {
                return Err(scope("nonfinite sampled output coefficient"));
            }
            if !terms.is_empty() {
                source.exact_dc_affine(e, owner)?;
            }
            Ok(false)
        }
        E::Operator { operator } => {
            let spec = p
                .operators
                .get(*operator)
                .ok_or_else(|| scope("unknown sampled output operator"))?;
            origin(spec.origin(), owner, w)?;
            Ok(true)
        }
        E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
            let a = output(left, owner, p, source)?;
            let b = output(right, owner, p, source)?;
            if matches!(e, E::Multiply { .. }) && a && b || matches!(e, E::Divide { .. }) && b {
                return Err(scope(
                    "sampled output requires linear held Transition relations",
                ));
            }
            if matches!(e, E::Divide { .. }) {
                source.exact_dc_expression(right, owner)?;
            }
            Ok(a || b)
        }
        _ => Err(scope(
            "sampled output excludes history predicates and non-DC live leaves",
        )),
    }
}

impl Admission {
    pub(super) fn qualify(p: &Program, source: &Arc<ProofContext>) -> Result<Self, Error> {
        let w = source.borrow_work();
        let inputs = source.event_input_nodes();
        if !p.step_bounds.is_empty() || p.operators.is_empty() {
            return Err(scope(
                "sampled Transition profile requires held operators and no bound_step",
            ));
        }
        for s in &p.states {
            w.step()?;
            if !s.initial.constant()?.is_finite() {
                return Err(scope(
                    "sampled Transition requires finite constant initialization",
                ));
            }
        }
        for event in &p.events {
            origin(&event.origin, &event.origin.instance, w)?;
            if !matches!(event.trigger, EventTrigger::Timer { .. }) {
                return Err(scope(
                    "sampled Transition profile requires independent fixed Timer leaves",
                ));
            }
            body(&event.body, &event.origin.instance, p, inputs, w)?;
        }
        for spec in &p.operators {
            w.step()?;
            let OperatorSpec::Transition {
                input,
                origin: site,
                ..
            } = spec
            else {
                return Err(scope(
                    "sampled analytic consumer requires held Transition operators only",
                ));
            };
            origin(site, &site.instance, w)?;
            held(input, &site.instance, p, w)?;
        }
        for c in &p.contributions {
            origin(&c.origin, &c.branch.instance, w)?;
            output(&c.rhs, &c.origin.instance, p, source)?;
        }
        Ok(Self)
    }
}
