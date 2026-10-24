//! Whole-segment affine proxies with a retained source-RN defect. The proxy
//! endpoints are never asserted to be samples of the actual RN waveform.
use super::*;

pub(crate) struct Prepared {
    pub points: Vec<(f64, f64)>,
    pub bounds: Vec<I>,
    pub exact_constant: Option<f64>,
}
/// Keep existing nonlinear/reset consumers on their owning path. This narrow
/// extra direct Idt case is just a sampled physical affine source.
pub(crate) fn direct_integral_candidate(e: &E, w: &Work) -> Result<bool, Error> {
    w.step()?;
    match e {
        E::RealBoundary { value, .. } => direct_integral_candidate(value, w),
        E::Affine { .. } => Ok(true),
        _ => Ok(false),
    }
}
struct Pair {
    a: R,
    b: R,
    error: f64,
}
impl Pair {
    fn at(&self, time: f64, w: &Work) -> Result<R, Error> {
        rational(w, |p| {
            let t = p.binary(time)?;
            let v = p.op(&self.b, &t, '*')?;
            p.op(&self.a, &v, '+')
        })
    }
    fn range(&self, segment: I, w: &Work) -> Result<I, Error> {
        let a = self.at(segment.lo, w)?;
        let b = self.at(segment.hi, w)?;
        rational(w, |p| Some(p.enclose(&a)?.hull(p.enclose(&b)?)))
    }
    fn actual(&self, segment: I, w: &Work) -> Result<I, Error> {
        let value = self.range(segment, w)?
            + I {
                lo: -self.error,
                hi: self.error,
            };
        if !value.finite() {
            return Err(unsupported());
        }
        Ok(value)
    }
    fn rounded(mut self, segment: I, w: &Work) -> Result<Self, Error> {
        let actual = self.actual(segment, w)?;
        // Use the original RN domain gate as well as the conservative full-ulp
        // defect. This retains overflow and finite-domain refusals.
        crate::real_expression::interval(actual, Some(w))?;
        let epsilon = (I::point(actual.magnitude()) * I::point(f64::EPSILON)
            + I::point(f64::from_bits(1)))
        .hi;
        self.error = (I::point(self.error) + I::point(epsilon)).hi;
        if !self.error.is_finite() {
            return Err(unsupported());
        }
        Ok(self)
    }
}
fn pair(e: &E, context: &ProofContext, states: &[I], segment: I) -> Result<Pair, Error> {
    let w = context.borrow_work();
    w.debit(2, 256)?;
    // This proves the actual original expression constant, including all RN
    // operations. A constant *proxy* alone never receives this certificate.
    if let Some(a) = constant(e, context, states, segment)? {
        return Ok(Pair {
            a,
            b: rational(w, |p| p.binary(0.))?,
            error: 0.,
        });
    }
    if let Some((a, b)) = line(e, context, segment)? {
        return Ok(Pair { a, b, error: 0. });
    }
    if let E::RealBoundary { value, .. } = e {
        return pair(value, context, states, segment)?.rounded(segment, w);
    }
    let (left, right, op, rn) = match e {
        E::Add { left, right } => (left, right, '+', false),
        E::Multiply { left, right } => (left, right, '*', false),
        E::Divide { left, right } => (left, right, '/', false),
        E::RealBinary {
            left,
            right,
            operation,
            ..
        } => {
            use crate::ir::RealOperation as O;
            (
                left,
                right,
                match operation {
                    O::Add => '+',
                    O::Subtract => '-',
                    O::Multiply => '*',
                    O::Divide => '/',
                },
                true,
            )
        }
        _ => return Err(unsupported()),
    };
    let mut a = pair(left, context, states, segment)?;
    let mut b = pair(right, context, states, segment)?;
    if rn {
        a = a.rounded(segment, w)?;
        b = b.rounded(segment, w)?;
    }
    let av = a.range(segment, w)?;
    let bv = b.range(segment, w)?;
    let ea = I::point(a.error);
    let eb = I::point(b.error);
    let error = match op {
        '+' | '-' => (ea + eb).hi,
        '*' => (I::point(av.magnitude()) * eb + I::point(bv.magnitude()) * ea + ea * eb).hi,
        '/' => {
            let actual = b.actual(segment, w)?;
            if actual.lo <= 0. && actual.hi >= 0. || bv.lo <= 0. && bv.hi >= 0. {
                return Err(unsupported());
            }
            let d = actual.lo.abs().min(actual.hi.abs());
            let d0 = bv.lo.abs().min(bv.hi.abs());
            (ea / I::point(d) + I::point(av.magnitude()) * eb / (I::point(d) * I::point(d0))).hi
        }
        _ => unreachable!(),
    };
    let (intercept, slope) = match op {
        '+' | '-' => rational(w, |p| Some((p.op(&a.a, &b.a, op)?, p.op(&a.b, &b.b, op)?)))?,
        '*' if a.b.is_zero() => rational(w, |p| {
            Some((p.op(&a.a, &b.a, '*')?, p.op(&a.a, &b.b, '*')?))
        })?,
        '*' if b.b.is_zero() => rational(w, |p| {
            Some((p.op(&a.a, &b.a, '*')?, p.op(&a.b, &b.a, '*')?))
        })?,
        '/' if b.b.is_zero() => rational(w, |p| {
            Some((p.op(&a.a, &b.a, '/')?, p.op(&a.b, &b.a, '/')?))
        })?,
        _ => return Err(unsupported()),
    };
    let result = Pair {
        a: intercept,
        b: slope,
        error,
    };
    result.actual(segment, w)?;
    if rn {
        result.rounded(segment, w)
    } else {
        Ok(result)
    }
}

