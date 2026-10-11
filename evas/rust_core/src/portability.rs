//! Read-only notices derived solely from committed event certificates and queries.
use crate::ir::{
    ModelPortabilityAdvisory, OperatorSpec, PortabilityAdvisories, PortabilityAdvisory, Program,
    TransientTrace,
};
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

pub(crate) fn modulo_sources(program: &Program) -> Vec<(usize, String)> {
    program
        .operators
        .iter()
        .enumerate()
        .filter(|(_, op)| matches!(op, OperatorSpec::IdtMod { .. }))
        .map(|(index, op)| (index, op.origin().label()))
        .collect()
}

pub(crate) fn collect(
    trace: Option<&TransientTrace>,
    strobes: Option<&[f64]>,
    modulo: &[(usize, String)],
) -> Option<PortabilityAdvisories> {
    let trace = trace?;
    let mut records = Vec::new();
    let mut dropped_records = 0;
    for (event_record, event) in trace.events.iter().enumerate() {
        let certificates: Vec<_> = if event.kind == "cross" || event.kind == "timer" {
            vec![(
                0,
                event.kind,
                event
                    .observation_time_bounds
                    .unwrap_or([event.time, event.time]),
            )]
        } else {
            event
                .fired_triggers
                .iter()
                .filter(|f| f.kind == "cross" || f.kind == "timer")
                .filter_map(|f| f.time_bounds.map(|b| (f.trigger, f.kind, b)))
                .collect()
        };
        for (trigger, kind, bounds) in certificates {
            let [lo, hi] = bounds;
            // A broad cross certificate cannot establish root proximity. A
            // timer notice names its committed deadline enclosure, not a root.
            if !lo.is_finite()
                || !hi.is_finite()
                || lo < 0.0
                || lo > hi
                || (kind == "cross" && hi > next_up(lo))
            {
                continue;
            }
            let (code, message) = if kind == "cross" {
                ("cross_observation_boundary", MESSAGE)
            } else {
                ("timer_observation_boundary", "Observation is inside or within one binary64 neighbor of a committed timer deadline enclosure. A backend may trigger elsewhere within the model's timing tolerance. Check samples and downstream history against their budgets; this notice neither proves a mismatch nor accepts a changed final result.")
            };
            for (query_source, times) in [
                ("output_times", trace.times.as_slice()),
                ("strobetimes", strobes.unwrap_or(&[])),
            ] {
                let start = times.partition_point(|t| *t < next_down(lo));
                let end = times.partition_point(|t| *t <= next_up(hi));
                let retain = (LIMIT - records.len()).min(end - start);
                dropped_records += end - start - retain;
                for (query_index, &query_time_s) in
                    times.iter().enumerate().skip(start).take(retain)
                {
                    records.push(PortabilityAdvisory {
                        code,
                        nonblocking: true,
                        message,
                        event_record,
                        event: event.event,
                        trigger,
                        origin: event.origin.clone(),
                        query_source,
                        query_index,
                        query_time_s,
                        time_bounds_s: bounds,
                    });
                }
            }
        }
    }
    let retain = (LIMIT - records.len()).min(modulo.len());
    dropped_records += modulo.len() - retain;
    let model_records: Vec<_> = modulo.iter().take(retain).map(|(operator, origin)| ModelPortabilityAdvisory {
        code: "modulo_phase_sensitive", nonblocking: true,
        message: "This model uses idtmod. Small integration or observation-time differences near a wrap can change the reported phase side or downstream decisions. Check circular phase, ordinary output and event counts separately. This source-level notice does not establish an observed wrap, a mismatch or an accepted difference.",
        operator: *operator, origin: origin.clone(),
    }).collect();
    if records.is_empty() && model_records.is_empty() {
        return None;
    }
    Some(PortabilityAdvisories {
        schema_version: 2,
        record_limit: LIMIT,
        records,
        model_records,
        dropped_records,
        truncated: dropped_records != 0,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ir::{EventRecord, FiredTrigger};
    fn collect(trace: Option<&TransientTrace>) -> Option<PortabilityAdvisories> {
        super::collect(trace, None, &[])
    }
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
    fn or_group_requires_each_fired_leaf_certificate() {
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
        assert_eq!(result.records.len(), 2);
        assert_eq!(result.records[0].trigger, 0);
        assert_eq!(result.records[1].trigger, 1);
        assert_eq!(result.records[1].time_bounds_s, [0.5, 0.5]);
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

    #[test]
    fn observation_grids_and_model_notices_share_the_budget() {
        let data = trace([0.5, 0.5], vec![0.5]);
        let modulo: Vec<_> = (0..130).map(|i| (i, format!("test:{i}"))).collect();
        let result = super::collect(Some(&data), Some(&[0.5]), &modulo).unwrap();
        assert_eq!(result.records.len(), 2);
        assert_eq!(result.records[0].query_source, "output_times");
        assert_eq!(result.records[1].query_source, "strobetimes");
        assert_eq!(result.model_records.len(), 126);
        assert_eq!(result.dropped_records, 4);
        assert!(result.truncated);
    }
}
