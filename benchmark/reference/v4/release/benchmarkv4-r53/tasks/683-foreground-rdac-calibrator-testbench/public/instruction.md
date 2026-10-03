# Foreground RDAC Calibrator Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Foreground RDAC Calibrator` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `foreground_rdac_calibrator.va`:
  - Module `foreground_rdac_calibrator` (entry)
    - position 0: `ck` (input, electrical)
    - position 1: `d` (input, electrical)
    - position 2: `vrefp` (input, electrical)
    - position 3: `vrefn` (input, electrical)
    - position 4: `dc0` (output, electrical)
    - position 5: `dc1` (output, electrical)
    - position 6: `dc2` (output, electrical)
    - position 7: `dc3` (output, electrical)
    - position 8: `dc4` (output, electrical)
    - position 9: `dc5` (output, electrical)
    - position 10: `dc6` (output, electrical)
    - position 11: `cvinp` (output, electrical)
    - position 12: `cvinn` (output, electrical)
    - position 13: `en` (output, electrical)
    - position 14: `enb` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/foreground_rdac_calibrator.va`
- DUT instance: `XDUT (ck d vrefp vrefn dc0 dc1 dc2 dc3 dc4 dc5 dc6 cvinp cvinn en enb) foreground_rdac_calibrator`
- Required saved public traces: `ck`, `cvinn`, `cvinp`, `d`, `dc0`, `dc1`, `dc2`, `dc3`, `dc4`, `dc5`, `dc6`, `en`, `enb`, `vrefn`, `vrefp`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `foreground_rdac_calibrator.vdd` defaults to `1.0`; valid range: finite; overrides vdd.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_INITIAL_MSB_TRIAL_CODE`: exercise and make observable: At startup, calibration is active with `dc6` asserted and all lower RDAC bits deasserted. Required traces: `time`, `ck`, `cvinn`, `cvinp`, `d`, `dc0`, `dc1`, `dc2`, `dc3`, `dc4`, `dc5`, `dc6`, `en`, `enb`, `vrefn`, `vrefp`.
- `P_CLOCKED_RDAC_DECISION_SEQUENCE`: exercise and make observable: On each rising `ck` crossing while active, resolve the current trial bit from `d` versus `vth` and advance from MSB to LSB. Required traces: `time`, `ck`, `cvinn`, `cvinp`, `d`, `dc0`, `dc1`, `dc2`, `dc3`, `dc4`, `dc5`, `dc6`, `en`, `enb`, `vrefn`, `vrefp`.
- `P_DECISION_POLARITY`: exercise and make observable: Comparator-low and comparator-high decisions update the trial bit in the declared polarity without inverting the search direction. Required traces: `time`, `ck`, `cvinn`, `cvinp`, `d`, `dc0`, `dc1`, `dc2`, `dc3`, `dc4`, `dc5`, `dc6`, `en`, `enb`, `vrefn`, `vrefp`.
- `P_CALIBRATION_COMPLETION`: exercise and make observable: After the final RDAC decision, deassert calibration enable and hold the completed code. Required traces: `time`, `ck`, `cvinn`, `cvinp`, `d`, `dc0`, `dc1`, `dc2`, `dc3`, `dc4`, `dc5`, `dc6`, `en`, `enb`, `vrefn`, `vrefp`.
- `P_RDAC_OUTPUT_LEVELS`: exercise and make observable: All RDAC code and enable outputs remain voltage-coded at valid low/high levels. Required traces: `time`, `ck`, `cvinn`, `cvinp`, `d`, `dc0`, `dc1`, `dc2`, `dc3`, `dc4`, `dc5`, `dc6`, `en`, `enb`, `vrefn`, `vrefp`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Initialize calibration active with the MSB trial code set (`dc6 = vdd`, all lower RDAC bits low). On each rising `ck` crossing while calibration is active, sample `d` against the `0.5*vdd` threshold and refine the 7-bit RDAC code from MSB toward LSB. For the current trial bit, keep that bit when `d < 0.5*vdd`; clear that bit when `d >= 0.5*vdd`. In both cases, assert the next lower trial bit as the search advances. After the seven-bit capture phase completes, deassert `en` and assert `enb`. Continuously drive `cvinp` from `vrefp` and `cvinn` from `vrefn`.


The required trace names are: `time`, `ck`, `cvinn`, `cvinp`, `d`, `dc0`, `dc1`, `dc2`, `dc3`, `dc4`, `dc5`, `dc6`, `en`, `enb`, `vrefn`, `vrefp`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
