# Task: vbr1_l1_element_shuffler:bugfix

## Release Task Contract

- Form: `bugfix`
- Level: `L1`
- Category: Calibration, DEM, and Control
- Base function: Element shuffler
- Domain: `voltage`
- Target artifact(s): `dut_fixed.va`
- Supplied/reference support artifact(s): `dut_buggy.va`, `element_shuffler.va`, `tb_element_shuffler_buggy.scs`, `tb_element_shuffler_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Repair the supplied buggy Verilog-A artifact while preserving the public module interface and artifact boundary.
- Use the buggy source plus the public intended behavior below; do not change the companion testbench contract.

## Public Interface To Preserve

- `dut_buggy.va` declares module `element_shuffler` with positional ports: `clk`, `rst_n`, `out0`, `out1`, `out2`, `out3`.
- `dut_fixed.va` declares module `element_shuffler` with positional ports: `clk`, `rst_n`, `out0`, `out1`, `out2`, `out3`.
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

## Observed Mismatch Framing

The supplied buggy artifact violates one or more public behavior checks above under the release validation testbench.
Repair the observable behavior without renaming modules, changing ports, or weakening the public testbench contract.

## Output Contract

Return exactly one source artifact named `dut_fixed.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

## Element shuffler bugfix

Repair the provided Verilog-A element shuffler. The DUT has one clock input
`clk`, an active-low reset input `rst_n`, and four voltage-domain one-hot
outputs `out0`, `out1`, `out2`, and `out3`.

After reset is released, each rising edge of `clk` advances a four-state
controller. The public output is not the simple rotating order used by a basic
DEM pointer; it is a fixed non-monotonic shuffle permutation. The sequence
sampled after the first six rising edges must be:

`out2, out0, out3, out1, out2, out0`.

Keep outputs voltage-domain only and drive them with `transition`. Do not use
current contributions.

Return exactly one complete Verilog-A file named `dut_fixed.va`.
