//! Bounded exact binary64 source arithmetic for phase and ordinary conditions.
//! Curves retain original rational knots; rounded clamp knots are never inputs.
use crate::interval::Interval as I;
use crate::ir::Expression;
use num_rational::BigRational as R;
use num_traits::{Signed, ToPrimitive, Zero};

pub(crate) const MAX_POINTS: usize = 512;
pub(crate) const MAX_BITS: u64 = 4096;
const MAX_OPS: usize = 200_000;
const MAX_DEPTH: usize = 64;
const MAX_EXPR_NODES: usize = 512;

#[derive(Clone)]
pub(crate) struct Curve(Vec<(R, R)>);
struct Budget(usize);
impl Budget {
    fn check(&mut self, value: R) -> Option<R> {
        self.0 = self.0.checked_add(1)?;
        (self.0 <= MAX_OPS && value.numer().bits() <= MAX_BITS && value.denom().bits() <= MAX_BITS)
            .then_some(value)
    }
}
fn binary(x: f64) -> Option<R> {
    R::from_float(x)
}

// A point evaluation proves the original expression tree, without rounding
// scalar products or reconstructing the source from projected clamp knots.
fn evaluate(
    e: &Expression,
    nodes: &[usize],
    sources: &[Option<Curve>],
    time: &R,
    budget: &mut Budget,
    depth: usize,
    count: &mut usize,
) -> Option<R> {
    *count += 1;
    if depth > MAX_DEPTH || *count > MAX_EXPR_NODES {
        return None;
    }
    match e {
        Expression::Affine { constant, terms } => {
            if terms.len() > MAX_POINTS {
                return None;
            }
            let mut value = binary(*constant)?;
            for term in terms {
                if term.node == 0 {
                    continue;
                }
                let k = nodes.iter().position(|n| *n == term.node)?;
                let v = sources.get(k)?.as_ref()?.value(time, budget)?;
                let product = budget.check(binary(term.coefficient)? * v)?;
                value = budget.check(value + product)?;
            }
            Some(value)
        }
        Expression::Add { left, right } | Expression::Multiply { left, right } => {
            let a = evaluate(left, nodes, sources, time, budget, depth + 1, count)?;
            let b = evaluate(right, nodes, sources, time, budget, depth + 1, count)?;
            budget.check(if matches!(e, Expression::Add { .. }) {
                a + b
            } else {
                a * b
            })
        }
        _ => None,
    }
}

/// Certify a comparison at the original binary64 query time. The caller first
/// validates predicate affinity and source ownership; absent exact provenance
/// or an exceeded resource budget yields no certificate.
pub(crate) fn predicate_sign(
    left: &Expression,
    right: &Expression,
    nodes: &[usize],
    sources: &[Option<Curve>],
    time: f64,
) -> Option<i8> {
    let time = binary(time)?;
    let mut budget = Budget(0);
    let mut count = 0;
    let left = evaluate(left, nodes, sources, &time, &mut budget, 0, &mut count)?;
    let right = evaluate(right, nodes, sources, &time, &mut budget, 0, &mut count)?;
    let difference = budget.check(left - right)?;
    Some(if difference.is_zero() {
        0
    } else if difference.is_positive() {
        1
    } else {
        -1
    })
}

