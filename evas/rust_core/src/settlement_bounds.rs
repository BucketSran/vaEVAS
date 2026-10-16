//! Forward-error enclosure of the original binary64 event IR.
//! Inputs, old states and operator history carry their supplied enclosures.
//! A cached map never freezes a particular operator sample.
use crate::affine_bounds::{affine, eliminate};
use crate::event_conditions::Selection;
use crate::events::EventModel;
use crate::interval::Interval as I;
use crate::ir::{Error, Expression, StateKind};
use std::collections::BTreeMap;

#[path = "filter_budget.rs"]
mod filter_budget;
pub(crate) use filter_budget::FilterBudget;

// Preserve operator history uncertainty as interval coefficients. State and
// voltage columns remain live, so a sampled state can still participate in
// the same-time joint equations. This map is rebuilt for each operator sample.
fn affine_with_operators(
    expr: &Expression,
    p: &crate::ir::Program,
    operators: &[I],
) -> Result<Vec<I>, Error> {
    let n = p.nodes.len() + p.states.len() + p.operators.len();
    let recurse = |e: &Expression| affine_with_operators(e, p, operators);
    match expr {
        Expression::Operator { operator } => {
            let mut result = vec![I::ZERO; n + 1];
            result[n] = operators[*operator];
            Ok(result)
        }
        Expression::Add { left, right } => Ok(recurse(left)?
            .iter()
            .zip(recurse(right)?)
            .map(|(&a, b)| a + b)
            .collect()),
        Expression::Multiply { left, right } => {
            let a = recurse(left)?;
            let b = recurse(right)?;
            if a[..n].iter().any(|v| !v.zero()) && b[..n].iter().any(|v| !v.zero()) {
                return Err(Error::new(
                    "event_accuracy",
                    "cannot certify nonlinear voltage/state product",
                ));
            }
            Ok((0..n)
                .map(|k| a[k] * b[n] + b[k] * a[n])
                .chain([a[n] * b[n]])
                .collect())
        }
        Expression::Divide { left, right } => {
            let a = recurse(left)?;
            let b = recurse(right)?;
            if b[..n].iter().any(|v| !v.zero()) || (b[n].lo <= 0.0 && b[n].hi >= 0.0) {
                return Err(Error::new(
                    "event_accuracy",
                    "cannot certify variable division",
                ));
            }
            Ok(a.iter().map(|&v| v / b[n]).collect())
        }
        _ => affine(expr, p),
    }
}

#[path = "initial_state_invariance.rs"]
mod initial_state_invariance;
pub(crate) use initial_state_invariance::unchanged as unchanged_initial_states;

fn dot(row: &[I], values: &[I]) -> I {
    row.iter()
        .zip(values)
        .fold(I::ZERO, |sum, (&a, &b)| sum + a * b)
}

fn substitute(row: &[I], updates: &[Vec<I>], nodes: usize) -> Vec<I> {
    let mut result = vec![I::ZERO; row.len()];
    result[..nodes].copy_from_slice(&row[..nodes]);
    result[nodes + updates.len()..].copy_from_slice(&row[nodes + updates.len()..]);
    *result.last_mut().unwrap() = *row.last().unwrap();
    for (&coefficient, update) in row[nodes..row.len() - 1].iter().zip(updates) {
        if !coefficient.zero() {
            for (r, &v) in result.iter_mut().zip(update) {
                *r = *r + coefficient * v;
            }
        }
    }
    result
}

pub(crate) struct Bounds {
    nodes: Vec<Vec<I>>,
    states: Vec<Vec<I>>,
}

