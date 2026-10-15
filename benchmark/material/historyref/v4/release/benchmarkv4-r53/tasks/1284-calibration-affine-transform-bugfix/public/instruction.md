# Calibration Affine Transform Bugfix

## Task Contract

The supplied Verilog-A system violates its public circuit contract. Repair the
complete editable bundle.

## Public Verilog-A Interface

Preserve this exact artifact and module interface:

- Artifact `calibration_affine_transform.va`:
  - Module `calibration_affine_transform` (entry)
    - position 0: `clk` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `raw` (input, electrical)
    - position 3: `gain_ctrl` (input, electrical)
    - position 4: `offset_ctrl` (input, electrical)
    - position 5: `en` (input, electrical)
    - position 6: `out` (output, electrical)
    - position 7: `resid_metric` (output, electrical)

## Public Parameter Contract

- `calibration_affine_transform.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `calibration_affine_transform.vhi` defaults to `0.9`; valid range: finite; overrides vhi.
- `calibration_affine_transform.center` defaults to `0.45`; valid range: finite; overrides center.
- `calibration_affine_transform.gain_base` defaults to `0.50`; valid range: finite; overrides gain_base.
- `calibration_affine_transform.gain_span` defaults to `1.00`; valid range: finite; overrides gain_span.
- `calibration_affine_transform.resid_fullscale` defaults to `0.45`; valid range: finite; overrides resid_fullscale.
- `calibration_affine_transform.tr` defaults to `60p`; valid range: finite; overrides tr.


## Required Behavior

The repaired bundle must satisfy every public property:

- `P_ON_EACH_RISING_CLOCK_CROSSING_COMPUTE`: restore: Update the stored output and residual metric only on each rising clk crossing. Required traces: `time`, `clk`, `en`, `gain_ctrl`, `offset_ctrl`, `out`, `raw`, `resid_metric`, `rst`.
- `P_MAP_GAIN_CTRL_TO_A_PUBLIC`: restore: Let gain = gain_base + gain_span * clip01(V(gain_ctrl) / vhi), offset = V(offset_ctrl) - center, and transformed = center + gain * (V(raw) - center) + offset. Required traces: `time`, `clk`, `en`, `gain_ctrl`, `offset_ctrl`, `out`, `raw`, `resid_metric`, `rst`.
- `P_CLEAR_OUTPUT_AND_METRIC_WHILE_RESET`: restore: At a rising edge, V(rst) > vth or V(en) <= vth stores both outputs at 0 V; otherwise store out = clamp(transformed, 0, vhi). Required traces: `time`, `clk`, `en`, `gain_ctrl`, `offset_ctrl`, `out`, `raw`, `resid_metric`, `rst`.
- `P_EXPOSE_A_BOUNDED_RESIDUAL_METRIC_FOR`: restore: Store resid_metric = vhi * clip01(abs(transformed - V(raw)) / resid_fullscale), where clip01 limits its argument to [0, 1]. Required traces: `time`, `clk`, `en`, `gain_ctrl`, `offset_ctrl`, `out`, `raw`, `resid_metric`, `rst`.
- `P_USE_LOCAL_ANALOG_HELPER_FUNCTIONS_RATHER`: restore: Use local analog helper functions rather than user task/endtask syntax. Required traces: `time`, `clk`, `en`, `gain_ctrl`, `offset_ctrl`, `out`, `raw`, `resid_metric`, `rst`.


The following canonical public behavior is normative for this derived form:

- Update the stored output and metric only on each rising `clk` crossing. At that edge, if `V(rst) > vth` or `V(en) <= vth`, store `out = 0 V` and `resid_metric = 0 V`.
- Otherwise let `gain = gain_base + gain_span * clip01(V(gain_ctrl) / vhi)` and `offset = V(offset_ctrl) - center`.
- Compute `transformed = center + gain * (V(raw) - center) + offset` and store `out = clamp(transformed, 0, vhi)`.
- Store `resid_metric = vhi * clip01(abs(transformed - V(raw)) / resid_fullscale)`. Here `clip01(x)` limits `x` to `[0, 1]`.
- Use local analog helper functions rather than user task/endtask syntax.


## Modeling Constraints

- Use deterministic voltage-domain behavioral Verilog-A.
- Do not hard-code validation stimulus, stop times, sample windows, gold internals, or simulator side channels.
- Preserve the exact file set, module graph, ports, parameters, and public traces.
- Do not add debug outputs, validation state, side channels, or stimulus-specific fixes.

## Output Contract

Return the repaired bundle with exactly these paths: `calibration_affine_transform.va`.
Every supplied `.va` file is editable; do not add or omit files.
