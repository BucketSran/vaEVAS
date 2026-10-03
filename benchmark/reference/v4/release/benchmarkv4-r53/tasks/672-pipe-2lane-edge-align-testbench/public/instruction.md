# Pipe 2lane Edge Align Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Pipe 2lane Edge Align` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `pipe_2lane_edge_align.va`:
  - Module `pipe_2lane_edge_align` (entry)
    - position 0: `din1` (input, electrical)
    - position 1: `din2` (input, electrical)
    - position 2: `clk_align` (input, electrical)
    - position 3: `dout` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/pipe_2lane_edge_align.va`
- DUT instance: `XDUT (din1 din2 clk_align dout) pipe_2lane_edge_align`
- Required saved public traces: `din1`, `din2`, `clk_align`, `dout`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `pipe_2lane_edge_align.vth` defaults to `0.45`; valid range: finite; overrides vth.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_INITIAL_LANE1_STATE`: exercise and make observable: Before alignment edges, the output state initializes from `din1`. Required traces: `time`, `din1`, `dout`.
- `P_RISING_EDGE_LANE1`: exercise and make observable: A rising `clk_align` crossing samples and publishes `din1`. Required traces: `time`, `clk_align`, `din1`, `dout`.
- `P_FALLING_EDGE_LANE2`: exercise and make observable: A falling `clk_align` crossing samples and publishes `din2`. Required traces: `time`, `clk_align`, `din2`, `dout`.
- `P_SELECTED_LEVEL_HOLD`: exercise and make observable: `dout` holds the last selected lane level with full output amplitude between alignment edges. Required traces: `time`, `clk_align`, `din1`, `din2`, `dout`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Initialize the output state from `din1`. On a rising `clk_align` crossing, sample and publish `din1`. On a falling `clk_align` crossing, sample and publish `din2`. Hold the last sampled lane between clock events.


The required trace names are: `time`, `din1`, `din2`, `clk_align`, `dout`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
