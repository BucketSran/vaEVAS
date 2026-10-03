# Task: vbr1_l1_unit_element_thermometer_dac:tb

## Release Task Contract

- Form: `tb`
- Level: `L1`
- Category: Data Converter Models
- Base function: Unit-element thermometer DAC
- Domain: `voltage`
- Target artifact(s): `tb_thermometer_dac_15seg_ref.scs`
- Supplied/reference support artifact(s): `thermometer_dac_15seg.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `thermometer_dac_15seg.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "thermometer_dac_15seg.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `thermometer_dac_15seg.va` declares module `thermometer_dac_15seg` with positional ports: `seg0`, `seg1`, `seg2`, `seg3`, `seg4`, `seg5`, `seg6`, `seg7`, `seg8`, `seg9`, `seg10`, `seg11`, `seg12`, `seg13`, `seg14`, `vref`, `vss`, `aout`.

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

Public stimulus/source nodes visible in the reference harness include:

- `vref`
- `vss`
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

## Public Stimulus Schedule Contract

Use this exact public source schedule in generated Spectre testbenches. This schedule is part of the public testbench contract; it is not hidden checker logic.

Public schedule source: `tb_thermometer_dac_15seg_ref.scs`.

```spectre
Vref (vref 0) vsource dc=0.9
Vss (vss 0) vsource dc=0
Vseg0  (seg0  0) vsource type=pwl wave=[0 0 29.5n 0 30n 0.9 180n 0.9]
Vseg1  (seg1  0) vsource type=pwl wave=[0 0 59.5n 0 60n 0.9 180n 0.9]
Vseg2  (seg2  0) vsource type=pwl wave=[0 0 89.5n 0 90n 0.9 180n 0.9]
Vseg3  (seg3  0) vsource type=pwl wave=[0 0 89.5n 0 90n 0.9 180n 0.9]
Vseg4  (seg4  0) vsource type=pwl wave=[0 0 89.5n 0 90n 0.9 180n 0.9]
Vseg5  (seg5  0) vsource type=pwl wave=[0 0 89.5n 0 90n 0.9 180n 0.9]
Vseg6  (seg6  0) vsource type=pwl wave=[0 0 89.5n 0 90n 0.9 180n 0.9]
Vseg7  (seg7  0) vsource type=pwl wave=[0 0 119.5n 0 120n 0.9 180n 0.9]
Vseg8  (seg8  0) vsource type=pwl wave=[0 0 119.5n 0 120n 0.9 180n 0.9]
Vseg9  (seg9  0) vsource type=pwl wave=[0 0 119.5n 0 120n 0.9 180n 0.9]
Vseg10 (seg10 0) vsource type=pwl wave=[0 0 119.5n 0 120n 0.9 180n 0.9]
Vseg11 (seg11 0) vsource type=pwl wave=[0 0 119.5n 0 120n 0.9 180n 0.9]
Vseg12 (seg12 0) vsource type=pwl wave=[0 0 119.5n 0 120n 0.9 180n 0.9]
Vseg13 (seg13 0) vsource type=pwl wave=[0 0 119.5n 0 120n 0.9 180n 0.9]
Vseg14 (seg14 0) vsource type=pwl wave=[0 0 149.5n 0 150n 0.9 180n 0.9]
```

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "thermometer_dac_15seg.va"

Vss (vss 0) vsource dc=0

XDUT (seg0 seg1 seg2 seg3 seg4 seg5 seg6 seg7 seg8 seg9 seg10 seg11 seg12 seg13 seg14 vref vss aout) thermometer_dac_15seg

tran tran stop=180n maxstep=500p
save seg0 seg1 seg2 seg3 seg4 seg5 seg6 seg7 seg8 seg9 seg10 seg11 seg12 seg13 seg14 aout
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `safe_time_output_levels_match_15_segment_thermometer_count`
- `full_scale_counts_all_15_segments`
- `output_is_monotonic_across_programmed_segment_counts`

## Output Contract

Return exactly one source artifact named `tb_thermometer_dac_15seg_ref.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Task: vbm1_thermometer_dac_15seg_tb

Write a Spectre testbench for a pure voltage-domain Verilog-A DUT named
`thermometer_dac_15seg.va`.

Return exactly one complete Spectre netlist named
`tb_thermometer_dac_15seg_ref.scs`.

## DUT Contract

The candidate DUT is:

```verilog
module thermometer_dac_15seg(
    seg0, seg1, seg2, seg3, seg4, seg5, seg6, seg7,
    seg8, seg9, seg10, seg11, seg12, seg13, seg14,
    vref, vss, aout
);
```

All ports are electrical. Segment inputs are 0 V / 0.9 V logic signals. `vref`
is 0.9 V, `vss` is 0 V, and `aout` should equal
`vss + (vref - vss) * active_segment_count / 15`.

## Required Testbench Behavior

- Include the DUT file with `ahdl_include "thermometer_dac_15seg.va"`.
- Instantiate the DUT with the exact port order above.
- Drive programmed active segment counts 0, 1, 2, 7, 14, and 15.
- Keep samples away from segment transitions so the checker can inspect settled
  values.
- Save `seg0` through `seg14` and `aout`.
- Use a transient stop time of at least 180 ns and a `maxstep` no larger than
  500 ps.

The public checker compares the saved waveform to the expected 15-segment
endpoint-scaled DAC levels and verifies full-scale behavior.
