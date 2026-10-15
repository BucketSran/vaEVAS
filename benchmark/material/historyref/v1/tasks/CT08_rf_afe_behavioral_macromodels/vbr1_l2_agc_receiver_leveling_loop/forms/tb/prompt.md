# Task: vbr1_l2_agc_receiver_leveling_loop:tb

## Release Task Contract

- Form: `tb`
- Level: `L2`
- Category: RF and AFE Behavioral Macromodels
- Base function: AGC receiver leveling loop
- Domain: `voltage`
- Target artifact(s): `tb_agc_receiver_leveling_loop.scs`
- Supplied/reference support artifact(s): `agc_receiver_leveling_loop.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## L2 Background And Claim Boundary

This Level-2 row is a behavioral composition/flow task for AGC receiver leveling loop. It should expose intermediate state, multi-stage behavior, or a closed-loop relation through the public observables below.
Stay within the listed voltage-domain/event-driven contract. Do not use transistor-level devices, current-domain loads, AC/noise analysis, S-parameters, or hidden checker logic unless the public contract explicitly lists them.
Paper-facing claims for this row are limited to the public behavior checks below; do not broaden the task into full silicon implementation, layout, device physics, or unlisted performance metrics.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `agc_receiver_leveling_loop.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "agc_receiver_leveling_loop.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `agc_receiver_leveling_loop.va` declares module `agc_receiver_leveling_loop` with positional ports: `clk`, `rst`, `vin`, `out`, `metric`, `gain_mon`, `rssi_mon`.

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
- `gain_mon`
- `rssi_mon`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `clk`
- `rst`
- `vin`

## Public Stimulus Schedule Contract

Use this exact public source schedule in generated Spectre testbenches. This schedule is part of the public testbench contract; it is not hidden checker logic.

Public schedule source: `tb_agc_receiver_leveling_loop.scs`.

```spectre
Vclk (clk 0) vsource type=pulse val0=0 val1=0.9 period=2n width=1n rise=50p fall=50p
Vrst (rst 0) vsource type=pwl wave=[0 0.9 2n 0.9 2.1n 0 80n 0]
Vvin (vin 0) vsource type=pwl wave=[0 0.45 8n 0.52 21.9n 0.52 22n 0.78 55.9n 0.78 56n 0.55 80n 0.55]
```

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "agc_receiver_leveling_loop.va"

XDUT (clk rst vin out metric gain_mon rssi_mon) agc_receiver_leveling_loop

tran tran stop=80n maxstep=0.5n
save clk rst vin out metric gain_mon rssi_mon
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `agc_reduces_gain_on_large_input`
- `leveled_output_amplitude`
- `lock_metric_after_settling`
- `rssi_monitor_rises_on_overload`
- `gain_monitor_decreases_after_high_rssi`

## Output Contract

Return exactly one source artifact named `tb_agc_receiver_leveling_loop.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### AGC receiver leveling loop (tb-generation)

Write a Spectre transient testbench for the described behavioral Verilog-A module.

Behavioral intent:

Compose a receiver gain path, envelope/RSSI observation, and gain-control update so output amplitude settles toward a target level.

Module name: `agc_receiver_leveling_loop`.
Domain: pure voltage-domain behavioral Verilog-A.
Do not use current contributions, transistor-level devices, AC/noise analysis,
or KCL/KVL solving assumptions.

This is a voltage-domain RF/AFE behavioral macromodel task. Model observable gain, compression, LO polarity, RSSI, limiting, AGC, or I/Q baseband behavior with event-driven voltage states. Do not implement transistor RF physics, S-parameters, current-domain loads, communication modem algorithms, or full link-level decoding.

Public port contract:

```verilog
module agc_receiver_leveling_loop(clk, rst, vin, out, metric, gain_mon, rssi_mon);
input clk, rst, vin;
output out, metric, gain_mon, rssi_mon;
electrical clk, rst, vin, out, metric, gain_mon, rssi_mon;
```

Signal contract:

clk and rst are voltage-coded logic signals. vin is the receiver input envelope around 0.45 V common mode. rssi_mon is the public envelope/RSSI monitor, gain_mon is the bounded public gain-control monitor, the internal gain-control loop reduces gain under overload and restores a target output amplitude, out is the leveled receiver output, and metric is high near target amplitude.

Saved waveform columns:

```text
clk rst vin out metric gain_mon rssi_mon
```

Public transient contract:

```spectre
tran tran stop=80n maxstep=0.5n
```
