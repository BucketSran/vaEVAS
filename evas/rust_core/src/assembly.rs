//! Validate IR and assemble one equation per instance-local voltage branch.
use crate::ir::{check_schema_version, BranchIdentity, Error, Expression, Program, Tolerances};
use crate::{expression, linear::Row};
use std::collections::{BTreeMap, BTreeSet, HashSet};

#[derive(Clone)]
pub(crate) struct Equation {
    pub(crate) branch: BranchIdentity,
    pub(crate) positive: usize,
    pub(crate) negative: usize,
    pub(crate) rhs_constant: f64,
    pub(crate) rhs_terms: Row,
    pub(crate) coefficients: Row,
    pub(crate) nonlinear: Vec<Expression>,
    pub(crate) original_rhs: Vec<Expression>,
    pub(crate) origins: Vec<String>,
}

pub(crate) struct AssembledCircuit {
    pub(crate) nodes: Vec<String>,
    pub(crate) equations: Vec<Equation>,
    pub(crate) driven: Vec<usize>,
    pub(crate) unknown: Vec<usize>,
    pub(crate) tolerances: Tolerances,
}

// Sorted compact terms keep residual evaluation contiguous without dense rows.
fn add_coefficient(row: &mut Row, node: usize, value: f64) {
    match row.binary_search_by_key(&node, |&(node, _)| node) {
        Ok(index) => row[index].1 += value,
        Err(index) => row.insert(index, (node, value)),
    }
}

/// Structural facts of one assembled program that trial-to-trial settlement
/// rebuilds can share: node list, driven/unknown order, the branch grouping
/// (program-order contribution index to final equation index) and the
/// per-equation branch identity plus origin labels. All numeric results
/// (`rhs_constant`, `rhs_terms`, `coefficients`, `nonlinear`, `original_rhs`)
/// are recomputed on every rebuild; only validation, grouping maps and label
/// construction are skipped, guarded by [`AssemblyPlan::matches`].
pub(crate) struct AssemblyPlan {
    nodes: Vec<String>,
    driven: Vec<usize>,
    unknown: Vec<usize>,
    /// Program-order contribution index -> final equation index.
    assignment: Vec<usize>,
    templates: Vec<EquationTemplate>,
}

struct EquationTemplate {
    branch: BranchIdentity,
    positive: usize,
    negative: usize,
    origins: Vec<String>,
}

impl AssemblyPlan {
    /// A plan may only be reused when every structural input that decides
    /// validation, grouping and driven resolution is identical: the node list,
    /// the contribution count, and each contribution's branch identity,
    /// endpoints and origin constants. The numeric right-hand sides may differ
    /// freely; they are rebuilt from scratch in the original contribution
    /// order, so an accepted rebuild is bit-identical to a fresh assembly of
    /// the same program. Skipping `expression::validate` is sound here because
    /// the compared trial programs are produced by `EventModel`'s
    /// freeze/bind/substitute pipeline from one already-validated program:
    /// their trees only recombine node indices and constants taken from that
    /// validated original, and the node list (hence the valid index range) is
    /// compared equal by this guard.
    fn matches(&self, program: &Program, driven_names: &[String]) -> bool {
        self.nodes == program.nodes
            && self.assignment.len() == program.contributions.len()
            && !program.contributions.is_empty()
            && program
                .contributions
                .iter()
                .zip(&self.assignment)
                .all(|(c, &i)| {
                    let Some(template) = self.templates.get(i) else {
                        return false;
                    };
                    template.branch == c.branch
                        && template.positive == c.positive
                        && template.negative == c.negative
                        && c.positive < self.nodes.len()
                        && c.negative < self.nodes.len()
                        && c.branch.instance == c.origin.instance
                        && !c.branch.local_positive.is_empty()
                        && !c.branch.local_negative.is_empty()
                        && c.branch.local_positive <= c.branch.local_negative
                        && !c.origin.instance.is_empty()
                        && !c.origin.source.is_empty()
                        && c.origin.line != 0
                        && c.origin.column != 0
                })
            && {
                // The driven list is a function of the (compared-equal) node
                // list and the caller's driven names; recompute to be safe.
                let mut driven = Vec::new();
                for name in driven_names {
                    match self.nodes.iter().position(|n| n == name) {
                        Some(index) if index != 0 && !driven.contains(&index) => {
                            driven.push(index);
                        }
                        _ => return false,
                    }
                }
                driven == self.driven
            }
    }
}

