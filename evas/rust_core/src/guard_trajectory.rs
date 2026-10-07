//! Polynomial guards on certified continuous trajectories within a held epoch.
use crate::events::{affine, EventModel};
use crate::interval::Interval as I;
use crate::ir::{Error, Expression, Program};
use crate::operators::Operators;
use crate::pwl::Trajectory;
use std::collections::BTreeSet;

pub(crate) fn dependencies(
    expr: &Expression,
    program: &Program,
    owner: &str,
) -> Result<(BTreeSet<usize>, BTreeSet<usize>), Error> {
    match expr {
        Expression::Add { left, right } | Expression::Multiply { left, right } => {
            let (mut nodes, mut operators) = dependencies(left, program, owner)?;
            let (n, o) = dependencies(right, program, owner)?;
            nodes.extend(n);
            operators.extend(o);
            Ok((nodes, operators))
        }
        Expression::Power { base, exponent } => {
            if !(1..=32).contains(exponent) {
                return Err(Error::new(
                    "invalid_ir",
                    "guard power exponent must be in [1,32]",
                ));
            }
            dependencies(base, program, owner)
        }
        Expression::Select { .. } => Err(Error::new(
            "unsupported_cross",
            "cross guard must be a continuous polynomial expression",
        )),
        _ => {
            let a = affine(expr, program, owner)?;
            Ok((a.node_dependencies, a.operator_dependencies))
        }
    }
}

pub(crate) fn evaluate(
    expr: &Expression,
    nodes: &[I],
    operators: &[I],
    states: &[I],
    node_derivatives: &[I],
    operator_derivatives: &[I],
) -> Result<(I, I), Error> {
    let result = match expr {
        Expression::Affine { constant, terms } => {
            terms
                .iter()
                .fold((I::point(*constant), I::ZERO), |(v, d), term| {
                    (
                        v + I::point(term.coefficient) * nodes[term.node],
                        d + I::point(term.coefficient) * node_derivatives[term.node],
                    )
                })
        }
        Expression::Operator { operator } => {
            (operators[*operator], operator_derivatives[*operator])
        }
        Expression::State { state } => (states[*state], I::ZERO),
        Expression::Add { left, right } => {
            let (a, da) = evaluate(
                left,
                nodes,
                operators,
                states,
                node_derivatives,
                operator_derivatives,
            )?;
            let (b, db) = evaluate(
                right,
                nodes,
                operators,
                states,
                node_derivatives,
                operator_derivatives,
            )?;
            (a + b, da + db)
        }
        Expression::Multiply { left, right } => {
            let (a, da) = evaluate(
                left,
                nodes,
                operators,
                states,
                node_derivatives,
                operator_derivatives,
            )?;
            let (b, db) = evaluate(
                right,
                nodes,
                operators,
                states,
                node_derivatives,
                operator_derivatives,
            )?;
            (a * b, da * b + a * db)
        }
        Expression::Power { base, exponent } => {
            let (a, da) = evaluate(
                base,
                nodes,
                operators,
                states,
                node_derivatives,
                operator_derivatives,
            )?;
            let mut previous = I::ONE;
            for _ in 1..*exponent {
                previous = previous * a;
            }
            (previous * a, I::point(*exponent as f64) * previous * da)
        }
        _ => {
            return Err(Error::new(
                "unsupported_cross",
                "noncontinuous guard expression",
            ))
        }
    };
    if !result.0.finite() || !result.1.finite() {
        return Err(Error::new(
            "event_resolution",
            "nonfinite polynomial guard enclosure",
        ));
    }
    Ok(result)
}

pub(crate) struct GuardTrajectory<'a> {
    model: &'a EventModel,
    trajectory: &'a Trajectory,
    operators: Option<&'a Operators>,
    states: Option<&'a [I]>,
    nodes: Vec<Vec<I>>,
}

