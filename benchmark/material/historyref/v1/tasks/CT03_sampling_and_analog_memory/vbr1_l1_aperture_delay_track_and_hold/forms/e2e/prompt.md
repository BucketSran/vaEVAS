# Task: vbr1_l1_aperture_delay_track_and_hold:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L1`
- Category: Sampling and Analog Memory
- Base function: Aperture-delay track-and-hold
- Domain: `voltage`
- Target artifact(s): `sample_hold_aperture_ref.va`, `tb_sample_hold_aperture_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate all target artifacts: `sample_hold_aperture_ref.va`, `tb_sample_hold_aperture_ref.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `sample_hold_aperture_ref.va` must be co-located with the generated Spectre testbench.
- Include the generated DUT exactly with `ahdl_include "sample_hold_aperture_ref.va"` in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

- `sample_hold_aperture_ref.va` declares module `sample_hold_aperture_ref` with positional ports: `VDD`, `VSS`, `clk`, `vin`, `vout`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=140n maxstep=100p
```

The release harness expects these exact public scalar observables:

- `vin`
- `clk`
- `vout`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `VDD`
- `VSS`
- `clk`
- `vin`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "sample_hold_aperture_ref.va"

Vvdd (VDD 0) vsource dc=0.9
Vvss (VSS 0) vsource dc=0.0

XDUT (VDD VSS clk vin vout) sample_hold_aperture_ref

tran tran stop=140n maxstep=100p
save vin clk vout
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `sampled_values_match_aperture_delayed_input`
- `held_output_remains_between_samples`

## Output Contract

Return exactly these source artifacts:

- `sample_hold_aperture_ref.va`
- `tb_sample_hold_aperture_ref.scs`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

Write both the Verilog-A DUT and Spectre testbench for a sample-and-hold with aperture delay.

The DUT module is `sample_hold_aperture_ref` with ports `VDD, VSS, clk, vin, vout`. All ports are electrical; digital-control ports use 0/0.9 V logic levels.

Required DUT behavior:
- On a rising `clk` edge, schedule sampling after a 200 ps aperture delay.
- At the aperture timer event, capture `vin` and hold it on `vout` until the next sample.
- Drive `vout` with smoothed voltage-domain transitions.

Required testbench behavior:
- Drive a changing input around clock edges so aperture-delayed sampling is distinguishable from immediate sampling.
- Save `clk`, `vin`, and `vout`.

Use voltage contributions only in the Verilog-A DUT. Do not use current contributions, `ddt()`, or `idt()`.
