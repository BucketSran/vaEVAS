//! Private physical phases before a still-pending immutable source root.
use super::*;
use crate::exact_source::RootTime;
use crate::transition_source_plan::Work;

fn input_nodes(model: &EventModel, w: &Work) -> Result<Vec<usize>, Error> {
    w.debit(2, (model.driven.len() * 8 + 32) as u64)?;
    let mut nodes = Vec::with_capacity(model.driven.len());
    for name in &model.driven {
        let mut found = None;
        for (index, node) in model.program.nodes.iter().enumerate() {
            w.debit(2, (name.len() + node.len() + 1) as u64)?;
            if name == node {
                found = Some(index);
                break;
            }
        }
        nodes.push(
            found.ok_or_else(|| Error::new("invalid_ir", "physical phase source node absent"))?,
        );
    }
    Ok(nodes)
}
fn independent(e: &crate::ir::Expression, nodes: &[usize], w: &Work) -> Result<bool, Error> {
    use crate::ir::Expression as E;
    w.step()?;
    Ok(match e {
        E::Affine { terms, .. } => {
            let mut valid = true;
            for t in terms {
                w.step()?;
                if t.node == 0 || t.coefficient == 0. {
                    continue;
                }
                w.debit(2, nodes.len() as u64)?;
                if !nodes.contains(&t.node) {
                    valid = false;
                }
            }
            valid
        }
        E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
            let a = independent(left, nodes, w)?;
            let b = independent(right, nodes, w)?;
            a && b
        }
        E::Power { base, .. } => independent(base, nodes, w)?,
        _ => false,
    })
}
fn immutable_group(
    model: &EventModel,
    trajectory: &Trajectory,
    events: &[ScheduledEvent],
    nodes: &[usize],
    root: &RootTime,
    w: &Work,
) -> Result<bool, Error> {
    for event in events {
        w.step()?;
        match &model.triggers[event.event].trigger {
            EventTrigger::Timer { .. } => (),
            EventTrigger::Cross { guard, .. }
                if !model.dynamic_guards[event.event]
                    && !model.relocalized_guards[event.event]
                    && model.guard_operators[event.event].is_empty() =>
            {
                if !independent(guard, nodes, w)? {
                    return Ok(false);
                }
                let Some(curve) = trajectory.original_guard_curve_history(
                    guard,
                    nodes,
                    trajectory.config.stop,
                    &Default::default(),
                    w,
                )?
                else {
                    return Ok(false);
                };
                let Some(value) = curve.at_root_history(root, w)? else {
                    return Ok(false);
                };
                if !num_traits::Zero::is_zero(&value) {
                    return Ok(false);
                }
            }
            _ => return Ok(false),
        }
    }
    Ok(true)
}
/// Same display alone is insufficient: the later root must independently be
/// immutable, strictly later, and physically no later than this display query.
pub(super) fn pending_before_display(
    model: &EventModel,
    trajectory: &Trajectory,
    calendar: &[ScheduledEvent],
    start: usize,
    end: usize,
    w: &Work,
) -> Result<Option<(RootTime, I)>, Error> {
    w.step()?;
    // Only reset-free integrals carry physical history through this bridge.
    // Memoryless functions keep their complete per-phase certificates; their
    // presence does not change an independent integral epoch.
    if model.forcing.is_some()
        || model.dc_projection.is_some()
        || model.program.operators.is_empty()
    {
        return Ok(None);
    }
    for op in &model.program.operators {
        w.step()?;
        if !matches!(op, crate::ir::OperatorSpec::Idt { reset: None, .. }
            | crate::ir::OperatorSpec::Math { .. } | crate::ir::OperatorSpec::Sin { .. }) {
            return Ok(None);
        }
    }
    if end >= calendar.len() || calendar[end].time != calendar[start].time {
        return Ok(None);
    }
    let next_end = crate::schedule::batch_end(calendar, end, model)?;
    let Some(root) = crate::schedule::common_root_with_work(&calendar[start..end], w)? else {
        return Ok(None);
    };
    let Some(next) = crate::schedule::common_root_with_work(&calendar[end..next_end], w)? else {
        return Ok(None);
    };
    if !root.order_with_work(&next, w)?.is_lt() {
        return Ok(None);
    }
    let mut p = crate::exact_source::history_paid::Paid::new(w);
    let display = p
        .binary(calendar[start].time)
        .map(crate::exact_source::history_paid::root);
    let Some(display) = p.finish(display)? else {
        return Ok(None);
    };
    if next.order_with_work(&display, w)?.is_gt() {
        return Ok(None);
    }
    let nodes = input_nodes(model, w)?;
    if !immutable_group(model, trajectory, &calendar[start..end], &nodes, &root, w)?
        || !immutable_group(
            model,
            trajectory,
            &calendar[end..next_end],
            &nodes,
            &next,
            w,
        )?
    {
        return Ok(None);
    }
    let bounds = crate::schedule::event_bounds_hull_with_work(
        &calendar[start..end],
        I::point(calendar[start].time),
        w,
    )?;
    Ok(Some((root, bounds)))
}
pub(super) fn physical_inputs(
    model: &EventModel,
    trajectory: &Trajectory,
    root: &RootTime,
    w: &Work,
) -> Result<Vec<I>, Error> {
    w.debit(2, (model.driven.len() * 16 + 32) as u64)?;
    let mut bounds = Vec::with_capacity(model.driven.len());
    for index in 0..model.driven.len() {
        w.step()?;
        let exact = trajectory
            .exact_sources
            .get(index)
            .and_then(Option::as_ref)
            .map(|curve| curve.at_root_history(root, w))
            .transpose()?
            .flatten();
        if let Some(exact) = exact {
            bounds.push(
                crate::exact_source::enclosure_with_work(&exact, w)?.ok_or_else(|| {
                    Error::new(
                        "event_resolution",
                        "physical phase input cannot be enclosed",
                    )
                })?,
            );
        } else if let Some(domain) = trajectory.sample_domain_at_root(index, root, w)? {
            let lo = crate::exact_source::enclosure_with_work(&domain.lo, w)?.ok_or_else(|| {
                Error::new(
                    "event_resolution",
                    "physical input domain lower bound unavailable",
                )
            })?;
            let hi = crate::exact_source::enclosure_with_work(&domain.hi, w)?.ok_or_else(|| {
                Error::new(
                    "event_resolution",
                    "physical input domain upper bound unavailable",
                )
            })?;
            bounds.push(I {
                lo: lo.lo,
                hi: hi.hi,
            });
        } else {
            return Err(Error::new(
                "event_resolution",
                "physical phase requires complete original input domains",
            ));
        }
    }
    Ok(bounds)
}
