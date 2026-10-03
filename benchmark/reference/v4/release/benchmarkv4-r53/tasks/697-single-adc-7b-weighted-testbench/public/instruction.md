# Single ADC 7b Weighted Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Single ADC 7b Weighted` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `single_adc_7b_weighted.va`:
  - Module `single_adc_7b_weighted` (entry)
    - position 0: `din0` (input, electrical)
    - position 1: `din1` (input, electrical)
    - position 2: `din2` (input, electrical)
    - position 3: `din3` (input, electrical)
    - position 4: `din4` (input, electrical)
    - position 5: `din5` (input, electrical)
    - position 6: `din6` (input, electrical)
    - position 7: `dout` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/single_adc_7b_weighted.va`
- DUT instance: `XDUT (din0 din1 din2 din3 din4 din5 din6 dout) single_adc_7b_weighted`
- Required saved public traces: `din0`, `din1`, `din2`, `din3`, `din4`, `din5`, `din6`, `dout`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `single_adc_7b_weighted.vth` defaults to `0.45`; valid range: finite; overrides vth.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_INPUT_THRESHOLDING`: exercise and make observable: Treat each `din` input as high only when it is above `vth`. Required traces: `time`, `din0`, `din1`, `din2`, `din3`, `din4`, `din5`, `din6`, `dout`.
- `P_WEIGHTED_CODE_SUM`: exercise and make observable: Sum the selected 7-bit weights, including the MSB contribution, using the declared weight basis. Required traces: `time`, `din0`, `din1`, `din2`, `din3`, `din4`, `din5`, `din6`, `dout`.
- `P_NORMALIZED_SINGLE_ENDED_OUTPUT`: exercise and make observable: Drive the normalized single-ended ADC output from the weighted code without extra fixed offsets or scale errors. Required traces: `time`, `din0`, `din1`, `din2`, `din3`, `din4`, `din5`, `din6`, `dout`.
- `P_MONOTONIC_CODE_RESPONSE`: exercise and make observable: The output changes monotonically with increasing selected code weight. Required traces: `time`, `din0`, `din1`, `din2`, `din3`, `din4`, `din5`, `din6`, `dout`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Treat each input as high when above `vth`. Sum the selected weights and drive the normalized single-ended ADC output according to the public weight basis. The output should be monotonic with the weighted code and held as a smooth voltage contribution.


The required trace names are: `time`, `din0`, `din1`, `din2`, `din3`, `din4`, `din5`, `din6`, `dout`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
