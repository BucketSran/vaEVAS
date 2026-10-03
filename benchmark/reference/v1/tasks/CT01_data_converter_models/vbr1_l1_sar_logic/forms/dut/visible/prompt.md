# Task: vbr1_l1_sar_logic:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: Data Converter Models
- Base function: SAR logic
- Domain: `voltage`
- Target artifact(s): `sar_logic_4b.va`
- Supplied/reference support artifact(s): `tb_sar_logic_4b_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

## Public Verilog-A Interface

- `sar_logic_4b.va` declares module `sar_logic_4b` with positional ports: `VDD`, `VSS`, `CLKS`, `DCOMP`, `DP_DAC_3`, `DP_DAC_2`, `DP_DAC_1`, `DP_DAC_0`, `RDY`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=260n maxstep=1n
```

The release harness expects these exact public scalar observables:

- `clks`
- `dcomp`
- `rdy`
- `dp_dac_3`
- `dp_dac_2`
- `dp_dac_1`
- `dp_dac_0`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `rdy_low_high_low_sequence`
- `dac_code_1010_at_conversion_done_window`

## Output Contract

Return exactly one source artifact named `sar_logic_4b.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Task: vbm1_sar_logic_4b_dut

Write a pure voltage-domain Verilog-A module for a 4-bit SAR logic sequencer.

The DUT module is `sar_logic_4b` with ports `VDD, VSS, CLKS, DCOMP, DP_DAC_3, DP_DAC_2, DP_DAC_1, DP_DAC_0, RDY`. All ports are electrical; digital-control ports use 0/0.9 V logic levels.

Required behavior:
- Implement a 4-bit successive-approximation state machine clocked by rising `CLKS` edges.
- Resolve the current trial bit from `DCOMP`, advance to the next lower bit, and assert `RDY` after bit 0 is resolved.
- Drive DAC decision pins and `RDY` as 0/0.9 V voltage-domain outputs with `transition()`.

Use voltage contributions only. Do not use current contributions, `ddt()`, or `idt()`.

Return exactly one complete Verilog-A file named `sar_logic_4b.va`.
