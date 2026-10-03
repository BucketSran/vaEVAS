# Task: vbr1_l1_lna_gain_compression_macro:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: RF and AFE Behavioral Macromodels
- Base function: LNA gain/compression macro
- Domain: `voltage`
- Target artifact(s): `lna_gain_compression_macro.va`
- Supplied/reference support artifact(s): `tb_lna_gain_compression_macro.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

## Public Verilog-A Interface

- `lna_gain_compression_macro.va` declares module `lna_gain_compression_macro` with positional ports: `clk`, `rst`, `vin`, `out`, `metric`.

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

- `small_signal_gain_present`
- `large_signal_compression_visible`
- `compressed_output_bounded`

## Public Behavioral Targets

- Treat vin around 0.45 V common mode; small-signal out should show gain greater than 1 around that common mode.
- For large drive, compress incremental gain and keep output bounded.
- Compression should be reasonably symmetric for positive and negative excursions.
- metric should be low or small in the linear region and high during compression.

## Output Contract

Return exactly one source artifact named `lna_gain_compression_macro.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### LNA gain/compression macro (spec-to-va)

Write the Verilog-A behavioral module only.

Behavioral intent:

Model an RF low-noise-amplifier front-end with small-signal gain, soft large-signal compression, and bounded output swing.

Module name: `lna_gain_compression_macro`.
Domain: pure voltage-domain behavioral Verilog-A.
Do not use current contributions, transistor-level devices, AC/noise analysis,
or KCL/KVL solving assumptions.

This is a voltage-domain RF/AFE behavioral macromodel task. Model observable gain, compression, LO polarity, RSSI, limiting, AGC, or I/Q baseband behavior with event-driven voltage states. Do not implement transistor RF physics, S-parameters, current-domain loads, communication modem algorithms, or full link-level decoding.

Public port contract:

```verilog
module lna_gain_compression_macro(clk, rst, vin, out, metric);
input clk, rst, vin;
output out, metric;
electrical clk, rst, vin, out, metric;
```

Signal contract:

clk and rst are voltage-coded logic signals. vin is an RF/AFE input envelope around 0.45 V common mode. out is the amplified voltage with soft large-signal compression. metric is high when compression is active.

Saved waveform columns:

```text
clk rst vin out metric
```

Public transient contract:

```spectre
tran tran stop=80n maxstep=0.5n
```
