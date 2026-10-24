//! Solve stateless operating points and check the original branch residuals.
use crate::assembly::{assemble, AssembledCircuit, Equation};
use crate::interval::Interval as I;
use crate::ir::{Error, Expression, Program, Solution, Tolerances};
use crate::{expression, linear, nonlinear};
use std::sync::{Arc, OnceLock};

pub(crate) type ForcingRow = (
    usize,
    usize,
    usize,
    f64,
    f64,
    I,
    Expression,
    crate::ir::Origin,
);

type AffineFactor = Arc<OnceLock<Result<linear::Factorization, Error>>>;

#[derive(Clone)]
pub struct Circuit {
    pub nodes: Vec<String>,
    pub(crate) forcing_phase: Option<(usize, f64)>,
    forcing_bounds: Vec<(usize, [f64; 2])>,
    forcing_offsets: Vec<(usize, f64)>,
    procedure_parameters: Vec<(f64, I)>,
    procedure_view: Option<std::sync::Arc<crate::procedure::CircuitView>>,
    procedure_occurrence: Option<std::sync::Arc<crate::procedure::CircuitView>>,
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
#[derive(Clone)]
struct DenseResidual {
    start: usize,
    coefficients: Vec<f64>,
}

impl Circuit {
    pub(crate) fn retain_procedure_occurrence(&mut self, source: &Self) {
        self.procedure_occurrence = source
            .procedure_view
            .as_ref()
            .filter(|v| !v.plan.actions.is_empty())
            .cloned();
    }
    pub(crate) fn procedure_view(&self) -> Option<&std::sync::Arc<crate::procedure::CircuitView>> {
        self.procedure_view.as_ref()
    }
    pub(crate) fn procedure_occurrence(
        &self,
    ) -> Option<&std::sync::Arc<crate::procedure::CircuitView>> {
        self.procedure_occurrence.as_ref()
    }
    pub(crate) fn set_procedure_view(
        &mut self,
        view: std::sync::Arc<crate::procedure::CircuitView>,
    ) {
        self.procedure_view = Some(view);
    }
    pub(crate) fn set_procedure_parameters(&mut self, values: Vec<f64>) {
        self.procedure_parameters = values.into_iter().map(|v| (v, I::point(v))).collect();
    }
    pub(crate) fn set_procedure_parameter_bounds(&mut self, bounds: &[I]) -> Result<(), Error> {
        if bounds.len() != self.procedure_parameters.len() {
            return Err(Error::new(
                "invalid_ir",
                "procedure parameter bounds mismatch",
            ));
        }
        for ((_, slot), &value) in self.procedure_parameters.iter_mut().zip(bounds) {
            *slot = value;
        }
        Ok(())
    }

    /// Prepay actual candidate storage. The cached factorization is an Arc.
    pub(crate) fn charge_history_copy(
        &self,
        w: &crate::transition_source_plan::Work,
    ) -> Result<(), Error> {
        w.debit(2, 15)?;
        w.debit(
            2,
            (2 + 3 * self.forcing_bounds.len() + 2 * self.forcing_offsets.len()) as u64,
        )?;
        for node in &self.nodes {
            w.step()?;
            w.debit(2, node.len() as u64)?;
        }
        w.debit(
            2,
            (self.driven.len() + self.unknown.len() + self.unknown_columns.len()) as u64,
        )?;
        for equation in &self.equations {
            w.step()?;
            w.debit(
                2,
                (9 + equation.branch.instance.len()
                    + equation.branch.local_positive.len()
                    + equation.branch.local_negative.len()
                    + 2 * equation.rhs_terms.len()
                    + 2 * equation.coefficients.len()) as u64,
            )?;
            for expression in equation.nonlinear.iter().chain(&equation.original_rhs) {
                crate::history_admission::charge_expression_copy(expression, w)?;
            }
            for origin in &equation.origins {
                w.step()?;
                w.debit(2, origin.len() as u64)?;
            }
        }
        for row in &self.driven_coefficients {
            w.step()?;
            w.debit(2, (2 * row.len()) as u64)?;
        }
        for residual in &self.dense_residuals {
            w.step()?;
            if let Some(residual) = residual {
                w.debit(2, (1 + residual.coefficients.len()) as u64)?;
            }
        }
        Ok(())
    }
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
        interval_evaluate(expr, values, None)?.value,
        "waveform expression",
    )
}

