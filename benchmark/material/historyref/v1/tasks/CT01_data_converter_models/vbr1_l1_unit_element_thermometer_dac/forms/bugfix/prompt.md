# Task: vbr1_l1_unit_element_thermometer_dac:bugfix

## Release Task Contract

- Form: `bugfix`
- Level: `L1`
- Category: Data Converter Models
- Base function: Unit-element thermometer DAC
- Domain: `voltage`
- Target artifact(s): `dut_fixed.va`
- Supplied/reference support artifact(s): `dut_buggy.va`, `tb_thermometer_dac_15seg_buggy.scs`, `tb_thermometer_dac_15seg_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Repair the supplied buggy Verilog-A artifact while preserving the public module interface and artifact boundary.
- Use the buggy source plus the public intended behavior below; do not change the companion testbench contract.

## Public Interface To Preserve

- `dut_buggy.va` declares module `thermometer_dac_15seg` with positional ports: `seg0`, `seg1`, `seg2`, `seg3`, `seg4`, `seg5`, `seg6`, `seg7`, `seg8`, `seg9`, `seg10`, `seg11`, `seg12`, `seg13`, `seg14`, `vref`, `vss`, `aout`.
- `dut_fixed.va` declares module `thermometer_dac_15seg` with positional ports: `seg0`, `seg1`, `seg2`, `seg3`, `seg4`, `seg5`, `seg6`, `seg7`, `seg8`, `seg9`, `seg10`, `seg11`, `seg12`, `seg13`, `seg14`, `vref`, `vss`, `aout`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=180n maxstep=500p
```

The release harness expects these exact public scalar observables:

- `seg0`
- `seg1`
- `seg2`
- `seg3`
- `seg4`
- `seg5`
- `seg6`
- `seg7`
- `seg8`
- `seg9`
- `seg10`
- `seg11`
- `seg12`
- `seg13`
- `seg14`
- `aout`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `safe_time_output_levels_match_15_segment_thermometer_count`
- `full_scale_counts_all_15_segments`
- `output_is_monotonic_across_programmed_segment_counts`

## Observed Mismatch Framing

The supplied buggy artifact violates one or more public behavior checks above under the release validation testbench.
Repair the observable behavior without renaming modules, changing ports, or weakening the public testbench contract.

## Output Contract

Return exactly one source artifact named `dut_fixed.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Task: vbm1_thermometer_dac_15seg_bugfix

Repair the provided pure voltage-domain Verilog-A 4-bit thermometer DAC.

The DUT has fifteen unary segment inputs, `seg0` through `seg14`, plus `vref`,
`vss`, and `aout`. Interpret the segment pins as a 15-segment thermometer code:
each segment above `vth` contributes exactly one unit. Drive `aout` linearly from
`vss` to `vref` using endpoint scaling:

`aout = vss + (vref - vss) * active_segment_count / 15`

The fixed model must count all fifteen unit segments. It must remain purely
voltage-domain, drive `aout` with `transition`, and must not use current
contributions or analog state operators.
