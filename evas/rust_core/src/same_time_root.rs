//! The exact root of a same-time cycle through program reals, and its binary64
//! rounding.
//!
//! Decision 22 (D-R2-1 option A, a clarification of ADR-006): when a rounded
//! program value feeds the equation it is computed from at the same time
//! point, the cycle's relations without their rounding steps are solved in
//! real arithmetic, and each stored value is the binary64 rounding (nearest,
//! ties to even) of that exact root. The caller certifies that the root is
//! unique in a box; this module finds the rounding of the root inside it.
//! Values the cycle reads are exact rational intervals: points where the
//! activation knows them exactly.
//!
//! Two routes; neither judges from an interval whether the root is rational:
//! - one exact Newton step: with point inputs and only +, -, *, / and integer
//!   powers of binary64 constants, x* = x0 - J(x0)^-1 F(x0) in rationals is
//!   the root when F(x*) is exactly zero (always for an affine cycle);
//! - refinement: otherwise the certified box is contracted in rational
//!   interval arithmetic (the Krawczyk operator keeps every root of the box
//!   and drops the parts that hold none) and, where that stalls on the
//!   finest grid, split at a rounding boundary with the same exclusion test,
//!   until both ends of every component round to the same binary64.
//!
//! Every rational operation is paid to the caller's Work. A box that cannot be
//! separated, a transcendental relation whose binary64 enclosure is too wide,
//! or a root at a rounding tie of a nonlinear cycle is refused by name; no
//! nominal or executed value replaces the rounding of the root.
use crate::interval::Interval as I;
use crate::ir::{Error, Expression};
use crate::real_rounding::Fault;
use crate::transition_source_plan::Work;
use num_rational::BigRational as R;
use num_traits::{One, Signed, ToPrimitive, Zero};

/// Bits of a box end kept below its magnitude: first, and at most.
const FIRST_BITS: i64 = 64;
const LAST_BITS: i64 = 256;
/// Contraction or split rounds of one refinement.
const ROUNDS: usize = 96;
/// No operand pair of one paid rational operation may be wider.
const MAX_BITS: u64 = 1 << 16;

/// An exact rational interval, `lo <= hi`.
#[derive(Clone, Debug, PartialEq)]
pub(crate) struct Q {
    pub lo: R,
    pub hi: R,
}

impl Q {
    pub(crate) fn point(value: R) -> Self {
        Self {
            lo: value.clone(),
            hi: value,
        }
    }
    pub(crate) fn is_point(&self) -> bool {
        self.lo == self.hi
    }
}

/// One relation of a cycle without its rounding steps: its member equals
/// `sign * sum(rhs)`.
pub(crate) struct Relation {
    pub sign: f64,
    pub rhs: Vec<Expression>,
}

/// A same-time cycle. Relation `c` defines member `c`.
pub(crate) struct Cycle<'a> {
    pub relations: &'a [Relation],
    /// Member index of each node read by the relations, None outside the cycle.
    pub column: &'a [Option<usize>],
    /// The value of every other node the relations read.
    pub values: &'a [Option<Q>],
    /// Names the cycle in refusals.
    pub name: &'a str,
}

fn width(value: &R) -> u64 {
    value.numer().bits().max(value.denom().bits())
}

fn pay(w: &Work, operands: &[&R]) -> Result<(), Error> {
    let bits = operands
        .iter()
        .fold(0_u64, |sum, value| sum.saturating_add(width(value)));
    if bits > MAX_BITS {
        return Err(Error::new(
            "waveform_accuracy",
            "exact same-time equation exceeds the rational size limit",
        ));
    }
    w.debit(2, crate::real_rounding::rational_fee(bits))
}

/// The exact value of a binary64.
pub(crate) fn binary(value: f64, w: &Work) -> Result<R, Error> {
    let exact = R::from_float(value).ok_or_else(|| {
        Error::new(
            "invalid_ir",
            "exact same-time equation reads a nonfinite value",
        )
    })?;
    pay(w, &[&exact])?;
    Ok(exact)
}

/// The binary64 nearest to an exact value, ties to even; an exact zero is +0.
pub(crate) fn nearest(value: &R, name: &str, w: &Work) -> Result<f64, Error> {
    crate::real_rounding::round_ratio(value, false, &mut |n| w.debit(2, n)).map_err(|fault| {
        match fault {
            Fault::Quota(error) => error,
            Fault::Overflow => Error::new(
                "nonfinite_arithmetic",
                format!("the binary64 rounding of the exact same-time root of {name} overflows"),
            ),
            other => Error::new(
                "invalid_ir",
                format!("exact same-time rounding of {name} failed: {other:?}"),
            ),
        }
    })
}

fn add(a: &R, b: &R, w: &Work) -> Result<R, Error> {
    pay(w, &[a, b])?;
    Ok(a + b)
}
fn sub(a: &R, b: &R, w: &Work) -> Result<R, Error> {
    pay(w, &[a, b])?;
    Ok(a - b)
}
fn mul(a: &R, b: &R, w: &Work) -> Result<R, Error> {
    pay(w, &[a, b])?;
    Ok(a * b)
}
fn div(a: &R, b: &R, w: &Work) -> Result<R, Error> {
    if b.is_zero() {
        return Err(Error::new(
            "waveform_accuracy",
            "division by zero in the exact same-time equation",
        ));
    }
    pay(w, &[a, b])?;
    Ok(a / b)
}
fn less(a: &R, b: &R, w: &Work) -> Result<bool, Error> {
    pay(w, &[a, b])?;
    Ok(a < b)
}

