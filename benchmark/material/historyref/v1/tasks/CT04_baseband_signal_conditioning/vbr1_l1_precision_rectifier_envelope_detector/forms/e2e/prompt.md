# Task: vbr1_l1_precision_rectifier_envelope_detector:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L1`
- Category: Baseband Signal Conditioning
- Base function: Precision rectifier/envelope detector
- Domain: `voltage`
- Target artifact(s): `precision_rectifier_envelope_detector.va`, `tb_precision_rectifier_envelope_detector.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate all target artifacts: `precision_rectifier_envelope_detector.va`, `tb_precision_rectifier_envelope_detector.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `precision_rectifier_envelope_detector.va` must be co-located with the generated Spectre testbench.
- Include the generated DUT exactly with `ahdl_include "precision_rectifier_envelope_detector.va"` in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

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

Return exactly these source artifacts:

- `precision_rectifier_envelope_detector.va`
- `tb_precision_rectifier_envelope_detector.scs`

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
