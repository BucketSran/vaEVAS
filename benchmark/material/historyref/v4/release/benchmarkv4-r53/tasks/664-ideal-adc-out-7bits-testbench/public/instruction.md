# Ideal ADC Out 7bits Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Ideal ADC Out 7bits` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `ideal_adc_out_7bits_scalar.va`:
  - Module `ideal_adc_out_7bits_scalar` (entry)
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

- Include path: `./dut/ideal_adc_out_7bits_scalar.va`
- DUT instance: `XDUT (din0 din1 din2 din3 din4 din5 din6 dout) ideal_adc_out_7bits_scalar`
- Required saved public traces: `din0`, `din1`, `din2`, `din3`, `din4`, `din5`, `din6`, `dout`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `ideal_adc_out_7bits_scalar.vth` defaults to `0.45`; valid range: finite; overrides vth.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_THRESHOLD_CODE_DETECTION`: exercise and make observable: Each `din` input is interpreted as asserted only when it is above `vth`. Required traces: `time`, `din0`, `din1`, `din2`, `din3`, `din4`, `din5`, `din6`, `dout`.
- `P_WEIGHTED_GROUP_SUM`: exercise and make observable: `din6` through `din2` contribute 16, 8, 4, 2, and 1 unit groups, while `din1` and `din0` contribute half-LSB and quarter-LSB trim groups. Required traces: `time`, `din0`, `din1`, `din2`, `din3`, `din4`, `din5`, `din6`, `dout`.
- `P_SCALED_SCALAR_OUTPUT`: exercise and make observable: `dout` represents the correctly scaled fractional scalar sum without fixed offsets or denominator errors. Required traces: `time`, `din0`, `din1`, `din2`, `din3`, `din4`, `din5`, `din6`, `dout`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Interpret each input as asserted above `vth`. `din6` through `din2` represent the 16, 8, 4, 2, and 1 unit groups of a nominal 5-bit span, while `din1` and `din0` are half-LSB and quarter-LSB trim groups. Sum the asserted groups and normalize by the nominal 5-bit full-scale span before driving `dout`.


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
