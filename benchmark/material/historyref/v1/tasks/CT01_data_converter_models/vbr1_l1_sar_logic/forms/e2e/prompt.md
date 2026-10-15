# Task: vbr1_l1_sar_logic:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L1`
- Category: Data Converter Models
- Base function: SAR logic
- Domain: `voltage`
- Target artifact(s): `sar_logic_4b.va`, `tb_sar_logic_4b_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate all target artifacts: `sar_logic_4b.va`, `tb_sar_logic_4b_ref.scs`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `sar_logic_4b.va` must be co-located with the generated Spectre testbench.
- Include the generated DUT exactly with `ahdl_include "sar_logic_4b.va"` in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

- `sar_logic_4b.va` declares module `sar_logic_4b` with positional ports: `VDD`, `VSS`, `CLKS`, `DCOMP`, `DP_DAC_3`, `DP_DAC_2`, `DP_DAC_1`, `DP_DAC_0`, `RDY`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=260n maxstep=1n
```

The release harness expects these exact public scalar observables:

- `clks`
- `dcomp`
- `rdy`
- `dp_dac_3`
- `dp_dac_2`
- `dp_dac_1`
- `dp_dac_0`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `vdd`
- `vss`
- `clks`
- `dcomp`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "sar_logic_4b.va"

Vvdd (vdd 0) vsource dc=0.9
Vvss (vss 0) vsource dc=0.0

IDUT (vdd vss clks dcomp dp_dac_3 dp_dac_2 dp_dac_1 dp_dac_0 rdy) sar_logic_4b

tran tran stop=260n maxstep=1n
save clks dcomp rdy dp_dac_3 dp_dac_2 dp_dac_1 dp_dac_0
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `rdy_low_high_low_sequence`
- `dac_code_1010_at_conversion_done_window`

## Output Contract

Return exactly these source artifacts:

- `sar_logic_4b.va`
- `tb_sar_logic_4b_ref.scs`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

# Task: vbm1_sar_logic_4b_e2e

Write both the Verilog-A DUT and Spectre testbench for a 4-bit SAR logic sequencer.

The DUT module is `sar_logic_4b` with ports `VDD, VSS, CLKS, DCOMP, DP_DAC_3, DP_DAC_2, DP_DAC_1, DP_DAC_0, RDY`. All ports are electrical; digital-control ports use 0/0.9 V logic levels.

Required DUT behavior:
- Implement a 4-bit successive-approximation state machine clocked by rising `CLKS` edges.
- Resolve the current trial bit from `DCOMP`, advance to the next lower bit, and assert `RDY` after bit 0 is resolved.
- Drive DAC decision pins and `RDY` as 0/0.9 V voltage-domain outputs with `transition()`.

Required testbench behavior:
- Clock the SAR through repeated conversion cycles with comparator decisions that produce code 1010 at the checked window.
- Save `CLKS`, `DCOMP`, all DAC decision pins, and `RDY`.

Use voltage contributions only in the Verilog-A DUT. Do not use current contributions, `ddt()`, or `idt()`.

Return exactly two files: `sar_logic_4b.va` and `tb_sar_logic_4b_ref.scs`.
