//! Arithmetic carried by occurrence-local value IDs. Program-real boundaries
//! round; ordinary voltage expressions retain their mathematical operations.
use crate::exact_source::history_paid::Paid;
use crate::interval::Interval as I;
use crate::ir::{self, Error, Expression as E};
use crate::real_rounding::{self, Fault, Image};
use crate::transition_source_plan::Work;
use num_rational::BigRational as R;
use num_traits::Zero;
use std::sync::Arc;

#[derive(Clone, Debug)]
pub(crate) enum Operation {
    Elementary(crate::operators::Function, Arc<ir::Origin>),
    Literal(f64),
    Affine {
        constant: f64,
        terms: Arc<[ir::Term]>,
    },
    State(usize),
    Operator(usize),
    Add,
    Multiply,
    Divide,
    Real(ir::RealOperation, Arc<ir::Origin>),
    Boundary(ir::RealBoundaryKind, Arc<ir::Origin>),
    Power(u32),
    Math(ir::EventMathFunction, Arc<ir::Origin>),
    Integer(ir::IntegerFunction, Arc<ir::Origin>),
    IntegerStore(usize, Option<Arc<ir::Origin>>),
    IntegerRound(Arc<ir::Origin>),
    CheckedInteger(Arc<ir::Origin>),
    Index(i32, i32, Arc<ir::Origin>),
}
#[derive(Clone)]
pub(crate) struct Cell {
    pub source_domain: Option<Arc<crate::source_domain::Domain>>,
    pub nominal: Option<f64>,
    pub image: Option<I>,
    pub mathematical: Option<Arc<R>>,
    pub proof: Option<Arc<R>>,
}
impl Cell {
    pub(crate) fn copy(&self, w: &Work) -> Result<Self, Error> {
        w.debit(2, 16)?;
        if let Some(d) = &self.source_domain {
            d.share_cost(w)?;
        }
        Ok(self.clone())
    }
    pub(crate) fn point(&self) -> Result<f64, Error> {
        self.nominal.ok_or_else(|| {
            Error::new(
                "event_condition",
                "procedure value still needs its physical voltage solve",
            )
        })
    }
    pub(crate) fn bound(&self) -> Result<I, Error> {
        self.image.ok_or_else(|| {
            Error::new(
                "event_condition",
                "procedure value has no finite physical enclosure yet",
            )
        })
    }
}
pub(crate) struct Domain<'a> {
    pub nodes: &'a [Option<f64>],
    pub node_bounds: &'a [I],
    pub states: &'a [Option<f64>],
    pub state_bounds: &'a [I],
    pub operators: &'a [Option<f64>],
    pub operator_bounds: &'a [I],
    pub local: &'a crate::event_value_proof::LocalState,
}
fn paid_binary(value: f64, w: &Work) -> Result<Option<Arc<R>>, Error> {
    let mut p = Paid::new(w);
    let r = p.binary(value);
    Ok(p.finish(r)?.map(Arc::new))
}
fn paid_op(a: &R, b: &R, op: char, w: &Work) -> Result<Option<Arc<R>>, Error> {
    let mut p = Paid::new(w);
    let r = p.op(a, b, op);
    Ok(p.finish(r)?.map(Arc::new))
}
fn paid_negated(value: &R, w: &Work) -> Result<Option<Arc<R>>, Error> {
    let mut p = Paid::new(w);
    let result = p.negated(value);
    Ok(p.finish(result)?.map(Arc::new))
}
// Only an exact mathematical unit can replace a physical product. A rounded
// nominal unit or an admissible source band is insufficient.
fn unit_sign(value: &Cell, w: &Work) -> Result<Option<bool>, Error> {
    w.step()?;
    let Some(point) = value.nominal else {
        return Ok(None);
    };
    if (point != 1. && point != -1.)
        || value.source_domain.is_some()
        || !value
            .image
            .is_some_and(|b| b.lo.to_bits() == point.to_bits() && b.hi.to_bits() == point.to_bits())
    {
        return Ok(None);
    }
    let Some((mathematical, proof)) = value.mathematical.as_ref().zip(value.proof.as_ref()) else {
        return Ok(None);
    };
    if !Arc::ptr_eq(mathematical, proof) {
        return Ok(None);
    }
    let mut p = Paid::new(w);
    let comparison = (|| {
        let unit = p.binary(point)?;
        p.cmp(proof, &unit)
    })();
    Ok(p.finish(comparison)?
        .filter(|o| o.is_eq())
        .map(|_| point < 0.))
}
fn unit_product(args: &[Cell], w: &Work) -> Result<Option<Cell>, Error> {
    for (unit, other) in [(&args[0], &args[1]), (&args[1], &args[0])] {
        let Some(negative) = unit_sign(unit, w)? else {
            continue;
        };
        if other.mathematical.is_some() && other.nominal.is_none() {
            continue;
        }
        if !negative {
            return other.copy(w).map(Some);
        }
        // Domain negation has its own source contract. Keep that old route.
        if other.source_domain.is_some() {
            continue;
        }
        let mathematical = other
            .mathematical
            .as_ref()
            .map(|v| paid_negated(v, w))
            .transpose()?
            .flatten();
        let shared = other
            .mathematical
            .as_ref()
            .zip(other.proof.as_ref())
            .is_some_and(|(a, b)| Arc::ptr_eq(a, b));
        let proof = if shared {
            w.debit(2, 16)?;
            mathematical.clone()
        } else {
            other
                .proof
                .as_ref()
                .map(|v| paid_negated(v, w))
                .transpose()?
                .flatten()
        };
        return Ok(Some(Cell {
            source_domain: None,
            nominal: other.nominal.map(|v| -v),
            image: other.image.map(|b| -b),
            mathematical,
            proof,
        }));
    }
    Ok(None)
}

