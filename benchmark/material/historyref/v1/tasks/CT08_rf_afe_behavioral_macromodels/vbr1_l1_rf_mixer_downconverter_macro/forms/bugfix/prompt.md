# Task: vbr1_l1_rf_mixer_downconverter_macro:bugfix

## Release Task Contract

- Form: `bugfix`
- Level: `L1`
- Category: RF and AFE Behavioral Macromodels
- Base function: RF mixer/downconverter macro
- Domain: `voltage`
- Target artifact(s): `dut_fixed.va`
- Supplied/reference support artifact(s): `dut_buggy.va`, `tb_rf_mixer_downconverter_macro.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Repair the supplied buggy Verilog-A artifact while preserving the public module interface and artifact boundary.
- Use the buggy source plus the public intended behavior below; do not change the companion testbench contract.

## Public Interface To Preserve

- `dut_buggy.va` declares module `rf_mixer_downconverter_macro` with positional ports: `clk`, `rst`, `vin`, `out`, `metric`.
- `dut_fixed.va` declares module `rf_mixer_downconverter_macro` with positional ports: `clk`, `rst`, `vin`, `out`, `metric`.

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

- `lo_polarity_controls_conversion_sign`
- `conversion_gain_visible`
- `baseband_output_bounded`

## Public Behavioral Targets

- Treat clk as the LO-polarity waveform with a 0.45 V logic threshold.
- Convert the input envelope around 0.45 V common mode to baseband by flipping sign with LO polarity.
- Preserve output common mode near 0.45 V and keep out bounded.
- metric should indicate active conversion or LO polarity state.

## Observed Mismatch Framing

The supplied buggy artifact violates one or more public behavior checks above under the release validation testbench.
Repair the observable behavior without renaming modules, changing ports, or weakening the public testbench contract.

## Output Contract

Return exactly one source artifact named `dut_fixed.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### RF mixer/downconverter macro (bugfix)

Repair the supplied buggy Verilog-A implementation using the public behavior checks and task description above. Treat the failing implementation as an observable mismatch; infer the repair from the source and public behavior rather than assuming a named root cause.

Behavioral intent:

Model a voltage-domain RF mixer/downconverter where the LO polarity modulates the RF input around common mode into a baseband output.

Module name: `rf_mixer_downconverter_macro`.
Domain: pure voltage-domain behavioral Verilog-A.
Do not use current contributions, transistor-level devices, AC/noise analysis,
or KCL/KVL solving assumptions.

This is a voltage-domain RF/AFE behavioral macromodel task. Model observable gain, compression, LO polarity, RSSI, limiting, AGC, or I/Q baseband behavior with event-driven voltage states. Do not implement transistor RF physics, S-parameters, current-domain loads, communication modem algorithms, or full link-level decoding.

Public port contract:

```verilog
module rf_mixer_downconverter_macro(clk, rst, vin, out, metric);
input clk, rst, vin;
output out, metric;
electrical clk, rst, vin, out, metric;
```

Signal contract:

clk is the public LO-polarity waveform and rst is voltage-coded reset. vin is an RF input envelope around 0.45 V common mode. out is the LO-polarity-converted baseband voltage. metric marks active conversion.

Saved waveform columns:

```text
clk rst vin out metric
```

Public transient contract:

```spectre
tran tran stop=80n maxstep=0.5n
```
