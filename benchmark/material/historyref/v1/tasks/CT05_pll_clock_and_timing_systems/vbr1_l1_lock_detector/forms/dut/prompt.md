# Task: vbr1_l1_lock_detector:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: PLL Clock and Timing Systems
- Base function: Lock detector
- Domain: `voltage`
- Target artifact(s): `lock_detector.va`
- Supplied/reference support artifact(s): `tb_lock_detector_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

## Public Verilog-A Interface

- `lock_detector.va` declares module `lock_detector` with positional ports: `ref_clk`, `fb_clk`, `rst_n`, `lock`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=220n maxstep=500p
```

The release harness expects these exact public scalar observables:

- `ref_clk`
- `fb_clk`
- `rst_n`
- `lock`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `lock_low_before_three_good_edges`
- `lock_high_after_consecutive_aligned_edges`

## Output Contract

Return exactly one source artifact named `lock_detector.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

## Lock Detector DUT

Write a pure voltage-domain Verilog-A module for a reference-feedback lock detector.

The DUT module is `lock_detector` with ports `ref_clk, fb_clk, rst_n, lock`. All ports are electrical; digital-control ports use 0/0.9 V logic levels.

Required behavior:
- Use active-low reset to clear lock state and the consecutive-hit counter.
- Record rising feedback-clock edge times and compare them against rising reference-clock edges.
- Assert `lock` after three consecutive reference events whose feedback edge is within 2 ns.

Use voltage contributions only. Do not use current contributions, `ddt()`, or `idt()`.

Return exactly one complete Verilog-A file named `lock_detector.va`.
