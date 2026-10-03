# Task: vbr1_l1_lfsr_prbs_generator:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: Stimulus and Source Generators
- Base function: PRBS stimulus/dither generator
- Domain: `voltage`
- Target artifact(s): `prbs7.va`, `prbs7_ref.va`
- Supplied/reference support artifact(s): `tb_prbs7_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

## Public Verilog-A Interface

- `prbs7.va` declares module `prbs7` with positional ports: `CLK`, `RSTB`, `PRBS_OUT`, `S0`, `S1`, `S2`, `S3`, `S4`, `S5`, `S6`.
- `prbs7_ref.va` declares module `prbs7_ref` with positional ports: `clk`, `rst_n`, `en`, `serial_out`, `state_0`, `state_1`, `state_2`, `state_3`, `state_4`, `state_5`, `state_6`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=120n maxstep=50p
```

The release harness expects these exact public scalar observables:

- `clk`
- `rst_n`
- `en`
- `serial_out`
- `state_0`
- `state_1`
- `state_2`
- `state_3`
- `state_4`
- `state_5`
- `state_6`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `prbs7_sequence_advances`
- `serial_output_has_transitions`
- `parallel_state_bus_updates`

## Output Contract

Return exactly these source artifacts:

- `prbs7.va`
- `prbs7_ref.va`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

Write a Verilog-A module named `prbs7_ref`.

Create a 7-bit pseudo-random bit sequence (PRBS-7) stimulus/dither source in
Verilog-A. The block is clock-driven, with a voltage-coded serial stimulus
output and a parallel 7-bit state bus output for observability. Use an LFSR
with XOR feedback taps at positions 7 and 6.

Expected behavior:
- 7-bit LFSR generating a deterministic pseudo-random stimulus sequence
- Max-length polynomial: x^7 + x^6 + 1 (or equivalent)
- Sequence length = 2^7 - 1 = 127 states before repeating
Ports:
- `clk`: input electrical
- `rst_n`: input electrical
- `en`: input electrical
- `serial_out`: output electrical
- `state_0`: output electrical
- `state_1`: output electrical
- `state_2`: output electrical
- `state_3`: output electrical
- `state_4`: output electrical
- `state_5`: output electrical
- `state_6`: output electrical

Write portable voltage-domain behavioral Verilog-A (pure voltage-domain behavioral model, no current contributions).
