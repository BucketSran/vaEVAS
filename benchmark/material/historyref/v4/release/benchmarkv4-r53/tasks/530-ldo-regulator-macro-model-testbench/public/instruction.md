# LDO Regulator Macro Model Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `LDO Regulator Macro Model` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `ldo_regulator_macro_model.va`:
  - Module `ldo_regulator_macro_model` (entry)
    - position 0: `clk` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `vin` (input, electrical)
    - position 3: `out` (output, electrical)
    - position 4: `metric` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/ldo_regulator_macro_model.va`
- DUT instance: `XFB_DUT (clk rst vin out metric) ldo_regulator_macro_model`
- Required saved public traces: `clk`, `rst`, `vin`, `out`, `metric`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `ldo_regulator_macro_model.tr` defaults to `1e-10` s; valid range: tr > 0; sets output transition smoothing.
- `ldo_regulator_macro_model.vth` defaults to `0.45` V; valid range: finite real; sets clk and rst logic threshold.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_INITIAL_AND_RESET_STATE`: exercise and make observable: Initialization or active-high reset sets out to 0.60 V and metric to 0.9 V. Required traces: `time`, `rst`, `out`, `metric`.
- `P_LOAD_TARGET`: exercise and make observable: At each eligible rising clock crossing, vin is clamped to 0 through 0.9 V and target equals 0.62 V minus 0.055 times that load. Required traces: `time`, `clk`, `rst`, `vin`, `out`, `metric`.
- `P_FIRST_ORDER_REGULATION`: exercise and make observable: Out advances by 0.35 of the remaining target error on each eligible rising clock crossing. Required traces: `time`, `clk`, `vin`, `out`.
- `P_REGULATED_OUTPUT_CLAMP`: exercise and make observable: The held output remains within 0.25 V through 0.75 V. Required traces: `time`, `out`.
- `P_ERROR_METRIC`: exercise and make observable: Metric equals 0.9 V minus four times the absolute output-to-target error, clamped to 0 through 0.9 V. Required traces: `time`, `vin`, `out`, `metric`.
- `P_CLOCKED_HOLD`: exercise and make observable: Out and metric hold between rising clock crossings except for transition smoothing. Required traces: `time`, `clk`, `vin`, `out`, `metric`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- `clk` and `rst` are voltage-coded logic signals.
- Treat `vin` as a bounded load/disturbance-control voltage, not as the regulator supply rail.
- Initialize and reset the regulated state to `out = 0.60 V` and `metric = 0.9 V`.
- On each rising `clk` crossing through `vth`, clamp `load = V(vin)` to `[0 V, 0.9 V]` and compute the regulation target as `target = 0.62 - 0.055 * load`.
- Update the regulated output state as `out_next = out_prev + 0.35 * (target - out_prev)`.
- Clamp the regulated output state to `[0.25 V, 0.75 V]` before driving `out`.
- Drive `metric = 0.9 - 4.0 * abs(out - target)`, clamped to `[0 V, 0.9 V]`, so regulation error lowers the metric during droop and recovery.
- Keep the model pure voltage-domain behavioral Verilog-A. Do not use branch-current contributions, transistor-level devices, AC/noise analysis, or KCL/KVL regulation loops.


The required trace names are: `time`, `clk`, `rst`, `vin`, `out`, `metric`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
