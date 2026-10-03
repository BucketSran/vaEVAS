# Task: vbr1_l1_burst_clock_source:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: Stimulus and Source Generators
- Base function: Burst clock source
- Domain: `voltage`
- Target artifact(s): `clk_burst_gen.va`
- Supplied/reference support artifact(s): `tb_clk_burst_gen_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

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

## Public Behavior Checks

- `clk_out_present`
- `clk_out_duty_cycle_is_burst`

## Output Contract

Return exactly one source artifact named `clk_burst_gen.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Burst clock source DUT

Write the Verilog-A DUT artifact(s) for `Burst clock source`.

This is a function-checked DUT task, not a generic companion wrapper. The
public contract below defines the exact module interface, voltage-domain
behavior, and waveform observables used by the release checker.

Domain: pure voltage-domain behavioral Verilog-A.

## Module Contract

- Declaration: `clk_burst_gen(CLK, RST_N, CLK_OUT)`

Ports:

- `CLK`: input electrical clock, 0 V low and 0.9 V high
- `RST_N`: input electrical active-low reset, deasserted high during checking
- `CLK_OUT`: output electrical burst clock

## Behavioral Contract

- parameter `div` defaults to 8 and sets the burst repeat period in input-clock cycles
- `CLK_OUT` mirrors `CLK` for the first two cycles of each `div`-cycle window
- `CLK_OUT` stays low for the remaining cycles and while reset is asserted
- use `@(cross(...))` edge detection and `transition(...)` output drive

## Public Evaluation Observables

The companion validation testbench saves these waveform columns:

- `CLK`
- `RST_N`
- `CLK_OUT`
