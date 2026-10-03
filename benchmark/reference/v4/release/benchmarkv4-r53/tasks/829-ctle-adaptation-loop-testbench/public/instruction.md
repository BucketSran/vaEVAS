# CTLE Adaptation Loop Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `CTLE Adaptation Loop` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `ctle_adaptation_loop_top.va`:
  - Module `ctle_adaptation_loop_top` (entry)
    - position 0: `vin` (inout, electrical)
    - position 1: `edge_metric_in` (inout, electrical)
    - position 2: `clk` (inout, electrical)
    - position 3: `rst` (inout, electrical)
    - position 4: `enable` (inout, electrical)
    - position 5: `boost_2` (inout, electrical)
    - position 6: `boost_1` (inout, electrical)
    - position 7: `boost_0` (inout, electrical)
    - position 8: `vout` (inout, electrical)
    - position 9: `adapt_metric` (inout, electrical)
    - position 10: `locked` (inout, electrical)
- Artifact `ctle_boost_core.va`:
  - Module `ctle_boost_core` (required_submodule)
    - position 0: `vin` (inout, electrical)
    - position 1: `boost_2` (inout, electrical)
    - position 2: `boost_1` (inout, electrical)
    - position 3: `boost_0` (inout, electrical)
    - position 4: `vout` (inout, electrical)
- Artifact `boost_adapt_controller.va`:
  - Module `boost_adapt_controller` (required_submodule)
    - position 0: `edge_metric_in` (inout, electrical)
    - position 1: `clk` (inout, electrical)
    - position 2: `rst` (inout, electrical)
    - position 3: `enable` (inout, electrical)
    - position 4: `boost_2` (inout, electrical)
    - position 5: `boost_1` (inout, electrical)
    - position 6: `boost_0` (inout, electrical)
    - position 7: `adapt_metric` (inout, electrical)
    - position 8: `locked` (inout, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include paths: `./dut/ctle_adaptation_loop_top.va`, `./dut/ctle_boost_core.va`, `./dut/boost_adapt_controller.va`
- DUT instance: `XDUT (vin edge_metric_in clk rst enable boost_2 boost_1 boost_0 vout adapt_metric locked) ctle_adaptation_loop_top`
- Required saved public traces: `vin`, `edge_metric_in`, `clk`, `rst`, `enable`, `boost_2`, `boost_1`, `boost_0`, `vout`, `adapt_metric`, `locked`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `ctle_adaptation_loop_top.vdd` defaults to `0.9`; valid range: finite; overrides vdd.
- `ctle_adaptation_loop_top.vss` defaults to `0.0`; valid range: finite; overrides vss.
- `ctle_adaptation_loop_top.vcm` defaults to `0.45`; valid range: finite; overrides vcm.
- `ctle_adaptation_loop_top.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `ctle_adaptation_loop_top.tr` defaults to `200p from (0:inf)`; valid range: finite; overrides tr.
- `ctle_adaptation_loop_top.edge_target` defaults to `0.55` V; valid range: finite; sets the target edge metric for boost adaptation.
- `ctle_adaptation_loop_top.adapt_tol` defaults to `30e-3 from [0:inf)` V; valid range: nonnegative; sets the lock tolerance around edge_target.
- `ctle_boost_core.vdd` defaults to `0.9`; valid range: finite; overrides vdd.
- `ctle_boost_core.vss` defaults to `0.0`; valid range: finite; overrides vss.
- `ctle_boost_core.vcm` defaults to `0.45`; valid range: finite; overrides vcm.
- `ctle_boost_core.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `ctle_boost_core.tr` defaults to `200p from (0:inf)`; valid range: finite; overrides tr.
- `ctle_boost_core.boost_step` defaults to `0.12 from [0:inf)`; valid range: nonnegative; sets the gain increment per boost code.
- `boost_adapt_controller.vdd` defaults to `0.9`; valid range: finite; overrides vdd.
- `boost_adapt_controller.vss` defaults to `0.0`; valid range: finite; overrides vss.
- `boost_adapt_controller.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `boost_adapt_controller.tr` defaults to `200p from (0:inf)`; valid range: finite; overrides tr.
- `boost_adapt_controller.edge_target` defaults to `0.55` V; valid range: finite; sets the target edge metric.
- `boost_adapt_controller.adapt_tol` defaults to `30e-3 from [0:inf)` V; valid range: nonnegative; sets the adaptation lock tolerance.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_ON_RESET_OR_WHEN_DISABLED_CLEAR`: exercise and make observable: On reset or when disabled, clear boost code, output, metric, and `locked`. Required traces: `time`, `vin`, `edge_metric_in`, `clk`, `rst`, `enable`, `boost_2`, `boost_1`, `boost_0`, `vout`, `adapt_metric`, `locked`.
- `P_ON_EACH_ENABLED_RISING_CLK_EDGE`: exercise and make observable: On each enabled rising `clk` edge, compare `edge_metric_in` with `edge_target`. Required traces: `time`, `vin`, `edge_metric_in`, `clk`, `rst`, `enable`, `boost_2`, `boost_1`, `boost_0`, `vout`, `adapt_metric`, `locked`.
- `P_INCREASE_BOOST_CODE_WHEN_EDGE_METRIC`: exercise and make observable: Increase boost code when edge metric is too low and decrease it when too high. Required traces: `time`, `vin`, `edge_metric_in`, `clk`, `rst`, `enable`, `boost_2`, `boost_1`, `boost_0`, `vout`, `adapt_metric`, `locked`.
- `P_DRIVE_VOUT_AS_A_BOOSTED_VERSION`: exercise and make observable: Drive `vout` as a boosted version of `vin - vcm` using the active boost code. Required traces: `time`, `vin`, `edge_metric_in`, `clk`, `rst`, `enable`, `boost_2`, `boost_1`, `boost_0`, `vout`, `adapt_metric`, `locked`.
- `P_ASSERT_LOCKED_AFTER_THREE_CONSECUTIVE_UPDATES`: exercise and make observable: Assert `locked` after three consecutive updates within the target tolerance. Required traces: `time`, `vin`, `edge_metric_in`, `clk`, `rst`, `enable`, `boost_2`, `boost_1`, `boost_0`, `vout`, `adapt_metric`, `locked`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- On reset or when disabled, clear boost code, output, metric, and `locked`.
- On each enabled rising `clk` edge, compare `edge_metric_in` with `edge_target`.
- Increase boost code when edge metric is too low and decrease it when too high.
- Drive `vout` as a boosted version of `vin - vcm` using the active boost code.
- Assert `locked` after three consecutive updates within the target tolerance.
- Use only voltage-domain behavioral state and voltage contributions on public electrical outputs.
- Do not expose pass/fail flags; expose only the public observable metrics named in the interface.


The required trace names are: `time`, `vin`, `edge_metric_in`, `clk`, `rst`, `enable`, `boost_2`, `boost_1`, `boost_0`, `vout`, `adapt_metric`, `locked`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
