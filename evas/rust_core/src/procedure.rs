//! Source ownership and the single occurrence-local procedure executor.
use crate::ir::{
    self, Error, Expression as E, ProcedureAction as A, ProcedureControl as C, ProcedureStep,
    Program,
};
use crate::transition_source_plan::Work;
use std::collections::BTreeSet;
fn invalid(message: &str) -> Error {
    Error::new("invalid_ir", message)
}
fn origin(o: &ir::Origin, owner: &str) -> Result<(), Error> {
    if o.instance != owner
        || o.source.is_empty()
        || o.line == 0
        || o.column == 0
        || !o.valid_expansion()
    {
        return Err(invalid("procedure source identity mismatch"));
    }
    Ok(())
}
#[path = "procedure_call_scope.rs"]
mod calls;
#[path = "procedure_plan.rs"]
mod plan;
#[path = "procedure_dependencies.rs"]
mod source_dependencies;
#[path = "procedure_structure.rs"]
mod structure;
pub(crate) use plan::{execute, CircuitView, Plan};
pub(crate) use source_dependencies::{
    activation_writes, dependencies as source_dependencies, sources as dependency_sources,
    unconditional_contributions, Sources as DependencySources,
};
/// Validate every arm, including inactive gates and captures. Runtime loop
/// iterations repeat the same source identity, never create new source owners.
pub(crate) fn validate(p: &Program, w: &Work) -> Result<(), Error> {
    calls::validate(p, w)?;
    // DFS owner/ordinal and each uniqueness set have distinct invariants.
    #[allow(clippy::too_many_arguments)]
    fn visit(
        steps: &[ProcedureStep],
        p: &Program,
        id: usize,
        owner: &str,
        last: &mut Option<u64>,
        events: &mut BTreeSet<usize>,
        contributions: &mut BTreeSet<usize>,
        bounds: &mut BTreeSet<usize>,
        w: &Work,
    ) -> Result<(), Error> {
        for step in steps {
            w.step()?;
            if last.is_some_and(|n| step.expanded_statement_ordinal <= n) {
                return Err(invalid(
                    "procedure ordinals must be unique in DFS source order",
                ));
            }
            *last = Some(step.expanded_statement_ordinal);
            match &step.action {
                A::Statement(s) => structure::statement(s, p, id, owner, w)?,
                A::Control(C::RealBind {
                    binding,
                    value,
                    origin: o,
                }) => {
                    structure::expression(value, p, Some(id), owner, w)?;
                    structure::source(o, owner, w)?;
                    let b = p
                        .real_bindings
                        .get(*binding)
                        .ok_or_else(|| invalid("real binding out of range"))?;
                    if b.procedure_id != id {
                        return Err(invalid("real binding belongs to another procedure"));
                    }
                }
                A::Control(C::EventGate { event }) => {
                    let e = p
                        .events
                        .get(*event)
                        .ok_or_else(|| invalid("event gate out of range"))?;
                    structure::source(&e.origin, owner, w)?;
                    for s in &e.body {
                        structure::statement(s, p, id, owner, w)?;
                    }
                    if e.procedure_id != Some(id)
                        || e.expanded_statement_ordinal != Some(step.expanded_statement_ordinal)
                        || e.origin.instance != owner
                        || !events.insert(*event)
                    {
                        return Err(invalid(
                            "event gate must have one matching procedure/source owner",
                        ));
                    }
                }
                A::Control(C::ContributionCapture { contribution }) => {
                    let c = p
                        .contributions
                        .get(*contribution)
                        .ok_or_else(|| invalid("contribution capture out of range"))?;
                    structure::source(&c.origin, owner, w)?;
                    structure::expression(&c.rhs, p, Some(id), owner, w)?;
                    if c.origin.instance != owner || !contributions.insert(*contribution) {
                        return Err(invalid("contribution capture must have one source owner"));
                    }
                }
                A::Control(C::StepBoundCapture { step_bound }) => {
                    let b = p
                        .step_bounds
                        .get(*step_bound)
                        .ok_or_else(|| invalid("step bound capture out of range"))?;
                    structure::source(&b.origin, owner, w)?;
                    structure::expression(&b.value, p, Some(id), owner, w)?;
                    structure::expression(&b.active, p, Some(id), owner, w)?;
                    if b.origin.instance != owner || !bounds.insert(*step_bound) {
                        return Err(invalid("step bound capture must have one source owner"));
                    }
                }
                A::Control(C::ProcedureIf {
                    left,
                    right,
                    then_body,
                    else_body,
                    origin: o,
                    ..
                }) => {
                    structure::source(o, owner, w)?;
                    structure::expression(left, p, Some(id), owner, w)?;
                    structure::expression(right, p, Some(id), owner, w)?;
                    visit(
                        then_body,
                        p,
                        id,
                        owner,
                        last,
                        events,
                        contributions,
                        bounds,
                        w,
                    )?;
                    visit(
                        else_body,
                        p,
                        id,
                        owner,
                        last,
                        events,
                        contributions,
                        bounds,
                        w,
                    )?;
                }
                A::Control(C::ProcedureLoop {
                    left,
                    right,
                    initialize,
                    body,
                    update,
                    origin: o,
                    ..
                }) => {
                    structure::source(o, owner, w)?;
                    structure::expression(left, p, Some(id), owner, w)?;
                    structure::expression(right, p, Some(id), owner, w)?;
                    for part in [initialize, body, update] {
                        visit(part, p, id, owner, last, events, contributions, bounds, w)?;
                    }
                }
            }
        }
        Ok(())
    }
    let mut ids = BTreeSet::new();
    let mut events = BTreeSet::new();
    let mut contributions = BTreeSet::new();
    let mut bounds = BTreeSet::new();
    for procedure in &p.procedures {
        w.debit(2, 64)?;
        if procedure.instance.is_empty() || !ids.insert(procedure.procedure_id) {
            return Err(invalid("duplicate or invalid procedure identity"));
        }
        visit(
            &procedure.body,
            p,
            procedure.procedure_id,
            &procedure.instance,
            &mut None,
            &mut events,
            &mut contributions,
            &mut bounds,
            w,
        )?;
    }
    for (i, e) in p.events.iter().enumerate() {
        w.step()?;
        if (!p.procedures.is_empty()
            || e.procedure_id.is_some()
            || e.expanded_statement_ordinal.is_some())
            && !events.contains(&i)
        {
            return Err(invalid("event has no procedure gate owner"));
        }
    }
    for b in &p.real_bindings {
        w.step()?;
        w.debit(2, p.procedures.len() as u64)?;
        let owner = p
            .procedures
            .iter()
            .find(|q| q.procedure_id == b.procedure_id)
            .map(|q| q.instance.as_str())
            .ok_or_else(|| invalid("real binding procedure absent"))?;
        structure::source(&b.origin, owner, w)?;
        if !ids.contains(&b.procedure_id) {
            return Err(invalid("real binding has no procedure owner"));
        }
    }
    if !p.procedures.is_empty() {
        for index in 0..p.contributions.len() {
            w.step()?;
            if !contributions.contains(&index) {
                return Err(invalid("contribution has no procedure capture owner"));
            }
        }
        for index in 0..p.step_bounds.len() {
            w.step()?;
            if !bounds.contains(&index) {
                return Err(invalid("step bound has no procedure capture owner"));
            }
        }
        // Each operator input is structurally visited once. References are only
        // checked here, never recursively expanded or numerically evaluated.
        for operator in &p.operators {
            let o = operator.origin();
            structure::source(o, &o.instance, w)?;
            let input = match operator {
                ir::OperatorSpec::Ddt { input, .. }
                | ir::OperatorSpec::Idt { input, .. }
                | ir::OperatorSpec::IdtMod { input, .. }
                | ir::OperatorSpec::Math { input, .. }
                | ir::OperatorSpec::Sin { input, .. }
                | ir::OperatorSpec::AbsDelay { input, .. }
                | ir::OperatorSpec::Transition { input, .. }
                | ir::OperatorSpec::Slew { input, .. }
                | ir::OperatorSpec::LaplaceNd { input, .. } => input,
            };
            structure::expression(input, p, None, &o.instance, w)?;
            if let ir::OperatorSpec::Idt {
                reset: Some(reset), ..
            } = operator
            {
                structure::expression(reset, p, None, &o.instance, w)?;
            }
        }
    }
    Ok(())
}

