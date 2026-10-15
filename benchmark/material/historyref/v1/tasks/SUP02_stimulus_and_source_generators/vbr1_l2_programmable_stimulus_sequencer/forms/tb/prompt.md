# Task: vbr1_l2_programmable_stimulus_sequencer:tb

## Release Task Contract

- Form: `tb`
- Level: `L2`
- Category: Stimulus and Source Generators
- Base function: Programmable stimulus sequencer
- Domain: `voltage`
- Target artifact(s): `tb_programmable_stimulus_sequencer.scs`
- Supplied/reference support artifact(s): `programmable_stimulus_sequencer.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## L2 Background And Claim Boundary

This Level-2 row is a reusable measurement/stimulus support flow for Programmable stimulus sequencer. It is certified as release content but remains outside the core circuit score denominator.
Stay within the listed voltage-domain/event-driven contract. Do not use transistor-level devices, current-domain loads, AC/noise analysis, S-parameters, or hidden checker logic unless the public contract explicitly lists them.
Paper-facing claims for this row are limited to support-flow behavior and must be reported separately from core analog/mixed-signal circuit-function coverage.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `programmable_stimulus_sequencer.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "programmable_stimulus_sequencer.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `programmable_stimulus_sequencer.va` declares module `programmable_stimulus_sequencer` with positional ports: `clk`, `rst`, `mode`, `gate`, `out`, `metric`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=90n maxstep=0.25n
```

The release harness expects these exact public scalar observables:

- `clk`
- `rst`
- `mode`
- `gate`
- `out`
- `metric`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `clk`
- `rst`
- `mode`
- `gate`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "programmable_stimulus_sequencer.va"

XDUT (clk rst mode gate out metric) programmable_stimulus_sequencer

tran tran stop=90n maxstep=0.25n
save clk rst mode gate out metric
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `ramp_segment_monotonic`
- `swept_chirp_segment_frequency_increases`
- `burst_prbs_gate_schedule`
- `mode_switch_continuity`

## Public L2 Behavior Contract

This support row is a programmable stimulus sequencer. The testbench must
exercise all public modes:

1. Drive `mode` low for a ramp segment.
2. Step `mode` to midscale for a swept sine or chirp segment.
3. Step `mode` high for a burst/PRBS segment.
4. Toggle `gate` during the high-mode segment so enabled and disabled burst
   intervals are both visible.
5. Save `clk rst mode gate out metric` exactly.

The expected public relation is: `out` is monotonic during ramp mode, has
increasing effective frequency during chirp mode, follows the burst gate during
high mode, and avoids large discontinuities at mode switches. Do not generate
checker logic.

## Output Contract

Return exactly one source artifact named `tb_programmable_stimulus_sequencer.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

### Programmable stimulus sequencer (tb-generation)

Write a Spectre transient testbench for the described behavioral Verilog-A module.

Behavioral intent:

Generate a programmable ramp, swept/chirp sine, and gated burst/PRBS stimulus schedule.

Module name: `programmable_stimulus_sequencer`.
Domain: pure voltage-domain behavioral Verilog-A.
Do not use current contributions, transistor-level devices, AC/noise analysis,
or KCL/KVL solving assumptions.

Public port contract:

```verilog
module programmable_stimulus_sequencer(clk, rst, mode, gate, out, metric);
input clk, rst, mode, gate;
output out, metric;
electrical clk, rst, mode, gate, out, metric;
```

Signal contract:

clk and rst are voltage-coded logic signals, low=0 V and high=0.9 V with threshold 0.45 V. mode selects ramp, sine, or burst/PRBS behavior. gate enables the burst segment. out is the generated stimulus waveform. metric is a voltage-coded segment-status observable.

Saved waveform columns:

```text
clk rst mode gate out metric
```

Public transient contract:

```spectre
tran tran stop=90n maxstep=0.25n
```
