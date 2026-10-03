# Offset RDAC Search Flow Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Offset RDAC Search Flow` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

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

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/offset_rdac_search_flow.va`
- DUT instance: `XDUT (ck d vinp vinn vrefp vrefn dc0 dc1 dc2 dc3 dc4 dc5 dc6) offset_rdac_search_flow`
- Required saved public traces: `ck`, `d`, `dc0`, `dc1`, `dc2`, `dc3`, `dc4`, `dc5`, `dc6`, `vinn`, `vinp`, `vrefn`, `vrefp`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- No public parameter is declared.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_TWO_PHASE_CLOCKED_FLOW`: exercise and make observable: Rising `ck` crossings execute the deterministic RDAC-refinement phase before the offset-search phase, using `d < 0.5 V` as the low comparator direction. Required traces: `time`, `ck`, `d`, `dc0`, `dc1`, `dc2`, `dc3`, `dc4`, `dc5`, `dc6`, `vinn`, `vinp`, `vrefn`, `vrefp`.
- `P_REFERENCE_AND_CODE_INITIALIZATION`: exercise and make observable: Initialize `vref`, `vin`, and the 7-bit RDAC trial code to the declared reference-grid and MSB-first state. Required traces: `time`, `ck`, `d`, `dc0`, `dc1`, `dc2`, `dc3`, `dc4`, `dc5`, `dc6`, `vinn`, `vinp`, `vrefn`, `vrefp`.
- `P_RDAC_REFINEMENT_SEQUENCE`: exercise and make observable: The six RDAC refinement clocks resolve the current bit and assert the next lower trial bit in the declared order. Required traces: `time`, `ck`, `d`, `dc0`, `dc1`, `dc2`, `dc3`, `dc4`, `dc5`, `dc6`, `vinn`, `vinp`, `vrefn`, `vrefp`.
- `P_OFFSET_SEARCH_BISECTION`: exercise and make observable: The eight offset-search clocks compare consecutive directions, halve the search step on direction changes, and update `vin/vref` with the declared polarity. Required traces: `time`, `ck`, `d`, `dc0`, `dc1`, `dc2`, `dc3`, `dc4`, `dc5`, `dc6`, `vinn`, `vinp`, `vrefn`, `vrefp`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

The supplied DUT is a deterministic two-phase foreground flow on rising crossings of `ck` through 0.5 V. Treat `d < 0.5 V` as the low comparator direction and `d >= 0.5 V` as the high comparator direction. Represent the generated input and reference as signed differential values `vin` and `vref`; drive `vinp/vinn` and `vrefp/vrefn` as half-differential outputs around the 0.6 V common mode: `p = 0.6 + 0.5 * value` and `n = 0.6 - 0.5 * value`.

Initialize `vref` and `vin` to the initial reference-grid value above. Initialize the RDAC code to `1000000` with `dc6` as the MSB, `dc0` as the LSB, high bits driven to 1 V, and low bits driven to 0 V.

The RDAC refinement phase contains six decision clocks. On those clocks, resolve the current trial bit and assert the next lower trial bit in this order: `(dc6, dc5)`, `(dc5, dc4)`, `(dc4, dc3)`, `(dc3, dc2)`, `(dc2, dc1)`, `(dc1, dc0)`. For each pair, keep the current bit high when `d < 0.5 V`; clear the current bit when `d >= 0.5 V`; in both cases set the next lower bit high. The clock immediately after the sixth RDAC decision is a phase handoff and does not perform another bit decision.

The offset-search phase then contains eight search-update clocks. Start each search window with a 40 mV step, compare each sampled comparator direction with the immediately previous sampled direction from the foreground flow, halve the current step before moving when the direction changes, then move `vin` by `+step` for `d < 0.5 V` or `-step` for `d >= 0.5 V`. After the eighth search-update clock, advance `vref` by one reference-grid LSB, reset `vin` to the new `vref`, reset the RDAC code to `1000000`, and keep the outputs recentered on that new reference. The next rising clock is a restart boundary; the following rising clock begins the next six-clock RDAC refinement sequence.


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
