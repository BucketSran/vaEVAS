# PAM4 Slicer and Gray Decoder Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `PAM4 Slicer and Gray Decoder` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `pam4_slicer_gray_decoder.va`:
  - Module `pam4_slicer_gray_decoder` (entry)
    - position 0: `vin` (input, electrical)
    - position 1: `clk` (input, electrical)
    - position 2: `rst` (input, electrical)
    - position 3: `enable` (input, electrical)
    - position 4: `bit_msb` (output, electrical)
    - position 5: `bit_lsb` (output, electrical)
    - position 6: `level_metric` (output, electrical)
    - position 7: `valid` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/pam4_slicer_gray_decoder.va`
- DUT instance: `XDUT (vin clk rst enable bit_msb bit_lsb level_metric valid) pam4_slicer_gray_decoder`
- Required saved public traces: `vin`, `clk`, `rst`, `enable`, `bit_msb`, `bit_lsb`, `level_metric`, `valid`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `pam4_slicer_gray_decoder.vdd` defaults to `0.9` V; valid range: vdd > vss; sets the logic-high output level.
- `pam4_slicer_gray_decoder.vss` defaults to `0.0` V; valid range: vss < vdd; sets the logic-low output level.
- `pam4_slicer_gray_decoder.vth` defaults to `0.45` V; valid range: vss < vth < vdd; sets the digital-voltage crossing threshold.
- `pam4_slicer_gray_decoder.t0` defaults to `0.225` V; valid range: t0 < t1; sets lower slice threshold.
- `pam4_slicer_gray_decoder.t1` defaults to `0.45` V; valid range: t0 < t1 < t2; sets middle slice threshold.
- `pam4_slicer_gray_decoder.t2` defaults to `0.675` V; valid range: t1 < t2; sets upper slice threshold.
- `pam4_slicer_gray_decoder.tr` defaults to `2e-10` s; valid range: tr > 0; sets transition smoothing.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RESET_DISABLE_CLEAR`: exercise and make observable: Reset or disable clears both bits, level metric, and valid. Required traces: `time`, `vin`, `clk`, `rst`, `enable`, `bit_msb`, `bit_lsb`, `level_metric`, `valid`.
- `P_RISING_EDGE_SAMPLE_HOLD`: exercise and make observable: vin is sliced only on enabled rising clk edges and outputs hold between samples. Required traces: `time`, `vin`, `clk`, `rst`, `enable`, `bit_msb`, `bit_lsb`, `level_metric`, `valid`.
- `P_PAM4_THRESHOLDS`: exercise and make observable: The three ordered thresholds divide vin into levels zero through three. Required traces: `time`, `vin`, `clk`, `rst`, `enable`, `bit_msb`, `bit_lsb`, `level_metric`, `valid`.
- `P_GRAY_MAPPING`: exercise and make observable: Levels zero through three map to Gray codes 00, 01, 11, and 10. Required traces: `time`, `vin`, `clk`, `rst`, `enable`, `bit_msb`, `bit_lsb`, `level_metric`, `valid`.
- `P_LEVEL_METRIC`: exercise and make observable: level_metric reports the sliced level as vss plus k/3 of the output span. Required traces: `time`, `vin`, `clk`, `rst`, `enable`, `bit_msb`, `bit_lsb`, `level_metric`, `valid`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- On reset or when disabled, clear output bits, `level_metric`, and `valid`.
- On each rising `clk` edge while enabled, slice `vin` into four ordered PAM4 levels using `t0`, `t1`, and `t2`.
- Encode the sliced level with Gray ordering: level 0 -> 00, level 1 -> 01, level 2 -> 11, level 3 -> 10.
- `level_metric` must expose sliced level `k` as
  `vss + (vdd - vss) * k / 3`, for `k` from 0 through 3.
- Assert `valid` after each enabled sample.


The required trace names are: `time`, `vin`, `clk`, `rst`, `enable`, `bit_msb`, `bit_lsb`, `level_metric`, `valid`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