fn rounded(value: &R, w: &Work) -> Result<f64, Error> {
    real_rounding::round_ratio(value, false, &mut |n| w.debit(2, n)).map_err(map_fault)
}
fn map_fault(error: Fault<Error>) -> Error {
    match error {
        Fault::Quota(e) => e,
        other => crate::real_expression::fault(other),
    }
}
fn nominal(value: &Cell, w: &Work) -> Result<Option<f64>, Error> {
    if let Some(r) = value.proof.as_ref().or(value.mathematical.as_ref()) {
        let negative_zero = r.is_zero()
            && value
                .nominal
                .is_some_and(|v| v == 0. && v.is_sign_negative());
        return real_rounding::round_ratio(r, negative_zero, &mut |n| w.debit(2, n))
            .map(Some)
            .map_err(map_fault);
    }
    Ok(value.nominal)
}
fn interval(value: &Cell, w: &Work) -> Result<Option<Image>, Error> {
    if let Some(d) = &value.source_domain {
        return d.rounded(value.image, value.nominal, w);
    }
    // A complete nonzero binary point is already its own RN image. Check
    // the exact current proof, never a rounded nominal approximation.
    w.debit(2, 0)?;
    w.debit(2, 4)?;
    if value.image.is_some_and(|b| b.lo != 0.) && physical_point_image(value, w)? {
        return Ok(value.image.map(|b| Image { lo: b.lo, hi: b.hi }));
    }
    if let Some(r) = &value.proof {
        if !value
            .image
            .is_some_and(|b| b.lo == 0. && b.hi == 0. && b.lo.to_bits() != b.hi.to_bits())
        {
            let v = real_rounding::round_ratio(
                r,
                r.is_zero()
                    && value
                        .nominal
                        .is_some_and(|v| v == 0. && v.is_sign_negative()),
                &mut |n| w.debit(2, n),
            )
            .map_err(map_fault)?;
            return Ok(Some(Image { lo: v, hi: v }));
        }
    }
    value
        .image
        .map(|b| crate::real_expression::interval(b, Some(w)).map(|b| Image { lo: b.lo, hi: b.hi }))
        .transpose()
}
// Reuse only the complete image already carried by this evaluated Cell.
// Negative/mixed zero keeps the old rational enclosure's zero convention.
fn physical_point_image(value: &Cell, w: &Work) -> Result<bool, Error> {
    w.debit(2, 0)?;
    w.debit(2, 8)?;
    if value.source_domain.is_some() {
        return Ok(false);
    }
    let Some(image) = value.image else {
        return Ok(false);
    };
    if !image.finite()
        || image.lo.to_bits() != image.hi.to_bits()
        || (image.lo == 0. && image.lo.is_sign_negative())
    {
        return Ok(false);
    }
    let Some(proof) = &value.proof else {
        return Ok(false);
    };
    crate::event_value_proof::binary_state_identity(proof, image.lo, w)
}
fn mathematical_domain(
    value: &Cell,
    w: &Work,
) -> Result<Option<Arc<crate::source_domain::Domain>>, Error> {
    if let Some(domain) = &value.source_domain {
        domain.share_cost(w)?;
        return Ok(Some(domain.clone()));
    }
    if let Some(proof) = &value.proof {
        return crate::source_domain::Domain::point(proof, w);
    }
    value
        .image
        .map(|bound| crate::source_domain::Domain::enclosure(bound, w))
        .transpose()
        .map(Option::flatten)
}
fn stored(point: Option<f64>, image: Option<Image>, w: &Work) -> Result<Cell, Error> {
    let proof = image
        .and_then(Image::singleton)
        .map(|v| paid_binary(v, w))
        .transpose()?
        .flatten();
    let mathematical = if point
        .zip(image.and_then(Image::singleton))
        .is_some_and(|(a, b)| a.to_bits() == b.to_bits())
    {
        w.debit(2, 16)?;
        proof.clone()
    } else {
        point.map(|v| paid_binary(v, w)).transpose()?.flatten()
    };
    Ok(Cell {
        source_domain: None,
        nominal: point,
        image: image.map(|v| I { lo: v.lo, hi: v.hi }),
        mathematical,
        proof,
    })
}
// stored() constructs binary(RN point) for both meanings at a singleton.
// Share only a current proof certified to be exactly that already-rounded point.
fn boundary_point_proof(
    value: &Cell,
    point: Option<f64>,
    image: Option<Image>,
    w: &Work,
) -> Result<Option<Cell>, Error> {
    w.debit(2, 0)?;
    w.debit(2, 8)?;
    if value.source_domain.is_some() {
        return Ok(None);
    }
    let Some((point, image)) = point.zip(image) else {
        return Ok(None);
    };
    if point == 0.
        || !point.is_finite()
        || image.lo.to_bits() != point.to_bits()
        || image.hi.to_bits() != point.to_bits()
        || !value
            .image
            .is_some_and(|b| b.lo.to_bits() == point.to_bits() && b.hi.to_bits() == point.to_bits())
        || !physical_point_image(value, w)?
    {
        return Ok(None);
    }
    // Cell.copy's existing reservation covers its two Arc clones. No rational
    // allocation, numerical operation, or new proof owner is introduced.
    w.debit(2, 16)?;
    let proof = value.proof.clone();
    Ok(Some(Cell {
        source_domain: None,
        nominal: Some(point),
        image: Some(I {
            lo: image.lo,
            hi: image.hi,
        }),
        mathematical: proof.clone(),
        proof,
    }))
}
impl Operation {
    /// Called only for Builder's immutable (operation, returned Cell) pair.
    /// These constructors certify mathematical equals exact binary(nominal).
    /// A physical Multiply additionally needs a paid exact dyadic identity.
    /// No numerical value or qualification is cached across activations.
    pub(crate) fn captured_binary_identity(&self, value: &Cell, w: &Work) -> Result<bool, Error> {
        w.debit(2, 0)?;
        w.debit(2, 8)?;
        if !matches!(
            self,
            Self::Literal(_)
                | Self::State(_)
                | Self::Real(..)
                | Self::Boundary(..)
                | Self::Multiply
        ) || value.source_domain.is_some()
        {
            return Ok(false);
        }
        let Some(point) = value.nominal else {
            return Ok(false);
        };
        if !point.is_finite()
            || !value.image.is_some_and(|b| {
                b.lo.to_bits() == point.to_bits() && b.hi.to_bits() == point.to_bits()
            })
        {
            return Ok(false);
        }
        let Some((mathematical, proof)) = value.mathematical.as_ref().zip(value.proof.as_ref())
        else {
            return Ok(false);
        };
        if !Arc::ptr_eq(mathematical, proof) {
            return Ok(false);
        }
        if matches!(self, Self::Multiply) {
            // Physical arithmetic has not crossed a source RN boundary. Only
            // its exact, nonzero complete point may stand for binary(nominal).
            // Keep every zero/sign/domain and unequal-R case on the old path.
            if point == 0. {
                return Ok(false);
            }
            return crate::event_value_proof::binary_state_identity(proof, point, w);
        }
        Ok(true)
    }
    pub(crate) fn evaluate(
        &self,
        args: &[Cell],
        domain: &Domain<'_>,
        w: &Work,
    ) -> Result<Cell, Error> {
        w.step()?;
        let mut out = match self {
            Self::Elementary(function, _) => {
                // Existing elementary proofs use bounded scalar series/range
                // reduction (no rational limbs or variable buffers). Prepay
                // their complete arithmetic/storage bound before entering them.
                w.debit(2, 4096)?;
                let refinement = match function {
                    crate::operators::Function::Ln => Some(crate::math_refinement::Function::Ln),
                    crate::operators::Function::Exp => Some(crate::math_refinement::Function::Exp),
                    _ => None,
                };
                let image = args[0].image.map(|b| function.bounds(b)).transpose()?;
                let source_domain = if let Some(function) = refinement {
                    match mathematical_domain(&args[0], w)? {
                        Some(input) => crate::source_domain::Domain::elementary_enclosed(
                            function, &input, image, w,
                        )?,
                        None => None,
                    }
                } else {
                    None
                };
                let point = args[0].nominal.map(|v| function.value(v));
                let proof = image
                    .filter(|b| b.lo.to_bits() == b.hi.to_bits())
                    .map(|b| paid_binary(b.lo, w))
                    .transpose()?
                    .flatten();
                Cell {
                    source_domain,
                    nominal: point,
                    image,
                    mathematical: proof.clone(),
                    proof,
                }
            }
            Self::IntegerStore(state, origin) => {
                // Building an unknown-voltage trial must retain this assertion
                // as an effect. Final numeric/domain evaluation executes it
                // again with the solved complete image before any commit.
                let Some(bound) = args[0].image else {
                    return args[0].copy(w);
                };
                let valid = bound.finite()
                    && bound.lo == bound.hi
                    && bound.lo.fract() == 0.
                    && bound.lo >= f64::from(i32::MIN)
                    && bound.hi <= f64::from(i32::MAX);
                if !valid {
                    return Err(Error::new(
                        "integer_range",
                        format!(
                            "integer store to state {state} requires one signed32 value{}",
                            origin
                                .as_ref()
                                .map(|o| format!(" at {}", o.label()))
                                .unwrap_or_default()
                        ),
                    ));
                }
                if args[0].nominal.is_some_and(|v| {
                    !v.is_finite()
                        || v.fract() != 0.
                        || v < f64::from(i32::MIN)
                        || v > f64::from(i32::MAX)
                }) {
                    return Err(Error::new(
                        "integer_range",
                        format!("integer store representative out of range at state {state}"),
                    ));
                }
                args[0].copy(w)?
            }
            Self::Literal(v) => {
                if !v.is_finite() {
                    return Err(Error::new(
                        "nonfinite_arithmetic",
                        "nonfinite procedure constant",
                    ));
                }
                let proof = paid_binary(*v, w)?;
                Cell {
                    source_domain: None,
                    nominal: Some(*v),
                    image: Some(I::point(*v)),
                    mathematical: proof.clone(),
                    proof,
                }
            }
            Self::State(state) => {
                let nominal = domain.states.get(*state).copied().flatten();
                let reused = nominal
                    .zip(domain.state_bounds.get(*state))
                    .map(|(point, bound)| domain.local.try_point_state(*state, point, *bound, w))
                    .transpose()?
                    .flatten();
                let mathematical = if let Some(value) = reused {
                    w.debit(2, 16)?;
                    Some(Arc::new(value))
                } else {
                    nominal.map(|v| paid_binary(v, w)).transpose()?.flatten()
                };
                let proof = if nominal
                    .zip(domain.state_bounds.get(*state))
                    .is_some_and(|(n, b)| {
                        b.lo.to_bits() == b.hi.to_bits() && n.to_bits() == b.lo.to_bits()
                    }) {
                    w.debit(2, 16)?;
                    mathematical.clone()
                } else {
                    domain
                        .local
                        .try_value(&E::State { state: *state }, domain.node_bounds)?
                        .map(Arc::new)
                };
                Cell {
                    source_domain: None,
                    nominal: domain.states.get(*state).copied().flatten(),
                    image: domain
                        .state_bounds
                        .get(*state)
                        .copied()
                        .filter(|b| b.finite()),
                    mathematical,
                    proof,
                }
            }
            Self::Operator(index) => {
                let point = domain.operators.get(*index).copied().flatten();
                let image = domain
                    .operator_bounds
                    .get(*index)
                    .copied()
                    .filter(|b| b.finite());
                let mathematical = point.map(|v| paid_binary(v, w)).transpose()?.flatten();
                let proof = image
                    .filter(|v| v.lo.to_bits() == v.hi.to_bits())
                    .map(|v| paid_binary(v.lo, w))
                    .transpose()?
                    .flatten();
                Cell {
                    source_domain: None,
                    nominal: point,
                    image,
                    mathematical,
                    proof,
                }
            }
            Self::Affine { constant, terms } => {
                w.debit(2, (terms.len() * 16 + 32) as u64)?;
                let mut image = Some(I::point(*constant));
                let mut math = paid_binary(*constant, w)?;
                for term in terms.iter() {
                    w.step()?;
                    if term.node == 0 {
                        continue;
                    }
                    image = image
                        .zip(
                            domain
                                .node_bounds
                                .get(term.node)
                                .copied()
                                .filter(|b| b.finite()),
                        )
                        .map(|(a, b)| a + I::point(term.coefficient) * b);
                    math = match math.zip(domain.nodes.get(term.node).copied().flatten()) {
                        Some((a, v)) => {
                            let c = paid_binary(term.coefficient, w)?;
                            let b = paid_binary(v, w)?;
                            let product = c
                                .zip(b)
                                .map(|(c, b)| paid_op(&c, &b, '*', w))
                                .transpose()?
                                .flatten();
                            product
                                .map(|b| paid_op(&a, &b, '+', w))
                                .transpose()?
                                .flatten()
                        }
                        None => None,
                    };
                }
                w.debit(2, (terms.len() * 16 + 16) as u64)?;
                let expression = E::Affine {
                    constant: *constant,
                    terms: terms.to_vec(),
                };
                let source_domain =
                    domain
                        .local
                        .source_domain(*constant, terms, domain.node_bounds, w)?;
                let proof = if source_domain.is_some() {
                    None
                } else {
                    domain
                        .local
                        .try_value(&expression, domain.node_bounds)?
                        .map(Arc::new)
                };
                let point = math.as_ref().map(|v| rounded(v, w)).transpose()?;
                Cell {
                    source_domain,
                    nominal: point,
                    image: image.filter(|b| b.finite()),
                    mathematical: math,
                    proof,
                }
            }
            Self::Boundary(_, _) => {
                let a = &args[0];
                let image = interval(a, w)?;
                let point = match image.and_then(Image::singleton) {
                    Some(value) => Some(value),
                    None => nominal(a, w)?,
                };
                match boundary_point_proof(a, point, image, w)? {
                    Some(value) => value,
                    None => stored(point, image, w)?,
                }
            }
            Self::Real(op, _) => {
                let image = interval(&args[0], w)?
                    .zip(interval(&args[1], w)?)
                    .map(|(a, b)| {
                        real_rounding::binary_image(
                            crate::real_expression::operation(*op),
                            a,
                            b,
                            &mut |n| w.debit(2, n),
                        )
                        .map_err(map_fault)
                    })
                    .transpose()?;
                let point = match image.and_then(Image::singleton) {
                    Some(value) => Some(value),
                    None => nominal(&args[0], w)?
                        .zip(nominal(&args[1], w)?)
                        .map(|(a, b)| crate::real_expression::point(*op, a, b))
                        .transpose()?,
                };
                stored(point, image, w)?
            }
            Self::Add | Self::Multiply | Self::Divide => {
                if let Some(value) = if matches!(self, Self::Multiply) {
                    unit_product(args, w)?
                } else {
                    None
                } {
                    value
                } else {
                    let (a, b) = (&args[0], &args[1]);
                    let op = match self {
                        Self::Add => '+',
                        Self::Multiply => '*',
                        _ => '/',
                    };
                    if matches!(self, Self::Divide)
                        && b.image.is_some_and(|b| b.lo <= 0. && b.hi >= 0.)
                    {
                        return Err(Error::new(
                            "event_domain",
                            "procedure divisor enclosure contains zero",
                        ));
                    }
                    let mathematical = a
                        .mathematical
                        .as_ref()
                        .zip(b.mathematical.as_ref())
                        .map(|(a, b)| paid_op(a, b, op, w))
                        .transpose()?
                        .flatten();
                    let shared = a
                        .mathematical
                        .as_ref()
                        .zip(a.proof.as_ref())
                        .is_some_and(|(a, b)| Arc::ptr_eq(a, b))
                        && b.mathematical
                            .as_ref()
                            .zip(b.proof.as_ref())
                            .is_some_and(|(a, b)| Arc::ptr_eq(a, b));
                    let proof = if shared {
                        w.debit(2, 16)?;
                        mathematical.clone()
                    } else {
                        a.proof
                            .as_ref()
                            .zip(b.proof.as_ref())
                            .map(|(a, b)| paid_op(a, b, op, w))
                            .transpose()?
                            .flatten()
                    };
                    let image = a
                        .image
                        .zip(b.image)
                        .map(|(a, b)| match self {
                            Self::Add => a + b,
                            Self::Multiply => a * b,
                            _ => a / b,
                        })
                        .filter(|b| b.finite());
                    let point = mathematical
                        .as_ref()
                        .map(|v| rounded(v, w))
                        .transpose()?
                        .or_else(|| {
                            a.nominal.zip(b.nominal).map(|(a, b)| match self {
                                Self::Add => a + b,
                                Self::Multiply => a * b,
                                _ => a / b,
                            })
                        });
                    let source_domain = if a.source_domain.is_some() || b.source_domain.is_some() {
                        match mathematical_domain(a, w)?.zip(mathematical_domain(b, w)?) {
                            Some((a, b)) => crate::source_domain::Domain::binary(&a, &b, op, w)?,
                            None => None,
                        }
                    } else {
                        None
                    };
                    Cell {
                        source_domain,
                        nominal: point,
                        image,
                        mathematical,
                        proof,
                    }
                }
            }
            Self::Power(exponent) => {
                let a = &args[0];
                let mut math = paid_binary(1., w)?;
                let mut proof = paid_binary(1., w)?;
                let mut image = Some(I::ONE);
                let input_domain = if a.source_domain.is_some() {
                    mathematical_domain(a, w)?
                } else {
                    None
                };
                let mut source_domain = if input_domain.is_some() {
                    match &math {
                        Some(one) => crate::source_domain::Domain::point(one, w)?,
                        None => None,
                    }
                } else {
                    None
                };
                for _ in 0..*exponent {
                    w.step()?;
                    math = math
                        .zip(a.mathematical.clone())
                        .map(|(a, b)| paid_op(&a, &b, '*', w))
                        .transpose()?
                        .flatten();
                    proof = proof
                        .zip(a.proof.clone())
                        .map(|(a, b)| paid_op(&a, &b, '*', w))
                        .transpose()?
                        .flatten();
                    image = image.zip(a.image).map(|(a, b)| a * b);
                    source_domain = match source_domain.zip(input_domain.as_ref()) {
                        Some((sum, input)) => {
                            crate::source_domain::Domain::binary(&sum, input, '*', w)?
                        }
                        None => None,
                    };
                }
                let point = math
                    .as_ref()
                    .map(|v| rounded(v, w))
                    .transpose()?
                    .or_else(|| a.nominal.map(|v| v.powi(*exponent as i32)));
                Cell {
                    source_domain,
                    nominal: point,
                    image: image.filter(|b| b.finite()),
                    mathematical: math,
                    proof,
                }
            }
            Self::Integer(function, origin) => {
                let operands = args
                    .iter()
                    .map(|v| {
                        v.bound()
                            .and_then(|b| crate::integer_primitive::point(b, origin))
                            .map(|value| ir::IntegerOperand::IntegerLiteral { value })
                    })
                    .collect::<Result<Vec<_>, _>>()?;
                let value = crate::integer_primitive::evaluate(
                    *function,
                    &operands,
                    origin,
                    &mut |_| Err(Error::new("invalid_ir", "unresolved integer DAG operand")),
                    &mut || w.step(),
                )?;
                let proof = paid_binary(f64::from(value), w)?;
                Cell {
                    source_domain: None,
                    nominal: Some(f64::from(value)),
                    image: Some(I::point(f64::from(value))),
                    mathematical: proof.clone(),
                    proof,
                }
            }
            Self::IntegerRound(origin) => {
                let image = args[0]
                    .image
                    .map(|b| crate::event_numeric::nearest_box(b, origin))
                    .transpose()?;
                let point = args[0].nominal.map(f64::round);
                let proof = image
                    .filter(|b| b.lo.to_bits() == b.hi.to_bits())
                    .map(|b| paid_binary(b.lo, w))
                    .transpose()?
                    .flatten();
                Cell {
                    source_domain: None,
                    nominal: point,
                    image,
                    mathematical: proof.clone(),
                    proof,
                }
            }
            Self::CheckedInteger(origin) => {
                let image = args[0]
                    .image
                    .map(|b| crate::event_numeric::checked_integer(b, origin))
                    .transpose()?;
                let proof = image
                    .filter(|b| b.lo.to_bits() == b.hi.to_bits())
                    .map(|b| paid_binary(b.lo, w))
                    .transpose()?
                    .flatten();
                Cell {
                    source_domain: None,
                    nominal: args[0].nominal,
                    image,
                    mathematical: proof.clone(),
                    proof,
                }
            }
            Self::Index(first, last, origin) => {
                let image = args[0]
                    .image
                    .map(|b| crate::event_numeric::checked_index(b, *first, *last, origin))
                    .transpose()?;
                let proof = image.map(|b| paid_binary(b.lo, w)).transpose()?.flatten();
                Cell {
                    source_domain: None,
                    nominal: args[0].nominal,
                    image,
                    mathematical: proof.clone(),
                    proof,
                }
            }
            Self::Math(function, origin) => {
                let point = args
                    .iter()
                    .map(|a| a.nominal)
                    .collect::<Option<Vec<_>>>()
                    .map(|values| {
                        use ir::EventMathFunction as F;
                        let a = values[0];
                        let value = match function {
                            F::Floor => a.floor(),
                            F::Abs => a.abs(),
                            F::Min => a.min(values[1]),
                            F::Max => a.max(values[1]),
                            F::Sqrt if a >= 0. => a.sqrt(),
                            F::Ln if a > 0. => a.ln(),
                            _ => {
                                return Err(Error::new(
                                    "event_domain",
                                    "pure procedure mathematics outside its domain",
                                ))
                            }
                        };
                        Ok::<_, Error>(value)
                    })
                    .transpose()?;
                let image = if args.iter().all(|v| v.image.is_some()) {
                    let e = E::EventMath {
                        function: *function,
                        args: (0..args.len()).map(|state| E::State { state }).collect(),
                        origin: (**origin).clone(),
                    };
                    Some(crate::event_numeric::bounds(
                        &e,
                        &[],
                        &args.iter().map(|a| a.image.unwrap()).collect::<Vec<_>>(),
                    )?)
                } else {
                    None
                };
                let proof = image
                    .filter(|b| b.lo.to_bits() == b.hi.to_bits())
                    .map(|b| paid_binary(b.lo, w))
                    .transpose()?
                    .flatten();
                let source_domain = if matches!(function, ir::EventMathFunction::Ln) {
                    match mathematical_domain(&args[0], w)? {
                        Some(input) => crate::source_domain::Domain::elementary_enclosed(
                            crate::math_refinement::Function::Ln,
                            &input,
                            image,
                            w,
                        )?,
                        None => None,
                    }
                } else {
                    None
                };
                Cell {
                    source_domain,
                    nominal: point,
                    image,
                    mathematical: proof.clone(),
                    proof,
                }
            }
        };
        // Continuous arithmetic carries its mathematical rational certificate.
        // Its enclosure may be tighter than a sequence of independent interval
        // operations; program-real nodes above already carry rounded images.
        if matches!(
            self,
            Self::Affine { .. } | Self::Add | Self::Multiply | Self::Divide | Self::Power(_)
        ) && !physical_point_image(&out, w)?
        {
            if let Some(proof) = &out.proof {
                if let Some(image) = crate::exact_source::enclosure_with_work(proof, w)? {
                    out.image = Some(image);
                }
            }
        }
        if out.nominal.is_some_and(|v| !v.is_finite()) {
            return Err(Error::new(
                "nonfinite_arithmetic",
                "nonfinite executed procedure operation",
            ));
        }
        Ok(out)
    }
}

