# Task: vbr1_l1_edge_interval_timer:tb

## Release Task Contract

- Form: `tb`
- Level: `L1`
- Category: Measurement Instrumentation Flows
- Base function: Edge interval timer
- Domain: `voltage`
- Target artifact(s): `tb_cross_interval_163p333_ref.scs`
- Supplied/reference support artifact(s): `cross_interval_163p333_ref.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `cross_interval_163p333_ref.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "cross_interval_163p333_ref.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `cross_interval_163p333_ref.va` declares module `cross_interval_163p333_ref` with positional ports: `VDD`, `VSS`, `a`, `b`, `delay_out`, `seen_out`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=12n maxstep=5p errpreset=conservative
```

The release harness expects these exact public scalar observables:

- `a`
- `b`
- `delay_out`
- `seen_out`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `VDD`
- `VSS`
- `a`
- `b`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "cross_interval_163p333_ref.va"

Vvdd (VDD 0) vsource dc=1.0 type=dc
Vvss (VSS 0) vsource dc=0.0 type=dc

IDUT (VDD VSS a b delay_out seen_out) cross_interval_163p333_ref

tran tran stop=12n maxstep=5p errpreset=conservative
save a b delay_out seen_out
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `cross_interval_163p333`

## Public L1 Testbench Stimulus Contract

This TB row measures the interval between two public threshold crossings:

- Drive input `a` from low to high near 10 ns.
- Drive input `b` from low to high about 163.333 ps after the `a` crossing.
- Use small transition times and a fine transient `maxstep` so the interval is
  numerically observable.
- Save `a`, `b`, `delay_out`, and `seen_out` exactly.

The expected public relation is: the DUT observes both crossings, asserts the
seen flag, and drives `delay_out` to the measured interval. Do not generate
checker logic.

## Output Contract

Return exactly one source artifact named `tb_cross_interval_163p333_ref.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Edge interval timer Testbench Companion

Write a Spectre transient testbench for the `Edge interval timer` behavioral
Verilog-A release task. This is the testbench-generation companion for an
already materialized end-to-end task.

The testbench should instantiate the same behavioral DUT or system module used
by the corresponding end-to-end form, drive the public transient scenario, save
the observable waveform or metric signals, and preserve the EVAS/Spectre
validation contract.

Domain: pure voltage-domain behavioral Verilog-A.

Public requirements:

- include a transient `tran` analysis
- save the public observables needed by the public behavior checks
- include or instantiate the Verilog-A behavioral module under test
- satisfy the named behavior checks using only public waveforms and side outputs
- avoid transistor-level devices, AC/noise analysis, and current-domain
  solver assumptions
