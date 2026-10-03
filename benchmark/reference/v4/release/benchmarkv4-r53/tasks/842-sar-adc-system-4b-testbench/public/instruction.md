# 4-bit SAR ADC System Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `4-bit SAR ADC System` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `sar_adc_top.va`:
  - Module `sar_adc_top` (entry)
    - position 0: `vin` (input, electrical)
    - position 1: `clk` (input, electrical)
    - position 2: `rst` (input, electrical)
    - position 3: `start` (input, electrical)
    - position 4: `code_3` (output, electrical)
    - position 5: `code_2` (output, electrical)
    - position 6: `code_1` (output, electrical)
    - position 7: `code_0` (output, electrical)
    - position 8: `done` (output, electrical)
    - position 9: `sample_dbg` (output, electrical)
    - position 10: `dac_dbg` (output, electrical)
- Artifact `sample_hold.va`:
  - Module `sample_hold` (required_submodule)
    - position 0: `vin` (input, electrical)
    - position 1: `clk` (input, electrical)
    - position 2: `rst` (input, electrical)
    - position 3: `sample_en` (input, electrical)
    - position 4: `sample_o` (output, electrical)
    - position 5: `sample_dbg` (output, electrical)
- Artifact `sar_comparator.va`:
  - Module `sar_comparator` (required_submodule)
    - position 0: `sample_i` (input, electrical)
    - position 1: `dac_i` (input, electrical)
    - position 2: `cmp_o` (output, electrical)
- Artifact `sar_controller.va`:
  - Module `sar_controller` (required_submodule)
    - position 0: `clk` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `start` (input, electrical)
    - position 3: `cmp_i` (input, electrical)
    - position 4: `sample_en` (output, electrical)
    - position 5: `trial_3` (output, electrical)
    - position 6: `trial_2` (output, electrical)
    - position 7: `trial_1` (output, electrical)
    - position 8: `trial_0` (output, electrical)
    - position 9: `code_3` (output, electrical)
    - position 10: `code_2` (output, electrical)
    - position 11: `code_1` (output, electrical)
    - position 12: `code_0` (output, electrical)
    - position 13: `done` (output, electrical)
- Artifact `binary_weighted_cdac.va`:
  - Module `binary_weighted_cdac` (required_submodule)
    - position 0: `bit_3` (input, electrical)
    - position 1: `bit_2` (input, electrical)
    - position 2: `bit_1` (input, electrical)
    - position 3: `bit_0` (input, electrical)
    - position 4: `dac_o` (output, electrical)
    - position 5: `dac_dbg` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include paths: `./dut/sar_adc_top.va`, `./dut/sample_hold.va`, `./dut/sar_comparator.va`, `./dut/sar_controller.va`, `./dut/binary_weighted_cdac.va`
- DUT instance: `XDUT (vin clk rst start code_3 code_2 code_1 code_0 done sample_dbg dac_dbg) sar_adc_top`
- Required saved public traces: `vin`, `clk`, `rst`, `start`, `code_3`, `code_2`, `code_1`, `code_0`, `done`, `sample_dbg`, `dac_dbg`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `sar_adc_top.vdd` defaults to `0.9` V; valid range: finite and consistent with the declared rail domain; overrides vdd for this module.
- `sar_adc_top.vss` defaults to `0.0` V; valid range: finite and consistent with the declared rail domain; overrides vss for this module.
- `sar_adc_top.vref` defaults to `0.9` V; valid range: finite and consistent with the declared rail domain; overrides vref for this module.
- `sar_adc_top.vth` defaults to `0.45` V; valid range: finite and consistent with the declared rail domain; overrides vth for this module.
- `sar_adc_top.tr` defaults to `200p` s; valid range: tr > 0; overrides tr for this module.
- `sample_hold.vss` defaults to `0.0` V; valid range: finite and consistent with the declared rail domain; overrides vss for this module.
- `sample_hold.vth` defaults to `0.45` V; valid range: finite and consistent with the declared rail domain; overrides vth for this module.
- `sample_hold.tr` defaults to `200p` s; valid range: tr > 0; overrides tr for this module.
- `sar_comparator.vdd` defaults to `0.9` V; valid range: finite and consistent with the declared rail domain; overrides vdd for this module.
- `sar_comparator.vss` defaults to `0.0` V; valid range: finite and consistent with the declared rail domain; overrides vss for this module.
- `sar_comparator.vth` defaults to `0.45` V; valid range: finite and consistent with the declared rail domain; overrides vth for this module.
- `sar_comparator.tr` defaults to `200p` s; valid range: tr > 0; overrides tr for this module.
- `sar_controller.vdd` defaults to `0.9` V; valid range: finite and consistent with the declared rail domain; overrides vdd for this module.
- `sar_controller.vss` defaults to `0.0` V; valid range: finite and consistent with the declared rail domain; overrides vss for this module.
- `sar_controller.vth` defaults to `0.45` V; valid range: finite and consistent with the declared rail domain; overrides vth for this module.
- `sar_controller.tr` defaults to `200p` s; valid range: tr > 0; overrides tr for this module.
- `binary_weighted_cdac.vss` defaults to `0.0` V; valid range: finite and consistent with the declared rail domain; overrides vss for this module.
- `binary_weighted_cdac.vref` defaults to `0.9` V; valid range: finite and consistent with the declared rail domain; overrides vref for this module.
- `binary_weighted_cdac.vth` defaults to `0.45` V; valid range: finite and consistent with the declared rail domain; overrides vth for this module.
- `binary_weighted_cdac.tr` defaults to `200p` s; valid range: tr > 0; overrides tr for this module.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_SAR_RESET_CLEAR`: exercise and make observable: Reset clears conversion state, code, done, sample_dbg, and dac_dbg. Required traces: `time`, `rst`, `code_3`, `code_2`, `code_1`, `code_0`, `done`, `sample_dbg`, `dac_dbg`.
- `P_SAR_SAMPLE_HOLD`: exercise and make observable: The first rising clock edge after start captures vin and sample_dbg holds that value through conversion. Required traces: `time`, `vin`, `clk`, `rst`, `start`, `sample_dbg`.
- `P_SAR_FINAL_CODE`: exercise and make observable: Four MSB-first trials quantize the held sample to the clamped unsigned 4-bit SAR code. Required traces: `time`, `vin`, `clk`, `start`, `code_3`, `code_2`, `code_1`, `code_0`, `done`.
- `P_SAR_DAC_TRIAL`: exercise and make observable: dac_dbg exposes vref times the active trial code divided by 16 and settles to the final-code DAC level. Required traces: `time`, `clk`, `code_3`, `code_2`, `code_1`, `code_0`, `done`, `dac_dbg`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- On reset, clear the conversion state, code outputs, `done`, `sample_dbg`, and `dac_dbg`.
- A rising `start` request arms a new conversion; the next rising `clk` samples `vin` into `sample_hold`.
- The controller then resolves bits from `code_3` down to `code_0`, one bit per rising `clk` edge.
- For each trial code, `binary_weighted_cdac` produces `dac_dbg = vref * trial_code / 16.0`.
- `sar_comparator` keeps the active trial bit when the held sample is greater than or equal to `dac_dbg`; otherwise it clears that bit.
- After bit 0 is resolved, assert `done` high and hold the final output code until reset or the next armed conversion.
- Drive each code bit as `vdd` for logic 1 and `vss` for logic 0.
- `sample_dbg` must expose the held sample voltage used for the active conversion.


The required trace names are: `time`, `vin`, `clk`, `rst`, `start`, `code_3`, `code_2`, `code_1`, `code_0`, `done`, `sample_dbg`, `dac_dbg`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
