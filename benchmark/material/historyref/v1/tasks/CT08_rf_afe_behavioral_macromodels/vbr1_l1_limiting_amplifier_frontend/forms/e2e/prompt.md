# Task: vbr1_l1_limiting_amplifier_frontend:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L1`
- Category: RF and AFE Behavioral Macromodels
- Base function: Limiting amplifier front-end
- Domain: `voltage`
- Target artifact(s): `limiting_amplifier_frontend.va`, `tb_limiting_amplifier_frontend.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate all target artifacts: `limiting_amplifier_frontend.va`, `tb_limiting_amplifier_frontend.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `limiting_amplifier_frontend.va` must be co-located with the generated Spectre testbench.
- Include the generated DUT exactly with `ahdl_include "limiting_amplifier_frontend.va"` in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

- `limiting_amplifier_frontend.va` declares module `limiting_amplifier_frontend` with positional ports: `clk`, `rst`, `vin`, `out`, `metric`.

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

Public schedule source: `tb_limiting_amplifier_frontend.scs`.

```spectre
Vclk (clk 0) vsource type=pulse val0=0 val1=0.9 period=2n width=1n rise=50p fall=50p
Vrst (rst 0) vsource type=pwl wave=[0 0.9 2n 0.9 2.1n 0 80n 0]
Vvin (vin 0) vsource type=pwl wave=[0 0.45 7.9n 0.45 8n 0.50 21.9n 0.50 22n 0.78 43.9n 0.78 44n 0.18 63.9n 0.18 64n 0.56 80n 0.56]
```

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "limiting_amplifier_frontend.va"

XDUT (clk rst vin out metric) limiting_amplifier_frontend

tran tran stop=80n maxstep=0.5n
save clk rst vin out metric
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `small_input_gain_preserved`
- `large_input_limited_high_low`
- `limiting_metric_asserted`

## Public Behavioral Targets

- Treat vin around 0.45 V common mode and preserve signal polarity around that common mode.
- For small input excursions, apply gain around common mode.
- For large positive or negative excursions, limit/compress output toward bounded high/low levels instead of continuing linearly.
- Assert metric high only when limiting/compression is active.
- Keep out in the 0-0.9 V range and avoid hard digital switching for small signals.

## Output Contract

Return exactly these source artifacts:

- `limiting_amplifier_frontend.va`
- `tb_limiting_amplifier_frontend.scs`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### Limiting amplifier front-end (end-to-end)

Write both the Verilog-A behavioral module and a Spectre transient testbench.

Behavioral intent:

Normalize AFE input amplitude with a limiting amplifier that preserves polarity and asserts a limiting status metric.

Module name: `limiting_amplifier_frontend`.
Domain: pure voltage-domain behavioral Verilog-A.
Do not use current contributions, transistor-level devices, AC/noise analysis,
or KCL/KVL solving assumptions.

This is a voltage-domain RF/AFE behavioral macromodel task. Model observable gain, compression, LO polarity, RSSI, limiting, AGC, or I/Q baseband behavior with event-driven voltage states. Do not implement transistor RF physics, S-parameters, current-domain loads, communication modem algorithms, or full link-level decoding.

Public port contract:

```verilog
module limiting_amplifier_frontend(clk, rst, vin, out, metric);
input clk, rst, vin;
output out, metric;
electrical clk, rst, vin, out, metric;
```

Signal contract:

clk and rst are voltage-coded logic signals. vin is the receiver front-end voltage around 0.45 V common mode. out is a bounded limiting-amplifier output that preserves polarity. metric marks limiting operation.

Saved waveform columns:

```text
clk rst vin out metric
```

Public transient contract:

```spectre
tran tran stop=80n maxstep=0.5n
```
