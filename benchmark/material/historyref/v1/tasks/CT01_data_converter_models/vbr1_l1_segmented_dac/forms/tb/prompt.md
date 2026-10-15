# Task: vbr1_l1_segmented_dac:tb

## Release Task Contract

- Form: `tb`
- Level: `L1`
- Category: Data Converter Models
- Base function: Segmented DAC
- Domain: `voltage`
- Target artifact(s): `tb_segmented_dac_ref.scs`
- Supplied/reference support artifact(s): `segmented_dac.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `segmented_dac.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "segmented_dac.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

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

## Output Contract

Return exactly one source artifact named `tb_segmented_dac_ref.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Task: vbm1_segmented_dac_tb

Write a Spectre testbench for a Verilog-A module named `segmented_dac` with
ports `b0 b1 t0 t1 t2 aout`.

The testbench should apply a small sequence of binary and thermometer input
codes that demonstrates monotonic output levels and the four-LSB weight of each
thermometer segment. Save all public inputs and `aout`. Use transient timing
that leaves safe sample windows away from code transitions.

Return exactly one Spectre testbench file named `tb_segmented_dac_ref.scs`.
