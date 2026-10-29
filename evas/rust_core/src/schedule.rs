//! Certified event calendars. Nominal timer times never accumulate accepted steps.
use crate::continuous::Continuous;
use crate::event_accuracy::{unresolved, GuardBounds};
use crate::events::EventModel;
use crate::exact_time::Clock;
use crate::interval::Interval as I;
use crate::ir::{Error, EventTrigger, Expression, TransientInputs};
use crate::operators::Operators;
use crate::pwl::{Root, Trajectory};
use std::sync::Arc;

#[path = "schedule_history_bookkeeping.rs"]
mod history_bookkeeping;
pub(crate) const EVENT_BUDGET: usize = 1_000_000;
pub(crate) const CAUSAL_MICROEVENT_BUDGET: usize = 64;

#[derive(Clone)]
pub(crate) struct ScheduledEvent {
    pub(crate) time: f64,
    pub(crate) event: usize,
    moment: Moment,
    // Set only by exact fixed-clock ordering. Retaining this pending event
    // across an epoch must not discard the proof against its predecessor.
    fixed_predecessor: Option<f64>,
    // Shared only by leaves copied from one certified isolation result.
    occurrence: Option<Arc<()>>,
}

/// Split execution by physical roots, even when binary64 representatives collide.
/// An unproved legacy simultaneous batch retains its previous conflict handling.
pub(crate) fn batch_end(
    events: &[ScheduledEvent],
    start: usize,
    model: &EventModel,
) -> Result<usize, Error> {
    let w = crate::real_expression::work(model);
    w.step()?;
    let mut end = start + 1;
    while end < events.len() && events[end].time == events[start].time {
        if matches!(
            events[start]
                .moment
                .exact_order_with_work(&events[end].moment, w)?,
            Some(std::cmp::Ordering::Less | std::cmp::Ordering::Greater)
        ) {
            break;
        }
        end += 1;
    }
    Ok(end)
}

pub(crate) fn common_occurrence(
    events: &[ScheduledEvent],
    model: &EventModel,
) -> Result<bool, Error> {
    let Some(first) = events.first() else {
        return Ok(false);
    };
    let w = crate::real_expression::work(model);
    w.debit(2, events.len() as u64 + 8)?;
    if events.len() == 1 {
        return Ok(true);
    }
    if let Some(token) = &first.occurrence {
        if events
            .iter()
            .all(|e| e.occurrence.as_ref().is_some_and(|t| Arc::ptr_eq(t, token)))
        {
            return Ok(true);
        }
    }
    Ok(common_root_with_work(events, w)?.is_some())
}

// The cache is scoped to one calendar/history epoch. Keys include the original
// guard owner, segment and full discovery settings. Reusing its root objects,
// rather than comparing their boxes, is the nonrational occurrence certificate.
struct SharedIsolation {
    leaf: usize,
    local: bool,
    segment: [f64; 2],
    roots: Vec<(crate::dynamic_roots::CertifiedRoot, Arc<()>)>,
}
fn same_isolation_guard(
    a: &Expression,
    b: &Expression,
    w: &crate::transition_source_plan::Work,
) -> Result<bool, Error> {
    w.step()?;
    Ok(match (a, b) {
        (
            Expression::Power {
                base: a,
                exponent: x,
            },
            Expression::Power {
                base: b,
                exponent: y,
            },
        ) => x == y && same_isolation_guard(a, b, w)?,
        (Expression::Add { left: a, right: b }, Expression::Add { left: c, right: d })
        | (
            Expression::Multiply { left: a, right: b },
            Expression::Multiply { left: c, right: d },
        )
        | (Expression::Divide { left: a, right: b }, Expression::Divide { left: c, right: d }) => {
            same_isolation_guard(a, c, w)? && same_isolation_guard(b, d, w)?
        }
        _ => crate::history_admission::same_expression(a, b, w)?,
    })
}
fn shared_isolation(
    cache: &mut Vec<SharedIsolation>,
    leaf: usize,
    local: bool,
    segment: [f64; 2],
    model: &EventModel,
    work: Option<&crate::transition_source_plan::Work>,
    isolate: impl FnOnce() -> Result<Vec<crate::dynamic_roots::CertifiedRoot>, Error>,
) -> Result<Vec<(crate::dynamic_roots::CertifiedRoot, Arc<()>)>, Error> {
    for entry in cache.iter() {
        if let Some(w) = work {
            w.step()?;
        }
        if entry.local != local || entry.segment != segment {
            continue;
        }
        let a = &model.triggers[entry.leaf];
        let b = &model.triggers[leaf];
        if let Some(w) = work {
            w.debit(
                2,
                (model.program.events[a.event].origin.instance.len()
                    + model.program.events[b.event].origin.instance.len()
                    + 1) as u64,
            )?;
        }
        if model.program.events[a.event].origin.instance
            != model.program.events[b.event].origin.instance
            || model.program.events[a.event].procedure_id
                != model.program.events[b.event].procedure_id
        {
            continue;
        }
        let same = match (&a.trigger, &b.trigger) {
            (
                EventTrigger::Cross {
                    guard: a,
                    direction: ad,
                    time_tolerance: at,
                    expression_tolerance: ae,
                },
                EventTrigger::Cross {
                    guard: b,
                    direction: bd,
                    time_tolerance: bt,
                    expression_tolerance: be,
                },
            ) => {
                ad == bd
                    && at == bt
                    && ae == be
                    && if let Some(w) = work {
                        same_isolation_guard(a, b, w)?
                    } else {
                        a == b
                    }
            }
            _ => false,
        };
        if same {
            if let Some(w) = work {
                w.debit(2, (entry.roots.len() * 64 + 32) as u64)?;
            }
            return Ok(entry.roots.clone());
        }
    }
    let discovered = isolate()?;
    if let Some(w) = work {
        w.debit(2, (discovered.len() * 160 + 128) as u64)?;
    }
    let roots = discovered
        .into_iter()
        .map(|root| (root, Arc::new(())))
        .collect::<Vec<_>>();
    let entry = SharedIsolation {
        leaf,
        local,
        segment,
        roots: roots.clone(),
    };
    if let Some(w) = work {
        crate::history_storage::push_vec(cache, entry, w)?;
    } else {
        cache.push(entry);
    }
    Ok(roots)
}

/// Every calendar leaf must prove the same mathematical root independently.
/// A representative or overlapping discovery boxes are never an identity.
pub(crate) fn copy_calendar(
    events: &[ScheduledEvent],
    model: &EventModel,
) -> Result<Vec<ScheduledEvent>, Error> {
    // New occurrence handles add storage and Arc clone work to every copied
    // entry, including the legacy calendar copy route.
    let original = crate::real_expression::work(model);
    original.debit(2, 0)?;
    original.debit(2, (events.len() * 16 + 32) as u64)?;
    let Some(w) = crate::analytic_request::proof_owner(model).map(|o| o.work()) else {
        return Ok(events.to_vec());
    };
    w.debit(2, 0)?;
    w.debit(
        2,
        (events.len() as u64).saturating_mul(
            std::mem::size_of::<ScheduledEvent>().div_ceil(std::mem::size_of::<usize>()) as u64,
        ),
    )?;
    let mut out = Vec::with_capacity(events.len());
    for event in events {
        w.step()?;
        out.push(event.clone_history(w)?)
    }
    Ok(out)
}
pub(crate) fn common_root(events: &[ScheduledEvent]) -> Option<crate::exact_source::RootTime> {
    let first = events.first()?.exact_root()?;
    for event in events.iter().skip(1) {
        if first.order(&event.exact_root()?) != std::cmp::Ordering::Equal {
            return None;
        }
    }
    Some(first)
}

/// This path needs an ordinary binary64 execution time before every later
/// physical root. It does not construct a microevent sequence within one ulp.
fn serial_transition_cluster(
    events: &mut [ScheduledEvent],
    model: &EventModel,
) -> Result<bool, Error> {
    // Qualification fixes every guard_operator set to empty for this route.
    // Avoid scanning a legacy dynamic-provider cluster that cannot apply.
    if let Some(w) = crate::analytic_request::proof_owner(model).map(|o| o.work()) {
        w.debit(2, 0)?;
        w.step()?;
        return Ok(false);
    }
    if !events.iter().any(|e| {
        model.guard_operators[e.event].iter().any(|&o| {
            matches!(
                model.program.operators[o],
                crate::ir::OperatorSpec::Transition { .. }
            )
        })
    }) || events.iter().any(|e| e.fixed_predecessor.is_some())
    {
        return Ok(false);
    }
    let Some(mut ordered) = events
        .iter()
        .map(|e| Some((e.exact_root()?, e.clone())))
        .collect::<Option<Vec<_>>>()
    else {
        return Ok(false);
    };
    ordered.sort_by(|(a, e), (b, f)| a.order(b).then(e.event.cmp(&f.event)));
    let mut start = 0;
    while start < ordered.len() {
        let mut end = start + 1;
        while end < ordered.len()
            && ordered[start].0.order(&ordered[end].0) == std::cmp::Ordering::Equal
        {
            end += 1;
        }
        let time = ordered[start..end]
            .iter()
            .map(|(_, e)| e.time)
            .max_by(f64::total_cmp)
            .unwrap();
        if end < ordered.len()
            && crate::exact_source::RootTime::point(time)
                .is_none_or(|t| t.order(&ordered[end].0) != std::cmp::Ordering::Less)
        {
            return Ok(false);
        }
        for (_, event) in &mut ordered[start..end] {
            if !event
                .moment
                .accepts(time, &model.triggers[event.event].trigger)
            {
                return Err(unresolved(
                    "serial transition root representative exceeds original tolerance",
                ));
            }
            event.time = time;
        }
        start = end;
    }
    for (destination, (_, event)) in events.iter_mut().zip(ordered) {
        *destination = event;
    }
    Ok(true)
}

impl ScheduledEvent {
    fn accepts_execution(
        &self,
        time: f64,
        model: &EventModel,
        work: Option<&crate::transition_source_plan::Work>,
    ) -> Result<bool, Error> {
        if self
            .moment
            .accepts(time, &model.triggers[self.event].trigger)
        {
            return Ok(true);
        }
        if !matches!(&self.moment, Moment::Cross(root) if root.has_source_zero())
            || model.dynamic_guards[self.event]
            || model.relocalized_guards[self.event]
            || !model.guard_operators[self.event].is_empty()
            || time != self.bounds().hi
        {
            return Ok(false);
        }
        // The physical root itself is exact. The outward display box does not
        // replace its zero-error root certificate, and time is not advanced.
        Ok(self
            .exact_root_with_work(work.unwrap_or_else(|| crate::real_expression::work(model)))?
            .is_some())
    }
    pub(crate) fn record_ambiguous_query(&self, site: &str, query: f64) {
        let (kind, clock, exact) = match &self.moment {
            Moment::HeldTimer { clock, exact, .. } => {
                ("held_timer", clock.is_some(), exact.is_some())
            }
            Moment::Timer { .. } => ("timer", true, false),
            Moment::Cross(_) => ("source_cross", false, self.exact_root().is_some()),
            Moment::Anchored { exact, .. } => ("anchored", false, exact.is_some()),
            Moment::Dynamic { exact, .. } => ("dynamic", false, exact.is_some()),
        };
        crate::diagnostics::detail(
            "ambiguous_query",
            "rejected",
            Some(query),
            &serde_json::json!({
                "site":site,"query":query,"leaf":self.event,"representative":self.time,
                "bounds":[self.bounds().lo,self.bounds().hi],"moment":kind,"clock":clock,"exact":exact
            }),
        );
    }
    fn exact_root(&self) -> Option<crate::exact_source::RootTime> {
        let root = if let Some(root) = self.moment.exact_history_root() {
            root.clone()
        } else if let Moment::Cross(root) = &self.moment {
            root.rational_time()?
        } else {
            crate::exact_source::RootTime::from_clock(self.moment.clock()?, self.bounds())?
        };
        root.refine(self.bounds())?;
        Some(root)
    }

    pub(crate) fn exact_input_value(
        &self,
        model: &EventModel,
        trajectory: &Trajectory,
        time: f64,
    ) -> Option<I> {
        if !self.can_refine_input_root(model) || !trajectory.has_only_physical_inputs() {
            return None;
        }
        let EventTrigger::Cross { guard, .. } = &model.triggers[self.event].trigger else {
            return None;
        };
        let nodes: Option<Vec<_>> = model
            .driven
            .iter()
            .map(|name| model.program.nodes.iter().position(|node| node == name))
            .collect();
        crate::exact_source::point_bounds(guard, &nodes?, &trajectory.exact_sources, time)
    }

    pub(crate) fn can_refine_input_root(&self, model: &EventModel) -> bool {
        model.guard_operators[self.event].is_empty()
            && !model.relocalized_guards[self.event]
            && self.fixed_predecessor.is_none()
            && matches!(self.moment, Moment::Dynamic { exact: None, bounds, .. }
                if bounds.lo < bounds.hi && self.time == bounds.hi)
    }

    /// Refine only a source-driven root, using its original proof and guard.
    /// Timers, exact roots and roots tied to a mutable history epoch are outside
    /// this policy. The public cross tolerances are never rewritten.
    pub(crate) fn refine_input_root(
        &self,
        model: &EventModel,
        trajectory: &Trajectory,
        operators: &Operators,
        target_width: Option<f64>,
        work_limit: usize,
    ) -> Result<(Self, crate::dynamic_roots::Refinement), Error> {
        if !self.can_refine_input_root(model) {
            return Err(unresolved("event is outside input-root refinement scope"));
        }
        let leaf = &model.triggers[self.event];
        let EventTrigger::Cross { guard, .. } = &leaf.trigger else {
            unreachable!()
        };
        let origin = &model.program.events[leaf.event].origin;
        let guards = crate::guard_trajectory::GuardTrajectory::new(model, trajectory, operators)?;
        let Moment::Dynamic {
            bounds, derivative, ..
        } = self.moment
        else {
            unreachable!()
        };
        let root = crate::dynamic_roots::refine(
            crate::dynamic_roots::CertifiedRoot { bounds, derivative },
            target_width,
            work_limit,
            &mut |t| {
                let original = guards.range(guard, t, &origin.instance)?.0;
                if target_width.is_none() && t.lo == t.hi {
                    if let Some(exact) = self.exact_input_value(model, trajectory, t.lo) {
                        let bounds = I {
                            lo: original.lo.max(exact.lo),
                            hi: original.hi.min(exact.hi),
                        };
                        if bounds.lo > bounds.hi {
                            return Err(unresolved(
                                "exact source value contradicts the guard enclosure",
                            ));
                        }
                        return Ok(bounds);
                    }
                }
                Ok(original)
            },
            &mut |t| Ok(guards.range(guard, t, &origin.instance)?.1),
        )?;
        let mut candidate = self.clone();
        let Moment::Dynamic {
            bounds, derivative, ..
        } = &mut candidate.moment
        else {
            unreachable!()
        };
        *bounds = root.root.bounds;
        *derivative = root.root.derivative;
        candidate.time = root.root.bounds.hi;
        if !candidate.moment.accepts(candidate.time, &leaf.trigger) {
            return Err(unresolved(
                "refined root exceeds the original cross tolerances",
            ));
        }
        Ok((candidate, root))
    }

    pub(crate) fn is_fixed_timer(&self) -> bool {
        self.moment.clock().is_some()
    }
    pub(crate) fn bounds(&self) -> I {
        self.moment.bounds()
    }
    pub(crate) fn clock(&self) -> Option<Clock> {
        self.moment.clock()
    }
    pub(crate) fn local_bounds(&self, clock: Clock) -> Option<I> {
        if let Some(root) = self.moment.exact_history_root() {
            return root.local_bounds(clock);
        }
        if let Some(other) = self.moment.clock() {
            return other.difference(clock);
        }
        match &self.moment {
            Moment::Anchored { anchor, delta, .. } if *anchor == clock => Some(*delta),
            Moment::Cross(root) => root.local_bounds(clock),
            _ => None,
        }
    }

    /// Compare the proved physical event with an exact binary64 query, never
    /// with its delayed execution representative. Equality observes post-event.
    pub(crate) fn physical_order_at(&self, time: f64) -> Option<std::cmp::Ordering> {
        let query = Moment::Timer {
            bounds: I::point(time),
            start: time,
            period: 0.,
            index: 0,
        };
        self.moment
            .exact_history_root()
            .and_then(|root| root.clock_delta_order(query.clock()?, 0.))
            .or_else(|| self.moment.exact_order(&query))
            .or_else(|| {
                if let Moment::Anchored { anchor, delta, .. } = &self.moment {
                    let query = anchor.delta(time)?;
                    if delta.hi <= query.lo {
                        return Some(std::cmp::Ordering::Less);
                    }
                    if delta.lo > query.hi {
                        return Some(std::cmp::Ordering::Greater);
                    }
                }
                let bounds = self.bounds();
                if bounds.lo == bounds.hi && bounds.lo == time {
                    Some(std::cmp::Ordering::Equal)
                } else if bounds.hi <= time {
                    Some(std::cmp::Ordering::Less)
                } else if bounds.lo > time {
                    Some(std::cmp::Ordering::Greater)
                } else {
                    None
                }
            })
    }

