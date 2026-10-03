# Task: vbr1_l2_measurement_flow:tb

## Release Task Contract

- Form: `tb`
- Level: `L2`
- Category: Measurement Instrumentation Flows
- Base function: Measurement flow
- Domain: `voltage`
- Target artifact(s): `tb_final_step_file_metric_ref.scs`
- Supplied/reference support artifact(s): `final_step_file_metric_ref.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## L2 Background And Claim Boundary

This Level-2 row is a reusable measurement/stimulus support flow for Measurement flow. It is certified as release content but remains outside the core circuit score denominator.
Stay within the listed voltage-domain/event-driven contract. Do not use transistor-level devices, current-domain loads, AC/noise analysis, S-parameters, or hidden checker logic unless the public contract explicitly lists them.
Paper-facing claims for this row are limited to support-flow behavior and must be reported separately from core analog/mixed-signal circuit-function coverage.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `final_step_file_metric_ref.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "final_step_file_metric_ref.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `final_step_file_metric_ref.va` declares module `final_step_file_metric_ref` with positional ports: `VDD`, `VSS`, `ref`, `metric_out`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=80n maxstep=20p errpreset=conservative
```

The release harness expects these exact public scalar observables:

- `ref`
- `metric_out`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `VDD`
- `VSS`
- `ref`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "final_step_file_metric_ref.va"

Vvdd (VDD 0) vsource dc=0.9 type=dc
Vvss (VSS 0) vsource dc=0.0 type=dc

IDUT (VDD VSS ref metric_out) final_step_file_metric_ref

tran tran stop=80n maxstep=20p errpreset=conservative
save ref metric_out
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `ref_edges_counted_on_expected_grid`
- `metric_out_normalizes_final_edge_count`
- `final_step_writes_candidate_metric_file`

## Public L2 Behavior Contract

This support row is a measurement flow with both waveform and file-backed
evidence. The testbench must expose edge counting and final metric publication:

1. Drive `ref` as a 0 V/0.9 V clock with a stable expected period.
2. Run the transient long enough for several expected reference edges.
3. Save `ref` and `metric_out` exactly.
4. Allow the supplied DUT to execute its final-step file write; do not replace
   it with checker logic in the testbench.

The expected public relation is: counted `ref` edges produce a bounded
normalized `metric_out`, and the final side-output file reports the same
candidate metric.

## Output Contract

Return exactly one source artifact named `tb_final_step_file_metric_ref.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Measurement flow Testbench Companion

Write a Spectre transient testbench for the `Measurement flow` behavioral
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
