# Task: vbr1_l2_measurement_flow:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L2`
- Category: Measurement Instrumentation Flows
- Base function: Measurement flow
- Domain: `voltage`
- Target artifact(s): `final_step_file_metric_ref.va`, `tb_final_step_file_metric_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## L2 Background And Claim Boundary

This Level-2 row is a reusable measurement/stimulus support flow for Measurement flow. It is certified as release content but remains outside the core circuit score denominator.
Stay within the listed voltage-domain/event-driven contract. Do not use transistor-level devices, current-domain loads, AC/noise analysis, S-parameters, or hidden checker logic unless the public contract explicitly lists them.
Paper-facing claims for this row are limited to support-flow behavior and must be reported separately from core analog/mixed-signal circuit-function coverage.

## Form-Specific Requirements

- Generate all target artifacts: `final_step_file_metric_ref.va`, `tb_final_step_file_metric_ref.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `final_step_file_metric_ref.va` must be co-located with the generated Spectre testbench.
- Include the generated DUT exactly with `ahdl_include "final_step_file_metric_ref.va"` in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

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
evidence. It must expose edge counting and final metric publication:

1. Edge counting:
   - Count rising edges of the public `ref` clock on the expected transient
     grid.
   - Drive the count-derived status through the public metric output.

2. Metric normalization:
   - Drive `metric_out` as a bounded normalized voltage derived from the final
     edge count.
   - Do not drive a constant placeholder metric.

3. Final-step side output:
   - At the final simulation step, write the candidate metric file requested by
     the release harness.
   - The file-backed value and `metric_out` should describe the same final
     measurement.

The expected public relation is: reference edges -> normalized metric waveform
-> final metric side file.

## Output Contract

Return exactly these source artifacts:

- `final_step_file_metric_ref.va`
- `tb_final_step_file_metric_ref.scs`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

Write a Verilog-A module named `final_step_file_metric_ref`.

# Task: final_step_file_metric_smoke

## Objective

Write a Verilog-A measurement helper that counts input edges, exposes the normalized count on a voltage output, and writes the final metric to a file during `@(final_step)`.

Public behavior requirements:
- The Spectre testbench should drive `VDD=0.9 V`, `VSS=0 V`, and a `ref` pulse train whose rising edges occur at 10 ns, 30 ns, 50 ns, and 70 ns.
- The DUT should count rising crossings of `ref` above the logic threshold and normalize the count by 4.
- `metric_out` should settle after each edge to the normalized count multiplied by `VDD`, producing approximately 0.225 V, 0.45 V, 0.675 V, and 0.9 V.
- During `@(final_step)`, write `candidate.out` with exactly one metric record of the form `count=<integer> metric=<real>`, where the final count is 4 and the final metric is approximately 1.000.
- Use `$fopen`, `$fwrite`, and `$fclose` for the file output. Use voltage-domain contributions and smooth transitions; do not use current-domain branch contributions.

Ports:
- `VDD`: inout electrical
- `VSS`: inout electrical
- `ref`: input electrical
- `metric_out`: output electrical
