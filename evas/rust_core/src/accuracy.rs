//! An observed voltage certificate and an optional local recovery demand.
//! These are internal assessments, never a replacement for final acceptance.
use crate::interval::Interval as I;
use serde::Serialize;

#[derive(Clone, Debug, Serialize)]
pub(crate) struct Assessment {
    pub consumer: String,
    pub representative: f64,
    pub enclosure: [f64; 2],
    pub error_bound: f64,
    pub budget: f64,
}

impl Assessment {
    pub(crate) fn new(
        consumer: String,
        value: f64,
        exact: I,
        absolute: f64,
        relative: f64,
    ) -> Self {
        let budget = I::point(absolute) + I::point(relative) * I::point(value.abs());
        Self {
            consumer,
            representative: value,
            enclosure: [exact.lo, exact.hi],
            error_bound: (I::point(value) - exact).magnitude(),
            budget: budget.lo.max(0.),
        }
    }

    pub(crate) fn finite(&self) -> bool {
        self.enclosure.iter().all(|x| x.is_finite())
            && self.representative.is_finite()
            && self.error_bound.is_finite()
            && self.budget.is_finite()
    }
}

#[derive(Debug, Serialize)]
pub(crate) struct Demand {
    #[serde(flatten)]
    pub assessment: Assessment,
    pub time: f64,
    pub source: Source,
    pub retained_bound: f64,
    pub inherited_state_bound: f64,
    pub time_sensitivity: f64,
    pub target_width: Option<f64>,
    pub future_input_coupling: bool,
}

#[derive(Debug, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub(crate) enum Source {
    CurrentRoot,
    Retained,
    MixedOrUnknown,
}

impl Demand {
    pub(crate) fn new(
        assessment: Assessment,
        time: f64,
        retained: f64,
        inherited: f64,
        slope: f64,
        independent: bool,
        future_input_coupling: bool,
    ) -> Option<Self> {
        if !assessment.finite() || ![retained, inherited, slope].iter().all(|x| x.is_finite()) {
            return None;
        }
        // This certificate is at the current representative. A changed
        // representative must be recertified, including its relative budget.
        let target = if slope > 0. && retained < assessment.budget {
            let bound = (I::point(assessment.budget) - I::point(retained)) / I::point(slope);
            (bound.finite() && bound.lo > 0.).then_some(bound.lo)
        } else {
            None
        };
        Some(Self {
            assessment,
            time,
            source: if independent {
                Source::Retained
            } else if target.is_some() {
                Source::CurrentRoot
            } else {
                Source::MixedOrUnknown
            },
            retained_bound: retained,
            inherited_state_bound: inherited,
            time_sensitivity: slope,
            target_width: target,
            future_input_coupling,
        })
    }
}
