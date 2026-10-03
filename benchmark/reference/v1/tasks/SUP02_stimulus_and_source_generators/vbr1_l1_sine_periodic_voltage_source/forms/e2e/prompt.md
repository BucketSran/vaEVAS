# Task: vbr1_l1_sine_periodic_voltage_source:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L1`
- Category: Stimulus and Source Generators
- Base function: Sine/periodic voltage source
- Domain: `voltage`
- Target artifact(s): `multitone.va`, `tb_multitone_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate all target artifacts: `multitone.va`, `tb_multitone_ref.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `multitone.va` must be co-located with the generated Spectre testbench.
- Include the generated DUT exactly with `ahdl_include "multitone.va"` in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

- `multitone.va` declares module `multitone` with positional ports: `OUT`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=500n maxstep=500p
```

The release harness expects these exact public scalar observables:

- `OUT`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "multitone.va"

XDUT (OUT) multitone

tran tran stop=500n maxstep=500p
save OUT
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `multitone_waveform_matches_public_samples`

## Output Contract

Return exactly these source artifacts:

- `multitone.va`
- `tb_multitone_ref.scs`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Sine/periodic voltage source E2E Companion

Write both the Verilog-A behavioral module and a Spectre transient testbench.

This task form is materialized from the already source-controlled `dut`
release gold for `Sine/periodic voltage source`. It exists to make the public
benchmark split complete without inventing a new circuit kernel or a fake
bugfix.

Domain: pure voltage-domain behavioral Verilog-A.

Public requirements:

- include the behavioral Verilog-A module
- include a transient `tran` analysis
- save the public observables needed by the public behavior checks
- avoid transistor-level devices, AC/noise analysis, and current-domain
  solver assumptions
