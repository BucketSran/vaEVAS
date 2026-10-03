# Task: vbr1_l1_element_shuffler:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L1`
- Category: Calibration, DEM, and Control
- Base function: Element shuffler
- Domain: `voltage`
- Target artifact(s): `element_shuffler.va`, `tb_element_shuffler_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate all target artifacts: `element_shuffler.va`, `tb_element_shuffler_ref.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `element_shuffler.va` must be co-located with the generated Spectre testbench.
- Include the generated DUT exactly with `ahdl_include "element_shuffler.va"` in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

- `element_shuffler.va` declares module `element_shuffler` with positional ports: `clk`, `rst_n`, `out0`, `out1`, `out2`, `out3`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=130n maxstep=500p
```

The release harness expects these exact public scalar observables:

- `clk`
- `rst_n`
- `out0`
- `out1`
- `out2`
- `out3`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `clk`
- `rst_n`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "element_shuffler.va"

XDUT (clk rst_n out0 out1 out2 out3) element_shuffler

tran tran stop=130n maxstep=500p
save clk rst_n out0 out1 out2 out3
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `fixed_time_active_output_sequence_at_20_40_60_80_100_120ns`
- `expected_permutation_sequence_2_0_3_1_2_0`

## Output Contract

Return exactly these source artifacts:

- `element_shuffler.va`
- `tb_element_shuffler_ref.scs`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

## Element shuffler end-to-end

Write both the Verilog-A DUT and Spectre testbench for a clocked one-hot
element shuffler.

The DUT module must be named `element_shuffler` and use electrical ports `clk`,
`rst_n`, `out0`, `out1`, `out2`, and `out3`. `rst_n` is active low. After reset,
successive rising clock edges should produce one-hot active outputs in the
non-monotonic public sequence `out2`, `out0`, `out3`, `out1`, then repeat.

The testbench must stimulate reset and enough rising clock edges to observe at
least six post-reset states, save all public observables, and run a transient
analysis suitable for fixed-time sequence checks.

Return exactly two files: `element_shuffler.va` and `tb_element_shuffler_ref.scs`.
