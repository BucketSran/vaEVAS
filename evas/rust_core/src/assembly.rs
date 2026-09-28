//! Validate IR and assemble one equation per instance-local voltage branch.
use crate::ir::{check_schema_version, BranchIdentity, Error, Program, Tolerances};
use std::collections::{BTreeMap, BTreeSet};

pub(crate) struct Equation {
    pub(crate) positive: usize,
    pub(crate) negative: usize,
    pub(crate) rhs_constant: f64,
    pub(crate) rhs_terms: Vec<f64>,
    pub(crate) coefficients: Vec<f64>,
    pub(crate) origins: Vec<String>,
}

pub(crate) struct AssembledCircuit {
    pub(crate) nodes: Vec<String>,
    pub(crate) equations: Vec<Equation>,
    pub(crate) driven: Vec<usize>,
    pub(crate) unknown: Vec<usize>,
    pub(crate) tolerances: Tolerances,
}

pub(crate) fn assemble(
    program: Program,
    driven_names: &[String],
    tolerances: Tolerances,
) -> Result<AssembledCircuit, Error> {
    check_schema_version(u64::from(program.schema_version))?;
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
    if program.contributions.is_empty() {
        return Err(Error::new(
            "invalid_ir",
            "program has no voltage contributions",
        ));
    }
    // Contributions share a branch only within one instance. Independent
    // ideal voltage sources in parallel must satisfy separate constraints.
    let mut grouped = BTreeMap::<BranchIdentity, Equation>::new();
    let mut node_bindings = BTreeMap::new();
    let mut bound_branches = BTreeMap::new();
    for c in program.contributions {
        if c.positive >= count
            || c.negative >= count
            || !c.rhs.constant.is_finite()
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
        let mut term_nodes = BTreeSet::new();
        for t in &c.rhs.terms {
            if t.node >= count || !t.coefficient.is_finite() || !term_nodes.insert(t.node) {
                return Err(Error::new(
                    "invalid_ir",
                    format!("invalid or duplicate term at {}", c.origin.label()),
                ));
            }
        }
        let equation = grouped.entry(c.branch).or_insert_with(|| Equation {
            positive: c.positive,
            negative: c.negative,
            rhs_constant: 0.0,
            rhs_terms: vec![0.0; count],
            coefficients: vec![0.0; count],
            origins: Vec::new(),
        });
        if (equation.positive, equation.negative) != (c.positive, c.negative) {
            return Err(Error::new(
                "invalid_ir",
                "one branch identity has conflicting endpoint bindings",
            ));
        }
        equation.rhs_constant += c.rhs.constant;
        for t in c.rhs.terms {
            equation.rhs_terms[t.node] += t.coefficient;
        }
        equation.origins.push(c.origin.label());
    }
    let mut equations: Vec<_> = grouped.into_values().collect();
    for eq in &mut equations {
        eq.coefficients = eq.rhs_terms.iter().map(|x| -x).collect();
        eq.coefficients[eq.positive] += 1.0;
        eq.coefficients[eq.negative] -= 1.0;
        if !eq.rhs_constant.is_finite() || eq.coefficients.iter().any(|x| !x.is_finite()) {
            return Err(Error::new(
                "nonfinite_arithmetic",
                format!(
                    "contribution accumulation overflow at {}",
                    eq.origins.join(", ")
                ),
            ));
        }
    }
    let unknown = (1..count).filter(|n| !driven.contains(n)).collect();
    Ok(AssembledCircuit {
        nodes: program.nodes,
        equations,
        driven,
        unknown,
        tolerances,
    })
}
