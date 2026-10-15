# Task: vbr1_l1_offset_comparator:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L1`
- Category: Comparator and Decision Circuits
- Base function: Offset comparator
- Domain: `voltage`
- Target artifact(s): `cmp_offset_ref.va`, `tb_comparator_offset_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate all target artifacts: `cmp_offset_ref.va`, `tb_comparator_offset_ref.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `cmp_offset_ref.va` must be co-located with the generated Spectre testbench.
- Include the generated DUT exactly with `ahdl_include "cmp_offset_ref.va"` in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

- `cmp_offset_ref.va` declares module `cmp_offset_ref` with positional ports: `VDD`, `VSS`, `CLK`, `VINP`, `VINN`, `OUT_P`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=28n maxstep=20p
```

The release harness expects these exact public scalar observables:

- `CLK`
- `VINP`
- `VINN`
- `OUT_P`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `VDD`
- `VSS`
- `CLK`
- `VINP`
- `VINN`

## Public Stimulus Schedule Contract

Use this exact public source schedule in generated Spectre testbenches. This schedule is part of the public testbench contract; it is not hidden checker logic.

Public schedule source: `tb_comparator_offset_ref.scs`.

```spectre
Vvdd (VDD 0) vsource dc=0.9
Vvss (VSS 0) vsource dc=0
Vclk (CLK 0) vsource type=pulse val0=0 val1=0.9 delay=1n rise=20p fall=20p width=1n period=4n
Vinp (VINP 0) vsource type=pwl wave=[ \
    0    0.440 \
    4n   0.440 \
    4.2n 0.450 \
    8n   0.450 \
    8.2n 0.453 \
    12n  0.453 \
    12.2n 0.457 \
    16n  0.457 \
    16.2n 0.470 \
    20n  0.470 \
    20.2n 0.450 \
    24n  0.450 \
    24.2n 0.440 \
    28n  0.440 \
]
Vinn (VINN 0) vsource dc=0.450
```

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "cmp_offset_ref.va"

Vvdd (VDD 0) vsource dc=0.9
Vvss (VSS 0) vsource dc=0

XDUT (VDD VSS CLK VINP VINN OUT_P) cmp_offset_ref

tran tran stop=28n maxstep=20p
save CLK VINP VINN OUT_P
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `clocked_output_sequence_LLLHHLL`
- `negative_diff_latches_low`
- `positive_diff_below_5mV_offset_latches_low`
- `positive_diff_above_5mV_offset_latches_high`
- `decisions_sampled_after_rising_clk_edges`

## Output Contract

Return exactly these source artifacts:

- `cmp_offset_ref.va`
- `tb_comparator_offset_ref.scs`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Offset Comparator End-to-End Task

Write both the Verilog-A DUT and Spectre testbench for a clocked comparator with input offset.

The DUT module is `cmp_offset_ref` with ports `VDD, VSS, CLK, VINP, VINN, OUT_P`. All ports are electrical; digital-control ports use 0/0.9 V logic levels.

Required DUT behavior:
- On each rising `CLK` edge, compare `VINP - VINN` against an internal positive
  offset threshold of about 5 mV.
- Borderline positive inputs below the offset, such as +3 mV, must still latch
  low; inputs above the offset, such as +7 mV or +20 mV, must latch high.
- Drive `OUT_P` to the supply level for a high decision and to `VSS` for a low decision.
- Use smoothed voltage-domain output transitions.

Required testbench behavior:
- Sweep `VINP` around `VINN` with clock-edge differential samples covering
  negative, zero, +3 mV, +7 mV, +20 mV, zero, and negative cases.
- Save the clock, differential inputs, and output so the expected settled
  decision sequence `LLLHHLL` is visible after rising clock edges.

Use voltage contributions only in the Verilog-A DUT. Do not use current contributions, `ddt()`, or `idt()`.
