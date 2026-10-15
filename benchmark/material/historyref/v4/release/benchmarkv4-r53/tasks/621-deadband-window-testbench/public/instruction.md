# Deadband Window Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Deadband Window` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `deadband_window.va`:
  - Module `deadband_window` (entry)
    - position 0: `sigin` (input, electrical)
    - position 1: `sigout` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/deadband_window.va`
- DUT instance: `XDUT (sigin sigout) deadband_window dead_high=0.2 dead_low=-0.2`
- Required saved public traces: `sigin`, `sigout`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `deadband_window.dead_high` defaults to `0.1`; valid range: finite; overrides dead_high.
- `deadband_window.dead_low` defaults to `-0.1`; valid range: finite; overrides dead_low.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_ZERO_INSIDE_DEADBAND`: exercise and make observable: For `dead_low <= V(sigin) <= dead_high`, drive `sigout` to 0 V. Required traces: `time`, `sigin`, `sigout`.
- `P_LOWER_RESIDUE`: exercise and make observable: For `V(sigin) < dead_low`, drive `sigout` to `V(sigin) - dead_low`. Required traces: `time`, `sigin`, `sigout`.
- `P_UPPER_RESIDUE`: exercise and make observable: For `V(sigin) > dead_high`, drive `sigout` to `V(sigin) - dead_high`. Required traces: `time`, `sigin`, `sigout`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- `P_ZERO_INSIDE_DEADBAND`: For `dead_low <= V(sigin) <= dead_high`, drive `sigout` to 0 V.

- `P_LOWER_RESIDUE`: For `V(sigin) < dead_low`, drive `sigout` to `V(sigin) - dead_low`.

- `P_UPPER_RESIDUE`: For `V(sigin) > dead_high`, drive `sigout` to `V(sigin) - dead_high`.


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
