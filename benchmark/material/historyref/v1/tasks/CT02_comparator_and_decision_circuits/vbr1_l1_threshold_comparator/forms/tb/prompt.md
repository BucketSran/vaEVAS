# Task: vbr1_l1_threshold_comparator:tb

## Release Task Contract

- Form: `tb`
- Level: `L1`
- Category: Comparator and Decision Circuits
- Base function: Threshold comparator
- Domain: `voltage`
- Target artifact(s): `tb_comparator_ref.scs`
- Supplied/reference support artifact(s): `comparator.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `comparator.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "comparator.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `comparator.va` declares module `comparator` with positional ports: `VDD`, `VSS`, `VINP`, `VINN`, `OUT_P`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=30n maxstep=0.1n
```

The release harness expects these exact public scalar observables:

- `vinp`
- `vinn`
- `out_p`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `vdd`
- `vss`
- `vinp`
- `vinn`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "comparator.va"

Vvdd (vdd 0) vsource dc=0.9
Vvss (vss 0) vsource dc=0.0

IDUT (vdd vss vinp vinn out_p) comparator

tran tran stop=30n maxstep=0.1n
save vinp vinn out_p
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `low_for_negative_diff`
- `high_for_positive_diff`
- `rising_trip_near_zero_diff`
- `falling_trip_near_zero_diff`
- `rail_referenced_output_levels`

## Output Contract

Return exactly one source artifact named `tb_comparator_ref.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Threshold comparator Testbench Companion

Write a Spectre transient testbench for the `Threshold comparator` behavioral
Verilog-A release task. This is the testbench-generation companion for an
already materialized end-to-end task.

The testbench should instantiate the same behavioral DUT or system module used
by the corresponding end-to-end form, drive the public transient scenario, save
the observable waveform or metric signals, and preserve the EVAS/Spectre
validation contract.

Domain: pure voltage-domain behavioral Verilog-A.

Public requirements:

- include `comparator.va` via `ahdl_include`
- instantiate `comparator` with scalar nodes `vdd`, `vss`, `vinp`, `vinn`,
  and `out_p`
- include `tran tran stop=30n maxstep=0.1n`
- save `vinp`, `vinn`, and `out_p`
- drive `vinp - vinn` through a negative, positive, and negative sequence so
  both comparator output edges are visible in one run
- keep output levels rail-referenced to the supplied `vdd`/`vss` nodes
- avoid transistor-level devices, AC/noise analysis, and current-domain
  solver assumptions
