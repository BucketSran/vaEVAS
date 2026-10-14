//! Select reachable event-body paths using certified input enclosures.
//! State predicates see accepted state and prior selected assignments; assignments settle jointly
//! with the voltage equations. No accepted simulation history is stored here.
use crate::event_accuracy::GuardBounds;
use crate::events::{affine, AffineState};
use crate::interval::Interval as I;
use crate::ir::{Error, EventTrigger, Expression, Origin, Program, Relation, Statement};

#[derive(Clone, Default, PartialEq, Eq)]
pub(crate) struct Selection {
    pub(crate) actions: Vec<(usize, Vec<usize>)>,
    pub(crate) ordered_steps: Vec<(usize, Vec<SelectedStep>)>,
    // Retain all predicate reads, including certified alternative arms.
    // An ambiguous equivalent choice records both possible directions.
    pub(crate) decisions: Vec<(usize, bool)>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn prior_write_invalidates_root_identity_even_when_state_interval_is_unchanged() {
        let origin =
            serde_json::json!({"source":"ordered.va","line":1,"column":1,"instance":"dut"});
        let guard = serde_json::json!({"op":"add",
            "left":{"op":"affine","constant":0.0,"terms":[{"node":1,"coefficient":1.0}]},
            "right":{"op":"multiply","left":{"op":"affine","constant":-1.0,"terms":[]},
                "right":{"op":"state","state":0}}});
        let mut program: Program = serde_json::from_value(serde_json::json!({
            "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","u"],"contributions":[],
            "states":[{"instance":"dut","name":"q","kind":"real","initial":0.0}],
            "events":[{"origin":origin,"trigger":{"kind":"cross","guard":guard,
                "direction":1,"time_tolerance":0.001,"expression_tolerance":0.001},
                "body":[{"kind":"assign","state":0,"rhs":{"op":"multiply",
                    "left":{"op":"affine","constant":-1.0,"terms":[]},
                    "right":{"op":"state","state":0}}},
                    {"kind":"if","relation":"gt","left":guard,
                     "right":{"op":"affine","constant":0.0,"terms":[]},
                     "then_body":[],"else_body":[],"origin":origin}]}]
        }))
        .unwrap();
        let mut conditions = Conditions::new(&program).unwrap();
        conditions.prepare(&program, &["u".to_string()]).unwrap();
        let noop = conditions
            .select_at_roots(
                &[0],
                &[I { lo: -1.0, hi: 1.0 }],
                &[0],
                &[I { lo: -1.0, hi: 1.0 }],
            )
            .unwrap();
        // The unchanged original Program is valid through both-arm equivalence,
        // not through an invalid reuse of the pre-write root identity.
        assert_eq!(noop.decisions, vec![(0, true), (0, false)]);
        let Statement::If {
            then_body,
            else_body,
            ..
        } = &mut program.events[0].body[1]
        else {
            panic!("fixture condition")
        };
        *then_body = serde_json::from_value(serde_json::json!([{"kind":"assign","state":0,"rhs":{"op":"affine","constant":1.0,"terms":[]}}])).unwrap();
        *else_body = serde_json::from_value(serde_json::json!([{"kind":"assign","state":0,"rhs":{"op":"affine","constant":2.0,"terms":[]}}])).unwrap();
        let mut conditions = Conditions::new(&program).unwrap();
        conditions.prepare(&program, &["u".to_string()]).unwrap();
        let error = conditions
            .select_at_roots(
                &[0],
                &[I { lo: -1.0, hi: 1.0 }],
                &[0],
                &[I { lo: -1.0, hi: 1.0 }],
            )
            .err()
            .expect("same interval is not proof that q=-q preserves the old value");
        assert_eq!(error.kind, "event_condition");
    }
}

#[derive(Clone, PartialEq, Eq)]
pub(crate) enum SelectedStep {
    Assign(usize),
    Display(usize),
}

enum Step {
    Assign(usize),
    Display(usize),
    If {
        predicate: usize,
        yes: Vec<Step>,
        no: Vec<Step>,
    },
}

