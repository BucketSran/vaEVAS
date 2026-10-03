//! Parallelism is restricted to independent static inputs, not physical time.
use crate::ir::{Error, Solution};
use crate::solver::Circuit;
use std::thread;

fn chunk(circuit: &Circuit, samples: &[Vec<f64>], start: usize) -> Result<Vec<Solution>, Error> {
    samples
        .iter()
        .enumerate()
        .map(|(index, inputs)| {
            circuit.solve(inputs).map_err(|mut error| {
                error.sample = Some(start + index);
                error
            })
        })
        .collect()
}

pub(crate) fn solve(
    circuit: &Circuit,
    samples: &[Vec<f64>],
    workers: usize,
) -> Result<Vec<Solution>, Error> {
    let workers = workers.min(samples.len());
    if workers <= 1 {
        return chunk(circuit, samples, 0);
    }
    let width = samples.len().div_ceil(workers);
    thread::scope(|scope| {
        let mut handles = Vec::with_capacity(workers);
        let mut spawn_error = None;
        for (index, samples) in samples.chunks(width).enumerate() {
            match thread::Builder::new()
                .spawn_scoped(scope, move || chunk(circuit, samples, index * width))
            {
                Ok(handle) => handles.push(handle),
                Err(error) => {
                    spawn_error = Some(Error::new("worker_start", error.to_string()));
                    break;
                }
            }
        }
        let mut result = Ok(Vec::with_capacity(samples.len()));
        // Join in input order and join every worker even after a failure.
        // OnceLock coordinates the first affine factorization; no sample state
        // is shared, and no partial response escapes.
        for handle in handles {
            let next = handle
                .join()
                .unwrap_or_else(|_| Err(Error::new("worker_failure", "static worker panicked")));
            match (&mut result, next) {
                (Ok(all), Ok(mut part)) => all.append(&mut part),
                (Ok(_), Err(error)) => result = Err(error),
                (Err(_), _) => {}
            }
        }
        if let Some(error) = spawn_error {
            Err(error)
        } else {
            result
        }
    })
}