    /// A voltage-sized root enclosure need not resolve a nearby query's phase.
    /// Prove that phase from the original transverse input guard without
    /// changing the sampling enclosure, representative, or accepted history.
    pub(crate) fn physical_order_for_query(
        &self,
        time: f64,
        model: &EventModel,
        trajectory: &Trajectory,
    ) -> Option<std::cmp::Ordering> {
        if let Some(order) = self.physical_order_at(time) {
            return Some(order);
        }
        // The guard's dependency proof, not unrelated downstream operators,
        // determines whether its sign can resolve a query. History-dependent
        // roots remain excluded and every selected history is still certified.
        if !self.can_refine_input_root(model) {
            return None;
        }
        let EventTrigger::Cross { guard, .. } = &model.triggers[self.event].trigger else {
            return None;
        };
        let operators = Operators::default();
        let source =
            crate::guard_trajectory::GuardTrajectory::new(model, trajectory, &operators).ok()?;
        let owner = &model.program.events[model.triggers[self.event].event]
            .origin
            .instance;
        crate::diagnostics::counter("root_query_phase_checks", 1);
        // Original physical PWLs can prove the sign at a binary64 query even
        // when ordinary interval products straddle zero. This certificate only
        // selects the already-isolated transverse root's side. Its enclosure,
        // sampled input bounds and execution time are unchanged.
        let nodes: Option<Vec<_>> = model
            .driven
            .iter()
            .map(|name| model.program.nodes.iter().position(|node| node == name))
            .collect();
        let sign = nodes
            .and_then(|nodes| {
                crate::exact_source::predicate_sign(
                    guard,
                    &crate::ir::Expression::Affine {
                        constant: 0.,
                        terms: vec![],
                    },
                    &nodes,
                    &trajectory.exact_sources,
                    time,
                )
            })
            .or_else(|| source.range(guard, I::point(time), owner).ok()?.0.sign())?;
        Some(match sign * self.dynamic_direction()? {
            -1 => std::cmp::Ordering::Greater,
            0 => std::cmp::Ordering::Equal,
            1 => std::cmp::Ordering::Less,
            _ => unreachable!(),
        })
    }

    pub(crate) fn retain_after(&mut self, prior: &Self, model: &EventModel) -> Result<bool, Error> {
        if self.moment.exact_order(&prior.moment) != Some(std::cmp::Ordering::Greater) {
            return Ok(false);
        }
        // The original exact roots order the phases; never invent a later time.
        self.time = self.time.max(prior.time);
        if !self.accepts_execution(self.time, model, None)? {
            return Err(unresolved(
                "retained exact event order exceeds original tolerances",
            ));
        }
        self.fixed_predecessor = Some(prior.time);
        Ok(true)
    }

    /// Certified guard side just after this cross root (LRM 2.4 5.10.3.1).
    /// Only strict sign-changing affine source roots carry this certificate.
    pub(crate) fn post_root_side(&self) -> Option<i8> {
        match &self.moment {
            Moment::Cross(root) => root.post_root_side(),
            _ => None,
        }
    }

    pub(crate) fn dynamic_direction(&self) -> Option<i8> {
        match self.moment {
            Moment::Dynamic { derivative, .. } | Moment::Anchored { derivative, .. } => {
                derivative.sign().filter(|&s| s != 0)
            }
            _ => None,
        }
    }
}

/// Opaque permission to observe a proved physical event in a local epoch.
/// Geometry alone cannot construct this: source moments retain their original
/// exact numerator and dynamic roots retain the immutable history that proved them.
pub(crate) struct OrderedObservation {
    anchor: Clock,
    delta: I,
    proofs: Vec<Arc<Continuous>>,
}
impl OrderedObservation {
    pub(crate) fn delta(&self) -> I {
        self.delta
    }
    pub(crate) fn validate(&self, history: &Arc<Continuous>) -> bool {
        history
            .local_epoch()
            .is_some_and(|(clock, start)| clock == self.anchor && self.delta.lo >= start)
            && self.proofs.iter().all(|proof| Arc::ptr_eq(proof, history))
    }
}
pub(crate) fn ordered_observation(
    events: &[ScheduledEvent],
    clock: Clock,
    model: &EventModel,
) -> Result<OrderedObservation, Error> {
    let first = events
        .first()
        .ok_or_else(|| unresolved("local physical observation has no event identity"))?;
    for event in events {
        if history_bookkeeping::order(first, event, model)? != Some(std::cmp::Ordering::Equal) {
            return Err(unresolved(
                "local observation cannot merge distinct physical events",
            ));
        }
    }
    let mut proofs = Vec::new();
    let mut delta = None;
    for event in events {
        let bound = event
            .local_bounds(clock)
            .ok_or_else(|| unresolved("local event has no exact physical time certificate"))?;
        delta = Some(delta.map_or(bound, |old: I| old.hull(bound)));
        match &event.moment {
            Moment::Anchored { history, .. } => proofs.push(history.clone()),
            Moment::Dynamic {
                exact: Some(_),
                history: Some(history),
                ..
            } => proofs.push(history.clone()),
            _ => {}
        }
    }
    Ok(OrderedObservation {
        anchor: clock,
        delta: delta.unwrap(),
        proofs,
    })
}
fn certified_order(
    a: &ScheduledEvent,
    b: &ScheduledEvent,
    model: &EventModel,
) -> Option<std::cmp::Ordering> {
    a.moment.exact_order(&b.moment).or_else(|| {
        let same_guard=matches!((&model.triggers[a.event].trigger,&model.triggers[b.event].trigger),(EventTrigger::Cross {guard:x,..},EventTrigger::Cross {guard:y,..}) if x==y);
        (same_guard && a.moment.coincides(&b.moment,true)).then_some(std::cmp::Ordering::Equal)
    })
}

#[derive(Clone)]
enum Moment {
    Cross(Root),
    Anchored {
        anchor: Clock,
        delta: I,
        derivative: I,
        end: f64,
        bounds: I,
        history: Arc<Continuous>,
        exact: Option<crate::exact_source::RootTime>,
    },
    Dynamic {
        history: Option<Arc<Continuous>>,
        exact: Option<crate::exact_source::RootTime>,
        bounds: I,
        derivative: I,
        end: f64,
    },
    Timer {
        bounds: I,
        start: f64,
        period: f64,
        index: usize,
    },
    HeldTimer {
        exact: Option<crate::exact_source::RootTime>,
        bounds: I,
        index: usize,
        clock: Option<Clock>,
    },
}

impl Moment {
    /// Static timer parameters and the bounded integer index define an exact
    /// binary-rational nominal time even when its interval endpoints overlap.
    fn clock(&self) -> Option<Clock> {
        match self {
            Self::Timer {
                start,
                period,
                index,
                ..
            } => Some(Clock {
                start: *start,
                period: *period,
                index: *index,
            }),
            Self::HeldTimer { clock, .. } => *clock,
            _ => None,
        }
    }
    fn exact_history_root(&self) -> Option<&crate::exact_source::RootTime> {
        match self {
            Self::Dynamic { exact, .. }
            | Self::Anchored { exact, .. }
            | Self::HeldTimer { exact, .. } => exact.as_ref(),
            _ => None,
        }
    }

    fn exact_order(&self, other: &Self) -> Option<std::cmp::Ordering> {
        if let Some(root) = self.exact_history_root() {
            if let Some(next) = other.exact_history_root() {
                return Some(root.order(next));
            }
            if let Some(clock) = other.clock() {
                return root.clock_delta_order(clock, 0.);
            }
            if let Self::Cross(next) = other {
                return Some(root.order(&next.rational_time()?));
            }
        }
        if other.exact_history_root().is_some() {
            return other.exact_order(self).map(std::cmp::Ordering::reverse);
        }
        if std::ptr::eq(self, other) {
            return Some(std::cmp::Ordering::Equal);
        }
        if let (Some(a), Some(b)) = (self.clock(), other.clock()) {
            return a.order(b);
        }
        match (self, other) {
            (Self::Anchored { anchor, delta, .. }, b) => {
                let other = if let Some(clock) = b.clock() {
                    clock.difference(*anchor)?
                } else {
                    match b {
                        Self::Cross(root) => root.local_bounds(*anchor)?,
                        Self::Anchored {
                            anchor: b,
                            delta: d,
                            ..
                        } if b == anchor => *d,
                        _ => return None,
                    }
                };
                if delta.hi < other.lo {
                    Some(std::cmp::Ordering::Less)
                } else if delta.lo > other.hi {
                    Some(std::cmp::Ordering::Greater)
                } else if delta.lo == delta.hi && *delta == other {
                    Some(std::cmp::Ordering::Equal)
                } else {
                    None
                }
            }
            (a, Self::Anchored { .. }) => other.exact_order(a).map(std::cmp::Ordering::reverse),
            (Self::Cross(a), Self::Cross(b)) => a.exact_order(b),
            (Self::Cross(root), clock) => root.clock_order(clock.clock()?),
            (clock, Self::Cross(root)) => root
                .clock_order(clock.clock()?)
                .map(std::cmp::Ordering::reverse),
            _ => None,
        }
    }

    fn bounds(&self) -> I {
        // Optional held-state provenance must not contract numeric sampling.
        if let Self::HeldTimer { bounds, .. } = self {
            return *bounds;
        }
        let discovery = match self {
            Self::Cross(root) => root.bounds,
            Self::Anchored { bounds, .. } => *bounds,
            Self::Dynamic { bounds, .. } => *bounds,
            Self::Timer { bounds, .. } => *bounds,
            Self::HeldTimer { bounds, .. } => *bounds,
        };
        self.exact_history_root()
            .and_then(|root| root.refine(discovery))
            .unwrap_or(discovery)
    }

    fn coincides(&self, other: &Self, same_guard: bool) -> bool {
        if let (Some(a), Some(b)) = (self.exact_history_root(), other.exact_history_root()) {
            return a.order(b) == std::cmp::Ordering::Equal;
        }
        let bounds = self.bounds();
        if bounds.lo == bounds.hi && bounds == other.bounds() {
            return true;
        }
        match (self, other) {
            (
                Self::Anchored {
                    anchor: a,
                    delta: x,
                    ..
                },
                Self::Anchored {
                    anchor: b,
                    delta: y,
                    ..
                },
            ) => a == b && x == y && (same_guard || x.lo == x.hi),
            (Self::Dynamic { bounds: a, .. }, Self::Dynamic { bounds: b, .. }) => {
                same_guard && a == b
            }
            (Self::Cross(a), Self::Cross(b)) => a.coincides(b, same_guard),
            (
                Self::Timer {
                    start: a,
                    period: p,
                    index: k,
                    ..
                },
                Self::Timer {
                    start: b,
                    period: q,
                    index: l,
                    ..
                },
            ) => a == b && p == q && k == l,
            (
                Self::HeldTimer {
                    bounds: a,
                    index: k,
                    ..
                },
                Self::HeldTimer {
                    bounds: b,
                    index: l,
                    ..
                },
            ) => same_guard && a == b && k == l,
            _ => false,
        }
    }

    fn accepts(&self, time: f64, trigger: &EventTrigger) -> bool {
        match (self, trigger) {
            (
                Self::Anchored {
                    anchor,
                    delta,
                    derivative,
                    end,
                    ..
                },
                EventTrigger::Cross {
                    time_tolerance,
                    expression_tolerance,
                    ..
                },
            ) => {
                let Some(local) = anchor.delta(time) else {
                    return false;
                };
                let delta = self
                    .exact_history_root()
                    .and_then(|r| r.local_bounds(*anchor))
                    .unwrap_or(*delta);
                let delay = local - delta;
                local.lo >= delta.hi
                    && time <= *end
                    && delay.hi <= *time_tolerance
                    && (*derivative * delay).magnitude() <= *expression_tolerance
            }
            (
                Self::Dynamic {
                    bounds,
                    derivative,
                    end,
                    ..
                },
                EventTrigger::Cross {
                    time_tolerance,
                    expression_tolerance,
                    ..
                },
            ) => {
                let bounds = self
                    .exact_history_root()
                    .and_then(|r| r.refine(*bounds))
                    .unwrap_or(*bounds);
                let delay = I::point(time) - bounds;
                time >= bounds.hi
                    && time <= *end
                    && delay.hi <= *time_tolerance
                    && (*derivative * delay).magnitude() <= *expression_tolerance
            }

            (
                Self::Cross(root),
                EventTrigger::Cross {
                    time_tolerance,
                    expression_tolerance,
                    ..
                },
            ) => root.accepts(time, *time_tolerance, *expression_tolerance),
            (Self::Timer { bounds, .. }, EventTrigger::Timer { time_tolerance, .. }) => {
                let error = I::point(time) - *bounds;
                error.finite() && error.magnitude() <= *time_tolerance
            }
            (Self::HeldTimer { bounds, .. }, EventTrigger::HeldTimer { time_tolerance, .. }) => {
                let error = I::point(time) - *bounds;
                error.finite() && error.magnitude() <= *time_tolerance
            }
            _ => false,
        }
    }
}

/// Resolve a complete cluster with certified physical order. Keep nominal
/// enclosures for sampling/forward-error propagation; representative delays
/// neither erase uncertainty nor relax any clock's original tolerance.
// Only a certified equal-time group containing a fixed zero-tolerance timer
// may use this contraction. Each fixed clock must independently prove the same
// singleton, contained in its original enclosure. Other moment kinds keep
// their own certificates and must still pass the ordinary accepts check.
fn contract_zero_timer_group(
    events: &mut [ScheduledEvent],
    model: &EventModel,
    work: Option<&crate::transition_source_plan::Work>,
) -> Result<Option<f64>, Error> {
    let mut time = None;
    for event in events.iter() {
        if let Some(w) = work {
            w.step()?;
        }
        if matches!(
            model.triggers[event.event].trigger,
            EventTrigger::Timer {
                time_tolerance: 0.0,
                ..
            }
        ) {
            let bounds = event.bounds();
            if bounds.lo != bounds.hi || !bounds.finite() || time.is_some_and(|t| t != bounds.lo) {
                return Err(unresolved(
                    "zero-tolerance timer group is not one exact point",
                ));
            }
            time = Some(bounds.lo);
        }
    }
    let Some(time) = time else { return Ok(None) };
    // Prove the whole group before changing its local certificates.
    for event in events.iter() {
        if let Some(w) = work {
            w.step()?;
        }
        if let Moment::Timer {
            bounds,
            start,
            period,
            index,
        } = event.moment
        {
            let clock = Clock {
                start,
                period,
                index,
            };
            let exact = if let Some(w) = work {
                clock.bounds_with_work(w)?
            } else {
                clock.bounds()
            }
            .ok_or_else(|| unresolved("fixed timer exact clock has no finite bounds"))?;
            if exact != I::point(time) || bounds.lo > time || bounds.hi < time {
                return Err(unresolved(
                    "fixed timer cannot share the zero-tolerance point",
                ));
            }
        }
    }
    for event in events.iter_mut() {
        if let Some(w) = work {
            w.step()?;
        }
        if let Moment::Timer { bounds, .. } = &mut event.moment {
            *bounds = I::point(time);
        }
    }
    Ok(Some(time))
}

