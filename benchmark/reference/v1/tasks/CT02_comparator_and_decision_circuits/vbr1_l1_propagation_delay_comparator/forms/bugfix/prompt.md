# Task: vbr1_l1_propagation_delay_comparator:bugfix

## Release Task Contract

- Form: `bugfix`
- Level: `L1`
- Category: Comparator and Decision Circuits
- Base function: Propagation-delay comparator
- Domain: `voltage`
- Target artifact(s): `dut_fixed.va`
- Supplied/reference support artifact(s): `dut_buggy.va`, `edge_interval_timer.va`, `tb_cmp_delay_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Repair the supplied buggy Verilog-A artifact while preserving the public module interface and artifact boundary.
- Use the buggy source plus the public intended behavior below; do not change the companion testbench contract.

## Public Interface To Preserve

- `dut_buggy.va` declares module `cmp_delay` with positional ports: `CLK`, `VINN`, `VINP`, `DCMPN`, `DCMPP`, `LP`, `LM`, `VSS`, `VDD`.
- `dut_fixed.va` declares module `cmp_delay` with positional ports: `CLK`, `VINN`, `VINP`, `DCMPN`, `DCMPP`, `LP`, `LM`, `VSS`, `VDD`.
- `edge_interval_timer.va` declares module `edge_interval_timer` with positional ports: `CLK_1`, `CLK_2`, `OUT_PS`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=16n maxstep=10p
```

The release harness expects these exact public scalar observables:

- `clk`
- `vinp`
- `vinn`
- `out_p`
- `out_n`
- `delay_ps`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `output_goes_high_in_each_phase`
- `clk_to_output_delay_increases_as_diff_shrinks`

## Observed Mismatch Framing

The supplied buggy artifact violates one or more public behavior checks above under the release validation testbench.
Repair the observable behavior without renaming modules, changing ports, or weakening the public testbench contract.

## Output Contract

Return exactly one source artifact named `dut_fixed.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Propagation-delay comparator Bugfix

Repair the supplied buggy Verilog-A implementation for `Propagation-delay comparator`.

The fixed implementation must preserve the public module name and ports used by
the reference Spectre testbench. In particular, `DCMPP` must resolve high for
the public positive-polarity phases, reset low between decisions, and show a
larger clock-to-output delay as the differential input shrinks from `10 mV` to
`0.01 mV`.

Domain: pure voltage-domain behavioral Verilog-A. Do not use current
contributions, transistor-level devices, AC/noise analysis, or KCL/KVL solving
assumptions.
