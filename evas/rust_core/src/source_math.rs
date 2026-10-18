//! Stateless native math stages are certified algebraic forcing, never history.
//! Audit original source dependencies before replacing operator references.
use crate::analog::Analog;
use crate::interval::Interval as I;
use crate::ir::{Error, Expression, OperatorSpec, Program, Solution, Term, Tolerances};
use crate::operators::Operators;
use crate::pwl::Trajectory;
use std::collections::{HashMap, HashSet};

/// A cheap dispatch candidate, not an admission or source-uncertainty proof.
/// Prepared::new audits the complete original trees once before any math work.
pub(crate) fn candidate(program: &Program) -> bool {
    !program.operators.is_empty()
        && program.states.is_empty()
        && program.events.is_empty()
        && program.step_bounds.is_empty()
        && program
            .operators
            .first()
            .is_some_and(|op| matches!(op, OperatorSpec::Sin { .. } | OperatorSpec::Math { .. }))
}

// One owner for this request's added structural scan. No repeated allowance per
// operator/contribution or fallback. Existing math proof owners remain unchanged.
struct Audit {
    remaining: Option<usize>,
}
impl Audit {
    fn charge(&mut self, amount: usize) -> Result<(), Error> {
        self.remaining = self.remaining.and_then(|n| n.checked_sub(amount));
        if self.remaining.is_none() {
            return Err(Error::new(
                "resource_budget",
                "source math audit exceeds 100000 items",
            ));
        }
        Ok(())
    }

    fn tree(
        &mut self,
        expression: &Expression,
        program: &Program,
        sources: &HashSet<usize>,
        owner: &str,
        operators: bool,
    ) -> Result<(), Error> {
        let mut pending = vec![expression];
        while let Some(expr) = pending.pop() {
            self.charge(1)?;
            match expr {
                Expression::Affine { constant, terms } => {
                    self.charge(terms.len())?;
                    if !constant.is_finite()
                        || terms.iter().any(|term| {
                            !term.coefficient.is_finite() || !sources.contains(&term.node)
                        })
                    {
                        return Err(unsupported());
                    }
                }
                Expression::Operator { operator } if operators => {
                    if program
                        .operators
                        .get(*operator)
                        .is_none_or(|op| op.origin().instance != owner)
                    {
                        return Err(unsupported());
                    }
                }
                Expression::Add { left, right }
                | Expression::Multiply { left, right }
                | Expression::Divide { left, right } => {
                    pending.push(right);
                    pending.push(left);
                }
                // No inactive-arm, power, output, state or history relaxation.
                _ => return Err(unsupported()),
            }
        }
        Ok(())
    }
}
fn unsupported() -> Error {
    Error::new(
        "unsupported_source_math_scope",
        "native math composition requires a complete stateless driven-input arithmetic program",
    )
}

