# Task: vbr1_l1_gain_estimator:tb

## Release Task Contract

- Form: `tb`
- Level: `L1`
- Category: Measurement Instrumentation Flows
- Base function: Gain estimator
- Domain: `voltage`
- Target artifact(s): `tb_gain_estimator_ref.scs`
- Supplied/reference support artifact(s): `gain_estimator.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `gain_estimator.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "gain_estimator.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `gain_estimator.va` declares module `gain_estimator` with positional ports: `VDD`, `VSS`, `vinp`, `vinn`, `voutp`, `voutn`, `gain_out`, `valid`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=240n maxstep=200p errpreset=conservative
```

The release harness expects these exact public scalar observables:

- `vinp`
- `vinn`
- `voutp`
- `voutn`
- `gain_out`
- `valid`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `VDD`
- `VSS`
- `vinp`
- `vinn`
- `voutp`
- `voutn`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "gain_estimator.va"

Vvdd (VDD 0) vsource type=dc dc=0.9
Vvss (VSS 0) vsource type=dc dc=0

XGAIN (VDD VSS vinp vinn voutp voutn gain_out valid) gain_estimator sample_period=1n start_time=20n gain_scale=10 min_input_span=0.02 tedge=200p

tran tran stop=240n maxstep=200p errpreset=conservative
save vinp vinn voutp voutn gain_out valid
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `valid_asserts_after_observation_window`
- `waveform_gain_is_about_six`
- `gain_out_matches_waveform_derived_gain`

## Public L1 Testbench Stimulus Contract

This TB row should provide a clean differential gain measurement window:

- Drive `vinp/vinn` as a small differential sine around 0.45 V common mode.
- Drive `voutp/voutn` as a larger differential sine at the same frequency and
  common mode, with about 6x the input differential amplitude.
- Run long enough for the supplied estimator observation window to complete.
- Save `vinp`, `vinn`, `voutp`, `voutn`, `gain_out`, and `valid` exactly.

The expected public relation is: waveform-derived differential gain is about
six, `gain_out` reports the same gain, and `valid` asserts after observation.
Do not generate checker logic.

## Output Contract

Return exactly one source artifact named `tb_gain_estimator_ref.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

Write a Spectre transient testbench for the supplied `gain_estimator` behavioral measurement helper.

Public requirements:

- Instantiate `gain_estimator` with ports `(VDD VSS vinp vinn voutp voutn gain_out valid)`.
- Drive `VDD=0.9 V` and `VSS=0 V`.
- Provide a differential input with about 60 mV peak-to-peak span.
- Provide a differential output with about 360 mV peak-to-peak span, corresponding to gain near 6.
- Run long enough for `valid` to assert and for `gain_out` to settle.
- Save exactly `vinp`, `vinn`, `voutp`, `voutn`, `gain_out`, and `valid`.
- Use voltage-domain behavioral sources only; avoid transistor-level devices, AC/noise analysis, and current-domain solver assumptions.
