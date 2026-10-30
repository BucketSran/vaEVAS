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
    // The structure of same-time feedback through program reals, read once
    // from the assembled relations of this procedure circuit.
    same_time: Arc<OnceLock<Arc<SameTimeStructure>>>,
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
        self.same_time = Arc::new(OnceLock::new());
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

// Unknown columns read by a bound waveform expression, and whether it has a
// rounding step. False for a leaf the interval evaluator does not certify;
// such a system keeps its refusal.
fn read_columns(
    expr: &Expression,
    columns: &[Option<usize>],
    out: &mut Vec<usize>,
    rounded: &mut bool,
    work: &crate::transition_source_plan::Work,
) -> Result<bool, Error> {
    work.step()?;
    match expr {
        Expression::Affine { terms, .. } => {
            work.debit(2, (terms.len() * 16) as u64)?;
            out.extend(terms.iter().filter_map(|t| columns[t.node]));
            Ok(true)
        }
        Expression::RealBinary { left, right, .. } => {
            *rounded = true;
            Ok(read_columns(left, columns, out, rounded, work)?
                && read_columns(right, columns, out, rounded, work)?)
        }
        Expression::Add { left, right }
        | Expression::Multiply { left, right }
        | Expression::Divide { left, right } => {
            Ok(read_columns(left, columns, out, rounded, work)?
                && read_columns(right, columns, out, rounded, work)?)
        }
        Expression::RealBoundary { value, .. } => {
            *rounded = true;
            read_columns(value, columns, out, rounded, work)
        }
        Expression::Power { base, .. } => read_columns(base, columns, out, rounded, work),
        Expression::EventMath { args, .. } => {
            for arg in args {
                if !read_columns(arg, columns, out, rounded, work)? {
                    return Ok(false);
                }
            }
            Ok(true)
        }
        _ => Ok(false),
    }
}

/// What the same-time structure reads from one bound waveform expression,
/// without values: every node it reads, whether it has a rounding step,
/// whether `read_columns` can read it, and whether every operation has an
/// exact real-arithmetic form (`same_time_root` evaluates it).
struct StructureRead {
    nodes: Vec<usize>,
    rounded: bool,
    walkable: bool,
    exact: bool,
}

impl StructureRead {
    fn new() -> Self {
        Self {
            nodes: Vec::new(),
            rounded: false,
            walkable: true,
            exact: true,
        }
    }
    fn read(&mut self, e: &Expression) {
        match e {
            Expression::Affine { terms, .. } => self.nodes.extend(terms.iter().map(|t| t.node)),
            Expression::RealBinary { left, right, .. } => {
                self.rounded = true;
                self.read(left);
                self.read(right);
            }
            Expression::RealBoundary { value, .. } => {
                self.rounded = true;
                self.read(value);
            }
            Expression::Add { left, right }
            | Expression::Multiply { left, right }
            | Expression::Divide { left, right } => {
                self.read(left);
                self.read(right);
            }
            Expression::Power { base, .. } => self.read(base),
            Expression::EventMath { function, args, .. } => {
                self.exact &= args.len() == 1
                    && crate::operators::Function::from_internal(*function).is_some();
                for arg in args {
                    self.read(arg);
                }
            }
            other => {
                self.walkable = false;
                self.exact = false;
                match other {
                    Expression::IntegerRound { value, .. }
                    | Expression::CheckedInteger { value, .. }
                    | Expression::Forcing { value, .. } => self.read(value),
                    Expression::CheckedIndex { index, .. }
                    | Expression::ArrayRead { index, .. } => self.read(index),
                    Expression::Select {
                        left,
                        right,
                        then_value,
                        else_value,
                        ..
                    } => {
                        for e in [left, right, then_value, else_value] {
                            self.read(e);
                        }
                    }
                    Expression::UnsupportedSystemCall { args, .. } => {
                        for arg in args {
                            self.read(arg);
                        }
                    }
                    Expression::RealCall { result, .. } => self.read(result),
                    _ => {}
                }
            }
        }
    }
}

/// A maximum matching of relations to the unknown columns each involves
/// (Kuhn's augmenting paths after a greedy start in candidate order, which
/// lists a relation's terminals first): the matched column of each relation.
fn relation_matching(candidates: &[Vec<usize>], n: usize) -> Vec<Option<usize>> {
    let mut owner: Vec<Option<usize>> = vec![None; n];
    let mut matched: Vec<Option<usize>> = vec![None; candidates.len()];
    for (row, columns) in candidates.iter().enumerate() {
        if let Some(&column) = columns.iter().find(|&&c| owner[c].is_none()) {
            owner[column] = Some(row);
            matched[row] = Some(column);
        }
    }
    let mut seen = vec![usize::MAX; n];
    for start in 0..candidates.len() {
        if matched[start].is_some() {
            continue;
        }
        // Rows on the search path with their next candidate, and the column
        // by which each row after the first was reached.
        let mut path = vec![(start, 0_usize)];
        let mut via = Vec::new();
        let mut free = None;
        while let Some(&(row, position)) = path.last() {
            let Some(&column) = candidates[row].get(position) else {
                path.pop();
                via.pop();
                continue;
            };
            if let Some(top) = path.last_mut() {
                top.1 += 1;
            }
            if seen[column] == start {
                continue;
            }
            seen[column] = start;
            match owner[column] {
                None => {
                    free = Some(column);
                    break;
                }
                Some(next) => {
                    via.push(column);
                    path.push((next, 0));
                }
            }
        }
        if let Some(mut column) = free {
            for k in (0..path.len()).rev() {
                let row = path[k].0;
                owner[column] = Some(row);
                matched[row] = Some(column);
                if k > 0 {
                    column = via[k - 1];
                }
            }
        }
    }
    matched
}

/// Why a same-time cycle through a program real lies outside the class
/// decision 22 implements: every unknown of the activation defined by
/// exactly one grounded relation, every operation of the cycle with an exact
/// real-arithmetic form.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
enum OutsideClass {
    /// A relation of the cycle between two unknown nodes.
    TwoUnknownNodes,
    /// A relation of the cycle to a driven node instead of ground.
    DrivenTerminal,
    /// An operation of the cycle without an exact real-arithmetic form.
    InexactOperation,
    /// Another unknown of the activation is not defined by one grounded relation.
    Layout,
}

/// Same-time feedback through program reals in one procedure circuit, read
/// once from its assembled relations without values (decision 22). Cycles
/// are those of "unknown reads unknown" under a maximum matching of the
/// relations to the unknowns they involve, whatever their terminals; a cycle
/// is through a program real when one of its relations has a rounding step.
#[derive(Default)]
pub(crate) struct SameTimeStructure {
    /// The first cycle through a program real outside the implemented class:
    /// why, and the origins of its relations.
    outside: Option<(OutsideClass, String)>,
    /// The activation is in the implemented class and has a same-time cycle
    /// (`Order::Cyclic` with a cycle).
    cyclic: bool,
    /// Procedure value nodes whose stored values are decision 22 roundings.
    pub(crate) values: Vec<usize>,
    /// Physical nodes, ground excluded, whose values those roundings read:
    /// the cycles' own physical members, and every physical node a cycle
    /// reads directly or through procedure values outside the cycles.
    pub(crate) reads: Vec<usize>,
}

/// Dependency structure of a system with a rounding step in which every
/// unknown is defined by exactly one grounded relation.
enum Order {
    /// No rounding step, or an unknown without exactly one such definition.
    Unsupported,
    /// (column, equation, sign) per unknown, each after every column it reads.
    Acyclic(Vec<(usize, usize, f64)>),
    /// Some values read their own result at the same time. `components` are
    /// the strongly connected components of "column reads column", each
    /// after every component it reads, with whether it is a cycle (several
    /// columns, or one column reading itself); `definition` is (equation,
    /// sign) and `reads` the columns its relation reads, per column.
    Cyclic {
        components: Vec<(Vec<usize>, bool)>,
        definition: Vec<(usize, f64)>,
        reads: Vec<Vec<usize>>,
    },
}

/// Whether a bound waveform expression has a rounding step (a program real).
fn rounding_step(e: &Expression) -> bool {
    match e {
        Expression::RealBoundary { .. } | Expression::RealBinary { .. } => true,
        Expression::Add { left, right }
        | Expression::Multiply { left, right }
        | Expression::Divide { left, right } => rounding_step(left) || rounding_step(right),
        Expression::Power { base, .. } => rounding_step(base),
        Expression::EventMath { args, .. } => args.iter().any(rounding_step),
        _ => false,
    }
}

/// The same relation in real arithmetic: every rounding step is dropped.
fn unrounded(expr: &Expression) -> Expression {
    let boxed = |e: &Expression| Box::new(unrounded(e));
    match expr {
        Expression::RealBoundary { value, .. } => unrounded(value),
        Expression::RealBinary {
            operation,
            left,
            right,
            ..
        } => {
            let (left, right) = (boxed(left), boxed(right));
            match operation {
                crate::ir::RealOperation::Add => Expression::Add { left, right },
                crate::ir::RealOperation::Subtract => Expression::Add {
                    left,
                    right: Box::new(Expression::Multiply {
                        left: Box::new(Expression::Affine {
                            constant: -1.,
                            terms: Vec::new(),
                        }),
                        right,
                    }),
                },
                crate::ir::RealOperation::Multiply => Expression::Multiply { left, right },
                crate::ir::RealOperation::Divide => Expression::Divide { left, right },
            }
        }
        Expression::Add { left, right } => Expression::Add {
            left: boxed(left),
            right: boxed(right),
        },
        Expression::Multiply { left, right } => Expression::Multiply {
            left: boxed(left),
            right: boxed(right),
        },
        Expression::Divide { left, right } => Expression::Divide {
            left: boxed(left),
            right: boxed(right),
        },
        Expression::Power { base, exponent } => Expression::Power {
            base: boxed(base),
            exponent: *exponent,
        },
        Expression::EventMath {
            function,
            args,
            origin,
        } => Expression::EventMath {
            function: *function,
            args: args.iter().map(unrounded).collect(),
            origin: origin.clone(),
        },
        other => other.clone(),
    }
}

/// (reads a marked unknown column, affine in the marked columns) for the
/// real-arithmetic reading of a bound waveform expression.
fn marked_affine(
    expr: &Expression,
    columns: &[Option<usize>],
    marked: &[bool],
    work: &crate::transition_source_plan::Work,
) -> Result<(bool, bool), Error> {
    work.step()?;
    let pair = |l: &Expression, r: &Expression| -> Result<_, Error> {
        Ok((
            marked_affine(l, columns, marked, work)?,
            marked_affine(r, columns, marked, work)?,
        ))
    };
    use crate::ir::RealOperation as Op;
    Ok(match expr {
        Expression::Affine { terms, .. } => (
            terms
                .iter()
                .any(|t| columns[t.node].is_some_and(|c| marked[c])),
            true,
        ),
        Expression::RealBoundary { value, .. } => marked_affine(value, columns, marked, work)?,
        Expression::Add { left, right }
        | Expression::RealBinary {
            operation: Op::Add | Op::Subtract,
            left,
            right,
            ..
        } => {
            let ((a, x), (b, y)) = pair(left, right)?;
            (a || b, x && y)
        }
        Expression::Multiply { left, right }
        | Expression::RealBinary {
            operation: Op::Multiply,
            left,
            right,
            ..
        } => {
            let ((a, x), (b, y)) = pair(left, right)?;
            (a || b, x && y && !(a && b))
        }
        Expression::Divide { left, right }
        | Expression::RealBinary {
            operation: Op::Divide,
            left,
            right,
            ..
        } => {
            let ((a, x), (b, y)) = pair(left, right)?;
            (a || b, x && y && !b)
        }
        Expression::Power { base, .. } => {
            let (a, x) = marked_affine(base, columns, marked, work)?;
            (a, x && !a)
        }
        Expression::EventMath { args, .. } => {
            let mut reads = false;
            for arg in args {
                reads |= marked_affine(arg, columns, marked, work)?.0;
            }
            (reads, !reads)
        }
        _ => (false, true),
    })
}

