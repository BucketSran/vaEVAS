//! Optional observations. This module never evaluates or commits model state.
use crate::ir::Error;
use serde::Serialize;
use std::{cell::RefCell, collections::BTreeMap, time::Instant};

#[derive(Clone, Copy)]
pub struct Options {
    pub max_records: usize,
    pub max_record_bytes: usize,
}

impl Default for Options {
    fn default() -> Self {
        Self {
            max_records: 2048,
            max_record_bytes: 1024 * 1024,
        }
    }
}

#[derive(Default, Serialize)]
pub struct Timing {
    pub calls: u64,
    /// Inclusive elapsed time; nested stages overlap and must not be summed.
    pub nanos: u64,
}

#[derive(Serialize)]
pub struct Record {
    pub kind: &'static str,
    pub outcome: &'static str,
    pub start: Option<f64>,
    pub end: Option<f64>,
    pub count: usize,
    pub reason: Option<String>,
}

#[derive(Serialize)]
pub struct Report {
    pub diagnostic_version: u32,
    pub status: &'static str,
    /// Scoped to the caller thread. Parallel static worker internals are excluded.
    pub coverage: &'static str,
    pub stages: BTreeMap<&'static str, Timing>,
    pub counters: BTreeMap<&'static str, u64>,
    pub records: Vec<Record>,
    pub truncated: bool,
    pub dropped_records: u64,
    pub record_bytes: usize,
    pub max_records: usize,
    pub max_record_bytes: usize,
    pub error: Option<serde_json::Value>,
}

thread_local! {
    static ACTIVE: RefCell<Option<Report>> = const { RefCell::new(None) };
}

struct Restore(Option<Report>);
impl Drop for Restore {
    fn drop(&mut self) {
        ACTIVE.with(|slot| *slot.borrow_mut() = self.0.take());
    }
}

/// Collect one operation, including failures. Nested captures restore the parent;
/// unwinding restores it too. No report is a certificate of numerical acceptance.
pub fn capture<T>(
    options: Options,
    operation: impl FnOnce() -> Result<T, Error>,
) -> (Result<T, Error>, Report) {
    let _restore = Restore(ACTIVE.with(|slot| {
        slot.replace(Some(Report {
            diagnostic_version: 1,
            status: "running",
            coverage: "calling_thread_only",
            stages: BTreeMap::new(),
            counters: BTreeMap::new(),
            records: Vec::new(),
            truncated: false,
            dropped_records: 0,
            record_bytes: 0,
            max_records: options.max_records.min(65536),
            max_record_bytes: options.max_record_bytes.min(8 * 1024 * 1024),
            error: None,
        }))
    }));
    let result = operation();
    let mut report = ACTIVE.with(|slot| slot.borrow_mut().take().unwrap());
    report.status = if result.is_ok() { "complete" } else { "failed" };
    if let Err(error) = &result {
        report.error = Some(serde_json::to_value(error).unwrap());
    }
    (result, report)
}

pub struct Span {
    name: &'static str,
    started: Option<Instant>,
}

pub fn span(name: &'static str) -> Span {
    Span {
        name,
        started: ACTIVE.with(|slot| slot.borrow().is_some().then(Instant::now)),
    }
}

impl Drop for Span {
    fn drop(&mut self) {
        if let Some(started) = self.started {
            let elapsed = started.elapsed().as_nanos().min(u64::MAX as u128) as u64;
            ACTIVE.with(|slot| {
                if let Some(report) = slot.borrow_mut().as_mut() {
                    let timing = report.stages.entry(self.name).or_default();
                    timing.calls = timing.calls.saturating_add(1);
                    timing.nanos = timing.nanos.saturating_add(elapsed);
                }
            });
        }
    }
}

pub(crate) fn counter(name: &'static str, value: usize) {
    ACTIVE.with(|slot| {
        if let Some(report) = slot.borrow_mut().as_mut() {
            let count = report.counters.entry(name).or_default();
            *count = count.saturating_add(value as u64);
        }
    });
}

pub(crate) fn record(
    kind: &'static str,
    outcome: &'static str,
    start: Option<f64>,
    end: Option<f64>,
    count: usize,
    reason: Option<&str>,
) {
    ACTIVE.with(|slot| {
        if let Some(report) = slot.borrow_mut().as_mut() {
            if report.records.len() >= report.max_records
                || report.record_bytes >= report.max_record_bytes
            {
                report.truncated = true;
                report.dropped_records = report.dropped_records.saturating_add(1);
                return;
            }
            // Time bounds come from already computed observations. Never export
            // a NaN/Inf as a JSON number, including on failed trials.
            let record = Record {
                kind,
                outcome,
                start: start.filter(|t| t.is_finite()),
                end: end.filter(|t| t.is_finite()),
                count,
                reason: reason.map(|s| s.chars().take(1024).collect()),
            };
            let bytes = serde_json::to_vec(&record).unwrap().len();
            if report.records.len() < report.max_records
                && bytes <= report.max_record_bytes.saturating_sub(report.record_bytes)
            {
                report.record_bytes += bytes;
                report.records.push(record);
            } else {
                report.truncated = true;
                report.dropped_records = report.dropped_records.saturating_add(1);
            }
        }
    });
}

/// Structured detail inside the existing bounded, optional record format.
/// Recovery never reads this report; disabling or truncating it changes no work.
pub(crate) fn detail(
    kind: &'static str,
    outcome: &'static str,
    time: Option<f64>,
    value: &impl Serialize,
) {
    if ACTIVE.with(|slot| slot.borrow().is_some()) {
        record(
            kind,
            outcome,
            time,
            time,
            1,
            Some(&serde_json::to_string(value).unwrap()),
        );
    }
}

/// Observe a candidate result without modifying or translating it.
pub(crate) fn outcome<T>(
    kind: &'static str,
    time: f64,
    result: Result<T, Error>,
) -> Result<T, Error> {
    if let Err(error) = &result {
        record(kind, "rejected", Some(time), None, 1, Some(&error.message));
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bounded_failure_and_nested_capture_restore_parent() {
        let (_, report) = capture(
            Options {
                max_records: 1,
                max_record_bytes: 1024,
            },
            || {
                record("trial", "accepted", Some(0.0), Some(1.0), 1, None);
                let (_, nested) = capture(Options::default(), || {
                    counter("nested", 1);
                    Ok(())
                });
                assert_eq!(nested.counters["nested"], 1);
                record(
                    "trial",
                    "rejected",
                    Some(f64::NAN),
                    None,
                    1,
                    Some("test rejection"),
                );
                Err::<(), _>(Error::new("test_failure", "unchanged"))
            },
        );
        assert_eq!(report.status, "failed");
        assert_eq!(report.records.len(), 1);
        assert_eq!(report.dropped_records, 1);
        assert!(report.truncated);
        assert!(report.counters.is_empty());
        assert!(serde_json::to_string(&report).is_ok());
        assert!(ACTIVE.with(|slot| slot.borrow().is_none()));
    }

    #[test]
    fn byte_budget_and_unwind_cleanup() {
        let (_, report) = capture(
            Options {
                max_records: 10,
                max_record_bytes: 1,
            },
            || {
                record("trial", "accepted", None, None, 0, None);
                Ok(())
            },
        );
        assert!(report.records.is_empty());
        assert!(report.truncated);
        let _ = std::panic::catch_unwind(|| {
            capture(Options::default(), || -> Result<(), Error> {
                panic!("test")
            })
        });
        assert!(ACTIVE.with(|slot| slot.borrow().is_none()));
    }
}