pub(crate) fn captures_only(p: &Program, w: &Work) -> Result<bool, Error> {
    w.debit(2, p.procedures.len() as u64)?;
    if !p.real_bindings.is_empty() {
        return Ok(false);
    }
    for procedure in &p.procedures {
        w.debit(2, procedure.body.len() as u64)?;
        for step in &procedure.body {
            if !matches!(
                step.action,
                A::Control(C::ContributionCapture { .. } | C::StepBoundCapture { .. })
            ) {
                return Ok(false);
            }
        }
    }
    fn plain(e: &E, w: &Work) -> Result<bool, Error> {
        w.step()?;
        match e {
            E::Affine { .. } => Ok(true),
            E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
                Ok(plain(left, w)? && plain(right, w)?)
            }
            E::Power { base, .. } => plain(base, w),
            E::Select {
                left,
                right,
                then_value,
                else_value,
                ..
            } => Ok(plain(left, w)?
                && plain(right, w)?
                && plain(then_value, w)?
                && plain(else_value, w)?),
            _ => Ok(false),
        }
    }
    for c in &p.contributions {
        if !plain(&c.rhs, w)? {
            return Ok(false);
        }
    }
    Ok(true)
}

pub(crate) fn binding_values(p: &Program, binding: usize) -> Vec<&E> {
    fn visit<'a>(steps: &'a [ProcedureStep], binding: usize, out: &mut Vec<&'a E>) {
        for s in steps {
            match &s.action {
                A::Control(C::RealBind {
                    binding: b, value, ..
                }) if *b == binding => out.push(value),
                A::Control(C::ProcedureIf {
                    then_body,
                    else_body,
                    ..
                }) => {
                    visit(then_body, binding, out);
                    visit(else_body, binding, out);
                }
                A::Control(C::ProcedureLoop {
                    initialize,
                    body,
                    update,
                    ..
                }) => {
                    for part in [initialize, body, update] {
                        visit(part, binding, out)
                    }
                }
                _ => {}
            }
        }
    }
    let mut out = Vec::new();
    for procedure in &p.procedures {
        visit(&procedure.body, binding, &mut out);
    }
    out
}