#[cfg(test)]
mod integer_store_tests {
    use super::*;
    #[test]
    fn unknown_integer_store_is_retained_until_a_complete_solved_image_exists() {
        let w = Work::default();
        let proofs = crate::event_value_proof::Proofs::new();
        let context =
            crate::event_value_proof::Context::candidate_frame(&proofs, 0, &[], &[], &w).unwrap();
        let local =
            crate::event_value_proof::LocalState::try_with_context(&[], Some(&context)).unwrap();
        let domain = Domain {
            nodes: &[],
            node_bounds: &[],
            states: &[],
            state_bounds: &[],
            operators: &[],
            operator_bounds: &[],
            local: &local,
        };
        let operation = Operation::IntegerStore(0, None);
        let unknown = Cell {
            source_domain: None,
            nominal: None,
            image: None,
            mathematical: None,
            proof: None,
        };
        assert!(operation
            .evaluate(&[unknown], &domain, &w)
            .unwrap()
            .image
            .is_none());
        for value in [f64::from(i32::MIN), 0., f64::from(i32::MAX)] {
            let cell = stored(
                Some(value),
                Some(Image {
                    lo: value,
                    hi: value,
                }),
                &w,
            )
            .unwrap();
            assert_eq!(
                operation
                    .evaluate(&[cell], &domain, &w)
                    .unwrap()
                    .point()
                    .unwrap(),
                value
            );
        }
        for (lo, hi) in [
            (1., 2.),
            (1.5, 1.5),
            (2147483648., 2147483648.),
            (-2147483649., -2147483649.),
        ] {
            let cell = Cell {
                source_domain: None,
                nominal: Some(lo),
                image: Some(I { lo, hi }),
                mathematical: None,
                proof: None,
            };
            assert_eq!(
                operation.evaluate(&[cell], &domain, &w).err().unwrap().kind,
                "integer_range"
            );
        }
    }
}

