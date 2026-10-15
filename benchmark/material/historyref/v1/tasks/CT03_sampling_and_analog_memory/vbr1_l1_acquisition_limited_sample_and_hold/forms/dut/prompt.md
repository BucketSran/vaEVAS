# Task: vbr1_l1_acquisition_limited_sample_and_hold:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: Sampling and Analog Memory
- Base function: Acquisition-limited sample-and-hold
- Domain: `voltage`
- Target artifact(s): `acquisition_limited_sample_hold.va`
- Supplied/reference support artifact(s): `tb_acquisition_limited_sample_hold.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

## Public Verilog-A Interface

- `acquisition_limited_sample_hold.va` declares module `acquisition_limited_sample_hold` with positional ports: `sample`, `rst`, `vin`, `vout`, `metric`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=90n maxstep=250p
```

The release harness expects these exact public scalar observables:

- `sample`
- `rst`
- `vin`
- `vout`
- `metric`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `finite_acquisition_does_not_jump_to_vin`
- `longer_sample_window_settles_closer_to_vin`
- `falling_sample_edge_holds_last_acquired_value`
- `reset_returns_to_initial_level`
- `metric_marks_tracking_window`

## Output Contract

Return exactly one source artifact named `acquisition_limited_sample_hold.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

Write a pure voltage-domain Verilog-A model for an acquisition-limited sample-and-hold.

The model must represent finite acquisition bandwidth rather than an ideal instantaneous sampler:
- `sample` high opens a tracking/acquisition window.
- While tracking, `vout` moves toward the current `V(vin)` in discrete 1 ns acquisition updates.
- A falling `sample` edge freezes the last acquired value.
- High `rst` returns the held output to `vinit`.
- `metric` is high only while the model is actively tracking/acquiring.

Module name: `acquisition_limited_sample_hold`.
Domain: pure voltage-domain behavioral Verilog-A.
Do not use current contributions, transistor-level devices, AC/noise analysis, or KCL/KVL solving assumptions.

Public port contract:

```verilog
module acquisition_limited_sample_hold(sample, rst, vin, vout, metric);
```

Saved waveform columns:

```text
sample rst vin vout metric
```

Public transient contract:

```spectre
tran tran stop=90n maxstep=250p
```
