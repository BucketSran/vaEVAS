# Calibration plan for the rebuilt ideal task

All VA execution below is pending. Software fixtures exercise the analytical checker and score reducer; they do not prove VA event semantics or a qualified final runner.

## Independent expectations

For public `windows`, track closes at 20 ns at threshold 0.9 V. The input falls linearly from 1.6 V at 16 ns to 0.2 V at 30 ns, so the frozen value is 1.2 V. The outputs at 24 ns and 28 ns must remain 1.2 V even though the input changes. The separate fixed hand anchors in `../test_software.py` also cover startup and reset releases, with expected values written as constants rather than obtained from gold or the interval algorithm.

For the endpoint example, `vin(t)=0.1+1.4*t/(60 ns)`. The close at 59.6 ns samples 1.4906666666666666 V. A guard below 0.2 ns leaves startup, the early window, both sides of the final close, and the 60 ns endpoint observable. A larger guard can erase a required interval and must reject the plan. These are geometry examples, not approved limits on slope, duration, guard, or minimum window width. The legal minimum-window example is pending `TBD_STIMULUS_DOMAIN`.

## Correct and incorrect VA candidates

Run `solution/circuit.va` and `alternative.va` through the same public and final protocol. The first clears storage on reset release into hold; the second clears storage on reset assertion. Accept both external behaviors. Also construct a correct combined-event implementation and a renamed/reordered local-state variant when qualifying the intended backend, so qualification does not require the reference source form. Correct alternatives rejected by the backend are environment gaps.

`mutants.py` writes concrete wrong VA candidates for future execution:

| Candidate | Required distinguishing observation |
| --- | --- |
| `inclusive_threshold` | `startup/equality_track` and `startup/equality_reset`: equality is low, with the other control chosen to expose each comparison |
| `initial_input` | `startup`: hold startup must equal nondefault vinit, not vin |
| `sample_at_open` | `windows`: later hold equals the closing ramp value |
| `hold_feedthrough` | `windows`: moving input during hold must not move vout |
| `stale_after_reset` | `reset_history/release_hold`: discard the earlier sample |
| `reset_to_zero` | `reset_history`: active reset equals its nonzero vinit |
| `track_priority` | `startup/t1r1` and overlap: reset must win |
| `hold_droop` | Long enough `windows` hold to distinguish the chosen slope within finalized voltage error |
| `fixed_threshold` | `isolation`: different thresholds shift ramp crossing times |
| `fixed_initial` | `startup` and `isolation`: nondefault initial/reset values |
| `finite_tracking` | `windows`: continuous ramp tracking without added settling |

Check instance independence with differently driven simultaneous instances, repeated instance-order permutations, and an intentionally coupled-model candidate. A portable coupled VA candidate and correct combined-event source are still pending. Software-swapped instance traces test checker sensitivity only. For every wrong VA candidate, require a completed trajectory and a mismatch at the listed semantic observation. Compile failures, timeouts, or unsupported operators are not semantic detection. Record those attempts with score 0 and their execution causes separately.

## Measurement and scoring qualification

Resolve the public domain and boundary TBDs before freezing cases. Derive voltage tolerance from intended ideal-model fidelity, then allocate separate truth/interpolation, simulator voltage, timestamp, crossing-location, and observation budgets. With maximum input slope L and crossing-time uncertainty delta_t, reserve at least L*delta_t for sample-value uncertainty. Do not infer the allowed voltage error from the gold's observed error. Check both defaults and varied parameters, endpoint/short-window examples, and zero-time monitoring. Repeat with tighter numerical settings to establish measurement stability without silently changing the public criterion.

The trusted runner must freeze only `/app/circuit.va`, record its SHA-256 before and after the run, copy it into a fresh author-controlled environment, and regenerate the declared stimulus and observation plan. It must not accept candidate CSV or self-reported results as final input. Preserve the full source, bench, checker, settings, toolchain and log identities. Rerun all public cases and the author extensions. Freeze the extensions and settings before model trials; the draft extensions are not yet a certified holdout.

Exercise the actual final entry with absent/empty/illegal submissions, compile/runtime failure, timeout, missing/duplicate/nonfinite/truncated traces, bad timestamps, mismatched driven inputs, one semantic failure, all passing cases, and incomplete execution. Executed unsuccessful attempts score 0 with causes; unexecuted/incomplete attempts have no completed score unless an executed failure already makes the task unsuccessful. All required passing cases score 1. No reward is emitted for the current blocked draft. Validate that solver-side files cannot replace the final benches or results. The current runner implements source freezing, explicit licensed launch, native PSF parsing and scoring. Pending protocol decisions stop it before process launch; actual backend and scoring calibration are still required.
