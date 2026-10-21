//! Explicit nonlinear readout outputs.
//!
//! A grounded output `V(y) <+ f(...)` whose value nobody reads is a pure
//! function of the rest of the certified circuit at each observation. When
//! `f` contains a decision that the affine event machinery cannot represent
//! (for example a clamp of a product of an input and a held state or an
//! operator sample), the core program receives `V(y) <+ 0` and each held
//! state/operator leaf of `f` is exposed through a private ideal voltage node.
//! After the core run, every returned row evaluates the original `f` from the
//! certified node boxes. A decision is taken only when its predicate interval
//! has a proven sign; otherwise the enclosure is the hull of both arms, so no
//! branch is guessed. The final box must satisfy the original voltage
//! tolerance, and a division whose denominator box contains zero is refused.
use crate::interval::Interval as I;
use crate::ir::{
    BranchIdentity, Contribution, ContributionKind, Error, Expression as E, Program, Relation,
    Response, Term, Tolerances,
};
use std::collections::BTreeSet;

struct Output {
    node: usize,
    // V(node) = sign * value; the frontend may orient the branch either way.
    sign: f64,
    value: E,
}

pub(crate) struct Plan {
    original_nodes: usize,
    outputs: Vec<Output>,
}

fn scope(message: &str) -> Error {
    Error::new("unsupported_readout", message)
}

fn predicate_degree(e: &E) -> Option<u8> {
    match e {
        E::Affine { terms, .. } => Some(u8::from(!terms.is_empty())),
        E::State { .. } => Some(1),
        E::Add { left, right } => Some(predicate_degree(left)?.max(predicate_degree(right)?)),
        E::Multiply { left, right } => {
            let d = predicate_degree(left)? + predicate_degree(right)?;
            (d <= 1).then_some(d)
        }
        E::Power { base, exponent } => {
            let d = predicate_degree(base)?;
            (d == 0 || *exponent == 1).then_some(d)
        }
        E::Select {
            left,
            right,
            then_value,
            else_value,
            ..
        } => Some(
            predicate_degree(left)?
                .max(predicate_degree(right)?)
                .max(predicate_degree(then_value)?)
                .max(predicate_degree(else_value)?),
        ),
        _ => None,
    }
}

/// A contribution needs this route only when one of its decisions has a
/// predicate outside the existing affine contract. Others keep their path.
fn needs_readout(e: &E) -> bool {
    match e {
        E::Select {
            left,
            right,
            then_value,
            else_value,
            ..
        } => {
            predicate_degree(left).is_none()
                || predicate_degree(right).is_none()
                || [left, right, then_value, else_value]
                    .iter()
                    .any(|e| needs_readout(e))
        }
        E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
            needs_readout(left) || needs_readout(right)
        }
        E::Power { base, .. } => needs_readout(base),
        _ => false,
    }
}

/// A held state or operator sample anywhere in the tree.
fn has_leaf(e: &E) -> bool {
    match e {
        E::State { .. } | E::Operator { .. } => true,
        E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
            has_leaf(left) || has_leaf(right)
        }
        E::Power { base, .. } => has_leaf(base),
        E::Select {
            left,
            right,
            then_value,
            else_value,
            ..
        } => [left, right, then_value, else_value].iter().any(|e| has_leaf(e)),
        _ => false,
    }
}

/// A tree that reads at least one live circuit voltage.
fn live_node(e: &E) -> bool {
    match e {
        E::Affine { terms, .. } => !terms.is_empty(),
        E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
            live_node(left) || live_node(right)
        }
        E::Power { base, .. } => live_node(base),
        E::Select {
            left,
            right,
            then_value,
            else_value,
            ..
        } => [left, right, then_value, else_value].iter().any(|e| live_node(e)),
        _ => false,
    }
}

/// Predicate degree with held states and operator samples frozen as gains.
fn held_gain_degree(e: &E) -> Option<u8> {
    match e {
        E::Affine { terms, .. } => Some(u8::from(!terms.is_empty())),
        E::State { .. } | E::Operator { .. } => Some(0),
        E::Add { left, right } => Some(held_gain_degree(left)?.max(held_gain_degree(right)?)),
        E::Multiply { left, right } => {
            let d = held_gain_degree(left)? + held_gain_degree(right)?;
            (d <= 1).then_some(d)
        }
        E::Divide { left, right } => {
            let d = held_gain_degree(left)?;
            (held_gain_degree(right)? == 0).then_some(d)
        }
        E::Power { base, exponent } => {
            let d = held_gain_degree(base)?;
            (d == 0 || *exponent == 1).then_some(d)
        }
        E::Select {
            left,
            right,
            then_value,
            else_value,
            ..
        } => Some(
            held_gain_degree(left)?
                .max(held_gain_degree(right)?)
                .max(held_gain_degree(then_value)?)
                .max(held_gain_degree(else_value)?),
        ),
        _ => None,
    }
}

