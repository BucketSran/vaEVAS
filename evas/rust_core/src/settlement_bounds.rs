//! Forward-error enclosure of the original binary64 event IR.
//! Inputs, old states and operator history carry their supplied enclosures.
//! Linear operator forcing stays live; bound coefficients retain their sample key.
use crate::affine_bounds::{affine, eliminate};
use crate::event_conditions::Selection;
use crate::events::EventModel;
use crate::interval::Interval as I;
use crate::ir::{Error, Expression, StateKind};
use std::cell::RefCell;
use std::collections::{BTreeMap, BTreeSet};

#[path = "filter_budget.rs"]
mod filter_budget;
pub(crate) use filter_budget::FilterBudget;

// Preserve operator history uncertainty as interval coefficients. State and
// voltage columns remain live for the same-time joint equations. Reuse requires
// identical endpoint bits for every operator sample read by this binding.
fn affine_with_operators(
    expr: &Expression,
    p: &crate::ir::Program,
    operators: &[I],
    bindings: &RefCell<BTreeSet<(usize, u64, u64)>>,
) -> Result<Vec<I>, Error> {
    let n = p.nodes.len() + p.states.len() + p.operators.len();
    let recurse = |e: &Expression| affine_with_operators(e, p, operators, bindings);
    match expr {
        Expression::Operator { operator } => {
            let mut result = vec![I::ZERO; n + 1];
            let sample = operators[*operator];
            bindings
                .borrow_mut()
                .insert((*operator, sample.lo.to_bits(), sample.hi.to_bits()));
            result[n] = sample;
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
    let dense = || {
        row.iter()
            .zip(values)
            .fold(I::ZERO, |sum, (&a, &b)| sum + a * b)
    };
    let mut sum = I::ZERO;
    for (&a, &b) in row.iter().zip(values) {
        #[cfg(test)]
        projection_work::add(1, 0);
        // Even an omitted zero coefficient must not hide nonfinite forcing.
        if !a.finite() || !b.finite() {
            return dense();
        }
        if !a.zero() {
            sum = sum + a * b;
        }
    }
    // The +0 base preserves signed-zero results when finite zero products are
    // omitted. Overflow needs the original zero additions and normalization.
    if sum.finite() {
        sum
    } else {
        dense()
    }
}

// Some records a complete finite-coefficient check and ascending nonzero
// indices for an immutable row. Dense/nonfinite rows keep the original dot.
fn nonzero_indices(row: &[I]) -> Option<Vec<usize>> {
    if row.iter().any(|v| !v.finite()) || row.iter().all(|v| !v.zero()) {
        None
    } else {
        Some(
            row.iter()
                .enumerate()
                .filter_map(|(k, v)| (!v.zero()).then_some(k))
                .collect(),
        )
    }
}

fn prepared_dot(row: &[I], indices: Option<&[usize]>, values: &[I], values_finite: bool) -> I {
    if let Some(indices) = indices.filter(|_| values_finite && row.len() == values.len()) {
        let sum = indices
            .iter()
            .fold(I::ZERO, |sum, &k| sum + row[k] * values[k]);
        if sum.finite() {
            return sum;
        }
    }
    // Preserve the original zip tails, zero/nonfinite products and overflow
    // normalization instead of rejecting at the eligibility check.
    dot(row, values)
}

#[cfg(test)]
mod projection_work {
    use std::cell::Cell;
    thread_local! { static WORK: Cell<(usize, usize)> = const { Cell::new((0, 0)) }; }
    thread_local! { static STATE_ROWS: Cell<usize> = const { Cell::new(0) }; }
    pub(super) fn state_row() {
        STATE_ROWS.with(|work| work.set(work.get() + 1));
    }
    pub(super) fn state_rows() -> usize {
        STATE_ROWS.with(Cell::get)
    }
    pub(super) fn add(pairs: usize, parameters: usize) {
        WORK.with(|work| {
            let (p, v) = work.get();
            work.set((p + pairs, v + parameters));
        });
    }
    pub(super) fn reset() {
        WORK.with(|work| work.set((0, 0)));
        STATE_ROWS.with(|work| work.set(0));
    }
    pub(super) fn get() -> (usize, usize) {
        WORK.with(Cell::get)
    }
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
    node_nonzero: Vec<Option<Vec<usize>>>,
    state_nonzero: Vec<Option<Vec<usize>>>,
    operator_bindings: Vec<(usize, u64, u64)>,
}

impl Bounds {
    fn from_rows(
        nodes: Vec<Vec<I>>,
        states: Vec<Vec<I>>,
        operator_bindings: Vec<(usize, u64, u64)>,
    ) -> Self {
        Self {
            node_nonzero: nodes.iter().map(|row| nonzero_indices(row)).collect(),
            state_nonzero: states.iter().map(|row| nonzero_indices(row)).collect(),
            nodes,
            states,
            operator_bindings,
        }
    }

    pub(crate) fn matches_operator_bindings(&self, operators: &[I]) -> bool {
        self.operator_bindings.iter().all(|&(operator, lo, hi)| {
            operators
                .get(operator)
                .is_some_and(|sample| sample.lo.to_bits() == lo && sample.hi.to_bits() == hi)
        })
    }

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
        Ok(Self::from_rows(Vec::new(), states, Vec::new()))
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
        let bindings = RefCell::new(BTreeSet::new());
        let bind = |expr: &Expression| {
            if operators.is_empty() {
                affine(expr, p)
            } else {
                // Keep linear operator columns and their exact cancellations.
                // Only bilinear coefficients require per-sample interval binding.
                affine(expr, p).or_else(|_| affine_with_operators(expr, p, operators, &bindings))
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
        let mut written = vec![false; p.states.len()];
        for (event, indices) in &selection.actions {
            let assignments = p.events[*event].assignments();
            let mut local = initial.clone();
            for &index in indices {
                let action = &assignments[index];
                local[action.state] = substitute(&bind(&action.rhs)?, &local, count);
                updates[action.state] = local[action.state].clone();
                written[action.state] = true;
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
        crate::event_accuracy::validate_projection(&values, variables, width)
            .map_err(|_| Error::new("event_accuracy", "nonfinite same-time enclosure"))?;
        let states = updates
            .iter()
            .enumerate()
            .map(|(state, row)| {
                if !written[state] {
                    // No selected write touched this exact +0/+1 initial row.
                    // The complete map above is finite; its corresponding
                    // state forcing row is the same canonical unit projection.
                    return Ok(values[count + state].clone());
                }
                #[cfg(test)]
                projection_work::state_row();
                crate::event_accuracy::project_row(row, &values, width)
                    .map_err(|_| Error::new("event_accuracy", "nonfinite same-time enclosure"))
            })
            .collect::<Result<Vec<_>, _>>()?;
        values.truncate(count);
        if values.iter().chain(&states).flatten().any(|v| !v.finite()) {
            return Err(Error::new(
                "event_accuracy",
                "nonfinite same-time enclosure",
            ));
        }
        Ok(Self::from_rows(
            values,
            states,
            bindings.into_inner().into_iter().collect(),
        ))
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
        let parameters_finite = parameters.iter().all(|value| {
            #[cfg(test)]
            projection_work::add(0, 1);
            value.finite()
        });
        for (rows, nonzero, actual, voltage) in [
            (&self.nodes, &self.node_nonzero, voltages, true),
            (&self.states, &self.state_nonzero, states, false),
        ] {
            if voltage && !check_voltages {
                continue;
            }
            for (k, (row, &value)) in rows.iter().zip(actual).enumerate() {
                let exact = prepared_dot(
                    row,
                    nonzero.get(k).and_then(|v| v.as_deref()),
                    &parameters,
                    parameters_finite,
                );
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

    fn identity_projection_fixture(count: usize) -> EventModel {
        let origin = json!({"source":"identity.va","line":1,"column":1,"instance":"M"});
        let states: Vec<_> = (0..count)
            .map(|k| json!({"instance":"M","name":format!("q{k}"),"kind":"real","initial":0}))
            .collect();
        let p = serde_json::from_value(json!({
            "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","y","u","v"],"states":states,
            "operators":[{"kind":"transition","input":{"op":"affine","constant":1,"terms":[]},
                "delay":0,"rise":1,"fall":1,"origin":origin},
                {"kind":"transition","input":{"op":"affine","constant":1,"terms":[]},
                "delay":0,"rise":1,"fall":1,"origin":origin}],
            "events":[{"origin":origin,"trigger":{"kind":"timer","start":1,"period":0,"enabled":true,"time_tolerance":0.001},
                "body":[{"kind":"assign","state":0,"rhs":{"op":"add","left":{"op":"state","state":0},"right":{"op":"affine","constant":1,"terms":[]}}},
                    {"kind":"assign","state":0,"rhs":{"op":"add","left":{"op":"state","state":0},"right":{"op":"affine","constant":-1,"terms":[]}}},
                    {"kind":"assign","state":1,"rhs":{"op":"affine","constant":0,"terms":[{"node":1,"coefficient":1}]}}]}],
            "contributions":[{"origin":origin,"branch":{"instance":"M","local_positive":"out","local_negative":"ref","kind":"voltage"},
                "positive":1,"negative":0,"rhs":{"op":"add","left":{"op":"multiply","left":{"op":"state","state":0},"right":{"op":"operator","operator":0}},
                    "right":{"op":"add","left":{"op":"multiply","left":{"op":"affine","constant":0.5,"terms":[]},"right":{"op":"state","state":1}},
                        "right":{"op":"affine","constant":0,"terms":[{"node":3,"coefficient":1}]}}}}]
        })).unwrap();
        EventModel::new(
            p,
            vec!["v".into(), "u".into()],
            crate::ir::Tolerances::default(),
        )
        .unwrap()
    }

    fn original_dense_state_rows(
        model: &EventModel,
        selection: &Selection,
        bounds: &Bounds,
    ) -> Vec<Vec<I>> {
        let p = &model.program;
        let count = p.nodes.len();
        let parameters = p.states.len() + p.operators.len();
        let variables = count + parameters;
        let width = model.driven.len() + parameters + 1;
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
                local[action.state] = substitute(&affine(&action.rhs, p).unwrap(), &local, count);
                updates[action.state] = local[action.state].clone();
            }
        }
        let mut values = bounds.nodes.clone();
        for k in 0..parameters {
            let mut row = vec![I::ZERO; width];
            row[model.driven.len() + k] = I::ONE;
            values.push(row);
        }
        updates
            .iter()
            .map(|row| {
                (0..width)
                    .map(|column| {
                        let base = if column == width - 1 {
                            row[variables]
                        } else {
                            I::ZERO
                        };
                        (0..variables).fold(base, |sum, j| sum + row[j] * values[j][column])
                    })
                    .collect()
            })
            .collect()
    }

    #[test]
    fn unchanged_state_projection_work_does_not_scale_with_held_state_rows() {
        let model = identity_projection_fixture(64);
        for operator in [I::ZERO, I::point(0.25), I { lo: 0.24, hi: 0.26 }] {
            projection_work::reset();
            let bounds = Bounds::for_program_with_operators(
                &model,
                &Selection::default(),
                &model.program,
                &[operator, I::ONE],
            )
            .unwrap();
            assert_eq!(
                projection_work::state_rows(),
                0,
                "unwritten states must not repeat a known identity projection"
            );
            assert_eq!(bounds.states.len(), 64);
            assert!(bounds.matches_operator_bindings(&[operator, I::ONE]));
        }
        for indices in [vec![0, 1], vec![0, 2]] {
            let selection = Selection {
                actions: vec![(0, indices.clone())],
                ..Selection::default()
            };
            projection_work::reset();
            Bounds::for_program_with_operators(
                &model,
                &selection,
                &model.program,
                &[I::point(0.25), I::ONE],
            )
            .unwrap();
            assert_eq!(
                projection_work::state_rows(),
                if indices == [0, 1] { 1 } else { 2 }
            );
        }
    }

    #[test]
    fn unwritten_projection_keeps_dense_bits_live_forcing_and_full_matrix_rejection() {
        let model = identity_projection_fixture(4);
        for indices in [vec![], vec![0], vec![0, 1], vec![2], vec![0, 2]] {
            let selection = Selection {
                actions: vec![(0, indices.clone())],
                ..Selection::default()
            };
            for operator in [I::point(-0.), I::point(0.25), I { lo: 0.24, hi: 0.26 }] {
                projection_work::reset();
                let bounds = Bounds::for_program_with_operators(
                    &model,
                    &selection,
                    &model.program,
                    &[operator, I::ONE],
                )
                .unwrap();
                let dense_rows = original_dense_state_rows(&model, &selection, &bounds);
                for (actual, expected) in bounds
                    .states
                    .iter()
                    .flatten()
                    .zip(dense_rows.iter().flatten())
                {
                    assert_eq!(
                        (actual.lo.to_bits(), actual.hi.to_bits()),
                        (expected.lo.to_bits(), expected.hi.to_bits())
                    );
                }
                let mut dense = Bounds::from_rows(bounds.nodes.clone(), dense_rows, Vec::new());
                dense.state_nonzero.clear();
                for last in [
                    I::point(-0.),
                    I { lo: -0., hi: 0. },
                    I { lo: -1., hi: 1. },
                    I::point(f64::INFINITY),
                    I::point(f64::NAN),
                ] {
                    let before = [I::ONE, I::ZERO, I::point(f64::from_bits(1)), last];
                    let a = bounds.check_states(
                        &model,
                        &[I::point(-0.), I::ONE],
                        &before,
                        &[operator, I::ONE],
                        &[],
                        &[0.; 4],
                    );
                    let b = dense.check_states(
                        &model,
                        &[I::point(-0.), I::ONE],
                        &before,
                        &[operator, I::ONE],
                        &[],
                        &[0.; 4],
                    );
                    match (a, b) {
                        (Ok(a), Ok(b)) => {
                            for (a, b) in a.iter().zip(b) {
                                assert_eq!(
                                    (a.lo.to_bits(), a.hi.to_bits()),
                                    (b.lo.to_bits(), b.hi.to_bits())
                                );
                            }
                        }
                        (Err(a), Err(b)) => assert_eq!((a.kind, a.message), (b.kind, b.message)),
                        _ => panic!("prepared and original dense state checks disagree"),
                    }
                }
            }
        }
        for nonfinite in [f64::INFINITY, f64::NAN] {
            let error = Bounds::for_program_with_operators(
                &model,
                &Selection::default(),
                &model.program,
                &[I::point(nonfinite), I::ONE],
            )
            .err()
            .unwrap();
            assert_eq!(error.kind, "event_accuracy");
        }
    }

    #[test]
    fn repeated_state_checks_scan_live_parameters_once_and_keep_dense_results() {
        let count = 64;
        let states: Vec<_> = (0..count)
            .map(|i| json!({"instance":"M","name":format!("q{i}"),"kind":"real","initial":0}))
            .collect();
        let program = serde_json::from_value(json!({
            "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","u"],
            "states":states,"contributions":[],
            "events":[{"origin":{"source":"rows.va","line":1,"column":1,"instance":"M"},
                "trigger":{"kind":"timer","start":1,"period":0,"enabled":true,"time_tolerance":0.001},
                "body":[{"kind":"assign","state":0,"rhs":{"op":"affine","constant":0,"terms":[]}}]}]
        }))
        .unwrap();
        let model =
            EventModel::new(program, vec!["u".into()], crate::ir::Tolerances::default()).unwrap();
        let bounds = Bounds::held_inputs(&model, &Selection::default()).unwrap();
        let mut fresh_dense = Bounds::from_rows(Vec::new(), bounds.states.clone(), Vec::new());
        fresh_dense.state_nonzero.clear();
        for sample in 0..2 {
            let before: Vec<_> = (0..count)
                .map(|i| I {
                    lo: (i + sample) as f64 / 64.,
                    hi: (i + sample) as f64 / 64. + sample as f64 / 256.,
                })
                .collect();
            let inputs = [I::point(sample as f64)];
            let parameters: Vec<_> = inputs
                .iter()
                .chain(&before)
                .copied()
                .chain([I::ONE])
                .collect();
            let expected: Vec<_> = bounds
                .states
                .iter()
                .map(|row| {
                    row.iter()
                        .zip(&parameters)
                        .fold(I::ZERO, |sum, (&a, &b)| sum + a * b)
                })
                .collect();
            projection_work::reset();
            let actual = bounds
                .check_states(&model, &inputs, &before, &[], &[], &vec![0.; count])
                .unwrap();
            let (pairs, parameter_visits) = projection_work::get();
            assert_eq!(
                pairs, 0,
                "prepared unit rows must not rescan the full dense width"
            );
            assert_eq!(
                parameter_visits,
                parameters.len(),
                "one current finite gate per check"
            );
            for (actual, expected) in actual.iter().zip(&expected) {
                assert_eq!(
                    (actual.lo.to_bits(), actual.hi.to_bits()),
                    (expected.lo.to_bits(), expected.hi.to_bits())
                );
            }
            let dense = fresh_dense
                .check_states(&model, &inputs, &before, &[], &[], &vec![0.; count])
                .unwrap();
            assert_eq!(actual, dense);
        }
        let mut before = vec![I::ZERO; count];
        for nonfinite in [f64::INFINITY, f64::NAN] {
            before[count - 1] = I::point(nonfinite);
            let err = bounds
                .check_states(&model, &[I::ZERO], &before, &[], &[], &vec![0.; count])
                .unwrap_err();
            assert_eq!(err.kind, "event_accuracy");
            assert!(
                err.message.contains("M:q0"),
                "zero-weight nonfinite forcing still reaches the original first-row error"
            );
            let dense = fresh_dense
                .check_states(&model, &[I::ZERO], &before, &[], &[], &vec![0.; count])
                .unwrap_err();
            assert_eq!((err.kind, err.message), (dense.kind, dense.message));
        }
        before[count - 1] = I::ZERO;
        assert_eq!(
            bounds
                .check_states(&model, &[I::ZERO], &before, &[], &[], &vec![0.; count])
                .unwrap(),
            vec![I::ZERO; count]
        );
    }

    #[test]
    fn sparse_dot_keeps_dense_edge_bits_and_skips_exact_zero_terms() {
        let dense = |row: &[I], values: &[I]| {
            row.iter()
                .zip(values)
                .fold(I::ZERO, |sum, (&a, &b)| sum + a * b)
        };
        let cases = [
            (vec![], vec![]),
            (vec![], vec![I::point(f64::INFINITY), I::point(f64::NAN)]),
            (vec![I::ONE], vec![]),
            (vec![I::ZERO; 4], vec![I::ONE; 4]),
            (vec![I::ONE, -I::ONE], vec![I::ONE; 2]),
            (vec![I::ONE, I::ZERO], vec![I::ONE]),
            (
                vec![I::ONE, I::ZERO],
                vec![I::ONE, I::ONE, I::point(f64::INFINITY)],
            ),
            (vec![I::ZERO], vec![I::point(f64::INFINITY)]),
            (vec![I::ZERO], vec![I::point(f64::NAN)]),
            (vec![I::point(f64::INFINITY)], vec![I::ZERO]),
            (
                vec![
                    I {
                        lo: 0.0,
                        hi: f64::MAX,
                    },
                    I {
                        lo: 0.0,
                        hi: f64::MAX,
                    },
                    I::ZERO,
                ],
                vec![I::ONE; 3],
            ),
            (
                vec![I::point(-0.0), I::ZERO, I { lo: -0.0, hi: 0.0 }],
                vec![-I::ONE, I::point(-0.0), I::ONE],
            ),
            (vec![I::point(f64::from_bits(1))], vec![I::point(0.5)]),
            (
                vec![I::point(1e16), I::ZERO, I::ONE, -I::ONE, -I::point(1e16)],
                vec![I::ONE; 5],
            ),
            (vec![I::ONE], vec![I::ONE, I::point(f64::INFINITY)]),
            (vec![I::ONE, I::point(f64::NAN)], vec![I::ONE]),
        ];
        for (row, values) in cases {
            let actual = dot(&row, &values);
            let expected = dense(&row, &values);
            assert_eq!(
                (actual.lo.to_bits(), actual.hi.to_bits()),
                (expected.lo.to_bits(), expected.hi.to_bits())
            );
            let indices = nonzero_indices(&row);
            let prepared = prepared_dot(
                &row,
                indices.as_deref(),
                &values,
                values.iter().all(|v| v.finite()),
            );
            assert_eq!(
                (prepared.lo.to_bits(), prepared.hi.to_bits()),
                (expected.lo.to_bits(), expected.hi.to_bits())
            );
        }
        let mut row = vec![I::ZERO; 64];
        row[31] = I::ONE;
        let values = vec![I::ONE; row.len()];
        crate::interval::zero_product_tests::reset_work();
        assert_eq!(dot(&row, &values), I::ONE);
        let (products, _) = crate::interval::zero_product_tests::work();
        assert_eq!(products, 4);
    }

    #[test]
    fn state_update_projection_matches_dense_after_joint_elimination() {
        let origin = json!({"source":"projection.va","line":1,"column":1,"instance":"dut"});
        let p: crate::ir::Program = serde_json::from_value(json!({
            "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","u","y"],
            "states":[{"instance":"dut","name":"q","kind":"real","initial":2},
                {"instance":"dut","name":"r","kind":"real","initial":-0.0}],
            "events":[{"origin":origin,"trigger":{"kind":"timer","start":1,"period":0,"enabled":true,"time_tolerance":0.001},
                "body":[{"kind":"assign","state":0,"rhs":{"op":"add","left":{"op":"state","state":0},
                    "right":{"op":"affine","constant":0.1,"terms":[{"node":1,"coefficient":0.3}]}}},
                    {"kind":"assign","state":1,"rhs":{"op":"add","left":{"op":"state","state":0},"right":{"op":"state","state":1}}}]}],
            "contributions":[{"origin":origin,"branch":{"instance":"dut","local_positive":"out","local_negative":"ref","kind":"voltage"},
                "positive":2,"negative":0,"rhs":{"op":"multiply","left":{"op":"affine","constant":0.1,"terms":[]},"right":{"op":"state","state":0}}}]
        })).unwrap();
        let model = EventModel::new(p, vec!["u".into()], crate::ir::Tolerances::default()).unwrap();
        let p = &model.program;
        let variables = p.nodes.len() + p.states.len();
        let width = 1 + p.states.len() + 1;
        let initial: Vec<_> = (0..p.states.len())
            .map(|i| {
                let mut row = vec![I::ZERO; variables + 1];
                row[p.nodes.len() + i] = I::ONE;
                row
            })
            .collect();
        for indices in [vec![], vec![0], vec![0, 1]] {
            let selection = Selection {
                actions: vec![(0, indices.clone())],
                ..Selection::default()
            };
            let actual = Bounds::for_program(&model, &selection, p).unwrap();
            let mut values = actual.nodes.clone();
            for i in 0..p.states.len() {
                let mut row = vec![I::ZERO; width];
                row[1 + i] = I::ONE;
                values.push(row);
            }
            let mut updates = initial.clone();
            let actions = p.events[0].assignments();
            for index in indices {
                updates[actions[index].state] = substitute(
                    &affine(&actions[index].rhs, p).unwrap(),
                    &updates,
                    p.nodes.len(),
                );
            }
            for (row, actual) in updates.iter().zip(&actual.states) {
                for k in 0..width {
                    let base = if k == width - 1 {
                        row[variables]
                    } else {
                        I::ZERO
                    };
                    let dense = (0..variables).fold(base, |sum, j| sum + row[j] * values[j][k]);
                    assert_eq!(
                        (actual[k].lo.to_bits(), actual[k].hi.to_bits()),
                        (dense.lo.to_bits(), dense.hi.to_bits())
                    );
                }
            }
        }
    }

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
        let bindings = RefCell::new(BTreeSet::new());
        let row = affine_with_operators(&expr, &p, &[I { lo: 0.4, hi: 0.6 }], &bindings).unwrap();
        assert_eq!(
            bindings.into_inner(),
            BTreeSet::from([(0, 0.4_f64.to_bits(), 0.6_f64.to_bits())])
        );
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