impl<'a> GuardTrajectory<'a> {
    pub(crate) fn new(
        model: &'a EventModel,
        trajectory: &'a Trajectory,
        operators: &'a Operators,
    ) -> Result<Self, Error> {
        Self::new_held(model, trajectory, Some(operators), None)
    }
    pub(crate) fn new_held(
        model: &'a EventModel,
        trajectory: &'a Trajectory,
        operators: Option<&'a Operators>,
        states: Option<&'a [I]>,
    ) -> Result<Self, Error> {
        // Validate structural dependencies even if algebraic projection cancels
        // their coefficients. A history-free calendar pass has no operators.
        if let Some(operators) = operators {
            for index in model.guard_operators.iter().flat_map(|ops| ops.iter()) {
                operators.check_guard(*index)?;
            }
        }
        Ok(Self {
            model,
            trajectory,
            operators,
            states,
            nodes: crate::affine_bounds::node_map(&model.program, &model.driven)?,
        })
    }

    pub(crate) fn changed_by(
        &self,
        expression: &Expression,
        owner: &str,
        before: &[I],
        after: &[I],
    ) -> Result<bool, Error> {
        let mut states = state_dependencies(expression);
        let (nodes, _) = dependencies(expression, &self.model.program, owner)?;
        let start = self.model.driven.len();
        for node in nodes {
            for (index, c) in self.nodes[node][start..start + before.len()]
                .iter()
                .enumerate()
            {
                if !c.zero() {
                    states.insert(index);
                }
            }
        }
        Ok(states.iter().any(|&index| before[index] != after[index]))
    }
    pub(crate) fn range(
        &self,
        expression: &Expression,
        time: I,
        owner: &str,
    ) -> Result<(I, I), Error> {
        self.range_impl(expression, time, owner, false)
    }

    /// Value-only enclosure of an ordered event observation. Unlike root
    /// isolation, this may use the saved physical state before a representative.
    pub(crate) fn event_value(
        &self,
        expression: &Expression,
        time: I,
        owner: &str,
    ) -> Result<I, Error> {
        Ok(self.range_impl(expression, time, owner, true)?.0)
    }

