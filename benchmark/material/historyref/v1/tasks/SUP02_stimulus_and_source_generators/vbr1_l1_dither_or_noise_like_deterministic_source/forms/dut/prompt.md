# Task: vbr1_l1_dither_or_noise_like_deterministic_source:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: Stimulus and Source Generators
- Base function: Dither or noise-like deterministic source
- Domain: `voltage`
- Target artifact(s): `noise_gen.va`, `noise_gen_ref.va`
- Supplied/reference support artifact(s): `tb_noise_gen_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

## Public Verilog-A Interface

- `noise_gen.va` declares module `noise_gen` with positional ports: `vin_i`, `vout_o`.
- `noise_gen_ref.va` declares module `noise_gen` with positional ports: `vin_i`, `vout_o`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=500n maxstep=1n
```

The release harness expects these exact public scalar observables:

- `vin_i`
- `vout_o`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `noise_is_nontrivial`
- `noise_std_in_range`

## Output Contract

Return exactly these source artifacts:

- `noise_gen.va`
- `noise_gen_ref.va`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Dither or noise-like deterministic source DUT

Write the Verilog-A DUT artifact(s) for `Dither or noise-like deterministic source`.

This is a function-checked DUT task, not a generic companion wrapper. The
public contract below defines the exact module interface, voltage-domain
behavior, and waveform observables used by the release checker.

Domain: pure voltage-domain behavioral Verilog-A.

## Module Contract

- Declaration: `noise_gen(vin_i, vout_o)`

Ports:

- `vin_i`: input electrical baseline voltage
- `vout_o`: output electrical baseline plus sampled dither/noise-like perturbation

## Behavioral Contract

- add zero-mean sampled perturbation to `V(vin_i)`
- the public task checks non-trivial variation and bounded standard deviation; it does not claim physical noise analysis
- drive the output with pure voltage-domain `transition(...)` behavior

## Public Evaluation Observables

The companion validation testbench saves these waveform columns:

- `vin_i`
- `vout_o`
