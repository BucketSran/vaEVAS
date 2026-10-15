# Task: vbr1_l1_power_on_reset_detector:tb

## Release Task Contract

- Form: `tb`
- Level: `L1`
- Category: Bias Reference and Power Management
- Base function: Power-on-reset detector
- Domain: `voltage`
- Target artifact(s): `tb_power_on_reset_detector.scs`
- Supplied/reference support artifact(s): `power_on_reset_detector.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `power_on_reset_detector.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "power_on_reset_detector.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `power_on_reset_detector.va` declares module `power_on_reset_detector` with positional ports: `clk`, `rst`, `vin`, `out`, `metric`.

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

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `clk`
- `rst`
- `vin`

## Public Stimulus Schedule Contract

Use this exact public source schedule in generated Spectre testbenches. This schedule is part of the public testbench contract; it is not hidden checker logic.

Public schedule source: `tb_power_on_reset_detector.scs`.

```spectre
Vclk (clk 0) vsource type=pulse val0=0 val1=0.9 period=2n width=1n rise=50p fall=50p
Vrst (rst 0) vsource type=pwl wave=[0 0.9 2n 0.9 2.1n 0 80n 0]
Vvin (vin 0) vsource type=pwl wave=[0 0.20 7.9n 0.20 8n 0.75 43.9n 0.75 44n 0.50 53.9n 0.50 54n 0.75 80n 0.75]
```

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "power_on_reset_detector.va"

XDUT (clk rst vin out metric) power_on_reset_detector

tran tran stop=80n maxstep=0.5n
save clk rst vin out metric
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `reset_asserted_below_supply_threshold`
- `release_delay_after_power_good`
- `brownout_reasserts_reset`

## Public Behavioral Targets

- Treat vin as a supply ramp. Keep out reset-asserted high while reset input is high or vin is below about 0.62 V.
- After vin is power-good and reset is released, wait about four rising clock updates before deasserting out low.
- During the release delay, metric may indicate partial release; after release, metric should be high.
- If supply falls below threshold or reset asserts again, immediately assert out high and clear the release delay.

## Output Contract

Return exactly one source artifact named `tb_power_on_reset_detector.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### Power-on-reset detector (tb-generation)

Write a Spectre transient testbench for the described behavioral Verilog-A module.

Behavioral intent:

Detect a supply ramp, hold reset asserted through a release-delay window, and reassert reset on brownout.

Module name: `power_on_reset_detector`.
Domain: pure voltage-domain behavioral Verilog-A.
Do not use current contributions, transistor-level devices, AC/noise analysis,
or KCL/KVL solving assumptions.

This is a voltage-domain macro-model task for bias/reference/power management behavior. Model observable startup, threshold, trim, hysteresis, droop, or recovery behavior with event-driven voltage state updates. Do not use branch currents, transistor devices, process-device equations, or true current-mode regulation loops.

Public port contract:

```verilog
module power_on_reset_detector(clk, rst, vin, out, metric);
input clk, rst, vin;
output out, metric;
electrical clk, rst, vin, out, metric;
```

Signal contract:

clk and rst are voltage-coded logic signals. vin is the supply-ramp/brownout stimulus. out is an active-high reset voltage that releases only after a power-good delay and reasserts on brownout. metric marks released/reset-valid status.

Saved waveform columns:

```text
clk rst vin out metric
```

Public transient contract:

```spectre
tran tran stop=80n maxstep=0.5n
```
