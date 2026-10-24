//! Complete rational sine-source images at an immutable rational clock root.
//! Qualification/binding stays with AnalyticRequest; no point-value proof is
//! asserted here. The normal RN consumer decides whether the full image fits.
use super::scope;
use crate::{
    exact_source::{history_paid::Paid, RootTime},
    ir::{AnalyticSource, Error, Expression as E, Program, Statement},
    source_domain::Domain,
    transition_source_plan::Work,
};
use num_rational::BigRational as R;
use std::{cell::RefCell, sync::Arc};

const BITS: u32 = 128;
struct Pair {
    lo: R,
    hi: R,
}
struct Entry {
    index: usize,
    parameters: [u64; 6],
    root: R,
    domain: Arc<Domain>,
}
#[derive(Default)]
struct State {
    owner: Option<Work>,
    pi: Option<Pair>,
    entries: Vec<Entry>,
}
#[derive(Default)]
pub(super) struct Cache(RefCell<State>);

fn q(p: &mut Paid<'_>, v: &R, up: bool) -> Option<R> {
    // Exact power of two. No transcendental f64 approximation enters the proof.
    let scale = p.binary(f64::from_bits((u64::from(BITS) + 1023) << 52))?;
    let scaled = p.op(v, &scale, '*')?;
    let mut cut = p.floor(&scaled)?;
    if up && !p.cmp(&cut, &scaled)?.is_eq() {
        let one = p.binary(1.)?;
        cut = p.op(&cut, &one, '+')?;
    }
    p.op(&cut, &scale, '/')
}
fn pair(p: &mut Paid<'_>, lo: R, hi: R) -> Option<Pair> {
    Some(Pair {
        lo: q(p, &lo, false)?,
        hi: q(p, &hi, true)?,
    })
}
fn copy(p: &mut Paid<'_>, v: &Pair) -> Option<Pair> {
    Some(Pair {
        lo: p.copy(&v.lo)?,
        hi: p.copy(&v.hi)?,
    })
}
fn add(p: &mut Paid<'_>, a: &Pair, b: &Pair) -> Option<Pair> {
    let lo = p.op(&a.lo, &b.lo, '+')?;
    let hi = p.op(&a.hi, &b.hi, '+')?;
    pair(p, lo, hi)
}
fn sub(p: &mut Paid<'_>, a: &Pair, b: &Pair) -> Option<Pair> {
    let lo = p.op(&a.lo, &b.hi, '-')?;
    let hi = p.op(&a.hi, &b.lo, '-')?;
    pair(p, lo, hi)
}
fn positive_mul(p: &mut Paid<'_>, a: &Pair, b: &Pair) -> Option<Pair> {
    let lo = p.op(&a.lo, &b.lo, '*')?;
    let hi = p.op(&a.hi, &b.hi, '*')?;
    pair(p, lo, hi)
}
fn scale(p: &mut Paid<'_>, a: &Pair, c: &R) -> Option<Pair> {
    let zero = p.binary(0.)?;
    let lo = p.op(&a.lo, c, '*')?;
    let hi = p.op(&a.hi, c, '*')?;
    if p.cmp(c, &zero)?.is_lt() {
        pair(p, hi, lo)
    } else {
        pair(p, lo, hi)
    }
}
fn inverse_atan(p: &mut Paid<'_>, n: f64, terms: u32) -> Option<Pair> {
    let one = p.binary(1.)?;
    let divisor = p.binary(n)?;
    let square = p.op(&divisor, &divisor, '*')?;
    let mut term = p.op(&one, &divisor, '/')?;
    let mut sum = Pair {
        lo: p.copy(&term)?,
        hi: p.copy(&term)?,
    };
    for k in 1..=terms {
        let a = p.binary(f64::from(2 * k - 1))?;
        let b = p.binary(f64::from(2 * k + 1))?;
        let t = p.op(&term, &a, '*')?;
        let t = p.op(&t, &b, '/')?;
        term = p.op(&t, &square, '/')?;
        let next = Pair {
            lo: p.copy(&term)?,
            hi: p.copy(&term)?,
        };
        sum = if k % 2 == 0 {
            add(p, &sum, &next)?
        } else {
            sub(p, &sum, &next)?
        };
    }
    // Alternating series remainder is bounded by the next omitted term.
    let a = p.binary(f64::from(2 * terms + 1))?;
    let b = p.binary(f64::from(2 * terms + 3))?;
    let t = p.op(&term, &a, '*')?;
    let t = p.op(&t, &b, '/')?;
    let tail = p.op(&t, &square, '/')?;
    let lo = p.op(&sum.lo, &tail, '-')?;
    let hi = p.op(&sum.hi, &tail, '+')?;
    pair(p, lo, hi)
}
fn pi(p: &mut Paid<'_>) -> Option<Pair> {
    // Machin identity pi=16 atan(1/5)-4 atan(1/239). Both atan series
    // are decreasing alternating series with the explicit omitted-term bound.
    let a = inverse_atan(p, 5., 40)?;
    let b = inverse_atan(p, 239., 12)?;
    let sixteen = p.binary(16.)?;
    let four = p.binary(4.)?;
    let a = scale(p, &a, &sixteen)?;
    let b = scale(p, &b, &four)?;
    sub(p, &a, &b)
}
fn sin_pi(p: &mut Paid<'_>, c: &R, pi: &Pair) -> Option<Pair> {
    let zero = p.binary(0.)?;
    let one = p.binary(1.)?;
    let two = p.binary(2.)?;
    let half = p.binary(0.5)?;
    // Reduce the exact rational multiple of pi before approximating pi.
    let shifted = p.op(c, &one, '+')?;
    let turns = p.op(&shifted, &two, '/')?;
    let turns = p.floor(&turns)?;
    let offset = p.op(&turns, &two, '*')?;
    let mut r = p.op(c, &offset, '-')?;
    let negative = p.cmp(&r, &zero)?.is_lt();
    if negative {
        r = p.op(&zero, &r, '-')?;
    }
    if p.cmp(&r, &half)?.is_gt() {
        r = p.op(&one, &r, '-')?;
    }
    let mut result = if p.cmp(&r, &zero)?.is_eq() {
        Pair {
            lo: p.copy(&zero)?,
            hi: p.copy(&zero)?,
        }
    } else if p.cmp(&r, &half)?.is_eq() {
        Pair {
            lo: p.copy(&one)?,
            hi: p.copy(&one)?,
        }
    } else {
        let x = scale(p, pi, &r)?;
        let square = positive_mul(p, &x, &x)?;
        let mut term = copy(p, &x)?;
        let mut sum = copy(p, &term)?;
        for k in 1..=28u32 {
            let a = p.binary(f64::from((2 * k) * (2 * k + 1)))?;
            let reciprocal = p.op(&one, &a, '/')?;
            let product = positive_mul(p, &term, &square)?;
            term = scale(p, &product, &reciprocal)?;
            sum = if k % 2 == 0 {
                add(p, &sum, &term)?
            } else {
                sub(p, &sum, &term)?
            };
        }
        // |x| <= pi/2 <2, hence every following term decreases. The true
        // sine remainder is bounded by the next omitted term for every x
        // in the complete rational argument interval (no monotonicity shortcut).
        let a = p.binary(58. * 59.)?;
        let reciprocal = p.op(&one, &a, '/')?;
        let product = positive_mul(p, &term, &square)?;
        let tail = scale(p, &product, &reciprocal)?;
        let lo = p.op(&sum.lo, &tail.hi, '-')?;
        let hi = p.op(&sum.hi, &tail.hi, '+')?;
        pair(p, lo, hi)?
    };
    if negative {
        result = Pair {
            lo: p.op(&zero, &result.hi, '-')?,
            hi: p.op(&zero, &result.lo, '-')?,
        };
    }
    Some(result)
}
impl Cache {
    pub(super) fn at_root(
        &self,
        index: usize,
        source: &AnalyticSource,
        error: f64,
        root: &RootTime,
        w: &Work,
    ) -> Result<Option<Arc<Domain>>, Error> {
        w.step()?;
        if !error.is_finite() || error < 0. {
            return Err(scope("invalid analytic source error domain"));
        }
        let AnalyticSource::Sine {
            sinedc,
            ampl,
            freq,
            sinephase,
            polarity,
            ..
        } = source;
        let parameters = [
            sinedc.to_bits(),
            ampl.to_bits(),
            freq.to_bits(),
            sinephase.to_bits(),
            f64::from(*polarity).to_bits(),
            error.to_bits(),
        ];
        let mut state = self.0.borrow_mut();
        if let Some(owner) = &state.owner {
            if !owner.same_owner(w) {
                return Err(scope("analytic source cache belongs to another request"));
            }
        } else {
            w.debit(2, 16)?;
            state.owner = Some(w.clone());
        }
        let mut paid = Paid::new(w);
        for entry in &state.entries {
            w.debit(2, 7)?;
            if entry.index == index && entry.parameters == parameters {
                let equal = paid.cmp(&entry.root, root.rational());
                if paid.finish(equal)?.is_some_and(|o| o.is_eq()) {
                    entry.domain.share_cost(w)?;
                    return Ok(Some(entry.domain.clone()));
                }
                paid = Paid::new(w);
            }
        }
        paid.finish(Some(()))?;
        if state.pi.is_none() {
            let mut p = Paid::new(w);
            let value = pi(&mut p);
            let value = p.finish(value)?;
            let Some(value) = value else {
                return Err(scope(
                    "analytic pi refinement exceeds exact arithmetic scope",
                ));
            };
            w.debit(2, 64)?;
            state.pi = Some(value);
        }
        let mut p = Paid::new(w);
        let pi = state.pi.as_ref().unwrap();
        let result = (|| {
            let AnalyticSource::Sine {
                sinedc,
                ampl,
                freq,
                sinephase,
                polarity,
                ..
            } = source;
            let freq = p.binary(*freq)?;
            let two = p.binary(2.)?;
            let phase = p.binary(*sinephase)?;
            let degrees = p.binary(180.)?;
            let t = p.copy(root.rational())?;
            let cycles = p.op(&freq, &t, '*')?;
            let cycles = p.op(&cycles, &two, '*')?;
            let degrees = p.op(&phase, &degrees, '/')?;
            let cycles = p.op(&cycles, &degrees, '+')?;
            let value = sin_pi(&mut p, &cycles, pi)?;
            let ampl = p.binary(*ampl)?;
            let value = scale(&mut p, &value, &ampl)?;
            let dc = p.binary(*sinedc)?;
            let lo = p.op(&value.lo, &dc, '+')?;
            let hi = p.op(&value.hi, &dc, '+')?;
            let value = Pair { lo, hi };
            let polarity = p.binary(f64::from(*polarity))?;
            let value = scale(&mut p, &value, &polarity)?;
            // The declared error is a genuine full source domain, not
            // uncertainty of the transcendental computation. Never shrink it.
            let error = p.binary(error)?;
            let lo = p.op(&value.lo, &error, '-')?;
            let hi = p.op(&value.hi, &error, '+')?;
            Some((Pair { lo, hi }, p.copy(root.rational())?))
        })();
        let Some((value, key)) = p.finish(result)? else {
            return Err(scope(
                "analytic sample refinement exceeds exact arithmetic scope",
            ));
        };
        let domain = if error == 0. {
            Domain::rational_point_bounds(value.lo, value.hi, w)?
        } else {
            Domain::rational_bounds(value.lo, value.hi, w)?
        };
        let Some(domain) = domain else {
            return Err(scope("invalid analytic source rational image"));
        };
        if state.entries.len() < 512 {
            if state.entries.len() == state.entries.capacity() {
                let next = state.entries.capacity().max(1) * 2;
                w.debit(
                    2,
                    ((next + state.entries.len()) * std::mem::size_of::<Entry>()) as u64,
                )?;
                let len = state.entries.len();
                state.entries.reserve_exact(next - len);
            }
            w.debit(2, std::mem::size_of::<Entry>() as u64)?;
            domain.share_cost(w)?;
            state.entries.push(Entry {
                index,
                parameters,
                root: key,
                domain: domain.clone(),
            });
        }
        Ok(Some(domain))
    }
}
fn expression(e: &E, node: usize, w: &Work) -> Result<bool, Error> {
    w.step()?;
    Ok(match e {
        E::Affine { terms, .. } => {
            let mut yes = false;
            for t in terms {
                w.step()?;
                yes |= t.node == node;
            }
            yes
        }
        E::Add { left, right }
        | E::Multiply { left, right }
        | E::Divide { left, right }
        | E::RealBinary { left, right, .. } => {
            let a = expression(left, node, w)?;
            let b = expression(right, node, w)?;
            a || b
        }
        E::RealBoundary { value, .. } | E::Power { base: value, .. } => expression(value, node, w)?,
        E::State { .. } => false,
        _ => {
            return Err(scope(
                "analytic source input scan found an unsupported original role",
            ))
        }
    })
}
fn statements(items: &[Statement], node: usize, w: &Work) -> Result<bool, Error> {
    let mut yes = false;
    for item in items {
        w.step()?;
        match item {
            Statement::Assign(a) => yes |= expression(&a.rhs, node, w)?,
            Statement::If {
                left,
                right,
                then_body,
                else_body,
                ..
            } => {
                yes |= expression(left, node, w)?;
                yes |= expression(right, node, w)?;
                yes |= statements(then_body, node, w)?;
                yes |= statements(else_body, node, w)?;
            }
            _ => {
                return Err(scope(
                    "analytic source input scan found an unsupported statement",
                ))
            }
        }
    }
    Ok(yes)
}
pub(super) fn read_node(p: &Program, node: usize, w: &Work) -> Result<bool, Error> {
    let mut yes = false;
    for event in &p.events {
        w.step()?;
        yes |= statements(&event.body, node, w)?;
    }
    Ok(yes)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn mathematical_point_enclosure_cannot_fall_back_to_a_nominal_at_boundary() {
        use crate::{
            interval::Interval as I,
            procedure_operations::{Cell, Domain as ExecutionDomain, Operation},
        };
        let source:AnalyticSource=serde_json::from_value(serde_json::json!({"kind":"sine","sinedc":f64::from_bits(1f64.to_bits()+1),"ampl":2f64.powi(-53),"freq":1.,"sinephase":0.,"source_name":"V","terminals":["x","0"],"polarity":1,"parameter_origin":"explicit-v1"})).unwrap();
        // Exact t differs from quarter, so sin(2*pi*t)<1. The mathematical
        // value is below the odd-dc/next-even midpoint, but its certified
        // 128-bit enclosure straddles that midpoint. Never choose nominal.
        let root = RootTime::raw("9007199254740993/36028797018963970".parse().unwrap());
        let work = Work::default();
        let cache = Cache::default();
        let point = cache
            .at_root(0, &source, 0., &root, &work)
            .unwrap()
            .unwrap();
        assert_eq!(
            point.rounded(None, Some(1.), &work).err().unwrap().kind,
            "event_accuracy"
        );
        work.debit(2, 128).unwrap();
        let sources = crate::source_domain::Sources::new(vec![None, Some(point)], &work).unwrap();
        let bound = I {
            lo: 1.,
            hi: f64::from_bits(1f64.to_bits() + 2),
        };
        let value = crate::source_domain::Sources::affine(
            Some(&sources),
            0.,
            &[crate::ir::Term {
                node: 1,
                coefficient: 1.,
            }],
            &[],
            &[I::point(0.), bound],
            &work,
        )
        .unwrap()
        .unwrap();
        assert_eq!(
            value
                .rounded(Some(bound), Some(1.), &work)
                .err()
                .unwrap()
                .kind,
            "event_accuracy"
        );
        let proofs = crate::event_value_proof::Proofs::new();
        let context =
            crate::event_value_proof::Context::candidate_frame(&proofs, 0, &[], &[], &work)
                .unwrap();
        let local =
            crate::event_value_proof::LocalState::try_with_context(&[], Some(&context)).unwrap();
        let domain = ExecutionDomain {
            nodes: &[],
            node_bounds: &[],
            states: &[],
            state_bounds: &[],
            operators: &[],
            operator_bounds: &[],
            local: &local,
        };
        let origin = Arc::new(crate::ir::Origin {
            source: "point-enclosure.va".into(),
            instance: "M".into(),
            line: 1,
            column: 1,
            expansion: vec![],
        });
        for kind in [
            crate::ir::RealBoundaryKind::Sample,
            crate::ir::RealBoundaryKind::Store,
        ] {
            let cell = Cell {
                source_domain: Some(value.clone()),
                nominal: Some(1.),
                image: Some(bound),
                mathematical: None,
                proof: None,
            };
            assert_eq!(
                Operation::Boundary(kind, origin.clone())
                    .evaluate(&[cell], &domain, &work)
                    .err()
                    .unwrap()
                    .kind,
                "event_accuracy"
            );
        }
        // Genuine uncertainty remains a full multi-cell image: it is not
        // reclassified as one mathematical value and cannot gain a proof.
        let band = cache
            .at_root(0, &source, 1e-6, &root, &work)
            .unwrap()
            .unwrap();
        assert!(band
            .rounded(Some(bound), Some(1.), &work)
            .unwrap()
            .unwrap()
            .singleton()
            .is_none());
    }
    #[test]
    fn rational_sine_images_and_pi_expose_complete_bounds_for_independent_oracle() {
        let work = Work::default();
        let mut paid = Paid::new(&work);
        let proof = pi(&mut paid);
        let proof = paid.finish(proof).unwrap().unwrap();
        println!("ANALYTIC_PI {} {}", proof.lo, proof.hi);
        let source:AnalyticSource=serde_json::from_value(serde_json::json!({"kind":"sine","sinedc":0.5,"ampl":0.25,"freq":1.,"sinephase":0.,"source_name":"V","terminals":["x","0"],"polarity":1,"parameter_origin":"explicit-v1"})).unwrap();
        let cache = Cache::default();
        for (index, root) in ["0", "1/6", "5/6", "1/8", "-1/8", "1/4", "3/4"]
            .iter()
            .enumerate()
        {
            let root = RootTime::raw(root.parse().unwrap());
            let before = work.spent();
            let domain = cache
                .at_root(index, &source, 0., &root, &work)
                .unwrap()
                .unwrap();
            assert!(work.spent() > before);
            println!(
                "ANALYTIC_SAMPLE {} {} {}",
                root.rational(),
                domain.lo,
                domain.hi
            );
            let image = domain.rounded(None, None, &work).unwrap().unwrap();
            assert!(image.singleton().is_some());
            let before = work.spent();
            let same = cache
                .at_root(index, &source, 0., &root, &work)
                .unwrap()
                .unwrap();
            assert!(Arc::ptr_eq(&same, &domain));
            assert!(work.spent() > before);
        }
        let root = RootTime::raw("1/6".parse().unwrap());
        let exact = cache
            .at_root(1, &source, 0., &root, &work)
            .unwrap()
            .unwrap();
        let noisy = cache
            .at_root(1, &source, 1e-6, &root, &work)
            .unwrap()
            .unwrap();
        assert!(!Arc::ptr_eq(&exact, &noisy));
        assert!(noisy
            .rounded(None, None, &work)
            .unwrap()
            .unwrap()
            .singleton()
            .is_none());
        let error = R::from_float(1e-6).unwrap();
        assert!(noisy.lo <= &exact.lo - &error && noisy.hi >= &exact.hi + &error);
        let foreign = Work::default();
        assert!(cache.at_root(99, &source, 0., &root, &foreign).is_err());
        // Exhaust exactly the already-used original allowance. New reads cannot
        // resurrect the cached numerical certificate under the same owner.
        work.debit(2, 1_000_000_001).unwrap_err();
        let root = RootTime::raw("1/6".parse().unwrap());
        for _ in 0..2 {
            assert_eq!(
                cache
                    .at_root(1, &source, 0., &root, &work)
                    .err()
                    .unwrap()
                    .kind,
                "step_budget"
            );
        }
        let fresh = Work::default();
        assert!(Cache::default()
            .at_root(0, &source, 0., &root, &fresh)
            .unwrap()
            .is_some());
    }
}
