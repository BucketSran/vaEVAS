# Task: vbr1_l1_crossing_metric_writer:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: Measurement Instrumentation Flows
- Base function: Crossing metric writer
- Domain: `voltage`
- Target artifact(s): `file_metric_writer.va`
- Supplied/reference support artifact(s): `tb_file_metric_writer_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

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

## Public Behavior Checks

- `done_low_before_crossing`
- `done_high_after_first_crossing`
- `metric_file_records_first_crossing_time`

## Output Contract

Return exactly one source artifact named `file_metric_writer.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Task: vbm1_file_metric_writer_dut

Write a pure voltage-domain Verilog-A module for a file metric writer.

The DUT module is `file_metric_writer` with ports `vin, done`. All ports are electrical; digital-control ports use 0/0.9 V logic levels.

Required behavior:
- Open a text metric file at startup using a string parameter named `filename` with default `metric.out`.
- On the first rising crossing of `vin` through 0.45 V, write the crossing time to the metric file and set `done` high.
- Keep `done` low before the first crossing and high afterwards; drive it with smoothed voltage transitions.

Use voltage contributions only. Do not use current contributions, `ddt()`, or `idt()`.

Review caveat: This is a normal measurement/file-output task. It is not a bugfix task; atomic file I/O semantics belong in EVAS/Spectre conformance.

Return exactly one complete Verilog-A file named `file_metric_writer.va`.