#[cfg(test)]
fn order_fixed_timers(
    events: &mut [ScheduledEvent],
    model: &EventModel,
    stop: f64,
    next_lower: Option<f64>,
) -> Result<(), Error> {
    order_fixed_timers_with_work(events, model, stop, next_lower, None)
}
fn order_fixed_timers_with_work(
    events: &mut [ScheduledEvent],
    model: &EventModel,
    stop: f64,
    next_lower: Option<f64>,
    work: Option<&crate::transition_source_plan::Work>,
) -> Result<(), Error> {
    let work = work.or_else(|| crate::analytic_request::proof_owner(model).map(|o| o.work()));
    let mut uncertified = false;
    if let Some(w) = work {
        history_bookkeeping::sort(events, w, |a, b| {
            let order =
                history_bookkeeping::order_with_work(a, b, model, work)?.unwrap_or_else(|| {
                    uncertified = true;
                    std::cmp::Ordering::Equal
                });
            Ok(order.then(a.event.cmp(&b.event)))
        })?;
    } else {
        events.sort_by(|a, b| {
            let order = certified_order(a, b, model).unwrap_or_else(|| {
                uncertified = true;
                std::cmp::Ordering::Equal
            });
            order.then(a.event.cmp(&b.event))
        });
    }
    if uncertified {
        return Err(unresolved("cannot certify exact fixed timer order"));
    }
    let mut start = 0;
    let mut previous: Option<f64> = None;
    let mut groups = 0;
    while start < events.len() {
        if let Some(w) = work {
            w.debit(2, 0)?;
            w.step()?;
        }
        // The controller permits the initial batch and at most this many
        // subsequent causal batches. Enforce the same limit while building
        // the connected cluster, before repeated extension can outgrow it.
        // Equal-time leaves share a group and do not consume extra batches.
        if groups > CAUSAL_MICROEVENT_BUDGET {
            return Err(Error::new(
                "event_budget",
                format!("bounded exact event cluster exceeds {CAUSAL_MICROEVENT_BUDGET} subsequent microevents"),
            ));
        }
        groups += 1;
        let mut end = start + 1;
        while end < events.len() {
            if let Some(w) = work {
                w.step()?;
            }
            match history_bookkeeping::order_with_work(&events[start], &events[end], model, work)? {
                Some(std::cmp::Ordering::Equal) => end += 1,
                Some(_) => break,
                None => return Err(unresolved("cannot certify exact fixed timer group")),
            }
        }
        // All equal nominal times must share one representative, including
        // when their different arithmetic decompositions have different bounds.
        let zero_time = contract_zero_timer_group(&mut events[start..end], model, work)?;
        let mut time = zero_time.unwrap_or_else(|| {
            events[start..end]
                .iter()
                .map(|e| e.time.max(e.bounds().hi))
                .fold(0.0, f64::max)
        });
        if let Some(prior) = previous {
            if zero_time.is_some() && prior >= time {
                return Err(unresolved(
                    "prior event occupies a zero-tolerance timer time",
                ));
            }
            time = time.max(prior);
        }
        if !time.is_finite() {
            return Err(unresolved("ordered timer representative is not finite"));
        }
        if time > stop {
            return Err(unresolved("ordered timer representatives exceed stop"));
        }
        if next_lower.is_some_and(|limit| time >= limit) {
            return Err(unresolved(
                "ordered timer representatives reach the next event boundary",
            ));
        }
        for event in &mut events[start..end] {
            if !event.accepts_execution(time, model, work)? {
                return Err(unresolved(
                    "ordered timer representative exceeds its original time tolerance",
                ));
            }
            event.time = time;
            if previous.is_some() {
                event.fixed_predecessor = previous;
            }
        }
        previous = Some(time);
        start = end;
    }
    Ok(())
}

#[allow(clippy::too_many_arguments)] // Existing timer inputs plus the consumed-boundary certificate.
fn add_timer(
    events: &mut Vec<ScheduledEvent>,
    event: usize,
    trigger: &EventTrigger,
    config: &TransientInputs,
    model: &EventModel,
    states: Option<&[I]>,
    after: Option<f64>,
    boundary: Option<&TimerBoundary<'_>>,
    time_proofs: Option<&crate::transient::time_provenance::TimeProofs>,
    work: Option<&crate::transition_source_plan::Work>,
) -> Result<(), Error> {
    let history_work =
        work.or_else(|| crate::analytic_request::proof_owner(model).map(|o| o.work()));
    if let Some(w) = history_work {
        w.debit(2, 0)?;
        w.debit(2, 16)?;
    }
    let stop = config.stop;
    let forced_points = !config.strobetimes.is_empty();
    let zero_tolerance = matches!(
        trigger,
        EventTrigger::Timer {
            time_tolerance: 0.0,
            ..
        }
    );
    let (start, period, enabled, held) = match trigger {
        EventTrigger::Timer {
            start,
            period,
            enabled,
            ..
        } => (I::point(*start), I::point(*period), *enabled, false),
        EventTrigger::HeldTimer {
            start,
            period,
            enabled,
            ..
        } => {
            let states = states.ok_or_else(|| {
                Error::new("unsupported_timer", "dynamic timer requires a held epoch")
            })?;
            let value = |expression: &crate::ir::Expression| -> Result<I, Error> {
                if !model.program.procedures.is_empty() {
                    let value = crate::procedure::held_parameter(
                        expression,
                        &model.program,
                        states,
                        crate::real_expression::work(model),
                    )?;
                    if !value.finite() {
                        return Err(unresolved("nonfinite source timer parameter bounds"));
                    }
                    return Ok(value);
                }
                if let Some(w) = history_work {
                    let width = model
                        .program
                        .nodes
                        .len()
                        .saturating_add(model.program.states.len())
                        .saturating_add(model.program.operators.len())
                        .saturating_add(1);
                    w.debit(2, model.source_copy_items.saturating_mul(width) as u64)?;
                }
                let row = crate::affine_bounds::affine(expression, &model.program)?;
                let offset = model.program.nodes.len();
                let result = states
                    .iter()
                    .enumerate()
                    .fold(*row.last().unwrap(), |sum, (i, &state)| {
                        sum + row[offset + i] * state
                    });
                if !result.finite() {
                    return Err(unresolved("nonfinite dynamic timer parameter bounds"));
                }
                Ok(result)
            };
            let start = value(start)?;
            let period = value(period)?;
            let enabled = value(enabled)?
                .sign()
                .ok_or_else(|| unresolved("cannot certify dynamic timer enable"))?
                != 0;
            // A nonpositive period has only its single start occurrence.
            // A certified negative start is already past at every t >= 0;
            // later state writes still rebuild this held timer's calendar.
            if period.hi <= 0. && start.hi < 0. {
                return Ok(());
            }
            if start.lo < 0. || period.lo <= 0. && period.hi > 0. {
                return Err(unresolved(
                    "cannot certify dynamic timer start or period regime",
                ));
            }
            (start, period, enabled, true)
        }
        _ => return Ok(()),
    };
    let exact = if let EventTrigger::HeldTimer {
        start: expression,
        period,
        ..
    } = trigger
    {
        if matches!(period.as_ref(), Expression::Affine {constant,terms} if terms.is_empty() && constant.is_finite() && *constant<=0.)
        {
            time_proofs
                .and_then(|proofs| crate::transient::time_provenance::value(expression, proofs))
                .filter(|root| root.refine(start).is_some())
        } else {
            None
        }
    } else {
        None
    };
    if !enabled || start.lo > stop {
        return Ok(());
    }
    if period.lo > 0.0 {
        let remaining = EVENT_BUDGET - events.len();
        let excess = start + I::point(remaining as f64) * period;
        if excess.finite() && excess.hi <= stop {
            return Err(Error::new(
                "event_budget",
                "event calendar exceeds 1,000,000 events",
            ));
        }
    }
    let mut previous = None;
    for index in 0..=EVENT_BUDGET {
        if let Some(w) = history_work {
            w.debit(2, 24)?;
        }
        // index is bounded below 2^53, so its f64 conversion is exact. The
        // enclosure covers both product and sum. Choosing its upper endpoint
        // cannot fire early, including when the source omitted time_tol. The
        // clock remains start + index * period, never prior accepted time + T.
        // For a fixed zero budget, first prove whether this clock is outside
        // the requested domain. A later nonrepresentable clock must not reject
        // an otherwise valid finite prefix whose stop precedes that clock.
        let exact_clock = Clock {
            start: start.lo,
            period: period.lo,
            index,
        };
        if zero_tolerance
            && if let Some(w) = history_work {
                exact_clock.order_with_work(
                    Clock {
                        start: stop,
                        period: 0.,
                        index: 0,
                    },
                    w,
                )?
            } else {
                exact_clock.order(Clock {
                    start: stop,
                    period: 0.,
                    index: 0,
                })
            } == Some(std::cmp::Ordering::Greater)
        {
            break;
        }
        let mut bounds = if zero_tolerance {
            if (index as f64).mul_add(period.lo, start.lo) == f64::INFINITY {
                break;
            }
            (if let Some(w) = history_work {
                exact_clock.bounds_with_work(w)?
            } else {
                exact_clock.bounds()
            })
            .ok_or_else(|| unresolved("zero-tolerance timer has no finite exact bounds"))?
        } else if forced_points && start.lo == start.hi && period.lo == period.hi {
            // A forced solve point must not be crossed only because interval
            // arithmetic widened an otherwise exactly ordered source clock.
            // A held clock qualifies only when both current parameters are
            // exact singletons. Keep uncertain held-timer bounds unchanged.
            {
                let clock = Clock {
                    start: start.lo,
                    period: period.lo,
                    index,
                };
                if let Some(w) = history_work {
                    clock.bounds_with_work(w)?
                } else {
                    clock.bounds()
                }
            }
            .unwrap_or_else(|| start + I::point(index as f64) * period)
        } else if index == 0 {
            start
        } else {
            start + I::point(index as f64) * period
        };
        if !held && bounds.finite() && bounds.lo <= stop && bounds.hi > stop {
            // Padding from interval multiply/add must not make a fixed clock
            // ambiguous at stop. Prove the side before contracting its bounds:
            // an exact clock just above stop can have a lower bound equal to it.
            let clock = Clock {
                start: start.lo,
                period: period.lo,
                index,
            };
            let endpoint = Clock {
                start: stop,
                period: 0.,
                index: 0,
            };
            match if let Some(w) = history_work {
                clock.order_with_work(endpoint, w)?
            } else {
                clock.order(endpoint)
            } {
                Some(std::cmp::Ordering::Greater) => break,
                Some(_) => {
                    if let Some(tight) = if let Some(w) = history_work {
                        clock.bounds_with_work(w)?
                    } else {
                        clock.bounds()
                    } {
                        bounds = tight;
                    }
                }
                None => {}
            }
        }
        let time = bounds.hi;
        if (index as f64).mul_add(period.lo, start.lo) == f64::INFINITY {
            // The rounded lower-operand sum overflowing proves every possible
            // nominal time is beyond finite stop. An infinite interval upper
            // bound alone proves nothing and must reach the rejection below.
            break;
        }
        if !bounds.finite() {
            return Err(unresolved("nonfinite timer nominal-time bounds"));
        }
        if bounds.lo > stop {
            break;
        }
        if bounds.hi > stop {
            return Err(unresolved(
                "cannot certify timer nominal time relative to stop",
            ));
        }
        if zero_tolerance && bounds.lo != bounds.hi {
            return Err(unresolved("zero-tolerance timer time is not representable"));
        }
        let mut physical_after = false;
        if held {
            if let Some(boundary) = boundary {
                let clock = (start.lo == start.hi && period.lo == period.hi).then_some(Clock {
                    start: start.lo,
                    period: period.lo,
                    index,
                });
                if boundary.already_past_or_consumed_with_work(
                    event,
                    bounds,
                    clock,
                    exact.as_ref(),
                    history_work,
                )? {
                    if period.hi <= 0. {
                        break;
                    }
                    continue;
                }
                let candidate = Moment::HeldTimer {
                    bounds,
                    index,
                    clock,
                    exact: exact
                        .as_ref()
                        .map(|root| {
                            root.clone_with_work(
                                history_work.unwrap_or_else(|| crate::real_expression::work(model)),
                            )
                        })
                        .transpose()?,
                };
                physical_after = boundary.proves_after(&candidate, model, history_work)?;
                if !physical_after && after.is_some_and(|time| bounds.lo <= time) {
                    return Err(unresolved(
                        "future held timer cannot be ordered after the accepted representative",
                    ));
                }
            }
        }
        if let Some(after) = after.filter(|_| !physical_after) {
            if bounds.hi <= after {
                if period.hi <= 0. {
                    break;
                }
                continue;
            }
            if bounds.lo <= after {
                return Err(unresolved(
                    "dynamic timer window overlaps the accepted boundary",
                ));
            }
        }
        if previous.is_some_and(|last| time <= last) {
            return Err(unresolved("timer period cannot advance representable time"));
        }
        if events.len() == EVENT_BUDGET {
            return Err(Error::new(
                "event_budget",
                "event calendar exceeds 1,000,000 events",
            ));
        }
        let event = ScheduledEvent {
            fixed_predecessor: None,
            occurrence: None,
            time,
            event,
            moment: if held {
                Moment::HeldTimer {
                    exact: exact.clone().filter(|root| root.refine(bounds).is_some()),
                    bounds,
                    index,
                    clock: (start.lo == start.hi && period.lo == period.hi).then_some(Clock {
                        start: start.lo,
                        period: period.lo,
                        index,
                    }),
                }
            } else {
                Moment::Timer {
                    bounds,
                    start: start.lo,
                    period: period.lo,
                    index,
                }
            },
        };
        if let Some(w) = history_work {
            crate::history_storage::push_vec(events, event, w)?
        } else {
            events.push(event)
        }
        previous = Some(time);
        if period.hi <= 0.0 || bounds == I::point(stop) {
            break;
        }
    }
    Ok(())
}

pub(crate) fn schedule(
    model: &EventModel,
    trajectory: &Trajectory,
    operators: &Operators,
) -> Result<Vec<ScheduledEvent>, Error> {
    schedule_with_history(model, trajectory, Some(operators), None, CalendarScope::All)
}

// Build the complete calendar first when every guard is independent of
// continuous history. No provisional nonlinear future is needed for timers
// or affine source guards.
pub(crate) fn independent_schedule(
    model: &EventModel,
    trajectory: &Trajectory,
) -> Result<Vec<ScheduledEvent>, Error> {
    schedule_with_history(model, trajectory, None, None, CalendarScope::All)
}

pub(crate) fn schedule_held(
    model: &EventModel,
    trajectory: &Trajectory,
    states: &[I],
) -> Result<Vec<ScheduledEvent>, Error> {
    schedule_held_with_time_proofs(model, trajectory, states, None)
}

pub(crate) fn schedule_held_with_time_proofs(
    model: &EventModel,
    trajectory: &Trajectory,
    states: &[I],
    time_proofs: Option<&crate::transient::time_provenance::TimeProofs>,
) -> Result<Vec<ScheduledEvent>, Error> {
    schedule_with_history(
        model,
        trajectory,
        None,
        Some(HeldCalendar {
            work: None,
            time_proofs,
            states,
            after: None,
            changed: &[],
            pending: &[],
            boundary: None,
        }),
        CalendarScope::All,
    )
}

pub(crate) fn schedule_held_charged(
    model: &EventModel,
    trajectory: &Trajectory,
    states: &[I],
    work: &crate::transition_source_plan::Work,
) -> Result<Vec<ScheduledEvent>, Error> {
    schedule_with_history(
        model,
        trajectory,
        None,
        Some(HeldCalendar {
            work: Some(work),
            time_proofs: None,
            states,
            after: None,
            changed: &[],
            pending: &[],
            boundary: None,
        }),
        CalendarScope::All,
    )
}

// Keep the original Work owner beside the old pending/consumed calendars so
// rescheduling cannot reset the allowance or lose occurrence identity.
#[allow(clippy::too_many_arguments)]
pub(crate) fn reschedule_held_charged(
    model: &EventModel,
    trajectory: &Trajectory,
    states: &[I],
    after: f64,
    changed: &[bool],
    pending: &[ScheduledEvent],
    consumed: &[ScheduledEvent],
    work: &crate::transition_source_plan::Work,
) -> Result<Vec<ScheduledEvent>, Error> {
    let boundary = TimerBoundary::new_with_work(model, after, consumed, Some(work))?;
    schedule_with_history(
        model,
        trajectory,
        None,
        Some(HeldCalendar {
            work: Some(work),
            time_proofs: None,
            states,
            after: Some(after),
            changed,
            pending,
            boundary: Some(&boundary),
        }),
        CalendarScope::All,
    )
}

#[allow(dead_code)] // Retain the existing no-provenance entry for compatibility.
pub(crate) fn reschedule_held(
    model: &EventModel,
    trajectory: &Trajectory,
    states: &[I],
    after: f64,
    changed: &[bool],
    pending: &[ScheduledEvent],
    consumed: &[ScheduledEvent],
) -> Result<Vec<ScheduledEvent>, Error> {
    reschedule_held_with_time_proofs(
        model, trajectory, states, after, changed, pending, consumed, None,
    )
}

#[allow(clippy::too_many_arguments)] // Existing calendar inputs plus independent optional proof.
pub(crate) fn reschedule_held_with_time_proofs(
    model: &EventModel,
    trajectory: &Trajectory,
    states: &[I],
    after: f64,
    changed: &[bool],
    pending: &[ScheduledEvent],
    consumed: &[ScheduledEvent],
    time_proofs: Option<&crate::transient::time_provenance::TimeProofs>,
) -> Result<Vec<ScheduledEvent>, Error> {
    let boundary = TimerBoundary::new(model, after, consumed)?;
    schedule_with_history(
        model,
        trajectory,
        None,
        Some(HeldCalendar {
            work: None,
            time_proofs,
            states,
            after: Some(after),
            changed,
            pending,
            boundary: Some(&boundary),
        }),
        CalendarScope::All,
    )
}

