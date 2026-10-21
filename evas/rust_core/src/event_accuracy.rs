//! Enclose affine guards from the original binary64 IR, including assembly and
//! linear solve roundoff. Held-state projections are rebuilt only after an
//! accepted event changes a relevant state enclosure.
use crate::affine_bounds::affine;
use crate::interval::{equal_products, Interval as I};
use crate::ir::{Error, EventTrigger, Expression, Program};

#[cfg(test)]
use crate::history_consumer_fixture as history_fixture;
#[path = "event_history_projection.rs"]
mod history_projection;

pub(crate) fn unresolved(message: &str) -> Error {
    Error::new("event_resolution", message)
}

pub(crate) struct GuardBounds {
    coefficients: Vec<Vec<I>>,
    state_coefficients: Vec<Vec<I>>,
    operator_coefficients: Vec<Vec<I>>,
    driven_count: usize,
    symbolic: Vec<Option<Expression>>,
    input_nodes: Vec<usize>,
    node_count: usize,
}

impl GuardBounds {
    pub(crate) fn for_model(
        model: &crate::events::EventModel,
        states: Option<&[I]>,
    ) -> Result<Self, Error> {
        if crate::analytic_request::proof_owner(model).is_some() {
            return history_projection::for_model(model, states);
        }
        if model.dc_projection.is_none() {
            return match states {
                Some(states) => {
                    Self::held(&model.program, &model.driven, &model.dynamic_guards, states)
                }
                None => Self::new(&model.program, &model.driven, &model.dynamic_guards),
            };
        }
        let expressions = model
            .triggers
            .iter()
            .enumerate()
            .map(|(i, leaf)| match &leaf.trigger {
                EventTrigger::Cross { guard, .. } if !model.dynamic_guards[i] => Some(guard),
                _ => None,
            })
            .collect::<Vec<_>>();
        Self::project_with_dc(
            &model.program,
            &model.driven,
            &expressions,
            states,
            false,
            false,
            model.dc_projection.as_deref(),
        )
    }

    pub(crate) fn new(
        program: &Program,
        driven: &[String],
        dynamic: &[bool],
    ) -> Result<Self, Error> {
        let mut expressions = Vec::new();
        for event in &program.events {
            for trigger in event.trigger.leaves()? {
                expressions.push(match trigger {
                    EventTrigger::Cross { guard, .. } => {
                        (!dynamic[expressions.len()]).then_some(guard)
                    }
                    EventTrigger::Timer { .. }
                    | EventTrigger::HeldTimer { .. }
                    | EventTrigger::FinalStep { .. }
                    | EventTrigger::InitialStep { .. } => None,
                    EventTrigger::Or { .. } => unreachable!("validated leaves are not OR groups"),
                });
            }
        }
        Self::expressions(program, driven, &expressions)
    }

    pub(crate) fn held(
        program: &Program,
        driven: &[String],
        dynamic: &[bool],
        states: &[I],
    ) -> Result<Self, Error> {
        let mut expressions = Vec::new();
        for event in &program.events {
            for trigger in event.trigger.leaves()? {
                expressions.push(match trigger {
                    EventTrigger::Cross { guard, .. } => {
                        (!dynamic[expressions.len()]).then_some(guard)
                    }
                    _ => None,
                });
            }
        }
        Self::project(program, driven, &expressions, Some(states), false, false)
    }

    /// Project state-independent affine expressions onto the driven inputs.
    pub(crate) fn expressions(
        program: &Program,
        driven: &[String],
        expressions: &[Option<&Expression>],
    ) -> Result<Self, Error> {
        Self::project(program, driven, expressions, None, false, false)
    }

    /// Keep accepted/local held states as certified forcing columns.
    pub(crate) fn stateful_expressions(
        program: &Program,
        driven: &[String],
        expressions: &[Option<&Expression>],
    ) -> Result<Self, Error> {
        Self::project(program, driven, expressions, None, true, false)
    }

    pub(crate) fn stateful_parameters(
        program: &Program,
        driven: &[String],
        expressions: &[Option<&Expression>],
    ) -> Result<Self, Error> {
        Self::project(program, driven, expressions, None, true, true)
    }

