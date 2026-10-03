# Task: vbr1_l1_clocked_sample_and_hold:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: Sampling and Analog Memory
- Base function: Clocked sample-and-hold
- Domain: `voltage`
- Target artifact(s): `sample_hold.va`
- Supplied/reference support artifact(s): `tb_sample_hold_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

## Public Verilog-A Interface

- `sample_hold.va` declares module `sample_hold` with positional ports: `VDD`, `VSS`, `IN`, `CLK`, `OUT`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=1u maxstep=2n
```

The release harness expects these exact public scalar observables:

- `in`
- `clk`
- `out`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `sh_output_tracks_input_at_edges`
- `sh_output_held_between_edges`

## Output Contract

Return exactly one source artifact named `sample_hold.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Clocked sample-and-hold DUT

Write the Verilog-A DUT artifact(s) for `Clocked sample-and-hold`.

This is a function-checked DUT task, not a generic companion wrapper. The
public contract below defines the exact module interface, voltage-domain
behavior, and waveform observables used by the release checker.

Domain: pure voltage-domain behavioral Verilog-A.

## Module Contract

- Declaration: `sample_hold(vdd, vss, in, clk, out)`

Ports:

- `vdd`, `vss`: electrical supply rails
- `in`: input electrical sampled voltage
- `clk`: input electrical sampling clock
- `out`: output electrical held voltage

## Behavioral Contract

- sample `V(in)` only on rising `clk` crossings
- hold the sampled value between clock edges without continuously tracking the input
- drive `out` with bounded voltage-domain `transition(...)` behavior

## Public Evaluation Observables

The companion validation testbench saves these waveform columns:

- `in`
- `clk`
- `out`
