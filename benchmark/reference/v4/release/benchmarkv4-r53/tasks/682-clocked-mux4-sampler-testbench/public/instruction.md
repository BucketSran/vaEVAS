# Clocked Mux4 Sampler Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Clocked Mux4 Sampler` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `clocked_mux4_sampler.va`:
  - Module `clocked_mux4_sampler` (entry)
    - position 0: `dsel0` (input, electrical)
    - position 1: `dsel1` (input, electrical)
    - position 2: `din0` (input, electrical)
    - position 3: `din1` (input, electrical)
    - position 4: `din2` (input, electrical)
    - position 5: `din3` (input, electrical)
    - position 6: `update` (input, electrical)
    - position 7: `rst` (input, electrical)
    - position 8: `clks` (input, electrical)
    - position 9: `dout` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/clocked_mux4_sampler.va`
- DUT instance: `XDUT (dsel0 dsel1 din0 din1 din2 din3 update rst clks dout) clocked_mux4_sampler`
- Required saved public traces: `clks`, `din0`, `din1`, `din2`, `din3`, `dout`, `dsel0`, `dsel1`, `rst`, `update`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `clocked_mux4_sampler.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `clocked_mux4_sampler.tdel` defaults to `1p`; valid range: finite; overrides tdel.
- `clocked_mux4_sampler.tr` defaults to `20p`; valid range: finite; overrides tr.
- `clocked_mux4_sampler.tf` defaults to `20p`; valid range: finite; overrides tf.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RESET_SELECTS_DIN0`: exercise and make observable: While `rst` is high, the selected channel and `dout` are forced to `din0`. Required traces: `time`, `clks`, `din0`, `din1`, `din2`, `din3`, `dout`, `dsel0`, `dsel1`, `rst`, `update`.
- `P_FALLING_CLOCK_UPDATE_SAMPLE`: exercise and make observable: On each falling `clks` crossing with reset inactive and `update` high, latch `dsel0/dsel1` and sample the selected input. Required traces: `time`, `clks`, `din0`, `din1`, `din2`, `din3`, `dout`, `dsel0`, `dsel1`, `rst`, `update`.
- `P_UPDATE_LOW_HOLDS_STATE`: exercise and make observable: On falling `clks` crossings with `update` low, hold the previous selection and output value. Required traces: `time`, `clks`, `din0`, `din1`, `din2`, `din3`, `dout`, `dsel0`, `dsel1`, `rst`, `update`.
- `P_SELECT_DECODE_AND_OUTPUT_TIMING`: exercise and make observable: The held two-bit selection maps to `din0..din3` in binary order and drives `dout` with the declared transition timing. Required traces: `time`, `clks`, `din0`, `din1`, `din2`, `din3`, `dout`, `dsel0`, `dsel1`, `rst`, `update`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

When `rst` is high, force the selected channel to `din0` and drive `dout` from `din0`. On each falling `clks` crossing while reset is inactive, if `update` is high, latch the two select bits and sample the selected input; if `update` is low, hold the previous selection and output value. Drive the held output with the public transition timing.


The required trace names are: `time`, `clks`, `din0`, `din1`, `din2`, `din3`, `dout`, `dsel0`, `dsel1`, `rst`, `update`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
