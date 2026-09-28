//! Branch assembly and residual checking have one owner, for every source form.
use crate::ir::{Error, Program, Solution, Tolerances};
use crate::linear;
use std::collections::{BTreeMap, BTreeSet};

struct Equation {
    positive: usize,
    negative: usize,
    rhs_constant: f64,
    rhs_terms: Vec<f64>,
    coefficients: Vec<f64>,
    origins: Vec<String>,
}

pub struct Circuit {
    pub nodes: Vec<String>,
    equations: Vec<Equation>,
    driven: Vec<usize>,
    unknown: Vec<usize>,
    tolerances: Tolerances,
}

impl Circuit {
    pub fn new(
        program: Program,
        driven_names: &[String],
        tolerances: Tolerances,
    ) -> Result<Self, Error> {
        if program.schema_version != 1 {
            return Err(Error::new(
                "unsupported_ir_version",
                "expected affine-voltage IR version 1",
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
                .ok_or_else(|| {
                    Error::new("invalid_inputs", format!("unknown driven node {name:?}"))
                })?;
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
        let mut grouped = BTreeMap::<(String, String), Equation>::new();
        for c in program.contributions {
            if c.positive >= count
                || c.negative >= count
                || !c.rhs.constant.is_finite()
                || c.branch.is_empty()
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
            let mut term_nodes = BTreeSet::new();
            for t in &c.rhs.terms {
                if t.node >= count || !t.coefficient.is_finite() || !term_nodes.insert(t.node) {
                    return Err(Error::new(
                        "invalid_ir",
                        format!("invalid or duplicate term at {}", c.origin.label()),
                    ));
                }
            }
            let equation = grouped
                .entry((c.origin.instance.clone(), c.branch))
                .or_insert_with(|| Equation {
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
        Ok(Self {
            nodes: program.nodes,
            equations,
            driven,
            unknown,
            tolerances,
        })
    }

    /// A stateless operating point. No previous solution or physical history is
    /// read or changed. Dynamic trial/commit state is deliberately not present.
    pub fn solve(&self, inputs: &[f64]) -> Result<Solution, Error> {
        if inputs.len() != self.driven.len() || inputs.iter().any(|x| !x.is_finite()) {
            return Err(Error::new(
                "invalid_inputs",
                "sample must contain one finite value per driven node",
            ));
        }
        let mut values = vec![0.0; self.nodes.len()];
        for (&node, &value) in self.driven.iter().zip(inputs) {
            values[node] = value;
        }
        let matrix = self
            .equations
            .iter()
            .map(|eq| self.unknown.iter().map(|&n| eq.coefficients[n]).collect())
            .collect();
        let rhs = self
            .equations
            .iter()
            .map(|eq| {
                eq.rhs_constant
                    - self
                        .driven
                        .iter()
                        .map(|&n| eq.coefficients[n] * values[n])
                        .sum::<f64>()
            })
            .collect();
        let solved = linear::solve(matrix, rhs, self.unknown.len()).map_err(|mut error| {
            error.message.push_str(&format!(
                "; unknown nodes: {:?}; constraints: {}",
                self.unknown
                    .iter()
                    .map(|&n| &self.nodes[n])
                    .collect::<Vec<_>>(),
                self.equations
                    .iter()
                    .flat_map(|eq| &eq.origins)
                    .cloned()
                    .collect::<Vec<_>>()
                    .join(", ")
            ));
            error
        })?;
        for (&node, value) in self.unknown.iter().zip(solved) {
            values[node] = value;
        }
        let mut max_residual_v = 0.0_f64;
        let mut max_residual_ratio = 0.0_f64;
        for eq in &self.equations {
            // Check the original physical branch equation, not the eliminated matrix.
            let lhs = values[eq.positive] - values[eq.negative];
            let rhs = eq.rhs_constant
                + eq.rhs_terms
                    .iter()
                    .zip(&values)
                    .map(|(a, v)| a * v)
                    .sum::<f64>();
            let residual = (lhs - rhs).abs();
            let bound =
                self.tolerances.absolute + self.tolerances.relative * lhs.abs().max(rhs.abs());
            if !residual.is_finite() || !bound.is_finite() {
                return Err(Error::new(
                    "nonfinite_arithmetic",
                    format!("nonfinite residual at {}", eq.origins.join(", ")),
                ));
            }
            if residual > bound {
                return Err(Error::new(
                    "residual_failure",
                    format!(
                        "residual {residual:e} V exceeds {bound:e} V at {}",
                        eq.origins.join(", ")
                    ),
                ));
            }
            max_residual_v = max_residual_v.max(residual);
            max_residual_ratio = max_residual_ratio.max(residual / bound);
        }
        Ok(Solution {
            voltages: values,
            max_residual_v,
            max_residual_ratio,
        })
    }
}
