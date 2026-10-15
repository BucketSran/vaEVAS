# Task: vbr1_l1_resettable_integrator:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: Baseband Signal Conditioning
- Base function: Resettable integrator
- Domain: `voltage`
- Target artifact(s): `resettable_integrator.va`
- Supplied/reference support artifact(s): `tb_resettable_integrator_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

## Public Verilog-A Interface

- `resettable_integrator.va` declares module `resettable_integrator` with positional ports: `vin`, `rst`, `vout`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=320n maxstep=500p
```

The release harness expects these exact public scalar observables:

- `vin`
- `rst`
- `vout`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `input_drive_present`
- `reset_pulse_exercised`
- `pre_reset_output_integrates_up`
- `reset_clears_integrator`
- `post_reset_integration_restarts`

## Output Contract

Return exactly one source artifact named `resettable_integrator.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

Write a pure voltage-domain Verilog-A module for a resettable timer integrator.

The DUT module is `resettable_integrator` with ports `vin, rst, vout`. All ports are electrical; digital-control ports use 0/0.9 V logic levels.

Required behavior:
- Use a 1 ns timer update to integrate `vin` into an internal accumulator.
- High `rst` clears the accumulator to 0 V.
- Clamp the accumulator between 0 V and 0.85 V and drive `vout` with `transition()`.

Use voltage contributions only. Do not use current contributions, `ddt()`, or `idt()`.
