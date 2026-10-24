//! Complete rational source bands, distinct from exact-value proofs.
//! Handles are request-local and every arithmetic/copy is paid by that owner.
use crate::{
    exact_source::history_paid::Paid,
    interval::Interval as I,
    ir::{Error, Term},
    real_rounding::{self, Image},
    transition_source_plan::Work,
};
use num_rational::BigRational as R;
use num_traits::{Signed, Zero};
use std::{collections::BTreeMap, sync::Arc};

enum Lineage {
    Binary(char, Arc<Domain>, Arc<Domain>),
    Elementary(crate::math_refinement::Function, Arc<Domain>),
}

pub(crate) struct Domain {
    pub(crate) lo: R,
    pub(crate) hi: R,
    owner: Work,
    lineage: Option<Lineage>,
    intrinsic_point: bool,
}
impl Domain {
    fn owned(lo: R, hi: R, w: &Work) -> Result<Option<Arc<Self>>, Error> {
        let mut p = Paid::new(w);
        let order = p.cmp(&lo, &hi);
        let order = p.finish(order)?;
        if order.is_none_or(|o| o.is_gt()) {
            return Ok(None);
        }
        w.debit(2, (std::mem::size_of::<Self>() + 32) as u64)?;
        Ok(Some(Arc::new(Self {
            lo,
            hi,
            owner: w.clone(),
            lineage: None,
            intrinsic_point: order.is_some_and(|o| o.is_eq()),
        })))
    }
    /// Complete caller-proved rational bounds, never an exact-value assertion.
    /// The caller prepays construction/copies; owned validates order and binds
    /// comparison/Arc storage to this same original request owner.
    pub(crate) fn rational_bounds(lo: R, hi: R, w: &Work) -> Result<Option<Arc<Self>>, Error> {
        Self::owned(lo, hi, w)
    }
    /// Enclosure of one mathematical value, not genuine source uncertainty.
    /// Bounds need not coincide: this grants no exact-value proof. Sampling
    /// must certify one RN cell or explicitly fail at the bounded precision.
    pub(crate) fn rational_point_bounds(
        lo: R,
        hi: R,
        w: &Work,
    ) -> Result<Option<Arc<Self>>, Error> {
        Self::owned_with_point(lo, hi, true, w)
    }
    fn owned_with_point(lo: R, hi: R, point: bool, w: &Work) -> Result<Option<Arc<Self>>, Error> {
        let Some(mut value) = Self::owned(lo, hi, w)? else {
            return Ok(None);
        };
        Arc::get_mut(&mut value).unwrap().intrinsic_point |= point;
        Ok(Some(value))
    }
    pub(crate) fn band(center: &R, error: f64, w: &Work) -> Result<Option<Arc<Self>>, Error> {
        let mut p = Paid::new(w);
        let value = (|| {
            let e = p.binary(error)?;
            let lo = p.op(center, &e, '-')?;
            let hi = p.op(center, &e, '+')?;
            Some((lo, hi))
        })();
        match p.finish(value)? {
            Some((lo, hi)) => Self::owned(lo, hi, w),
            None => Ok(None),
        }
    }
    pub(crate) fn point(value: &R, w: &Work) -> Result<Option<Arc<Self>>, Error> {
        let mut p = Paid::new(w);
        let pair = (|| Some((p.copy(value)?, p.copy(value)?)))();
        match p.finish(pair)? {
            Some((lo, hi)) => Self::owned(lo, hi, w),
            None => Ok(None),
        }
    }
    pub(crate) fn share_cost(&self, w: &Work) -> Result<(), Error> {
        if !self.owner.same_owner(w) {
            return Err(Error::new(
                "invalid_ir",
                "source domain belongs to another request",
            ));
        }
        w.debit(2, 16)
    }
    fn scaled(&self, c: f64, w: &Work) -> Result<Option<Arc<Self>>, Error> {
        self.share_cost(w)?;
        let mut p = Paid::new(w);
        let pair = (|| {
            let c = p.binary(c)?;
            let a = p.op(&self.lo, &c, '*')?;
            let b = p.op(&self.hi, &c, '*')?;
            Some(if c.is_negative() { (b, a) } else { (a, b) })
        })();
        match p.finish(pair)? {
            Some((lo, hi)) => Self::owned_with_point(lo, hi, self.intrinsic_point, w),
            None => Ok(None),
        }
    }
    fn add(&self, other: &Self, w: &Work) -> Result<Option<Arc<Self>>, Error> {
        self.share_cost(w)?;
        other.share_cost(w)?;
        let mut p = Paid::new(w);
        let pair = (|| {
            Some((
                p.op(&self.lo, &other.lo, '+')?,
                p.op(&self.hi, &other.hi, '+')?,
            ))
        })();
        match p.finish(pair)? {
            Some((lo, hi)) => {
                Self::owned_with_point(lo, hi, self.intrinsic_point && other.intrinsic_point, w)
            }
            None => Ok(None),
        }
    }
    pub(crate) fn enclosure(bound: I, w: &Work) -> Result<Option<Arc<Self>>, Error> {
        if !bound.finite() {
            return Ok(None);
        }
        let mut p = Paid::new(w);
        let pair = (|| Some((p.binary(bound.lo)?, p.binary(bound.hi)?)))();
        match p.finish(pair)? {
            Some((lo, hi)) => Self::owned(lo, hi, w),
            None => Ok(None),
        }
    }
    fn pair_copy(&self, w: &Work) -> Result<(R, R), Error> {
        self.share_cost(w)?;
        let mut p = Paid::new(w);
        let pair = (|| Some((p.copy(&self.lo)?, p.copy(&self.hi)?)))();
        p.finish(pair)?.ok_or_else(|| {
            Error::new(
                "waveform_accuracy",
                "rational domain copy exceeds its supported width",
            )
        })
    }
    fn binary_bounds(a: (&R, &R), b: (&R, &R), op: char, w: &Work) -> Result<(R, R), Error> {
        let mut p = Paid::new(w);
        let pair = (|| {
            if op == '+' {
                return Some((p.op(a.0, b.0, '+')?, p.op(a.1, b.1, '+')?));
            }
            if op == '/' {
                let zero = p.binary(0.)?;
                if !p.cmp(b.0, &zero)?.is_gt() && !p.cmp(b.1, &zero)?.is_lt() {
                    return None;
                }
            }
            let mut lo = p.op(a.0, b.0, op)?;
            let mut hi = p.copy(&lo)?;
            for (x, y) in [(a.0, b.1), (a.1, b.0), (a.1, b.1)] {
                let v = p.op(x, y, op)?;
                if p.cmp(&v, &lo)?.is_lt() {
                    lo = p.copy(&v)?;
                }
                if p.cmp(&v, &hi)?.is_gt() {
                    hi = v;
                }
            }
            Some((lo, hi))
        })();
        p.finish(pair)?.ok_or_else(|| {
            Error::new(
                "event_domain",
                "mathematical rational domain is undefined or exceeds its supported width",
            )
        })
    }
    fn function_bounds(
        function: crate::math_refinement::Function,
        lo: &R,
        hi: &R,
        bits: u32,
        w: &Work,
    ) -> Result<(R, R), Error> {
        crate::math_refinement::bounds(function, lo, hi, bits, &mut |n| w.debit(2, n)).map_err(
            |fault| match fault {
                crate::math_refinement::Fault::Quota(e) => e,
                crate::math_refinement::Fault::Domain => {
                    Error::new("event_domain", "mathematical function domain is invalid")
                }
                crate::math_refinement::Fault::NonFinite => Error::new(
                    "nonfinite_arithmetic",
                    "nonfinite mathematical function range",
                ),
                crate::math_refinement::Fault::PrecisionLimit => Error::new(
                    "waveform_accuracy",
                    "mathematical function refinement reached its bounded precision",
                ),
            },
        )
    }
    pub(crate) fn binary(
        a: &Arc<Self>,
        b: &Arc<Self>,
        op: char,
        w: &Work,
    ) -> Result<Option<Arc<Self>>, Error> {
        a.share_cost(w)?;
        b.share_cost(w)?;
        let (lo, hi) = Self::binary_bounds((&a.lo, &a.hi), (&b.lo, &b.hi), op, w)?;
        let Some(mut value) = Self::owned(lo, hi, w)? else {
            return Ok(None);
        };
        // The freshly allocated handle is unique. No recursive value clone.
        w.debit(2, 48)?;
        let unique = Arc::get_mut(&mut value).expect("new domain is unique");
        unique.intrinsic_point = a.intrinsic_point && b.intrinsic_point;
        unique.lineage = Some(Lineage::Binary(op, a.clone(), b.clone()));
        Ok(Some(value))
    }
    #[cfg(test)]
    pub(crate) fn elementary(
        function: crate::math_refinement::Function,
        a: &Arc<Self>,
        w: &Work,
    ) -> Result<Option<Arc<Self>>, Error> {
        w.debit(2, 4096)?;
        let native = match function {
            crate::math_refinement::Function::Ln => crate::operators::Function::Ln,
            crate::math_refinement::Function::Exp => crate::operators::Function::Exp,
        };
        let bound = a
            .native_enclosure(w)?
            .map(|b| native.bounds(b))
            .transpose()?;
        Self::elementary_enclosed(function, a, bound, w)
    }
    pub(crate) fn elementary_enclosed(
        function: crate::math_refinement::Function,
        a: &Arc<Self>,
        bound: Option<I>,
        w: &Work,
    ) -> Result<Option<Arc<Self>>, Error> {
        a.share_cost(w)?;
        // Preserve a complete coarse enclosure until an actual source RN
        // consumer requests refinement. Physical observers need no extra
        // transcendental precision and retain the existing function contract.
        let pair = if let Some(bound) = bound.filter(|b| b.finite()) {
            let mut p = Paid::new(w);
            let pair = (|| Some((p.binary(bound.lo)?, p.binary(bound.hi)?)))();
            p.finish(pair)?
        } else {
            Some(Self::function_bounds(function, &a.lo, &a.hi, 64, w)?)
        };
        let Some((lo, hi)) = pair else {
            return Ok(None);
        };
        let Some(mut value) = Self::owned(lo, hi, w)? else {
            return Ok(None);
        };
        w.debit(2, 32)?;
        let unique = Arc::get_mut(&mut value).expect("new domain is unique");
        unique.intrinsic_point = a.intrinsic_point;
        unique.lineage = Some(Lineage::Elementary(function, a.clone()));
        Ok(Some(value))
    }
    fn refined(&self, bits: u32, w: &Work) -> Result<(R, R), Error> {
        // Fresh per-refinement memo. References borrow the immutable DAG; no
        // expression expansion, source replay, or cross-query value cache.
        let mut stack = Vec::new();
        let mut memo: BTreeMap<usize, (R, R)> = BTreeMap::new();
        fn push<'a>(
            stack: &mut Vec<(&'a Domain, bool)>,
            entry: (&'a Domain, bool),
            w: &Work,
        ) -> Result<(), Error> {
            if stack.len() == stack.capacity() {
                let n = stack.capacity().max(1).saturating_mul(2);
                w.debit(
                    2,
                    ((n + stack.len()) * std::mem::size_of::<(&Domain, bool)>()) as u64,
                )?;
                stack.reserve_exact(n - stack.len());
            }
            w.debit(2, 16)?;
            stack.push(entry);
            Ok(())
        }
        push(&mut stack, (self, false), w)?;
        while let Some((node, ready)) = stack.pop() {
            node.share_cost(w)?;
            let key = node as *const Domain as usize;
            w.debit(2, ((memo.len() + 1).ilog2() as u64 + 2) * 32)?;
            if memo.contains_key(&key) {
                continue;
            }
            if !ready {
                push(&mut stack, (node, true), w)?;
                match &node.lineage {
                    Some(Lineage::Binary(_, a, b)) => {
                        push(&mut stack, (b, false), w)?;
                        push(&mut stack, (a, false), w)?;
                    }
                    Some(Lineage::Elementary(_, a)) => push(&mut stack, (a, false), w)?,
                    None => {}
                }
                continue;
            }
            let value = match &node.lineage {
                Some(Lineage::Binary(op, a, b)) => {
                    w.debit(2, ((memo.len() + 1).ilog2() as u64 + 2) * 64)?;
                    let a = &memo[&(a.as_ref() as *const Domain as usize)];
                    let b = &memo[&(b.as_ref() as *const Domain as usize)];
                    Self::binary_bounds((&a.0, &a.1), (&b.0, &b.1), *op, w)?
                }
                Some(Lineage::Elementary(function, a)) => {
                    w.debit(2, ((memo.len() + 1).ilog2() as u64 + 2) * 32)?;
                    let a = &memo[&(a.as_ref() as *const Domain as usize)];
                    Self::function_bounds(*function, &a.0, &a.1, bits, w)?
                }
                None => node.pair_copy(w)?,
            };
            // BTreeMap insertion reserves the entry and a conservative full
            // node split/move allowance before the allocator can run.
            let entry = std::mem::size_of::<(usize, (R, R))>() as u64;
            w.debit(
                2,
                ((memo.len() + 1).ilog2() as u64 + 2)
                    .saturating_mul((entry + 32).saturating_mul(32)),
            )?;
            memo.insert(key, value);
        }
        memo.remove(&(self as *const Domain as usize))
            .ok_or_else(|| Error::new("invalid_ir", "mathematical lineage result missing"))
    }
    pub(crate) fn native_enclosure(&self, w: &Work) -> Result<Option<I>, Error> {
        self.share_cost(w)?;
        let lo = crate::exact_source::enclosure_with_work(&self.lo, w)?;
        let hi = crate::exact_source::enclosure_with_work(&self.hi, w)?;
        Ok(lo
            .zip(hi)
            .map(|(lo, hi)| I {
                lo: lo.lo,
                hi: hi.hi,
            })
            .filter(|b| b.finite()))
    }
    pub(crate) fn contained(&self, b: I, w: &Work) -> Result<bool, Error> {
        self.share_cost(w)?;
        if !b.finite() {
            return Ok(false);
        }
        let mut p = Paid::new(w);
        let yes = (|| {
            let lo = p.binary(b.lo)?;
            let hi = p.binary(b.hi)?;
            Some(!p.cmp(&self.lo, &lo)?.is_lt() && !p.cmp(&self.hi, &hi)?.is_gt())
        })();
        Ok(p.finish(yes)?.unwrap_or(false))
    }
    pub(crate) fn rounded(
        &self,
        fallback: Option<I>,
        nominal: Option<f64>,
        w: &Work,
    ) -> Result<Option<Image>, Error> {
        self.share_cost(w)?;
        // Rational zero has no sign. Preserve the existing complete zero-sign
        // set instead of manufacturing a +0 singleton from its numeric value.
        if self.lo.is_zero() && self.hi.is_zero() {
            if let Some(b) = fallback {
                return crate::real_expression::interval(b, Some(w))
                    .map(|b| Some(Image { lo: b.lo, hi: b.hi }));
            }
            let negative = nominal.is_some_and(|x| x == 0. && x.is_sign_negative());
            let v = if negative { -0. } else { 0. };
            return Ok(Some(Image { lo: v, hi: v }));
        }
        let convert = |lo: &R, hi: &R| {
            real_rounding::image(lo, hi, &mut |n| w.debit(2, n)).map_err(|e| match e {
                real_rounding::Fault::Quota(e) => e,
                other => crate::real_expression::fault(other),
            })
        };
        let mut image = convert(&self.lo, &self.hi)?;
        if self.lineage.is_some() && image.singleton().is_none() {
            for bits in [64, 128, 256, 512, 1024, 2048, 4096] {
                let previous = image;
                let (lo, hi) = self.refined(bits, w)?;
                image = convert(&lo, &hi)?;
                if image.singleton().is_some() {
                    break;
                }
                // Genuine source uncertainty may span multiple cells forever.
                // Keeping an unchanged complete image is sound; no midpoint
                // value or exact-value proof is manufactured from it.
                if !self.intrinsic_point
                    && image.lo.to_bits() == previous.lo.to_bits()
                    && image.hi.to_bits() == previous.hi.to_bits()
                {
                    break;
                }
            }
        }
        if self.intrinsic_point && image.singleton().is_none() {
            return Err(Error::new(
                "event_accuracy",
                "mathematical point does not yet certify one binary64 rounding cell",
            ));
        }
        Ok(Some(image))
    }
}

pub(crate) struct Sources {
    owner: Work,
    by_node: Vec<Option<Arc<Domain>>>,
}
impl Sources {
    /// The caller prepays the vector before constructing its entries.
    pub(crate) fn new(by_node: Vec<Option<Arc<Domain>>>, w: &Work) -> Result<Arc<Self>, Error> {
        w.debit(2, 96)?;
        Ok(Arc::new(Self {
            owner: w.clone(),
            by_node,
        }))
    }
    pub(crate) fn share_cost(&self) -> Result<(), Error> {
        self.owner.debit(2, 16)
    }
    pub(crate) fn affine(
        bands: Option<&Self>,
        constant: f64,
        terms: &[Term],
        exact: &[Option<R>],
        bounds: &[I],
        w: &Work,
    ) -> Result<Option<Arc<Domain>>, Error> {
        if bands.is_some_and(|b| !b.owner.same_owner(w)) {
            return Err(Error::new(
                "invalid_ir",
                "source bands belong to another request",
            ));
        }
        w.debit(2, (terms.len() * 2 + 16) as u64)?;
        let mut p = Paid::new(w);
        let c = p.binary(constant);
        let Some(c) = p.finish(c)? else {
            return Ok(None);
        };
        let Some(mut sum) = Domain::point(&c, w)? else {
            return Ok(None);
        };
        for t in terms {
            w.step()?;
            if t.node == 0 || t.coefficient == 0. {
                continue;
            }
            let value = if let Some(v) = bands
                .and_then(|b| b.by_node.get(t.node))
                .and_then(Option::as_ref)
            {
                v.share_cost(w)?;
                Some(v.clone())
            } else if let Some(Some(v)) = exact.get(t.node) {
                Domain::point(v, w)?
            } else if let Some(b) = bounds
                .get(t.node)
                .filter(|b| b.finite() && b.lo.to_bits() == b.hi.to_bits())
            {
                // A complete singleton bound is authoritative. The nominal
                // frame is deliberately not consulted, including for sources.
                let mut p = Paid::new(w);
                let value = p.binary(b.lo);
                let Some(value) = p.finish(value)? else {
                    return Ok(None);
                };
                Domain::point(&value, w)?
            } else {
                return Ok(None);
            };
            let Some(value) = value else {
                return Ok(None);
            };
            let Some(product) = value.scaled(t.coefficient, w)? else {
                return Ok(None);
            };
            let Some(next) = sum.add(&product, w)? else {
                return Ok(None);
            };
            sum = next;
        }
        Ok(Some(sum))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn binary(v: f64, w: &Work) -> R {
        let mut p = Paid::new(w);
        let v = p.binary(v);
        p.finish(v).unwrap().unwrap()
    }
    #[test]
    fn full_band_rounding_does_not_select_the_centre() {
        let w = Work::default();
        let one = binary(1., &w);
        let d = Domain::band(&one, 2f64.powi(-55), &w).unwrap().unwrap();
        assert_eq!(
            d.rounded(None, None, &w)
                .unwrap()
                .unwrap()
                .singleton()
                .unwrap()
                .to_bits(),
            1f64.to_bits()
        );
        let broad = Domain::band(&one, 0.25, &w).unwrap().unwrap();
        assert!(broad
            .rounded(None, Some(1.), &w)
            .unwrap()
            .unwrap()
            .singleton()
            .is_none());
        let overflow = Domain::band(&binary(f64::MAX, &w), f64::MAX, &w)
            .unwrap()
            .unwrap();
        assert!(overflow.rounded(None, Some(f64::MAX), &w).is_err());
    }
    #[test]
    fn affine_uses_complete_singletons_and_preserves_unknowns() {
        let w = Work::default();
        let terms = [
            Term {
                node: 1,
                coefficient: 1.,
            },
            Term {
                node: 2,
                coefficient: -1.,
            },
        ];
        let bounds = [I::point(0.), I::point(2f64.powi(53)), I::point(-1.)];
        let d = Sources::affine(None, 0., &terms, &[], &bounds, &w)
            .unwrap()
            .unwrap();
        assert_eq!(
            d.rounded(None, None, &w)
                .unwrap()
                .unwrap()
                .singleton()
                .unwrap(),
            2f64.powi(53)
        );
        let mut unknown = bounds;
        unknown[2] = I { lo: -2., hi: -1. };
        assert!(Sources::affine(None, 0., &terms, &[], &unknown, &w)
            .unwrap()
            .is_none());
        unknown[2] = I { lo: -0., hi: 0. };
        assert!(Sources::affine(None, 0., &terms, &[], &unknown, &w)
            .unwrap()
            .is_none());
        // An exact centre or singleton machine box cannot override a real band.
        let one = binary(1., &w);
        let band = Domain::band(&one, 0.25, &w).unwrap().unwrap();
        w.debit(2, 64).unwrap();
        let sources = Sources::new(vec![None, Some(band)], &w).unwrap();
        let terms = [Term {
            node: 1,
            coefficient: 1.,
        }];
        let exact = [None, Some(one)];
        let d = Sources::affine(
            Some(&sources),
            0.,
            &terms,
            &exact,
            &[I::point(0.), I::point(1.)],
            &w,
        )
        .unwrap()
        .unwrap();
        assert!(d
            .rounded(None, Some(1.), &w)
            .unwrap()
            .unwrap()
            .singleton()
            .is_none());
    }
    #[test]
    fn signed_underflow_keeps_both_zeros() {
        let w = Work::default();
        let zero = binary(0., &w);
        let d = Domain::band(&zero, f64::from_bits(1), &w)
            .unwrap()
            .unwrap()
            .scaled(0.5, &w)
            .unwrap()
            .unwrap();
        let image = d.rounded(None, None, &w).unwrap().unwrap();
        assert_eq!(
            (image.lo.to_bits(), image.hi.to_bits()),
            ((-0f64).to_bits(), 0f64.to_bits())
        );
        assert!(image.singleton().is_none());
        let point = Domain::point(&zero, &w).unwrap().unwrap();
        assert_eq!(
            point
                .rounded(Some(I::point(-0.)), Some(-0.), &w)
                .unwrap()
                .unwrap()
                .singleton()
                .unwrap()
                .to_bits(),
            (-0f64).to_bits()
        );
    }
    #[test]
    fn mathematical_lineage_rounds_once_and_keeps_real_source_uncertainty() {
        use crate::math_refinement::Function;
        let w = Work::default();
        let base = Domain::point(&binary(f64::from_bits(0x3ff0000000000001), &w), &w)
            .unwrap()
            .unwrap();
        let exponent = Domain::point(&binary(f64::from_bits(0x3fe0000000000001), &w), &w)
            .unwrap()
            .unwrap();
        let logarithm = Domain::elementary(Function::Ln, &base, &w)
            .unwrap()
            .unwrap();
        let product = Domain::binary(&logarithm, &exponent, '*', &w)
            .unwrap()
            .unwrap();
        let exponential = Domain::elementary(Function::Exp, &product, &w)
            .unwrap()
            .unwrap();
        let image = exponential.rounded(None, Some(1.), &w).unwrap().unwrap();
        assert_eq!(image.singleton().unwrap().to_bits(), 0x3ff0000000000001);
        let uncertain = Domain::band(&binary(1., &w), 0.125, &w).unwrap().unwrap();
        let logarithm = Domain::elementary(Function::Ln, &uncertain, &w)
            .unwrap()
            .unwrap();
        let exponential = Domain::elementary(Function::Exp, &logarithm, &w)
            .unwrap()
            .unwrap();
        assert!(exponential
            .rounded(None, Some(1.), &w)
            .unwrap()
            .unwrap()
            .singleton()
            .is_none());
    }
    #[test]
    fn domain_handles_keep_owner_and_sticky_budget() {
        let rich = Work::default();
        let value = binary(1., &rich);
        let d = Domain::band(&value, 0.125, &rich).unwrap().unwrap();
        assert!(d.share_cost(&Work::default()).is_err());
        let w = Work::limited([128, 8192, 400]);
        let clone = w.clone();
        assert!(Domain::band(&value, 0.125, &w).is_err());
        let first = w.spent();
        assert!(Domain::band(&value, 0.125, &clone).is_err());
        assert_eq!(clone.spent(), first);
        assert!(clone.step().is_err());
        assert_eq!(w.spent(), first + 1);
        println!(
            "same-owner budget: failed={first}, retry={}, explicit_step={}",
            first,
            w.spent()
        );
    }
}
