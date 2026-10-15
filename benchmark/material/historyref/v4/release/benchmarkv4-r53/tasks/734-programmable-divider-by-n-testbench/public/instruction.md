# Programmable Divider By N Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Programmable Divider By N` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `programmable_divider_by_n.va`:
  - Module `programmable_divider_by_n` (entry)
    - position 0: `clk` (input, electrical)
    - position 1: `divctrl` (input, electrical)
    - position 2: `out` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/programmable_divider_by_n.va`
- DUT instance: `XDUT (clk divctrl out) programmable_divider_by_n`
- Required saved public traces: `clk`, `divctrl`, `out`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `programmable_divider_by_n.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `programmable_divider_by_n.vh` defaults to `0.9`; valid range: finite; overrides vh.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_DIVIDE_RATIO_EDGE_COUNTING`: exercise and make observable: On rising crossings of `clk` through `vth`, round `divctrl` to the requested divide ratio, clip ratios below one to one, maintain the modulo counter, and assert `out` only when the counter state is zero. Required traces: `time`, `clk`, `divctrl`, `out`.
- `P_CLOCK_THRESHOLD_OBSERVABILITY`: exercise and make observable: Use the public `vth` threshold for edge detection so the declared clock stimulus produces the expected counted edges. Required traces: `time`, `clk`, `divctrl`, `out`.
- `P_OUTPUT_HIGH_LEVEL`: exercise and make observable: Drive high output states near the public `vh` level and low states near `0 V`. Required traces: `time`, `clk`, `divctrl`, `out`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Detect rising crossings of `clk` through `vth`. At each qualifying edge, interpret `divctrl` as the requested divide ratio by rounding it to the nearest integer; clip ratios below one to one. Maintain an internal modulo counter for the current ratio and drive `out` high only when the counter state is zero, low otherwise. For a requested ratio of three, the output is high once every three input clock edges.


The required trace names are: `time`, `clk`, `divctrl`, `out`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