/// Shape 1 (held-gain decision): a nonaffine predicate coupling a held state
/// or operator sample with a live voltage that becomes affine once the held
/// leaves are frozen. Decisions over held values only (q*q>0) or over live
/// voltages only (V(a)*V(b)>0) are not this shape.
fn held_gain_decision(left: &E, right: &E) -> bool {
    (predicate_degree(left).is_none() || predicate_degree(right).is_none())
        && (has_leaf(left) || has_leaf(right))
        && (live_node(left) || live_node(right))
        && held_gain_degree(left).is_some()
        && held_gain_degree(right).is_some()
}

/// Every nonaffine decision in this value is a held-gain decision, and there
/// is at least one. `None` when a nonaffine decision has another shape.
fn held_gain_value(e: &E) -> Option<bool> {
    match e {
        E::Select {
            left,
            right,
            then_value,
            else_value,
            ..
        } => {
            let nonaffine = predicate_degree(left).is_none() || predicate_degree(right).is_none();
            if nonaffine && !held_gain_decision(left, right) {
                return None;
            }
            let mut any = nonaffine;
            for child in [left, right, then_value, else_value] {
                any |= held_gain_value(child)?;
            }
            Some(any)
        }
        E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
            Some(held_gain_value(left)? | held_gain_value(right)?)
        }
        E::Power { base, .. } => held_gain_value(base),
        _ => Some(false),
    }
}

/// Shape 2 (stateless algebraic instance): the contribution's instance owns no
/// state, event, operator or step bound and the value reads no held leaf, so
/// it is a pure function of live node voltages at each row.
fn stateless_owner(program: &Program, c: &Contribution) -> bool {
    let instance = &c.origin.instance;
    !has_leaf(&c.rhs)
        && *instance == c.branch.instance
        && program.states.iter().all(|s| s.instance != *instance)
        && program.events.iter().all(|e| e.origin.instance != *instance)
        && program
            .operators
            .iter()
            .all(|o| o.origin().instance != *instance)
        && program
            .step_bounds
            .iter()
            .all(|b| b.origin.instance != *instance)
}

/// Whether the row route owns this nonaffine decision output.
fn owned(program: &Program, c: &Contribution) -> bool {
    stateless_owner(program, c) || held_gain_value(&c.rhs) == Some(true)
}

fn structural(e: &E, nodes: &mut BTreeSet<usize>, depth: usize) -> Result<(), Error> {
    if depth > 256 {
        return Err(scope("readout expression is too deep"));
    }
    match e {
        E::Affine { constant, terms } => {
            if !constant.is_finite() || terms.iter().any(|t| !t.coefficient.is_finite()) {
                return Err(scope("readout constants must be finite"));
            }
            nodes.extend(terms.iter().map(|t| t.node));
        }
        E::State { .. } | E::Operator { .. } => {}
        E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
            structural(left, nodes, depth + 1)?;
            structural(right, nodes, depth + 1)?;
        }
        E::Power { base, exponent } => {
            if !(1..=32).contains(exponent) {
                return Err(scope("readout power exponent must be in [1,32]"));
            }
            structural(base, nodes, depth + 1)?;
        }
        E::Select {
            left,
            right,
            then_value,
            else_value,
            ..
        } => {
            for e in [left, right, then_value, else_value] {
                structural(e, nodes, depth + 1)?;
            }
        }
        _ => return Err(scope("readout values support only arithmetic decisions")),
    }
    Ok(())
}

/// Every node index referenced anywhere in a serialized IR value, including
/// zero-coefficient terms, inactive arms, guards, event bodies and operators.
fn referenced(v: &serde_json::Value, out: &mut BTreeSet<u64>) {
    match v {
        serde_json::Value::Object(m) => {
            if let (Some(n), Some(_)) =
                (m.get("node").and_then(|n| n.as_u64()), m.get("coefficient"))
            {
                out.insert(n);
            }
            for child in m.values() {
                referenced(child, out);
            }
        }
        serde_json::Value::Array(a) => {
            for child in a {
                referenced(child, out);
            }
        }
        _ => {}
    }
}

