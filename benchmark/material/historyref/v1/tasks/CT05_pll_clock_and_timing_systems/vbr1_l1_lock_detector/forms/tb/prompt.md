# Task: vbr1_l1_lock_detector:tb

## Release Task Contract

- Form: `tb`
- Level: `L1`
- Category: PLL Clock and Timing Systems
- Base function: Lock detector
- Domain: `voltage`
- Target artifact(s): `tb_lock_detector_ref.scs`
- Supplied/reference support artifact(s): `lock_detector.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `lock_detector.va` will be co-located with the generated testbench by the evaluation harness.
- Include it exactly with `ahdl_include "lock_detector.va"` in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

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

Return exactly one source artifact named `tb_lock_detector_ref.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

## Lock Detector Testbench Companion

Write a Spectre testbench for a reference-feedback lock detector DUT.

The DUT module is `lock_detector` with ports `ref_clk, fb_clk, rst_n, lock`. All ports are electrical; digital-control ports use 0/0.9 V logic levels. The candidate DUT file will be available as `lock_detector.va`; include it with `ahdl_include` and instantiate the DUT using the exact module and port names.

The testbench must exercise:
- Use active-low reset to clear lock state and the consecutive-hit counter.
- Record rising feedback-clock edge times and compare them against rising reference-clock edges.
- Assert `lock` after three consecutive reference events whose feedback edge is within 2 ns.

Stimulus and observability requirements:
- Drive initial mismatched or unsettled clocks followed by aligned reference and feedback clocks.
- Save `ref_clk`, `fb_clk`, `rst_n`, and `lock`.

Return exactly one Spectre testbench file named `tb_lock_detector_ref.scs`.
