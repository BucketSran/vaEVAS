# Task: vbr1_l1_log_rssi_power_detector:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: RF and AFE Behavioral Macromodels
- Base function: Log/RSSI power detector
- Domain: `voltage`
- Target artifact(s): `log_rssi_power_detector.va`
- Supplied/reference support artifact(s): `tb_log_rssi_power_detector.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

## Public Verilog-A Interface

- `log_rssi_power_detector.va` declares module `log_rssi_power_detector` with positional ports: `clk`, `rst`, `vin`, `out`, `metric`.

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

- `rssi_monotonic_with_envelope`
- `log_spacing_compresses_large_steps`
- `low_input_floor_bounded`

## Public Behavioral Targets

- Treat vin as an envelope around 0.45 V common mode and estimate amplitude as abs(vin - 0.45).
- Use a Spectre/EVAS-friendly compressed or piecewise approximation; do not rely on unsupported log10, round, integer casts, or digital Verilog.
- out should be monotonic with amplitude, but large-amplitude steps should be compressed rather than linear.
- Keep a low-input floor near the bottom of the RSSI range.
- metric should expose normalized envelope magnitude and remain bounded within 0-0.9 V.

## Output Contract

Return exactly one source artifact named `log_rssi_power_detector.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### Log/RSSI power detector (spec-to-va)

Write the Verilog-A behavioral module only.

Behavioral intent:

Convert received envelope magnitude into a monotonic logarithmic RSSI-style voltage code.

Module name: `log_rssi_power_detector`.
Domain: pure voltage-domain behavioral Verilog-A.
Do not use current contributions, transistor-level devices, AC/noise analysis,
or KCL/KVL solving assumptions.

This is a voltage-domain RF/AFE behavioral macromodel task. Model observable gain, compression, LO polarity, RSSI, limiting, AGC, or I/Q baseband behavior with event-driven voltage states. Do not implement transistor RF physics, S-parameters, current-domain loads, communication modem algorithms, or full link-level decoding.

Public port contract:

```verilog
module log_rssi_power_detector(clk, rst, vin, out, metric);
input clk, rst, vin;
output out, metric;
electrical clk, rst, vin, out, metric;
```

Signal contract:

clk and rst are voltage-coded logic signals. vin is the received signal envelope around 0.45 V common mode. out is a monotonic logarithmic RSSI voltage code. metric exposes normalized envelope magnitude.

Saved waveform columns:

```text
clk rst vin out metric
```

Public transient contract:

```spectre
tran tran stop=80n maxstep=0.5n
```
