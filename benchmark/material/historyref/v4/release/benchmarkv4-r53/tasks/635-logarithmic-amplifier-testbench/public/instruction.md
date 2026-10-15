# Logarithmic Amplifier Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Logarithmic Amplifier` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `logarithmic_amplifier.va`:
  - Module `logarithmic_amplifier` (entry)
    - position 0: `sigin` (input, electrical)
    - position 1: `sigout` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/logarithmic_amplifier.va`
- DUT instance: `XDUT (sigin sigout) logarithmic_amplifier`
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

- `P_INPUT_OFFSET_SUBTRACTION`: exercise and make observable: Subtract 0.2 V from `V(sigin)` before computing magnitude. Required traces: `time`, `sigin`, `sigout`.
- `P_ABSOLUTE_MAGNITUDE`: exercise and make observable: Use the absolute value of the offset-corrected voltage as the logarithm argument magnitude. Required traces: `time`, `sigin`, `sigout`.
- `P_MAGNITUDE_FLOOR`: exercise and make observable: Floor the magnitude at 0.1 V before applying the logarithm. Required traces: `time`, `sigin`, `sigout`.
- `P_NATURAL_LOG_OUTPUT`: exercise and make observable: Drive `sigout` to the natural logarithm of the guarded magnitude. Required traces: `time`, `sigin`, `sigout`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Subtract a 0.2 V input offset, take the absolute value of the adjusted voltage, floor the magnitude at 0.1 V to keep the logarithm well-defined, and drive `sigout` with the natural logarithm of that guarded magnitude.


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
