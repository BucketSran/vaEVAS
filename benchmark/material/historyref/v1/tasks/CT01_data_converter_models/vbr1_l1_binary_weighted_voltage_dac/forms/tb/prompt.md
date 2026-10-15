# Task: vbr1_l1_binary_weighted_voltage_dac:tb

## Release Task Contract

- Form: `tb`
- Level: `L1`
- Category: Data Converter Models
- Base function: Simple 4-bit binary-coded DAC
- Domain: `voltage`
- Target artifact(s): `tb_simple_binary_voltage_dac_4b_ref.scs`
- Supplied/reference support artifact(s): `simple_binary_voltage_dac_4b.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `simple_binary_voltage_dac_4b.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "simple_binary_voltage_dac_4b.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

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

## Public L1 Testbench Stimulus Contract

This TB row should exercise all static codes of a 4-bit binary DAC:

- Drive `vref = 0.9 V` and `vss = 0 V`.
- Apply unsigned binary codes 0 through 15 in increasing order.
- Use 0 V/0.9 V logic levels for `code_0` through `code_3`, with `code_0` as
  the LSB and `code_3` as the MSB.
- Hold each code stable for a visible window before switching to the next code.
- Save all four code bits and `aout` exactly.

The expected public relation is `aout = vss + code/15 * (vref - vss)`,
monotonic from zero-scale to full-scale. Do not generate checker logic.

## Output Contract

Return exactly one source artifact named `tb_simple_binary_voltage_dac_4b_ref.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Task: vbm1_simple_binary_voltage_dac_4b_tb

Write a Spectre testbench for a simple 4-bit binary-coded DAC DUT.

The DUT module is `simple_binary_voltage_dac_4b` with ports `code_0, code_1, code_2, code_3, vref, vss, aout`. All ports are electrical; digital-control ports use 0/0.9 V logic levels. The candidate DUT file will be available as `simple_binary_voltage_dac_4b.va`; include it with `ahdl_include` and instantiate the DUT using the exact module and port names.

The testbench must exercise:
- Implement the simple mathematical 4-bit binary-coded DAC described by the input code and references.
- Interpret `code_0..code_3` as a binary code with weights 1, 2, 4, and 8.
- Drive `aout` linearly between `vss` and `vref` using code/15 and smooth with `transition()`; no unit-element or segmented DAC structure is required.

Stimulus and observability requirements:
- Apply all 16 unsigned binary codes from `0` through `15` in increasing order,
  using the required public stimulus pattern above.
- Save all code bits and `aout`.

Review note: This is a behavioral binary-weighted transfer model, not a unit-element or segmented DAC implementation.

Return exactly one Spectre testbench file named `tb_simple_binary_voltage_dac_4b_ref.scs`.
