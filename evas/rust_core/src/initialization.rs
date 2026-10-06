//! Resolve only external-input affine comparisons before any state/history exists.
use crate::events::check_state;
use crate::expression::{resolve_selects, validate};
use crate::interval::Interval as I;
use crate::ir::{check_schema_version, Error, Expression, Program, StateInitial, StateKind};
use std::collections::{HashMap, HashSet};

fn unsupported(message: impl Into<String>) -> Error {
    Error::new("unsupported_initialization", message)
}

/// Preserve structural dependencies, including zero coefficients/cancelled terms.
fn affine_degree(expression: &Expression, allowed: &HashSet<usize>) -> Result<u8, Error> {
    Ok(match expression {
        Expression::Affine { terms, .. } => {
            if terms.iter().any(|t| !allowed.contains(&t.node)) {
                return Err(unsupported(
                    "initial comparison depends on an undriven voltage",
                ));
            }
            u8::from(!terms.is_empty())
        }
        Expression::Add { left, right } => {
            affine_degree(left, allowed)?.max(affine_degree(right, allowed)?)
        }
        Expression::Multiply { left, right } => {
            let degree = affine_degree(left, allowed)? + affine_degree(right, allowed)?;
            if degree > 1 {
                return Err(unsupported(
                    "initial comparison must be structurally affine",
                ));
            }
            degree
        }
        Expression::Power { base, exponent } => {
            let degree = affine_degree(base, allowed)?;
            if degree > 0 && *exponent != 1 {
                return Err(unsupported(
                    "initial comparison must be structurally affine",
                ));
            }
            degree
        }
        _ => {
            return Err(unsupported(
                "initial comparison cannot read state, history, or another decision",
            ))
        }
    })
}

fn bit(expression: &Expression, expected: f64) -> bool {
    matches!(expression, Expression::Affine { constant, terms } if *constant == expected && terms.is_empty())
}

fn predicate(
    expression: &Expression,
    owner: &str,
    kind: &StateKind,
    nodes: &[I],
    allowed: &HashSet<usize>,
) -> Result<f64, Error> {
    let Expression::Select {
        left,
        right,
        then_value,
        else_value,
        origin,
        ..
    } = expression
    else {
        return Err(unsupported(
            "initial expression must be a single 0/1 comparison",
        ));
    };
    if *kind != StateKind::Real || !bit(then_value, 1.0) || !bit(else_value, 0.0) {
        return Err(unsupported(
            "initial comparison requires a real state and exact 1/0 arms",
        ));
    }
    if origin.instance != owner {
        return Err(Error::new(
            "invalid_ir",
            "initial predicate owner differs from state owner",
        ));
    }
    // Validate field values/indices first. Structural rejection remains independent
    // of the selected branch and of numerical cancellations.
    affine_degree(left, allowed)?;
    affine_degree(right, allowed)?;
    validate(expression, nodes.len())?;
    let result = resolve_selects(expression, nodes).map_err(|mut error| {
        if error.kind == "condition_precision" {
            error.kind = "initialization_precision";
            error.message = format!(
                "initial comparison cannot be certified at {}",
                origin.label()
            );
        }
        error
    })?;
    match result {
        Expression::Affine { constant, terms } if terms.is_empty() => Ok(constant),
        _ => Err(unsupported(
            "initial comparison did not resolve to a constant",
        )),
    }
}

