# Task: vbr1_l1_clock_divider:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: PLL Clock and Timing Systems
- Base function: Clock divider
- Domain: `voltage`
- Target artifact(s): `clk_divider_ref.va`
- Supplied/reference support artifact(s): `clk_divider.va`, `tb_clk_divider_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

## Public Verilog-A Interface

- `clk_divider.va` declares module `clk_divider` with positional ports: `CLK_IN`, `RST_N`, `CLK_OUT`, `LOCK`.
- `clk_divider_ref.va` declares module `clk_divider_ref` with positional ports: `clk_in`, `rst_n`, `div_code_0`, `div_code_1`, `div_code_2`, `div_code_3`, `div_code_4`, `div_code_5`, `div_code_6`, `div_code_7`, `clk_out`, `lock`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=80n maxstep=50p
```

The release harness expects these exact public scalar observables:

- `clk_in`
- `rst_n`
- `clk_out`
- `lock`
- `div_code_0`
- `div_code_1`
- `div_code_2`
- `div_code_3`
- `div_code_4`
- `div_code_5`
- `div_code_6`
- `div_code_7`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `ratio_code_decodes_to_5`
- `output_period_matches_five_input_edges`
- `lock_asserts_after_first_complete_output_period`

## Output Contract

Return exactly one source artifact named `clk_divider_ref.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

This entry is scoped as a PLL/ADPLL feedback-divider timing primitive, not as a generic digital-logic benchmark. Model the divider through voltage-domain clock edges, reset behavior, decoded ratio, and lock timing used by PLL loops.

## PLL Feedback Divider DUT

Write a pure voltage-domain Verilog-A module for a resettable programmable clock divider.

The DUT module is `clk_divider_ref` with ports `clk_in, rst_n, div_code_0, div_code_1, div_code_2, div_code_3, div_code_4, div_code_5, div_code_6, div_code_7, clk_out, lock`. All ports are electrical; digital-control ports use 0/0.9 V logic levels.

Required behavior:
- Decode an 8-bit voltage-domain ratio code into an integer divide ratio, with code 0 treated as ratio 1.
- Use active-low reset to clear the counter, output state, and lock state.
- For ratio greater than 1, divide the input clock with floor/ceil high and low segment lengths; assert `lock` after the first complete output period.

Use voltage contributions only. Do not use current contributions, `ddt()`, or `idt()`.

Review caveat: The staged evidence also preserves an auxiliary legacy `clk_divider.va`; the public task contract targets `clk_divider_ref`.

Return exactly one complete Verilog-A file named `clk_divider_ref.va`.
