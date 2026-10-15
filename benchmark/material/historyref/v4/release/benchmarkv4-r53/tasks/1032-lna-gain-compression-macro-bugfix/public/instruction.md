# LNA Gain Compression Macro Bugfix

## Task Contract

The supplied Verilog-A system violates its public circuit contract. Repair the
complete editable bundle.

## Public Verilog-A Interface

Preserve this exact artifact and module interface:

- Artifact `lna_gain_compression_macro.va`:
  - Module `lna_gain_compression_macro` (entry)
    - position 0: `clk` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `vin` (input, electrical)
    - position 3: `out` (output, electrical)
    - position 4: `metric` (output, electrical)

## Public Parameter Contract

- `lna_gain_compression_macro.tr` defaults to `1e-10` s; valid range: tr > 0; sets output transition smoothing.
- `lna_gain_compression_macro.vth` defaults to `0.45` V; valid range: finite real; sets clk and rst logic threshold.
- `lna_gain_compression_macro.gain` defaults to `2.2` V/V; valid range: gain > 0; sets small-signal gain about 0.45 V common mode.


## Required Behavior

The repaired bundle must satisfy every public property:

- `P_INITIAL_AND_RESET_COMMON_MODE`: restore: Initialization sets out to 0.45 V and clears metric; an active-high reset sampled on a rising clk crossing restores the same state. Required traces: `time`, `clk`, `rst`, `out`, `metric`.
- `P_SMALL_SIGNAL_GAIN`: restore: For linear values from 0.14 V through 0.76 V, out equals 0.45 V plus gain times the sampled vin deviation and metric is 0.1 V. Required traces: `time`, `clk`, `vin`, `out`, `metric`.
- `P_POSITIVE_COMPRESSION`: restore: Above linear 0.76 V, excess signal is compressed by factor 0.28 and metric is 0.8 V. Required traces: `time`, `clk`, `vin`, `out`, `metric`.
- `P_NEGATIVE_COMPRESSION`: restore: Below linear 0.14 V, excess signal is compressed by factor 0.28 and metric is 0.8 V. Required traces: `time`, `clk`, `vin`, `out`, `metric`.
- `P_FINAL_OUTPUT_CLAMP`: restore: The final held output remains within 0.04 V through 0.86 V. Required traces: `time`, `out`.
- `P_CLOCKED_HOLD`: restore: Out and metric update on rising clock crossings and hold between samples. Required traces: `time`, `clk`, `vin`, `out`, `metric`.


The following canonical public behavior is normative for this derived form:

- Initialize `out` to the 0.45 V common-mode level and `metric` low.
- Update the held output state on rising `clk` crossings.
- On a rising `clk` crossing where `rst` is high, return the output to common mode and clear `metric`; reset is sampled synchronously with `clk`.
- Compute the small-signal value as `linear = 0.45 + gain * (V(vin) - 0.45)`.
- In the linear region `0.14 <= linear <= 0.76`, drive `out = linear` and
  drive `metric = 0.1`.
- For positive compression, when `linear > 0.76`, drive
  `out = 0.76 + 0.28 * (linear - 0.76)` and drive `metric = 0.8`.
- For negative compression, when `linear < 0.14`, drive
  `out = 0.14 + 0.28 * (linear - 0.14)` and drive `metric = 0.8`.
- Clamp the final output to the public range `0.04 V <= out <= 0.86 V`.

The validation scenario is a public verification scenario for wiring and saved
observables. Do not hard-code its transient stop time, waveform breakpoints, or
sample windows into the DUT.


## Modeling Constraints

- Use deterministic rising-edge sampled piecewise gain compression.
- Use smoothed voltage contributions only.
- Do not use current contributions, transistor-level devices, AC/noise analysis, KCL/KVL assumptions, or validation side channels.
- Preserve the exact file set, module graph, ports, parameters, and public traces.
- Do not add debug outputs, validation state, side channels, or stimulus-specific fixes.

## Output Contract

Return the repaired bundle with exactly these paths: `lna_gain_compression_macro.va`.
Every supplied `.va` file is editable; do not add or omit files.
