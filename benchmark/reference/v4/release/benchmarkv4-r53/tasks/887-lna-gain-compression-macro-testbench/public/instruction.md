# LNA Gain-compression Macro Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `LNA Gain-compression Macro` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `lna_gain_compression_macro.va`:
  - Module `lna_gain_compression_macro` (entry)
    - position 0: `vin` (inout, electrical)
    - position 1: `enable` (inout, electrical)
    - position 2: `rst` (inout, electrical)
    - position 3: `vout` (inout, electrical)
    - position 4: `gain_metric` (inout, electrical)
    - position 5: `compression_flag` (inout, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/lna_gain_compression_macro.va`
- DUT instance: `XDUT (vin enable rst vout gain_metric compression_flag) lna_gain_compression_macro`
- Required saved public traces: `vin`, `enable`, `rst`, `vout`, `gain_metric`, `compression_flag`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `lna_gain_compression_macro.vdd` defaults to `0.9`; valid range: finite; overrides vdd.
- `lna_gain_compression_macro.vss` defaults to `0.0`; valid range: finite; overrides vss.
- `lna_gain_compression_macro.vcm` defaults to `0.45`; valid range: finite; overrides vcm.
- `lna_gain_compression_macro.small_gain` defaults to `4.0`; valid range: finite; overrides small_gain.
- `lna_gain_compression_macro.input_clip` defaults to `0.18`; valid range: finite; overrides input_clip.
- `lna_gain_compression_macro.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `lna_gain_compression_macro.tr` defaults to `200p from (0:inf)`; valid range: finite; overrides tr.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_ON_RESET_OR_WHEN_DISABLED_DRIVE`: exercise and make observable: On reset or when disabled, drive `vout` to `vcm`, clear `gain_metric`, and clear `compression_flag`. Required traces: `time`, `vin`, `enable`, `rst`, `vout`, `gain_metric`, `compression_flag`.
- `P_WHEN_ENABLED_PROVIDE_HIGH_GAIN_FOR`: exercise and make observable: While enabled compute excess=max(0,abs(vin-vcm)-input_clip) and active_gain=small_gain/(1+excess/0.20). Required traces: `time`, `vin`, `enable`, `rst`, `vout`, `gain_metric`, `compression_flag`.
- `P_REDUCE_EFFECTIVE_GAIN_MONOTONICALLY_WHEN_THE`: exercise and make observable: Drive vout=clamp(vcm+active_gain*(vin-vcm),vss,vdd), with active_gain decreasing monotonically once abs(vin-vcm)>input_clip. Required traces: `time`, `vin`, `enable`, `rst`, `vout`, `gain_metric`, `compression_flag`.
- `P_EXPOSE_ACTIVE_GAIN_ON_GAIN_METRIC`: exercise and make observable: Drive gain_metric=clamp(vdd*active_gain/small_gain,vss,vdd) and compression_flag=vdd exactly when active_gain<0.85*small_gain, otherwise vss. Required traces: `time`, `vin`, `enable`, `rst`, `vout`, `gain_metric`, `compression_flag`.
- `P_CLAMP_VOUT_INSIDE_VSS_VDD`: exercise and make observable: Clamp `vout` inside `[vss, vdd]`. Required traces: `time`, `vin`, `enable`, `rst`, `vout`, `gain_metric`, `compression_flag`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- On reset or when disabled, drive `vout` to `vcm`, clear `gain_metric`, and clear `compression_flag`.
- When enabled, provide high gain for small input deviations around `vcm`.
- Reduce effective gain monotonically when the absolute input deviation exceeds `input_clip`.
- Expose active gain on `gain_metric` and assert `compression_flag` during compressed operation.
- Clamp `vout` inside `[vss, vdd]`.

While enabled, compute

`excess = max(0,abs(vin-vcm)-input_clip)`

`active_gain = small_gain/(1+excess/0.20)`

and drive `vout=clamp(vcm+active_gain*(vin-vcm),vss,vdd)`. Encode active gain
as `gain_metric=clamp(vdd*active_gain/small_gain,vss,vdd)`. Assert
`compression_flag=vdd` exactly when `active_gain < 0.85*small_gain`, otherwise
drive it to vss. Reset or disable drives `vout=vcm` and clears both metric and
flag to vss.


The required trace names are: `time`, `vin`, `enable`, `rst`, `vout`, `gain_metric`, `compression_flag`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
