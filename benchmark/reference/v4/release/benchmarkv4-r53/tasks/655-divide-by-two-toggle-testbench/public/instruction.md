# Divide By Two Toggle Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Divide By Two Toggle` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `divide_by_two_toggle.va`:
  - Module `divide_by_two_toggle` (entry)
    - position 0: `clkin` (input, electrical)
    - position 1: `clkout` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/divide_by_two_toggle.va`
- DUT instance: `XDUT (clkin clkout) divide_by_two_toggle`
- Required saved public traces: `clkin`, `clkout`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- No public parameter is declared.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RISING_EDGE_TOGGLE_STATE`: exercise and make observable: Each rising `clkin` crossing through 0.5 V toggles the retained divider state. Required traces: `time`, `clkin`, `clkout`.
- `P_INITIAL_LOW_STATE`: exercise and make observable: The retained state and `clkout` start low before the first input-clock edge. Required traces: `time`, `clkin`, `clkout`.
- `P_OUTPUT_RAIL_LEVELS`: exercise and make observable: `clkout` drives 0.9 V for high state and 0.0 V for low state without amplitude scaling. Required traces: `time`, `clkin`, `clkout`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Initialize the internal state low. On each rising crossing of `clkin` through 0.5 V, toggle the internal state. Drive `clkout` to 0.9 V when the state is high and 0.0 V when it is low.


The required trace names are: `time`, `clkin`, `clkout`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
