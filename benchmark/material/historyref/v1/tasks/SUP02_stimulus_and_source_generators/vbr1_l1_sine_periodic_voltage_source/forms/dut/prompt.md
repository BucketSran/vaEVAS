# Task: vbr1_l1_sine_periodic_voltage_source:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: Stimulus and Source Generators
- Base function: Sine/periodic voltage source
- Domain: `voltage`
- Target artifact(s): `multitone.va`
- Supplied/reference support artifact(s): `tb_multitone_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

## Public Verilog-A Interface

- `multitone.va` declares module `multitone` with positional ports: `OUT`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=500n maxstep=500p
```

The release harness expects these exact public scalar observables:

- `OUT`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `multitone_waveform_matches_public_samples`

## Output Contract

Return exactly one source artifact named `multitone.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

Write a Verilog-A module named `multitone`.

Create a signal source that outputs the sum of N sinusoids. Parameters: an array of frequencies and amplitudes (up to 8 tones). Include $bound_step for the highest frequency component.

Ports:
- `OUT`: output electrical
