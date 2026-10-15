# Task: vbr1_l2_iq_downconversion_chain:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L2`
- Category: RF and AFE Behavioral Macromodels
- Base function: I/Q downconversion chain
- Domain: `voltage`
- Target artifact(s): `iq_downconversion_chain.va`, `tb_iq_downconversion_chain.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## L2 Background And Claim Boundary

This Level-2 row is a behavioral composition/flow task for I/Q downconversion chain. It should expose intermediate state, multi-stage behavior, or a closed-loop relation through the public observables below.
Stay within the listed voltage-domain/event-driven contract. Do not use transistor-level devices, current-domain loads, AC/noise analysis, S-parameters, or hidden checker logic unless the public contract explicitly lists them.
Paper-facing claims for this row are limited to the public behavior checks below; do not broaden the task into full silicon implementation, layout, device physics, or unlisted performance metrics.

## Form-Specific Requirements

- Generate all target artifacts: `iq_downconversion_chain.va`, `tb_iq_downconversion_chain.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `iq_downconversion_chain.va` must be co-located with the generated Spectre testbench.
- Include the generated DUT exactly with `ahdl_include "iq_downconversion_chain.va"` in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

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

Implement the chain as a visible receiver-style behavioral flow:

1. Quadrature LO/state stage:
   - Advance a four-phase quadrature sequence on the public `clk`.
   - Expose phase on `phase_mon`.
   - Expose voltage-coded LO polarity on `lo_i` and `lo_q`.
   - I and Q must be distinct quadrature phases, not two copies of the same
     waveform.

2. Mixer stage:
   - Treat `vin` as an RF/envelope input around 0.45 V common mode.
   - Drive `mix_i` and `mix_q` as bounded mixer products using the I/Q LO
     polarity.

3. Baseband output stage:
   - Drive `out` from the I-path baseband response and `metric` from the Q-path
     baseband response.
   - `out` and `metric` should follow the corresponding mixer paths while
     remaining bounded in the 0 V to 0.9 V signal range.
   - When `vin` returns to common mode, both baseband observables should return
     near common mode.

Concrete public implementation guidance:

- Use a four-state public LO sequence advanced by rising `clk` edges after
  reset. A suitable voltage-coded truth table is:

```text
phase  phase_mon  lo_i  lo_q  meaning
0      0.0 V      high  mid   +I
1      0.3 V      mid   high  +Q
2      0.6 V      low   mid   -I
3      0.9 V      mid   low   -Q
```

- Use 0.45 V as the common-mode mid level. A practical encoding is high around
  0.85 V, mid around 0.45 V, and low around 0.05 V.
- Compute `base = vin - 0.45`. For positive I/Q phases, the corresponding
  mixer output should move above 0.45 V when `vin` is above common mode; for
  negative phases it should move below 0.45 V. Keep mixer outputs bounded in
  the 0 V to 0.9 V range.
- Drive `out` from the I-path baseband state and `metric` from the Q-path
  baseband state. They may be simple first-order responses to `mix_i` and
  `mix_q`, but they must remain distinguishable over the public four-phase
  schedule.

## Output Contract

Return exactly these source artifacts:

- `iq_downconversion_chain.va`
- `tb_iq_downconversion_chain.scs`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### I/Q downconversion chain (end-to-end)

Write both the Verilog-A behavioral module and a Spectre transient testbench.

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
