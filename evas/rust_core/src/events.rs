//! Bound affine event model. State is separate from electrical unknowns.
use crate::ir::{Error, Expression, Program, StateKind, Term, Tolerances};
use crate::solver::Circuit;
use std::collections::BTreeSet;

pub(crate) struct AffineState {
    constant: f64,
    nodes: Vec<f64>,
    states: Vec<f64>,
    // Structural dependence survives coefficient cancellation and underflow.
    // It is deliberately conservative, including exact algebraic cancellations.
    has_variables: bool,
}

impl AffineState {
    pub(crate) fn value(&self, nodes: &[f64], states: &[f64]) -> Result<f64, Error> {
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
                .sum::<f64>();
        if !value.is_finite() {
            return Err(Error::new(
                "nonfinite_arithmetic",
                "nonfinite event expression",
            ));
        }
        Ok(value)
    }

    fn bind(&self, states: &[f64]) -> Result<Expression, Error> {
        Ok(Expression::Affine {
            constant: self.value(&[], states)?,
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

fn affine(expr: &Expression, program: &Program, owner: &str) -> Result<AffineState, Error> {
    let mut result = AffineState {
        constant: 0.0,
        nodes: vec![0.0; program.nodes.len()],
        states: vec![0.0; program.states.len()],
        has_variables: false,
    };
    match expr {
        Expression::Affine { constant, terms } => {
            crate::expression::validate(expr, program.nodes.len())?;
            result.constant = *constant;
            for term in terms {
                result.nodes[term.node] = term.coefficient;
                result.has_variables |= term.coefficient != 0.0;
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
            result.states = a
                .states
                .iter()
                .zip(&b.states)
                .map(|(x, y)| ka * x + kb * y)
                .collect();
        }
        Expression::Power { .. } => {
            return Err(Error::new(
                "unsupported_transient",
                "polynomial transient equations are not supported",
            ))
        }
    }
    if !result.constant.is_finite()
        || result
            .nodes
            .iter()
            .chain(&result.states)
            .any(|v| !v.is_finite())
    {
        return Err(Error::new(
            "nonfinite_arithmetic",
            "affine event coefficient overflow",
        ));
    }
    Ok(result)
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

pub(crate) struct EventModel {
    pub(crate) program: Program,
    rhs: Vec<AffineState>,
    pub(crate) guards: Vec<AffineState>,
    actions: Vec<Vec<(usize, AffineState)>>,
    pub(crate) driven: Vec<String>,
    tolerances: Tolerances,
}

impl EventModel {
    pub(crate) fn new(
        program: Program,
        driven: Vec<String>,
        tolerances: Tolerances,
    ) -> Result<Self, Error> {
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
            {
                return Err(Error::new(
                    "invalid_ir",
                    "invalid or duplicate state identity",
                ));
            }
            check_state(state.initial, &state.kind)?;
        }
        let rhs = program
            .contributions
            .iter()
            .map(|c| affine(&c.rhs, &program, &c.origin.instance))
            .collect::<Result<Vec<_>, _>>()?;
        let mut guards = Vec::new();
        let mut actions = Vec::new();
        let mut writers = vec![None; program.states.len()];
        for (index, event) in program.events.iter().enumerate() {
            if !(-1..=1).contains(&event.direction)
                || !event.time_tolerance.is_finite()
                || event.time_tolerance <= 0.0
                || !event.expression_tolerance.is_finite()
                || event.expression_tolerance <= 0.0
                || event.origin.instance.is_empty()
                || event.origin.source.is_empty()
                || event.origin.line == 0
                || event.origin.column == 0
                || !program
                    .contributions
                    .iter()
                    .any(|c| c.branch.instance == event.origin.instance)
            {
                return Err(Error::new("invalid_ir", "invalid cross settings or origin"));
            }
            let guard = affine(&event.guard, &program, &event.origin.instance)?;
            if guard.states.iter().any(|v| *v != 0.0) {
                return Err(Error::new(
                    "unsupported_cross",
                    format!("cross guard depends on state at {}", event.origin.label()),
                ));
            }
            guards.push(guard);
            let mut body = Vec::new();
            for assignment in &event.assignments {
                let state = program.states.get(assignment.state).ok_or_else(|| {
                    Error::new("invalid_ir", "assignment state index out of range")
                })?;
                if state.instance != event.origin.instance
                    || writers[assignment.state].is_some_and(|i| i != index)
                {
                    return Err(Error::new(
                        "unsupported_cross",
                        "a state may be written by only one cross block in its instance",
                    ));
                }
                writers[assignment.state] = Some(index);
                let value = affine(&assignment.rhs, &program, &event.origin.instance)?;
                if state.kind == StateKind::Integer
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
        }
        for (index, body) in actions.iter().enumerate() {
            if body.iter().any(|(_, rhs)| {
                rhs.states
                    .iter()
                    .enumerate()
                    .any(|(s, c)| *c != 0.0 && writers[s].is_some_and(|writer| writer != index))
            }) {
                return Err(Error::new(
                    "unsupported_cross",
                    "cross blocks cannot read state written by another cross block",
                ));
            }
        }
        let model = Self {
            program,
            rhs,
            guards,
            actions,
            driven,
            tolerances,
        };
        model.check_guard_dependencies()?;
        Ok(model)
    }

    pub(crate) fn initial(&self) -> Vec<f64> {
        self.program.states.iter().map(|s| s.initial).collect()
    }

    pub(crate) fn circuit(&self, states: &[f64]) -> Result<Circuit, Error> {
        Circuit::new(self.bind(states)?, &self.driven, self.tolerances.clone())
    }

    fn bind(&self, states: &[f64]) -> Result<Program, Error> {
        let mut program = self.program.clone();
        program.states.clear();
        program.events.clear();
        for (contribution, rhs) in program.contributions.iter_mut().zip(&self.rhs) {
            contribution.rhs = rhs.bind(states)?;
        }
        Ok(program)
    }

    fn check_guard_dependencies(&self) -> Result<(), Error> {
        // Conservative undirected equation connectivity, excluding fixed inputs
        // and ground. No floating-point sensitivity threshold can hide feedback.
        let assembled = crate::assembly::assemble(
            self.bind(&self.initial())?,
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
            .filter(|(_, rhs)| rhs.states.iter().any(|v| *v != 0.0))
            .map(|(c, _)| &c.branch)
            .collect();
        let mut groups = Vec::new();
        let mut affected = vec![false; self.program.nodes.len()];
        for equation in &assembled.equations {
            let group: Vec<_> = assembled
                .unknown
                .iter()
                .copied()
                .filter(|n| equation.coefficients[*n] != 0.0)
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
        for (guard, event) in self.guards.iter().zip(&self.program.events) {
            if guard
                .nodes
                .iter()
                .zip(&affected)
                .any(|(c, a)| *c != 0.0 && *a)
            {
                return Err(Error::new(
                    "unsupported_cross",
                    format!(
                        "cross guard may depend on state through the voltage network at {}",
                        event.origin.label()
                    ),
                ));
            }
        }
        Ok(())
    }

    /// Prepare only. Every block sees the same pre-event voltages/state; statements
    /// inside one block see its own earlier assignments. No accepted state changes.
    pub(crate) fn apply(
        &self,
        events: &[usize],
        voltages: &[f64],
        before: &[f64],
    ) -> Result<Vec<f64>, Error> {
        let mut after = before.to_vec();
        for &index in events {
            let mut local = before.to_vec();
            for (state, expression) in &self.actions[index] {
                local[*state] = expression.value(voltages, &local)?;
                check_state(local[*state], &self.program.states[*state].kind)?;
                after[*state] = local[*state];
            }
        }
        Ok(after)
    }
}
