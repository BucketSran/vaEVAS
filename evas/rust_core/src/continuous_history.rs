//! Joint event candidate history: preserve physical states and rebuild only the future.
use super::*;

impl LinearContinuous {
    pub(crate) fn changes_on_event(&self) -> bool {
        self.event_dependent
    }

    pub(crate) fn same_history(&self, other: &Self) -> bool {
        self.start == other.start
            && self.parameters == other.parameters
            && self.initial == other.initial
    }

    pub(crate) fn restarted(
        &self,
        time: f64,
        time_bounds: I,
        parameters: &[I],
    ) -> Result<Self, Error> {
        if !self.event_dependent || self.parameters == parameters {
            return Ok(self.clone());
        }
        if time_bounds.lo != time_bounds.hi
            && self
                .context
                .trajectory
                .knots
                .iter()
                .any(|&knot| knot > time_bounds.lo && knot <= time && knot < self.stop)
        {
            return Err(Error::new(
                "event_resolution",
                "joint event-time enclosure crosses a PWL slope boundary",
            ));
        }
        let mut physical = vec![None::<I>; self.initial.len()];
        if time_bounds.lo == 0.0 {
            for (slot, value) in physical.iter_mut().zip(&self.initial) {
                *slot = Some(*value);
            }
        }
        for segment in &self.segments {
            let lo = time_bounds.lo.max(segment.start);
            let hi = time_bounds.hi.min(segment.end);
            if lo > hi {
                continue;
            }
            let values = crate::state_space::propagate(
                &segment.matrix,
                &segment.initial,
                I { lo, hi } - I::point(segment.start),
            )?;
            for (slot, value) in physical.iter_mut().zip(values) {
                *slot = Some(slot.map_or(value, |prior| prior.hull(value)));
            }
        }
        let physical = physical
            .into_iter()
            .map(|v| {
                v.ok_or_else(|| {
                    Error::new(
                        "event_resolution",
                        "joint history cannot enclose event time",
                    )
                })
            })
            .collect::<Result<Vec<_>, _>>()?;
        let mut next = Self::build(
            self.context.clone(),
            parameters.to_vec(),
            time,
            Some(physical),
        )?
        .ok_or_else(|| {
            Error::new(
                "invalid_ir",
                "continuous network disappeared during event replay",
            )
        })?;
        if time_bounds.lo != time_bounds.hi {
            // Enclose post-event propagation from any actual event in its root
            // box to the representative time. Prior and future dynamics both
            // participate; no event-time uncertainty is silently discarded.
            let segment = &next.segments[0];
            let mut initial = segment.initial.clone();
            let count = self.initial.len();
            let mut times = vec![time_bounds.lo, time_bounds.hi];
            times.extend(
                self.context
                    .trajectory
                    .knots
                    .iter()
                    .copied()
                    .filter(|t| *t > time_bounds.lo && *t < time_bounds.hi),
            );
            for t in times {
                for (slot, value) in initial[count..]
                    .iter_mut()
                    .zip(self.context.trajectory.value_bounds(t))
                {
                    *slot = slot.hull(value);
                }
            }
            let propagated = crate::state_space::propagate(
                &segment.matrix,
                &initial,
                I {
                    lo: 0.0,
                    hi: (I::point(time) - I::point(time_bounds.lo)).hi,
                },
            )?;
            next = Self::build(
                self.context.clone(),
                parameters.to_vec(),
                time,
                Some(propagated[..count].to_vec()),
            )?
            .unwrap();
        }
        Ok(next)
    }
}
