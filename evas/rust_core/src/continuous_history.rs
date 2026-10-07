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
            && self.event_seed == other.event_seed
    }

    pub(crate) fn event_bounds(&self, window: I) -> Result<Vec<I>, Error> {
        if window.lo < self.start && window.hi == self.start {
            let segment = self.segments.first().ok_or_else(|| {
                Error::new(
                    "event_resolution",
                    "no linear candidate segment for event sample",
                )
            })?;
            let mut forcing = segment.initial.clone();
            let (sources, slopes) = self.context.trajectory.range(window)?;
            let count = self.initial.len();
            forcing[count..count + sources.len()].copy_from_slice(&sources);
            forcing[count + sources.len()..count + 2 * sources.len()].copy_from_slice(&slopes);
            segment
                .values
                .iter()
                .map(|row| dot(row, &forcing, "linear event sample"))
                .collect()
        } else if window.lo < self.start {
            let physical = self.ordered_event_state(window)?;
            let segment = &self.segments[0];
            let mut forcing = segment.initial.clone();
            let count = self.initial.len();
            forcing[..count].copy_from_slice(&physical);
            let (sources, slopes) = self.context.trajectory.range(window)?;
            forcing[count..count + sources.len()].copy_from_slice(&sources);
            forcing[count + sources.len()..count + 2 * sources.len()].copy_from_slice(&slopes);
            segment
                .values
                .iter()
                .map(|row| dot(row, &forcing, "ordered event sample"))
                .collect()
        } else {
            self.range_bounds(window)
        }
    }

    /// Enclose the physical states at a later, already ordered event whose
    /// nominal window reaches behind the prior representative. The saved
    /// post-map state is at tau, not b: propagate for every possible duration
    /// from tau to this observation. Ordinary trajectory queries cannot use
    /// this enclosure because they have no proof of being after that event.
    fn ordered_event_state(&self, window: I) -> Result<Vec<I>, Error> {
        let (prior, physical) = self.event_seed.as_ref().ok_or_else(|| {
            Error::new(
                "event_resolution",
                "ordered event has no physical history enclosure",
            )
        })?;
        if window.lo < prior.lo || window.hi < self.start {
            return Err(Error::new(
                "event_resolution",
                "ordered event exceeds retained history coverage",
            ));
        }
        if self
            .context
            .trajectory
            .knots
            .iter()
            .any(|&knot| knot > prior.lo && knot <= window.hi && knot < self.stop)
        {
            return Err(Error::new(
                "event_resolution",
                "ordered event history crosses a PWL slope boundary",
            ));
        }
        let segment = &self.segments[0];
        let count = physical.len();
        let mut initial = segment.initial.clone();
        initial[..count].copy_from_slice(physical);
        // Source values belong to the actual prior event window, not b.
        let (sources, slopes) = self.context.trajectory.range(*prior)?;
        initial[count..count + sources.len()].copy_from_slice(&sources);
        initial[count + sources.len()..count + 2 * sources.len()].copy_from_slice(&slopes);
        let values = crate::state_space::propagate(
            &segment.matrix,
            &initial,
            I {
                lo: 0.0,
                hi: (I::point(window.hi) - I::point(prior.lo)).hi,
            },
        )?;
        Ok(values[..count].to_vec())
    }

    pub(crate) fn restarted(
        &self,
        time: f64,
        time_bounds: I,
        parameters: &[I],
    ) -> Result<Self, Error> {
        self.event_candidate(time, time_bounds, parameters, true)
    }

    pub(crate) fn mapped_event(
        &self,
        time: f64,
        time_bounds: I,
        parameters: &[I],
    ) -> Result<Self, Error> {
        self.event_candidate(time, time_bounds, parameters, false)
    }

    fn event_candidate(
        &self,
        time: f64,
        time_bounds: I,
        parameters: &[I],
        propagate_to_representative: bool,
    ) -> Result<Self, Error> {
        if !self.event_dependent || self.parameters == parameters {
            return Ok(self.clone());
        }
        if !time.is_finite() || !time_bounds.finite() || time_bounds.hi != time {
            return Err(Error::new(
                "event_resolution",
                "linear event representative must be the upper endpoint of its time enclosure",
            ));
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
        let mut physical = if time_bounds.lo < self.start {
            self.ordered_event_state(time_bounds)?
                .into_iter()
                .map(Some)
                .collect()
        } else {
            vec![None::<I>; self.initial.len()]
        };
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
        // build applies the final held reset map. Save that physical state
        // before adding any propagation to the representative.
        let event_seed = (time_bounds, next.initial.clone());
        if propagate_to_representative && time_bounds.lo != time_bounds.hi {
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
        next.event_seed = Some(event_seed);
        Ok(next)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn interior_event_representative_is_not_a_certified_forward_restart() {
        let origin = serde_json::json!({"source":"window.va","line":1,"column":1,"instance":"dut"});
        let program: Program = serde_json::from_value(serde_json::json!({
            "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","y"],
            "states":[{"instance":"dut","name":"q","kind":"integer","initial":0}],
            "operators":[{"kind":"idt","input":{"op":"state","state":0},"ic":0,"origin":origin}],
            "contributions":[{"branch":{"instance":"dut","local_positive":"y","local_negative":"r","kind":"voltage"},
                "positive":1,"negative":0,"rhs":{"op":"operator","operator":0},"origin":origin}]
        })).unwrap();
        let trajectory = Trajectory::new(
            crate::ir::TransientInputs {
                pwl: vec![],
                output_times: vec![0.0, 1.0],
                stop: 1.0,
                max_step: 1.0,
            },
            0,
        )
        .unwrap();
        let base = LinearContinuous::new(&program, &trajectory, &[], &[0.0])
            .unwrap()
            .unwrap();
        let original = base.bounds(1.0).unwrap();
        let window = I { lo: 0.25, hi: 0.75 };
        // With q:0->1 at tau=.75, y(1)=.25. Forward-only propagation
        // from representative .5 instead gives [.5,.75], excluding .25.
        assert!(base.restarted(0.5, window, &[I::ONE]).is_err());
        assert_eq!(base.bounds(1.0).unwrap(), original);
        let candidate = base.restarted(window.hi, window, &[I::ONE]).unwrap();
        let at_stop = candidate.bounds(1.0).unwrap()[0];
        assert!(at_stop.lo <= 0.25 && at_stop.hi >= 0.75);
    }
}
