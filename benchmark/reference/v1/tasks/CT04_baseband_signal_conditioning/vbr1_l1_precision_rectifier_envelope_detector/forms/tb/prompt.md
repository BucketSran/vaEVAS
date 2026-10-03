# Task: vbr1_l1_precision_rectifier_envelope_detector:tb

## Release Task Contract

- Form: `tb`
- Level: `L1`
- Category: Baseband Signal Conditioning
- Base function: Precision rectifier/envelope detector
- Domain: `voltage`
- Target artifact(s): `tb_precision_rectifier_envelope_detector.scs`
- Supplied/reference support artifact(s): `precision_rectifier_envelope_detector.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `precision_rectifier_envelope_detector.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "precision_rectifier_envelope_detector.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `precision_rectifier_envelope_detector.va` declares module `precision_rectifier_envelope_detector` with positional ports: `clk`, `rst`, `vin`, `rect`, `env`, `metric`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=90n maxstep=250p
```

The release harness expects these exact public scalar observables:

- `clk`
- `rst`
- `vin`
- `rect`
- `env`
- `metric`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `clk`
- `rst`
- `vin`

## Public Stimulus Schedule Contract

Use this exact public source schedule in generated Spectre testbenches. This schedule is part of the public testbench contract; it is not hidden checker logic.

Public schedule source: `tb_precision_rectifier_envelope_detector.scs`.

```spectre
Vclk (clk 0) vsource type=pulse val0=0 val1=0.9 period=2n width=1n delay=0.5n rise=100p fall=100p
Vrst (rst 0) vsource type=pwl wave=[0 0.9 2n 0.9 2.1n 0 90n 0]
Vvin (vin 0) vsource type=pwl wave=[0 0.45 8n 0.75 16n 0.45 24n 0.15 32n 0.45 42n 0.85 54n 0.45 66n 0.35 78n 0.45 90n 0.45]
```

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "precision_rectifier_envelope_detector.va"

XDUT (clk rst vin rect env metric) precision_rectifier_envelope_detector

tran tran stop=90n maxstep=250p
save clk rst vin rect env metric
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `full_wave_rectification_around_common_mode`
- `envelope_peak_hold_and_decay`
- `negative_half_cycle_rectifies`
- `hold_metric_marks_envelope_memory`

## Output Contract

Return exactly one source artifact named `tb_precision_rectifier_envelope_detector.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

Write a voltage-domain precision rectifier with an envelope output.

The module rectifies the absolute deviation around the common-mode voltage rather than around
ground. It also tracks a peak envelope: the envelope updates quickly to new rectified peaks and
decays slowly when the rectified input falls. The metric output is high when the envelope is
holding above the instantaneous rectified value.

Public port contract:

```verilog
module precision_rectifier_envelope_detector(clk, rst, vin, rect, env, metric);
input clk, rst, vin;
output rect, env, metric;
electrical clk, rst, vin, rect, env, metric
```

Signal contract:

All logic controls are voltage-coded, low=0 V and high=0.9 V with threshold 0.45 V. The design remains pure voltage-domain behavioral Verilog-A: no current contributions, transistor devices, AC/noise analysis, or KCL/KVL solving assumptions.

Saved waveform columns:

```text
clk rst vin rect env metric
```

Public transient contract:

```spectre
tran tran stop=96n maxstep=0.25n
```