fn interval_evaluate(
    expr: &Expression,
    values: &[I],
    work: Option<&crate::transition_source_plan::Work>,
) -> Result<IntervalValue, Error> {
    let count = values.len();
    if let Some(w) = work {
        w.debit(2, (count.saturating_mul(16) + 32) as u64)?;
    }
    let mut gradient = vec![I::ZERO; count];
    let value = match expr {
        Expression::EventMath { function, args, .. }
            if crate::operators::Function::from_internal(*function).is_some() =>
        {
            if let Some(w) = work {
                w.debit(2, 4096)?;
            }
            let function = crate::operators::Function::from_internal(*function).unwrap();
            let input = interval_evaluate(&args[0], values, work)?;
            let value = function.bounds(input.value)?;
            let derivative = function.derivative(input.value).unwrap_or(I {
                lo: f64::NEG_INFINITY,
                hi: f64::INFINITY,
            });
            for (g, d) in gradient.iter_mut().zip(input.gradient) {
                *g = derivative * d;
            }
            value
        }
        Expression::RealBoundary { value, .. } => {
            let v = interval_evaluate(value, values, work)?;
            let image = crate::real_expression::interval(v.value, work)?;
            if image.lo.to_bits() != image.hi.to_bits() {
                gradient.fill(I {
                    lo: f64::NEG_INFINITY,
                    hi: f64::INFINITY,
                });
            }
            image
        }
        Expression::RealBinary {
            operation,
            left,
            right,
            ..
        } => {
            let a = interval_evaluate(left, values, work)?;
            let b = interval_evaluate(right, values, work)?;
            let image =
                crate::real_expression::binary_interval(*operation, a.value, b.value, work)?;
            if image.lo.to_bits() != image.hi.to_bits() {
                gradient.fill(I {
                    lo: f64::NEG_INFINITY,
                    hi: f64::INFINITY,
                });
            }
            image
        }
        Expression::RealCall { .. } | Expression::UnsupportedSystemCall { .. } => {
            return Err(Error::new(
                "invalid_ir",
                "unexecuted procedure call requires its owning source frame",
            ))
        }
        Expression::RealLocal { .. } => return Err(Error::new("invalid_ir", "unbound real local")),
        Expression::Forcing { .. } => {
            return Err(Error::new(
                "unsupported_forcing_scope",
                "forcing marker requires its owning independent component dispatcher",
            ))
        }
        Expression::IntegerPrimitive { .. }
        | Expression::ArrayRead { .. }
        | Expression::IntegerRound { .. }
        | Expression::CheckedInteger { .. }
        | Expression::CheckedIndex { .. }
        | Expression::EventMath { .. }
        | Expression::State { .. }
        | Expression::Operator { .. }
        | Expression::Select { .. } => {
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
            let left = interval_evaluate(left, values, work)?;
            let right = interval_evaluate(right, values, work)?;
            for (g, term) in gradient.iter_mut().zip(left.gradient) {
                *g = *g + term;
            }
            for (g, term) in gradient.iter_mut().zip(right.gradient) {
                *g = *g + term;
            }
            left.value + right.value
        }
        Expression::Multiply { left, right } => {
            let left = interval_evaluate(left, values, work)?;
            let right = interval_evaluate(right, values, work)?;
            for ((g, dl), dr) in gradient.iter_mut().zip(left.gradient).zip(right.gradient) {
                *g = dl * right.value + left.value * dr;
            }
            left.value * right.value
        }
        Expression::Divide { left, right } => {
            let left = interval_evaluate(left, values, work)?;
            let right = interval_evaluate(right, values, work)?;
            if right.value.lo <= 0. && right.value.hi >= 0. {
                return Err(Error::new(
                    "waveform_accuracy",
                    "division denominator interval contains zero",
                ));
            }
            for ((g, dl), dr) in gradient.iter_mut().zip(left.gradient).zip(right.gradient) {
                *g = dl / right.value - left.value * dr / (right.value * right.value);
            }
            left.value / right.value
        }
        Expression::Power { base, exponent } => {
            let base = interval_evaluate(base, values, work)?;
            let derivative =
                I::point(f64::from(*exponent)) * interval_power(base.value, exponent - 1);
            for (g, db) in gradient.iter_mut().zip(base.gradient) {
                *g = derivative * db;
            }
            interval_power(base.value, *exponent)
        }
    };
    if value.finite() {
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
        let assembled = assemble(program, driven_names, tolerances)?;
        Self::from_assembled(assembled)
    }

    /// `Circuit::new` for trial rebuilds that share one assembly structure.
    /// The scratch plan skips only validation, grouping and label work; every
    /// numeric equation value is recomputed in the original contribution
    /// order, so a reused build is bit-identical to `Circuit::new`.
    pub(crate) fn new_with_scratch(
        program: Program,
        driven_names: &[String],
        tolerances: Tolerances,
        scratch: &mut Option<crate::assembly::AssemblyPlan>,
    ) -> Result<Self, Error> {
        let _timing = crate::diagnostics::span("circuit.prepare");
        let assembled =
            crate::assembly::assemble_with_plan(program, driven_names, tolerances, scratch)?;
        Self::from_assembled(assembled)
    }

    fn from_assembled(
        AssembledCircuit {
            nodes,
            equations,
            driven,
            unknown,
            tolerances,
        }: AssembledCircuit,
    ) -> Result<Self, Error> {
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
            forcing_phase: None,
            forcing_bounds: Vec::new(),
            forcing_offsets: Vec::new(),
            procedure_parameters: Vec::new(),
            procedure_view: None,
            procedure_occurrence: None,
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
                        - interval_evaluate(
                            expr,
                            values,
                            self.procedure_view.as_ref().map(|v| &v.plan.work),
                        )
                        .map(|v| v.value)
                        .map_err(|mut error| {
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
                    for (node, derivative) in interval_evaluate(
                        expr,
                        values,
                        self.procedure_view.as_ref().map(|v| &v.plan.work),
                    )
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
        self.waveform_bounds(solution, input_bounds).map(|_| ())
    }

    /// Return the enclosure already established by the original-relation proof.
    /// This exposes its certificate without a second solve or weaker acceptance.
    pub(crate) fn waveform_bounds(
        &self,
        solution: &Solution,
        input_bounds: &[I],
    ) -> Result<Vec<I>, Error> {
        if let Some(view) = &self.procedure_view {
            view.plan.work.debit(2, 0)?;
        }
        let expanded;
        let solution = if let Some(view) = &self.procedure_view {
            if solution.voltages.len() == view.node_count {
                expanded = Solution {
                    voltages: view.expand(&solution.voltages)?,
                    ..solution.clone()
                };
                &expanded
            } else {
                solution
            }
        } else {
            solution
        };
        let mut bounds = self.waveform_bounds_complete(solution, input_bounds)?;
        if let Some(view) = &self.procedure_view {
            bounds.truncate(view.node_count);
        }
        Ok(bounds)
    }
    fn reserve_waveform_retry(
        &self,
        inputs: usize,
        n: usize,
        work: &crate::transition_source_plan::Work,
    ) -> Result<(), Error> {
        // The unchanged interval evaluator prepays every interval gradient.
        // Count rectangular rows as well as unknown columns: redundant voltage
        // constraints still allocate rows and participate in LU elimination.
        // Factorization::new unconditionally chooses Dense below 32 columns.
        // Its bound excludes BTree updates that cannot occur in that branch;
        // larger systems retain the conservative sparse-tree reservation.
        let n = n as u64;
        let m = self.equations.len() as u64;
        let n2 = n.saturating_mul(n);
        let n3 = n2.saturating_mul(n);
        let mn = m.saturating_mul(n);
        let mn2 = mn.saturating_mul(n);
        let arithmetic = if n < 32 {
            n3.saturating_mul(512)
                .saturating_add(n2.saturating_mul(512))
                .saturating_add(mn2.saturating_mul(32))
        } else {
            n3.saturating_add(mn2).saturating_mul(4096)
        };
        let storage = n2
            .saturating_add(mn)
            .saturating_add(m)
            .saturating_add(self.nodes.len() as u64)
            .saturating_add(inputs as u64)
            .saturating_add(1)
            .saturating_mul(256);
        work.debit(2, arithmetic.saturating_add(storage))?;
        // Existing failure messages can name a complete voltage node. Reserve
        // actual string bytes before the repeated proof can construct one.
        for name in &self.nodes {
            work.debit(2, (name.len() as u64).saturating_mul(4).saturating_add(32))?;
        }
        fn shape(
            e: &Expression,
            w: &crate::transition_source_plan::Work,
        ) -> Result<(u64, u64), Error> {
            w.step()?;
            let combine = |a: (u64, u64), b: (u64, u64)| {
                (
                    a.0.saturating_add(b.0).saturating_add(1),
                    a.1.saturating_add(b.1),
                )
            };
            match e {
                Expression::Affine { terms, .. } => Ok((1, terms.len() as u64)),
                Expression::Add { left, right }
                | Expression::Multiply { left, right }
                | Expression::Divide { left, right }
                | Expression::RealBinary { left, right, .. } => {
                    Ok(combine(shape(left, w)?, shape(right, w)?))
                }
                Expression::Power { base, exponent } => {
                    let (a, b) = shape(base, w)?;
                    Ok((a.saturating_add(u64::from(*exponent)).saturating_add(1), b))
                }
                Expression::RealBoundary { value, .. } => {
                    let (a, b) = shape(value, w)?;
                    Ok((a.saturating_add(1), b))
                }
                Expression::EventMath { function, args, .. }
                    if crate::operators::Function::from_internal(*function).is_some()
                        && args.len() == 1 =>
                {
                    let (a, b) = shape(&args[0], w)?;
                    Ok((a.saturating_add(1), b))
                }
                _ => Err(Error::new(
                    "waveform_accuracy",
                    "original waveform retry requires already bound mathematical expressions",
                )),
            }
        }
        for equation in &self.equations {
            work.step()?;
            // Native affine residual/Jacobian traversals do not enter the paid
            // interval visitor. Pay their actual stored terms before retrying.
            work.debit(
                2,
                (equation.rhs_terms.len() as u64)
                    .saturating_mul(32)
                    .saturating_add((equation.original_rhs.len() as u64).saturating_mul(32))
                    .saturating_add(64),
            )?;
            // At most two nominal AD visits: residual and Jacobian. Each
            // sparse gradient has no more than min(refs,node_count) entries.
            for expression in &equation.nonlinear {
                let (ops, refs) = shape(expression, work)?;
                let width = refs.min(self.nodes.len() as u64).saturating_add(1);
                work.debit(
                    2,
                    ops.saturating_add(refs)
                        .saturating_mul(width)
                        .saturating_mul(128)
                        .saturating_add(64),
                )?;
            }
            for origin in &equation.origins {
                work.debit(
                    2,
                    (origin.len() as u64).saturating_mul(4).saturating_add(32),
                )?;
            }
        }
        Ok(())
    }
    fn waveform_bounds_complete(
        &self,
        solution: &Solution,
        input_bounds: &[I],
    ) -> Result<Vec<I>, Error> {
        self.waveform_bounds_attempt(solution, input_bounds, true)
    }
    fn waveform_bounds_attempt(
        &self,
        solution: &Solution,
        input_bounds: &[I],
        contract: bool,
    ) -> Result<Vec<I>, Error> {
        if let Some(view) = &self.procedure_view {
            view.plan.work.debit(2, 0)?;
        }
        if let Some(view) = &self.procedure_view {
            if let Some(bounds) =
                view.plan
                    .cell_bounds(input_bounds, &solution.voltages, self.nodes.len())?
            {
                return Ok(bounds);
            }
        }

        let _timing = crate::diagnostics::span("voltage.waveform_certificate");

        let extended;
        let input_bounds = if !self.procedure_parameters.is_empty()
            && input_bounds.len() + self.procedure_parameters.len() == self.driven.len()
        {
            extended = input_bounds
                .iter()
                .copied()
                .chain(self.procedure_parameters.iter().map(|(_, b)| *b))
                .collect::<Vec<_>>();
            extended.as_slice()
        } else {
            input_bounds
        };
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
        // Exact residuals in a point-input affine system establish an exact
        // representable root; the already successful factorization proves
        // uniqueness. This does not require a floating box wider than one ULP.
        if contract
            && self.procedure_view.is_some()
            && input_bounds
                .iter()
                .all(|b| b.lo.to_bits() == b.hi.to_bits())
            && residuals.iter().all(|r| r.lo == 0. && r.hi == 0.)
            && self
                .affine_factor
                .as_ref()
                .and_then(|f| f.get())
                .is_some_and(Result::is_ok)
        {
            return Ok(point_values);
        }
        if self.unknown.is_empty() {
            return Ok(point_values);
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
        // Rounded operations are discontinuous across cells. First contract
        // grounded equations with their full value images, retaining every
        // possible root in the original voltage-budget box. A singleton fixed
        // box plus exact residual zero proves existence and uniqueness there.
        if let Some(view) = self.procedure_view.as_ref().filter(|_| contract) {
            loop {
                view.plan.work.debit(
                    2,
                    ((self.nodes.len() + self.equations.len() + 1) * 64) as u64,
                )?;
                let mut changed = false;
                for eq in &self.equations {
                    let (node, sign) = if eq.negative == 0 {
                        (eq.positive, 1.)
                    } else if eq.positive == 0 {
                        (eq.negative, -1.)
                    } else {
                        continue;
                    };
                    if self.unknown_columns[node].is_none() {
                        continue;
                    }
                    let mut image = I::ZERO;
                    for rhs in &eq.original_rhs {
                        image = image
                            + interval_evaluate(rhs, &box_values, Some(&view.plan.work))?.value;
                    }
                    image = I::point(sign) * image;
                    let old = box_values[node];
                    let next = I {
                        lo: old.lo.max(image.lo),
                        hi: old.hi.min(image.hi),
                    };
                    if next.lo > next.hi {
                        return Err(Error::new(
                            "waveform_accuracy",
                            "rounded equation images have no common physical root",
                        ));
                    }
                    changed |= next.lo.to_bits() != old.lo.to_bits()
                        || next.hi.to_bits() != old.hi.to_bits();
                    box_values[node] = next;
                }
                if self
                    .unknown
                    .iter()
                    .all(|&node| box_values[node].lo.to_bits() == box_values[node].hi.to_bits())
                {
                    let exact = self.interval_residuals(&box_values)?;
                    if exact.iter().all(|r| r.lo == 0. && r.hi == 0.) {
                        return Ok(box_values);
                    }
                }
                if !changed {
                    break;
                }
            }
            for (j, &node) in self.unknown.iter().enumerate() {
                deltas[j] = box_values[node] - I::point(solution.voltages[node]);
            }
        }
        // A scalar monotonicity proof avoids constructing an inverse-like
        // matrix. A missed proof falls back to the unchanged Krawczyk path.
        // All contributions to a branch are replayed through original_rhs;
        // splitting a relation into several contributions does not bypass or
        // disable its proof. The nominal Jacobian is only a preconditioner.
        let scalar_jacobian = if n == 1 {
            let jacobian = self.interval_jacobian(&box_values)?;
            let node = self.unknown[0];
            if contract
                && scalar_root_box(
                    residuals[0],
                    jacobian[0][0],
                    solution.voltages[node],
                    box_values[node],
                )
            {
                // Mean value theorem: each true root differs from the center
                // by -F(center,U)/F'(X,U). Preserve that image, not only success.
                point_values[node] =
                    I::point(solution.voltages[node]) - residuals[0] / jacobian[0][0];
                return Ok(point_values);
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
                if contract {
                    if let Some(view) = &self.procedure_view {
                        // A fresh complete certificate on the original inner
                        // voltage-budget box, never an intersection of K and X.
                        // The first attempt and its fees remain consumed.
                        self.reserve_waveform_retry(input_bounds.len(), n, &view.plan.work)?;
                        return self.waveform_bounds_attempt(solution, input_bounds, false);
                    }
                }
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
        for (j, &node) in self.unknown.iter().enumerate() {
            point_values[node] = krawczyk[j];
        }
        Ok(point_values)
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
        let initial_expanded = initial_voltages
            .map(|v| match &self.procedure_view {
                Some(view) if v.len() == view.node_count => view.expand(v),
                _ => Ok(v.to_vec()),
            })
            .transpose()?;
        // Propose an affine root without RN only inside the cell verifier.
        // Acceptance still requires a distinct exact rational neighborhood on
        // which every executed RN node is constant and the frozen physical
        // affine system has one root. Ordinary captures with already-certified
        // RN nodes do not enter this path.
        let certified = if let Some(view) = &self.procedure_view {
            if let Some(program) = &view.physical_program {
                view.plan.work.debit(
                    2,
                    ((inputs.len() + self.procedure_parameters.len()) * 24 + 64) as u64,
                )?;
                let complete = inputs
                    .iter()
                    .copied()
                    .chain(self.procedure_parameters.iter().map(|(v, _)| *v))
                    .collect::<Vec<_>>();
                view.plan.try_cell(
                    program,
                    &self.driven,
                    &complete,
                    inputs.len(),
                    view.node_count,
                    &view.ids,
                )?
            } else {
                None
            }
        } else {
            None
        };
        let mut solution = if let Some(values) = certified {
            Solution {
                voltages: values,
                certified_voltage_bounds: None,
                max_residual_v: 0.,
                max_residual_ratio: 0.,
                max_scaled_residual_ratio: None,
                max_voltage_correction_v: None,
                max_voltage_correction_ratio: None,
            }
        } else {
            self.solve_complete(inputs, initial_expanded.as_deref())?
        };
        if let Some(view) = &self.procedure_view {
            solution.voltages.truncate(view.node_count);
            if let Some(bounds) = solution.certified_voltage_bounds.as_mut() {
                bounds.truncate(view.node_count);
            }
        }
        Ok(solution)
    }
    fn solve_complete(
        &self,
        inputs: &[f64],
        initial_voltages: Option<&[f64]>,
    ) -> Result<Solution, Error> {
        let _timing = crate::diagnostics::span("circuit.solve");
        crate::diagnostics::counter("circuit_solve_calls", 1);

        let extended;
        let inputs = if !self.procedure_parameters.is_empty()
            && inputs.len() + self.procedure_parameters.len() == self.driven.len()
        {
            extended = inputs
                .iter()
                .copied()
                .chain(self.procedure_parameters.iter().map(|(v, _)| *v))
                .collect::<Vec<_>>();
            extended.as_slice()
        } else {
            inputs
        };
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
            certified_voltage_bounds: None,
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

    // Graph reserves all scans, output-node metadata and the returned vector.
    // This is the reduced nominal view of the very same installed physical
    // phase; it never removes a same-branch residual or relabels an input.
    pub(crate) fn forcing_legacy_voltage_view(
        &self,
        identity: usize,
        time: f64,
        values: &[f64],
        expected: &[usize],
    ) -> Result<Vec<f64>, Error> {
        let invalid = || {
            Error::new(
                "invalid_ir",
                "forcing reduced view does not match installed phase/source offsets",
            )
        };
        if !time.is_finite()
            || values.len()
                != self
                    .procedure_view
                    .as_ref()
                    .map_or(self.nodes.len(), |view| view.node_count)
            || values.iter().any(|v| !v.is_finite())
        {
            return Err(invalid());
        }
        for (i, &node) in expected.iter().enumerate() {
            if node == 0 || node >= values.len() || expected[..i].contains(&node) {
                return Err(invalid());
            }
        }
        match self.forcing_phase {
            None => {
                if !self.forcing_offsets.is_empty() || !self.forcing_bounds.is_empty() {
                    return Err(invalid());
                }
                return Ok(values.to_vec());
            }
            Some(phase) if phase == (identity, time) => (),
            _ => return Err(invalid()),
        }
        if self.forcing_offsets.len() != expected.len()
            || self.forcing_bounds.len() != expected.len()
        {
            return Err(invalid());
        }
        let mut reduced = values.to_vec();
        for (i, ((&node, &(cached, offset)), &(bound_node, bounds))) in expected
            .iter()
            .zip(&self.forcing_offsets)
            .zip(&self.forcing_bounds)
            .enumerate()
        {
            if cached != node
                || bound_node != node
                || !offset.is_finite()
                || !bounds[0].is_finite()
                || !bounds[1].is_finite()
                || bounds[0] > bounds[1]
                || self.forcing_offsets[..i]
                    .iter()
                    .any(|(prior, _)| *prior == node)
            {
                return Err(invalid());
            }
            reduced[node] -= offset;
            if !reduced[node].is_finite() {
                return Err(invalid());
            }
        }
        Ok(reduced)
    }

    pub(crate) fn install_forcing_phase(
        &mut self,
        identity: usize,
        time: f64,
        solution: &mut Solution,
        rows: Vec<ForcingRow>,
        operator_bounds: &[I],
        residual_certificate: bool,
    ) -> Result<(), Error> {
        let already_applied = match self.forcing_phase {
            Some(phase) if phase == (identity, time) => true,
            Some(_) => {
                return Err(Error::new(
                    "invalid_ir",
                    "forcing a different physical phase requires a fresh candidate circuit",
                ))
            }
            None => false,
        };
        if !already_applied {
            // The Graph prepaid this exact output storage before this call.
            // Reserve once so pushes cannot add uncharged growth copies.
            self.forcing_bounds = Vec::with_capacity(rows.len());
            self.forcing_offsets = Vec::with_capacity(rows.len());
        }
        let boxes = solution.certified_voltage_bounds.as_mut().ok_or_else(|| {
            Error::new("invalid_ir", "forcing requires original observation boxes")
        })?;
        for (node, positive, negative, rhs, value, bound, original, origin) in rows {
            let equation = self
                .equations
                .iter_mut()
                .find(|e| {
                    e.positive == positive
                        && e.negative == negative
                        && e.branch.instance == origin.instance
                })
                .ok_or_else(|| {
                    Error::new("invalid_ir", "forcing relation lost from reduced circuit")
                })?;
            // Every non-source residual remains in the same assembled branch.
            // Source-output independence was audited before reduction; no row
            // may use this output as an input or feed another consumer.
            if !equation.nonlinear.is_empty() {
                return Err(Error::new(
                    "invalid_ir",
                    "forcing residual must use the existing affine phase",
                ));
            }
            if !already_applied {
                equation.rhs_constant += rhs;
                solution.voltages[node] += value;
                equation.original_rhs.push(original.clone());
            }
            if already_applied && !residual_certificate {
                // Event closure can recertify the reduced row before projecting
                // the same immutable physical phase again. Restore that phase's
                // complete certified box, not the newly written residual box.
                boxes[node] = self
                    .forcing_bounds
                    .iter()
                    .find(|(n, _)| *n == node)
                    .map(|(_, b)| *b)
                    .ok_or_else(|| Error::new("invalid_ir", "missing forcing phase box"))?;
            } else {
                let combined = I {
                    lo: boxes[node][0],
                    hi: boxes[node][1],
                } + bound;
                boxes[node] = [
                    combined.lo.min(solution.voltages[node]),
                    combined.hi.max(solution.voltages[node]),
                ];
            }
            if already_applied {
                let slot = self
                    .forcing_bounds
                    .iter_mut()
                    .find(|(n, _)| *n == node)
                    .ok_or_else(|| Error::new("invalid_ir", "missing forcing phase box"))?;
                slot.1 = boxes[node];
            } else {
                self.forcing_bounds.push((node, boxes[node]));
                self.forcing_offsets.push((node, value));
            }
            // Repeated same-phase queries recheck the existing complete branch
            // point/box certificate, without accumulating the source a second time.
            let original = equation
                .original_rhs
                .iter()
                .cloned()
                .reduce(|left, right| Expression::Add {
                    left: Box::new(left),
                    right: Box::new(right),
                })
                .unwrap();
            let expanded;
            let points = if let Some(view) = &self.procedure_view {
                expanded = view.expand(&solution.voltages)?;
                expanded.as_slice()
            } else {
                solution.voltages.as_slice()
            };
            let point_rhs = expression::evaluate(&original, points)?.value;
            let lhs = solution.voltages[positive] - solution.voltages[negative];
            let limit = self.tolerances.absolute
                + self.tolerances.relative * lhs.abs().max(point_rhs.abs());
            let residual = (lhs - point_rhs).abs();
            if let Some(view) = &self.procedure_view {
                view.plan.work.debit(2, (boxes.len() * 16 + 64) as u64)?;
            }
            let public: Vec<_> = boxes.iter().map(|b| I { lo: b[0], hi: b[1] }).collect();
            let physical = match &self.procedure_view {
                Some(view) => view.expand_bounds(&public, points, operator_bounds)?,
                None => public,
            };
            let box_residual = (physical[positive] - physical[negative])
                - interval_expression(&original, &physical)?;
            if !residual.is_finite()
                || residual > limit
                || !box_residual.finite()
                || box_residual.lo < -limit
                || box_residual.hi > limit
            {
                return Err(Error::new(
                    "residual_failure",
                    "forcing original relation lacks point/box residual certificate",
                ));
            }
            equation.original_rhs = vec![original];
        }
        let expanded;
        let points = if let Some(view) = &self.procedure_view {
            expanded = view.expand(&solution.voltages)?;
            expanded.as_slice()
        } else {
            solution.voltages.as_slice()
        };
        let (residual, ratio) = self.check_affine_residuals(points)?;
        solution.max_residual_v = residual;
        solution.max_residual_ratio = ratio;
        self.forcing_phase = Some((identity, time));
        Ok(())
    }

    #[cfg(test)]
    pub(crate) fn forcing_frame_snapshot(&self) -> serde_json::Value {
        let equations: Vec<_> = self
            .equations
            .iter()
            .map(|e| {
                serde_json::json!({
            "branch":e.branch,"positive":e.positive,"negative":e.negative,
            "rhs_constant":e.rhs_constant,"rhs_terms":e.rhs_terms,"coefficients":e.coefficients,
            "nonlinear":e.nonlinear,"original_rhs":e.original_rhs,"origins":e.origins})
            })
            .collect();
        let dense: Vec<_> = self
            .dense_residuals
            .iter()
            .map(|d| d.as_ref().map(|d| (d.start, &d.coefficients)))
            .collect();
        serde_json::json!({"nodes":self.nodes,"forcing_phase":self.forcing_phase,"forcing_bounds":self.forcing_bounds,"forcing_offsets":self.forcing_offsets,"equations":equations,
            "driven":self.driven,"unknown":self.unknown,"unknown_columns":self.unknown_columns,
            "tolerances":self.tolerances,"driven_coefficients":self.driven_coefficients,"dense_residuals":dense,
            "affine_factor_identity":self.affine_factor.as_ref().map(|f|Arc::as_ptr(f) as usize),
            "affine_factor_initialized":self.affine_factor.as_ref().map(|f|f.get().is_some())})
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
#[path = "solver_private_phase_tests.rs"]
mod private_phase_tests;

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

#[cfg(test)]
mod forcing_offset_cache_tests {
    use super::*;
    use serde_json::json;
    #[test]
    fn forcing_offset_cache_preserves_residual_and_rejects_malformed_phase() {
        let p: Program = serde_json::from_value(json!({"schema_version":crate::ir::SCHEMA_VERSION,
            "nodes":["0","u","y"],"contributions":[{"positive":2,"negative":0,
            "branch":{"instance":"dut","local_positive":"p","local_negative":"r","kind":"voltage"},
            "origin":{"source":"offset-cache.va","line":1,"column":1,"instance":"dut"},
            "rhs":{"op":"affine","constant":0,"terms":[]}}]}))
        .unwrap();
        let mut c = Circuit::new(p, &["u".into()], Tolerances::default()).unwrap();
        let values = [0., 0., 0.75];
        assert_eq!(
            c.forcing_legacy_voltage_view(9, 0.75, &values, &[2])
                .unwrap(),
            values
        );
        c.forcing_phase = Some((9, 0.75));
        c.forcing_offsets = vec![(2, 0.25)];
        c.forcing_bounds = vec![(2, [0.75, 0.75])];
        let before = c.forcing_frame_snapshot();
        for _ in 0..2 {
            assert_eq!(
                c.forcing_legacy_voltage_view(9, 0.75, &values, &[2])
                    .unwrap(),
                [0., 0., 0.5]
            );
        }
        assert_eq!(before, c.forcing_frame_snapshot());
        let mut cases = vec![];
        let mut bad = c.clone();
        bad.forcing_offsets.clear();
        cases.push(bad);
        let mut bad = c.clone();
        bad.forcing_offsets[0].1 = f64::NAN;
        cases.push(bad);
        let mut bad = c.clone();
        bad.forcing_offsets[0].0 = 99;
        cases.push(bad);
        let mut bad = c.clone();
        bad.forcing_bounds[0].0 = 1;
        cases.push(bad);
        let mut bad = c.clone();
        bad.forcing_bounds[0].1 = [1., 0.];
        cases.push(bad);
        let mut bad = c.clone();
        bad.forcing_phase = None;
        cases.push(bad);
        let mut bad = c.clone();
        bad.forcing_phase = Some((8, 0.75));
        cases.push(bad);
        let mut bad = c.clone();
        bad.forcing_phase = Some((9, 0.5));
        cases.push(bad);
        for bad in cases {
            for _ in 0..2 {
                assert_eq!(
                    bad.forcing_legacy_voltage_view(9, 0.75, &values, &[2])
                        .unwrap_err()
                        .kind,
                    "invalid_ir"
                );
            }
        }
        for nodes in [vec![], vec![2, 2], vec![0], vec![99]] {
            assert_eq!(
                c.forcing_legacy_voltage_view(9, 0.75, &values, &nodes)
                    .unwrap_err()
                    .kind,
                "invalid_ir"
            );
        }
        assert_eq!(before, c.forcing_frame_snapshot());
    }
}

#[cfg(test)]
mod strict_budget_retry_tests {
    use super::*;
    use crate::{events::EventModel, transition_source_plan::Work};
    use serde_json::json;
    fn program() -> Program {
        let o = json!({"source":"strict-budget.va","line":1,"column":1,"instance":"dut"});
        serde_json::from_value(json!({"schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","u","y","z"],
            "contributions":[
                {"branch":{"instance":"dut","local_positive":"a","local_negative":"r","kind":"voltage"},"positive":2,"negative":0,
                    "rhs":{"op":"affine","constant":0.0,"terms":[{"node":1,"coefficient":3.0}]},"origin":o},
                {"branch":{"instance":"dut","local_positive":"b","local_negative":"r","kind":"voltage"},"positive":3,"negative":0,
                    "rhs":{"op":"affine","constant":2.0,"terms":[]},"origin":o}],
            "procedures":[{"procedure_id":0,"instance":"dut","body":[
                {"expanded_statement_ordinal":0,"action":{"kind":"contribution_capture","contribution":0}},
                {"expanded_statement_ordinal":1,"action":{"kind":"contribution_capture","contribution":1}}]}]})).unwrap()
    }
    fn circuit(w: &Work, domain: I) -> Circuit {
        let model = EventModel::new_with_procedure_work(
            program(),
            vec!["u".into()],
            Tolerances {
                absolute: 1e-10,
                relative: 0.,
            },
            w.clone(),
        )
        .unwrap();
        model.circuit_at(&[], &[], &[domain]).unwrap()
    }
    #[test]
    fn strict_retry_complete_original_box_contains_independent_physical_root() {
        let w = Work::default();
        let c = circuit(&w, I::point(0.2));
        let s = c.solve(&[0.2]).unwrap();
        let b = c.waveform_bounds(&s, &[I::point(0.2)]).unwrap();
        let q = num_rational::BigRational::from_float(0.2).unwrap();
        let root = q * num_rational::BigRational::from_integer(3.into());
        assert!(
            num_rational::BigRational::from_float(b[2].lo).unwrap() <= root
                && root <= num_rational::BigRational::from_float(b[2].hi).unwrap()
        );
        assert!(b[3].lo <= 2. && 2. <= b[3].hi);
        for node in [2, 3] {
            assert!((b[node] - I::point(s.voltages[node])).magnitude() <= 1e-10);
        }
    }
    #[test]
    fn strict_retry_preserves_complete_true_input_domain() {
        let w = Work::default();
        let domain = I { lo: 0.19, hi: 0.21 };
        let c = circuit(&w, domain);
        let s = c.solve(&[0.2]).unwrap();
        assert_eq!(
            c.waveform_bounds(&s, &[domain]).unwrap_err().kind,
            "waveform_accuracy"
        );
    }
    #[test]
    fn overdetermined_rows_remain_outside_retry_and_keep_natural_budget() {
        fn overdetermined(w: &Work) -> Circuit {
            let mut value = serde_json::to_value(program()).unwrap();
            let mut row = value["contributions"][0].clone();
            // A redundant triangle relation is legal; a second local branch
            // aliasing the same connected endpoint pair is intentionally not.
            row["branch"]["local_negative"] = json!("b");
            row["negative"] = json!(3);
            row["rhs"]["constant"] = json!(-2.0);
            value["contributions"].as_array_mut().unwrap().push(row);
            value["procedures"][0]["body"].as_array_mut().unwrap().push(json!({
                "expanded_statement_ordinal":2,"action":{"kind":"contribution_capture","contribution":2}}));
            let p: Program = serde_json::from_value(value).unwrap();
            let model = EventModel::new_with_procedure_work(
                p,
                vec!["u".into()],
                Tolerances {
                    absolute: 1e-10,
                    relative: 0.,
                },
                w.clone(),
            )
            .unwrap();
            model.circuit_at(&[], &[], &[I::point(0.2)]).unwrap()
        }
        let probe = Work::default();
        let c = overdetermined(&probe);
        let solution = c.solve(&[0.2]).unwrap();
        assert!(c.equations.len() > c.unknown.len());
        let prefix = probe.spent();
        let error = c.waveform_bounds(&solution, &[I::point(0.2)]).unwrap_err();
        assert_eq!(error.kind, "waveform_accuracy");
        assert!(error.message.contains("requires a square system"));
        let total = probe.spent();
        assert!(total > prefix);
        let w = Work::limited([128, 8192, total - 1]);
        let c = overdetermined(&w);
        let solution = c.solve(&[0.2]).unwrap();
        assert_eq!(w.spent(), prefix);
        assert_eq!(
            c.waveform_bounds(&solution, &[I::point(0.2)])
                .unwrap_err()
                .kind,
            "step_budget"
        );
        let failed = w.spent();
        for _ in 0..2 {
            assert_eq!(
                c.waveform_bounds(&solution, &[I::point(0.2)])
                    .unwrap_err()
                    .kind,
                "step_budget"
            );
            assert_eq!(w.spent(), failed);
        }
    }
    #[test]
    fn strict_retry_original_owner_natural_exhaustion_and_sticky_queries() {
        let probe = Work::default();
        let c = circuit(&probe, I::point(0.2));
        let s = c.solve(&[0.2]).unwrap();
        let prefix = probe.spent();
        c.waveform_bounds(&s, &[I::point(0.2)]).unwrap();
        let total = probe.spent();
        assert!(total > prefix);
        let w = Work::limited([128, 8192, total - 1]);
        let c = circuit(&w, I::point(0.2));
        let s = c.solve(&[0.2]).unwrap();
        assert_eq!(w.spent(), prefix);
        assert_eq!(
            c.waveform_bounds(&s, &[I::point(0.2)]).unwrap_err().kind,
            "step_budget"
        );
        let failed = w.spent();
        for _ in 0..2 {
            assert_eq!(
                c.waveform_bounds(&s, &[I::point(0.2)]).unwrap_err().kind,
                "step_budget"
            );
            assert_eq!(w.spent(), failed);
        }
    }
}
