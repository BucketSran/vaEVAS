# Task: vbr1_l1_sample_and_hold_with_droop_leakage:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L1`
- Category: Sampling and Analog Memory
- Base function: Sample-and-hold with droop/leakage
- Domain: `voltage`
- Target artifact(s): `leaky_hold.va`, `tb_leaky_hold_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate all target artifacts: `leaky_hold.va`, `tb_leaky_hold_ref.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `leaky_hold.va` must be co-located with the generated Spectre testbench.
- Include the generated DUT exactly with `ahdl_include "leaky_hold.va"` in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

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

Return exactly these source artifacts:

- `leaky_hold.va`
- `tb_leaky_hold_ref.scs`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

Write both the Verilog-A DUT and Spectre testbench for a sample-and-hold with
observable droop/leakage.

The DUT module is `leaky_hold` with ports `sample, rst, vin, vout`. All ports
are electrical; digital-control ports use 0/0.9 V logic levels.

Required DUT behavior:
- A rising `sample` edge captures the current value of `V(vin)`, not a fixed
  internal level.
- A 1 ns timer applies exponential droop by multiplying the held value by
  0.985 while reset is low.
- High `rst` clears the held value; drive `vout` through `transition()`.

Required testbench behavior:
- Generate at least three capture events with distinct `vin` levels, an
  observable droop interval, reset clearing, and post-reset recapture.
- Save `sample`, `rst`, `vin`, and `vout`.

Use voltage contributions only in the Verilog-A DUT. Do not use current contributions, `ddt()`, or `idt()`.
