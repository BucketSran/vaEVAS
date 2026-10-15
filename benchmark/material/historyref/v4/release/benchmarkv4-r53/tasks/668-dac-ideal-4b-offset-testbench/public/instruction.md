# DAC Ideal 4b Offset Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `DAC Ideal 4b Offset` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `dac_ideal_4b_offset.va`:
  - Module `dac_ideal_4b_offset` (entry)
    - position 0: `din0` (input, electrical)
    - position 1: `din1` (input, electrical)
    - position 2: `din2` (input, electrical)
    - position 3: `din3` (input, electrical)
    - position 4: `dout` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/dac_ideal_4b_offset.va`
- DUT instance: `XDUT (din0 din1 din2 din3 dout) dac_ideal_4b_offset`
- Required saved public traces: `din0`, `din1`, `din2`, `din3`, `dout`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `dac_ideal_4b_offset.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `dac_ideal_4b_offset.offset` defaults to `0.239`; valid range: finite; overrides offset.
- `dac_ideal_4b_offset.scaling` defaults to `32.0 * 10.0 / 9.0`; valid range: finite; overrides scaling.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_THRESHOLDED_4BIT_CODE`: exercise and make observable: `din3` is the MSB and `din0` is the LSB of a 4-bit unsigned code using threshold `vth`. Required traces: `time`, `din0`, `din1`, `din2`, `din3`, `dout`.
- `P_OFFSET_PLUS_SCALED_TRIM`: exercise and make observable: The output equals the public `offset` plus the code-scaled trim increment using the public `scaling` factor. Required traces: `time`, `din0`, `din1`, `din2`, `din3`, `dout`.
- `P_EVENT_UPDATED_OUTPUT`: exercise and make observable: `dout` updates on input threshold crossings or initial step and otherwise holds the smooth voltage output. Required traces: `time`, `din0`, `din1`, `din2`, `din3`, `dout`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Interpret `din3` as the MSB and `din0` as the LSB of a 4-bit unsigned code using threshold `vth`. Add the code-scaled trim increment to `offset`, using `scaling` as the public code-to-voltage scale, and drive the result on `dout`.


The required trace names are: `time`, `din0`, `din1`, `din2`, `din3`, `dout`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
