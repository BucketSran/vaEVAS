//! Resolve certified zero-time voltage comparisons before any state/history exists.
use crate::events::check_state;
use crate::expression::{resolve_selects, validate};
use crate::interval::Interval as I;
use crate::ir::{check_schema_version, Error, Expression, Program, StateKind};
use std::collections::{HashMap, HashSet};

#[path = "initialization_nodes.rs"]
mod initial_nodes;

fn unsupported(message: impl Into<String>) -> Error {
    Error::new("unsupported_initialization", message)
}

/// Preserve structural dependencies, including zero coefficients/cancelled terms.
fn affine_degree(expression: &Expression, allowed: &HashSet<usize>) -> Result<u8, Error> {
    Ok(match expression {
        Expression::RealBoundary { value, .. } | Expression::Forcing { value, .. } => {
            affine_degree(value, allowed)?
        }
        Expression::RealBinary {
            operation,
            left,
            right,
            ..
        } => {
            use crate::ir::RealOperation::{Add, Divide, Multiply, Subtract};
            match operation {
                Add | Subtract => {
                    affine_degree(left, allowed)?.max(affine_degree(right, allowed)?)
                }
                Multiply => {
                    let degree = affine_degree(left, allowed)? + affine_degree(right, allowed)?;
                    if degree > 1 {
                        return Err(unsupported(
                            "initial comparison must be structurally affine",
                        ));
                    }
                    degree
                }
                Divide => {
                    if affine_degree(right, allowed)? != 0 {
                        return Err(unsupported(
                            "initial comparison must be structurally affine",
                        ));
                    }
                    affine_degree(left, allowed)?
                }
            }
        }
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

// Procedural initialization is compiled to a source-order expression. Runtime
// checks every arm before selecting, and accepts only a deterministic value.
fn predicate(
    expression: &Expression,
    owner: &str,
    kind: &StateKind,
    nodes: &[I],
    allowed: &HashSet<usize>,
) -> Result<f64, Error> {
    fn check(e: &Expression, owner: &str, allowed: &HashSet<usize>) -> Result<u8, Error> {
        Ok(match e {
            Expression::Select {
                left,
                right,
                then_value,
                else_value,
                origin,
                ..
            } => {
                if origin.instance != owner || !origin.valid_expansion() {
                    return Err(Error::new("invalid_ir", "invalid initial expression owner"));
                }
                for predicate in [left, right] {
                    check(predicate, owner, allowed)?;
                }
                check(then_value, owner, allowed)?.max(check(else_value, owner, allowed)?)
            }
            Expression::Add { left, right } => {
                check(left, owner, allowed)?.max(check(right, owner, allowed)?)
            }
            Expression::Multiply { left, right } => {
                let degree = check(left, owner, allowed)? + check(right, owner, allowed)?;
                if degree > 1 {
                    return Err(unsupported(
                        "initial expression must be structurally affine",
                    ));
                }
                degree
            }
            _ => affine_degree(e, allowed)?,
        })
    }
    let degree = check(expression, owner, allowed)?;
    if matches!(kind, StateKind::Integer) && degree != 0 {
        return Err(unsupported(
            "integer initialization cannot implicitly sample a real voltage",
        ));
    }
    validate(expression, nodes.len())?;
    let result = resolve_selects(expression, nodes).map_err(|mut error| {
        if error.kind == "condition_precision" {
            error.kind = "initialization_precision";
        }
        error
    })?;
    // State.initial and every downstream history use an exact binary64 value.
    // Propagate original input enclosures; a nominal evaluation is not proof.
    fn enclosure(e: &Expression, nodes: &[I]) -> Result<I, Error> {
        Ok(match e {
            Expression::RealBoundary { value, .. } | Expression::Forcing { value, .. } => {
                enclosure(value, nodes)?
            }
            Expression::Affine { constant, terms } => {
                terms.iter().fold(I::point(*constant), |value, term| {
                    value + I::point(term.coefficient) * nodes[term.node]
                })
            }
            Expression::Add { left, right } => enclosure(left, nodes)? + enclosure(right, nodes)?,
            Expression::Multiply { left, right } => {
                enclosure(left, nodes)? * enclosure(right, nodes)?
            }
            Expression::Power { base, exponent } => {
                let base = enclosure(base, nodes)?;
                (0..*exponent).fold(I::ONE, |value, _| value * base)
            }
            _ => return Err(unsupported("unsupported selected initial expression")),
        })
    }
    let bounds = enclosure(&result, nodes)?;
    if !bounds.finite() || bounds.lo != bounds.hi {
        return Err(Error::new(
            "initialization_precision",
            "initial value is not finite and point-certified",
        ));
    }
    Ok(bounds.lo)
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
    let values = initial_nodes::resolve(&program, nodes, allowed)?;
    for (state, value) in program.states.iter_mut().zip(values) {
        state.initial = value.into();
    }
    Ok(program)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ir::{Origin, Relation, State, StateInitial, Term};

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
    fn late_voltage_dependency_failure_does_not_publish_prior_initial_values() {
        let mut original = predicate_program();
        let mut second = original.states[0].clone();
        second.name = "later".into();
        let StateInitial::Predicate(Expression::Select { left, .. }) = &mut second.initial else {
            unreachable!()
        };
        **left = Expression::Affine {
            constant: 0.,
            terms: vec![Term {
                node: 2,
                coefficient: 1.,
            }],
        };
        original.states.push(second);
        let error = resolve(original.clone(), &["u".into()], &[I::point(0.9)]).unwrap_err();
        assert_eq!(error.kind, "unsupported_initialization");
        assert!(error.message.contains("dut:later"));
        assert!(original
            .states
            .iter()
            .all(|s| matches!(s.initial, StateInitial::Predicate(_))));
        let recovered = resolve(
            original,
            &["u".into(), "y".into()],
            &[I::point(0.9), I::point(0.1)],
        )
        .unwrap();
        assert_eq!(recovered.states[0].initial.constant().unwrap(), 1.);
        assert_eq!(recovered.states[1].initial.constant().unwrap(), 0.);
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
            **left = Expression::Add {
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
            };
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
    fn cancelled_undriven_dependency_is_rejected_and_constant_payload_is_exact() {
        let mut p = predicate_program();
        let StateInitial::Predicate(Expression::Select { left, .. }) = &mut p.states[0].initial
        else {
            panic!()
        };
        **left = Expression::Affine {
            constant: 1.,
            terms: vec![Term {
                node: 2,
                coefficient: 0.,
            }],
        };
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
        let resolved = resolve(p, &["u".into()], &[I::point(0.9)]).unwrap();
        assert_eq!(resolved.states[0].initial.constant().unwrap(), 1.);
    }

    #[test]
    fn sampled_initial_values_are_candidate_local_and_retry_after_late_failure() {
        let mut original = predicate_program();
        original.states[0].initial = StateInitial::Predicate(Expression::Affine {
            constant: 0.125,
            terms: vec![Term {
                node: 1,
                coefficient: 0.5,
            }],
        });
        let mut later = original.states[0].clone();
        later.instance = "other".into();
        later.name = "sample".into();
        later.initial = StateInitial::Predicate(Expression::Affine {
            constant: 0.,
            terms: vec![Term {
                node: 2,
                coefficient: 1.,
            }],
        });
        original.states.push(later);
        let inputs = ["u".into(), "y".into()];
        // First state can be certified before the second state fails. Nothing
        // from this candidate is installed in the reusable source program.
        let error = resolve(
            original.clone(),
            &inputs,
            &[I::point(1.), I { lo: 1., hi: 2. }],
        )
        .unwrap_err();
        assert_eq!(error.kind, "initialization_precision");
        assert!(error.message.contains("other:sample"));
        assert!(original
            .states
            .iter()
            .all(|s| matches!(s.initial, StateInitial::Predicate(_))));
        let first = resolve(original.clone(), &inputs, &[I::point(1.), I::point(0.25)]).unwrap();
        assert_eq!(first.states[0].initial.constant().unwrap(), 0.625);
        assert_eq!(first.states[1].initial.constant().unwrap(), 0.25);
        let second = resolve(original, &inputs, &[I::point(2.), I::point(0.5)]).unwrap();
        assert_eq!(second.states[0].initial.constant().unwrap(), 1.125);
        assert_eq!(second.states[1].initial.constant().unwrap(), 0.5);
    }

    #[test]
    fn sampling_refuses_nonrepresentable_sums_and_all_arm_nonlinearity() {
        let mut p = predicate_program();
        p.states[0].initial = StateInitial::Predicate(Expression::Affine {
            constant: 0.2,
            terms: vec![Term {
                node: 1,
                coefficient: 1.,
            }],
        });
        // Exact binary64 0.1 + exact binary64 0.2 is not a binary64 point.
        assert_eq!(
            resolve(p, &["u".into()], &[I::point(0.1)])
                .unwrap_err()
                .kind,
            "initialization_precision"
        );
        let mut p = predicate_program();
        let StateInitial::Predicate(Expression::Select { else_value, .. }) =
            &mut p.states[0].initial
        else {
            unreachable!()
        };
        let voltage = Expression::Affine {
            constant: 0.,
            terms: vec![Term {
                node: 1,
                coefficient: 1.,
            }],
        };
        **else_value = Expression::Multiply {
            left: Box::new(voltage.clone()),
            right: Box::new(voltage),
        };
        // The inactive branch must retain its structural validity obligation.
        assert_eq!(
            resolve(p, &["u".into()], &[I::point(1.)]).unwrap_err().kind,
            "unsupported_initialization"
        );
    }

    #[test]
    fn selected_voltage_arms_remain_exact_and_integer_sampling_is_refused() {
        let mut p = predicate_program();
        let StateInitial::Predicate(Expression::Select { then_value, .. }) =
            &mut p.states[0].initial
        else {
            unreachable!()
        };
        **then_value = Expression::Affine {
            constant: -0.25,
            terms: vec![Term {
                node: 1,
                coefficient: 1.,
            }],
        };
        let selected = resolve(p.clone(), &["u".into()], &[I::point(1.)]).unwrap();
        assert_eq!(selected.states[0].initial.constant().unwrap(), 0.75);
        p.states[0].kind = StateKind::Integer;
        assert_eq!(
            resolve(p, &["u".into()], &[I::point(1.25)])
                .unwrap_err()
                .kind,
            "unsupported_initialization"
        );
    }

    #[test]
    fn internal_samples_require_the_complete_original_voltage_closure() {
        let mut p = predicate_program();
        p.states[0].initial = StateInitial::Predicate(Expression::Affine {
            constant: 0.,
            terms: vec![Term {
                node: 2,
                coefficient: 1.,
            }],
        });
        let contribution = serde_json::json!({
            "branch":{"instance":"dut","local_positive":"y","local_negative":"0","kind":"voltage"},
            "positive":2,"negative":0,
            "rhs":{"op":"affine","constant":0.5,"terms":[]},
            "origin":{"source":"initial.va","line":1,"column":2,"instance":"dut"}
        });
        p.contributions
            .push(serde_json::from_value(contribution.clone()).unwrap());
        let resolved = resolve(p.clone(), &["u".into()], &[I::point(1.)]).unwrap();
        assert_eq!(resolved.states[0].initial.constant().unwrap(), 0.5);
        // The independent 0.5 term can seed q, but the complete same-branch
        // equation y = 0.5 + q contradicts q = y. Never publish that seed.
        let mut feedback = contribution;
        feedback["rhs"] = serde_json::json!({"op":"state","state":0});
        p.contributions
            .push(serde_json::from_value(feedback).unwrap());
        assert_eq!(
            resolve(p, &["u".into()], &[I::point(1.)]).unwrap_err().kind,
            "unsupported_initialization"
        );
    }
}
