# Task: vbr1_l2_iq_downconversion_chain:tb

## Release Task Contract

- Form: `tb`
- Level: `L2`
- Category: RF and AFE Behavioral Macromodels
- Base function: I/Q downconversion chain
- Domain: `voltage`
- Target artifact(s): `tb_iq_downconversion_chain.scs`
- Supplied/reference support artifact(s): `iq_downconversion_chain.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## L2 Background And Claim Boundary

This Level-2 row is a behavioral composition/flow task for I/Q downconversion chain. It should expose intermediate state, multi-stage behavior, or a closed-loop relation through the public observables below.
Stay within the listed voltage-domain/event-driven contract. Do not use transistor-level devices, current-domain loads, AC/noise analysis, S-parameters, or hidden checker logic unless the public contract explicitly lists them.
Paper-facing claims for this row are limited to the public behavior checks below; do not broaden the task into full silicon implementation, layout, device physics, or unlisted performance metrics.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `iq_downconversion_chain.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "iq_downconversion_chain.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `iq_downconversion_chain.va` declares module `iq_downconversion_chain` with positional ports: `clk`, `rst`, `vin`, `out`, `metric`, `lo_i`, `lo_q`, `mix_i`, `mix_q`, `phase_mon`.

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
- `lo_i`
- `lo_q`
- `mix_i`
- `mix_q`
- `phase_mon`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `clk`
- `rst`
- `vin`

## Public Stimulus Schedule Contract

Use this exact public source schedule in generated Spectre testbenches. This schedule is part of the public testbench contract; it is not hidden checker logic.

Public schedule source: `tb_iq_downconversion_chain.scs`.

```spectre
Vclk (clk 0) vsource type=pulse val0=0 val1=0.9 period=2n width=1n rise=50p fall=50p
Vrst (rst 0) vsource type=pwl wave=[0 0.9 2n 0.9 2.1n 0 80n 0]
Vvin (vin 0) vsource type=pwl wave=[0 0.45 7.9n 0.45 8n 0.72 55.9n 0.72 56n 0.45 65.9n 0.45 66n 0.25 80n 0.25]
```

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "iq_downconversion_chain.va"

XDUT (clk rst vin out metric lo_i lo_q mix_i mix_q phase_mon) iq_downconversion_chain

tran tran stop=80n maxstep=0.5n
save clk rst vin out metric lo_i lo_q mix_i mix_q phase_mon
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `quadrature_iq_phase_sequence`
- `lo_iq_phase_monitors_are_visible`
- `mixer_outputs_track_lo_polarity_and_input`
- `i_and_q_outputs_are_distinct`
- `baseband_outputs_follow_mixer_paths`
- `common_mode_hold_when_input_centered`

## Public L2 Behavior Contract

The testbench must make the full I/Q chain visible:

1. Drive reset high initially, then release it before the RF input step.
2. Drive `vin` above, at, and below the 0.45 V common-mode level.
3. Save `phase_mon`, `lo_i`, `lo_q`, `mix_i`, `mix_q`, `out`, and `metric`.
4. The expected public relation is LO phase -> mixer polarity -> I/Q baseband
   outputs. Do not generate checker logic; the evaluator checks this relation
   from saved waveform columns.

## Output Contract

Return exactly one source artifact named `tb_iq_downconversion_chain.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### I/Q downconversion chain (tb-generation)

Write a Spectre transient testbench for the described behavioral Verilog-A module.

Behavioral intent:

Compose quadrature LO sequencing, two mixer paths, and baseband I/Q observables in a voltage-domain receiver chain.

Module name: `iq_downconversion_chain`.
Domain: pure voltage-domain behavioral Verilog-A.
Do not use current contributions, transistor-level devices, AC/noise analysis,
or KCL/KVL solving assumptions.

This is a voltage-domain RF/AFE behavioral macromodel task. Model observable gain, compression, LO polarity, RSSI, limiting, AGC, or I/Q baseband behavior with event-driven voltage states. Do not implement transistor RF physics, S-parameters, current-domain loads, communication modem algorithms, or full link-level decoding.

Public port contract:

```verilog
module iq_downconversion_chain(clk, rst, vin, out, metric, lo_i, lo_q, mix_i, mix_q, phase_mon);
input clk, rst, vin;
output out, metric, lo_i, lo_q, mix_i, mix_q, phase_mon;
electrical clk, rst, vin, out, metric, lo_i, lo_q, mix_i, mix_q, phase_mon;
```

Signal contract:

clk is the quadrature LO phase-advance clock and rst is voltage-coded reset. vin is the RF input envelope around 0.45 V common mode. phase_mon exposes the four-phase LO state, lo_i and lo_q expose voltage-coded I/Q LO polarity, mix_i and mix_q expose bounded mixer outputs, out is the I-path baseband observable, and metric is the Q-path baseband observable.

Saved waveform columns:

```text
clk rst vin out metric lo_i lo_q mix_i mix_q phase_mon
```

Public transient contract:

```spectre
tran tran stop=80n maxstep=0.5n
```