/// Assemble `program`, reusing `scratch` when its recorded structure matches.
/// The first call (or any structural change) performs a full validated
/// assembly and records a fresh plan; matching successors rebuild only the
/// numeric equation contents in the identical contribution order.
pub(crate) fn assemble_with_plan(
    program: Program,
    driven_names: &[String],
    tolerances: Tolerances,
    scratch: &mut Option<AssemblyPlan>,
) -> Result<AssembledCircuit, Error> {
    if scratch
        .as_ref()
        .is_some_and(|plan| plan.matches(&program, driven_names))
    {
        let plan = scratch.as_ref().expect("checked plan");
        crate::diagnostics::counter("assembly_plan_reuse", 1);
        check_schema_version(u64::from(program.schema_version))?;
        if !program.states.is_empty() || !program.events.is_empty() || !program.operators.is_empty()
        {
            return Err(Error::new(
                "unsupported_analysis",
                "state/event program requires transient execution",
            ));
        }
        if !tolerances.absolute.is_finite()
            || tolerances.absolute <= 0.0
            || !tolerances.relative.is_finite()
            || tolerances.relative < 0.0
        {
            return Err(Error::new(
                "invalid_config",
                "absolute tolerance must be positive; relative tolerance nonnegative; both finite",
            ));
        }
        let mut equations: Vec<_> = plan
            .templates
            .iter()
            .map(|template| Equation {
                branch: template.branch.clone(),
                positive: template.positive,
                negative: template.negative,
                rhs_constant: 0.0,
                rhs_terms: Row::new(),
                coefficients: Row::new(),
                nonlinear: Vec::new(),
                original_rhs: Vec::new(),
                origins: template.origins.clone(),
            })
            .collect();
        for (index, c) in program.contributions.into_iter().enumerate() {
            let equation = &mut equations[plan.assignment[index]];
            equation.original_rhs.push(c.rhs.clone());
            match c.rhs {
                Expression::Affine { constant, terms } => {
                    equation.rhs_constant += constant;
                    for t in terms {
                        add_coefficient(&mut equation.rhs_terms, t.node, t.coefficient);
                    }
                }
                expression => equation.nonlinear.push(expression),
            }
        }
        finalize_equations(&mut equations)?;
        return Ok(AssembledCircuit {
            nodes: program.nodes,
            equations,
            driven: plan.driven.clone(),
            unknown: plan.unknown.clone(),
            tolerances,
        });
    }
    let (assembled, branches) = assemble_inner(program, driven_names, tolerances)?;
    *scratch = Some(plan_of(&assembled, &branches));
    Ok(assembled)
}

fn plan_of(assembled: &AssembledCircuit, branches: &[BranchIdentity]) -> AssemblyPlan {
    let mut order = BTreeMap::new();
    for (index, equation) in assembled.equations.iter().enumerate() {
        order.insert(equation.branch.clone(), index);
    }
    AssemblyPlan {
        nodes: assembled.nodes.clone(),
        driven: assembled.driven.clone(),
        unknown: assembled.unknown.clone(),
        assignment: branches
            .iter()
            .map(|branch| order.get(branch).copied().unwrap_or(0))
            .collect(),
        templates: assembled
            .equations
            .iter()
            .map(|equation| EquationTemplate {
                branch: equation.branch.clone(),
                positive: equation.positive,
                negative: equation.negative,
                origins: equation.origins.clone(),
            })
            .collect(),
    }
}

pub(crate) fn assemble(
    program: Program,
    driven_names: &[String],
    tolerances: Tolerances,
) -> Result<AssembledCircuit, Error> {
    assemble_inner(program, driven_names, tolerances).map(|(assembled, _)| assembled)
}