fn expose(e: &E, leaves: &mut Vec<E>, base: usize) -> E {
    match e {
        E::State { .. } | E::Operator { .. } => {
            let index = leaves.iter().position(|l| l == e).unwrap_or_else(|| {
                leaves.push(e.clone());
                leaves.len() - 1
            });
            E::Affine {
                constant: 0.,
                terms: vec![Term {
                    node: base + index,
                    coefficient: 1.,
                }],
            }
        }
        E::Add { left, right } => E::Add {
            left: Box::new(expose(left, leaves, base)),
            right: Box::new(expose(right, leaves, base)),
        },
        E::Multiply { left, right } => E::Multiply {
            left: Box::new(expose(left, leaves, base)),
            right: Box::new(expose(right, leaves, base)),
        },
        E::Divide { left, right } => E::Divide {
            left: Box::new(expose(left, leaves, base)),
            right: Box::new(expose(right, leaves, base)),
        },
        E::Power { base: b, exponent } => E::Power {
            base: Box::new(expose(b, leaves, base)),
            exponent: *exponent,
        },
        E::Select {
            relation,
            left,
            right,
            then_value,
            else_value,
            origin,
        } => E::Select {
            relation: *relation,
            left: Box::new(expose(left, leaves, base)),
            right: Box::new(expose(right, leaves, base)),
            then_value: Box::new(expose(then_value, leaves, base)),
            else_value: Box::new(expose(else_value, leaves, base)),
            origin: origin.clone(),
        },
        _ => e.clone(),
    }
}

impl Plan {
    /// Partition qualifying readout outputs. `None` leaves the request intact.
    pub(crate) fn split(program: &mut Program, driven: &[String]) -> Result<Option<Self>, Error> {
        // Only the two owned shapes engage this route; any other nonaffine
        // decision (for example V(a)*V(b)>0 beside held state, or q*q>0)
        // stays with the core program, which keeps its own refusal.
        let candidates: Vec<_> = (0..program.contributions.len())
            .filter(|&i| needs_readout(&program.contributions[i].rhs))
            .collect();
        if !candidates
            .iter()
            .any(|&i| owned(program, &program.contributions[i]))
        {
            return Ok(None);
        }
        let original_nodes = program.nodes.len();
        let mut reads = BTreeSet::new();
        let rest = serde_json::json!({
            "rhs": program.contributions.iter().map(|c| &c.rhs).collect::<Vec<_>>(),
            "events": &program.events,
            "operators": &program.operators,
            "step_bounds": &program.step_bounds,
        });
        referenced(
            &serde_json::to_value(&rest).map_err(|e| Error::new("invalid_ir", e.to_string()))?,
            &mut reads,
        );
        // A target is grounded, undriven, owned by exactly one contribution
        // and never read anywhere, including by any readout or its own value.
        let qualifies = |i: usize| -> Result<(), Error> {
            let c = &program.contributions[i];
            let target = c.positive.max(c.negative);
            if c.positive.min(c.negative) != 0
                || target == 0
                || target >= original_nodes
                || driven.contains(&program.nodes[target])
            {
                return Err(scope(
                    "nonlinear decision outputs require an undriven grounded voltage output",
                ));
            }
            if program
                .contributions
                .iter()
                .filter(|o| o.positive == target || o.negative == target)
                .count()
                != 1
            {
                return Err(scope("a nonlinear decision output cannot share its node"));
            }
            if reads.contains(&(target as u64)) {
                return Err(scope(
                    "a nonlinear decision output cannot be read by the circuit, events or itself",
                ));
            }
            let mut nodes = BTreeSet::new();
            structural(&c.rhs, &mut nodes, 0)?;
            if nodes.iter().any(|n| *n >= original_nodes) {
                return Err(scope("readout reads an unknown node"));
            }
            Ok(())
        };
        for &i in &candidates {
            qualifies(i)?;
            if !owned(program, &program.contributions[i]) {
                return Err(scope(
                    "a nonlinear decision output requires a held-gain decision or a stateless algebraic owner",
                ));
            }
        }
        // Once engaged, other unread decision outputs of the same request use
        // the same row evaluation instead of the affine event representation.
        let mut candidates: Vec<_> = (0..program.contributions.len())
            .filter(|&i| {
                candidates.contains(&i)
                    || crate::analog::has_select(&program.contributions[i].rhs)
                        && qualifies(i).is_ok()
            })
            .collect();
        candidates.sort_unstable();
        let mut outputs = Vec::new();
        for &i in &candidates {
            let base = program.nodes.len();
            let c = program.contributions[i].clone();
            let mut leaves = Vec::new();
            let value = expose(&c.rhs, &mut leaves, base);
            for (k, leaf) in leaves.into_iter().enumerate() {
                let name = format!("{}.__readout{}_{}", c.origin.instance, i, k);
                if program.nodes.contains(&name) {
                    return Err(scope("readout node name collision"));
                }
                program.nodes.push(name.clone());
                // Keep the branch's own ground binding and the sorted local
                // orientation used by assembly; flip the RHS with the branch.
                let ground = if c.positive == 0 {
                    &c.branch.local_positive
                } else {
                    &c.branch.local_negative
                };
                let local = format!("__readout{}_{}", i, k);
                let (local_positive, local_negative, positive, negative, rhs) = if *ground < local {
                    let negated = E::Multiply {
                        left: Box::new(E::Affine {
                            constant: -1.,
                            terms: vec![],
                        }),
                        right: Box::new(leaf),
                    };
                    (ground.clone(), local, 0, base + k, negated)
                } else {
                    (local, ground.clone(), base + k, 0, leaf)
                };
                program.contributions.push(Contribution {
                    branch: BranchIdentity {
                        instance: c.branch.instance.clone(),
                        local_positive,
                        local_negative,
                        kind: ContributionKind::Voltage,
                    },
                    positive,
                    negative,
                    rhs,
                    origin: c.origin.clone(),
                });
            }
            program.contributions[i].rhs = E::Affine {
                constant: 0.,
                terms: vec![],
            };
            let target = c.positive.max(c.negative);
            outputs.push(Output {
                node: target,
                sign: if c.positive == target { 1. } else { -1. },
                value,
            });
        }
        Ok(Some(Self {
            original_nodes,
            outputs,
        }))
    }

