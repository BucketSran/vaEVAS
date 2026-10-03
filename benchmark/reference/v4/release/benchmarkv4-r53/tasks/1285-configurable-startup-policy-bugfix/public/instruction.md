# Configurable Startup Policy Bugfix

## Task Contract

The supplied Verilog-A system violates its public circuit contract. Repair the
complete editable bundle.

## Public Verilog-A Interface

Preserve this exact artifact and module interface:

- Artifact `configurable_startup_policy.va`:
  - Module `configurable_startup_policy` (entry)
    - position 0: `in0` (input, electrical)
    - position 1: `in1` (input, electrical)
    - position 2: `in2` (input, electrical)
    - position 3: `in3` (input, electrical)
    - position 4: `ctrl0` (input, electrical)
    - position 5: `ctrl1` (input, electrical)
    - position 6: `vdd` (input, electrical)
    - position 7: `vss` (input, electrical)
    - position 8: `en` (input, electrical)
    - position 9: `out` (output, electrical)
    - position 10: `flag` (output, electrical)
    - position 11: `metric` (output, electrical)

## Public Parameter Contract

- `configurable_startup_policy.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `configurable_startup_policy.vhi` defaults to `0.9`; valid range: finite; overrides vhi.
- `configurable_startup_policy.span_min` defaults to `0.62`; valid range: finite; overrides span_min.
- `configurable_startup_policy.span_max` defaults to `1.28`; valid range: finite; overrides span_max.
- `configurable_startup_policy.tr` defaults to `50p`; valid range: finite; overrides tr.


## Required Behavior

The repaired bundle must satisfy every public property:

- `P_MEASURE_ANALOG_INPUTS_RELATIVE_TO_THE`: restore: Let span=V(vdd,vss) and x0=clip01((V(in0)-V(vss))/max(span,0.05)). Invalid enable/span clears all outputs. Otherwise out=vhi*x0, flag=vhi exactly for 0.24<=x0<=0.72 and clip01(V(ctrl0)/vhi)>0.35, and metric=vhi*clip01(abs(x0-0.48)/0.48). in1..in3 and ctrl1 have no effect. Required traces: `time`, `ctrl0`, `ctrl1`, `en`, `flag`, `in0`, `in1`, `in2`, `in3`, `metric`, `out`, `vdd`, `vss`.
- `P_BUILD_A_VOLTAGE_DOMAIN_ANALOG_MIXED`: restore: Build a voltage-domain analog/mixed-signal helper or monitor. Parameter-style startup policy selector replacing unsupported preprocessor variants with runtime-observable behavior. Required traces: `time`, `ctrl0`, `ctrl1`, `en`, `flag`, `in0`, `in1`, `in2`, `in3`, `metric`, `out`, `vdd`, `vss`.
- `P_VTH_0_45_V_LOGIC_THRESHOLD`: restore: `vth = 0.45 V`: logic threshold for voltage-coded controls. Required traces: `time`, `ctrl0`, `ctrl1`, `en`, `flag`, `in0`, `in1`, `in2`, `in3`, `metric`, `out`, `vdd`, `vss`.
- `P_VHI_0_9_V_HIGH_LEVEL`: restore: `vhi = 0.9 V`: high level for output observables. Required traces: `time`, `ctrl0`, `ctrl1`, `en`, `flag`, `in0`, `in1`, `in2`, `in3`, `metric`, `out`, `vdd`, `vss`.
- `P_SPAN_MIN_0_62_V_SPAN`: restore: `span_min = 0.62 V`, `span_max = 1.28 V`: legal local supply span measured as Required traces: `time`, `ctrl0`, `ctrl1`, `en`, `flag`, `in0`, `in1`, `in2`, `in3`, `metric`, `out`, `vdd`, `vss`.
- `P_TR_50P_OUTPUT_TRANSITION_SMOOTHING_TIME`: restore: `tr = 50p`: output transition smoothing time. Required traces: `time`, `ctrl0`, `ctrl1`, `en`, `flag`, `in0`, `in1`, `in2`, `in3`, `metric`, `out`, `vdd`, `vss`.


The following canonical public behavior is normative for this derived form:

Let `span = V(vdd, vss)` and `x0 = clip01((V(in0) - V(vss)) / max(span, 0.05))`.
The row is valid exactly when `V(en) > vth` and
`span_min <= span <= span_max`; otherwise drive all outputs to `0 V`.
When valid, drive `out = vhi * x0`, assert `flag = vhi` exactly when
`0.24 <= x0 <= 0.72` and `clip01(V(ctrl0) / vhi) > 0.35`, and drive
`metric = vhi * clip01(abs(x0 - 0.48) / 0.48)`. Inputs `in1..in3` and
`ctrl1` do not affect these observables.


## Modeling Constraints

- Use deterministic voltage-domain behavioral Verilog-A.
- Do not hard-code validation stimulus, stop times, sample windows, gold internals, or simulator side channels.
- Preserve the exact file set, module graph, ports, parameters, and public traces.
- Do not add debug outputs, validation state, side channels, or stimulus-specific fixes.

## Output Contract

Return the repaired bundle with exactly these paths: `configurable_startup_policy.va`.
Every supplied `.va` file is editable; do not add or omit files.
