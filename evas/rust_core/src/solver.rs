//! Solve stateless operating points and check the original branch residuals.
use crate::assembly::{assemble, AssembledCircuit, Equation};
use crate::ir::{Error, Program, Solution, Tolerances};
use crate::{linear, nonlinear};
use std::sync::OnceLock;

pub struct Circuit {
    pub nodes: Vec<String>,
    equations: Vec<Equation>,
    driven: Vec<usize>,
    unknown: Vec<usize>,
    tolerances: Tolerances,
    unknown_columns: Vec<Option<usize>>,
    driven_coefficients: Vec<linear::Row>,
    // Only coefficients are cached; inputs, solutions and physical state are not.
    affine_factor: Option<OnceLock<Result<linear::Factorization, Error>>>,
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
        let affine_factor = equations
            .iter()
            .all(|eq| eq.nonlinear.is_empty())
            .then(OnceLock::new);
        let mut unknown_columns = vec![None; nodes.len()];
        for (column, &node) in unknown.iter().enumerate() {
            unknown_columns[node] = Some(column);
        }
        let mut input_columns = vec![None; nodes.len()];
        for (column, &node) in driven.iter().enumerate() {
            input_columns[node] = Some(column);
        }
        let driven_coefficients = equations
            .iter()
            .map(|eq| {
                let mut row: linear::Row = eq
                    .coefficients
                    .iter()
                    .filter_map(|&(node, value)| input_columns[node].map(|column| (column, value)))
                    .collect();
                // Preserve the caller's input summation order without scanning zeros.
                row.sort_unstable_by_key(|&(column, _)| column);
                row
            })
            .collect();
        Ok(Self {
            nodes,
            equations,
            driven,
            unknown,
            tolerances,
            affine_factor,
            unknown_columns,
            driven_coefficients,
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
        let Some(factor) = &self.affine_factor else {
            return nonlinear::solve(
                &self.equations,
                &self.unknown,
                &self.unknown_columns,
                values,
                &self.tolerances,
            );
        };
        let rhs = self
            .equations
            .iter()
            .zip(&self.driven_coefficients)
            .map(|(eq, terms)| {
                eq.rhs_constant
                    - terms
                        .iter()
                        .map(|&(column, value)| value * inputs[column])
                        .sum::<f64>()
            })
            .collect();
        // Lazy preparation keeps Circuit::new and sample-error timing unchanged.
        // A new circuit (including one rebound to new event state) gets a new cache.
        let prepared = factor.get_or_init(|| {
            let matrix = self
                .equations
                .iter()
                .map(|eq| {
                    eq.coefficients
                        .iter()
                        .filter_map(|&(node, value)| {
                            self.unknown_columns[node].map(|column| (column, value))
                        })
                        .collect()
                })
                .collect();
            linear::Factorization::new(matrix, self.unknown.len())
        });
        let solved = match prepared {
            Ok(factor) => factor.solve(rhs),
            Err(error) => Err(Error::new(error.kind, error.message.clone())),
        }
        .map_err(|mut error| {
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
                    .map(|&(node, coefficient)| coefficient * values[node])
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
