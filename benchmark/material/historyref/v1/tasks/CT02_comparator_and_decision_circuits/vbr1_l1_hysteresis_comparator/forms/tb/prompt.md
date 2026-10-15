# Task: vbr1_l1_hysteresis_comparator:tb

## Release Task Contract

- Form: `tb`
- Level: `L1`
- Category: Comparator and Decision Circuits
- Base function: Hysteresis comparator
- Domain: `voltage`
- Target artifact(s): `tb_cmp_hysteresis_ref.scs`
- Supplied/reference support artifact(s): `cmp_hysteresis.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `cmp_hysteresis.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "cmp_hysteresis.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `cmp_hysteresis.va` declares module `cmp_hysteresis` with positional ports: `VINN`, `VINP`, `OUTN`, `OUTP`, `VSS`, `VDD`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=80n maxstep=100p
```

The release harness expects these exact public scalar observables:

- `vinp`
- `vinn`
- `out_p`
- `out_n`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `vdd`
- `gnd`
- `vinp`
- `vinn`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "cmp_hysteresis.va"

Vvdd (vdd 0) vsource dc=0.9 type=dc

IDUT (vinn vinp out_n out_p gnd vdd) cmp_hysteresis vhys=10m tedge=50p

tran tran stop=80n maxstep=100p
save vinp vinn out_p out_n
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `output_shows_hysteresis_window`
- `upward_and_downward_trip_points_are_separated`

## Output Contract

Return exactly one source artifact named `tb_cmp_hysteresis_ref.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Hysteresis comparator Testbench Companion

Write a Spectre transient testbench for the `Hysteresis comparator` behavioral
Verilog-A release task. This is the testbench-generation companion for an
already materialized end-to-end task.

The testbench should instantiate the same behavioral DUT or system module used
by the corresponding end-to-end form, drive the public transient scenario, save
the observable waveform or metric signals, and preserve the EVAS/Spectre
validation contract.

Domain: pure voltage-domain behavioral Verilog-A.

Public requirements:

- include `cmp_hysteresis.va` via `ahdl_include`
- instantiate `cmp_hysteresis` with scalar nodes `vinn`, `vinp`, `out_n`,
  `out_p`, `gnd`, and `vdd`
- include `tran tran stop=80n maxstep=100p`
- save `vinp`, `vinn`, `out_p`, and `out_n`
- drive the differential input upward through `+vhys/2` and downward through
  `-vhys/2`, with an intermediate hold region between the two thresholds
- make the upward and downward trip points visibly separated in the saved
  waveform
- avoid transistor-level devices, AC/noise analysis, and current-domain
  solver assumptions
