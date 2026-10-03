# Task: vbr1_l1_ramp_or_step_source:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: Stimulus and Source Generators
- Base function: Periodic phase-ramp guard source
- Domain: `voltage`
- Target artifact(s): `bound_step_period_guard_ref.va`
- Supplied/reference support artifact(s): `tb_bound_step_period_guard_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

## Public Verilog-A Interface

- `bound_step_period_guard_ref.va` declares module `bound_step_period_guard_ref` with positional ports: `VDD`, `VSS`, `guard_out`, `phase_out`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=34n maxstep=20n errpreset=conservative
```

The release harness expects these exact public scalar observables:

- `guard_out`
- `phase_out`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `periodic_phase_ramp_wraps`
- `guard_pulse_repeats_each_period`
- `guard_pulse_width_fraction`

## Output Contract

Return exactly one source artifact named `bound_step_period_guard_ref.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Periodic phase-ramp guard source DUT

Write the Verilog-A DUT artifact(s) for `Periodic phase-ramp guard source`.

This is a function-checked DUT task, not a generic companion wrapper. The
public contract below defines the exact module interface, voltage-domain
behavior, and waveform observables used by the release checker.

Domain: pure voltage-domain behavioral Verilog-A.

## Module Contract

- Declaration: `bound_step_period_guard_ref(VDD, VSS, guard_out, phase_out)`

Ports:

- `VDD`, `VSS`: electrical supply rails
- `guard_out`: output electrical guard pulse that marks the beginning of each period
- `phase_out`: output electrical normalized phase ramp within each period

## Behavioral Contract

- generate an 8 ns periodic phase ramp from 0 V toward `VDD`
- wrap the phase ramp at each new period
- drive `guard_out` high only during the first 1.5 ns of each period
- `$bound_step(...)` may be used to keep the narrow guard pulse observable, but the scored function is the ramp and guard timing

## Public Evaluation Observables

The companion validation testbench saves these waveform columns:

- `time`
- `guard_out`
- `phase_out`
