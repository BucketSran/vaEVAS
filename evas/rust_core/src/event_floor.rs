//! Certificate-driven original-source Floor, only for the new nonbinary route.
//! No accepted history, no source cache, and no fresh per-call quota.
use crate::exact_source::{binary, enclosure, Budget};
use crate::interval::Interval as I;
use crate::ir::{Error, EventMathFunction as F, Expression as E};
use crate::transition_source_plan::Work;
use num_rational::BigRational as R;
use num_traits::ToPrimitive;
use std::collections::BTreeSet;

pub(crate) fn charge(w: &Work, n: usize, category: &'static str) -> Result<(), Error> {
    if let Err(e) = w.debit(2, n as u64) {
        crate::diagnostics::counter("floor_source_work_exhausted", 1);
        return Err(e);
    }
    crate::diagnostics::counter(category, n);
    crate::diagnostics::counter("floor_source_work_debit", n);
    Ok(())
}
pub(crate) fn binary_scale(v: f64) -> bool {
    let b = v.abs().to_bits();
    let e = b >> 52;
    let f = b & ((1_u64 << 52) - 1);
    v == 0. || v.is_finite() && if e == 0 { f.count_ones() == 1 } else { f == 0 }
}
pub(crate) fn new_operand_charged(e: &E, w: &Work) -> Result<bool, Error> {
    charge(w, 1, "floor_source_operand_scan")?;
    Ok(match e {
        E::Divide { .. } => true,
        E::Affine { terms, .. } => {
            let mut found = false;
            for t in terms {
                charge(w, 1, "floor_source_operand_scan")?;
                if !binary_scale(t.coefficient) {
                    found = true;
                    break;
                }
            }
            found
        }
        E::Multiply { left, right } => {
            let mut constant = false;
            for child in [left.as_ref(), right.as_ref()] {
                charge(w, 1, "floor_source_operand_scan")?;
                if matches!(child,E::Affine{constant,terms} if terms.is_empty()&&!binary_scale(*constant))
                {
                    constant = true;
                    break;
                }
            }
            constant || new_operand_charged(left, w)? || new_operand_charged(right, w)?
        }
        E::Add { left, right } => new_operand_charged(left, w)? || new_operand_charged(right, w)?,
        _ => false,
    })
}
pub(crate) fn contains_charged(e: &E, w: &Work) -> Result<bool, Error> {
    charge(w, 1, "floor_source_dispatch_scan")?;
    Ok(match e {
        E::IntegerRound { .. } => true,
        E::EventMath {
            function: F::Floor,
            args,
            ..
        } => {
            if let Some(arg) = args.first() {
                new_operand_charged(arg, w)?
            } else {
                false
            }
        }
        E::EventMath { args, .. } => {
            let mut found = false;
            for arg in args {
                if contains_charged(arg, w)? {
                    found = true;
                    break;
                }
            }
            found
        }
        E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
            contains_charged(left, w)? || contains_charged(right, w)?
        }
        E::CheckedInteger { value, .. } => contains_charged(value, w)?,
        E::CheckedIndex { index, .. } | E::ArrayRead { index, .. } => contains_charged(index, w)?,
        E::Power { base, .. } => contains_charged(base, w)?,
        E::Select {
            left,
            right,
            then_value,
            else_value,
            ..
        } => {
            let mut found = false;
            for child in [left, right, then_value, else_value] {
                if contains_charged(child, w)? {
                    found = true;
                    break;
                }
            }
            found
        }
        _ => false,
    })
}
/// This exception requires the already admitted source owner. Legacy display
/// arithmetic retains its old observer gate without a new eligibility walk.
pub(crate) fn display_operand(e: &E, work: Option<&Work>) -> Result<bool, Error> {
    let Some(w) = work else { return Ok(false) };
    fn allowed(e: &E, w: &Work) -> Result<bool, Error> {
        charge(w, 1, "floor_source_display_scan")?;
        Ok(match e {
            E::EventMath {
                function: F::Floor,
                args,
                ..
            } => args.len() == 1 && new_operand_charged(&args[0], w)?,
            E::EventMath { .. }
            | E::IntegerPrimitive { .. }
            | E::ArrayRead { .. }
            | E::CheckedIndex { .. }
            | E::IntegerRound { .. }
            | E::CheckedInteger { .. } => false,
            E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
                allowed(left, w)? && allowed(right, w)?
            }
            E::Power { base, .. } => allowed(base, w)?,
            E::Select {
                left,
                right,
                then_value,
                else_value,
                ..
            } => {
                let mut yes = true;
                for child in [left, right, then_value, else_value] {
                    if !allowed(child, w)? {
                        yes = false;
                        break;
                    }
                }
                yes
            }
            _ => true,
        })
    }
    Ok(contains_charged(e, w)? && allowed(e, w)?)
}
fn invalid(s: &str) -> Error {
    Error::new("event_condition", s)
}
fn copy_r(v: &R, w: &Work) -> Result<R, Error> {
    let limbs = 1 + (v.numer().bits() + v.denom().bits()).div_ceil(64) as usize;
    charge(w, limbs, "floor_source_copy_limbs")?;
    Ok(v.clone())
}
struct Pair {
    point: f64,
    bounds: I,
    exact: Option<R>,
}
/// One original argument tree, one local exact Budget and the borrowed request Work.
pub(crate) fn decide(
    e: &E,
    nodes: &[I],
    local: &crate::event_value_proof::LocalState,
) -> Result<f64, Error> {
    let w = local
        .floor_work()
        .ok_or_else(|| invalid("source floor lacks request proof owner"))?;
    #[allow(clippy::too_many_arguments)]
    fn visit(
        e: &E,
        nodes: &[I],
        local: &crate::event_value_proof::LocalState,
        w: &Work,
        budget: &mut Budget,
        depth: usize,
        count: &mut usize,
        exact: bool,
    ) -> Result<Pair, Error> {
        charge(w, 1, "floor_source_ast")?;
        *count += 1;
        if depth > 64 || *count > 512 {
            return Err(invalid("source floor expression limit"));
        }
        let result = match e {
            E::Affine { constant, terms } => {
                let mut p = *constant;
                let mut b = I::point(*constant);
                let mut r = exact.then(|| binary(*constant)).flatten();
                for t in terms {
                    charge(w, 1, "floor_source_terms")?;
                    let v = local
                        .floor_bound(t.node)
                        .or_else(|| nodes.get(t.node).copied())
                        .ok_or_else(|| invalid("floor input missing"))?;
                    let nominal = v.lo + (v.hi - v.lo) * 0.5;
                    charge(w, 4, "floor_source_interval")?;
                    p += t.coefficient * nominal;
                    b = b + I::point(t.coefficient) * v;
                    if exact {
                        let value = local
                            .floor_node(t.node)
                            .map(|r| copy_r(r, w))
                            .transpose()?
                            .or_else(|| (v.lo == v.hi).then(|| binary(v.lo)).flatten());
                        charge(w, 2, "floor_source_exact_ops")?;
                        r = match (r, value, binary(t.coefficient)) {
                            (Some(a), Some(v), Some(k)) => Some(
                                budget
                                    .check(k * v)
                                    .and_then(|product| budget.check(a + product))
                                    .ok_or_else(|| {
                                        invalid("source floor exact expression resource cap")
                                    })?,
                            ),
                            _ => None,
                        };
                    }
                }
                Pair {
                    point: p,
                    bounds: b,
                    exact: r,
                }
            }
            E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
                let a = visit(left, nodes, local, w, budget, depth + 1, count, exact)?;
                let b = visit(right, nodes, local, w, budget, depth + 1, count, exact)?;
                if matches!(e, E::Divide { .. }) && (b.bounds.lo <= 0. && b.bounds.hi >= 0.) {
                    return Err(Error::new(
                        "event_domain",
                        "source floor denominator enclosure contains zero",
                    ));
                }
                charge(w, 2, "floor_source_interval")?;
                let (point, bounds) = match e {
                    E::Add { .. } => (a.point + b.point, a.bounds + b.bounds),
                    E::Multiply { .. } => (a.point * b.point, a.bounds * b.bounds),
                    _ => (a.point / b.point, a.bounds / b.bounds),
                };
                if exact {
                    charge(w, 1, "floor_source_exact_ops")?;
                }
                let exact = match (a.exact, b.exact) {
                    (Some(a), Some(b)) => Some(
                        budget
                            .check(match e {
                                E::Add { .. } => a + b,
                                E::Multiply { .. } => a * b,
                                _ => a / b,
                            })
                            .ok_or_else(|| invalid("source floor exact expression resource cap"))?,
                    ),
                    _ => None,
                };
                Pair {
                    point,
                    bounds,
                    exact,
                }
            }
            _ => return Err(invalid("unsupported source floor original operand")),
        };
        if !result.point.is_finite()
            || !result.bounds.finite()
            || result.point < result.bounds.lo
            || result.point > result.bounds.hi
        {
            return Err(Error::new(
                "nonfinite_arithmetic",
                "invalid original source floor child",
            ));
        }
        if result.exact.is_some() {
            charge(w, 1024, "floor_source_exact_enclosure")?;
        }
        if result.exact.as_ref().is_some_and(|r| {
            enclosure(r).is_none_or(|v| v.lo < result.bounds.lo || v.hi > result.bounds.hi)
        }) {
            return Err(invalid(
                "source floor child exact value escapes original bound",
            ));
        }
        Ok(result)
    }
    let a = visit(e, nodes, local, w, &mut Budget(0), 0, &mut 0, false)?;
    let lo = a.bounds.lo.floor();
    let hi = a.bounds.hi.floor();
    let k = if lo == hi {
        crate::diagnostics::counter("floor_source_interval_decisions", 1);
        lo
    } else {
        crate::diagnostics::counter("floor_source_exact_decisions", 1);
        charge(w, 1, "floor_source_exact_ops")?;
        let a = visit(e, nodes, local, w, &mut Budget(0), 0, &mut 0, true)?;
        let r = a
            .exact
            .ok_or_else(|| invalid("source uncertainty spans multiple floor bins"))?;
        let k = r.floor();
        // The exact integer is the half-open bin; nearest float is never a cut.
        let f = k
            .to_f64()
            .ok_or_else(|| invalid("source floor bin not representable"))?;
        if binary(f).as_ref() != Some(&k) {
            return Err(invalid("source floor bin not exact binary64"));
        }
        f
    };
    if !k.is_finite() {
        return Err(invalid("nonfinite source floor bin"));
    }
    Ok(k)
}

