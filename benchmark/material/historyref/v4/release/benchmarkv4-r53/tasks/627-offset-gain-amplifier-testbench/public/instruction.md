# Offset Gain Amplifier Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Offset Gain Amplifier` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `offset_gain_amplifier.va`:
  - Module `offset_gain_amplifier` (entry)
    - position 0: `sigin` (input, electrical)
    - position 1: `sigout` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/offset_gain_amplifier.va`
- DUT instance: `XDUT (sigin sigout) offset_gain_amplifier`
- Required saved public traces: `sigin`, `sigout`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- No public parameter is declared.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_INPUT_OFFSET_SUBTRACTION`: exercise and make observable: Subtract 0.2 V from `V(sigin)` before applying gain. Required traces: `time`, `sigin`, `sigout`.
- `P_FIXED_GAIN_THREE`: exercise and make observable: Drive `sigout` to `3.0 * (V(sigin) - 0.2)`. Required traces: `time`, `sigin`, `sigout`.
- `P_DIRECT_MEMORYLESS_OUTPUT`: exercise and make observable: Use a direct memoryless voltage output without clipping, filtering, current output, or stimulus-specific behavior. Required traces: `time`, `sigin`, `sigout`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- `P_INPUT_OFFSET_SUBTRACTION`: Subtract 0.2 V from `V(sigin)` before applying gain.

- `P_FIXED_GAIN_THREE`: Drive `sigout` to `3.0 * (V(sigin) - 0.2)`.

- `P_DIRECT_MEMORYLESS_OUTPUT`: Use a direct memoryless voltage output without clipping, filtering, current output, or stimulus-specific behavior.


The required trace names are: `time`, `sigin`, `sigout`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
