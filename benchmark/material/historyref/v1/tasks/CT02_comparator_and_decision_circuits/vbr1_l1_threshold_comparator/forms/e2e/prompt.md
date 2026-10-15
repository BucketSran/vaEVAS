# Task: vbr1_l1_threshold_comparator:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L1`
- Category: Comparator and Decision Circuits
- Base function: Threshold comparator
- Domain: `voltage`
- Target artifact(s): `comparator.va`, `tb_comparator_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate all target artifacts: `comparator.va`, `tb_comparator_ref.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `comparator.va` must be co-located with the generated Spectre testbench.
- Include the generated DUT exactly with `ahdl_include "comparator.va"` in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

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

Return exactly these source artifacts:

- `comparator.va`
- `tb_comparator_ref.scs`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

Write a Verilog-A module named `comparator`.

Create a voltage-domain comparator in Verilog-A, then produce a minimal Spectre
transient testbench and run a smoke simulation.

Behavioral intent:

- differential comparison around `VINP - VINN = 0`
- output toggles high/low with supply-referenced logic levels
- finite output edge transition
- both low-to-high and high-to-low threshold crossings should be visible in the
  waveform under a negative-positive-negative input sweep

Ports:
- `VDD`: inout electrical
- `VSS`: inout electrical
- `VINP`: input electrical
- `VINN`: input electrical
- `OUT_P`: output electrical
