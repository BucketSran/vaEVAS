# Task: vbr1_l1_resettable_integrator:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L1`
- Category: Baseband Signal Conditioning
- Base function: Resettable integrator
- Domain: `voltage`
- Target artifact(s): `resettable_integrator.va`, `tb_resettable_integrator_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate all target artifacts: `resettable_integrator.va`, `tb_resettable_integrator_ref.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `resettable_integrator.va` must be co-located with the generated Spectre testbench.
- Include the generated DUT exactly with `ahdl_include "resettable_integrator.va"` in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

- `resettable_integrator.va` declares module `resettable_integrator` with positional ports: `vin`, `rst`, `vout`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=320n maxstep=500p
```

The release harness expects these exact public scalar observables:

- `vin`
- `rst`
- `vout`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `rst`
- `vin`

## Public Stimulus Schedule Contract

Use this exact public source schedule in generated Spectre testbenches. This schedule is part of the public testbench contract; it is not hidden checker logic.

Public schedule source: `tb_resettable_integrator_ref.scs`.

```spectre
Vrst (rst 0) vsource type=pwl wave=[0 0.9 25n 0.9 26n 0 220n 0 221n 0.9 250n 0.9 251n 0 320n 0]
Vin (vin 0) vsource dc=0.002
```

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "resettable_integrator.va"

XDUT (vin rst vout) resettable_integrator

tran tran stop=320n maxstep=500p
save vin rst vout
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `input_drive_present`
- `reset_pulse_exercised`
- `pre_reset_output_integrates_up`
- `reset_clears_integrator`
- `post_reset_integration_restarts`

## Output Contract

Return exactly these source artifacts:

- `resettable_integrator.va`
- `tb_resettable_integrator_ref.scs`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

Write both the Verilog-A DUT and Spectre testbench for a resettable timer integrator.

The DUT module is `resettable_integrator` with ports `vin, rst, vout`. All ports are electrical; digital-control ports use 0/0.9 V logic levels.

Required DUT behavior:
- Use a 1 ns timer update to integrate `vin` into an internal accumulator.
- High `rst` clears the accumulator to 0 V.
- Clamp the accumulator between 0 V and 0.85 V and drive `vout` with `transition()`.

Required testbench behavior:
- Drive a positive input, reset pulse, and post-reset positive input interval.
- Save `vin`, `rst`, and `vout` across pre-reset integration, reset clearing, and restart windows.

Use voltage contributions only in the Verilog-A DUT. Do not use current contributions, `ddt()`, or `idt()`.
