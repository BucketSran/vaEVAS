# Offset RDAC Search Flow Bugfix

## Task Contract

The supplied Verilog-A system violates its public circuit contract. Repair the
complete editable bundle.

## Public Verilog-A Interface

Preserve this exact artifact and module interface:

- Artifact `offset_rdac_search_flow.va`:
  - Module `offset_rdac_search_flow` (entry)
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

- No public parameter is declared.


## Required Behavior

The repaired bundle must satisfy every public property:

- `P_TWO_PHASE_CLOCKED_FLOW`: restore: Rising `ck` crossings execute the deterministic RDAC-refinement phase before the offset-search phase, using `d < 0.5 V` as the low comparator direction. Required traces: `time`, `ck`, `d`, `dc0`, `dc1`, `dc2`, `dc3`, `dc4`, `dc5`, `dc6`, `vinn`, `vinp`, `vrefn`, `vrefp`.
- `P_REFERENCE_AND_CODE_INITIALIZATION`: restore: Initialize `vref`, `vin`, and the 7-bit RDAC trial code to the declared reference-grid and MSB-first state. Required traces: `time`, `ck`, `d`, `dc0`, `dc1`, `dc2`, `dc3`, `dc4`, `dc5`, `dc6`, `vinn`, `vinp`, `vrefn`, `vrefp`.
- `P_RDAC_REFINEMENT_SEQUENCE`: restore: The six RDAC refinement clocks resolve the current bit and assert the next lower trial bit in the declared order. Required traces: `time`, `ck`, `d`, `dc0`, `dc1`, `dc2`, `dc3`, `dc4`, `dc5`, `dc6`, `vinn`, `vinp`, `vrefn`, `vrefp`.
- `P_OFFSET_SEARCH_BISECTION`: restore: The eight offset-search clocks compare consecutive directions, halve the search step on direction changes, and update `vin/vref` with the declared polarity. Required traces: `time`, `ck`, `d`, `dc0`, `dc1`, `dc2`, `dc3`, `dc4`, `dc5`, `dc6`, `vinn`, `vinp`, `vrefn`, `vrefp`.


The following canonical public behavior is normative for this derived form:

Implement a deterministic two-phase foreground flow on rising crossings of `ck` through 0.5 V. Treat `d < 0.5 V` as the low comparator direction and `d >= 0.5 V` as the high comparator direction. Represent the generated input and reference as signed differential values `vin` and `vref`; drive `vinp/vinn` and `vrefp/vrefn` as half-differential outputs around the 0.6 V common mode: `p = 0.6 + 0.5 * value` and `n = 0.6 - 0.5 * value`.

Initialize `vref` and `vin` to the initial reference-grid value above. Initialize the RDAC code to `1000000` with `dc6` as the MSB, `dc0` as the LSB, high bits driven to 1 V, and low bits driven to 0 V.

The RDAC refinement phase contains six decision clocks. On those clocks, resolve the current trial bit and assert the next lower trial bit in this order: `(dc6, dc5)`, `(dc5, dc4)`, `(dc4, dc3)`, `(dc3, dc2)`, `(dc2, dc1)`, `(dc1, dc0)`. For each pair, keep the current bit high when `d < 0.5 V`; clear the current bit when `d >= 0.5 V`; in both cases set the next lower bit high. The clock immediately after the sixth RDAC decision is a phase handoff and does not perform another bit decision.

The offset-search phase then contains eight search-update clocks. Start each search window with a 40 mV step, compare each sampled comparator direction with the immediately previous sampled direction from the foreground flow, halve the current step before moving when the direction changes, then move `vin` by `+step` for `d < 0.5 V` or `-step` for `d >= 0.5 V`. After the eighth search-update clock, advance `vref` by one reference-grid LSB, reset `vin` to the new `vref`, reset the RDAC code to `1000000`, and keep the outputs recentered on that new reference. The next rising clock is a restart boundary; the following rising clock begins the next six-clock RDAC refinement sequence.


## Modeling Constraints

- Use deterministic voltage-domain behavioral Verilog-A.
- Do not hard-code validation stimulus, stop times, sample windows, gold internals, or simulator side channels.
- Preserve the exact file set, module graph, ports, parameters, and public traces.
- Do not add debug outputs, validation state, side channels, or stimulus-specific fixes.

## Output Contract

Return the repaired bundle with exactly these paths: `offset_rdac_search_flow.va`.
Every supplied `.va` file is editable; do not add or omit files.
