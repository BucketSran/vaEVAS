# Calibration Deadband Controller Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Calibration Deadband Controller` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `calibration_deadband_controller.va`:
  - Module `calibration_deadband_controller` (entry)
    - position 0: `clk` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `vin` (input, electrical)
    - position 3: `out` (output, electrical)
    - position 4: `metric` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/calibration_deadband_controller.va`
- DUT instance: `XFB_DUT (clk rst vin out metric) calibration_deadband_controller`
- Required saved public traces: `clk`, `rst`, `vin`, `out`, `metric`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `calibration_deadband_controller.tr` defaults to `1e-10` s; valid range: tr > 0; sets output transition smoothing.
- `calibration_deadband_controller.vth` defaults to `0.45` V; valid range: finite real; sets clk and rst logic threshold.
- `calibration_deadband_controller.target` defaults to `0.45` V; valid range: vmin <= target <= vmax; sets initial, reset, and zero-error trim target.
- `calibration_deadband_controller.deadband` defaults to `0.05` V; valid range: deadband >= 0; sets the symmetric no-update error interval.
- `calibration_deadband_controller.step_size` defaults to `0.06` V; valid range: step_size > 0; sets trim increment or decrement per accepted update.
- `calibration_deadband_controller.vmin` defaults to `0.05` V; valid range: vmin <= target and vmin < vmax; sets lower output clamp.
- `calibration_deadband_controller.vmax` defaults to `0.85` V; valid range: vmax >= target and vmax > vmin; sets upper output clamp.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_INITIAL_AND_RESET_TARGET`: exercise and make observable: Out initializes to target and returns to target while rst is above vth; metric is low during reset. Required traces: `time`, `rst`, `out`, `metric`.
- `P_POSITIVE_ERROR_STEP`: exercise and make observable: At a rising clock crossing with vin minus target greater than deadband, out increases by one step_size and metric goes high. Required traces: `time`, `clk`, `rst`, `vin`, `out`, `metric`.
- `P_NEGATIVE_ERROR_STEP`: exercise and make observable: At a rising clock crossing with vin minus target less than negative deadband, out decreases by one step_size and metric goes high. Required traces: `time`, `clk`, `rst`, `vin`, `out`, `metric`.
- `P_DEADBAND_HOLD`: exercise and make observable: At a rising clock crossing with signed error inside the inclusive deadband, out holds and metric remains low. Required traces: `time`, `clk`, `rst`, `vin`, `out`, `metric`.
- `P_OUTPUT_CLAMP`: exercise and make observable: Repeated updates cannot drive out below vmin or above vmax. Required traces: `time`, `clk`, `vin`, `out`.
- `P_BETWEEN_EDGE_HOLD`: exercise and make observable: Out state does not follow vin between rising clock crossings. Required traces: `time`, `clk`, `vin`, `out`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- Initialize the trim output to `target`.
- On each rising crossing of `clk` through `vth`, sample `vin` and update the trim state.
- While `rst` is above `vth`, reset the trim state to `target` and drive `metric` low.
- Compute signed error as `V(vin) - target`.
- If the error is greater than `deadband`, increase the trim by `step_size`.
- If the error is less than `-deadband`, decrease the trim by `step_size`.
- If the error is inside the deadband, hold the trim state.
- Clamp the trim state between `vmin` and `vmax`.
- Drive `metric` high only on accepted trim updates and low otherwise.


The required trace names are: `time`, `clk`, `rst`, `vin`, `out`, `metric`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
