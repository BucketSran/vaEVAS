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
        // A post-side certificate also cannot survive this earlier write.
        assert_eq!(
            conditions
                .select_with_source_sides(
                    &[0],
                    &[I { lo: -1., hi: 1. }],
                    &[],
                    &[I { lo: -1., hi: 1. }],
                    &[(0, 1)]
                )
                .err()
                .unwrap()
                .kind,
            "event_condition"
        );
    }

    #[test]
    fn empty_and_inactive_selections_preserve_results_but_reject_unknown_indices() {
        let origin = serde_json::json!({"source":"empty.va","line":1,"column":1,"instance":"M"});
        let program:Program=serde_json::from_value(serde_json::json!({
            "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","u"],"contributions":[],
            "states":[{"instance":"M","name":"q","kind":"real","initial":0}],
            "events":[{"origin":origin,"trigger":{"kind":"timer","start":0.5,"period":0,"enabled":true,"time_tolerance":0.001},
                "body":[{"kind":"if","relation":"gt","left":{"op":"state","state":0},"right":{"op":"affine","constant":0,"terms":[]},
                    "then_body":[],"else_body":[],"origin":origin}]}]
        })).unwrap();
        let mut conditions = Conditions::new(&program).unwrap();
        conditions.prepare(&program, &["u".into()]).unwrap();
        // No reachable event used these inputs/bounds before the optimization.
        assert!(conditions.select_at_roots(&[], &[], &[], &[]).unwrap() == Selection::default());
        conditions.restrict_events(&[false]);
        assert!(conditions.select_at_roots(&[0], &[], &[], &[]).unwrap() == Selection::default());
        assert_eq!(
            conditions
                .select_at_roots(&[1], &[], &[], &[])
                .err()
                .unwrap()
                .kind,
            "invalid_ir"
        );
    }
}

#[derive(Clone, PartialEq, Eq)]
pub(crate) enum SelectedStep {
    Assign(usize),
    Display(usize),
}

enum Step {
    ArrayWrite {
        index: Expression,
        first: i32,
        last: i32,
        start: usize,
        predicate: usize,
        origin: Origin,
    },
    Loop {
        initialize: Vec<Step>,
        predicate: usize,
        body: Vec<Step>,
        update: Vec<Step>,
        origin: Origin,
    },
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
    numeric: bool,
    network_states: std::collections::BTreeSet<usize>,
}

pub(crate) struct Conditions {
    bodies: Vec<Vec<Step>>,
    predicates: Vec<Predicate>,
    bounds: Option<GuardBounds>,
    // Exact zero-set certificates, indexed by calendar leaf, not event body.
    root_predicates: Vec<Vec<usize>>,
    source_root_sides: Vec<Vec<(usize, i8)>>,
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
    numeric: bool,
    network_states: std::collections::BTreeSet<usize>,
}