    pub(crate) fn local_range_impl(
        &self,
        expression: &Expression,
        time: I,
        owner: &str,
    ) -> Result<(I, I), Error> {
        let p = &self.model.program;
        let (node_deps, mut operator_deps) = dependencies(expression, p, owner)?;
        // Ownership was validated in EventModel. The network can contain
        // operators in other instances, so follow each projected node map.
        let state_start = self.model.driven.len();
        let operator_start = state_start + p.states.len();
        for &node in &node_deps {
            if self.states.is_none()
                && self.nodes[node][state_start..operator_start]
                    .iter()
                    .any(|v| !v.zero())
            {
                return Err(Error::new(
                    "unsupported_cross",
                    "guard voltage depends on event state",
                ));
            }
            for (k, c) in self.nodes[node][operator_start..operator_start + p.operators.len()]
                .iter()
                .enumerate()
            {
                if !c.zero() {
                    operator_deps.insert(k);
                }
            }
        }
        if node_deps.iter().any(|&node| {
            self.nodes[node][..self.model.driven.len()]
                .iter()
                .any(|c| !c.zero())
        }) {
            return Err(Error::new(
                "event_resolution",
                "local causal guard depends on a driven source",
            ));
        }
        let mut values = vec![I::ZERO; self.model.driven.len()];
        let mut derivatives = values.clone();
        let initial: Vec<_> = p.states.iter().map(|s| I::point(s.initial)).collect();
        let states = self.states.unwrap_or(&initial);
        values.extend(states);
        derivatives.extend(vec![I::ZERO; p.states.len()]);
        let mut operator_values = vec![I::ZERO; p.operators.len()];
        let mut operator_derivatives = operator_values.clone();
        for index in operator_deps {
            (operator_values[index], operator_derivatives[index]) = self
                .operators
                .ok_or_else(|| {
                    Error::new("event_resolution", "local guard lacks physical history")
                })?
                .local_range(index, time)?;
        }
        values.extend(&operator_values);
        values.push(I::ONE);
        derivatives.extend(&operator_derivatives);
        derivatives.push(I::ZERO);
        let node_values: Vec<_> = self.nodes[..p.nodes.len()]
            .iter()
            .map(|row| {
                row.iter()
                    .zip(&values)
                    .fold(I::ZERO, |sum, (&a, &b)| sum + a * b)
            })
            .collect();
        let node_derivatives: Vec<_> = self.nodes[..p.nodes.len()]
            .iter()
            .map(|row| {
                row.iter()
                    .zip(&derivatives)
                    .fold(I::ZERO, |sum, (&a, &b)| sum + a * b)
            })
            .collect();
        evaluate(
            expression,
            &node_values,
            &operator_values,
            states,
            &node_derivatives,
            &operator_derivatives,
        )
    }
    fn range_impl(
        &self,
        expression: &Expression,
        time: I,
        owner: &str,
        event: bool,
    ) -> Result<(I, I), Error> {
        let p = &self.model.program;
        let (node_deps, mut operator_deps) = dependencies(expression, p, owner)?;
        // Ownership was validated in EventModel. The network can contain
        // operators in other instances, so follow each projected node map.
        let state_start = self.model.driven.len();
        let operator_start = state_start + p.states.len();
        for node in node_deps {
            if self.states.is_none()
                && self.nodes[node][state_start..operator_start]
                    .iter()
                    .any(|v| !v.zero())
            {
                return Err(Error::new(
                    "unsupported_cross",
                    "guard voltage depends on event state",
                ));
            }
            for (k, c) in self.nodes[node][operator_start..operator_start + p.operators.len()]
                .iter()
                .enumerate()
            {
                if !c.zero() {
                    operator_deps.insert(k);
                }
            }
        }
        let (mut values, mut derivatives) = self.trajectory.range(time)?;
        let initial: Vec<_> = p.states.iter().map(|s| I::point(s.initial)).collect();
        let states = self.states.unwrap_or(&initial);
        values.extend(states);
        derivatives.extend(vec![I::ZERO; p.states.len()]);
        let mut operator_values = vec![I::ZERO; p.operators.len()];
        let mut operator_derivatives = operator_values.clone();
        let event_values = if event && !operator_deps.is_empty() {
            Some(
                self.operators
                    .ok_or_else(|| {
                        Error::new("unsupported_cross", "guard requires operator history")
                    })?
                    .event_bounds(time.hi, time)?,
            )
        } else {
            None
        };
        for index in operator_deps {
            if let Some(values) = &event_values {
                operator_values[index] = values[index];
                continue;
            }
            (operator_values[index], operator_derivatives[index]) = self
                .operators
                .ok_or_else(|| Error::new("unsupported_cross", "guard requires operator history"))?
                .range(index, time)?;
        }
        values.extend(&operator_values);
        values.push(I::ONE);
        derivatives.extend(&operator_derivatives);
        derivatives.push(I::ZERO);
        let node_values: Vec<_> = self.nodes[..p.nodes.len()]
            .iter()
            .map(|row| {
                row.iter()
                    .zip(&values)
                    .fold(I::ZERO, |sum, (&a, &b)| sum + a * b)
            })
            .collect();
        let node_derivatives: Vec<_> = self.nodes[..p.nodes.len()]
            .iter()
            .map(|row| {
                row.iter()
                    .zip(&derivatives)
                    .fold(I::ZERO, |sum, (&a, &b)| sum + a * b)
            })
            .collect();
        evaluate(
            expression,
            &node_values,
            &operator_values,
            states,
            &node_derivatives,
            &operator_derivatives,
        )
    }
}

pub(crate) fn state_dependencies(expression: &Expression) -> BTreeSet<usize> {
    match expression {
        Expression::State { state } => BTreeSet::from([*state]),
        Expression::Add { left, right } | Expression::Multiply { left, right } => {
            state_dependencies(left)
                .union(&state_dependencies(right))
                .copied()
                .collect()
        }
        Expression::Power { base, .. } => state_dependencies(base),
        _ => BTreeSet::new(),
    }
}