    pub(crate) fn apply(
        &self,
        response: &mut Response,
        tolerances: &Tolerances,
    ) -> Result<(), Error> {
        let width = response.nodes.len();
        if width < self.original_nodes {
            return Err(Error::new(
                "invalid_ir",
                "readout response lost original nodes",
            ));
        }
        for solution in &mut response.solutions {
            let bounds = solution.certified_voltage_bounds.as_ref().ok_or_else(|| {
                Error::new(
                    "waveform_accuracy",
                    "nonlinear decision output requires certified voltage bounds",
                )
            })?;
            if bounds.len() != width || solution.voltages.len() != width {
                return Err(Error::new("invalid_ir", "readout row width mismatch"));
            }
            let boxes: Vec<_> = bounds.iter().map(|b| I { lo: b[0], hi: b[1] }).collect();
            let mut results = Vec::new();
            for o in &self.outputs {
                let (value, bound) = evaluate(&o.value, &solution.voltages, &boxes)?;
                let (value, bound) = if o.sign < 0. {
                    (-value, -bound)
                } else {
                    (value, bound)
                };
                let bound = I {
                    lo: bound.lo.min(value),
                    hi: bound.hi.max(value),
                };
                if !value.is_finite() || !bound.finite() {
                    return Err(Error::new(
                        "nonfinite_arithmetic",
                        "nonlinear decision output is nonfinite",
                    ));
                }
                let error = (value - bound.lo).max(bound.hi - value);
                let allowed =
                    tolerances.absolute + tolerances.relative * value.abs().max(bound.magnitude());
                if error > allowed {
                    return Err(Error::new(
                        "waveform_accuracy",
                        "nonlinear decision output box exceeds original voltage tolerance",
                    ));
                }
                results.push((o.node, value, bound));
            }
            let bounds = solution.certified_voltage_bounds.as_mut().unwrap();
            for (node, value, bound) in results {
                solution.voltages[node] = value;
                bounds[node] = [bound.lo, bound.hi];
            }
            solution.voltages.truncate(self.original_nodes);
            bounds.truncate(self.original_nodes);
        }
        response.nodes.truncate(self.original_nodes);
        if let Some(evidence) = &mut response.observation_evidence {
            evidence.nodes.truncate(self.original_nodes);
            evidence.voltage_bounds_v = response
                .solutions
                .iter()
                .map(|s| s.certified_voltage_bounds.clone())
                .collect();
        }
        Ok(())
    }
}