fn assemble_inner(
    program: Program,
    driven_names: &[String],
    tolerances: Tolerances,
) -> Result<(AssembledCircuit, Vec<BranchIdentity>), Error> {
    check_schema_version(u64::from(program.schema_version))?;
    if !program.states.is_empty() || !program.events.is_empty() || !program.operators.is_empty() {
        return Err(Error::new(
            "unsupported_analysis",
            "state/event program requires transient execution",
        ));
    }
    let count = program.nodes.len();
    let unique: BTreeSet<_> = program.nodes.iter().collect();
    if count == 0
        || program.nodes[0] != "0"
        || unique.len() != count
        || program.nodes.iter().any(|n| n.is_empty())
    {
        return Err(Error::new(
            "invalid_ir",
            "nodes must be unique, nonempty and start with ground '0'",
        ));
    }
    if !tolerances.absolute.is_finite()
        || tolerances.absolute <= 0.0
        || !tolerances.relative.is_finite()
        || tolerances.relative < 0.0
    {
        return Err(Error::new(
            "invalid_config",
            "absolute tolerance must be positive; relative tolerance nonnegative; both finite",
        ));
    }
    let mut driven = Vec::new();
    for name in driven_names {
        let index = program
            .nodes
            .iter()
            .position(|n| n == name)
            .ok_or_else(|| Error::new("invalid_inputs", format!("unknown driven node {name:?}")))?;
        if index == 0 || driven.contains(&index) {
            return Err(Error::new(
                "invalid_inputs",
                "driven nodes must be unique and cannot include ground",
            ));
        }
        driven.push(index);
    }
    let mut predicate_nodes: HashSet<usize> = driven.iter().copied().collect();
    predicate_nodes.insert(0);
    // Passive measurement circuits need no equations when every voltage is
    // fixed by a submitted source or ground. Floating nodes still require an
    // equation and must not acquire an invented zero voltage.
    if program.contributions.is_empty() && driven.len() + 1 != count {
        return Err(Error::new(
            "invalid_ir",
            "program has no voltage contributions",
        ));
    }
    // Contributions share a branch only within one instance. Independent
    // ideal voltage sources in parallel must satisfy separate constraints.
    let mut branches: Vec<BranchIdentity> = Vec::new();
    let mut grouped = BTreeMap::<BranchIdentity, Equation>::new();
    let mut node_bindings = BTreeMap::new();
    let mut bound_branches = BTreeMap::new();
    for c in program.contributions {
        if c.positive >= count
            || c.negative >= count
            || c.branch.instance != c.origin.instance
            || c.branch.local_positive.is_empty()
            || c.branch.local_negative.is_empty()
            || c.branch.local_positive > c.branch.local_negative
            || c.origin.instance.is_empty()
            || c.origin.source.is_empty()
            || c.origin.line == 0
            || c.origin.column == 0
        {
            return Err(Error::new(
                "invalid_ir",
                "invalid contribution target, constant or source identity",
            ));
        }
        for (local, global) in [
            (&c.branch.local_positive, c.positive),
            (&c.branch.local_negative, c.negative),
        ] {
            let previous = node_bindings.insert((c.branch.instance.clone(), local.clone()), global);
            if (local == "0" && global != 0) || previous.is_some_and(|node| node != global) {
                return Err(Error::new(
                    "invalid_ir",
                    format!("inconsistent local node binding at {}", c.origin.label()),
                ));
            }
        }
        let bound_pair = (
            c.branch.instance.clone(),
            c.positive.min(c.negative),
            c.positive.max(c.negative),
        );
        if bound_branches
            .insert(bound_pair, c.branch.clone())
            .is_some_and(|identity| identity != c.branch)
        {
            return Err(Error::new(
                "invalid_ir",
                format!(
                    "distinct local contribution branches alias after connection at {}",
                    c.origin.label()
                ),
            ));
        }
        expression::validate(&c.rhs, count).map_err(|mut error| {
            error.message.push_str(&format!(" at {}", c.origin.label()));
            error
        })?;
        expression::validate_select_predicates(&c.rhs, &predicate_nodes).map_err(|mut error| {
            error.message.push_str(&format!(" at {}", c.origin.label()));
            error
        })?;
        branches.push(c.branch.clone());
        let branch = c.branch.clone();
        let equation = grouped.entry(c.branch).or_insert_with(|| Equation {
            branch,
            positive: c.positive,
            negative: c.negative,
            rhs_constant: 0.0,
            rhs_terms: Row::new(),
            coefficients: Row::new(),
            nonlinear: Vec::new(),
            original_rhs: Vec::new(),
            origins: Vec::new(),
        });
        if (equation.positive, equation.negative) != (c.positive, c.negative) {
            return Err(Error::new(
                "invalid_ir",
                "one branch identity has conflicting endpoint bindings",
            ));
        }
        equation.original_rhs.push(c.rhs.clone());
        match c.rhs {
            Expression::Affine { constant, terms } => {
                equation.rhs_constant += constant;
                for t in terms {
                    add_coefficient(&mut equation.rhs_terms, t.node, t.coefficient);
                }
            }
            expression => equation.nonlinear.push(expression),
        }
        equation.origins.push(c.origin.label());
    }
    let mut equations: Vec<_> = grouped.into_values().collect();
    finalize_equations(&mut equations)?;
    let unknown = (1..count).filter(|n| !driven.contains(n)).collect();
    Ok((
        AssembledCircuit {
            nodes: program.nodes,
            equations,
            driven,
            unknown,
            tolerances,
        },
        branches,
    ))
}