#[cfg(test)]
mod physical_unit_tests {
    use super::*;
    fn point(value: f64, w: &Work) -> Cell {
        let proof = paid_binary(value, w).unwrap();
        Cell {
            source_domain: None,
            nominal: Some(value),
            image: Some(I::point(value)),
            mathematical: proof.clone(),
            proof,
        }
    }
    #[test]
    fn captured_identity_uses_actual_binary_constructors_and_preserves_zero_bits() {
        let w = Work::default();
        let origin: Arc<ir::Origin> = Arc::new(
            serde_json::from_value(
                serde_json::json!({"source":"capture.va","line":1,"column":1,"instance":"dut"}),
            )
            .unwrap(),
        );
        for value in [0., -0., 0.1, -0.1, 1., f64::MIN_POSITIVE] {
            let states = [Some(value)];
            let bounds = [I::point(value)];
            let local =
                crate::event_value_proof::LocalState::try_with_context(&bounds, None).unwrap();
            let domain = Domain {
                nodes: &[],
                node_bounds: &[],
                states: &states,
                state_bounds: &bounds,
                operators: &[],
                operator_bounds: &[],
                local: &local,
            };
            for operation in [Operation::Literal(value), Operation::State(0)] {
                let captured = operation.evaluate(&[], &domain, &w).unwrap();
                assert!(operation.captured_binary_identity(&captured, &w).unwrap());
                assert_eq!(captured.point().unwrap().to_bits(), value.to_bits());
                assert_eq!(
                    **captured.mathematical.as_ref().unwrap(),
                    crate::exact_source::binary(value).unwrap()
                );
                for kind in [
                    ir::RealBoundaryKind::Sample,
                    ir::RealBoundaryKind::Store,
                    ir::RealBoundaryKind::Snapshot,
                    ir::RealBoundaryKind::Argument,
                    ir::RealBoundaryKind::Return,
                ] {
                    let boundary = Operation::Boundary(kind, origin.clone());
                    let cell = boundary
                        .evaluate(std::slice::from_ref(&captured), &domain, &w)
                        .unwrap();
                    assert!(boundary.captured_binary_identity(&cell, &w).unwrap());
                    assert_eq!(
                        **cell.mathematical.as_ref().unwrap(),
                        crate::exact_source::binary(cell.point().unwrap()).unwrap()
                    );
                }
            }
            let real = Operation::Real(ir::RealOperation::Add, origin.clone());
            let cell = real
                .evaluate(&[point(0.1, &w), point(0.2, &w)], &domain, &w)
                .unwrap();
            assert!(real.captured_binary_identity(&cell, &w).unwrap());
            assert_eq!(
                **cell.mathematical.as_ref().unwrap(),
                crate::exact_source::binary(0.1 + 0.2).unwrap()
            );
        }
    }
    #[test]
    fn captured_identity_limits_physical_operations_and_rejects_incomplete_or_source_domain_cells()
    {
        let w = Work::default();
        let complete = point(1., &w);
        assert!(Operation::Multiply
            .captured_binary_identity(&complete, &w)
            .unwrap());
        for operation in [
            Operation::Add,
            Operation::Divide,
            Operation::Power(1),
            Operation::Operator(0),
            Operation::IntegerStore(0, None),
        ] {
            assert!(!operation.captured_binary_identity(&complete, &w).unwrap());
        }
        let mut cell = complete.clone();
        cell.image = Some(I { lo: 0.5, hi: 1.5 });
        for operation in [Operation::Literal(1.), Operation::Multiply] {
            assert!(!operation.captured_binary_identity(&cell, &w).unwrap());
        }
        let mut cell = complete.clone();
        cell.proof = None;
        for operation in [Operation::Literal(1.), Operation::Multiply] {
            assert!(!operation.captured_binary_identity(&cell, &w).unwrap());
        }
        let mut cell = complete.clone();
        cell.proof = paid_binary(1., &w).unwrap();
        for operation in [Operation::Literal(1.), Operation::Multiply] {
            assert!(!operation.captured_binary_identity(&cell, &w).unwrap());
        }
        let mut cell = complete.clone();
        cell.nominal = None;
        for operation in [Operation::Literal(1.), Operation::Multiply] {
            assert!(!operation.captured_binary_identity(&cell, &w).unwrap());
        }
        for value in [0., -0.] {
            assert!(!Operation::Multiply
                .captured_binary_identity(&point(value, &w), &w)
                .unwrap());
        }
        let mut mixed = point(0., &w);
        mixed.image = Some(I { lo: -0., hi: 0. });
        assert!(!Operation::Multiply
            .captured_binary_identity(&mixed, &w)
            .unwrap());
        let mut cell = complete;
        cell.source_domain =
            crate::source_domain::Domain::enclosure(I { lo: 0.99, hi: 1.01 }, &w).unwrap();
        for operation in [Operation::Literal(1.), Operation::Multiply] {
            assert!(!operation.captured_binary_identity(&cell, &w).unwrap());
        }
    }
    #[test]
    fn captured_identity_prepays_original_owner_and_stops_before_reading_after_exhaustion() {
        let setup = Work::default();
        let cell = point(1., &setup);
        let operation = Operation::Literal(1.);
        let w = Work::limited([128, 8192, 8]);
        let strong = Arc::strong_count(cell.mathematical.as_ref().unwrap());
        assert!(operation.captured_binary_identity(&cell, &w).unwrap());
        assert_eq!(w.spent(), 8);
        assert_eq!(
            operation
                .captured_binary_identity(&cell, &w)
                .unwrap_err()
                .kind,
            "step_budget"
        );
        let exhausted = w.spent();
        assert_eq!(exhausted, 16);
        let shared = w.clone();
        assert!(shared.same_owner(&w));
        for _ in 0..2 {
            assert_eq!(
                operation
                    .captured_binary_identity(&cell, &shared)
                    .unwrap_err()
                    .kind,
                "step_budget"
            );
            assert_eq!(w.spent(), exhausted);
        }
        assert_eq!(
            Arc::strong_count(cell.mathematical.as_ref().unwrap()),
            strong
        );
    }

