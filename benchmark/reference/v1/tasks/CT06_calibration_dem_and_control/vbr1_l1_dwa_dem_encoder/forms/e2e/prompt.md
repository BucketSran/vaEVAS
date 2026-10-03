# Task: vbr1_l1_dwa_dem_encoder:e2e

## Release Task Contract

- Form: `e2e`
- Level: `L1`
- Category: Calibration, DEM, and Control
- Base function: DWA/DEM encoder
- Domain: `voltage`
- Target artifact(s): `dwa_ptr_gen.va`, `tb_dwa_ptr_gen_ref.scs`, `v2b_4b.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Generate all target artifacts: `dwa_ptr_gen.va`, `tb_dwa_ptr_gen_ref.scs`, `v2b_4b.va`.
- The Spectre testbench must exercise the generated DUT/system through public observables; do not generate hidden checker logic.
- The generated Verilog-A file(s) `dwa_ptr_gen.va`, `v2b_4b.va` must be co-located with the generated Spectre testbench.
- Include each generated Verilog-A file exactly with a matching `ahdl_include "<file>.va"` line in the generated testbench.
- Use Spectre AHDL instance syntax with the instance name first and module name last: `XNAME (node1 node2 ...) module_name`.
- Never write module-first syntax such as `module_name instance_name (...)`; that is not the release Spectre testbench syntax.

## Public Verilog-A Interface

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

## Output Contract

Return exactly these source artifacts:

- `dwa_ptr_gen.va`
- `tb_dwa_ptr_gen_ref.scs`
- `v2b_4b.va`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

Write a Verilog-A module named `dwa_ptr_gen` and one minimal EVAS-compatible Spectre testbench.

## DWA/DEM encoder end-to-end

## Objective

Create a pure voltage-domain Data Weighted Averaging (DWA) pointer generator. The testbench must
drive several input codes and expose a rotating 16-cell pointer and cell-enable window.

## DUT Contract

- Main module name: `dwa_ptr_gen`
- If you create an analog-to-4-bit helper module, name it `v2b_4b`.
- Ports, all `electrical`, exactly in this order:
  - Inputs: `clk_i`, `rst_ni`, `code_msb_i[3:0]`
  - Outputs: `cell_en_o[15:0]`, `ptr_o[15:0]`
- Parameters:
  - `vdd` real, default `0.9`
  - `vth` real, default `0.45`
  - `ptr_init` integer, default `0`
- Behavior:
  - Reset is active-low.
  - On reset, initialize the one-hot pointer to `ptr_init`.
  - On each rising `clk_i` edge after reset, decode the 4-bit input code and update:
    - `new_ptr = (old_ptr + code) % 16`
  - `ptr_o[*]` must be one-hot at the current pointer.
  - `cell_en_o[*]` must assert at least one selected cell after reset and represent the selected DWA window.
  - Use `@(cross(V(clk_i) - vth, +1))` and `transition(...)`.
  - Do not use current contributions, `ddt()`, or `idt()`.

## Testbench Contract

- Use a 0.9 V supply and 0 V reference.
- Generate a 100 MHz-class `clk_i` pulse clock and active-low `rst_ni` that deasserts early enough to leave several post-reset clock edges.
- Drive a sequence of 4-bit input codes that exercises pointer movement over multiple cells.
- If using `v2b_4b`, expose scalar code nodes `code_3`, `code_2`, `code_1`, `code_0`.
- Instantiate the DWA DUT by positional scalar ports.
- Save these exact scalar names:
  - `clk_i`, `rst_ni`
  - `cell_en_15` through `cell_en_0`
  - `ptr_15` through `ptr_0`

## Observable CSV Contract

The waveform CSV must expose the exact scalar names listed above. If the DUT uses vector ports
internally, the testbench must connect or save every bit as a scalar node.
