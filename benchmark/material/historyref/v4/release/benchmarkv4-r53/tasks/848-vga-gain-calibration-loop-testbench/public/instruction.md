# VGA Gain Calibration Loop Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `VGA Gain Calibration Loop` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `vga_cal_loop_top.va`:
  - Module `vga_cal_loop_top` (entry)
    - position 0: `vin` (input, electrical)
    - position 1: `target` (input, electrical)
    - position 2: `clk` (input, electrical)
    - position 3: `rst` (input, electrical)
    - position 4: `start` (input, electrical)
    - position 5: `vout` (output, electrical)
    - position 6: `gain_3` (output, electrical)
    - position 7: `gain_2` (output, electrical)
    - position 8: `gain_1` (output, electrical)
    - position 9: `gain_0` (output, electrical)
    - position 10: `locked` (output, electrical)
    - position 11: `peak_metric` (output, electrical)
- Artifact `peak_detector.va`:
  - Module `peak_detector` (required_submodule)
    - position 0: `vin` (input, electrical)
    - position 1: `clk` (input, electrical)
    - position 2: `rst` (input, electrical)
    - position 3: `start` (input, electrical)
    - position 4: `peak_metric` (output, electrical)
- Artifact `gain_controller.va`:
  - Module `gain_controller` (required_submodule)
    - position 0: `peak_metric` (input, electrical)
    - position 1: `target` (input, electrical)
    - position 2: `clk` (input, electrical)
    - position 3: `rst` (input, electrical)
    - position 4: `start` (input, electrical)
    - position 5: `gain_3` (output, electrical)
    - position 6: `gain_2` (output, electrical)
    - position 7: `gain_1` (output, electrical)
    - position 8: `gain_0` (output, electrical)
- Artifact `vga_model.va`:
  - Module `vga_model` (required_submodule)
    - position 0: `vin` (input, electrical)
    - position 1: `gain_3` (input, electrical)
    - position 2: `gain_2` (input, electrical)
    - position 3: `gain_1` (input, electrical)
    - position 4: `gain_0` (input, electrical)
    - position 5: `vout` (output, electrical)
- Artifact `lock_detector.va`:
  - Module `lock_detector` (required_submodule)
    - position 0: `peak_metric` (input, electrical)
    - position 1: `target` (input, electrical)
    - position 2: `clk` (input, electrical)
    - position 3: `rst` (input, electrical)
    - position 4: `start` (input, electrical)
    - position 5: `locked` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include paths: `./dut/vga_cal_loop_top.va`, `./dut/peak_detector.va`, `./dut/gain_controller.va`, `./dut/vga_model.va`, `./dut/lock_detector.va`
