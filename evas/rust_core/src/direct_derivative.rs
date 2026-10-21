//! Immutable chain-rule evaluation on certified continuous physical PWL inputs.
//! No finite differences, sampled history, event state or internal voltage fallback.
use super::*;

fn valid(expr: &Expression, program: &Program, driven: &[usize]) -> bool {
    match expr {
        Expression::Affine { constant, terms } => {
            constant.is_finite()
                && terms
                    .iter()
                    .all(|t| t.coefficient.is_finite() && (t.node == 0 || driven.contains(&t.node)))
        }
        Expression::Add { left, right } | Expression::Multiply { left, right } => {
            valid(left, program, driven) && valid(right, program, driven)
        }
        Expression::Power { base, exponent } => {
            (1..=32).contains(exponent) && valid(base, program, driven)
        }
        Expression::Operator { operator } => match program.operators.get(*operator) {
            Some(OperatorSpec::Idt {
                input: Expression::Affine { constant, terms },
                ic,
                reset: None,
                ..
            }) => terms.is_empty() && constant.is_finite() && ic.is_finite(),
            _ => false,
        },
        _ => false,
    }
}

pub(crate) fn eligible(expr: &Expression, program: &Program, driven: &[usize]) -> bool {
    crate::affine_bounds::affine(expr, program).is_err() && valid(expr, program, driven)
}

