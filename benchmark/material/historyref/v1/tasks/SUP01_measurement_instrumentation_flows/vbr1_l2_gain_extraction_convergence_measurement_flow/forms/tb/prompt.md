# Task: vbr1_l2_gain_extraction_convergence_measurement_flow:tb

## Release Task Contract

- Form: `tb`
- Level: `L2`
- Category: Measurement Instrumentation Flows
- Base function: Dithered differential gain extraction flow
- Domain: `voltage`
- Target artifact(s): `tb_gain_extraction_ref.scs`
- Supplied/reference support artifact(s): `dither_adder.va`, `gain_amp_fixed.va`, `lfsr.va`, `vin_src.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## L2 Background And Claim Boundary

This Level-2 row is a reusable measurement/stimulus support flow for Dithered differential gain extraction flow. It is certified as release content but remains outside the core circuit score denominator.
Stay within the listed voltage-domain/event-driven contract. Do not use transistor-level devices, current-domain loads, AC/noise analysis, S-parameters, or hidden checker logic unless the public contract explicitly lists them.
Paper-facing claims for this row are limited to support-flow behavior and must be reported separately from core analog/mixed-signal circuit-function coverage.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `dither_adder.va`, `gain_amp_fixed.va`, `lfsr.va`, `vin_src.va` will be co-located with the generated testbench by the evaluation harness.
- Include each supplied Verilog-A support file exactly with a matching `ahdl_include "<file>.va"` line in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

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

This support row is a dithered differential gain extraction flow. The testbench
must expose the source, dither, and amplified output relation:

1. Include and instantiate the supplied public source, dither, and fixed-gain
   support modules.
2. Drive the public clock/reset/enable signals so deterministic dithered
   samples occur after reset.
3. Save `vinp vinn vamp_p vamp_n` exactly.
4. Run long enough for multiple dithered samples, not only one static point.

The expected public relation is that the differential output amplitude
`vamp_p - vamp_n` is consistently larger than the input differential amplitude
`vinp - vinn`. Do not generate checker logic.

## Output Contract

Return exactly one source artifact named `tb_gain_extraction_ref.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Dithered differential gain extraction flow Testbench Companion

Write a Spectre transient testbench for the `Dithered differential gain extraction flow` behavioral
Verilog-A release task. This is the testbench-generation companion for an
already materialized end-to-end task.

The testbench should instantiate the same behavioral DUT or system module used
by the corresponding end-to-end form, drive the public transient scenario, save
the observable waveform or metric signals, and preserve the EVAS/Spectre
validation contract.

Domain: pure voltage-domain behavioral Verilog-A.

Public requirements:

- include a transient `tran` analysis
- save the public observables needed by the public behavior checks
- include or instantiate the Verilog-A behavioral module under test
- satisfy the named behavior checks using only public waveforms and side outputs
- avoid transistor-level devices, AC/noise analysis, and current-domain
  solver assumptions