struct Predicate {
    event: usize,
    relation: Relation,
    expression: Expression,
    origin: Origin,
    dependencies: AffineState,
}

pub(crate) struct Conditions {
    bodies: Vec<Vec<Step>>,
    predicates: Vec<Predicate>,
    bounds: Option<GuardBounds>,
    // Exact zero-set certificates, indexed by calendar leaf, not event body.
    root_predicates: Vec<Vec<usize>>,
    assignments: Vec<Vec<AssignmentBounds>>,
    action_identity: Vec<Vec<ActionIdentity>>,
    stateful_events: Vec<bool>,
    state_count: usize,
    active_events: Vec<bool>,
}

const MAX_BRANCH_PROOF_ATTEMPTS: usize = 64;

#[derive(PartialEq, Eq)]
struct ActionIdentity {
    state: usize,
    // Canonical serialization preserves every original expression
    // field, including +0.0 versus -0.0. Point values are not identity.
    rhs: Vec<u8>,
}

struct AssignmentBounds {
    state: usize,
    expression: Expression,
    dependencies: AffineState,
    row: usize,
}

fn compile(
    body: &[Statement],
    p: &Program,
    owner: &str,
    next: &mut usize,
    displays: &mut usize,
    predicates: &mut Vec<Predicate>,
) -> Result<Vec<Step>, Error> {
    body.iter()
        .map(|statement| match statement {
            Statement::Assign(_) => {
                let index = *next;
                *next += 1;
                Ok(Step::Assign(index))
            }
            Statement::Display { .. } => {
                let index = *displays;
                *displays += 1;
                Ok(Step::Display(index))
            }
            Statement::If {
                relation,
                left,
                right,
                then_body,
                else_body,
                origin,
            } => {
                if origin.instance != owner
                    || origin.source.is_empty()
                    || origin.line == 0
                    || origin.column == 0
                {
                    return Err(Error::new("invalid_ir", "invalid condition origin"));
                }
                let expression = Expression::Add {
                    left: left.clone(),
                    right: Box::new(Expression::Multiply {
                        left: Box::new(Expression::Affine {
                            constant: -1.0,
                            terms: vec![],
                        }),
                        right: right.clone(),
                    }),
                };
                let dependencies = affine(&expression, p, owner)?;
                if !dependencies.operator_dependencies.is_empty() {
                    return Err(Error::new(
                        "unsupported_condition",
                        format!(
                            "event condition cannot depend on operators at {}",
                            origin.label()
                        ),
                    ));
                }
                let predicate = predicates.len();
                predicates.push(Predicate {
                    event: usize::MAX,
                    relation: *relation,
                    expression,
                    origin: origin.clone(),
                    dependencies,
                });
                Ok(Step::If {
                    predicate,
                    yes: compile(then_body, p, owner, next, displays, predicates)?,
                    no: compile(else_body, p, owner, next, displays, predicates)?,
                })
            }
        })
        .collect()
}

