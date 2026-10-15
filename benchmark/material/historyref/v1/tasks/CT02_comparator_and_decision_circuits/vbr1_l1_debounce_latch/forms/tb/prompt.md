# Task: vbr1_l1_debounce_latch:tb

## Release Task Contract

- Form: `tb`
- Level: `L1`
- Category: Comparator and Decision Circuits
- Base function: Comparator debounce latch
- Domain: `voltage`
- Target artifact(s): `tb_debounce_latch_ref.scs`
- Supplied/reference support artifact(s): `debounce_latch.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `debounce_latch.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "debounce_latch.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `debounce_latch.va` declares module `debounce_latch` with positional ports: `sig`, `rst_n`, `out`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=140n maxstep=500p
```

The release harness expects these exact public scalar observables:

- `sig`
- `rst_n`
- `out`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `sig`
- `rst_n`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "debounce_latch.va"

XDUT (sig rst_n out) debounce_latch

tran tran stop=140n maxstep=500p
save sig rst_n out
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `short_glitch_rejected`
- `stable_high_qualified_after_delay`
- `falling_sig_clears_output`

## Output Contract

Return exactly one source artifact named `tb_debounce_latch_ref.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Comparator Debounce Latch Testbench

Write a Spectre testbench for a comparator decision latch with delayed glitch qualification.

The DUT module is `debounce_latch` with ports `sig, rst_n, out`. Treat `sig` as a noisy voltage-coded comparator decision. All ports are electrical; voltage-coded control ports use 0/0.9 V logic levels. The candidate DUT file will be available as `debounce_latch.va`; include it with `ahdl_include` and instantiate the DUT using the exact module and port names.

The testbench must exercise:
- Use active-low reset `rst_n`; reset forces `out` low and cancels any pending qualification.
- On a rising comparator-decision edge on `sig` while reset is released, arm a 12 ns qualification timer.
- On the timer event, set `out` high only if `sig` and `rst_n` are still high; falling `sig` clears or cancels the output.

Stimulus and observability requirements:
- Create short rejected pulses and longer accepted pulses on `sig` after reset releases.
- Run long enough to observe at least one rejected pulse and one qualified high output.
- Save `sig`, `rst_n`, and `out`.