impl Bounds {
    /// Separate sampling time from the later voltage read. Combining these
    /// two affine maps first would incorrectly cancel q(tau)-u(b).
    #[allow(clippy::too_many_arguments)]
    pub(crate) fn input_root_demand(
        &self,
        observation: &Self,
        model: &EventModel,
        time: f64,
        point_inputs: &[I],
        input_slopes: &[I],
        before: &[I],
        before_values: &[f64],
        sampled: &[I],
        voltages: &[f64],
    ) -> Option<crate::accuracy::Demand> {
        if !model.program.operators.is_empty() {
            return None;
        }
        let parameters: Vec<_> = point_inputs
            .iter()
            .chain(before)
            .copied()
            .chain([I::ONE])
            .collect();
        let fixed_states: Vec<_> = self
            .states
            .iter()
            .map(|row| dot(row, &parameters))
            .collect();
        let fixed: Vec<_> = point_inputs
            .iter()
            .chain(&fixed_states)
            .copied()
            .chain([I::ONE])
            .collect();
        let observed: Vec<_> = point_inputs
            .iter()
            .chain(sampled)
            .copied()
            .chain([I::ONE])
            .collect();
        let n = point_inputs.len();
        // Input feedthrough can change a sampled consumer's relative budget
        // and rounding enclosure later, even without another physical event.
        let future_input_coupling = observation.nodes.iter().any(|row| {
            row[..n].iter().any(|c| !c.zero()) && row[n..n + before.len()].iter().any(|c| !c.zero())
        });
        for (k, (row, &value)) in observation.nodes.iter().zip(voltages).enumerate() {
            let assessment = crate::accuracy::Assessment::new(
                model.program.nodes[k].clone(),
                value,
                dot(row, &observed),
                model.tolerances.absolute,
                model.tolerances.relative,
            );
            if assessment.finite() && assessment.error_bound <= assessment.budget {
                continue;
            }
            let mut sensitivity = I::ZERO;
            let mut inherited = I::ZERO;
            let mut independent = row[..n].iter().all(|c| c.zero());
            for (&a, state) in row[n..n + before.len()].iter().zip(&self.states) {
                if a.zero() {
                    continue;
                }
                independent &= state[..n].iter().all(|c| c.zero());
                // Sum magnitudes: different PWL inputs need not have the same
                // knot or the same slope at every point of this root interval.
                for (&c, &slope) in state[..n].iter().zip(input_slopes) {
                    sensitivity = sensitivity
                        + I::point(a.magnitude())
                            * I::point(c.magnitude())
                            * I::point(slope.magnitude());
                }
                for ((&c, &bound), &nominal) in state[n..n + before.len()]
                    .iter()
                    .zip(before)
                    .zip(before_values)
                {
                    inherited = inherited
                        + I::point(a.magnitude())
                            * I::point(c.magnitude())
                            * I::point((I::point(nominal) - bound).magnitude());
                }
            }
            return crate::accuracy::Demand::new(
                assessment,
                time,
                (I::point(value) - dot(row, &fixed)).magnitude(),
                inherited.hi,
                sensitivity.hi,
                independent,
                future_input_coupling,
            );
        }
        None
    }

    /// Project an independently proved direct-input/held batch without solving
    /// any voltage network or inventing an operator observation.
    pub(crate) fn held_inputs(model: &EventModel, selection: &Selection) -> Result<Self, Error> {
        let p = &model.program;
        let count = p.nodes.len();
        let variables = count + p.states.len() + p.operators.len();
        let driven: Vec<_> = model
            .driven
            .iter()
            .map(|n| p.nodes.iter().position(|v| v == n).unwrap())
            .collect();
        let initial: Vec<_> = (0..p.states.len())
            .map(|k| {
                let mut row = vec![I::ZERO; variables + 1];
                row[count + k] = I::ONE;
                row
            })
            .collect();
        let mut updates = initial.clone();
        for (event, indices) in &selection.actions {
            let assignments = p.events[*event].assignments();
            let mut local = initial.clone();
            for &index in indices {
                let action = &assignments[index];
                local[action.state] = substitute(&affine(&action.rhs, p)?, &local, count);
                updates[action.state] = local[action.state].clone();
            }
        }
        let mut states = Vec::with_capacity(updates.len());
        for row in updates {
            if row[..count]
                .iter()
                .enumerate()
                .any(|(i, x)| i != 0 && !driven.contains(&i) && !x.zero())
                || row[count + p.states.len()..variables]
                    .iter()
                    .any(|x| !x.zero())
            {
                return Err(Error::new(
                    "unsupported_initial_history",
                    "bootstrap state update has unresolved voltage or history dependence",
                ));
            }
            states.push(
                driven
                    .iter()
                    .map(|&i| row[i])
                    .chain(row[count..count + p.states.len()].iter().copied())
                    .chain([row[variables]])
                    .collect(),
            );
        }
        Ok(Self {
            nodes: Vec::new(),
            states,
        })
    }

