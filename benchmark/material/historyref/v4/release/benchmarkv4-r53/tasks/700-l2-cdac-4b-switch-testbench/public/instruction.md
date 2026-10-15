# L2 CDAC 4b Switch Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `L2 CDAC 4b Switch` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `l2_cdac_4b_switch.va`:
  - Module `l2_cdac_4b_switch` (entry)
    - position 0: `din1` (input, electrical)
    - position 1: `din2` (input, electrical)
    - position 2: `din3` (input, electrical)
    - position 3: `din4` (input, electrical)
    - position 4: `rdy` (input, electrical)
    - position 5: `aout` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/l2_cdac_4b_switch.va`
- DUT instance: `XDUT (din1 din2 din3 din4 rdy aout) l2_cdac_4b_switch`
- Required saved public traces: `aout`, `din1`, `din2`, `din3`, `din4`, `rdy`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `l2_cdac_4b_switch.vdd` defaults to `1.1`; valid range: finite; overrides vdd.
- `l2_cdac_4b_switch.vth` defaults to `0.55`; valid range: finite; overrides vth.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_FIRST_READY_EDGE_ARMS_ONLY`: exercise and make observable: The first rising `rdy` edge arms the DAC and leaves the initialized output at zero. Required traces: `time`, `aout`, `din1`, `din2`, `din3`, `din4`, `rdy`.
- `P_READY_SAMPLES_FOUR_BITS`: exercise and make observable: Each later rising `rdy` edge samples `din1..din4` against `vth` with the declared switched weights. Required traces: `time`, `aout`, `din1`, `din2`, `din3`, `din4`, `rdy`.
- `P_SWITCHED_WEIGHT_DENOMINATOR`: exercise and make observable: Compute `switched_weight` and normalize by `8.5` before output scaling. Required traces: `time`, `aout`, `din1`, `din2`, `din3`, `din4`, `rdy`.
- `P_BIPOLAR_CDAC_OUTPUT`: exercise and make observable: Map the sampled ratio to `(switched_weight / 8.5) * 2.0 * vdd - vdd` and hold it between ready edges. Required traces: `time`, `aout`, `din1`, `din2`, `din3`, `din4`, `rdy`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

The first rising `rdy` edge only arms the DAC and leaves the initialized output at zero. On each later rising `rdy` edge, sample `din1..din4` against `vth` with switched weights `0.5, 1, 2, 4` from `din1` through `din4`. The source-normalization basis is a total weight of 8.5: the 7.5 total switched weight plus a fixed non-switching reference contribution of 1.0.

Let `switched_weight` be the sum of the enabled switched weights on that `rdy` edge. Map the sampled ratio to a bipolar single-ended output as `(switched_weight / 8.5) * 2.0 * vdd - vdd`. Thus no enabled input bits produce `-vdd`, and all enabled input bits produce `((7.5 / 8.5) * 2.0 - 1.0) * vdd`.


The required trace names are: `time`, `aout`, `din1`, `din2`, `din3`, `din4`, `rdy`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