    fn project(
        program: &Program,
        driven: &[String],
        expressions: &[Option<&Expression>],
        states: Option<&[I]>,
        keep_states: bool,
        keep_operators: bool,
    ) -> Result<Self, Error> {
        Self::project_with_dc(
            program,
            driven,
            expressions,
            states,
            keep_states,
            keep_operators,
            None,
        )
    }
    #[allow(clippy::too_many_arguments)]
    pub(crate) fn project_with_dc(
        program: &Program,
        driven: &[String],
        expressions: &[Option<&Expression>],
        states: Option<&[I]>,
        keep_states: bool,
        keep_operators: bool,
        dc: Option<&crate::dc_projection::DcProjection>,
    ) -> Result<Self, Error> {
        let count = program.nodes.len();
        let variables = count + program.states.len() + program.operators.len();
        let width = driven.len() + program.states.len() + program.operators.len() + 1;
        // Direct driven/state predicates do not need unrelated output equations.
        // In particular an analog Select elsewhere cannot change a supplied input.
        let driven_nodes: Vec<_> = driven
            .iter()
            .map(|name| {
                program
                    .nodes
                    .iter()
                    .position(|node| node == name)
                    .ok_or_else(|| Error::new("invalid_inputs", "unknown driven node"))
            })
            .collect::<Result<_, _>>()?;
        let direct = expressions
            .iter()
            .flatten()
            .map(|expression| affine(expression, program))
            .collect::<Result<Vec<_>, _>>()?
            .iter()
            .all(|row| (1..count).all(|node| row[node].zero() || driven_nodes.contains(&node)));
        // A forced voltage alias can have a nonzero reference. Substitute only
        // a proven acyclic, single-branch relation and then recheck affinity.
        // Unrelated nonlinear outputs need not enter this guard projection.
        let expanded = (!direct)
            .then(|| {
                expressions
                    .iter()
                    .map(|expression| {
                        expression
                            .map(|expression| {
                                let expanded =
                                    crate::causal_voltage::expand(expression, program, driven)?;
                                let row = affine(&expanded, program)?;
                                if (1..count)
                                    .any(|node| !row[node].zero() && !driven_nodes.contains(&node))
                                {
                                    return Err(unresolved("unresolved forced guard voltage"));
                                }
                                Ok(expanded)
                            })
                            .transpose()
                    })
                    .collect::<Result<Vec<_>, Error>>()
                    .ok()
            })
            .flatten();
        let direct = direct || expanded.is_some();
        let symbolic = if !direct
            && keep_states
            && keep_operators
            && program
                .contributions
                .iter()
                .any(|c| crate::analog::has_select(&c.rhs))
        {
            expressions
                .iter()
                .map(|e| {
                    e.map(|e| crate::causal_voltage::expand(e, program, driven))
                        .transpose()
                })
                .collect::<Result<Vec<_>, _>>()?
        } else {
            vec![None; expressions.len()]
        };
        let symbolic_mode = symbolic.iter().any(Option::is_some);
        let nodes = if direct || symbolic_mode {
            let mut nodes = vec![vec![I::ZERO; width]; variables];
            for (column, &node) in driven_nodes.iter().enumerate() {
                nodes[node][column] = I::ONE;
            }
            for index in 0..program.states.len() + program.operators.len() {
                nodes[count + index][driven.len() + index] = I::ONE;
            }
            nodes
        } else {
            crate::affine_bounds::node_map_with_dc(program, driven, dc)?
        };
        validate_projection(&nodes, variables, width)?;
        let mut coefficients = expressions
            .iter()
            .enumerate()
            .map(|(index, expression)| {
                // Keep rows aligned with event indices; timer has no guard.
                let Some(guard) = expression.filter(|_| !symbolic_mode) else {
                    return Ok(vec![I::ZERO; width]);
                };
                let guard = expanded
                    .as_ref()
                    .and_then(|expressions| expressions[index].as_ref())
                    .unwrap_or(guard);
                let guard = affine(guard, program)?;
                project_row(&guard, &nodes, width)
            })
            .collect::<Result<Vec<_>, Error>>()?;
        let state_coefficients = coefficients
            .iter()
            .map(|row| row[driven.len()..driven.len() + program.states.len()].to_vec())
            .collect();
        if let Some(states) = states {
            if states.len() != program.states.len() {
                return Err(Error::new(
                    "invalid_ir",
                    "held state bounds length mismatch",
                ));
            }
            for row in &mut coefficients {
                for (index, state) in states.iter().enumerate() {
                    row[width - 1] = row[width - 1] + row[driven.len() + index] * *state;
                    row[driven.len() + index] = I::ZERO;
                }
            }
        }
        if coefficients.iter().flatten().any(|x| !x.finite()) {
            return Err(unresolved("nonfinite event trajectory bounds"));
        }
        if !keep_operators
            && coefficients.iter().any(|row| {
                row[driven.len() + if keep_states { program.states.len() } else { 0 }..width - 1]
                    .iter()
                    .any(|x| !x.zero())
            })
        {
            return Err(unresolved(
                "cannot certify cross guard independence from event state",
            ));
        }
        let operator_coefficients = coefficients
            .iter()
            .map(|row| row[driven.len() + program.states.len()..width - 1].to_vec())
            .collect();
        Ok(Self {
            coefficients,
            operator_coefficients,
            state_coefficients,
            driven_count: driven.len(),
            symbolic,
            input_nodes: driven_nodes,
            node_count: count,
        })
    }