    #[test]
    fn signed_zero_is_preserved_for_both_units_and_operand_positions() {
        let w = Work::default();
        for unit in [1., -1.] {
            for value in [0., -0.] {
                let a = point(unit, &w);
                let b = point(value, &w);
                for args in [[a.clone(), b.clone()], [b.clone(), a.clone()]] {
                    let out = unit_product(&args, &w).unwrap().unwrap();
                    let want = unit * value;
                    assert_eq!(out.nominal.unwrap().to_bits(), want.to_bits());
                    assert_eq!(out.image.unwrap().lo.to_bits(), want.to_bits());
                    assert_eq!(out.image.unwrap().hi.to_bits(), want.to_bits());
                    assert!(Arc::ptr_eq(
                        out.mathematical.as_ref().unwrap(),
                        out.proof.as_ref().unwrap()
                    ));
                }
            }
        }
    }
    #[test]
    fn source_domain_is_shared_for_positive_unit_and_not_negated_by_this_fastpath() {
        let w = Work::default();
        let mut value = point(0.5, &w);
        value.source_domain =
            crate::source_domain::Domain::enclosure(I { lo: 0.49, hi: 0.51 }, &w).unwrap();
        value.image = Some(I { lo: 0.49, hi: 0.51 });
        value.proof = None;
        let original = value.source_domain.clone();
        let positive = unit_product(&[point(1., &w), value.clone()], &w)
            .unwrap()
            .unwrap();
        assert!(Arc::ptr_eq(
            positive.source_domain.as_ref().unwrap(),
            original.as_ref().unwrap()
        ));
        assert_eq!(positive.image, value.image);
        assert!(unit_product(&[point(-1., &w), value.clone()], &w)
            .unwrap()
            .is_none());
        let foreign = Work::default();
        assert_eq!(
            unit_product(&[point(1., &foreign), value], &foreign)
                .err()
                .unwrap()
                .kind,
            "invalid_ir"
        );
    }
    #[test]
    fn rounded_nominal_unit_and_distinct_unproved_math_cannot_skip_a_product() {
        let w = Work::default();
        let mut unit = point(1., &w);
        let q = Arc::new(R::new(
            18014398509481985_i64.into(),
            18014398509481984_i64.into(),
        ));
        unit.mathematical = Some(q.clone());
        unit.proof = Some(q);
        assert!(unit_product(&[unit, point(2., &w)], &w).unwrap().is_none());
        let mut unit = point(1., &w);
        unit.mathematical = paid_binary(1., &w).unwrap();
        assert!(unit_product(&[unit, point(2., &w)], &w).unwrap().is_none());
    }
    #[test]
    fn original_owner_exhaustion_is_sticky_and_failed_negation_does_not_modify_input() {
        let owner = Work::default();
        let values = [point(-1., &owner), point(3., &owner)];
        let limited = Work::limited([128, 8192, 0]);
        for _ in 0..2 {
            assert_eq!(
                unit_product(&values, &limited).err().unwrap().kind,
                "step_budget"
            );
        }
        assert_eq!(values[1].nominal, Some(3.));
        let q = values[1].mathematical.as_ref().unwrap();
        let mut p = Paid::new(&limited);
        let out = p.negated(q);
        assert_eq!(p.finish(out).unwrap_err().kind, "step_budget");
        assert_eq!(**q, R::from_integer(3.into()));
    }
    #[test]
    fn repeated_real_work_naturally_exhausts_one_owner_and_retry_cannot_refund() {
        let w = Work::limited([128, 8192, 50000]);
        let values = [point(-1., &w), point(3., &w)];
        let mut successes = 0;
        loop {
            match unit_product(&values, &w) {
                Ok(Some(_)) => successes += 1,
                Err(error) => {
                    assert_eq!(error.kind, "step_budget");
                    break;
                }
                _ => panic!("unit product unexpectedly unavailable"),
            }
        }
        assert!(successes > 0);
        let spent = w.spent();
        let retry = w.clone();
        assert!(w.same_owner(&retry));
        assert_eq!(
            unit_product(&values, &retry).err().unwrap().kind,
            "step_budget"
        );
        assert!(w.spent() > spent);
        assert_eq!(retry.spent(), w.spent());
        assert_eq!(values[1].nominal, Some(3.));
    }
}

