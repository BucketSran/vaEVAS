//! Conditional forward-error enclosure of the original binary64 event IR.
//! Old states and sampled inputs are parameters, so one batch can reuse this map.
use crate::affine_bounds::{affine, eliminate};
use crate::events::EventModel;
use crate::interval::Interval as I;
use crate::ir::{Error, StateKind};
use std::collections::BTreeMap;

fn substitute(row: &[I], updates: &[Vec<I>], nodes: usize) -> Vec<I> {
    let mut result = vec![I::ZERO; row.len()];
    result[..nodes].copy_from_slice(&row[..nodes]);
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
    pub(crate) fn new(model: &EventModel, events: &[usize]) -> Result<Self, Error> {
        let p = &model.program;
        let count = p.nodes.len();
        let variables = count + p.states.len();
        let driven: Vec<_> = model
            .driven
            .iter()
            .map(|name| p.nodes.iter().position(|n| n == name).unwrap())
            .collect();
        let unknown: Vec<_> = (1..count).filter(|n| !driven.contains(n)).collect();
        let n = unknown.len();
        let width = driven.len() + p.states.len() + 1;
        let initial: Vec<_> = (0..p.states.len())
            .map(|k| {
                let mut row = vec![I::ZERO; variables + 1];
                row[count + k] = I::ONE;
                row
            })
            .collect();
        let mut updates = initial.clone();
        for &event in events {
            let mut local = initial.clone();
            for action in &p.events[event].assignments {
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
        for state in 0..p.states.len() {
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

    pub(crate) fn check(
        &self,
        model: &EventModel,
        inputs: &[f64],
        before: &[f64],
        voltages: &[f64],
        states: &[f64],
    ) -> Result<(), Error> {
        let parameters: Vec<_> = inputs.iter().chain(before).copied().chain([1.0]).collect();
        for (rows, actual, voltage) in
            [(&self.nodes, voltages, true), (&self.states, states, false)]
        {
            for (k, (row, &value)) in rows.iter().zip(actual).enumerate() {
                let exact = row
                    .iter()
                    .zip(&parameters)
                    .fold(I::ZERO, |sum, (&a, &b)| sum + a * I::point(b));
                let integer = !voltage && model.program.states[k].kind == StateKind::Integer;
                let absolute = if voltage {
                    model.tolerances.absolute
                } else {
                    0.0
                };
                let relative = if integer {
                    0.0
                } else {
                    model.tolerances.relative
                };
                // A lower bound on the requested budget and an upper bound on
                // actual error. No voltage absolute tolerance for generic state.
                let budget = I::point(absolute) + I::point(relative) * I::point(value.abs());
                let error = I::point(value) - exact;
                if !exact.finite()
                    || !error.finite()
                    || !budget.finite()
                    || error.magnitude() > budget.lo.max(0.0)
                {
                    let name = if voltage {
                        model.program.nodes[k].clone()
                    } else {
                        format!(
                            "{}:{}",
                            model.program.states[k].instance, model.program.states[k].name
                        )
                    };
                    return Err(Error::new("event_accuracy",format!(
                        "cannot certify same-time forward error at {name}: bound {:e}, budget {:e}",error.magnitude(),budget.lo)));
                }
            }
        }
        Ok(())
    }
}