/// Request binding, never candidate history. Serialization is streamed through
/// the debit sink; no uncharged whole-tree JSON Value/Vec is manufactured.
pub(crate) struct Request {
    pub(crate) source: std::sync::Arc<crate::transition_source_plan::ProofContext>,
    work: Work,
    identity: Vec<u8>,
    program_items: usize,
}
struct Sink<'a> {
    work: &'a Work,
    data: Vec<u8>,
    failed: bool,
}
impl std::io::Write for Sink<'_> {
    fn write(&mut self, bytes: &[u8]) -> std::io::Result<usize> {
        if charge(self.work, bytes.len() + 1, "floor_source_binding_scan").is_err() {
            self.failed = true;
            return Err(std::io::Error::other("source floor work exhausted"));
        }
        charge(self.work, bytes.len(), "floor_source_copy")
            .map_err(|_| std::io::Error::other("source floor copy exhausted"))?;
        if self.data.len().saturating_add(bytes.len()) > self.data.capacity() {
            charge(self.work, self.data.len(), "floor_source_copy")
                .map_err(|_| std::io::Error::other("source floor growth copy exhausted"))?;
        }
        self.data.extend_from_slice(bytes);
        Ok(bytes.len())
    }
    fn flush(&mut self) -> std::io::Result<()> {
        Ok(())
    }
}
fn encoded<T: serde::Serialize>(v: &T, w: &Work) -> Result<Vec<u8>, Error> {
    let mut sink = Sink {
        work: w,
        data: Vec::new(),
        failed: false,
    };
    serde_json::to_writer(&mut sink, v)
        .map_err(|_| Error::new("step_budget", "source floor binding work exhausted"))?;
    Ok(sink.data)
}
pub(crate) fn check_provided_binding(
    source: &crate::transition_source_plan::ProofContext,
    program: &crate::ir::Program,
    trajectory: &crate::pwl::Trajectory,
    driven: &[String],
) -> Result<(), Error> {
    let work = source.borrow_work();
    charge(work, 0, "floor_source_identity_scan")?;
    let (original, physical, names) = source.original_binding();
    let expected = encoded(&(original, &physical.config, names), work)?;
    let actual = encoded(&(program, &trajectory.config, driven), work)?;
    charge(
        work,
        expected.len().saturating_add(actual.len()),
        "floor_source_identity_debit",
    )?;
    if expected != actual {
        return Err(Error::new(
            "invalid_ir",
            "provided event source owner has a different original binding",
        ));
    }
    Ok(())
}
impl Drop for Request {
    fn drop(&mut self) {
        crate::diagnostics::counter("floor_source_work_end", self.work.spent() as usize);
    }
}
impl Request {
    pub(crate) fn new(
        admission: &crate::event_control::Admission<'_>,
        t: &crate::pwl::Trajectory,
        driven: &[String],
        provided: Option<std::sync::Arc<crate::transition_source_plan::ProofContext>>,
    ) -> Result<Option<std::sync::Arc<Self>>, Error> {
        if let Some(source) = &provided {
            charge(source.borrow_work(), 0, "floor_source_admission_walk")?;
        }
        if !admission.source_floor() {
            return Ok(None);
        }
        let p = admission.program();
        let work = provided
            .as_ref()
            .map_or_else(|| Work::for_trajectory(t), |s| s.borrow_work().clone());
        crate::diagnostics::counter("floor_source_work_begin", work.spent() as usize);
        let program_bytes = encoded(p, &work)?;
        let size = program_bytes.len();
        let identity = encoded(&t.config, &work)?;
        let names = encoded(&driven, &work)?.len();
        charge(
            &work,
            8_usize.saturating_mul(size + identity.len() + names),
            "floor_source_copy",
        )?;
        t.charge_source_copy_named(
            &work,
            [
                "floor_source_ast",
                "floor_source_copy",
                "floor_source_work_debit",
            ],
        )?;
        let source = if let Some(source) = provided {
            let (original, trajectory, names) = source.original_binding();
            charge(
                &work,
                names.len().saturating_mul(2),
                "floor_source_identity_scan",
            )?;
            charge(
                &work,
                program_bytes.len() * 2
                    + identity.len() * 2
                    + names
                        .iter()
                        .map(String::len)
                        .sum::<usize>()
                        .saturating_mul(2),
                "floor_source_identity_debit",
            )?;
            if encoded(original, &work)? != program_bytes
                || encoded(&trajectory.config, &work)? != identity
                || names != driven
            {
                return Err(invalid(
                    "provided source owner has a different original binding",
                ));
            }
            source
        } else {
            crate::diagnostics::counter("floor_source_owner_created", 1);
            crate::transition_source_plan::ProofContext::event_request_with_work(
                p,
                t,
                driven,
                size,
                work.clone(),
            )?
        };
        crate::diagnostics::counter("floor_source_factory_calls", 1);
        Ok(Some(std::sync::Arc::new(Self {
            source,
            work,
            identity,
            program_items: size,
        })))
    }
    pub(crate) fn work(&self) -> &Work {
        &self.work
    }
    fn bootstrap_reservation(&self, e: &E, owner: &str) -> Result<(), Error> {
        charge(&self.work, 0, "floor_source_bootstrap_reservation")?;
        let n = encoded(e, &self.work)?.len().saturating_add(1);
        let (_, _, driven) = self.source.original_binding();
        // Serialized storage bounds every AST node, term, origin byte and
        // program coordinate. Per node, dense vectors and set unions use at
        // most linear program storage; ordered sets use at most n comparisons
        // per key. Each driven-name lookup may scan all program-name bytes.
        // Sixty-four logical reads/writes/headers per such pair cover these
        // helper operations without relying on allocator or tree constants.
        let amount = n
            .saturating_mul(
                n.saturating_add(self.program_items)
                    .saturating_add(owner.len())
                    .saturating_add(1),
            )
            .saturating_mul(driven.len().saturating_add(1))
            .saturating_mul(64);
        charge(&self.work, amount, "floor_source_bootstrap_reservation")
    }
    pub(crate) fn bootstrap_numeric(&self, e: &E, owner: &str) -> Result<(), Error> {
        self.bootstrap_reservation(e, owner)?;
        crate::diagnostics::counter("floor_source_bootstrap_numeric_calls", 1);
        let (program, _, _) = self.source.original_binding();
        crate::event_numeric::validate(e, program, owner)
    }
    pub(crate) fn input_nodes(&self) -> Result<&[usize], Error> {
        let indices = self.source.event_input_nodes();
        charge(
            &self.work,
            indices.len().saturating_mul(8).saturating_add(2),
            "floor_source_input_map",
        )?;
        crate::diagnostics::counter("floor_source_input_map_calls", 1);
        Ok(indices)
    }
    pub(crate) fn bootstrap_dependencies(
        &self,
        e: &E,
        owner: &str,
    ) -> Result<(BTreeSet<usize>, bool), Error> {
        self.bootstrap_reservation(e, owner)?;
        crate::diagnostics::counter("floor_source_bootstrap_dependency_calls", 1);
        let (program, _, driven) = self.source.original_binding();
        let (nodes, states, operators) =
            crate::continuous::integral_dependency_edges(e, program, owner)?;
        let driven: std::collections::BTreeSet<_> = driven
            .iter()
            .filter_map(|name| program.nodes.iter().position(|node| node == name))
            .collect();
        let allowed =
            operators.is_empty() && nodes.iter().all(|node| *node == 0 || driven.contains(node));
        Ok((states, allowed))
    }
    pub(crate) fn check_source(&self, t: &crate::pwl::Trajectory) -> Result<(), Error> {
        charge(&self.work, 0, "floor_source_identity_scan")?;
        let candidate = encoded(&t.config, &self.work)?;
        charge(
            &self.work,
            candidate.len() + self.identity.len(),
            "floor_source_identity_debit",
        )?;
        if candidate != self.identity {
            return Err(invalid(
                "source floor context belongs to a different source request",
            ));
        }
        Ok(())
    }
}

