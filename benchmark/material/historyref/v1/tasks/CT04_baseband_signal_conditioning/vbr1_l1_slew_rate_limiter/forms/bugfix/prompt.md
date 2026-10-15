# Task: vbr1_l1_slew_rate_limiter:bugfix

## Release Task Contract

- Form: `bugfix`
- Level: `L1`
- Category: Baseband Signal Conditioning
- Base function: Slew-rate limiter
- Domain: `voltage`
- Target artifact(s): `dut_fixed.va`
- Supplied/reference support artifact(s): `dut_buggy.va`, `tb_slew_rate_limiter_buggy.scs`, `tb_slew_rate_limiter_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Repair the supplied buggy Verilog-A artifact while preserving the public module interface and artifact boundary.
- Use the buggy source plus the public intended behavior below; do not change the companion testbench contract.

## Public Interface To Preserve

- `dut_buggy.va` declares module `slew_rate_limiter` with positional ports: `vin`, `vout`.
- `dut_fixed.va` declares module `slew_rate_limiter` with positional ports: `vin`, `vout`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=170n maxstep=500p
```

The release harness expects these exact public scalar observables:

- `vin`
- `vout`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `input_up_down_steps_exercised`
- `rising_step_changes_by_no_more_than_configured_step_per_update`
- `falling_step_changes_by_no_more_than_configured_step_per_update`
- `output_eventually_reaches_new_target_after_large_step`
- `lagged_response_not_passthrough`

## Observed Mismatch Framing

The supplied buggy artifact violates one or more public behavior checks above under the release validation testbench.
Repair the observable behavior without renaming modules, changing ports, or weakening the public testbench contract.

## Output Contract

Return exactly one source artifact named `dut_fixed.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

The provided voltage-domain slew-rate limiter has a one-sided limiting bug: it
limits upward steps but lets downward input steps jump immediately to the target
voltage. Fix the model so both rising and falling output changes are bounded by
the configured per-update step.

The fixed module must be named `slew_rate_limiter` and use electrical ports
`vin` and `vout`. On each periodic update, if `vin` is above the current output
state by more than the configured step, increase the state by one step. If `vin`
is below the current output state by more than the configured step, decrease the
state by one step. Otherwise, snap to `vin`. The output should be driven through
a smoothed voltage contribution.

Use voltage contributions and smoothed output transitions. Do not use current
contributions, `ddt()`, or `idt()`.
