# Task: vbr1_l1_binary_weighted_voltage_dac:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L1`
- Category: Data Converter Models
- Base function: Simple 4-bit binary-coded DAC
- Domain: `voltage`
- Target artifact(s): `simple_binary_voltage_dac_4b.va`, `tb_simple_binary_voltage_dac_4b_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate all target artifacts: `simple_binary_voltage_dac_4b.va`, `tb_simple_binary_voltage_dac_4b_ref.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `simple_binary_voltage_dac_4b.va` must be co-located with the generated Spectre testbench.
- Include the generated DUT exactly with `ahdl_include "simple_binary_voltage_dac_4b.va"` in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

- `simple_binary_voltage_dac_4b.va` declares module `simple_binary_voltage_dac_4b` with positional ports: `code_0`, `code_1`, `code_2`, `code_3`, `vref`, `vss`, `aout`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=165n maxstep=500p
```

The release harness expects these exact public scalar observables:

- `code_0`
- `code_1`
- `code_2`
- `code_3`
- `aout`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `vref`
- `vss`
- `code_0`
- `code_1`
- `code_2`
- `code_3`

## Public Stimulus Schedule Contract

Use this exact public source schedule in generated Spectre testbenches. This schedule is part of the public testbench contract; it is not hidden checker logic.

Public schedule source: `tb_simple_binary_voltage_dac_4b_ref.scs`.

```spectre
Vref (vref 0) vsource dc=0.9
Vss (vss 0) vsource dc=0
// Code samples at 5/15/.../155 ns cover every 4-bit code from 0 through 15.
Vb0 (code_0 0) vsource type=pwl wave=[0 0 9.5n 0 10n 0.9 19.5n 0.9 20n 0 29.5n 0 30n 0.9 39.5n 0.9 40n 0 49.5n 0 50n 0.9 59.5n 0.9 60n 0 69.5n 0 70n 0.9 79.5n 0.9 80n 0 89.5n 0 90n 0.9 99.5n 0.9 100n 0 109.5n 0 110n 0.9 119.5n 0.9 120n 0 129.5n 0 130n 0.9 139.5n 0.9 140n 0 149.5n 0 150n 0.9 165n 0.9]
Vb1 (code_1 0) vsource type=pwl wave=[0 0 9.5n 0 10n 0 19.5n 0 20n 0.9 29.5n 0.9 30n 0.9 39.5n 0.9 40n 0 49.5n 0 50n 0 59.5n 0 60n 0.9 69.5n 0.9 70n 0.9 79.5n 0.9 80n 0 89.5n 0 90n 0 99.5n 0 100n 0.9 109.5n 0.9 110n 0.9 119.5n 0.9 120n 0 129.5n 0 130n 0 139.5n 0 140n 0.9 149.5n 0.9 150n 0.9 165n 0.9]
Vb2 (code_2 0) vsource type=pwl wave=[0 0 9.5n 0 10n 0 19.5n 0 20n 0 29.5n 0 30n 0 39.5n 0 40n 0.9 49.5n 0.9 50n 0.9 59.5n 0.9 60n 0.9 69.5n 0.9 70n 0.9 79.5n 0.9 80n 0 89.5n 0 90n 0 99.5n 0 100n 0 109.5n 0 110n 0 119.5n 0 120n 0.9 129.5n 0.9 130n 0.9 139.5n 0.9 140n 0.9 149.5n 0.9 150n 0.9 165n 0.9]
Vb3 (code_3 0) vsource type=pwl wave=[0 0 9.5n 0 10n 0 19.5n 0 20n 0 29.5n 0 30n 0 39.5n 0 40n 0 49.5n 0 50n 0 59.5n 0 60n 0 69.5n 0 70n 0 79.5n 0 80n 0.9 89.5n 0.9 90n 0.9 99.5n 0.9 100n 0.9 109.5n 0.9 110n 0.9 119.5n 0.9 120n 0.9 129.5n 0.9 130n 0.9 139.5n 0.9 140n 0.9 149.5n 0.9 150n 0.9 165n 0.9]
```

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "simple_binary_voltage_dac_4b.va"

Vss (vss 0) vsource dc=0

XDUT (code_0 code_1 code_2 code_3 vref vss aout) simple_binary_voltage_dac_4b

tran tran stop=165n maxstep=500p
save code_0 code_1 code_2 code_3 aout
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `all_16_binary_codes_match_ideal_levels`
- `code_bits_match_expected_sampled_sequence`
- `monotonic_output`
- `zero_and_full_scale_codes_reach_references`

## Public L1 Behavior Contract

This row is a single 4-bit binary-weighted voltage DAC plus its public
testbench:

- Interpret `code_0` through `code_3` as an unsigned binary code, with
  `code_0` as the LSB and `code_3` as the MSB.
- Drive `aout` linearly between `vss` and `vref` as `code/15`.
- Use a testbench sequence that applies all 16 codes in increasing order with a
  stable window for each code.
- Save all code bits and `aout` so monotonicity, endpoint levels, and
  code-to-output consistency are visible.

The task is a behavioral transfer model; do not implement segmented or
unit-element mismatch behavior here.

## Output Contract

Return exactly these source artifacts:

- `simple_binary_voltage_dac_4b.va`
- `tb_simple_binary_voltage_dac_4b_ref.scs`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Task: vbm1_simple_binary_voltage_dac_4b_e2e

Write both the Verilog-A DUT and Spectre testbench for a simple 4-bit binary-coded DAC.

The DUT module is `simple_binary_voltage_dac_4b` with ports `code_0, code_1, code_2, code_3, vref, vss, aout`. All ports are electrical; digital-control ports use 0/0.9 V logic levels.

Required DUT behavior:
- Implement the simple mathematical 4-bit binary-coded DAC described by the input code and references.
- Interpret `code_0..code_3` as a binary code with weights 1, 2, 4, and 8.
- Drive `aout` linearly between `vss` and `vref` using code/15 and smooth with `transition()`; no unit-element or segmented DAC structure is required.

Required testbench behavior:
- Apply all 16 unsigned binary codes from `0` through `15` in increasing order,
  using the required public stimulus pattern above.
- Save all code bits and `aout`.

Use voltage contributions only in the Verilog-A DUT. Do not use current contributions, `ddt()`, or `idt()`.

Review note: This is a behavioral binary-weighted transfer model, not a unit-element or segmented DAC implementation.

Return exactly two files: `simple_binary_voltage_dac_4b.va` and `tb_simple_binary_voltage_dac_4b_ref.scs`.
