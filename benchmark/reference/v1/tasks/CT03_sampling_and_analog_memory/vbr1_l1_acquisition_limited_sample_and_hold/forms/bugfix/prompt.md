# Task: vbr1_l1_acquisition_limited_sample_and_hold:bugfix

## Release Task Contract

- Form: `bugfix`
- Level: `L1`
- Category: Sampling and Analog Memory
- Base function: Acquisition-limited sample-and-hold
- Domain: `voltage`
- Target artifact(s): `dut_fixed.va`
- Supplied/reference support artifact(s): `dut_buggy.va`, `tb_acquisition_limited_sample_hold.scs`, `tb_acquisition_limited_sample_hold_buggy.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Repair the supplied buggy Verilog-A artifact while preserving the public module interface and artifact boundary.
- Use the buggy source plus the public intended behavior below; do not change the companion testbench contract.

## Public Interface To Preserve

- `dut_buggy.va` declares module `acquisition_limited_sample_hold` with positional ports: `sample`, `rst`, `vin`, `vout`, `metric`.
- `dut_fixed.va` declares module `acquisition_limited_sample_hold` with positional ports: `sample`, `rst`, `vin`, `vout`, `metric`.

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

## Observed Mismatch Framing

The supplied buggy artifact violates one or more public behavior checks above under the release validation testbench.
Repair the observable behavior without renaming modules, changing ports, or weakening the public testbench contract.

Representative public mismatch scenarios:

| Scenario | Expected behavior | Faulty behavior to repair |
| --- | --- | --- |
| `sample` goes high while `vin` steps | `vout` moves toward `vin` with finite acquisition, not an instantaneous copy | `vout` jumps too aggressively or ignores the acquisition limit |
| longer sample-high window | `vout` settles closer to `vin` than in a shorter window | acquisition progress is not reflected in the held output |
| `sample` falls | `vout` holds the last acquired value with bounded droop/hold behavior | output keeps tracking the input after the hold edge |
| reset asserted | `vout` and metric return to the public initial state | reset does not clear the held/acquisition state |

## Output Contract

Return exactly one source artifact named `dut_fixed.va`.
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
