//! Static call ownership is checked over every arm without numeric execution.
use super::*;
use crate::ir::{OperatorSpec, Statement as S};

pub(super) fn input(op: &OperatorSpec) -> &E {
    match op {
        OperatorSpec::Ddt { input, .. }
        | OperatorSpec::Idt { input, .. }
        | OperatorSpec::IdtMod { input, .. }
        | OperatorSpec::Math { input, .. }
        | OperatorSpec::Sin { input, .. }
        | OperatorSpec::AbsDelay { input, .. }
        | OperatorSpec::Transition { input, .. }
        | OperatorSpec::Slew { input, .. }
        | OperatorSpec::LaplaceNd { input, .. } => input,
    }
}
fn statements<'a>(s: &'a [S], f: &mut impl FnMut(&'a E) -> Result<(), Error>) -> Result<(), Error> {
    for s in s {
        match s {
            S::Assign(a) => f(&a.rhs)?,
            S::ArrayWrite { index, rhs, .. } => {
                f(index)?;
                f(rhs)?;
            }
            S::Display { args, .. } => {
                for e in args {
                    f(e)?;
                }
            }
            S::If {
                left,
                right,
                then_body,
                else_body,
                ..
            } => {
                f(left)?;
                f(right)?;
                statements(then_body, f)?;
                statements(else_body, f)?;
            }
            S::Loop {
                initialize,
                left,
                right,
                body,
                update,
                ..
            } => {
                f(left)?;
                f(right)?;
                for s in [initialize, body, update] {
                    statements(s, f)?;
                }
            }
        }
    }
    Ok(())
}
pub(super) fn step_expressions<'a>(
    s: &'a [ProcedureStep],
    f: &mut impl FnMut(&'a E) -> Result<(), Error>,
) -> Result<(), Error> {
    for s in s {
        match &s.action {
            A::Statement(s) => statements(std::slice::from_ref(s), f)?,
            A::Control(C::RealBind { value, .. }) => f(value)?,
            A::Control(C::ProcedureIf {
                left,
                right,
                then_body,
                else_body,
                ..
            }) => {
                f(left)?;
                f(right)?;
                step_expressions(then_body, f)?;
                step_expressions(else_body, f)?;
            }
            A::Control(C::ProcedureLoop {
                left,
                right,
                initialize,
                body,
                update,
                ..
            }) => {
                f(left)?;
                f(right)?;
                for s in [initialize, body, update] {
                    step_expressions(s, f)?;
                }
            }
            _ => {}
        }
    }
    Ok(())
}
pub(super) fn children<'a>(
    e: &'a E,
    f: &mut impl FnMut(&'a E) -> Result<(), Error>,
) -> Result<(), Error> {
    match e {
        E::RealCall { body, result, .. } => {
            step_expressions(body, f)?;
            f(result)?;
        }
        E::UnsupportedSystemCall { args, .. } | E::EventMath { args, .. } => {
            for e in args {
                f(e)?;
            }
        }
        E::RealBinary { left, right, .. }
        | E::Add { left, right }
        | E::Multiply { left, right }
        | E::Divide { left, right } => {
            f(left)?;
            f(right)?;
        }
        E::RealBoundary { value, .. }
        | E::IntegerRound { value, .. }
        | E::CheckedInteger { value, .. }
        | E::Power { base: value, .. } => f(value)?,
        E::CheckedIndex { index, .. } | E::ArrayRead { index, .. } => f(index)?,
        E::Select {
            left,
            right,
            then_value,
            else_value,
            ..
        } => {
            for e in [left, right, then_value, else_value] {
                f(e)?;
            }
        }
        E::Forcing { value, checked, .. } => {
            f(value)?;
            for e in checked {
                f(e)?;
            }
        }
        _ => {}
    }
    Ok(())
}
pub(super) fn trigger_expressions<'a>(
    t: &'a ir::EventTrigger,
    w: &Work,
    f: &mut impl FnMut(&'a E) -> Result<(), Error>,
) -> Result<(), Error> {
    w.step()?;
    match t {
        ir::EventTrigger::Or { triggers } => {
            for t in triggers {
                trigger_expressions(t, w, f)?;
            }
        }
        ir::EventTrigger::Cross { guard, .. } => f(guard)?,
        ir::EventTrigger::HeldTimer {
            start,
            period,
            enabled,
            ..
        } => {
            for e in [start, period, enabled] {
                f(e)?;
            }
        }
        _ => {}
    }
    Ok(())
}
fn roots<'a>(
    p: &'a Program,
    w: &Work,
    f: &mut impl FnMut(&'a E) -> Result<(), Error>,
) -> Result<(), Error> {
    for s in &p.states {
        w.step()?;
        if let ir::StateInitial::Predicate(e) = &s.initial {
            f(e)?;
        }
    }
    for e in &p.events {
        w.step()?;
        trigger_expressions(&e.trigger, w, f)?;
        statements(&e.body, f)?;
    }
    for c in &p.contributions {
        w.step()?;
        f(&c.rhs)?;
    }
    for b in &p.step_bounds {
        w.step()?;
        f(&b.value)?;
        f(&b.active)?;
    }
    for o in &p.operators {
        w.step()?;
        f(input(o))?;
        if let OperatorSpec::Idt { reset: Some(r), .. } = o {
            f(r)?;
        }
    }
    for q in &p.procedures {
        w.step()?;
        step_expressions(&q.body, f)?;
    }
    Ok(())
}
fn collect(e: &E, owned: &mut BTreeSet<usize>, w: &Work) -> Result<(), Error> {
    w.step()?;
    if let E::RealCall { bindings, .. } = e {
        for &b in bindings {
            w.debit(2, ((owned.len() + 1).ilog2() as u64 + 2) * 32)?;
            if !owned.insert(b) {
                return Err(invalid("call binding has more than one syntactic owner"));
            }
        }
    }
    children(e, &mut |e| collect(e, owned, w))
}
struct Audit<'a> {
    p: &'a Program,
    w: &'a Work,
    function_body: bool,
    active: BTreeSet<usize>,
    done: BTreeSet<(usize, Option<usize>, Vec<usize>, bool)>,
}
impl Audit<'_> {
    fn local(&self, b: usize, allowed: &[usize], procedure: Option<usize>) -> Result<(), Error> {
        self.w.debit(2, (allowed.len() + 1) as u64)?;
        let binding = self
            .p
            .real_bindings
            .get(b)
            .ok_or_else(|| invalid("real binding index out of range"))?;
        if self.function_body && binding.lifetime != ir::RealBindingLifetime::Call {
            return Err(invalid(
                "pure function body cannot read an occurrence local",
            ));
        }
        if procedure.is_some_and(|id| id != binding.procedure_id)
            || (binding.lifetime == ir::RealBindingLifetime::Call && !allowed.contains(&b))
        {
            return Err(invalid("call binding escaped its activation scope"));
        }
        Ok(())
    }
    fn expression(
        &mut self,
        e: &E,
        allowed: &[usize],
        procedure: Option<usize>,
        owner: &str,
    ) -> Result<(), Error> {
        self.w.step()?;
        match e {
            E::State { .. } if self.function_body => {
                return Err(invalid("pure function body cannot read external state"))
            }
            E::ArrayRead { .. } if self.function_body => {
                return Err(invalid("pure function body cannot read an external array"))
            }
            E::IntegerPrimitive { args, .. } if self.function_body => {
                fn closed(n: &ir::IntegerOperand, w: &Work) -> Result<bool, Error> {
                    w.step()?;
                    match n {
                        ir::IntegerOperand::IntegerLiteral { .. } => Ok(true),
                        ir::IntegerOperand::IntegerState { .. } => Ok(false),
                        ir::IntegerOperand::IntegerPrimitive { args, .. } => {
                            for a in args {
                                if !closed(a, w)? {
                                    return Ok(false);
                                }
                            }
                            Ok(true)
                        }
                    }
                }
                for arg in args {
                    if !closed(arg, self.w)? {
                        return Err(invalid(
                            "pure function body cannot read external integer state",
                        ));
                    }
                }
            }
            E::RealLocal { binding } => self.local(*binding, allowed, procedure)?,
            E::RealCall {
                origin: o,
                bindings,
                body,
                result,
            } => {
                structure::source(o, owner, self.w)?;
                if !o.expansion.iter().any(|(n, _)| n == "function_call") {
                    return Err(invalid("pure call lacks its function-call source identity"));
                }
                self.w
                    .debit(2, ((allowed.len() + bindings.len()) * 32 + 64) as u64)?;
                let mut scope = allowed.to_vec();
                for &b in bindings {
                    self.w.step()?;
                    let binding = self
                        .p
                        .real_bindings
                        .get(b)
                        .ok_or_else(|| invalid("call binding out of range"))?;
                    if binding.lifetime != ir::RealBindingLifetime::Call
                        || binding.origin.instance != owner
                        || procedure.is_some_and(|id| binding.procedure_id != id)
                    {
                        return Err(invalid("call owns a foreign or non-call binding"));
                    }
                    scope.push(b);
                }
                // Argument prefixes inherit the caller context. Entering a function
                // body is sticky across nested calls; an inner argument label cannot
                // reopen module-level system-call privileges.
                let parent = self.function_body;
                let evaluated = (|| {
                    let mut prefix = true;
                    let mut last = None;
                    for step in body {
                        self.w.step()?;
                        prefix &= matches!(
                            &step.action,
                            A::Control(C::RealBind {
                                value: E::RealBoundary {
                                    kind: ir::RealBoundaryKind::Argument,
                                    ..
                                },
                                ..
                            })
                        );
                        self.function_body = parent || !prefix;
                        self.steps(
                            std::slice::from_ref(step),
                            if prefix { &scope } else { bindings },
                            procedure,
                            owner,
                            Some(bindings),
                            &mut last,
                        )?;
                    }
                    self.function_body = true;
                    self.expression(result, bindings, procedure, owner)
                })();
                self.function_body = parent;
                evaluated?;
            }
            E::UnsupportedSystemCall {
                function,
                seed,
                args,
                origin: o,
            } => {
                if self.function_body {
                    return Err(invalid(
                        "unsupported system call is forbidden in a pure function body",
                    ));
                }
                structure::source(o, owner, self.w)?;
                self.w.debit(2, function.len() as u64)?;
                if function != "rdist_normal"
                    || args.len() != 2
                    || self
                        .p
                        .states
                        .get(*seed)
                        .is_none_or(|s| s.instance != owner || s.kind != ir::StateKind::Integer)
                {
                    return Err(invalid(
                        "invalid recognized unsupported system-call signature or seed",
                    ));
                }
                for e in args {
                    self.expression(e, allowed, procedure, owner)?;
                }
            }
            E::Operator { operator } => {
                let op = self
                    .p
                    .operators
                    .get(*operator)
                    .ok_or_else(|| invalid("operator reference out of range"))?;
                if self.function_body
                    && !matches!(op, OperatorSpec::Math { .. } | OperatorSpec::Sin { .. })
                {
                    return Err(invalid(
                        "pure function body cannot read an external history operator",
                    ));
                }
                self.w.debit(
                    2,
                    ((allowed.len() + 1) * 32 + (self.done.len() + 1).ilog2() as usize * 16) as u64,
                )?;
                let key = (*operator, procedure, allowed.to_vec(), self.function_body);
                if self.done.contains(&key) {
                    return Ok(());
                }
                if !self.active.insert(*operator) {
                    return Err(invalid("call operator dependency cycle"));
                }
                self.expression(input(op), allowed, procedure, owner)?;
                if let OperatorSpec::Idt { reset: Some(e), .. } = op {
                    self.expression(e, allowed, procedure, owner)?;
                }
                self.active.remove(operator);
                self.done.insert(key);
            }
            _ => children(e, &mut |e| self.expression(e, allowed, procedure, owner))?,
        }
        Ok(())
    }
    fn steps(
        &mut self,
        steps: &[ProcedureStep],
        scope: &[usize],
        procedure: Option<usize>,
        owner: &str,
        owned: Option<&[usize]>,
        last: &mut Option<u64>,
    ) -> Result<(), Error> {
        for s in steps {
            self.w.step()?;
            if owned.is_some() {
                if last.is_some_and(|v| s.expanded_statement_ordinal <= v) {
                    return Err(invalid(
                        "call ordinals must be unique in its own DFS namespace",
                    ));
                }
                *last = Some(s.expanded_statement_ordinal);
            }
            match &s.action {
                A::Control(C::RealBind {
                    binding,
                    value,
                    origin: o,
                }) => {
                    if let Some(owned) = owned {
                        self.w.debit(2, owned.len() as u64)?;
                        if !owned.contains(binding) {
                            return Err(invalid(
                                "pure call writes a binding outside its ownership",
                            ));
                        }
                    }
                    self.local(*binding, scope, procedure)?;
                    structure::source(o, owner, self.w)?;
                    self.expression(value, scope, procedure, owner)?;
                }
                A::Control(C::ProcedureIf {
                    left,
                    right,
                    then_body,
                    else_body,
                    origin: o,
                    ..
                }) => {
                    structure::source(o, owner, self.w)?;
                    self.expression(left, scope, procedure, owner)?;
                    self.expression(right, scope, procedure, owner)?;
                    self.steps(then_body, scope, procedure, owner, owned, last)?;
                    self.steps(else_body, scope, procedure, owner, owned, last)?;
                }
                _ if owned.is_some() => {
                    return Err(invalid(
                        "pure call body only permits real binding and conditional steps",
                    ))
                }
                A::Control(C::ProcedureLoop {
                    left,
                    right,
                    initialize,
                    body,
                    update,
                    ..
                }) => {
                    self.expression(left, scope, procedure, owner)?;
                    self.expression(right, scope, procedure, owner)?;
                    for s in [initialize, body, update] {
                        self.steps(s, scope, procedure, owner, None, last)?;
                    }
                }
                A::Statement(s) => statements(std::slice::from_ref(s), &mut |e| {
                    self.expression(e, scope, procedure, owner)
                })?,
                _ => {}
            }
        }
        Ok(())
    }
}
pub(super) fn validate(p: &Program, w: &Work) -> Result<(), Error> {
    let mut owned = BTreeSet::new();
    roots(p, w, &mut |e| collect(e, &mut owned, w))?;
    for (i, b) in p.real_bindings.iter().enumerate() {
        w.step()?;
        if b.lifetime == ir::RealBindingLifetime::Call && !owned.contains(&i) {
            return Err(invalid("call binding has no syntactic owner"));
        }
    }
    let mut audit = Audit {
        p,
        w,
        function_body: false,
        active: BTreeSet::new(),
        done: BTreeSet::new(),
    };
    for state in &p.states {
        w.step()?;
        if let ir::StateInitial::Predicate(e) = &state.initial {
            structure::expression(e, p, None, &state.instance, w)?;
            audit.expression(e, &[], None, &state.instance)?;
        }
    }
    for q in &p.procedures {
        w.step()?;
        audit.steps(
            &q.body,
            &[],
            Some(q.procedure_id),
            &q.instance,
            None,
            &mut None,
        )?;
    }
    for e in &p.events {
        w.step()?;
        trigger_expressions(&e.trigger, w, &mut |v| {
            structure::expression(v, p, e.procedure_id, &e.origin.instance, w)?;
            audit.expression(v, &[], e.procedure_id, &e.origin.instance)
        })?;
        statements(&e.body, &mut |v| {
            audit.expression(v, &[], e.procedure_id, &e.origin.instance)
        })?;
    }
    for c in &p.contributions {
        w.step()?;
        audit.expression(&c.rhs, &[], None, &c.origin.instance)?;
    }
    for b in &p.step_bounds {
        w.step()?;
        audit.expression(&b.value, &[], None, &b.origin.instance)?;
        audit.expression(&b.active, &[], None, &b.origin.instance)?;
    }
    // Discover call-owning operator inputs before checking loose table rows.
    // An earlier math row may legitimately read a call owned by a later row.
    fn has_call(e: &E, w: &Work) -> Result<bool, Error> {
        w.step()?;
        if matches!(e, E::RealCall { .. }) {
            return Ok(true);
        }
        let mut found = false;
        children(e, &mut |e| {
            found |= has_call(e, w)?;
            Ok(())
        })?;
        Ok(found)
    }
    for o in &p.operators {
        w.step()?;
        if has_call(input(o), w)? {
            audit.expression(input(o), &[], None, &o.origin().instance)?;
        }
    }
    for (i, o) in p.operators.iter().enumerate() {
        w.debit(2, (audit.done.len() + 1) as u64)?;
        if !audit.done.iter().any(|(j, _, _, _)| *j == i) {
            audit.expression(input(o), &[], None, &o.origin().instance)?;
            if let OperatorSpec::Idt { reset: Some(e), .. } = o {
                audit.expression(e, &[], None, &o.origin().instance)?;
            }
        }
    }
    Ok(())
}
