# Task: vbr1_l1_debounce_latch:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: Comparator and Decision Circuits
- Base function: Comparator debounce latch
- Domain: `voltage`
- Target artifact(s): `debounce_latch.va`
- Supplied/reference support artifact(s): `tb_debounce_latch_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

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

## Public Behavior Checks

- `short_glitch_rejected`
- `stable_high_qualified_after_delay`
- `falling_sig_clears_output`

## Output Contract

Return exactly one source artifact named `debounce_latch.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Comparator Debounce Latch DUT

Write a pure voltage-domain Verilog-A module for a comparator decision latch with delayed glitch qualification.

The DUT module is `debounce_latch` with ports `sig, rst_n, out`. Treat `sig` as a noisy voltage-coded comparator decision. All ports are electrical; voltage-coded control ports use 0/0.9 V logic levels.

Required behavior:
- Use active-low reset `rst_n`; reset forces `out` low and cancels any pending qualification.
- On a rising comparator-decision edge on `sig` while reset is released, arm a 12 ns qualification timer.
- On the timer event, set `out` high only if `sig` and `rst_n` are still high; falling `sig` clears or cancels the output.

Use voltage contributions only. Do not use current contributions, `ddt()`, or `idt()`.
