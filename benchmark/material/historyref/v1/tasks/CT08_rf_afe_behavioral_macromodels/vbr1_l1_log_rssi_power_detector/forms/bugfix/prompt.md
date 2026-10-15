# Task: vbr1_l1_log_rssi_power_detector:bugfix

## Release Task Contract

- Form: `bugfix`
- Level: `L1`
- Category: RF and AFE Behavioral Macromodels
- Base function: Log/RSSI power detector
- Domain: `voltage`
- Target artifact(s): `dut_fixed.va`
- Supplied/reference support artifact(s): `dut_buggy.va`, `tb_log_rssi_power_detector.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Repair the supplied buggy Verilog-A artifact while preserving the public module interface and artifact boundary.
- Use the buggy source plus the public intended behavior below; do not change the companion testbench contract.

## Public Interface To Preserve

- `dut_buggy.va` declares module `log_rssi_power_detector` with positional ports: `clk`, `rst`, `vin`, `out`, `metric`.
- `dut_fixed.va` declares module `log_rssi_power_detector` with positional ports: `clk`, `rst`, `vin`, `out`, `metric`.

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

## Observed Mismatch Framing

The supplied buggy artifact violates one or more public behavior checks above under the release validation testbench.
Repair the observable behavior without renaming modules, changing ports, or weakening the public testbench contract.

## Output Contract

Return exactly one source artifact named `dut_fixed.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### Log/RSSI power detector (bugfix)

Repair the supplied buggy Verilog-A implementation using the public behavior checks and task description above. Treat the failing implementation as an observable mismatch; infer the repair from the source and public behavior rather than assuming a named root cause.

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
