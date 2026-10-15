# Divide By Eight Clock Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Divide By Eight Clock` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `divide_by_eight_clock.va`:
  - Module `divide_by_eight_clock` (entry)
    - position 0: `vin` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `en` (input, electrical)
    - position 3: `vout` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/divide_by_eight_clock.va`
- DUT instance: `XDUT (vin rst en vout) divide_by_eight_clock`
- Required saved public traces: `en`, `rst`, `vin`, `vout`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `divide_by_eight_clock.divisor` defaults to `8`; valid range: finite; overrides divisor.
- `divide_by_eight_clock.tdel` defaults to `10p`; valid range: finite; overrides tdel.
- `divide_by_eight_clock.tr` defaults to `20p`; valid range: finite; overrides tr.
- `divide_by_eight_clock.tf` defaults to `20p`; valid range: finite; overrides tf.
- `divide_by_eight_clock.vdd` defaults to `0.9`; valid range: finite; overrides vdd.
- `divide_by_eight_clock.vth` defaults to `0.45`; valid range: finite; overrides vth.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RESET_FORCES_INITIAL_HIGH`: exercise and make observable: Active-high `rst` forces the divider counter to zero and drives `vout` high regardless of input-clock activity. Required traces: `time`, `en`, `rst`, `vin`, `vout`.
- `P_ENABLE_QUALIFIED_DIVIDE_BY_EIGHT`: exercise and make observable: Rising `vin` crossings through `vth` advance the divide-by-eight counter only while `en` is high. Required traces: `time`, `en`, `rst`, `vin`, `vout`.
- `P_OUTPUT_DUTY_AND_LEVEL`: exercise and make observable: The divided waveform follows the specified high/low count window and uses the declared high and low voltage levels. Required traces: `time`, `en`, `rst`, `vin`, `vout`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Initialize the divided output high. An active-high reset forces the counter to zero and the output high. On rising input-clock crossings through `vth`, advance the counter only when reset is low and enable is high. Wrap the counter modulo `divisor` and drive the output high for the first half of the count range and low for the second half.


The required trace names are: `time`, `en`, `rst`, `vin`, `vout`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
