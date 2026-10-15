# Task: vbr1_l1_digital_phase_accumulator_with_modulo_wrap:bugfix

## Release Task Contract

- Form: `bugfix`
- Level: `L1`
- Category: PLL Clock and Timing Systems
- Base function: Digital phase accumulator with modulo wrap
- Domain: `voltage`
- Target artifact(s): `dut_fixed.va`
- Supplied/reference support artifact(s): `dut_buggy.va`, `tb_phase_accumulator_timer_wrap_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Repair the supplied buggy Verilog-A artifact while preserving the public module interface and artifact boundary.
- Use the buggy source plus the public intended behavior below; do not change the companion testbench contract.

## Public Interface To Preserve

- `dut_buggy.va` declares module `phase_accumulator_timer_wrap_ref` with positional ports: `VDD`, `VSS`, `clk_out`, `phase_out`.
- `dut_fixed.va` declares module `phase_accumulator_timer_wrap_ref` with positional ports: `VDD`, `VSS`, `clk_out`, `phase_out`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=75n maxstep=20p errpreset=conservative
```

The release harness expects these exact public scalar observables:

- `clk_out`
- `phase_out`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `phase_advances_by_step`
- `phase_wraps_modulo_one`
- `clock_state_follows_wrapped_phase`

## Observed Mismatch Framing

The supplied buggy artifact violates one or more public behavior checks above under the release validation testbench.
Repair the observable behavior without renaming modules, changing ports, or weakening the public testbench contract.

## Output Contract

Return exactly one source artifact named `dut_fixed.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

This entry is scoped as an ADPLL/NCO phase-timing primitive, not as a generic digital-logic benchmark. Model the wrapped phase state and derived voltage-domain timing outputs that a behavioral PLL loop would consume.

## Digital phase accumulator with modulo wrap Bugfix

Repair the supplied buggy Verilog-A implementation for `Digital phase accumulator with modulo wrap`.

The fixed implementation must preserve the public module name and ports used by
the reference Spectre testbench. Domain: pure voltage-domain behavioral
Verilog-A. Do not use current contributions, transistor-level devices,
AC/noise analysis, or KCL/KVL solving assumptions.
