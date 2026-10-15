# Task: vbr1_l1_debounce_latch:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L1`
- Category: Comparator and Decision Circuits
- Base function: Comparator debounce latch
- Domain: `voltage`
- Target artifact(s): `debounce_latch.va`, `tb_debounce_latch_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate all target artifacts: `debounce_latch.va`, `tb_debounce_latch_ref.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `debounce_latch.va` must be co-located with the generated Spectre testbench.
- Include the generated DUT exactly with `ahdl_include "debounce_latch.va"` in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

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

Return exactly these source artifacts:

- `debounce_latch.va`
- `tb_debounce_latch_ref.scs`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Comparator Debounce Latch End-to-End Task

Write both the Verilog-A DUT and Spectre testbench for a comparator decision latch with delayed glitch qualification.

The DUT module is `debounce_latch` with ports `sig, rst_n, out`. Treat `sig` as a noisy voltage-coded comparator decision. All ports are electrical; voltage-coded control ports use 0/0.9 V logic levels.

Required DUT behavior:
- Use active-low reset `rst_n`; reset forces `out` low and cancels any pending qualification.
- On a rising comparator-decision edge on `sig` while reset is released, arm a 12 ns qualification timer.
- On the timer event, set `out` high only if `sig` and `rst_n` are still high; falling `sig` clears or cancels the output.

Required testbench behavior:
- Create short rejected pulses and longer accepted pulses on `sig` after reset releases.
- Run long enough to observe at least one rejected pulse and one qualified high output.
- Save `sig`, `rst_n`, and `out`.

Use voltage contributions only in the Verilog-A DUT. Do not use current contributions, `ddt()`, or `idt()`.