fn q_add(a: &Q, b: &Q, w: &Work) -> Result<Q, Error> {
    let lo = add(&a.lo, &b.lo, w)?;
    let hi = if a.is_point() && b.is_point() {
        lo.clone()
    } else {
        add(&a.hi, &b.hi, w)?
    };
    Ok(Q { lo, hi })
}
fn q_neg(a: &Q, w: &Work) -> Result<Q, Error> {
    pay(w, &[&a.lo, &a.hi])?;
    Ok(Q {
        lo: -a.hi.clone(),
        hi: -a.lo.clone(),
    })
}
fn q_sub(a: &Q, b: &Q, w: &Work) -> Result<Q, Error> {
    q_add(a, &q_neg(b, w)?, w)
}
fn hull(values: Vec<R>, w: &Work) -> Result<Q, Error> {
    let mut iter = values.into_iter();
    let first = iter
        .next()
        .ok_or_else(|| Error::new("invalid_ir", "empty exact interval hull"))?;
    let (mut lo, mut hi) = (first.clone(), first);
    for value in iter {
        if less(&value, &lo, w)? {
            lo = value;
        } else if less(&hi, &value, w)? {
            hi = value;
        }
    }
    Ok(Q { lo, hi })
}
/// An interval times an exact factor.
fn q_scale(a: &Q, factor: &R, w: &Work) -> Result<Q, Error> {
    if a.is_point() {
        return Ok(Q::point(mul(&a.lo, factor, w)?));
    }
    let (x, y) = (mul(&a.lo, factor, w)?, mul(&a.hi, factor, w)?);
    Ok(if factor.is_negative() {
        Q { lo: y, hi: x }
    } else {
        Q { lo: x, hi: y }
    })
}
fn q_mul(a: &Q, b: &Q, w: &Work) -> Result<Q, Error> {
    if a.is_point() {
        return q_scale(b, &a.lo, w);
    }
    if b.is_point() {
        return q_scale(a, &b.lo, w);
    }
    hull(
        vec![
            mul(&a.lo, &b.lo, w)?,
            mul(&a.lo, &b.hi, w)?,
            mul(&a.hi, &b.lo, w)?,
            mul(&a.hi, &b.hi, w)?,
        ],
        w,
    )
}
fn q_div(a: &Q, b: &Q, w: &Work) -> Result<Q, Error> {
    if !(b.lo.is_positive() || b.hi.is_negative()) {
        return Err(Error::new(
            "waveform_accuracy",
            "division denominator interval contains zero in the exact same-time equation",
        ));
    }
    let one = R::one();
    let inverse = if b.is_point() {
        Q::point(div(&one, &b.lo, w)?)
    } else {
        Q {
            lo: div(&one, &b.hi, w)?,
            hi: div(&one, &b.lo, w)?,
        }
    };
    q_mul(a, &inverse, w)
}
fn q_pow(a: &Q, exponent: u32, w: &Work) -> Result<Q, Error> {
    let power = |value: &R| -> Result<R, Error> {
        let mut result = R::one();
        for _ in 0..exponent {
            result = mul(&result, value, w)?;
        }
        Ok(result)
    };
    if a.is_point() {
        return Ok(Q::point(power(&a.lo)?));
    }
    let (lo, hi) = (power(&a.lo)?, power(&a.hi)?);
    Ok(if exponent % 2 == 1 || !a.lo.is_negative() {
        Q { lo, hi }
    } else if !a.hi.is_positive() {
        Q { lo: hi, hi: lo }
    } else {
        Q {
            lo: R::zero(),
            hi: if less(&lo, &hi, w)? { hi } else { lo },
        }
    })
}

/// The binary64 interval that encloses an exact interval.
fn outward(a: &Q, name: &str, w: &Work) -> Result<I, Error> {
    let lo = nearest(&a.lo, name, w)?;
    let hi = nearest(&a.hi, name, w)?;
    let lo = if less(&a.lo, &binary(lo, w)?, w)? {
        lo.next_down()
    } else {
        lo
    };
    let hi = if less(&binary(hi, w)?, &a.hi, w)? {
        hi.next_up()
    } else {
        hi
    };
    Ok(I { lo, hi })
}

/// The binary64 interval that encloses an exact interval.
pub(crate) fn enclosure(a: &Q, name: &str, w: &Work) -> Result<I, Error> {
    outward(a, name, w)
}

/// The exact sum of two exact intervals.
pub(crate) fn sum(a: &Q, b: &Q, w: &Work) -> Result<Q, Error> {
    q_add(a, b, w)
}

/// An exact interval times a binary64 factor.
pub(crate) fn scaled(a: &Q, factor: f64, w: &Work) -> Result<Q, Error> {
    q_scale(a, &binary(factor, w)?, w)
}

/// The exact interval of a finite binary64 interval.
pub(crate) fn exact_interval(value: I, w: &Work) -> Result<Q, Error> {
    if !value.finite() || value.lo > value.hi {
        return Err(Error::new(
            "waveform_accuracy",
            "exact same-time equation needs finite enclosures",
        ));
    }
    let lo = binary(value.lo, w)?;
    let hi = if value.lo.to_bits() == value.hi.to_bits() {
        lo.clone()
    } else {
        binary(value.hi, w)?
    };
    Ok(Q { lo, hi })
}

struct Value {
    value: Q,
    gradient: Vec<Q>,
    /// No binary64 enclosure of a transcendental function was used.
    exact: bool,
}

fn zeros(n: usize) -> Vec<Q> {
    vec![Q::point(R::zero()); n]
}