    /// Every voltage here is a forcing value certified by the physical stage.
    /// No voltage equation is solved or inferred by this projection.
    pub(crate) fn passive_program(program: &Program) -> (Program, Vec<String>) {
        let mut projected = program.clone();
        projected.contributions.clear();
        // Preserve original global operator columns for every trigger leaf.
        // Operator guards cannot project onto node/state forcing and obtain
        // no passive zero-set match. Dropping these columns can alias op0 to
        // the constant or make later operator IDs index outside the row.
        // This Program is only an expression projection, never a history.

        projected.step_bounds.clear();
        let driven = program.nodes[1..].to_vec();
        (projected, driven)
    }

    pub(crate) fn changed_by(&self, before: &[I], after: &[I]) -> Vec<bool> {
        self.state_coefficients
            .iter()
            .map(|row| {
                row.iter()
                    .enumerate()
                    .any(|(i, c)| !c.zero() && before[i] != after[i])
            })
            .collect()
    }

    /// Only a proven zero coefficient permits ignoring an input breakpoint.
    pub(crate) fn active_inputs_history(
        &self,
        expression: usize,
        w: &crate::transition_source_plan::Work,
    ) -> Result<Vec<usize>, Error> {
        w.debit(2, 0)?;
        let mut out = Vec::new();
        for (i, coefficient) in self.coefficients[expression][..self.driven_count]
            .iter()
            .enumerate()
        {
            w.step()?;
            if !coefficient.zero() {
                crate::history_storage::push_vec(&mut out, i, w)?
            }
        }
        Ok(out)
    }
    pub(crate) fn active_inputs(&self, expression: usize) -> Vec<usize> {
        self.coefficients[expression][..self.driven_count]
            .iter()
            .enumerate()
            .filter_map(|(i, coefficient)| (!coefficient.zero()).then_some(i))
            .collect()
    }

    /// Reuse the certified circuit projection as an exact source expression.
    /// A non-point coefficient or remaining state/operator column cannot be
    /// rounded into the unique physical curve required for root provenance.
    pub(crate) fn exact_input_expression_history(
        &self,
        expression: usize,
        w: &crate::transition_source_plan::Work,
    ) -> Result<Option<Expression>, Error> {
        w.debit(2, 0)?;
        w.step()?;
        if self.symbolic[expression].is_some() {
            return Ok(None);
        }
        let row = &self.coefficients[expression];
        for v in row {
            w.step()?;
            if v.lo != v.hi {
                return Ok(None);
            }
        }
        for v in &row[self.driven_count..row.len() - 1] {
            w.step()?;
            if !v.zero() {
                return Ok(None);
            }
        }
        let mut terms = Vec::new();
        for (v, &node) in row[..self.driven_count].iter().zip(&self.input_nodes) {
            w.step()?;
            if !v.zero() {
                crate::history_storage::push_vec(
                    &mut terms,
                    crate::ir::Term {
                        node,
                        coefficient: v.lo,
                    },
                    w,
                )?
            }
        }
        Ok(row.last().map(|last| Expression::Affine {
            constant: last.lo,
            terms,
        }))
    }
    pub(crate) fn value_history(
        &self,
        expression: usize,
        inputs: &[I],
        w: &crate::transition_source_plan::Work,
    ) -> Result<I, Error> {
        w.debit(2, 0)?;
        w.step()?;
        let row = &self.coefficients[expression];
        let mut value = *row.last().unwrap();
        for (&a, &v) in row.iter().zip(inputs) {
            w.step()?;
            value = value + a * v
        }
        Ok(value)
    }
    pub(crate) fn exact_input_expression(&self, expression: usize) -> Option<Expression> {
        if self.symbolic[expression].is_some() {
            return None;
        }
        let row = &self.coefficients[expression];
        if row.iter().any(|v| v.lo != v.hi)
            || row[self.driven_count..row.len() - 1]
                .iter()
                .any(|v| !v.zero())
        {
            return None;
        }
        Some(Expression::Affine {
            constant: row.last()?.lo,
            terms: row[..self.driven_count]
                .iter()
                .zip(&self.input_nodes)
                .filter(|(v, _)| !v.zero())
                .map(|(v, &node)| crate::ir::Term {
                    node,
                    coefficient: v.lo,
                })
                .collect(),
        })
    }