impl Curve {
    pub(crate) fn source(points: &[[f64; 2]]) -> Option<Self> {
        if points.len() > MAX_POINTS {
            return None;
        }
        Some(Self(
            points
                .iter()
                .map(|[t, v]| Some((binary(*t)?, binary(*v)?)))
                .collect::<Option<Vec<_>>>()?,
        ))
    }
    fn value(&self, time: &R, budget: &mut Budget) -> Option<R> {
        let index = self.0.partition_point(|p| p.0 < *time);
        let (end, b) = self.0.get(index)?;
        if end == time {
            return Some(b.clone());
        }
        let (start, a) = self.0.get(index.checked_sub(1)?)?;
        let delta = budget.check(b - a)?;
        let elapsed = budget.check(time - start)?;
        let duration = budget.check(end - start)?;
        let fraction = budget.check(elapsed / duration)?;
        let change = budget.check(delta * fraction)?;
        budget.check(a + change)
    }
    pub(crate) fn expression(
        expr: &Expression,
        nodes: &[usize],
        sources: &[Option<Self>],
        stop: f64,
    ) -> Option<Self> {
        // Existing callers validate affinity/ownership first. Recheck degree
        // here as well: endpoint interpolation cannot certify a quadratic.
        fn varying(e: &Expression, depth: usize, count: &mut usize) -> Option<bool> {
            *count += 1;
            if depth > MAX_DEPTH || *count > MAX_EXPR_NODES {
                return None;
            }
            match e {
                Expression::Affine { terms, .. } => Some(terms.iter().any(|t| t.node != 0)),
                Expression::Add { left, right } => {
                    let a = varying(left, depth + 1, count)?;
                    let b = varying(right, depth + 1, count)?;
                    Some(a || b)
                }
                Expression::Multiply { left, right } => {
                    let a = varying(left, depth + 1, count)?;
                    let b = varying(right, depth + 1, count)?;
                    if a && b {
                        None
                    } else {
                        Some(a || b)
                    }
                }
                _ => None,
            }
        }
        varying(expr, 0, &mut 0)?;
        // Only referenced sources contribute knots/uncertainty. Ground is exact.
        fn dependencies(
            e: &Expression,
            out: &mut Vec<usize>,
            depth: usize,
            count: &mut usize,
        ) -> Option<()> {
            *count += 1;
            if depth > MAX_DEPTH || *count > MAX_EXPR_NODES {
                return None;
            }
            match e {
                Expression::Affine { terms, .. } => {
                    if terms.len() > MAX_POINTS {
                        return None;
                    }
                    out.extend(terms.iter().map(|t| t.node).filter(|n| *n != 0))
                }
                Expression::Add { left, right } | Expression::Multiply { left, right } => {
                    dependencies(left, out, depth + 1, count)?;
                    dependencies(right, out, depth + 1, count)?;
                }
                _ => return None,
            }
            (out.len() <= MAX_POINTS).then_some(())
        }
        let mut deps = Vec::new();
        dependencies(expr, &mut deps, 0, &mut 0)?;
        let mut budget = Budget(0);
        let stop = binary(stop)?;
        let mut knots = vec![R::zero(), stop.clone()];
        for node in deps {
            let k = nodes.iter().position(|n| *n == node)?;
            let curve = sources.get(k)?.as_ref()?;
            knots.extend(curve.0.iter().map(|p| p.0.clone()).filter(|t| *t < stop));
            if knots.len() > MAX_POINTS * MAX_POINTS {
                return None;
            }
        }
        knots.sort();
        knots.dedup();
        if knots.len() > MAX_POINTS {
            return None;
        }
        Some(Self(
            knots
                .into_iter()
                .map(|t| {
                    let value = evaluate(expr, nodes, sources, &t, &mut budget, 0, &mut 0)?;
                    Some((t, value))
                })
                .collect::<Option<Vec<_>>>()?,
        ))
    }
    pub(crate) fn clipped(&self, lo: f64, hi: f64) -> Option<Self> {
        let lo = binary(lo)?;
        let hi = binary(hi)?;
        let mut budget = Budget(0);
        let mut result = Vec::new();
        for pair in self.0.windows(2) {
            let (start, a) = &pair[0];
            let (end, b) = &pair[1];
            result.push((start.clone(), a.clone().max(lo.clone()).min(hi.clone())));
            let mut roots = Vec::new();
            if a != b {
                for threshold in [&lo, &hi] {
                    if threshold > a.min(b) && threshold < a.max(b) {
                        let delta = budget.check(b - a)?;
                        let duration = budget.check(end - start)?;
                        let numerator = budget.check((threshold - a) * duration)?;
                        let shift = budget.check(numerator / delta)?;
                        let root = budget.check(start + shift)?;
                        roots.push((root, threshold.clone()));
                    }
                }
            }
            roots.sort();
            result.extend(roots);
            if result.len() >= MAX_POINTS {
                return None;
            }
        }
        let (t, v) = self.0.last()?;
        result.push((t.clone(), v.clone().max(lo).min(hi)));
        Some(Self(result))
    }

