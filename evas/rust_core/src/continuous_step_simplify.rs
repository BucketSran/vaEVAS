//! Remove a mesh-only condition from a private history program only after
//! proving every possible active cap is no tighter than the existing max step.
//! The original runtime program, dependencies and accepted-frame checks remain.
use super::*;

fn enclose(e: &Expression, nodes: &[I], states: &[I]) -> Option<I> {
    let value = match e {
        Expression::IntegerPrimitive { .. }
        | Expression::ArrayRead { .. }
        | Expression::CheckedInteger { .. }
        | Expression::CheckedIndex { .. }
        | Expression::EventMath { .. } => return None,
        Expression::Affine { constant, terms } => {
            terms.iter().try_fold(I::point(*constant), |sum, term| {
                Some(sum + I::point(term.coefficient) * *nodes.get(term.node)?)
            })?
        }
        Expression::State { state } => *states.get(*state)?,
        Expression::Operator { .. } => return None,
        Expression::Add { left, right } => {
            enclose(left, nodes, states)? + enclose(right, nodes, states)?
        }
        Expression::Multiply { left, right } => {
            enclose(left, nodes, states)? * enclose(right, nodes, states)?
        }
        Expression::Divide { left, right } => {
            let a = enclose(left, nodes, states)?;
            let b = enclose(right, nodes, states)?;
            if b.lo <= 0. && b.hi >= 0. {
                return None;
            }
            a / b
        }
        Expression::Power { base, exponent } => {
            let b = enclose(base, nodes, states)?;
            if *exponent > 32 {
                return None;
            }
            (0..*exponent).fold(I::ONE, |v, _| v * b)
        }
        Expression::Select {
            left,
            right,
            then_value,
            else_value,
            ..
        } => {
            // Both predicates and both arms must have valid finite domains.
            // No representative branch or correlated-square assumption.
            enclose(left, nodes, states)?;
            enclose(right, nodes, states)?;
            enclose(then_value, nodes, states)?.hull(enclose(else_value, nodes, states)?)
        }
    };
    value.finite().then_some(value)
}

