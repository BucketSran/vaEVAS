# Task: vbr1_l1_lfsr_prbs_generator:tb

## Release Task Contract

- Form: `tb`
- Level: `L1`
- Category: Stimulus and Source Generators
- Base function: PRBS stimulus/dither generator
- Domain: `voltage`
- Target artifact(s): `tb_lfsr_ref.scs`
- Supplied/reference support artifact(s): `lfsr.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `lfsr.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "lfsr.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `lfsr.va` declares module `lfsr` with positional ports: `DPN`, `VDD`, `VSS`, `CLK`, `EN`, `RSTB`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=500n maxstep=2n
```

The release harness expects these exact public scalar observables:

- `clk`
- `rstb`
- `dpn`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `vdd`
- `vss`
- `clk`
- `rstb`
- `en`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "lfsr.va"

Vvdd (vdd 0) vsource dc=0.9
Vvss (vss 0) vsource dc=0.0

IDUT (dpn vdd vss clk en rstb) lfsr seed=123

tran tran stop=500n maxstep=2n
save clk rstb dpn
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `lfsr_output_not_stuck`
- `lfsr_has_min_transitions`

## Public L1 Testbench Stimulus Contract

This TB row should expose a running PRBS/LFSR sequence:

- Drive `clk` as a fast periodic 0 V/0.9 V clock.
- Hold reset active at the beginning, then release it and keep enable high.
- Run long enough after reset release for many LFSR updates.
- Save `clk`, `rstb`, and `dpn` exactly.

The expected public relation is: after reset release, `dpn` should toggle many
times and should not remain stuck. Do not generate checker logic.

## Output Contract

Return exactly one source artifact named `tb_lfsr_ref.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# PRBS stimulus/dither generator Testbench Companion

Write a Spectre transient testbench for the `PRBS stimulus/dither generator` behavioral
Verilog-A release task. Treat the DUT output as a deterministic voltage-coded
stimulus/dither source for mixed-signal dynamic tests. This is the
testbench-generation companion for an already materialized end-to-end task.

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
