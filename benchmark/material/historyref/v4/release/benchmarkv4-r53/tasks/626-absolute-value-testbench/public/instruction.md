# Absolute Value Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Absolute Value` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `absolute_value_behavior.va`:
  - Module `absolute_value_behavior` (entry)
    - position 0: `sigin` (input, electrical)
    - position 1: `sigout` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/absolute_value_behavior.va`
- DUT instance: `XDUT (sigin sigout) absolute_value_behavior`
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

- `P_POSITIVE_INPUT_PASSTHROUGH`: exercise and make observable: For nonnegative `V(sigin)`, drive `sigout` to the same nonnegative voltage. Required traces: `time`, `sigin`, `sigout`.
- `P_NEGATIVE_INPUT_REFLECTION`: exercise and make observable: For negative `V(sigin)`, drive `sigout` to `-V(sigin)`. Required traces: `time`, `sigin`, `sigout`.
- `P_MEMORYLESS_ABSOLUTE_VALUE`: exercise and make observable: The output is an instantaneous absolute-value function of `sigin` with no retained state or waveform schedule. Required traces: `time`, `sigin`, `sigout`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- `P_POSITIVE_INPUT_PASSTHROUGH`: For nonnegative `V(sigin)`, drive `sigout` to the same nonnegative voltage.

- `P_NEGATIVE_INPUT_REFLECTION`: For negative `V(sigin)`, drive `sigout` to `-V(sigin)`.

- `P_MEMORYLESS_ABSOLUTE_VALUE`: The output is an instantaneous absolute-value function of `sigin` with no retained state or waveform schedule.


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
