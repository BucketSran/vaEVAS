# Baseband AGC and Filter Chain Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Baseband AGC and Filter Chain` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `agc_chain_top.va`:
  - Module `agc_chain_top` (entry)
    - position 0: `vin` (input, electrical)
    - position 1: `target` (input, electrical)
    - position 2: `clk` (input, electrical)
    - position 3: `rst` (input, electrical)
    - position 4: `enable` (input, electrical)
    - position 5: `vout` (output, electrical)
    - position 6: `gain_3` (output, electrical)
    - position 7: `gain_2` (output, electrical)
    - position 8: `gain_1` (output, electrical)
    - position 9: `gain_0` (output, electrical)
    - position 10: `level_metric` (output, electrical)
    - position 11: `clip_flag` (output, electrical)
    - position 12: `settled` (output, electrical)
- Artifact `level_meter.va`:
  - Module `level_meter` (required_submodule)
    - position 0: `vin` (input, electrical)
    - position 1: `clk` (input, electrical)
    - position 2: `rst` (input, electrical)
    - position 3: `enable` (input, electrical)
    - position 4: `level_metric` (output, electrical)
- Artifact `gain_controller.va`:
  - Module `gain_controller` (required_submodule)
    - position 0: `level_metric` (input, electrical)
    - position 1: `target` (input, electrical)
    - position 2: `clk` (input, electrical)
    - position 3: `rst` (input, electrical)
    - position 4: `enable` (input, electrical)
    - position 5: `gain_3` (output, electrical)
    - position 6: `gain_2` (output, electrical)
    - position 7: `gain_1` (output, electrical)
    - position 8: `gain_0` (output, electrical)
    - position 9: `settled` (output, electrical)
- Artifact `vga_stage.va`:
  - Module `vga_stage` (required_submodule)
    - position 0: `vin` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `enable` (input, electrical)
    - position 3: `gain_3` (input, electrical)
    - position 4: `gain_2` (input, electrical)
    - position 5: `gain_1` (input, electrical)
    - position 6: `gain_0` (input, electrical)
    - position 7: `vga_out` (output, electrical)
- Artifact `filter_stage.va`:
  - Module `filter_stage` (required_submodule)
    - position 0: `vga_in` (input, electrical)
    - position 1: `clk` (input, electrical)
    - position 2: `rst` (input, electrical)
    - position 3: `enable` (input, electrical)
    - position 4: `vout` (output, electrical)
    - position 5: `clip_flag` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include paths: `./dut/agc_chain_top.va`, `./dut/level_meter.va`, `./dut/gain_controller.va`, `./dut/vga_stage.va`, `./dut/filter_stage.va`
