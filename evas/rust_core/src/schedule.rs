//! Immutable event calendar. Nominal timer times never accumulate accepted steps.
use crate::event_accuracy::{unresolved, GuardBounds};
use crate::events::EventModel;
use crate::interval::Interval as I;
use crate::ir::{Error, EventTrigger};
use crate::operators::Operators;
use crate::pwl::{Root, Trajectory};

pub(crate) const EVENT_BUDGET: usize = 1_000_000;

pub(crate) struct ScheduledEvent {
    pub(crate) time: f64,
    pub(crate) event: usize,
    moment: Moment,
}

impl ScheduledEvent {
    pub(crate) fn bounds(&self) -> I {
        self.moment.bounds()
    }
}

enum Moment {
    Cross(Root),
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
}

impl Moment {
    fn bounds(&self) -> I {
        match self {
            Self::Cross(root) => root.bounds,
            Self::Dynamic { bounds, .. } => *bounds,
            Self::Timer { bounds, .. } => *bounds,
        }
    }

    fn coincides(&self, other: &Self, same_guard: bool) -> bool {
        let bounds = self.bounds();
        if bounds.lo == bounds.hi && bounds == other.bounds() {
            return true;
        }
        match (self, other) {
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
            _ => false,
        }
    }

    fn accepts(&self, time: f64, trigger: &EventTrigger) -> bool {
        match (self, trigger) {
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
            _ => false,
        }
    }
}

fn add_timer(
    events: &mut Vec<ScheduledEvent>,
    event: usize,
    trigger: &EventTrigger,
    stop: f64,
) -> Result<(), Error> {
    let EventTrigger::Timer {
        start,
        period,
        enabled,
        ..
    } = trigger
    else {
        return Ok(());
    };
    if !enabled || *start > stop {
        return Ok(());
    }
    if *period > 0.0 {
        let remaining = EVENT_BUDGET - events.len();
        let excess = I::point(*start) + I::point(remaining as f64) * I::point(*period);
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
        // enclosure covers both product and sum; mul_add chooses one rounded
        // representative of the real start + index * period, not prior time + T.
        let bounds = if index == 0 {
            I::point(*start)
        } else {
            I::point(*start) + I::point(index as f64) * I::point(*period)
        };
        let time = if index == 0 {
            *start
        } else {
            (index as f64).mul_add(*period, *start)
        };
        if time == f64::INFINITY {
            // All operands are nonnegative: this and every later nominal time
            // are beyond finite stop. No overflowing event is accepted.
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
            time,
            event,
            moment: Moment::Timer {
                bounds,
                start: *start,
                period: *period,
                index,
            },
        });
        previous = Some(time);
        if *period <= 0.0 || bounds == I::point(stop) {
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
    let mut events = Vec::new();
    // A timer-only network needs no guard trajectory certification.
    let bounds = if model.guards.iter().any(Option::is_some) {
        Some(GuardBounds::new(
            &model.program,
            &model.driven,
            &model.dynamic_guards,
        )?)
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
            if model.dynamic_guards[index] {
                continue;
            }
            let event = &model.program.events[leaf.event];
            let EventTrigger::Cross { direction, .. } = &leaf.trigger else {
                continue;
            };
            // A state-independent guard is affine on the union of the knots
            // of its nonzero input coefficients. Unrelated knots must not
            // introduce artificial near-boundary root uncertainty.
            let knots = trajectory.input_knots(&bounds.active_inputs(index));
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
            for root in roots {
                if events.len() == EVENT_BUDGET {
                    return Err(Error::new(
                        "event_budget",
                        "event calendar exceeds 1,000,000 events",
                    ));
                }
                events.push(ScheduledEvent {
                    time: root.bounds.hi,
                    event: index,
                    moment: Moment::Cross(root),
                });
            }
        }
    }
    if model.dynamic_guards.iter().any(|&g| g) {
        let guards = crate::guard_trajectory::GuardTrajectory::new(model, trajectory, operators)?;
        for (index, leaf) in model.triggers.iter().enumerate() {
            if !model.dynamic_guards[index] {
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
            for segment in trajectory.knots.windows(2) {
                let roots = crate::dynamic_roots::isolate(
                    segment[0],
                    segment[1],
                    &mut |t| Ok(guards.range(guard, t, &origin.instance)?.0),
                    &mut |t| Ok(guards.range(guard, t, &origin.instance)?.1),
                    *direction,
                    *time_tolerance,
                    *expression_tolerance,
                )?;
                for root in roots {
                    if events.len() >= EVENT_BUDGET {
                        return Err(Error::new(
                            "event_budget",
                            "dynamic event calendar exceeds budget",
                        ));
                    }
                    events.push(ScheduledEvent {
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
        add_timer(&mut events, index, &leaf.trigger, trajectory.config.stop)?;
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
