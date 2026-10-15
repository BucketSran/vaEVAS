# Task: vbr1_l1_gain_trim_controller:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L1`
- Category: Calibration, DEM, and Control
- Base function: Gain trim controller
- Domain: `voltage`
- Target artifact(s): `gain_trim_controller.va`, `tb_gain_trim_controller_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate all target artifacts: `gain_trim_controller.va`, `tb_gain_trim_controller_ref.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `gain_trim_controller.va` must be co-located with the generated Spectre testbench.
- Include the generated DUT exactly with `ahdl_include "gain_trim_controller.va"` in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

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

Public stimulus/source nodes visible in the reference harness include:

- `clk`
- `rst`
- `meas`
- `target`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "gain_trim_controller.va"

XDUT (clk rst meas target gain_ctrl) gain_trim_controller

tran tran stop=620n maxstep=500p
save clk rst meas target gain_ctrl
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `reset_gain_control_near_0p30`
- `low_measured_value_increases_control`
- `high_measured_value_decreases_control`
- `gain_control_reaches_high_and_low_clamps`

## Output Contract

Return exactly these source artifacts:

- `gain_trim_controller.va`
- `tb_gain_trim_controller_ref.scs`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

## Gain trim controller end-to-end

Write both the Verilog-A DUT and Spectre testbench for a gain trim controller.

The DUT module is `gain_trim_controller` with ports `clk, rst, meas, target, gain_ctrl`. All ports are electrical; digital-control ports use 0/0.9 V logic levels.

Required DUT behavior:
- Initialize and reset `gain_ctrl` to 0.30 V on rising `clk` while `rst` is high.
- When `meas` is below `target - 0.02`, increase the control by 0.05 V; when above `target + 0.02`, decrease it by 0.05 V.
- Hold inside the deadband, clamp to 0.05 V to 0.85 V, and drive through `transition()`.

Required testbench behavior:
- Provide target and measured waveforms that create low-measured and high-measured windows long enough to hit both clamps.
- Run transient analysis with clocked samples through trim increase, upper clamp, trim decrease, and lower clamp phases.

Use voltage contributions only in the Verilog-A DUT. Do not use current contributions, `ddt()`, or `idt()`.

Return exactly two files: `gain_trim_controller.va` and `tb_gain_trim_controller_ref.scs`.
