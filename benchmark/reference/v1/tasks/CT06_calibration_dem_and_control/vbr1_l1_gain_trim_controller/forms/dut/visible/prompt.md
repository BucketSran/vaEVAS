# Task: vbr1_l1_gain_trim_controller:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: Calibration, DEM, and Control
- Base function: Gain trim controller
- Domain: `voltage`
- Target artifact(s): `gain_trim_controller.va`
- Supplied/reference support artifact(s): `tb_gain_trim_controller_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

## Public Verilog-A Interface

- `gain_trim_controller.va` declares module `gain_trim_controller` with positional ports: `clk`, `rst`, `meas`, `target`, `gain_ctrl`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=620n maxstep=500p
```

The release harness expects these exact public scalar observables:

- `clk`
- `rst`
- `meas`
- `target`
- `gain_ctrl`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `reset_gain_control_near_0p30`
- `low_measured_value_increases_control`
- `high_measured_value_decreases_control`
- `gain_control_reaches_high_and_low_clamps`

## Output Contract

Return exactly one source artifact named `gain_trim_controller.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

## Gain trim controller DUT

Write a pure voltage-domain Verilog-A module for a gain trim controller.

The DUT module is `gain_trim_controller` with ports `clk, rst, meas, target, gain_ctrl`. All ports are electrical; digital-control ports use 0/0.9 V logic levels.

Required behavior:
- Initialize and reset `gain_ctrl` to 0.30 V on rising `clk` while `rst` is high.
- When `meas` is below `target - 0.02`, increase the control by 0.05 V; when above `target + 0.02`, decrease it by 0.05 V.
- Hold inside the deadband, clamp to 0.05 V to 0.85 V, and drive through `transition()`.

Use voltage contributions only. Do not use current contributions, `ddt()`, or `idt()`.

Return exactly one complete Verilog-A file named `gain_trim_controller.va`.
