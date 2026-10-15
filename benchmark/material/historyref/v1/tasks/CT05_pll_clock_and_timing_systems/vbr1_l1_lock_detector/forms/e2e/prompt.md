# Task: vbr1_l1_lock_detector:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L1`
- Category: PLL Clock and Timing Systems
- Base function: Lock detector
- Domain: `voltage`
- Target artifact(s): `lock_detector.va`, `tb_lock_detector_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate all target artifacts: `lock_detector.va`, `tb_lock_detector_ref.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `lock_detector.va` must be co-located with the generated Spectre testbench.
- Include the generated DUT exactly with `ahdl_include "lock_detector.va"` in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

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

Public stimulus/source nodes visible in the reference harness include:

- `rst_n`
- `ref_clk`
- `fb_clk`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "lock_detector.va"

XDUT (ref_clk fb_clk rst_n lock) lock_detector

tran tran stop=220n maxstep=500p
save ref_clk fb_clk rst_n lock
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `lock_low_before_three_good_edges`
- `lock_high_after_consecutive_aligned_edges`

## Output Contract

Return exactly these source artifacts:

- `lock_detector.va`
- `tb_lock_detector_ref.scs`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

## Lock Detector End-to-End Task

Write both the Verilog-A DUT and Spectre testbench for a reference-feedback lock detector.

The DUT module is `lock_detector` with ports `ref_clk, fb_clk, rst_n, lock`. All ports are electrical; digital-control ports use 0/0.9 V logic levels.

Required DUT behavior:
- Use active-low reset to clear lock state and the consecutive-hit counter.
- Record rising feedback-clock edge times and compare them against rising reference-clock edges.
- Assert `lock` after three consecutive reference events whose feedback edge is within 2 ns.

Required testbench behavior:
- Drive initial mismatched or unsettled clocks followed by aligned reference and feedback clocks.
- Save `ref_clk`, `fb_clk`, `rst_n`, and `lock`.

Use voltage contributions only in the Verilog-A DUT. Do not use current contributions, `ddt()`, or `idt()`.

Return exactly two files: `lock_detector.va` and `tb_lock_detector_ref.scs`.