    pub(crate) fn values(&self, inputs: &[I]) -> Vec<I> {
        self.coefficients
            .iter()
            .map(|row| {
                row.iter()
                    .zip(inputs)
                    .fold(*row.last().unwrap(), |sum, (&a, &v)| sum + a * v)
            })
            .collect()
    }

    pub(crate) fn value_with_states(&self, expression: usize, inputs: &[I], states: &[I]) -> I {
        let row = &self.coefficients[expression];
        row[..self.driven_count]
            .iter()
            .zip(inputs)
            .chain(self.state_coefficients[expression].iter().zip(states))
            .fold(*row.last().unwrap(), |sum, (&coefficient, &value)| {
                sum + coefficient * value
            })
    }

    fn operator_value(&self, expression: usize, operators: &[I]) -> I {
        self.operator_coefficients[expression]
            .iter()
            .enumerate()
            .filter(|(_, v)| !v.zero())
            .fold(I::ZERO, |sum, (k, &coefficient)| {
                sum + coefficient
                    * operators.get(k).copied().unwrap_or(I {
                        lo: f64::NEG_INFINITY,
                        hi: f64::INFINITY,
                    })
            })
    }
    pub(crate) fn values_with_operators(&self, inputs: &[I], operators: &[I]) -> Vec<I> {
        self.values(inputs)
            .into_iter()
            .enumerate()
            .map(|(k, v)| v + self.operator_value(k, operators))
            .collect()
    }
    pub(crate) fn value_with_parameters(
        &self,
        expression: usize,
        inputs: &[I],
        states: &[I],
        operators: &[I],
    ) -> I {
        self.value_with_states(expression, inputs, states)
            + self.operator_value(expression, operators)
    }

    pub(crate) fn same_zero_set_history(
        &self,
        first: usize,
        second: usize,
        w: &crate::transition_source_plan::Work,
    ) -> Result<bool, Error> {
        w.debit(2, 0)?;
        w.debit(2, 4)?;
        if self.symbolic[first].is_some() || self.symbolic[second].is_some() {
            return Ok(false);
        }
        let a = &self.coefficients[first];
        let b = &self.coefficients[second];
        for v in a.iter().chain(b) {
            w.step()?;
            if v.lo != v.hi {
                return Ok(false);
            }
        }
        let mut pivot = None;
        for (i, v) in a.iter().enumerate() {
            w.step()?;
            if !v.zero() {
                pivot = Some(i);
                break;
            }
        }
        let Some(pivot) = pivot else { return Ok(false) };
        w.step()?;
        if b[pivot].zero() {
            return Ok(false);
        }
        for (x, y) in a.iter().zip(b) {
            w.debit(2, crate::exact_time::PAIR_SIGN_FEE)?;
            if !equal_products(x.lo, b[pivot].lo, y.lo, a[pivot].lo) {
                return Ok(false);
            }
        }
        Ok(true)
    }
    /// Sign of k when expression `second` is exactly k times `first`.
    pub(crate) fn zero_set_ratio_sign(&self, first: usize, second: usize) -> Option<i8> {
        if !self.same_zero_set(first, second) {
            return None;
        }
        let a = &self.coefficients[first];
        let b = &self.coefficients[second];
        let pivot = a.iter().position(|v| !v.zero())?;
        let ratio = a[pivot].sign()? * b[pivot].sign()?;
        (ratio != 0).then_some(ratio)
    }
    pub(crate) fn same_zero_set(&self, first: usize, second: usize) -> bool {
        if self.symbolic[first].is_some() || self.symbolic[second].is_some() {
            return false;
        }
        let a = &self.coefficients[first];
        let b = &self.coefficients[second];
        if a.iter().chain(b).any(|v| v.lo != v.hi) {
            return false;
        }
        let Some(pivot) = a.iter().position(|v| !v.zero()) else {
            return false;
        };
        !b[pivot].zero()
            && a.iter()
                .zip(b)
                .all(|(x, y)| equal_products(x.lo, b[pivot].lo, y.lo, a[pivot].lo))
    }

