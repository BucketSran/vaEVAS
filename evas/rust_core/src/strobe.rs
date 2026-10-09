//! Normalize forced solve points, then retain the user's separate output grid.
use crate::ir::{Error, Request, Response, StrobeEvidence};

pub(crate) fn run(mut request: Request) -> Result<Response, Error> {
    let config = request.transient.as_mut().unwrap();
    if config.strobetimes.is_empty() {
        return crate::transient::run_inner(request);
    }
    // Validate the original grid before unioning: sorting must not repair a
    // malformed user request. Source knots remain independent of solve points.
    crate::pwl::Trajectory::new(config.clone(), request.driven.len())?;
    let outputs = config.output_times.clone();
    let strobes = config.strobetimes.clone();
    config.output_times.extend(&strobes);
    config.output_times.sort_by(f64::total_cmp);
    config.output_times.dedup();
    let combined = config.output_times.clone();
    let mut result = crate::transient::run_inner(request)?;
    let evidence = result.observation_evidence.as_ref().ok_or_else(|| {
        Error::new(
            "event_consistency",
            "strobe computation has no observation provenance",
        )
    })?;
    let mut receipt = StrobeEvidence {
        schema_version: 1,
        times: strobes.clone(),
        sample_origins: Vec::new(),
        voltages_v: Vec::new(),
    };
    for &time in &strobes {
        let index = combined.binary_search_by(|t| t.total_cmp(&time)).unwrap();
        let origin = evidence.sample_origins[index];
        if origin == "certified_causal_frame" {
            // That is a certified query through an atomic event cluster, not
            // proof that its continuous trajectory accepted a step here.
            return Err(Error::new(
                "unsupported_strobe",
                "forced solve point falls inside an atomic causal event cluster",
            ));
        }
        receipt.sample_origins.push(origin);
        receipt
            .voltages_v
            .push(result.solutions[index].voltages.clone());
        crate::diagnostics::record(
            "strobe_point",
            "computed",
            Some(time),
            Some(time),
            1,
            Some(origin),
        );
    }
    let keep: Vec<bool> = combined
        .iter()
        .map(|t| outputs.binary_search_by(|x| x.total_cmp(t)).is_ok())
        .collect();
    fn select<T>(values: &mut Vec<T>, keep: &[bool]) {
        let mut index = 0;
        values.retain(|_| {
            let selected = keep[index];
            index += 1;
            selected
        });
    }
    select(&mut result.solutions, &keep);
    let trace = result.transient.as_mut().unwrap();
    select(&mut trace.states, &keep);
    trace.times = outputs;
    let evidence = result.observation_evidence.as_mut().unwrap();
    select(&mut evidence.sample_origins, &keep);
    select(&mut evidence.voltage_bounds_v, &keep);
    if trace.times.first() != Some(&0.0) {
        evidence.initial_settled = None;
    }
    result.strobe_evidence = Some(receipt);
    Ok(result)
}
