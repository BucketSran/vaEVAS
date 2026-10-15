# Task: vbr1_l2_converter_static_linearity_measurement_flow:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L2`
- Category: Data Converter Models
- Base function: Converter static linearity measurement flow
- Domain: `voltage`
- Target artifact(s): `converter_static_linearity_measurement_flow.va`, `tb_converter_static_linearity_measurement_flow.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## L2 Background And Claim Boundary

This Level-2 row is a behavioral composition/flow task for Converter static linearity measurement flow. It should expose intermediate state, multi-stage behavior, or a closed-loop relation through the public observables below.
Stay within the listed voltage-domain/event-driven contract. Do not use transistor-level devices, current-domain loads, AC/noise analysis, S-parameters, or hidden checker logic unless the public contract explicitly lists them.
Paper-facing claims for this row are limited to the public behavior checks below; do not broaden the task into full silicon implementation, layout, device physics, or unlisted performance metrics.

## Form-Specific Requirements

- Generate all target artifacts: `converter_static_linearity_measurement_flow.va`, `tb_converter_static_linearity_measurement_flow.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `converter_static_linearity_measurement_flow.va` must be co-located with the generated Spectre testbench.
- Include the generated DUT exactly with `ahdl_include "converter_static_linearity_measurement_flow.va"` in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

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
DAC. The public behavior must expose four linked stages:

1. Ramp sampling and quantization:
   - After reset releases, sample a slow monotonic `vin` ramp on rising clock
     edges.
   - Drive `code` as a voltage-coded 4-bit result that covers the full useful
     code range during the ramp.

2. Non-ideal reconstruction:
   - Drive `recon` from the measured code as a monotonic but deliberately
     non-uniform DAC reconstruction.
   - Adjacent code steps should not all be identical; the task is meant to
     expose static-linearity error, not an ideal converter.

3. DNL-like metric:
   - Drive `dnl` from the observed reconstruction step error between adjacent
     sampled codes.
   - Keep the metric bounded in the public voltage range so it can be compared
     as a waveform.

4. INL-like metric:
   - Drive `inl` from the accumulated reconstruction error relative to an
     ideal monotonic transfer.
   - The metric should track the reconstruction history rather than a constant
     placeholder.

Use a public transient schedule with a 0 V to 0.9 V ramp, reset released before
the useful ramp samples, and enough rising clock edges to visit all 16 4-bit
codes. Save exactly `clk rst vin code recon dnl inl`.

## Output Contract

Return exactly these source artifacts:

- `converter_static_linearity_measurement_flow.va`
- `tb_converter_static_linearity_measurement_flow.scs`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Converter static linearity measurement flow (end-to-end)

Build a voltage-domain static-linearity characterization flow for a 4-bit converter pair.

The circuit samples an input ramp, quantizes it to a 4-bit code, reconstructs a deliberately
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