    pub(crate) fn symbolic(&self, expression: usize) -> bool {
        self.symbolic[expression].is_some()
    }

    /// No operator column: the value depends only on inputs, states and constants.
    pub(crate) fn operator_free(&self, expression: usize) -> bool {
        self.symbolic[expression].is_none()
            && self.operator_coefficients[expression]
                .iter()
                .all(|v| v.zero())
    }

    /// Exactly zero input and operator columns: between events the value can
    /// change only through its state columns.
    pub(crate) fn input_free(&self, expression: usize) -> bool {
        self.operator_free(expression)
            && self.coefficients[expression][..self.driven_count]
                .iter()
                .all(|v| v.zero())
    }

    pub(crate) fn checked_value(
        &self,
        expression: usize,
        inputs: &[I],
        states: &[I],
        operators: &[I],
    ) -> Result<I, Error> {
        if let Some(e) = &self.symbolic[expression] {
            let mut nodes = vec![I::ZERO; self.node_count];
            for (&n, &v) in self.input_nodes.iter().zip(inputs) {
                nodes[n] = v;
            }
            crate::causal_voltage::bounds(e, &nodes, states, operators)
        } else {
            Ok(self.value_with_parameters(expression, inputs, states, operators))
        }
    }
}

pub(crate) fn validate_projection(
    nodes: &[Vec<I>],
    variables: usize,
    width: usize,
) -> Result<(), Error> {
    if width == 0 || nodes.len() != variables || nodes.iter().any(|row| row.len() != width) {
        return Err(Error::new(
            "invalid_ir",
            "event projection dimensions mismatch",
        ));
    }
    if nodes.iter().flatten().any(|value| !value.finite()) {
        return Err(unresolved("nonfinite event trajectory bounds"));
    }
    Ok(())
}

