# Linearity RDAC Offset Sweep Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Linearity RDAC Offset Sweep` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `linearity_rdac_offset_sweep.va`:
  - Module `linearity_rdac_offset_sweep` (entry)
    - position 0: `ck` (input, electrical)
    - position 1: `d` (input, electrical)
    - position 2: `vinp` (output, electrical)
    - position 3: `vinn` (output, electrical)
    - position 4: `vrefp` (output, electrical)
    - position 5: `vrefn` (output, electrical)
    - position 6: `dc0` (output, electrical)
    - position 7: `dc1` (output, electrical)
    - position 8: `dc2` (output, electrical)
    - position 9: `dc3` (output, electrical)
    - position 10: `dc4` (output, electrical)
    - position 11: `dc5` (output, electrical)
    - position 12: `dc6` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/linearity_rdac_offset_sweep.va`
- DUT instance: `XDUT (ck d vinp vinn vrefp vrefn dc0 dc1 dc2 dc3 dc4 dc5 dc6) linearity_rdac_offset_sweep`
- Required saved public traces: `ck`, `d`, `dc0`, `dc1`, `dc2`, `dc3`, `dc4`, `dc5`, `dc6`, `vinn`, `vinp`, `vrefn`, `vrefp`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `linearity_rdac_offset_sweep.vcm` defaults to `0.6`; valid range: finite; overrides vcm.
- `linearity_rdac_offset_sweep.vppd` defaults to `1.0`; valid range: finite; overrides vppd.
- `linearity_rdac_offset_sweep.vdd` defaults to `1.0`; valid range: finite; overrides vdd.
- `linearity_rdac_offset_sweep.nlvl` defaults to `17.0`; valid range: finite; overrides nlvl.
- `linearity_rdac_offset_sweep.iter_num` defaults to `4`; valid range: finite; overrides iter_num.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_CLOCKED_SWEEP_DIRECTION`: exercise and make observable: Rising `ck` crossings implement the RDAC sweep using `d < 0.5*vdd` as the low comparator direction. Required traces: `time`, `ck`, `d`, `dc0`, `dc1`, `dc2`, `dc3`, `dc4`, `dc5`, `dc6`, `vinn`, `vinp`, `vrefn`, `vrefp`.
- `P_SWEEP_INITIAL_STATE`: exercise and make observable: Initialize `vref`, `vin`, search step, and stored comparator direction to the declared sweep state. Required traces: `time`, `ck`, `d`, `dc0`, `dc1`, `dc2`, `dc3`, `dc4`, `dc5`, `dc6`, `vinn`, `vinp`, `vrefn`, `vrefp`.
- `P_ITERATIVE_SEARCH_UPDATES`: exercise and make observable: For each RDAC code, run exactly `iter_num` search-update clocks and halve the step before moving on direction changes. Required traces: `time`, `ck`, `d`, `dc0`, `dc1`, `dc2`, `dc3`, `dc4`, `dc5`, `dc6`, `vinn`, `vinp`, `vrefn`, `vrefp`.
- `P_CODE_UPDATE_AND_RECENTER`: exercise and make observable: The clock after each search window updates the 7-bit code, recenters the search, and advances the sweep without an extra search step. Required traces: `time`, `ck`, `d`, `dc0`, `dc1`, `dc2`, `dc3`, `dc4`, `dc5`, `dc6`, `vinn`, `vinp`, `vrefn`, `vrefp`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

The supplied DUT implements the sweep on rising crossings of `ck` through `0.5 * vdd`. Treat `d < 0.5 * vdd` as the low comparator direction and `d >= 0.5 * vdd` as the high comparator direction. Represent the generated input and reference as signed differential values `vin` and `vref`; drive `vinp/vinn` and `vrefp/vrefn` as half-differential outputs around `vcm`: `p = vcm + 0.5 * value` and `n = vcm - 0.5 * value`.

Initialize `vref` to the initial reference-grid value above, initialize `vin = vref`, initialize the search step to 40 mV, and initialize the stored comparator direction to the low direction. Initialize the 7-bit sweep code to full scale `127`, with `dc0` as the LSB, `dc6` as the MSB, high bits driven to `vdd`, and low bits driven to 0 V.

For each RDAC code, run exactly `iter_num` search-update clocks. On each search-update clock, sample `d`, halve the current step before moving when the sampled direction differs from the stored direction, then move `vin` by `+step` for the low direction or `-step` for the high direction. Update the stored direction to the sampled direction after the move.

The rising clock after those `iter_num` search updates is a code-update and recenter clock, not another search update. On that clock, decrement the 7-bit sweep code by one when it is nonzero; when the code is zero, wrap it back to `127` and advance `vref` by one reference-grid LSB. Update `dc0..dc6` from the new code, reset `vin = vref`, reset the search step to 40 mV, and begin the next code's `iter_num` search-update clocks on the following rising clock. The stored comparator direction carries across the code-update clock.


The required trace names are: `time`, `ck`, `d`, `dc0`, `dc1`, `dc2`, `dc3`, `dc4`, `dc5`, `dc6`, `vinn`, `vinp`, `vrefn`, `vrefp`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
