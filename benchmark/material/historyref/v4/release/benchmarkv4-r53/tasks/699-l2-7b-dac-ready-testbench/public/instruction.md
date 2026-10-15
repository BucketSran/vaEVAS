# L2 7b DAC Ready Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `L2 7b DAC Ready` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `l2_7b_dac_ready.va`:
  - Module `l2_7b_dac_ready` (entry)
    - position 0: `din1` (input, electrical)
    - position 1: `din2` (input, electrical)
    - position 2: `din3` (input, electrical)
    - position 3: `din4` (input, electrical)
    - position 4: `din5` (input, electrical)
    - position 5: `din6` (input, electrical)
    - position 6: `din7` (input, electrical)
    - position 7: `rdy` (input, electrical)
    - position 8: `aout` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/l2_7b_dac_ready.va`
- DUT instance: `XDUT (din1 din2 din3 din4 din5 din6 din7 rdy aout) l2_7b_dac_ready`
- Required saved public traces: `aout`, `din1`, `din2`, `din3`, `din4`, `din5`, `din6`, `din7`, `rdy`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `l2_7b_dac_ready.vdd` defaults to `0.9`; valid range: finite; overrides vdd.
- `l2_7b_dac_ready.vth` defaults to `0.45`; valid range: finite; overrides vth.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_FIRST_READY_EDGE_ARMS_ONLY`: exercise and make observable: The first rising `rdy` edge arms the DAC and leaves the initialized output at zero. Required traces: `time`, `aout`, `din1`, `din2`, `din3`, `din4`, `din5`, `din6`, `din7`, `rdy`.
- `P_READY_SAMPLES_SEVEN_BITS`: exercise and make observable: Each later rising `rdy` edge samples `din1..din7` against `vth` with the declared switched-capacitor weights. Required traces: `time`, `aout`, `din1`, `din2`, `din3`, `din4`, `din5`, `din6`, `din7`, `rdy`.
- `P_BIPOLAR_WEIGHTED_DAC_OUTPUT`: exercise and make observable: Map the sampled 7-bit weight to the declared bipolar single-ended output with the correct denominator and offset. Required traces: `time`, `aout`, `din1`, `din2`, `din3`, `din4`, `din5`, `din6`, `din7`, `rdy`.
- `P_DAC_OUTPUT_LEVEL_AND_HOLD`: exercise and make observable: Hold `aout` between ready edges and drive the declared voltage scale without half-level errors. Required traces: `time`, `aout`, `din1`, `din2`, `din3`, `din4`, `din5`, `din6`, `din7`, `rdy`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

The first rising `rdy` edge only arms the DAC and leaves the initialized output at zero. On each later rising `rdy` edge, sample `din1..din7` with switched capacitor weights `0.5, 1, 2, 4, 8, 16, 32` from `din1` through `din7`. Normalize the bipolar single-ended output against the full capacitive basis, including one additional fixed non-switching unit capacitance. An all-zero sampled code should drive near `-vdd`; an all-one sampled code remains below `+vdd` because of the fixed unit.


The required trace names are: `time`, `aout`, `din1`, `din2`, `din3`, `din4`, `din5`, `din6`, `din7`, `rdy`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
