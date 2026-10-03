# Task: vbr1_l1_lfsr_prbs_generator:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L1`
- Category: Stimulus and Source Generators
- Base function: PRBS stimulus/dither generator
- Domain: `voltage`
- Target artifact(s): `lfsr.va`, `tb_lfsr_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate all target artifacts: `lfsr.va`, `tb_lfsr_ref.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `lfsr.va` must be co-located with the generated Spectre testbench.
- Include the generated DUT exactly with `ahdl_include "lfsr.va"` in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

- `lfsr.va` declares module `lfsr` with positional ports: `DPN`, `VDD`, `VSS`, `CLK`, `EN`, `RSTB`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=500n maxstep=2n
```

The release harness expects these exact public scalar observables:

- `clk`
- `rstb`
- `dpn`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `vdd`
- `vss`
- `clk`
- `rstb`
- `en`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "lfsr.va"

Vvdd (vdd 0) vsource dc=0.9
Vvss (vss 0) vsource dc=0.0

IDUT (dpn vdd vss clk en rstb) lfsr seed=123

tran tran stop=500n maxstep=2n
save clk rstb dpn
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `lfsr_output_not_stuck`
- `lfsr_has_min_transitions`

## Output Contract

Return exactly these source artifacts:

- `lfsr.va`
- `tb_lfsr_ref.scs`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

Write a Verilog-A module named `lfsr`.

Create a voltage-domain 31-bit Linear Feedback Shift Register (LFSR)
stimulus/dither source in Verilog-A, then produce a voltage-domain Spectre
transient testbench and run a smoke simulation.

Behavioral intent:

- one input clock `clk`, one active-low reset `rstb`, one enable `en`, power rails `vdd` / `vss`
- one voltage-coded PRBS stimulus/dither output node `dpn` driven from the MSB of the shift register
- on reset (rstb low), initialize the register from a `seed` parameter
- on each rising edge of `clk` with `rstb` high, advance the LFSR using the
  maximal-length polynomial for n=31: taps at positions 31, 21, 1, 0
- `dpn` should follow the MSB of the register via a voltage-level transition

Implementation constraints:

- pure voltage-domain Verilog-A only
- portable voltage-domain behavioral Verilog-A syntax
- use `@(cross(...))` for clock and reset edge detection
- use `transition(...)` to drive `dpn`
- `clk`, `dpn`, and `rstb` must appear in the waveform CSV

Minimum simulation goal:

- seed=123, clock 1 GHz, reset deasserts at ~101 ns, run for 500 ns
- after reset, `dpn` must toggle at least 10 times so the stimulus is not stuck HIGH or LOW
- high fraction of `dpn` must be between 5% and 95%

Ports:
- `DPN`: output electrical
- `VDD`: inout electrical
- `VSS`: inout electrical
- `CLK`: input electrical
- `EN`: input electrical
- `RSTB`: input electrical