#[derive(Clone)]
pub(super) struct DirectDerivative {
    expr: Expression,
    program: Arc<Program>,
    trajectory: Arc<Trajectory>,
    driven: Vec<usize>,
}
impl DirectDerivative {
    pub(super) fn new(
        expr: &Expression,
        program: &Program,
        trajectory: &Trajectory,
        driven: &[String],
    ) -> Result<Self, Error> {
        let nodes = driven
            .iter()
            .map(|name| {
                program
                    .nodes
                    .iter()
                    .position(|n| n == name)
                    .ok_or_else(|| Error::new("invalid_inputs", "unknown derivative source"))
            })
            .collect::<Result<Vec<_>, _>>()?;
        if !eligible(expr, program, &nodes) || !trajectory.has_only_physical_inputs() {
            return Err(Error::new("unsupported_operator", "polynomial ddt requires continuous physical PWL sources or constant-rate unreset integrals"));
        }
        Ok(Self {
            expr: expr.clone(),
            program: Arc::new(program.clone()),
            trajectory: Arc::new(trajectory.clone()),
            driven: nodes,
        })
    }
    // Dual intervals carry both the operand value and its exact chain-rule derivative.
    fn eval(
        &self,
        expr: &Expression,
        time: I,
        values: &[I],
        slopes: &[I],
    ) -> Result<(I, I), Error> {
        let result = match expr {
            Expression::Affine { constant, terms } => {
                let mut v = I::point(*constant);
                let mut d = I::ZERO;
                for term in terms {
                    if term.node == 0 {
                        continue;
                    }
                    let source = self.driven.iter().position(|n| *n == term.node).unwrap();
                    v = v + I::point(term.coefficient) * values[source];
                    d = d + I::point(term.coefficient) * slopes[source];
                }
                (v, d)
            }
            Expression::Operator { operator } => {
                let OperatorSpec::Idt {
                    input: Expression::Affine { constant, .. },
                    ic,
                    ..
                } = &self.program.operators[*operator]
                else {
                    unreachable!()
                };
                (
                    I::point(*ic) + I::point(*constant) * time,
                    I::point(*constant),
                )
            }
            Expression::Add { left, right } => {
                let (a, da) = self.eval(left, time, values, slopes)?;
                let (b, db) = self.eval(right, time, values, slopes)?;
                (a + b, da + db)
            }
            Expression::Multiply { left, right } => {
                let (a, da) = self.eval(left, time, values, slopes)?;
                let (b, db) = self.eval(right, time, values, slopes)?;
                (a * b, da * b + a * db)
            }
            Expression::Power { base, exponent } => {
                let (a, da) = self.eval(base, time, values, slopes)?;
                let mut previous = I::ONE;
                for _ in 1..*exponent {
                    previous = previous * a;
                }
                (previous * a, I::point(*exponent as f64) * previous * da)
            }
            _ => unreachable!(),
        };
        if !result.0.finite() || !result.1.finite() {
            return Err(Error::new(
                "waveform_accuracy",
                "nonfinite polynomial derivative enclosure",
            ));
        }
        Ok(result)
    }
    pub(super) fn bounds(&self, time: f64) -> Result<I, Error> {
        if time == 0. {
            return Ok(I::ZERO);
        }
        let values = self.trajectory.value_bounds(time);
        let slopes: Vec<_> = self
            .trajectory
            .config
            .pwl
            .iter()
            .map(|source| {
                // Interior corners use the right side; the final stop uses the left.
                let i = source
                    .partition_point(|p| {
                        p[0] < time || p[0] == time && time != self.trajectory.config.stop
                    })
                    .min(source.len() - 1)
                    .max(1);
                let [a, x] = source[i - 1];
                let [b, y] = source[i];
                (I::point(y) - I::point(x)) / (I::point(b) - I::point(a))
            })
            .collect();
        Ok(self.eval(&self.expr, I::point(time), &values, &slopes)?.1)
    }
    pub(super) fn range(&self, time: I) -> Result<I, Error> {
        if time.lo == time.hi {
            return self.bounds(time.lo);
        }
        let (values, slopes) = self.trajectory.range(time)?;
        let value = self.eval(&self.expr, time, &values, &slopes)?.1;
        // The source segment enclosure covers the open interval's slopes.
        // A closed upper endpoint at an interior knot instead observes the
        // right derivative. Include both point observations, also preserving
        // zero DC and the left derivative at the request's terminal point.
        Ok(value
            .hull(self.bounds(time.lo)?)
            .hull(self.bounds(time.hi)?))
    }
    pub(super) fn value(&self, time: f64) -> Result<f64, Error> {
        let b = self.bounds(time)?;
        Ok(b.lo + (b.hi - b.lo) * 0.5)
    }
    pub(super) fn next_breakpoint(&self, after: f64) -> Option<f64> {
        self.trajectory.knots.iter().copied().find(|t| *t > after)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ir::{Term, TransientInputs, SCHEMA_VERSION};

    fn squared_pwl(stop: f64) -> DirectDerivative {
        let program = Program {
            step_bounds: vec![],
            schema_version: SCHEMA_VERSION,
            nodes: vec!["0".into(), "u".into()],
            contributions: vec![],
            states: vec![],
            events: vec![],
            operators: vec![],
        };
        let expr = Expression::Power {
            base: Box::new(Expression::Affine {
                constant: 0.,
                terms: vec![Term {
                    node: 1,
                    coefficient: 1.,
                }],
            }),
            exponent: 2,
        };
        let trajectory = Trajectory::new(
            TransientInputs {
                analytic_sources: vec![],
                pwl_errors_v: None,
                pwl: vec![vec![[0., 2.], [0.5, 3.], [1., 2.]]],
                output_times: vec![0., stop],
                strobetimes: vec![],
                stop,
                max_step: stop,
            },
            1,
        )
        .unwrap();
        DirectDerivative::new(&expr, &program, &trajectory, &["u".into()]).unwrap()
    }

    #[test]
    fn closed_range_contains_dc_and_right_sided_interior_corner() {
        let history = squared_pwl(1.);
        // d(u^2)=2*u*u': 10 at .25, -12 at the right side of .5.
        let interval = I { lo: 0.25, hi: 0.5 };
        let range = history.range(interval).unwrap();
        assert!(range.lo <= -12. && range.hi >= 12., "{range:?}");
        for interval in [
            I { lo: 0., hi: 0.5 },
            interval,
            I { lo: 0.5, hi: 0.75 },
            I { lo: 0., hi: 1. },
        ] {
            let range = history.range(interval).unwrap();
            for t in [interval.lo, interval.hi, 0.5] {
                if t < interval.lo || t > interval.hi {
                    continue;
                }
                let point = history.bounds(t).unwrap();
                assert!(
                    range.lo <= point.lo && range.hi >= point.hi,
                    "range {interval:?}={range:?} excludes bounds({t})={point:?}"
                );
            }
        }
    }

    #[test]
    fn closed_range_preserves_left_sided_stop_with_extended_source() {
        let history = squared_pwl(0.5);
        // A request ending at .5 observes +12 from the left, although the
        // underlying source also declares the later descending segment.
        let range = history.range(I { lo: 0.25, hi: 0.5 }).unwrap();
        let endpoint = history.bounds(0.5).unwrap();
        assert!(endpoint.lo <= 12. && endpoint.hi >= 12.);
        assert!(range.lo <= endpoint.lo && range.hi >= endpoint.hi);
        assert!(
            range.lo > 9.,
            "terminal query included future slope: {range:?}"
        );
        let initial_range = history.range(I { lo: 0., hi: 0.25 }).unwrap();
        assert!(initial_range.lo <= 0. && initial_range.hi >= 10.);
    }
}
