# Task: vbr1_l1_lna_gain_compression_macro:tb

## Release Task Contract

- Form: `tb`
- Level: `L1`
- Category: RF and AFE Behavioral Macromodels
- Base function: LNA gain/compression macro
- Domain: `voltage`
- Target artifact(s): `tb_lna_gain_compression_macro.scs`
- Supplied/reference support artifact(s): `lna_gain_compression_macro.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `lna_gain_compression_macro.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "lna_gain_compression_macro.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

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

Public stimulus/source nodes visible in the reference harness include:

- `clk`
- `rst`
- `vin`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "lna_gain_compression_macro.va"

XDUT (clk rst vin out metric) lna_gain_compression_macro

tran tran stop=80n maxstep=0.5n
save clk rst vin out metric
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

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

Return exactly one source artifact named `tb_lna_gain_compression_macro.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### LNA gain/compression macro (tb-generation)

Write a Spectre transient testbench for the described behavioral Verilog-A module.

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
