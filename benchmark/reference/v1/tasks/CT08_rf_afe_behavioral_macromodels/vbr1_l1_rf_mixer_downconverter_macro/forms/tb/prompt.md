# Task: vbr1_l1_rf_mixer_downconverter_macro:tb

## Release Task Contract

- Form: `tb`
- Level: `L1`
- Category: RF and AFE Behavioral Macromodels
- Base function: RF mixer/downconverter macro
- Domain: `voltage`
- Target artifact(s): `tb_rf_mixer_downconverter_macro.scs`
- Supplied/reference support artifact(s): `rf_mixer_downconverter_macro.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `rf_mixer_downconverter_macro.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "rf_mixer_downconverter_macro.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `rf_mixer_downconverter_macro.va` declares module `rf_mixer_downconverter_macro` with positional ports: `clk`, `rst`, `vin`, `out`, `metric`.

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
ahdl_include "rf_mixer_downconverter_macro.va"

XDUT (clk rst vin out metric) rf_mixer_downconverter_macro

tran tran stop=80n maxstep=0.5n
save clk rst vin out metric
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `lo_polarity_controls_conversion_sign`
- `conversion_gain_visible`
- `baseband_output_bounded`

## Public Behavioral Targets

- Treat clk as the LO-polarity waveform with a 0.45 V logic threshold.
- Convert the input envelope around 0.45 V common mode to baseband by flipping sign with LO polarity.
- Preserve output common mode near 0.45 V and keep out bounded.
- metric should indicate active conversion or LO polarity state.

## Output Contract

Return exactly one source artifact named `tb_rf_mixer_downconverter_macro.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### RF mixer/downconverter macro (tb-generation)

Write a Spectre transient testbench for the described behavioral Verilog-A module.

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
