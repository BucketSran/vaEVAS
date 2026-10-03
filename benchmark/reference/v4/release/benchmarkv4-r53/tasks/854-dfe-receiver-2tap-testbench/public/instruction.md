# 2-tap DFE Receiver Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `2-tap DFE Receiver` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `dfe_rx_top.va`:
  - Module `dfe_rx_top` (entry)
    - position 0: `vin` (input, electrical)
    - position 1: `clk` (input, electrical)
    - position 2: `rst` (input, electrical)
    - position 3: `tap1_1` (input, electrical)
    - position 4: `tap1_0` (input, electrical)
    - position 5: `tap2_1` (input, electrical)
    - position 6: `tap2_0` (input, electrical)
    - position 7: `decision` (output, electrical)
    - position 8: `fb_metric` (output, electrical)
    - position 9: `slicer_in_dbg` (output, electrical)
- Artifact `slicer.va`:
  - Module `slicer` (required_submodule)
    - position 0: `vin` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `fb_metric` (input, electrical)
    - position 3: `decision_raw` (output, electrical)
    - position 4: `slicer_in_dbg` (output, electrical)
- Artifact `feedback_filter.va`:
  - Module `feedback_filter` (required_submodule)
    - position 0: `tap1_1` (input, electrical)
    - position 1: `tap1_0` (input, electrical)
    - position 2: `tap2_1` (input, electrical)
    - position 3: `tap2_0` (input, electrical)
    - position 4: `hist1` (input, electrical)
    - position 5: `hist2` (input, electrical)
    - position 6: `fb_metric` (output, electrical)
- Artifact `decision_latch.va`:
  - Module `decision_latch` (required_submodule)
    - position 0: `clk` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `slicer_in_dbg` (input, electrical)
    - position 3: `decision` (output, electrical)
    - position 4: `hist1` (output, electrical)
    - position 5: `hist2` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include paths: `./dut/dfe_rx_top.va`, `./dut/slicer.va`, `./dut/feedback_filter.va`, `./dut/decision_latch.va`
- DUT instance: `XDUT (vin clk rst tap1_1 tap1_0 tap2_1 tap2_0 decision fb_metric slicer_in_dbg) dfe_rx_top`
- Required saved public traces: `vin`, `clk`, `rst`, `tap1_1`, `tap1_0`, `tap2_1`, `tap2_0`, `decision`, `fb_metric`, `slicer_in_dbg`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `dfe_rx_top.vdd` defaults to `0.9`; valid range: finite; overrides vdd for module dfe_rx_top.
- `dfe_rx_top.vss` defaults to `0.0`; valid range: finite; overrides vss for module dfe_rx_top.
- `dfe_rx_top.vcm` defaults to `0.45`; valid range: finite; overrides vcm for module dfe_rx_top.
- `dfe_rx_top.vth` defaults to `0.45`; valid range: finite; overrides vth for module dfe_rx_top.
- `dfe_rx_top.tap_lsb` defaults to `20e-3`; valid range: finite; overrides tap_lsb for module dfe_rx_top.
- `dfe_rx_top.tr` defaults to `200e-12`; valid range: finite; overrides tr for module dfe_rx_top.
- `slicer.vdd` defaults to `0.9`; valid range: finite; overrides vdd for module slicer.
- `slicer.vss` defaults to `0.0`; valid range: finite; overrides vss for module slicer.
- `slicer.vcm` defaults to `0.45`; valid range: finite; overrides vcm for module slicer.
- `slicer.vth` defaults to `0.45`; valid range: finite; overrides vth for module slicer.
- `slicer.tr` defaults to `200e-12`; valid range: finite; overrides tr for module slicer.
- `feedback_filter.vdd` defaults to `0.9`; valid range: finite; overrides vdd for module feedback_filter.
- `feedback_filter.vss` defaults to `0.0`; valid range: finite; overrides vss for module feedback_filter.
- `feedback_filter.vth` defaults to `0.45`; valid range: finite; overrides vth for module feedback_filter.
- `feedback_filter.tap_lsb` defaults to `20e-3`; valid range: finite; overrides tap_lsb for module feedback_filter.
- `feedback_filter.tr` defaults to `200e-12`; valid range: finite; overrides tr for module feedback_filter.
- `decision_latch.vdd` defaults to `0.9`; valid range: finite; overrides vdd for module decision_latch.
- `decision_latch.vss` defaults to `0.0`; valid range: finite; overrides vss for module decision_latch.
- `decision_latch.vcm` defaults to `0.45`; valid range: finite; overrides vcm for module decision_latch.
- `decision_latch.vth` defaults to `0.45`; valid range: finite; overrides vth for module decision_latch.
- `decision_latch.tr` defaults to `200e-12`; valid range: finite; overrides tr for module decision_latch.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RESET_CLEAR`: exercise and make observable: Reset clears the decision history and all public outputs. Required traces: `time`, `rst`, `decision`, `fb_metric`, `slicer_in_dbg`.
- `P_TWO_TAP_FEEDBACK`: exercise and make observable: The feedback metric uses both configured taps and the previous two decisions. Required traces: `time`, `clk`, `rst`, `tap1_1`, `tap1_0`, `tap2_1`, `tap2_0`, `decision`, `fb_metric`.
- `P_CORRECTED_INPUT`: exercise and make observable: The debug slicer input equals VIN minus the active signed feedback correction. Required traces: `time`, `vin`, `clk`, `rst`, `fb_metric`, `slicer_in_dbg`.
- `P_CLOCKED_DECISION`: exercise and make observable: Each rising clock edge latches the threshold decision derived from the corrected input. Required traces: `time`, `vin`, `clk`, `rst`, `decision`, `slicer_in_dbg`.
- `P_HISTORY_ORDER`: exercise and make observable: Feedback for a decision is based only on decisions from preceding clock edges. Required traces: `time`, `vin`, `clk`, `rst`, `decision`, `fb_metric`, `slicer_in_dbg`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- On reset, clear the decision history, `decision`, `fb_metric`, and `slicer_in_dbg`.
- On each rising `clk` edge, `feedback_filter` must compute feedback from the previous two decisions only.
- The current slicer input is `V(vin)` minus the computed feedback correction.
- `slicer` must drive the new decision high when the corrected slicer input is greater than or equal to `vcm`, otherwise low.
- `decision_latch` must update the two-decision history after the new decision is produced.
- `fb_metric` must expose the signed feedback correction used for the active decision.
- `slicer_in_dbg` must expose the corrected slicer input used by the active decision.


The required trace names are: `time`, `vin`, `clk`, `rst`, `tap1_1`, `tap1_0`, `tap2_1`, `tap2_0`, `decision`, `fb_metric`, `slicer_in_dbg`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