/// One right-hand side over the members `x`, with its gradient in the members
/// when `n` is their count (no gradient when `n` is zero).
fn evaluate(e: &Expression, cycle: &Cycle, x: &[Q], n: usize, w: &Work) -> Result<Value, Error> {
    w.step()?;
    w.debit(2, (n as u64).saturating_mul(16).saturating_add(32))?;
    let pair = |l: &Expression, r: &Expression| -> Result<(Value, Value), Error> {
        Ok((evaluate(l, cycle, x, n, w)?, evaluate(r, cycle, x, n, w)?))
    };
    Ok(match e {
        Expression::Affine { constant, terms } => {
            let mut value = Q::point(binary(*constant, w)?);
            let mut gradient = zeros(n);
            for term in terms {
                w.step()?;
                let coefficient = binary(term.coefficient, w)?;
                let read = match cycle.column.get(term.node).copied().flatten() {
                    Some(j) => {
                        if n > 0 {
                            gradient[j] = q_add(&gradient[j], &Q::point(coefficient.clone()), w)?;
                        }
                        x[j].clone()
                    }
                    None => cycle
                        .values
                        .get(term.node)
                        .and_then(Option::as_ref)
                        .cloned()
                        .ok_or_else(|| {
                            Error::new(
                                "invalid_ir",
                                "exact same-time equation reads a node without a value",
                            )
                        })?,
                };
                value = q_add(&value, &q_scale(&read, &coefficient, w)?, w)?;
            }
            Value {
                value,
                gradient,
                exact: true,
            }
        }
        Expression::Add { left, right } => {
            let (a, b) = pair(left, right)?;
            let mut gradient = Vec::with_capacity(n);
            for (x, y) in a.gradient.iter().zip(&b.gradient) {
                gradient.push(q_add(x, y, w)?);
            }
            Value {
                value: q_add(&a.value, &b.value, w)?,
                gradient,
                exact: a.exact && b.exact,
            }
        }
        Expression::Multiply { left, right } => {
            let (a, b) = pair(left, right)?;
            let mut gradient = Vec::with_capacity(n);
            for (x, y) in a.gradient.iter().zip(&b.gradient) {
                gradient.push(q_add(
                    &q_mul(x, &b.value, w)?,
                    &q_mul(&a.value, y, w)?,
                    w,
                )?);
            }
            Value {
                value: q_mul(&a.value, &b.value, w)?,
                gradient,
                exact: a.exact && b.exact,
            }
        }
        Expression::Divide { left, right } => {
            let (a, b) = pair(left, right)?;
            let value = q_div(&a.value, &b.value, w)?;
            let mut gradient = Vec::with_capacity(n);
            for (x, y) in a.gradient.iter().zip(&b.gradient) {
                // d(a/b) = (da - (a/b) db) / b
                gradient.push(q_div(&q_sub(x, &q_mul(&value, y, w)?, w)?, &b.value, w)?);
            }
            Value {
                value,
                gradient,
                exact: a.exact && b.exact,
            }
        }
        Expression::Power { base, exponent } => {
            let a = evaluate(base, cycle, x, n, w)?;
            let mut gradient = zeros(n);
            if *exponent > 0 && n > 0 {
                let slope = q_scale(
                    &q_pow(&a.value, exponent - 1, w)?,
                    &R::from_integer((*exponent).into()),
                    w,
                )?;
                for (g, d) in gradient.iter_mut().zip(&a.gradient) {
                    *g = q_mul(&slope, d, w)?;
                }
            }
            Value {
                value: q_pow(&a.value, *exponent, w)?,
                gradient,
                exact: a.exact,
            }
        }
        Expression::EventMath { function, args, .. }
            if args.len() == 1 && crate::operators::Function::from_internal(*function).is_some() =>
        {
            let function = crate::operators::Function::from_internal(*function).unwrap();
            w.debit(2, 4096)?;
            let a = evaluate(&args[0], cycle, x, n, w)?;
            let enclosure = outward(&a.value, cycle.name, w)?;
            let value = exact_interval(function.bounds(enclosure)?, w)?;
            let mut gradient = Vec::with_capacity(n);
            if n > 0 {
                let slope = exact_interval(function.derivative(enclosure)?, w)?;
                for d in &a.gradient {
                    gradient.push(q_mul(&slope, d, w)?);
                }
            }
            Value {
                value,
                gradient,
                exact: false,
            }
        }
        _ => {
            return Err(Error::new(
                "waveform_accuracy",
                format!(
                    "the exact same-time equation of {} has an operation without a rational or interval form",
                    cycle.name
                ),
            ))
        }
    })
}

/// F(x) = x - sign * sum(rhs) of every relation, with its gradient when `n`
/// is the member count.
fn residual(cycle: &Cycle, x: &[Q], n: usize, w: &Work) -> Result<Vec<Value>, Error> {
    let mut out = Vec::with_capacity(cycle.relations.len());
    for (c, relation) in cycle.relations.iter().enumerate() {
        w.step()?;
        let mut sum = Value {
            value: Q::point(R::zero()),
            gradient: zeros(n),
            exact: true,
        };
        for rhs in &relation.rhs {
            let term = evaluate(rhs, cycle, x, n, w)?;
            sum.value = q_add(&sum.value, &term.value, w)?;
            for (g, d) in sum.gradient.iter_mut().zip(&term.gradient) {
                *g = q_add(g, d, w)?;
            }
            sum.exact &= term.exact;
        }
        let sign = binary(relation.sign, w)?;
        let value = q_sub(&x[c], &q_scale(&sum.value, &sign, w)?, w)?;
        let mut gradient = Vec::with_capacity(n);
        for g in &sum.gradient {
            gradient.push(q_neg(&q_scale(g, &sign, w)?, w)?);
        }
        if n > 0 {
            gradient[c] = q_add(&gradient[c], &Q::point(R::one()), w)?;
        }
        out.push(Value {
            value,
            gradient,
            exact: sum.exact,
        });
    }
    Ok(out)
}

