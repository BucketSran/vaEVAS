# Task: vbr1_l1_threshold_comparator:bugfix

## Release Task Contract

- Form: `bugfix`
- Level: `L1`
- Category: Comparator and Decision Circuits
- Base function: Threshold comparator
- Domain: `voltage`
- Target artifact(s): `dut_fixed.va`
- Supplied/reference support artifact(s): `dut_buggy.va`, `tb_comparator_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Repair the supplied buggy Verilog-A artifact while preserving the public module interface and artifact boundary.
- Use the buggy source plus the public intended behavior below; do not change the companion testbench contract.

## Public Interface To Preserve

- `dut_buggy.va` declares module `comparator` with positional ports: `VDD`, `VSS`, `VINP`, `VINN`, `OUT_P`.
- `dut_fixed.va` declares module `comparator` with positional ports: `VDD`, `VSS`, `VINP`, `VINN`, `OUT_P`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=30n maxstep=0.1n
```

The release harness expects these exact public scalar observables:

- `vinp`
- `vinn`
- `out_p`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `low_for_negative_diff`
- `high_for_positive_diff`
- `rising_trip_near_zero_diff`
- `falling_trip_near_zero_diff`
- `polarity_matches_vinp_minus_vinn`

## Observed Mismatch Framing

The supplied buggy artifact violates one or more public behavior checks above under the release validation testbench.
Repair the observable behavior without renaming modules, changing ports, or weakening the public testbench contract.

## Output Contract

Return exactly one source artifact named `dut_fixed.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Threshold comparator Bugfix

Repair the supplied buggy Verilog-A implementation for `Threshold comparator`.

The fixed implementation must preserve the public module name and ports used by
the reference Spectre testbench. Domain: pure voltage-domain behavioral
Verilog-A. Do not use current contributions, transistor-level devices,
AC/noise analysis, or KCL/KVL solving assumptions.

The repaired behavior is bidirectional: `OUT_P` must be low for negative
`VINP - VINN`, high for positive `VINP - VINN`, and must switch correctly on
both rising and falling zero-differential crossings.
