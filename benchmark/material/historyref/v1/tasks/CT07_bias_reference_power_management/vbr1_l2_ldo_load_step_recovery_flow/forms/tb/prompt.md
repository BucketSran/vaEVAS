# Task: vbr1_l2_ldo_load_step_recovery_flow:tb

## Release Task Contract

- Form: `tb`
- Level: `L2`
- Category: Bias Reference and Power Management
- Base function: LDO load-step recovery flow
- Domain: `voltage`
- Target artifact(s): `tb_ldo_load_step_recovery_flow.scs`
- Supplied/reference support artifact(s): `ldo_load_step_recovery_flow.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## L2 Background And Claim Boundary

This Level-2 row is a behavioral composition/flow task for LDO load-step recovery flow. It should expose intermediate state, multi-stage behavior, or a closed-loop relation through the public observables below.
Stay within the listed voltage-domain/event-driven contract. Do not use transistor-level devices, current-domain loads, AC/noise analysis, S-parameters, or hidden checker logic unless the public contract explicitly lists them.
Paper-facing claims for this row are limited to the public behavior checks below; do not broaden the task into full silicon implementation, layout, device physics, or unlisted performance metrics.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `ldo_load_step_recovery_flow.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "ldo_load_step_recovery_flow.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `ldo_load_step_recovery_flow.va` declares module `ldo_load_step_recovery_flow` with positional ports: `clk`, `rst`, `vin`, `out`, `metric`, `load_mon`, `ctrl_mon`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=80n maxstep=0.5n
```

The release harness expects these exact public scalar observables:

- `clk`
- `rst`
- `vin`
- `out`
- `metric`
- `load_mon`
- `ctrl_mon`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `clk`
- `rst`
- `vin`

## Public Stimulus Schedule Contract

Use this exact public source schedule in generated Spectre testbenches. This schedule is part of the public testbench contract; it is not hidden checker logic.

Public schedule source: `tb_ldo_load_step_recovery_flow.scs`.

```spectre
Vclk (clk 0) vsource type=pulse val0=0 val1=0.9 period=2n width=1n rise=50p fall=50p
Vrst (rst 0) vsource type=pwl wave=[0 0.9 2n 0.9 2.1n 0 80n 0]
Vvin (vin 0) vsource type=pwl wave=[0 0.10 15.9n 0.10 16n 0.85 41.9n 0.85 42n 0.20 61.9n 0.20 62n 0.75 80n 0.75]
```

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "ldo_load_step_recovery_flow.va"

XDUT (clk rst vin out metric load_mon ctrl_mon) ldo_load_step_recovery_flow

tran tran stop=80n maxstep=0.5n
save clk rst vin out metric load_mon ctrl_mon
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `load_step_transient_droop_visible`
- `closed_loop_recovery_after_step`
- `metric_marks_recovered_regulation`
- `load_monitor_tracks_step`
- `control_monitor_responds_to_droop`

## Output Contract

Return exactly one source artifact named `tb_ldo_load_step_recovery_flow.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### LDO load-step recovery flow (tb-generation)

Write a Spectre transient testbench for the described behavioral Verilog-A module.

Behavioral intent:

Compose a regulator macro model with repeated load-step disturbances and recovery-status observation.

Module name: `ldo_load_step_recovery_flow`.
Domain: pure voltage-domain behavioral Verilog-A.
Do not use current contributions, transistor-level devices, AC/noise analysis,
or KCL/KVL solving assumptions.

This is a voltage-domain macro-model task for bias/reference/power management behavior. Model observable startup, threshold, trim, hysteresis, droop, or recovery behavior with event-driven voltage state updates. Do not use branch currents, transistor devices, process-device equations, or true current-mode regulation loops.

Public port contract:

```verilog
module ldo_load_step_recovery_flow(clk, rst, vin, out, metric, load_mon, ctrl_mon);
input clk, rst, vin;
output out, metric, load_mon, ctrl_mon;
electrical clk, rst, vin, out, metric, load_mon, ctrl_mon;
```

Signal contract:

clk and rst are voltage-coded logic signals. vin is the public load-step stimulus. load_mon tracks the bounded load request seen by the regulator macro, ctrl_mon is an abstract voltage-domain pass/recovery control monitor, out is the regulator output after transient droop and recovery, and metric marks recovered regulation after each load transition. This remains a behavioral load-step recovery macro, not a transistor/pass-device LDO implementation.

Saved waveform columns:

```text
clk rst vin out metric load_mon ctrl_mon
```

Public transient contract:

```spectre
tran tran stop=80n maxstep=0.5n
```
