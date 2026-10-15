# Sampled Error Update Monitor Bugfix

## Task Contract

The supplied Verilog-A system violates its public circuit contract. Repair the
complete editable bundle.

## Public Verilog-A Interface

Preserve this exact artifact and module interface:

- Artifact `sampled_error_update_monitor.va`:
  - Module `sampled_error_update_monitor` (entry)
    - position 0: `clk` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `sample` (input, electrical)
    - position 3: `target` (input, electrical)
    - position 4: `coef` (input, electrical)
    - position 5: `out` (output, electrical)
    - position 6: `err_metric` (output, electrical)
    - position 7: `progress` (output, electrical)

## Public Parameter Contract

- `sampled_error_update_monitor.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `sampled_error_update_monitor.vhi` defaults to `0.9`; valid range: finite; overrides vhi.
- `sampled_error_update_monitor.err_fullscale` defaults to `0.50`; valid range: finite; overrides err_fullscale.
- `sampled_error_update_monitor.err_window` defaults to `0.040`; valid range: finite; overrides err_window.
- `sampled_error_update_monitor.ready_count` defaults to `3`; valid range: finite; overrides ready_count.
- `sampled_error_update_monitor.tr` defaults to `60p`; valid range: finite; overrides tr.


## Required Behavior

The repaired bundle must satisfy every public property:

- `P_RESET_CLEARS_STATE_AND_OBSERVABLES`: restore: At each rising clk edge with V(rst) > vth, clear the stable count, out, err_metric, and progress to zero. Required traces: `clk`, `coef`, `err_metric`, `out`, `progress`, `rst`, `sample`, `target`, `time`.
- `P_CORRECTED_OUTPUT_USES_SAMPLE_TARGET_AND_COEF`: restore: At each reset-low rising edge, let coeff=clip01(V(coef)/vhi) and error=V(target)-V(sample), then store out=clamp(V(sample)+coeff*error,0,vhi). Required traces: `clk`, `coef`, `err_metric`, `out`, `progress`, `rst`, `sample`, `target`, `time`.
- `P_ERROR_METRIC_REPORTS_ABSOLUTE_ERROR`: restore: At the same edge, store err_metric=vhi*clip01(abs(error)/err_fullscale). Required traces: `clk`, `coef`, `err_metric`, `out`, `progress`, `rst`, `sample`, `target`, `time`.
- `P_PROGRESS_COUNTS_CONSECUTIVE_IN_WINDOW_SAMPLES`: restore: Increment the stable count capped at ready_count exactly when abs(error)<=err_window, otherwise clear it; store progress=vhi*clip01(stable_count/ready_count). Required traces: `clk`, `coef`, `err_metric`, `out`, `progress`, `rst`, `sample`, `target`, `time`.


The following canonical public behavior is normative for this derived form:

- `P_RESET_CLEARS_STATE_AND_OBSERVABLES`: At each rising `clk` edge with `V(rst) > vth`, clear the stable count, `out`, `err_metric`, and `progress` to zero.
- `P_CORRECTED_OUTPUT_USES_SAMPLE_TARGET_AND_COEF`: At each reset-low rising edge, let `coeff = clip01(V(coef) / vhi)` and `error = V(target) - V(sample)`, then store `out = clamp(V(sample) + coeff * error, 0, vhi)`.
- `P_ERROR_METRIC_REPORTS_ABSOLUTE_ERROR`: Store `err_metric = vhi * clip01(abs(error) / err_fullscale)` at the same edge.
- `P_PROGRESS_COUNTS_CONSECUTIVE_IN_WINDOW_SAMPLES`: When `abs(error) <= err_window`, increment the stable count capped at `ready_count`; otherwise clear it. Store `progress = vhi * clip01(stable_count / ready_count)`.

The evaluator saves and may inspect these public trace signals: `time`, `clk`, `coef`, `err_metric`, `out`, `progress`, `rst`, `sample`, `target`.


## Modeling Constraints

- Use deterministic voltage-domain behavioral Verilog-A.
- Do not hard-code validation stimulus, stop times, sample windows, gold internals, or simulator side channels.
- Preserve the exact file set, module graph, ports, parameters, and public traces.
- Do not add debug outputs, validation state, side channels, or stimulus-specific fixes.

## Output Contract

Return the repaired bundle with exactly these paths: `sampled_error_update_monitor.va`.
Every supplied `.va` file is editable; do not add or omit files.