// Calendar passes share the same ordering and tolerance checks. Independent
// events first bound the immutable future supplied to history-root isolation.
enum CalendarScope<'a> {
    All,
    Independent,
    History {
        until: f64,
        consumed: &'a [(usize, i8)],
    },
}
impl CalendarScope<'_> {
    fn includes(&self, model: &EventModel, index: usize) -> bool {
        match self {
            Self::All => true,
            Self::Independent => model.guard_operators[index].is_empty(),
            Self::History { .. } => !model.guard_operators[index].is_empty(),
        }
    }
}

pub(crate) fn independent_epoch(
    model: &EventModel,
    trajectory: &Trajectory,
    states: &[I],
    after: Option<f64>,
) -> Result<Vec<ScheduledEvent>, Error> {
    independent_epoch_with_time_proofs(model, trajectory, states, after, None)
}

pub(crate) fn independent_epoch_with_time_proofs(
    model: &EventModel,
    trajectory: &Trajectory,
    states: &[I],
    after: Option<f64>,
    time_proofs: Option<&crate::transient::time_provenance::TimeProofs>,
) -> Result<Vec<ScheduledEvent>, Error> {
    if let Some(w) = crate::analytic_request::proof_owner(model).map(|o| o.work()) {
        w.debit(2, 0)?;
        w.debit(2, model.triggers.len() as u64)?;
    }
    let changed = vec![true; model.triggers.len()];
    schedule_with_history(
        model,
        trajectory,
        None,
        Some(HeldCalendar {
            work: None,
            time_proofs,
            states,
            after,
            changed: &changed,
            pending: &[],
            boundary: None,
        }),
        CalendarScope::Independent,
    )
}

pub(crate) struct HistoryEpoch<'a> {
    pub(crate) states: &'a [I],
    pub(crate) after: Option<f64>,
    pub(crate) until: f64,
    pub(crate) consumed: &'a [(usize, i8)],
    pub(crate) pending: &'a [ScheduledEvent],
}

#[allow(dead_code)] // Retain the existing no-provenance entry for compatibility.
pub(crate) fn reschedule_independent(
    model: &EventModel,
    trajectory: &Trajectory,
    states: &[I],
    after: f64,
    changed: &[bool],
    pending: &[ScheduledEvent],
    consumed: &[ScheduledEvent],
) -> Result<Vec<ScheduledEvent>, Error> {
    reschedule_independent_with_time_proofs(
        model, trajectory, states, after, changed, pending, consumed, None,
    )
}

#[allow(clippy::too_many_arguments)] // Existing calendar inputs plus independent optional proof.
pub(crate) fn reschedule_independent_with_time_proofs(
    model: &EventModel,
    trajectory: &Trajectory,
    states: &[I],
    after: f64,
    changed: &[bool],
    pending: &[ScheduledEvent],
    consumed: &[ScheduledEvent],
    time_proofs: Option<&crate::transient::time_provenance::TimeProofs>,
) -> Result<Vec<ScheduledEvent>, Error> {
    let boundary = TimerBoundary::new(model, after, consumed)?;
    schedule_with_history(
        model,
        trajectory,
        None,
        Some(HeldCalendar {
            work: None,
            time_proofs,
            states,
            after: Some(after),
            changed,
            pending,
            boundary: Some(&boundary),
        }),
        CalendarScope::Independent,
    )
}

pub(crate) fn history_epoch(
    model: &EventModel,
    trajectory: &Trajectory,
    operators: &Operators,
    epoch: HistoryEpoch<'_>,
) -> Result<Vec<ScheduledEvent>, Error> {
    history_epoch_with_time_proofs(model, trajectory, operators, epoch, None)
}

pub(crate) fn history_epoch_with_time_proofs(
    model: &EventModel,
    trajectory: &Trajectory,
    operators: &Operators,
    epoch: HistoryEpoch<'_>,
    time_proofs: Option<&crate::transient::time_provenance::TimeProofs>,
) -> Result<Vec<ScheduledEvent>, Error> {
    history_epoch_with_time_proofs_and_boundary(
        model,
        trajectory,
        operators,
        epoch,
        time_proofs,
        None,
    )
}

pub(crate) fn history_epoch_with_time_proofs_and_boundary(
    model: &EventModel,
    trajectory: &Trajectory,
    operators: &Operators,
    epoch: HistoryEpoch<'_>,
    time_proofs: Option<&crate::transient::time_provenance::TimeProofs>,
    batch: Option<&[ScheduledEvent]>,
) -> Result<Vec<ScheduledEvent>, Error> {
    let boundary = match (epoch.after, batch) {
        (Some(after), Some(batch)) => Some(TimerBoundary::new_with_work(
            model,
            after,
            batch,
            Some(crate::real_expression::work(model)),
        )?),
        (_, None) => None,
        (None, Some(_)) => {
            return Err(unresolved(
                "physical calendar boundary requires its accepted observation",
            ))
        }
    };
    let changed: Vec<_> = model
        .guard_operators
        .iter()
        .map(|ops| !ops.is_empty())
        .collect();
    schedule_with_history(
        model,
        trajectory,
        Some(operators),
        Some(HeldCalendar {
            work: None,
            time_proofs,
            states: epoch.states,
            after: epoch.after,
            changed: &changed,
            pending: epoch.pending,
            boundary: boundary.as_ref(),
        }),
        CalendarScope::History {
            until: epoch.until,
            consumed: epoch.consumed,
        },
    )
}

/// Evidence from this candidate batch, never from a body ID or an older event.
/// A changed held clock cannot silently create an unconsumed current occurrence.
struct TimerBoundary<'a> {
    observation: I,
    consumed: std::collections::BTreeMap<usize, &'a ScheduledEvent>,
    common_moment: Option<&'a Moment>,
}

impl<'a> TimerBoundary<'a> {
    fn new(model: &EventModel, after: f64, batch: &'a [ScheduledEvent]) -> Result<Self, Error> {
        Self::new_with_work(model, after, batch, None)
    }
    fn new_with_work(
        model: &EventModel,
        after: f64,
        batch: &'a [ScheduledEvent],
        work: Option<&crate::transition_source_plan::Work>,
    ) -> Result<Self, Error> {
        if let Some(w) = work {
            w.debit(2, 0)?;
        }
        if !after.is_finite() || batch.is_empty() {
            return Err(unresolved(
                "held timer rescheduling requires the current event batch",
            ));
        }
        let mut observation = I::point(after);
        let mut consumed = std::collections::BTreeMap::new();
        for event in batch {
            if let Some(w) = work {
                w.debit(2, (16 + usize::BITS) as u64)?;
            }
            if event.time != after
                || event.event >= model.triggers.len()
                || !event.bounds().finite()
                || event.bounds().lo > event.bounds().hi
            {
                return Err(unresolved(
                    "held timer boundary does not identify the current batch",
                ));
            }
            observation = observation.hull(event.bounds());
            if matches!(
                model.triggers[event.event].trigger,
                EventTrigger::HeldTimer { .. }
            ) && (!matches!(event.moment, Moment::HeldTimer { .. })
                || consumed.insert(event.event, event).is_some())
            {
                return Err(unresolved(
                    "held timer consumption requires a unique timer leaf",
                ));
            }
        }
        let first = &batch[0].moment;
        let mut common = true;
        // The first borrowed occurrence is identical to itself. Its root need
        // not have a global rational form to establish that local identity.
        // Other occurrences still require the original common-root proof.
        for event in batch.iter().skip(1) {
            let owner = work.unwrap_or_else(|| crate::real_expression::work(model));
            owner.step()?;
            // Shared isolation already certified these leaves as one physical
            // occurrence in this immutable calendar epoch. Boxes are not keys.
            if batch[0]
                .occurrence
                .as_ref()
                .zip(event.occurrence.as_ref())
                .is_some_and(|(a, b)| Arc::ptr_eq(a, b))
            {
                continue;
            }
            let order = if let Some(w) = work {
                first.exact_order_with_work(&event.moment, w)?
            } else {
                first.exact_order(&event.moment)
            };
            if order != Some(std::cmp::Ordering::Equal)
                && !(first.bounds().lo == first.bounds().hi && first.bounds() == event.bounds())
            {
                common = false;
                break;
            }
        }
        let common_moment = common.then_some(first);
        Ok(Self {
            observation,
            consumed,
            common_moment,
        })
    }

    fn proves_after(
        &self,
        moment: &Moment,
        model: &EventModel,
        work: Option<&crate::transition_source_plan::Work>,
    ) -> Result<bool, Error> {
        let Some(prior) = self.common_moment else {
            return Ok(false);
        };
        let owner = work.unwrap_or_else(|| crate::real_expression::work(model));
        owner.step()?;
        // Disjoint certified physical enclosures already prove strict order.
        // Only overlapping boxes need the exact clock/root comparison; equal
        // display values never establish equality or justify this fast path.
        let current = moment.bounds();
        let previous = prior.bounds();
        if current.lo > previous.hi {
            return Ok(true);
        }
        if current.hi < previous.lo {
            return Ok(false);
        }
        Ok(moment.exact_order_with_work(
            prior,
            work.unwrap_or_else(|| crate::real_expression::work(model)),
        )? == Some(std::cmp::Ordering::Greater))
    }

    #[cfg(test)]
    fn already_past_or_consumed(
        &self,
        leaf: usize,
        bounds: I,
        clock: Option<Clock>,
        exact: Option<&crate::exact_source::RootTime>,
    ) -> Result<bool, Error> {
        self.already_past_or_consumed_with_work(leaf, bounds, clock, exact, None)
    }
    fn already_past_or_consumed_with_work(
        &self,
        leaf: usize,
        bounds: I,
        clock: Option<Clock>,
        exact: Option<&crate::exact_source::RootTime>,
        work: Option<&crate::transition_source_plan::Work>,
    ) -> Result<bool, Error> {
        if let Some(w) = work {
            w.debit(2, (16 + usize::BITS) as u64)?;
        }
        let compare = |a: &Moment, b: &Moment| {
            if let Some(w) = work {
                a.exact_order_with_work(b, w)
            } else {
                Ok(a.exact_order(b))
            }
        };
        if bounds.hi < self.observation.lo {
            return Ok(true);
        }
        if bounds.lo > self.observation.hi {
            return Ok(false);
        }
        let candidate = Moment::HeldTimer {
            bounds,
            index: clock.map_or(0, |c| c.index),
            clock,
            exact: match (exact, work) {
                (Some(root), Some(w)) => Some(root.clone_with_work(w)?),
                _ => exact.cloned(),
            },
        };
        if let Some(old) = self.common_moment {
            if exact.is_some() {
                match compare(&candidate, old)? {
                    Some(std::cmp::Ordering::Less) => return Ok(true),
                    Some(std::cmp::Ordering::Greater) => return Ok(false),
                    _ => {}
                }
            }
        }
        if let (Some(clock), Some(old)) = (clock, self.common_moment) {
            let candidate = Moment::HeldTimer {
                exact: match (exact, work) {
                    (Some(root), Some(w)) => Some(root.clone_with_work(w)?),
                    _ => exact.cloned(),
                },
                bounds,
                index: clock.index,
                clock: Some(clock),
            };
            match compare(&candidate, old)? {
                Some(std::cmp::Ordering::Less) => return Ok(true),
                Some(std::cmp::Ordering::Greater) => return Ok(false),
                _ => {}
            }
        }
        if let Some(old) = self.consumed.get(&leaf) {
            if exact.is_some()
                && compare(&candidate, &old.moment)? == Some(std::cmp::Ordering::Equal)
            {
                return Ok(true);
            }
            let same_clock = match (clock, old.clock()) {
                (Some(new), Some(old)) => {
                    if let Some(w) = work {
                        new.order_with_work(old, w)? == Some(std::cmp::Ordering::Equal)
                    } else {
                        new.order(old) == Some(std::cmp::Ordering::Equal)
                    }
                }
                _ => bounds.lo == bounds.hi && bounds == old.bounds(),
            };
            if same_clock {
                return Ok(true);
            }
        }
        if bounds.lo != bounds.hi {
            return Err(unresolved(
                "dynamic timer window overlaps the accepted boundary",
            ));
        }
        Err(unresolved(
            "new unconsumed held timer at current event boundary requires a same-time closure",
        ))
    }
}

struct HeldCalendar<'a> {
    work: Option<&'a crate::transition_source_plan::Work>,
    time_proofs: Option<&'a crate::transient::time_provenance::TimeProofs>,
    states: &'a [I],
    after: Option<f64>,
    changed: &'a [bool],
    pending: &'a [ScheduledEvent],
    boundary: Option<&'a TimerBoundary<'a>>,
}

impl HeldCalendar<'_> {
    // Prove the entire retained prefix, including equal-time groups. A third
    // overlapping clock is linked to the second, not directly to `after`.
    // New/changed moments and any intervening non-fixed event break this proof.
    fn retained_fixed_prefix(&self, after: f64) -> Vec<f64> {
        let pending: Vec<_> = self
            .pending
            .iter()
            .filter(|event| !self.changed[event.event])
            .collect();
        let mut anchor = after;
        let mut times = Vec::new();
        let mut start = 0;
        while start < pending.len() {
            let time = pending[start].time;
            let mut end = start + 1;
            while end < pending.len() && pending[end].time == time {
                end += 1;
            }
            if time <= anchor
                || !pending[start..end].iter().all(|event| {
                    !self.changed[event.event]
                        && (event.moment.clock().is_some()
                            || matches!(event.moment, Moment::Cross(_) | Moment::Anchored { .. }))
                        && event.fixed_predecessor == Some(anchor)
                })
            {
                break;
            }
            times.push(time);
            anchor = time;
            start = end;
        }
        times
    }
}