- DUT instance: `XDUT (vin target clk rst enable vout gain_3 gain_2 gain_1 gain_0 level_metric clip_flag settled) agc_chain_top`
- Required saved public traces: `vin`, `target`, `clk`, `rst`, `enable`, `vout`, `gain_3`, `gain_2`, `gain_1`, `gain_0`, `level_metric`, `clip_flag`, `settled`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `agc_chain_top.vdd` defaults to `0.9`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vdd behavior for module agc_chain_top.
- `agc_chain_top.vss` defaults to `0.0`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vss behavior for module agc_chain_top.
- `agc_chain_top.vcm` defaults to `0.45`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vcm behavior for module agc_chain_top.
- `agc_chain_top.vth` defaults to `0.45`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vth behavior for module agc_chain_top.
- `agc_chain_top.gain_min` defaults to `0.5`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public gain_min behavior for module agc_chain_top.
- `agc_chain_top.gain_lsb` defaults to `0.1`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public gain_lsb behavior for module agc_chain_top.
- `agc_chain_top.alpha` defaults to `0.25`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public alpha behavior for module agc_chain_top.
- `agc_chain_top.tol` defaults to `20e-3`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public tol behavior for module agc_chain_top.
- `agc_chain_top.tr` defaults to `200p from (0:inf)` s; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public tr behavior for module agc_chain_top.
- `level_meter.vdd` defaults to `0.9`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vdd behavior for module level_meter.
- `level_meter.vss` defaults to `0.0`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vss behavior for module level_meter.
- `level_meter.vcm` defaults to `0.45`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vcm behavior for module level_meter.
- `level_meter.vth` defaults to `0.45`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vth behavior for module level_meter.
- `level_meter.tr` defaults to `200p from (0:inf)` s; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public tr behavior for module level_meter.
- `gain_controller.vdd` defaults to `0.9`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vdd behavior for module gain_controller.
- `gain_controller.vss` defaults to `0.0`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vss behavior for module gain_controller.
- `gain_controller.vth` defaults to `0.45`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vth behavior for module gain_controller.
- `gain_controller.tol` defaults to `20e-3`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public tol behavior for module gain_controller.
- `gain_controller.tr` defaults to `200p from (0:inf)` s; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public tr behavior for module gain_controller.
- `vga_stage.vdd` defaults to `0.9`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vdd behavior for module vga_stage.
- `vga_stage.vss` defaults to `0.0`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vss behavior for module vga_stage.
- `vga_stage.vcm` defaults to `0.45`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vcm behavior for module vga_stage.
- `vga_stage.vth` defaults to `0.45`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vth behavior for module vga_stage.
- `vga_stage.gain_min` defaults to `0.5`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public gain_min behavior for module vga_stage.
- `vga_stage.gain_lsb` defaults to `0.1`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public gain_lsb behavior for module vga_stage.
- `vga_stage.tr` defaults to `200p from (0:inf)` s; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public tr behavior for module vga_stage.
- `filter_stage.vdd` defaults to `0.9`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vdd behavior for module filter_stage.
- `filter_stage.vss` defaults to `0.0`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vss behavior for module filter_stage.
- `filter_stage.vcm` defaults to `0.45`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vcm behavior for module filter_stage.
- `filter_stage.vth` defaults to `0.45`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vth behavior for module filter_stage.
- `filter_stage.alpha` defaults to `0.25`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public alpha behavior for module filter_stage.
- `filter_stage.tr` defaults to `200p from (0:inf)` s; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public tr behavior for module filter_stage.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RESET_DISABLE_CLEAR`: exercise and make observable: Reset or disabled operation restores gain code 4, clears metrics and flags, and drives vout to vcm. Required traces: `time`, `rst`, `enable`, `vout`, `gain_3`, `gain_2`, `gain_1`, `gain_0`, `level_metric`, `clip_flag`, `settled`.
- `P_LEVEL_GAIN_CONTROL`: exercise and make observable: Each enabled rising clock samples the input magnitude and moves the bounded gain code toward the target deadband. Required traces: `time`, `vin`, `target`, `clk`, `rst`, `enable`, `gain_3`, `gain_2`, `gain_1`, `gain_0`, `level_metric`.
- `P_VGA_FILTER_RESPONSE`: exercise and make observable: The VGA applies gain_min plus gain_lsb times code and the sampled filter moves by alpha toward that VGA result. Required traces: `time`, `vin`, `clk`, `enable`, `vout`, `gain_3`, `gain_2`, `gain_1`, `gain_0`.
- `P_CLIP_AND_SETTLE`: exercise and make observable: clip_flag reports an unclamped filter excursion beyond the rails and settled asserts only after three consecutive in-tolerance updates. Required traces: `time`, `target`, `clk`, `enable`, `vout`, `level_metric`, `clip_flag`, `settled`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- On reset or when `enable` is low, set gain code to 4, clear metrics, clear flags, and drive `vout` to `vcm`.
- `level_meter` measures the magnitude of `vin` deviation from `vcm` once per rising `clk` edge.
- `gain_controller` increments the gain code when the measured level is below `V(target) - tol` and decrements it when above `V(target) + tol`.
- `vga_stage` applies the selected gain to the input deviation from `vcm`.
- `filter_stage` applies sampled low-pass smoothing to the VGA output.
- `clip_flag` must assert when the unclamped filtered output would exceed `vss` through `vdd`.
- `settled` must assert after three consecutive updates where `level_metric` is within tolerance.


The required trace names are: `time`, `vin`, `target`, `clk`, `rst`, `enable`, `vout`, `gain_3`, `gain_2`, `gain_1`, `gain_0`, `level_metric`, `clip_flag`, `settled`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
