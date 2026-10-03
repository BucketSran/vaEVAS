# Duty Cycle Meter 8b Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Duty Cycle Meter 8b` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `duty_cycle_meter_8b.va`:
  - Module `duty_cycle_meter_8b` (entry)
    - position 0: `clk_in` (input, electrical)
    - position 1: `valid` (output, electrical)
    - position 2: `duty0` (output, electrical)
    - position 3: `duty1` (output, electrical)
    - position 4: `duty2` (output, electrical)
    - position 5: `duty3` (output, electrical)
    - position 6: `duty4` (output, electrical)
    - position 7: `duty5` (output, electrical)
    - position 8: `duty6` (output, electrical)
    - position 9: `duty7` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/duty_cycle_meter_8b.va`
- DUT instance: `XDUT (clk_in valid duty0 duty1 duty2 duty3 duty4 duty5 duty6 duty7) duty_cycle_meter_8b`
- Required saved public traces: `clk_in`, `valid`, `duty0`, `duty1`, `duty2`, `duty3`, `duty4`, `duty5`, `duty6`, `duty7`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `duty_cycle_meter_8b.vdd` defaults to `0.9` V; valid range: vdd > 0; sets the voltage-coded duty-code and valid high level.
- `duty_cycle_meter_8b.vth` defaults to `0.45` V; valid range: 0 < vth < vdd; sets the clock rising and falling threshold.
- `duty_cycle_meter_8b.tr` defaults to `2e-11` s; valid range: tr > 0; sets output transition smoothing.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_COMPLETE_CYCLE_MEASUREMENT`: exercise and make observable: A new duty result is produced only after observing a rising edge, one intervening falling edge, and the next rising edge. Required traces: `time`, `clk_in`, `valid`, `duty0`, `duty1`, `duty2`, `duty3`, `duty4`, `duty5`, `duty6`, `duty7`.
- `P_HIGH_FRACTION_CODE`: exercise and make observable: For each complete cycle, the unsigned code is the rounded value of 255 times high time divided by period. Required traces: `time`, `clk_in`, `duty0`, `duty1`, `duty2`, `duty3`, `duty4`, `duty5`, `duty6`, `duty7`.
- `P_CODE_SATURATION`: exercise and make observable: The reported duty code is saturated to the inclusive range 0 through 255. Required traces: `time`, `clk_in`, `duty0`, `duty1`, `duty2`, `duty3`, `duty4`, `duty5`, `duty6`, `duty7`.
- `P_VALID_HOLD`: exercise and make observable: valid remains low before the first complete measurement and asserts and holds high after a duty result is available. Required traces: `time`, `clk_in`, `valid`.
- `P_BIT_ORDER_AND_LEVELS`: exercise and make observable: duty0 is the least significant bit and duty7 is the most significant bit; asserted outputs use vdd and inactive outputs use 0 V. Required traces: `time`, `valid`, `duty0`, `duty1`, `duty2`, `duty3`, `duty4`, `duty5`, `duty6`, `duty7`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- Record each rising and falling threshold crossing of `clk_in`.
- For each complete cycle with one falling edge between two rising edges, compute `round(255 * high_time / period)`.
- Saturate the code to 0 through 255.
- Drive `duty0` as the least significant bit through `duty7` as the most significant bit.
- Assert and hold `valid` after a duty-cycle measurement has been made.


The required trace names are: `time`, `clk_in`, `valid`, `duty0`, `duty1`, `duty2`, `duty3`, `duty4`, `duty5`, `duty6`, `duty7`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
