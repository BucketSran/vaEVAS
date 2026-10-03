# Task: vbr1_l1_programmable_gain_amplifier:tb

## Release Task Contract

- Form: `tb`
- Level: `L1`
- Category: Baseband Signal Conditioning
- Base function: Programmable gain amplifier
- Domain: `voltage`
- Target artifact(s): `tb_programmable_gain_amplifier.scs`
- Supplied/reference support artifact(s): `programmable_gain_amplifier.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `programmable_gain_amplifier.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "programmable_gain_amplifier.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `programmable_gain_amplifier.va` declares module `programmable_gain_amplifier` with positional ports: `clk`, `rst`, `gain_sel`, `vin`, `out`, `metric`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=90n maxstep=250p
```

The release harness expects these exact public scalar observables:

- `clk`
- `rst`
- `gain_sel`
- `vin`
- `out`
- `metric`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `clk`
- `rst`
- `gain_sel`
- `vin`

## Public Stimulus Schedule Contract

Use this exact public source schedule in generated Spectre testbenches. This schedule is part of the public testbench contract; it is not hidden checker logic.

Public schedule source: `tb_programmable_gain_amplifier.scs`.

```spectre
Vclk (clk 0) vsource type=pulse val0=0 val1=0.9 period=8n width=4n delay=2n rise=80p fall=80p
Vrst (rst 0) vsource type=pwl wave=[0 0.9 2n 0.9 2.1n 0 90n 0]
Vgain (gain_sel 0) vsource type=pwl wave=[0 0 18n 0 20n 0.9 48n 0.9 50n 0 70n 0 72n 0.9 90n 0.9]
Vvin (vin 0) vsource type=pwl wave=[0 0.45 8n 0.60 16n 0.30 24n 0.72 34n 0.72 36n 0.20 46n 0.20 54n 0.55 68n 0.55 70n 0.85 83n 0.85 86n 0.10 90n 0.45]
```

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "programmable_gain_amplifier.va"

XDUT (clk rst gain_sel vin out metric) programmable_gain_amplifier

tran tran stop=90n maxstep=250p
save clk rst gain_sel vin out metric
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `gain_select_changes_slope`
- `sampled_gain_holds_between_clock_edges`
- `common_mode_is_preserved`
- `rail_clamps_with_clip_metric`
- `reset_returns_to_unity_gain`

## Output Contract

Return exactly one source artifact named `tb_programmable_gain_amplifier.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

Write a pure voltage-domain Verilog-A programmable gain amplifier.

The gain code is sampled on rising `clk` edges:
- reset selects unity gain and returns the output to the common-mode voltage.
- `gain_sel=0` selects a low gain.
- `gain_sel=1` selects a high gain.
- The output is `vcm + gain * (V(vin)-vcm)` with rail clamps.
- `metric` is high when the unclamped target clips to either rail.
- The testbench should exercise reset, low-gain unclipped operation, high-gain positive clipping, high-gain negative clipping, and a later high-gain clipped segment after a gain selection change.

Module name: `programmable_gain_amplifier`.
Domain: pure voltage-domain behavioral Verilog-A.
Do not use current contributions, transistor-level devices, AC/noise analysis, or KCL/KVL solving assumptions.

Public port contract:

```verilog
module programmable_gain_amplifier(clk, rst, gain_sel, vin, out, metric);
```

Saved waveform columns:

```text
clk rst gain_sel vin out metric
```

Public transient contract:

```spectre
tran tran stop=90n maxstep=250p
```
