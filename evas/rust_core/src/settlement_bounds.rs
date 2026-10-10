//! Forward-error enclosure of the original binary64 event IR.
//! Inputs, old states and operator history carry their supplied enclosures.
//! A cached map never freezes a particular operator sample.
use crate::affine_bounds::{affine, eliminate};
use crate::event_conditions::Selection;
use crate::events::EventModel;
use crate::interval::Interval as I;
use crate::ir::{Error, StateKind};
use std::collections::BTreeMap;

#[path = "filter_budget.rs"]
mod filter_budget;
pub(crate) use filter_budget::FilterBudget;

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

    pub(crate) fn new(model: &EventModel, selection: &Selection) -> Result<Self, Error> {
        let p = &model.program;
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
                let action = assignments[index];
                local[action.state] = substitute(&affine(&action.rhs, p)?, &local, count);
                updates[action.state] = local[action.state].clone();
            }
        }
        let mut grouped = BTreeMap::new();
        for c in &p.contributions {
            let rhs = substitute(&affine(&c.rhs, p)?, &updates, count);
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
