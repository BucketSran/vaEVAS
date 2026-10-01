//! Select reachable event-body paths using certified input enclosures.
//! Predicates are state independent; selected assignments still settle jointly
//! with the voltage equations. No accepted simulation history is stored here.
use crate::event_accuracy::GuardBounds;
use crate::events::{affine, AffineState};
use crate::interval::Interval as I;
use crate::ir::{Error, EventTrigger, Expression, Origin, Program, Relation, Statement};

#[derive(Clone, Default, PartialEq, Eq)]
pub(crate) struct Selection {
    pub(crate) actions: Vec<(usize, Vec<usize>)>,
    // Include decisions even when both arms contain no assignments.
    decisions: Vec<(usize, bool)>,
}

enum Step {
    Assign(usize),
    If {
        predicate: usize,
        yes: Vec<Step>,
        no: Vec<Step>,
    },
}

struct Predicate {
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
}

fn compile(
    body: &[Statement],
    p: &Program,
    owner: &str,
    next: &mut usize,
    predicates: &mut Vec<Predicate>,
) -> Result<Vec<Step>, Error> {
    body.iter()
        .map(|statement| match statement {
            Statement::Assign(_) => {
                let index = *next;
                *next += 1;
                Ok(Step::Assign(index))
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
                if !dependencies.state_dependencies.is_empty()
                    || !dependencies.operator_dependencies.is_empty()
                {
                    return Err(Error::new(
                        "unsupported_condition",
                        format!(
                            "event condition must be state independent at {}",
                            origin.label()
                        ),
                    ));
                }
                let predicate = predicates.len();
                predicates.push(Predicate {
                    relation: *relation,
                    expression,
                    origin: origin.clone(),
                    dependencies,
                });
                Ok(Step::If {
                    predicate,
                    yes: compile(then_body, p, owner, next, predicates)?,
                    no: compile(else_body, p, owner, next, predicates)?,
                })
            }
        })
        .collect()
}

impl Conditions {
    pub(crate) fn new(program: &Program) -> Result<Self, Error> {
        let mut predicates = Vec::new();
        let bodies = program
            .events
            .iter()
            .map(|event| {
                compile(
                    &event.body,
                    program,
                    &event.origin.instance,
                    &mut 0,
                    &mut predicates,
                )
            })
            .collect::<Result<_, _>>()?;
        Ok(Self {
            bodies,
            predicates,
            bounds: None,
            root_predicates: Vec::new(),
        })
    }

    pub(crate) fn enabled(&self) -> bool {
        !self.predicates.is_empty()
    }

    pub(crate) fn check_dependencies(&self, affected: &[bool]) -> Result<(), Error> {
        for predicate in &self.predicates {
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
        Ok(())
    }

    pub(crate) fn prepare(&mut self, program: &Program, driven: &[String]) -> Result<(), Error> {
        self.root_predicates.clear();
        if self.enabled() {
            let expressions: Vec<_> = self
                .predicates
                .iter()
                .map(|p| Some(&p.expression))
                .collect();
            self.bounds = Some(
                GuardBounds::expressions(program, driven, &expressions)
                    .map_err(|e| Error::new("event_condition", e.message))?,
            );
            // A root enclosure contains times other than the actual root.
            // Preserve g(tau)=0 when a predicate has the same proven zero set.
            // Projection must be exact; rounded matching is never a proof.
            for event in &program.events {
                for trigger in event.trigger.leaves()? {
                    let matches = if let EventTrigger::Cross { guard, .. } = trigger {
                        let expressions: Vec<_> = std::iter::once(Some(guard))
                            .chain(self.predicates.iter().map(|p| Some(&p.expression)))
                            .collect();
                        GuardBounds::expressions(program, driven, &expressions)
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
        self.select_at_roots(events, inputs, &[])
    }

    pub(crate) fn select_at_roots(
        &self,
        events: &[usize],
        inputs: &[I],
        fired_leaves: &[usize],
    ) -> Result<Selection, Error> {
        let mut values = self
            .bounds
            .as_ref()
            .map(|b| b.values(inputs))
            .unwrap_or_default();
        for &leaf in fired_leaves {
            if let Some(predicates) = self.root_predicates.get(leaf) {
                for &predicate in predicates {
                    values[predicate] = I::ZERO;
                }
            }
        }
        fn walk(
            body: &[Step],
            values: &[I],
            predicates: &[Predicate],
            actions: &mut Vec<usize>,
            decisions: &mut Vec<(usize, bool)>,
        ) -> Result<(), Error> {
            for step in body {
                match step {
                    Step::Assign(index) => actions.push(*index),
                    Step::If { predicate, yes, no } => {
                        let p = &predicates[*predicate];
                        let value = values[*predicate];
                        let (yes_proved, no_proved) = match p.relation {
                            Relation::Lt => (value.hi < 0.0, value.lo >= 0.0),
                            Relation::Le => (value.hi <= 0.0, value.lo > 0.0),
                            Relation::Gt => (value.lo > 0.0, value.hi <= 0.0),
                            Relation::Ge => (value.lo >= 0.0, value.hi < 0.0),
                        };
                        if !value.finite() || !(yes_proved || no_proved) {
                            return Err(Error::new("event_condition", format!("cannot certify {:?} condition at {}: difference in [{:e}, {:e}]", p.relation, p.origin.label(), value.lo, value.hi)));
                        }
                        decisions.push((*predicate, yes_proved));
                        walk(
                            if yes_proved { yes } else { no },
                            values,
                            predicates,
                            actions,
                            decisions,
                        )?;
                    }
                }
            }
            Ok(())
        }
        let mut result = Selection::default();
        for &event in events {
            let mut actions = Vec::new();
            walk(
                &self.bodies[event],
                &values,
                &self.predicates,
                &mut actions,
                &mut result.decisions,
            )?;
            result.actions.push((event, actions));
        }
        Ok(result)
    }
}
