# Task: vbr1_l1_lock_detector:bugfix

## Release Task Contract

- Form: `bugfix`
- Level: `L1`
- Category: PLL Clock and Timing Systems
- Base function: Lock detector
- Domain: `voltage`
- Target artifact(s): `dut_fixed.va`
- Supplied/reference support artifact(s): `dut_buggy.va`, `tb_lock_detector_buggy.scs`, `tb_lock_detector_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Repair the supplied buggy Verilog-A artifact while preserving the public module interface and artifact boundary.
- Use the buggy source plus the public intended behavior below; do not change the companion testbench contract.

## Public Interface To Preserve

- `dut_buggy.va` declares module `lock_detector` with positional ports: `ref_clk`, `fb_clk`, `rst_n`, `lock`.
- `dut_fixed.va` declares module `lock_detector` with positional ports: `ref_clk`, `fb_clk`, `rst_n`, `lock`.

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

- `lock_low_before_required_consecutive_count`
- `lock_high_after_third_aligned_reference_edge_with_need_3`
- `lock_remains_high_after_next_aligned_edge`
- `reset_clears_lock_and_streak`

## Observed Mismatch Framing

The supplied buggy artifact violates one or more public behavior checks above under the release validation testbench.
Repair the observable behavior without renaming modules, changing ports, or weakening the public testbench contract.

## Output Contract

Return exactly one source artifact named `dut_fixed.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

## Lock Detector Bugfix

The provided voltage-domain PLL lock detector has a lock assertion off-by-one
bug. It should assert `lock` after the configured number of consecutive
reference-clock edges each observe a recent feedback-clock edge within the
configured time tolerance.

Fix the design so reset clears the internal feedback timestamp, streak counter,
and lock state. While reset is released, every rising `fb_clk` crossing records
the feedback edge time, and every rising `ref_clk` crossing increments the
streak only when the most recent feedback edge is within `tol`. The fixed design
must assert `lock` as soon as the streak reaches `need`.

The fixed module must be named `lock_detector` and use electrical ports
`ref_clk`, `fb_clk`, `rst_n`, and `lock`. Use voltage contributions and smoothed
output transitions. Do not use current contributions, `ddt()`, or `idt()`.

Return exactly one complete Verilog-A file named `dut_fixed.va`.
