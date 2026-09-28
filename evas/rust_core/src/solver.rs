//! Solve stateless operating points and check the original branch residuals.
use crate::assembly::{assemble, AssembledCircuit, Equation};
use crate::ir::{Error, Program, Solution, Tolerances};
use crate::{linear, nonlinear};

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
        let AssembledCircuit {
            nodes,
            equations,
            driven,
            unknown,
            tolerances,
        } = assemble(program, driven_names, tolerances)?;
        Ok(Self {
            nodes,
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
        if self.equations.iter().any(|eq| !eq.nonlinear.is_empty()) {
            return nonlinear::solve(&self.equations, &self.unknown, values, &self.tolerances);
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
            max_scaled_residual_ratio: None,
            max_voltage_correction_v: None,
            max_voltage_correction_ratio: None,
        })
    }
}
