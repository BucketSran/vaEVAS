# Dual Modulus Divider 16 17 Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Dual Modulus Divider 16 17` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `dual_modulus_divider_16_17.va`:
  - Module `dual_modulus_divider_16_17` (entry)
    - position 0: `fin` (input, electrical)
    - position 1: `mc` (input, electrical)
    - position 2: `fout` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/dual_modulus_divider_16_17.va`
- DUT instance: `XDUT (fin mc fout) dual_modulus_divider_16_17`
- Required saved public traces: `fin`, `fout`, `mc`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- No public parameter is declared.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_MC_SELECTS_MODULUS`: exercise and make observable: `mc` selects divide-by-16 when low and divide-by-17 when high for rising `fin` crossings. Required traces: `time`, `fin`, `fout`, `mc`.
- `P_DIVIDE_COUNT_TIMING`: exercise and make observable: The output counter resets only at the terminal count for the selected modulus. Required traces: `time`, `fin`, `fout`, `mc`.
- `P_OUTPUT_LOW_MARKER_AND_LEVEL`: exercise and make observable: `fout` uses the specified low-marker count and declared voltage-coded output levels. Required traces: `time`, `fin`, `fout`, `mc`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Start with `fout` low. Count rising crossings of `fin` through 0.5 V. Produce the divider output pulse pattern for divide-by-16 when `mc` is low, and extend the terminal count by one input edge for divide-by-17 when `mc` is high at the modulus decision point. Assert the high marker on the terminal divide event: count 15 for divide-by-16 and count 16 for divide-by-17. Return `fout` low at the midpoint marker, count 8 within the following marker interval.


The required trace names are: `time`, `fin`, `fout`, `mc`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
