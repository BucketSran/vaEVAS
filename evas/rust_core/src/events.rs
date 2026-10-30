//! Bound affine event model. State is separate from electrical unknowns.
use crate::event_conditions::{Conditions, Selection};
use crate::interval::Interval as I;
use crate::ir::{Error, EventTrigger, Expression, Program, StateKind, Term, Tolerances};
use crate::settlement_bounds::Bounds;
use crate::solver::Circuit;
use std::cell::RefCell;
use std::collections::BTreeSet;
#[path = "event_source_predicate.rs"]
mod source_predicate;
pub(crate) use source_predicate::qualify_point as qualify_point_predicate;
pub(crate) use source_predicate::Binding as SourcePredicateBinding;

#[derive(Clone, PartialEq)]
pub(crate) struct AffineState {
    pub(crate) constant: f64,
    pub(crate) nodes: Vec<f64>,
    pub(crate) states: Vec<f64>,
    operators: Vec<f64>,
    pub(crate) node_dependencies: BTreeSet<usize>,
    pub(crate) state_dependencies: BTreeSet<usize>,
    pub(crate) operator_dependencies: BTreeSet<usize>,
    // Structural dependence survives coefficient cancellation and underflow.
    // It is deliberately conservative, including exact algebraic cancellations.
    has_variables: bool,
}

impl AffineState {
    /// Source execution owns the numerical row. This marks only conservative
    /// structural dependencies; its zero coefficients are never a solve row.
    pub(crate) fn mark_dependency_metadata(&mut self) {
        self.has_variables = !self.node_dependencies.is_empty()
            || !self.state_dependencies.is_empty()
            || !self.operator_dependencies.is_empty();
    }

    pub(crate) fn held_row(
        row: &[I],
        program: &Program,
        dependencies: BTreeSet<usize>,
        work: &crate::transition_source_plan::Work,
    ) -> Result<Self, Error> {
        work.debit(
            2,
            (program.nodes.len() + program.states.len() + program.operators.len()) as u64,
        )?;
        let mut states = Vec::with_capacity(program.states.len());
        for value in &row[program.nodes.len()..program.nodes.len() + program.states.len()] {
            work.step()?;
            if value.lo != value.hi {
                return Err(Error::new(
                    "condition_precision",
                    "held target coefficients require exact point rows",
                ));
            }
            states.push(value.lo);
        }
        let constant = *row
            .last()
            .ok_or_else(|| Error::new("invalid_ir", "missing held target row"))?;
        if constant.lo != constant.hi {
            return Err(Error::new(
                "condition_precision",
                "held target constant has uncertain coefficients",
            ));
        }
        Ok(Self {
            constant: constant.lo,
            nodes: vec![0.; program.nodes.len()],
            states,
            operators: vec![0.; program.operators.len()],
            has_variables: !dependencies.is_empty(),
            state_dependencies: dependencies,
            node_dependencies: BTreeSet::new(),
            operator_dependencies: BTreeSet::new(),
        })
    }

    // Actual owned storage, including the private dense operator coefficients.
    // This is used only by the opt-in forcing clone admission.
    pub(crate) fn owned_copy_items(&self) -> usize {
        self.nodes
            .len()
            .saturating_add(self.states.len())
            .saturating_add(self.operators.len())
            .saturating_add(self.node_dependencies.len().saturating_mul(4))
            .saturating_add(self.state_dependencies.len().saturating_mul(4))
            .saturating_add(self.operator_dependencies.len().saturating_mul(4))
    }
    pub(crate) fn union_dependencies(&mut self, other: &Self) {
        self.node_dependencies.extend(&other.node_dependencies);
        self.state_dependencies.extend(&other.state_dependencies);
        self.operator_dependencies
            .extend(&other.operator_dependencies);
        self.has_variables |= other.has_variables;
    }

    /// Substitute voltage-affine trial updates for state references. Each update
    /// is based on the accepted old state, with local statement order preserved.
    fn substitute(&self, updates: &[Self]) -> Result<Self, Error> {
        let mut result = self.clone();
        result.states.clear();
        for (&coefficient, update) in self.states.iter().zip(updates) {
            if coefficient == 0.0 {
                continue;
            }
            result.constant += coefficient * update.constant;
            for (node, &value) in result.nodes.iter_mut().zip(&update.nodes) {
                *node += coefficient * value;
            }
        }
        if !result.constant.is_finite() || result.nodes.iter().any(|v| !v.is_finite()) {
            return Err(Error::new(
                "nonfinite_arithmetic",
                "nonfinite event substitution",
            ));
        }
        Ok(result)
    }

    pub(crate) fn value(&self, nodes: &[f64], states: &[f64]) -> Result<f64, Error> {
        self.value_with(nodes, states, &[])
    }

    pub(crate) fn value_with(
        &self,
        nodes: &[f64],
        states: &[f64],
        operators: &[f64],
    ) -> Result<f64, Error> {
        let value = self.constant
            + self
                .nodes
                .iter()
                .zip(nodes)
                .map(|(a, v)| a * v)
                .sum::<f64>()
            + self
                .states
                .iter()
                .zip(states)
                .map(|(a, v)| a * v)
                .sum::<f64>()
            + self
                .operators
                .iter()
                .zip(operators)
                .map(|(a, v)| a * v)
                .sum::<f64>();
        if !value.is_finite() {
            return Err(Error::new(
                "nonfinite_arithmetic",
                "nonfinite event expression",
            ));
        }
        Ok(value)
    }

    pub(crate) fn single_operator_form(&self) -> Option<(usize, f64, f64)> {
        if !self.node_dependencies.is_empty() || !self.state_dependencies.is_empty() {
            return None;
        }
        let mut found = None;
        for (index, &coefficient) in self.operators.iter().enumerate() {
            if coefficient == 0.0 {
                continue;
            }
            if found.replace((index, coefficient, self.constant)).is_some() {
                return None;
            }
        }
        found
    }

    fn bind(&self, states: &[f64], operators: &[f64]) -> Result<Expression, Error> {
        Ok(Expression::Affine {
            constant: self.value_with(&[], states, operators)?,
            terms: self
                .nodes
                .iter()
                .enumerate()
                .filter(|(_, a)| **a != 0.0)
                .map(|(node, coefficient)| Term {
                    node,
                    coefficient: *coefficient,
                })
                .collect(),
        })
    }
}

pub(crate) fn affine(
    expr: &Expression,
    program: &Program,
    owner: &str,
) -> Result<AffineState, Error> {
    let mut result = AffineState {
        constant: 0.0,
        nodes: vec![0.0; program.nodes.len()],
        states: vec![0.0; program.states.len()],
        operators: vec![0.0; program.operators.len()],
        node_dependencies: BTreeSet::new(),
        state_dependencies: BTreeSet::new(),
        operator_dependencies: BTreeSet::new(),
        has_variables: false,
    };
    match expr {
        Expression::RealLocal { binding } => {
            return Err(crate::real_expression::unbound_local(*binding, program))
        }
        Expression::RealCall { .. }
        | Expression::UnsupportedSystemCall { .. }
        | Expression::RealBinary { .. }
        | Expression::RealBoundary { .. } => {
            return affine(&crate::real_expression::materialized(expr)?, program, owner)
        }
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
        | Expression::EventMath { .. } => {
            return Err(Error::new(
                "unsupported_transient",
                "pure event mathematics requires an isolated observer",
            ))
        }
        Expression::Affine { constant, terms } => {
            crate::expression::validate(expr, program.nodes.len())?;
            result.constant = *constant;
            for term in terms {
                result.nodes[term.node] = term.coefficient;
                // Explicit raw-IR references remain structural even at zero weight.
                result.has_variables = true;
                result.node_dependencies.insert(term.node);
            }
        }
        Expression::State { state } => {
            if *state >= program.states.len() || program.states[*state].instance != owner {
                return Err(Error::new(
                    "invalid_ir",
                    "state reference must belong to its instance",
                ));
            }
            result.states[*state] = 1.0;
            result.state_dependencies.insert(*state);
            result.has_variables = true;
        }
        Expression::Operator { operator } => {
            if *operator >= program.operators.len()
                || program.operators[*operator].origin().instance != owner
            {
                return Err(Error::new(
                    "invalid_ir",
                    "operator reference must belong to its instance",
                ));
            }
            result.operators[*operator] = 1.0;
            result.operator_dependencies.insert(*operator);
            result.has_variables = true;
        }
        Expression::Add { left, right } | Expression::Multiply { left, right } => {
            let a = affine(left, program, owner)?;
            let b = affine(right, program, owner)?;
            let multiply = matches!(expr, Expression::Multiply { .. });
            if multiply && a.has_variables && b.has_variables {
                return Err(Error::new(
                    "unsupported_transient",
                    "transient expressions must be jointly affine in voltage and state",
                ));
            }
            result.has_variables = a.has_variables || b.has_variables;
            result.node_dependencies = a
                .node_dependencies
                .union(&b.node_dependencies)
                .copied()
                .collect();
            result.state_dependencies = a
                .state_dependencies
                .union(&b.state_dependencies)
                .copied()
                .collect();
            result.operator_dependencies = a
                .operator_dependencies
                .union(&b.operator_dependencies)
                .copied()
                .collect();
            let (ka, kb) = if multiply {
                (b.constant, a.constant)
            } else {
                (1.0, 1.0)
            };
            result.constant = if multiply {
                a.constant * b.constant
            } else {
                a.constant + b.constant
            };
            result.nodes = a
                .nodes
                .iter()
                .zip(&b.nodes)
                .map(|(x, y)| ka * x + kb * y)
                .collect();
            result.operators = a
                .operators
                .iter()
                .zip(&b.operators)
                .map(|(x, y)| ka * x + kb * y)
                .collect();
            result.states = a
                .states
                .iter()
                .zip(&b.states)
                .map(|(x, y)| ka * x + kb * y)
                .collect();
        }
        Expression::Divide { left, right } => {
            let mut numerator = affine(left, program, owner)?;
            let denominator = affine(right, program, owner)?;
            if denominator.has_variables || denominator.constant == 0.0 {
                return Err(Error::new(
                    "unsupported_transient",
                    "affine event division requires a finite nonzero constant denominator",
                ));
            }
            numerator.constant /= denominator.constant;
            for value in numerator
                .nodes
                .iter_mut()
                .chain(&mut numerator.states)
                .chain(&mut numerator.operators)
            {
                *value /= denominator.constant;
            }
            result = numerator;
        }
        Expression::Power { .. } => {
            return Err(Error::new(
                "unsupported_transient",
                "polynomial transient equations are not supported",
            ))
        }
        Expression::Select { .. } => {
            return Err(Error::new(
                "unsupported_transient",
                "ordinary analog conditionals are not supported in transient event equations",
            ))
        }
    }
    if !result.constant.is_finite()
        || result
            .nodes
            .iter()
            .chain(&result.states)
            .chain(&result.operators)
            .any(|v| !v.is_finite())
    {
        return Err(Error::new(
            "nonfinite_arithmetic",
            "affine event coefficient overflow",
        ));
    }
    Ok(result)
}