/// x with A x = b in rationals; None when A is singular.
fn solve_exact(mut a: Vec<Vec<R>>, mut b: Vec<R>, w: &Work) -> Result<Option<Vec<R>>, Error> {
    let n = b.len();
    for k in 0..n {
        w.step()?;
        let Some(pivot) = (k..n).find(|&i| !a[i][k].is_zero()) else {
            return Ok(None);
        };
        a.swap(k, pivot);
        b.swap(k, pivot);
        let row = a[k].clone();
        let rhs = b[k].clone();
        for i in k + 1..n {
            w.step()?;
            if a[i][k].is_zero() {
                continue;
            }
            let factor = div(&a[i][k], &row[k], w)?;
            for j in k..n {
                let product = mul(&factor, &row[j], w)?;
                a[i][j] = sub(&a[i][j], &product, w)?;
            }
            let product = mul(&factor, &rhs, w)?;
            b[i] = sub(&b[i], &product, w)?;
        }
    }
    let mut x = vec![R::zero(); n];
    for k in (0..n).rev() {
        w.step()?;
        let mut sum = b[k].clone();
        for j in k + 1..n {
            let product = mul(&a[k][j], &x[j], w)?;
            sum = sub(&sum, &product, w)?;
        }
        x[k] = div(&sum, &a[k][k], w)?;
    }
    Ok(Some(x))
}

/// The root by one exact Newton step from the members' values `start`: Some
/// when the relations are rational, every value they read is a point (their
/// residual and Jacobian are points), the Jacobian at `start` is nonsingular
/// and the step lands exactly on a root. A value they do not read may be an
/// interval.
pub(crate) fn exact_root(cycle: &Cycle, start: &[f64], w: &Work) -> Result<Option<Vec<R>>, Error> {
    let n = cycle.relations.len();
    if start.len() != n {
        return Err(Error::new(
            "invalid_ir",
            "exact same-time root needs one start value per member",
        ));
    }
    let mut x0 = Vec::with_capacity(n);
    for &value in start {
        x0.push(binary(value, w)?);
    }
    let points = x0.iter().cloned().map(Q::point).collect::<Vec<_>>();
    let at_start = residual(cycle, &points, n, w)?;
    if at_start
        .iter()
        .any(|v| !v.exact || !v.value.is_point() || v.gradient.iter().any(|g| !g.is_point()))
    {
        return Ok(None);
    }
    let jacobian = at_start
        .iter()
        .map(|v| v.gradient.iter().map(|g| g.lo.clone()).collect())
        .collect();
    let values = at_start.iter().map(|v| v.value.lo.clone()).collect();
    let Some(step) = solve_exact(jacobian, values, w)? else {
        return Ok(None);
    };
    let mut root = Vec::with_capacity(n);
    for (x, d) in x0.iter().zip(&step) {
        root.push(sub(x, d, w)?);
    }
    let points = root.iter().cloned().map(Q::point).collect::<Vec<_>>();
    let at_root = residual(cycle, &points, 0, w)?;
    Ok(at_root
        .iter()
        .all(|v| v.value.is_point() && v.value.lo.is_zero())
        .then_some(root))
}

/// A start for the certificate of a cycle whose binary64 Newton cannot meet
/// its residual tolerance (a magnitude whose binary64 spacing exceeds it):
/// exact Newton steps from `start`, each iterate kept on the grid
/// FIRST_BITS below its magnitude, until two iterates round alike. None when
/// the relations are not rational with point inputs, a Jacobian is singular,
/// or the iterates do not settle. This proves nothing; the certificate does.
pub(crate) fn newton_start(
    cycle: &Cycle,
    start: &[f64],
    w: &Work,
) -> Result<Option<Vec<f64>>, Error> {
    let n = cycle.relations.len();
    if start.len() != n {
        return Ok(None);
    }
    let mut x = Vec::with_capacity(n);
    for &value in start {
        x.push(binary(value, w)?);
    }
    let mut previous: Option<Vec<f64>> = None;
    for _ in 0..ROUNDS {
        w.step()?;
        let points = x.iter().cloned().map(Q::point).collect::<Vec<_>>();
        let at = residual(cycle, &points, n, w)?;
        if at
            .iter()
            .any(|v| !v.exact || !v.value.is_point() || v.gradient.iter().any(|g| !g.is_point()))
        {
            return Ok(None);
        }
        let jacobian = at
            .iter()
            .map(|v| v.gradient.iter().map(|g| g.lo.clone()).collect())
            .collect();
        let values = at.iter().map(|v| v.value.lo.clone()).collect();
        let Some(step) = solve_exact(jacobian, values, w)? else {
            return Ok(None);
        };
        let mut next = Vec::with_capacity(n);
        for (value, delta) in x.iter().zip(&step) {
            next.push(coarsen(Q::point(sub(value, delta, w)?), FIRST_BITS, w)?.lo);
        }
        x = next;
        let mut rounded = Vec::with_capacity(n);
        for value in &x {
            rounded.push(nearest(value, cycle.name, w)?);
        }
        if previous.as_ref().is_some_and(|p| {
            p.iter()
                .zip(&rounded)
                .all(|(a, b)| a.to_bits() == b.to_bits())
        }) {
            return Ok(Some(rounded));
        }
        previous = Some(rounded);
    }
    Ok(None)
}

fn pow2(exponent: i64) -> R {
    let one = R::one();
    let shifted = one.numer() << (exponent.unsigned_abs() as usize);
    if exponent >= 0 {
        R::from_integer(shifted)
    } else {
        R::new(one.numer().clone(), shifted)
    }
}