pub(crate) struct Prepared {
    operators: Operators,
    analog: Analog,
    original_nodes: usize,
}
impl Prepared {
    pub(crate) fn new(
        program: &Program,
        trajectory: &Trajectory,
        driven: &[String],
        tolerances: &Tolerances,
    ) -> Result<Self, Error> {
        if !candidate(program) {
            return Err(unsupported());
        }
        let mut audit = Audit {
            remaining: Some(100_000),
        };
        // Native math currently samples its DirectInput at nominal knots.
        // A distinct physical shape may have additional rational kinks. This
        // explicit refusal must not become a scope miss with old-path fallback.
        // A zero band already proves physical/nominal equality at every union
        // knot in Curve::shaped, so the complete linear curves coincide.
        if let Some(errors) = &trajectory.config.pwl_errors_v {
            audit.charge(errors.len())?;
            if errors
                .iter()
                .any(|error| error.shape().is_some() && error.bound() > 0.)
            {
                return Err(Error::new(
                    "unsupported_source_uncertainty",
                    "native math composition does not support exact physical source shapes",
                ));
            }
        }
        audit.charge(program.nodes.len() + driven.len())?;
        let nodes: HashMap<_, _> = program
            .nodes
            .iter()
            .enumerate()
            .map(|(index, name)| (name.as_str(), index))
            .collect();
        let mut sources = HashSet::from([0]);
        for name in driven {
            let node = *nodes.get(name.as_str()).ok_or_else(unsupported)?;
            if !sources.insert(node) {
                return Err(unsupported());
            }
        }
        for op in &program.operators {
            audit.charge(1)?;
            let (OperatorSpec::Sin { input, origin } | OperatorSpec::Math { input, origin, .. }) =
                op
            else {
                return Err(unsupported());
            };
            let before = audit.remaining.unwrap();
            audit.tree(input, program, &sources, &origin.instance, false)?;
            let input_items = before - audit.remaining.unwrap();
            // affine allocates/traverses dense coordinate vectors per input
            // AST node. Reserve their conservative actual inner-work bound in
            // the same request allowance before invoking this existing helper.
            let dimensions = program.nodes.len() + program.operators.len() + 1;
            let cost = input_items
                .checked_mul(dimensions)
                .and_then(|n| n.checked_mul(6))
                .unwrap_or(usize::MAX);
            audit.charge(cost)?;
            // Retain the existing native math input contract, including source
            // obligations erased by coefficient cancellation in affine lowering.
            let affine = crate::events::affine(input, program, &origin.instance)
                .map_err(|_| unsupported())?;
            if !affine.state_dependencies.is_empty()
                || !affine.operator_dependencies.is_empty()
                || affine
                    .node_dependencies
                    .iter()
                    .any(|n| !sources.contains(n))
            {
                return Err(unsupported());
            }
        }
        for contribution in &program.contributions {
            audit.charge(1)?;
            audit.tree(
                &contribution.rhs,
                program,
                &sources,
                &contribution.origin.instance,
                true,
            )?;
        }
        let operators = Operators::new_until(
            program,
            trajectory,
            driven,
            &[],
            trajectory.config.stop,
            tolerances,
        )?;
        // Reserve the counted original structure for the one added owned copy.
        // This admission allowance never replenishes Operators' proof counters.
        let scanned = 100_000 - audit.remaining.unwrap();
        audit.charge(scanned)?;
        let mut reduced = program.clone();
        let original_nodes = reduced.nodes.len();
        let mut extended = driven.to_vec();
        for index in 0..program.operators.len() {
            audit.charge(2)?;
            let name = format!("$source_math_{index}");
            if nodes.contains_key(name.as_str()) {
                return Err(Error::new(
                    "invalid_ir",
                    "reserved source math node collision",
                ));
            }
            reduced.nodes.push(name.clone());
            extended.push(name);
        }
        fn replace(expr: &mut Expression, start: usize, audit: &mut Audit) -> Result<(), Error> {
            audit.charge(1)?;
            match expr {
                Expression::Operator { operator } => {
                    *expr = Expression::Affine {
                        constant: 0.,
                        terms: vec![Term {
                            node: start + *operator,
                            coefficient: 1.,
                        }],
                    }
                }
                Expression::Add { left, right }
                | Expression::Multiply { left, right }
                | Expression::Divide { left, right } => {
                    replace(left, start, audit)?;
                    replace(right, start, audit)?;
                }
                _ => {}
            }
            Ok(())
        }
        for contribution in &mut reduced.contributions {
            replace(&mut contribution.rhs, original_nodes, &mut audit)?;
        }
        reduced.operators.clear();
        let analog = Analog::new(reduced, extended, tolerances.clone())?;
        Ok(Self {
            operators,
            analog,
            original_nodes,
        })
    }

