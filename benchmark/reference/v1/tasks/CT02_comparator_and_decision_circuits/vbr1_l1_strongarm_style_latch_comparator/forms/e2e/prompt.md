# Task: vbr1_l1_strongarm_style_latch_comparator:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L1`
- Category: Comparator and Decision Circuits
- Base function: StrongARM-style latch comparator
- Domain: `voltage`
- Target artifact(s): `cmp_strongarm.va`, `tb_cmp_strongarm_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate all target artifacts: `cmp_strongarm.va`, `tb_cmp_strongarm_ref.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `cmp_strongarm.va` must be co-located with the generated Spectre testbench.
- Include the generated DUT exactly with `ahdl_include "cmp_strongarm.va"` in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

- `cmp_strongarm.va` declares module `cmp_strongarm` with positional ports: `CLK`, `VINN`, `VINP`, `DCMPN`, `DCMPP`, `LP`, `LM`, `VSS`, `VDD`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=4n maxstep=5p
```

The release harness expects these exact public scalar observables:

- `clk`
- `vinp`
- `vinn`
- `out_p`
- `out_n`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `vdd`
- `gnd`
- `clk`
- `vinp`
- `vinn`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "cmp_strongarm.va"

Vvdd (vdd 0) vsource dc=0.9 type=dc

IDUT (clk vinn vinp out_n out_p lp_int lm_int gnd vdd) cmp_strongarm

tran tran stop=4n maxstep=5p
save clk vinp vinn out_p out_n
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `outputs_toggle_nontrivially`
- `rising_clk_edge_latches_positive_decision`
- `rising_clk_edge_latches_negative_decision`
- `falling_clk_resets_both_outputs_low`
- `latched_decision_holds_through_input_swap`

## Output Contract

Return exactly these source artifacts:

- `cmp_strongarm.va`
- `tb_cmp_strongarm_ref.scs`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# StrongARM-Style Latch Comparator End-to-End Task

Write both the Verilog-A DUT and Spectre testbench for a clocked StrongArm-style
comparator.

The DUT module must be named `cmp_strongarm` and use electrical ports `CLK`,
`VINN`, `VINP`, `DCMPN`, `DCMPP`, `LP`, `LM`, `VSS`, and `VDD`. On rising clock
edges, compare `VINP - VINN` with optional `voffset`; on falling clock edges,
reset both comparator outputs low. Drive `DCMPP` and `DCMPN` as complementary
0/0.9 V logic outputs.

The comparator must be edge-latched rather than transparent: once a rising edge
sets the decision, input polarity changes during that evaluate-high phase must
not change `DCMPP`/`DCMPN` until the next clock edge. `LP` and `LM` should track
the internal latch state consistently with the main outputs.

The testbench should use 0.9 V supplies, a 1 GHz clock, and a small differential
input that produces positive and negative edge decisions, falling-edge reset
windows, and within-evaluate input swaps that prove latch hold. Save the clock,
inputs, and outputs. Keep the transient stop time away from a source transition
boundary.