impl Conditions {
    pub(crate) fn new(program: &Program) -> Result<Self, Error> {
        let mut predicates = Vec::new();
        let mut stateful_events = Vec::new();
        let mut state_references = Vec::new();
        let bodies = program
            .events
            .iter()
            .enumerate()
            .map(|(event_index, event)| {
                let start = predicates.len();
                let body = compile(
                    &event.body,
                    program,
                    &event.origin.instance,
                    &mut 0,
                    &mut 0,
                    &mut predicates,
                )?;
                for predicate in &mut predicates[start..] {
                    predicate.event = event_index;
                }
                stateful_events.push(
                    predicates[start..]
                        .iter()
                        .any(|p| !p.dependencies.state_dependencies.is_empty()),
                );
                state_references.push(
                    predicates[start..]
                        .iter()
                        .flat_map(|p| p.dependencies.state_dependencies.iter().copied())
                        .collect::<std::collections::BTreeSet<_>>(),
                );
                Ok(body)
            })
            .collect::<Result<_, _>>()?;
        let assignments = program
            .events
            .iter()
            .enumerate()
            .map(|(index, event)| {
                if !stateful_events[index] {
                    return Ok(Vec::new());
                }
                let mut assignments = event
                    .assignments()
                    .into_iter()
                    .map(|a| {
                        Ok(AssignmentBounds {
                            state: a.state,
                            expression: a.rhs.clone(),
                            dependencies: affine(&a.rhs, program, &event.origin.instance)?,
                            row: usize::MAX,
                        })
                    })
                    .collect::<Result<Vec<_>, Error>>()?;
                // Only updates capable of reaching a predicate need replay bounds.
                // Sampling an unrelated operator output still settles normally.
                let mut references = state_references[index].clone();
                loop {
                    let previous = references.len();
                    for a in &mut assignments {
                        if references.contains(&a.state) {
                            a.row = 0;
                            references.extend(&a.dependencies.state_dependencies);
                        }
                    }
                    if references.len() == previous {
                        break;
                    }
                }
                Ok(assignments)
            })
            .collect::<Result<Vec<_>, Error>>()?;
        // Keep every original assignment, independently of replay-row pruning.
        let action_identity = program
            .events
            .iter()
            .map(|event| {
                event
                    .assignments()
                    .iter()
                    .map(|assignment| {
                        Ok(ActionIdentity {
                            state: assignment.state,
                            rhs: serde_json::to_vec(&assignment.rhs).map_err(|_| {
                                Error::new("invalid_ir", "cannot retain event assignment identity")
                            })?,
                        })
                    })
                    .collect::<Result<Vec<_>, Error>>()
            })
            .collect::<Result<Vec<_>, Error>>()?;
        Ok(Self {
            bodies,
            predicates,
            bounds: None,
            root_predicates: Vec::new(),
            assignments,
            action_identity,
            stateful_events,
            state_count: program.states.len(),
            active_events: vec![true; program.events.len()],
        })
    }

    /// Preserve predicate/action IDs while selecting only the assigned stage.
    pub(crate) fn restrict_events(&mut self, active: &[bool]) {
        self.active_events = active.to_vec();
        for (event, body) in self.bodies.iter_mut().enumerate() {
            if !active[event] {
                body.clear();
            }
        }
        for (event, assignments) in self.assignments.iter_mut().enumerate() {
            if !active[event] {
                for assignment in assignments {
                    assignment.row = usize::MAX;
                }
            }
        }
    }

    pub(crate) fn enabled(&self) -> bool {
        !self.predicates.is_empty()
    }

    /// Executed predicates and alternative proof predicates read state. Other blocks may
    /// write the same state at different event times, but not in this batch.
    pub(crate) fn check_selection_readers(
        &self,
        selection: &Selection,
        writers: &[Option<usize>],
    ) -> Result<(), Error> {
        for &(index, _) in &selection.decisions {
            let predicate = &self.predicates[index];
            if predicate
                .dependencies
                .state_dependencies
                .iter()
                .any(|&state| writers[state].is_some_and(|writer| writer != predicate.event))
            {
                return Err(Error::new("unsupported_cross", format!(
                    "simultaneous event condition reads state written by another selected block at {}",
                    predicate.origin.label())));
            }
        }
        Ok(())
    }

    pub(crate) fn check_dependencies(&self, affected: &[bool]) -> Result<(), Error> {
        for predicate in self
            .predicates
            .iter()
            .filter(|p| self.active_events[p.event])
        {
            if predicate
                .dependencies
                .node_dependencies
                .iter()
                .any(|&node| affected[node])
            {
                return Err(Error::new(
                    "unsupported_condition",
                    format!(
                        "event condition may depend on state through the voltage network at {}",
                        predicate.origin.label()
                    ),
                ));
            }
        }
        // A state condition cannot replay an assignment whose RHS needs the
        // post-event joint electrical solution. Such a replay would read old
        // voltages and choose a potentially different branch.
        for assignment in self
            .assignments
            .iter()
            .flatten()
            .filter(|a| a.row != usize::MAX)
        {
            if !assignment.dependencies.operator_dependencies.is_empty()
                || assignment
                    .dependencies
                    .node_dependencies
                    .iter()
                    .any(|&node| affected[node])
            {
                return Err(Error::new("unsupported_condition",
                    "state-dependent event condition needs an assignment with state-independent voltage inputs"));
            }
        }
        Ok(())
    }

