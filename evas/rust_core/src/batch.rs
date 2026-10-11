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
        let result = join_workers(handles, samples.len());
        if let Some(error) = spawn_error {
            Err(error)
        } else {
            result
        }
    })
}

fn join_workers(
    handles: Vec<thread::ScopedJoinHandle<'_, Result<Vec<Solution>, Error>>>,
    samples: usize,
) -> Result<Vec<Solution>, Error> {
    let mut result = Ok(Vec::with_capacity(samples));
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
    result
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicBool, Ordering};

    #[test]
    fn actual_worker_panic_is_reported_after_joining_every_worker() {
        let completed = AtomicBool::new(false);
        let error = thread::scope(|scope| {
            let failed = scope.spawn(|| panic!("test-only worker fault"));
            let successor = scope.spawn(|| {
                completed.store(true, Ordering::SeqCst);
                Ok(Vec::new())
            });
            join_workers(vec![failed, successor], 2).unwrap_err()
        });
        assert!(completed.load(Ordering::SeqCst));
        let payload = serde_json::to_value(error).unwrap();
        assert_eq!(payload["kind"], "worker_failure");
        assert_eq!(payload["message"], "static worker panicked");
        assert_eq!(payload["sample"], serde_json::Value::Null);
    }

    #[test]
    fn first_input_error_wins_over_later_worker_panic() {
        let error = thread::scope(|scope| {
            let first = scope.spawn(|| Err(Error::new("nonfinite_arithmetic", "first input")));
            let later = scope.spawn(|| panic!("test-only later fault"));
            join_workers(vec![first, later], 2).unwrap_err()
        });
        assert_eq!(error.kind, "nonfinite_arithmetic");
        assert_eq!(error.message, "first input");
    }
}
