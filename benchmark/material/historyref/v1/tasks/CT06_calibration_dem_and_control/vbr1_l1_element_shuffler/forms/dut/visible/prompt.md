# Task: vbr1_l1_element_shuffler:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: Calibration, DEM, and Control
- Base function: Element shuffler
- Domain: `voltage`
- Target artifact(s): `element_shuffler.va`
- Supplied/reference support artifact(s): `tb_element_shuffler_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

## Public Verilog-A Interface

- `element_shuffler.va` declares module `element_shuffler` with positional ports: `clk`, `rst_n`, `out0`, `out1`, `out2`, `out3`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=130n maxstep=500p
```

The release harness expects these exact public scalar observables:

- `clk`
- `rst_n`
- `out0`
- `out1`
- `out2`
- `out3`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `fixed_time_active_output_sequence_at_20_40_60_80_100_120ns`
- `expected_permutation_sequence_2_0_3_1_2_0`

## Output Contract

Return exactly one source artifact named `element_shuffler.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

## Element shuffler DUT

Write a pure voltage-domain Verilog-A module named `element_shuffler`.

The module has electrical ports `clk`, `rst_n`, `out0`, `out1`, `out2`, and
`out3`. `rst_n` is active low. On reset, return to the initial state. On each
rising edge of `clk` while reset is released, advance through a deterministic
four-step shuffler whose public order is intentionally non-monotonic. Exactly
one output is high at a time, driven as a 0/0.9 V logic level with smoothed
transitions.

The public observable sequence after reset is released is:

- first sampled state: `out2` high
- then `out0`
- then `out3`
- then `out1`
- then the sequence repeats

Use voltage contributions only. Do not use current contributions, `ddt()`, or
`idt()`.

Return exactly one complete Verilog-A file named `element_shuffler.va`.
