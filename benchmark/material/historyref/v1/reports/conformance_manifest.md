# vaBench Release L0 Conformance Manifest

Date: 2026-05-17

These cases are EVAS/Spectre diagnostics. They are intentionally outside
the scored L1/L2 vaBench benchmark denominator.

## Summary

| Metric | Value |
| --- | ---: |
| conformance cases | 4 |
| model capability count | 0 |
| benchmark coverage count | 0 |
| bugfix claim count | 0 |
| broad parity denominator count | 0 |
| runner hooks required | 4 |

## Cases

| ID | Axis | Expected relation | Package path |
| --- | --- | --- | --- |
| `cross_event_post_side_read` | `event-sampling` | `waveform_equivalent` | `benchmark-vabench-release-v1/conformance/evas-spectre/cross_event_post_side_read` |
| `file_metric_writer_io_timing` | `checker-semantics` | `binary_outcome_equal` | `benchmark-vabench-release-v1/conformance/evas-spectre/file_metric_writer_io_timing` |
| `settling_done_boundary` | `solver-time-sampling` | `binary_outcome_equal` | `benchmark-vabench-release-v1/conformance/evas-spectre/settling_done_boundary` |
| `vco_timer0_startup` | `event-ordering` | `waveform_equivalent` | `benchmark-vabench-release-v1/conformance/evas-spectre/vco_timer0_startup` |
