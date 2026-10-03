# Clocked Power Ready Sampler Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Clocked Power Ready Sampler` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `clocked_power_ready_sampler.va`:
  - Module `clocked_power_ready_sampler` (entry)
    - position 0: `clk` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `in0` (input, electrical)
    - position 3: `in1` (input, electrical)
    - position 4: `in2` (input, electrical)
    - position 5: `in3` (input, electrical)
    - position 6: `ctrl0` (input, electrical)
    - position 7: `ctrl1` (input, electrical)
    - position 8: `vdd` (input, electrical)
    - position 9: `vss` (input, electrical)
    - position 10: `en` (input, electrical)
    - position 11: `out` (output, electrical)
    - position 12: `flag` (output, electrical)
    - position 13: `metric` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/clocked_power_ready_sampler.va`
- DUT instance: `XDUT (clk rst in0 in1 in2 in3 ctrl0 ctrl1 vdd vss en out flag metric) clocked_power_ready_sampler`
- Required saved public traces: `clk`, `ctrl0`, `ctrl1`, `en`, `flag`, `in0`, `in1`, `in2`, `in3`, `metric`, `out`, `rst`, `vdd`, `vss`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `clocked_power_ready_sampler.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `clocked_power_ready_sampler.vhi` defaults to `0.9`; valid range: finite; overrides vhi.
- `clocked_power_ready_sampler.span_min` defaults to `0.62`; valid range: finite; overrides span_min.
- `clocked_power_ready_sampler.span_max` defaults to `1.28`; valid range: finite; overrides span_max.
- `clocked_power_ready_sampler.tr` defaults to `50p`; valid range: finite; overrides tr.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_MEASURE_ANALOG_INPUTS_RELATIVE_TO_THE`: exercise and make observable: Measure analog inputs relative to the local `vss` rail and normalize by the current local supply span. Let `span = V(vdd, vss)` and treat the row as valid only when `V(en) > vth` and `span_min <= span <= span_max`. If `span` is below `0.05 V`, use `0.05 V` as the normalization span. Define `clip01(y)` as `y` limited to the range `[0, 1]` and `x0..x3 = clip01((V(inN) - V(vss)) / span)`. Required traces: `time`, `clk`, `ctrl0`, `ctrl1`, `en`, `flag`, `in0`, `in1`, `in2`, `in3`, `metric`, `out`, `rst`, `vdd`, `vss`.
- `P_INITIALIZE_THE_READY_COUNT_AND_ALL`: exercise and make observable: Initialize the ready count and all observables to `0 V`. On a rising crossing of `clk` or a rising crossing of `rst`, clear the count and all observables when `rst` is high or the row is not valid. Otherwise, increment a saturating count by one up to a maximum of `4` when both `x0 > 0.25` and `x1 > 0.20`; if that sampled condition is not met, clear the count to zero. Drive `out = vhi * clip01(count / 4.0)`, assert `flag = vhi` when `count >= 3`, and drive `metric = vhi * clip01(abs(x0 - x1))`. Hold the last observable values between update events. Required traces: `time`, `clk`, `ctrl0`, `ctrl1`, `en`, `flag`, `in0`, `in1`, `in2`, `in3`, `metric`, `out`, `rst`, `vdd`, `vss`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- `P_MEASURE_ANALOG_INPUTS_RELATIVE_TO_THE`: Measure analog inputs relative to the local `vss` rail and normalize by the current local supply span. Let `span = V(vdd, vss)` and treat the row as valid only when `V(en) > vth` and `span_min <= span <= span_max`. If `span` is below `0.05 V`, use `0.05 V` as the normalization span. Define `clip01(y)` as `y` limited to the range `[0, 1]` and `x0..x3 = clip01((V(inN) - V(vss)) / span)`.
- `P_INITIALIZE_THE_READY_COUNT_AND_ALL`: Initialize the ready count and all observables to `0 V`. On a rising crossing of `clk` or a rising crossing of `rst`, clear the count and all observables when `rst` is high or the row is not valid. Otherwise, increment a saturating count by one up to a maximum of `4` when both `x0 > 0.25` and `x1 > 0.20`; if that sampled condition is not met, clear the count to zero. Drive `out = vhi * clip01(count / 4.0)`, assert `flag = vhi` when `count >= 3`, and drive `metric = vhi * clip01(abs(x0 - x1))`. Hold the last observable values between update events.

The evaluator saves and may inspect these public trace signals: `time`, `clk`, `ctrl0`, `ctrl1`, `en`, `flag`, `in0`, `in1`, `in2`, `in3`, `metric`, `out`, `rst`, `vdd`, `vss`.


The required trace names are: `time`, `clk`, `ctrl0`, `ctrl1`, `en`, `flag`, `in0`, `in1`, `in2`, `in3`, `metric`, `out`, `rst`, `vdd`, `vss`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
