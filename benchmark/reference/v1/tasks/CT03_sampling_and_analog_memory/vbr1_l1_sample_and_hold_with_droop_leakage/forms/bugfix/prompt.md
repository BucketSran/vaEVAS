# Task: vbr1_l1_sample_and_hold_with_droop_leakage:bugfix

## Release Task Contract

- Form: `bugfix`
- Level: `L1`
- Category: Sampling and Analog Memory
- Base function: Sample-and-hold with droop/leakage
- Domain: `voltage`
- Target artifact(s): `dut_fixed.va`
- Supplied/reference support artifact(s): `dut_buggy.va`, `tb_leaky_hold_buggy.scs`, `tb_leaky_hold_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Repair the supplied buggy Verilog-A artifact while preserving the public module interface and artifact boundary.
- Use the buggy source plus the public intended behavior below; do not change the companion testbench contract.

## Public Interface To Preserve

- `dut_buggy.va` declares module `leaky_hold` with positional ports: `sample`, `rst`, `vin`, `vout`.
- `dut_fixed.va` declares module `leaky_hold` with positional ports: `sample`, `rst`, `vin`, `vout`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=170n maxstep=250p
```

The release harness expects these exact public scalar observables:

- `sample`
- `rst`
- `vin`
- `vout`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `sample_event_captures_vin_not_fixed_internal_level`
- `safe_window_vout_decays_monotonically`
- `reset_window_clears_output_near_zero`
- `post_reset_sample_recovers_to_vin`

## Observed Mismatch Framing

The supplied buggy artifact violates one or more public behavior checks above under the release validation testbench.
Repair the observable behavior without renaming modules, changing ports, or weakening the public testbench contract.

## Output Contract

Return exactly one source artifact named `dut_fixed.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

The provided voltage-domain leaky-hold model has an input-sampling bug: on a
sample event it captures a fixed internal level instead of the current value of
`V(vin)`. Fix the design so each sample event captures `vin`, the held value
decays while reset is low, and the output clears promptly when reset is high.

The fixed module must be named `leaky_hold` and use electrical ports `sample`,
`rst`, `vin`, and `vout`. On a rising `sample` threshold crossing, the held
value should be driven near the sampled `vin` level. A periodic leakage update
should reduce the held value over time while `rst` is low. When `rst` is high,
the held value and output should clear near zero.

Use voltage contributions and smoothed output transitions. Do not use current
contributions, `ddt()`, or `idt()`.
