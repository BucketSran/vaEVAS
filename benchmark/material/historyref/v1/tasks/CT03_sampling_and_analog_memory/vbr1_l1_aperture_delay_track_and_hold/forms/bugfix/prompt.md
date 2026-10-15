# Task: vbr1_l1_aperture_delay_track_and_hold:bugfix

## Release Task Contract

- Form: `bugfix`
- Level: `L1`
- Category: Sampling and Analog Memory
- Base function: Aperture-delay track-and-hold
- Domain: `voltage`
- Target artifact(s): `dut_fixed.va`
- Supplied/reference support artifact(s): `dut_buggy.va`, `tb_sample_hold_aperture_buggy.scs`, `tb_sample_hold_aperture_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Repair the supplied buggy Verilog-A artifact while preserving the public module interface and artifact boundary.
- Use the buggy source plus the public intended behavior below; do not change the companion testbench contract.

## Public Interface To Preserve

- `dut_buggy.va` declares module `sample_hold_aperture_ref` with positional ports: `VDD`, `VSS`, `clk`, `vin`, `vout`.
- `dut_fixed.va` declares module `sample_hold_aperture_ref` with positional ports: `VDD`, `VSS`, `clk`, `vin`, `vout`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=130n maxstep=100p
```

The release harness expects these exact public scalar observables:

- `vin`
- `clk`
- `vout`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `rising_clk_arms_delayed_aperture_sample`
- `vout_matches_vin_after_aperture_not_at_clock_edge`
- `held_output_sequence_changes_only_after_safe_aperture_windows`

## Observed Mismatch Framing

The supplied buggy artifact violates one or more public behavior checks above under the release validation testbench.
Repair the observable behavior without renaming modules, changing ports, or weakening the public testbench contract.

## Output Contract

Return exactly one source artifact named `dut_fixed.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

The provided voltage-domain track/hold model has an aperture bug: it samples
`vin` immediately at the rising `clk` edge instead of waiting for the configured
aperture delay. Fix the model so each rising clock edge arms a delayed sample,
then captures `vin` after `taperture` and holds that value until the next
sample event.

The fixed module must be named `sample_hold_aperture_ref` and use electrical
ports `VDD`, `VSS`, `clk`, `vin`, and `vout`. The output should drive the held
sample value with a smoothed voltage transition. The supply pins are available
for interface compatibility, but this task is still a pure voltage-domain
behavioral model.

Use voltage contributions and smoothed output transitions. Do not use current
contributions, `ddt()`, or `idt()`.