pub(crate) fn call_children(
    e: &E,
    f: &mut impl FnMut(&E) -> Result<(), Error>,
) -> Result<(), Error> {
    calls::children(e, f)
}

/// Whether an event body can compare anything: an if, a loop, a selection or
/// a call. Bounded by the validated body; nothing is evaluated.
pub(crate) fn body_controls(body: &[ir::Statement]) -> bool {
    fn expression(e: &E) -> bool {
        if matches!(e, E::Select { .. } | E::RealCall { .. }) {
            return true;
        }
        let mut found = false;
        let _ = calls::children(e, &mut |child| {
            found |= expression(child);
            Ok(())
        });
        found
    }
    body.iter().any(|statement| match statement {
        ir::Statement::If { .. } | ir::Statement::Loop { .. } => true,
        ir::Statement::Assign(a) => expression(&a.rhs),
        ir::Statement::ArrayWrite { index, rhs, .. } => expression(index) || expression(rhs),
        ir::Statement::Display { args, .. } => args.iter().any(expression),
    })
}

/// One immutable validated source graph and the same request ledger, shared by
/// active/passive condition views rather than deep-copying the model twice.
pub(crate) struct Prepared {
    pub program: std::sync::Arc<Program>,
    pub work: Work,
    pub requires_execution: bool,
}
pub(crate) fn prepare(p: &Program, w: &Work) -> Result<Prepared, Error> {
    validate(p, w)?;
    let requires_execution = !captures_only(p, w)?;
    let n = crate::event_floor::encoded_size(p, w)?;
    w.debit(2, (n as u64).saturating_mul(8))?;
    Ok(Prepared {
        program: std::sync::Arc::new(p.clone()),
        work: w.clone(),
        requires_execution,
    })
}

