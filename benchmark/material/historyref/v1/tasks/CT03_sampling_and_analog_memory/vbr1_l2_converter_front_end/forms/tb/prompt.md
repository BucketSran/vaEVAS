# Task: vbr1_l2_converter_front_end:tb

## Release Task Contract

- Form: `tb`
- Level: `L2`
- Category: Sampling and Analog Memory
- Base function: Converter front-end
- Domain: `voltage`
- Target artifact(s): `tb_sample_hold_droop_ref.scs`
- Supplied/reference support artifact(s): `sample_hold_droop_ref.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## L2 Background And Claim Boundary

This Level-2 row is a behavioral composition/flow task for Converter front-end. It should expose intermediate state, multi-stage behavior, or a closed-loop relation through the public observables below.
Stay within the listed voltage-domain/event-driven contract. Do not use transistor-level devices, current-domain loads, AC/noise analysis, S-parameters, or hidden checker logic unless the public contract explicitly lists them.
Paper-facing claims for this row are limited to the public behavior checks below; do not broaden the task into full silicon implementation, layout, device physics, or unlisted performance metrics.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `sample_hold_droop_ref.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "sample_hold_droop_ref.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `sample_hold_droop_ref.va` declares module `sample_hold_droop_ref` with positional ports: `vdd`, `vss`, `clk`, `vin`, `vout`, `valid`, `coarse`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=170n maxstep=0.1n
```

The release harness expects these exact public scalar observables:

- `vin`
- `clk`
- `vout`
- `valid`
- `coarse`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `vdd`
- `vss`
- `clk`
- `vin`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "sample_hold_droop_ref.va"

Vvdd (vdd 0) vsource dc=0.9
Vvss (vss 0) vsource dc=0.0

XDUT (vdd vss clk vin vout valid coarse) sample_hold_droop_ref vth=0.45 tau=90n dt=0.5n taperture=200p valid_width=2n trf=40p

tran tran stop=170n maxstep=0.1n
save vin clk vout valid coarse
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `aperture_delayed_sample_tracks_vin`
- `hold_windows_show_bounded_droop`
- `coarse_decision_matches_held_sample`
- `valid_pulses_mark_completed_samples`

## Public L2 Behavior Contract

This row is a converter front-end chain. The testbench must make the sampling
handoff observable:

1. Drive multiple rising `clk` edges and keep all signals in the 0 V to 0.9 V
   voltage domain.
2. Move `vin` near selected clock edges so the aperture-delayed sample differs
   from a naive immediate-edge sample.
3. Leave hold intervals long enough for bounded droop on `vout` to be visible.
4. Save `valid` pulses and `coarse` so the evaluator can identify completed
   samples and compare the coarse decision against the held value.

The expected public relation is: aperture-delayed `vin` sample -> drooping held
`vout` -> `coarse` threshold decision -> `valid` pulse. Do not generate checker
logic in the testbench.

## Output Contract

Return exactly one source artifact named `tb_sample_hold_droop_ref.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Converter front-end chain Testbench Companion

Write a Spectre transient testbench for the `Converter front-end` behavioral
Verilog-A release task. This is the testbench-generation companion for an
already materialized end-to-end task.

The testbench should instantiate the same behavioral DUT or system module used
by the corresponding end-to-end form, drive an aperture-sensitive sampling
scenario, save the observable waveform or metric signals, and preserve the
EVAS/Spectre validation contract.

Domain: pure voltage-domain behavioral Verilog-A.

Public requirements:

- include a transient `tran` analysis
- save `vin`, `clk`, `vout`, `valid`, and `coarse`
- include or instantiate the Verilog-A behavioral module under test
- exercise aperture-delayed sampling, bounded hold droop, coarse decision, and
  valid-pulse behavior
- avoid transistor-level devices, AC/noise analysis, and current-domain
  solver assumptions
