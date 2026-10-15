# Task: vbr1_l1_dwa_dem_encoder:tb

## Release Task Contract

- Form: `tb`
- Level: `L1`
- Category: Calibration, DEM, and Control
- Base function: DWA/DEM encoder
- Domain: `voltage`
- Target artifact(s): `tb_dwa_ptr_gen_ref.scs`
- Supplied/reference support artifact(s): `dwa_ptr_gen.va`, `v2b_4b.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate only the Spectre transient testbench artifact(s); do not generate hidden checker logic.
- Instantiate the supplied/public DUT module(s), drive a public transient scenario, and save the required observables.
- The supplied DUT/support Verilog-A file(s) `dwa_ptr_gen.va`, `v2b_4b.va` will be co-located with the generated testbench by the evaluation harness.
- Include each supplied Verilog-A support file exactly with a matching `ahdl_include "<file>.va"` line in the generated Spectre `.scs` netlist.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public DUT Interface To Instantiate

- `dwa_ptr_gen.va` declares module `dwa_ptr_gen` with positional ports: `clk_i`, `rst_ni`, `code_msb_i`, `cell_en_o`, `ptr_o`.
- `v2b_4b.va` declares module `v2b_4b` with positional ports: `clk`, `vin`, `out_3`, `out_2`, `out_1`, `out_0`.

## Public Testbench And Observable Contract

Public transient setting used by the release harness:

```spectre
tran tran stop=100n maxstep=2n
```

The release harness expects these exact public scalar observables:

- `clk_i`
- `rst_ni`
- `code_3`
- `code_2`
- `code_1`
- `code_0`
- `cell_en_15`
- `cell_en_14`
- `cell_en_13`
- `cell_en_12`
- `cell_en_11`
- `cell_en_10`
- `cell_en_9`
- `cell_en_8`
- `cell_en_7`
- `cell_en_6`
- `cell_en_5`
- `cell_en_4`
- `cell_en_3`
- `cell_en_2`
- `cell_en_1`
- `cell_en_0`
- `ptr_15`
- `ptr_14`
- `ptr_13`
- `ptr_12`
- `ptr_11`
- `ptr_10`
- `ptr_9`
- `ptr_8`
- `ptr_7`
- `ptr_6`
- `ptr_5`
- `ptr_4`
- `ptr_3`
- `ptr_2`
- `ptr_1`
- `ptr_0`

When this form generates a testbench, use plain scalar save names for these observables; do not rely on instance-qualified or aliased save names.

Public stimulus/source nodes visible in the reference harness include:

- `clk_i`
- `rst_ni`
- `vin_node`

## Public Spectre Testbench Scaffold

When this form generates a `.scs` testbench, use the following public skeleton shape. Fill in only the public stimulus details required by the task; do not copy or emit hidden checker logic.

```spectre
simulator lang=spectre
global 0
ahdl_include "dwa_ptr_gen.va"
ahdl_include "v2b_4b.va"

IV2B (clk_i vin_node code_3 code_2 code_1 code_0) v2b_4b vdd=0.9
IDUT (clk_i rst_ni code_3 code_2 code_1 code_0 cell_en_15 cell_en_14 cell_en_13 cell_en_12 cell_en_11 cell_en_10 cell_en_9 cell_en_8 cell_en_7 cell_en_6 cell_en_5 cell_en_4 cell_en_3 cell_en_2 cell_en_1 cell_en_0 ptr_15 ptr_14 ptr_13 ptr_12 ptr_11 ptr_10 ptr_9 ptr_8 ptr_7 ptr_6 ptr_5 ptr_4 ptr_3 ptr_2 ptr_1 ptr_0) dwa_ptr_gen vdd=0.9 vth=0.45 ptr_init=0

tran tran stop=100n maxstep=2n
save clk_i rst_ni code_3 code_2 code_1 code_0 cell_en_15 cell_en_14 cell_en_13 cell_en_12 cell_en_11 cell_en_10 cell_en_9 cell_en_8 cell_en_7 cell_en_6 cell_en_5 cell_en_4 cell_en_3 cell_en_2 cell_en_1 cell_en_0 ptr_15 ptr_14 ptr_13 ptr_12 ptr_11 ptr_10 ptr_9 ptr_8 ptr_7 ptr_6 ptr_5 ptr_4 ptr_3 ptr_2 ptr_1 ptr_0
```

Critical syntax rules:

- Every Verilog-A DUT/support file used by the testbench must have a literal `ahdl_include "<file>.va"` line in the `.scs` artifact.
- Spectre AHDL instances use instance-first/module-last syntax: `XNAME (node1 node2 ...) module_name`.
- Do not use module-first syntax such as `module_name instance_name (...)`.
- Keep saved names as plain scalar public observables, not instance-qualified aliases.

## Public Behavior Checks

- `pointer_advances_by_sampled_input_code`
- `cell_enable_window_matches_effective_code_plus_lsb_boundary`
- `pointer_output_is_one_hot`
- `wraparound_and_multi_code_coverage`

## Public L1 Testbench Stimulus Contract

This TB row should exercise DWA pointer motion and cell-enable coverage:

- Drive `clk_i` as a periodic 0 V/0.9 V clock and release `rst_ni` before the
  useful samples.
- Drive `code_3..code_0` through several stable nonzero input codes, including
  values large enough to advance the pointer by more than one cell.
- Include enough samples for pointer wraparound to become visible.
- Hold each input code stable around the clock edge that samples it.
- Save the clock/reset, input code bits, pointer bits, and cell-enable bits
  exactly as public scalar waveforms.

The expected public relation is: sampled input code controls how far the DWA
pointer advances, while the cell-enable window matches the active unit cells.
Do not generate checker logic.

## Output Contract

Return exactly one source artifact named `tb_dwa_ptr_gen_ref.scs`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

## DWA/DEM encoder testbench companion

Write a Spectre transient testbench for the `DWA/DEM encoder` behavioral
Verilog-A release task. This is the testbench-generation companion for an
already materialized end-to-end task.

The testbench should instantiate the same behavioral DUT or system module used
by the corresponding end-to-end form, drive the public transient scenario, save
the observable waveform or metric signals, and preserve the EVAS/Spectre
validation contract.

Domain: pure voltage-domain behavioral Verilog-A.

Public requirements:

- include a transient `tran` analysis
- save the public observables needed by the checker
- include or instantiate the Verilog-A behavioral module under test
- avoid transistor-level devices, AC/noise analysis, and current-domain
  solver assumptions
