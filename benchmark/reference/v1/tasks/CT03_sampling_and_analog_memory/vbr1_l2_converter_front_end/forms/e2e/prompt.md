# Task: vbr1_l2_converter_front_end:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L2`
- Category: Sampling and Analog Memory
- Base function: Converter front-end
- Domain: `voltage`
- Target artifact(s): `sample_hold_droop_ref.va`, `tb_sample_hold_droop_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## L2 Background And Claim Boundary

This Level-2 row is a behavioral composition/flow task for Converter front-end. It should expose intermediate state, multi-stage behavior, or a closed-loop relation through the public observables below.
Stay within the listed voltage-domain/event-driven contract. Do not use transistor-level devices, current-domain loads, AC/noise analysis, S-parameters, or hidden checker logic unless the public contract explicitly lists them.
Paper-facing claims for this row are limited to the public behavior checks below; do not broaden the task into full silicon implementation, layout, device physics, or unlisted performance metrics.

## Form-Specific Requirements

- Generate all target artifacts: `sample_hold_droop_ref.va`, `tb_sample_hold_droop_ref.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `sample_hold_droop_ref.va` must be co-located with the generated Spectre testbench.
- Include the generated DUT exactly with `ahdl_include "sample_hold_droop_ref.va"` in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

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

This row is a converter front-end chain. It must expose the handoff from
aperture-delayed sampling to hold droop and coarse decision:

1. Aperture-delayed sampling:
   - On each rising `clk` edge, wait the public `taperture` interval before
     sampling `vin`.
   - The testbench should move `vin` near selected clock edges so delayed
     sampling can be distinguished from immediate edge sampling.

2. Hold and droop:
   - Drive `vout` from the sampled value, then let it droop gradually toward
     `vss` between samples according to the public droop behavior.
   - Keep droop bounded; `vout` should not jump instantly to zero during a hold
     window.

3. Coarse decision and valid pulse:
   - Drive `coarse` from the held sample compared with `vth`.
   - Pulse `valid` after the delayed sample completes so completed samples can
     be identified in the saved waveform.

The public relation is: `vin` near the aperture instant -> held `vout` with
bounded droop -> `coarse` decision -> `valid` pulse marking sample completion.

## Output Contract

Return exactly these source artifacts:

- `sample_hold_droop_ref.va`
- `tb_sample_hold_droop_ref.scs`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

Write a Verilog-A module named `sample_hold_droop_ref` and one minimal
voltage-domain Spectre transient testbench.

## Objective

Create a pure voltage-domain converter front-end chain: aperture-delayed
sampling, hold droop, a coarse threshold decision, and a valid pulse that marks
completed samples.

## DUT Contract

- Module name: `sample_hold_droop_ref`
- Ports, all `electrical`, exactly in this order: `vdd`, `vss`, `clk`, `vin`,
  `vout`, `valid`, `coarse`
- Parameters:
  - `vth` real, default `0.45`
  - `tau` real, default `90n`
  - `dt` real, default `0.5n`
  - `taperture` real, default `200p`
  - `valid_width` real, default `2n`
  - `trf` real, default `40p`
- Behavior:
  - On each rising edge of `clk`, wait `taperture`, then sample `V(vin)`.
  - Between samples, hold the sampled value on `vout` while adding finite
    droop toward `V(vss)`.
  - Drive `coarse` high when the sampled value is above `vth`, otherwise low.
  - Pulse `valid` after each aperture-delayed sample completes.
  - Keep all outputs in the supply range and use `transition(...)`.

## Testbench Contract

- Use a 0.9 V supply and 0 V reference.
- Drive `clk` with enough rising edges inside the final validation window to create multiple hold intervals.
- Drive `vin` transitions near selected clock edges so aperture-delayed sampling
  is distinguishable from immediate edge sampling.
- Instantiate the DUT by positional ports.
- Save these exact scalar names: `vin`, `clk`, `vout`, `valid`, `coarse`.
- Include the generated DUT file `sample_hold_droop_ref.va`.
