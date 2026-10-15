# Cascode Gain-cell Headroom Macro Bugfix

## Task Contract

The supplied Verilog-A system violates its public circuit contract. Repair the
complete editable bundle.

## Public Verilog-A Interface

Preserve this exact artifact and module interface:

- Artifact `cascode_gain_cell_headroom.va`:
  - Module `cascode_gain_cell_headroom` (entry)
    - position 0: `vin` (input, electrical)
    - position 1: `vbias` (input, electrical)
    - position 2: `vdd_sense` (input, electrical)
    - position 3: `enable` (input, electrical)
    - position 4: `rst` (input, electrical)
    - position 5: `vout` (output, electrical)
    - position 6: `gain_metric` (output, electrical)
    - position 7: `headroom_ok` (output, electrical)

## Public Parameter Contract

- `cascode_gain_cell_headroom.vss` defaults to `0.0`; valid range: finite; overrides vss.
- `cascode_gain_cell_headroom.vcm` defaults to `0.45`; valid range: finite; overrides vcm.
- `cascode_gain_cell_headroom.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `cascode_gain_cell_headroom.gain` defaults to `1.8`; valid range: finite; overrides gain.
- `cascode_gain_cell_headroom.headroom_drop` defaults to `0.16`; valid range: finite; overrides headroom_drop.
- `cascode_gain_cell_headroom.tr` defaults to `150p from (0:inf)`; valid range: finite; overrides tr.


## Required Behavior

The repaired bundle must satisfy every public property:

- `P_RESET_OR_LOW_ENABLE_DRIVES_VOUT`: restore: Reset or low `enable` drives `vout` to common mode and clears metrics. Required traces: `time`, `vin`, `vbias`, `vdd_sense`, `enable`, `rst`, `vout`, `gain_metric`, `headroom_ok`.
- `P_WHEN_ENABLED_COMPUTE_AN_INVERTING_GAIN`: restore: While enabled compute rail_limit=min(vdd_sense,vbias)-headroom_drop and the inverting raw output vcm-gain*(vin-vcm). Required traces: `time`, `vin`, `vbias`, `vdd_sense`, `enable`, `rst`, `vout`, `gain_metric`, `headroom_ok`.
- `P_CLAMP_THE_OUTPUT_BETWEEN_VSS_AND`: restore: Drive vout=clamp(vcm-gain*(vin-vcm),vss,rail_limit). Required traces: `time`, `vin`, `vbias`, `vdd_sense`, `enable`, `rst`, `vout`, `gain_metric`, `headroom_ok`.
- `P_GAIN_METRIC_REPORTS_THE_ABSOLUTE_OUTPUT`: restore: `gain_metric` reports the absolute output excursion from common mode. Required traces: `time`, `vin`, `vbias`, `vdd_sense`, `enable`, `rst`, `vout`, `gain_metric`, `headroom_ok`.
- `P_HEADROOM_OK_IS_HIGH_ONLY_WHEN`: restore: Drive headroom_ok=0.9V exactly when rail_limit>vcm+0.05V, otherwise vss; reset or disable clears headroom_ok and gain_metric and drives vout=vcm. Required traces: `time`, `vin`, `vbias`, `vdd_sense`, `enable`, `rst`, `vout`, `gain_metric`, `headroom_ok`.


The following canonical public behavior is normative for this derived form:

- Reset or low `enable` drives `vout` to common mode and clears metrics.
- When enabled, compute an inverting gain-cell output around common mode.
- Clamp the output between `vss` and the available headroom limit.
- `gain_metric` reports the absolute output excursion from common mode.
- `headroom_ok` is high only when the available headroom limit remains above common mode.

Compute the available rail as
`rail_limit=min(vdd_sense,vbias)-headroom_drop`. While enabled, drive

`vout = clamp(vcm-gain*(vin-vcm),vss,rail_limit)`

and `gain_metric=abs(vout-vcm)`. Assert `headroom_ok=0.9 V` exactly when
`rail_limit > vcm+0.05 V`, otherwise drive it to vss. Reset or low `enable`
drives `vout=vcm` and clears `gain_metric` and `headroom_ok` to vss.


## Modeling Constraints

- Use deterministic voltage-domain behavioral Verilog-A.
- Do not hard-code validation stimulus, stop times, sample windows, gold internals, or simulator side channels.
- Preserve the exact file set, module graph, ports, parameters, and public traces.
- Do not add debug outputs, validation state, side channels, or stimulus-specific fixes.

## Output Contract

Return the repaired bundle with exactly these paths: `cascode_gain_cell_headroom.va`.
Every supplied `.va` file is editable; do not add or omit files.