// Conservative contribution connectivity, independent of the currently selected arm.
// Coefficients are used only for dependency analysis; runtime equations resolve
// Select before affine binding.
pub(crate) fn contribution_affine(
    expr: &Expression,
    program: &Program,
    owner: &str,
) -> Result<AffineState, Error> {
    contribution_shape(expr, program, owner).map(|(row, _)| row)
}
fn contribution_shape(
    expr: &Expression,
    program: &Program,
    owner: &str,
) -> Result<(AffineState, bool), Error> {
    match expr {
        Expression::Select {
            left,
            right,
            then_value,
            else_value,
            ..
        } => {
            let (mut result, mut dc) = contribution_shape(then_value, program, owner)?;
            for child in [left, right, else_value] {
                let (other, child_dc) = contribution_shape(child, program, owner)?;
                dc |= child_dc;
                result.node_dependencies.extend(other.node_dependencies);
                result.state_dependencies.extend(other.state_dependencies);
                result
                    .operator_dependencies
                    .extend(other.operator_dependencies);
                result.has_variables |= other.has_variables;
            }
            Ok((result, dc))
        }
        Expression::Add { left, right }
        | Expression::Multiply { left, right }
        | Expression::Divide { left, right } => {
            let (a, ad) = contribution_shape(left, program, owner)?;
            let (b, bd) = contribution_shape(right, program, owner)?;
            // Reuse affine validation on a representative arm, retaining every
            // structural dependency separately for feedback checks.
            let representative = representative(expr);
            let operator_free = |v: &AffineState| v.operator_dependencies.is_empty();
            let operator_only = |v: &AffineState| {
                !v.operator_dependencies.is_empty()
                    && v.node_dependencies.is_empty()
                    && v.state_dependencies.is_empty()
            };
            let state_only = |v: &AffineState| {
                !v.state_dependencies.is_empty()
                    && v.node_dependencies.is_empty()
                    && v.operator_dependencies.is_empty()
            };
            let held_coefficient =
                (state_only(&a) && operator_only(&b)) || (operator_only(&a) && state_only(&b));
            let transition_coefficient = ((operator_free(&a) && operator_only(&b))
                || (operator_only(&a) && operator_free(&b)))
                && a.operator_dependencies
                    .iter()
                    .chain(&b.operator_dependencies)
                    .all(|&index| {
                        matches!(
                            program.operators[index],
                            crate::ir::OperatorSpec::Transition { .. }
                        )
                    });
            let sampled_coefficient = matches!(expr, Expression::Multiply { .. })
                && (held_coefficient || transition_coefficient);
            if matches!(expr, Expression::Divide { .. }) && b.has_variables {
                return Err(Error::new(
                    "unsupported_transient",
                    "affine event division requires a constant denominator",
                ));
            }
            let scalar_product = matches!(expr, Expression::Multiply { .. })
                && (!a.has_variables || !b.has_variables);
            let mut result = if sampled_coefficient
                || scalar_product
                || matches!(expr, Expression::Add { .. } | Expression::Divide { .. })
            {
                affine(
                    &freeze_operators(&representative, &vec![1.0; program.operators.len()]),
                    program,
                    owner,
                )?
            } else {
                affine(&representative, program, owner)?
            };
            // Reuse these existing parsed rows: an already-zero factor is
            // affine on the legacy path and must not acquire a DC admission tax.
            let live = |v: &AffineState| {
                v.constant != 0.
                    || v.nodes
                        .iter()
                        .chain(&v.states)
                        .chain(&v.operators)
                        .any(|&c| c != 0.)
            };
            let dc = ad
                || bd
                || sampled_coefficient
                    && transition_coefficient
                    && live(&a)
                    && live(&b)
                    && (!a.node_dependencies.is_empty() || !b.node_dependencies.is_empty());
            result.has_variables |= a.has_variables || b.has_variables;
            result.node_dependencies.extend(a.node_dependencies);
            result.node_dependencies.extend(b.node_dependencies);
            result.state_dependencies.extend(a.state_dependencies);
            result.state_dependencies.extend(b.state_dependencies);
            result.operator_dependencies.extend(a.operator_dependencies);
            result.operator_dependencies.extend(b.operator_dependencies);
            Ok((result, dc))
        }
        _ => affine(expr, program, owner).map(|row| (row, false)),
    }
}

// Operator samples are fixed during the same-time voltage/state solve. Only
// contribution coefficients use this binding; event RHS affinity stays strict.
fn freeze_operators(expr: &Expression, values: &[f64]) -> Expression {
    match expr {
        Expression::Operator { operator } => Expression::Affine {
            constant: values[*operator],
            terms: Vec::new(),
        },
        Expression::Add { left, right } => Expression::Add {
            left: Box::new(freeze_operators(left, values)),
            right: Box::new(freeze_operators(right, values)),
        },
        Expression::Multiply { left, right } => Expression::Multiply {
            left: Box::new(freeze_operators(left, values)),
            right: Box::new(freeze_operators(right, values)),
        },
        Expression::Divide { left, right } => Expression::Divide {
            left: Box::new(freeze_operators(left, values)),
            right: Box::new(freeze_operators(right, values)),
        },
        _ => expr.clone(),
    }
}

fn representative(expr: &Expression) -> Expression {
    match expr {
        Expression::Select { then_value, .. } => representative(then_value),
        Expression::Add { left, right } => Expression::Add {
            left: Box::new(representative(left)),
            right: Box::new(representative(right)),
        },
        Expression::Multiply { left, right } => Expression::Multiply {
            left: Box::new(representative(left)),
            right: Box::new(representative(right)),
        },
        Expression::Divide { left, right } => Expression::Divide {
            left: Box::new(representative(left)),
            right: Box::new(representative(right)),
        },
        _ => expr.clone(),
    }
}

pub(crate) fn check_state(value: f64, kind: &StateKind) -> Result<(), Error> {
    if !value.is_finite() {
        return Err(Error::new("nonfinite_arithmetic", "nonfinite state value"));
    }
    if *kind == StateKind::Integer
        && (value.fract() != 0.0 || !(-2147483648.0..=2147483647.0).contains(&value))
    {
        return Err(Error::new(
            "state_range",
            "integer state must remain an exact signed 32-bit integer",
        ));
    }
    Ok(())
}

pub(crate) struct TriggerLeaf {
    pub(crate) event: usize,
    pub(crate) index: usize,
    pub(crate) trigger: EventTrigger,
}

pub(crate) struct EventModel {
    pub(crate) analytic_request: Option<std::sync::Arc<crate::analytic_request::Request>>,
    pub(crate) history_admission: Option<std::sync::Arc<crate::history_admission::Admission>>,
    pub(crate) typed_transition_targets: BTreeSet<usize>,
    pub(crate) source_copy_items: usize,
    pub(crate) mixed_cold_work: std::sync::OnceLock<crate::transition_source_plan::Work>,
    /// Work-slot limit for any ledger this model must create lazily (the cold
    /// owner); taken from the request trajectory, the default without one.
    pub(crate) proof_work_limit: u64,
    pub(crate) mixed_cold_context:
        std::sync::OnceLock<std::sync::Arc<crate::transition_source_plan::ProofContext>>,
    pub(crate) source_context: Option<std::sync::Arc<crate::transition_source_plan::ProofContext>>,
    pub(crate) program: Program,
    pub(crate) independent_physical:
        std::sync::OnceLock<Option<std::sync::Arc<crate::procedure_affine::Projection>>>,
    pub(crate) floor_source: Option<std::sync::Arc<crate::event_floor::Request>>,
    pub(crate) forcing: Option<std::sync::Arc<crate::forcing_graph::Graph>>,
    pub(crate) dc_projection: Option<std::sync::Arc<crate::dc_projection::DcProjection>>,
    rhs: Vec<AffineState>,
    pub(crate) guards: Vec<Option<AffineState>>,
    pub(crate) dynamic_guards: Vec<bool>,
    pub(crate) relocalized_guards: Vec<bool>,
    pub(crate) guard_operators: Vec<BTreeSet<usize>>,
    pub(crate) triggers: Vec<TriggerLeaf>,
    actions: Vec<Vec<(usize, AffineState)>>,
    pub(crate) action_expressions: Vec<Vec<Expression>>,
    pub(crate) numeric_actions: Vec<Vec<bool>>,
    pub(crate) causal_numeric: Vec<bool>,
    pub(crate) conditions: Conditions,
    pub(crate) passive_conditions: Conditions,
    pub(crate) passive_events: Vec<bool>,
    pub(crate) driven: Vec<String>,
    pub(crate) tolerances: Tolerances,
    // Bounded one-batch cache; stores coefficients, never accepted/trial state.
    certificate: RefCell<Option<(Selection, Bounds)>>,
    initial_values: Vec<f64>,
}

