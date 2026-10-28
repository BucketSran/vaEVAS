//! Recheck only control choices depending on independently provided nodes.
//! Unrelated history targets retain their original time/source proof context.
use super::*;

pub(super) fn compare(
    relation: ir::Relation,
    a: &Cell,
    b: &Cell,
    w: &Work,
) -> Result<Option<bool>, Error> {
    let (yes, no) = crate::event_numeric::sign(relation, a.bound()? - b.bound()?);
    if yes {
        return Ok(Some(true));
    }
    if no {
        return Ok(Some(false));
    }
    let Some((a, b)) = a.proof.as_ref().zip(b.proof.as_ref()) else {
        return Ok(None);
    };
    let mut paid = crate::exact_source::history_paid::Paid::new(w);
    let order = paid.cmp(a, b);
    let order = paid.finish(order)?.ok_or_else(|| {
        Error::new(
            "event_condition",
            "procedure comparison exceeds its exact allowance",
        )
    })?;
    Ok(Some(match relation {
        ir::Relation::Lt => order.is_lt(),
        ir::Relation::Le => !order.is_gt(),
        ir::Relation::Gt => order.is_gt(),
        ir::Relation::Ge => !order.is_lt(),
    }))
}
impl Plan {
    #[allow(clippy::too_many_arguments)]
    pub(super) fn recertify_controls(
        &self,
        exogenous: &[bool],
        points: &[Option<f64>],
        boxes: &[I],
        before: &[I],
        operators: &[I],
        context: Option<&Context<'_>>,
        w: &Work,
    ) -> Result<(), Error> {
        w.debit(2, (self.count + 64) as u64)?;
        let mut dependent = Vec::with_capacity(self.count);
        for id in 0..self.count {
            w.step()?;
            let node = self
                .graph
                .node(id)
                .ok_or_else(|| invalid("missing control graph node"))?;
            let mut live = false;
            if let O::Affine { terms, .. } = &node.operation {
                for term in terms.iter() {
                    w.step()?;
                    // Zero coefficients still retain the original source dependency.
                    live |= term.node != 0 && !exogenous[term.node] && boxes[term.node].finite();
                }
            }
            for &operand in &node.operands {
                w.step()?;
                live |= dependent[operand];
            }
            dependent.push(live);
        }
        w.debit(
            2,
            ((self.guards.len() * 2 + self.selectors.len()) * 16 + 64) as u64,
        )?;
        let mut roots = Vec::new();
        for guard in &self.guards {
            w.step()?;
            if dependent[guard.left] || dependent[guard.right] {
                roots.extend([guard.left, guard.right]);
            }
        }
        for selector in &self.selectors {
            w.step()?;
            if dependent[selector.index] {
                roots.push(selector.index);
            }
        }
        if roots.is_empty() {
            return Ok(());
        }
        let values = self.evaluate(
            false,
            &roots,
            points,
            boxes,
            &self.point_states,
            before,
            &self.point_operators,
            operators,
            context,
            w,
        )?;
        let mut values = values.iter();
        for guard in &self.guards {
            w.step()?;
            if dependent[guard.left] || dependent[guard.right] {
                let a = values.next().ok_or_else(|| invalid("missing guard left"))?;
                let b = values
                    .next()
                    .ok_or_else(|| invalid("missing guard right"))?;
                let same = if guard.post_root {
                    super::right_limit::recertify(guard.relation, a, b, guard.value, w)?
                } else {
                    compare(guard.relation, a, b, w)? == Some(guard.value)
                };
                if !same {
                    return Err(Error::new("event_condition",
                        "current independent node enclosure changes source-position branch execution"));
                }
            }
        }
        for selector in &self.selectors {
            w.step()?;
            if dependent[selector.index] {
                let bound = values
                    .next()
                    .ok_or_else(|| invalid("missing array selector"))?
                    .bound()?;
                // checked_index admitted a single in-range integer at capture.
                // The current full image must prove precisely that same slot.
                if bound.lo != selector.value || bound.hi != selector.value {
                    return Err(Error::new(
                        "array_index_range",
                        "current independent node enclosure changes source-position array slot",
                    ));
                }
            }
        }
        Ok(())
    }
}
