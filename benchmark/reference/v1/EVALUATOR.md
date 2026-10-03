# vaBench Release Evaluator Contract

Date: 2026-06-23

This contract describes how the release package is consumed by evaluators
and paper-facing baselines. It does not create certification evidence.

## Task Selection

| Metric | Value |
| --- | ---: |
| package entries | 86 |
| package forms | 300 |
| certified entries | 86 |
| certified forms | 300 |
| scored entries | 73 |
| scored forms | 265 |
| L0 conformance excluded | `True` |
| v1.1 expansion tasks | 300 |
| v1.1 existing certified forms | 271 |
| v1.1 proposed pending forms | 29 |
| partial-pass negatives per expansion task | 5 |
| partial-pass negative candidates | 1500 |

## Backend Roles

| Backend | Role | Final judge |
| --- | --- | --- |
| `static` | source/package integrity gate | `False` |
| `evas` | formal behavioral Verilog-A certification and scoring evaluator | `True` |
| `spectre` | optional non-blocking parity reference | `False` |

## Gates

- Score gate: `score_enabled`; scored entries/forms = 73/265
- Baseline gate: `ready_for_baseline_runs`; claim allowed = `True`

## Commands

| Command | Value |
| --- | --- |
| `refresh_package` | `python3 runners/run_vabench_release_longrun.py` |
| `finish_after_bridge` | `python3 runners/finish_vabench_release_after_bridge.py` |
| `primary_dual_rerun` | `./scripts/run_with_bridge.sh python3 runners/run_vabench_release_dual_rerun.py --output-root results/vabench-release-v1-dual-rerun --timeout-s 180` |
| `enable_score_denominator` | `python3 runners/enable_vabench_release_score_denominator.py` |
| `refresh_score_denominator` | `python3 runners/report_vabench_release_score_denominator.py` |
| `refresh_baseline_gate` | `python3 runners/report_vabench_release_baseline_artifact.py` |
| `build_300_expansion` | `python3 runners/build_vabench_300_expansion.py` |
| `audit_300_negatives` | `python3 runners/audit_vabench_300_expansion.py` |

## Claim Boundary

- This contract defines evaluator IO and score gates; it is not simulator certification evidence.
- Pinned strict EVAS is the formal judge for release certification and scoring.
- Spectre is optional non-blocking parity evidence and is not required for a score claim.
- L0 conformance cases are evaluator health checks and never scored benchmark rows.
- Optional parity and speed claims require their own evidence and do not alter the benchmark score gate.