impl EventModel {
    pub(crate) fn new(
        program: Program,
        driven: Vec<String>,
        tolerances: Tolerances,
    ) -> Result<Self, Error> {
        Self::new_with_trajectory(program, driven, tolerances, None)
    }
    pub(crate) fn new_with_trajectory(
        program: Program,
        driven: Vec<String>,
        tolerances: Tolerances,
        trajectory: Option<&crate::pwl::Trajectory>,
    ) -> Result<Self, Error> {
        Self::build_with_context(program, driven, tolerances, trajectory, None, true)
    }
    /// A composed caller constructs one original-request owner before Stage0.
    /// Held target admission borrows it; retries and Operators clones keep it.
    #[allow(dead_code)] // Composed Stage0 request entry; independently tested below.
    pub(crate) fn new_with_context(
        program: Program,
        driven: Vec<String>,
        tolerances: Tolerances,
        trajectory: Option<&crate::pwl::Trajectory>,
        provided: Option<std::sync::Arc<crate::transition_source_plan::ProofContext>>,
    ) -> Result<Self, Error> {
        Self::build_with_context(program, driven, tolerances, trajectory, provided, false)
    }
    fn build_with_context(
        program: Program,
        driven: Vec<String>,
        tolerances: Tolerances,
        trajectory: Option<&crate::pwl::Trajectory>,
        provided: Option<std::sync::Arc<crate::transition_source_plan::ProofContext>>,
        request_entry: bool,
    ) -> Result<Self, Error> {
        Self::build_with_execution(
            program,
            driven,
            tolerances,
            trajectory,
            provided,
            request_entry,
            None,
            None,
        )
    }
    pub(crate) fn new_with_procedure_work(
        program: Program,
        driven: Vec<String>,
        tolerances: Tolerances,
        work: crate::transition_source_plan::Work,
    ) -> Result<Self, Error> {
        Self::build_with_execution(
            program,
            driven,
            tolerances,
            None,
            None,
            true,
            None,
            Some(work),
        )
    }
    pub(crate) fn new_with_forcing(
        program: Program,
        driven: Vec<String>,
        tolerances: Tolerances,
        trajectory: &crate::pwl::Trajectory,
        execution: crate::forcing_graph::PreparedExecution,
    ) -> Result<Self, Error> {
        Self::build_with_execution(
            program,
            driven,
            tolerances,
            Some(trajectory),
            None,
            false,
            Some(execution),
            None,
        )
    }
    #[allow(clippy::too_many_arguments)]
    fn build_with_execution(
        program: Program,
        driven: Vec<String>,
        tolerances: Tolerances,
        trajectory: Option<&crate::pwl::Trajectory>,
        provided: Option<std::sync::Arc<crate::transition_source_plan::ProofContext>>,
        request_entry: bool,
        execution: Option<crate::forcing_graph::PreparedExecution>,
        procedure_work: Option<crate::transition_source_plan::Work>,
    ) -> Result<Self, Error> {
        let composed = execution.is_some();
        let composed_history = execution
            .as_ref()
            .is_some_and(|e| e.requires_composed_history());
        let mut provided = match execution {
            Some(execution) => Some(execution.context(
                &program,
                trajectory.ok_or_else(|| {
                    Error::new(
                        "invalid_ir",
                        "forcing execution requires physical trajectory",
                    )
                })?,
                &driven,
            )?),
            None => provided,
        };
        let mut admission =
            crate::event_control::admit(&program, provided.as_ref().map(|s| s.borrow_work()))?;
        let held_ramp = crate::dc_projection::DcProjection::held_ramp_candidate(&program);
        // The mandatory structural phase supplies only an old-refusal shape.
        // Establish the original request owner here, before new role traversal,
        // source qualification, relation expansion or any candidate copy.
        if (admission.history_candidate() || held_ramp) && provided.is_none() {
            if !request_entry {
                return Err(Error::new(
                    "invalid_ir",
                    "history consumer requires its original prepared source context",
                ));
            }
            let context = crate::transition_source_plan::ProofContext::new_held(
                &program,
                trajectory.ok_or_else(|| {
                    Error::new(
                        "unsupported_condition",
                        "history consumer requires original physical trajectory",
                    )
                })?,
                &driven,
                admission.copy_items,
            )?;
            admission = crate::event_control::admit(&program, Some(context.borrow_work()))?;
            provided = Some(context);
        }
        if trajectory.is_none() && admission.source_floor() {
            return Err(Error::new(
                "unsupported_floor",
                "source floor requires the original physical trajectory",
            ));
        }
        if !request_entry
            && provided.is_none()
            && (!admission.targets.is_empty() || admission.source_floor())
        {
            return Err(Error::new(
                "invalid_ir",
                "event source helper requires the original provided source context",
            ));
        }
        let floor_source = if let Some(t) = trajectory {
            crate::event_floor::Request::new(&admission, t, &driven, provided.clone())?
        } else {
            None
        };
        if floor_source.is_none() && !composed {
            if let Some(source) = &provided {
                crate::event_floor::check_provided_binding(
                    source,
                    &program,
                    trajectory.ok_or_else(|| {
                        Error::new(
                            "unsupported_held_integer_target",
                            "typed target requires its original trajectory",
                        )
                    })?,
                    &driven,
                )?;
            }
        }
        let shared = provided.or_else(|| floor_source.as_ref().map(|r| r.source.clone()));
        let source_context = if let Some(context) = shared {
            Some(context)
        } else if admission.targets.is_empty() {
            None
        } else {
            Some(crate::transition_source_plan::ProofContext::new_held(
                &program,
                trajectory.ok_or_else(|| {
                    Error::new(
                        "unsupported_held_integer_target",
                        "typed target requires a transient point frame",
                    )
                })?,
                &driven,
                admission.copy_items,
            )?)
        };
        let initial_values = program
            .states
            .iter()
            .map(|s| s.initial.constant())
            .collect::<Result<Vec<_>, _>>()?;
        let mut identities = BTreeSet::new();
        for state in &program.states {
            if state.instance.is_empty()
                || state.name.is_empty()
                || state.instance.contains(':')
                || state.name.contains(':')
                || !identities.insert((&state.instance, &state.name))
                || !program
                    .contributions
                    .iter()
                    .any(|c| c.branch.instance == state.instance)
                    && !program
                        .events
                        .iter()
                        .any(|e| e.origin.instance == state.instance)
            {
                return Err(Error::new(
                    "invalid_ir",
                    "invalid or duplicate state identity",
                ));
            }
            check_state(state.initial.constant()?, &state.kind)?;
        }
        if composed && admission.history_candidate() {
            return Err(Error::new(
                "unsupported_forcing_scope",
                "forcing ordinary contribution predicates require a composed history admission",
            ));
        }
        let dc_projection = if held_ramp {
            if composed {
                return Err(Error::new(
                    "unsupported_forcing_scope",
                    "DC held ramps require the original independent physical request",
                ));
            }
            Some(crate::dc_projection::DcProjection::with_source(
                &program,
                source_context
                    .as_ref()
                    .ok_or_else(|| {
                        Error::new(
                            "invalid_ir",
                            "DC held ramp requires its prepared source owner",
                        )
                    })?
                    .clone(),
            )?)
        } else {
            None
        };
        let proof_work_limit = trajectory.map_or(crate::ir::DEFAULT_PROOF_WORK_LIMIT, |t| {
            t.proof_work_limit()
        });
        let real_work = if program.procedures.is_empty() {
            None
        } else {
            Some(procedure_work.unwrap_or_else(|| {
                source_context
                    .as_ref()
                    .map(|c| c.borrow_work().clone())
                    .or_else(|| trajectory.and_then(|t| t.procedure_work().cloned()))
                    .unwrap_or_else(|| {
                        crate::transition_source_plan::Work::for_limit(proof_work_limit)
                    })
            }))
        };
        let prepared_procedures = real_work
            .as_ref()
            .map(|w| crate::procedure::prepare(&program, w))
            .transpose()?;
        let executes = prepared_procedures
            .as_ref()
            .is_some_and(|p| p.requires_execution);
        let history_admission = if admission.history_candidate() {
            Some(crate::history_admission::Admission::new(
                &program,
                &driven,
                source_context
                    .as_ref()
                    .ok_or_else(|| Error::new("invalid_ir", "missing prepared history owner"))?
                    .clone(),
            )?)
        } else {
            let legacy_selection = (|| {
                if executes {
                    return Ok::<_, Error>(());
                }
                for c in &program.contributions {
                    let expression = dc_projection
                        .as_ref()
                        .map(|projection| projection.view(&c.rhs))
                        .transpose()?
                        .unwrap_or(&c.rhs);
                    crate::continuous::validate_selection(
                        expression,
                        &program,
                        &driven,
                        &c.origin.instance,
                    )
                    .or_else(|error| {
                        if error.kind == "unsupported_transient"
                            && crate::analog::has_select(expression)
                        {
                            crate::continuous::validate_integral_input(
                                expression,
                                &program,
                                &c.origin.instance,
                            )?;
                            crate::causal_voltage::history_selection(expression, &program, &driven)
                        } else {
                            Err(error)
                        }
                    })?;
                }
                Ok::<_, Error>(())
            })();
            legacy_selection?;
            None
        };
        let source_bindings = if executes {
            Some(crate::procedure::dependency_sources(
                &program,
                real_work.as_ref().expect("procedure owner"),
            )?)
        } else {
            None
        };
        let shaped = program
            .contributions
            .iter()
            .map(|c| {
                let expression = dc_projection
                    .as_ref()
                    .map(|projection| projection.view(&c.rhs))
                    .transpose()?
                    .unwrap_or(&c.rhs);
                if executes {
                    crate::procedure::source_dependencies(
                        expression,
                        &program,
                        source_bindings.as_ref().expect("source index"),
                        real_work.as_ref().expect("procedure owner"),
                    )
                    .map(|row| (row, false))
                } else {
                    contribution_shape(expression, &program, &c.origin.instance)
                }
            })
            .collect::<Result<Vec<_>, _>>()?;
        let dc_supply = shaped.iter().any(|(_, dc)| *dc);
        let rhs = shaped.into_iter().map(|(row, _)| row).collect::<Vec<_>>();
        let passive_events = crate::passive_events::classify(&program)?;
        let mut guards = Vec::new();
        let mut dynamic_guards = Vec::new();
        let mut triggers = Vec::new();
        fn validate_displays(
            body: &[crate::ir::Statement],
            program: &Program,
            owner: &str,
            numeric: bool,
            work: Option<&crate::transition_source_plan::Work>,
        ) -> Result<(), Error> {
            for statement in body {
                match statement {
                    crate::ir::Statement::Display {
                        format,
                        args,
                        origin,
                    } => {
                        if origin.instance != owner
                            || origin.source.is_empty()
                            || origin.line == 0
                            || origin.column == 0
                        {
                            return Err(Error::new("invalid_ir", "invalid display origin"));
                        }
                        crate::display::validate(format, args.len())?;
                        for argument in args {
                            crate::display::validate_expression(argument, program, owner)?;
                            if !numeric
                                && crate::event_numeric::contains_legacy_math(argument)
                                && !crate::event_floor::display_operand(argument, work)?
                            {
                                return Err(Error::new(
                                    "unsupported_transient",
                                    "pure event mathematics requires an isolated observer",
                                ));
                            }
                        }
                    }
                    crate::ir::Statement::Loop {
                        initialize,
                        body,
                        update,
                        ..
                    } => {
                        validate_displays(initialize, program, owner, numeric, work)?;
                        validate_displays(body, program, owner, numeric, work)?;
                        validate_displays(update, program, owner, numeric, work)?;
                    }
                    crate::ir::Statement::If {
                        then_body,
                        else_body,
                        ..
                    } => {
                        validate_displays(then_body, program, owner, numeric, work)?;
                        validate_displays(else_body, program, owner, numeric, work)?;
                    }
                    crate::ir::Statement::ArrayWrite {
                        states,
                        index,
                        rhs,
                        first,
                        last,
                        origin,
                    } => {
                        if !numeric {
                            return Err(Error::new(
                                "unsupported_transient",
                                "array writes require an isolated observer event",
                            ));
                        }
                        crate::event_numeric::validate_array(
                            states, index, *first, *last, origin, program, owner,
                        )?;
                        crate::event_numeric::validate(rhs, program, owner)?;
                    }
                    crate::ir::Statement::Assign(_) => {}
                }
            }
            Ok(())
        }
        let original_role_work = history_admission
            .as_ref()
            .map(|token| token.context.borrow_work())
            .or_else(|| floor_source.as_ref().map(|r| r.work()))
            .or_else(|| {
                if composed_history {
                    source_context.as_ref().map(|c| c.borrow_work())
                } else {
                    None
                }
            })
            .or_else(|| trajectory.and_then(|t| t.analytic_work()));
        for (index, event) in program.events.iter().enumerate() {
            validate_displays(
                &event.body,
                &program,
                &event.origin.instance,
                passive_events[index],
                // A procedure-backed display argument is a Plan effect root:
                // its qualification walk runs on the procedure owner (NF-11).
                if event.procedure_id.is_some() {
                    original_role_work.or(real_work.as_ref())
                } else {
                    original_role_work
                },
            )?;
        }
        let mut actions = Vec::new();
        let mut action_expressions = Vec::new();
        let mut numeric_actions = Vec::new();
        let causal_numeric = crate::causal_event::classify(
            &program,
            &passive_events,
            &driven,
            &admission,
            original_role_work.or(real_work.as_ref()),
            source_bindings.as_ref(),
        )?;
        let general_events: Vec<_> = passive_events
            .iter()
            .zip(&causal_numeric)
            .map(|(a, b)| *a || *b)
            .collect();
        for (index, event) in program.events.iter().enumerate() {
            if program.procedures.is_empty()
                && (event.procedure_id.is_some() || event.expanded_statement_ordinal.is_some())
            {
                return Err(Error::new(
                    "invalid_ir",
                    "event metadata names an undeclared procedure",
                ));
            }
            if event.origin.instance.is_empty()
                || event.origin.source.is_empty()
                || event.origin.line == 0
                || event.origin.column == 0
            {
                return Err(Error::new("invalid_ir", "invalid event origin"));
            }
            for (leaf, trigger) in event.trigger.leaves()?.into_iter().enumerate() {
                let guard = match trigger {
                    EventTrigger::Cross {
                        guard,
                        direction,
                        time_tolerance,
                        expression_tolerance,
                    } => {
                        if !(-1..=1).contains(direction)
                            || !time_tolerance.is_finite()
                            || *time_tolerance <= 0.0
                            || !expression_tolerance.is_finite()
                            || *expression_tolerance <= 0.0
                        {
                            return Err(Error::new("invalid_ir", "invalid cross settings"));
                        }
                        crate::guard_trajectory::dependencies(
                            guard,
                            &program,
                            &event.origin.instance,
                        )?;
                        let bound = affine(guard, &program, &event.origin.instance).ok();
                        dynamic_guards.push(bound.is_none());
                        bound
                    }
                    EventTrigger::Timer {
                        start,
                        period,
                        time_tolerance,
                        ..
                    } => {
                        if !start.is_finite()
                            || *start < 0.0
                            || !period.is_finite()
                            || !time_tolerance.is_finite()
                            || *time_tolerance < 0.0
                        {
                            return Err(Error::new("invalid_ir", "invalid timer settings"));
                        }
                        dynamic_guards.push(false);
                        None
                    }
                    EventTrigger::HeldTimer {
                        start,
                        period,
                        enabled,
                        time_tolerance,
                    } => {
                        if !time_tolerance.is_finite() || *time_tolerance <= 0. {
                            return Err(Error::new("invalid_ir", "invalid timer tolerance"));
                        }
                        for expression in [start, period, enabled] {
                            let value = if executes {
                                crate::procedure::source_dependencies(
                                    expression,
                                    &program,
                                    source_bindings.as_ref().expect("source index"),
                                    real_work.as_ref().expect("procedure owner"),
                                )?
                            } else {
                                affine(expression, &program, &event.origin.instance)?
                            };
                            if !value.node_dependencies.is_empty()
                                || !value.operator_dependencies.is_empty()
                            {
                                return Err(Error::new("unsupported_timer", "dynamic timer parameters require held-state affine expressions"));
                            }
                        }
                        dynamic_guards.push(false);
                        None
                    }
                    EventTrigger::InitialStep {} | EventTrigger::FinalStep {} => {
                        dynamic_guards.push(false);
                        None
                    }
                    EventTrigger::Or { .. } => unreachable!("validated leaves are not OR groups"),
                };
                guards.push(guard);
                triggers.push(TriggerLeaf {
                    event: index,
                    index: leaf,
                    trigger: trigger.clone(),
                });
            }
            let mut body = Vec::new();
            let mut expressions = Vec::new();
            let mut numeric = Vec::new();
            for assignment in event.assignments() {
                let state = program.states.get(assignment.state).ok_or_else(|| {
                    Error::new("invalid_ir", "assignment state index out of range")
                })?;
                if state.instance != event.origin.instance {
                    return Err(Error::new(
                        "unsupported_cross",
                        "event assignment must write a state in its instance",
                    ));
                }
                let ordinary = affine(&assignment.rhs, &program, &event.origin.instance);
                let is_numeric = (executes || general_events[index]) && ordinary.is_err();
                let value = if executes || is_numeric {
                    if executes {
                        crate::procedure::source_dependencies(
                            &assignment.rhs,
                            &program,
                            source_bindings.as_ref().expect("source bindings"),
                            real_work.as_ref().expect("source owner"),
                        )?
                    } else {
                        crate::event_numeric::dependencies(
                            &assignment.rhs,
                            &program,
                            &event.origin.instance,
                        )?
                    }
                } else {
                    ordinary?
                };
                expressions.push(assignment.rhs.clone());
                numeric.push(is_numeric);
                if !(executes
                    || value.operator_dependencies.is_empty()
                    || (event.procedure_id.is_some()
                        && value.operator_dependencies.iter().all(|&i| {
                            matches!(
                                program.operators.get(i),
                                Some(
                                    crate::ir::OperatorSpec::Math { .. }
                                        | crate::ir::OperatorSpec::Sin { .. }
                                )
                            )
                        })))
                {
                    return Err(Error::new(
                        "unsupported_transient",
                        "operator calls are only allowed in contributions",
                    ));
                }
                if !executes
                    && state.kind == StateKind::Integer
                    && general_events[index]
                    && !crate::event_numeric::integral(&assignment.rhs, &program)
                {
                    return Err(Error::new(
                        "unsupported_transient",
                        "integer assignments require integral state arithmetic",
                    ));
                }
                if !executes
                    && state.kind == StateKind::Integer
                    && !general_events[index]
                    && (value.constant.fract() != 0.0
                        || value.nodes.iter().any(|v| *v != 0.0)
                        || value.states.iter().zip(&program.states).any(|(v, s)| {
                            v.fract() != 0.0 || (*v != 0.0 && s.kind != StateKind::Integer)
                        }))
                {
                    return Err(Error::new(
                        "unsupported_transient",
                        "integer assignments require integral state arithmetic",
                    ));
                }
                body.push((assignment.state, value));
            }
            actions.push(body);
            action_expressions.push(expressions);
            numeric_actions.push(numeric);
        }
        let mut conditions = Conditions::new_with_numeric(&program, &general_events)?;
        if let Some(p) = &prepared_procedures {
            conditions.install_procedures(p)?;
        }
        conditions.restrict_events(&passive_events.iter().map(|p| !p).collect::<Vec<_>>());
        let mut passive_conditions = Conditions::new_with_numeric(&program, &general_events)?;
        if let Some(p) = &prepared_procedures {
            passive_conditions.install_procedures(p)?;
        }
        passive_conditions.restrict_events(&passive_events);
        let (projected, node_inputs) =
            crate::event_accuracy::GuardBounds::passive_program(&program);
        passive_conditions.prepare(&projected, &node_inputs)?;
        let typed_transition_targets = admission.targets;
        let mut model = Self {
            independent_physical: std::sync::OnceLock::new(),
            analytic_request: None,
            history_admission,
            typed_transition_targets,
            source_copy_items: admission.copy_items,
            mixed_cold_work: real_work
                .map_or_else(std::sync::OnceLock::new, std::sync::OnceLock::from),
            proof_work_limit,
            mixed_cold_context: std::sync::OnceLock::new(),
            source_context,
            conditions,
            passive_conditions,
            passive_events,
            program,
            dc_projection,
            floor_source,
            forcing: None,
            rhs,
            guards,
            dynamic_guards,
            relocalized_guards: Vec::new(),
            guard_operators: Vec::new(),
            triggers,
            actions,
            action_expressions,
            numeric_actions,
            causal_numeric,
            driven,
            tolerances,
            certificate: RefCell::new(None),
            initial_values,
        };
        model.check_guard_dependencies()?;
        if composed_history
            && (model.dynamic_guards.iter().any(|&v| v)
                || model.relocalized_guards.iter().any(|&v| v)
                || model.guard_operators.iter().any(|v| !v.is_empty()))
        {
            return Err(Error::new(
                "unsupported_forcing_scope",
                "composed forcing requires the original independent physical event calendar",
            ));
        }
        if model.history_admission.is_some()
            && (model.floor_source.is_some()
                || !model.typed_transition_targets.is_empty()
                || model.dynamic_guards.iter().any(|&x| x)
                || model.guard_operators.iter().any(|ops| !ops.is_empty()))
        {
            return Err(Error::new(
                "unsupported_condition",
                "ordinary history consumer requires the independent held-Transition event calendar",
            ));
        }
        // Reuse dependency metadata already audited above. Original Transition
        // products plus an internal history cross cannot use the legacy affine
        // network map; direct/implicit supported callers incur no DC proof.
        if let Some(t) = trajectory {
            if model.dc_projection.is_none()
                && model.guard_operators.iter().any(|ops| !ops.is_empty())
                && model
                    .program
                    .operators
                    .iter()
                    .all(|o| matches!(o, crate::ir::OperatorSpec::Transition { .. }))
                && dc_supply
            {
                model.dc_projection = Some(crate::dc_projection::DcProjection::new(
                    &model.program,
                    t,
                    &model.driven,
                )?);
            }
        }
        model.conditions.prepare_with_dc(
            &model.program,
            &model.driven,
            model.dc_projection.as_deref(),
        )?;
        Ok(model)
    }

