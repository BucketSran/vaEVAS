# Task: vbr1_l1_dac_mismatch_unit_weighting_model:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L1`
- Category: Data Converter Models
- Base function: DAC mismatch/unit-weighting model
- Domain: `voltage`
- Target artifact(s): `dac_mismatch_unit_weighting_model.va`, `tb_dac_mismatch_unit_weighting_model.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate all target artifacts: `dac_mismatch_unit_weighting_model.va`, `tb_dac_mismatch_unit_weighting_model.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `dac_mismatch_unit_weighting_model.va` must be co-located with the generated Spectre testbench.
- Include the generated DUT exactly with `ahdl_include "dac_mismatch_unit_weighting_model.va"` in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

- `dac_mismatch_unit_weighting_model.va` declares module `dac_mismatch_unit_weighting_model` with positional ports: `b0`, `b1`, `b2`, `b3`, `out`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=80n maxstep=0.5n
```

The release harness expects these exact public scalar observables:

- `b0`
- `b1`
- `b2`
- `b3`
- `out`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `b0`
- `b1`
- `b2`
- `b3`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "dac_mismatch_unit_weighting_model.va"

XDUT (b0 b1 b2 b3 out) dac_mismatch_unit_weighting_model

tran tran stop=80n maxstep=0.5n
save b0 b1 b2 b3 out
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `weighted_code_response`
- `explicit_mismatch_terms`
- `bounded_reconstruction_voltage`

## Output Contract

Return exactly these source artifacts:

- `dac_mismatch_unit_weighting_model.va`
- `tb_dac_mismatch_unit_weighting_model.scs`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### DAC mismatch/unit-weighting model (end-to-end)

Write both the Verilog-A behavioral module and a Spectre transient testbench.

Behavioral intent:

Model a 4-bit voltage DAC using explicit nonideal unit weights and a bounded output range.

Module name: `dac_mismatch_unit_weighting_model`.
Domain: pure voltage-domain behavioral Verilog-A.
Do not use current contributions, transistor-level devices, AC/noise analysis,
or KCL/KVL solving assumptions.

Public port contract:

```verilog
module dac_mismatch_unit_weighting_model(b0, b1, b2, b3, out);
input b0, b1, b2, b3;
output out;
electrical b0, b1, b2, b3, out;
```

Signal contract:

b0..b3 are voltage-coded logic bits, low=0 V and high=0.9 V with threshold 0.45 V. out is a bounded voltage reconstruction in [0, 0.9] V.

Saved waveform columns:

```text
b0 b1 b2 b3 out
```

Public transient contract:

```spectre
tran tran stop=80n maxstep=0.5n
```