#[cfg(test)]
mod physical_point_enclosure_tests {
    use super::*;
    fn cell(point: f64, w: &Work) -> Cell {
        let proof = paid_binary(point, w).unwrap();
        Cell {
            source_domain: None,
            nominal: Some(point),
            image: Some(I::point(point)),
            mathematical: proof.clone(),
            proof,
        }
    }
    #[test]
    fn physical_point_enclosure_requires_exact_rational_not_rounded_match() {
        let w = Work::default();
        for point in [
            0.,
            f64::from_bits(1),
            -f64::from_bits(1),
            0.1,
            -0.1,
            1.,
            f64::MAX,
        ] {
            let value = cell(point, &w);
            assert!(physical_point_image(&value, &w).unwrap());
            let old = crate::exact_source::enclosure_with_work(value.proof.as_ref().unwrap(), &w)
                .unwrap()
                .unwrap();
            assert_eq!(old.lo.to_bits(), point.to_bits());
            assert_eq!(old.hi.to_bits(), point.to_bits());
        }
        let mut rounded = cell(0.2, &w);
        rounded.proof = Some(Arc::new(R::new(1.into(), 5.into())));
        assert!(!physical_point_image(&rounded, &w).unwrap());
        let mut near = cell(1., &w);
        near.proof = Some(Arc::new(
            R::from_integer(1.into()) + R::new(1.into(), (1u64 << 60).into()),
        ));
        assert!(!physical_point_image(&near, &w).unwrap());
        let mut value = cell(1., &w);
        value.image = Some(I {
            lo: 1f64.next_down(),
            hi: 1f64.next_up(),
        });
        assert!(!physical_point_image(&value, &w).unwrap());
        let mut value = cell(1., &w);
        value.source_domain =
            crate::source_domain::Domain::enclosure(I { lo: 0.99, hi: 1.01 }, &w).unwrap();
        assert!(!physical_point_image(&value, &w).unwrap());
        let mut value = cell(1., &w);
        value.proof = None;
        assert!(!physical_point_image(&value, &w).unwrap());
        let mut value = cell(1., &w);
        value.image = None;
        assert!(!physical_point_image(&value, &w).unwrap());
        // The proof, rather than an unrelated nominal or mathematical value,
        // certifies exactly the existing physical point image.
        let mut value = cell(1., &w);
        value.nominal = Some(2.);
        value.mathematical = paid_binary(3., &w).unwrap();
        assert!(physical_point_image(&value, &w).unwrap());
    }
    #[test]
    fn physical_point_enclosure_preserves_original_negative_and_mixed_zero_fallback() {
        let w = Work::default();
        assert!(!physical_point_image(&cell(-0., &w), &w).unwrap());
        let mut mixed = cell(0., &w);
        mixed.image = Some(I { lo: -0., hi: 0. });
        assert!(!physical_point_image(&mixed, &w).unwrap());
        let proofs = crate::event_value_proof::Proofs::new();
        let context =
            crate::event_value_proof::Context::candidate_frame(&proofs, 0, &[], &[], &w).unwrap();
        let local =
            crate::event_value_proof::LocalState::try_with_context(&[], Some(&context)).unwrap();
        let domain = Domain {
            nodes: &[],
            node_bounds: &[],
            states: &[],
            state_bounds: &[],
            operators: &[],
            operator_bounds: &[],
            local: &local,
        };
        for x in [0., -0., 0.1, -0.1] {
            for unit in [1., -1.] {
                let out = Operation::Multiply
                    .evaluate(&[cell(x, &w), cell(unit, &w)], &domain, &w)
                    .unwrap();
                let expected =
                    crate::exact_source::enclosure_with_work(out.proof.as_ref().unwrap(), &w)
                        .unwrap()
                        .unwrap();
                let actual = out.image.unwrap();
                assert_eq!(actual.lo.to_bits(), expected.lo.to_bits());
                assert_eq!(actual.hi.to_bits(), expected.hi.to_bits());
                assert_eq!(out.nominal.unwrap().to_bits(), (x * unit).to_bits());
            }
        }
    }
    #[test]
    fn physical_point_enclosure_prepays_original_owner_and_failed_retry_is_sticky() {
        let setup = Work::default();
        let value = cell(0.1, &setup);
        let w = Work::limited([128, 8192, 50_000]);
        let mut exhausted = false;
        for _ in 0..10_000 {
            match physical_point_image(&value, &w) {
                Ok(true) => {}
                Ok(false) => panic!("point proof changed"),
                Err(error) => {
                    assert_eq!(error.kind, "step_budget");
                    exhausted = true;
                    break;
                }
            }
        }
        assert!(exhausted);
        assert!(w.spent() > 50_000);
        let spent = w.spent();
        let shared = w.clone();
        for _ in 0..2 {
            assert_eq!(
                physical_point_image(&value, &shared).unwrap_err().kind,
                "step_budget"
            );
            assert_eq!(w.spent(), spent);
        }
        assert_eq!(value.image.unwrap().lo.to_bits(), 0.1f64.to_bits());
    }
}