fn schedule_with_history(
    model: &EventModel,
    trajectory: &Trajectory,
    operators: Option<&Operators>,
    held: Option<HeldCalendar<'_>>,
    scope: CalendarScope<'_>,
) -> Result<Vec<ScheduledEvent>, Error> {
    let history_work = held
        .as_ref()
        .and_then(|h| h.work)
        .or_else(|| crate::analytic_request::proof_owner(model).map(|o| o.work()));
    if let Some(w) = history_work {
        w.debit(2, 0)?;
    }
    if held.as_ref().is_some_and(|h| h.work.is_some()) {
        for leaf in &model.triggers {
            history_work.unwrap().step()?;
            if !matches!(
                leaf.trigger,
                EventTrigger::InitialStep { .. }
                    | EventTrigger::Timer { .. }
                    | EventTrigger::HeldTimer { .. }
            ) {
                return Err(unresolved(
                    "cold timer proof requires a timer-only calendar",
                ));
            }
        }
    }
    let _timing = crate::diagnostics::span("event.calendar");
    let mut shared_roots = Vec::new();

    let mut events = if let Some(w) = history_work {
        let mut events = Vec::new();
        if let Some(held) = &held {
            for event in held.pending {
                w.step()?;
                if !held.changed[event.event] {
                    let copied = if held.work.is_some() {
                        event.clone_cold_timer(w)?
                    } else {
                        event.clone_history(w)?
                    };
                    crate::history_storage::push_vec(&mut events, copied, w)?;
                }
            }
        }
        events
    } else {
        held.as_ref().map_or_else(Vec::new, |h| {
            h.pending
                .iter()
                .filter(|e| !h.changed[e.event])
                .cloned()
                .collect()
        })
    };
    // A timer-only network needs no guard trajectory certification.
    let bounds = if model.guards.iter().any(Option::is_some) {
        Some(GuardBounds::for_model(
            model,
            held.as_ref().map(|h| h.states),
        )?)
    } else {
        None
    };
    if let Some(bounds) = &bounds {
        // Each source-selected branch is checked at its actual input value.
        for &time in &trajectory.knots {
            let circuit = model.circuit_at(
                &model.initial(),
                &vec![0.; model.program.operators.len()],
                &crate::event_value_proof::history::input_bounds(model, trajectory, time)?,
            )?;
            circuit.solve(&crate::event_value_proof::history::inputs(
                model, trajectory, time,
            )?)?;
        }
        for (index, leaf) in model.triggers.iter().enumerate() {
            if let Some(w) = history_work {
                w.step()?;
            }
            if !scope.includes(model, index) || model.dynamic_guards[index] {
                continue;
            }
            if held
                .as_ref()
                .is_some_and(|h| h.after.is_some() && !h.changed[index])
            {
                continue;
            }
            let EventTrigger::Cross {
                guard, direction, ..
            } = &leaf.trigger
            else {
                continue;
            };
            // A state-independent guard is affine on the union of the knots
            // of its nonzero input coefficients. Unrelated knots must not
            // introduce artificial near-boundary root uncertainty.
            let active_inputs = if let Some(w) = history_work {
                bounds.active_inputs_history(index, w)?
            } else {
                bounds.active_inputs(index)
            };
            let input_nodes = if let Some(w) = history_work {
                let nodes = crate::analytic_request::proof_owner(model)
                    .expect("paid calendar role")
                    .input_nodes();
                w.debit(2, nodes.len() as u64)?;
                nodes.to_vec()
            } else {
                model
                    .driven
                    .iter()
                    .map(|name| {
                        model
                            .program
                            .nodes
                            .iter()
                            .position(|node| node == name)
                            .unwrap()
                    })
                    .collect::<Vec<_>>()
            };
            let projected_guard = if let Some(w) = history_work {
                bounds.exact_input_expression_history(index, w)?
            } else {
                bounds.exact_input_expression(index)
            };
            let physical = if let Some(w) = history_work {
                trajectory.shaped_roots_history(
                    guard,
                    projected_guard.as_ref(),
                    &input_nodes,
                    &active_inputs,
                    *direction,
                    held.as_ref().and_then(|h| h.after),
                    w,
                )?
            } else {
                trajectory.shaped_roots(
                    guard,
                    projected_guard.as_ref(),
                    &input_nodes,
                    &active_inputs,
                    *direction,
                    held.as_ref().and_then(|h| h.after),
                )?
            };
            let mut knots = if let Some(w) = history_work {
                trajectory.history_input_knots(&active_inputs, w)?
            } else {
                trajectory.input_knots(&active_inputs)
            };
            if let Some(after) = held.as_ref().and_then(|h| h.after) {
                knots.retain(|t| *t > after);
                knots.insert(0, after);
            }
            if knots.len() < 2 {
                continue;
            }
            let mut values = Vec::new();
            for &time in &knots {
                let inputs =
                    crate::event_value_proof::history::input_bounds(model, trajectory, time)?;
                let value = if let Some(w) = history_work {
                    bounds.value_history(index, &inputs, w)?
                } else {
                    bounds.values(&inputs)[index]
                };
                if let Some(w) = history_work {
                    crate::history_storage::push_vec(&mut values, value, w)?
                } else {
                    values.push(value)
                }
            }
            let roots = match physical {
                Some(roots) => roots,
                None => {
                    if let Some(w) = history_work {
                        trajectory.roots_history(&knots, &values, *direction, w)?
                    } else {
                        trajectory.roots(&knots, &values, *direction)?
                    }
                }
            };
            let source_curve = if roots.is_empty() {
                None
            } else if let Some(w) = history_work {
                history_bookkeeping::curve(
                    trajectory,
                    guard,
                    projected_guard.as_ref(),
                    &input_nodes,
                    w,
                )?
            } else {
                let input_nodes = model
                    .driven
                    .iter()
                    .map(|name| {
                        model
                            .program
                            .nodes
                            .iter()
                            .position(|node| node == name)
                            .unwrap()
                    })
                    .collect::<Vec<_>>();
                trajectory
                    .original_guard_curve(guard, &input_nodes)
                    .or_else(|| {
                        // GuardBounds supplies this projection only for exact
                        // point coefficients over original input nodes. Keep
                        // the same source-time certificate for ordinary PWL
                        // roots as for shaped roots; root_in still checks that
                        // it identifies the discovered physical root.
                        trajectory.original_guard_curve(projected_guard.as_ref()?, &input_nodes)
                    })
            };
            for root in roots {
                let root = if let Some(w) = history_work {
                    root.with_source_time_history(source_curve.as_ref(), w)?
                } else {
                    root.with_source_time(source_curve.as_ref())
                };
                if events.len() == EVENT_BUDGET {
                    return Err(Error::new(
                        "event_budget",
                        "event calendar exceeds 1,000,000 events",
                    ));
                }
                let event = ScheduledEvent {
                    fixed_predecessor: None,
                    occurrence: None,
                    time: root.bounds.hi,
                    event: index,
                    moment: Moment::Cross(root),
                };
                if let Some(w) = history_work {
                    crate::history_storage::push_vec(&mut events, event, w)?
                } else {
                    events.push(event)
                }
            }
        }
    }
    if model
        .dynamic_guards
        .iter()
        .enumerate()
        .any(|(i, &g)| g && scope.includes(model, i))
    {
        let guards = if let Some(h) = &held {
            crate::guard_trajectory::GuardTrajectory::new_held(
                model,
                trajectory,
                operators,
                Some(h.states),
            )?
        } else {
            let operators = operators.ok_or_else(|| {
                Error::new(
                    "unsupported_cross",
                    "history-dependent calendar requires a certified trajectory",
                )
            })?;
            crate::guard_trajectory::GuardTrajectory::new(model, trajectory, operators)?
        };
        for (index, leaf) in model.triggers.iter().enumerate() {
            if let Some(w) = history_work {
                w.step()?;
            }
            if !scope.includes(model, index) || !model.dynamic_guards[index] {
                continue;
            }
            if held
                .as_ref()
                .is_some_and(|h| h.after.is_some() && !h.changed[index])
            {
                continue;
            }
            let EventTrigger::Cross {
                guard,
                direction,
                time_tolerance,
                expression_tolerance,
            } = &leaf.trigger
            else {
                unreachable!()
            };
            let origin = &model.program.events[leaf.event].origin;
            if let Some((anchor, mut start)) = operators.and_then(Operators::local_epoch) {
                let CalendarScope::History { until, consumed } = &scope else {
                    return Err(unresolved(
                        "local closure requires a bounded history calendar",
                    ));
                };
                let end = anchor
                    .delta(*until)
                    .ok_or_else(|| {
                        unresolved("local event coverage exceeds exact time arithmetic")
                    })?
                    .hi;
                if end <= start {
                    continue;
                }
                let precision = (*time_tolerance).min((end - start) * f64::EPSILON * 8.);
                if let Some((_, incoming)) = consumed.iter().find(|(event, _)| *event == index) {
                    start = crate::dynamic_roots::depart_consumed(
                        start,
                        end,
                        &mut |t| Ok(guards.local_range_impl(guard, t, &origin.instance)?.0),
                        &mut |t| Ok(guards.local_range_impl(guard, t, &origin.instance)?.1),
                        precision,
                        (*incoming, *direction),
                    )?;
                }
                let roots = shared_isolation(
                    &mut shared_roots,
                    index,
                    true,
                    [start, end],
                    model,
                    Some(crate::real_expression::work(model)),
                    || {
                        crate::dynamic_roots::isolate_history(
                            start,
                            end,
                            &mut |t| Ok(guards.local_range_impl(guard, t, &origin.instance)?.0),
                            &mut |t| Ok(guards.local_range_impl(guard, t, &origin.instance)?.1),
                            *direction,
                            precision,
                            *expression_tolerance,
                        )
                    },
                )?;
                for (root, occurrence) in roots {
                    if events.len() >= EVENT_BUDGET {
                        return Err(Error::new(
                            "event_budget",
                            "local causal calendar exceeds event budget",
                        ));
                    }
                    let clock = I::point(anchor.start)
                        + I::point(anchor.period) * I::point(anchor.index as f64);
                    let bounds = clock + root.bounds;
                    let moment = Moment::Anchored {
                        anchor,
                        delta: root.bounds,
                        derivative: root.derivative,
                        end: trajectory.config.stop,
                        bounds,
                        history: operators.unwrap().history_certificate().unwrap(),
                        exact: guards
                            .exact_affine_root(guard, root.bounds, true)
                            .and_then(|r| r.shifted_clock(anchor)),
                    };
                    let mut time = moment.bounds().hi;
                    if let Some(after) = held.as_ref().and_then(|h| h.after) {
                        time = time.max(after.next_up());
                    }
                    if !moment.accepts(time, &leaf.trigger) {
                        let local = anchor
                            .delta(time)
                            .ok_or_else(|| unresolved("local representative is uncertifiable"))?;
                        let minimum = (local - root.bounds).lo;
                        let forced_after = held
                            .as_ref()
                            .and_then(|h| h.after)
                            .is_some_and(|after| time == after.next_up());
                        let previous_is_before = anchor
                            .delta(time.next_down())
                            .is_some_and(|d| d.hi < root.bounds.lo);
                        if minimum > *time_tolerance && (forced_after || previous_is_before) {
                            return Err(unresolved("cross_ttol_unrepresentable: no strictly ordered binary64 representative satisfies the original cross time tolerance"));
                        }
                        return Err(unresolved("local causal root has no representative within its original tolerances"));
                    }
                    if events
                        .iter()
                        .filter(|event| matches!(event.moment, Moment::Anchored { .. }))
                        .count()
                        >= CAUSAL_MICROEVENT_BUDGET
                    {
                        return Err(Error::new(
                            "event_budget",
                            "bounded causal candidate calendar exceeds 64 microevents",
                        ));
                    }
                    events.push(ScheduledEvent {
                        fixed_predecessor: None,
                        occurrence: Some(occurrence),
                        time,
                        event: index,
                        moment,
                    });
                }
                continue;
            }
            let mut knots = trajectory.knots.clone();
            if let Some(after) = held.as_ref().and_then(|h| h.after) {
                knots.retain(|t| *t > after);
                knots.insert(0, after);
            }
            if let CalendarScope::History { until, consumed } = &scope {
                let start = held.as_ref().and_then(|h| h.after).unwrap_or(0.0);
                knots.retain(|&t| t <= *until);
                if *until > start && knots.last().copied() != Some(*until) {
                    knots.push(*until);
                }
                if let Some((_, incoming)) = consumed
                    .iter()
                    .find(|(event, _)| *event == index)
                    .filter(|_| *until > start)
                {
                    let departed = crate::dynamic_roots::depart_consumed(
                        start,
                        *until,
                        &mut |t| Ok(guards.range(guard, t, &origin.instance)?.0),
                        &mut |t| Ok(guards.range(guard, t, &origin.instance)?.1),
                        *time_tolerance,
                        (*incoming, *direction),
                    )?;
                    knots.retain(|&t| t > departed);
                    knots.insert(0, departed);
                }
            }
            for segment in knots.windows(2) {
                let roots = shared_isolation(
                    &mut shared_roots,
                    index,
                    false,
                    [segment[0], segment[1]],
                    model,
                    Some(crate::real_expression::work(model)),
                    || {
                        Ok(if !matches!(scope, CalendarScope::All) {
                            crate::dynamic_roots::isolate_history(
                                segment[0],
                                segment[1],
                                &mut |t| Ok(guards.range(guard, t, &origin.instance)?.0),
                                &mut |t| Ok(guards.range(guard, t, &origin.instance)?.1),
                                *direction,
                                *time_tolerance,
                                *expression_tolerance,
                            )?
                        } else {
                            crate::dynamic_roots::isolate(
                                segment[0],
                                segment[1],
                                &mut |t| Ok(guards.range(guard, t, &origin.instance)?.0),
                                &mut |t| Ok(guards.range(guard, t, &origin.instance)?.1),
                                *direction,
                                *time_tolerance,
                                *expression_tolerance,
                            )?
                        })
                    },
                )?;
                for (root, occurrence) in roots {
                    if events.len() >= EVENT_BUDGET {
                        return Err(Error::new(
                            "event_budget",
                            "dynamic event calendar exceeds budget",
                        ));
                    }
                    let moment = Moment::Dynamic {
                        history: operators.and_then(Operators::history_certificate),
                        exact: guards.exact_affine_root(guard, root.bounds, false),
                        bounds: root.bounds,
                        derivative: root.derivative,
                        end: segment[1],
                    };
                    let time = moment.bounds().hi;
                    if moment.exact_history_root().is_some() && !moment.accepts(time, &leaf.trigger)
                    {
                        return Err(unresolved(
                            "refined history root exceeds original tolerances",
                        ));
                    }
                    events.push(ScheduledEvent {
                        fixed_predecessor: None,
                        occurrence: Some(occurrence),
                        time,
                        event: index,
                        moment,
                    });
                }
            }
        }
    }
    for (index, leaf) in model.triggers.iter().enumerate() {
        if let Some(w) = history_work {
            w.step()?;
        }
        if !scope.includes(model, index) {
            continue;
        }
        if held
            .as_ref()
            .is_some_and(|h| h.after.is_some() && !h.changed[index])
        {
            continue;
        }
        add_timer(
            &mut events,
            index,
            &leaf.trigger,
            &trajectory.config,
            model,
            held.as_ref().map(|h| h.states),
            held.as_ref().and_then(|h| h.after),
            held.as_ref().and_then(|h| h.boundary),
            held.as_ref().and_then(|h| h.time_proofs),
            history_work,
        )?;
    }
    if let Some(after) = held.as_ref().and_then(|h| h.after) {
        if let Some(w) = history_work {
            w.debit(
                2,
                (held.as_ref().unwrap().pending.len() as u64).saturating_mul(16),
            )?;
        }
        let retained = held.as_ref().unwrap().retained_fixed_prefix(after);
        if let Some(w) = history_work {
            for event in &events {
                w.step()?;
                let physical_after = held
                    .as_ref()
                    .and_then(|h| h.boundary)
                    .map(|b| b.proves_after(&event.moment, model, Some(w)))
                    .transpose()?
                    .unwrap_or(false);
                let proven_later = physical_after
                    || if event.time > after {
                        let root = event.exact_root_with_work(w)?;
                        let mut paid = crate::exact_source::history_paid::Paid::new(w);
                        let point = paid
                            .binary(after)
                            .map(crate::exact_source::history_paid::root);
                        let point = paid.finish(point)?;
                        if let (Some(a), Some(b)) = (root, point) {
                            a.order_with_work(&b, w)?.is_gt()
                        } else {
                            false
                        }
                    } else {
                        false
                    };
                let linked = event.fixed_predecessor.is_some()
                    && retained
                        .binary_search_by(|time| time.total_cmp(&event.time))
                        .is_ok()
                    && event.time > after;
                if event.bounds().lo <= after && !proven_later && !linked {
                    return Err(unresolved(
                        "future event window overlaps the accepted event boundary",
                    ));
                }
            }
        } else {
            for event in &events {
                let physical_after = held
                    .as_ref()
                    .and_then(|h| h.boundary)
                    .map(|b| b.proves_after(&event.moment, model, None))
                    .transpose()?
                    .unwrap_or(false);
                let proven_later = physical_after
                    || event
                        .exact_root()
                        .zip(crate::exact_source::RootTime::point(after))
                        .is_some_and(|(a, b)| {
                            event.time > after && a.order(&b) == std::cmp::Ordering::Greater
                        })
                    || matches!(event.moment, Moment::Anchored {delta,..} if delta.lo > operators.and_then(Operators::local_epoch).map_or(f64::INFINITY,|(_,start)|start) && event.time>after)
                    || (event.fixed_predecessor.is_some()
                        && retained
                            .binary_search_by(|time| time.total_cmp(&event.time))
                            .is_ok()
                        && event.time > after);
                if event.bounds().lo <= after && !proven_later {
                    return Err(unresolved(
                        "future event window overlaps the accepted event boundary",
                    ));
                }
            }
        }
    }
    if let Some(w) = history_work {
        history_bookkeeping::sort(&mut events, w, |a, b| {
            Ok(a.moment
                .bounds_with_work(w)?
                .lo
                .total_cmp(&b.moment.bounds_with_work(w)?.lo)
                .then(a.event.cmp(&b.event)))
        })?;
    } else {
        events.sort_by(|a, b| {
            a.moment
                .bounds()
                .lo
                .total_cmp(&b.moment.bounds().lo)
                .then(a.event.cmp(&b.event))
        });
    }
    let mut start = 0;
    while start < events.len() {
        if let Some(w) = history_work {
            w.step()?;
        }
        // Find the whole connected enclosure cluster before attempting an
        // exact ordering certificate. Moments without that proof retain the
        // existing simultaneous-root and ambiguity checks below.
        let mut cluster_end = start + 1;
        let mut cluster_hi = events[start].bounds().hi.max(events[start].time);
        while cluster_end < events.len() {
            if let Some(w) = history_work {
                w.step()?;
            }
            if !matches!(
                events[cluster_end].bounds().lo.partial_cmp(&cluster_hi),
                Some(std::cmp::Ordering::Less | std::cmp::Ordering::Equal)
            ) {
                break;
            }
            cluster_hi = cluster_hi
                .max(events[cluster_end].bounds().hi)
                .max(events[cluster_end].time);
            cluster_end += 1;
        }
        if cluster_end > start + 1
            && if let Some(w) = history_work {
                w.step()?;
                false
            } else {
                serial_transition_cluster(&mut events[start..cluster_end], model)?
            }
        {
            start = cluster_end;
            continue;
        }
        if cluster_end > start + 1
            && history_bookkeeping::independent_kinds_with_work(
                &events[start..cluster_end],
                model,
                history_work,
            )?
            && history_bookkeeping::all_ordered_with_work(
                &events[start..cluster_end],
                model,
                history_work,
            )?
        {
            loop {
                if let Some(w) = history_work {
                    w.step()?;
                }
                order_fixed_timers_with_work(
                    &mut events[start..cluster_end],
                    model,
                    trajectory.config.stop,
                    None,
                    history_work,
                )?;
                // Strict representatives may extend beyond the original
                // connected enclosures. Include the next physical event only
                // when its original certificate orders it against the entire
                // cluster, then recheck every representative's own budgets.
                // A disjoint enclosure is not a deadline when those exact
                // proofs permit the same bounded causal transaction to grow.
                let last = events[cluster_end - 1].time;
                let Some(next) = events.get(cluster_end) else {
                    break;
                };
                if next.bounds().lo > last {
                    break;
                }
                // Include the whole next enclosure component. Equal-time
                // leaves necessarily share a component, so a large same-time
                // batch must not cause one full sort per leaf. Disjoint
                // components add distinct physical groups, whose count is
                // bounded by the controller's shared microevent budget.
                let mut extension_end = cluster_end + 1;
                let mut extension_hi = next.bounds().hi.max(next.time);
                while extension_end < events.len() {
                    if let Some(w) = history_work {
                        w.step()?;
                    }
                    if !matches!(
                        events[extension_end].bounds().lo.partial_cmp(&extension_hi),
                        Some(std::cmp::Ordering::Less | std::cmp::Ordering::Equal)
                    ) {
                        break;
                    }
                    extension_hi = extension_hi
                        .max(events[extension_end].bounds().hi)
                        .max(events[extension_end].time);
                    extension_end += 1;
                }
                for index in cluster_end..extension_end {
                    if let Some(w) = history_work {
                        w.step()?;
                    }
                    let next = &events[index];
                    if !(next.moment.clock().is_some()
                        || matches!(next.moment, Moment::Cross(_) | Moment::Anchored { .. }))
                        || history_bookkeeping::any_unordered_with_work(
                            &events[start..index],
                            next,
                            model,
                            history_work,
                        )?
                    {
                        return Err(unresolved(
                            "cannot certify exact ordering of the next event while extending the connected cluster",
                        ));
                    }
                }
                cluster_end = extension_end;
            }
            start = cluster_end;
            continue;
        }
        let mut end = start + 1;
        let mut time = events[start].time;
        // Include uncertain nominal times on either side of the chosen time.
        let mut hi = events[start].moment.bounds().hi;
        while end < events.len() {
            if let Some(w) = history_work {
                w.step()?;
            }
            if !matches!(
                events[end].moment.bounds().lo.partial_cmp(&hi.max(time)),
                Some(std::cmp::Ordering::Less | std::cmp::Ordering::Equal)
            ) {
                break;
            }
            let first = &events[start];
            let next = &events[end];
            let same_guard = match (
                &model.triggers[first.event].trigger,
                &model.triggers[next.event].trigger,
            ) {
                (EventTrigger::Cross { guard: a, .. }, EventTrigger::Cross { guard: b, .. }) => {
                    let equal = if let Some(w) = history_work {
                        crate::history_admission::same_expression(a, b, w)?
                    } else {
                        a == b
                    };
                    let projected = if !equal
                        && !model.dynamic_guards[first.event]
                        && !model.dynamic_guards[next.event]
                    {
                        if let Some(bounds) = bounds.as_ref() {
                            if let Some(w) = history_work {
                                bounds.same_zero_set_history(first.event, next.event, w)?
                            } else {
                                bounds.same_zero_set(first.event, next.event)
                            }
                        } else {
                            false
                        }
                    } else {
                        false
                    };
                    equal || projected
                }
                (
                    EventTrigger::HeldTimer {
                        start: a,
                        period: p,
                        ..
                    },
                    EventTrigger::HeldTimer {
                        start: b,
                        period: q,
                        ..
                    },
                ) => a == b && p == q,
                _ => false,
            };
            if !if let Some(w) = history_work {
                history_bookkeeping::coincides(&first.moment, &next.moment, same_guard, w)?
            } else {
                first.moment.coincides(&next.moment, same_guard)
            } {
                return Err(unresolved(
                    "cannot certify ordering of distinct events with overlapping time bounds",
                ));
            }
            time = time.max(next.time);
            hi = hi.max(next.moment.bounds().hi);
            end += 1;
        }
        for event in &mut events[start..end] {
            if let Some(w) = history_work {
                w.step()?;
            }
            let leaf = &model.triggers[event.event];
            let spec = &model.program.events[leaf.event];
            if !event.moment.accepts(time, &leaf.trigger) {
                return Err(unresolved(&format!(
                    "event uncertainty or representable time exceeds tolerances at {}",
                    spec.origin.label()
                )));
            }
            event.time = time;
        }
        start = end;
    }
    Ok(events)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ir::{Program, Tolerances, SCHEMA_VERSION};
    use serde_json::json;

    fn model() -> EventModel {
        let origin = json!({"source":"calendar","line":1,"column":1,"instance":"dut"});
        let program: Program = serde_json::from_value(json!({
            "schema_version":SCHEMA_VERSION,"nodes":["0","y"],
            "states":[{"instance":"dut","name":"n","kind":"integer","initial":0}],
            "events":[{"trigger":{"kind":"timer","start":1.,"period":0.,
                "time_tolerance":10.,"enabled":true},"origin":origin,
                "body":[{"kind":"assign","state":0,"rhs":{"op":"affine","constant":1.,"terms":[]}}]}],
            "contributions":[{"branch":{"instance":"dut","local_positive":"r","local_negative":"y","kind":"voltage"},
                "positive":0,"negative":1,"origin":origin,"rhs":{"op":"state","state":0}}]
        })).unwrap();
        EventModel::new(program, vec![], Tolerances::default()).unwrap()
    }

    fn event(start: f64, lo: f64, hi: f64) -> ScheduledEvent {
        ScheduledEvent {
            fixed_predecessor: None,
            occurrence: None,
            time: hi,
            event: 0,
            moment: Moment::Timer {
                bounds: I { lo, hi },
                start,
                period: 0.,
                index: 0,
            },
        }
    }

    #[test]
    fn singleton_boundary_uses_occurrence_identity_but_different_roots_do_not_share_it() {
        let model = model();
        let w = crate::transition_source_plan::Work::default();
        let mut first = event(0.6, 0.4, 0.6);
        first.moment = Moment::Dynamic {
            history: None,
            exact: None,
            bounds: I { lo: 0.4, hi: 0.6 },
            derivative: I::ONE,
            end: 1.,
        };
        let singleton = [first.clone()];
        let boundary = TimerBoundary::new_with_work(&model, 0.6, &singleton, Some(&w)).unwrap();
        assert!(boundary.common_moment.is_some());
        assert!(boundary
            .proves_after(&event(0.75, 0.75, 0.75).moment, &model, Some(&w))
            .unwrap());
        let mut unproved = [first.clone(), first.clone()];
        unproved[0].occurrence = Some(Arc::new(()));
        unproved[1].occurrence = Some(Arc::new(()));
        assert!(
            TimerBoundary::new_with_work(&model, 0.6, &unproved, Some(&w))
                .unwrap()
                .common_moment
                .is_none()
        );
        unproved[1].occurrence = unproved[0].occurrence.clone();
        assert!(
            TimerBoundary::new_with_work(&model, 0.6, &unproved, Some(&w))
                .unwrap()
                .common_moment
                .is_some()
        );
        let mut second = first.clone();
        if let Moment::Dynamic { exact, .. } = &mut first.moment {
            *exact = crate::exact_source::RootTime::point(0.45);
        }
        if let Moment::Dynamic { exact, .. } = &mut second.moment {
            *exact = crate::exact_source::RootTime::point(0.55);
        }
        let pair = [first.clone(), second];
        let boundary = TimerBoundary::new_with_work(&model, 0.6, &pair, Some(&w)).unwrap();
        assert!(boundary.common_moment.is_none());
        assert!(!boundary
            .proves_after(&event(0.75, 0.75, 0.75).moment, &model, Some(&w))
            .unwrap());
        first.time = 0.59;
        assert_eq!(
            TimerBoundary::new_with_work(&model, 0.6, &[first], Some(&w))
                .err()
                .unwrap()
                .kind,
            "event_resolution"
        );
    }

    #[test]
    fn calendar_copy_keeps_normal_fee_and_checks_sticky_owner_before_cloning_handles() {
        let model = model();
        let work = crate::transition_source_plan::Work::limited([128, 8192, 80]);
        assert!(model.mixed_cold_work.set(work.clone()).is_ok());
        let token = Arc::new(());
        let mut events = vec![event(1., 1., 1.), event(2., 2., 2.), event(3., 3., 3.)];
        events[0].occurrence = Some(token.clone());
        let before = Arc::strong_count(&token);
        let copied = copy_calendar(&events, &model).unwrap();
        assert_eq!(work.spent(), 80);
        assert_eq!(copied.len(), 3);
        assert_eq!(Arc::strong_count(&token), before + 1);
        drop(copied);
        assert_eq!(Arc::strong_count(&token), before);
        assert_eq!(
            copy_calendar(&events, &model).err().unwrap().kind,
            "step_budget"
        );
        let exhausted = work.spent();
        assert_eq!(exhausted, 160);
        assert_eq!(Arc::strong_count(&token), before);
        for _ in 0..2 {
            assert_eq!(
                copy_calendar(&events, &model).err().unwrap().kind,
                "step_budget"
            );
            assert_eq!(work.spent(), exhausted);
            assert_eq!(Arc::strong_count(&token), before);
        }
    }

    #[test]
    fn exact_groups_keep_original_enclosures_and_joint_representative() {
        let m = model();
        // The three enclosures form a transitive chain, with an equal-time subgroup.
        let mut events = vec![event(2., 1.5, 3.), event(1., 0.5, 1.5), event(2., 2., 4.)];
        order_fixed_timers(&mut events, &m, 10., None).unwrap();
        assert_eq!(
            events.iter().map(|e| e.time).collect::<Vec<_>>(),
            [1.5, 4., 4.]
        );
        assert_eq!(
            events.iter().map(|e| e.bounds()).collect::<Vec<_>>(),
            [
                I { lo: 0.5, hi: 1.5 },
                I { lo: 1.5, hi: 3. },
                I { lo: 2., hi: 4. }
            ]
        );
    }

    #[test]
    fn shared_isolation_identity_is_not_box_or_representative_identity() {
        let m = model();
        let mut first = event(1., 1., 1.5);
        first.moment = Moment::Dynamic {
            history: None,
            exact: None,
            bounds: I { lo: 1., hi: 1.5 },
            derivative: I::ONE,
            end: 2.,
        };
        first.occurrence = Some(Arc::new(()));
        let same = first.clone();
        assert!(common_occurrence(&[first.clone(), same], &m).unwrap());
        let mut different = first.clone();
        different.occurrence = Some(Arc::new(()));
        assert!(!common_occurrence(&[first.clone(), different], &m).unwrap());
        let mut missing = first.clone();
        missing.occurrence = None;
        assert!(!common_occurrence(&[first, missing], &m).unwrap());
    }

    #[test]
    fn isolation_tokens_stay_inside_owner_epoch_and_search_segment() {
        let mut m = model();
        m.triggers[0].trigger = EventTrigger::Cross {
            guard: Expression::Power {
                base: Box::new(Expression::State { state: 0 }),
                exponent: 2,
            },
            direction: 1,
            time_tolerance: 1e-10,
            expression_tolerance: 1e-10,
        };
        let root = crate::dynamic_roots::CertifiedRoot {
            bounds: I { lo: 1., hi: 1.5 },
            derivative: I::ONE,
        };
        let mut cache = Vec::new();
        let w = crate::real_expression::work(&m);
        let first = shared_isolation(&mut cache, 0, false, [0., 2.], &m, Some(w), || {
            Ok(vec![root])
        })
        .unwrap();
        let same = shared_isolation(&mut cache, 0, false, [0., 2.], &m, Some(w), || {
            panic!("shared guard rediscovered")
        })
        .unwrap();
        assert!(Arc::ptr_eq(&first[0].1, &same[0].1));
        let segment = shared_isolation(&mut cache, 0, false, [2., 3.], &m, Some(w), || {
            Ok(vec![root])
        })
        .unwrap();
        assert!(!Arc::ptr_eq(&first[0].1, &segment[0].1));
        let mut next_epoch = Vec::new();
        let next = shared_isolation(&mut next_epoch, 0, false, [0., 2.], &m, Some(w), || {
            Ok(vec![root])
        })
        .unwrap();
        assert!(!Arc::ptr_eq(&first[0].1, &next[0].1));
        // Owner changes must not borrow a previously discovered root certificate.
        m.program.events[0].origin.instance = "other_instance".into();
        // A real calendar never changes its immutable owner context. A fresh
        // calendar is mandatory for any state/history/instance epoch change.
        let mut changed_epoch = Vec::new();
        let w = crate::real_expression::work(&m);
        let changed = shared_isolation(&mut changed_epoch, 0, false, [0., 2.], &m, Some(w), || {
            Ok(vec![root])
        })
        .unwrap();
        assert!(!Arc::ptr_eq(&first[0].1, &changed[0].1));
    }

    #[test]
    fn occurrence_consumers_use_simple_request_owner_and_sticky_failure() {
        let m = model();
        let w = crate::transition_source_plan::Work::limited([128, 8192, 1]);
        assert!(m.mixed_cold_work.set(w.clone()).is_ok());
        let events = [event(1., 1., 1.)];
        assert_eq!(
            common_occurrence(&events, &m).unwrap_err().kind,
            "step_budget"
        );
        let spent = w.spent();
        assert_eq!(
            common_occurrence(&events, &m).unwrap_err().kind,
            "step_budget"
        );
        assert!(w.spent() > spent);
        assert_eq!(batch_end(&events, 0, &m).unwrap_err().kind, "step_budget");
        assert_eq!(
            copy_calendar(&events, &m).err().unwrap().kind,
            "step_budget"
        );
    }

    #[test]
    fn occurrence_cache_charges_original_owner_and_failure_stays_exhausted() {
        let m = model();
        let w = crate::real_expression::work(&m);
        let alias = crate::real_expression::work(&m);
        assert!(w.same_owner(alias));
        let root = crate::dynamic_roots::CertifiedRoot {
            bounds: I { lo: 1., hi: 1.5 },
            derivative: I::ONE,
        };
        let mut cache = Vec::new();
        let before = w.spent();
        shared_isolation(&mut cache, 0, false, [0., 2.], &m, Some(w), || {
            Ok(vec![root])
        })
        .unwrap();
        assert!(w.spent() > before);
        let small = crate::transition_source_plan::Work::limited([128, 8192, 1]);
        for _ in 0..2 {
            assert_eq!(
                shared_isolation(&mut cache, 0, false, [2., 3.], &m, Some(&small), || Ok(
                    vec![root]
                ))
                .err()
                .unwrap()
                .kind,
                "step_budget"
            );
            assert_eq!(cache.len(), 1);
        }
    }

    #[test]
    fn physical_group_budget_counts_distinct_roots_inside_one_float_cell() {
        use num_rational::BigRational as R;
        let mut m = model();
        let constant = |v| {
            Box::new(Expression::Affine {
                constant: v,
                terms: vec![],
            })
        };
        m.triggers[0].trigger = EventTrigger::HeldTimer {
            start: constant(1.),
            period: constant(0.),
            time_tolerance: 10.,
            enabled: constant(1.),
        };
        let bounds = I {
            lo: 1.,
            hi: 1.0_f64.next_up(),
        };
        let events = || {
            (1..=66)
                .map(|i| {
                    let value = R::from_integer(1.into()) + R::new(i.into(), (1_u64 << 60).into());
                    let mut e = event(1., bounds.lo, bounds.hi);
                    e.moment = Moment::HeldTimer {
                        exact: crate::exact_source::RootTime::affine(
                            -value,
                            R::from_integer(1.into()),
                            bounds,
                        ),
                        bounds,
                        index: i as usize,
                        clock: None,
                    };
                    e
                })
                .collect::<Vec<_>>()
        };
        let mut allowed = events();
        allowed.pop();
        order_fixed_timers(&mut allowed, &m, 2., None).unwrap();
        assert!(allowed.iter().all(|e| e.time == bounds.hi));
        let mut too_many = events();
        assert_eq!(
            order_fixed_timers(&mut too_many, &m, 2., None)
                .unwrap_err()
                .kind,
            "event_budget"
        );
        let boundary = TimerBoundary::new(&m, allowed[0].time, &allowed[..1]).unwrap();
        assert!(boundary.proves_after(&allowed[1].moment, &m, None).unwrap());
        assert!(!boundary.proves_after(&allowed[0].moment, &m, None).unwrap());
    }

    #[test]
    fn physical_phases_share_representatives_and_outside_still_fails_closed() {
        let m = model();
        let close = || vec![event(1., 1., 1.5), event(1.1, 1., 1.5)];
        let mut shared = close();
        order_fixed_timers(&mut shared, &m, 1.5, None).unwrap();
        assert_eq!(
            shared.iter().map(|e| e.time).collect::<Vec<_>>(),
            [1.5, 1.5]
        );
        assert_eq!(batch_end(&shared, 0, &m).unwrap(), 1);
        for (stop, next, message) in [
            (1.4, None, "ordered timer representatives exceed stop"),
            (
                2.,
                Some(1.5),
                "ordered timer representatives reach the next event boundary",
            ),
        ] {
            let error = order_fixed_timers(&mut close(), &m, stop, next)
                .err()
                .unwrap();
            assert_eq!(error.kind, "event_resolution");
            assert_eq!(error.message, message);
        }
        let mut overflow = vec![
            event(f64::MAX.next_down(), f64::MAX.next_down(), f64::MAX),
            event(f64::MAX, f64::MAX, f64::MAX),
        ];
        // Exact physical phases do not need an invented next_up(MAX).
        let mut wide = model();
        if let EventTrigger::Timer { time_tolerance, .. } = &mut wide.triggers[0].trigger {
            *time_tolerance = f64::MAX;
        }
        order_fixed_timers(&mut overflow, &wide, f64::MAX, None).unwrap();
        assert!(overflow.iter().all(|e| e.time == f64::MAX));
        assert_eq!(batch_end(&overflow, 0, &wide).unwrap(), 1);
        let mut invalid = vec![event(f64::NAN, 0., 1.), event(1., 1., 1.)];
        assert_eq!(
            order_fixed_timers(&mut invalid, &m, 2., None)
                .err()
                .unwrap()
                .kind,
            "event_resolution"
        );
    }
}