- DUT instance: `XDUT (vin target clk rst start vout gain_3 gain_2 gain_1 gain_0 locked peak_metric) vga_cal_loop_top`
- Required saved public traces: `vin`, `target`, `clk`, `rst`, `start`, `vout`, `gain_3`, `gain_2`, `gain_1`, `gain_0`, `locked`, `peak_metric`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `vga_cal_loop_top.vdd` defaults to `0.9` V; valid range: finite and consistent with the declared rail domain; overrides vdd for this module.
- `vga_cal_loop_top.vss` defaults to `0.0` V; valid range: finite and consistent with the declared rail domain; overrides vss for this module.
- `vga_cal_loop_top.vth` defaults to `0.45` V; valid range: finite and consistent with the declared rail domain; overrides vth for this module.
- `vga_cal_loop_top.gain_min` defaults to `0.5`; valid range: finite; overrides gain_min for this module.
- `vga_cal_loop_top.gain_lsb` defaults to `0.1`; valid range: finite; overrides gain_lsb for this module.
- `vga_cal_loop_top.tol` defaults to `20e-3` V; valid range: finite and consistent with the declared rail domain; overrides tol for this module.
- `vga_cal_loop_top.tr` defaults to `200e-12` s; valid range: tr > 0; overrides tr for this module.
- `peak_detector.vth` defaults to `0.45` V; valid range: finite and consistent with the declared rail domain; overrides vth for this module.
- `peak_detector.tr` defaults to `200e-12` s; valid range: tr > 0; overrides tr for this module.
- `gain_controller.vdd` defaults to `0.9` V; valid range: finite and consistent with the declared rail domain; overrides vdd for this module.
- `gain_controller.vss` defaults to `0.0` V; valid range: finite and consistent with the declared rail domain; overrides vss for this module.
- `gain_controller.vth` defaults to `0.45` V; valid range: finite and consistent with the declared rail domain; overrides vth for this module.
- `gain_controller.tol` defaults to `20e-3` V; valid range: finite and consistent with the declared rail domain; overrides tol for this module.
- `gain_controller.tr` defaults to `200e-12` s; valid range: tr > 0; overrides tr for this module.
- `vga_model.vth` defaults to `0.45` V; valid range: finite and consistent with the declared rail domain; overrides vth for this module.
- `vga_model.gain_min` defaults to `0.5`; valid range: finite; overrides gain_min for this module.
- `vga_model.gain_lsb` defaults to `0.1`; valid range: finite; overrides gain_lsb for this module.
- `lock_detector.vdd` defaults to `0.9` V; valid range: finite and consistent with the declared rail domain; overrides vdd for this module.
- `lock_detector.vss` defaults to `0.0` V; valid range: finite and consistent with the declared rail domain; overrides vss for this module.
- `lock_detector.vth` defaults to `0.45` V; valid range: finite and consistent with the declared rail domain; overrides vth for this module.
- `lock_detector.tol` defaults to `20e-3` V; valid range: finite and consistent with the declared rail domain; overrides tol for this module.
- `lock_detector.tr` defaults to `200e-12` s; valid range: tr > 0; overrides tr for this module.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_VGA_RESET_STATE`: exercise and make observable: Reset restores gain code four and clears peak_metric and locked. Required traces: `time`, `clk`, `rst`, `gain_3`, `gain_2`, `gain_1`, `gain_0`, `peak_metric`, `locked`.
- `P_VGA_PEAK_SAMPLE`: exercise and make observable: Each enabled rising clock samples the absolute vin magnitude into peak_metric. Required traces: `time`, `vin`, `clk`, `rst`, `start`, `peak_metric`.
- `P_VGA_GAIN_DIRECTION`: exercise and make observable: The gain code moves one bounded step toward target according to the prior sampled peak and clamps to zero through fifteen. Required traces: `time`, `target`, `clk`, `rst`, `start`, `peak_metric`, `gain_3`, `gain_2`, `gain_1`, `gain_0`.
- `P_VGA_OUTPUT_GAIN`: exercise and make observable: vout continuously equals vin times gain_min plus gain_lsb times gain code. Required traces: `time`, `vin`, `vout`, `gain_3`, `gain_2`, `gain_1`, `gain_0`.
- `P_VGA_LOCK_QUALIFICATION`: exercise and make observable: locked asserts after three consecutive enabled updates whose prior sampled peak lies within tolerance. Required traces: `time`, `target`, `clk`, `rst`, `start`, `peak_metric`, `locked`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- On reset, set gain code to 4, clear `locked`, clear `peak_metric`, and drive `vout` from the reset gain.
- When `start` is high, `peak_detector` samples the absolute magnitude of `vin` on each rising `clk` edge.
- `vga_model` drives `vout = (gain_min + gain_lsb * gain_code) * V(vin)`.
- `gain_controller` increments the gain code by one when `peak_metric` is below `V(target) - tol`, decrements it by one when above `V(target) + tol`, and otherwise holds it.
- Clamp the gain code to the range 0 to 15.
- `lock_detector` asserts `locked` after three consecutive update cycles where the peak is within tolerance.
- Drive `gain_3..gain_0` as voltage-coded copies of the current gain code.


The required trace names are: `time`, `vin`, `target`, `clk`, `rst`, `start`, `vout`, `gain_3`, `gain_2`, `gain_1`, `gain_0`, `locked`, `peak_metric`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
