//! Whole-response sensitivity for one sample, one fixed edge and one stable
//! first-order filter. This is a refinement proposal, not a voltage certificate.
use super::{dot, Bounds};
use crate::events::EventModel;
use crate::interval::Interval as I;
use crate::operators::transition_filter::BudgetPath;
use serde::Serialize;

#[derive(Debug, Serialize)]
pub(crate) struct FilterBudget {
    pub consumer: String,
    pub budget: f64,
    pub retained_bound: f64,
    pub inherited_state_bound: f64,
    pub sample_sensitivity: f64,
    pub edge_sensitivity: f64,
    pub output_sensitivity: f64,
    pub predicted_error_bound: f64,
    pub target_width: Option<f64>,
}

impl Bounds {
    #[allow(clippy::too_many_arguments)]
    pub(crate) fn filter_root_budget(
        &self,
        observation: &Self,
        model: &EventModel,
        path: &BudgetPath,
        inputs: &[I],
        point_inputs: &[I],
        slopes: &[I],
        before: &[I],
        before_values: &[f64],
        sampled_value: f64,
        width: I,
    ) -> Option<FilterBudget> {
        if self.states.len() != 1 || before.len() != 1 {
            return None;
        }
        let n = inputs.len();
        let row = &self.states[0];
        // Sampling an operator or a feedback-dependent value needs a different
        // derivative bound. Integer input-dependent assignments are not affine.
        if row[n + 1..n + 3].iter().any(|x| !x.zero())
            || (model.program.states[0].kind == crate::ir::StateKind::Integer
                && row[..n].iter().any(|x| !x.zero()))
        {
            return None;
        }
        let parameters = |u: &[I]| {
            u.iter()
                .chain(before)
                .copied()
                .chain([I::ZERO, I::ZERO, I::ONE])
                .collect::<Vec<_>>()
        };
        let sample = dot(row, &parameters(inputs));
        let fixed = dot(row, &parameters(point_inputs));
        let retained = I::point((I::point(sampled_value) - fixed).magnitude());
        let inherited = I::point(row[n].magnitude())
            * I::point((I::point(before_values[0]) - before[0]).magnitude());
        let sample_slope = row[..n].iter().zip(slopes).fold(I::ZERO, |s, (&a, &m)| {
            s + I::point(a.magnitude()) * I::point(m.magnitude())
        });
        // The ramp is Lipschitz in both its target and its start time. Sum the
        // two contributions even though they share the same uncertain root.
        let edge_slope = I::point((sample - path.initial).magnitude()) / I::point(path.duration);
        let edge_total = sample_slope + edge_slope;
        let gain = I::point(path.gain.magnitude());
        let mut sensitivities = [I::ZERO; 3];
        let mut retained_errors = [I::ZERO; 3];
        sensitivities[0] = sample_slope;
        sensitivities[1 + path.transition] = edge_total;
        sensitivities[1 + path.filter] = gain * edge_total;
        retained_errors[0] = retained;
        retained_errors[1 + path.transition] = retained + path.edge_error;
        retained_errors[1 + path.filter] = path.filter_error + gain * (retained + path.edge_error);
        let mut demands = Vec::new();
        for (k, row) in observation.nodes.iter().enumerate() {
            let weights = &row[n..n + 3];
            if weights.iter().all(|x| x.zero()) {
                continue;
            }
            // Absolute-only planning avoids a future zero reducing the budget.
            // Direct input feedthrough and uncertain projection coefficients
            // retain full recovery rather than omitting their error terms.
            if row[..n].iter().any(|x| !x.zero()) || row.iter().any(|x| x.lo != x.hi) {
                return None;
            }
            let weighted = |bounds: &[I]| {
                weights
                    .iter()
                    .zip(bounds)
                    .fold(I::ZERO, |s, (&a, &b)| s + I::point(a.magnitude()) * b)
            };
            let slope = weighted(&sensitivities);
            let floor = weighted(&retained_errors);
            let budget = model.tolerances.absolute;
            if ![slope, floor, sample_slope, edge_slope, inherited, width]
                .iter()
                .all(|x| x.finite())
            {
                return None;
            }
            if slope.zero() && floor.hi <= budget {
                continue;
            }
            let target = (I::point(budget) - floor) / slope;
            let target_width =
                (slope.lo > 0. && target.finite() && target.lo > 0.).then_some(target.lo);
            demands.push(FilterBudget {
                consumer: model.program.nodes[k].clone(),
                budget,
                retained_bound: floor.hi,
                inherited_state_bound: inherited.hi,
                sample_sensitivity: sample_slope.hi,
                edge_sensitivity: edge_slope.hi,
                output_sensitivity: slope.hi,
                predicted_error_bound: (floor + slope * width).hi,
                target_width,
            });
        }
        // All consumers count, including an exposed edge and signed gains.
        // A retained floor that cannot fit must not be hidden by another node.
        demands.into_iter().min_by(|a, b| {
            a.target_width
                .unwrap_or(0.)
                .total_cmp(&b.target_width.unwrap_or(0.))
        })
    }
}
