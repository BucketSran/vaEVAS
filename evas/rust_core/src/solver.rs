//! Solve stateless operating points and check the original branch residuals.
use crate::assembly::{assemble, AssembledCircuit, Equation};
use crate::interval::Interval as I;
use crate::ir::{Error, Expression, Program, Solution, Tolerances};
use crate::{expression, linear, nonlinear};
use std::sync::{Arc, OnceLock};

type AffineFactor = Arc<OnceLock<Result<linear::Factorization, Error>>>;

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
    affine_factor: Option<AffineFactor>,
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

fn interval_power(base: I, exponent: u32) -> I {
    let mut result = I::ONE;
    for _ in 0..exponent {
        result = result * base;
    }
    result
}

fn add_dense_coefficient(row: &mut [f64], column: Option<usize>, value: f64) {
    if let Some(column) = column {
        row[column] += value;
    }
}

// For every fixed input in U, a nonzero derivative of constant sign makes F
// monotone on X. If |F(center,U)|/min|F'| fits strictly on both sides of the
// center, the mean value theorem gives opposite endpoint signs, hence one root
// in X. Distances are rounded inward; the error radius is rounded outward.
fn scalar_root_box(residual: I, derivative: I, center: f64, enclosure: I) -> bool {
    let minimum = if derivative.lo > 0.0 {
        derivative.lo
    } else if derivative.hi < 0.0 {
        -derivative.hi
    } else {
        return false;
    };
    if !residual.finite() || !derivative.finite() || !enclosure.finite() {
        return false;
    }
    let error = (I::point(residual.magnitude()) / I::point(minimum)).hi;
    let left = (I::point(center) - I::point(enclosure.lo)).lo;
    let right = (I::point(enclosure.hi) - I::point(center)).lo;
    error.is_finite() && error < left && error < right
}

struct IntervalValue {
    value: I,
    gradient: Vec<I>,
}

fn finite_interval(value: I, what: &str) -> Result<I, Error> {
    if value.finite() {
        Ok(value)
    } else {
        Err(Error::new(
            "waveform_accuracy",
            format!("cannot bound {what} with finite interval arithmetic"),
        ))
    }
}

pub(crate) fn interval_expression(expr: &Expression, values: &[I]) -> Result<I, Error> {
    finite_interval(
        interval_evaluate(expr, values)?.value,
        "waveform expression",
    )
}

fn interval_evaluate(expr: &Expression, values: &[I]) -> Result<IntervalValue, Error> {
    let count = values.len();
    let mut gradient = vec![I::ZERO; count];
    let value = match expr {
        Expression::State { .. } | Expression::Operator { .. } | Expression::Select { .. } => {
            return Err(Error::new(
                "unsupported_analysis",
                "waveform certificate requires bound states/operators and resolved conditions",
            ))
        }
        Expression::Affine { constant, terms } => {
            let mut value = I::point(*constant);
            for t in terms {
                value = value + I::point(t.coefficient) * values[t.node];
                gradient[t.node] = gradient[t.node] + I::point(t.coefficient);
            }
            value
        }
        Expression::Add { left, right } => {
            let left = interval_evaluate(left, values)?;
            let right = interval_evaluate(right, values)?;
            for (g, term) in gradient.iter_mut().zip(left.gradient) {
                *g = *g + term;
            }
            for (g, term) in gradient.iter_mut().zip(right.gradient) {
                *g = *g + term;
            }
            left.value + right.value
        }
        Expression::Multiply { left, right } => {
            let left = interval_evaluate(left, values)?;
            let right = interval_evaluate(right, values)?;
            for ((g, dl), dr) in gradient.iter_mut().zip(left.gradient).zip(right.gradient) {
                *g = dl * right.value + left.value * dr;
            }
            left.value * right.value
        }
        Expression::Power { base, exponent } => {
            let base = interval_evaluate(base, values)?;
            let derivative =
                I::point(f64::from(*exponent)) * interval_power(base.value, exponent - 1);
            for (g, db) in gradient.iter_mut().zip(base.gradient) {
                *g = derivative * db;
            }
            interval_power(base.value, *exponent)
        }
    };
    if value.finite() && gradient.iter().all(|g| g.finite()) {
        Ok(IntervalValue { value, gradient })
    } else {
        Err(Error::new(
            "waveform_accuracy",
            "cannot bound waveform value or derivative with finite interval arithmetic",
        ))
    }
}

