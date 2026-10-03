# Muxed Track-hold Array Readout Bugfix

## Task Contract

The supplied Verilog-A system violates its public circuit contract. Repair the
complete editable bundle.

## Public Verilog-A Interface

Preserve this exact artifact and module interface:

- Artifact `muxed_track_hold_array_top.va`:
  - Module `muxed_track_hold_array_top` (entry)
    - position 0: `vin0` (input, electrical)
    - position 1: `vin1` (input, electrical)
    - position 2: `vin2` (input, electrical)
    - position 3: `clk` (input, electrical)
    - position 4: `rst` (input, electrical)
    - position 5: `sel_1` (input, electrical)
    - position 6: `sel_0` (input, electrical)
    - position 7: `sample_en` (input, electrical)
    - position 8: `vout` (output, electrical)
    - position 9: `channel_metric` (output, electrical)
    - position 10: `valid` (output, electrical)
- Artifact `track_hold_cell.va`:
  - Module `track_hold_cell` (required_submodule)
    - position 0: `vin` (input, electrical)
    - position 1: `clk` (input, electrical)
    - position 2: `rst` (input, electrical)
    - position 3: `sample_en` (input, electrical)
    - position 4: `vhold` (output, electrical)
    - position 5: `held_valid` (output, electrical)
- Artifact `readout_mux.va`:
  - Module `readout_mux` (required_submodule)
    - position 0: `vh0` (input, electrical)
    - position 1: `vh1` (input, electrical)
    - position 2: `vh2` (input, electrical)
    - position 3: `valid0` (input, electrical)
    - position 4: `valid1` (input, electrical)
    - position 5: `valid2` (input, electrical)
    - position 6: `rst` (input, electrical)
    - position 7: `sel_1` (input, electrical)
    - position 8: `sel_0` (input, electrical)
    - position 9: `vout` (output, electrical)
    - position 10: `channel_metric` (output, electrical)
    - position 11: `valid` (output, electrical)

## Public Parameter Contract

- `muxed_track_hold_array_top.vdd` defaults to `0.9`; valid range: finite; overrides vdd.
- `muxed_track_hold_array_top.vss` defaults to `0.0`; valid range: finite; overrides vss.
- `muxed_track_hold_array_top.vcm` defaults to `0.45`; valid range: finite; overrides vcm.
- `muxed_track_hold_array_top.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `muxed_track_hold_array_top.tr` defaults to `200p from (0:inf)`; valid range: finite; overrides tr.
- `track_hold_cell.vdd` defaults to `0.9`; valid range: finite; overrides vdd.
- `track_hold_cell.vss` defaults to `0.0`; valid range: finite; overrides vss.
- `track_hold_cell.vcm` defaults to `0.45`; valid range: finite; overrides vcm.
- `track_hold_cell.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `track_hold_cell.tr` defaults to `200p from (0:inf)`; valid range: finite; overrides tr.
- `readout_mux.vdd` defaults to `0.9`; valid range: finite; overrides vdd.
- `readout_mux.vss` defaults to `0.0`; valid range: finite; overrides vss.
- `readout_mux.vcm` defaults to `0.45`; valid range: finite; overrides vcm.
- `readout_mux.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `readout_mux.tr` defaults to `200p from (0:inf)`; valid range: finite; overrides tr.
- `readout_mux.tick` defaults to `400p from (0:inf)`; valid range: finite; overrides tick.


## Required Behavior

The repaired bundle must satisfy every public property:

- `P_ON_RESET_CLEAR_ALL_HELD_CHANNEL`: restore: On reset, initialize all three held channels and vout to vcm, and drive channel_metric=vss and valid=vss. Required traces: `time`, `vin0`, `vin1`, `vin2`, `clk`, `rst`, `sel_1`, `sel_0`, `sample_en`, `vout`, `channel_metric`, `valid`.
- `P_ON_EACH_ENABLED_SAMPLING_CLOCK_EDGE`: restore: On each enabled sampling clock edge, capture all three input channels into separate hold states. Required traces: `time`, `vin0`, `vin1`, `vin2`, `clk`, `rst`, `sel_1`, `sel_0`, `sample_en`, `vout`, `channel_metric`, `valid`.
- `P_DECODE_SEL_1_SEL_0_AND`: restore: Decode code=(sel_0>vth?1:0)+2*(sel_1>vth?1:0), route held channel 0..2, and propagate its held-valid state. Code 3 holds vout and channel_metric and clears valid. Required traces: `time`, `vin0`, `vin1`, `vin2`, `clk`, `rst`, `sel_1`, `sel_0`, `sample_en`, `vout`, `channel_metric`, `valid`.
- `P_EXPOSE_THE_SELECTED_CHANNEL_INDEX_ON`: restore: For valid codes 0..2, drive channel_metric=clamp(vcm+0.15*code,vss,vdd). Required traces: `time`, `vin0`, `vin1`, `vin2`, `clk`, `rst`, `sel_1`, `sel_0`, `sample_en`, `vout`, `channel_metric`, `valid`.
- `P_HOLD_ALL_CHANNEL_SAMPLES_BETWEEN_SAMPLING`: restore: Hold all channel samples between sampling events. Required traces: `time`, `vin0`, `vin1`, `vin2`, `clk`, `rst`, `sel_1`, `sel_0`, `sample_en`, `vout`, `channel_metric`, `valid`.
- `P_USE_ONLY_VOLTAGE_DOMAIN_BEHAVIORAL_STATE`: restore: Use only voltage-domain behavioral state and voltage contributions on public electrical outputs. Required traces: `time`, `vin0`, `vin1`, `vin2`, `clk`, `rst`, `sel_1`, `sel_0`, `sample_en`, `vout`, `channel_metric`, `valid`.


The following canonical public behavior is normative for this derived form:

- On reset, initialize all three held channels and `vout` to `vcm`, and drive `channel_metric = vss` and `valid = vss`.
- On each enabled sampling clock edge, capture all three input channels into separate hold states.
- Decode `code = (sel_0 > vth ? 1 : 0) + 2*(sel_1 > vth ? 1 : 0)` and route held channel 0, 1, or 2 to `vout`; propagate that channel's held-valid state to `valid`. Invalid code 3 holds the previous `vout` and `channel_metric` and clears `valid`.
- For valid codes 0..2, drive `channel_metric = clamp(vcm + 0.15*code, vss, vdd)`.
- Hold all channel samples between sampling events.
- Use only voltage-domain behavioral state and voltage contributions on public electrical outputs.
- Do not expose pass/fail flags; expose only the public observable metrics named in the interface.


## Modeling Constraints

- Use deterministic voltage-domain behavioral Verilog-A.
- Do not hard-code validation stimulus, stop times, sample windows, gold internals, or simulator side channels.
- Preserve the exact file set, module graph, ports, parameters, and public traces.
- Do not add debug outputs, validation state, side channels, or stimulus-specific fixes.

## Output Contract

Return the repaired bundle with exactly these paths: `muxed_track_hold_array_top.va`, `track_hold_cell.va`, `readout_mux.va`.
Every supplied `.va` file is editable; do not add or omit files.