pub(super) fn program(context: &Context, parameters: &[I]) -> Result<Program, Error> {
    let original = context.program.as_ref();
    let mut result = original.clone();
    if original.step_bounds.is_empty() {
        return Ok(result);
    }
    // Retain all ownership, origin and expression validation before making a
    // private optimization; zero coefficients do not hide dependencies.
    crate::step_bounds::Bounds::new(original)?;
    let Ok((inputs, _)) = context.trajectory.range(I {
        lo: 0.,
        hi: context.trajectory.config.stop,
    }) else {
        return Ok(result);
    };
    let driven: Vec<_> = context
        .driven
        .iter()
        .map(|name| original.nodes.iter().position(|n| n == name).unwrap())
        .collect();
    let mut nodes = vec![I::ZERO; original.nodes.len()];
    for (&n, &v) in driven.iter().zip(&inputs) {
        nodes[n] = v;
    }
    let max_step = context.trajectory.config.max_step;
    for bound in &mut result.step_bounds {
        validate(
            &bound.active,
            original,
            &context.driven,
            &bound.origin.instance,
        )?;
        validate(
            &bound.value,
            original,
            &context.driven,
            &bound.origin.instance,
        )?;
        let mut direct = true;
        for e in [&bound.active, &bound.value] {
            let (n, _, o) =
                crate::continuous::integral_dependency_edges(e, original, &bound.origin.instance)?;
            direct &= o.is_empty() && n.iter().all(|n| *n == 0 || driven.contains(n));
        }
        if !direct {
            continue;
        }
        let Some(_active) = enclose(&bound.active, &nodes, parameters) else {
            continue;
        };
        let Some(value) = enclose(&bound.value, &nodes, parameters) else {
            continue;
        };
        if value.lo >= max_step && max_step > 0. && max_step.is_finite() {
            // Only a redundant cap can lose its activation condition without
            // forcing smaller steps throughout an otherwise inactive epoch.
            // Tighter caps retain their original condition and physical cuts.
            bound.active = Expression::Affine {
                constant: 1.,
                terms: vec![],
            };
            bound.value = Expression::Affine {
                constant: value.lo.min(max_step),
                terms: vec![],
            };
        }
    }
    Ok(result)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::{json, Value};
    fn constant(v: f64) -> Value {
        json!({"op":"affine","constant":v,"terms":[]})
    }
    fn input() -> Value {
        json!({"op":"affine","constant":0.,"terms":[{"node":1,"coefficient":1.}]})
    }
    fn select(a: Value, b: Value) -> Value {
        json!({"op":"select","relation":"gt","left":input(),"right":constant(0.5),
            "then_value":a,"else_value":b,"origin":origin()})
    }
    fn origin() -> Value {
        json!({"source":"cap.va","instance":"dut","line":1,"column":1})
    }
    fn context(value: Value) -> Context {
        let p:Program=serde_json::from_value(json!({"schema_version":crate::ir::SCHEMA_VERSION,
            "nodes":["0","u","y"],"states":[{"instance":"dut","name":"q","kind":"real","initial":1.}],
            "events":[],"operators":[],"contributions":[],
            "step_bounds":[{"active":select(constant(1.),constant(0.)),"value":value,"origin":origin()}]})).unwrap();
        let t: crate::ir::TransientInputs =
            serde_json::from_value(json!({"pwl":[[[0.,0.],[1.,1.]]],
            "output_times":[0.,1.],"stop":1.,"max_step":0.125}))
            .unwrap();
        Context {
            program: Arc::new(p),
            trajectory: Trajectory::new(t, 1).unwrap(),
            driven: vec!["u".to_owned()],
            force_integrals: false,
            detached_timed: false,
            live_parameters: None,
            time_proofs: Default::default(),
        }
    }
    #[test]
    fn redundant_conditional_cap_is_private_and_epoch_specific() {
        let c = context(json!({"op":"state","state":0}));
        let before = serde_json::to_string(c.program.as_ref()).unwrap();
        let rewritten = program(&c, &[I::point(0.25)]).unwrap();
        assert_eq!(
            rewritten.step_bounds[0].active,
            serde_json::from_value(constant(1.)).unwrap()
        );
        assert_eq!(
            rewritten.step_bounds[0].value,
            serde_json::from_value(constant(0.125)).unwrap()
        );
        let tighter = program(&c, &[I::point(0.0625)]).unwrap();
        assert_eq!(
            tighter.step_bounds[0].active,
            c.program.step_bounds[0].active
        );
        assert_eq!(tighter.step_bounds[0].value, c.program.step_bounds[0].value);
        assert_eq!(before, serde_json::to_string(c.program.as_ref()).unwrap());
    }
    #[test]
    fn all_values_and_predicate_domains_must_be_valid() {
        for value in [
            constant(-1.),
            constant(0.),
            json!({"op":"divide","left":constant(1.),"right":constant(0.)}),
            json!({"op":"affine","constant":1.,"terms":[{"node":2,"coefficient":0.}]}),
        ] {
            let c = context(value);
            let after = program(&c, &[I::ONE]).unwrap();
            assert_eq!(after.step_bounds[0].value, c.program.step_bounds[0].value);
        }
        let c = context(select(constant(0.25), constant(0.0625)));
        let tighter = program(&c, &[I::ONE]).unwrap();
        assert_eq!(
            tighter.step_bounds[0].active,
            c.program.step_bounds[0].active
        );
        assert_eq!(tighter.step_bounds[0].value, c.program.step_bounds[0].value);
        let c = context(select(constant(0.25), constant(0.5)));
        assert_ne!(
            program(&c, &[I::ONE]).unwrap().step_bounds[0].value,
            c.program.step_bounds[0].value
        );
    }
    #[test]
    fn nonfinite_and_uncertain_division_do_not_prove_a_cap() {
        let divide = Expression::Divide {
            left: Box::new(serde_json::from_value(constant(1.)).unwrap()),
            right: Box::new(Expression::State { state: 0 }),
        };
        assert!(enclose(&divide, &[I::ZERO], &[I { lo: -1., hi: 1. }]).is_none());
        let nonfinite = Expression::Affine {
            constant: f64::INFINITY,
            terms: vec![],
        };
        assert!(enclose(&nonfinite, &[], &[]).is_none());
    }
}
