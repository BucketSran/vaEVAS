# SST Driver Impedance Macro Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `SST Driver Impedance Macro` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `sst_driver_macro.va`:
  - Module `sst_driver_macro` (entry)
    - position 0: `data` (input, electrical)
    - position 1: `enable` (input, electrical)
    - position 2: `clk` (input, electrical)
    - position 3: `rst` (input, electrical)
    - position 4: `z_2` (input, electrical)
    - position 5: `z_1` (input, electrical)
    - position 6: `z_0` (input, electrical)
    - position 7: `vout` (output, electrical)
    - position 8: `swing_metric` (output, electrical)
    - position 9: `z_metric` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/sst_driver_macro.va`
- DUT instance: `XDUT (data enable clk rst z_2 z_1 z_0 vout swing_metric z_metric) sst_driver_macro`
- Required saved public traces: `data`, `enable`, `clk`, `rst`, `z_2`, `z_1`, `z_0`, `vout`, `swing_metric`, `z_metric`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `sst_driver_macro.vdd` defaults to `0.9`; valid range: finite; overrides vdd for module sst_driver_macro.
- `sst_driver_macro.vss` defaults to `0.0`; valid range: finite; overrides vss for module sst_driver_macro.
- `sst_driver_macro.vcm` defaults to `0.45`; valid range: finite; overrides vcm for module sst_driver_macro.
- `sst_driver_macro.vth` defaults to `0.45`; valid range: finite; overrides vth for module sst_driver_macro.
- `sst_driver_macro.swing_min` defaults to `0.15`; valid range: finite; overrides swing_min for module sst_driver_macro.
- `sst_driver_macro.swing_lsb` defaults to `25e-3`; valid range: finite; overrides swing_lsb for module sst_driver_macro.
- `sst_driver_macro.tr` defaults to `200p from (0:inf)`; valid range: finite; overrides tr for module sst_driver_macro.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RESET_DISABLE_CLEAR`: exercise and make observable: Reset or low enable drives common mode and clears public metrics. Required traces: `time`, `rst`, `enable`, `vout`, `swing_metric`, `z_metric`.
- `P_CLOCKED_DATA`: exercise and make observable: The data decision updates only on enabled rising clock edges. Required traces: `time`, `data`, `enable`, `clk`, `rst`, `vout`.
- `P_SWING_MAPPING`: exercise and make observable: The trim code selects swing_min plus swing_lsb per code step. Required traces: `time`, `z_2`, `z_1`, `z_0`, `vout`, `swing_metric`.
- `P_DATA_POLARITY`: exercise and make observable: High and low latched data drive equal-polarity swings around VCM. Required traces: `time`, `data`, `clk`, `rst`, `enable`, `vout`, `swing_metric`.
- `P_TRIM_METRIC`: exercise and make observable: The trim metric maps unsigned codes 0 and 7 to the public rails linearly. Required traces: `time`, `z_2`, `z_1`, `z_0`, `z_metric`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- On reset or when `enable` is low, drive `vout` to `vcm` and clear `swing_metric`.
- On rising `clk` edges while enabled, latch the input data level.
- Convert `z_2..z_0` to an unsigned trim code from 0 to 7.
- Map larger trim codes to larger voltage swing around `vcm` using `swing_min` and `swing_lsb`.
- Drive `vout` above `vcm` for data high and below `vcm` for data low.
- `swing_metric` must expose the selected swing magnitude in volts.
- `z_metric` must expose trim code `k` as `vss + (vdd - vss) * k / 7`, so
  codes 0 and 7 map to the public output rails.


The required trace names are: `time`, `data`, `enable`, `clk`, `rst`, `z_2`, `z_1`, `z_0`, `vout`, `swing_metric`, `z_metric`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
