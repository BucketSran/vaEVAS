# Offset-calibrated Comparator System Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Offset-calibrated Comparator System` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `calibrated_comparator_top.va`:
  - Module `calibrated_comparator_top` (entry)
    - position 0: `vinp` (input, electrical)
    - position 1: `vinn` (input, electrical)
    - position 2: `clk` (input, electrical)
    - position 3: `rst` (input, electrical)
    - position 4: `cal_en` (input, electrical)
    - position 5: `cal_ref` (input, electrical)
    - position 6: `decision` (output, electrical)
    - position 7: `ready` (output, electrical)
    - position 8: `offset_3` (output, electrical)
    - position 9: `offset_2` (output, electrical)
    - position 10: `offset_1` (output, electrical)
    - position 11: `offset_0` (output, electrical)
    - position 12: `threshold_dbg` (output, electrical)
- Artifact `comparator_core.va`:
  - Module `comparator_core` (required_submodule)
    - position 0: `vinp` (input, electrical)
    - position 1: `vinn` (input, electrical)
    - position 2: `threshold_i` (input, electrical)
    - position 3: `rst` (input, electrical)
    - position 4: `decision` (output, electrical)
- Artifact `offset_dac.va`:
  - Module `offset_dac` (required_submodule)
    - position 0: `offset_3` (input, electrical)
    - position 1: `offset_2` (input, electrical)
    - position 2: `offset_1` (input, electrical)
    - position 3: `offset_0` (input, electrical)
    - position 4: `rst` (input, electrical)
    - position 5: `threshold_dbg` (output, electrical)
- Artifact `calibration_fsm.va`:
  - Module `calibration_fsm` (required_submodule)
    - position 0: `clk` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `cal_en` (input, electrical)
    - position 3: `cal_ref` (input, electrical)
    - position 4: `ready` (output, electrical)
    - position 5: `offset_3` (output, electrical)
    - position 6: `offset_2` (output, electrical)
    - position 7: `offset_1` (output, electrical)
    - position 8: `offset_0` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include paths: `./dut/calibrated_comparator_top.va`, `./dut/comparator_core.va`, `./dut/offset_dac.va`, `./dut/calibration_fsm.va`
- DUT instance: `XDUT (vinp vinn clk rst cal_en cal_ref decision ready offset_3 offset_2 offset_1 offset_0 threshold_dbg) calibrated_comparator_top`
- Required saved public traces: `vinp`, `vinn`, `clk`, `rst`, `cal_en`, `cal_ref`, `decision`, `ready`, `offset_3`, `offset_2`, `offset_1`, `offset_0`, `threshold_dbg`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `calibrated_comparator_top.vdd` defaults to `0.9` V; valid range: finite and consistent with the declared rail domain; overrides vdd for this module.
- `calibrated_comparator_top.vss` defaults to `0.0` V; valid range: finite and consistent with the declared rail domain; overrides vss for this module.
- `calibrated_comparator_top.vth` defaults to `0.45` V; valid range: finite and consistent with the declared rail domain; overrides vth for this module.
- `calibrated_comparator_top.offset_lsb` defaults to `5e-3` V; valid range: finite and consistent with the declared rail domain; overrides offset_lsb for this module.
- `calibrated_comparator_top.tr` defaults to `200p` s; valid range: tr > 0; overrides tr for this module.
- `comparator_core.vdd` defaults to `0.9` V; valid range: finite and consistent with the declared rail domain; overrides vdd for this module.
- `comparator_core.vss` defaults to `0.0` V; valid range: finite and consistent with the declared rail domain; overrides vss for this module.
- `comparator_core.vth` defaults to `0.45` V; valid range: finite and consistent with the declared rail domain; overrides vth for this module.
- `comparator_core.tr` defaults to `200p` s; valid range: tr > 0; overrides tr for this module.
- `offset_dac.offset_lsb` defaults to `5e-3` V; valid range: finite and consistent with the declared rail domain; overrides offset_lsb for this module.
- `offset_dac.vss` defaults to `0.0` V; valid range: finite and consistent with the declared rail domain; overrides vss for this module.
- `offset_dac.vth` defaults to `0.45` V; valid range: finite and consistent with the declared rail domain; overrides vth for this module.
- `offset_dac.tr` defaults to `200p` s; valid range: tr > 0; overrides tr for this module.
- `calibration_fsm.vdd` defaults to `0.9` V; valid range: finite and consistent with the declared rail domain; overrides vdd for this module.
- `calibration_fsm.vss` defaults to `0.0` V; valid range: finite and consistent with the declared rail domain; overrides vss for this module.
- `calibration_fsm.vth` defaults to `0.45` V; valid range: finite and consistent with the declared rail domain; overrides vth for this module.
- `calibration_fsm.tr` defaults to `200p` s; valid range: tr > 0; overrides tr for this module.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_CAL_RESET_CLEAR`: exercise and make observable: Reset clears offset code, decision, ready, and threshold_dbg. Required traces: `time`, `rst`, `offset_3`, `offset_2`, `offset_1`, `offset_0`, `decision`, `ready`, `threshold_dbg`.
- `P_CAL_CODE_UPDATE`: exercise and make observable: Each enabled rising clock updates and clamps the offset code in the direction selected by cal_ref. Required traces: `time`, `clk`, `rst`, `cal_en`, `cal_ref`, `offset_3`, `offset_2`, `offset_1`, `offset_0`.
- `P_CAL_OFFSET_DAC`: exercise and make observable: threshold_dbg equals signed code minus eight times offset_lsb outside reset. Required traces: `time`, `rst`, `offset_3`, `offset_2`, `offset_1`, `offset_0`, `threshold_dbg`.
- `P_CAL_READY_QUALIFICATION`: exercise and make observable: ready asserts after four updates in one calibration window and the code holds while cal_en is low. Required traces: `time`, `clk`, `rst`, `cal_en`, `ready`, `offset_3`, `offset_2`, `offset_1`, `offset_0`.
- `P_CAL_COMPARATOR_DECISION`: exercise and make observable: decision reflects the sign of vinp minus vinn plus threshold_dbg and is low in reset. Required traces: `time`, `vinp`, `vinn`, `rst`, `threshold_dbg`, `decision`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- On reset, clear the offset code, `decision`, `ready`, and `threshold_dbg`.
- While `cal_en` is high, `calibration_fsm` updates the signed offset code once per rising `clk` edge using `cal_ref` as the calibration error input.
- When `cal_ref` is above `vth`, increment the offset code by one step up to code 15; otherwise decrement by one step down to code 0.
- After four calibration updates with `cal_en` high, assert `ready` and hold the final offset code until reset or another calibration window.
- `offset_dac` must convert the 4-bit offset code to `threshold_dbg = (offset_code - 8) * offset_lsb`.
- `comparator_core` must drive `decision` high when `V(vinp) - V(vinn) + threshold_dbg >= 0`, otherwise low.
- Drive `offset_3..offset_0` as voltage-coded copies of the current offset code.


The required trace names are: `time`, `vinp`, `vinn`, `clk`, `rst`, `cal_en`, `cal_ref`, `decision`, `ready`, `offset_3`, `offset_2`, `offset_1`, `offset_0`, `threshold_dbg`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
