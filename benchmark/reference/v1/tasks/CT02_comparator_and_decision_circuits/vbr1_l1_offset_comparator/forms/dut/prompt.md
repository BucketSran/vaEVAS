# Task: vbr1_l1_offset_comparator:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: Comparator and Decision Circuits
- Base function: Offset comparator
- Domain: `voltage`
- Target artifact(s): `cmp_offset_ref.va`
- Supplied/reference support artifact(s): `tb_comparator_offset_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

## Public Verilog-A Interface

- `cmp_offset_ref.va` declares module `cmp_offset_ref` with positional ports: `VDD`, `VSS`, `CLK`, `VINP`, `VINN`, `OUT_P`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=28n maxstep=20p
```

The release harness expects these exact public scalar observables:

- `CLK`
- `VINP`
- `VINN`
- `OUT_P`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `clocked_output_sequence_LLLHHLL`
- `negative_diff_latches_low`
- `positive_diff_below_5mV_offset_latches_low`
- `positive_diff_above_5mV_offset_latches_high`
- `decisions_sampled_after_rising_clk_edges`

## Output Contract

Return exactly one source artifact named `cmp_offset_ref.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Offset Comparator DUT

Write a pure voltage-domain Verilog-A module for a clocked comparator with input offset.

The DUT module is `cmp_offset_ref` with ports `VDD, VSS, CLK, VINP, VINN, OUT_P`. All ports are electrical; digital-control ports use 0/0.9 V logic levels.

Required behavior:
- On each rising `CLK` edge, compare `VINP - VINN` against an internal positive
  offset threshold of about 5 mV.
- Borderline positive inputs below the offset, such as +3 mV, must still latch
  low; inputs above the offset, such as +7 mV or +20 mV, must latch high.
- Drive `OUT_P` to the supply level for a high decision and to `VSS` for a low decision.
- Use smoothed voltage-domain output transitions.

Use voltage contributions only. Do not use current contributions, `ddt()`, or `idt()`.