    /// Same acceptance certificate, retaining its already-computed node intervals.
    pub(crate) fn certify_observation(
        &self,
        selection: &Selection,
        inputs: &[I],
        before: &[I],
        operators: &[I],
        voltages: &[f64],
        states: &[f64],
    ) -> Result<(Vec<I>, Vec<I>), Error> {
        self.certify_observation_at_roots_with_proofs(
            selection,
            &[],
            inputs,
            before,
            operators,
            voltages,
            states,
            None,
        )
    }

    #[allow(clippy::too_many_arguments)] // Root, state and voltage certificates are distinct inputs.
    #[cfg(test)]
    pub(crate) fn certify_observation_at_roots(
        &self,
        selection: &Selection,
        fired: &[usize],
        inputs: &[I],
        before: &[I],
        operators: &[I],
        voltages: &[f64],
        states: &[f64],
    ) -> Result<(Vec<I>, Vec<I>), Error> {
        self.certify_observation_at_roots_with_proofs(
            selection, fired, inputs, before, operators, voltages, states, None,
        )
    }
    #[allow(clippy::too_many_arguments)]
    pub(crate) fn certify_observation_at_roots_with_proofs(
        &self,
        selection: &Selection,
        fired: &[usize],
        inputs: &[I],
        before: &[I],
        operators: &[I],
        voltages: &[f64],
        states: &[f64],
        proofs: Option<&crate::event_value_proof::Context<'_>>,
    ) -> Result<(Vec<I>, Vec<I>), Error> {
        self.certify_observation_at_roots_with_lineage(
            selection, fired, inputs, before, operators, voltages, states, proofs, None,
        )
    }
    #[allow(clippy::too_many_arguments)] // Preserve the independent root, state and voltage inputs.
    pub(crate) fn certify_observation_at_roots_with_lineage(
        &self,
        selection: &Selection,
        fired: &[usize],
        inputs: &[I],
        before: &[I],
        operators: &[I],
        voltages: &[f64],
        states: &[f64],
        proofs: Option<&crate::event_value_proof::Context<'_>>,
        lineage: Option<&crate::transient::point_lineage::PointLineage<'_>>,
    ) -> Result<(Vec<I>, Vec<I>), Error> {
        self.certify_observation_with_context(
            selection, fired, inputs, before, operators, voltages, states, proofs, lineage, None,
        )
    }
    #[allow(clippy::too_many_arguments)]
    pub(crate) fn certify_observation_with_held_ramp_proof(
        &self,
        selection: &Selection,
        inputs: &[I],
        before: &[I],
        operators: &[I],
        voltages: &[f64],
        states: &[f64],
        observation: &crate::dc_projection::HeldRampObservationProof<'_>,
    ) -> Result<(Vec<I>, Vec<I>), Error> {
        self.certify_observation_with_context(
            selection,
            &[],
            inputs,
            before,
            operators,
            voltages,
            states,
            None,
            None,
            Some(observation),
        )
    }
    #[allow(clippy::too_many_arguments)]
    pub(crate) fn certify_observation_with_context(
        &self,
        selection: &Selection,
        fired: &[usize],
        inputs: &[I],
        before: &[I],
        operators: &[I],
        voltages: &[f64],
        states: &[f64],
        proofs: Option<&crate::event_value_proof::Context<'_>>,
        lineage: Option<&crate::transient::point_lineage::PointLineage<'_>>,
        observation: Option<&crate::dc_projection::HeldRampObservationProof<'_>>,
    ) -> Result<(Vec<I>, Vec<I>), Error> {
        let _timing = crate::diagnostics::span("event.certificate");
        // The occurrence Plan already owns every source-position predicate.
        // Running legacy Select reduction first tries to read RealLocal values
        // without that frame and can also substitute a later ordinary value.
        if selection.plan.is_some() {
            return crate::causal_event::certificate(
                self,
                selection,
                &self.program,
                fired,
                inputs,
                before,
                operators,
                voltages,
                states,
                true,
                proofs,
            )?
            .ok_or_else(|| Error::new("invalid_ir", "procedure observation certificate missing"));
        }
        let nominal_bounds: Vec<_> = if observation.is_none() {
            states.iter().copied().map(I::point).collect()
        } else {
            Vec::new()
        };
        let selected = self.selected_program_with_observation_proof(
            observation.map_or(nominal_bounds.as_slice(), |proof| proof.state_bounds()),
            inputs,
            fired,
            operators,
            lineage,
            observation,
        )?;
        if let Some(result) = crate::causal_event::certificate(
            self, selection, &selected, fired, inputs, before, operators, voltages, states, true,
            proofs,
        )? {
            return Ok(result);
        }
        let resolved = selected
            .contributions
            .iter()
            .zip(&self.program.contributions)
            .any(|(a, b)| a.rhs != b.rhs);
        // Linear operator outputs remain live forcing. A sampled coefficient
        // may reuse its map only with the same full interval endpoint bits.
        let cached = match self.certificate.borrow().as_ref() {
            Some((path, bounds)) => {
                path.same_path(selection, crate::real_expression::work(self))?
                    && bounds.matches_operator_bindings(operators)
            }
            None => false,
        };
        if resolved {
            let bounds = Bounds::for_program_with_operators(self, selection, &selected, operators)?;
            let result =
                bounds.check_observation(self, inputs, before, operators, voltages, states)?;
            let replay = self.selected_program_with_observation_proof(
                &result.0,
                inputs,
                fired,
                operators,
                lineage,
                observation,
            )?;
            if replay
                .contributions
                .iter()
                .zip(&selected.contributions)
                .any(|(a, b)| a.rhs != b.rhs)
            {
                return Err(Error::new(
                    "event_condition",
                    "state enclosure changes contribution selection",
                ));
            }
            return Ok(result);
        }
        let mut cache = self.certificate.borrow_mut();
        if !cached {
            let bounds = if Bounds::sample_independent(self, selection)? {
                Bounds::new(self, selection)?
            } else {
                Bounds::for_program_with_operators(self, selection, &selected, operators)?
            };
            *cache = Some((
                selection.try_clone_path(crate::real_expression::work(self))?,
                bounds,
            ));
        } else {
            crate::diagnostics::counter("certificate_cache_hits", 1);
        }
        let result = cache
            .as_ref()
            .unwrap()
            .1
            .check_observation(self, inputs, before, operators, voltages, states)?;
        // Preserve the original operator-bearing path's enclosure replay.
        if !operators.is_empty() {
            let replay = self.selected_program_with_observation_proof(
                &result.0,
                inputs,
                fired,
                operators,
                lineage,
                observation,
            )?;
            if replay
                .contributions
                .iter()
                .zip(&selected.contributions)
                .any(|(a, b)| a.rhs != b.rhs)
            {
                return Err(Error::new(
                    "event_condition",
                    "state enclosure changes contribution selection",
                ));
            }
        }
        Ok(result)
    }

