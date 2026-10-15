# Task: vbr1_l1_strongarm_style_latch_comparator:tb

## Release Task Contract

- Form: `tb`
- Level: `L1`
- Category: Comparator and Decision Circuits
- Base function: StrongARM-style latch comparator
- Domain: `voltage`
- Target artifact(s): `tb_cmp_strongarm_ref.scs`
- Supplied/reference support artifact(s): `cmp_strongarm.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `cmp_strongarm.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "cmp_strongarm.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

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
- `stimulus_exercises_positive_and_negative_edge_decisions`
- `stimulus_swaps_inputs_during_evaluate_phase`
- `falling_clk_reset_windows_are_observable`

## Output Contract

Return exactly one source artifact named `tb_cmp_strongarm_ref.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# StrongARM-Style Latch Comparator Testbench

Write a Spectre testbench for a Verilog-A module named `cmp_strongarm` with
ports `CLK VINN VINP DCMPN DCMPP LP LM VSS VDD`.

The testbench should provide 0.9 V supply rails, a 1 GHz clock, and a small
differential input around common-mode 0.45 V. It must demonstrate three
properties in one run:

- a positive differential sampled on a rising clock edge drives `out_p` high
  and `out_n` low
- a negative differential sampled on a rising clock edge drives `out_n` high
  and `out_p` low
- if the differential input polarity swaps while `CLK` remains high, the
  already-latched decision holds until the falling clock reset

Save the clock, differential inputs, and comparator outputs using plain signal
names. Use a transient stop time that is not exactly on the final input
transition.
