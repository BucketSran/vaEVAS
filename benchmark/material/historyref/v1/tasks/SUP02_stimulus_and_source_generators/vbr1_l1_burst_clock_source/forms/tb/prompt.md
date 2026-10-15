# Task: vbr1_l1_burst_clock_source:tb

## Release Task Contract

- Form: `tb`
- Level: `L1`
- Category: Stimulus and Source Generators
- Base function: Burst clock source
- Domain: `voltage`
- Target artifact(s): `tb_clk_burst_gen_ref.scs`
- Supplied/reference support artifact(s): `clk_burst_gen.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `clk_burst_gen.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "clk_burst_gen.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `clk_burst_gen.va` declares module `clk_burst_gen` with positional ports: `CLK`, `RST_N`, `CLK_OUT`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=3000n maxstep=5n
```

The release harness expects these exact public scalar observables:

- `CLK`
- `RST_N`
- `CLK_OUT`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `CLK`
- `RST_N`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "clk_burst_gen.va"

IDUT (CLK RST_N CLK_OUT) clk_burst_gen div=8 vdd=0.9 vth=0.45

tran tran stop=3000n maxstep=5n
save CLK RST_N CLK_OUT
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `clk_out_present`
- `clk_out_duty_cycle_is_burst`

## Public L1 Testbench Stimulus Contract

This TB row should expose a burst clock generator after reset:

- Drive `CLK` as a slow periodic 0 V/0.9 V input clock.
- Hold `RST_N` low initially, then release it before the useful burst window.
- Run long enough for divided or gated output bursts to appear on `CLK_OUT`.
- Save `CLK`, `RST_N`, and `CLK_OUT` exactly.

The expected public relation is: `CLK_OUT` contains clock activity only in the
burst pattern defined by the supplied generator, not a constant output. Do not
generate checker logic.

## Output Contract

Return exactly one source artifact named `tb_clk_burst_gen_ref.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Burst clock source Testbench Companion

Write a Spectre transient testbench for the `Burst clock source` behavioral
Verilog-A release task. This is the testbench-generation companion for an
already materialized end-to-end task.

The testbench should instantiate the same behavioral DUT or system module used
by the corresponding end-to-end form, drive the public transient scenario, save
the observable waveform or metric signals, and preserve the EVAS/Spectre
validation contract.

Domain: pure voltage-domain behavioral Verilog-A.

Public requirements:

- include a transient `tran` analysis
- save the public observables needed by the public behavior checks
- include or instantiate the Verilog-A behavioral module under test
- satisfy the named behavior checks using only public waveforms and side outputs
- avoid transistor-level devices, AC/noise analysis, and current-domain
  solver assumptions