    #[allow(clippy::too_many_arguments)] // Root, state and voltage certificates are distinct inputs.
    #[cfg(test)]
    pub(crate) fn certify_event_states(
        &self,
        selection: &Selection,
        fired: &[usize],
        inputs: &[I],
        before: &[I],
        operators: &[I],
        voltages: &[f64],
        states: &[f64],
    ) -> Result<Vec<I>, Error> {
        self.certify_event_states_with_proofs(
            selection, fired, inputs, before, operators, voltages, states, None,
        )
    }
    #[allow(clippy::too_many_arguments)]
    pub(crate) fn certify_event_states_with_proofs(
        &self,
        selection: &Selection,
        fired: &[usize],
        inputs: &[I],
        before: &[I],
        operators: &[I],
        voltages: &[f64],
        states: &[f64],
        proofs: Option<&crate::event_value_proof::Context<'_>>,
    ) -> Result<Vec<I>, Error> {
        self.certify_event_states_with_lineage(
            selection, fired, inputs, before, operators, voltages, states, proofs, None,
        )
    }
    #[allow(clippy::too_many_arguments)] // Preserve the independent root, state and voltage inputs.
    pub(crate) fn certify_event_states_with_lineage(
        &self,
        selection: &Selection,
        fired: &[usize],
        inputs: &[I],
        before: &[I],
        operators: &[I],
        voltages: &[f64],
        states: &[f64],
        proofs: Option<&crate::event_value_proof::Context<'_>>,
        lineage: Option<&crate::transient::point_lineage::PointLineage<'_>>,
    ) -> Result<Vec<I>, Error> {
        self.certify_event_states_with_observation_proof(
            selection, fired, inputs, before, operators, voltages, states, proofs, lineage, None,
        )
    }
    #[allow(clippy::too_many_arguments)]
    pub(crate) fn certify_event_states_with_observation_proof(
        &self,
        selection: &Selection,
        fired: &[usize],
        inputs: &[I],
        before: &[I],
        operators: &[I],
        voltages: &[f64],
        states: &[f64],
        proofs: Option<&crate::event_value_proof::Context<'_>>,
        lineage: Option<&crate::transient::point_lineage::PointLineage<'_>>,
        observation: Option<&crate::dc_projection::HeldRampObservationProof<'_>>,
    ) -> Result<Vec<I>, Error> {
        let _timing = crate::diagnostics::span("event.state_certificate");

        let nominal: Vec<_> = states.iter().copied().map(I::point).collect();
        let selected = self.selected_program_with_observation_proof(
            observation.map_or(nominal.as_slice(), |proof| proof.state_bounds()),
            inputs,
            fired,
            operators,
            lineage,
            observation,
        )?;
        if let Some(result) = crate::causal_event::certificate(
            self, selection, &selected, fired, inputs, before, operators, voltages, states, false,
            proofs,
        )? {
            return Ok(result.0);
        }
        let resolved = selected
            .contributions
            .iter()
            .zip(&self.program.contributions)
            .any(|(a, b)| a.rhs != b.rhs);
        // Linear operator outputs remain live forcing. A sampled coefficient
        // may reuse its map only with the same full interval endpoint bits.
        let cached = match self.certificate.borrow().as_ref() {
            Some((path, bounds)) => {
                path.same_path(selection, crate::real_expression::work(self))?
                    && bounds.matches_operator_bindings(operators)
            }
            None => false,
        };
        if resolved {
            let bounds = Bounds::for_program_with_operators(self, selection, &selected, operators)?;
            let result = bounds.check_states(self, inputs, before, operators, voltages, states)?;
            let replay = self.selected_program_with_observation_proof(
                &result,
                inputs,
                fired,
                operators,
                lineage,
                observation,
            )?;
            if replay
                .contributions
                .iter()
                .zip(&selected.contributions)
                .any(|(a, b)| a.rhs != b.rhs)
            {
                return Err(Error::new(
                    "event_condition",
                    "state enclosure changes contribution selection",
                ));
            }
            return Ok(result);
        }
        let mut cache = self.certificate.borrow_mut();
        if !cached {
            let bounds = if Bounds::sample_independent(self, selection)? {
                Bounds::new(self, selection)?
            } else {
                Bounds::for_program_with_operators(self, selection, &selected, operators)?
            };
            *cache = Some((
                selection.try_clone_path(crate::real_expression::work(self))?,
                bounds,
            ));
        } else {
            crate::diagnostics::counter("certificate_cache_hits", 1);
        }
        let result = cache
            .as_ref()
            .unwrap()
            .1
            .check_states(self, inputs, before, operators, voltages, states)?;
        if !operators.is_empty() {
            let replay = self.selected_program_with_observation_proof(
                &result,
                inputs,
                fired,
                operators,
                lineage,
                observation,
            )?;
            if replay
                .contributions
                .iter()
                .zip(&selected.contributions)
                .any(|(a, b)| a.rhs != b.rhs)
            {
                return Err(Error::new(
                    "event_condition",
                    "state enclosure changes contribution selection",
                ));
            }
        }
        Ok(result)
    }

    pub(crate) fn assigned(&self, selection: &Selection) -> Vec<usize> {
        selection
            .actions
            .iter()
            .flat_map(|(event, indices)| indices.iter().map(|&index| self.actions[*event][index].0))
            .collect()
    }

