# Task: vbr1_l1_strongarm_style_latch_comparator:bugfix

## Release Task Contract

- Form: `bugfix`
- Level: `L1`
- Category: Comparator and Decision Circuits
- Base function: StrongARM-style latch comparator
- Domain: `voltage`
- Target artifact(s): `dut_fixed.va`
- Supplied/reference support artifact(s): `dut_buggy.va`, `tb_strongarm_reset_priority_bug_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Repair the supplied buggy Verilog-A artifact while preserving the public module interface and artifact boundary.
- Use the buggy source plus the public intended behavior below; do not change the companion testbench contract.

## Public Interface To Preserve

- `dut_buggy.va` declares module `strongarm_reset_priority_buggy` with positional ports: `vdd`, `vss`, `clk`, `rst`, `inp`, `inn`, `outp`, `outn`.
- `dut_fixed.va` declares module `strongarm_reset_priority_fixed` with positional ports: `vdd`, `vss`, `clk`, `rst`, `inp`, `inn`, `outp`, `outn`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=80n maxstep=20p errpreset=conservative
```

The release harness expects these exact public scalar observables:

- `clk`
- `rst`
- `inp`
- `inn`
- `outp`
- `outn`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

## Public Behavior Checks

- `reset_window_forces_outp_outn_low`
- `post_reset_high_and_low_input_polarity_windows_are_correct`

## Observed Mismatch Framing

The supplied buggy artifact violates one or more public behavior checks above under the release validation testbench.
Repair the observable behavior without renaming modules, changing ports, or weakening the public testbench contract.

## Output Contract

Return exactly one source artifact named `dut_fixed.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# StrongARM Reset-Priority Bugfix

The following voltage-domain StrongArm-style comparator has a reset-priority
bug: clock edges can update the outputs while `rst` is high. Fix the design so
reset has unconditional priority and forces both outputs low.

The fixed module must be named `strongarm_reset_priority_fixed` and use
electrical ports `vdd`, `vss`, `clk`, `rst`, `inp`, `inn`, `outp`, and `outn`.
When `rst` is high, both outputs must remain low. When reset is released, rising
clock edges should compare `inp` and `inn`: `outp` high / `outn` low for
`inp > inn`, and `outn` high / `outp` low for `inn > inp`.

Use voltage contributions and smoothed output transitions. Do not use current
contributions, `ddt()`, or `idt()`.
