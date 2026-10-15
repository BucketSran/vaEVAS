# Current-limited Regulator Macro Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Current-limited Regulator Macro` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `current_limited_regulator_macro.va`:
  - Module `current_limited_regulator_macro` (entry)
    - position 0: `vin` (input, electrical)
    - position 1: `load_demand` (input, electrical)
    - position 2: `enable` (input, electrical)
    - position 3: `rst` (input, electrical)
    - position 4: `vout` (output, electrical)
    - position 5: `limit_metric` (output, electrical)
    - position 6: `regulation_ok` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/current_limited_regulator_macro.va`
- DUT instance: `XDUT (vin load_demand enable rst vout limit_metric regulation_ok) current_limited_regulator_macro demand_limit=0.65 dropout=0.08 vref=0.75`
- Required saved public traces: `vin`, `load_demand`, `enable`, `rst`, `vout`, `limit_metric`, `regulation_ok`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `current_limited_regulator_macro.vdd` defaults to `0.9` V; valid range: vdd > vss; overrides the public vdd behavior parameter consistently for this module.
- `current_limited_regulator_macro.vss` defaults to `0` V; valid range: vss < vdd; overrides the public vss behavior parameter consistently for this module.
- `current_limited_regulator_macro.vref` defaults to `0.75` V; valid range: vref is finite and preserves the public operating range; overrides the public vref behavior parameter consistently for this module.
- `current_limited_regulator_macro.dropout` defaults to `0.08` V; valid range: dropout is finite and preserves the public operating range; overrides the public dropout behavior parameter consistently for this module.
- `current_limited_regulator_macro.demand_limit` defaults to `0.65` V; valid range: demand_limit is finite and preserves the public operating range; overrides the public demand_limit behavior parameter consistently for this module.
- `current_limited_regulator_macro.vth` defaults to `0.45` V; valid range: vth is finite and preserves the public operating range; overrides the public vth behavior parameter consistently for this module.
- `current_limited_regulator_macro.tr` defaults to `2e-10` s; valid range: tr > 0; overrides the public tr behavior parameter consistently for this module.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RESET_DISABLE_CLEAR`: exercise and make observable: Reset or disabled operation drives vout, limit_metric, and regulation_ok low. Required traces: `time`, `vin`, `load_demand`, `enable`, `rst`, `vout`, `limit_metric`, `regulation_ok`.
- `P_NORMAL_REGULATION`: exercise and make observable: With adequate headroom and sub-limit demand, vout equals vref and regulation_ok is asserted. Required traces: `time`, `vin`, `load_demand`, `enable`, `rst`, `vout`, `regulation_ok`.
- `P_DROPOUT_CLAMP`: exercise and make observable: When input headroom is insufficient, vout is clamped to max(vss, vin minus dropout). Required traces: `time`, `vin`, `load_demand`, `enable`, `rst`, `vout`.
- `P_CURRENT_LIMITING`: exercise and make observable: Demand above demand_limit produces limit_metric equal to the overload and reduces vout by that overload subject to rails and dropout. Required traces: `time`, `vin`, `load_demand`, `enable`, `rst`, `vout`, `limit_metric`.
- `P_REGULATION_FLAG`: exercise and make observable: regulation_ok is high only for enabled, non-reset, non-limited operation with enough input headroom. Required traces: `time`, `vin`, `load_demand`, `enable`, `rst`, `regulation_ok`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- On reset or when disabled, drive `vout`, `limit_metric`, and `regulation_ok` low.
- When enabled with enough input headroom and load demand below `demand_limit`, drive `vout` toward `vref`.
- When input headroom is insufficient, clamp the target output below `V(vin) - dropout`.
- When `load_demand` exceeds `demand_limit`, reduce the target output in proportion to the overload and expose the overload amount on `limit_metric`.
- Assert `regulation_ok` only when the commanded target is within the normal regulation window and not current-limited.
- This is a voltage-domain macromodel; the load demand is a voltage-coded proxy and no branch-current oracle is required.


The required trace names are: `time`, `vin`, `load_demand`, `enable`, `rst`, `vout`, `limit_metric`, `regulation_ok`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