    pub(crate) fn check_selection_writers(&self, selection: &Selection) -> Result<(), Error> {
        fn reads_other_writer(
            expr: &Expression,
            event: usize,
            writers: &[Option<usize>],
            selection: &Selection,
        ) -> bool {
            match expr {
                Expression::RealBinary { left, right, .. } => {
                    reads_other_writer(left, event, writers, selection)
                        || reads_other_writer(right, event, writers, selection)
                }
                Expression::RealBoundary { value, .. } => {
                    reads_other_writer(value, event, writers, selection)
                }
                Expression::RealCall { .. } | Expression::UnsupportedSystemCall { .. } => {
                    let mut conflict = false;
                    let _ = crate::procedure::call_children(expr, &mut |e| {
                        conflict |= reads_other_writer(e, event, writers, selection);
                        Ok(())
                    });
                    conflict
                }
                Expression::RealLocal { .. } => false,
                Expression::Forcing { value, .. } => {
                    reads_other_writer(value, event, writers, selection)
                }
                Expression::CheckedIndex { index, .. }
                | Expression::IntegerRound { value: index, .. }
                | Expression::CheckedInteger { value: index, .. } => {
                    reads_other_writer(index, event, writers, selection)
                }
                Expression::ArrayRead { states, index, .. } => {
                    states.iter().any(|&state| {
                        writers[state].is_some_and(|w| {
                            w != event && !crate::procedure_frames::ordered(selection, w, event)
                        })
                    }) || reads_other_writer(index, event, writers, selection)
                }
                Expression::IntegerPrimitive { args, .. } => {
                    let mut refs = Vec::new();
                    crate::integer_primitive::states(args, &mut refs);
                    refs.iter().any(|&state| {
                        writers[state].is_some_and(|w| {
                            w != event && !crate::procedure_frames::ordered(selection, w, event)
                        })
                    })
                }
                Expression::EventMath { args, .. } => args
                    .iter()
                    .any(|e| reads_other_writer(e, event, writers, selection)),
                Expression::State { state } => writers[*state].is_some_and(|writer| {
                    writer != event && !crate::procedure_frames::ordered(selection, writer, event)
                }),
                Expression::Add { left, right }
                | Expression::Multiply { left, right }
                | Expression::Divide { left, right } => {
                    reads_other_writer(left, event, writers, selection)
                        || reads_other_writer(right, event, writers, selection)
                }
                Expression::Power { base, .. } => {
                    reads_other_writer(base, event, writers, selection)
                }
                Expression::Select {
                    left,
                    right,
                    then_value,
                    else_value,
                    ..
                } => [left, right, then_value, else_value]
                    .iter()
                    .any(|expr| reads_other_writer(expr, event, writers, selection)),
                Expression::Affine { .. } | Expression::Operator { .. } => false,
            }
        }
        fn display_args<'a>(body: &'a [crate::ir::Statement], out: &mut Vec<&'a [Expression]>) {
            for statement in body {
                match statement {
                    crate::ir::Statement::Loop {
                        initialize,
                        body,
                        update,
                        ..
                    } => {
                        display_args(initialize, out);
                        display_args(body, out);
                        display_args(update, out);
                    }
                    crate::ir::Statement::Display { args, .. } => out.push(args),
                    crate::ir::Statement::If {
                        then_body,
                        else_body,
                        ..
                    } => {
                        display_args(then_body, out);
                        display_args(else_body, out);
                    }
                    _ => {}
                }
            }
        }
        let mut writers = vec![None; self.program.states.len()];
        for (event, indices) in &selection.actions {
            for &index in indices {
                let state = self.actions[*event][index].0;
                if writers[state].is_some_and(|writer| {
                    writer != *event && !crate::procedure_frames::ordered(selection, writer, *event)
                }) {
                    return Err(Error::new(
                        "event_conflict",
                        format!(
                            "simultaneous event blocks write state {}:{}",
                            self.program.states[state].instance, self.program.states[state].name
                        ),
                    ));
                }
                writers[state] = Some(*event);
            }
        }
        self.conditions
            .check_selection_readers(selection, &writers)?;
        self.passive_conditions
            .check_selection_readers(selection, &writers)?;
        for (event, indices) in &selection.actions {
            for &index in indices {
                let (_, rhs) = &self.actions[*event][index];
                if rhs.state_dependencies.iter().any(|&s| {
                    writers[s].is_some_and(|writer| {
                        writer != *event
                            && !crate::procedure_frames::ordered(selection, writer, *event)
                    })
                }) {
                    return Err(Error::new("unsupported_cross", "simultaneous event blocks cannot read state written by another selected block"));
                }
            }
        }
        for (event, steps) in &selection.ordered_steps {
            let mut displays = Vec::new();
            display_args(&self.program.events[*event].body, &mut displays);
            for step in steps {
                if let crate::event_conditions::SelectedStep::Display(index) = step {
                    if displays[*index]
                        .iter()
                        .any(|expr| reads_other_writer(expr, *event, &writers, selection))
                    {
                        return Err(Error::new("unsupported_cross", "simultaneous event blocks cannot read state written by another selected block"));
                    }
                }
            }
        }
        Ok(())
    }

    pub(crate) fn initial(&self) -> Vec<f64> {
        self.initial_values.clone()
    }

    pub(crate) fn circuit(&self, states: &[f64]) -> Result<Circuit, Error> {
        self.circuit_with(states, &vec![0.0; self.program.operators.len()])
    }

    pub(crate) fn circuit_with(&self, states: &[f64], operators: &[f64]) -> Result<Circuit, Error> {
        Circuit::new(
            self.bind(states, operators)?,
            &self.driven,
            self.tolerances.clone(),
        )
    }

    pub(crate) fn check_contribution_predicate_updates(
        &self,
        selection: &Selection,
        source: Option<SourcePredicateBinding<'_>>,
    ) -> Result<(), Error> {
        fn predicates(
            e: &Expression,
            program: &Program,
            driven: &[String],
            out: &mut BTreeSet<usize>,
        ) -> Result<(), Error> {
            match e {
                Expression::Select {
                    left,
                    right,
                    then_value,
                    else_value,
                    ..
                } => {
                    for e in [left, right] {
                        let expanded = crate::causal_voltage::expand(e, program, driven)?;
                        out.extend(crate::guard_trajectory::state_dependencies(&expanded));
                    }
                    for e in [left, right, then_value, else_value] {
                        predicates(e, program, driven, out)?;
                    }
                }
                Expression::Add { left, right }
                | Expression::Multiply { left, right }
                | Expression::Divide { left, right } => {
                    predicates(left, program, driven, out)?;
                    predicates(right, program, driven, out)?;
                }
                _ => {}
            }
            Ok(())
        }
        let mut tested = BTreeSet::new();
        for c in &self.program.contributions {
            predicates(&c.rhs, &self.program, &self.driven, &mut tested)?;
        }
        for (event, indices) in &selection.actions {
            // Causal numeric actions are evaluated from actual driven inputs,
            // not unknown same-time voltage nodes. Classification audited every
            // original action and the existing writer checks retain isolation.
            if self.causal_numeric[*event] {
                continue;
            }
            let mut voltage_dependent = vec![false; self.program.states.len()];
            for &index in indices {
                let (state, rhs) = &self.actions[*event][index];
                voltage_dependent[*state] = !rhs.node_dependencies.is_empty()
                    || rhs.state_dependencies.iter().any(|&s| voltage_dependent[s]);
            }
            if tested.iter().any(|&s| voltage_dependent[s]) {
                if let Some(binding) = source {
                    if source_predicate::qualify(self, *event, binding)? {
                        continue;
                    }
                }
                return Err(Error::new(
                    "unsupported_condition",
                    "same-time contribution predicate depends on a voltage-assigned state",
                ));
            }
        }
        Ok(())
    }

    /// Freeze certified predicates, retaining selected arm state references.
    pub(crate) fn selected_program(&self, states: &[I], inputs: &[I]) -> Result<Program, Error> {
        self.selected_program_at_roots(states, inputs, &[])
            .map(std::borrow::Cow::into_owned)
    }

    pub(crate) fn selected_program_at_roots(
        &self,
        states: &[I],
        inputs: &[I],
        fired: &[usize],
    ) -> Result<std::borrow::Cow<'_, Program>, Error> {
        self.selected_program_with_parameters(states, inputs, fired, &[])
    }

    pub(crate) fn selected_program_with_parameters(
        &self,
        states: &[I],
        inputs: &[I],
        fired: &[usize],
        operators: &[I],
    ) -> Result<std::borrow::Cow<'_, Program>, Error> {
        self.selected_program_with_lineage(states, inputs, fired, operators, None)
    }
    pub(crate) fn selected_program_with_lineage(
        &self,
        states: &[I],
        inputs: &[I],
        fired: &[usize],
        operators: &[I],
        lineage: Option<&crate::transient::point_lineage::PointLineage<'_>>,
    ) -> Result<std::borrow::Cow<'_, Program>, Error> {
        self.selected_program_with_observation_proof(
            states, inputs, fired, operators, lineage, None,
        )
    }
    pub(crate) fn selected_program_with_observation_proof(
        &self,
        states: &[I],
        inputs: &[I],
        fired: &[usize],
        operators: &[I],
        lineage: Option<&crate::transient::point_lineage::PointLineage<'_>>,
        observation: Option<&crate::dc_projection::HeldRampObservationProof<'_>>,
    ) -> Result<std::borrow::Cow<'_, Program>, Error> {
        if let Some(proof) = observation {
            proof.validate_states(states)?;
        }
        let ramp_projection = self
            .dc_projection
            .as_ref()
            .filter(|projection| projection.is_held_ramp());
        let selection_context = self
            .history_admission
            .as_ref()
            .map(|token| &token.context)
            .or_else(|| ramp_projection.map(|projection| &projection.source));
        let history_work = selection_context.map(|context| context.borrow_work());
        if let Some(w) = history_work {
            w.debit(2, self.program.nodes.len() as u64)?;
        }
        let mut nodes = vec![I::ZERO; self.program.nodes.len()];
        for (name, &value) in self.driven.iter().zip(inputs) {
            let index = if let Some(w) = history_work {
                let mut found = None;
                for (index, node) in self.program.nodes.iter().enumerate() {
                    w.step()?;
                    if node == name {
                        found = Some(index);
                        break;
                    }
                }
                found
            } else {
                self.program.nodes.iter().position(|n| n == name)
            }
            .ok_or_else(|| Error::new("invalid_inputs", "unknown driven node"))?;
            nodes[index] = value;
        }
        // This function changes contribution Select nodes only. With none in
        // the complete original RHS trees, the validated program is identical;
        // borrow it rather than cloning every unrelated event statement.
        if self.history_admission.is_none()
            && ramp_projection.is_none()
            && self
                .program
                .contributions
                .iter()
                .all(|c| !crate::analog::has_select(&c.rhs))
        {
            return Ok(std::borrow::Cow::Borrowed(&self.program));
        }
        let mut p = if let Some(context) = selection_context {
            let w = context.borrow_work();
            let bytes = crate::event_floor::admission_bytes(&self.program, w)?;
            w.debit(2, bytes.len().saturating_mul(32) as u64)?;
            serde_json::from_slice::<Program>(&bytes)
                .map_err(|e| Error::new("invalid_ir", e.to_string()))?
        } else {
            self.program.clone()
        };
        for (index, c) in p.contributions.iter_mut().enumerate() {
            if let Some(token) = &self.history_admission {
                c.rhs = token.resolve(index, &nodes, states, operators)?;
                continue;
            }
            let original = ramp_projection
                .map(|projection| projection.view(&c.rhs))
                .transpose()?
                .unwrap_or(&c.rhs);
            let expression = self.resolve_root_selects(original, fired)?;
            let resolved = if let Some(proof) = observation {
                let exact = |left: &Expression, right: &Expression, owner: &str| {
                    proof.sign(
                        left,
                        right,
                        owner,
                        &self.program,
                        &self.driven,
                        &nodes,
                        states,
                    )
                };
                crate::continuous::resolve_selection_with_source_sign(
                    &expression,
                    &self.program,
                    &self.driven,
                    &nodes,
                    states,
                    &exact,
                )
            } else {
                crate::continuous::resolve_selection_with_lineage(
                    &expression,
                    &self.program,
                    &self.driven,
                    &nodes,
                    states,
                    lineage,
                )
            };
            c.rhs = resolved.or_else(|error| {
                if error.kind == "unsupported_transient" && !operators.is_empty() {
                    crate::causal_voltage::resolve(
                        &expression,
                        &self.program,
                        &self.driven,
                        &nodes,
                        states,
                        operators,
                    )
                } else {
                    Err(error)
                }
            })?;
        }
        Ok(std::borrow::Cow::Owned(p))
    }

    fn resolve_root_selects(&self, e: &Expression, fired: &[usize]) -> Result<Expression, Error> {
        use crate::ir::Relation;
        let recurse = |e: &Expression| self.resolve_root_selects(e, fired);
        Ok(match e {
            Expression::Select {
                relation,
                left,
                right,
                then_value,
                else_value,
                origin,
            } => {
                let left = recurse(left)?;
                let right = recurse(right)?;
                let difference = Expression::Add {
                    left: Box::new(left.clone()),
                    right: Box::new(Expression::Multiply {
                        left: Box::new(Expression::Affine {
                            constant: -1.,
                            terms: vec![],
                        }),
                        right: Box::new(right.clone()),
                    }),
                };
                let root = fired.iter().any(|&leaf| {
                    let Some(TriggerLeaf {
                        trigger: EventTrigger::Cross { guard, .. },
                        ..
                    }) = self.triggers.get(leaf)
                    else {
                        return false;
                    };
                    crate::event_accuracy::GuardBounds::project_with_dc(
                        &self.program,
                        &self.driven,
                        &[Some(guard), Some(&difference)],
                        None,
                        false,
                        false,
                        self.dc_projection.as_deref(),
                    )
                    .is_ok_and(|b| b.same_zero_set(0, 1))
                });
                if root {
                    recurse(if matches!(relation, Relation::Le | Relation::Ge) {
                        then_value
                    } else {
                        else_value
                    })?
                } else {
                    Expression::Select {
                        relation: *relation,
                        left: Box::new(left),
                        right: Box::new(right),
                        then_value: Box::new(recurse(then_value)?),
                        else_value: Box::new(recurse(else_value)?),
                        origin: origin.clone(),
                    }
                }
            }
            Expression::Add { left, right } => Expression::Add {
                left: Box::new(recurse(left)?),
                right: Box::new(recurse(right)?),
            },
            Expression::Multiply { left, right } => Expression::Multiply {
                left: Box::new(recurse(left)?),
                right: Box::new(recurse(right)?),
            },
            Expression::Divide { left, right } => Expression::Divide {
                left: Box::new(recurse(left)?),
                right: Box::new(recurse(right)?),
            },
            Expression::Power { base, exponent } => Expression::Power {
                base: Box::new(recurse(base)?),
                exponent: *exponent,
            },
            _ => e.clone(),
        })
    }

    pub(crate) fn observation_selection(
        &self,
        inputs: &[I],
        states: &[f64],
        state_bounds: &[I],
        operators: &[f64],
        operator_bounds: &[I],
    ) -> Result<Selection, Error> {
        if self.program.procedures.is_empty() {
            return self
                .conditions
                .select_at_roots(&[], inputs, &[], state_bounds);
        }
        let work = crate::real_expression::work(self);
        let proofs = crate::event_value_proof::Proofs::new();
        let context = crate::event_value_proof::Context::candidate_frame(
            &proofs,
            self.program.nodes.len(),
            states,
            operators,
            work,
        )?
        .try_with_operators(operator_bounds)?;
        self.conditions
            .select_with_proofs(&[], inputs, &[], state_bounds, Some(&context))
    }
    #[allow(clippy::too_many_arguments)]
    pub(crate) fn circuit_at_procedure_observation(
        &self,
        states: &[f64],
        state_bounds: &[I],
        operators: &[f64],
        operator_bounds: &[I],
        inputs: &[I],
        trajectory: &crate::pwl::Trajectory,
        time: f64,
    ) -> Result<Circuit, Error> {
        if self.program.procedures.is_empty() {
            return self.circuit_at(states, operators, inputs);
        }
        self.procedure_circuit_at(
            states,
            operators,
            inputs,
            Some((trajectory, time, state_bounds, operator_bounds)),
        )
    }
    fn procedure_circuit_at(
        &self,
        states: &[f64],
        operators: &[f64],
        inputs: &[I],
        observation: Option<(&crate::pwl::Trajectory, f64, &[I], &[I])>,
    ) -> Result<Circuit, Error> {
        let work = crate::real_expression::work(self);
        work.debit(
            2,
            ((self.program.nodes.len() + states.len()) * 24 + 64) as u64,
        )?;
        let proofs = crate::event_value_proof::Proofs::new();
        let mut context = crate::event_value_proof::Context::candidate_frame(
            &proofs,
            self.program.nodes.len(),
            states,
            operators,
            work,
        )?;
        if let Some((_, _, _, bounds)) = observation {
            context = context.try_with_operators(bounds)?;
        }
        let mut nodes = vec![
            I {
                lo: f64::NEG_INFINITY,
                hi: f64::INFINITY
            };
            self.program.nodes.len()
        ];
        nodes[0] = I::ZERO;
        work.debit(2, (self.driven.len() * 16 + 32) as u64)?;
        let mut source_nodes = Vec::with_capacity(self.driven.len());
        for (name, &bound) in self.driven.iter().zip(inputs) {
            if let Some(i) = self.program.nodes.iter().position(|n| n == name) {
                nodes[i] = bound;
                source_nodes.push(i);
            }
        }
        let before = observation.map_or_else(
            || states.iter().copied().map(I::point).collect::<Vec<_>>(),
            |(_, _, bounds, _)| bounds.to_vec(),
        );
        let build = |context: &crate::event_value_proof::Context<'_>| {
            let plan = crate::procedure::execute(
                &self.program,
                &[],
                &nodes,
                &before,
                Some(context),
                work,
            )?;
            work.debit(
                2,
                (std::mem::size_of_val(&plan) + 2 * std::mem::size_of::<usize>()) as u64,
            )?;
            std::sync::Arc::new(plan).circuit(
                &self.program,
                &self.driven,
                states,
                operators,
                self.tolerances.clone(),
                work,
            )
        };
        match build(&context) {
            Ok(circuit) => {
                let pending = observation.is_some()
                    && match circuit.procedure_view() {
                        Some(view) => view.unresolved_source_rounding(&source_nodes)?,
                        None => false,
                    };
                if !pending {
                    if let Some((trajectory, time, _, _)) = observation {
                        self.bind_exact_sources(&circuit, inputs, trajectory, time)?;
                    }
                    return Ok(circuit);
                }
            }
            Err(error) if error.kind == "event_condition" && observation.is_some() => {}
            Err(error) => return Err(error),
        }
        // A complete interval proof suffices for most observations.
        // Only an undecidable predicate or sampled value needs exact
        // source membership at b. Neither pure candidate publishes
        // state; both attempts spend the original, sticky Work owner.
        let (trajectory, time, _, bounds) = observation.unwrap();
        let root = crate::exact_source::RootTime::point(time)
            .ok_or_else(|| Error::new("invalid_ir", "invalid procedure observation time"))?;
        context = crate::event_value_proof::Context::try_new(
            self,
            trajectory,
            inputs,
            &proofs,
            Some(&root),
        )?
        .try_with_operators(bounds)?;
        context.set_candidate_frame(states, operators, &[], false)?;
        build(&context)
    }

    /// The exact source value of each driven node at an observation time,
    /// installed in the Plan of a circuit with a same-time cycle through
    /// program reals: its exact equation reads them (decision 22).
    fn bind_exact_sources(
        &self,
        circuit: &Circuit,
        inputs: &[I],
        trajectory: &crate::pwl::Trajectory,
        time: f64,
    ) -> Result<(), Error> {
        let Some(view) = circuit.procedure_view() else {
            return Ok(());
        };
        if !circuit.has_same_time_cycle()? {
            return Ok(());
        }
        let Some(root) = crate::exact_source::RootTime::point(time) else {
            return Ok(());
        };
        let work = crate::real_expression::work(self);
        work.debit(
            2,
            ((self.program.nodes.len() + self.driven.len()) * 64 + 64) as u64,
        )?;
        let mut exact = vec![None; self.program.nodes.len()];
        for (k, (name, bound)) in self.driven.iter().zip(inputs).enumerate() {
            work.debit(2, 200_000)?;
            let Some(value) = trajectory
                .exact_sources
                .get(k)
                .and_then(Option::as_ref)
                .and_then(|curve| curve.at_root(&root))
            else {
                continue;
            };
            if !crate::exact_source::enclosure(&value)
                .is_some_and(|e| bound.lo <= e.lo && e.hi <= bound.hi)
            {
                continue;
            }
            for (node, candidate) in self.program.nodes.iter().enumerate() {
                work.debit(2, (candidate.len() + name.len() + 1) as u64)?;
                if candidate == name {
                    exact[node] = Some(value);
                    break;
                }
            }
        }
        view.plan.set_exact_driven(exact);
        Ok(())
    }

    pub(crate) fn circuit_at(
        &self,
        states: &[f64],
        operators: &[f64],
        inputs: &[I],
    ) -> Result<Circuit, Error> {
        self.circuit_at_with_lineage(states, operators, inputs, None)
    }
    pub(crate) fn circuit_at_with_lineage(
        &self,
        states: &[f64],
        operators: &[f64],
        inputs: &[I],
        lineage: Option<&crate::transient::point_lineage::PointLineage<'_>>,
    ) -> Result<Circuit, Error> {
        self.circuit_at_with_lineage_and_scratch(states, operators, inputs, lineage, None)
    }
    /// `circuit_at_with_lineage` optionally sharing a same-window assembly
    /// plan. The plan holds only structure the model fixes (nodes, branch
    /// grouping, labels); every trial's state, operator and input values are
    /// rebuilt here, so reuse cannot leak a previous trial's numbers.
    pub(crate) fn circuit_at_with_lineage_and_scratch(
        &self,
        states: &[f64],
        operators: &[f64],
        inputs: &[I],
        lineage: Option<&crate::transient::point_lineage::PointLineage<'_>>,
        scratch: Option<&mut Option<crate::assembly::AssemblyPlan>>,
    ) -> Result<Circuit, Error> {
        if !self.program.procedures.is_empty() {
            return self.procedure_circuit_at(states, operators, inputs, None);
        }
        let program = if let Some(lineage) = lineage {
            self.bound_circuit_program_at_with_lineage(states, operators, inputs, Some(lineage))?
        } else {
            self.bound_circuit_program_at(states, operators, inputs)?
        };
        match scratch {
            Some(scratch) => {
                Circuit::new_with_scratch(program, &self.driven, self.tolerances.clone(), scratch)
            }
            None => Circuit::new(program, &self.driven, self.tolerances.clone()),
        }
    }

    fn bound_circuit_program_at(
        &self,
        states: &[f64],
        operators: &[f64],
        inputs: &[I],
    ) -> Result<Program, Error> {
        self.bound_circuit_program_at_with_lineage(states, operators, inputs, None)
    }

    fn bound_circuit_program_at_with_lineage(
        &self,
        states: &[f64],
        operators: &[f64],
        inputs: &[I],
        lineage: Option<&crate::transient::point_lineage::PointLineage<'_>>,
    ) -> Result<Program, Error> {
        self.bound_circuit_program_at_with_observation_proof(
            states, operators, inputs, lineage, None,
        )
    }
    pub(crate) fn circuit_at_with_observation_proof(
        &self,
        states: &[f64],
        operators: &[f64],
        inputs: &[I],
        proof: &crate::dc_projection::HeldRampObservationProof<'_>,
    ) -> Result<Circuit, Error> {
        if !self.program.procedures.is_empty() {
            return self.procedure_circuit_at(states, operators, inputs, None);
        }
        let program = self.bound_circuit_program_at_with_observation_proof(
            states,
            operators,
            inputs,
            None,
            Some(proof),
        )?;
        Circuit::new(program, &self.driven, self.tolerances.clone())
    }
    fn bound_circuit_program_at_with_observation_proof(
        &self,
        states: &[f64],
        operators: &[f64],
        inputs: &[I],
        lineage: Option<&crate::transient::point_lineage::PointLineage<'_>>,
        observation: Option<&crate::dc_projection::HeldRampObservationProof<'_>>,
    ) -> Result<Program, Error> {
        let bounds: Vec<_> = states.iter().copied().map(I::point).collect();
        let selected = self.selected_program_with_observation_proof(
            observation.map_or(bounds.as_slice(), |proof| proof.state_bounds()),
            inputs,
            &[],
            &operators.iter().copied().map(I::point).collect::<Vec<_>>(),
            lineage,
            observation,
        )?;
        let rhs = selected
            .contributions
            .iter()
            .map(|c| {
                affine(
                    &freeze_operators(&c.rhs, operators),
                    &selected,
                    &c.origin.instance,
                )
            })
            .collect::<Result<Vec<_>, _>>()?;
        // Preserve the same electrical program without cloning tables discarded
        // by the former clone-and-clear path. Dependencies were validated on selected.
        let mut program = Program {
            schema_version: selected.schema_version,
            nodes: selected.nodes.clone(),
            contributions: selected.contributions.clone(),
            states: Vec::new(),
            events: Vec::new(),
            operators: Vec::new(),
            step_bounds: selected.step_bounds.clone(),
            procedures: Vec::new(),
            real_bindings: Vec::new(),
        };
        for (contribution, rhs) in program.contributions.iter_mut().zip(&rhs) {
            contribution.rhs = rhs.bind(states, operators)?;
        }
        Ok(program)
    }

    /// Eliminate trial state updates from F(v, state, t)=0 to obtain an affine
    /// voltage system F(v, Phi(old_state, v), t)=0. No accepted state is mutated.
    #[cfg(test)]
    pub(crate) fn event_circuit(
        &self,
        selection: &Selection,
        before: &[f64],
        operators: &[f64],
    ) -> Result<Circuit, Error> {
        self.event_trial_program(&self.program, selection, before, operators)
            .and_then(|program| Circuit::new(program, &self.driven, self.tolerances.clone()))
    }

    /// `event_circuit`'s program only.
    #[cfg(test)]
    fn event_trial_program(
        &self,
        selected: &Program,
        selection: &Selection,
        before: &[f64],
        operators: &[f64],
    ) -> Result<Program, Error> {
        self.event_trial_program_impl(selected, selection, before, operators, None, None)
    }
    /// The joint trial circuit with driven input values and the physical proof
    /// context, optionally sharing an assembly plan with its window peers.
    #[allow(clippy::too_many_arguments)]
    pub(crate) fn event_circuit_with_inputs_proofs_and_scratch(
        &self,
        selected: &Program,
        selection: &Selection,
        before: &[f64],
        operators: &[f64],
        inputs: &[f64],
        proofs: Option<&crate::event_value_proof::Context<'_>>,
        scratch: Option<&mut Option<crate::assembly::AssemblyPlan>>,
    ) -> Result<Circuit, Error> {
        if let Some(plan) = &selection.plan {
            return plan.circuit(
                &self.program,
                &self.driven,
                before,
                operators,
                self.tolerances.clone(),
                crate::real_expression::work(self),
            );
        }
        let program = self.event_trial_program_impl(
            selected,
            selection,
            before,
            operators,
            Some(inputs),
            proofs,
        )?;
        match scratch {
            Some(scratch) => {
                Circuit::new_with_scratch(program, &self.driven, self.tolerances.clone(), scratch)
            }
            None => Circuit::new(program, &self.driven, self.tolerances.clone()),
        }
    }
    fn event_trial_program_impl(
        &self,
        selected: &Program,
        selection: &Selection,
        before: &[f64],
        operators: &[f64],
        inputs: Option<&[f64]>,
        proofs: Option<&crate::event_value_proof::Context<'_>>,
    ) -> Result<Program, Error> {
        if let Some(w) = proofs.and_then(|c| c.floor_work()) {
            let n = self.program.nodes.len()
                + self.program.states.len()
                + self.program.operators.len()
                + 1;
            let mut actions = selection.actions.len() + 1;
            for (_, indices) in &selection.actions {
                crate::event_floor::charge(w, 1, "floor_source_joint_scan")?;
                actions = actions.saturating_add(indices.len());
            }
            crate::event_floor::charge(
                w,
                8usize
                    .saturating_mul(n)
                    .saturating_mul(n)
                    .saturating_mul(actions),
                "floor_source_joint_dense",
            )?;
        }
        let initial: Vec<_> = before
            .iter()
            .map(|&value| AffineState {
                constant: value,
                nodes: vec![0.0; self.program.nodes.len()],
                states: Vec::new(),
                operators: Vec::new(),
                node_dependencies: BTreeSet::new(),
                state_dependencies: BTreeSet::new(),
                operator_dependencies: BTreeSet::new(),
                has_variables: false,
            })
            .collect();
        let mut updates = initial.clone();
        let mut frames = crate::procedure_frames::Frames::new(
            selection,
            Some(crate::real_expression::work(self)),
        )?;
        for (event, indices) in &selection.actions {
            let mut local = frames.take(*event).unwrap_or_else(|| initial.clone());
            for &index in indices {
                let (state, rhs) = &self.actions[*event][index];
                local[*state] = if self.causal_numeric[*event] {
                    let inputs = inputs.ok_or_else(|| {
                        Error::new("invalid_inputs", "sampled event needs driven input values")
                    })?;
                    let mut nodes = vec![0.; self.program.nodes.len()];
                    for (name, &value) in self.driven.iter().zip(inputs) {
                        nodes[self.program.nodes.iter().position(|n| n == name).unwrap()] = value;
                    }
                    let values = local
                        .iter()
                        .map(|v| v.value(&nodes, &[]))
                        .collect::<Result<Vec<_>, _>>()?;
                    let value = crate::event_numeric::value_with_proofs(
                        &self.action_expressions[*event][index],
                        &self.program,
                        &self.program.events[*event].origin.instance,
                        &nodes,
                        &values,
                        proofs,
                    )?;
                    let mut fixed = initial[*state].clone();
                    fixed.constant = value;
                    fixed
                } else {
                    rhs.substitute(&local)?
                };
                if self.program.states[*state].kind == StateKind::Integer {
                    // Integer updates were checked to use integral state-only
                    // arithmetic. Catch overflow before a floating linear solve.
                    check_state(local[*state].constant, &StateKind::Integer)?;
                }
                updates[*state] = local[*state].clone();
            }
            frames.put(*event, local);
        }
        // Match the previous clone-and-clear result without first cloning the
        // immutable state/event/operator trees that the voltage solve discards.
        let mut program = Program {
            schema_version: selected.schema_version,
            nodes: selected.nodes.clone(),
            contributions: selected.contributions.clone(),
            states: Vec::new(),
            events: Vec::new(),
            operators: Vec::new(),
            step_bounds: selected.step_bounds.clone(),
            procedures: Vec::new(),
            real_bindings: Vec::new(),
        };
        let rhs = selected
            .contributions
            .iter()
            .map(|c| {
                affine(
                    &freeze_operators(&c.rhs, operators),
                    selected,
                    &c.origin.instance,
                )
            })
            .collect::<Result<Vec<_>, _>>()?;
        for (contribution, rhs) in program.contributions.iter_mut().zip(&rhs) {
            contribution.rhs = rhs.substitute(&updates)?.bind(&[], operators)?;
        }
        Ok(program)
    }

    fn bind(&self, states: &[f64], operators: &[f64]) -> Result<Program, Error> {
        let mut program = self.selected_program(
            &states.iter().copied().map(I::point).collect::<Vec<_>>(),
            &vec![I::ZERO; self.driven.len()],
        )?;
        let rhs = program
            .contributions
            .iter()
            .map(|c| {
                affine(
                    &freeze_operators(&c.rhs, operators),
                    &program,
                    &c.origin.instance,
                )
            })
            .collect::<Result<Vec<_>, _>>()?;
        program.states.clear();
        program.events.clear();
        program.operators.clear();
        for (contribution, rhs) in program.contributions.iter_mut().zip(&rhs) {
            contribution.rhs = rhs.bind(states, operators)?;
        }
        Ok(program)
    }

    fn check_guard_dependencies(&mut self) -> Result<(), Error> {
        if let Some(token) = &self.history_admission {
            let w = token.context.borrow_work();
            let affected = token.condition_affected(&self.program)?;
            for leaf in &self.triggers {
                w.step()?;
                match &leaf.trigger {
                    EventTrigger::Cross { guard, .. } => {
                        let row = crate::history_admission::affine_paid(guard, &self.program, w)?;
                        for (i, value) in row[..row.len() - 1].iter().enumerate() {
                            w.step()?;
                            if value.zero() {
                                continue;
                            }
                            let mut driven = i == 0;
                            if i < self.program.nodes.len() && !driven {
                                for &node in token.context.event_input_nodes() {
                                    w.step()?;
                                    if node == i {
                                        driven = true;
                                        break;
                                    }
                                }
                            }
                            if !driven {
                                return Err(Error::new("unsupported_condition","ordinary history consumer requires an independent original event calendar"));
                            }
                        }
                    }
                    EventTrigger::Timer { .. } => (),
                    _ => {
                        return Err(Error::new(
                            "unsupported_condition",
                            "ordinary history consumer requires independent cross/timer events",
                        ))
                    }
                }
                w.debit(2, 2)?;
                self.relocalized_guards.push(false);
                self.guard_operators.push(BTreeSet::new());
            }
            self.conditions.check_dependencies(&affected)?;
            return Ok(());
        }
        // Conservative undirected equation connectivity, excluding fixed inputs
        // and ground. No floating-point sensitivity threshold can hide feedback.
        let assembled = crate::assembly::assemble(
            {
                let mut p = self.program.clone();
                for (c, rhs) in p.contributions.iter_mut().zip(&self.rhs) {
                    c.rhs = rhs.bind(&self.initial(), &vec![0.0; p.operators.len()])?;
                }
                p.states.clear();
                p.events.clear();
                p.operators.clear();
                p
            },
            &self.driven,
            self.tolerances.clone(),
        )?;
        // Use assembled branches, with one LHS for all additive contributions.
        // Checking each contribution could cancel that LHS prematurely and
        // incorrectly classify a state-dependent guard as independent.
        let stateful: BTreeSet<_> = self
            .program
            .contributions
            .iter()
            .zip(&self.rhs)
            .filter(|(_, rhs)| {
                !rhs.state_dependencies.is_empty() || !rhs.operator_dependencies.is_empty()
            })
            .map(|(c, _)| &c.branch)
            .collect();
        let mut groups = Vec::new();
        let mut affected = vec![false; self.program.nodes.len()];
        for equation in &assembled.equations {
            let group: Vec<_> = assembled
                .unknown
                .iter()
                .copied()
                .filter(|n| {
                    equation
                        .coefficients
                        .binary_search_by_key(n, |&(node, _)| node)
                        .is_ok()
                        || self
                            .program
                            .contributions
                            .iter()
                            .zip(&self.rhs)
                            .any(|(c, rhs)| {
                                c.branch == equation.branch && rhs.node_dependencies.contains(n)
                            })
                })
                .collect();
            if stateful.contains(&equation.branch) {
                for &n in &group {
                    affected[n] = true;
                }
            }
            groups.push(group);
        }
        loop {
            let mut changed = false;
            for group in &groups {
                if group.iter().any(|n| affected[*n]) {
                    for &n in group {
                        changed |= !affected[n];
                        affected[n] = true;
                    }
                }
            }
            if !changed {
                break;
            }
        }
        // Event-state influence is forbidden; continuous operator influence is
        // handled by dynamic localization instead of being misclassified as q.
        let mut event_affected = vec![false; self.program.nodes.len()];
        let mut operator_influence = vec![BTreeSet::new(); self.program.nodes.len()];
        for (group, equation) in groups.iter().zip(&assembled.equations) {
            let ops: BTreeSet<_> = self
                .program
                .contributions
                .iter()
                .zip(&self.rhs)
                .filter(|(c, _)| c.branch == equation.branch)
                .flat_map(|(_, rhs)| rhs.operator_dependencies.iter().copied())
                .collect();
            for &node in group {
                operator_influence[node].extend(&ops);
            }
            if self
                .program
                .contributions
                .iter()
                .zip(&self.rhs)
                .any(|(c, rhs)| c.branch == equation.branch && !rhs.state_dependencies.is_empty())
            {
                for &node in group {
                    event_affected[node] = true;
                }
            }
        }
        loop {
            let mut changed = false;
            for group in &groups {
                let ops: BTreeSet<_> = group
                    .iter()
                    .flat_map(|&node| operator_influence[node].iter().copied())
                    .collect();
                for &node in group {
                    let before = operator_influence[node].len();
                    operator_influence[node].extend(&ops);
                    changed |= operator_influence[node].len() != before;
                }
                if group.iter().any(|n| event_affected[*n]) {
                    for &node in group {
                        changed |= !event_affected[node];
                        event_affected[node] = true;
                    }
                }
            }
            if !changed {
                break;
            }
        }
        for (index, leaf) in self.triggers.iter().enumerate() {
            let event = &self.program.events[leaf.event];
            if let EventTrigger::Cross { guard, .. } = &leaf.trigger {
                let (nodes, mut operators) = crate::guard_trajectory::dependencies(
                    guard,
                    &self.program,
                    &event.origin.instance,
                )?;
                for node in &nodes {
                    operators.extend(&operator_influence[*node]);
                }
                let held = nodes.iter().any(|node| event_affected[*node])
                    || !crate::guard_trajectory::state_dependencies(guard).is_empty();
                self.relocalized_guards.push(held);
                self.dynamic_guards[index] |=
                    !operators.is_empty() || (!held && nodes.iter().any(|node| affected[*node]));
                self.guard_operators.push(operators);
            } else {
                self.relocalized_guards
                    .push(matches!(leaf.trigger, EventTrigger::HeldTimer { .. }));
                self.guard_operators.push(BTreeSet::new());
            }
        }
        let condition_affected: Vec<_> = event_affected
            .iter()
            .enumerate()
            .map(|(node, &stateful)| {
                stateful
                    || operator_influence[node].iter().any(|&op| {
                        !matches!(
                            self.program.operators[op],
                            crate::ir::OperatorSpec::Transition { .. }
                        )
                    })
            })
            .collect();
        self.conditions.check_dependencies(&condition_affected)?;
        crate::reset_dependencies::check(
            &self.program,
            &self.rhs,
            &self.actions,
            &groups,
            &assembled,
            // Construction already bound the owner of a program with
            // procedures; any other program leaves its lazy owner to the caller.
            (!self.program.procedures.is_empty()).then(|| crate::real_expression::work(self)),
        )
    }

    /// Replay the certified path and capture displays at their statement position.
    /// The returned records are candidate data; the caller commits them on acceptance.
    pub(crate) fn apply_with_displays(
        &self,
        selection: &Selection,
        voltages: &[f64],
        before: &[f64],
        time: f64,
    ) -> Result<(Vec<f64>, Vec<crate::ir::DisplayRecord>), Error> {
        self.apply_with_displays_with_proofs(selection, voltages, before, time, None)
    }
    pub(crate) fn apply_with_displays_with_proofs(
        &self,
        selection: &Selection,
        voltages: &[f64],
        before: &[f64],
        time: f64,
        proofs: Option<&crate::event_value_proof::Context<'_>>,
    ) -> Result<(Vec<f64>, Vec<crate::ir::DisplayRecord>), Error> {
        if let Some(plan) = &selection.plan {
            let w = crate::real_expression::work(self);
            let states = plan.numeric_states(&self.program, voltages, before, proofs, w)?;
            let mut records = Vec::new();
            for (event, format, args, origin) in &plan.displays {
                w.debit(2, (args.len() * 8 + format.len() + 64) as u64)?;
                let values = plan.numeric_values(args, voltages, before, proofs, w)?;
                records.push(crate::ir::DisplayRecord {
                    time,
                    event: *event,
                    origin: origin.label(),
                    text: crate::display::render(format, &values)?,
                });
            }
            return Ok((states, records));
        }
        fn collect<'a>(body: &'a [crate::ir::Statement], out: &mut Vec<&'a crate::ir::Statement>) {
            for statement in body {
                match statement {
                    crate::ir::Statement::Loop {
                        initialize,
                        body,
                        update,
                        ..
                    } => {
                        collect(initialize, out);
                        collect(body, out);
                        collect(update, out);
                    }
                    crate::ir::Statement::Display { .. } => out.push(statement),
                    crate::ir::Statement::If {
                        then_body,
                        else_body,
                        ..
                    } => {
                        collect(then_body, out);
                        collect(else_body, out);
                    }
                    _ => {}
                }
            }
        }
        let mut after = before.to_vec();
        let mut records = Vec::new();
        let mut frames = crate::procedure_frames::Frames::new(
            selection,
            Some(crate::real_expression::work(self)),
        )?;
        for (event, steps) in &selection.ordered_steps {
            let body = &self.program.events[*event];
            let mut displays = Vec::new();
            collect(&body.body, &mut displays);
            let mut local = frames.take(*event).unwrap_or_else(|| before.to_vec());
            for step in steps {
                match step {
                    crate::event_conditions::SelectedStep::Assign(index) => {
                        let (state, expression) = &self.actions[*event][*index];
                        local[*state] = if self.numeric_actions[*event][*index] {
                            crate::event_numeric::value_with_proofs(
                                &self.action_expressions[*event][*index],
                                &self.program,
                                &self.program.events[*event].origin.instance,
                                voltages,
                                &local,
                                proofs,
                            )?
                        } else {
                            expression.value(voltages, &local)?
                        };
                        check_state(local[*state], &self.program.states[*state].kind)?;
                        after[*state] = local[*state];
                    }
                    crate::event_conditions::SelectedStep::Display(index) => {
                        if let crate::ir::Statement::Display {
                            format,
                            args,
                            origin,
                        } = displays[*index]
                        {
                            let values = args
                                .iter()
                                .map(|expr| {
                                    crate::event_numeric::value_with_proofs(
                                        expr,
                                        &self.program,
                                        &body.origin.instance,
                                        voltages,
                                        &local,
                                        proofs,
                                    )
                                })
                                .collect::<Result<Vec<_>, _>>()?;
                            records.push(crate::ir::DisplayRecord {
                                time,
                                event: *event,
                                origin: origin.label(),
                                text: crate::display::render(format, &values)?,
                            });
                        }
                    }
                }
            }
            frames.put(*event, local);
        }
        Ok((after, records))
    }

    /// Replay against supplied trial voltages and the fixed accepted old state.
    /// Statements in one block see earlier assignments. No accepted state changes.
    pub(crate) fn apply(
        &self,
        selection: &Selection,
        voltages: &[f64],
        before: &[f64],
    ) -> Result<Vec<f64>, Error> {
        self.apply_with_proofs(selection, voltages, before, None)
    }
    pub(crate) fn apply_with_proofs(
        &self,
        selection: &Selection,
        voltages: &[f64],
        before: &[f64],
        proofs: Option<&crate::event_value_proof::Context<'_>>,
    ) -> Result<Vec<f64>, Error> {
        if let Some(plan) = &selection.plan {
            return plan.numeric_states(
                &self.program,
                voltages,
                before,
                proofs,
                crate::real_expression::work(self),
            );
        }
        let mut after = before.to_vec();
        let mut frames = crate::procedure_frames::Frames::new(
            selection,
            Some(crate::real_expression::work(self)),
        )?;
        for (event, indices) in &selection.actions {
            let mut local = frames.take(*event).unwrap_or_else(|| before.to_vec());
            for &index in indices {
                let (state, expression) = &self.actions[*event][index];
                local[*state] = if self.numeric_actions[*event][index] {
                    crate::event_numeric::value_with_proofs(
                        &self.action_expressions[*event][index],
                        &self.program,
                        &self.program.events[*event].origin.instance,
                        voltages,
                        &local,
                        proofs,
                    )?
                } else {
                    expression.value(voltages, &local)?
                };
                check_state(local[*state], &self.program.states[*state].kind)?;
                after[*state] = local[*state];
            }
            frames.put(*event, local);
        }
        Ok(after)
    }
}

