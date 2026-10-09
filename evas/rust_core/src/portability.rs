//! Read-only notices derived solely from committed event certificates and queries.
use crate::ir::{PortabilityAdvisories, PortabilityAdvisory, TransientTrace};
const LIMIT: usize = 128;
const MESSAGE: &str = "Observation is within one binary64 neighbor of a committed cross root certificate. Boundary samples may depend on backend event/observation ordering; inspect nearby samples before portability comparisons. This nonblocking notice does not establish an actual backend mismatch or the exact root side.";

fn next_up(x: f64) -> f64 {
    if x == 0.0 {
        return f64::from_bits(1);
    }
    f64::from_bits(if x > 0.0 {
        x.to_bits() + 1
    } else {
        x.to_bits() - 1
    })
}
fn next_down(x: f64) -> f64 {
    -next_up(-x)
}

pub(crate) fn collect(trace: Option<&TransientTrace>) -> Option<PortabilityAdvisories> {
    let trace = trace?;
    let mut records = Vec::new();
    let mut dropped_records = 0;
    for (event_record, event) in trace.events.iter().enumerate() {
        // Ordinary cross records omit fired_triggers. OR groups retain leaf certificates.
        let roots: Vec<_> = if event.kind == "cross" {
            vec![(
                0,
                event
                    .observation_time_bounds
                    .unwrap_or([event.time, event.time]),
            )]
        } else {
            event
                .fired_triggers
                .iter()
                .filter(|f| f.kind == "cross")
                .filter_map(|f| f.time_bounds.map(|b| (f.trigger, b)))
                .collect()
        };
        for (trigger, bounds) in roots {
            let [lo, hi] = bounds;
            // A broad certificate cannot establish proximity to the root itself.
            if !lo.is_finite() || !hi.is_finite() || lo < 0.0 || lo > hi || hi > next_up(lo) {
                continue;
            }
            let lower = next_down(lo);
            let upper = next_up(hi);
            let start = trace.times.partition_point(|t| *t < lower);
            let end = trace.times.partition_point(|t| *t <= upper);
            // Count the entire matching range even after storage is exhausted.
            let retain = (LIMIT - records.len()).min(end - start);
            dropped_records += end - start - retain;
            for query_index in start..start + retain {
                records.push(PortabilityAdvisory {
                    code: "cross_observation_boundary",
                    nonblocking: true,
                    message: MESSAGE,
                    event_record,
                    event: event.event,
                    trigger,
                    origin: event.origin.clone(),
                    query_index,
                    query_time_s: trace.times[query_index],
                    root_time_bounds_s: bounds,
                });
            }
        }
    }
    if records.is_empty() {
        return None;
    }
    Some(PortabilityAdvisories {
        schema_version: 1,
        record_limit: LIMIT,
        records,
        dropped_records,
        truncated: dropped_records != 0,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ir::{EventRecord, FiredTrigger};
    fn trace(bounds: [f64; 2], times: Vec<f64>) -> TransientTrace {
        TransientTrace {
            times,
            state_names: vec![],
            states: vec![],
            accepted_steps: 0,
            discarded_trials: 0,
            events: vec![EventRecord {
                time: bounds[1],
                observation_time_bounds: Some(bounds),
                event: 0,
                origin: "test.va:1:1 (dut)".into(),
                kind: "cross",
                guard_value: Some(0.0),
                fired_triggers: vec![],
                before: vec![],
                after: vec![],
            }],
        }
    }
    #[test]
    fn broad_certificate_cannot_establish_local_proximity() {
        assert!(collect(Some(&trace([0.4, 0.6], vec![0.0, 0.5, 1.0]))).is_none());
        assert!(collect(Some(&trace([0.5, next_up(next_up(0.5))], vec![0.5]))).is_none());
        assert!(collect(None).is_none());
    }
    #[test]
    fn zero_and_subnormal_neighbors_are_finite_local_observations() {
        let result = collect(Some(&trace(
            [0.0, 0.0],
            vec![0.0, f64::from_bits(1), f64::from_bits(2)],
        )))
        .unwrap();
        assert_eq!(result.records.len(), 2);
        assert_eq!(result.records[1].query_time_s, f64::from_bits(1));
    }
    #[test]
    fn or_group_requires_a_cross_leaf_certificate() {
        let mut trace = trace([0.0, 1.0], vec![0.0, 0.5, 1.0]);
        trace.events[0].kind = "or";
        trace.events[0].fired_triggers = vec![
            FiredTrigger {
                trigger: 0,
                kind: "timer",
                guard_value: None,
                time_bounds: Some([0.5, 0.5]),
            },
            FiredTrigger {
                trigger: 1,
                kind: "cross",
                guard_value: Some(0.0),
                time_bounds: Some([0.5, 0.5]),
            },
            FiredTrigger {
                trigger: 2,
                kind: "cross",
                guard_value: Some(0.0),
                time_bounds: None,
            },
        ];
        let result = collect(Some(&trace)).unwrap();
        assert_eq!(result.records.len(), 1);
        assert_eq!(result.records[0].trigger, 1);
        assert_eq!(result.records[0].root_time_bounds_s, [0.5, 0.5]);
    }
    #[test]
    fn bounded_records_count_all_dropped_matches() {
        let mut data = trace([0.5, 0.5], vec![0.5]);
        for event in 1..140 {
            let mut record = trace([0.5, 0.5], vec![]).events.remove(0);
            record.event = event;
            data.events.push(record);
        }
        let result = collect(Some(&data)).unwrap();
        assert_eq!(result.records.len(), 128);
        assert_eq!(result.dropped_records, 12);
        assert!(result.truncated);
    }
}
