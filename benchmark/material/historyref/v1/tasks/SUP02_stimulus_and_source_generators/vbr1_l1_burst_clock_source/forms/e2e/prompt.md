# Task: vbr1_l1_burst_clock_source:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L1`
- Category: Stimulus and Source Generators
- Base function: Burst clock source
- Domain: `voltage`
- Target artifact(s): `clk_burst_gen.va`, `tb_clk_burst_gen_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate all target artifacts: `clk_burst_gen.va`, `tb_clk_burst_gen_ref.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `clk_burst_gen.va` must be co-located with the generated Spectre testbench.
- Include the generated DUT exactly with `ahdl_include "clk_burst_gen.va"` in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

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

## Output Contract

Return exactly these source artifacts:

- `clk_burst_gen.va`
- `tb_clk_burst_gen_ref.scs`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

Write a Verilog-A module named `clk_burst_gen`.

Create a voltage-domain clock burst generator in Verilog-A,
then produce a minimal EVAS-compatible Spectre testbench and run a smoke simulation.

Behavioral intent:

- one input clock `CLK`, one active-low reset `RST_N`, one output clock `CLK_OUT`
- parameter `div` (integer, ≥ 3) sets the burst period in input clock cycles
- on each burst period, `CLK_OUT` mirrors `CLK` for only the first 2 cycles,
  then stays low until the period resets
- active-low reset restarts the counter and suppresses output

Implementation constraints:

- pure voltage-domain Verilog-A only
- EVAS-compatible syntax
- use `@(cross(...))` for clock rising and falling edge detection
- use `transition(...)` to drive `CLK_OUT`
- `CLK`, `RST_N`, and `CLK_OUT` must appear in the waveform CSV

Minimum simulation goal:

- input clock 100 ns period, div=8, reset deasserts at ~235 ns, run for 3000 ns
- after reset, `CLK_OUT` must be present (max voltage > 0.8 V)
- `CLK_OUT` high fraction over the active window must be less than 50%
  (burst mode: only 2 out of 8 cycles pass through)

Ports:
- `CLK`: input electrical
- `RST_N`: input electrical
- `CLK_OUT`: output electrical