    pub(crate) fn prepare(&mut self, program: &Program, driven: &[String]) -> Result<(), Error> {
        self.root_predicates.clear();
        if self.enabled() {
            let mut expressions: Vec<_> = self
                .predicates
                .iter()
                .map(|p| self.active_events[p.event].then_some(&p.expression))
                .collect();
            for assignment in self
                .assignments
                .iter_mut()
                .flatten()
                .filter(|a| a.row != usize::MAX)
            {
                assignment.row = expressions.len();
                expressions.push(Some(&assignment.expression));
            }
            self.bounds = Some(
                GuardBounds::stateful_expressions(program, driven, &expressions)
                    .map_err(|e| Error::new("event_condition", e.message))?,
            );
            // A root enclosure contains times other than the actual root.
            // Preserve g(tau)=0 when a predicate has the same proven zero set.
            // Projection must be exact; rounded matching is never a proof.
            for event in &program.events {
                for trigger in event.trigger.leaves()? {
                    let matches = if let EventTrigger::Cross { guard, .. } = trigger {
                        let expressions: Vec<_> = std::iter::once(Some(guard))
                            .chain(
                                self.predicates
                                    .iter()
                                    .map(|p| self.active_events[p.event].then_some(&p.expression)),
                            )
                            .collect();
                        GuardBounds::stateful_expressions(program, driven, &expressions)
                            .map(|bounds| {
                                (0..self.predicates.len())
                                    .filter(|&i| bounds.same_zero_set(0, i + 1))
                                    .collect()
                            })
                            .unwrap_or_default()
                    } else {
                        vec![]
                    };
                    self.root_predicates.push(matches);
                }
            }
        }
        Ok(())
    }

    pub(crate) fn select(&self, events: &[usize], inputs: &[I]) -> Result<Selection, Error> {
        self.select_at_roots(events, inputs, &[], &[])
    }

