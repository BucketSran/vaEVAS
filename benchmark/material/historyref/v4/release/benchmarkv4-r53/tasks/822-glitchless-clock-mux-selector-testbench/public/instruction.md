# Glitchless Clock Mux Selector Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Glitchless Clock Mux Selector` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `glitchless_clock_mux_selector.va`:
  - Module `glitchless_clock_mux_selector` (entry)
    - position 0: `clk_a` (inout, electrical)
    - position 1: `clk_b` (inout, electrical)
    - position 2: `sel` (inout, electrical)
    - position 3: `rst` (inout, electrical)
    - position 4: `enable` (inout, electrical)
    - position 5: `clk_out` (inout, electrical)
    - position 6: `switch_metric` (inout, electrical)
    - position 7: `valid` (inout, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/glitchless_clock_mux_selector.va`
- DUT instance: `XDUT (clk_a clk_b sel rst enable clk_out switch_metric valid) glitchless_clock_mux_selector`
- Required saved public traces: `clk_a`, `clk_b`, `sel`, `rst`, `enable`, `clk_out`, `switch_metric`, `valid`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `glitchless_clock_mux_selector.vdd` defaults to `0.9`; valid range: finite; overrides vdd.
- `glitchless_clock_mux_selector.vss` defaults to `0.0`; valid range: finite; overrides vss.
- `glitchless_clock_mux_selector.vcm` defaults to `0.45`; valid range: finite; overrides vcm.
- `glitchless_clock_mux_selector.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `glitchless_clock_mux_selector.tr` defaults to `200p from (0:inf)`; valid range: finite; overrides tr.
- `glitchless_clock_mux_selector.tick` defaults to `200p from (0:inf)`; valid range: finite; overrides tick.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_ON_RESET_OR_WHEN_DISABLED_DRIVE`: exercise and make observable: On reset or when disabled, drive `clk_out`, `switch_metric`, and `valid` low. Required traces: `time`, `clk_a`, `clk_b`, `sel`, `rst`, `enable`, `clk_out`, `switch_metric`, `valid`.
- `P_ROUTE_CLK_A_WHEN_SEL_IS`: exercise and make observable: Route `clk_a` when `sel` is low and `clk_b` when `sel` is high. Required traces: `time`, `clk_a`, `clk_b`, `sel`, `rst`, `enable`, `clk_out`, `switch_metric`, `valid`.
- `P_WHEN_SEL_CHANGES_WAIT_UNTIL_BOTH`: exercise and make observable: When `sel` changes, wait until both input clocks are low before changing the active source. Required traces: `time`, `clk_a`, `clk_b`, `sel`, `rst`, `enable`, `clk_out`, `switch_metric`, `valid`.
- `P_EXPOSE_A_SWITCH_EVENT_ON_SWITCH`: exercise and make observable: Expose a switch event on `switch_metric` for one output cycle after the selected source changes. Required traces: `time`, `clk_a`, `clk_b`, `sel`, `rst`, `enable`, `clk_out`, `switch_metric`, `valid`.
- `P_ASSERT_VALID_AFTER_THE_SELECTED_SOURCE`: exercise and make observable: Assert `valid` after the selected source has produced one clean output edge. Required traces: `time`, `clk_a`, `clk_b`, `sel`, `rst`, `enable`, `clk_out`, `switch_metric`, `valid`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- On reset or when disabled, drive `clk_out`, `switch_metric`, and `valid` low.
- Route `clk_a` when `sel` is low and `clk_b` when `sel` is high.
- When `sel` changes, wait until both input clocks are low before changing the active source.
- Expose a switch event on `switch_metric` for one output cycle after the selected source changes.
- Assert `valid` after the selected source has produced one clean output edge.
- Use only voltage-domain behavioral state and voltage contributions on public electrical outputs.
- Do not expose pass/fail flags; expose only the public observable metrics named in the interface.


The required trace names are: `time`, `clk_a`, `clk_b`, `sel`, `rst`, `enable`, `clk_out`, `switch_metric`, `valid`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