/// Roughly log2 of the larger end magnitude of a nonzero interval.
fn magnitude(a: &Q) -> Option<i64> {
    let scale = |v: &R| -> Option<i64> {
        (!v.is_zero()).then(|| v.numer().bits() as i64 - v.denom().bits() as i64)
    };
    match (scale(&a.lo), scale(&a.hi)) {
        (Some(x), Some(y)) => Some(x.max(y)),
        (x, y) => x.or(y),
    }
}

/// The interval rounded outward to the grid `bits` below its magnitude.
fn coarsen(a: Q, bits: i64, w: &Work) -> Result<Q, Error> {
    let Some(scale) = magnitude(&a) else {
        return Ok(a);
    };
    let grid = pow2(scale - bits);
    let lo = div(&a.lo, &grid, w)?.floor();
    let hi = div(&a.hi, &grid, w)?.ceil();
    Ok(Q {
        lo: mul(&lo, &grid, w)?,
        hi: mul(&hi, &grid, w)?,
    })
}

/// A grid point of the interval near its middle.
fn middle(a: &Q, bits: i64, w: &Work) -> Result<R, Error> {
    let half = R::new(1.into(), 2.into());
    let exact = mul(&add(&a.lo, &a.hi, w)?, &half, w)?;
    let Some(scale) = magnitude(a) else {
        return Ok(exact);
    };
    let grid = pow2(scale - bits);
    let point = mul(&div(&exact, &grid, w)?.floor(), &grid, w)?;
    Ok(if less(&point, &a.lo, w)? {
        exact
    } else {
        point
    })
}

/// The inverse of the binary64 midpoint Jacobian, as exact rationals.
fn preconditioner(jacobian: &[Value], name: &str, w: &Work) -> Result<Vec<Vec<R>>, Error> {
    let n = jacobian.len();
    let refuse = || {
        Error::new(
            "waveform_accuracy",
            format!("cannot build the refinement preconditioner of the exact same-time equation of {name}"),
        )
    };
    w.debit(
        2,
        ((n * n + n) as u64).saturating_mul(64).saturating_add(64),
    )?;
    let mut rows = Vec::with_capacity(n);
    for v in jacobian {
        let mut row = Vec::new();
        for (k, g) in v.gradient.iter().enumerate() {
            let middle =
                (g.lo.to_f64().unwrap_or(f64::NAN) + g.hi.to_f64().unwrap_or(f64::NAN)) / 2.;
            if !middle.is_finite() {
                return Err(refuse());
            }
            if middle != 0. {
                row.push((k, middle));
            }
        }
        rows.push(row);
    }
    let factor = crate::linear::Factorization::new(rows, n).map_err(|_| refuse())?;
    let mut inverse = vec![vec![R::zero(); n]; n];
    for i in 0..n {
        let mut unit = vec![0.; n];
        unit[i] = 1.;
        let column = factor.solve(unit).map_err(|_| refuse())?;
        for (j, value) in column.into_iter().enumerate() {
            if !value.is_finite() {
                return Err(refuse());
            }
            inverse[j][i] = binary(value, w)?;
        }
    }
    Ok(inverse)
}

/// The Krawczyk image of the box intersected with it, rounded outward to the
/// grid and kept inside the box; None when some component has no common
/// point with its image, so the box holds no root.
fn krawczyk(cycle: &Cycle, b: &[Q], bits: i64, w: &Work) -> Result<Option<Vec<Q>>, Error> {
    let n = b.len();
    let mut centre = Vec::with_capacity(n);
    for q in b {
        centre.push(middle(q, bits, w)?);
    }
    let points = centre.iter().cloned().map(Q::point).collect::<Vec<_>>();
    let at_centre = residual(cycle, &points, 0, w)?;
    let over_box = residual(cycle, b, n, w)?;
    let c = preconditioner(&over_box, cycle.name, w)?;
    let mut out = Vec::with_capacity(n);
    for j in 0..n {
        w.step()?;
        let mut image = Q::point(centre[j].clone());
        for i in 0..n {
            image = q_sub(&image, &q_scale(&at_centre[i].value, &c[j][i], w)?, w)?;
        }
        for k in 0..n {
            let mut entry = Q::point(if j == k { R::one() } else { R::zero() });
            for i in 0..n {
                entry = q_sub(&entry, &q_scale(&over_box[i].gradient[k], &c[j][i], w)?, w)?;
            }
            let offset = Q {
                lo: sub(&b[k].lo, &centre[k], w)?,
                hi: sub(&b[k].hi, &centre[k], w)?,
            };
            image = q_add(&image, &q_mul(&entry, &offset, w)?, w)?;
        }
        let lo = if less(&image.lo, &b[j].lo, w)? {
            b[j].lo.clone()
        } else {
            image.lo
        };
        let hi = if less(&b[j].hi, &image.hi, w)? {
            b[j].hi.clone()
        } else {
            image.hi
        };
        if less(&hi, &lo, w)? {
            return Ok(None);
        }
        let grid = coarsen(Q { lo, hi }, bits, w)?;
        out.push(Q {
            lo: if less(&grid.lo, &b[j].lo, w)? {
                b[j].lo.clone()
            } else {
                grid.lo
            },
            hi: if less(&b[j].hi, &grid.hi, w)? {
                b[j].hi.clone()
            } else {
                grid.hi
            },
        });
    }
    Ok(Some(out))
}

/// The rounding boundary just above RN(lo): the zero between -0 and +0, or
/// the midpoint between RN(lo) and the next binary64.
fn boundary(rounded_lo: f64, w: &Work) -> Result<R, Error> {
    if rounded_lo == 0. && rounded_lo.is_sign_negative() {
        return Ok(R::zero());
    }
    let half = R::new(1.into(), 2.into());
    mul(
        &add(
            &binary(rounded_lo, w)?,
            &binary(rounded_lo.next_up(), w)?,
            w,
        )?,
        &half,
        w,
    )
}