    /// Only affinity-shape failures permit sampled-coefficient fallback. All
    /// other diagnostics propagate; a failed matrix/accuracy proof is never
    /// interpreted as a cache miss. Examine both factors and all references,
    /// including exact zero terms, with the existing joint-affinity checker.
    pub(crate) fn sample_independent(
        model: &EventModel,
        selection: &Selection,
    ) -> Result<bool, Error> {
        let p = &model.program;
        let assignments = selection.actions.iter().flat_map(|(event, indices)| {
            let actions = p.events[*event].assignments();
            indices
                .iter()
                .map(move |&index| actions[index].rhs.clone())
                .collect::<Vec<_>>()
        });
        for expression in p
            .contributions
            .iter()
            .map(|c| c.rhs.clone())
            .chain(assignments)
        {
            if let Err(error) = affine(&expression, p) {
                if error.kind == "event_resolution"
                    && matches!(
                        error.message.as_str(),
                        "cannot certify jointly affine event expression"
                            | "cannot certify affine variable division"
                            | "cannot bound a polynomial event expression"
                            | "cannot bound an ordinary analog conditional in an event expression"
                    )
                {
                    return Ok(false);
                }
                return Err(error);
            }
        }
        Ok(true)
    }

    pub(crate) fn new(model: &EventModel, selection: &Selection) -> Result<Self, Error> {
        Self::for_program(model, selection, &model.program)
    }

    pub(crate) fn for_program(
        model: &EventModel,
        selection: &Selection,
        p: &crate::ir::Program,
    ) -> Result<Self, Error> {
        Self::for_program_with_operators(model, selection, p, &[])
    }

