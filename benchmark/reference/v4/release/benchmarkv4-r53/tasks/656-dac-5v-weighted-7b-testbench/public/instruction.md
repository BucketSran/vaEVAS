# DAC 5V Weighted 7b Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `DAC 5V Weighted 7b` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `dac_5v_weighted_7b.va`:
  - Module `dac_5v_weighted_7b` (entry)
    - position 0: `clks` (input, electrical)
    - position 1: `din0` (input, electrical)
    - position 2: `din1` (input, electrical)
    - position 3: `din2` (input, electrical)
    - position 4: `din3` (input, electrical)
    - position 5: `din4` (input, electrical)
    - position 6: `din5` (input, electrical)
    - position 7: `din6` (input, electrical)
    - position 8: `vout` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/dac_5v_weighted_7b.va`
- DUT instance: `XDUT (clks din0 din1 din2 din3 din4 din5 din6 vout) dac_5v_weighted_7b`
- Required saved public traces: `clks`, `din0`, `din1`, `din2`, `din3`, `din4`, `din5`, `din6`, `vout`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `dac_5v_weighted_7b.vth` defaults to `0.75`; valid range: finite; overrides vth.
- `dac_5v_weighted_7b.tt` defaults to `200p from [1p:inf]`; valid range: finite; overrides tt.
- `dac_5v_weighted_7b.delay` defaults to `1n from [1p:inf]`; valid range: finite; overrides delay.
- `dac_5v_weighted_7b.refp` defaults to `5`; valid range: finite; overrides refp.
- `dac_5v_weighted_7b.refn` defaults to `1`; valid range: finite; overrides refn.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_CLOCKED_SEVEN_BIT_WEIGHTED_SUM`: exercise and make observable: Each rising `clks` crossing samples `din0` through `din6` into the declared seven-bit weighted DAC sum. Required traces: `time`, `clks`, `din0`, `din1`, `din2`, `din3`, `din4`, `din5`, `din6`, `vout`.
- `P_MSB_AND_TERMINATION_CONTRIBUTIONS`: exercise and make observable: `din0` contributes the largest switched weight and the fixed termination contribution is included. Required traces: `time`, `clks`, `din0`, `din1`, `din2`, `din3`, `din4`, `din5`, `din6`, `vout`.
- `P_REFERENCE_ENDPOINTS_AND_SCALE`: exercise and make observable: The output uses the declared `refp` and `refn` endpoints and full DAC scale. Required traces: `time`, `clks`, `din0`, `din1`, `din2`, `din3`, `din4`, `din5`, `din6`, `vout`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

On each rising crossing of `clks` through `vth`, evaluate a 7-bit binary-weighted DAC where `din0` is the largest weight and `din6` is the smallest switched weight. Each bit selects `refp` for high and `refn` for low at its binary fraction. Include the fixed terminating LSB contribution tied to `refn`, then drive the held DAC output.


The required trace names are: `time`, `clks`, `din0`, `din1`, `din2`, `din3`, `din4`, `din5`, `din6`, `vout`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
