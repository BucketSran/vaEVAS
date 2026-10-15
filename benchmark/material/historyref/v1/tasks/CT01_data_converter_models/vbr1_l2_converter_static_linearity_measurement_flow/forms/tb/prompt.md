# Task: vbr1_l2_converter_static_linearity_measurement_flow:tb

## Release Task Contract

- Form: `tb`
- Level: `L2`
- Category: Data Converter Models
- Base function: Converter static linearity measurement flow
- Domain: `voltage`
- Target artifact(s): `tb_converter_static_linearity_measurement_flow.scs`
- Supplied/reference support artifact(s): `converter_static_linearity_measurement_flow.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## L2 Background And Claim Boundary

This Level-2 row is a behavioral composition/flow task for Converter static linearity measurement flow. It should expose intermediate state, multi-stage behavior, or a closed-loop relation through the public observables below.
Stay within the listed voltage-domain/event-driven contract. Do not use transistor-level devices, current-domain loads, AC/noise analysis, S-parameters, or hidden checker logic unless the public contract explicitly lists them.
Paper-facing claims for this row are limited to the public behavior checks below; do not broaden the task into full silicon implementation, layout, device physics, or unlisted performance metrics.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `converter_static_linearity_measurement_flow.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "converter_static_linearity_measurement_flow.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `converter_static_linearity_measurement_flow.va` declares module `converter_static_linearity_measurement_flow` with positional ports: `clk`, `rst`, `vin`, `code`, `recon`, `dnl`, `inl`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=96n maxstep=250p
```

The release harness expects these exact public scalar observables:

- `clk`
- `rst`
- `vin`
- `code`
- `recon`
- `dnl`
- `inl`

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
ahdl_include "converter_static_linearity_measurement_flow.va"

XDUT (clk rst vin code recon dnl inl) converter_static_linearity_measurement_flow

tran tran stop=96n maxstep=250p
save clk rst vin code recon dnl inl
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `ramp_code_coverage`
- `monotonic_reconstruction`
- `nonuniform_dnl_metric`
- `inl_metric_matches_reconstruction_error`
- `dnl_metric_matches_step_error`

## Public L2 Behavior Contract

This row is a converter characterization flow, not just a standalone ADC or
DAC. The testbench must expose four linked public stages:

1. Ramp sampling and quantization:
   - Release reset before the useful samples.
   - Drive a slow monotonic `vin` ramp from the low end toward the high end of
     the 0 V to 0.9 V signal range.
   - Provide enough rising clock edges for the supplied DUT to visit all 16
     4-bit codes.

2. Non-ideal reconstruction:
   - The saved `recon` waveform should show a monotonic but non-uniform
     reconstruction from the observed code sequence.

3. DNL-like metric:
   - The saved `dnl` waveform should expose non-zero step-error behavior for
     non-uniform adjacent code steps.

4. INL-like metric:
   - The saved `inl` waveform should track accumulated reconstruction error
     against the ramp history.

Use a 0 V/0.9 V clock, a reset pulse that deasserts before the ramp, and save
exactly `clk rst vin code recon dnl inl`. Do not generate checker logic; the
external evaluator computes coverage, monotonicity, and metric consistency from
these saved waveforms.

## Output Contract

Return exactly one source artifact named `tb_converter_static_linearity_measurement_flow.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Converter static linearity measurement flow (testbench generation)

Write a Spectre transient testbench for a supplied voltage-domain
static-linearity characterization flow for a 4-bit converter pair.

The supplied DUT samples an input ramp, quantizes it to a 4-bit code, reconstructs a deliberately
non-ideal DAC voltage, and uses a lightweight measurement stage to derive DNL/INL-like
metric voltages from the observed reconstruction. This is a converter measurement flow:
the checker observes code coverage, monotonic reconstruction, non-uniform code steps, and
metric consistency against the measured code/reconstruction history.

Public port contract:

```verilog
module converter_static_linearity_measurement_flow(clk, rst, vin, code, recon, dnl, inl);
input clk, rst, vin;
output code, recon, dnl, inl;
electrical clk, rst, vin, code, recon, dnl, inl;
```

Signal contract:

All logic controls are voltage-coded, low=0 V and high=0.9 V with threshold 0.45 V. The design remains pure voltage-domain behavioral Verilog-A: no current contributions, transistor devices, AC/noise analysis, or KCL/KVL solving assumptions.

Saved waveform columns:

```text
clk rst vin code recon dnl inl
```

Public transient contract:

```spectre
tran tran stop=96n maxstep=0.25n
```