fn lost(name: &str) -> Error {
    Error::new(
        "invalid_ir",
        format!("the certified exact same-time root of {name} left its enclosure"),
    )
}

/// RN of the unique root in the certified box `start`, by refinement, with
/// the final enclosure of the root, per member.
pub(crate) fn refine(cycle: &Cycle, start: &[I], w: &Work) -> Result<Vec<(f64, Q)>, Error> {
    let n = start.len();
    if n != cycle.relations.len() {
        return Err(Error::new(
            "invalid_ir",
            "exact same-time refinement needs one enclosure per member",
        ));
    }
    let mut b = Vec::with_capacity(n);
    for &bound in start {
        b.push(exact_interval(bound, w)?);
    }
    let points = cycle.values.iter().flatten().all(Q::is_point);
    let mut bits = FIRST_BITS;
    let mut stalled = false;
    for _ in 0..ROUNDS {
        w.step()?;
        let mut ends = Vec::with_capacity(n);
        for q in &b {
            ends.push((
                nearest(&q.lo, cycle.name, w)?,
                nearest(&q.hi, cycle.name, w)?,
            ));
        }
        let Some(open) = ends
            .iter()
            .position(|(lo, hi)| lo.to_bits() != hi.to_bits())
        else {
            return Ok(ends.into_iter().map(|(value, _)| value).zip(b).collect());
        };
        if !stalled {
            let next = krawczyk(cycle, &b, bits, w)?.ok_or_else(|| lost(cycle.name))?;
            let mut halved = false;
            for (j, (old, new)) in b.iter().zip(&next).enumerate() {
                if ends[j].0.to_bits() == ends[j].1.to_bits() {
                    continue;
                }
                let before = sub(&old.hi, &old.lo, w)?;
                let after = sub(&new.hi, &new.lo, w)?;
                halved |= !less(&before, &add(&after, &after, w)?, w)?;
            }
            b = next;
            if !halved {
                if bits < LAST_BITS {
                    bits = (bits * 2).min(LAST_BITS);
                } else {
                    stalled = true;
                }
            }
            continue;
        }
        // The contraction stalls on the finest grid: split the first open
        // component at its rounding boundary and keep the half the Krawczyk
        // test cannot exclude.
        stalled = false;
        let t = boundary(ends[open].0, w)?;
        let (mut left, mut right) = (b.clone(), b.clone());
        left[open].hi = t.clone();
        right[open].lo = t.clone();
        match (
            krawczyk(cycle, &left, bits, w)?,
            krawczyk(cycle, &right, bits, w)?,
        ) {
            (Some(l), None) => b = l,
            (None, Some(r)) => b = r,
            (None, None) => return Err(lost(cycle.name)),
            (Some(_), Some(_)) => {
                // One unknown with point inputs: a root exactly at the
                // boundary is the boundary itself, rounded ties to even.
                if n == 1 && points {
                    let at = residual(cycle, &[Q::point(t.clone())], 0, w)?;
                    if at[0].value.is_point() && at[0].value.lo.is_zero() {
                        return Ok(vec![(nearest(&t, cycle.name, w)?, Q::point(t))]);
                    }
                }
                break;
            }
        }
    }
    Err(Error::new(
        "waveform_accuracy",
        format!(
            "cannot determine the binary64 rounding of the exact same-time root of {}: its enclosure straddles a rounding boundary",
            cycle.name
        ),
    ))
}

/// The value of an expression with its rounding steps, over exact intervals:
/// each rounded image is the binary64 rounding of both ends. None for a
/// transcendental function or an operation without an exact form.
pub(crate) fn rounded_image(
    e: &Expression,
    values: &[Option<Q>],
    w: &Work,
) -> Result<Option<Q>, Error> {
    w.step()?;
    let pair = |l: &Expression, r: &Expression| -> Result<Option<(Q, Q)>, Error> {
        Ok(rounded_image(l, values, w)?.zip(rounded_image(r, values, w)?))
    };
    let rounded = |q: Q| -> Result<Q, Error> {
        let lo = binary(nearest(&q.lo, "a rounded value", w)?, w)?;
        let hi = if q.is_point() {
            lo.clone()
        } else {
            binary(nearest(&q.hi, "a rounded value", w)?, w)?
        };
        Ok(Q { lo, hi })
    };
    Ok(match e {
        Expression::Affine { constant, terms } => {
            let mut value = Q::point(binary(*constant, w)?);
            for term in terms {
                w.step()?;
                let Some(read) = values.get(term.node).and_then(Option::as_ref) else {
                    return Ok(None);
                };
                value = q_add(&value, &q_scale(read, &binary(term.coefficient, w)?, w)?, w)?;
            }
            Some(value)
        }
        Expression::Add { left, right } => match pair(left, right)? {
            Some((a, b)) => Some(q_add(&a, &b, w)?),
            None => None,
        },
        Expression::Multiply { left, right } => match pair(left, right)? {
            Some((a, b)) => Some(q_mul(&a, &b, w)?),
            None => None,
        },
        Expression::Divide { left, right } => match pair(left, right)? {
            Some((a, b)) if b.lo.is_positive() || b.hi.is_negative() => Some(q_div(&a, &b, w)?),
            _ => None,
        },
        Expression::Power { base, exponent } => match rounded_image(base, values, w)? {
            Some(a) => Some(q_pow(&a, *exponent, w)?),
            None => None,
        },
        Expression::RealBoundary { value, .. } => match rounded_image(value, values, w)? {
            Some(a) => Some(rounded(a)?),
            None => None,
        },
        Expression::RealBinary {
            operation,
            left,
            right,
            ..
        } => {
            use crate::ir::RealOperation as Op;
            let Some((a, b)) = pair(left, right)? else {
                return Ok(None);
            };
            let exact = match operation {
                Op::Add => q_add(&a, &b, w)?,
                Op::Subtract => q_sub(&a, &b, w)?,
                Op::Multiply => q_mul(&a, &b, w)?,
                Op::Divide if b.lo.is_positive() || b.hi.is_negative() => q_div(&a, &b, w)?,
                Op::Divide => return Ok(None),
            };
            Some(rounded(exact)?)
        }
        _ => None,
    })
}

