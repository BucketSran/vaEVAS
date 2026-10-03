# Task: vbr1_l1_bang_bang_phase_detector:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L1`
- Category: PLL Clock and Timing Systems
- Base function: Bang-bang phase detector
- Domain: `voltage`
- Target artifact(s): `bbpd_data_edge_alignment_ref.va`, `tb_bbpd_data_edge_alignment_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate all target artifacts: `bbpd_data_edge_alignment_ref.va`, `tb_bbpd_data_edge_alignment_ref.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `bbpd_data_edge_alignment_ref.va` must be co-located with the generated Spectre testbench.
- Include the generated DUT exactly with `ahdl_include "bbpd_data_edge_alignment_ref.va"` in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

- `bbpd_data_edge_alignment_ref.va` declares module `bbpd_data_edge_alignment_ref` with positional ports: `vdd`, `vss`, `clk`, `data`, `up`, `dn`, `retimed_data`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=170n maxstep=0.1n
```

The release harness expects these exact public scalar observables:

- `clk`
- `data`
- `up`
- `dn`
- `retimed_data`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `vdd`
- `vss`
- `clk`
- `data`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "bbpd_data_edge_alignment_ref.va"

Vvdd (vdd 0) vsource dc=0.9
Vvss (vss 0) vsource dc=0.0

XDUT (vdd vss clk data up dn retimed_data) bbpd_data_edge_alignment_ref

tran tran stop=170n maxstep=0.1n
save clk data up dn retimed_data
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `up_pulses_dominate_in_lead_window`
- `dn_pulses_dominate_in_lag_window`
- `up_dn_overlap_fraction_low`

## Output Contract

Return exactly these source artifacts:

- `bbpd_data_edge_alignment_ref.va`
- `tb_bbpd_data_edge_alignment_ref.scs`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

Write a voltage-domain Alexander-style bang-bang phase detector (BBPD) and
matching transient testbench that expose data/clock edge-alignment behavior.

Module name: `bbpd_data_edge_alignment_ref`.

Required DUT behavior:

- Ports are exactly `vdd`, `vss`, `clk`, `data`, `up`, `dn`, `retimed_data`.
- `vdd` and `vss` are supply rails; `clk` and `data` are voltage-coded logic inputs.
- `up`, `dn`, and `retimed_data` are voltage outputs driven between the supply rails.
- Use Verilog-A event handling with `cross()` for clock/data edges.
- Emit bounded `up` pulses when data edges lead the clock and bounded `dn`
  pulses when data edges lag the clock.
- Keep `up` and `dn` mostly non-overlapping; do not leave both asserted after
  the alignment decision.
- Update `retimed_data` on clock edges to the sampled data value.

Required testbench behavior:

- Generate lead and lag windows with at least six observable data transitions.
- Save plain scalar observables `clk`, `data`, `up`, `dn`, and `retimed_data`.
- Run the public transient long enough for both lead-dominated and
  lag-dominated windows to appear.
