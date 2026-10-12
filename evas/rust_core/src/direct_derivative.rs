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
        Ok(if time.lo == 0. {
            value.hull(I::ZERO)
        } else {
            value
        })
    }
    pub(super) fn value(&self, time: f64) -> Result<f64, Error> {
        let b = self.bounds(time)?;
        Ok(b.lo + (b.hi - b.lo) * 0.5)
    }
    pub(super) fn next_breakpoint(&self, after: f64) -> Option<f64> {
        self.trajectory.knots.iter().copied().find(|t| *t > after)
    }
}
