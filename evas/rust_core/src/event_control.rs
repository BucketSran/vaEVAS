//! Admission boundaries for compact event-only control IR.
use crate::ir::{Error, Program};
use serde_json::Value;

pub(crate) fn validate(program: &Program) -> Result<(), Error> {
    let mut value =
        serde_json::to_value(program).map_err(|e| Error::new("invalid_ir", e.to_string()))?;
    let mut stack = vec![(&value, 0usize)];
    let mut items = 0usize;
    while let Some((v, depth)) = stack.pop() {
        items += 1;
        if items > 100_000 || depth + usize::from(v.is_array() || v.is_object()) > 96 {
            return Err(Error::new(
                "resource_budget",
                "IR exceeds 100000 values/containers or depth96",
            ));
        }
        match v {
            Value::Object(m) => stack.extend(m.values().map(|x| (x, depth + 1))),
            Value::Array(a) => stack.extend(a.iter().map(|x| (x, depth + 1))),
            _ => {}
        }
    }
    fn event_only(v: &Value) -> bool {
        match v {
            Value::Object(m) => {
                m.get("op").and_then(Value::as_str).is_some_and(|op| {
                    matches!(
                        op,
                        "integer_primitive" | "checked_index" | "checked_integer" | "array_read"
                    )
                }) || m.values().any(event_only)
            }
            Value::Array(a) => a.iter().any(event_only),
            _ => false,
        }
    }
    let events = value
        .as_object_mut()
        .unwrap()
        .remove("events")
        .unwrap_or(Value::Null);
    if event_only(&value) {
        return Err(Error::new(
            "unsupported_analysis",
            "checked integer/index and array access require an isolated observer event body",
        ));
    }
    if let Value::Array(events) = events {
        for event in events {
            if event.get("trigger").is_some_and(event_only) {
                return Err(Error::new(
                    "unsupported_analysis",
                    "checked event arithmetic cannot appear in an event trigger",
                ));
            }
        }
    }
    Ok(())
}
