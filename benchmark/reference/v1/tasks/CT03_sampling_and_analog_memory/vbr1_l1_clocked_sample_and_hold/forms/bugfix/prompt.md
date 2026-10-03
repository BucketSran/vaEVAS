# Task: vbr1_l1_clocked_sample_and_hold:bugfix

## Release Task Contract

- Form: `bugfix`
- Level: `L1`
- Category: Sampling and Analog Memory
- Base function: Clocked sample-and-hold
- Domain: `voltage`
- Target artifact(s): `dut_fixed.va`
- Supplied/reference support artifact(s): `dut_buggy.va`, `tb_sample_hold_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Repair the supplied buggy Verilog-A artifact while preserving the public module interface and artifact boundary.
- Use the buggy source plus the public intended behavior below; do not change the companion testbench contract.

## Public Interface To Preserve

- `dut_buggy.va` declares module `sample_hold` with positional ports: `VDD`, `VSS`, `IN`, `CLK`, `OUT`.
- `dut_fixed.va` declares module `sample_hold` with positional ports: `VDD`, `VSS`, `IN`, `CLK`, `OUT`.

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

- `samples_on_rising_clock_edge`
- `output_holds_between_edges`
- `sample_value_tracks_input_at_edge`

## Observed Mismatch Framing

The supplied buggy artifact violates one or more public behavior checks above under the release validation testbench.
Repair the observable behavior without renaming modules, changing ports, or weakening the public testbench contract.

## Output Contract

Return exactly one source artifact named `dut_fixed.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Clocked sample-and-hold Bugfix

Repair the supplied buggy Verilog-A implementation for `Clocked sample-and-hold`.

The fixed implementation must preserve the public module name and ports used by
the reference Spectre testbench. Domain: pure voltage-domain behavioral
Verilog-A. Do not use current contributions, transistor-level devices,
AC/noise analysis, or KCL/KVL solving assumptions.