pub(crate) fn prepare(
    operator: usize,
    context: &ProofContext,
    states: &[I],
) -> Result<Prepared, Error> {
    let (program, trajectory, _) = context.original_binding();
    let w = context.borrow_work();
    let spec = program.operators.get(operator).ok_or_else(unsupported)?;
    let input = match spec {
        crate::ir::OperatorSpec::IdtMod { input, .. }
        | crate::ir::OperatorSpec::Idt {
            input, reset: None, ..
        } => input,
        _ => return Err(unsupported()),
    };
    let sources = crate::procedure::dependency_sources(program, w)?;
    let deps = crate::procedure::source_dependencies(input, program, &sources, w)?;
    if !deps.state_dependencies.is_empty() || !deps.operator_dependencies.is_empty() {
        return Err(unsupported());
    }
    for node in deps.node_dependencies {
        w.step()?;
        if node != 0 && !context.event_input_nodes().contains(&node) {
            return Err(unsupported());
        }
    }
    let cuts = partition(context, states)?;
    w.debit(2, (cuts.len() * 64 + 128) as u64)?;
    let mut points: Vec<(f64, f64)> = Vec::with_capacity(cuts.len());
    let mut bounds: Vec<I> = Vec::with_capacity(cuts.len());
    let mut exact_constant = None;
    let mut all_constant = true;
    for cut in cuts.windows(2) {
        let lo = round(cut[0].rational(), w)?;
        let hi = round(cut[1].rational(), w)?;
        if !rational(w, |p| {
            let a = p.binary(lo)?;
            let b = p.binary(hi)?;
            Some(p.cmp(&a, cut[0].rational())?.is_eq() && p.cmp(&b, cut[1].rational())?.is_eq())
        })? || lo >= hi
        {
            return Err(unsupported());
        }
        let segment = I { lo, hi };
        let probe = between(&cut[0], &cut[1], w)?;
        let plan = activate(context, states, &probe)?;
        let expression = plan.input_expression(operator, w)?;
        let actual_constant = constant(&expression, context, states, segment)?;
        let value = pair(&expression, context, states, segment)?;
        match actual_constant {
            Some(v) => {
                let native = round(&v, w)?;
                let representable = rational(w, |p| {
                    let a = p.binary(native)?;
                    Some(p.cmp(&a, &v)?.is_eq())
                })?;
                if !representable
                    || exact_constant.is_some_and(|a: f64| a.to_bits() != native.to_bits())
                {
                    all_constant = false;
                }
                exact_constant = Some(native);
            }
            None => all_constant = false,
        }
        for (index, time) in [lo, hi].into_iter().enumerate() {
            let v = value.at(time, w)?;
            let nominal = round(&v, w)?;
            let band = rational(w, |p| p.enclose(&v))?
                + I {
                    lo: -value.error,
                    hi: value.error,
                };
            if !band.finite() {
                return Err(unsupported());
            }
            let band = band.hull(I::point(nominal));
            if index == 0 && !points.is_empty() {
                let last = bounds.last_mut().unwrap();
                *last = last.hull(band);
            } else {
                points.push((time, nominal));
                bounds.push(band);
            }
        }
    }
    if points.len() < 2 || points.last().unwrap().0 != trajectory.config.stop {
        return Err(unsupported());
    }
    Ok(Prepared {
        points,
        bounds,
        exact_constant: all_constant.then_some(exact_constant).flatten(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    fn context() -> Arc<ProofContext> {
        let r: crate::ir::Request =
            serde_json::from_str(include_str!("../tests/fixtures/ir33_phase_affine.json")).unwrap();
        let mut t = crate::pwl::Trajectory::new(r.transient.unwrap(), r.driven.len()).unwrap();
        let w = Work::default();
        t.bind_procedure_work(&w).unwrap();
        ProofContext::new(&r.program, &t, &r.driven, w).unwrap()
    }
    #[test]
    fn source_rn_staircase_area_keeps_full_defect_and_query_independence() {
        let c = context();
        let p = prepare(0, &c, &[]).unwrap();
        assert!(p.exact_constant.is_none());
        let h = crate::idt::Idt::enclosed(p.points, p.bounds, 0.).unwrap();
        for (time, exact) in [(1., 0.5), (0.25, 0.), (0.75, 0.25), (0.25, 0.)] {
            let b = h.value_bounds(time).unwrap();
            assert!(b.lo <= exact && b.hi >= exact, "{time}: {b:?}");
        }
        let accepted = h.value_bounds(0.75).unwrap();
        let candidate = h.clone();
        candidate.value(1.).unwrap();
        drop(candidate);
        assert_eq!(h.value_bounds(0.75).unwrap(), accepted);
    }
    #[test]
    fn proxy_constant_does_not_prove_the_original_rn_graph_constant() {
        let c = context();
        let node = c.event_input_nodes()[0];
        let base = || E::Affine {
            constant: 4503599627370496.,
            terms: vec![crate::ir::Term {
                node,
                coefficient: 1.,
            }],
        };
        let origin = c.original_binding().0.operators[0].origin().clone();
        let rounded = |value: E| E::RealBoundary {
            value: Box::new(value),
            kind: crate::ir::RealBoundaryKind::Sample,
            origin: origin.clone(),
        };
        let expr = E::Add {
            left: Box::new(rounded(base())),
            right: Box::new(E::Multiply {
                left: Box::new(crate::real_expression::literal(-1.)),
                right: Box::new(rounded(E::Add {
                    left: Box::new(base()),
                    right: Box::new(crate::real_expression::literal(0.25)),
                })),
            }),
        };
        let segment = I { lo: 0., hi: 1. };
        assert!(constant(&expr, &c, &[], segment).unwrap().is_none());
        let result = pair(&expr, &c, &[], segment).unwrap();
        assert!(result.b.is_zero());
        assert!(result.error > 0.);
    }
    #[test]
    fn source_history_rejects_zero_internal_dependencies_and_retains_exhaustion() {
        let c = context();
        let (program, t, driven) = c.original_binding();
        let w = c.borrow_work();
        let mut p = program.clone();
        let node = p.nodes.iter().position(|n| n == "y").unwrap();
        let crate::ir::OperatorSpec::IdtMod { input, .. } = &mut p.operators[0] else {
            unreachable!()
        };
        *input = E::Add {
            left: Box::new(input.clone()),
            right: Box::new(E::Affine {
                constant: 0.,
                terms: vec![crate::ir::Term {
                    node,
                    coefficient: 0.,
                }],
            }),
        };
        let altered = ProofContext::new(&p, t, driven, w.clone()).unwrap();
        assert_eq!(
            prepare(0, &altered, &[]).err().unwrap().kind,
            "unsupported_history_input"
        );
        prepare(0, &c, &[]).unwrap();
        w.debit(2, 1_000_000_000 - w.spent()).unwrap();
        for _ in 0..2 {
            assert_eq!(prepare(0, &c, &[]).err().unwrap().kind, "step_budget");
        }
        prepare(0, &context(), &[]).unwrap();
    }
}