fn sign(relation: Relation, d: I) -> (bool, bool) {
    match relation {
        Relation::Lt => (d.hi < 0., d.lo >= 0.),
        Relation::Le => (d.hi <= 0., d.lo > 0.),
        Relation::Gt => (d.lo > 0., d.hi <= 0.),
        Relation::Ge => (d.lo >= 0., d.hi < 0.),
    }
}

fn nominal_select(relation: Relation, a: f64, b: f64) -> bool {
    match relation {
        Relation::Lt => a < b,
        Relation::Le => a <= b,
        Relation::Gt => a > b,
        Relation::Ge => a >= b,
    }
}

/// Representative value and outward enclosure of one readout expression.
fn evaluate(e: &E, values: &[f64], boxes: &[I]) -> Result<(f64, I), Error> {
    let result = match e {
        E::Affine { constant, terms } => {
            let mut v = *constant;
            let mut b = I::point(*constant);
            for t in terms {
                v += t.coefficient * values[t.node];
                b = b + I::point(t.coefficient) * boxes[t.node];
            }
            (v, b)
        }
        E::Add { left, right } => {
            let (a, x) = evaluate(left, values, boxes)?;
            let (c, y) = evaluate(right, values, boxes)?;
            (a + c, x + y)
        }
        E::Multiply { left, right } => {
            let (a, x) = evaluate(left, values, boxes)?;
            let (c, y) = evaluate(right, values, boxes)?;
            (a * c, x * y)
        }
        E::Divide { left, right } => {
            let (a, x) = evaluate(left, values, boxes)?;
            let (c, y) = evaluate(right, values, boxes)?;
            if y.lo <= 0. && y.hi >= 0. {
                return Err(Error::new(
                    "nonfinite_arithmetic",
                    "readout division denominator interval contains zero",
                ));
            }
            (a / c, x / y)
        }
        E::Power { base, exponent } => {
            let (a, x) = evaluate(base, values, boxes)?;
            // `structural` admits only exponents 1..=32, so this guard is
            // defensive; x**0 is exactly 1 and must not fall through as x.
            if *exponent == 0 {
                (1., I::ONE)
            } else {
                let mut v = a;
                let mut b = x;
                for _ in 1..*exponent {
                    v *= a;
                    b = b * x;
                }
                (v, b)
            }
        }
        E::Select {
            relation,
            left,
            right,
            then_value,
            else_value,
            ..
        } => {
            let (a, x) = evaluate(left, values, boxes)?;
            let (c, y) = evaluate(right, values, boxes)?;
            let d = x - y;
            if !d.finite() {
                return Err(Error::new(
                    "nonfinite_arithmetic",
                    "readout predicate is nonfinite",
                ));
            }
            match sign(*relation, d) {
                (true, _) => evaluate(then_value, values, boxes)?,
                (_, true) => evaluate(else_value, values, boxes)?,
                _ => {
                    // Undecided: either arm may hold for the true inputs.
                    let (t, tb) = evaluate(then_value, values, boxes)?;
                    let (f, fb) = evaluate(else_value, values, boxes)?;
                    let v = if nominal_select(*relation, a, c) {
                        t
                    } else {
                        f
                    };
                    (v, tb.hull(fb))
                }
            }
        }
        _ => return Err(scope("unsupported readout expression")),
    };
    if !result.0.is_finite() || !result.1.finite() {
        return Err(Error::new(
            "nonfinite_arithmetic",
            "readout arithmetic is nonfinite",
        ));
    }
    Ok(result)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn expr(v: serde_json::Value) -> E {
        serde_json::from_value(v).unwrap()
    }
    fn node(n: usize) -> serde_json::Value {
        json!({"op":"affine","constant":0.,"terms":[{"node":n,"coefficient":1.}]})
    }
    fn constant(c: f64) -> serde_json::Value {
        json!({"op":"affine","constant":c,"terms":[]})
    }
    fn origin() -> serde_json::Value {
        json!({"source":"m.va","line":1,"column":1,"instance":"M"})
    }
    // min(1, V1*V2) as a decision on a product.
    fn clamp() -> E {
        let product = json!({"op":"multiply","left":node(1),"right":node(2)});
        expr(
            json!({"op":"select","relation":"gt","left":product,"right":constant(1.),
            "then_value":constant(1.),"else_value":product,"origin":origin()}),
        )
    }

    #[test]
    fn decided_predicates_select_one_arm() {
        let boxes = [I::ZERO, I::point(0.5), I { lo: 1.0, hi: 1.25 }];
        let (v, b) = evaluate(&clamp(), &[0., 0.5, 1.1], &boxes).unwrap();
        assert_eq!(v, 0.55);
        assert!(b.lo <= 0.5 && b.hi >= 0.625 && b.hi < 0.7);
    }

    #[test]
    fn straddling_predicate_encloses_both_arms_without_guessing() {
        // V1*V2 in [0.9, 1.1]: either arm is possible.
        let boxes = [I::ZERO, I::ONE, I { lo: 0.9, hi: 1.1 }];
        let (v, b) = evaluate(&clamp(), &[0., 1., 1.05], &boxes).unwrap();
        assert_eq!(v, 1.);
        assert!(b.lo <= 0.9 && b.hi >= 1.0);
        // A discontinuous decision with the same uncertain sign gives a hull
        // far wider than any voltage tolerance; apply() must refuse it.
        let step = expr(
            json!({"op":"select","relation":"gt","left":node(2),"right":constant(1.),
            "then_value":constant(1.),"else_value":constant(0.),"origin":origin()}),
        );
        let (_, b) = evaluate(&step, &[0., 1., 1.05], &boxes).unwrap();
        assert!(b.lo <= 0. && b.hi >= 1.);
    }

    #[test]
    fn zero_containing_denominator_is_refused() {
        let quotient = expr(json!({"op":"divide","left":constant(1.),"right":node(1)}));
        let error =
            evaluate(&quotient, &[0., 0.1], &[I::ZERO, I { lo: -0.1, hi: 0.1 }]).unwrap_err();
        assert_eq!(error.kind, "nonfinite_arithmetic");
    }

    #[test]
    fn power_zero_is_one() {
        let zero_power = expr(json!({"op":"power","base":node(1),"exponent":0}));
        let (v, b) = evaluate(&zero_power, &[0., 2.], &[I::ZERO, I { lo: 1.5, hi: 2.5 }]).unwrap();
        assert_eq!(v, 1.);
        assert_eq!(b, I::ONE);
    }

    fn program(rhs: E, with_state: bool) -> Program {
        let o = origin();
        serde_json::from_value(json!({"schema_version":crate::ir::SCHEMA_VERSION,
            "nodes":["0","u","v","y"],
            "states": if with_state {json!([{"instance":"M","name":"g","kind":"real","initial":1.}])} else {json!([])},
            "contributions":[{"origin":o,"branch":{"instance":"M","local_positive":"y","local_negative":"zz","kind":"voltage"},
                "positive":3,"negative":0,"rhs":rhs}]}))
        .unwrap()
    }

    #[test]
    fn only_held_gain_or_stateless_algebraic_decisions_are_owned() {
        let state = json!({"op":"state","state":0});
        let select = |left: serde_json::Value| {
            expr(json!({"op":"select","relation":"gt","left":left,"right":constant(0.5),
                "then_value":constant(0.),"else_value":constant(1.),"origin":origin()}))
        };
        let bilinear = select(json!({"op":"multiply","left":node(1),"right":node(2)}));
        let held_only = select(json!({"op":"multiply","left":state.clone(),"right":state.clone()}));
        let held_gain = select(json!({"op":"multiply","left":state.clone(),"right":node(1)}));
        for e in [&bilinear, &held_only, &held_gain] {
            assert!(needs_readout(e));
        }
        // Beside held state (the history_consumer bilinear_guard shape), a
        // live-only product is not owned; neither is a held-only product.
        let p = program(bilinear.clone(), true);
        assert!(!owned(&p, &p.contributions[0]));
        let p = program(held_only, true);
        assert!(!owned(&p, &p.contributions[0]));
        let p = program(held_gain, true);
        assert!(owned(&p, &p.contributions[0]));
        // The same live-only product is owned when its instance is stateless.
        let p = program(bilinear, false);
        assert!(owned(&p, &p.contributions[0]));
    }

    #[test]
    fn needs_readout_only_for_nonaffine_predicates() {
        assert!(needs_readout(&clamp()));
        let affine = expr(
            json!({"op":"select","relation":"gt","left":node(2),"right":constant(1.),
            "then_value":constant(1.),"else_value":json!({"op":"multiply","left":node(1),"right":node(2)}),
            "origin":origin()}),
        );
        assert!(!needs_readout(&affine));
    }
}
