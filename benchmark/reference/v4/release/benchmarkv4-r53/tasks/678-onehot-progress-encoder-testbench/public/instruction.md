# Onehot Progress Encoder Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Onehot Progress Encoder` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `onehot_progress_encoder.va`:
  - Module `onehot_progress_encoder` (entry)
    - position 0: `ck` (input, electrical)
    - position 1: `d0` (output, electrical)
    - position 2: `d1` (output, electrical)
    - position 3: `d2` (output, electrical)
    - position 4: `d3` (output, electrical)
    - position 5: `d4` (output, electrical)
    - position 6: `d5` (output, electrical)
    - position 7: `d6` (output, electrical)
    - position 8: `d7` (output, electrical)
    - position 9: `d8` (output, electrical)
    - position 10: `d9` (output, electrical)
    - position 11: `d10` (output, electrical)
    - position 12: `d11` (output, electrical)
    - position 13: `d12` (output, electrical)
    - position 14: `d13` (output, electrical)
    - position 15: `d14` (output, electrical)
    - position 16: `d15` (output, electrical)
    - position 17: `sum` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/onehot_progress_encoder.va`
- DUT instance: `XDUT (ck d0 d1 d2 d3 d4 d5 d6 d7 d8 d9 d10 d11 d12 d13 d14 d15 sum) onehot_progress_encoder`
- Required saved public traces: `ck`, `d0`, `d1`, `d2`, `d3`, `d4`, `d5`, `d6`, `d7`, `d8`, `d9`, `d10`, `d11`, `d12`, `d13`, `d14`, `d15`, `sum`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- No public parameter is declared.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_PROGRESS_INITIAL_STATE`: exercise and make observable: All progress outputs and the count initialize to zero. Required traces: `time`, `ck`, `d0`, `d1`, `d2`, `d3`, `d4`, `d5`, `d6`, `d7`, `d8`, `d9`, `d10`, `d11`, `d12`, `d13`, `d14`, `d15`, `sum`.
- `P_SEQUENTIAL_ONEHOT_ASSERTION`: exercise and make observable: Each rising `ck` crossing asserts the next progress bit in order from `d0` through `d15` without skipping the first bit. Required traces: `time`, `ck`, `d0`, `d1`, `d2`, `d3`, `d4`, `d5`, `d6`, `d7`, `d8`, `d9`, `d10`, `d11`, `d12`, `d13`, `d14`, `d15`.
- `P_ACCUMULATING_PROGRESS_BITS`: exercise and make observable: Previously asserted progress bits remain high until all sixteen bits have been asserted. Required traces: `time`, `ck`, `d0`, `d1`, `d2`, `d3`, `d4`, `d5`, `d6`, `d7`, `d8`, `d9`, `d10`, `d11`, `d12`, `d13`, `d14`, `d15`.
- `P_SUM_COUNT_OUTPUT`: exercise and make observable: `sum` reports the current count value corresponding to the number of asserted progress bits. Required traces: `time`, `ck`, `sum`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Initialize all progress outputs and the count to zero. On each rising `ck` crossing, set the next progress bit high and increment the count until all sixteen bits have been asserted. Drive `sum` with the current count value and hold all state between clock events.


The required trace names are: `time`, `ck`, `d0`, `d1`, `d2`, `d3`, `d4`, `d5`, `d6`, `d7`, `d8`, `d9`, `d10`, `d11`, `d12`, `d13`, `d14`, `d15`, `sum`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