pub(crate) fn resolve(
    mut program: Program,
    driven: &[String],
    inputs: &[I],
) -> Result<Program, Error> {
    check_schema_version(u64::from(program.schema_version))?;
    let indices: HashMap<_, _> = program
        .nodes
        .iter()
        .enumerate()
        .map(|(i, n)| (n.as_str(), i))
        .collect();
    if program.nodes.first().map(String::as_str) != Some("0")
        || indices.len() != program.nodes.len()
    {
        return Err(Error::new(
            "invalid_ir",
            "invalid initialization node table",
        ));
    }
    if driven.len() != inputs.len() {
        return Err(Error::new(
            "invalid_inputs",
            "initialization input dimension mismatch",
        ));
    }
    let mut allowed = HashSet::from([0]);
    let mut nodes = vec![I::ZERO; program.nodes.len()];
    for (name, &input) in driven.iter().zip(inputs) {
        let Some(&index) = indices.get(name.as_str()) else {
            return Err(Error::new("invalid_inputs", "unknown driven node"));
        };
        if index == 0 || !allowed.insert(index) || !input.finite() || input.lo > input.hi {
            return Err(Error::new("invalid_inputs", "invalid initialization input"));
        }
        nodes[index] = input;
    }
    // Collect the entire candidate before changing even this owned program.
    // No EventModel, operator history, calendar, Frame or trace has been created.
    let values = program
        .states
        .iter()
        .map(|state| {
            let value = match &state.initial {
                StateInitial::Constant(value) => *value,
                StateInitial::Predicate(expression) => {
                    predicate(expression, &state.instance, &state.kind, &nodes, &allowed).map_err(
                        |mut error| {
                            error
                                .message
                                .push_str(&format!(" for {}:{}", state.instance, state.name));
                            error
                        },
                    )?
                }
            };
            check_state(value, &state.kind)?;
            Ok(value)
        })
        .collect::<Result<Vec<_>, Error>>()?;
    for (state, value) in program.states.iter_mut().zip(values) {
        state.initial = value.into();
    }
    Ok(program)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ir::{Origin, Relation, State, Term};

    fn predicate_program() -> Program {
        let expression = Expression::Select {
            relation: Relation::Gt,
            left: Box::new(Expression::Affine {
                constant: 0.,
                terms: vec![Term {
                    node: 1,
                    coefficient: 1.,
                }],
            }),
            right: Box::new(Expression::Affine {
                constant: 0.65,
                terms: vec![],
            }),
            then_value: Box::new(Expression::Affine {
                constant: 1.,
                terms: vec![],
            }),
            else_value: Box::new(Expression::Affine {
                constant: 0.,
                terms: vec![],
            }),
            origin: Origin {
                source: "initial.va".into(),
                line: 1,
                column: 2,
                instance: "dut".into(),
                expansion: vec![],
            },
        };
        let mut program: Program = serde_json::from_value(serde_json::json!({
            "schema_version": crate::ir::SCHEMA_VERSION, "nodes": ["0","u","y"], "contributions": []
        }))
        .unwrap();
        program.states.push(State {
            instance: "dut".into(),
            name: "q".into(),
            kind: StateKind::Real,
            initial: StateInitial::Predicate(expression),
        });
        program
    }

    #[test]
    fn uncertain_initialization_returns_before_any_model_or_commit_and_can_retry() {
        let original = predicate_program();
        let driven = vec!["u".into()];
        let error = resolve(
            original.clone(),
            &driven,
            &[I {
                lo: 0.64999,
                hi: 0.65001,
            }],
        )
        .unwrap_err();
        assert_eq!(error.kind, "initialization_precision");
        assert!(error.message.contains("initial.va:1:2"));
        assert!(error.message.contains("dut:q"));
        assert!(matches!(
            original.states[0].initial,
            StateInitial::Predicate(_)
        ));
        let resolved = resolve(original.clone(), &driven, &[I::point(0.9)]).unwrap();
        assert_eq!(resolved.states[0].initial.constant().unwrap(), 1.);
        let again = resolve(original, &driven, &[I::point(0.1)]).unwrap();
        assert_eq!(again.states[0].initial.constant().unwrap(), 0.);
    }

    #[test]
    fn original_exact_tie_and_affine_cancellation_use_exact_predicate_math() {
        let driven = vec!["u".into()];
        for relation in [Relation::Gt, Relation::Ge, Relation::Lt, Relation::Le] {
            let mut p = predicate_program();
            let StateInitial::Predicate(Expression::Select {
                relation: r, left, ..
            }) = &mut p.states[0].initial
            else {
                panic!()
            };
            *r = relation;
            // 2*u - u is exactly u at the original binary64 input.
            *left = Box::new(Expression::Add {
                left: Box::new(Expression::Affine {
                    constant: 0.,
                    terms: vec![Term {
                        node: 1,
                        coefficient: 2.,
                    }],
                }),
                right: Box::new(Expression::Affine {
                    constant: 0.,
                    terms: vec![Term {
                        node: 1,
                        coefficient: -1.,
                    }],
                }),
            });
            let answer = resolve(p, &driven, &[I::point(0.65)]).unwrap().states[0]
                .initial
                .constant()
                .unwrap();
            assert_eq!(
                answer,
                if matches!(relation, Relation::Ge | Relation::Le) {
                    1.
                } else {
                    0.
                }
            );
        }
    }

    #[test]
    fn cancelled_undriven_dependencies_and_non_predicate_payload_are_rejected() {
        let mut p = predicate_program();
        let StateInitial::Predicate(Expression::Select { left, .. }) = &mut p.states[0].initial
        else {
            panic!()
        };
        *left = Box::new(Expression::Affine {
            constant: 1.,
            terms: vec![Term {
                node: 2,
                coefficient: 0.,
            }],
        });
        assert_eq!(
            resolve(p, &["u".into()], &[I::point(0.9)])
                .unwrap_err()
                .kind,
            "unsupported_initialization"
        );
        let mut p = predicate_program();
        p.states[0].initial = StateInitial::Predicate(Expression::Affine {
            constant: 1.,
            terms: vec![],
        });
        assert_eq!(
            resolve(p, &["u".into()], &[I::point(0.9)])
                .unwrap_err()
                .kind,
            "unsupported_initialization"
        );
    }
}
