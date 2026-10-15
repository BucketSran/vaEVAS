# Task: vbr1_l1_resettable_integrator:bugfix

## Release Task Contract

- Form: `bugfix`
- Level: `L1`
- Category: Baseband Signal Conditioning
- Base function: Resettable integrator
- Domain: `voltage`
- Target artifact(s): `dut_fixed.va`
- Supplied/reference support artifact(s): `dut_buggy.va`, `tb_resettable_integrator_buggy.scs`, `tb_resettable_integrator_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Repair the supplied buggy Verilog-A artifact while preserving the public module interface and artifact boundary.
- Use the buggy source plus the public intended behavior below; do not change the companion testbench contract.

## Public Interface To Preserve

- `dut_buggy.va` declares module `resettable_integrator` with positional ports: `vin`, `rst`, `vout`.
- `dut_fixed.va` declares module `resettable_integrator` with positional ports: `vin`, `rst`, `vout`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=320n maxstep=500p
```

The release harness expects these exact public scalar observables:

- `vin`
- `rst`
- `vout`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `input_drive_present`
- `reset_pulse_exercised`
- `integrator_ramps_during_reset_low_window`
- `reset_window_clears_output_near_zero`
- `post_reset_integration_restarts_from_zero`

## Observed Mismatch Framing

The supplied buggy artifact violates one or more public behavior checks above under the release validation testbench.
Repair the observable behavior without renaming modules, changing ports, or weakening the public testbench contract.

Representative public mismatch scenarios:

| Scenario | Expected behavior | Faulty behavior to repair |
| --- | --- | --- |
| reset is low/inactive with positive input | `vout` ramps upward over time | output does not integrate or has the wrong ramp direction |
| reset pulse asserted | `vout` clears near zero during the reset window | output keeps the old integrated state |
| reset released after the pulse | integration restarts from the reset-cleared value | output resumes from stale pre-reset state |

## Output Contract

Return exactly one source artifact named `dut_fixed.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

The provided voltage-domain resettable integrator fails to clear its accumulated
state during reset. Fix the model so reset immediately holds the integrated
output near zero and the accumulator restarts from zero when reset is released.

The fixed module must be named `resettable_integrator` and use electrical ports
`vin`, `rst`, and `vout`. While reset is low, the model should periodically add
the scaled input contribution to an internal accumulator. The accumulator should
be clamped to the valid output range and driven through a smoothed voltage
transition.

Use voltage contributions and event-driven state updates. Do not use current
contributions, `ddt()`, or `idt()`.