fn compile(
    body: &[Statement],
    p: &Program,
    owner: &str,
    next: &mut usize,
    displays: &mut usize,
    predicates: &mut Vec<Predicate>,
    general: bool,
) -> Result<Vec<Step>, Error> {
    body.iter()
        .map(|statement| match statement {
            Statement::ArrayWrite {
                states,
                index,
                first,
                last,
                origin,
                ..
            } => {
                if !general {
                    return Err(Error::new(
                        "unsupported_transient",
                        "array writes require an isolated observer event",
                    ));
                }
                crate::event_numeric::validate_array(
                    states, index, *first, *last, origin, p, owner,
                )?;
                let dependencies = crate::event_numeric::dependencies(index, p, owner)?;
                let predicate = predicates.len();
                predicates.push(Predicate {
                    event: usize::MAX,
                    relation: Relation::Ge,
                    expression: *index.clone(),
                    origin: origin.clone(),
                    dependencies,
                    numeric: true,
                });
                let start = *next;
                *next += states.len();
                Ok(Step::ArrayWrite {
                    index: *index.clone(),
                    first: *first,
                    last: *last,
                    start,
                    predicate,
                    origin: origin.clone(),
                })
            }
            Statement::Loop {
                initialize,
                relation,
                left,
                right,
                body,
                update,
                origin,
            } => {
                if !general {
                    return Err(Error::new(
                        "unsupported_loop",
                        "runtime loops require an isolated observer event",
                    ));
                }
                validate_loop(
                    initialize, *relation, left, right, body, update, origin, p, owner,
                )?;
                let init = compile(initialize, p, owner, next, displays, predicates, general)?;
                let wrapped = Statement::If {
                    relation: *relation,
                    left: left.clone(),
                    right: right.clone(),
                    then_body: body.clone(),
                    else_body: vec![],
                    origin: origin.clone(),
                };
                let mut compiled =
                    compile(&[wrapped], p, owner, next, displays, predicates, general)?;
                let Step::If { predicate, yes, .. } = compiled.pop().unwrap() else {
                    unreachable!()
                };
                let update = compile(update, p, owner, next, displays, predicates, general)?;
                Ok(Step::Loop {
                    initialize: init,
                    predicate,
                    body: yes,
                    update,
                    origin: origin.clone(),
                })
            }
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
                let ordinary = affine(&expression, p, owner);
                let numeric = ordinary.is_err() && general;
                let dependencies = if numeric {
                    crate::event_numeric::dependencies(&expression, p, owner)?
                } else {
                    ordinary?
                };
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
                    numeric,
                    network_states: Default::default(),
                });
                Ok(Step::If {
                    predicate,
                    yes: compile(then_body, p, owner, next, displays, predicates, general)?,
                    no: compile(else_body, p, owner, next, displays, predicates, general)?,
                })
            }
        })
        .collect()
}

