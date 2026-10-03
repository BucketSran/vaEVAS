# Task: vbr1_l1_gain_trim_controller:bugfix

## Release Task Contract

- Form: `bugfix`
- Level: `L1`
- Category: Calibration, DEM, and Control
- Base function: Gain trim controller
- Domain: `voltage`
- Target artifact(s): `dut_fixed.va`
- Supplied/reference support artifact(s): `dut_buggy.va`, `tb_gain_trim_controller_buggy.scs`, `tb_gain_trim_controller_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Repair the supplied buggy Verilog-A artifact while preserving the public module interface and artifact boundary.
- Use the buggy source plus the public intended behavior below; do not change the companion testbench contract.

## Public Interface To Preserve

- `dut_buggy.va` declares module `gain_trim_controller` with positional ports: `clk`, `rst`, `meas`, `target`, `gain_ctrl`.
- `dut_fixed.va` declares module `gain_trim_controller` with positional ports: `clk`, `rst`, `meas`, `target`, `gain_ctrl`.

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

- `reset_restores_nominal_gain_control`
- `low_measurement_window_increases_gain_control`
- `high_measurement_window_decreases_gain_control`
- `gain_control_reaches_high_and_low_clamps`

## Observed Mismatch Framing

The supplied buggy artifact violates one or more public behavior checks above under the release validation testbench.
Repair the observable behavior without renaming modules, changing ports, or weakening the public testbench contract.

## Output Contract

Return exactly one source artifact named `dut_fixed.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

## Gain trim controller bugfix

The provided voltage-domain gain-trim controller updates the control
voltage in the wrong direction relative to the measured error. Fix the
controller so it increases gain control when the measured value is below the
target band and decreases gain control when the measured value is above the
target band.

The fixed module must be named `gain_trim_controller` and use electrical ports
`clk`, `rst`, `meas`, `target`, and `gain_ctrl`. Reset should restore the
control voltage to its nominal starting value. Rising clock edges should update
the control state, and the output should reach and hold both the upper and lower valid trim clamps under sustained error windows.

Use voltage contributions and event-driven state updates. Do not use current
contributions, `ddt()`, or `idt()`.

Return exactly one complete Verilog-A file named `dut_fixed.va`.
