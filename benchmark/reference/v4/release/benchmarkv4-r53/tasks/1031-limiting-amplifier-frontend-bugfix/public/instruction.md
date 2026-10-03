# Limiting Amplifier Frontend Bugfix

## Task Contract

The supplied Verilog-A system violates its public circuit contract. Repair the
complete editable bundle.

## Public Verilog-A Interface

Preserve this exact artifact and module interface:

- Artifact `limiting_amplifier_frontend.va`:
  - Module `limiting_amplifier_frontend` (entry)
    - position 0: `clk` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `vin` (input, electrical)
    - position 3: `out` (output, electrical)
    - position 4: `metric` (output, electrical)

## Public Parameter Contract

- `limiting_amplifier_frontend.tr` defaults to `1e-10` s; valid range: tr > 0; sets output transition smoothing.
- `limiting_amplifier_frontend.vth` defaults to `0.45` V; valid range: finite real; sets clk and rst logic threshold.


## Required Behavior

The repaired bundle must satisfy every public property:

- `P_INITIAL_AND_RESET_COMMON_MODE`: restore: Initialization sets out to 0.45 V and metric to 0 V; an active-high reset sampled on a rising clk crossing restores the same state. Required traces: `time`, `clk`, `rst`, `out`, `metric`.
- `P_LINEAR_REGION`: restore: For sampled input deviation from -0.09 V through 0.09 V, out equals 0.45 V plus 1.7 times the deviation and metric is 0 V. Required traces: `time`, `clk`, `vin`, `out`, `metric`.
- `P_POSITIVE_LIMITING`: restore: Above the positive boundary, out follows 0.73 V plus 0.45 times excess deviation and metric is 0.85 V. Required traces: `time`, `clk`, `vin`, `out`, `metric`.
- `P_NEGATIVE_LIMITING`: restore: Below the negative boundary, out follows 0.17 V plus 0.45 times excess negative deviation and metric is 0.85 V. Required traces: `time`, `clk`, `vin`, `out`, `metric`.
- `P_OUTPUT_CLAMP`: restore: The final held output remains within 0.04 V through 0.86 V. Required traces: `time`, `out`.
- `P_CLOCKED_HOLD`: restore: Out and metric update only on rising clock crossings and hold between samples. Required traces: `time`, `clk`, `vin`, `out`, `metric`.


The following canonical public behavior is normative for this derived form:

- Initialize `out` to `0.45 V` and `metric` to `0 V`.
- On each rising `clk` crossing through `vth`, sample `vin` unless reset is active.
- On a rising `clk` crossing where `rst` is above `vth`, reset `out` to `0.45 V` and clear `metric` to `0 V`; reset is sampled synchronously with `clk`.
- Treat `x = V(vin) - 0.45 V` as the signed input.
- In the central linear region, when `-0.09 V <= x <= 0.09 V`, drive `out = 0.45 + 1.7 * x` and `metric = 0 V`.
- In the positive limiting region, when `x > 0.09 V`, drive `out = 0.73 + 0.45 * (x - 0.09)` and `metric = 0.85 V`.
- In the negative limiting region, when `x < -0.09 V`, drive `out = 0.17 + 0.45 * (x + 0.09)` and `metric = 0.85 V`.
- Clamp the output to `[0.04 V, 0.86 V]`.


## Modeling Constraints

- Use deterministic rising-edge sampled piecewise limiting behavior.
- Use smoothed voltage contributions only.
- Do not hard-code validation timing or use simulator-specific side channels.
- Preserve the exact file set, module graph, ports, parameters, and public traces.
- Do not add debug outputs, validation state, side channels, or stimulus-specific fixes.

## Output Contract

Return the repaired bundle with exactly these paths: `limiting_amplifier_frontend.va`.
Every supplied `.va` file is editable; do not add or omit files.