    pub(crate) fn select_at_roots(
        &self,
        events: &[usize],
        inputs: &[I],
        fired_leaves: &[usize],
        before_bounds: &[I],
    ) -> Result<Selection, Error> {
        let mut values = self
            .bounds
            .as_ref()
            .map(|b| b.values(inputs))
            .unwrap_or_default();
        let mut at_root = vec![false; self.predicates.len()];
        for &leaf in fired_leaves {
            if let Some(predicates) = self.root_predicates.get(leaf) {
                for &predicate in predicates {
                    values[predicate] = I::ZERO;
                    at_root[predicate] = true;
                }
            }
        }
        #[allow(clippy::too_many_arguments)] // Keep the recursive event-selection context explicit.
        fn walk(
            body: &[Step],
            values: &[I],
            predicates: &[Predicate],
            actions: &mut Vec<usize>,
            decisions: &mut Vec<(usize, bool)>,
            ordered: &mut Vec<SelectedStep>,
            assignments: &[AssignmentBounds],
            identity: &[ActionIdentity],
            bounds: Option<&GuardBounds>,
            inputs: &[I],
            states: &mut [I],
            written: &mut [bool],
            at_root: &[bool],
            proof_attempts: &mut usize,
        ) -> Result<(), Error> {
            for step in body {
                match step {
                    Step::Assign(index) => {
                        actions.push(*index);
                        ordered.push(SelectedStep::Assign(*index));
                        if let Some(a) = assignments.get(*index).filter(|a| a.row != usize::MAX) {
                            let value = bounds.unwrap().value_with_states(a.row, inputs, states);
                            if !value.finite() {
                                return Err(Error::new(
                                    "event_condition",
                                    "nonfinite prior-assignment bounds",
                                ));
                            }
                            states[a.state] = value;
                            written[a.state] = true;
                        }
                    }
                    Step::Display(index) => ordered.push(SelectedStep::Display(*index)),
                    Step::If { predicate, yes, no } => {
                        let p = &predicates[*predicate];
                        let value = if p.dependencies.state_dependencies.is_empty() {
                            values[*predicate]
                        } else if at_root[*predicate]
                            && p.dependencies
                                .state_dependencies
                                .iter()
                                .all(|&state| !written[state])
                        {
                            I::ZERO
                        } else {
                            bounds
                                .unwrap()
                                .value_with_states(*predicate, inputs, states)
                        };
                        let (yes_proved, no_proved) = match p.relation {
                            Relation::Lt => (value.hi < 0.0, value.lo >= 0.0),
                            Relation::Le => (value.hi <= 0.0, value.lo > 0.0),
                            Relation::Gt => (value.lo > 0.0, value.hi <= 0.0),
                            Relation::Ge => (value.lo >= 0.0, value.hi < 0.0),
                        };
                        if !value.finite() || !(yes_proved || no_proved) {
                            let original = Error::new("event_condition", format!("cannot certify {:?} condition at {}: difference in [{:e}, {:e}]", p.relation, p.origin.label(), value.lo, value.hi));
                            if !value.finite() || *proof_attempts > MAX_BRANCH_PROOF_ATTEMPTS - 2 {
                                return Err(original);
                            }
                            *proof_attempts += 2;
                            crate::diagnostics::counter("event_branch_proof_attempts", 2);
                            // Both alternatives are checked against the same original
                            // enclosures. No sign assumption narrows a sampled value.
                            let mut ya = Vec::new();
                            let mut na = Vec::new();
                            let mut yd = Vec::new();
                            let mut nd = Vec::new();
                            let mut yo = Vec::new();
                            let mut no_ordered = Vec::new();
                            let mut ys = states.to_vec();
                            let mut ns = states.to_vec();
                            let mut yw = written.to_vec();
                            let mut nw = written.to_vec();
                            let yr = walk(
                                yes,
                                values,
                                predicates,
                                &mut ya,
                                &mut yd,
                                &mut yo,
                                assignments,
                                identity,
                                bounds,
                                inputs,
                                &mut ys,
                                &mut yw,
                                at_root,
                                proof_attempts,
                            );
                            let nr = walk(
                                no,
                                values,
                                predicates,
                                &mut na,
                                &mut nd,
                                &mut no_ordered,
                                assignments,
                                identity,
                                bounds,
                                inputs,
                                &mut ns,
                                &mut nw,
                                at_root,
                                proof_attempts,
                            );
                            // Never turn an invalid domain/IR/resource diagnostic
                            // into an alternative certificate or a cache miss.
                            for result in [&yr, &nr] {
                                if let Err(error) = result {
                                    if error.kind != "event_condition" {
                                        return Err(Error {
                                            kind: error.kind,
                                            message: error.message.clone(),
                                            sample: error.sample,
                                        });
                                    }
                                }
                            }
                            let same_writes = ya.len() == na.len()
                                && ya.iter().zip(&na).all(|(&a, &b)| {
                                    identity
                                        .get(a)
                                        .zip(identity.get(b))
                                        .is_some_and(|(a, b)| a == b)
                                });
                            let no_display = yo
                                .iter()
                                .chain(&no_ordered)
                                .all(|step| matches!(step, SelectedStep::Assign(_)));
                            let same_bounds = ys.len() == ns.len()
                                && ys.iter().zip(&ns).all(|(a, b)| {
                                    a.lo.to_bits() == b.lo.to_bits()
                                        && a.hi.to_bits() == b.hi.to_bits()
                                });
                            if yr.is_err()
                                || nr.is_err()
                                || !same_writes
                                || !no_display
                                || !same_bounds
                                || yw != nw
                            {
                                return Err(original);
                            }
                            states.copy_from_slice(&ys);
                            written.copy_from_slice(&yw);
                            actions.extend(ya);
                            ordered.extend(yo);
                            // The chosen writes are identical. Keep the reads from
                            // both proofs for writer checks and certificate identity.
                            decisions.extend([(*predicate, true), (*predicate, false)]);
                            decisions.extend(yd);
                            decisions.extend(nd);
                            crate::diagnostics::counter("event_equivalent_branch_proofs", 1);
                            continue;
                        }
                        decisions.push((*predicate, yes_proved));
                        walk(
                            if yes_proved { yes } else { no },
                            values,
                            predicates,
                            actions,
                            decisions,
                            ordered,
                            assignments,
                            identity,
                            bounds,
                            inputs,
                            states,
                            written,
                            at_root,
                            proof_attempts,
                        )?;
                    }
                }
            }
            Ok(())
        }
        let mut result = Selection::default();
        let mut proof_attempts = 0;
        for &event in events {
            if !self.active_events[event] {
                continue;
            }
            if self.stateful_events[event] && before_bounds.len() != self.state_count {
                return Err(Error::new(
                    "invalid_ir",
                    "event condition accepted state bounds length mismatch",
                ));
            }
            let mut actions = Vec::new();
            let mut ordered = Vec::new();
            let mut states = before_bounds.to_vec();
            let mut written = vec![false; self.state_count];
            walk(
                &self.bodies[event],
                &values,
                &self.predicates,
                &mut actions,
                &mut result.decisions,
                &mut ordered,
                &self.assignments[event],
                &self.action_identity[event],
                self.bounds.as_ref(),
                inputs,
                &mut states,
                &mut written,
                &at_root,
                &mut proof_attempts,
            )?;
            result.actions.push((event, actions));
            result.ordered_steps.push((event, ordered));
        }
        Ok(result)
    }
}

