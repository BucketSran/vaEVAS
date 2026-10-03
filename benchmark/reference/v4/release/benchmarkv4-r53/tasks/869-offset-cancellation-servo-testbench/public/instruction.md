# Offset-cancellation Servo Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Offset-cancellation Servo` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `offset_servo_top.va`:
  - Module `offset_servo_top` (entry)
    - position 0: `vinp` (inout, electrical)
    - position 1: `vinn` (inout, electrical)
    - position 2: `clk` (inout, electrical)
    - position 3: `rst` (inout, electrical)
    - position 4: `cal_en` (inout, electrical)
    - position 5: `corrected_out` (inout, electrical)
    - position 6: `trim_4` (inout, electrical)
    - position 7: `trim_3` (inout, electrical)
    - position 8: `trim_2` (inout, electrical)
    - position 9: `trim_1` (inout, electrical)
    - position 10: `trim_0` (inout, electrical)
    - position 11: `error_metric` (inout, electrical)
    - position 12: `done` (inout, electrical)
- Artifact `offset_sampler.va`:
  - Module `offset_sampler` (required_submodule)
    - position 0: `vinp` (inout, electrical)
    - position 1: `vinn` (inout, electrical)
    - position 2: `clk` (inout, electrical)
    - position 3: `rst` (inout, electrical)
    - position 4: `cal_en` (inout, electrical)
    - position 5: `sampled_error` (inout, electrical)
- Artifact `trim_dac.va`:
  - Module `trim_dac` (required_submodule)
    - position 0: `vinp` (inout, electrical)
    - position 1: `vinn` (inout, electrical)
    - position 2: `rst` (inout, electrical)
    - position 3: `trim_4` (inout, electrical)
    - position 4: `trim_3` (inout, electrical)
    - position 5: `trim_2` (inout, electrical)
    - position 6: `trim_1` (inout, electrical)
    - position 7: `trim_0` (inout, electrical)
    - position 8: `corrected_out` (inout, electrical)
