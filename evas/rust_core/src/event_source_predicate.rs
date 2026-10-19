//! Eligibility for the old voltage-assigned contribution-predicate refusal.
//! Borrow the accepted timed operator's original source owner. This only proves
//! absence of unknown electrical feedback; settlement still certifies the mode.
use super::EventModel;
use crate::ir::{Expression as E, Statement};
use crate::pwl::Trajectory;
use crate::transition_source_plan::{ProofContext, Work};

pub(crate) type Binding<'a> = (&'a ProofContext, &'a Trajectory);

fn charge(work: &Work, amount: usize) -> Result<(), crate::ir::Error> {
    work.debit(2, amount as u64)?;
    crate::diagnostics::counter("source_predicate_qualification_work", amount);
    Ok(())
}

struct Audit<'a> {
    model: &'a EventModel,
    work: &'a Work,
    owner: &'a str,
}
impl Audit<'_> {
    fn input(&self, node: usize) -> Result<bool, crate::ir::Error> {
        charge(self.work, 1)?;
        if node == 0 {
            return Ok(true);
        }
        let Some(name) = self.model.program.nodes.get(node) else {
            return Ok(false);
        };
        // lib.rs supplies time as a driven transport column; it is not an
        // electrical input role, including in zero-weight and unselected trees.
        charge(self.work, 1 + name.len().min("$abstime".len()))?;
        if name == "$abstime" {
            return Ok(false);
        }
        let mut driven = false;
        for expected in &self.model.driven {
            charge(self.work, 1 + expected.len().min(name.len()))?;
            if expected == name {
                driven = true;
                break;
            }
        }
        if !driven {
            return Ok(false);
        }
        // A declared output/internal relation cannot become a physical source
        // merely because its net also appears in the supplied driven list.
        for contribution in &self.model.program.contributions {
            charge(self.work, 2)?;
            if contribution.positive == node || contribution.negative == node {
                return Ok(false);
            }
        }
        Ok(true)
    }

    fn source_state(&self, expression: &E) -> Result<bool, crate::ir::Error> {
        charge(self.work, 1)?;
        Ok(match expression {
            E::Affine { constant, terms } => {
                let mut valid = constant.is_finite();
                for term in terms {
                    charge(self.work, 2)?;
                    let source = self.input(term.node)?;
                    valid &= source && term.coefficient.is_finite();
                }
                valid
            }
            E::State { state } => {
                let Some(state) = self.model.program.states.get(*state) else {
                    return Ok(false);
                };
                charge(self.work, 1 + self.owner.len().min(state.instance.len()))?;
                state.instance == self.owner
            }
            E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
                let a = self.source_state(left)?;
                let b = self.source_state(right)?;
                a && b
            }
            E::Select {
                left,
                right,
                then_value,
                else_value,
                ..
            } => {
                let mut valid = true;
                for child in [left, right, then_value, else_value] {
                    valid &= self.source_state(child)?;
                }
                valid
            }
            // No new observer control, arithmetic operator or history role.
            _ => false,
        })
    }

    fn predicates(&self, expression: &E) -> Result<bool, crate::ir::Error> {
        charge(self.work, 1)?;
        Ok(match expression {
            E::Select {
                left,
                right,
                then_value,
                else_value,
                ..
            } => {
                let a = self.source_state(left)?;
                let b = self.source_state(right)?;
                let mut valid = a && b;
                for child in [left, right, then_value, else_value] {
                    valid &= self.predicates(child)?;
                }
                valid
            }
            E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
                let a = self.predicates(left)?;
                let b = self.predicates(right)?;
                a && b
            }
            E::Affine { .. } | E::State { .. } | E::Operator { .. } => true,
            _ => false,
        })
    }

    fn body(&self, statements: &[Statement]) -> Result<bool, crate::ir::Error> {
        let mut valid = true;
        for statement in statements {
            charge(self.work, 1)?;
            match statement {
                Statement::Assign(assignment) => {
                    valid &= self.source_state(&assignment.rhs)?;
                }
                Statement::If {
                    left,
                    right,
                    then_body,
                    else_body,
                    ..
                } => {
                    valid &= self.source_state(left)?;
                    valid &= self.source_state(right)?;
                    valid &= self.body(then_body)?;
                    valid &= self.body(else_body)?;
                }
                _ => valid = false,
            }
        }
        Ok(valid)
    }
}

pub(crate) fn qualify(
    model: &EventModel,
    event: usize,
    binding: Binding<'_>,
) -> Result<bool, crate::ir::Error> {
    let (source, trajectory) = binding;
    let work = source.borrow_work();
    charge(work, 0)?;
    crate::event_floor::check_provided_binding(source, &model.program, trajectory, &model.driven)?;
    charge(work, 2)?;
    if model.passive_events[event] {
        return Ok(false);
    }
    let valid = qualify_owner(model, &model.program.events[event].origin.instance, work)?;
    if valid {
        crate::diagnostics::counter("source_predicate_qualified_events", 1);
    }
    Ok(valid)
}

fn qualify_owner(model: &EventModel, owner: &str, work: &Work) -> Result<bool, crate::ir::Error> {
    let audit = Audit { model, work, owner };
    let mut valid = true;
    // Same-instance State references are safe only if every original writer
    // has an input-only source. Inspect initial and other callbacks as well,
    // including all guards and unselected arms; do not launder a held sample
    // of an unknown internal/output voltage through a later callback.
    for (index, original) in model.program.events.iter().enumerate() {
        charge(work, 1 + owner.len().min(original.origin.instance.len()))?;
        if original.origin.instance != owner {
            continue;
        }
        for &numeric in &model.numeric_actions[index] {
            charge(work, 1)?;
            valid &= !numeric;
        }
        valid &= audit.body(&original.body)?;
    }
    for contribution in &model.program.contributions {
        charge(work, 1)?;
        let local = Audit {
            model,
            work,
            owner: &contribution.origin.instance,
        };
        valid &= local.predicates(&contribution.rhs)?;
    }
    Ok(valid)
}

/// The point consumer gets no durable exemption. Recheck the immutable source
/// binding and complete original roles on the same request Work at each demand.
pub(crate) fn qualify_point(
    model: &EventModel,
    owner: &str,
    binding: Binding<'_>,
    left: &E,
    right: &E,
) -> Result<bool, crate::ir::Error> {
    let (source, trajectory) = binding;
    let work = source.borrow_work();
    charge(work, 0)?;
    crate::event_floor::check_provided_binding(source, &model.program, trajectory, &model.driven)?;
    let audit = Audit { model, work, owner };
    let mut valid = qualify_owner(model, owner, work)?;
    valid &= audit.source_state(left)?;
    valid &= audit.source_state(right)?;
    Ok(valid)
}