    pub(crate) fn for_program_with_operators(
        model: &EventModel,
        selection: &Selection,
        p: &crate::ir::Program,
        operators: &[I],
    ) -> Result<Self, Error> {
        crate::diagnostics::counter("certificate_bounds_builds", 1);
        let bind = |expr: &Expression| {
            if operators.is_empty() {
                affine(expr, p)
            } else {
                // Keep linear operator columns and their exact cancellations.
                // Only bilinear coefficients require per-sample interval binding.
                affine(expr, p).or_else(|_| affine_with_operators(expr, p, operators))
            }
        };
        let count = p.nodes.len();
        let parameters = p.states.len() + p.operators.len();
        let variables = count + parameters;
        let driven: Vec<_> = model
            .driven
            .iter()
            .map(|name| p.nodes.iter().position(|n| n == name).unwrap())
            .collect();
        let unknown: Vec<_> = (1..count).filter(|n| !driven.contains(n)).collect();
        let n = unknown.len();
        let width = driven.len() + parameters + 1;
        let initial: Vec<_> = (0..p.states.len())
            .map(|k| {
                let mut row = vec![I::ZERO; variables + 1];
                row[count + k] = I::ONE;
                row
            })
            .collect();
        let mut updates = initial.clone();
        for (event, indices) in &selection.actions {
            let assignments = p.events[*event].assignments();
            let mut local = initial.clone();
            for &index in indices {
                let action = &assignments[index];
                local[action.state] = substitute(&bind(&action.rhs)?, &local, count);
                updates[action.state] = local[action.state].clone();
            }
        }
        let mut grouped = BTreeMap::new();
        for c in &p.contributions {
            let rhs = substitute(&bind(&c.rhs)?, &updates, count);
            let row = grouped.entry(&c.branch).or_insert_with(|| {
                let mut row = vec![I::ZERO; variables + 1];
                row[c.positive] = row[c.positive] + I::ONE;
                row[c.negative] = row[c.negative] - I::ONE;
                row
            });
            for (r, term) in row.iter_mut().zip(rhs) {
                *r = *r - term;
            }
        }
        let rows = grouped
            .values()
            .map(|row: &Vec<I>| {
                unknown
                    .iter()
                    .map(|&k| row[k])
                    .chain(driven.iter().map(|&k| -row[k]))
                    .chain((count..variables).map(|k| -row[k]))
                    .chain([-row[variables]])
                    .collect()
            })
            .collect();
        let rows =
            eliminate(rows, n, width).map_err(|e| Error::new("event_accuracy", e.message))?;
        let mut values = vec![vec![I::ZERO; width]; variables];
        for (k, &node) in driven.iter().enumerate() {
            values[node][k] = I::ONE;
        }
        for state in 0..parameters {
            values[count + state][driven.len() + state] = I::ONE;
        }
        for r in (0..n).rev() {
            for k in 0..width {
                let rest =
                    (r + 1..n).fold(I::ZERO, |sum, c| sum + rows[r][c] * values[unknown[c]][k]);
                values[unknown[r]][k] = rows[r][n + k] - rest;
            }
        }
        let states = updates
            .iter()
            .map(|row| {
                (0..width)
                    .map(|k| {
                        let base = if k == width - 1 {
                            row[variables]
                        } else {
                            I::ZERO
                        };
                        (0..variables).fold(base, |sum, j| sum + row[j] * values[j][k])
                    })
                    .collect::<Vec<_>>()
            })
            .collect::<Vec<_>>();
        values.truncate(count);
        if values.iter().chain(&states).flatten().any(|v| !v.finite()) {
            return Err(Error::new(
                "event_accuracy",
                "nonfinite same-time enclosure",
            ));
        }
        Ok(Self {
            nodes: values,
            states,
        })
    }

    /// Event-time voltage forcing, distinct from the later b observation.
    pub(crate) fn node_enclosures(
        &self,
        inputs: &[I],
        before: &[I],
        operators: &[I],
    ) -> Result<Vec<I>, Error> {
        let parameters: Vec<_> = inputs
            .iter()
            .chain(before)
            .chain(operators)
            .copied()
            .chain([I::ONE])
            .collect();
        let nodes: Vec<_> = self.nodes.iter().map(|row| dot(row, &parameters)).collect();
        if nodes.iter().any(|n| !n.finite()) {
            return Err(Error::new(
                "event_accuracy",
                "nonfinite physical event voltage enclosure",
            ));
        }
        Ok(nodes)
    }

    pub(crate) fn check_states(
        &self,
        model: &EventModel,
        inputs: &[I],
        before: &[I],
        operators: &[I],
        voltages: &[f64],
        states: &[f64],
    ) -> Result<Vec<I>, Error> {
        self.check_selected(model, (inputs, before, operators), voltages, states, false)
            .map(|(states, _)| states)
    }

    pub(crate) fn check_observation(
        &self,
        model: &EventModel,
        inputs: &[I],
        before: &[I],
        operators: &[I],
        voltages: &[f64],
        states: &[f64],
    ) -> Result<(Vec<I>, Vec<I>), Error> {
        self.check_selected(model, (inputs, before, operators), voltages, states, true)
    }

