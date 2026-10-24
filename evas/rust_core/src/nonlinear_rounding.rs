//! A smooth proxy paired with a retained source-RN expression. RN is never
//! differentiated. Its uniform forcing defect is integrated separately as O(h).
use super::*;
#[derive(Clone, PartialEq)]
pub(super) enum RoundedField {
    Linear(Vec<I>),
    Add(Box<Self>, Box<Self>),
    Multiply(Box<Self>, Box<Self>),
    Divide(Box<Self>, Box<Self>),
    Round(Box<Self>),
    Power(Box<Self>, u32),
}
impl RoundedField {
    pub(super) fn compile(
        e: &Expression,
        p: &Program,
        system: &AlgebraicSystem,
        mapping: &[Vec<I>],
        w: &crate::transition_source_plan::Work,
    ) -> Result<Self, Error> {
        w.debit(2, 128)?;
        let compile = |e: &Expression| Self::compile(e, p, system, mapping, w).map(Box::new);
        Ok(match e {
            Expression::RealBoundary { value, .. } => Self::Round(compile(value)?),
            Expression::RealBinary {
                operation,
                left,
                right,
                ..
            } => {
                use crate::ir::RealOperation as O;
                w.debit(2, 768)?;
                let a = Box::new(Self::Round(compile(left)?));
                let b = Box::new(Self::Round(compile(right)?));
                let value = match operation {
                    O::Add => Self::Add(a, b),
                    O::Subtract => {
                        let mut row = vec![I::ZERO; system.width];
                        *row.last_mut().unwrap() = I::point(-1.);
                        Self::Add(a, Box::new(Self::Multiply(Box::new(Self::Linear(row)), b)))
                    }
                    O::Multiply => Self::Multiply(a, b),
                    O::Divide => Self::Divide(a, b),
                };
                Self::Round(Box::new(value))
            }
            Expression::Add { left, right } => Self::Add(compile(left)?, compile(right)?),
            Expression::Multiply { left, right } => Self::Multiply(compile(left)?, compile(right)?),
            Expression::Divide { left, right } => Self::Divide(compile(left)?, compile(right)?),
            Expression::Power { base, exponent } => Self::Power(compile(base)?, *exponent),
            _ => {
                w.debit(
                    2,
                    ((system.width + p.nodes.len() + p.states.len() + p.operators.len() + 8) * 64)
                        as u64,
                )?;
                Self::Linear(expand_input(
                    &affine_bounds::affine(e, p)?,
                    p,
                    system,
                    mapping,
                )?)
            }
        })
    }
    pub(super) fn proxy(
        &self,
        w: &crate::transition_source_plan::Work,
    ) -> Result<Polynomial, Error> {
        w.debit(2, 128)?;
        Ok(match self {
            Self::Linear(row) => {
                w.debit(2, (row.len() * 16) as u64)?;
                Polynomial::Linear(row.clone())
            }
            Self::Round(a) => a.proxy(w)?,
            Self::Add(a, b) => Polynomial::Add(Box::new(a.proxy(w)?), Box::new(b.proxy(w)?)),
            Self::Multiply(a, b) => {
                Polynomial::Multiply(Box::new(a.proxy(w)?), Box::new(b.proxy(w)?))
            }
            Self::Divide(a, b) => Polynomial::Multiply(
                Box::new(a.proxy(w)?),
                Box::new(Polynomial::Reciprocal(Box::new(b.proxy(w)?))),
            ),
            Self::Power(a, n) => Polynomial::Power(Box::new(a.proxy(w)?), *n),
        })
    }
    /// Returns (smooth value, actual RN value - smooth value), preserving the
    /// correlation in the difference instead of subtracting two wide ranges.
    pub(super) fn enclosure(
        &self,
        variables: &[Jet],
        w: &crate::transition_source_plan::Work,
    ) -> Result<(I, I), Error> {
        w.debit(2, 128)?;
        let result = match self {
            Self::Linear(row) => {
                w.debit(2, (row.len() * 4) as u64)?;
                let value = row
                    .iter()
                    .zip(variables)
                    .fold(*row.last().unwrap(), |s, (&c, x)| s + c * x[0]);
                (value, I::ZERO)
            }
            Self::Round(a) => {
                let (a, error) = a.enclosure(variables, w)?;
                let actual = a + error;
                let epsilon = (I::point(actual.magnitude()) * I::point(f64::EPSILON)
                    + I::point(f64::from_bits(1)))
                .hi;
                (
                    a,
                    error
                        + I {
                            lo: -epsilon,
                            hi: epsilon,
                        },
                )
            }
            Self::Add(a, b) => {
                let (a, ea) = a.enclosure(variables, w)?;
                let (b, eb) = b.enclosure(variables, w)?;
                (a + b, ea + eb)
            }
            Self::Multiply(a, b) => {
                let (a, ea) = a.enclosure(variables, w)?;
                let (b, eb) = b.enclosure(variables, w)?;
                (a * b, a * eb + b * ea + ea * eb)
            }
            Self::Divide(a, b) => {
                let (a, ea) = a.enclosure(variables, w)?;
                let (b, eb) = b.enclosure(variables, w)?;
                if b.lo <= 0. && b.hi >= 0. || (b + eb).lo <= 0. && (b + eb).hi >= 0. {
                    return Err(Error::new(
                        "waveform_accuracy",
                        "source RN denominator may reach zero",
                    ));
                }
                (a / b, (ea * b - a * eb) / (b * (b + eb)))
            }
            Self::Power(a, n) => {
                let (a, ea) = a.enclosure(variables, w)?;
                let mut value = I::ONE;
                let mut error = I::ZERO;
                for _ in 0..*n {
                    w.debit(2, 32)?;
                    error = value * ea + a * error + error * ea;
                    value = value * a;
                }
                (value, error)
            }
        };
        if !result.0.finite() || !result.1.finite() {
            return Err(Error::new(
                "waveform_accuracy",
                "source RN forcing defect is nonfinite",
            ));
        }
        Ok(result)
    }
}
