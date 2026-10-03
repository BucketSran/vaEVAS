# Unary DAC Glitch-energy Metric Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Unary DAC Glitch-energy Metric` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `unary_dac_glitch_energy_metric.va`:
  - Module `unary_dac_glitch_energy_metric` (entry)
    - position 0: `clk` (inout, electrical)
    - position 1: `rst` (inout, electrical)
    - position 2: `enable` (inout, electrical)
    - position 3: `code_2` (inout, electrical)
    - position 4: `code_1` (inout, electrical)
    - position 5: `code_0` (inout, electrical)
    - position 6: `vout` (inout, electrical)
    - position 7: `glitch_metric` (inout, electrical)
    - position 8: `valid` (inout, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/unary_dac_glitch_energy_metric.va`
- DUT instance: `XDUT (clk rst enable code_2 code_1 code_0 vout glitch_metric valid) unary_dac_glitch_energy_metric`
- Required saved public traces: `clk`, `rst`, `enable`, `code_2`, `code_1`, `code_0`, `vout`, `glitch_metric`, `valid`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `unary_dac_glitch_energy_metric.vdd` defaults to `0.9`; valid range: finite; overrides vdd.
- `unary_dac_glitch_energy_metric.vss` defaults to `0.0`; valid range: finite; overrides vss.
- `unary_dac_glitch_energy_metric.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `unary_dac_glitch_energy_metric.tr` defaults to `200p from (0:inf)`; valid range: finite; overrides tr.
- `unary_dac_glitch_energy_metric.tick` defaults to `250p from (0:inf)`; valid range: finite; overrides tick.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_ON_RESET_OR_WHEN_DISABLED_CLEAR`: exercise and make observable: On reset or when disabled, clear output, previous code, glitch metric, and `valid`. Required traces: `time`, `clk`, `rst`, `enable`, `code_2`, `code_1`, `code_0`, `vout`, `glitch_metric`, `valid`.
- `P_ON_EACH_ENABLED_RISING_CLK_EDGE`: exercise and make observable: On each enabled rising `clk` edge, decode the 3-bit code as a unary element count. Required traces: `time`, `clk`, `rst`, `enable`, `code_2`, `code_1`, `code_0`, `vout`, `glitch_metric`, `valid`.
- `P_DRIVE_VOUT_PROPORTIONAL_TO_THE_DECODED`: exercise and make observable: Drive `vout` proportional to the decoded count. Required traces: `time`, `clk`, `rst`, `enable`, `code_2`, `code_1`, `code_0`, `vout`, `glitch_metric`, `valid`.
- `P_DRIVE_GLITCH_METRIC_PROPORTIONAL_TO_THE`: exercise and make observable: Drive `glitch_metric` proportional to the absolute change in count since the previous enabled update. Required traces: `time`, `clk`, `rst`, `enable`, `code_2`, `code_1`, `code_0`, `vout`, `glitch_metric`, `valid`.
- `P_ASSERT_VALID_AFTER_THE_FIRST_ENABLED`: exercise and make observable: Assert `valid` after the first enabled code update. Required traces: `time`, `clk`, `rst`, `enable`, `code_2`, `code_1`, `code_0`, `vout`, `glitch_metric`, `valid`.
- `P_USE_ONLY_VOLTAGE_DOMAIN_BEHAVIORAL_STATE`: exercise and make observable: Use only voltage-domain behavioral state and voltage contributions on public electrical outputs. Required traces: `time`, `clk`, `rst`, `enable`, `code_2`, `code_1`, `code_0`, `vout`, `glitch_metric`, `valid`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- On reset or when disabled, clear output, previous code, glitch metric, and `valid`.
- On each enabled rising `clk` edge, decode the 3-bit code as a unary element count.
- Drive `vout` proportional to the decoded count.
- Drive `glitch_metric` proportional to the absolute change in count since the previous enabled update.
- Assert `valid` after the first enabled code update.
- Use only voltage-domain behavioral state and voltage contributions on public electrical outputs.
- Do not expose pass/fail flags; expose only the public observable metrics named in the interface.


The required trace names are: `time`, `clk`, `rst`, `enable`, `code_2`, `code_1`, `code_0`, `vout`, `glitch_metric`, `valid`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
