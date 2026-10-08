//! Joint event candidate history: preserve physical states and rebuild only the future.
use super::*;

impl LinearContinuous {
    pub(super) fn local_from_seed(&self, horizon: f64) -> Result<Self, Error> {
        let (_, state) = self.event_seed.as_ref().ok_or_else(|| {
            Error::new("event_resolution", "local event flow lacks a physical seed")
        })?;
        let count = state.len();
        let source_count = self.context.driven.len();
        let autonomous = |row: &Vec<I>| {
            row[count..count + 2 * source_count]
                .iter()
                .all(|c| c.zero())
        };
        if self
            .segments
            .iter()
            .any(|s| !s.matrix[..count].iter().all(autonomous) || !s.values.iter().all(autonomous))
        {
            return Err(Error::new(
                "event_resolution",
                "local causal closure requires autonomous continuous flow and outputs",
            ));
        }
        let context = local_context(&self.context, horizon);
        let mut next = Self::build(context, self.parameters.clone(), 0., Some(state.clone()))?
            .ok_or_else(|| Error::new("invalid_ir", "local continuous flow disappeared"))?;
        next.exact_affine = self.exact_seed.as_ref().and_then(|seed| {
            exact_affine::History::build(
                &next.exact_states,
                &next.segments,
                0.,
                next.initial.len(),
                Some(seed.clone()),
            )
        });
        Ok(next)
    }

    pub(crate) fn changes_on_event(&self) -> bool {
        self.event_dependent
    }

    pub(crate) fn same_history(&self, other: &Self) -> bool {
        self.start == other.start
            && self.parameters == other.parameters
            && self.initial == other.initial
            && self.event_seed == other.event_seed
            && self.exact_affine == other.exact_affine
            && self.exact_seed == other.exact_seed
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
        if self.crosses_source_corner(prior.lo, window.hi) {
            return self.piecewise_event_state(physical, prior.lo, window.hi);
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

    fn crosses_source_corner(&self, lo: f64, hi: f64) -> bool {
        self.context
            .trajectory
            .knots
            .iter()
            .any(|&knot| knot > lo && knot <= hi && knot < self.stop)
    }

    // The fixed mode has one matrix across source pieces. Refill each piece's
    // source coordinates and propagate all durations up to its length. Carry
    // only physical coordinates, never apply the reset map a second time.
    fn piecewise_event_state(&self, physical: &[I], lo: f64, hi: f64) -> Result<Vec<I>, Error> {
        let segment = self
            .segments
            .first()
            .ok_or_else(|| Error::new("event_resolution", "no linear segment for event bridge"))?;
        let count = physical.len();
        let mut state = physical.to_vec();
        let mut cuts = vec![lo];
        cuts.extend(
            self.context
                .trajectory
                .knots
                .iter()
                .copied()
                .filter(|&t| t > lo && t < hi),
        );
        cuts.push(hi);
        for pair in cuts.windows(2) {
            let (source, slopes) = self.context.trajectory.range(I {
                lo: pair[0],
                hi: pair[1],
            })?;
            let mut initial = segment.initial.clone();
            initial[..count].copy_from_slice(&state);
            initial[count..count + source.len()].copy_from_slice(&source);
            initial[count + source.len()..count + 2 * source.len()].copy_from_slice(&slopes);
            state = crate::state_space::propagate(
                &segment.matrix,
                &initial,
                I {
                    lo: 0.0,
                    hi: (I::point(pair[1]) - I::point(pair[0])).hi,
                },
            )?[..count]
                .to_vec();
        }
        Ok(state)
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
        // Only a proved point event can carry an exact seed into changed flow.
        // The interval propagation above remains the numerical history authority.
        let exact_seed = (time_bounds.lo == time_bounds.hi)
            .then(|| self.exact_affine.as_ref()?.states_at(time))
            .flatten();
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
            let physical = if next.crosses_source_corner(time_bounds.lo, time) {
                next.piecewise_event_state(&next.initial, time_bounds.lo, time)?
            } else {
                crate::state_space::propagate(
                    &segment.matrix,
                    &initial,
                    I {
                        lo: 0.0,
                        hi: (I::point(time) - I::point(time_bounds.lo)).hi,
                    },
                )?[..count]
                    .to_vec()
            };
            next = Self::build(
                self.context.clone(),
                parameters.to_vec(),
                time,
                Some(physical),
            )?
            .unwrap();
        }
        next.exact_affine = exact_seed.as_ref().and_then(|seed| {
            exact_affine::History::build(
                &next.exact_states,
                &next.segments,
                time,
                next.initial.len(),
                Some(seed.clone()),
            )
        });
        next.exact_seed = exact_seed;
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
        assert!(base.exact_affine.is_some());
        let window = I { lo: 0.25, hi: 0.75 };
        // With q:0->1 at tau=.75, y(1)=.25. Forward-only propagation
        // from representative .5 instead gives [.5,.75], excluding .25.
        assert!(base.restarted(0.5, window, &[I::ONE]).is_err());
        assert_eq!(base.bounds(1.0).unwrap(), original);
        let candidate = base.restarted(window.hi, window, &[I::ONE]).unwrap();
        assert!(candidate.exact_affine.is_none());
        assert!(candidate.exact_seed.is_none());
        assert!(base.exact_affine.is_some());
        let at_stop = candidate.bounds(1.0).unwrap()[0];
        assert!(at_stop.lo <= 0.25 && at_stop.hi >= 0.75);
    }
    #[test]
    fn exact_affine_provenance_rejects_reset_and_feedback() {
        let origin = serde_json::json!({"source":"proof.va","line":1,"column":1,"instance":"dut"});
        let program:Program=serde_json::from_value(serde_json::json!({
            "schema_version":crate::ir::SCHEMA_VERSION,"nodes":["0","z"],
            "states":[{"instance":"dut","name":"q","kind":"real","initial":3}],
            "operators":[{"kind":"idt","input":{"op":"state","state":0},"ic":1,"origin":origin}],
            "contributions":[{"branch":{"instance":"dut","local_positive":"z","local_negative":"r","kind":"voltage"},
                "positive":1,"negative":0,"rhs":{"op":"operator","operator":0},"origin":origin}]
        })).unwrap();
        let trajectory = Trajectory::new(
            crate::ir::TransientInputs {
                pwl: vec![],
                output_times: vec![0., 1.],
                stop: 1.,
                max_step: 1.,
            },
            0,
        )
        .unwrap();
        let base = LinearContinuous::new(&program, &trajectory, &[], &[3.])
            .unwrap()
            .unwrap();
        assert!(base.exact_affine.is_some());
        let mut reset = program.clone();
        if let OperatorSpec::Idt { reset, .. } = &mut reset.operators[0] {
            *reset = Some(Expression::State { state: 0 });
        }
        assert!(LinearContinuous::new(&reset, &trajectory, &[], &[3.])
            .unwrap()
            .unwrap()
            .exact_affine
            .is_none());
        let mut feedback = program;
        if let OperatorSpec::Idt { input, .. } = &mut feedback.operators[0] {
            *input = Expression::Operator { operator: 0 };
        }
        assert!(LinearContinuous::new(&feedback, &trajectory, &[], &[3.])
            .unwrap()
            .unwrap()
            .exact_affine
            .is_none());
    }
}