/// A source real node needs its occurrence environment. This scan does not
/// evaluate domains, so an inactive function remains inactive.
pub(crate) fn requires_source_frame(e: &E, p: &Program, w: &Work) -> Result<bool, Error> {
    fn visit(e: &E, p: &Program, w: &Work, seen: &mut BTreeSet<usize>) -> Result<bool, Error> {
        w.step()?;
        if matches!(
            e,
            E::RealCall { .. }
                | E::RealLocal { .. }
                | E::RealBoundary { .. }
                | E::RealBinary { .. }
                | E::UnsupportedSystemCall { .. }
                | E::State { .. }
        ) {
            return Ok(true);
        }
        if let E::Operator { operator } = e {
            if let Some(
                ir::OperatorSpec::Math { input, .. } | ir::OperatorSpec::Sin { input, .. },
            ) = p.operators.get(*operator)
            {
                w.debit(2, ((seen.len() + 1).ilog2() as u64 + 2) * 32)?;
                if !seen.insert(*operator) {
                    return Err(invalid("procedure memoryless dependency cycle"));
                }
                let result = visit(input, p, w, seen);
                seen.remove(operator);
                return result;
            }
        }
        let mut required = false;
        calls::children(e, &mut |e| {
            required |= visit(e, p, w, seen)?;
            Ok(())
        })?;
        Ok(required)
    }
    visit(e, p, w, &mut BTreeSet::new())
}

/// Structural closedness must not evaluate an inactive numeric domain.
/// In particular, closed physical arithmetic need not have a native constant
/// fold in order to belong to the source procedure's lazy execution.
pub(crate) fn closed_math_input(e: &E, w: &Work) -> Result<bool, Error> {
    w.step()?;
    Ok(match e {
        E::Affine { terms, .. } => {
            let mut closed = true;
            for t in terms {
                w.step()?;
                closed &= t.node == 0 || t.coefficient == 0.;
            }
            closed
        }
        E::Add { left, right }
        | E::Multiply { left, right }
        | E::Divide { left, right }
        | E::RealBinary { left, right, .. } => {
            closed_math_input(left, w)? && closed_math_input(right, w)?
        }
        E::Power { base, .. }
        | E::RealBoundary { value: base, .. }
        | E::IntegerRound { value: base, .. }
        | E::CheckedInteger { value: base, .. } => closed_math_input(base, w)?,
        E::Select {
            left,
            right,
            then_value,
            else_value,
            ..
        } => {
            closed_math_input(left, w)?
                && closed_math_input(right, w)?
                && closed_math_input(then_value, w)?
                && closed_math_input(else_value, w)?
        }
        E::EventMath { args, .. } => {
            let mut closed = true;
            for arg in args {
                closed &= closed_math_input(arg, w)?;
            }
            closed
        }
        _ => false,
    })
}

/// Closed memoryless call sites belong to the source activation, not the
/// physical DAE dispatcher. Include every local definition/control dependency;
/// a zero coefficient or declaration seed cannot erase a physical dependency.
pub(crate) fn closed_math_program(p: &Program, w: &Work) -> Result<bool, Error> {
    if p.procedures.is_empty() || p.operators.is_empty() {
        return Ok(false);
    }
    if !p.operators.iter().all(|op| {
        matches!(
            op,
            ir::OperatorSpec::Math { .. } | ir::OperatorSpec::Sin { .. }
        )
    }) {
        return Ok(false);
    }
    let sources = dependency_sources(p, w)?;
    for (index, op) in p.operators.iter().enumerate() {
        let deps = source_dependencies(calls::input(op), p, &sources, w)?;
        if deps.node_dependencies.iter().any(|&node| node != 0)
            || !deps.state_dependencies.is_empty()
            || deps
                .operator_dependencies
                .iter()
                .any(|&other| other >= index)
        {
            return Ok(false);
        }
    }
    Ok(true)
}

/// Held trigger arithmetic uses the same rounded source primitives and sticky
/// owner as event values. No physical input is supplied by this state-only
/// admission; source locals still require their owning occurrence frame.
pub(crate) fn held_parameter(
    e: &E,
    p: &Program,
    states: &[crate::interval::Interval],
    w: &Work,
) -> Result<crate::interval::Interval, Error> {
    w.debit(2, (p.nodes.len() * 16 + 64) as u64)?;
    let nodes = vec![crate::interval::Interval::ZERO; p.nodes.len()];
    let proofs = crate::event_value_proof::Proofs::new();
    let context =
        crate::event_value_proof::Context::candidate_frame(&proofs, p.nodes.len(), &[], &[], w)?;
    let local = crate::event_value_proof::LocalState::try_with_context(states, Some(&context))?;
    crate::event_numeric::bounds_with_proofs(e, &nodes, &local)
}

#[cfg(test)]
#[path = "raw_event_owner_tests.rs"]
mod raw_event_owner_tests;