/// Replace only eligible Floor calls on the executed expression path. The
/// caller retains original typed assignment and voltage/domain acceptance.
pub(crate) fn resolve(
    e: &E,
    nodes: &[I],
    local: &crate::event_value_proof::LocalState,
) -> Result<E, Error> {
    let w = local
        .floor_work()
        .ok_or_else(|| invalid("source floor replay lacks request owner"))?;
    let bytes = encoded(e, w)?.len();
    charge(w, bytes.saturating_mul(8), "floor_source_copy")?;
    fn walk(
        e: &E,
        nodes: &[I],
        local: &crate::event_value_proof::LocalState,
        w: &Work,
    ) -> Result<E, Error> {
        charge(w, 1, "floor_source_ast")?;
        Ok(match e {
            E::IntegerRound { value, origin } => {
                charge(w, 1, "integer_round_source_visit")?;
                let E::Affine { constant, terms } = value.as_ref() else {
                    return Err(invalid("integer conversion requires direct input"));
                };
                let mut bound = I::point(*constant);
                for term in terms {
                    charge(w, 4, "integer_round_source_interval")?;
                    let input = local
                        .floor_bound(term.node)
                        .or_else(|| nodes.get(term.node).copied())
                        .ok_or_else(|| invalid("integer conversion input missing"))?;
                    bound = bound + I::point(term.coefficient) * input;
                }
                charge(w, 8, "integer_round_source_decision")?;
                let v = crate::event_numeric::nearest_box(bound, origin)?;
                E::Affine {
                    constant: v.lo,
                    terms: vec![],
                }
            }
            E::EventMath {
                function: F::Floor,
                args,
                ..
            } if args
                .first()
                .map(|arg| new_operand_charged(arg, w))
                .transpose()?
                .unwrap_or(false) =>
            {
                E::Affine {
                    constant: decide(&args[0], nodes, local)?,
                    terms: vec![],
                }
            }
            E::Add { left, right } => E::Add {
                left: Box::new(walk(left, nodes, local, w)?),
                right: Box::new(walk(right, nodes, local, w)?),
            },
            E::Multiply { left, right } => E::Multiply {
                left: Box::new(walk(left, nodes, local, w)?),
                right: Box::new(walk(right, nodes, local, w)?),
            },
            E::Divide { left, right } => E::Divide {
                left: Box::new(walk(left, nodes, local, w)?),
                right: Box::new(walk(right, nodes, local, w)?),
            },
            E::Power { base, exponent } => E::Power {
                base: Box::new(walk(base, nodes, local, w)?),
                exponent: *exponent,
            },
            E::CheckedInteger { value, origin } => E::CheckedInteger {
                value: Box::new(walk(value, nodes, local, w)?),
                origin: origin.clone(),
            },
            E::CheckedIndex {
                index,
                first,
                last,
                origin,
            } => E::CheckedIndex {
                index: Box::new(walk(index, nodes, local, w)?),
                first: *first,
                last: *last,
                origin: origin.clone(),
            },
            E::ArrayRead {
                states,
                index,
                first,
                last,
                origin,
            } => E::ArrayRead {
                states: states.clone(),
                index: Box::new(walk(index, nodes, local, w)?),
                first: *first,
                last: *last,
                origin: origin.clone(),
            },
            E::EventMath {
                function,
                args,
                origin,
            } => E::EventMath {
                function: *function,
                args: args
                    .iter()
                    .map(|e| walk(e, nodes, local, w))
                    .collect::<Result<_, _>>()?,
                origin: origin.clone(),
            },
            E::Select {
                relation,
                left,
                right,
                then_value,
                else_value,
                ..
            } => {
                let d = crate::event_numeric::bounds_with_proofs(left, nodes, local)?
                    - crate::event_numeric::bounds_with_proofs(right, nodes, local)?;
                let (yes, no) = crate::event_numeric::sign(*relation, d);
                if !yes && !no {
                    return Err(invalid("source floor replay selection is ambiguous"));
                }
                walk(if yes { then_value } else { else_value }, nodes, local, w)?
            }
            _ => e.clone(),
        })
    }
    walk(e, nodes, local, w)
}

pub(crate) fn encoded_size<T: serde::Serialize>(v: &T, w: &Work) -> Result<usize, Error> {
    Ok(encoded(v, w)?.len())
}

/// Charged serializer used before parsing a supplied-owner admission buffer.
pub(crate) fn admission_bytes<T: serde::Serialize>(
    value: &T,
    work: &Work,
) -> Result<Vec<u8>, Error> {
    encoded(value, work)
}