impl Conditions {
    #[cfg(test)]
    pub(crate) fn new(program: &Program) -> Result<Self, Error> {
        Self::new_with_numeric(program, &vec![false; program.events.len()])
    }
    pub(crate) fn new_with_numeric(program: &Program, general: &[bool]) -> Result<Self, Error> {
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
                    general[event_index],
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
                            dependencies: if general[index] {
                                crate::event_numeric::dependencies(
                                    &a.rhs,
                                    program,
                                    &event.origin.instance,
                                )?
                            } else {
                                affine(&a.rhs, program, &event.origin.instance)?
                            },
                            numeric: general[index]
                                && affine(&a.rhs, program, &event.origin.instance).is_err(),
                            row: usize::MAX,
                            network_states: Default::default(),
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
            source_root_sides: Vec::new(),
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
                .chain(&predicate.network_states)
                .any(|&state| writers[state].is_some_and(|writer| writer != predicate.event))
            {
                return Err(Error::new("unsupported_cross", format!(
                    "simultaneous event condition reads state written by another selected block at {}",
                    predicate.origin.label())));
            }
        }
        for (event, indices) in &selection.actions {
            for &index in indices {
                if let Some(assignment) = self.assignments[*event].get(index) {
                    if assignment
                        .network_states
                        .iter()
                        .any(|&state| writers[state].is_some_and(|writer| writer != *event))
                    {
                        return Err(Error::new("unsupported_cross",
                            "simultaneous event condition replay reads a voltage affected by another selected block"));
                    }
                }
            }
        }
        Ok(())
    }

    /// Only unchanged external node forcing may be observed before the joint solve.
    /// All syntactic upstream state reads survive cancellation and current values.
    pub(crate) fn network_observers(
        &mut self,
        affected: &[bool],
        states: &[std::collections::BTreeSet<usize>],
        program: &Program,
    ) -> Result<Vec<bool>, Error> {
        let mut events = vec![false; self.active_events.len()];
        for predicate in &mut self.predicates {
            if !self.active_events[predicate.event] {
                continue;
            }
            for &node in &predicate.dependencies.node_dependencies {
                predicate.network_states.extend(&states[node]);
                events[predicate.event] |= affected[node];
            }
            if program.events[predicate.event]
                .assignments()
                .iter()
                .any(|a| predicate.network_states.contains(&a.state))
            {
                return Err(Error::new(
                    "unsupported_condition",
                    format!(
                        "event condition reads a voltage affected by its callback writes at {}",
                        predicate.origin.label()
                    ),
                ));
            }
        }
        for (event, assignments) in self.assignments.iter_mut().enumerate() {
            if !self.active_events[event] {
                continue;
            }
            for assignment in assignments.iter_mut().filter(|a| a.row != usize::MAX) {
                for &node in &assignment.dependencies.node_dependencies {
                    assignment.network_states.extend(&states[node]);
                    events[event] |= affected[node];
                }
                if program.events[event]
                    .assignments()
                    .iter()
                    .any(|a| assignment.network_states.contains(&a.state))
                {
                    return Err(Error::new(
                        "unsupported_condition",
                        "event condition replay reads a voltage affected by its callback writes",
                    ));
                }
            }
        }
        Ok(events)
    }

    pub(crate) fn has_active_event(&self, events: &[usize]) -> bool {
        events.iter().any(|&e| self.active_events[e])
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
        self.source_root_sides.clear();
        if self.enabled() {
            let mut expressions: Vec<_> = self
                .predicates
                .iter()
                .map(|p| (self.active_events[p.event] && !p.numeric).then_some(&p.expression))
                .collect();
            for assignment in self
                .assignments
                .iter_mut()
                .flatten()
                .filter(|a| a.row != usize::MAX)
            {
                assignment.row = expressions.len();
                expressions.push((!assignment.numeric).then_some(&assignment.expression));
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
                    let (matches, sides) = if let EventTrigger::Cross { guard, .. } = trigger {
                        let expressions: Vec<_> = std::iter::once(Some(guard))
                            .chain(self.predicates.iter().map(|p| {
                                (self.active_events[p.event] && !p.numeric).then_some(&p.expression)
                            }))
                            .collect();
                        GuardBounds::stateful_expressions(program, driven, &expressions)
                            .map(|bounds| {
                                (
                                    (0..self.predicates.len())
                                        .filter(|&i| bounds.same_zero_set(0, i + 1))
                                        .collect(),
                                    (0..self.predicates.len())
                                        .filter_map(|i| {
                                            bounds
                                                .source_zero_set_orientation(0, i + 1)
                                                .map(|sign| (i, sign))
                                        })
                                        .collect(),
                                )
                            })
                            .unwrap_or_default()
                    } else {
                        (vec![], vec![])
                    };
                    self.source_root_sides.push(sides);
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
        self.select_with_source_sides(events, inputs, fired_leaves, before_bounds, &[])
    }

    pub(crate) fn select_with_source_sides(
        &self,
        events: &[usize],
        inputs: &[I],
        fired_leaves: &[usize],
        before_bounds: &[I],
        source_sides: &[(usize, i8)],
    ) -> Result<Selection, Error> {
        if events
            .iter()
            .any(|&event| event >= self.active_events.len())
        {
            return Err(Error::new(
                "invalid_ir",
                "selected event index out of range",
            ));
        }
        if !events.iter().any(|&event| self.active_events[event]) {
            return Ok(Selection::default());
        }
        let mut values = self
            .bounds
            .as_ref()
            .map(|b| b.values(inputs))
            .unwrap_or_default();
        let mut at_root = vec![None; self.predicates.len()];
        for &leaf in fired_leaves {
            if let Some(predicates) = self.root_predicates.get(leaf) {
                for &predicate in predicates {
                    values[predicate] = I::ZERO;
                    at_root[predicate] = Some(0);
                }
            }
        }
        for &(leaf, side) in source_sides {
            if !matches!(side, -1 | 1) {
                return Err(Error::new("invalid_ir", "invalid source root side"));
            }
            if let Some(predicates) = self.source_root_sides.get(leaf) {
                for &(predicate, orientation) in predicates {
                    at_root[predicate] = Some(side * orientation);
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
            context: &Conditions,
            inputs: &[I],
            states: &mut [I],
            written: &mut [bool],
            at_root: &[Option<i8>],
            proof_attempts: &mut usize,
            loop_iterations: &mut usize,
        ) -> Result<(), Error> {
            let bounds = context.bounds.as_ref();
            let numeric_nodes: Vec<I> = std::iter::once(I::ZERO)
                .chain(inputs.iter().copied())
                .collect();
            for step in body {
                match step {
                    Step::ArrayWrite {
                        index,
                        first,
                        last,
                        start,
                        predicate,
                        origin,
                    } => {
                        let value = crate::event_numeric::checked_index(
                            crate::event_numeric::bounds(index, &numeric_nodes, states)?,
                            *first,
                            *last,
                            origin,
                        )?;
                        decisions.push((*predicate, true));
                        let slot = *start + (value.lo - f64::from(*first)) as usize;
                        walk(
                            &[Step::Assign(slot)],
                            values,
                            predicates,
                            actions,
                            decisions,
                            ordered,
                            assignments,
                            identity,
                            context,
                            inputs,
                            states,
                            written,
                            at_root,
                            proof_attempts,
                            loop_iterations,
                        )?;
                    }
                    Step::Loop {
                        initialize,
                        predicate,
                        body,
                        update,
                        origin,
                    } => {
                        walk(
                            initialize,
                            values,
                            predicates,
                            actions,
                            decisions,
                            ordered,
                            assignments,
                            identity,
                            context,
                            inputs,
                            states,
                            written,
                            at_root,
                            proof_attempts,
                            loop_iterations,
                        )?;
                        loop {
                            let p = &predicates[*predicate];
                            let value = if p.numeric {
                                crate::event_numeric::bounds(&p.expression, &numeric_nodes, states)?
                            } else {
                                bounds
                                    .unwrap()
                                    .value_with_states(*predicate, inputs, states)
                            };
                            let (yes, no) = crate::event_numeric::sign(p.relation, value);
                            if !value.finite() || !(yes || no) {
                                return Err(Error::new(
                                    "event_condition",
                                    format!(
                                        "cannot certify loop continuation at {}",
                                        origin.label()
                                    ),
                                ));
                            }
                            decisions.push((*predicate, yes));
                            if no {
                                break;
                            }
                            if *loop_iterations >= 4096 {
                                return Err(Error::new(
                                    "event_loop_budget",
                                    format!(
                                        "event exceeds 4096 total loop iterations at {}",
                                        origin.label()
                                    ),
                                ));
                            }
                            *loop_iterations += 1;
                            walk(
                                body,
                                values,
                                predicates,
                                actions,
                                decisions,
                                ordered,
                                assignments,
                                identity,
                                context,
                                inputs,
                                states,
                                written,
                                at_root,
                                proof_attempts,
                                loop_iterations,
                            )?;
                            walk(
                                update,
                                values,
                                predicates,
                                actions,
                                decisions,
                                ordered,
                                assignments,
                                identity,
                                context,
                                inputs,
                                states,
                                written,
                                at_root,
                                proof_attempts,
                                loop_iterations,
                            )?;
                        }
                    }
                    Step::Assign(index) => {
                        actions.push(*index);
                        ordered.push(SelectedStep::Assign(*index));
                        if let Some(a) = assignments.get(*index).filter(|a| a.row != usize::MAX) {
                            let value = if a.numeric {
                                crate::event_numeric::bounds(&a.expression, &numeric_nodes, states)?
                            } else {
                                bounds.unwrap().value_with_states(a.row, inputs, states)
                            };
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
                        let value = if p.numeric {
                            crate::event_numeric::bounds(&p.expression, &numeric_nodes, states)?
                        } else if p.dependencies.state_dependencies.is_empty() {
                            values[*predicate]
                        } else if at_root[*predicate] == Some(0)
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
                        let sign_proof = at_root[*predicate].filter(|_| {
                            !p.numeric
                                && p.dependencies
                                    .state_dependencies
                                    .iter()
                                    .all(|&state| !written[state])
                                && p.network_states.iter().all(|&state| !written[state])
                        });
                        let (yes_proved, no_proved) = if let Some(sign) = sign_proof {
                            let yes = match p.relation {
                                Relation::Lt => sign < 0,
                                Relation::Le => sign <= 0,
                                Relation::Gt => sign > 0,
                                Relation::Ge => sign >= 0,
                            };
                            (yes, !yes)
                        } else {
                            match p.relation {
                                Relation::Lt => (value.hi < 0.0, value.lo >= 0.0),
                                Relation::Le => (value.hi <= 0.0, value.lo > 0.0),
                                Relation::Gt => (value.lo > 0.0, value.hi <= 0.0),
                                Relation::Ge => (value.lo >= 0.0, value.hi < 0.0),
                            }
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
                                context,
                                inputs,
                                &mut ys,
                                &mut yw,
                                at_root,
                                proof_attempts,
                                loop_iterations,
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
                                context,
                                inputs,
                                &mut ns,
                                &mut nw,
                                at_root,
                                proof_attempts,
                                loop_iterations,
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
                            context,
                            inputs,
                            states,
                            written,
                            at_root,
                            proof_attempts,
                            loop_iterations,
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
            let mut loop_iterations = 0;
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
                self,
                inputs,
                &mut states,
                &mut written,
                &at_root,
                &mut proof_attempts,
                &mut loop_iterations,
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

#[allow(clippy::too_many_arguments)]
fn validate_loop(
    init: &[Statement],
    relation: Relation,
    left: &Expression,
    right: &Expression,
    body: &[Statement],
    update: &[Statement],
    origin: &Origin,
    p: &Program,
    owner: &str,
) -> Result<(), Error> {
    let invalid = || {
        Error::new(
            "invalid_ir",
            format!("invalid bounded integer loop at {}", origin.label()),
        )
    };
    if origin.instance != owner
        || origin.source.is_empty()
        || origin.line == 0
        || origin.column == 0
        || !origin.valid_expansion()
    {
        return Err(invalid());
    }
    let ([Statement::Assign(start)], [Statement::Assign(end)]) = (init, update) else {
        return Err(invalid());
    };
    if start.state != end.state
        || p.states
            .get(start.state)
            .is_none_or(|s| s.instance != owner || s.kind != crate::ir::StateKind::Integer)
        || !matches!(left,Expression::State{state} if *state==start.state)
    {
        return Err(invalid());
    }
    crate::event_numeric::validate(&start.rhs, p, owner)?;
    crate::event_numeric::validate(right, p, owner)?;
    if !crate::event_numeric::integral(&start.rhs, p) || !crate::event_numeric::integral(right, p) {
        return Err(invalid());
    }
    fn strip(e: &Expression) -> Expression {
        match e {
            Expression::CheckedInteger { value, .. } => strip(value),
            Expression::Add { left, right } => Expression::Add {
                left: Box::new(strip(left)),
                right: Box::new(strip(right)),
            },
            Expression::Multiply { left, right } => Expression::Multiply {
                left: Box::new(strip(left)),
                right: Box::new(strip(right)),
            },
            _ => e.clone(),
        }
    }
    let step = affine(&strip(&end.rhs), p, owner)?;
    if !step.constant.is_finite()
        || step.constant == 0.
        || step.constant.fract() != 0.
        || step.nodes.iter().any(|v| *v != 0.)
        || !step.operator_dependencies.is_empty()
        || step
            .states
            .iter()
            .enumerate()
            .any(|(i, v)| *v != if i == start.state { 1. } else { 0. })
        || matches!(relation, Relation::Lt | Relation::Le) != (step.constant > 0.)
    {
        return Err(invalid());
    }
    let event = crate::ir::Event {
        trigger: EventTrigger::FinalStep {},
        body: body.to_vec(),
        origin: origin.clone(),
    };
    if event.assignments().iter().any(|a| a.state == start.state) {
        return Err(invalid());
    }
    Ok(())
}