#[cfg(test)]
mod branch_review_tests {
    use super::*;
    use serde_json::json;
    fn c(v: f64) -> serde_json::Value {
        json!({"op":"affine","constant":v,"terms":[]})
    }
    fn model(counts: &[usize], writes: bool) -> crate::events::EventModel {
        let o = json!({"source":"branch_review.va","line":1,"column":1,"instance":"D"});
        let mut events = vec![];
        for &n in counts {
            let assign = if writes {
                json!([{"kind":"assign","state":0,"rhs":c(1.)}])
            } else {
                json!([])
            };
            let body:Vec<_>=(0..n).map(|_|json!({"kind":"if","relation":"ge","left":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]},"right":c(0.),"then_body":assign,"else_body":assign,"origin":o})).collect();
            events.push(json!({"origin":o,"trigger":{"kind":"timer","start":0.5,"period":0,"enabled":true,"time_tolerance":1e-9},"body":body}));
        }
        let p=serde_json::from_value(json!({"schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","u","y"],"states":[{"instance":"D","name":"q","kind":"real","initial":0}],"operators":[],"events":events,"contributions":[{"origin":o,"branch":{"instance":"D","local_positive":"out","local_negative":"ref","kind":"voltage"},"positive":2,"negative":0,"rhs":{"op":"state","state":0}}]})).unwrap();
        crate::events::EventModel::new(p, vec!["u".into()], crate::ir::Tolerances::default())
            .unwrap()
    }
    #[test]
    fn budget_is_shared_across_events_and_nonfinite_predicate_cannot_fork() {
        let m = model(&[16, 16], false);
        let (r, d) = crate::diagnostics::capture(Default::default(), || {
            m.conditions.select(&[0, 1], &[I { lo: -1., hi: 1. }])
        });
        assert!(r.is_ok());
        assert_eq!(d.counters["event_branch_proof_attempts"], 64);
        let m = model(&[16, 17], false);
        let (r, d) = crate::diagnostics::capture(Default::default(), || {
            m.conditions.select(&[0, 1], &[I { lo: -1., hi: 1. }])
        });
        assert_eq!(r.err().unwrap().kind, "event_condition");
        assert_eq!(d.counters["event_branch_proof_attempts"], 64);
        let m = model(&[1], true);
        let (r, d) = crate::diagnostics::capture(Default::default(), || {
            m.conditions.select(
                &[0],
                &[I {
                    lo: f64::NEG_INFINITY,
                    hi: f64::INFINITY,
                }],
            )
        });
        assert_eq!(r.err().unwrap().kind, "event_condition");
        assert!(!d.counters.contains_key("event_branch_proof_attempts"));
    }
}