/// Strongly connected components of "column reads column" (Tarjan, without
/// recursion), each emitted after every component it reads, with whether it
/// is a cycle: several columns, or one column that reads itself.
fn strong_components(
    reads: &[Vec<usize>],
    work: &crate::transition_source_plan::Work,
) -> Result<Vec<(Vec<usize>, bool)>, Error> {
    // Index, low link, stack flag, the stack, the frame stack and the result.
    work.debit(2, ((6 * reads.len() + 1) * 64) as u64)?;
    strong_components_with(reads, &mut || work.step())
}

/// `strong_components` with each visit reported to `step` (the charged order
/// pays one step per visit; the structural identification pays nothing).
fn strong_components_with(
    reads: &[Vec<usize>],
    step: &mut dyn FnMut() -> Result<(), Error>,
) -> Result<Vec<(Vec<usize>, bool)>, Error> {
    let n = reads.len();
    let mut index = vec![usize::MAX; n];
    let mut low = vec![0_usize; n];
    let mut on_stack = vec![false; n];
    let mut stack = Vec::with_capacity(n);
    let mut components = Vec::new();
    let mut next = 0;
    for start in 0..n {
        if index[start] != usize::MAX {
            continue;
        }
        let mut frames = vec![(start, 0_usize)];
        index[start] = next;
        low[start] = next;
        next += 1;
        stack.push(start);
        on_stack[start] = true;
        while let Some(&(column, position)) = frames.last() {
            step()?;
            if let Some(&read) = reads[column].get(position) {
                if let Some(top) = frames.last_mut() {
                    top.1 += 1;
                }
                if index[read] == usize::MAX {
                    index[read] = next;
                    low[read] = next;
                    next += 1;
                    stack.push(read);
                    on_stack[read] = true;
                    frames.push((read, 0));
                } else if on_stack[read] {
                    low[column] = low[column].min(index[read]);
                }
                continue;
            }
            frames.pop();
            if let Some(&(parent, _)) = frames.last() {
                low[parent] = low[parent].min(low[column]);
            }
            if low[column] == index[column] {
                let mut members = Vec::new();
                loop {
                    step()?;
                    let Some(member) = stack.pop() else {
                        return Err(Error::new(
                            "invalid_ir",
                            "strongly connected component stack underflow",
                        ));
                    };
                    on_stack[member] = false;
                    members.push(member);
                    if member == column {
                        break;
                    }
                }
                let cyclic = members.len() > 1 || reads[column].contains(&column);
                members.reverse();
                components.push((members, cyclic));
            }
        }
    }
    Ok(components)
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
            same_time: Arc::new(OnceLock::new()),
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

    /// How a system with a rounding step in which every unknown is defined by
    /// exactly one grounded relation can be certified without differentiating
    /// a rounding step.
    fn substitution_order(
        &self,
        work: &crate::transition_source_plan::Work,
    ) -> Result<Order, Error> {
        let n = self.unknown.len();
        if self.equations.len() != n {
            return Ok(Order::Unsupported);
        }
        // Definitions, pending counts, reader lists, order and the copied
        // value vector; read entries are paid where they are collected.
        work.debit(2, ((self.nodes.len() + 8 * n + 1) * 64) as u64)?;
        let mut definition = vec![None; n];
        for (index, eq) in self.equations.iter().enumerate() {
            work.step()?;
            let (node, sign) = if eq.negative == 0 {
                (eq.positive, 1.)
            } else if eq.positive == 0 {
                (eq.negative, -1.)
            } else {
                return Ok(Order::Unsupported);
            };
            let Some(column) = self.unknown_columns[node] else {
                return Ok(Order::Unsupported);
            };
            if definition[column].replace((index, sign)).is_some() {
                return Ok(Order::Unsupported);
            }
        }
        let Some(definition) = definition.into_iter().collect::<Option<Vec<_>>>() else {
            return Ok(Order::Unsupported);
        };
        let mut pending = vec![0_usize; n];
        let mut readers = vec![Vec::new(); n];
        let mut reads = vec![Vec::new(); n];
        let mut rounded = false;
        for (column, &(index, _)) in definition.iter().enumerate() {
            for rhs in &self.equations[index].original_rhs {
                if !read_columns(
                    rhs,
                    &self.unknown_columns,
                    &mut reads[column],
                    &mut rounded,
                    work,
                )? {
                    return Ok(Order::Unsupported);
                }
            }
            work.debit(2, (reads[column].len() * 32) as u64)?;
            for &read in &reads[column] {
                pending[column] += 1;
                readers[read].push(column);
            }
        }
        if !rounded {
            return Ok(Order::Unsupported);
        }
        // Kahn order: a column is evaluated after every column it reads. A
        // column left over lies on a cycle or after one.
        let mut ready = (0..n).filter(|&c| pending[c] == 0).collect::<Vec<_>>();
        let mut order = Vec::with_capacity(n);
        while let Some(column) = ready.pop() {
            work.step()?;
            let (index, sign) = definition[column];
            order.push((column, index, sign));
            for &reader in &readers[column] {
                work.step()?;
                pending[reader] -= 1;
                if pending[reader] == 0 {
                    ready.push(reader);
                }
            }
        }
        if order.len() == n {
            return Ok(Order::Acyclic(order));
        }
        let components = strong_components(&reads, work)?;
        Ok(Order::Cyclic {
            components,
            definition,
            reads,
        })
    }

    /// A same-time cycle through a program real in an event activation
    /// (D-R2-1 option A, decision 22): EVAS certifies only a cycle whose
    /// relations are jointly affine in its own unknowns; any other is refused
    /// as a capability limit before a local proof could select one of its
    /// roots, also where its exact equation has exactly one solution (q =
    /// 1 - 0.25*V(y)^3 with V(y) <+ q). A cycle without a rounding step is a
    /// continuous relation and keeps the original contract.
    fn nonlinear_same_time_feedback(&self) -> Result<Option<Error>, Error> {
        let Some(view) = self
            .procedure_view
            .as_ref()
            .filter(|v| !v.plan.actions.is_empty())
        else {
            return Ok(None);
        };
        if !self.same_time_cycle_shape() {
            return Ok(None);
        }
        let work = &view.plan.work;
        let Order::Cyclic {
            components,
            definition,
            ..
        } = self.substitution_order(work)?
        else {
            return Ok(None);
        };
        let mut member = vec![false; definition.len()];
        for (columns, cyclic) in &components {
            if !cyclic || !self.through_program_real(columns, &definition) {
                continue;
            }
            for &column in columns {
                member[column] = true;
            }
            for &column in columns {
                for rhs in &self.equations[definition[column].0].original_rhs {
                    if !marked_affine(rhs, &self.unknown_columns, &member, work)?.1 {
                        let origins = self.cycle_origins(columns, &definition, work)?;
                        work.debit(2, (origins.len() + 256) as u64)?;
                        return Ok(Some(Error::new(
                            "unsupported_transient",
                            format!(
                                "certification of same-time feedback through a program real at \
                                 {origins} that is not jointly affine is not implemented in an \
                                 event activation (capability limit)"
                            ),
                        )));
                    }
                }
            }
            for &column in columns {
                member[column] = false;
            }
        }
        Ok(None)
    }

    /// Whether some relation of a cycle has a rounding step: the cycle runs
    /// through a program real (decision 22).
    fn through_program_real(&self, columns: &[usize], definition: &[(usize, f64)]) -> bool {
        columns.iter().any(|&column| {
            self.equations[definition[column].0]
                .original_rhs
                .iter()
                .any(rounding_step)
        })
    }

    /// The origins of a cycle's relations, each once, in member order.
    fn cycle_origins(
        &self,
        columns: &[usize],
        definition: &[(usize, f64)],
        work: &crate::transition_source_plan::Work,
    ) -> Result<String, Error> {
        let mut origins: Vec<&String> = Vec::new();
        for &column in columns {
            for origin in &self.equations[definition[column].0].origins {
                work.step()?;
                if !origins.contains(&origin) {
                    work.debit(2, (origin.len() + 2) as u64)?;
                    origins.push(origin);
                }
            }
        }
        Ok(origins
            .iter()
            .map(|o| o.as_str())
            .collect::<Vec<_>>()
            .join(", "))
    }

    /// D-R2-1 option A (decision 22, an ADR-006 clarification): a cycle of
    /// same-time relations through rounded program values is the
    /// real-arithmetic equation of that cycle. Components are taken in
    /// dependency order: a value outside every cycle keeps its rounding and is
    /// bounded by substitution (its complete rounded image), and each cycle is
    /// certified by the unchanged Krawczyk test on its own relations without
    /// their rounding steps, with every value it reads fixed to its enclosure.
    /// A refusal of that test is the refusal of the cycle's equation.
    fn component_waveform_bounds(
        &self,
        solution: &Solution,
        base: &[I],
        components: &[(Vec<usize>, bool)],
        definition: &[(usize, f64)],
    ) -> Result<Vec<I>, Error> {
        let Some(view) = &self.procedure_view else {
            return Err(Error::new(
                "invalid_ir",
                "same-time cycle certificate requires its procedure view",
            ));
        };
        let work = &view.plan.work;
        let mut values = base.to_vec();
        for (columns, cyclic) in components {
            if !cyclic {
                for &column in columns {
                    let (index, sign) = definition[column];
                    values[self.unknown[column]] =
                        self.substituted_value(index, sign, &values, work)?;
                }
                continue;
            }
            let bounds = self.cycle_bounds(solution, &values, columns, definition, work)?;
            for &column in columns {
                values[self.unknown[column]] = bounds[self.unknown[column]];
            }
        }
        self.check_substituted_budget(solution, &values, work)?;
        Ok(values)
    }

    /// The unchanged Krawczyk test of one cycle on its own relations without
    /// their rounding steps, every value it reads fixed to `values`: node
    /// bounds whose members enclose the cycle's one root for every value in
    /// those enclosures.
    fn cycle_bounds(
        &self,
        solution: &Solution,
        values: &[I],
        columns: &[usize],
        definition: &[(usize, f64)],
        work: &crate::transition_source_plan::Work,
    ) -> Result<Vec<I>, Error> {
        let cycle = self.cycle_circuit(columns, definition, work)?;
        let inputs = cycle
            .driven
            .iter()
            .map(|&node| values[node])
            .collect::<Vec<_>>();
        cycle.waveform_bounds_attempt(solution, &inputs, false)
    }

    /// One cycle's relations without their rounding steps as a circuit of its
    /// own: its members are the unknowns and every other node is driven.
    fn cycle_circuit(
        &self,
        columns: &[usize],
        definition: &[(usize, f64)],
        work: &crate::transition_source_plan::Work,
    ) -> Result<Self, Error> {
        let mut member = vec![false; self.nodes.len()];
        for &column in columns {
            member[self.unknown[column]] = true;
        }
        // The cycle's own circuit has no procedure view, so its attempt
        // pays nothing per operation: prepay a complete retry of it, and
        // the copied circuit, on the original owner.
        self.reserve_waveform_retry(self.nodes.len(), columns.len(), work)?;
        self.charge_history_copy(work)?;
        let mut cycle = self.clone();
        cycle.procedure_view = None;
        cycle.procedure_occurrence = None;
        cycle.procedure_parameters = Vec::new();
        cycle.affine_factor = None;
        cycle.driven_coefficients = Vec::new();
        cycle.dense_residuals = Vec::new();
        cycle.same_time = Arc::new(OnceLock::new());
        cycle.equations = Vec::with_capacity(columns.len());
        for &column in columns {
            work.step()?;
            let mut eq = self.equations[definition[column].0].clone();
            eq.original_rhs = eq.original_rhs.iter().map(unrounded).collect();
            eq.nonlinear = eq.nonlinear.iter().map(unrounded).collect();
            cycle.equations.push(eq);
        }
        cycle.unknown = columns.iter().map(|&column| self.unknown[column]).collect();
        cycle.driven = (1..self.nodes.len())
            .filter(|&node| !member[node])
            .collect();
        cycle.unknown_columns = vec![None; self.nodes.len()];
        for (j, &node) in cycle.unknown.iter().enumerate() {
            cycle.unknown_columns[node] = Some(j);
        }
        Ok(cycle)
    }

    /// Whether the system has a same-time cycle through a rounded program
    /// value (decision 22).
    pub(crate) fn has_same_time_cycle(&self) -> Result<bool, Error> {
        let Some(view) = &self.procedure_view else {
            return Ok(false);
        };
        if !self.same_time_cycle_shape() {
            return Ok(false);
        }
        Ok(match self.substitution_order(&view.plan.work)? {
            Order::Cyclic { components, .. } => components.iter().any(|(_, cyclic)| *cyclic),
            _ => false,
        })
    }

    /// Whether the activation is in the implemented class of decision 22 and
    /// has a same-time cycle: every unknown defined by one grounded relation,
    /// a rounding step, and a column that reads itself through the others
    /// (the structure of `Order::Cyclic` with a cycle). The charged
    /// substitution order then decides; most systems with program reals have
    /// no such cycle and never pay for that order.
    fn same_time_cycle_shape(&self) -> bool {
        self.same_time_structure().cyclic
    }

    /// The same-time structure of this circuit (`SameTimeStructure`). Only the
    /// assembled relations are read, without values, so the read is not
    /// charged; it is kept with the circuit.
    pub(crate) fn same_time_structure(&self) -> Arc<SameTimeStructure> {
        self.same_time
            .get_or_init(|| Arc::new(self.read_same_time_structure()))
            .clone()
    }

    fn read_same_time_structure(&self) -> SameTimeStructure {
        let Some(view) = &self.procedure_view else {
            return SameTimeStructure::default();
        };
        if !self.has_rounding() {
            return SameTimeStructure::default();
        }
        let n = self.unknown.len();
        // Per relation: the unknown columns at its terminals and those it
        // reads, and what it reads without values.
        let mut terminals = Vec::with_capacity(self.equations.len());
        let mut read_columns = Vec::with_capacity(self.equations.len());
        let mut reads = Vec::with_capacity(self.equations.len());
        let mut grounded = true;
        let mut defined = vec![false; n];
        for eq in &self.equations {
            let mut ends = Vec::new();
            for node in [eq.positive, eq.negative] {
                if let Some(column) = self.unknown_columns[node] {
                    if !ends.contains(&column) {
                        ends.push(column);
                    }
                }
            }
            let mut read = StructureRead::new();
            for rhs in &eq.original_rhs {
                read.read(rhs);
            }
            let mut columns = Vec::new();
            for &node in &read.nodes {
                if let Some(column) = self.unknown_columns[node] {
                    if !columns.contains(&column) {
                        columns.push(column);
                    }
                }
            }
            let node = if eq.negative == 0 {
                eq.positive
            } else if eq.positive == 0 {
                eq.negative
            } else {
                0
            };
            match self.unknown_columns[node] {
                Some(column) if !defined[column] && read.walkable => defined[column] = true,
                _ => grounded = false,
            }
            terminals.push(ends);
            read_columns.push(columns);
            reads.push(read);
        }
        grounded &= self.equations.len() == n;
        let candidates = terminals
            .iter()
            .zip(&read_columns)
            .map(|(ends, columns)| {
                let mut all = ends.clone();
                all.extend(columns.iter().filter(|c| !ends.contains(c)));
                all
            })
            .collect::<Vec<_>>();
        let matched = relation_matching(&candidates, n);
        let mut owner = vec![None; n];
        for (row, column) in matched.iter().enumerate() {
            if let Some(column) = *column {
                owner[column] = Some(row);
            }
        }
        // Column c reads every other unknown its relation involves, and
        // itself only where its right-hand side reads it.
        let depends = (0..n)
            .map(|column| match owner[column] {
                Some(row) => candidates[row]
                    .iter()
                    .copied()
                    .filter(|&c| c != column || read_columns[row].contains(&c))
                    .collect(),
                None => Vec::new(),
            })
            .collect::<Vec<Vec<usize>>>();
        let Ok(components) = strong_components_with(&depends, &mut || Ok(())) else {
            return SameTimeStructure {
                outside: Some((OutsideClass::Layout, String::new())),
                ..SameTimeStructure::default()
            };
        };
        let origins = |columns: &[usize]| {
            let mut all: Vec<&str> = Vec::new();
            for &column in columns {
                for origin in owner[column]
                    .map(|row| self.equations[row].origins.as_slice())
                    .unwrap_or_default()
                {
                    if !all.contains(&origin.as_str()) {
                        all.push(origin.as_str());
                    }
                }
            }
            all.join(", ")
        };
        let mut outside: Option<(OutsideClass, String)> = None;
        let mut cyclic = false;
        for (columns, is_cycle) in &components {
            if !is_cycle {
                continue;
            }
            cyclic = true;
            let rows = columns
                .iter()
                .filter_map(|&column| owner[column])
                .collect::<Vec<_>>();
            if !rows.iter().any(|&row| reads[row].rounded) {
                continue;
            }
            let mut why = OutsideClass::Layout;
            let mut found = !grounded;
            for &row in &rows {
                let eq = &self.equations[row];
                let reason = if terminals[row].len() == 2 {
                    Some(OutsideClass::TwoUnknownNodes)
                } else if eq.positive != 0 && eq.negative != 0 {
                    Some(OutsideClass::DrivenTerminal)
                } else if !reads[row].exact {
                    Some(OutsideClass::InexactOperation)
                } else {
                    None
                };
                if let Some(reason) = reason {
                    why = why.min(reason);
                    found = true;
                }
            }
            if found && outside.as_ref().is_none_or(|(old, _)| why < *old) {
                outside = Some((why, origins(columns)));
            }
        }
        if outside.is_some() || !grounded || !cyclic {
            return SameTimeStructure {
                outside,
                ..SameTimeStructure::default()
            };
        }
        // Decision 22 stores the roundings of every cycle's members; they
        // read the physical nodes of the cycle and every physical node its
        // relations read, through procedure values outside the cycles.
        let mut member = vec![false; n];
        for (columns, is_cycle) in &components {
            if *is_cycle {
                for &column in columns {
                    member[column] = true;
                }
            }
        }
        let mut values = Vec::new();
        let mut key = vec![false; view.node_count];
        let mut visited = vec![false; n];
        let mut stack = Vec::new();
        for column in 0..n {
            if !member[column] {
                continue;
            }
            let node = self.unknown[column];
            if node >= view.node_count {
                values.push(node);
            } else if node != 0 {
                key[node] = true;
            }
            visited[column] = true;
            stack.push(column);
        }
        while let Some(column) = stack.pop() {
            let Some(row) = owner[column] else {
                continue;
            };
            for &node in &reads[row].nodes {
                if node == 0 {
                    continue;
                }
                if node < view.node_count {
                    key[node] = true;
                } else if let Some(read) = self.unknown_columns[node] {
                    if !visited[read] {
                        visited[read] = true;
                        stack.push(read);
                    }
                }
            }
        }
        values.sort_unstable();
        SameTimeStructure {
            outside: None,
            cyclic: true,
            values,
            reads: (0..view.node_count).filter(|&node| key[node]).collect(),
        }
    }

    /// Decision 22 scope (D_R2_1): a same-time cycle through a program real
    /// outside the implemented class is refused as a capability limit before
    /// any RN cell, numeric solve or derivative certificate, even where its
    /// exact equation has exactly one solution. The refusal states no fact
    /// about the solutions of that equation.
    fn same_time_capability_refusal(&self) -> Result<Option<Error>, Error> {
        let structure = self.same_time_structure();
        let Some((outside, origins)) = &structure.outside else {
            return Ok(None);
        };
        if let Some(view) = &self.procedure_view {
            view.plan.work.debit(2, (origins.len() + 256) as u64)?;
        }
        Ok(Some(match outside {
            OutsideClass::TwoUnknownNodes => Error::new(
                "unsupported_transient",
                format!(
                    "same-time feedback through a program real at {origins} through a relation \
                     between two unknown nodes is not implemented (capability limit)"
                ),
            ),
            OutsideClass::DrivenTerminal => Error::new(
                "unsupported_transient",
                format!(
                    "same-time feedback through a program real at {origins} through a relation \
                     to a driven node instead of ground is not implemented (capability limit)"
                ),
            ),
            OutsideClass::InexactOperation => Error::new(
                "unsupported_transient",
                format!(
                    "same-time feedback through a program real at {origins} through an operation \
                     without an exact real-arithmetic form is not implemented (capability limit)"
                ),
            ),
            OutsideClass::Layout => Error::new(
                "unsupported_transient",
                format!(
                    "same-time feedback through a program real at {origins} in an activation whose \
                     unknowns are not each defined by one grounded relation is not implemented \
                     (capability limit)"
                ),
            ),
        }))
    }

    /// Decision 22 (D-R2-1 option A, an ADR-006 clarification): (node, value)
    /// for every member of a same-time cycle through program reals, the value
    /// being the binary64 rounding of the exact root of the cycle's equation;
    /// None without such a cycle. `solution` is expanded.
    ///
    /// The exact equation reads each driven value as this activation's own
    /// input (its exact source value where the activation has one), a value
    /// outside every cycle with its rounding steps, and a program value of an
    /// earlier cycle as its stored rounding. `input_bounds`, the certificate's
    /// driven enclosures, only certify the root: each cycle is then certified
    /// on them and its exact root must lie in that certificate. Without them
    /// (the solve) an affine cycle needs no enclosure; any other is certified
    /// on the activation's own inputs before it is refined.
    fn same_time_roundings(
        &self,
        solution: &Solution,
        input_bounds: Option<&[I]>,
    ) -> Result<Option<Vec<(usize, f64)>>, Error> {
        use crate::same_time_root::{self as root, Cycle, Relation, Q};
        let Some(view) = &self.procedure_view else {
            return Ok(None);
        };
        if !self.same_time_cycle_shape() {
            return Ok(None);
        }
        let work = &view.plan.work;
        let Order::Cyclic {
            components,
            definition,
            reads,
        } = self.substitution_order(work)?
        else {
            return Ok(None);
        };
        if !components.iter().any(|(_, cyclic)| *cyclic) {
            return Ok(None);
        }
        if solution.voltages.len() != self.nodes.len() {
            return Err(Error::new(
                "invalid_ir",
                "same-time roundings require the expanded activation solution",
            ));
        }
        let n = self.unknown.len();
        work.debit(
            2,
            ((self.nodes.len() + n) as u64)
                .saturating_mul(96)
                .saturating_add(64),
        )?;
        // Only cycles and the values they read need an exact value.
        let mut needed = vec![false; n];
        for (columns, cyclic) in components.iter().rev() {
            for &column in columns {
                work.step()?;
                if *cyclic || needed[column] {
                    needed[column] = true;
                    for &read in &reads[column] {
                        needed[read] = true;
                    }
                }
            }
        }
        let bounds = match input_bounds {
            Some(bounds)
                if !self.procedure_parameters.is_empty()
                    && bounds.len() + self.procedure_parameters.len() == self.driven.len() =>
            {
                Some(
                    bounds
                        .iter()
                        .copied()
                        .chain(self.procedure_parameters.iter().map(|(_, b)| *b))
                        .collect::<Vec<_>>(),
                )
            }
            Some(bounds) => Some(bounds.to_vec()),
            None => None,
        };
        if bounds
            .as_ref()
            .is_some_and(|b| b.len() != self.driven.len())
        {
            return Err(Error::new(
                "invalid_inputs",
                "input bounds must contain one interval per driven node",
            ));
        }
        let mut values = solution
            .voltages
            .iter()
            .copied()
            .map(I::point)
            .collect::<Vec<_>>();
        let mut exact: Vec<Option<Q>> = vec![None; self.nodes.len()];
        exact[0] = Some(Q::point(num_rational::BigRational::from_integer(0.into())));
        for (k, &node) in self.driven.iter().enumerate() {
            work.step()?;
            let point = root::binary(solution.voltages[node], work)?;
            let enclosure = bounds.as_ref().map(|b| b[k]);
            let own = match view.exact_input(node) {
                Some(value) => {
                    let inside = match enclosure {
                        Some(b) => {
                            let b = root::exact_interval(b, work)?;
                            b.lo <= value && value <= b.hi
                        }
                        None => true,
                    };
                    inside.then_some(value)
                }
                None => None,
            };
            values[node] = match (enclosure, &own) {
                (Some(b), _) => b,
                (None, Some(value)) => {
                    root::enclosure(&Q::point(value.clone()), "a source value", work)?
                }
                (None, None) => I::point(solution.voltages[node]),
            };
            exact[node] = Some(Q::point(own.unwrap_or(point)));
        }
        let mut result = Vec::new();
        for (columns, cyclic) in &components {
            if !cyclic {
                for &column in columns {
                    if !needed[column] {
                        continue;
                    }
                    let (index, sign) = definition[column];
                    let node = self.unknown[column];
                    values[node] = self.substituted_value(index, sign, &values, work)?;
                    let mut sum = Some(Q::point(num_rational::BigRational::from_integer(0.into())));
                    for rhs in &self.equations[index].original_rhs {
                        sum = match (sum, root::rounded_image(rhs, &exact, work)?) {
                            (Some(a), Some(b)) => Some(root::sum(&a, &b, work)?),
                            _ => None,
                        };
                    }
                    exact[node] = Some(match sum {
                        Some(value) => root::scaled(&value, sign, work)?,
                        None => root::exact_interval(values[node], work)?,
                    });
                }
                continue;
            }
            let relations = columns
                .iter()
                .map(|&column| {
                    let eq = &self.equations[definition[column].0];
                    Relation {
                        sign: definition[column].1,
                        rhs: eq.original_rhs.iter().map(unrounded).collect(),
                    }
                })
                .collect::<Vec<_>>();
            let mut column_of = vec![None; self.nodes.len()];
            for (i, &column) in columns.iter().enumerate() {
                column_of[self.unknown[column]] = Some(i);
            }
            let mut origins = Vec::new();
            for &column in columns {
                for origin in &self.equations[definition[column].0].origins {
                    work.step()?;
                    if !origins.contains(origin) {
                        work.debit(2, (origin.len() + 2) as u64)?;
                        origins.push(origin.clone());
                    }
                }
            }
            let name = origins.join(", ");
            let start = columns
                .iter()
                .map(|&column| solution.voltages[self.unknown[column]])
                .collect::<Vec<_>>();
            let (rounded, certified) = {
                let cycle = Cycle {
                    relations: &relations,
                    column: &column_of,
                    values: &exact,
                    name: &name,
                };
                let found = root::exact_root(&cycle, &start, work)?;
                let certified = if bounds.is_some() || found.is_none() {
                    Some(self.cycle_bounds(solution, &values, columns, &definition, work)?)
                } else {
                    None
                };
                let rounded = match found {
                    Some(found) => {
                        let mut rounded = Vec::with_capacity(columns.len());
                        for (&column, value) in columns.iter().zip(found) {
                            if let Some(all) = &certified {
                                let b = root::exact_interval(all[self.unknown[column]], work)?;
                                if value < b.lo || value > b.hi {
                                    return Err(Error::new(
                                        "invalid_ir",
                                        format!("exact same-time root of {name} lies outside its certified enclosure"),
                                    ));
                                }
                            }
                            rounded.push((root::nearest(&value, &name, work)?, Q::point(value)));
                        }
                        rounded
                    }
                    None => {
                        let all = certified.as_ref().ok_or_else(|| {
                            Error::new("invalid_ir", "same-time refinement lost its certificate")
                        })?;
                        let start = columns
                            .iter()
                            .map(|&column| all[self.unknown[column]])
                            .collect::<Vec<_>>();
                        root::refine(&cycle, &start, work)?
                    }
                };
                (rounded, certified)
            };
            for (&column, (value, enclosure)) in columns.iter().zip(rounded) {
                let node = self.unknown[column];
                values[node] = match &certified {
                    Some(all) => all[node],
                    None => root::enclosure(&enclosure, &name, work)?,
                };
                exact[node] = Some(if node >= view.node_count {
                    Q::point(root::binary(value, work)?)
                } else {
                    enclosure
                });
                result.push((node, value));
            }
        }
        Ok(Some(result))
    }

    /// Whether an RN cell can hold the decision 22 values of this system at
    /// these inputs: every same-time cycle is affine with point inputs and
    /// the roundings of its exact root are a binary64 fixed point of the
    /// rounded relations. Otherwise the cell, a binary64 fixed point, can only
    /// differ from them, and its search is not attempted.
    fn cell_may_hold_same_time_roundings(&self, inputs: &[f64]) -> Result<bool, Error> {
        use crate::same_time_root::{self as root, Cycle, Relation, Q};
        let Some(view) = &self.procedure_view else {
            return Ok(true);
        };
        let work = &view.plan.work;
        let Order::Cyclic {
            components,
            definition,
            ..
        } = self.substitution_order(work)?
        else {
            return Ok(true);
        };
        let Some(mut values) = self.with_inputs(inputs, vec![0.0; self.nodes.len()]) else {
            return Ok(false);
        };
        work.debit(
            2,
            (values.len() as u64).saturating_mul(64).saturating_add(64),
        )?;
        for (columns, cyclic) in &components {
            if !cyclic {
                for &column in columns {
                    let (index, sign) = definition[column];
                    values[self.unknown[column]] =
                        sign * self.point_rhs(&self.equations[index], &values)?;
                }
                continue;
            }
            let relations = columns
                .iter()
                .map(|&column| Relation {
                    sign: definition[column].1,
                    rhs: self.equations[definition[column].0]
                        .original_rhs
                        .iter()
                        .map(unrounded)
                        .collect(),
                })
                .collect::<Vec<_>>();
            let mut column_of = vec![None; self.nodes.len()];
            for (i, &column) in columns.iter().enumerate() {
                column_of[self.unknown[column]] = Some(i);
            }
            let mut exact = Vec::with_capacity(values.len());
            for (node, &value) in values.iter().enumerate() {
                work.step()?;
                exact.push(match column_of[node] {
                    Some(_) => None,
                    None => Some(Q::point(match view.exact_input(node) {
                        Some(value) if self.driven.contains(&node) => value,
                        _ => root::binary(value, work)?,
                    })),
                });
            }
            let start = vec![0.0; columns.len()];
            let cycle = Cycle {
                relations: &relations,
                column: &column_of,
                values: &exact,
                name: "a same-time cycle",
            };
            let Some(found) = root::exact_root(&cycle, &start, work)? else {
                return Ok(false);
            };
            for (&column, value) in columns.iter().zip(found) {
                values[self.unknown[column]] = root::nearest(&value, cycle.name, work)?;
            }
        }
        for eq in &self.equations {
            let rhs = self.point_rhs(eq, &values)?;
            if values[eq.positive] - values[eq.negative] != rhs {
                return Ok(false);
            }
        }
        Ok(true)
    }

    /// Install the decision 22 roundings in an expanded solution and record
    /// the program values among them for this activation's numeric values.
    fn store_same_time(
        &self,
        solution: &mut Solution,
        rounded: &[(usize, f64)],
    ) -> Result<(), Error> {
        let Some(view) = &self.procedure_view else {
            return Ok(());
        };
        let work = &view.plan.work;
        work.debit(
            2,
            (rounded.len() as u64).saturating_mul(32).saturating_add(32),
        )?;
        let mut values = Vec::new();
        for &(node, value) in rounded {
            solution.voltages[node] = value;
            if node >= view.node_count {
                let id = view
                    .ids
                    .get(node - view.node_count)
                    .copied()
                    .ok_or_else(|| {
                        Error::new("invalid_ir", "same-time value has no procedure value")
                    })?;
                values.push((id, value));
            }
        }
        view.plan
            .record_same_time(&solution.voltages[..view.node_count], &view.before, values)
    }

    /// The certificate of the stored values: every member of a same-time cycle
    /// holds the rounding of its exact root, which lies in the cycle's
    /// certificate on the complete driven enclosures. A program value is
    /// checked against the record its activation's solve made for these
    /// voltages and states; without that record the value was never stored,
    /// and the certificate is refused (an activation rebuilt only for this
    /// certificate stores nothing).
    fn check_same_time_roundings(
        &self,
        solution: &Solution,
        input_bounds: &[I],
    ) -> Result<(), Error> {
        let Some(view) = &self.procedure_view else {
            return Ok(());
        };
        if !self.same_time_cycle_shape() {
            return Ok(());
        }
        let recorded = view
            .plan
            .same_time_record(&solution.voltages[..view.node_count], &view.before)?;
        // A solution that is an RN cell's own root is that cell's certificate:
        // the solve keeps a cell only where it holds the decision 22 values,
        // and records them.
        if recorded.is_some()
            && view
                .plan
                .cell_bounds(input_bounds, &solution.voltages, self.nodes.len())?
                .is_some()
        {
            return Ok(());
        }
        let Some(rounded) = self.same_time_roundings(solution, Some(input_bounds))? else {
            return Ok(());
        };
        for (node, value) in rounded {
            let stored = if node < view.node_count {
                solution.voltages[node]
            } else {
                let id = view.ids.get(node - view.node_count).copied();
                match recorded
                    .as_ref()
                    .and_then(|r| r.iter().find(|(given, _)| Some(*given) == id))
                {
                    Some(&(_, value)) => value,
                    None => {
                        return Err(Error::new(
                            "waveform_accuracy",
                            format!(
                                "cannot certify same-time value at {}: its activation stored no \
                                 rounding for these voltages and states",
                                self.nodes[node]
                            ),
                        ))
                    }
                }
            };
            if stored.to_bits() != value.to_bits() {
                return Err(Error::new(
                    "waveform_accuracy",
                    format!(
                        "same-time value {stored:e} at {} is not the binary64 rounding {value:e} of its exact root",
                        self.nodes[node]
                    ),
                ));
            }
        }
        Ok(())
    }

    /// One relation evaluated over the current enclosures: the complete image
    /// of its right-hand side, rounding steps included.
    fn substituted_value(
        &self,
        index: usize,
        sign: f64,
        values: &[I],
        work: &crate::transition_source_plan::Work,
    ) -> Result<I, Error> {
        let eq = &self.equations[index];
        let mut image = I::ZERO;
        for rhs in &eq.original_rhs {
            image = image
                + interval_evaluate(rhs, values, Some(work))
                    .map_err(|mut error| {
                        error
                            .message
                            .push_str(&format!(" at {}", eq.origins.join(", ")));
                        error
                    })?
                    .value;
        }
        finite_interval(I::point(sign) * image, "substituted waveform value")
    }

    /// The same voltage budget as the Krawczyk distance test, here as a bound
    /// on every root for the complete input box.
    fn check_substituted_budget(
        &self,
        solution: &Solution,
        values: &[I],
        work: &crate::transition_source_plan::Work,
    ) -> Result<(), Error> {
        for &node in &self.unknown {
            work.step()?;
            let center = solution.voltages[node];
            let budget = self.voltage_budget_lower(center)?;
            let bound = (values[node] - I::point(center)).magnitude();
            if !bound.is_finite() || bound > budget {
                return Err(Error::new(
                    "waveform_accuracy",
                    format!(
                        "cannot certify same-time forward error at {}: bound {bound:e}, budget {budget:e}",
                        self.nodes[node]
                    ),
                ));
            }
        }
        Ok(())
    }

    /// A rounded program value has no derivative the Krawczyk test can use:
    /// an image of several binary64 values has no finite slope enclosure, and
    /// a one-value image has slope zero while the Newton preconditioner passes
    /// the operand derivative through. When such a value is in the system and
    /// every unknown is defined by exactly one grounded relation, with no
    /// cycle among these definitions, substitution in dependency order gives
    /// one root for every input in the box, and the interval image of that
    /// substitution encloses all of them. Each rounded image is the exact set
    /// of binary64 values of its operand image (ADR-006); no derivative, error
    /// model or representative input is used. A same-time cycle among these
    /// definitions is certified on its exact equation (decision 22,
    /// `component_waveform_bounds`); a system without a rounding step keeps
    /// the original refusal.
    fn substitution_fallback(
        &self,
        refusal: Error,
        solution: &Solution,
        base: &[I],
    ) -> Result<Vec<I>, Error> {
        if refusal.kind != "waveform_accuracy" {
            return Err(refusal);
        }
        let Some(view) = &self.procedure_view else {
            return Err(refusal);
        };
        match self.substitution_order(&view.plan.work)? {
            Order::Acyclic(order) => self.substituted_waveform_bounds(solution, base, order),
            Order::Cyclic {
                components,
                definition,
                ..
            } => self.component_waveform_bounds(solution, base, &components, &definition),
            Order::Unsupported => Err(refusal),
        }
    }

    fn substituted_waveform_bounds(
        &self,
        solution: &Solution,
        base: &[I],
        order: Vec<(usize, usize, f64)>,
    ) -> Result<Vec<I>, Error> {
        let Some(view) = &self.procedure_view else {
            return Err(Error::new(
                "invalid_ir",
                "substitution requires its procedure view",
            ));
        };
        let work = &view.plan.work;
        let mut values = base.to_vec();
        for (column, index, sign) in order {
            values[self.unknown[column]] = self.substituted_value(index, sign, &values, work)?;
        }
        self.check_substituted_budget(solution, &values, work)?;
        Ok(values)
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
                // Decision 22: the program values of a same-time cycle are
                // certified only where the activation's solve stored them.
                if self.same_time_cycle_shape()
                    && view
                        .plan
                        .same_time_record(&solution.voltages, &view.before)?
                        .is_none()
                {
                    return Err(Error::new(
                        "waveform_accuracy",
                        "cannot certify same-time program values: their activation stored no \
                         rounding for these voltages and states",
                    ));
                }
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
        if self.procedure_view.is_some() && self.has_rounding() {
            self.check_same_time_roundings(solution, input_bounds)?;
        }
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
        if contract {
            if let Some(refusal) = self.same_time_capability_refusal()? {
                return Err(refusal);
            }
            if let Some(refusal) = self.nonlinear_same_time_feedback()? {
                return Err(refusal);
            }
        }
        // Decision 22: a same-time cycle through program reals is certified on
        // its exact equation; the rounded relations certify a binary64 fixed
        // point instead of the root it stores. An RN cell still certifies a
        // solution that is its own root: the solve stores the cell only where
        // the cell's values are the roundings of the exact root.
        let cyclic = match &self.procedure_view {
            Some(view) if contract && self.same_time_cycle_shape() => {
                match self.substitution_order(&view.plan.work)? {
                    Order::Cyclic {
                        components,
                        definition,
                        ..
                    } if components.iter().any(|(_, cyclic)| *cyclic) => {
                        Some((components, definition))
                    }
                    _ => None,
                }
            }
            _ => None,
        };
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
        if let Some((components, definition)) = cyclic {
            return self.component_waveform_bounds(
                solution,
                &point_values,
                &components,
                &definition,
            );
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
            let jacobian = match self.interval_jacobian(&box_values) {
                Ok(jacobian) => jacobian,
                Err(error) => return self.substitution_fallback(error, solution, &point_values),
            };
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
        // Every refusal of the derivative-based proof below may still be
        // answered by substitution; its own refusals are accuracy refusals.
        let refuse = |error| self.substitution_fallback(error, solution, &point_values);
        let jacobian = match self.waveform_jacobian_rows(solution) {
            Ok(jacobian) => jacobian,
            Err(error) => return refuse(error),
        };
        let factor = match linear::Factorization::new(jacobian, n) {
            Ok(factor) => factor,
            Err(error) => {
                return refuse(Error::new(
                    "waveform_accuracy",
                    format!(
                        "cannot build Krawczyk waveform preconditioner from local Jacobian: {}",
                        error.message
                    ),
                ))
            }
        };
        let mut preconditioner = vec![vec![0.0; n]; n];
        for row_index in 0..n {
            let mut rhs = vec![0.0; n];
            rhs[row_index] = 1.0;
            let column = match factor.solve(rhs) {
                Ok(column) => column,
                Err(error) => {
                    return refuse(Error::new(
                        "waveform_accuracy",
                        format!(
                            "cannot solve Krawczyk waveform preconditioner column: {}",
                            error.message
                        ),
                    ))
                }
            };
            for (column_index, value) in column.into_iter().enumerate() {
                if !value.is_finite() {
                    return refuse(Error::new(
                        "waveform_accuracy",
                        "nonfinite Krawczyk waveform preconditioner",
                    ));
                }
                preconditioner[column_index][row_index] = value;
            }
        }
        let interval_jacobian = match scalar_jacobian {
            Some(jacobian) => jacobian,
            None => match self.interval_jacobian(&box_values) {
                Ok(jacobian) => jacobian,
                Err(error) => return refuse(error),
            },
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
                return refuse(Error::new(
                    "waveform_accuracy",
                    "nonfinite Krawczyk waveform image",
                ));
            }
            max_norm = max_norm.max(row_norm.hi);
            krawczyk[j] = image;
        }
        if max_norm.partial_cmp(&1.0) != Some(std::cmp::Ordering::Less) {
            return refuse(Error::new(
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
                return refuse(Error::new(
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
                return refuse(Error::new(
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
        // Decision 22 scope: a same-time cycle through a program real outside
        // the implemented class is refused before any RN cell or numeric solve.
        if let Some(refusal) = self.same_time_capability_refusal()? {
            return Err(refusal);
        }
        if let Some(refusal) = self.nonlinear_same_time_feedback()? {
            return Err(refusal);
        }
        let initial_expanded = initial_voltages
            .map(|v| match &self.procedure_view {
                Some(view) if v.len() == view.node_count => view.expand_executed(v),
                _ => Ok(v.to_vec()),
            })
            .transpose()?;
        // Propose an affine root without RN only inside the cell verifier.
        // Acceptance still requires a distinct exact rational neighborhood on
        // which every executed RN node is constant and the frozen physical
        // affine system has one root. Ordinary captures with already-certified
        // RN nodes do not enter this path. On a same-time cycle through program
        // reals the cell is only a solve: its binary64 fixed point stands where
        // it equals the rounding of the exact root (decision 22, below).
        let cyclic =
            self.procedure_view.is_some() && self.has_rounding() && self.has_same_time_cycle()?;
        let certified = if let Some(view) = &self.procedure_view {
            if let Some(program) = view.physical_program.as_ref().filter(|_| !cyclic) {
                self.try_cell(view, program, inputs)?
            } else if let Some(program) = view.physical_program.as_ref() {
                if self.cell_may_hold_same_time_roundings(inputs)? {
                    self.try_cell(view, program, inputs)?
                } else {
                    None
                }
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
            match self.solve_complete(inputs, initial_expanded.as_deref()) {
                Err(error) if self.procedure_view.is_some() => {
                    self.recover_solution(inputs, initial_expanded.as_deref(), error)?
                }
                Ok(solution) if initial_expanded.is_none() => {
                    self.with_consistent_activation(inputs, solution)?
                }
                result => result?,
            }
        };
        if let Some(view) = &self.procedure_view {
            // Decision 22: a same-time cycle through program reals stores the
            // rounding of its exact root, whichever route found the solution.
            if cyclic {
                if solution.voltages.len() == view.node_count {
                    solution.voltages = view.expand_executed(&solution.voltages)?;
                }
                if let Some(rounded) = self.same_time_roundings(&solution, None)? {
                    self.store_same_time(&mut solution, &rounded)?;
                }
            }
            solution.voltages.truncate(view.node_count);
            if let Some(bounds) = solution.certified_voltage_bounds.as_mut() {
                bounds.truncate(view.node_count);
            }
        }
        Ok(solution)
    }
    /// The RN cell route of `solve_with_initial`.
    fn try_cell(
        &self,
        view: &crate::procedure::CircuitView,
        program: &Program,
        inputs: &[f64],
    ) -> Result<Option<Vec<f64>>, Error> {
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
        )
    }
    /// Whether some relation has a rounding step (a program real).
    fn has_rounding(&self) -> bool {
        self.equations
            .iter()
            .any(|eq| eq.original_rhs.iter().any(rounding_step))
    }
    /// Newton failed on a system with executed program reals. A singular
    /// local rank first tries substitution (an acyclic system is determined
    /// by it). At a numerical limit (singular rank or no convergence) values
    /// that already satisfy every relation within its residual tolerance are
    /// kept; the waveform certificate still decides them. Without a caller
    /// seed, Newton restarts from the activation's own values.
    fn recover_solution(
        &self,
        inputs: &[f64],
        initial: Option<&[f64]>,
        error: Error,
    ) -> Result<Solution, Error> {
        let budget = |e: &Error| e.kind == "step_budget";
        if error.kind == "singular_jacobian" {
            match self.substitution_solve(inputs) {
                Ok(Some(solution)) => return Ok(solution),
                Err(order_error) if budget(&order_error) => return Err(order_error),
                Ok(None) | Err(_) => {}
            }
        }
        let numerical = matches!(error.kind, "nonconvergence" | "singular_jacobian");
        if let Some(initial) = initial {
            if numerical {
                match self.point_solution(inputs, initial.to_vec()) {
                    Ok(Some(solution)) => return Ok(solution),
                    Err(point_error) if budget(&point_error) => return Err(point_error),
                    Ok(None) | Err(_) => {}
                }
            }
            return Err(error);
        }
        if !(numerical || matches!(error.kind, "nonfinite_arithmetic" | "real_arithmetic")) {
            return Err(error);
        }
        let seed = match self.procedure_seed(inputs, numerical) {
            Ok(Some(seed)) => seed,
            Err(seed_error) if budget(&seed_error) => return Err(seed_error),
            Ok(None) | Err(_) => return Err(error),
        };
        match self.solve_complete(inputs, Some(&seed)) {
            Ok(solution) => Ok(solution),
            Err(retry)
                if numerical && matches!(retry.kind, "nonconvergence" | "singular_jacobian") =>
            {
                match self.point_solution(inputs, seed) {
                    Ok(Some(solution)) => Ok(solution),
                    Err(point_error) if budget(&point_error) => Err(point_error),
                    Ok(None) | Err(_) => Err(error),
                }
            }
            Err(retry) => Err(retry),
        }
    }
    /// The default Newton seed is zero for every unknown, including the values
    /// of executed program reals, so a relation that divides by such a value
    /// fails at the seed although the activation never produced zero, and a
    /// value scaled far beyond its operands can stop the line search there.
    /// The activation's own values at these inputs are a valid seed instead;
    /// the root found from it still needs the unchanged waveform certificate.
    /// With `settle`, each solved voltage defined by one grounded relation is
    /// first set to that relation read at the activation, which is then
    /// executed again from these voltages.
    fn procedure_seed(&self, inputs: &[f64], settle: bool) -> Result<Option<Vec<f64>>, Error> {
        let Some(view) = &self.procedure_view else {
            return Ok(None);
        };
        view.plan.work.debit(2, (view.node_count * 8 + 32) as u64)?;
        let mut voltages = vec![0.0; view.node_count];
        for (&node, &value) in self.driven.iter().zip(inputs) {
            if node < view.node_count {
                voltages[node] = value;
            }
        }
        let seed = view.expand_executed(&voltages)?;
        if !settle {
            return Ok(Some(seed));
        }
        for eq in &self.equations {
            let (node, sign) = match (eq.positive, eq.negative) {
                (node, 0) => (node, 1.),
                (0, node) => (node, -1.),
                _ => continue,
            };
            if node >= view.node_count || self.unknown_columns[node].is_none() {
                continue;
            }
            voltages[node] = sign * self.point_rhs(eq, &seed)?;
        }
        if voltages.iter().any(|v| !v.is_finite()) {
            return Ok(Some(seed));
        }
        view.expand_executed(&voltages).map(Some)
    }
    /// Newton accepts a point when every residual and its full correction fit
    /// the residual tolerance. From the zero seed it can accept values of
    /// executed program reals that the activation does not compute at the
    /// accepted voltages: a product of samples has slope zero at zero, so its
    /// correction there is zero, and a wide tolerance accepts the remaining
    /// residual. Read with the activation's own values, a relation then misses
    /// its residual bound and the waveform certificate refuses the point. Such
    /// a point is solved once more from the activation's values (the nominal
    /// seed); if that fails, the first point and its refusal are kept. Only a
    /// program value Newton left at its zero seed while its own relation reads
    /// a nonzero value can hide this way, so other points are kept unchecked.
    /// On a same-time cycle through program reals
    /// the values checked are the roundings of the cycle's exact root
    /// (decision 22), not the activation's executed values; a point whose
    /// roundings cannot be found is solved once more as well.
    fn with_consistent_activation(
        &self,
        inputs: &[f64],
        solution: Solution,
    ) -> Result<Solution, Error> {
        let budget = |e: &Error| e.kind == "step_budget";
        let Some(view) = &self.procedure_view else {
            return Ok(solution);
        };
        if solution.voltages.len() != self.nodes.len() {
            return Ok(solution);
        }
        let cyclic = self.has_same_time_cycle()?;
        let mut trapped = false;
        for eq in &self.equations {
            if !cyclic
                && !trapped
                && eq.negative == 0
                && eq.positive >= view.node_count
                && solution.voltages[eq.positive] == 0.
            {
                trapped = match self.point_rhs(eq, &solution.voltages) {
                    Ok(value) => value != 0.,
                    Err(error) if budget(&error) => return Err(error),
                    Err(_) => true,
                };
            }
        }
        if !cyclic && !trapped {
            return Ok(solution);
        }
        let mut activation = match view.expand_executed(&solution.voltages[..view.node_count]) {
            Ok(values) => values,
            Err(error) if budget(&error) => return Err(error),
            Err(_) => return Ok(solution),
        };
        let rounded = if cyclic {
            match self.same_time_roundings(&solution, None) {
                Ok(rounded) => Some(rounded),
                Err(error) if budget(&error) => return Err(error),
                Err(_) => None,
            }
        } else {
            Some(None)
        };
        if let Some(rounded) = rounded {
            for &(node, value) in rounded.iter().flatten() {
                activation[node] = value;
            }
            match self.point_solution(inputs, activation) {
                Ok(Some(_)) => return Ok(solution),
                Err(error) if budget(&error) => return Err(error),
                Ok(None) | Err(_) => {}
            }
        }
        let seed = match self.procedure_seed(inputs, false) {
            Ok(Some(seed)) => seed,
            Err(error) if budget(&error) => return Err(error),
            Ok(None) | Err(_) => return Ok(solution),
        };
        match self.solve_complete(inputs, Some(&seed)) {
            Ok(resolved) => Ok(resolved),
            Err(error) if budget(&error) => Err(error),
            Err(_) => Ok(solution),
        }
    }
    /// Newton checks the local rank of every unknown, including program
    /// values whose relation reads only earlier values. A rounded value scaled
    /// far beyond its operand, as in 1e16*(V(u)-c), makes the row-scaled
    /// factorization call such a triangular system singular although
    /// substitution determines every unknown. The substituted values still
    /// need the unchanged waveform certificate. With a same-time cycle the
    /// components are taken in dependency order: substitution outside the
    /// cycles, and Newton on each cycle's own relations without their rounding
    /// steps (decision 22) with every value it reads fixed, in rationals where
    /// binary64 Newton cannot meet the tolerance. Such a point starts the
    /// decision 22 roundings and their certificate; the rounded relations need
    /// not hold at it within the residual tolerance (an exact power of a large
    /// value has no binary64 neighbour that close).
    fn substitution_solve(&self, inputs: &[f64]) -> Result<Option<Solution>, Error> {
        let Some(view) = &self.procedure_view else {
            return Ok(None);
        };
        let work = &view.plan.work;
        let Some(mut values) = self.with_inputs(inputs, vec![0.0; self.nodes.len()]) else {
            return Ok(None);
        };
        match self.substitution_order(work)? {
            Order::Acyclic(order) => {
                for (column, index, sign) in order {
                    values[self.unknown[column]] =
                        sign * self.point_rhs(&self.equations[index], &values)?;
                }
                self.point_solution(inputs, values)
            }
            Order::Cyclic {
                components,
                definition,
                ..
            } => {
                for (columns, cyclic) in &components {
                    if !cyclic {
                        for &column in columns {
                            let (index, sign) = definition[column];
                            values[self.unknown[column]] =
                                sign * self.point_rhs(&self.equations[index], &values)?;
                        }
                        continue;
                    }
                    let cycle = self.cycle_circuit(columns, &definition, work)?;
                    let fixed = cycle
                        .driven
                        .iter()
                        .map(|&node| values[node])
                        .collect::<Vec<_>>();
                    let solved = match cycle.solve_complete(&fixed, None) {
                        Ok(solution) => Some(
                            cycle
                                .unknown
                                .iter()
                                .map(|&node| solution.voltages[node])
                                .collect::<Vec<_>>(),
                        ),
                        Err(error) if error.kind == "step_budget" => return Err(error),
                        Err(_) => self.exact_cycle_start(columns, &definition, &values, work)?,
                    };
                    let Some(solved) = solved else {
                        return Ok(None);
                    };
                    for (&column, value) in columns.iter().zip(solved) {
                        values[self.unknown[column]] = value;
                    }
                }
                if values.iter().any(|v| !v.is_finite()) {
                    return Ok(None);
                }
                let (mut residual_v, mut ratio) = (0.0_f64, 0.0_f64);
                for eq in &self.equations {
                    let lhs = values[eq.positive] - values[eq.negative];
                    let rhs = self.point_rhs(eq, &values)?;
                    let bound = self.tolerances.absolute
                        + self.tolerances.relative * lhs.abs().max(rhs.abs());
                    let residual = (lhs - rhs).abs();
                    if !(residual.is_finite() && bound.is_finite() && bound > 0.) {
                        return Ok(None);
                    }
                    residual_v = residual_v.max(residual);
                    ratio = ratio.max(residual / bound);
                }
                Ok(Some(Solution {
                    certified_voltage_bounds: None,
                    voltages: values,
                    max_residual_v: residual_v,
                    max_residual_ratio: ratio,
                    max_scaled_residual_ratio: None,
                    max_voltage_correction_v: None,
                    max_voltage_correction_ratio: None,
                }))
            }
            Order::Unsupported => Ok(None),
        }
    }
    /// Exact Newton on one cycle's relations without their rounding steps,
    /// every other value read as the exact binary64 it holds in `values`.
    fn exact_cycle_start(
        &self,
        columns: &[usize],
        definition: &[(usize, f64)],
        values: &[f64],
        work: &crate::transition_source_plan::Work,
    ) -> Result<Option<Vec<f64>>, Error> {
        use crate::same_time_root::{self as root, Cycle, Relation, Q};
        let relations = columns
            .iter()
            .map(|&column| Relation {
                sign: definition[column].1,
                rhs: self.equations[definition[column].0]
                    .original_rhs
                    .iter()
                    .map(unrounded)
                    .collect(),
            })
            .collect::<Vec<_>>();
        let mut column_of = vec![None; self.nodes.len()];
        for (i, &column) in columns.iter().enumerate() {
            column_of[self.unknown[column]] = Some(i);
        }
        work.debit(
            2,
            (values.len() as u64).saturating_mul(64).saturating_add(64),
        )?;
        let mut exact = Vec::with_capacity(values.len());
        for (node, &value) in values.iter().enumerate() {
            exact.push(match column_of[node] {
                Some(_) => None,
                None => Some(Q::point(root::binary(value, work)?)),
            });
        }
        let start = columns
            .iter()
            .map(|&column| values[self.unknown[column]])
            .collect::<Vec<_>>();
        root::newton_start(
            &Cycle {
                relations: &relations,
                column: &column_of,
                values: &exact,
                name: "a same-time cycle",
            },
            &start,
            work,
        )
    }
    /// The values completed with the driven inputs and procedure parameters.
    fn with_inputs(&self, inputs: &[f64], mut values: Vec<f64>) -> Option<Vec<f64>> {
        let complete = inputs
            .iter()
            .copied()
            .chain(self.procedure_parameters.iter().map(|(v, _)| *v))
            .collect::<Vec<_>>();
        let inputs = if complete.len() == self.driven.len() {
            &complete
        } else {
            inputs
        };
        if inputs.len() != self.driven.len() || values.len() != self.nodes.len() {
            return None;
        }
        for (&node, &value) in self.driven.iter().zip(inputs) {
            values[node] = value;
        }
        Some(values)
    }
    fn point_rhs(&self, eq: &Equation, values: &[f64]) -> Result<f64, Error> {
        if let Some(view) = &self.procedure_view {
            view.plan.work.step()?;
        }
        let mut rhs = eq.rhs_constant
            + eq.rhs_terms
                .iter()
                .map(|&(node, coefficient)| coefficient * values[node])
                .sum::<f64>();
        for expr in &eq.nonlinear {
            rhs += expression::evaluate(expr, values)?.value;
        }
        Ok(rhs)
    }
    /// These values as a solution when every relation already holds within
    /// its residual tolerance; None otherwise.
    fn point_solution(&self, inputs: &[f64], values: Vec<f64>) -> Result<Option<Solution>, Error> {
        let Some(values) = self.with_inputs(inputs, values) else {
            return Ok(None);
        };
        let (mut residual_v, mut ratio) = (0.0_f64, 0.0_f64);
        for eq in &self.equations {
            let lhs = values[eq.positive] - values[eq.negative];
            let rhs = self.point_rhs(eq, &values)?;
            let bound =
                self.tolerances.absolute + self.tolerances.relative * lhs.abs().max(rhs.abs());
            let residual = (lhs - rhs).abs();
            if !(residual.is_finite() && bound.is_finite() && residual <= bound) {
                return Ok(None);
            }
            residual_v = residual_v.max(residual);
            ratio = ratio.max(residual / bound);
        }
        Ok(Some(Solution {
            certified_voltage_bounds: None,
            voltages: values,
            max_residual_v: residual_v,
            max_residual_ratio: ratio,
            max_scaled_residual_ratio: None,
            max_voltage_correction_v: None,
            max_voltage_correction_ratio: None,
        }))
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

#[cfg(test)]
mod rounded_substitution_tests {
    use super::*;
    use crate::{events::EventModel, transition_source_plan::Work};
    use serde_json::{json, Value};

    const LOW: f64 = 0.39699999999999996;
    const HIGH: f64 = 0.3970000000000001;

    fn sample(node: usize) -> Value {
        let o = json!({"source":"rounded.va","line":1,"column":1,"instance":"dut"});
        json!({"op":"real_boundary","kind":"sample","origin":o,
            "value":{"op":"affine","constant":0.0,"terms":[{"node":node,"coefficient":1.0}]}})
    }
    // den = (V(d) < 0.25) ? <then> : <else>; V(y) <+ <rhs reading den>,
    // stored in the canonical branch order as V(0,y) <+ -<rhs>.
    fn program(then_value: Value, else_value: Value, rhs: Value) -> Program {
        let o = json!({"source":"rounded.va","line":1,"column":1,"instance":"dut"});
        let select = json!({"op":"select","relation":"lt","left":sample(1),
            "right":{"op":"affine","constant":0.25,"terms":[]},
            "then_value":then_value,"else_value":else_value,"origin":o});
        let negated =
            json!({"op":"multiply","left":{"op":"affine","constant":-1.0,"terms":[]},"right":rhs});
        serde_json::from_value(json!({"schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","d","y"],
            "contributions":[{"branch":{"instance":"dut","local_positive":"0","local_negative":"y","kind":"voltage"},
                "positive":0,"negative":2,"rhs":negated,"origin":o}],
            "procedures":[{"procedure_id":0,"instance":"dut","body":[
                {"expanded_statement_ordinal":0,"action":{"kind":"real_bind","binding":0,"origin":o,
                    "value":{"op":"real_boundary","kind":"snapshot","origin":o,"value":select}}},
                {"expanded_statement_ordinal":1,"action":{"kind":"contribution_capture","contribution":0}}]}],
            "real_bindings":[{"procedure_id":0,"name":"den","origin":o,"lifetime":"occurrence"}]}))
        .unwrap()
    }
    fn both_arms() -> Program {
        let o = json!({"source":"rounded.va","line":1,"column":1,"instance":"dut"});
        program(
            json!({"op":"real_binary","operation":"multiply","origin":o,
                "left":{"op":"affine","constant":0.5,"terms":[]},"right":sample(1)}),
            sample(1),
            json!({"op":"real_local","binding":0}),
        )
    }
    fn circuit(p: Program, absolute: f64, w: &Work, domain: I) -> Circuit {
        let model = EventModel::new_with_procedure_work(
            p,
            vec!["d".into()],
            Tolerances {
                absolute,
                relative: 0.,
            },
            w.clone(),
        )
        .unwrap();
        model.circuit_at(&[], &[], &[domain]).unwrap()
    }
    fn moving() -> I {
        I { lo: LOW, hi: HIGH }
    }

    #[test]
    fn selected_real_over_a_moving_input_box_is_enclosed_by_substitution() {
        let w = Work::default();
        let c = circuit(both_arms(), 1e-12, &w, moving());
        let s = c.solve(&[0.397]).unwrap();
        let b = c.waveform_bounds(&s, &[moving()]).unwrap();
        // V(d) >= 0.25 on the whole box, so y = RN(V(d)): every binary64 in
        // [LOW, HIGH] is a possible answer and each must be enclosed.
        assert!(b[2].lo <= LOW && HIGH <= b[2].hi);
        assert!((b[2] - I::point(s.voltages[2])).magnitude() <= 1e-12);
    }
    #[test]
    fn substitution_reports_the_forward_error_beyond_the_budget() {
        // V(y) <+ 1000*(den - 0.396): every relation's residual fits 1e-15 V,
        // but the amplified set of possible rounded values does not.
        let o = json!({"source":"rounded.va","line":1,"column":1,"instance":"dut"});
        let p = program(
            json!({"op":"real_binary","operation":"multiply","origin":o,
                "left":{"op":"affine","constant":0.5,"terms":[]},"right":sample(1)}),
            sample(1),
            json!({"op":"multiply","left":{"op":"affine","constant":1000.0,"terms":[]},
                "right":{"op":"add","left":{"op":"real_local","binding":0},
                    "right":{"op":"affine","constant":-0.396,"terms":[]}}}),
        );
        let w = Work::default();
        let c = circuit(p, 1e-15, &w, moving());
        let s = c.solve(&[0.397]).unwrap();
        let error = c.waveform_bounds(&s, &[moving()]).unwrap_err();
        assert_eq!(error.kind, "waveform_accuracy");
        assert!(
            error
                .message
                .starts_with("cannot certify same-time forward error at y: bound "),
            "{}",
            error.message
        );
    }
    #[test]
    fn rounded_value_read_by_its_own_relation_is_the_root_of_the_real_equation() {
        // den = V(y) on the selected arm and y = 0.5*den + V(d): the rounded
        // value feeds its own operand, so there is no substitution order. The
        // real-arithmetic equation y = 0.5*y + V(d) has the root 2*V(d).
        let p = program(
            sample(1),
            sample(2),
            json!({"op":"add","left":{"op":"multiply","left":{"op":"affine","constant":0.5,"terms":[]},
                "right":{"op":"real_local","binding":0}},
                "right":{"op":"affine","constant":0.0,"terms":[{"node":1,"coefficient":1.0}]}}),
        );
        let w = Work::default();
        let c = circuit(p, 1e-12, &w, moving());
        let s = c.solve(&[0.397]).unwrap();
        let b = c.waveform_bounds(&s, &[moving()]).unwrap();
        let rational = |v: f64| num_rational::BigRational::from_float(v).unwrap();
        let two = rational(2.);
        assert!(rational(b[2].lo) <= two.clone() * rational(LOW));
        assert!(two * rational(HIGH) <= rational(b[2].hi));
        assert!((b[2] - I::point(s.voltages[2])).magnitude() <= 1e-12);
    }
    #[test]
    fn a_rounded_value_that_only_reads_itself_is_refused() {
        // den = V(y) and V(y) <+ den: every real value solves y = y.
        let p = program(sample(2), sample(2), json!({"op":"real_local","binding":0}));
        let w = Work::default();
        let c = circuit(p, 1e-12, &w, moving());
        let refused = c
            .solve(&[0.397])
            .and_then(|s| c.waveform_bounds(&s, &[moving()]));
        assert!(refused.is_err());
    }
    #[test]
    fn values_outside_a_same_time_cycle_keep_their_rounding() {
        // den = V(y) on both arms of a selection and V(y) <+ 2*den - 2: the
        // rounded value feeds its own operand (root y = 2, not contractive).
        // q = RN(RN(3*V(d)) - 0.3) and V(w) <+ 1e18*q lie outside the cycle;
        // at V(d) = 0.1 the rounded q is 2^-54, while 3*0.1 - 0.3 is 2^-55 in
        // real arithmetic, so w = 1e18*2^-54 only with q's rounding kept.
        let at =
            |column: u32| json!({"source":"rounded.va","line":1,"column":column,"instance":"dut"});
        let constant = |v: f64| json!({"op":"affine","constant":v,"terms":[]});
        let local = |binding: usize| json!({"op":"real_local","binding":binding});
        let negated = |rhs: Value| json!({"op":"multiply","left":constant(-1.0),"right":rhs});
        let select = json!({"op":"select","relation":"lt","left":sample(1),"right":constant(0.25),
            "then_value":sample(2),"else_value":sample(2),"origin":at(1)});
        let tripled = json!({"op":"real_binary","operation":"multiply","origin":at(2),
            "left":sample(1),"right":constant(3.0)});
        let difference = json!({"op":"real_binary","operation":"subtract","origin":at(3),
            "left":tripled,"right":constant(0.3)});
        let y_rhs = json!({"op":"add","left":{"op":"multiply","left":constant(2.0),"right":local(0)},
            "right":constant(-2.0)});
        let w_rhs = json!({"op":"multiply","left":constant(1e18),"right":local(1)});
        let branch = |node: &str| json!({"instance":"dut","local_positive":"0","local_negative":node,"kind":"voltage"});
        let bind = |ordinal: usize, binding: usize, value: Value, column: u32| {
            json!({"expanded_statement_ordinal":ordinal,"action":{"kind":"real_bind","binding":binding,
                "origin":at(column),"value":{"op":"real_boundary","kind":"snapshot","origin":at(column + 1),
                "value":value}}})
        };
        let p: Program = serde_json::from_value(json!({"schema_version":crate::ir::SCHEMA_VERSION,
            "nodes":["0","d","y","w"],
            "contributions":[
                {"branch":branch("y"),"positive":0,"negative":2,"rhs":negated(y_rhs),"origin":at(4)},
                {"branch":branch("w"),"positive":0,"negative":3,"rhs":negated(w_rhs),"origin":at(5)}],
            "procedures":[{"procedure_id":0,"instance":"dut","body":[
                bind(0, 0, select, 6),
                bind(1, 1, difference, 8),
                {"expanded_statement_ordinal":2,"action":{"kind":"contribution_capture","contribution":0}},
                {"expanded_statement_ordinal":3,"action":{"kind":"contribution_capture","contribution":1}}]}],
            "real_bindings":[{"procedure_id":0,"name":"den","origin":at(10),"lifetime":"occurrence"},
                {"procedure_id":0,"name":"q","origin":at(11),"lifetime":"occurrence"}]}))
        .unwrap();
        let w = Work::default();
        let c = circuit(p, 1e-9, &w, I::point(0.1));
        let s = c.solve(&[0.1]).unwrap();
        let rounded = 1e18 * 2_f64.powi(-54);
        assert_eq!(s.voltages[3], rounded);
        let b = c.waveform_bounds(&s, &[I::point(0.1)]).unwrap();
        assert!(b[3].lo <= rounded && rounded <= b[3].hi, "{:?}", b[3]);
        assert!(b[2].lo <= 2. && 2. <= b[2].hi, "{:?}", b[2]);
    }
    #[test]
    fn scaled_rounded_value_with_a_singular_local_rank_is_solved_by_substitution() {
        // V(y) <+ 1e16*(den - 0.397): row scaling calls the local rank
        // singular, substitution solves it, and the amplified set of rounded
        // values is refused by its forward error.
        let p = program(
            sample(1),
            sample(1),
            json!({"op":"multiply","left":{"op":"affine","constant":1e16,"terms":[]},
                "right":{"op":"add","left":{"op":"real_local","binding":0},
                    "right":{"op":"affine","constant":-0.397,"terms":[]}}}),
        );
        let w = Work::default();
        let c = circuit(p, 1e-9, &w, moving());
        let s = c.solve(&[0.397]).unwrap();
        assert_eq!(s.voltages[2], 0.);
        let error = c.waveform_bounds(&s, &[moving()]).unwrap_err();
        assert!(
            error
                .message
                .starts_with("cannot certify same-time forward error at y: bound "),
            "{}",
            error.message
        );
    }
    #[test]
    fn substitution_spends_the_original_owner_and_stays_exhausted() {
        let probe = Work::default();
        let c = circuit(both_arms(), 1e-12, &probe, moving());
        let s = c.solve(&[0.397]).unwrap();
        let prefix = probe.spent();
        c.waveform_bounds(&s, &[moving()]).unwrap();
        let total = probe.spent();
        assert!(total > prefix);
        let w = Work::limited([128, 8192, total - 1]);
        let c = circuit(both_arms(), 1e-12, &w, moving());
        let s = c.solve(&[0.397]).unwrap();
        assert_eq!(w.spent(), prefix);
        assert_eq!(
            c.waveform_bounds(&s, &[moving()]).unwrap_err().kind,
            "step_budget"
        );
        let failed = w.spent();
        for _ in 0..2 {
            assert_eq!(
                c.waveform_bounds(&s, &[moving()]).unwrap_err().kind,
                "step_budget"
            );
            assert_eq!(w.spent(), failed);
        }
    }
    #[test]
    fn division_by_a_selected_real_starts_newton_from_the_activation() {
        // den = (V(d) < 0.25) ? 0.25 : V(d); V(y) <+ 0.2/den. The zero seed
        // would divide by zero although den is never below 0.25.
        let p = program(
            json!({"op":"affine","constant":0.25,"terms":[]}),
            sample(1),
            json!({"op":"divide","left":{"op":"affine","constant":0.2,"terms":[]},
                "right":{"op":"real_local","binding":0}}),
        );
        let w = Work::default();
        let c = circuit(p, 1e-12, &w, moving());
        let s = c.solve(&[0.397]).unwrap();
        let b = c.waveform_bounds(&s, &[moving()]).unwrap();
        assert!((b[2] - I::point(s.voltages[2])).magnitude() <= 1e-12);
        let exact = |d: f64| {
            num_rational::BigRational::from_float(0.2).unwrap()
                / num_rational::BigRational::from_float(d).unwrap()
        };
        let lo = num_rational::BigRational::from_float(b[2].lo).unwrap();
        let hi = num_rational::BigRational::from_float(b[2].hi).unwrap();
        assert!(lo <= exact(HIGH) && exact(LOW) <= hi);
    }
    #[test]
    fn reset_sample_with_a_one_value_rounded_image_is_certified() {
        // @(timer(0.5)) begin rst=1; q=V(z); end  @(timer(0.75)) rst=0;
        // V(z) <+ idt(q,1,rst); V(y) <+ laplace_nd(V(z),{1},{1,1}); V(held) <+ q.
        // After the reset q = RN(V(z)) has a one-value image: its interval
        // slope is zero while the Newton preconditioner passes the operand
        // derivative through, so the Krawczyk contraction bound is 2.
        // Each operator, event and contribution has its own call site.
        let at =
            |column: u32| json!({"source":"reset.va","line":1,"column":column,"instance":"dut"});
        let constant = |value: f64| json!({"op":"affine","constant":value,"terms":[]});
        let z = json!({"op":"affine","constant":0.0,"terms":[{"node":1,"coefficient":1.0}]});
        let branch = |positive: &str, negative: &str| json!({"instance":"dut","local_positive":positive,"local_negative":negative,"kind":"voltage"});
        let timer = |start: f64| json!({"kind":"timer","start":start,"period":0.0,"time_tolerance":1e-12,"enabled":true});
        let gate = |ordinal: usize, action: Value| json!({"expanded_statement_ordinal":ordinal,"action":action});
        let request: crate::ir::Request = serde_json::from_value(json!({
            "program":{"schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","z","held","u","y"],
                "contributions":[
                    {"branch":branch("r","z"),"positive":0,"negative":1,"origin":at(1),
                        "rhs":{"op":"multiply","left":constant(-1.0),"right":{"op":"operator","operator":0}}},
                    {"branch":branch("r","y"),"positive":0,"negative":4,"origin":at(2),
                        "rhs":{"op":"multiply","left":constant(-1.0),"right":{"op":"operator","operator":1}}},
                    {"branch":branch("held","r"),"positive":2,"negative":0,"origin":at(3),
                        "rhs":{"op":"state","state":0}}],
                "states":[{"instance":"dut","name":"q","kind":"real","initial":0.0},
                    {"instance":"dut","name":"rst","kind":"integer","initial":0.0}],
                "events":[
                    {"trigger":timer(0.5),"origin":at(4),"procedure_id":0,"expanded_statement_ordinal":1,"body":[
                        {"kind":"assign","state":1,"rhs":constant(1.0)},
                        {"kind":"assign","state":0,"rhs":{"op":"real_boundary","kind":"store","origin":at(5),
                            "value":{"op":"real_boundary","kind":"sample","origin":at(6),"value":z}}}]},
                    {"trigger":timer(0.75),"origin":at(7),"procedure_id":0,"expanded_statement_ordinal":2,"body":[
                        {"kind":"assign","state":1,"rhs":constant(0.0)}]},
                    {"trigger":{"kind":"initial_step"},"origin":at(8),"procedure_id":0,"expanded_statement_ordinal":0,"body":[
                        {"kind":"assign","state":0,"rhs":{"op":"real_boundary","kind":"store","origin":at(9),
                            "value":constant(1.0)}},
                        {"kind":"assign","state":1,"rhs":constant(0.0)}]}],
                "operators":[
                    {"kind":"idt","input":{"op":"state","state":0},"ic":1.0,"reset":{"op":"state","state":1},"origin":at(10)},
                    {"kind":"laplace_nd","input":z,"numerator":[1.0],"denominator":[1.0,1.0],"origin":at(11)}],
                "step_bounds":[],
                "procedures":[{"procedure_id":0,"instance":"dut","body":[
                    gate(0,json!({"kind":"event_gate","event":2})),
                    gate(1,json!({"kind":"event_gate","event":0})),
                    gate(2,json!({"kind":"event_gate","event":1})),
                    gate(3,json!({"kind":"contribution_capture","contribution":0})),
                    gate(4,json!({"kind":"contribution_capture","contribution":1})),
                    gate(5,json!({"kind":"contribution_capture","contribution":2}))]}],
                "real_bindings":[]},
            "driven":["u"],"samples":[],
            "transient":{"pwl":[[[0,0],[1,1]]],"output_times":[0,0.25,0.5,0.625,0.75,0.875,1],
                "stop":1,"max_step":1},
            "tolerances":{"absolute":1e-7,"relative":1e-7}}))
        .unwrap();
        let response = serde_json::to_value(crate::run(request).unwrap()).unwrap();
        let at_reset = 0.5 + (-0.5_f64).exp();
        let at_release = 1. + (at_reset - 1.) * (-0.25_f64).exp();
        let times: [f64; 7] = [0., 0.25, 0.5, 0.625, 0.75, 0.875, 1.];
        let rows = response["solutions"].as_array().unwrap();
        assert_eq!(rows.len(), times.len());
        for (row, t) in rows.iter().zip(times) {
            let (z, y) = if t < 0.5 {
                (1. + t, t + (-t).exp())
            } else if t <= 0.75 {
                (1., 1. + (at_reset - 1.) * (-(t - 0.5)).exp())
            } else {
                (1. + t - 0.75, (t - 0.75) + at_release * (-(t - 0.75)).exp())
            };
            let v = |node: usize| row["voltages"][node].as_f64().unwrap();
            assert!((v(1) - z).abs() <= 1e-7, "z at {t}: {row}");
            assert!((v(4) - y).abs() <= 1e-7, "y at {t}: {row}");
            assert!((v(2) - 1.).abs() <= 1e-7, "held at {t}: {row}");
        }
    }
}

#[cfg(test)]
mod same_time_structure_tests {
    use super::relation_matching;

    #[test]
    fn relation_matching_moves_a_greedy_choice_along_an_augmenting_path() {
        // Relation 0 may define column 0 or 1, relation 1 only column 0: the
        // greedy start gives column 0 to relation 0, the augmenting path then
        // moves relation 0 to column 1.
        assert_eq!(
            relation_matching(&[vec![0, 1], vec![0]], 2),
            vec![Some(1), Some(0)]
        );
        // Two relations that can only define the same column: one stays free.
        assert_eq!(
            relation_matching(&[vec![0], vec![0]], 1),
            vec![Some(0), None]
        );
        // A longer path: relation 2 takes column 0 from relation 1, which takes
        // column 1 from relation 0, which moves to column 2.
        assert_eq!(
            relation_matching(&[vec![1, 2], vec![0, 1], vec![0]], 3),
            vec![Some(2), Some(1), Some(0)]
        );
    }
}
