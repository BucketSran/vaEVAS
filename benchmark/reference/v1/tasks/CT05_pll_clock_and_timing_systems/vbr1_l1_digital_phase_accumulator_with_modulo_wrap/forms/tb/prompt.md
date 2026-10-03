# Task: vbr1_l1_digital_phase_accumulator_with_modulo_wrap:tb

## Release Task Contract

- Form: `tb`
- Level: `L1`
- Category: PLL Clock and Timing Systems
- Base function: Digital phase accumulator with modulo wrap
- Domain: `voltage`
- Target artifact(s): `tb_phase_accumulator_timer_wrap_ref.scs`
- Supplied/reference support artifact(s): `phase_accumulator_timer_wrap_ref.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `phase_accumulator_timer_wrap_ref.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "phase_accumulator_timer_wrap_ref.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `phase_accumulator_timer_wrap_ref.va` declares module `phase_accumulator_timer_wrap_ref` with positional ports: `VDD`, `VSS`, `clk_out`, `phase_out`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=75n maxstep=20p errpreset=conservative
```

The release harness expects these exact public scalar observables:

- `clk_out`
- `phase_out`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `VDD`
- `VSS`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "phase_accumulator_timer_wrap_ref.va"

Vvdd (VDD 0) vsource dc=0.9 type=dc
Vvss (VSS 0) vsource dc=0.0 type=dc

IDUT (VDD VSS clk_out phase_out) phase_accumulator_timer_wrap_ref

tran tran stop=75n maxstep=20p errpreset=conservative
save clk_out phase_out
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `phase_accumulator_timer_wrap`

## Output Contract

Return exactly one source artifact named `tb_phase_accumulator_timer_wrap_ref.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

This entry is scoped as an ADPLL/NCO phase-timing primitive, not as a generic digital-logic benchmark. Model the wrapped phase state and derived voltage-domain timing outputs that a behavioral PLL loop would consume.

## Digital phase accumulator with modulo wrap Testbench Companion

Write a Spectre transient testbench for the `Digital phase accumulator with modulo wrap` behavioral
Verilog-A release task. This is the testbench-generation companion for an
already materialized end-to-end task.

The testbench should instantiate the same behavioral DUT or system module used
by the corresponding end-to-end form, drive the public transient scenario, save
the observable waveform or metric signals, and preserve the EVAS/Spectre
validation contract.

Domain: pure voltage-domain behavioral Verilog-A.

Public requirements:

- include a transient `tran` analysis
- save the public observables needed by the checker
- include or instantiate the Verilog-A behavioral module under test
- avoid transistor-level devices, AC/noise analysis, and current-domain
  solver assumptions
