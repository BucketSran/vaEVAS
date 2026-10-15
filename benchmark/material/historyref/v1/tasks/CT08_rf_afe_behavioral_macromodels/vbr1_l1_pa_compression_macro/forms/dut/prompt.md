# Task: vbr1_l1_pa_compression_macro:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: RF and AFE Behavioral Macromodels
- Base function: PA compression macro
- Domain: `voltage`
- Target artifact(s): `pa_compression_macro.va`
- Supplied/reference support artifact(s): `tb_pa_compression_macro.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

## Public Verilog-A Interface

- `pa_compression_macro.va` declares module `pa_compression_macro` with positional ports: `clk`, `rst`, `vin`, `out`, `metric`.

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

- `pa_gain_above_unity`
- `pa_large_signal_compression`
- `pa_output_limit_metric`

## Public Behavioral Targets

- Treat vin as PA drive around 0.45 V common mode.
- Moderate drive should show gain above unity.
- Large drive should compress toward bounded high/low output limits rather than continuing linear gain.
- metric should rise when the output is near compression or limiting.
- Keep out and metric within the 0-0.9 V voltage-domain range.

## Output Contract

Return exactly one source artifact named `pa_compression_macro.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### PA compression macro (spec-to-va)

Write the Verilog-A behavioral module only.

Behavioral intent:

Model a power-amplifier behavioral macro with high gain at moderate drive and compressed output near large-signal limits.

Module name: `pa_compression_macro`.
Domain: pure voltage-domain behavioral Verilog-A.
Do not use current contributions, transistor-level devices, AC/noise analysis,
or KCL/KVL solving assumptions.

This is a voltage-domain RF/AFE behavioral macromodel task. Model observable gain, compression, LO polarity, RSSI, limiting, AGC, or I/Q baseband behavior with event-driven voltage states. Do not implement transistor RF physics, S-parameters, current-domain loads, communication modem algorithms, or full link-level decoding.

Public port contract:

```verilog
module pa_compression_macro(clk, rst, vin, out, metric);
input clk, rst, vin;
output out, metric;
electrical clk, rst, vin, out, metric;
```

Signal contract:

clk and rst are voltage-coded logic signals. vin is the PA drive voltage around 0.45 V common mode. out is the amplified output with large-signal compression and rail limits. metric marks compression/limit operation.

Saved waveform columns:

```text
clk rst vin out metric
```

Public transient contract:

```spectre
tran tran stop=80n maxstep=0.5n
```
