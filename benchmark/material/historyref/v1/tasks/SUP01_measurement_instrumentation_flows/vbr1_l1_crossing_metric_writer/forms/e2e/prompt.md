# Task: vbr1_l1_crossing_metric_writer:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L1`
- Category: Measurement Instrumentation Flows
- Base function: Crossing metric writer
- Domain: `voltage`
- Target artifact(s): `file_metric_writer.va`, `tb_file_metric_writer_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate all target artifacts: `file_metric_writer.va`, `tb_file_metric_writer_ref.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `file_metric_writer.va` must be co-located with the generated Spectre testbench.
- Include the generated DUT exactly with `ahdl_include "file_metric_writer.va"` in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

- `file_metric_writer.va` declares module `file_metric_writer` with positional ports: `vin`, `done`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=90n maxstep=500p
```

The release harness expects these exact public scalar observables:

- `vin`
- `done`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `vin`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "file_metric_writer.va"

XDUT (vin done) file_metric_writer filename="metric.out"

tran tran stop=90n maxstep=500p
save vin done
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `done_low_before_crossing`
- `done_high_after_first_crossing`
- `metric_file_records_first_crossing_time`

## Output Contract

Return exactly these source artifacts:

- `file_metric_writer.va`
- `tb_file_metric_writer_ref.scs`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Task: vbm1_file_metric_writer_e2e

Write both the Verilog-A DUT and Spectre testbench for a file metric writer.

The DUT module is `file_metric_writer` with ports `vin, done`. All ports are electrical; digital-control ports use 0/0.9 V logic levels.

Required DUT behavior:
- Open a text metric file at startup using a string parameter named `filename` with default `metric.out`.
- On the first rising crossing of `vin` through 0.45 V, write the crossing time to the metric file and set `done` high.
- Keep `done` low before the first crossing and high afterwards; drive it with smoothed voltage transitions.

Required testbench behavior:
- Drive `vin` through exactly one public rising crossing near 30 ns.
- Run to a later safe window and save `vin` and `done`; the file side effect is supporting evidence, not the only metric.

Use voltage contributions only in the Verilog-A DUT. Do not use current contributions, `ddt()`, or `idt()`.

Review caveat: This is a normal measurement/file-output task. It is not a bugfix task; atomic file I/O semantics belong in EVAS/Spectre conformance.

Return exactly two files: `file_metric_writer.va` and `tb_file_metric_writer_ref.scs`.