- Artifact `error_integrator.va`:
  - Module `error_integrator` (required_submodule)
    - position 0: `sampled_error` (inout, electrical)
    - position 1: `clk` (inout, electrical)
    - position 2: `rst` (inout, electrical)
    - position 3: `cal_en` (inout, electrical)
    - position 4: `trim_4` (inout, electrical)
    - position 5: `trim_3` (inout, electrical)
    - position 6: `trim_2` (inout, electrical)
    - position 7: `trim_1` (inout, electrical)
    - position 8: `trim_0` (inout, electrical)
    - position 9: `error_metric` (inout, electrical)
    - position 10: `done` (inout, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include paths: `./dut/offset_servo_top.va`, `./dut/offset_sampler.va`, `./dut/trim_dac.va`, `./dut/error_integrator.va`
- DUT instance: `XDUT (vinp vinn clk rst cal_en corrected_out trim_4 trim_3 trim_2 trim_1 trim_0 error_metric done) offset_servo_top`
- Required saved public traces: `vinp`, `vinn`, `clk`, `rst`, `cal_en`, `corrected_out`, `trim_4`, `trim_3`, `trim_2`, `trim_1`, `trim_0`, `error_metric`, `done`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `offset_servo_top.vdd` defaults to `0.9` V; valid range: finite; overrides logic high output level.
- `offset_servo_top.vss` defaults to `0.0` V; valid range: finite; overrides logic low output level.
- `offset_servo_top.vth` defaults to `0.45` V; valid range: finite; overrides clock/control threshold.
- `offset_servo_top.trim_lsb` defaults to `2e-3` V; valid range: finite positive; overrides offset correction per trim-code step.
- `offset_servo_top.error_tol` defaults to `5e-3` V; valid range: finite positive; overrides residual offset tolerance.
- `offset_servo_top.tr` defaults to `200p from (0:inf)` s; valid range: positive; overrides output transition smoothing time.
- `offset_sampler.vss` defaults to `0.0` V; valid range: finite; overrides reset sample level.
- `offset_sampler.vth` defaults to `0.45` V; valid range: finite; overrides clock/control threshold.
- `offset_sampler.tr` defaults to `200p from (0:inf)` s; valid range: positive; overrides output transition smoothing time.
- `trim_dac.vdd` defaults to `0.9` V; valid range: finite; overrides logic high output level.
- `trim_dac.vss` defaults to `0.0` V; valid range: finite; overrides logic low output level.
- `trim_dac.vth` defaults to `0.45` V; valid range: finite; overrides trim-bit threshold.
- `trim_dac.trim_lsb` defaults to `2e-3` V; valid range: finite positive; overrides offset correction per trim-code step.
- `trim_dac.tr` defaults to `200p from (0:inf)` s; valid range: positive; overrides output transition smoothing time.
- `error_integrator.vdd` defaults to `0.9` V; valid range: finite; overrides logic high output level.
- `error_integrator.vss` defaults to `0.0` V; valid range: finite; overrides logic low output level.
- `error_integrator.vth` defaults to `0.45` V; valid range: finite; overrides clock/control threshold.
- `error_integrator.trim_lsb` defaults to `2e-3` V; valid range: finite positive; overrides offset correction per trim-code step.
- `error_integrator.error_tol` defaults to `5e-3` V; valid range: finite positive; overrides residual offset tolerance.
- `error_integrator.tr` defaults to `200p from (0:inf)` s; valid range: positive; overrides output transition smoothing time.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RESET_DISABLE_CLEAR`: exercise and make observable: On reset, clear trim code, corrected output, error metric, and done; when calibration is disabled, do not advance trim search state. Required traces: `time`, `vinp`, `vinn`, `clk`, `rst`, `cal_en`, `corrected_out`, `trim_4`, `trim_3`, `trim_2`, `trim_1`, `trim_0`, `error_metric`, `done`.
- `P_TRIM_SEARCH_DIRECTION`: exercise and make observable: Update the signed 5-bit trim code in the direction that reduces sampled differential error. Required traces: `time`, `vinp`, `vinn`, `clk`, `rst`, `cal_en`, `corrected_out`, `trim_4`, `trim_3`, `trim_2`, `trim_1`, `trim_0`, `error_metric`, `done`.
- `P_CORRECTED_RESIDUAL`: exercise and make observable: Drive corrected_out as the differential input minus the signed trim correction. Required traces: `time`, `vinp`, `vinn`, `clk`, `rst`, `cal_en`, `corrected_out`, `trim_4`, `trim_3`, `trim_2`, `trim_1`, `trim_0`, `error_metric`, `done`.
- `P_ERROR_METRIC`: exercise and make observable: Expose the current residual offset on error_metric after each enabled trim update. Required traces: `time`, `vinp`, `vinn`, `clk`, `rst`, `cal_en`, `corrected_out`, `trim_4`, `trim_3`, `trim_2`, `trim_1`, `trim_0`, `error_metric`, `done`.
- `P_DONE_QUALIFICATION`: exercise and make observable: Assert done only after four consecutive calibration updates with residual magnitude within error_tol. Required traces: `time`, `vinp`, `vinn`, `clk`, `rst`, `cal_en`, `corrected_out`, `trim_4`, `trim_3`, `trim_2`, `trim_1`, `trim_0`, `error_metric`, `done`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- On reset, clear the trim code, `corrected_out`, `error_metric`, and `done`.
- While `cal_en` is high, `offset_sampler` samples the differential input error once per rising `clk` edge.
- `error_integrator` updates a 5-bit trim code in the direction that reduces the sampled differential error.
- `trim_dac` converts the trim code to a signed correction applied to the differential input.
- `corrected_out` must expose the corrected differential signal as a voltage metric.
- Drive `trim_4..trim_0` as voltage-coded copies of the trim code.
- Assert `done` after four consecutive calibration updates where `error_metric` magnitude is within `error_tol`.


The required trace names are: `time`, `vinp`, `vinn`, `clk`, `rst`, `cal_en`, `corrected_out`, `trim_4`, `trim_3`, `trim_2`, `trim_1`, `trim_0`, `error_metric`, `done`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