impl EventModel {
    pub(crate) fn held_parameter_dependencies(
        &self,
        e: &Expression,
        owner: &str,
    ) -> Result<AffineState, Error> {
        if self.program.procedures.is_empty() {
            return affine(e, &self.program, owner);
        }
        let w = crate::real_expression::work(self);
        let sources = crate::procedure::dependency_sources(&self.program, w)?;
        crate::procedure::source_dependencies(e, &self.program, &sources, w)
    }
}

#[cfg(test)]
#[path = "events_certificate_cache_tests.rs"]
mod certificate_cache_tests;

#[cfg(test)]
mod forcing_affine_storage_tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn affine_state_owned_copy_items_counts_private_dense_operator_dimension() {
        let mut counts = Vec::new();
        for k in [1usize, 1024usize] {
            let o = json!({"source":"affine-storage.va","line":1,"column":1,"instance":"D"});
            let transition = json!({"kind":"transition","input":{"op":"state","state":0},
            "delay":0.,"rise":0.125,"fall":0.125,"origin":o});
            let p: Program = serde_json::from_value(json!({
            "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","u"],
            "states":[{"instance":"D","name":"q","kind":"integer","initial":0.}],
            "operators":vec![transition;k],"contributions":[],"events":[]}))
            .unwrap();
            let a = affine(&Expression::State { state: 0 }, &p, "D").unwrap();
            // Independently from the constructor dimensions: 2 node slots, 1 state
            // slot, K private operator slots, one dependency-set entry at 4 items.
            // Even unused zero-valued operator coefficients occupy owned storage.
            assert_eq!(a.nodes.len(), 2);
            assert_eq!(a.states.len(), 1);
            assert_eq!(a.operators.len(), k);
            assert_eq!(a.state_dependencies.len(), 1);
            assert!(a.node_dependencies.is_empty());
            assert!(a.operator_dependencies.is_empty());
            assert_eq!(a.owned_copy_items(), 2 + 1 + k + 4);
            counts.push(a.owned_copy_items());
        }
        assert_eq!(counts[1] - counts[0], 1023);
    }
}
