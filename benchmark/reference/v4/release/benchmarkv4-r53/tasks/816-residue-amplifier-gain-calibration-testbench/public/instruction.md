# Residue Amplifier Gain-calibration Loop Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Residue Amplifier Gain-calibration Loop` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `residue_amp_gain_calibration_top.va`:
  - Module `residue_amp_gain_calibration_top` (entry)
    - position 0: `vin` (inout, electrical)
    - position 1: `residue_ref` (inout, electrical)
    - position 2: `clk` (inout, electrical)
    - position 3: `rst` (inout, electrical)
    - position 4: `cal_en` (inout, electrical)
    - position 5: `gain_2` (inout, electrical)
    - position 6: `gain_1` (inout, electrical)
    - position 7: `gain_0` (inout, electrical)
    - position 8: `vout` (inout, electrical)
    - position 9: `error_metric` (inout, electrical)
    - position 10: `locked` (inout, electrical)
- Artifact `residue_amp_core.va`:
  - Module `residue_amp_core` (required_submodule)
    - position 0: `vin` (inout, electrical)
    - position 1: `rst` (inout, electrical)
    - position 2: `cal_en` (inout, electrical)
    - position 3: `gain_2` (inout, electrical)
    - position 4: `gain_1` (inout, electrical)
    - position 5: `gain_0` (inout, electrical)
    - position 6: `vout` (inout, electrical)