pub(crate) fn project_row(guard: &[I], nodes: &[Vec<I>], width: usize) -> Result<Vec<I>, Error> {
    if guard.len() != nodes.len() + 1 {
        return Err(Error::new("invalid_ir", "event guard dimensions mismatch"));
    }
    if guard.iter().any(|value| !value.finite()) {
        return Err(unresolved("nonfinite event trajectory bounds"));
    }
    // The caller validates the complete node map; validate every original guard
    // coefficient before omitting products with either finite exact-zero factor.
    // Keep the original j order of every remaining operation. With a +0 base,
    // adding a finite exact-zero product cannot change either endpoint's bits.
    // A -0 constant is the exception: use the original dense fold for that one
    // column, preserving its signed-zero result as well.
    let terms: Vec<_> = guard[..nodes.len()]
        .iter()
        .enumerate()
        .filter(|(_, value)| !value.zero())
        .collect();
    Ok((0..width)
        .map(|column| {
            let base = if column == width - 1 {
                guard[nodes.len()]
            } else {
                I::ZERO
            };
            if [base.lo, base.hi]
                .iter()
                .any(|value| *value == 0.0 && value.is_sign_negative())
            {
                (0..nodes.len()).fold(base, |sum, j| sum + guard[j] * nodes[j][column])
            } else {
                let sum = terms.iter().fold(base, |sum, &(j, value)| {
                    let node = nodes[j][column];
                    if node.zero() {
                        sum
                    } else {
                        sum + *value * node
                    }
                });
                // Overflow may produce a half-infinite interval which a later
                // dense zero addition normalizes to WHOLE. Keep the original
                // fold on this rejected path too, including endpoint bits.
                if !sum.finite() {
                    (0..nodes.len()).fold(base, |sum, j| sum + guard[j] * nodes[j][column])
                } else {
                    sum
                }
            }
        })
        .collect())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ir::Expression;
    use proptest::prelude::*;
    #[test]
    fn bookkeeping_r2_direct_projection_matches_legacy_bits() {
        let input =
            serde_json::json!({"op":"affine","constant":0.,"terms":[{"node":1,"coefficient":1.}]});
        let constant = |v: f64| serde_json::json!({"op":"affine","constant":v,"terms":[]});
        for guard in [
            serde_json::json!({"op":"add","left":input,"right":constant(-0.375)}),
            serde_json::json!({"op":"divide","left":input,"right":constant(3.)}),
            constant(-0.),
        ] {
            let mut value = history_fixture::fixture();
            value["program"]["events"][1]["trigger"] = serde_json::json!({"kind":"cross","guard":guard,"direction":1,"time_tolerance":1e-10,"expression_tolerance":1e-10});
            let request: crate::ir::Request = serde_json::from_value(value).unwrap();
            let trajectory =
                crate::pwl::Trajectory::new(request.transient.unwrap(), request.driven.len())
                    .unwrap();
            let model = crate::events::EventModel::new_with_trajectory(
                request.program,
                request.driven,
                request.tolerances,
                Some(&trajectory),
            )
            .unwrap();
            let states: Vec<_> = model.initial().into_iter().map(I::point).collect();
            for held in [false, true] {
                let legacy = if held {
                    GuardBounds::held(
                        &model.program,
                        &model.driven,
                        &model.dynamic_guards,
                        &states,
                    )
                } else {
                    GuardBounds::new(&model.program, &model.driven, &model.dynamic_guards)
                }
                .unwrap();
                let paid =
                    GuardBounds::for_model(&model, held.then_some(states.as_slice())).unwrap();
                let bits = |rows: &Vec<Vec<I>>| {
                    rows.iter()
                        .map(|row| {
                            row.iter()
                                .map(|v| (v.lo.to_bits(), v.hi.to_bits()))
                                .collect::<Vec<_>>()
                        })
                        .collect::<Vec<_>>()
                };
                assert_eq!(bits(&paid.coefficients), bits(&legacy.coefficients));
                assert_eq!(
                    bits(&paid.state_coefficients),
                    bits(&legacy.state_coefficients)
                );
                assert_eq!(
                    bits(&paid.operator_coefficients),
                    bits(&legacy.operator_coefficients)
                );
                assert_eq!(paid.input_nodes, legacy.input_nodes);
                assert_eq!(paid.node_count, legacy.node_count);
                assert_eq!(paid.driven_count, legacy.driven_count);
                assert_eq!(paid.symbolic, legacy.symbolic);
            }
        }
    }

    fn same_projection(guard: &[I], nodes: &[Vec<I>], width: usize) {
        validate_projection(nodes, guard.len() - 1, width).unwrap();
        let sparse = project_row(guard, nodes, width).unwrap();
        for (k, actual) in sparse.iter().enumerate() {
            let base = if k == width - 1 {
                guard[nodes.len()]
            } else {
                I::ZERO
            };
            let dense = (0..nodes.len()).fold(base, |sum, j| sum + guard[j] * nodes[j][k]);
            assert_eq!(
                (actual.lo.to_bits(), actual.hi.to_bits()),
                (dense.lo.to_bits(), dense.hi.to_bits())
            );
        }
    }

    #[test]
    fn sparse_projection_preserves_signed_zero_and_rejects_invalid_inputs() {
        let zero = [I::ZERO, I::point(-0.0), I { lo: -0.0, hi: 0.0 }];
        for a in zero {
            for b in zero {
                same_projection(
                    &[a, I::ONE, -I::ONE, b],
                    &[vec![b, I::ONE], vec![a, I::ONE], vec![a, I::ONE]],
                    2,
                );
            }
        }
        assert!(validate_projection(&[vec![I::ONE]], 2, 1).is_err());
        assert!(validate_projection(&[vec![I::ONE]], 1, 2).is_err());
        assert!(validate_projection(&[], 0, 0).is_err());
        assert!(validate_projection(&[vec![I::point(f64::INFINITY)]], 1, 1).is_err());
        assert!(project_row(&[I::ZERO], &[vec![I::ONE]], 1).is_err());
        assert!(project_row(&[I::ZERO, I::point(f64::NAN)], &[vec![I::ONE]], 1).is_err());
    }

    #[test]
    fn sparse_projection_preserves_dense_nonfinite_normalization() {
        same_projection(
            &[
                I {
                    lo: 0.0,
                    hi: f64::MAX,
                },
                I::ZERO,
                I {
                    lo: 0.0,
                    hi: f64::MAX,
                },
            ],
            &[vec![I::ONE], vec![I::ONE]],
            1,
        );
    }

    #[test]
    fn sparse_projection_work_tracks_nonzero_guard_terms() {
        let variables = 1024;
        let width = variables + 1;
        let mut nodes = vec![vec![I::ZERO; width]; variables];
        for (j, row) in nodes.iter_mut().enumerate() {
            row[j] = I::ONE;
        }
        let mut guard = vec![I::ZERO; variables + 1];
        guard[513] = I::ONE;
        crate::interval::zero_product_tests::reset_work();
        let projected = project_row(&guard, &nodes, width).unwrap();
        let (products, _) = crate::interval::zero_product_tests::work();
        assert_eq!(products, 4);
        assert_eq!(projected[513], I::ONE);
        assert_eq!(projected.iter().filter(|x| !x.zero()).count(), 1);
    }

    #[test]
    fn sparse_projection_skips_zero_node_factors_in_dense_guard() {
        let variables = 64;
        let width = variables + 1;
        let mut nodes = vec![vec![I::ZERO; width]; variables];
        for (j, row) in nodes.iter_mut().enumerate() {
            row[j] = I::ONE;
        }
        let mut guard = vec![I::ONE; variables + 1];
        guard[variables] = I::ZERO;
        same_projection(&guard, &nodes, width);
        crate::interval::zero_product_tests::reset_work();
        project_row(&guard, &nodes, width).unwrap();
        let (products, _) = crate::interval::zero_product_tests::work();
        assert_eq!(products, 4 * variables);
    }

    proptest! {
        #![proptest_config(ProptestConfig::with_cases(1024))]
        #[test]
        fn sparse_projection_matches_original_dense_bits(
            values in prop::collection::vec(any::<u64>().prop_map(f64::from_bits).prop_filter("finite", |v| v.is_finite()), 48),
            zeros in prop::collection::vec(any::<bool>(), 6),
            node_zeros in prop::collection::vec(any::<bool>(), 12),
        ) {
            let interval = |a: f64, b: f64| I {lo:a.min(b), hi:a.max(b)};
            let mut guard: Vec<_> = (0..6).map(|j| if zeros[j] {I::ZERO} else {interval(values[j*2], values[j*2+1])}).collect();
            guard.push(interval(values[12], values[13]));
            let nodes: Vec<_> = (0..6).map(|j| (0..2).map(|k| if node_zeros[j*2+k] {I::ZERO} else {interval(values[14+j*4+k*2], values[15+j*4+k*2])}).collect()).collect();
            same_projection(&guard, &nodes, 2);
        }
    }

    #[test]
    fn interval_conversion_rejects_products_with_uncertain_variable_coefficients() {
        let program: Program = serde_json::from_value(serde_json::json!({
            "schema_version": crate::ir::SCHEMA_VERSION,
            "nodes": ["0", "u"], "contributions": []
        }))
        .unwrap();
        let leaf = |coefficient| Expression::Affine {
            constant: 0.0,
            terms: vec![crate::ir::Term {
                node: 1,
                coefficient,
            }],
        };
        let expression = Expression::Multiply {
            left: Box::new(Expression::Add {
                left: Box::new(Expression::Add {
                    left: Box::new(leaf(1.0)),
                    right: Box::new(leaf(1e-16)),
                }),
                right: Box::new(leaf(-1.0)),
            }),
            right: Box::new(leaf(1e16)),
        };
        assert_eq!(
            affine(&expression, &program).unwrap_err().kind,
            "event_resolution"
        );
    }
}
