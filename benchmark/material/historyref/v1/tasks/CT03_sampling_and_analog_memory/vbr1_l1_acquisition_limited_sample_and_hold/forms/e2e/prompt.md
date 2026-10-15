# Task: vbr1_l1_acquisition_limited_sample_and_hold:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L1`
- Category: Sampling and Analog Memory
- Base function: Acquisition-limited sample-and-hold
- Domain: `voltage`
- Target artifact(s): `acquisition_limited_sample_hold.va`, `tb_acquisition_limited_sample_hold.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate all target artifacts: `acquisition_limited_sample_hold.va`, `tb_acquisition_limited_sample_hold.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `acquisition_limited_sample_hold.va` must be co-located with the generated Spectre testbench.
- Include the generated DUT exactly with `ahdl_include "acquisition_limited_sample_hold.va"` in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

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

Public stimulus/source nodes visible in the reference harness include:

- `sample`
- `rst`
- `vin`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "acquisition_limited_sample_hold.va"

XDUT (sample rst vin vout metric) acquisition_limited_sample_hold

tran tran stop=90n maxstep=250p
save sample rst vin vout metric
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `finite_acquisition_does_not_jump_to_vin`
- `longer_sample_window_settles_closer_to_vin`
- `falling_sample_edge_holds_last_acquired_value`
- `reset_returns_to_initial_level`
- `metric_marks_tracking_window`

## Output Contract

Return exactly these source artifacts:

- `acquisition_limited_sample_hold.va`
- `tb_acquisition_limited_sample_hold.scs`

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
