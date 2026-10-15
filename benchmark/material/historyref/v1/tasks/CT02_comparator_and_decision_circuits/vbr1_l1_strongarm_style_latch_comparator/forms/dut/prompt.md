# Task: vbr1_l1_strongarm_style_latch_comparator:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: Comparator and Decision Circuits
- Base function: StrongARM-style latch comparator
- Domain: `voltage`
- Target artifact(s): `cmp_strongarm.va`
- Supplied/reference support artifact(s): `tb_cmp_strongarm_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

## Public Verilog-A Interface

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

## Public Behavior Checks

- `outputs_toggle_nontrivially`
- `rising_clk_edge_latches_positive_decision`
- `rising_clk_edge_latches_negative_decision`
- `falling_clk_resets_both_outputs_low`
- `latched_decision_holds_through_input_swap`

## Output Contract

Return exactly one source artifact named `cmp_strongarm.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# StrongARM-Style Latch Comparator DUT

Write a pure voltage-domain Verilog-A module named `cmp_strongarm`.

The module is a clocked StrongArm-style comparator with electrical ports
`CLK`, `VINN`, `VINP`, `DCMPN`, `DCMPP`, `LP`, `LM`, `VSS`, and `VDD`. On each
rising edge of `CLK`, compare `VINP - VINN` after applying the optional
`voffset` parameter. Drive `DCMPP` high and `DCMPN` low when the offset-adjusted
differential input is positive; drive `DCMPN` high and `DCMPP` low when it is
negative. On falling clock edges, reset both comparator outputs low.

The model must be edge-latched, not transparent during the high clock phase:
after a rising edge decision, later input polarity swaps must not change
`DCMPP`/`DCMPN` until the next rising clock edge. Drive `LP` and `LM` as
observable latch-state nodes consistent with `DCMPP` and `DCMPN`.

Use voltage contributions and smoothed output transitions. Do not use current
contributions, `ddt()`, or `idt()`.
