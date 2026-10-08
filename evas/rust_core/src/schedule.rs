//! Certified event calendars. Nominal timer times never accumulate accepted steps.
use crate::continuous::Continuous;
use crate::event_accuracy::{unresolved, GuardBounds};
use crate::events::EventModel;
use crate::exact_time::Clock;
use crate::interval::Interval as I;
use crate::ir::{Error, EventTrigger};
use crate::operators::Operators;
use crate::pwl::{Root, Trajectory};
use std::sync::Arc;

pub(crate) const EVENT_BUDGET: usize = 1_000_000;

#[derive(Clone)]
pub(crate) struct ScheduledEvent {
    pub(crate) time: f64,
    pub(crate) event: usize,
    moment: Moment,
    // Set only by exact fixed-clock ordering. Retaining this pending event
    // across an epoch must not discard the proof against its predecessor.
    fixed_predecessor: Option<f64>,
}

impl ScheduledEvent {
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
        self.moment.exact_order(&query).or_else(|| {
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

    pub(crate) fn retain_after(&mut self, prior: &Self, model: &EventModel) -> Result<bool, Error> {
        if self.moment.exact_order(&prior.moment) != Some(std::cmp::Ordering::Greater) {
            return Ok(false);
        }
        self.time = self.time.max(prior.time.next_up());
        if !self
            .moment
            .accepts(self.time, &model.triggers[self.event].trigger)
        {
            return Err(unresolved(
                "retained exact event order exceeds original tolerances",
            ));
        }
        self.fixed_predecessor = Some(prior.time);
        Ok(true)
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
    if events
        .iter()
        .any(|event| certified_order(first, event, model) != Some(std::cmp::Ordering::Equal))
    {
        return Err(unresolved(
            "local observation cannot merge distinct physical events",
        ));
    }
    let mut proofs = Vec::new();
    let mut delta = None;
    for event in events {
        let bound = event
            .local_bounds(clock)
            .ok_or_else(|| unresolved("local event has no exact physical time certificate"))?;
        delta = Some(delta.map_or(bound, |old: I| old.hull(bound)));
        if let Moment::Anchored { history, .. } = &event.moment {
            proofs.push(history.clone());
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
    },
    Dynamic {
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
    fn exact_order(&self, other: &Self) -> Option<std::cmp::Ordering> {
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
        match self {
            Self::Cross(root) => root.bounds,
            Self::Anchored { bounds, .. } => *bounds,
            Self::Dynamic { bounds, .. } => *bounds,
            Self::Timer { bounds, .. } => *bounds,
            Self::HeldTimer { bounds, .. } => *bounds,
        }
    }

    fn coincides(&self, other: &Self, same_guard: bool) -> bool {
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
                let delay = local - *delta;
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
                },
                EventTrigger::Cross {
                    time_tolerance,
                    expression_tolerance,
                    ..
                },
            ) => {
                let delay = I::point(time) - *bounds;
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

/// Resolve only a complete overlapping cluster of fixed timers. Keep nominal
/// enclosures for sampling/forward-error propagation; representative delays
/// neither erase uncertainty nor relax any clock's original tolerance.
fn order_fixed_timers(
    events: &mut [ScheduledEvent],
    model: &EventModel,
    stop: f64,
    next_lower: Option<f64>,
) -> Result<(), Error> {
    let mut uncertified = false;
    events.sort_by(|a, b| {
        let order = certified_order(a, b, model).unwrap_or_else(|| {
            uncertified = true;
            std::cmp::Ordering::Equal
        });
        order.then(a.event.cmp(&b.event))
    });
    if uncertified {
        return Err(unresolved("cannot certify exact fixed timer order"));
    }
    let mut start = 0;
    let mut previous: Option<f64> = None;
    while start < events.len() {
        let mut end = start + 1;
        while end < events.len() {
            match certified_order(&events[start], &events[end], model) {
                Some(std::cmp::Ordering::Equal) => end += 1,
                Some(_) => break,
                None => return Err(unresolved("cannot certify exact fixed timer group")),
            }
        }
        // All equal nominal times must share one representative, including
        // when their different arithmetic decompositions have different bounds.
        let mut time = events[start..end]
            .iter()
            .map(|e| e.time.max(e.bounds().hi))
            .fold(0.0, f64::max);
        if let Some(prior) = previous {
            time = time.max(prior.next_up());
        }
        if !time.is_finite() || time > stop || next_lower.is_some_and(|limit| time >= limit) {
            return Err(unresolved(
                "ordered timer representatives exceed stop or the next event boundary",
            ));
        }
        for event in &mut events[start..end] {
            if !event
                .moment
                .accepts(time, &model.triggers[event.event].trigger)
            {
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

fn add_timer(
    events: &mut Vec<ScheduledEvent>,
    event: usize,
    trigger: &EventTrigger,
    stop: f64,
    model: &EventModel,
    states: Option<&[I]>,
    after: Option<f64>,
) -> Result<(), Error> {
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
            if start.lo < 0. || period.lo <= 0. && period.hi > 0. {
                return Err(unresolved(
                    "cannot certify dynamic timer start or period regime",
                ));
            }
            (start, period, enabled, true)
        }
        _ => return Ok(()),
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
        // index is bounded below 2^53, so its f64 conversion is exact. The
        // enclosure covers both product and sum. Choosing its upper endpoint
        // cannot fire early, including when the source omitted time_tol. The
        // clock remains start + index * period, never prior accepted time + T.
        let bounds = if index == 0 {
            start
        } else {
            start + I::point(index as f64) * period
        };
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
        if let Some(after) = after {
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
        events.push(ScheduledEvent {
            fixed_predecessor: None,
            time,
            event,
            moment: if held {
                Moment::HeldTimer {
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
        });
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
    schedule_with_history(
        model,
        trajectory,
        None,
        Some(HeldCalendar {
            states,
            after: None,
            changed: &[],
            pending: &[],
        }),
        CalendarScope::All,
    )
}

pub(crate) fn reschedule_held(
    model: &EventModel,
    trajectory: &Trajectory,
    states: &[I],
    after: f64,
    changed: &[bool],
    pending: &[ScheduledEvent],
) -> Result<Vec<ScheduledEvent>, Error> {
    schedule_with_history(
        model,
        trajectory,
        None,
        Some(HeldCalendar {
            states,
            after: Some(after),
            changed,
            pending,
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
    let changed = vec![true; model.triggers.len()];
    schedule_with_history(
        model,
        trajectory,
        None,
        Some(HeldCalendar {
            states,
            after,
            changed: &changed,
            pending: &[],
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

pub(crate) fn reschedule_independent(
    model: &EventModel,
    trajectory: &Trajectory,
    states: &[I],
    after: f64,
    changed: &[bool],
    pending: &[ScheduledEvent],
) -> Result<Vec<ScheduledEvent>, Error> {
    schedule_with_history(
        model,
        trajectory,
        None,
        Some(HeldCalendar {
            states,
            after: Some(after),
            changed,
            pending,
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
            states: epoch.states,
            after: epoch.after,
            changed: &changed,
            pending: epoch.pending,
        }),
        CalendarScope::History {
            until: epoch.until,
            consumed: epoch.consumed,
        },
    )
}

struct HeldCalendar<'a> {
    states: &'a [I],
    after: Option<f64>,
    changed: &'a [bool],
    pending: &'a [ScheduledEvent],
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
    let _timing = crate::diagnostics::span("event.calendar");

    let mut events: Vec<_> = held.as_ref().map_or_else(Vec::new, |h| {
        h.pending
            .iter()
            .filter(|e| !h.changed[e.event])
            .cloned()
            .collect()
    });
    // A timer-only network needs no guard trajectory certification.
    let bounds = if model.guards.iter().any(Option::is_some) {
        Some(if let Some(h) = &held {
            GuardBounds::held(
                &model.program,
                &model.driven,
                &model.dynamic_guards,
                h.states,
            )?
        } else {
            GuardBounds::new(&model.program, &model.driven, &model.dynamic_guards)?
        })
    } else {
        None
    };
    if let Some(bounds) = &bounds {
        let circuit = model.circuit(&model.initial())?;
        // Preserve network-consistency checks on all physical input knots.
        for &time in &trajectory.knots {
            circuit.solve(&trajectory.values(time))?;
        }
        for (index, leaf) in model.triggers.iter().enumerate() {
            if !scope.includes(model, index) || model.dynamic_guards[index] {
                continue;
            }
            if held
                .as_ref()
                .is_some_and(|h| h.after.is_some() && !h.changed[index])
            {
                continue;
            }
            let event = &model.program.events[leaf.event];
            let EventTrigger::Cross {
                guard, direction, ..
            } = &leaf.trigger
            else {
                continue;
            };
            // A state-independent guard is affine on the union of the knots
            // of its nonzero input coefficients. Unrelated knots must not
            // introduce artificial near-boundary root uncertainty.
            let mut knots = trajectory.input_knots(&bounds.active_inputs(index));
            if let Some(after) = held.as_ref().and_then(|h| h.after) {
                knots.retain(|t| *t > after);
                knots.insert(0, after);
            }
            if knots.len() < 2 {
                continue;
            }
            let values: Vec<_> = knots
                .iter()
                .map(|&time| bounds.values(&trajectory.value_bounds(time))[index])
                .collect();
            let roots = trajectory
                .roots(&knots, &values, *direction)
                .map_err(|mut error| {
                    error
                        .message
                        .push_str(&format!(" at {}", event.origin.label()));
                    error
                })?;
            let source_curve = if roots.is_empty() {
                None
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
                trajectory.original_guard_curve(guard, &input_nodes)
            };
            for root in roots {
                let root = root.with_source_time(source_curve.as_ref());
                if events.len() == EVENT_BUDGET {
                    return Err(Error::new(
                        "event_budget",
                        "event calendar exceeds 1,000,000 events",
                    ));
                }
                events.push(ScheduledEvent {
                    fixed_predecessor: None,
                    time: root.bounds.hi,
                    event: index,
                    moment: Moment::Cross(root),
                });
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
                let roots = crate::dynamic_roots::isolate_history(
                    start,
                    end,
                    &mut |t| Ok(guards.local_range_impl(guard, t, &origin.instance)?.0),
                    &mut |t| Ok(guards.local_range_impl(guard, t, &origin.instance)?.1),
                    *direction,
                    precision,
                    *expression_tolerance,
                )?;
                for root in roots {
                    if events.len() >= EVENT_BUDGET {
                        return Err(Error::new(
                            "event_budget",
                            "local causal calendar exceeds event budget",
                        ));
                    }
                    let clock = I::point(anchor.start)
                        + I::point(anchor.period) * I::point(anchor.index as f64);
                    let bounds = clock + root.bounds;
                    let mut time = bounds.hi;
                    if let Some(after) = held.as_ref().and_then(|h| h.after) {
                        time = time.max(after.next_up());
                    }
                    let moment = Moment::Anchored {
                        anchor,
                        delta: root.bounds,
                        derivative: root.derivative,
                        end: trajectory.config.stop,
                        bounds,
                        history: operators.unwrap().history_certificate().unwrap(),
                    };
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
                        >= 64
                    {
                        return Err(Error::new(
                            "event_budget",
                            "bounded causal candidate calendar exceeds 64 microevents",
                        ));
                    }
                    events.push(ScheduledEvent {
                        fixed_predecessor: None,
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
                let roots = if !matches!(scope, CalendarScope::All) {
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
                };
                for root in roots {
                    if events.len() >= EVENT_BUDGET {
                        return Err(Error::new(
                            "event_budget",
                            "dynamic event calendar exceeds budget",
                        ));
                    }
                    events.push(ScheduledEvent {
                        fixed_predecessor: None,
                        time: root.bounds.hi,
                        event: index,
                        moment: Moment::Dynamic {
                            bounds: root.bounds,
                            derivative: root.derivative,
                            end: segment[1],
                        },
                    });
                }
            }
        }
    }
    for (index, leaf) in model.triggers.iter().enumerate() {
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
            trajectory.config.stop,
            model,
            held.as_ref().map(|h| h.states),
            held.as_ref().and_then(|h| h.after),
        )?;
    }
    if let Some(after) = held.as_ref().and_then(|h| h.after) {
        let retained = held.as_ref().unwrap().retained_fixed_prefix(after);
        if events.iter().any(|event| {
            event.bounds().lo <= after
                && !matches!(event.moment, Moment::Anchored {delta,..} if delta.lo > operators.and_then(Operators::local_epoch).map_or(f64::INFINITY,|(_,start)|start) && event.time>after)
                && !(event.fixed_predecessor.is_some()
                    && retained
                        .binary_search_by(|time| time.total_cmp(&event.time))
                        .is_ok()
                    && event.time > after)
        }) {
            return Err(unresolved("future event window overlaps the accepted event boundary"));
        }
    }
    events.sort_by(|a, b| {
        a.moment
            .bounds()
            .lo
            .total_cmp(&b.moment.bounds().lo)
            .then(a.event.cmp(&b.event))
    });
    let mut start = 0;
    while start < events.len() {
        // Find the whole connected enclosure cluster before attempting a
        // timer-only certificate. Mixed or state-dependent moments retain the
        // existing simultaneous-root and ambiguity checks below.
        let mut cluster_end = start + 1;
        let mut cluster_hi = events[start].bounds().hi.max(events[start].time);
        while cluster_end < events.len() && events[cluster_end].bounds().lo <= cluster_hi {
            cluster_hi = cluster_hi
                .max(events[cluster_end].bounds().hi)
                .max(events[cluster_end].time);
            cluster_end += 1;
        }
        if cluster_end > start + 1
            && events[start..cluster_end].iter().all(|e| {
                e.moment.clock().is_some()
                    || matches!(e.moment, Moment::Cross(_) | Moment::Anchored { .. })
            })
            && events[start..cluster_end].iter().all(|a| {
                events[start..cluster_end]
                    .iter()
                    .all(|b| certified_order(a, b, model).is_some())
            })
        {
            let next_lower = events.get(cluster_end).map(|e| e.bounds().lo);
            order_fixed_timers(
                &mut events[start..cluster_end],
                model,
                trajectory.config.stop,
                next_lower,
            )?;
            start = cluster_end;
            continue;
        }
        let mut end = start + 1;
        let mut time = events[start].time;
        // Include uncertain nominal times on either side of the chosen time.
        let mut hi = events[start].moment.bounds().hi;
        while end < events.len() && events[end].moment.bounds().lo <= hi.max(time) {
            let first = &events[start];
            let next = &events[end];
            let same_guard = match (
                &model.triggers[first.event].trigger,
                &model.triggers[next.event].trigger,
            ) {
                (EventTrigger::Cross { guard: a, .. }, EventTrigger::Cross { guard: b, .. }) => {
                    a == b
                        || (!model.dynamic_guards[first.event]
                            && !model.dynamic_guards[next.event]
                            && bounds
                                .as_ref()
                                .is_some_and(|b| b.same_zero_set(first.event, next.event)))
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
            if !first.moment.coincides(&next.moment, same_guard) {
                return Err(unresolved(
                    "cannot certify ordering of distinct events with overlapping time bounds",
                ));
            }
            time = time.max(next.time);
            hi = hi.max(next.moment.bounds().hi);
            end += 1;
        }
        for event in &mut events[start..end] {
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
    fn unrepresentable_or_outside_representatives_fail_closed() {
        let m = model();
        let close = || vec![event(1., 1., 1.5), event(1.1, 1., 1.5)];
        for (stop, next) in [(1.5, None), (2., Some(1.5_f64.next_up()))] {
            let error = order_fixed_timers(&mut close(), &m, stop, next)
                .err()
                .unwrap();
            assert_eq!(error.kind, "event_resolution");
        }
        let mut overflow = vec![
            event(f64::MAX.next_down(), f64::MAX.next_down(), f64::MAX),
            event(f64::MAX, f64::MAX, f64::MAX),
        ];
        // Allow the first representative. The second needs next_up(MAX), never infinity.
        let mut wide = model();
        if let EventTrigger::Timer { time_tolerance, .. } = &mut wide.triggers[0].trigger {
            *time_tolerance = f64::MAX;
        }
        assert_eq!(
            order_fixed_timers(&mut overflow, &wide, f64::MAX, None)
                .err()
                .unwrap()
                .kind,
            "event_resolution"
        );
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
