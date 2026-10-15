# Task: vbr1_l1_segmented_dac:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L1`
- Category: Data Converter Models
- Base function: Segmented DAC
- Domain: `voltage`
- Target artifact(s): `segmented_dac.va`, `tb_segmented_dac_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate all target artifacts: `segmented_dac.va`, `tb_segmented_dac_ref.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `segmented_dac.va` must be co-located with the generated Spectre testbench.
- Include the generated DUT exactly with `ahdl_include "segmented_dac.va"` in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

- `segmented_dac.va` declares module `segmented_dac` with positional ports: `b0`, `b1`, `t0`, `t1`, `t2`, `vref`, `vss`, `aout`.

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

Public stimulus/source nodes visible in the reference harness include:

- `vref`
- `vss`
- `b0`
- `b1`
- `t0`
- `t1`
- `t2`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "segmented_dac.va"

Vss (vss 0) vsource dc=0

XDUT (b0 b1 t0 t1 t2 vref vss aout) segmented_dac

tran tran stop=150n maxstep=500p
save b0 b1 t0 t1 t2 aout
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `safe_time_output_levels_match_expected_segmented_codes`
- `output_is_monotonic_across_programmed_codes`
- `thermometer_segment_weight_is_four_lsb_steps`

## Output Contract

Return exactly these source artifacts:

- `segmented_dac.va`
- `tb_segmented_dac_ref.scs`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Task: vbm1_segmented_dac_e2e

Write both the Verilog-A DUT and Spectre testbench for a small voltage-domain
segmented DAC.

The DUT module must be named `segmented_dac` and use electrical ports `b0`,
`b1`, `t0`, `t1`, `t2`, and `aout`. Treat `b0`/`b1` as binary LSB controls and
`t0`/`t1`/`t2` as thermometer segment controls. With `vref=0.72`, each binary
LSB contributes `vref/12`, and each thermometer segment contributes four LSB
steps.

The testbench must apply enough codes to show monotonic levels and save all
public observables.

Return exactly two files: `segmented_dac.va` and `tb_segmented_dac_ref.scs`.
