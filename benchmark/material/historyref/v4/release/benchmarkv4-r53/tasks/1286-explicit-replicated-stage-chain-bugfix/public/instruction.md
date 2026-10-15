# Explicit Replicated Stage Chain Bugfix

## Task Contract

The supplied Verilog-A system violates its public circuit contract. Repair the
complete editable bundle.

## Public Verilog-A Interface

Preserve this exact artifact and module interface:

- Artifact `explicit_replicated_stage_chain.va`:
  - Module `explicit_replicated_stage_chain` (entry)
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

- `explicit_replicated_stage_chain.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `explicit_replicated_stage_chain.vhi` defaults to `0.9`; valid range: finite; overrides vhi.
- `explicit_replicated_stage_chain.span_min` defaults to `0.62`; valid range: finite; overrides span_min.
- `explicit_replicated_stage_chain.span_max` defaults to `1.28`; valid range: finite; overrides span_max.
- `explicit_replicated_stage_chain.tr` defaults to `50p`; valid range: finite; overrides tr.


## Required Behavior

The repaired bundle must satisfy every public property:

- `P_MEASURE_ANALOG_INPUTS_RELATIVE_TO_THE`: restore: Let xN=clip01((V(inN)-V(vss))/max(V(vdd,vss),0.05)). Invalid enable/span clears all outputs. Otherwise core=0.36*x0+0.28*x1+0.18*x2+0.10*x3+0.04, out=vhi*clip01(core), flag=vhi exactly when core>0.48, and metric=vhi*clip01(abs(x0-x1)/0.55). Controls have no effect. Required traces: `time`, `ctrl0`, `ctrl1`, `en`, `flag`, `in0`, `in1`, `in2`, `in3`, `metric`, `out`, `vdd`, `vss`.
- `P_BUILD_A_VOLTAGE_DOMAIN_ANALOG_MIXED`: restore: Build a voltage-domain analog/mixed-signal helper or monitor. Explicitly unrolled replicated-stage chain metric replacing generate/genvar syntax with observable stage composition. Required traces: `time`, `ctrl0`, `ctrl1`, `en`, `flag`, `in0`, `in1`, `in2`, `in3`, `metric`, `out`, `vdd`, `vss`.
- `P_VTH_0_45_V_LOGIC_THRESHOLD`: restore: `vth = 0.45 V`: logic threshold for voltage-coded controls. Required traces: `time`, `ctrl0`, `ctrl1`, `en`, `flag`, `in0`, `in1`, `in2`, `in3`, `metric`, `out`, `vdd`, `vss`.
- `P_VHI_0_9_V_HIGH_LEVEL`: restore: `vhi = 0.9 V`: high level for output observables. Required traces: `time`, `ctrl0`, `ctrl1`, `en`, `flag`, `in0`, `in1`, `in2`, `in3`, `metric`, `out`, `vdd`, `vss`.
- `P_SPAN_MIN_0_62_V_SPAN`: restore: `span_min = 0.62 V`, `span_max = 1.28 V`: legal local supply span measured as Required traces: `time`, `ctrl0`, `ctrl1`, `en`, `flag`, `in0`, `in1`, `in2`, `in3`, `metric`, `out`, `vdd`, `vss`.
- `P_TR_50P_OUTPUT_TRANSITION_SMOOTHING_TIME`: restore: `tr = 50p`: output transition smoothing time. Required traces: `time`, `ctrl0`, `ctrl1`, `en`, `flag`, `in0`, `in1`, `in2`, `in3`, `metric`, `out`, `vdd`, `vss`.


The following canonical public behavior is normative for this derived form:

Let `span = V(vdd, vss)` and
`xN = clip01((V(inN) - V(vss)) / max(span, 0.05))` for all four inputs.
The row is valid exactly when `V(en) > vth` and
`span_min <= span <= span_max`; otherwise drive all outputs to `0 V`.
When valid, let `core = 0.36*x0 + 0.28*x1 + 0.18*x2 + 0.10*x3 + 0.04`.
Drive `out = vhi * clip01(core)`, assert `flag = vhi` exactly when
`core > 0.48`, and drive `metric = vhi * clip01(abs(x0 - x1) / 0.55)`.
The `ctrl0` and `ctrl1` inputs do not affect these observables.


## Modeling Constraints

- Use deterministic voltage-domain behavioral Verilog-A.
- Do not hard-code validation stimulus, stop times, sample windows, gold internals, or simulator side channels.
- Preserve the exact file set, module graph, ports, parameters, and public traces.
- Do not add debug outputs, validation state, side channels, or stimulus-specific fixes.

## Output Contract

Return the repaired bundle with exactly these paths: `explicit_replicated_stage_chain.va`.
Every supplied `.va` file is editable; do not add or omit files.