    pub(crate) fn wrapped(
        &self,
        time: f64,
        ic: f64,
        modulus: f64,
        offset: f64,
    ) -> Option<(f64, I)> {
        let t = binary(time)?;
        let mut total = binary(ic)?;
        let m = binary(modulus)?;
        let off = binary(offset)?;
        if t < self.0.first()?.0 || t > self.0.last()?.0 || m <= R::zero() {
            return None;
        }
        let mut budget = Budget(0);
        for pair in self.0.windows(2) {
            let (start, a) = &pair[0];
            let (end, b) = &pair[1];
            if t <= *start {
                break;
            }
            let until = t.clone().min(end.clone());
            let value = if until == *end {
                b.clone()
            } else {
                self.value(&until, &mut budget)?
            };
            let sum = budget.check(a + value)?;
            let elapsed = budget.check(until - start)?;
            let area = budget.check(sum * elapsed / R::from_integer(2.into()))?;
            total = budget.check(total + area)?;
        }
        let phase = budget.check(total - &off)?;
        let normalized = budget.check(phase.clone() / &m)?;
        let turn = normalized.floor().to_integer();
        // Retain the existing representable turn-count limit.
        if R::from_integer(turn.clone()).abs() > binary(4_503_599_627_370_496.0)? {
            return None;
        }
        let displacement = budget.check(R::from_integer(turn) * &m)?;
        let wrapped = budget.check(&off + phase - displacement)?;
        let upper = budget.check(off.clone() + m)?;
        let mut value = wrapped.to_f64()?;
        if !value.is_finite() {
            return None;
        }
        // Half-open output: a rounded value may land on the excluded upper
        // endpoint even though the exact phase is strictly below it.
        if binary(value)? >= upper {
            value = value.next_down();
        }
        if binary(value)? < off {
            value = value.next_up();
        }
        let converted = binary(value)?;
        if !value.is_finite() || converted < off || converted >= upper {
            return None;
        }
        let bounds = I {
            lo: if converted > wrapped {
                value.next_down()
            } else {
                value
            },
            hi: if converted < wrapped {
                value.next_up()
            } else {
                value
            },
        };
        (bounds.finite() && binary(bounds.lo)? <= wrapped && wrapped <= binary(bounds.hi)?)
            .then_some((value, bounds))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn ordinary_point_certificate_requires_exact_source_provenance() {
        let input = Expression::Affine {
            constant: 0.0,
            terms: vec![crate::ir::Term {
                node: 1,
                coefficient: 1.0,
            }],
        };
        let threshold = Expression::Affine {
            constant: 0.5,
            terms: vec![],
        };
        let source = Curve::source(&[[0.0, 0.0], [2.0, 1.0]]);
        assert_eq!(
            predicate_sign(&input, &threshold, &[1], &[source], 1.0),
            Some(0)
        );
        // Enclosed/generated sources without exact provenance stay uncertain.
        assert_eq!(predicate_sign(&input, &threshold, &[1], &[None], 1.0), None);
        assert_eq!(predicate_sign(&input, &threshold, &[], &[], 1.0), None);
    }

    #[test]
    fn point_certificate_preserves_nonexact_scalar_products_and_budget() {
        let scalar = |constant| Expression::Affine {
            constant,
            terms: vec![],
        };
        let product = Expression::Multiply {
            left: Box::new(scalar(0.1)),
            right: Box::new(scalar(0.1)),
        };
        // The mathematical product of binary64 0.1 is strictly below the
        // rounded binary64 product. Folding it would incorrectly prove equality.
        assert_eq!(
            predicate_sign(&product, &scalar(0.1 * 0.1), &[], &[], 0.0),
            Some(-1)
        );
        let mut deep = scalar(0.0);
        for _ in 0..=MAX_DEPTH {
            deep = Expression::Add {
                left: Box::new(deep),
                right: Box::new(scalar(0.0)),
            };
        }
        assert_eq!(predicate_sign(&deep, &scalar(0.0), &[], &[], 0.0), None);
    }

    #[test]
    fn ground_terms_are_exact_zero_without_a_driven_source() {
        let expr = Expression::Affine {
            constant: 0.25,
            terms: vec![crate::ir::Term {
                node: 0,
                coefficient: 17.0,
            }],
        };
        let curve = Curve::expression(&expr, &[], &[], 1.0).unwrap();
        assert_eq!(
            curve.value(&binary(0.5).unwrap(), &mut Budget(0)),
            binary(0.25)
        );
    }

    #[test]
    fn resource_limits_admit_boundary_and_fall_back_above_it() {
        for count in [MAX_POINTS - 1, MAX_POINTS, MAX_POINTS + 1] {
            let points: Vec<_> = (0..count).map(|i| [i as f64, 1.0]).collect();
            assert_eq!(Curve::source(&points).is_some(), count <= MAX_POINTS);
        }
        for bits in [MAX_BITS - 1, MAX_BITS, MAX_BITS + 1] {
            let value = R::from_integer(
                num_rational::BigRational::from_float(2.0)
                    .unwrap()
                    .numer()
                    .clone()
                    << (bits - 2) as usize,
            );
            assert_eq!(Budget(0).check(value.clone()).is_some(), bits <= MAX_BITS);
            let reciprocal = R::new(1.into(), value.to_integer());
            assert_eq!(Budget(0).check(reciprocal).is_some(), bits <= MAX_BITS);
        }
        for used in [MAX_OPS - 2, MAX_OPS - 1, MAX_OPS] {
            assert_eq!(Budget(used).check(R::zero()).is_some(), used < MAX_OPS);
        }
    }
    #[test]
    fn expression_size_and_depth_limits_have_bounded_fallback() {
        fn scalar() -> Expression {
            Expression::Affine {
                constant: 1.0,
                terms: vec![],
            }
        }
        for depth in [MAX_DEPTH - 1, MAX_DEPTH, MAX_DEPTH + 1] {
            let mut e = scalar();
            for _ in 0..depth {
                e = Expression::Add {
                    left: Box::new(e),
                    right: Box::new(scalar()),
                };
            }
            assert_eq!(
                Curve::expression(&e, &[], &[], 1.0).is_some(),
                depth <= MAX_DEPTH
            );
        }
        fn tree(leaves: usize) -> Expression {
            if leaves == 1 {
                scalar()
            } else {
                Expression::Add {
                    left: Box::new(tree(leaves / 2)),
                    right: Box::new(tree(leaves - leaves / 2)),
                }
            }
        }
        // A binary expression tree has an odd node count: 511 and 513 are
        // the nearest representable sizes on either side of the 512 limit.
        for leaves in [255, 256, 257] {
            assert_eq!(
                Curve::expression(&tree(leaves), &[], &[], 1.0).is_some(),
                2 * leaves - 1 <= MAX_EXPR_NODES
            );
        }
    }

    #[test]
    fn varying_products_are_not_certified_as_linear_curves() {
        let node = Expression::Affine {
            constant: 0.0,
            terms: vec![crate::ir::Term {
                node: 1,
                coefficient: 1.0,
            }],
        };
        let sources = vec![Curve::source(&[[0.0, 0.0], [1.0, 1.0]])];
        let quadratic = Expression::Multiply {
            left: Box::new(node.clone()),
            right: Box::new(node.clone()),
        };
        assert!(Curve::expression(&quadratic, &[1], &sources, 1.0).is_none());
        let scaled = Expression::Multiply {
            left: Box::new(node),
            right: Box::new(Expression::Affine {
                constant: 2.0,
                terms: vec![],
            }),
        };
        assert!(Curve::expression(&scaled, &[1], &sources, 1.0).is_some());
    }
    #[test]
    fn narrow_nonrepresentable_upper_endpoint_keeps_nominal_in_range() {
        let source = Curve::source(&[[0.0, 0.0], [1.0, 0.0]]).unwrap();
        let (value, bounds) = source.wrapped(1.0, 1e16, 0.1, 1e16).unwrap();
        assert_eq!(value, 1e16);
        assert_eq!(bounds, I::point(1e16));
    }
    #[test]
    fn high_side_rounding_stays_inside_half_open_range_and_encloses_exact_value() {
        let tiny = f64::from_bits(1);
        let source = Curve::source(&[[0.0, -tiny], [1.0, -tiny]]).unwrap();
        let (value, bounds) = source.wrapped(1.0, 0.0, 1.0, 0.0).unwrap();
        assert_eq!(value, 1.0_f64.next_down());
        let exact = binary(1.0).unwrap() - binary(tiny).unwrap();
        assert!(binary(bounds.lo).unwrap() <= exact && exact <= binary(bounds.hi).unwrap());
    }
}
