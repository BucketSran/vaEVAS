//! Ephemeral proof binding for ordinary point observations only.
//! The accepted Frame remains the sole owner of held-state lineage and boxes.
use super::{EventModel, Frame, Trajectory};
use crate::event_value_proof::{Context, LocalState, Proofs};
use crate::interval::Interval as I;
use crate::ir::{Error, Expression, Program};

pub(crate) struct PointLineage<'a> {
    accepted: &'a Frame,
    model: &'a EventModel,
    trajectory: &'a Trajectory,
    proof_identity: *const Proofs,
    time: f64,
    window: I,
    ordinary: bool,
}
impl<'a> PointLineage<'a> {
    pub(super) fn new(
        accepted: &'a Frame,
        model: &'a EventModel,
        trajectory: &'a Trajectory,
        context: &Context<'_>,
        time: f64,
        window: I,
        ordinary: bool,
    ) -> Self {
        Self {
            accepted,
            model,
            trajectory,
            proof_identity: context.proof_identity(),
            time,
            window,
            ordinary,
        }
    }
    #[allow(clippy::too_many_arguments)] // Keep caller source identity and supplied boxes explicit.
    pub(crate) fn sign(
        &self,
        left: &Expression,
        right: &Expression,
        owner: &str,
        program: &Program,
        driven: &[String],
        nodes: &[I],
        states: &[I],
    ) -> Result<Option<i8>, Error> {
        crate::diagnostics::counter("point_lineage_demands", 1);
        let Some(source) = self.accepted.operators.source_context.as_ref() else {
            return Ok(None);
        };
        let work = source.borrow_work();
        work.debit(2, 0)?;
        work.debit(
            2,
            (32 + states.len() * 4 + self.accepted.states.len() * 4 + self.model.driven.len() * 4)
                as u64,
        )?;
        if !self.ordinary
            || self.window.lo != self.window.hi
            || self.window.lo != self.time
            || !self.time.is_finite()
            || self.time < self.accepted.time
            || self.time > self.trajectory.config.stop
            || !std::ptr::eq(program, &self.model.program)
            || !std::ptr::eq(driven, self.model.driven.as_slice())
            || !std::ptr::eq(self.proof_identity, &self.accepted.value_proofs)
            || states.len() != self.accepted.state_bounds.len()
            || states.len() != self.accepted.states.len()
            || nodes.len() != program.nodes.len()
        {
            return Ok(None);
        }
        for (i, bounds) in states.iter().enumerate() {
            work.step()?;
            let old = self.accepted.state_bounds[i];
            if !(old.finite()
                && old.lo <= self.accepted.states[i]
                && self.accepted.states[i] <= old.hi)
                || (*bounds != old && *bounds != I::point(self.accepted.states[i]))
            {
                return Ok(None);
            }
        }
        if !crate::events::qualify_point_predicate(
            self.model,
            owner,
            (source.as_ref(), self.trajectory),
            left,
            right,
        )? {
            return Ok(None);
        }
        let original = source.original_binding().1;
        work.debit(2, (8 + original.config.pwl.len() * 4) as u64)?;
        // A validated original exact shape remains deterministic even when
        // its rounded PWL projection carries a nonzero enclosure band. Reuse
        // the existing paid qualification; unknown bands and generated sources
        // retain refusal, while exhaustion must remain a real budget error.
        match original.forcing_shaped_inputs(work) {
            Ok(_) => {}
            Err(error) if error.kind == "unsupported_forcing_scope" => return Ok(None),
            Err(error) => return Err(error),
        }
        let physical = original.history_value_bounds(self.time, work)?;
        work.debit(2, (16 + program.nodes.len() * 8) as u64)?;
        let mut exact = vec![None; program.nodes.len()];
        // Unknown placeholders remain nonpoint, so the legacy evaluator's
        // singleton fallback cannot manufacture exact internal/input values.
        let unknown = I {
            lo: f64::NEG_INFINITY,
            hi: f64::INFINITY,
        };
        let mut masked = vec![unknown; program.nodes.len()];
        work.debit(2, 128)?;
        exact[0] = crate::exact_source::binary(0.);
        masked[0] = I::ZERO;
        let Some(root) = crate::exact_source::RootTime::point(self.time) else {
            return Ok(None);
        };
        for (k, name) in self.model.driven.iter().enumerate() {
            work.step()?;
            let mut index = None;
            for (n, candidate) in program.nodes.iter().enumerate() {
                work.debit(2, (1 + name.len().min(candidate.len())) as u64)?;
                if candidate == name {
                    index = Some(n);
                    break;
                }
            }
            let Some(n) = index else {
                return Ok(None);
            };
            let Some(bounds) = physical.get(k) else {
                return Ok(None);
            };
            if nodes[n] != *bounds {
                return Ok(None);
            }
            let Some(curve) = original.exact_sources.get(k).and_then(Option::as_ref) else {
                return Ok(None);
            };
            // Preserve the existing exact helper's200k local allowance, paid
            // against this request before entry, plus bounded result storage.
            work.debit(2, 200_000 + 256)?;
            let Some(value) = curve.at_root(&root) else {
                return Ok(None);
            };
            if !crate::exact_source::enclosure_with_work(&value, work)?
                .is_some_and(|b| bounds.lo <= b.lo && b.hi <= bounds.hi)
            {
                return Ok(None);
            }
            exact[n] = Some(value);
        }
        let Some(local) = LocalState::strict_point_lineage(
            &self.accepted.state_bounds,
            &self.accepted.value_proofs,
            exact,
            work,
        )?
        else {
            return Ok(None);
        };
        // Each legacy evaluator callback precedes a node, clone or operation.
        //4096-bit admitted operands need at most8192-bit temporary products;
        // reserve their storage and comparison work before every callback.
        let mut pay = || work.debit(2, 16_384).ok();
        let a = local
            .value_with_work(left, &masked, &mut pay)
            .map_err(|_| Error::new("step_budget", "point lineage exact work exhausted"))?;
        let b = local
            .value_with_work(right, &masked, &mut pay)
            .map_err(|_| Error::new("step_budget", "point lineage exact work exhausted"))?;
        let Some((a, b)) = a.zip(b) else {
            return Ok(None);
        };
        work.debit(2, 16_384)?;
        let sign = match a.cmp(&b) {
            std::cmp::Ordering::Less => -1,
            std::cmp::Ordering::Equal => 0,
            std::cmp::Ordering::Greater => 1,
        };
        crate::diagnostics::counter("point_lineage_certified_predicates", 1);
        Ok(Some(sign))
    }
}

#[cfg(test)]
#[path = "transient_point_lineage_tests.rs"]
mod tests;