#[cfg(test)]
mod tests {
    //! Expected values were computed independently with Python's
    //! fractions.Fraction (float(Fraction) rounds once, ties to even) and
    //! exact bisection; see the R2 delivery notes. None comes from EVAS.
    use super::*;
    use crate::ir::Term;

    fn ratio(numerator: i64, denominator: i64) -> R {
        R::new(numerator.into(), denominator.into())
    }
    fn two_to(exponent: i64) -> R {
        pow2(exponent)
    }
    fn affine(constant: f64, terms: &[(usize, f64)]) -> Expression {
        Expression::Affine {
            constant,
            terms: terms
                .iter()
                .map(|&(node, coefficient)| Term { node, coefficient })
                .collect(),
        }
    }
    fn product(left: Expression, right: Expression) -> Expression {
        Expression::Multiply {
            left: Box::new(left),
            right: Box::new(right),
        }
    }
    fn sum(left: Expression, right: Expression) -> Expression {
        Expression::Add {
            left: Box::new(left),
            right: Box::new(right),
        }
    }
    fn cube(node: usize) -> Expression {
        Expression::Power {
            base: Box::new(affine(0., &[(node, 1.)])),
            exponent: 3,
        }
    }

    #[test]
    fn nearest_rounds_once_ties_to_even_with_subnormals_zero_signs_and_overflow() {
        let w = Work::default();
        let one = R::one();
        for (value, bits) in [
            (ratio(2, 3), 0x3fe5555555555555_u64),
            (&one + two_to(-53), 0x3ff0000000000000),
            (
                &one + R::from_integer(3.into()) * two_to(-53),
                0x3ff0000000000002,
            ),
            (R::from_integer(3.into()) * two_to(-1076), 0x1),
            (R::from_integer(3.into()) * two_to(-1075), 0x2),
            (-two_to(-1076), 0x8000000000000000),
            (-two_to(-1075), 0x8000000000000000),
            (R::zero(), 0x0),
            (two_to(1024) - two_to(970) - R::one(), 0x7fefffffffffffff),
        ] {
            assert_eq!(
                nearest(&value, "test", &w).unwrap().to_bits(),
                bits,
                "{value}"
            );
        }
        let error = nearest(&(two_to(1024) - two_to(970)), "test", &w).unwrap_err();
        assert_eq!(error.kind, "nonfinite_arithmetic");
    }

    #[test]
    fn one_exact_newton_step_solves_affine_cycles() {
        let w = Work::default();
        // s = -0.5*s + 1 (node 1): the root 2/3 has no binary64 fixed point
        // of the rounded map; RN(2/3) is 0x3fe5555555555555.
        let scalar = [Relation {
            sign: 1.,
            rhs: vec![affine(1., &[(1, -0.5)])],
        }];
        let column = [None, Some(0)];
        let values = [Some(Q::point(R::zero())), None];
        let cycle = Cycle {
            relations: &scalar,
            column: &column,
            values: &values,
            name: "test",
        };
        let root = exact_root(&cycle, &[0.6666666666666667], &w)
            .unwrap()
            .unwrap();
        assert_eq!(root, vec![ratio(2, 3)]);
        assert_eq!(
            nearest(&root[0], "test", &w).unwrap().to_bits(),
            0x3fe5555555555555
        );
        // s = a*y + b*z + f, h = c*y + d*z + g with y = s, z = h (method 32,
        // system 17): the root is (-2/21, 34/21).
        let (a, b, c, d, f, g) = (-0.125, -0.375, -0.125, 0.375, 0.5, 1.);
        let coupled = [
            Relation {
                sign: 1.,
                rhs: vec![affine(f, &[(1, a), (2, b)])],
            },
            Relation {
                sign: 1.,
                rhs: vec![affine(g, &[(1, c), (2, d)])],
            },
        ];
        let column = [None, Some(0), Some(1)];
        let values = [Some(Q::point(R::zero())), None, None];
        let cycle = Cycle {
            relations: &coupled,
            column: &column,
            values: &values,
            name: "test",
        };
        let root = exact_root(&cycle, &[0., 0.], &w).unwrap().unwrap();
        assert_eq!(root, vec![ratio(-2, 21), ratio(34, 21)]);
        let rounded = root
            .iter()
            .map(|v| nearest(v, "test", &w).unwrap())
            .collect::<Vec<_>>();
        assert_eq!(rounded, vec![-0.09523809523809523, 1.619047619047619]);
        // s = -0.5*s + u: an interval input u the cycle reads is not a point,
        // so no exact step; an interval it does not read (node 0) is ignored.
        let input = [Relation {
            sign: 1.,
            rhs: vec![affine(0., &[(1, -0.5), (2, 1.)])],
        }];
        let column = [None, Some(0), None];
        let unread = Q {
            lo: R::zero(),
            hi: two_to(-60),
        };
        for (u, root) in [
            (Q::point(R::one()), Some(vec![ratio(2, 3)])),
            (
                Q {
                    lo: R::one(),
                    hi: R::one() + two_to(-60),
                },
                None,
            ),
        ] {
            let values = [Some(unread.clone()), None, Some(u)];
            let cycle = Cycle {
                relations: &input,
                column: &column,
                values: &values,
                name: "test",
            };
            assert_eq!(exact_root(&cycle, &[0.], &w).unwrap(), root);
        }
    }

