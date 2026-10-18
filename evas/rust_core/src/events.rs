//! Bound affine event model. State is separate from electrical unknowns.
use crate::event_conditions::{Conditions, Selection};
use crate::interval::Interval as I;
use crate::ir::{Error, EventTrigger, Expression, Program, StateKind, Term, Tolerances};
use crate::settlement_bounds::Bounds;
use crate::solver::Circuit;
use std::cell::RefCell;
use std::collections::BTreeSet;

#[derive(Clone)]
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
        Expression::IntegerPrimitive { .. }
        | Expression::ArrayRead { .. }
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
    pub(crate) typed_transition_targets: BTreeSet<usize>,
    pub(crate) source_context: Option<std::sync::Arc<crate::transition_source_plan::ProofContext>>,
    pub(crate) program: Program,
    pub(crate) floor_source: Option<std::sync::Arc<crate::event_floor::Request>>,
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
        let admission =
            crate::event_control::admit(&program, provided.as_ref().map(|s| s.borrow_work()))?;
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
        if floor_source.is_none() {
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
        for c in &program.contributions {
            crate::continuous::validate_selection(&c.rhs, &program, &driven, &c.origin.instance)
                .or_else(|error| {
                    if error.kind == "unsupported_transient" && crate::analog::has_select(&c.rhs) {
                        crate::continuous::validate_integral_input(
                            &c.rhs,
                            &program,
                            &c.origin.instance,
                        )?;
                        crate::causal_voltage::history_selection(&c.rhs, &program, &driven)
                    } else {
                        Err(error)
                    }
                })?;
        }
        let shaped = program
            .contributions
            .iter()
            .map(|c| contribution_shape(&c.rhs, &program, &c.origin.instance))
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
                                && crate::event_numeric::contains_math(argument)
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
        for (index, event) in program.events.iter().enumerate() {
            validate_displays(
                &event.body,
                &program,
                &event.origin.instance,
                passive_events[index],
                floor_source.as_ref().map(|r| r.work()),
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
            floor_source.as_ref().map(|r| r.work()),
        )?;
        let general_events: Vec<_> = passive_events
            .iter()
            .zip(&causal_numeric)
            .map(|(a, b)| *a || *b)
            .collect();
        for (index, event) in program.events.iter().enumerate() {
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
                            let value = affine(expression, &program, &event.origin.instance)?;
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
                let is_numeric = general_events[index] && ordinary.is_err();
                let value = if is_numeric {
                    crate::event_numeric::dependencies(
                        &assignment.rhs,
                        &program,
                        &event.origin.instance,
                    )?
                } else {
                    ordinary?
                };
                expressions.push(assignment.rhs.clone());
                numeric.push(is_numeric);
                if !value.operator_dependencies.is_empty() {
                    return Err(Error::new(
                        "unsupported_transient",
                        "operator calls are only allowed in contributions",
                    ));
                }
                if state.kind == StateKind::Integer
                    && general_events[index]
                    && !crate::event_numeric::integral(&assignment.rhs, &program)
                {
                    return Err(Error::new(
                        "unsupported_transient",
                        "integer assignments require integral state arithmetic",
                    ));
                }
                if state.kind == StateKind::Integer
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
        conditions.restrict_events(&passive_events.iter().map(|p| !p).collect::<Vec<_>>());
        let mut passive_conditions = Conditions::new_with_numeric(&program, &general_events)?;
        passive_conditions.restrict_events(&passive_events);
        let (projected, node_inputs) =
            crate::event_accuracy::GuardBounds::passive_program(&program);
        passive_conditions.prepare(&projected, &node_inputs)?;
        let typed_transition_targets = admission.targets;
        let mut model = Self {
            typed_transition_targets,
            source_context,
            conditions,
            passive_conditions,
            passive_events,
            program,
            dc_projection: None,
            floor_source,
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
        // Reuse dependency metadata already audited above. Original Transition
        // products plus an internal history cross cannot use the legacy affine
        // network map; direct/implicit supported callers incur no DC proof.
        if let Some(t) = trajectory {
            if model.guard_operators.iter().any(|ops| !ops.is_empty())
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
        let _timing = crate::diagnostics::span("event.certificate");
        let selected = self.selected_program_with_parameters(
            &states.iter().copied().map(I::point).collect::<Vec<_>>(),
            inputs,
            fired,
            operators,
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
        let cached = self
            .certificate
            .borrow()
            .as_ref()
            .is_some_and(|(path, bounds)| {
                path == selection && bounds.matches_operator_bindings(operators)
            });
        if resolved {
            let bounds = Bounds::for_program_with_operators(self, selection, &selected, operators)?;
            let result =
                bounds.check_observation(self, inputs, before, operators, voltages, states)?;
            let replay =
                self.selected_program_with_parameters(&result.0, inputs, fired, operators)?;
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
            *cache = Some((selection.clone(), bounds));
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
            let replay =
                self.selected_program_with_parameters(&result.0, inputs, fired, operators)?;
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
        let _timing = crate::diagnostics::span("event.state_certificate");

        let selected = self.selected_program_with_parameters(
            &states.iter().copied().map(I::point).collect::<Vec<_>>(),
            inputs,
            fired,
            operators,
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
        let cached = self
            .certificate
            .borrow()
            .as_ref()
            .is_some_and(|(path, bounds)| {
                path == selection && bounds.matches_operator_bindings(operators)
            });
        if resolved {
            let bounds = Bounds::for_program_with_operators(self, selection, &selected, operators)?;
            let result = bounds.check_states(self, inputs, before, operators, voltages, states)?;
            let replay =
                self.selected_program_with_parameters(&result, inputs, fired, operators)?;
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
            *cache = Some((selection.clone(), bounds));
        } else {
            crate::diagnostics::counter("certificate_cache_hits", 1);
        }
        let result = cache
            .as_ref()
            .unwrap()
            .1
            .check_states(self, inputs, before, operators, voltages, states)?;
        if !operators.is_empty() {
            let replay =
                self.selected_program_with_parameters(&result, inputs, fired, operators)?;
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
        fn reads_other_writer(expr: &Expression, event: usize, writers: &[Option<usize>]) -> bool {
            match expr {
                Expression::CheckedIndex { index, .. }
                | Expression::CheckedInteger { value: index, .. } => {
                    reads_other_writer(index, event, writers)
                }
                Expression::ArrayRead { states, index, .. } => {
                    states
                        .iter()
                        .any(|&state| writers[state].is_some_and(|w| w != event))
                        || reads_other_writer(index, event, writers)
                }
                Expression::IntegerPrimitive { args, .. } => {
                    let mut refs = Vec::new();
                    crate::integer_primitive::states(args, &mut refs);
                    refs.iter()
                        .any(|&state| writers[state].is_some_and(|w| w != event))
                }
                Expression::EventMath { args, .. } => {
                    args.iter().any(|e| reads_other_writer(e, event, writers))
                }
                Expression::State { state } => {
                    writers[*state].is_some_and(|writer| writer != event)
                }
                Expression::Add { left, right }
                | Expression::Multiply { left, right }
                | Expression::Divide { left, right } => {
                    reads_other_writer(left, event, writers)
                        || reads_other_writer(right, event, writers)
                }
                Expression::Power { base, .. } => reads_other_writer(base, event, writers),
                Expression::Select {
                    left,
                    right,
                    then_value,
                    else_value,
                    ..
                } => [left, right, then_value, else_value]
                    .iter()
                    .any(|expr| reads_other_writer(expr, event, writers)),
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
                if writers[state].is_some_and(|writer| writer != *event) {
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
                if rhs
                    .state_dependencies
                    .iter()
                    .any(|&s| writers[s].is_some_and(|writer| writer != *event))
                {
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
                        .any(|expr| reads_other_writer(expr, *event, &writers))
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
        let mut nodes = vec![I::ZERO; self.program.nodes.len()];
        for (name, &value) in self.driven.iter().zip(inputs) {
            let index = self
                .program
                .nodes
                .iter()
                .position(|n| n == name)
                .ok_or_else(|| Error::new("invalid_inputs", "unknown driven node"))?;
            nodes[index] = value;
        }
        // This function changes contribution Select nodes only. With none in
        // the complete original RHS trees, the validated program is identical;
        // borrow it rather than cloning every unrelated event statement.
        if self
            .program
            .contributions
            .iter()
            .all(|c| !crate::analog::has_select(&c.rhs))
        {
            return Ok(std::borrow::Cow::Borrowed(&self.program));
        }
        let mut p = self.program.clone();
        for c in &mut p.contributions {
            let expression = self.resolve_root_selects(&c.rhs, fired)?;
            c.rhs = crate::continuous::resolve_selection(
                &expression,
                &self.program,
                &self.driven,
                &nodes,
                states,
            )
            .or_else(|error| {
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

    pub(crate) fn circuit_at(
        &self,
        states: &[f64],
        operators: &[f64],
        inputs: &[I],
    ) -> Result<Circuit, Error> {
        Circuit::new(
            self.bound_circuit_program_at(states, operators, inputs)?,
            &self.driven,
            self.tolerances.clone(),
        )
    }

    fn bound_circuit_program_at(
        &self,
        states: &[f64],
        operators: &[f64],
        inputs: &[I],
    ) -> Result<Program, Error> {
        let bounds: Vec<_> = states.iter().copied().map(I::point).collect();
        let selected = self.selected_program_with_parameters(
            &bounds,
            inputs,
            &[],
            &operators.iter().copied().map(I::point).collect::<Vec<_>>(),
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
        self.event_circuit_program(&self.program, selection, before, operators)
    }

    #[cfg(test)]
    pub(crate) fn event_circuit_program(
        &self,
        selected: &Program,
        selection: &Selection,
        before: &[f64],
        operators: &[f64],
    ) -> Result<Circuit, Error> {
        self.event_circuit_program_impl(selected, selection, before, operators, None, None)
    }
    pub(crate) fn event_circuit_program_with_inputs_and_proofs(
        &self,
        selected: &Program,
        selection: &Selection,
        before: &[f64],
        operators: &[f64],
        inputs: &[f64],
        proofs: Option<&crate::event_value_proof::Context<'_>>,
    ) -> Result<Circuit, Error> {
        self.event_circuit_program_impl(
            selected,
            selection,
            before,
            operators,
            Some(inputs),
            proofs,
        )
    }
    fn event_circuit_program_impl(
        &self,
        selected: &Program,
        selection: &Selection,
        before: &[f64],
        operators: &[f64],
        inputs: Option<&[f64]>,
        proofs: Option<&crate::event_value_proof::Context<'_>>,
    ) -> Result<Circuit, Error> {
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
        for (event, indices) in &selection.actions {
            let mut local = initial.clone();
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
        Circuit::new(program, &self.driven, self.tolerances.clone())
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
        for (event, steps) in &selection.ordered_steps {
            let body = &self.program.events[*event];
            let mut displays = Vec::new();
            collect(&body.body, &mut displays);
            let mut local = before.to_vec();
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
        let mut after = before.to_vec();
        for (event, indices) in &selection.actions {
            let mut local = before.to_vec();
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
        }
        Ok(after)
    }
}

#[cfg(test)]
#[path = "events_certificate_cache_tests.rs"]
mod certificate_cache_tests;
