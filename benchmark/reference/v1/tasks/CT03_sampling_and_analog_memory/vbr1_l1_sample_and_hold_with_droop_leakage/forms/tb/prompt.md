# Task: vbr1_l1_sample_and_hold_with_droop_leakage:tb

## Release Task Contract

- Form: `tb`
- Level: `L1`
- Category: Sampling and Analog Memory
- Base function: Sample-and-hold with droop/leakage
- Domain: `voltage`
- Target artifact(s): `tb_leaky_hold_ref.scs`
- Supplied/reference support artifact(s): `leaky_hold.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `leaky_hold.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "leaky_hold.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `leaky_hold.va` declares module `leaky_hold` with positional ports: `sample`, `rst`, `vin`, `vout`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=170n maxstep=250p
```

The release harness expects these exact public scalar observables:

- `sample`
- `rst`
- `vin`
- `vout`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `sample`
- `rst`
- `vin`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "leaky_hold.va"

XDUT (sample rst vin vout) leaky_hold

tran tran stop=170n maxstep=250p
save sample rst vin vout
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `rising_sample_edge_captures_vin`
- `multiple_input_levels_are_preserved`
- `held_output_droops_over_time`
- `reset_clears_output`
- `post_reset_sample_recovers_to_vin`

## Output Contract

Return exactly one source artifact named `tb_leaky_hold_ref.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

Write a Spectre testbench for a sample-and-hold DUT with observable
droop/leakage.

The DUT module is `leaky_hold` with ports `sample, rst, vin, vout`. All ports
are electrical; digital-control ports use 0/0.9 V logic levels. The candidate
DUT file will be available as `leaky_hold.va`; include it with `ahdl_include`
and instantiate the DUT using the exact module and port names.

The testbench must exercise:
- A rising `sample` edge captures the current value of `V(vin)`, not a fixed
  internal level.
- A 1 ns timer applies exponential droop by multiplying the held value by
  0.985 while reset is low.
- High `rst` clears the held value; drive `vout` through `transition()`.

Stimulus and observability requirements:
- Generate at least three capture events with distinct `vin` levels, an
  observable droop interval, reset clearing, and post-reset recapture.
- Save `sample`, `rst`, `vin`, and `vout`.
