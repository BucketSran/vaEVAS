//! History calendar bookkeeping keeps the original source and request identity.
use super::*;
use crate::transition_source_plan::Work;
pub(super) fn order(
    a: &ScheduledEvent,
    b: &ScheduledEvent,
    model: &EventModel,
) -> Result<Option<std::cmp::Ordering>, Error> {
    order_with_work(a, b, model, None)
}
pub(super) fn order_with_work(
    a: &ScheduledEvent,
    b: &ScheduledEvent,
    model: &EventModel,
    work: Option<&Work>,
) -> Result<Option<std::cmp::Ordering>, Error> {
    let Some(w) = work.or_else(|| crate::event_value_proof::history::work(model)) else {
        return Ok(certified_order(a, b, model));
    };
    w.debit(2, 0)?;
    if let Some(order) = a.moment.exact_order_with_work(&b.moment, w)? {
        return Ok(Some(order));
    }
    let same_guard = match (
        &model.triggers[a.event].trigger,
        &model.triggers[b.event].trigger,
    ) {
        (EventTrigger::Cross { guard: a, .. }, EventTrigger::Cross { guard: b, .. }) => {
            crate::history_admission::same_expression(a, b, w)?
        }
        _ => false,
    };
    Ok((same_guard && coincides(&a.moment, &b.moment, true, w)?)
        .then_some(std::cmp::Ordering::Equal))
}
pub(super) fn coincides(a: &Moment, b: &Moment, same: bool, w: &Work) -> Result<bool, Error> {
    w.debit(2, 0)?;
    w.debit(2, 8)?;
    if let Some(order) = a.exact_order_with_work(b, w)? {
        return Ok(order == std::cmp::Ordering::Equal);
    }
    let bounds = a.bounds_with_work(w)?;
    if bounds.lo == bounds.hi && bounds == b.bounds_with_work(w)? {
        return Ok(true);
    }
    match (a, b) {
        (Moment::Cross(a), Moment::Cross(b)) => a.coincides_history(b, same, w),
        (
            Moment::Timer {
                start: a,
                period: p,
                index: k,
                ..
            },
            Moment::Timer {
                start: b,
                period: q,
                index: l,
                ..
            },
        ) => Ok(a == b && p == q && k == l),
        _ => Err(unresolved(
            "history calendar escaped independent Cross/Timer gate",
        )),
    }
}
pub(super) use crate::history_storage::sort;
pub(super) fn independent_kinds_with_work(
    events: &[ScheduledEvent],
    model: &EventModel,
    work: Option<&Work>,
) -> Result<bool, Error> {
    let work = work.or_else(|| crate::event_value_proof::history::work(model));
    if let Some(w) = work {
        w.debit(2, 0)?;
    }
    for event in events {
        if let Some(w) = work {
            w.step()?;
        }
        if !(event.moment.clock().is_some()
            || matches!(event.moment, Moment::Cross(_) | Moment::Anchored { .. }))
        {
            return Ok(false);
        }
    }
    Ok(true)
}
pub(super) fn all_ordered_with_work(
    events: &[ScheduledEvent],
    model: &EventModel,
    work: Option<&Work>,
) -> Result<bool, Error> {
    for a in events {
        for b in events {
            if order_with_work(a, b, model, work)?.is_none() {
                return Ok(false);
            }
        }
    }
    Ok(true)
}
pub(super) fn any_unordered_with_work(
    events: &[ScheduledEvent],
    next: &ScheduledEvent,
    model: &EventModel,
    work: Option<&Work>,
) -> Result<bool, Error> {
    for event in events {
        if order_with_work(event, next, model, work)?.is_none() {
            return Ok(true);
        }
    }
    Ok(false)
}
pub(super) fn curve(
    t: &Trajectory,
    guard: &Expression,
    projected: Option<&Expression>,
    nodes: &[usize],
    w: &Work,
) -> Result<Option<crate::exact_source::Curve>, Error> {
    let empty = crate::exact_source::TimeProofs::new();
    let result = t.original_guard_curve_history(guard, nodes, t.config.stop, &empty, w)?;
    if result.is_some() {
        return Ok(result);
    }
    if let Some(projected) = projected {
        t.original_guard_curve_history(projected, nodes, t.config.stop, &empty, w)
    } else {
        Ok(None)
    }
}