/// Identical finalization for fresh and planned assemblies: drop exact zero
/// terms, negate into the coefficient row, add the unit branch stamp and check
/// finiteness. The operation order must stay the same in both paths.
fn finalize_equations(equations: &mut [Equation]) -> Result<(), Error> {
    for eq in equations {
        eq.rhs_terms.retain(|&(_, value)| value != 0.0);
        eq.coefficients = eq.rhs_terms.iter().map(|&(n, x)| (n, -x)).collect();
        add_coefficient(&mut eq.coefficients, eq.positive, 1.0);
        add_coefficient(&mut eq.coefficients, eq.negative, -1.0);
        eq.coefficients.retain(|&(_, value)| value != 0.0);
        if !eq.rhs_constant.is_finite() || eq.coefficients.iter().any(|(_, x)| !x.is_finite()) {
            return Err(Error::new(
                "nonfinite_arithmetic",
                format!(
                    "contribution accumulation overflow at {}",
                    eq.origins.join(", ")
                ),
            ));
        }
    }
    Ok(())
}

#[cfg(test)]
mod plan_tests {
    use super::*;

    fn program(constant: f64, extra: bool) -> Program {
        let mut contributions: Vec<crate::ir::Contribution> =
            vec![serde_json::from_value(serde_json::json!({
                "branch": {"instance": "dut", "local_positive": "a",
                           "local_negative": "b", "kind": "voltage"},
                "positive": 1, "negative": 2,
                "rhs": {"op": "affine", "constant": constant,
                        "terms": [{"node": 1, "coefficient": 0.5}]},
                "origin": {"source": "plan.va", "line": 1, "column": 1, "instance": "dut"}
            }))
            .unwrap()];
        if extra {
            contributions.push(
                serde_json::from_value(serde_json::json!({
                    "branch": {"instance": "dut", "local_positive": "c",
                               "local_negative": "d", "kind": "voltage"},
                    "positive": 2, "negative": 0,
                    "rhs": {"op": "affine", "constant": 1.0, "terms": []},
                    "origin": {"source": "plan.va", "line": 2, "column": 1, "instance": "dut"}
                }))
                .unwrap(),
            );
        }
        serde_json::from_value(serde_json::json!({
            "schema_version": crate::ir::SCHEMA_VERSION,
            "nodes": ["0", "x", "y"],
            "contributions": contributions,
        }))
        .unwrap()
    }

    // A planned rebuild must be bit-identical to a fresh validated assembly
    // of the same program, and a structural change must fall back to one.
    #[test]
    fn planned_rebuild_is_bit_identical_and_structure_changes_fall_back() {
        let driven = ["x".to_string()];
        let tolerances = crate::ir::Tolerances::default();
        let mut scratch = None;
        let first = assemble_with_plan(
            program(1.0, false),
            &driven,
            tolerances.clone(),
            &mut scratch,
        )
        .unwrap();
        assert!(scratch.is_some());
        assert_eq!(first.equations.len(), 1);
        let reused = assemble_with_plan(
            program(2.5, false),
            &driven,
            tolerances.clone(),
            &mut scratch,
        )
        .unwrap();
        let fresh = assemble(program(2.5, false), &driven, tolerances.clone()).unwrap();
        assert_eq!(reused.nodes, fresh.nodes);
        assert_eq!(reused.driven, fresh.driven);
        assert_eq!(reused.unknown, fresh.unknown);
        assert_eq!(reused.equations.len(), fresh.equations.len());
        for (planned, plain) in reused.equations.iter().zip(&fresh.equations) {
            assert_eq!(planned.branch, plain.branch);
            assert_eq!(planned.rhs_constant.to_bits(), plain.rhs_constant.to_bits());
            assert_eq!(planned.rhs_terms, plain.rhs_terms);
            assert_eq!(planned.coefficients, plain.coefficients);
            assert_eq!(planned.origins, plain.origins);
            assert_eq!(
                serde_json::to_string(&planned.original_rhs).unwrap(),
                serde_json::to_string(&plain.original_rhs).unwrap()
            );
        }
        // A new contribution changes the structure: the plan must not match,
        // and the fallback must still assemble the grown program.
        let grown = assemble_with_plan(
            program(2.5, true),
            &driven,
            tolerances.clone(),
            &mut scratch,
        )
        .unwrap();
        assert_eq!(grown.equations.len(), 2);
        let fresh_grown = assemble(program(2.5, true), &driven, tolerances).unwrap();
        for (planned, plain) in grown.equations.iter().zip(&fresh_grown.equations) {
            assert_eq!(
                serde_json::to_string(&planned.original_rhs).unwrap(),
                serde_json::to_string(&plain.original_rhs).unwrap()
            );
            assert_eq!(planned.rhs_constant.to_bits(), plain.rhs_constant.to_bits());
            assert_eq!(planned.rhs_terms, plain.rhs_terms);
            assert_eq!(planned.coefficients, plain.coefficients);
        }
    }
}
