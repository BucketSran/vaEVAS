# Task: vbr1_l2_gain_extraction_convergence_measurement_flow:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L2`
- Category: Measurement Instrumentation Flows
- Base function: Dithered differential gain extraction flow
- Domain: `voltage`
- Target artifact(s): `dither_adder.va`, `gain_amp_fixed.va`, `lfsr.va`, `tb_gain_extraction_ref.scs`, `vin_src.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## L2 Background And Claim Boundary

This Level-2 row is a reusable measurement/stimulus support flow for Dithered differential gain extraction flow. It is certified as release content but remains outside the core circuit score denominator.
Stay within the listed voltage-domain/event-driven contract. Do not use transistor-level devices, current-domain loads, AC/noise analysis, S-parameters, or hidden checker logic unless the public contract explicitly lists them.
Paper-facing claims for this row are limited to support-flow behavior and must be reported separately from core analog/mixed-signal circuit-function coverage.

## Form-Specific Requirements

- Generate all target artifacts: `dither_adder.va`, `gain_amp_fixed.va`, `lfsr.va`, `tb_gain_extraction_ref.scs`, `vin_src.va`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `dither_adder.va`, `gain_amp_fixed.va`, `lfsr.va`, `vin_src.va` must be co-located with the generated Spectre testbench.
- Include each generated Verilog-A file exactly with a matching `ahdl_include "<file>.va"` line in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

- `dither_adder.va` declares module `dither_adder` with positional ports: `VRES_P`, `VRES_N`, `DPN`, `VOUT_P`, `VOUT_N`.
- `gain_amp_fixed.va` declares module `gain_amp_fixed` with positional ports: `VIN_P`, `VIN_N`, `VOUT_P`, `VOUT_N`.
- `lfsr.va` declares module `lfsr` with positional ports: `DPN`, `VDD`, `VSS`, `CLK`, `EN`, `RSTB`.
- `vin_src.va` declares module `vin_src` with positional ports: `CLK`, `RST_N`, `VOUT_P`, `VOUT_N`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=20u maxstep=8n
```

The release harness expects these exact public scalar observables:

- `vinp`
- `vinn`
- `vamp_p`
- `vamp_n`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `vdd`
- `vss`
- `clk`
- `rst_n`
- `en`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "dither_adder.va"
ahdl_include "gain_amp_fixed.va"
ahdl_include "lfsr.va"
ahdl_include "vin_src.va"

Vvdd (vdd 0) vsource dc=vdd
Vvss (vss 0) vsource dc=0

IVIN (clk rst_n vinp vinn) vin_src vdd=vdd vth=0.45 ampl=0.02 freq=fin sigma=VIN_NOISE SEED=0
ILFSR (dpn vdd vss clk en rst_n) lfsr seed=42
IDITH (vinp vinn dpn vdin_p vdin_n) dither_adder vdd=vdd vth=0.45 DITHER_AMP=DITHER_AMP
IAMP (vdin_p vdin_n vamp_p vamp_n) gain_amp_fixed vdd=vdd ACTUAL_GAIN=ACTUAL_GAIN

tran tran stop=20u maxstep=8n
save vinp vinn vamp_p vamp_n
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `gain_amplification_present`
- `differential_gain_above_threshold`

## Public L2 Behavior Contract

This support row is a dithered differential gain extraction flow. It must expose
the generated input pair and the amplified output pair:

1. Source and dither:
   - Generate a deterministic voltage-domain differential input pair
     `vinp/vinn`.
   - Apply a repeatable dither or PRBS-like perturbation so the measurement is
     not based on one static sample.

2. Fixed-gain path:
   - Drive `vamp_p/vamp_n` as the amplified differential output pair.
   - Keep common-mode and signal levels bounded in the public voltage domain.

3. Measurement relation:
   - The output differential amplitude should be visibly larger than the input
     differential amplitude over the saved transient.
   - The gain relation should be consistent across the dithered samples rather
     than a one-time spike.

The expected public relation is: deterministic differential input plus dither
-> amplified differential output with gain above the public threshold.

## Output Contract

Return exactly these source artifacts:

- `dither_adder.va`
- `gain_amp_fixed.va`
- `lfsr.va`
- `tb_gain_extraction_ref.scs`
- `vin_src.va`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

Write a minimal voltage-domain gain extraction smoke system and one EVAS-compatible Spectre testbench.

# Task: gain_extraction_smoke

## Objective

Create a dither-based gain extraction signal path whose output differential swing is measurably
larger than the input differential swing. The checker measures waveform statistics, not an internal
estimator code.

## Required Verilog-A Modules

Return these Verilog-A modules:

1. `vin_src`
   - Ports: `clk`, `rst_n`, `vinp`, `vinn`
   - Generates a small differential voltage stimulus after reset.
2. `lfsr`
   - Ports: `dpn`, `vdd`, `vss`, `clk`, `en`, `rst_n`
   - Produces a 1-bit pseudo-random dither sign signal on `dpn`.
3. `dither_adder`
   - Ports: `vinp`, `vinn`, `dpn`, `vdin_p`, `vdin_n`
   - Adds `+/-DITHER_AMP` to the differential input according to `dpn`.
4. `gain_amp_fixed`
   - Ports: `vdin_p`, `vdin_n`, `vamp_p`, `vamp_n`
   - Applies a configurable differential gain.

Do not create a `gain_estimator` module for this task; the EVAS checker estimates gain from saved
waveforms.

## Behavioral Contract

- Use pure voltage-domain Verilog-A only.
- Use `@(cross(...))` for clocked state updates.
- Use `transition(...)` for digital-like outputs.
- `gain_amp_fixed` should support parameter `ACTUAL_GAIN`.
- `dither_adder` should support parameter `DITHER_AMP`.
- `vin_src` should support enough parameterization to generate a small clocked differential input stimulus.
- The saved waveforms must satisfy:
  - `std(vamp_p - vamp_n) / std(vinp - vinn) > 4.0`
  - `std(vamp_p - vamp_n) > std(vinp - vinn)`

## Testbench Contract

- Use a 0.9 V supply and 0 V reference.
- Drive a 50 MHz-class clock, active-low reset, and enable signal.
- Instantiate `vin_src`, `lfsr`, `dither_adder`, and `gain_amp_fixed` as a connected signal path.
- Use `ACTUAL_GAIN=8.64` and `DITHER_AMP=0.014063` or equivalent parameters that produce clear gain separation.
- Save these exact scalar names: `vinp`, `vinn`, `vamp_p`, `vamp_n`.
