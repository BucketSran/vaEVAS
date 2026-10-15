# Task: vbr1_l1_limiting_amplifier_frontend:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: RF and AFE Behavioral Macromodels
- Base function: Limiting amplifier front-end
- Domain: `voltage`
- Target artifact(s): `limiting_amplifier_frontend.va`
- Supplied/reference support artifact(s): `tb_limiting_amplifier_frontend.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

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

Return exactly one source artifact named `limiting_amplifier_frontend.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### Limiting amplifier front-end (spec-to-va)

Write the Verilog-A behavioral module only.

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