#[cfg(test)]
mod exact_history_root_tests {
    use super::*;
    use num_rational::BigRational as R;
    #[test]
    fn exact_history_refinement_retains_discovery_and_distinguishes_subulp_roots() {
        let discovery = I { lo: 0.3, hi: 0.4 };
        let a = crate::exact_source::RootTime::affine(
            R::from_integer((-1).into()),
            R::from_integer(3.into()),
            discovery,
        )
        .unwrap();
        assert!(a.refine(I::point(0.5)).is_none());
        assert!(crate::exact_source::RootTime::affine(
            R::from_integer((-1).into()),
            R::from_integer(3.into()),
            I::point(0.5)
        )
        .is_none());
        let shifted = R::new(1.into(), 3.into()) + R::new(1.into(), (1u64 << 60).into());
        let b =
            crate::exact_source::RootTime::affine(-shifted, R::from_integer(1.into()), discovery)
                .unwrap();
        let first = Moment::Dynamic {
            history: None,
            exact: Some(a),
            bounds: discovery,
            derivative: I::point(3.),
            end: 1.,
        };
        let second = Moment::Dynamic {
            history: None,
            exact: Some(b),
            bounds: discovery,
            derivative: I::ONE,
            end: 1.,
        };
        assert_eq!(first.bounds(), second.bounds());
        assert_eq!(first.exact_order(&second), Some(std::cmp::Ordering::Less));
        assert!(!first.coincides(&second, true));
        if let Moment::Dynamic { bounds, .. } = &first {
            assert_eq!(*bounds, discovery);
        }
        let tight = first.bounds();
        assert!(discovery.lo <= tight.lo && tight.hi <= discovery.hi);
        let trigger = EventTrigger::Cross {
            guard: crate::ir::Expression::Affine {
                constant: 0.,
                terms: vec![],
            },
            direction: 1,
            time_tolerance: 1e-20,
            expression_tolerance: 1e-8,
        };
        assert!(!first.accepts(tight.hi, &trigger));
    }
}