    fn check_selected(
        &self,
        model: &EventModel,
        inputs: (&[I], &[I], &[I]),
        voltages: &[f64],
        states: &[f64],
        check_voltages: bool,
    ) -> Result<(Vec<I>, Vec<I>), Error> {
        let (inputs, before, operators) = inputs;
        let parameters: Vec<_> = inputs
            .iter()
            .copied()
            .chain(before.iter().copied())
            .chain(operators.iter().copied())
            .chain([I::ONE])
            .collect();
        let mut state_bounds = Vec::new();
        let mut voltage_bounds = Vec::new();
        for (rows, actual, voltage) in
            [(&self.nodes, voltages, true), (&self.states, states, false)]
        {
            if voltage && !check_voltages {
                continue;
            }
            for (k, (row, &value)) in rows.iter().zip(actual).enumerate() {
                let exact = row
                    .iter()
                    .zip(&parameters)
                    .fold(I::ZERO, |sum, (&a, &b)| sum + a * b);
                if !voltage {
                    state_bounds.push(exact);
                } else {
                    voltage_bounds.push(exact);
                }
                let integer = !voltage && model.program.states[k].kind == StateKind::Integer;
                let absolute = if voltage {
                    model.tolerances.absolute
                } else {
                    0.0
                };
                let relative = if voltage {
                    model.tolerances.relative
                } else {
                    0.0
                };
                // A lower bound on the requested budget and an upper bound on
                // actual error. Generic real states have no physical unit budget.
                // Keep their finite enclosures for later voltage, history and
                // event consumers; integer states still require zero error.
                let budget = I::point(absolute) + I::point(relative) * I::point(value.abs());
                let error = I::point(value) - exact;
                if !exact.finite()
                    || !error.finite()
                    || !budget.finite()
                    || ((voltage || integer) && error.magnitude() > budget.lo.max(0.0))
                {
                    let name = if voltage {
                        model.program.nodes[k].clone()
                    } else {
                        format!(
                            "{}:{}",
                            model.program.states[k].instance, model.program.states[k].name
                        )
                    };
                    let kind = if model.program.operators.is_empty() {
                        "event_accuracy"
                    } else {
                        "waveform_accuracy"
                    };
                    crate::diagnostics::detail(
                        "accuracy_failure",
                        "rejected",
                        None,
                        &crate::accuracy::Assessment::new(
                            name.clone(),
                            value,
                            exact,
                            absolute,
                            relative,
                        ),
                    );
                    return Err(Error::new(kind,format!(
                        "cannot certify same-time forward error at {name}: bound {:e}, budget {:e}",error.magnitude(),budget.lo)));
                }
            }
        }
        Ok((state_bounds, voltage_bounds))
    }
}

#[cfg(test)]
mod sampled_coefficient_tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn sampled_operator_uncertainty_remains_in_state_coefficient() {
        let origin = json!({"source":"coefficient.va","line":1,"column":1,"instance":"dut"});
        let p: crate::ir::Program = serde_json::from_value(json!({
            "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","y"],
            "states":[{"instance":"dut","name":"q","kind":"real","initial":2}],
            "events":[], "contributions":[],
            "operators":[{"kind":"transition","input":{"op":"state","state":0},
                "delay":0,"rise":1,"fall":1,"origin":origin}]
        }))
        .unwrap();
        let expr = Expression::Multiply {
            left: Box::new(Expression::State { state: 0 }),
            right: Box::new(Expression::Operator { operator: 0 }),
        };
        let row = affine_with_operators(&expr, &p, &[I { lo: 0.4, hi: 0.6 }]).unwrap();
        assert!(row[2].lo <= 0.4 && row[2].hi >= 0.6);
        assert!(row[3].zero());
        let value = dot(
            &row,
            &[I::ZERO, I::ZERO, I::point(2.0), I::point(0.5), I::ONE],
        );
        assert!(value.lo <= 0.8 && value.hi >= 1.2);
        // A nominal-only binding would produce 1 and erase both endpoints.
        assert!(value.lo < 1.0 && value.hi > 1.0);
    }
}
