# Bootstrapped Sampler Charge Metric Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Bootstrapped Sampler Charge Metric` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `bootstrapped_sampler_charge_metric.va`:
  - Module `bootstrapped_sampler_charge_metric` (entry)
    - position 0: `vin` (inout, electrical)
    - position 1: `clk` (inout, electrical)
    - position 2: `rst` (inout, electrical)
    - position 3: `enable` (inout, electrical)
    - position 4: `vhold` (inout, electrical)
    - position 5: `boot_metric` (inout, electrical)
    - position 6: `droop_flag` (inout, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/bootstrapped_sampler_charge_metric.va`
- DUT instance: `XDUT (vin clk rst enable vhold boot_metric droop_flag) bootstrapped_sampler_charge_metric`
- Required saved public traces: `vin`, `clk`, `rst`, `enable`, `vhold`, `boot_metric`, `droop_flag`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `bootstrapped_sampler_charge_metric.vdd` defaults to `0.9`; valid range: finite; overrides vdd.
- `bootstrapped_sampler_charge_metric.vss` defaults to `0.0`; valid range: finite; overrides vss.
- `bootstrapped_sampler_charge_metric.vcm` defaults to `0.45`; valid range: finite; overrides vcm.
- `bootstrapped_sampler_charge_metric.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `bootstrapped_sampler_charge_metric.tr` defaults to `200p from (0:inf)`; valid range: finite; overrides tr.
- `bootstrapped_sampler_charge_metric.droop_step` defaults to `2e-3`; valid range: finite; overrides droop_step.
- `bootstrapped_sampler_charge_metric.droop_tol` defaults to `10e-3`; valid range: finite; overrides droop_tol.
- `bootstrapped_sampler_charge_metric.tick` defaults to `1n from (0:inf)`; valid range: finite; overrides tick.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_ON_RESET_OR_WHEN_DISABLED_CLEAR`: exercise and make observable: On reset or when disabled, clear held output, bootstrap metric, and droop flag. Required traces: `time`, `vin`, `clk`, `rst`, `enable`, `vhold`, `boot_metric`, `droop_flag`.
- `P_ON_EACH_RISING_CLK_EDGE_WHILE`: exercise and make observable: On each rising `clk` edge while enabled, capture `vin` into `vhold`. Required traces: `time`, `vin`, `clk`, `rst`, `enable`, `vhold`, `boot_metric`, `droop_flag`.
- `P_EXPOSE_A_BOOT_METRIC_THAT_INCREASES`: exercise and make observable: Expose a `boot_metric` that increases when the sampled input is near the rails and decreases near common-mode. Required traces: `time`, `vin`, `clk`, `rst`, `enable`, `vhold`, `boot_metric`, `droop_flag`.
- `P_BETWEEN_SAMPLES_HOLD_VHOLD_AND_APPLY`: exercise and make observable: Between samples, hold `vhold` and apply a bounded droop step toward `vcm`. Required traces: `time`, `vin`, `clk`, `rst`, `enable`, `vhold`, `boot_metric`, `droop_flag`.
- `P_ASSERT_DROOP_FLAG_WHEN_ACCUMULATED_HOLD`: exercise and make observable: Assert `droop_flag` when accumulated hold error exceeds `droop_tol`. Required traces: `time`, `vin`, `clk`, `rst`, `enable`, `vhold`, `boot_metric`, `droop_flag`.
- `P_USE_ONLY_VOLTAGE_DOMAIN_BEHAVIORAL_STATE`: exercise and make observable: Use only voltage-domain behavioral state and voltage contributions on public electrical outputs. Required traces: `time`, `vin`, `clk`, `rst`, `enable`, `vhold`, `boot_metric`, `droop_flag`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- On reset or when disabled, clear held output, bootstrap metric, and droop flag.
- On each rising `clk` edge while enabled, capture `vin` into `vhold`.
- Expose a `boot_metric` that increases when the sampled input is near the rails and decreases near common-mode.
- Between samples, hold `vhold` and apply a bounded droop step toward `vcm`.
- Assert `droop_flag` when accumulated hold error exceeds `droop_tol`.
- Use only voltage-domain behavioral state and voltage contributions on public electrical outputs.
- Do not expose pass/fail flags; expose only the public observable metrics named in the interface.


The required trace names are: `time`, `vin`, `clk`, `rst`, `enable`, `vhold`, `boot_metric`, `droop_flag`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
