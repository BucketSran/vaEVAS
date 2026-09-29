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
    dense_residuals: Vec<Option<DenseResidual>>,
    // Only coefficients are cached; inputs, solutions and physical state are not.
    affine_factor: Option<OnceLock<Result<linear::Factorization, Error>>>,
}

// Cache dense spans only when they occupy at most twice the actual terms.
// Sparse rows retain indexed traversal, so isolated distant nodes never cause
// an allocation proportional to their node-number span.
struct DenseResidual {
    start: usize,
    coefficients: Vec<f64>,
}

impl DenseResidual {
    fn prepare(terms: &linear::Row) -> Option<Self> {
        let start = terms.first()?.0;
        let length = terms.last()?.0 - start + 1;
        if terms.len() < 8 || length > 2 * terms.len() {
            return None;
        }
        let mut coefficients = vec![0.0; length];
        for &(node, value) in terms {
            coefficients[node - start] = value;
        }
        Some(Self {
            start,
            coefficients,
        })
    }

    fn evaluate(&self, values: &[f64]) -> f64 {
        self.coefficients
            .iter()
            .zip(&values[self.start..self.start + self.coefficients.len()])
            .map(|(a, v)| a * v)
            .sum()
    }
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
        let dense_residuals = if affine_factor.is_some() {
            equations
                .iter()
                .map(|eq| DenseResidual::prepare(&eq.rhs_terms))
                .collect()
        } else {
            Vec::new()
        };
        Ok(Self {
            nodes,
            equations,
            driven,
            unknown,
            tolerances,
            affine_factor,
            unknown_columns,
            driven_coefficients,
            dense_residuals,
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
        for (eq, dense) in self.equations.iter().zip(&self.dense_residuals) {
            // Check the original physical branch equation, not the eliminated matrix.
            let lhs = values[eq.positive] - values[eq.negative];
            let rhs = eq.rhs_constant
                + match dense {
                    Some(row) => row.evaluate(&values),
                    None => eq
                        .rhs_terms
                        .iter()
                        .map(|&(node, coefficient)| coefficient * values[node])
                        .sum::<f64>(),
                };
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

#[cfg(test)]
mod tests {
    use super::{Circuit, DenseResidual};
    use crate::events::EventModel;
    use crate::interval::Interval as I;
    use crate::ir::{Program, Tolerances, SCHEMA_VERSION};
    use crate::linear::Factorization;
    use serde_json::json;

    fn sparse_event_model() -> EventModel {
        let mut nodes = vec!["0".to_string(), "u".to_string()];
        nodes.extend((0..40).map(|i| format!("y{i}")));
        let u = json!({"op":"affine", "constant":0,
                       "terms":[{"node":1,"coefficient":1}]});
        let q = json!({"op":"state","state":0});
        let delta = 2.0_f64.powi(-55);
        let contributions: Vec<_> = (0..40)
            .map(|i| {
                json!({
                    "branch":{"instance":"dut","local_positive":format!("a{i}"),
                              "local_negative":"r","kind":"voltage"},
                    "positive":i+2,"negative":0,
                    "rhs":{"op":"add","left":q,"right":{"op":"affine", "constant":i as f64/8.0,
                        "terms":[{"node":1,"coefficient":1}]}},
                    "origin":{"source":"sparse-trial.va","line":i+1,"column":1,"instance":"dut"}
                })
            })
            .collect();
        let program: Program = serde_json::from_value(json!({
            "schema_version":SCHEMA_VERSION,"nodes":nodes,"contributions":contributions,
            "states":[{"instance":"dut","name":"q","kind":"real","initial":0}],
            "events":[{"trigger":{"kind":"timer","start":0.5,"period":0,
                                     "time_tolerance":1e-9,"enabled":true},
                "assignments":[
                    {"state":0,"rhs":u},
                    {"state":0,"rhs":{"op":"add","left":q,
                        "right":{"op":"affine","constant":delta,"terms":[]}}},
                    {"state":0,"rhs":{"op":"add","left":q,"right":{"op":"multiply",
                        "left":{"op":"affine","constant":-1,"terms":[]},"right":u}}}
                ],
                "origin":{"source":"sparse-trial.va","line":41,"column":1,"instance":"dut"}}]
        }))
        .unwrap();
        EventModel::new(program, vec!["u".into()], Tolerances::default()).unwrap()
    }

    fn assert_sparse(circuit: &Circuit) {
        assert!(matches!(
            circuit.affine_factor.as_ref().unwrap().get().unwrap(),
            Ok(Factorization::Sparse(_))
        ));
    }

    #[test]
    fn sparse_settlement_certifies_after_numeric_solve_and_retries_changed_inputs() {
        let model = sparse_event_model();
        let before = model.initial();
        let bounds = vec![I::ZERO];
        let accepted = model.circuit(&before).unwrap();
        let old = accepted.solve(&[0.0]).unwrap();
        assert_sparse(&accepted);
        let delta = 2.0_f64.powi(-55);
        // Same event batch throughout. A discarded good trial and a genuinely
        // failed forward certificate must not freeze the input or state values.
        for input in [0.0, 1.0, 1.0, 2.0_f64.powi(-56), 0.0] {
            let candidate = model.event_circuit(&[0], &before, &[]).unwrap();
            let numeric = candidate.solve(&[input]).unwrap();
            assert_sparse(&candidate);
            assert!(numeric.max_residual_ratio <= 1.0);
            let prepared =
                crate::settlement::prepare(&model, &[0], &[input], &before, &[], &bounds, &[]);
            if input == 1.0 {
                // Sequential binary64 replay loses delta in (1+delta)-1,
                // although the substituted voltage solve has a tiny residual.
                assert_eq!(prepared.err().unwrap().kind, "event_accuracy");
            } else {
                let (states, certified, circuit, solution) = prepared.unwrap();
                assert_eq!(states, [delta]);
                assert!(certified[0].lo <= delta && certified[0].hi >= delta);
                assert_sparse(&circuit);
                assert_eq!(solution.voltages[2], input + delta);
            }
            assert_eq!(before, [0.0]);
            assert_eq!(bounds, [I::ZERO]);
            assert_eq!(accepted.solve(&[0.0]).unwrap().voltages, old.voltages);
        }
    }

    #[test]
    fn sparse_factor_survives_original_relation_failure_then_new_rhs() {
        let model = sparse_event_model();
        let mut program = model.program.clone();
        program.states.clear();
        program.events.clear();
        for (i, c) in program.contributions.iter_mut().enumerate() {
            c.rhs = serde_json::from_value(json!({"op":"affine","constant":i as f64/8.0,
                "terms":[{"node":1,"coefficient":1}]}))
            .unwrap();
        }
        let mut redundant = program.contributions[0].clone();
        redundant.branch.instance = "clamp".into();
        redundant.origin.instance = "clamp".into();
        redundant.rhs =
            serde_json::from_value(json!({"op":"affine","constant":0,"terms":[]})).unwrap();
        program.contributions.push(redundant);
        let circuit = Circuit::new(program, &["u".into()], Tolerances::default()).unwrap();
        let initial = circuit.solve(&[0.0]).unwrap();
        assert_sparse(&circuit);
        assert_eq!(circuit.solve(&[1.0]).unwrap_err().kind, "residual_failure");
        assert_eq!(circuit.solve(&[0.0]).unwrap().voltages, initial.voltages);
    }

    #[test]
    fn dense_residual_span_keeps_holes_and_node_offset_without_distant_allocation() {
        // All eight products are one; missing positions must contribute zero.
        let terms = vec![
            (3, 1.0),
            (4, 2.0),
            (6, 4.0),
            (7, 8.0),
            (9, 16.0),
            (10, 32.0),
            (12, 64.0),
            (13, 128.0),
        ];
        let prepared = DenseResidual::prepare(&terms).unwrap();
        assert_eq!(prepared.coefficients.len(), 11);
        let mut values = vec![99.0; 15];
        for &(node, coefficient) in &terms {
            values[node] = 1.0 / coefficient;
        }
        assert_eq!(prepared.evaluate(&values), 8.0);
        let mut distant = terms;
        distant.last_mut().unwrap().0 = 1_000_000;
        assert!(DenseResidual::prepare(&distant).is_none());
    }
}