#[cfg(test)]
mod point_rn_consumer_tests {
    use super::*;
    fn cell(point: f64, w: &Work) -> Cell {
        let proof = paid_binary(point, w).unwrap();
        Cell {
            source_domain: None,
            nominal: Some(point),
            image: Some(I::point(point)),
            mathematical: proof.clone(),
            proof,
        }
    }
    fn bits(value: Option<Image>) -> Option<(u64, u64)> {
        value.map(|b| (b.lo.to_bits(), b.hi.to_bits()))
    }
    #[test]
    fn point_rn_consumer_uses_current_exact_proof_and_distinct_cells_without_value_cache() {
        let w = Work::default();
        for point in [
            f64::from_bits(1),
            -f64::from_bits(1),
            0.1,
            0.2,
            -0.2,
            1.,
            f64::MAX,
        ] {
            let first = cell(point, &w);
            let second = cell(point, &w);
            assert!(!Arc::ptr_eq(
                first.proof.as_ref().unwrap(),
                second.proof.as_ref().unwrap()
            ));
            for value in [first, second] {
                let before = w.spent();
                assert_eq!(
                    bits(interval(&value, &w).unwrap()),
                    Some((point.to_bits(), point.to_bits()))
                );
                assert!(w.spent() > before);
            }
        }
        let mut stale_image = cell(0.2, &w);
        stale_image.proof = paid_binary(0.3, &w).unwrap();
        let expected = 0.3f64.to_bits();
        assert_eq!(
            bits(interval(&stale_image, &w).unwrap()),
            Some((expected, expected))
        );
        let mut unrelated_nominal = cell(0.1, &w);
        unrelated_nominal.nominal = Some(2.);
        assert_eq!(
            bits(interval(&unrelated_nominal, &w).unwrap()),
            Some((0.1f64.to_bits(), 0.1f64.to_bits()))
        );
    }
    #[test]
    fn point_rn_consumer_preserves_near_rationals_nonpoints_source_domains_and_zero_signs() {
        let w = Work::default();
        for (point, rational) in [
            (0.2, R::new(1.into(), 5.into())),
            (
                1.,
                R::from_integer(1.into()) + R::new(1.into(), (1u64 << 60).into()),
            ),
        ] {
            let mut value = cell(point, &w);
            value.proof = Some(Arc::new(rational.clone()));
            assert!(!physical_point_image(&value, &w).unwrap());
            let expected = rounded(&rational, &w).unwrap();
            assert_eq!(
                bits(interval(&value, &w).unwrap()),
                Some((expected.to_bits(), expected.to_bits()))
            );
        }
        let mut band = cell(1., &w);
        band.proof = None;
        band.image = Some(I { lo: 0.99, hi: 1.01 });
        let actual = interval(&band, &w).unwrap().unwrap();
        assert!(actual.lo < 1. && actual.hi > 1.);
        let mut source = cell(1., &w);
        source.image = Some(I { lo: 0.99, hi: 1.01 });
        source.source_domain =
            crate::source_domain::Domain::enclosure(source.image.unwrap(), &w).unwrap();
        let expected = source
            .source_domain
            .as_ref()
            .unwrap()
            .rounded(source.image, source.nominal, &w)
            .unwrap();
        assert_eq!(bits(interval(&source, &w).unwrap()), bits(expected));
        for lo in [0., -0.] {
            for hi in [0., -0.] {
                for nominal in [0., -0.] {
                    let mut zero = cell(nominal, &w);
                    zero.image = Some(I { lo, hi });
                    let expected = if lo.to_bits() != hi.to_bits() {
                        crate::real_expression::interval(zero.image.unwrap(), Some(&w))
                            .map(|b| Some(Image { lo: b.lo, hi: b.hi }))
                            .unwrap()
                    } else {
                        Some(Image {
                            lo: nominal,
                            hi: nominal,
                        })
                    };
                    assert_eq!(bits(interval(&zero, &w).unwrap()), bits(expected));
                }
            }
        }
    }
    #[test]
    fn point_rn_consumer_natural_exhaustion_uses_original_owner_and_is_sticky() {
        let setup = Work::default();
        let value = cell(0.1, &setup);
        let w = Work::limited([128, 8192, 50_000]);
        let mut exhausted = false;
        for _ in 0..10_000 {
            match interval(&value, &w) {
                Ok(Some(image)) => assert_eq!(image.lo.to_bits(), 0.1f64.to_bits()),
                Ok(None) => panic!("point vanished"),
                Err(error) => {
                    assert_eq!(error.kind, "step_budget");
                    exhausted = true;
                    break;
                }
            }
        }
        assert!(exhausted);
        assert!(w.spent() > 50_000);
        let spent = w.spent();
        let shared = w.clone();
        for _ in 0..2 {
            assert_eq!(interval(&value, &shared).unwrap_err().kind, "step_budget");
            assert_eq!(w.spent(), spent);
        }
    }
}

#[cfg(test)]
mod boundary_point_proof_tests {
    use super::*;
    fn cell(point: f64, w: &Work) -> Cell {
        let proof = paid_binary(point, w).unwrap();
        Cell {
            source_domain: None,
            nominal: Some(point),
            image: Some(I::point(point)),
            mathematical: proof.clone(),
            proof,
        }
    }
    fn image(point: f64) -> Option<Image> {
        Some(Image {
            lo: point,
            hi: point,
        })
    }
    #[test]
    fn boundary_point_proof_reuses_only_current_rounded_proof_not_input_math() {
        let w = Work::default();
        for point in [
            f64::from_bits(1),
            -f64::from_bits(1),
            0.1,
            0.2,
            -0.2,
            1.,
            f64::MAX,
        ] {
            let first = cell(point, &w);
            let second = cell(point, &w);
            assert!(!Arc::ptr_eq(
                first.proof.as_ref().unwrap(),
                second.proof.as_ref().unwrap()
            ));
            for mut value in [first, second] {
                value.mathematical = paid_binary(3., &w).unwrap();
                let out = boundary_point_proof(&value, Some(point), image(point), &w)
                    .unwrap()
                    .unwrap();
                let old = stored(Some(point), image(point), &w).unwrap();
                assert_eq!(out.mathematical.as_deref(), old.mathematical.as_deref());
                assert!(Arc::ptr_eq(
                    out.proof.as_ref().unwrap(),
                    value.proof.as_ref().unwrap()
                ));
                assert!(Arc::ptr_eq(
                    out.proof.as_ref().unwrap(),
                    out.mathematical.as_ref().unwrap()
                ));
                assert_eq!(out.nominal.unwrap().to_bits(), point.to_bits());
            }
        }
        let stale = cell(0.1, &w);
        assert!(boundary_point_proof(&stale, Some(0.2), image(0.2), &w)
            .unwrap()
            .is_none());
    }
    #[test]
    fn boundary_point_proof_keeps_near_rational_domain_nonpoint_and_zero_fallback() {
        let w = Work::default();
        let mut near = cell(0.2, &w);
        near.proof = Some(Arc::new(R::new(1.into(), 5.into())));
        assert!(boundary_point_proof(&near, Some(0.2), image(0.2), &w)
            .unwrap()
            .is_none());
        let mut near = cell(1., &w);
        near.proof = Some(Arc::new(
            R::from_integer(1.into()) + R::new(1.into(), (1u64 << 60).into()),
        ));
        assert!(boundary_point_proof(&near, Some(1.), image(1.), &w)
            .unwrap()
            .is_none());
        let mut band = cell(1., &w);
        band.image = Some(I { lo: 0.99, hi: 1.01 });
        assert!(boundary_point_proof(&band, Some(1.), image(1.), &w)
            .unwrap()
            .is_none());
        let mut source = cell(1., &w);
        source.source_domain =
            crate::source_domain::Domain::enclosure(I { lo: 0.99, hi: 1.01 }, &w).unwrap();
        assert!(boundary_point_proof(&source, Some(1.), image(1.), &w)
            .unwrap()
            .is_none());
        let missing = Cell {
            source_domain: None,
            nominal: None,
            image: None,
            mathematical: None,
            proof: None,
        };
        assert!(boundary_point_proof(&missing, None, None, &w)
            .unwrap()
            .is_none());
        for point in [0., -0.] {
            let zero = cell(point, &w);
            assert!(boundary_point_proof(&zero, Some(point), image(point), &w)
                .unwrap()
                .is_none());
            let old = stored(Some(point), image(point), &w).unwrap();
            assert_eq!(old.nominal.unwrap().to_bits(), point.to_bits());
            assert_eq!(old.image.unwrap().lo.to_bits(), point.to_bits());
        }
        let mut mixed = cell(0., &w);
        mixed.image = Some(I { lo: -0., hi: 0. });
        assert!(
            boundary_point_proof(&mixed, Some(0.), Some(Image { lo: -0., hi: 0. }), &w)
                .unwrap()
                .is_none()
        );
    }
    #[test]
    fn boundary_point_proof_original_owner_natural_failure_does_not_clone_on_retry() {
        let setup = Work::default();
        let value = cell(0.1, &setup);
        let setup_spent = setup.spent();
        let strong = Arc::strong_count(value.proof.as_ref().unwrap());
        let w = Work::limited([128, 8192, 50_000]);
        let mut exhausted = false;
        for _ in 0..10_000 {
            match boundary_point_proof(&value, Some(0.1), image(0.1), &w) {
                Ok(Some(out)) => {
                    assert_eq!(out.nominal.unwrap(), 0.1);
                }
                Ok(None) => panic!("point proof vanished"),
                Err(error) => {
                    assert_eq!(error.kind, "step_budget");
                    exhausted = true;
                    break;
                }
            }
        }
        assert!(exhausted);
        assert!(w.spent() > 50_000);
        let spent = w.spent();
        let shared = w.clone();
        for _ in 0..2 {
            assert_eq!(
                boundary_point_proof(&value, Some(0.1), image(0.1), &shared)
                    .err()
                    .unwrap()
                    .kind,
                "step_budget"
            );
            assert_eq!(w.spent(), spent);
            assert_eq!(Arc::strong_count(value.proof.as_ref().unwrap()), strong);
            assert_eq!(setup.spent(), setup_spent);
        }
    }
}

