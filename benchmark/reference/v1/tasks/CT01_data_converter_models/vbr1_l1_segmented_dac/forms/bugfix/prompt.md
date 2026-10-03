# Task: vbr1_l1_segmented_dac:bugfix

## Release Task Contract

- Form: `bugfix`
- Level: `L1`
- Category: Data Converter Models
- Base function: Segmented DAC
- Domain: `voltage`
- Target artifact(s): `dut_fixed.va`
- Supplied/reference support artifact(s): `dut_buggy.va`, `tb_segmented_dac_buggy.scs`, `tb_segmented_dac_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Repair the supplied buggy Verilog-A artifact while preserving the public module interface and artifact boundary.
- Use the buggy source plus the public intended behavior below; do not change the companion testbench contract.

## Public Interface To Preserve

- `dut_buggy.va` declares module `segmented_dac` with positional ports: `b0`, `b1`, `t0`, `t1`, `t2`, `vref`, `vss`, `aout`.
- `dut_fixed.va` declares module `segmented_dac` with positional ports: `b0`, `b1`, `t0`, `t1`, `t2`, `vref`, `vss`, `aout`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=150n maxstep=500p
```

The release harness expects these exact public scalar observables:

- `b0`
- `b1`
- `t0`
- `t1`
- `t2`
- `aout`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `safe_time_output_levels_match_expected_segmented_codes`
- `output_is_monotonic_across_programmed_codes`
- `thermometer_segment_weight_is_four_lsb_steps`

## Observed Mismatch Framing

The supplied buggy artifact violates one or more public behavior checks above under the release validation testbench.
Repair the observable behavior without renaming modules, changing ports, or weakening the public testbench contract.

## Output Contract

Return exactly one source artifact named `dut_fixed.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Task: vbm1_segmented_dac_bugfix

The provided voltage-domain segmented DAC has a segment-weighting bug: the
thermometer-coded segment bits contribute half of their intended weight. Fix the
DAC so the binary LSBs and thermometer segment bits produce a monotonic output
with the correct 15-step full-scale normalization.

The fixed module must be named `segmented_dac` and use electrical ports `b0`,
`b1`, `t0`, `t1`, `t2`, `vref`, `vss`, and `aout`. The binary bits should
contribute weights 1 and 2, and each thermometer segment bit should contribute
weight 4. The analog output should be referenced to `vss`.

Use voltage contributions and smoothed output transitions. Do not use current
contributions, `ddt()`, or `idt()`.

Return exactly one complete Verilog-A file named `dut_fixed.va`.
