# Task: vbr1_l1_sample_and_hold_with_droop_leakage:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: Sampling and Analog Memory
- Base function: Sample-and-hold with droop/leakage
- Domain: `voltage`
- Target artifact(s): `leaky_hold.va`
- Supplied/reference support artifact(s): `tb_leaky_hold_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

## Public Verilog-A Interface

- `leaky_hold.va` declares module `leaky_hold` with positional ports: `sample`, `rst`, `vin`, `vout`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=170n maxstep=250p
```

The release harness expects these exact public scalar observables:

- `sample`
- `rst`
- `vin`
- `vout`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `rising_sample_edge_captures_vin`
- `multiple_input_levels_are_preserved`
- `held_output_droops_over_time`
- `reset_clears_output`
- `post_reset_sample_recovers_to_vin`

## Output Contract

Return exactly one source artifact named `leaky_hold.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

Write a pure voltage-domain Verilog-A module for a sample-and-hold with
observable droop/leakage.

The DUT module is `leaky_hold` with ports `sample, rst, vin, vout`. All ports
are electrical; digital-control ports use 0/0.9 V logic levels.

Required behavior:
- A rising `sample` edge captures the current value of `V(vin)`, not a fixed
  internal level.
- A 1 ns timer applies exponential droop by multiplying the held value by
  0.985 while reset is low.
- High `rst` clears the held value; drive `vout` through `transition()`.

Use voltage contributions only. Do not use current contributions, `ddt()`, or `idt()`.
