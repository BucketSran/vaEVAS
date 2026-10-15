# Flash Thermometer Centered Sum Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Flash Thermometer Centered Sum` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `flash_thermometer_centered_sum.va`:
  - Module `flash_thermometer_centered_sum` (entry)
    - position 0: `b0` (input, electrical)
    - position 1: `b1` (input, electrical)
    - position 2: `b2` (input, electrical)
    - position 3: `b3` (input, electrical)
    - position 4: `b4` (input, electrical)
    - position 5: `b5` (input, electrical)
    - position 6: `b6` (input, electrical)
    - position 7: `b7` (input, electrical)
    - position 8: `dout` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/flash_thermometer_centered_sum.va`
- DUT instance: `XDUT (b0 b1 b2 b3 b4 b5 b6 b7 dout) flash_thermometer_centered_sum`
- Required saved public traces: `b0`, `b1`, `b2`, `b3`, `b4`, `b5`, `b6`, `b7`, `dout`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `flash_thermometer_centered_sum.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `flash_thermometer_centered_sum.gain` defaults to `0.1125`; valid range: finite; overrides gain.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_THERMOMETER_THRESHOLD_COUNT`: exercise and make observable: Each `b0` through `b7` input above `vth` contributes exactly one count to the thermometer total. Required traces: `time`, `b0`, `b1`, `b2`, `b3`, `b4`, `b5`, `b6`, `b7`, `dout`.
- `P_CENTERED_SUM`: exercise and make observable: The output subtracts the four-count midpoint so the analog sum is centered around zero asserted-input balance. Required traces: `time`, `b0`, `b1`, `b2`, `b3`, `b4`, `b5`, `b6`, `b7`, `dout`.
- `P_OUTPUT_GAIN`: exercise and make observable: The centered count is multiplied by `gain` and driven on `dout` without extra scaling. Required traces: `time`, `b0`, `b1`, `b2`, `b3`, `b4`, `b5`, `b6`, `b7`, `dout`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Count how many thermometer inputs are above `vth`. Center the count around midscale by subtracting four asserted inputs, then scale the centered count by `gain` and drive `dout`.


The required trace names are: `time`, `b0`, `b1`, `b2`, `b3`, `b4`, `b5`, `b6`, `b7`, `dout`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