    pub(crate) fn solve(
        &mut self,
        values: &[f64],
        bounds: &[I],
        time: f64,
        _exact: &[Option<crate::exact_source::Curve>],
    ) -> Result<Solution, Error> {
        let mut values = values.to_vec();
        values.extend(self.operators.values(time)?);
        let mut bounds = bounds.to_vec();
        bounds.extend(self.operators.bounds(time)?);
        // Admission excludes every Select. Analog only consults exact curves
        // for Select predicates; true source uncertainty remains in bounds.
        // Avoid copying the original rational knots at every output query.
        let mut solution = self.analog.solve(&values, &bounds, None, time, &[])?;
        solution.voltages.truncate(self.original_nodes);
        if let Some(bounds) = &mut solution.certified_voltage_bounds {
            bounds.truncate(self.original_nodes);
        }
        Ok(solution)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn fixture() -> (Program, Trajectory, Vec<String>, Tolerances) {
        let origin = json!({"source":"forcing.va","line":1,"column":1,"instance":"dut"});
        let input = json!({"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]});
        let program: Program = serde_json::from_value(json!({
            "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","u","y"],
            "states":[],"events":[],"step_bounds":[],
            "operators":[{"kind":"math","function":"tanh","input":input,"origin":origin}],
            "contributions":[{"positive":2,"negative":0,"origin":origin,
                "branch":{"kind":"voltage","instance":"dut","local_positive":"out","local_negative":"ref"},
                "rhs":{"op":"multiply","left":input,"right":{"op":"operator","operator":0}}}]
        })).unwrap();
        let config = serde_json::from_value(serde_json::json!({
            "pwl":[[[0.,0.],[1.,1.]]],"output_times":[0.,1.],"stop":1.,"max_step":1.
        }))
        .unwrap();
        (
            program,
            Trajectory::new(config, 1).unwrap(),
            vec!["u".into()],
            Tolerances::default(),
        )
    }

    #[test]
    fn audit_budget_is_shared_by_roots_and_stays_exhausted_on_retry() {
        let mut audit = Audit { remaining: Some(3) };
        let (program, _, _, _) = fixture();
        let sources = HashSet::from([0, 1]);
        // Each affine root costs one node and one term. The second root does
        // not receive a new allowance; failure cannot be revived by zero debit.
        let OperatorSpec::Math { input, .. } = &program.operators[0] else {
            panic!()
        };
        audit.tree(input, &program, &sources, "dut", false).unwrap();
        assert_eq!(
            audit
                .tree(input, &program, &sources, "dut", false)
                .unwrap_err()
                .kind,
            "resource_budget"
        );
        assert!(audit.charge(0).is_err());
    }

    #[test]
    fn raw_original_zero_dependencies_wrong_owner_and_unreachable_arms_refuse() {
        let (program, trajectory, driven, tolerance) = fixture();
        for node in [2, 99] {
            let mut invalid = program.clone();
            if let OperatorSpec::Math { input, .. } = &mut invalid.operators[0] {
                *input = Expression::Affine {
                    constant: 0.1,
                    terms: vec![Term {
                        node,
                        coefficient: 0.,
                    }],
                };
            }
            assert!(Prepared::new(&invalid, &trajectory, &driven, &tolerance).is_err());
        }
        let mut invalid = program.clone();
        if let OperatorSpec::Math { origin, .. } = &mut invalid.operators[0] {
            origin.instance = "other".into();
        }
        assert!(Prepared::new(&invalid, &trajectory, &driven, &tolerance).is_err());
        let mut raw = serde_json::to_value(&program).unwrap();
        let original = raw["contributions"][0]["rhs"].clone();
        raw["contributions"][0]["rhs"] = json!({"op":"select","relation":"gt",
            "left":{"op":"affine","constant":1,"terms":[]},
            "right":{"op":"affine","constant":0,"terms":[]},
            "then_value":original,"else_value":{"op":"operator","operator":999},
            "origin":{"source":"forcing.va","line":3,"column":1,"instance":"dut"}});
        let invalid: Program = serde_json::from_value(raw).unwrap();
        assert!(Prepared::new(&invalid, &trajectory, &driven, &tolerance).is_err());
    }

    #[test]
    fn failed_same_prepared_query_keeps_source_and_certificate_for_retry() {
        let (program, trajectory, driven, tolerance) = fixture();
        let mut prepared = Prepared::new(&program, &trajectory, &driven, &tolerance).unwrap();
        let clean = prepared
            .solve(&[0.25], &[I::point(0.25)], 0.25, &trajectory.exact_sources)
            .unwrap();
        assert!(clean.certified_voltage_bounds.is_some());
        assert_eq!(
            prepared
                .solve(
                    &[0.25],
                    &[I { lo: 0.1, hi: 0.4 }],
                    0.25,
                    &trajectory.exact_sources
                )
                .unwrap_err()
                .kind,
            "waveform_accuracy"
        );
        let retried = prepared
            .solve(&[0.25], &[I::point(0.25)], 0.25, &trajectory.exact_sources)
            .unwrap();
        assert_eq!(clean.voltages, retried.voltages);
        assert_eq!(
            clean.certified_voltage_bounds,
            retried.certified_voltage_bounds
        );
    }
}