impl Circuit {
    pub fn new(
        program: Program,
        driven_names: &[String],
        tolerances: Tolerances,
    ) -> Result<Self, Error> {
        let _timing = crate::diagnostics::span("circuit.prepare");

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
            .then(|| Arc::new(OnceLock::new()));
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

    fn waveform_jacobian_rows(&self, solution: &Solution) -> Result<Vec<linear::Row>, Error> {
        self.equations
            .iter()
            .map(|eq| {
                let mut row = vec![0.0; self.unknown.len()];
                add_dense_coefficient(&mut row, self.unknown_columns[eq.positive], 1.0);
                add_dense_coefficient(&mut row, self.unknown_columns[eq.negative], -1.0);
                for &(node, coefficient) in &eq.rhs_terms {
                    add_dense_coefficient(&mut row, self.unknown_columns[node], -coefficient);
                }
                for expr in &eq.nonlinear {
                    for (node, derivative) in expression::evaluate(expr, &solution.voltages)
                        .map_err(|mut error| {
                            error
                                .message
                                .push_str(&format!(" at {}", eq.origins.join(", ")));
                            error
                        })?
                        .gradient
                    {
                        add_dense_coefficient(&mut row, self.unknown_columns[node], -derivative);
                    }
                }
                if row.iter().any(|value| !value.is_finite()) {
                    return Err(Error::new(
                        "waveform_accuracy",
                        format!("nonfinite waveform Jacobian at {}", eq.origins.join(", ")),
                    ));
                }
                Ok(row
                    .into_iter()
                    .enumerate()
                    .filter_map(|(column, value)| (value != 0.0).then_some((column, value)))
                    .collect())
            })
            .collect()
    }

    fn interval_residuals(&self, values: &[I]) -> Result<Vec<I>, Error> {
        self.equations
            .iter()
            .map(|eq| {
                let mut residual = values[eq.positive] - values[eq.negative];
                for expr in &eq.original_rhs {
                    residual = residual
                        - interval_expression(expr, values).map_err(|mut error| {
                            error
                                .message
                                .push_str(&format!(" at {}", eq.origins.join(", ")));
                            error
                        })?;
                }
                finite_interval(residual, "waveform residual")
            })
            .collect()
    }

    fn interval_jacobian(&self, values: &[I]) -> Result<Vec<Vec<I>>, Error> {
        self.equations
            .iter()
            .map(|eq| {
                let mut row = vec![I::ZERO; self.unknown.len()];
                if let Some(column) = self.unknown_columns[eq.positive] {
                    row[column] = row[column] + I::ONE;
                }
                if let Some(column) = self.unknown_columns[eq.negative] {
                    row[column] = row[column] - I::ONE;
                }
                for expr in &eq.original_rhs {
                    for (node, derivative) in interval_evaluate(expr, values)
                        .map_err(|mut error| {
                            error
                                .message
                                .push_str(&format!(" at {}", eq.origins.join(", ")));
                            error
                        })?
                        .gradient
                        .into_iter()
                        .enumerate()
                    {
                        if let Some(column) = self.unknown_columns[node] {
                            row[column] = row[column] - derivative;
                        }
                    }
                }
                if row.iter().all(|entry| entry.finite()) {
                    Ok(row)
                } else {
                    Err(Error::new(
                        "waveform_accuracy",
                        format!("nonfinite interval Jacobian at {}", eq.origins.join(", ")),
                    ))
                }
            })
            .collect()
    }

    fn voltage_budget_lower(&self, voltage: f64) -> Result<f64, Error> {
        let budget = I::point(self.tolerances.absolute)
            + I::point(self.tolerances.relative) * I::point(voltage.abs());
        if budget.finite() && budget.lo > 0.0 {
            Ok(budget.lo)
        } else {
            Err(Error::new(
                "waveform_accuracy",
                "nonfinite waveform voltage budget",
            ))
        }
    }

    /// Certify that the accepted point solution also satisfies each original
    /// branch relation for the exact binary64-PWL input interval represented at
    /// this observation time, with a root inside the requested voltage box.
    /// Point inputs still require this forward-error proof: small floating-point
    /// residuals do not bound root error near a singular Jacobian.
    pub(crate) fn check_waveform_accuracy(
        &self,
        solution: &Solution,
        input_bounds: &[I],
    ) -> Result<(), Error> {
        let _timing = crate::diagnostics::span("voltage.waveform_certificate");

        if input_bounds.len() != self.driven.len() {
            return Err(Error::new(
                "invalid_inputs",
                "input bounds must contain one interval per driven node",
            ));
        }
        if input_bounds.iter().any(|b| !b.finite()) {
            return Err(Error::new(
                "waveform_accuracy",
                "cannot certify waveform accuracy with nonfinite input bounds",
            ));
        }
        let mut point_values = solution
            .voltages
            .iter()
            .copied()
            .map(I::point)
            .collect::<Vec<_>>();
        for (&node, &bounds) in self.driven.iter().zip(input_bounds) {
            point_values[node] = bounds;
        }
        let residuals = self.interval_residuals(&point_values)?;
        for (eq, residual) in self.equations.iter().zip(&residuals) {
            let lhs = solution.voltages[eq.positive] - solution.voltages[eq.negative];
            let mut rhs = eq.rhs_constant
                + eq.rhs_terms
                    .iter()
                    .map(|&(node, coefficient)| coefficient * solution.voltages[node])
                    .sum::<f64>();
            for expr in &eq.nonlinear {
                rhs += expression::evaluate(expr, &solution.voltages)
                    .map_err(|mut error| {
                        error
                            .message
                            .push_str(&format!(" at {}", eq.origins.join(", ")));
                        error
                    })?
                    .value;
            }
            let bound =
                self.tolerances.absolute + self.tolerances.relative * lhs.abs().max(rhs.abs());
            if !bound.is_finite() || residual.lo < -bound || residual.hi > bound {
                return Err(Error::new(
                    "waveform_accuracy",
                    format!(
                        "waveform residual interval [{:e}, {:e}] V exceeds ±{:e} V at {}",
                        residual.lo,
                        residual.hi,
                        bound,
                        eq.origins.join(", ")
                    ),
                ));
            }
        }
        if self.unknown.is_empty() {
            return Ok(());
        }
        let n = self.unknown.len();
        if self.equations.len() != n {
            return Err(Error::new(
                "waveform_accuracy",
                format!(
                    "Krawczyk waveform certificate requires a square system; got {} equations for {n} unknowns",
                    self.equations.len()
                ),
            ));
        }
        let mut box_values = point_values.clone();
        let mut deltas = Vec::with_capacity(n);
        for &node in &self.unknown {
            let center = solution.voltages[node];
            let budget = self.voltage_budget_lower(center)?;
            let lo = (center - budget).next_up();
            let hi = (center + budget).next_down();
            if !(lo < center && center < hi && lo.is_finite() && hi.is_finite()) {
                return Err(Error::new(
                    "waveform_accuracy",
                    format!(
                        "cannot build an inner waveform budget box at node {}",
                        self.nodes[node]
                    ),
                ));
            }
            box_values[node] = I { lo, hi };
            deltas.push(I { lo, hi } - I::point(center));
        }
        // A scalar monotonicity proof avoids constructing an inverse-like
        // matrix. A missed proof falls back to the unchanged Krawczyk path.
        // All contributions to a branch are replayed through original_rhs;
        // splitting a relation into several contributions does not bypass or
        // disable its proof. The nominal Jacobian is only a preconditioner.
        let scalar_jacobian = if n == 1 {
            let jacobian = self.interval_jacobian(&box_values)?;
            let node = self.unknown[0];
            if scalar_root_box(
                residuals[0],
                jacobian[0][0],
                solution.voltages[node],
                box_values[node],
            ) {
                return Ok(());
            }
            Some(jacobian)
        } else {
            None
        };
        let jacobian = self.waveform_jacobian_rows(solution)?;
        let factor = linear::Factorization::new(jacobian, n).map_err(|error| {
            Error::new(
                "waveform_accuracy",
                format!(
                    "cannot build Krawczyk waveform preconditioner from local Jacobian: {}",
                    error.message
                ),
            )
        })?;
        let mut preconditioner = vec![vec![0.0; n]; n];
        for row_index in 0..n {
            let mut rhs = vec![0.0; n];
            rhs[row_index] = 1.0;
            let column = factor.solve(rhs).map_err(|error| {
                Error::new(
                    "waveform_accuracy",
                    format!(
                        "cannot solve Krawczyk waveform preconditioner column: {}",
                        error.message
                    ),
                )
            })?;
            for (column_index, value) in column.into_iter().enumerate() {
                if !value.is_finite() {
                    return Err(Error::new(
                        "waveform_accuracy",
                        "nonfinite Krawczyk waveform preconditioner",
                    ));
                }
                preconditioner[column_index][row_index] = value;
            }
        }
        let interval_jacobian = match scalar_jacobian {
            Some(jacobian) => jacobian,
            None => self.interval_jacobian(&box_values)?,
        };
        let mut max_norm = 0.0_f64;
        let mut krawczyk = vec![I::ZERO; n];
        for j in 0..n {
            let mut correction = I::ZERO;
            for i in 0..n {
                correction = correction + I::point(preconditioner[j][i]) * residuals[i];
            }
            let mut image = I::point(solution.voltages[self.unknown[j]]) - correction;
            let mut row_norm = I::ZERO;
            for k in 0..n {
                let mut entry = if j == k { I::ONE } else { I::ZERO };
                for i in 0..n {
                    entry = entry - I::point(preconditioner[j][i]) * interval_jacobian[i][k];
                }
                row_norm = row_norm + I::point(entry.magnitude());
                image = image + entry * deltas[k];
            }
            if !row_norm.finite() || !image.finite() {
                return Err(Error::new(
                    "waveform_accuracy",
                    "nonfinite Krawczyk waveform image",
                ));
            }
            max_norm = max_norm.max(row_norm.hi);
            krawczyk[j] = image;
        }
        if max_norm.partial_cmp(&1.0) != Some(std::cmp::Ordering::Less) {
            return Err(Error::new(
                "waveform_accuracy",
                format!("Krawczyk waveform contraction bound {max_norm:e} is not below 1"),
            ));
        }
        for (j, &node) in self.unknown.iter().enumerate() {
            let image = krawczyk[j];
            let budget_box = box_values[node];
            if !(image.lo > budget_box.lo && image.hi < budget_box.hi) {
                return Err(Error::new(
                    "waveform_accuracy",
                    format!(
                        "Krawczyk waveform image [{:e}, {:e}] V is not strictly inside [{:e}, {:e}] V at node {}",
                        image.lo,
                        image.hi,
                        budget_box.lo,
                        budget_box.hi,
                        self.nodes[node]
                    ),
                ));
            }
            let budget = self.voltage_budget_lower(solution.voltages[node])?;
            let distance = (image - I::point(solution.voltages[node])).magnitude();
            if !distance.is_finite() || distance > budget {
                return Err(Error::new(
                    "waveform_accuracy",
                    format!(
                        "Krawczyk waveform distance {distance:e} V exceeds budget {budget:e} V at node {}",
                        self.nodes[node]
                    ),
                ));
            }
        }
        Ok(())
    }

    /// A stateless operating point. No previous solution or physical history is
    /// read or changed. Dynamic trial/commit state is deliberately not present.
    pub fn solve(&self, inputs: &[f64]) -> Result<Solution, Error> {
        self.solve_with_initial(inputs, None)
    }

    /// Stateless operating point with a caller-supplied voltage initial guess.
    /// This is used by transient observation-only polynomial solves; accepted
    /// voltage history is only a Newton seed and never physical simulator state.
    pub(crate) fn solve_with_initial(
        &self,
        inputs: &[f64],
        initial_voltages: Option<&[f64]>,
    ) -> Result<Solution, Error> {
        let _timing = crate::diagnostics::span("circuit.solve");
        crate::diagnostics::counter("circuit_solve_calls", 1);

        if inputs.len() != self.driven.len() || inputs.iter().any(|x| !x.is_finite()) {
            return Err(Error::new(
                "invalid_inputs",
                "sample must contain one finite value per driven node",
            ));
        }
        if let Some(guess) = initial_voltages {
            if guess.len() != self.nodes.len() || guess.iter().any(|x| !x.is_finite()) {
                return Err(Error::new(
                    "invalid_inputs",
                    "initial voltage guess must contain one finite value per node",
                ));
            }
        }
        let mut values = vec![0.0; self.nodes.len()];
        if let Some(guess) = initial_voltages {
            for &node in &self.unknown {
                values[node] = guess[node];
            }
        }
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
        match self.check_affine_residuals(&values) {
            Ok((absolute, ratio)) => Ok(Self::affine_solution(values, absolute, ratio)),
            Err(error) if error.kind == "residual_failure" => {
                // A failed trial may use two corrections with the same LU.
                // The original voltage equations still decide acceptance.
                prepared
                    .as_ref()
                    .ok()
                    .and_then(|factor| self.refine_affine(factor, values))
                    .ok_or(error)
            }
            Err(error) => Err(error),
        }
    }

    fn affine_solution(values: Vec<f64>, absolute: f64, ratio: f64) -> Solution {
        Solution {
            voltages: values,
            max_residual_v: absolute,
            max_residual_ratio: ratio,
            max_scaled_residual_ratio: None,
            max_voltage_correction_v: None,
            max_voltage_correction_ratio: None,
        }
    }

    fn refine_affine(
        &self,
        factor: &linear::Factorization,
        mut values: Vec<f64>,
    ) -> Option<Solution> {
        let residuals = |values: &[f64]| -> Option<Vec<f64>> {
            self.equations
                .iter()
                .map(|eq| linear::refinement_residual(eq.rhs_constant, &eq.coefficients, values))
                .collect()
        };
        let norm = |r: &[f64]| r.iter().fold(0.0_f64, |a, b| a.max(b.abs()));
        let mut residual = residuals(&values)?;
        for _ in 0..2 {
            let correction = factor.solve(residual.clone()).ok()?;
            let mut candidate = values.clone();
            for (&node, delta) in self.unknown.iter().zip(correction) {
                candidate[node] += delta;
            }
            if candidate.iter().any(|v| !v.is_finite()) || candidate == values {
                return None;
            }
            let next = residuals(&candidate)?;
            if norm(&next) >= norm(&residual) {
                return None;
            }
            if let Ok((absolute, ratio)) = self.check_affine_residuals(&candidate) {
                return Some(Self::affine_solution(candidate, absolute, ratio));
            }
            values = candidate;
            residual = next;
        }
        None
    }

    /// Reuse only an identical numeric matrix. RHS and all physical checks stay
    /// local. Changed coefficients/order or a nonlinear mode prevent reuse.
    pub(crate) fn reuse_affine_factor_from(&mut self, previous: &Self) {
        let compatible = self.affine_factor.is_some()
            && previous.affine_factor.is_some()
            && self.nodes == previous.nodes
            && self.unknown == previous.unknown
            && self.driven == previous.driven
            && self.equations.len() == previous.equations.len()
            && self
                .equations
                .iter()
                .zip(&previous.equations)
                .all(|(a, b)| {
                    a.coefficients.len() == b.coefficients.len()
                        && a.coefficients
                            .iter()
                            .zip(&b.coefficients)
                            .all(|((na, va), (nb, vb))| na == nb && va.to_bits() == vb.to_bits())
                });
        if compatible {
            self.affine_factor.clone_from(&previous.affine_factor);
            crate::diagnostics::counter("affine_cache_links", 1);
        }
    }

    fn check_affine_residuals(&self, values: &[f64]) -> Result<(f64, f64), Error> {
        let _timing = crate::diagnostics::span("voltage.original_residual");

        let mut max_residual_v = 0.0_f64;
        let mut max_residual_ratio = 0.0_f64;
        for (eq, dense) in self.equations.iter().zip(&self.dense_residuals) {
            // Check the original physical branch equation, not the eliminated matrix.
            let lhs = values[eq.positive] - values[eq.negative];
            let rhs = eq.rhs_constant
                + match dense {
                    Some(row) => row.evaluate(values),
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
        Ok((max_residual_v, max_residual_ratio))
    }
}

#[cfg(test)]
mod tests {
    use super::{scalar_root_box, Circuit, DenseResidual};
    use crate::events::EventModel;
    use crate::interval::Interval as I;
    use crate::ir::{Program, Tolerances, SCHEMA_VERSION};
    use crate::linear::Factorization;
    use serde_json::json;

    #[test]
    fn scalar_root_box_uses_both_slope_orientations_and_strict_inward_distances() {
        let residual = I { lo: -0.1, hi: 0.1 };
        let enclosure = I { lo: 1.9, hi: 2.1 };
        for derivative in [I { lo: 3.0, hi: 4.0 }, I { lo: -4.0, hi: -3.0 }] {
            assert!(scalar_root_box(residual, derivative, 2.0, enclosure));
        }
        // An endpoint root is not a strict interior certificate.
        assert!(!scalar_root_box(
            I::ONE,
            I::ONE,
            0.0,
            I { lo: -1.0, hi: 1.0 }
        ));
        assert!(scalar_root_box(
            I::ZERO,
            I::ONE,
            1.0,
            I {
                lo: 1.0_f64.next_down(),
                hi: 1.0_f64.next_up(),
            }
        ));
    }

    #[test]
    fn scalar_root_box_does_not_accept_small_residual_with_large_root_error() {
        assert!(!scalar_root_box(
            I {
                lo: -1e-13,
                hi: 1e-13
            },
            I::point(1e-12),
            0.0,
            I {
                lo: -1e-10,
                hi: 1e-10
            },
        ));
        for derivative in [I::ZERO, I { lo: -1.0, hi: 1.0 }, I::point(1e-308)] {
            assert!(!scalar_root_box(
                I::point(1e308),
                derivative,
                0.0,
                I { lo: -1.0, hi: 1.0 }
            ));
        }
    }

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
                "body":[
                    {"kind":"assign", "state":0,"rhs":u},
                    {"kind":"assign", "state":0,"rhs":{"op":"add","left":q,
                        "right":{"op":"affine","constant":delta,"terms":[]}}},
                    {"kind":"assign", "state":0,"rhs":{"op":"add","left":q,"right":{"op":"multiply",
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
        let mut program = sparse_event_model().program;
        // y0=q exposes the lost exact 2^-55 even when other sparse rows
        // have large offsets. Retain their topology and sparse dispatch.
        program.contributions[0].rhs =
            serde_json::from_value(json!({"op":"state","state":0})).unwrap();
        let model = EventModel::new(
            program,
            vec!["u".into()],
            Tolerances {
                absolute: 1e-20,
                relative: 1e-5,
            },
        )
        .unwrap();
        let before = model.initial();
        let bounds = vec![I::ZERO];
        let accepted = model.circuit(&before).unwrap();
        let old = accepted.solve(&[0.0]).unwrap();
        assert_sparse(&accepted);
        let delta = 2.0_f64.powi(-55);
        // Same event batch throughout. A discarded good trial and a genuinely
        // failed forward certificate must not freeze the input or state values.
        for input in [0.0, 1.0, 1.0, 2.0_f64.powi(-56), 0.0] {
            let selection = model.conditions.select(&[0], &[I::point(input)]).unwrap();
            let candidate = model.event_circuit(&selection, &before, &[]).unwrap();
            let numeric = candidate.solve(&[input]).unwrap();
            assert_sparse(&candidate);
            assert!(numeric.max_residual_ratio <= 1.0);
            let prepared = crate::settlement::prepare(
                &model,
                &[0],
                (&[input], &[I::point(input)]),
                &before,
                &[],
                &bounds,
                &[],
                Some(&accepted),
            );
            if input == 1.0 {
                // Sequential binary64 replay loses delta in (1+delta)-1,
                // although the substituted voltage solve has a tiny residual.
                assert_eq!(prepared.err().unwrap().kind, "event_accuracy");
            } else {
                let crate::settlement::Prepared {
                    states,
                    bounds: certified,
                    circuit,
                    solution,
                    ..
                } = prepared.unwrap();
                assert_eq!(states, [delta]);
                assert!(certified[0].lo <= delta && certified[0].hi >= delta);
                assert_sparse(&circuit);
                assert_eq!(solution.voltages[2], delta);
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
    fn initial_voltage_guess_must_match_node_shape_and_be_finite() {
        let program: Program = serde_json::from_value(json!({
            "schema_version": SCHEMA_VERSION,
            "nodes": ["0", "u", "y"],
            "contributions": [{
                "branch": {"instance": "dut", "local_positive": "0",
                           "local_negative": "y", "kind": "voltage"},
                "positive": 0, "negative": 2,
                "rhs": {"op": "affine", "constant": 0,
                        "terms": [{"node": 1, "coefficient": -1}]},
                "origin": {"source": "guess.va", "line": 1, "column": 1,
                           "instance": "dut"}
            }]
        }))
        .unwrap();
        let circuit = Circuit::new(program, &["u".into()], Tolerances::default()).unwrap();
        assert_eq!(
            circuit
                .solve_with_initial(&[1.0], Some(&[0.0, 1.0]))
                .unwrap_err()
                .kind,
            "invalid_inputs"
        );
        assert_eq!(
            circuit
                .solve_with_initial(&[1.0], Some(&[0.0, 1.0, f64::NAN]))
                .unwrap_err()
                .kind,
            "invalid_inputs"
        );
        assert_eq!(
            circuit
                .solve_with_initial(&[2.0], Some(&[0.0, 99.0, -4.0]))
                .unwrap()
                .voltages,
            [0.0, 2.0, 2.0]
        );
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

#[cfg(test)]
#[path = "solver_cache_tests.rs"]
mod cache_tests;
