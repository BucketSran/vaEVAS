# Sampled Error Update Monitor Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Sampled Error Update Monitor` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

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

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/sampled_error_update_monitor.va`
- DUT instance: `XDUT (clk rst sample target coef out err_metric progress) sampled_error_update_monitor`
- Required saved public traces: `clk`, `coef`, `err_metric`, `out`, `progress`, `rst`, `sample`, `target`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `sampled_error_update_monitor.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `sampled_error_update_monitor.vhi` defaults to `0.9`; valid range: finite; overrides vhi.
- `sampled_error_update_monitor.err_fullscale` defaults to `0.50`; valid range: finite; overrides err_fullscale.
- `sampled_error_update_monitor.err_window` defaults to `0.040`; valid range: finite; overrides err_window.
- `sampled_error_update_monitor.ready_count` defaults to `3`; valid range: finite; overrides ready_count.
- `sampled_error_update_monitor.tr` defaults to `60p`; valid range: finite; overrides tr.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RESET_CLEARS_STATE_AND_OBSERVABLES`: exercise and make observable: At each rising clk edge with V(rst) > vth, clear the stable count, out, err_metric, and progress to zero. Required traces: `clk`, `coef`, `err_metric`, `out`, `progress`, `rst`, `sample`, `target`, `time`.
- `P_CORRECTED_OUTPUT_USES_SAMPLE_TARGET_AND_COEF`: exercise and make observable: At each reset-low rising edge, let coeff=clip01(V(coef)/vhi) and error=V(target)-V(sample), then store out=clamp(V(sample)+coeff*error,0,vhi). Required traces: `clk`, `coef`, `err_metric`, `out`, `progress`, `rst`, `sample`, `target`, `time`.
- `P_ERROR_METRIC_REPORTS_ABSOLUTE_ERROR`: exercise and make observable: At the same edge, store err_metric=vhi*clip01(abs(error)/err_fullscale). Required traces: `clk`, `coef`, `err_metric`, `out`, `progress`, `rst`, `sample`, `target`, `time`.
- `P_PROGRESS_COUNTS_CONSECUTIVE_IN_WINDOW_SAMPLES`: exercise and make observable: Increment the stable count capped at ready_count exactly when abs(error)<=err_window, otherwise clear it; store progress=vhi*clip01(stable_count/ready_count). Required traces: `clk`, `coef`, `err_metric`, `out`, `progress`, `rst`, `sample`, `target`, `time`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- `P_RESET_CLEARS_STATE_AND_OBSERVABLES`: At each rising `clk` edge with `V(rst) > vth`, clear the stable count, `out`, `err_metric`, and `progress` to zero.
- `P_CORRECTED_OUTPUT_USES_SAMPLE_TARGET_AND_COEF`: At each reset-low rising edge, let `coeff = clip01(V(coef) / vhi)` and `error = V(target) - V(sample)`, then store `out = clamp(V(sample) + coeff * error, 0, vhi)`.
- `P_ERROR_METRIC_REPORTS_ABSOLUTE_ERROR`: Store `err_metric = vhi * clip01(abs(error) / err_fullscale)` at the same edge.
- `P_PROGRESS_COUNTS_CONSECUTIVE_IN_WINDOW_SAMPLES`: When `abs(error) <= err_window`, increment the stable count capped at `ready_count`; otherwise clear it. Store `progress = vhi * clip01(stable_count / ready_count)`.

The evaluator saves and may inspect these public trace signals: `time`, `clk`, `coef`, `err_metric`, `out`, `progress`, `rst`, `sample`, `target`.


The required trace names are: `time`, `clk`, `coef`, `err_metric`, `out`, `progress`, `rst`, `sample`, `target`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
