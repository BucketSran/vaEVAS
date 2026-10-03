# Linearity RDAC Offset Sweep Bugfix

## Task Contract

The supplied Verilog-A system violates its public circuit contract. Repair the
complete editable bundle.

## Public Verilog-A Interface

Preserve this exact artifact and module interface:

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

## Public Parameter Contract

- `linearity_rdac_offset_sweep.vcm` defaults to `0.6`; valid range: finite; overrides vcm.
- `linearity_rdac_offset_sweep.vppd` defaults to `1.0`; valid range: finite; overrides vppd.
- `linearity_rdac_offset_sweep.vdd` defaults to `1.0`; valid range: finite; overrides vdd.
- `linearity_rdac_offset_sweep.nlvl` defaults to `17.0`; valid range: finite; overrides nlvl.
- `linearity_rdac_offset_sweep.iter_num` defaults to `4`; valid range: finite; overrides iter_num.


## Required Behavior

The repaired bundle must satisfy every public property:

- `P_CLOCKED_SWEEP_DIRECTION`: restore: Rising `ck` crossings implement the RDAC sweep using `d < 0.5*vdd` as the low comparator direction. Required traces: `time`, `ck`, `d`, `dc0`, `dc1`, `dc2`, `dc3`, `dc4`, `dc5`, `dc6`, `vinn`, `vinp`, `vrefn`, `vrefp`.
- `P_SWEEP_INITIAL_STATE`: restore: Initialize `vref`, `vin`, search step, and stored comparator direction to the declared sweep state. Required traces: `time`, `ck`, `d`, `dc0`, `dc1`, `dc2`, `dc3`, `dc4`, `dc5`, `dc6`, `vinn`, `vinp`, `vrefn`, `vrefp`.
- `P_ITERATIVE_SEARCH_UPDATES`: restore: For each RDAC code, run exactly `iter_num` search-update clocks and halve the step before moving on direction changes. Required traces: `time`, `ck`, `d`, `dc0`, `dc1`, `dc2`, `dc3`, `dc4`, `dc5`, `dc6`, `vinn`, `vinp`, `vrefn`, `vrefp`.
- `P_CODE_UPDATE_AND_RECENTER`: restore: The clock after each search window updates the 7-bit code, recenters the search, and advances the sweep without an extra search step. Required traces: `time`, `ck`, `d`, `dc0`, `dc1`, `dc2`, `dc3`, `dc4`, `dc5`, `dc6`, `vinn`, `vinp`, `vrefn`, `vrefp`.


The following canonical public behavior is normative for this derived form:

Implement the sweep on rising crossings of `ck` through `0.5 * vdd`. Treat `d < 0.5 * vdd` as the low comparator direction and `d >= 0.5 * vdd` as the high comparator direction. Represent the generated input and reference as signed differential values `vin` and `vref`; drive `vinp/vinn` and `vrefp/vrefn` as half-differential outputs around `vcm`: `p = vcm + 0.5 * value` and `n = vcm - 0.5 * value`.

Initialize `vref` to the initial reference-grid value above, initialize `vin = vref`, initialize the search step to 40 mV, and initialize the stored comparator direction to the low direction. Initialize the 7-bit sweep code to full scale `127`, with `dc0` as the LSB, `dc6` as the MSB, high bits driven to `vdd`, and low bits driven to 0 V.

For each RDAC code, run exactly `iter_num` search-update clocks. On each search-update clock, sample `d`, halve the current step before moving when the sampled direction differs from the stored direction, then move `vin` by `+step` for the low direction or `-step` for the high direction. Update the stored direction to the sampled direction after the move.

The rising clock after those `iter_num` search updates is a code-update and recenter clock, not another search update. On that clock, decrement the 7-bit sweep code by one when it is nonzero; when the code is zero, wrap it back to `127` and advance `vref` by one reference-grid LSB. Update `dc0..dc6` from the new code, reset `vin = vref`, reset the search step to 40 mV, and begin the next code's `iter_num` search-update clocks on the following rising clock. The stored comparator direction carries across the code-update clock.


## Modeling Constraints

- Use deterministic voltage-domain behavioral Verilog-A.
- Do not hard-code validation stimulus, stop times, sample windows, gold internals, or simulator side channels.
- Preserve the exact file set, module graph, ports, parameters, and public traces.
- Do not add debug outputs, validation state, side channels, or stimulus-specific fixes.

## Output Contract

Return the repaired bundle with exactly these paths: `linearity_rdac_offset_sweep.va`.
Every supplied `.va` file is editable; do not add or omit files.