#[cfg(test)]
#[path = "schedule_timer_boundary_tests.rs"]
mod timer_boundary_tests;

#[cfg(test)]
mod common_exact_root_tests {
    use super::*;
    use crate::exact_source::RootTime;
    use num_rational::BigRational as R;
    use num_traits::One;
    fn event(exact: Option<RootTime>) -> ScheduledEvent {
        ScheduledEvent {
            time: 0.4,
            event: 0,
            fixed_predecessor: None,
            occurrence: None,
            moment: Moment::Dynamic {
                history: None,
                exact,
                bounds: I { lo: 0.3, hi: 0.4 },
                derivative: I::ONE,
                end: 1.,
            },
        }
    }
    #[test]
    fn identical_discovery_boxes_do_not_prove_common_root() {
        let a =
            RootTime::affine(-R::one(), R::from_integer(3.into()), I { lo: 0.3, hi: 0.4 }).unwrap();
        let b = RootTime::affine(
            -R::from_integer(7.into()),
            R::from_integer(20.into()),
            I { lo: 0.3, hi: 0.4 },
        )
        .unwrap();
        assert!(common_root(&[event(Some(a.clone())), event(Some(a.clone()))]).is_some());
        assert!(common_root(&[event(Some(a.clone())), event(Some(b))]).is_none());
        assert!(common_root(&[event(Some(a)), event(None)]).is_none());
        assert!(common_root(&[]).is_none());
    }
    #[test]
    fn fixed_clock_and_history_root_require_mathematical_equality() {
        let window = I { lo: 0.3, hi: 0.4 };
        let root = RootTime::from_clock(
            Clock {
                start: 0.1,
                period: 0.25,
                index: 1,
            },
            window,
        )
        .unwrap();
        let history = event(Some(root));
        let timer = ScheduledEvent {
            time: 0.4,
            event: 1,
            fixed_predecessor: None,
            occurrence: None,
            moment: Moment::Timer {
                bounds: window,
                start: 0.1,
                period: 0.25,
                index: 1,
            },
        };
        assert!(common_root(&[history, timer]).is_some());
        assert!(RootTime::from_clock(
            Clock {
                start: 0.,
                period: 1.,
                index: EVENT_BUDGET + 1
            },
            window
        )
        .is_none());
    }
}

#[cfg(test)]
mod exact_deadline_review_tests {
    use super::*;
    use crate::exact_source::{binary, RootTime};
    use num_rational::BigRational as R;
    use num_traits::One;

    #[test]
    fn anchored_absolute_root_is_not_shifted_again_by_common_root() {
        let origin =
            serde_json::json!({"source":"anchored_review.va","line":1,"column":1,"instance":"dut"});
        let program = serde_json::from_value(serde_json::json!({
            "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","y"],
            "operators":[{"kind":"idt","input":{"op":"affine","constant":1,"terms":[{"node":1,"coefficient":1}]},"ic":0,"origin":origin}],
            "contributions":[{"branch":{"instance":"dut","local_positive":"y","local_negative":"r","kind":"voltage"},
                "positive":1,"negative":0,"rhs":{"op":"operator","operator":0},"origin":origin}]
        })).unwrap();
        let trajectory = Trajectory::new(
            crate::ir::TransientInputs {
                analytic_sources: vec![],
                pwl_errors_v: None,
                strobetimes: vec![],
                pwl: vec![],
                output_times: vec![0., 2.],
                stop: 2.,
                max_step: 0.125,
                proof_work_limit: None,
            },
            0,
        )
        .unwrap();
        let history = Arc::new(
            Continuous::new(&program, &trajectory, &[], &[])
                .unwrap()
                .unwrap(),
        );
        let anchor = Clock {
            start: 0.1,
            period: 0.2,
            index: 1,
        };
        let local =
            RootTime::affine(-R::one(), R::from_integer(3.into()), I { lo: 0.3, hi: 0.4 }).unwrap();
        let absolute = local.shifted_clock(anchor).unwrap();
        let window = absolute.bounds().unwrap();
        // Independently form the expected absolute value from original binary parameters.
        let expected_value =
            binary(0.1).unwrap() + binary(0.2).unwrap() + R::new(1.into(), 3.into());
        let expected = RootTime::affine(-expected_value.clone(), R::one(), window).unwrap();
        let event = ScheduledEvent {
            time: window.hi,
            event: 0,
            fixed_predecessor: None,
            occurrence: None,
            moment: Moment::Anchored {
                anchor,
                delta: local.bounds().unwrap(),
                derivative: I::ONE,
                end: 2.,
                bounds: window,
                history,
                exact: Some(absolute),
            },
        };
        let companion = ScheduledEvent {
            time: window.hi,
            event: 1,
            fixed_predecessor: None,
            occurrence: None,
            moment: Moment::Dynamic {
                history: None,
                exact: Some(expected.clone()),
                bounds: window,
                derivative: I::ONE,
                end: 2.,
            },
        };
        let common = common_root(&[event, companion]).unwrap();
        assert_eq!(common.order(&expected), std::cmp::Ordering::Equal);
        assert_ne!(
            common.order(&expected.shifted_clock(anchor).unwrap()),
            std::cmp::Ordering::Equal
        );
        assert_eq!(common.bounds(), Some(window));
        // Carry the extracted proof through both pending activation and fresh end.
        let mut edge = crate::transition::Transition::new(0., 0.125, 0.25, 0.25).unwrap();
        edge.advance_at_with_exact(window.hi, window, 1., I::ONE, true, Some(&common))
            .unwrap();
        let activation = edge.next_breakpoint(0.).unwrap();
        edge.advance_at(activation, I::point(activation), 1., I::ONE, false)
            .unwrap();
        // Independent callback at absolute+.25 with duration .125 has the same
        // endpoint. Neither source time is a point, so old point/sum keys cannot pass.
        let reference_root = RootTime::affine(
            -(expected_value + binary(0.25).unwrap()),
            R::one(),
            I { lo: 0., hi: 2. },
        )
        .unwrap();
        let reference_window = reference_root.bounds().unwrap();
        let mut reference = crate::transition::Transition::new(0., 0., 0.125, 0.125).unwrap();
        reference
            .advance_at_with_exact(
                reference_window.hi,
                reference_window,
                1.,
                I::ONE,
                true,
                Some(&reference_root),
            )
            .unwrap();
        assert!(
            edge.deadlines(activation)[0].coincides(&reference.deadlines(reference_window.hi)[0])
        );
    }
}

#[cfg(test)]
mod held_review_tests {
    use super::*;
    use crate::exact_source::RootTime;
    use num_rational::BigRational as R;
    fn root(value: R) -> RootTime {
        RootTime::affine(-value, R::from_integer(1.into()), I { lo: 0., hi: 1. }).unwrap()
    }
    #[test]
    fn held_exact_preserves_wide_box_and_consumes_only_matching_leaf() {
        let a = root(R::new(1.into(), 3.into()));
        let b = root(R::new(1.into(), 3.into()) + R::new(1.into(), (1u64 << 60).into()));
        let bounds = I { lo: 0.3, hi: 0.4 };
        let old = ScheduledEvent {
            time: 0.4,
            event: 2,
            fixed_predecessor: None,
            occurrence: None,
            moment: Moment::HeldTimer {
                bounds,
                index: 0,
                clock: None,
                exact: Some(a.clone()),
            },
        };
        assert_eq!(old.bounds(), bounds);
        assert_ne!(old.bounds(), a.bounds().unwrap());
        let boundary = TimerBoundary {
            observation: bounds,
            consumed: std::collections::BTreeMap::from([(2, &old)]),
            common_moment: Some(&old.moment),
        };
        assert!(boundary
            .already_past_or_consumed(2, bounds, None, Some(&a))
            .unwrap());
        assert!(boundary
            .already_past_or_consumed(3, bounds, None, Some(&a))
            .is_err());
        assert!(!boundary
            .already_past_or_consumed(2, bounds, None, Some(&b))
            .unwrap());
        assert!(boundary
            .already_past_or_consumed(2, bounds, None, None)
            .is_err());
        for t in [1. / 3., (1. / 3.0_f64).next_up()] {
            assert_eq!(
                old.physical_order_at(t),
                Some(
                    a.clock_delta_order(
                        Clock {
                            start: t,
                            period: 0.,
                            index: 0
                        },
                        0.
                    )
                    .unwrap()
                )
            );
        }
    }
}
#[cfg(test)]
mod held_calendar_review_tests {
    use super::*;

    #[test]
    fn cold_paid_clone_retains_held_identity_without_widening_history_admission() {
        let event = ScheduledEvent {
            time: 0.5,
            event: 0,
            fixed_predecessor: Some(0.25),
            occurrence: None,
            moment: Moment::HeldTimer {
                bounds: I::point(0.5),
                index: 0,
                clock: Some(Clock {
                    start: 0.5,
                    period: 0.,
                    index: 0,
                }),
                exact: crate::exact_source::RootTime::point(0.5),
            },
        };
        let work = crate::transition_source_plan::Work::default();
        assert!(event.clone_history(&work).is_err());
        let spent = work.spent();
        let copied = event.clone_cold_timer(&work).unwrap();
        assert!(work.spent() > spent);
        assert_eq!(copied.time, event.time);
        assert_eq!(copied.fixed_predecessor, event.fixed_predecessor);
        assert_eq!(
            copied.moment.exact_order(&event.moment),
            Some(std::cmp::Ordering::Equal)
        );
        let small = crate::transition_source_plan::Work::limited([128, 8192, 0]);
        for _ in 0..2 {
            let before = small.spent();
            assert_eq!(
                event.clone_cold_timer(&small).err().unwrap().kind,
                "step_budget"
            );
            assert!(small.spent() > before);
            assert_eq!(event.time, 0.5);
            assert_eq!(event.clock().unwrap().start, 0.5);
        }
    }
    use crate::exact_source::RootTime;
    use crate::transient::time_provenance::{invalidate_timers, TimeProofs};
    use num_rational::BigRational as R;
    use serde_json::json;
    fn fixture(dynamic_period: bool) -> (EventModel, Trajectory) {
        let o = json!({"source":"review.va","line":1,"column":1,"instance":"D"});
        let c = |v: f64| json!({"op":"affine","constant":v,"terms":[]});
        let s = |i: usize| json!({"op":"state","state":i});
        let period = if dynamic_period { s(2) } else { c(0.) };
        let p=serde_json::from_value(json!({"schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","y"],"states":[{"instance":"D","name":"due","kind":"real","initial":0.3333333333333333},{"instance":"D","name":"enabled","kind":"real","initial":1},{"instance":"D","name":"period","kind":"real","initial":0}],"operators":[],"events":[{"origin":o,"trigger":{"kind":"timer","start":0.1,"period":0,"enabled":true,"time_tolerance":1e-6},"body":[]},{"origin":o,"trigger":{"kind":"held_timer","start":s(0),"period":period,"enabled":s(1),"time_tolerance":0.2},"body":[]}],"contributions":[{"origin":o,"branch":{"instance":"D","local_positive":"out","local_negative":"ref","kind":"voltage"},"positive":1,"negative":0,"rhs":s(0)}]})).unwrap();
        let m = EventModel::new(p, vec![], crate::ir::Tolerances::default()).unwrap();
        let t = Trajectory::new(
            crate::ir::TransientInputs {
                analytic_sources: vec![],
                pwl_errors_v: None,
                pwl: vec![],
                strobetimes: vec![],
                output_times: vec![0., 1.],
                stop: 1.,
                max_step: 0.1,
                proof_work_limit: None,
            },
            0,
        )
        .unwrap();
        (m, t)
    }
    #[test]
    fn same_numeric_bounds_proof_replacement_clear_and_cancel_rebuild_calendar() {
        let (m, t) = fixture(false);
        let wide = I { lo: 0.3, hi: 0.4 };
        let states = [wide, I::ONE, I::ZERO];
        let proof = |v: R| RootTime::affine(-v, R::from_integer(1.into()), wide).unwrap();
        let a = proof(R::new(1.into(), 3.into()));
        let b = proof(R::new(1.into(), 3.into()) + R::new(1.into(), (1u64 << 60).into()));
        let before = TimeProofs::from([(0, a.clone())]);
        let calendar = schedule_held_with_time_proofs(&m, &t, &states, Some(&before)).unwrap();
        let batch = vec![calendar[0].clone()];
        let pending = vec![calendar[1].clone()];
        assert_eq!(pending[0].exact_root(), Some(a.clone()));
        assert_eq!(pending[0].bounds(), wide);
        for after in [TimeProofs::from([(0, b.clone())]), TimeProofs::new()] {
            let mut changed = vec![false; 2];
            invalidate_timers(&m.triggers, &before, &after, &mut changed);
            assert_eq!(changed, vec![false, true]);
            let next = reschedule_held_with_time_proofs(
                &m,
                &t,
                &states,
                0.1,
                &changed,
                &pending,
                &batch,
                Some(&after),
            )
            .unwrap();
            assert_eq!(next.len(), 1);
            assert_eq!(next[0].exact_root(), after.get(&0).cloned());
            assert_eq!(next[0].time, pending[0].time);
            assert_eq!(next[0].bounds(), pending[0].bounds());
        }
        // Reusing the old changed mask would retain a stale key; calibrate the detector.
        let after = TimeProofs::from([(0, b.clone())]);
        let stale = reschedule_held_with_time_proofs(
            &m,
            &t,
            &states,
            0.1,
            &[false, false],
            &pending,
            &batch,
            Some(&after),
        )
        .unwrap();
        assert_eq!(stale[0].exact_root(), Some(a));
        assert_ne!(stale[0].exact_root(), Some(b));
        let cancelled = reschedule_held_with_time_proofs(
            &m,
            &t,
            &[wide, I::ZERO, I::ZERO],
            0.1,
            &[false, true],
            &pending,
            &batch,
            Some(&after),
        )
        .unwrap();
        assert!(cancelled.is_empty());
        let rearmed = reschedule_held_with_time_proofs(
            &m,
            &t,
            &states,
            0.1,
            &[false, true],
            &cancelled,
            &batch,
            Some(&after),
        )
        .unwrap();
        assert_eq!(rearmed[0].exact_root(), after.get(&0).cloned());
        let (dynamic, t) = fixture(true);
        let no_key = schedule_held_with_time_proofs(&dynamic, &t, &states, Some(&after)).unwrap();
        assert!(no_key
            .iter()
            .find(|e| e.event == 1)
            .unwrap()
            .exact_root()
            .is_none());
    }
}