- Artifact `gain_cal_controller.va`:
  - Module `gain_cal_controller` (required_submodule)
    - position 0: `residue` (inout, electrical)
    - position 1: `residue_ref` (inout, electrical)
    - position 2: `clk` (inout, electrical)
    - position 3: `rst` (inout, electrical)
    - position 4: `cal_en` (inout, electrical)
    - position 5: `gain_2` (inout, electrical)
    - position 6: `gain_1` (inout, electrical)
    - position 7: `gain_0` (inout, electrical)
    - position 8: `error_metric` (inout, electrical)
    - position 9: `locked` (inout, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include paths: `./dut/residue_amp_gain_calibration_top.va`, `./dut/residue_amp_core.va`, `./dut/gain_cal_controller.va`
- DUT instance: `XDUT (vin residue_ref clk rst cal_en gain_2 gain_1 gain_0 vout error_metric locked) residue_amp_gain_calibration_top`
- Required saved public traces: `vin`, `residue_ref`, `clk`, `rst`, `cal_en`, `gain_2`, `gain_1`, `gain_0`, `vout`, `error_metric`, `locked`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `residue_amp_gain_calibration_top.vdd` defaults to `0.9`; valid range: finite; overrides vdd.
- `residue_amp_gain_calibration_top.vss` defaults to `0.0`; valid range: finite; overrides vss.
- `residue_amp_gain_calibration_top.vcm` defaults to `0.45`; valid range: finite; overrides vcm.
- `residue_amp_gain_calibration_top.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `residue_amp_gain_calibration_top.tr` defaults to `200p from (0:inf)`; valid range: finite; overrides tr.
- `residue_amp_gain_calibration_top.base_gain` defaults to `2.0`; valid range: finite; overrides base_gain.
- `residue_amp_gain_calibration_top.gain_lsb` defaults to `0.25`; valid range: finite; overrides gain_lsb.
- `residue_amp_gain_calibration_top.lock_tol` defaults to `15e-3`; valid range: finite; overrides lock_tol.
- `residue_amp_core.vdd` defaults to `0.9`; valid range: finite; overrides vdd.
- `residue_amp_core.vss` defaults to `0.0`; valid range: finite; overrides vss.
- `residue_amp_core.vcm` defaults to `0.45`; valid range: finite; overrides vcm.
- `residue_amp_core.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `residue_amp_core.tr` defaults to `200p from (0:inf)`; valid range: finite; overrides tr.
- `residue_amp_core.base_gain` defaults to `2.0`; valid range: finite; overrides base_gain.
- `residue_amp_core.gain_lsb` defaults to `0.25`; valid range: finite; overrides gain_lsb.
- `residue_amp_core.tick` defaults to `250p from (0:inf)`; valid range: finite; overrides tick.
- `gain_cal_controller.vdd` defaults to `0.9`; valid range: finite; overrides vdd.
- `gain_cal_controller.vss` defaults to `0.0`; valid range: finite; overrides vss.
- `gain_cal_controller.vcm` defaults to `0.45`; valid range: finite; overrides vcm.
- `gain_cal_controller.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `gain_cal_controller.tr` defaults to `200p from (0:inf)`; valid range: finite; overrides tr.
- `gain_cal_controller.lock_tol` defaults to `15e-3`; valid range: finite; overrides lock_tol.
- `gain_cal_controller.tick` defaults to `250p from (0:inf)`; valid range: finite; overrides tick.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_ON_RESET_CLEAR_GAIN_CODE_OUTPUT`: exercise and make observable: On reset or while `cal_en` is low, clear the unsigned gain code and lock streak; drive gain bits, `error_metric`, and `locked` to `vss`, and drive the common-mode-centered `vout` to `vcm`. Required traces: `time`, `vin`, `residue_ref`, `clk`, `rst`, `cal_en`, `gain_2`, `gain_1`, `gain_0`, `vout`, `error_metric`, `locked`.
- `P_WHILE_CAL_EN_IS_HIGH_COMPARE`: exercise and make observable: While `cal_en` is high, sample `signed_error = residue_ref-vout` on each rising `clk` edge and expose `error_metric = abs(residue_ref-vout)`. Required traces: `time`, `vin`, `residue_ref`, `clk`, `rst`, `cal_en`, `gain_2`, `gain_1`, `gain_0`, `vout`, `error_metric`, `locked`.
- `P_INCREMENT_OR_DECREMENT_THE_GAIN_CODE`: exercise and make observable: When signed error exceeds `lock_tol`, increment the unsigned code by one up to 7; when it is below `-lock_tol`, decrement by one down to 0; otherwise hold the code. Required traces: `time`, `vin`, `residue_ref`, `clk`, `rst`, `cal_en`, `gain_2`, `gain_1`, `gain_0`, `vout`, `error_metric`, `locked`.
- `P_DRIVE_VOUT_AS_A_CLAMPED_RESIDUE`: exercise and make observable: Decode `gain = base_gain + gain_lsb*code` and drive `vout = clamp(vcm + gain*(vin-vcm), vss, vdd)` while enabled. Required traces: `time`, `vin`, `residue_ref`, `clk`, `rst`, `cal_en`, `gain_2`, `gain_1`, `gain_0`, `vout`, `error_metric`, `locked`.
- `P_ASSERT_LOCKED_AFTER_THREE_CONSECUTIVE_UPDATES`: exercise and make observable: Drive `locked` to `vdd` after three consecutive enabled rising-edge samples with error magnitude at or below `lock_tol`, otherwise drive `vss`; clear the streak on reset, disable, or an out-of-tolerance sample. Required traces: `time`, `vin`, `residue_ref`, `clk`, `rst`, `cal_en`, `gain_2`, `gain_1`, `gain_0`, `vout`, `error_metric`, `locked`.
- `P_USE_ONLY_VOLTAGE_DOMAIN_BEHAVIORAL_STATE`: exercise and make observable: Use only voltage-domain behavioral state and voltage contributions on public electrical outputs. Required traces: `time`, `vin`, `residue_ref`, `clk`, `rst`, `cal_en`, `gain_2`, `gain_1`, `gain_0`, `vout`, `error_metric`, `locked`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- On reset, clear gain code, output, error metric, and `locked`.
- While `cal_en` is high, compare the current residue output against `residue_ref` on each rising `clk` edge.
- Increment or decrement the gain code by one step to reduce the signed error.
- Drive `vout` as a clamped residue-amplified version of `vin - vcm` using the active gain code.
- Assert `locked` after three consecutive updates with error magnitude below `lock_tol`.
- Use only voltage-domain behavioral state and voltage contributions on public electrical outputs.
- Do not expose pass/fail flags; expose only the public observable metrics named in the interface.

`gain_2`, `gain_1`, and `gain_0` are DUT-driven observable outputs that encode
an unsigned gain code from 0 through 7; they are not coefficient inputs.  On
reset or while `cal_en` is low, clear the code and lock streak, drive the three
gain outputs, `error_metric`, and `locked` to `vss`, and drive `vout` to the
neutral residue level `vcm`.  Holding `vout` at `vcm` is the defined cleared
output state for this common-mode-centered residue signal.

While enabled, decode the active code as
`gain = base_gain + gain_lsb*code` and drive
`vout = clamp(vcm + gain*(vin-vcm), vss, vdd)`.  At each rising `clk` edge,
sample `signed_error = residue_ref-vout`.  When `signed_error > lock_tol`,
increment the code by one, saturating at 7.  When
`signed_error < -lock_tol`, decrement the code by one, saturating at 0.  When
`abs(signed_error) <= lock_tol`, leave the code unchanged.  Expose the error
magnitude as `error_metric = abs(residue_ref-vout)`.

Count consecutive enabled rising-edge samples whose error magnitude is at or
below `lock_tol`.  Drive `locked` to `vdd` after the third such sample and to
`vss` otherwise.  An out-of-tolerance sample, reset, or disabled interval
clears the consecutive-sample count.  Apply the public `tr` smoothing time to
observable output transitions without changing these settled values.


The required trace names are: `time`, `vin`, `residue_ref`, `clk`, `rst`, `cal_en`, `gain_2`, `gain_1`, `gain_0`, `vout`, `error_metric`, `locked`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
