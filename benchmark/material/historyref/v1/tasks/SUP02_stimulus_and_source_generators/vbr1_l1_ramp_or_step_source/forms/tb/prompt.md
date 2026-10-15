# Task: vbr1_l1_ramp_or_step_source:tb

## Release Task Contract

- Form: `tb`
- Level: `L1`
- Category: Stimulus and Source Generators
- Base function: Periodic phase-ramp guard source
- Domain: `voltage`
- Target artifact(s): `tb_bound_step_period_guard_ref.scs`
- Supplied/reference support artifact(s): `bound_step_period_guard_ref.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `bound_step_period_guard_ref.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "bound_step_period_guard_ref.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

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

Public stimulus/source nodes visible in the reference harness include:

- `VDD`
- `VSS`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "bound_step_period_guard_ref.va"

Vvdd (VDD 0) vsource dc=0.9 type=dc
Vvss (VSS 0) vsource dc=0.0 type=dc

IDUT (VDD VSS guard_out phase_out) bound_step_period_guard_ref period=8n pulse_w=1.5n points_per_period=16 tedge=40p

tran tran stop=34n maxstep=20n errpreset=conservative
save guard_out phase_out
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `periodic_phase_ramp_wraps`
- `guard_pulse_repeats_each_period`
- `guard_pulse_width_fraction`

## Output Contract

Return exactly one source artifact named `tb_bound_step_period_guard_ref.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Periodic phase-ramp guard source TB Companion

Write a Spectre transient testbench for this behavioral release task.

This task form is materialized from the already source-controlled `e2e`
release gold for `Periodic phase-ramp guard source`. It exists to make the public
benchmark split complete without inventing a new circuit kernel or a fake
bugfix.

Domain: pure voltage-domain behavioral Verilog-A.

Public requirements:

- include a transient `tran` analysis
- save the public observables needed by the public behavior checks
- include or instantiate the behavioral module under test
- satisfy the named behavior checks using only public waveforms and side outputs
- avoid transistor-level devices, AC/noise analysis, and current-domain
  solver assumptions