// old common_root and all old consumers remain unchanged.
impl Moment {
    /// Preserve old bounds mathematical fallback, but never discard Work errors.
    fn bounds_with_work(&self, w: &crate::transition_source_plan::Work) -> Result<I, Error> {
        w.debit(2, 0)?;
        w.debit(2, 32)?;
        if let Self::HeldTimer { bounds, .. } = self {
            return Ok(*bounds);
        }
        let discovery = match self {
            Self::Cross(root) => root.bounds,
            Self::Anchored { bounds, .. }
            | Self::Dynamic { bounds, .. }
            | Self::Timer { bounds, .. }
            | Self::HeldTimer { bounds, .. } => *bounds,
        };
        if let Some(root) = self.exact_history_root() {
            return Ok(root.refine_with_work(discovery, w)?.unwrap_or(discovery));
        }
        Ok(discovery)
    }
}
impl ScheduledEvent {
    fn clone_history(&self, w: &crate::transition_source_plan::Work) -> Result<Self, Error> {
        w.debit(2, 0)?;
        w.debit(2, 8)?;
        let moment = match &self.moment {
            Moment::Cross(root) => Moment::Cross(root.clone_history(w)?),
            Moment::Timer {
                bounds,
                start,
                period,
                index,
            } => Moment::Timer {
                bounds: *bounds,
                start: *start,
                period: *period,
                index: *index,
            },
            _ => {
                return Err(unresolved(
                    "history calendar escaped independent Cross/Timer gate",
                ))
            }
        };
        Ok(Self {
            time: self.time,
            event: self.event,
            moment,
            fixed_predecessor: self.fixed_predecessor,
            occurrence: self.occurrence.clone(),
        })
    }
    // Payment does not widen the History capability. Only the constructor's
    // explicit timer-only route can retain an existing held timer occurrence.
    fn clone_cold_timer(&self, w: &crate::transition_source_plan::Work) -> Result<Self, Error> {
        if let Moment::HeldTimer {
            bounds,
            index,
            clock,
            exact,
        } = &self.moment
        {
            w.debit(2, 16)?;
            let exact = exact
                .as_ref()
                .map(|root| root.clone_with_work(w))
                .transpose()?;
            Ok(Self {
                time: self.time,
                event: self.event,
                fixed_predecessor: self.fixed_predecessor,
                occurrence: self.occurrence.clone(),
                moment: Moment::HeldTimer {
                    bounds: *bounds,
                    index: *index,
                    clock: *clock,
                    exact,
                },
            })
        } else {
            self.clone_history(w)
        }
    }
    fn exact_root_with_work(
        &self,
        w: &crate::transition_source_plan::Work,
    ) -> Result<Option<crate::exact_source::RootTime>, Error> {
        w.debit(2, 0)?;
        w.debit(2, 32)?;
        let bounds = self.moment.bounds_with_work(w)?;
        let root = if let Some(root) = self.moment.exact_history_root() {
            root.clone_with_work(w)?
        } else if let Moment::Cross(root) = &self.moment {
            let Some(root) = root.rational_time_with_work(w)? else {
                return Ok(None);
            };
            root
        } else {
            let Some(clock) = self.moment.clock() else {
                return Ok(None);
            };
            let Some(root) = crate::exact_source::RootTime::from_clock_with_work(clock, bounds, w)?
            else {
                return Ok(None);
            };
            root
        };
        if root.refine_with_work(bounds, w)?.is_none() {
            return Ok(None);
        }
        Ok(Some(root))
    }
}
pub(crate) fn common_root_with_work(
    events: &[ScheduledEvent],
    w: &crate::transition_source_plan::Work,
) -> Result<Option<crate::exact_source::RootTime>, Error> {
    w.debit(2, 0)?;
    w.debit(
        2,
        (events.len() as u64).saturating_mul(8).saturating_add(16),
    )?;
    let Some(event) = events.first() else {
        return Ok(None);
    };
    let Some(first) = event.exact_root_with_work(w)? else {
        return Ok(None);
    };
    for event in events.iter().skip(1) {
        let Some(next) = event.exact_root_with_work(w)? else {
            return Ok(None);
        };
        if first.order_with_work(&next, w)? != std::cmp::Ordering::Equal {
            return Ok(None);
        }
    }
    Ok(Some(first))
}
pub(crate) fn event_ids_with_work(
    events: &[ScheduledEvent],
    w: &crate::transition_source_plan::Work,
) -> Result<Vec<usize>, Error> {
    w.debit(2, 0)?;
    w.debit(
        2,
        (events.len() as u64).saturating_mul(4).saturating_add(32),
    )?;
    Ok(events.iter().map(|event| event.event).collect())
}

/// Public-to-crate opt-in accessor: paid nested cached proof refinement.
impl ScheduledEvent {
    pub(crate) fn bounds_with_work(
        &self,
        w: &crate::transition_source_plan::Work,
    ) -> Result<I, Error> {
        self.moment.bounds_with_work(w)
    }
}
/// Every bounds read in the caller fold is separately paid; common_root's paid
/// reads do not cover this independent traversal.
pub(crate) fn event_bounds_hull_with_work(
    events: &[ScheduledEvent],
    initial: I,
    w: &crate::transition_source_plan::Work,
) -> Result<I, Error> {
    w.debit(2, 0)?;
    w.debit(
        2,
        (events.len() as u64).saturating_mul(8).saturating_add(32),
    )?;
    let mut result = initial;
    for event in events {
        let bounds = event.bounds_with_work(w)?;
        result = I {
            lo: result.lo.min(bounds.lo),
            hi: result.hi.max(bounds.hi),
        };
    }
    Ok(result)
}

// Same-request calendar and phase seams. Continuous local observation
// remains outside the Forcing provider scope.
// New Forcing scope rejects ambiguous Dynamic/noexact guard re-evaluation.
// This is a deliberate new-route restriction, not an old mathematical None.

impl Moment {
    fn exact_order_with_work(
        &self,
        other: &Self,
        w: &crate::transition_source_plan::Work,
    ) -> Result<Option<std::cmp::Ordering>, Error> {
        w.debit(2, 0)?;
        w.debit(2, 128)?;
        if let Some(root) = self.exact_history_root() {
            if let Some(next) = other.exact_history_root() {
                return Ok(Some(root.order_with_work(next, w)?));
            }
            if let Some(clock) = other.clock() {
                return root.clock_delta_order_with_work(clock, 0., w);
            }
            if let Self::Cross(next) = other {
                let Some(next) = next.rational_time_with_work(w)? else {
                    return Ok(None);
                };
                return Ok(Some(root.order_with_work(&next, w)?));
            }
        }
        if other.exact_history_root().is_some() {
            return Ok(other
                .exact_order_with_work(self, w)?
                .map(std::cmp::Ordering::reverse));
        }
        if std::ptr::eq(self, other) {
            return Ok(Some(std::cmp::Ordering::Equal));
        }
        if let (Some(a), Some(b)) = (self.clock(), other.clock()) {
            return a.order_with_work(b, w);
        }
        match (self, other) {
            (Self::Anchored { anchor, delta, .. }, b) => {
                let other = if let Some(clock) = b.clock() {
                    clock.difference_with_work(*anchor, w)?
                } else {
                    match b {
                        Self::Cross(root) => root.local_bounds_with_work(*anchor, w)?,
                        Self::Anchored {
                            anchor: b,
                            delta: d,
                            ..
                        } if b == anchor => Some(*d),
                        _ => None,
                    }
                };
                let Some(other) = other else {
                    return Ok(None);
                };
                Ok(if delta.hi < other.lo {
                    Some(std::cmp::Ordering::Less)
                } else if delta.lo > other.hi {
                    Some(std::cmp::Ordering::Greater)
                } else if delta.lo == delta.hi && *delta == other {
                    Some(std::cmp::Ordering::Equal)
                } else {
                    None
                })
            }
            (a, Self::Anchored { .. }) => Ok(other
                .exact_order_with_work(a, w)?
                .map(std::cmp::Ordering::reverse)),
            (Self::Cross(a), Self::Cross(b)) => a.exact_order_with_work(b, w),
            (Self::Cross(root), clock) => {
                let Some(clock) = clock.clock() else {
                    return Ok(None);
                };
                root.clock_delta_order_with_work(clock, 0., w)
            }
            (clock, Self::Cross(root)) => {
                let Some(clock) = clock.clock() else {
                    return Ok(None);
                };
                Ok(root
                    .clock_delta_order_with_work(clock, 0., w)?
                    .map(std::cmp::Ordering::reverse))
            }
            _ => Ok(None),
        }
    }
}
impl ScheduledEvent {
    pub(crate) fn physical_order_at_with_work(
        &self,
        time: f64,
        w: &crate::transition_source_plan::Work,
    ) -> Result<Option<std::cmp::Ordering>, Error> {
        w.debit(2, 0)?;
        w.debit(2, 128)?;
        let query = Moment::Timer {
            bounds: I::point(time),
            start: time,
            period: 0.,
            index: 0,
        };
        if let Some(root) = self.moment.exact_history_root() {
            if let Some(order) = root.clock_delta_order_with_work(query.clock().unwrap(), 0., w)? {
                return Ok(Some(order));
            }
        }
        if let Some(order) = self.moment.exact_order_with_work(&query, w)? {
            return Ok(Some(order));
        }
        if let Moment::Anchored { anchor, delta, .. } = &self.moment {
            if let Some(query) = anchor.delta_with_work(time, w)? {
                if delta.hi <= query.lo {
                    return Ok(Some(std::cmp::Ordering::Less));
                }
                if delta.lo > query.hi {
                    return Ok(Some(std::cmp::Ordering::Greater));
                }
            } else {
                return Ok(None);
            }
        }
        let bounds = self.bounds_with_work(w)?;
        Ok(if bounds.lo == bounds.hi && bounds.lo == time {
            Some(std::cmp::Ordering::Equal)
        } else if bounds.hi <= time {
            Some(std::cmp::Ordering::Less)
        } else if bounds.lo > time {
            Some(std::cmp::Ordering::Greater)
        } else {
            None
        })
    }
    pub(crate) fn physical_order_for_query_with_work(
        &self,
        time: f64,
        model: &EventModel,
        w: &crate::transition_source_plan::Work,
    ) -> Result<Option<std::cmp::Ordering>, Error> {
        w.debit(2, 0)?;
        if let Some(order) = self.physical_order_at_with_work(time, w)? {
            return Ok(Some(order));
        }
        w.debit(2, 64)?;
        if !self.can_refine_input_root(model) {
            return Ok(None);
        }
        // Root-approved new Forcing scope: original predicate_sign +
        // GuardTrajectory::new/range are not admitted here. Never fall back
        // after Work error, and never convert this refusal to mathematical None.
        Err(Error::new("unsupported_forcing_scope","forcing phase query needs an original exact root or an already certified interval side; dynamic guard re-evaluation is outside the forcing scope"))
    }
}

#[cfg(test)]
mod forcing_phase_accounting_tests {
    use super::*;
    use crate::ir::{Program, Tolerances, SCHEMA_VERSION};
    use crate::transition_source_plan::Work;
    use serde_json::json;

    #[test]
    fn forcing_unproved_dynamic_phase_is_explicit_scope_error_without_guard_fallback() {
        let o = json!({"source":"forcing-phase.va","line":1,"column":1,"instance":"D"});
        let p:Program=serde_json::from_value(json!({"schema_version":SCHEMA_VERSION,"nodes":["0","u","y"],
            "states":[{"name":"q","instance":"D","kind":"real","initial":0.}],
            "events":[{"origin":o,"trigger":{"kind":"cross","guard":{"op":"affine","constant":-0.5,"terms":[{"node":1,"coefficient":1.}]},
                "direction":1,"time_tolerance":0.2,"expression_tolerance":0.2},
                "body":[{"kind":"assign","state":0,"rhs":{"op":"affine","constant":1.,"terms":[]}}]}],
            "contributions":[{"origin":o,"branch":{"instance":"D","local_positive":"p","local_negative":"r","kind":"voltage"},
                "positive":2,"negative":0,"rhs":{"op":"state","state":0}}]})).unwrap();
        let model = EventModel::new(p, vec!["u".into()], Tolerances::default()).unwrap();
        let event = ScheduledEvent {
            time: 0.6,
            event: 0,
            fixed_predecessor: None,
            occurrence: None,
            moment: Moment::Dynamic {
                history: None,
                exact: None,
                bounds: I { lo: 0.4, hi: 0.6 },
                derivative: I::point(1.),
                end: 1.,
            },
        };
        assert!(event.can_refine_input_root(&model));
        assert_eq!(event.physical_order_at(0.5), None);
        let (result, report) = crate::diagnostics::capture(Default::default(), || {
            event.physical_order_for_query_with_work(0.5, &model, &Work::default())
        });
        assert_eq!(result.unwrap_err().kind, "unsupported_forcing_scope");
        assert_eq!(report.counters.get("root_query_phase_checks"), None);
        let exact = ScheduledEvent {
            moment: Moment::Dynamic {
                history: None,
                exact: Some(crate::exact_source::RootTime::point(0.5).unwrap()),
                bounds: I { lo: 0.4, hi: 0.6 },
                derivative: I::point(1.),
                end: 1.,
            },
            ..event
        };
        let work = Work::default();
        for (time, want) in [
            (0.25, std::cmp::Ordering::Greater),
            (0.5, std::cmp::Ordering::Equal),
            (0.75, std::cmp::Ordering::Less),
        ] {
            assert_eq!(
                exact
                    .physical_order_for_query_with_work(time, &model, &work)
                    .unwrap(),
                Some(want)
            );
            assert_eq!(exact.physical_order_at(time), Some(want));
        }
    }
}

#[cfg(test)]
impl ScheduledEvent {
    pub(crate) fn analytic_test_snapshot(&self) -> serde_json::Value {
        let moment = match &self.moment {
            Moment::Cross(root) => {
                serde_json::json!({"kind":"cross","root":root.analytic_test_snapshot()})
            }
            Moment::Timer {
                bounds,
                start,
                period,
                index,
            } => {
                serde_json::json!({"kind":"timer","bounds":[bounds.lo,bounds.hi],"start":start,"period":period,"index":index})
            }
            _ => panic!("non-independent moment escaped analytic event scope"),
        };
        serde_json::json!({"time":self.time,"event":self.event,"moment":moment,"fixed_predecessor":self.fixed_predecessor})
    }
}