#[cfg(test)]
mod multiply_captured_point_tests {
    use super::*;
    fn cell(point: f64, w: &Work) -> Cell {
        let proof = paid_binary(point, w).unwrap();
        Cell {
            source_domain: None,
            nominal: Some(point),
            image: Some(I::point(point)),
            mathematical: proof.clone(),
            proof,
        }
    }
    fn qualified(value: &Cell, w: &Work) -> bool {
        Operation::Multiply
            .captured_binary_identity(value, w)
            .unwrap()
    }
    #[test]
    fn multiply_captured_point_pays_each_distinct_cell_and_activation() {
        let w = Work::default();
        for point in [
            f64::from_bits(1),
            -f64::from_bits(1),
            0.1,
            -0.2,
            1.,
            -1.,
            f64::MAX,
        ] {
            let first = cell(point, &w);
            let second = cell(point, &w);
            assert!(!Arc::ptr_eq(
                first.proof.as_ref().unwrap(),
                second.proof.as_ref().unwrap()
            ));
            for current in [&first, &second, &first] {
                let before = w.spent();
                assert!(qualified(current, &w));
                assert!(w.spent() > before);
            }
            let mut changed = first.clone();
            changed.nominal = Some(point / 2.);
            assert!(!qualified(&changed, &w));
        }
        // Two equal-valued captures do not establish a shared proof identity.
        let mut distinct = cell(0.2, &w);
        distinct.mathematical = paid_binary(0.2, &w).unwrap();
        assert!(!qualified(&distinct, &w));
    }
    #[test]
    fn multiply_captured_point_rejects_nonexact_near_domain_zero_and_foreign_frame() {
        let w = Work::default();
        for r in [
            R::new(1.into(), 5.into()),
            R::from_integer(1.into()) + R::new(1.into(), (1u64 << 60).into()),
        ] {
            let point = if r < R::from_integer(1.into()) {
                0.2
            } else {
                1.
            };
            let proof = Arc::new(r);
            let mut value = cell(point, &w);
            value.mathematical = Some(proof.clone());
            value.proof = Some(proof);
            assert!(!qualified(&value, &w));
        }
        let mut band = cell(1., &w);
        band.image = Some(I { lo: 0.99, hi: 1.01 });
        assert!(!qualified(&band, &w));
        for bounds in [I::point(1.), I { lo: 0.99, hi: 1.01 }] {
            let mut source = cell(1., &w);
            source.source_domain = crate::source_domain::Domain::enclosure(bounds, &w).unwrap();
            assert!(source.source_domain.is_some());
            assert!(!qualified(&source, &w));
        }
        for point in [0., -0.] {
            assert!(!qualified(&cell(point, &w), &w));
        }
        let mut mixed = cell(0., &w);
        mixed.image = Some(I { lo: -0., hi: 0. });
        assert!(!qualified(&mixed, &w));
        let mut stale = cell(1., &w);
        stale.nominal = Some(2.);
        stale.image = Some(I::point(2.));
        assert!(!qualified(&stale, &w));
        let mut missing = cell(1., &w);
        missing.proof = None;
        assert!(!qualified(&missing, &w));
        // Other physical operations retain the original generic comparison.
        for op in [Operation::Add, Operation::Divide, Operation::Power(2)] {
            assert!(!op.captured_binary_identity(&cell(1., &w), &w).unwrap());
        }
    }
    #[test]
    fn multiply_captured_point_keeps_actual_product_math_and_negative_unit() {
        let w = Work::default();
        let proofs = crate::event_value_proof::Proofs::new();
        let context =
            crate::event_value_proof::Context::candidate_frame(&proofs, 0, &[], &[], &w).unwrap();
        let local =
            crate::event_value_proof::LocalState::try_with_context(&[], Some(&context)).unwrap();
        let domain = Domain {
            nodes: &[],
            node_bounds: &[],
            states: &[],
            state_bounds: &[],
            operators: &[],
            operator_bounds: &[],
            local: &local,
        };
        let product = Operation::Multiply
            .evaluate(&[cell(0.1, &w), cell(0.1, &w)], &domain, &w)
            .unwrap();
        assert!(!qualified(&product, &w));
        let product = Operation::Multiply
            .evaluate(&[cell(-1., &w), cell(0.1, &w)], &domain, &w)
            .unwrap();
        assert!(qualified(&product, &w));
        assert_eq!(product.nominal.unwrap().to_bits(), (-0.1f64).to_bits());
        for point in [0., -0.] {
            let product = Operation::Multiply
                .evaluate(&[cell(-1., &w), cell(point, &w)], &domain, &w)
                .unwrap();
            assert!(!qualified(&product, &w));
            assert_eq!(product.nominal.unwrap().to_bits(), (-point).to_bits());
        }
    }
    #[test]
    fn multiply_captured_point_natural_owner_exhaustion_is_sticky() {
        let setup = Work::default();
        let value = cell(0.1, &setup);
        let before_setup = setup.spent();
        let count = Arc::strong_count(value.proof.as_ref().unwrap());
        let w = Work::limited([128, 8192, 50_000]);
        let mut failed = false;
        for _ in 0..10_000 {
            match Operation::Multiply.captured_binary_identity(&value, &w) {
                Ok(true) => {}
                Ok(false) => panic!("qualification changed"),
                Err(e) => {
                    assert_eq!(e.kind, "step_budget");
                    failed = true;
                    break;
                }
            }
        }
        assert!(failed);
        assert!(w.spent() > 50_000);
        let spent = w.spent();
        for _ in 0..2 {
            assert_eq!(
                Operation::Multiply
                    .captured_binary_identity(&value, &w.clone())
                    .unwrap_err()
                    .kind,
                "step_budget"
            );
            assert_eq!(w.spent(), spent);
            assert_eq!(setup.spent(), before_setup);
            assert_eq!(Arc::strong_count(value.proof.as_ref().unwrap()), count);
        }
    }
    #[test]
    fn multiply_captured_point_default_billion_owner_naturally_exhausts_and_fresh_recovers() {
        let setup = Work::default();
        let value = cell(1., &setup);
        let setup_spent = setup.spent();
        let references = Arc::strong_count(value.proof.as_ref().unwrap());
        let w = Work::default();
        assert_eq!(w.spent(), 0);
        let mut attempts = 0u64;
        loop {
            attempts += 1;
            assert!(
                attempts <= 100_000_000,
                "helper failed to exhaust the unmodified default owner"
            );
            match Operation::Multiply.captured_binary_identity(&value, &w) {
                Ok(true) => {}
                Ok(false) => panic!("qualification changed"),
                Err(e) => {
                    assert_eq!(e.kind, "step_budget");
                    break;
                }
            }
        }
        assert!(w.spent() > 1_000_000_000);
        let spent = w.spent();
        for _ in 0..2 {
            assert_eq!(
                Operation::Multiply
                    .captured_binary_identity(&value, &w.clone())
                    .unwrap_err()
                    .kind,
                "step_budget"
            );
            assert_eq!(w.spent(), spent);
        }
        let fresh = Work::default();
        assert_eq!(fresh.spent(), 0);
        assert!(qualified(&value, &fresh));
        assert!(fresh.spent() > 0);
        assert_eq!(setup.spent(), setup_spent);
        assert_eq!(Arc::strong_count(value.proof.as_ref().unwrap()), references);
        println!(
            "MULTIPLY_DEFAULT_OWNER attempts={attempts} used={spent} fresh_used={}",
            fresh.spent()
        );
    }
    #[test]
    fn multiply_captured_point_does_not_reuse_real_call_or_changed_state_activations() {
        let p: crate::ir::Program =
            serde_json::from_str(include_str!("testdata/real_call_activation.json")).unwrap();
        let w = Work::default();
        crate::procedure::validate(&p, &w).unwrap();
        let nodes = vec![I::ZERO; p.nodes.len()];
        for n in [1., 2., 1.] {
            let before = vec![I::ZERO, I::ZERO, I::point(n)];
            let plan = crate::procedure::execute(&p, &[0], &nodes, &before, None, &w).unwrap();
            let result = plan
                .numeric_states(&p, &vec![0.; p.nodes.len()], &[0., 0., n], None, &w)
                .unwrap();
            assert_eq!(result, [n.exp(), n + 1., n]);
        }
    }
}