    // y = u - 0.25*y^3 with y at node 2 and u at node 1.
    fn cubic() -> [Relation; 1] {
        [Relation {
            sign: 1.,
            rhs: vec![sum(
                affine(0., &[(1, 1.)]),
                product(affine(-0.25, &[]), cube(2)),
            )],
        }]
    }

    #[test]
    fn refinement_rounds_the_irrational_root_of_a_cubic() {
        let relations = cubic();
        let column = [None, None, Some(0)];
        // RN of the roots: 1.0466710176581202 and 1.3646556076560385.
        for (u, bits) in [
            (ratio(4, 3), 0x3ff0bf2a1be833e0_u64),
            (R::from_integer(2.into()), 0x3ff5d5a11e52f899),
        ] {
            let w = Work::default();
            let values = [Some(Q::point(R::zero())), Some(Q::point(u.clone())), None];
            let cycle = Cycle {
                relations: &relations,
                column: &column,
                values: &values,
                name: "test",
            };
            // The step from a binary64 start does not land on the root.
            assert!(exact_root(&cycle, &[1.], &w).unwrap().is_none());
            let result = refine(&cycle, &[I { lo: 1., hi: 1.5 }], &w).unwrap();
            assert_eq!(result[0].0.to_bits(), bits, "{u}");
            let enclosure = &result[0].1;
            assert!(enclosure.lo <= enclosure.hi);
        }
    }

    #[test]
    fn a_nonlinear_root_at_a_rounding_tie() {
        // y^3 = (1 + 2^-53)^3: the root is the midpoint between 1 and
        // 1 + 2^-52. With one unknown and point inputs it rounds to even
        // (1.0); with a second unknown z = y the tie is refused.
        let tie = R::one() + two_to(-53);
        let target = &tie * &tie * &tie;
        let one = [Relation {
            sign: 1.,
            rhs: vec![sum(
                affine(0., &[(2, 1.)]),
                sum(affine(0., &[(1, 1.)]), product(affine(-1., &[]), cube(2))),
            )],
        }];
        let column = [None, None, Some(0)];
        let values = [
            Some(Q::point(R::zero())),
            Some(Q::point(target.clone())),
            None,
        ];
        let cycle = Cycle {
            relations: &one,
            column: &column,
            values: &values,
            name: "test",
        };
        let w = Work::default();
        let result = refine(&cycle, &[I { lo: 0.75, hi: 1.25 }], &w).unwrap();
        assert_eq!(result[0].0.to_bits(), 0x3ff0000000000000);
        assert_eq!(result[0].1, Q::point(tie));
        let two = [
            Relation {
                sign: 1.,
                rhs: vec![sum(
                    affine(0., &[(3, 1.)]),
                    sum(affine(0., &[(1, 1.)]), product(affine(-1., &[]), cube(3))),
                )],
            },
            Relation {
                sign: 1.,
                rhs: vec![affine(0., &[(2, 1.)])],
            },
        ];
        let column = [None, None, Some(0), Some(1)];
        let values = [
            Some(Q::point(R::zero())),
            Some(Q::point(target)),
            None,
            None,
        ];
        let cycle = Cycle {
            relations: &two,
            column: &column,
            values: &values,
            name: "test",
        };
        let w = Work::default();
        let error = refine(
            &cycle,
            &[I { lo: 0.75, hi: 1.25 }, I { lo: 0.75, hi: 1.25 }],
            &w,
        )
        .unwrap_err();
        assert_eq!(error.kind, "waveform_accuracy");
        assert!(
            error.message.contains("straddles a rounding boundary"),
            "{}",
            error.message
        );
    }

    #[test]
    fn refinement_beyond_the_proof_budget_is_refused() {
        let relations = cubic();
        let column = [None, None, Some(0)];
        let values = [Some(Q::point(R::zero())), Some(Q::point(ratio(4, 3))), None];
        let cycle = Cycle {
            relations: &relations,
            column: &column,
            values: &values,
            name: "test",
        };
        let probe = Work::default();
        refine(&cycle, &[I { lo: 1., hi: 1.5 }], &probe).unwrap();
        let w = Work::limited([128, 8192, probe.spent() / 2]);
        let error = refine(&cycle, &[I { lo: 1., hi: 1.5 }], &w).unwrap_err();
        assert_eq!(error.kind, "step_budget");
        let spent = w.spent();
        assert_eq!(
            refine(&cycle, &[I { lo: 1., hi: 1.5 }], &w)
                .unwrap_err()
                .kind,
            "step_budget"
        );
        assert!(w.spent() >= spent);
    }

    #[test]
    fn rounded_images_keep_each_rounding_step() {
        let w = Work::default();
        // RN(RN(3*0.1) - 0.3) = 2^-54, while 3*0.1 - 0.3 is 2^-55 exactly.
        let values = [
            Some(Q::point(R::zero())),
            Some(Q::point(binary(0.1, &w).unwrap())),
        ];
        let origin = crate::ir::Origin {
            source: "test.va".into(),
            line: 1,
            column: 1,
            instance: "dut".into(),
            expansion: Vec::new(),
        };
        let tripled = Expression::RealBinary {
            operation: crate::ir::RealOperation::Multiply,
            left: Box::new(affine(0., &[(1, 1.)])),
            right: Box::new(affine(3., &[])),
            origin: origin.clone(),
        };
        let difference = Expression::RealBinary {
            operation: crate::ir::RealOperation::Subtract,
            left: Box::new(tripled),
            right: Box::new(affine(0.3, &[])),
            origin,
        };
        let image = rounded_image(&difference, &values, &w).unwrap().unwrap();
        assert_eq!(image, Q::point(two_to(-54)));
    }
}
