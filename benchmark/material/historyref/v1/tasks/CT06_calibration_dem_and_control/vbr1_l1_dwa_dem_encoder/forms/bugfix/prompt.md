# Task: vbr1_l1_dwa_dem_encoder:bugfix

## Release Task Contract

- Form: `bugfix`
- Level: `L1`
- Category: Calibration, DEM, and Control
- Base function: DWA/DEM encoder
- Domain: `voltage`
- Target artifact(s): `dut_fixed.va`
- Supplied/reference support artifact(s): `dut_buggy.va`, `tb_dwa_ptr_gen_ref.scs`, `v2b_4b.va`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Repair the supplied buggy Verilog-A artifact while preserving the public module interface and artifact boundary.
- Use the buggy source plus the public intended behavior below; do not change the companion testbench contract.

## Public Interface To Preserve

- `dut_buggy.va` declares module `dwa_ptr_gen` with positional ports: `clk_i`, `rst_ni`, `code_msb_i`, `cell_en_o`, `ptr_o`.
- `dut_fixed.va` declares module `dwa_ptr_gen` with positional ports: `clk_i`, `rst_ni`, `code_msb_i`, `cell_en_o`, `ptr_o`.
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

## Public Behavior Checks

- `pointer_advances_by_sampled_input_code`
- `cell_enable_window_matches_effective_code_plus_lsb_boundary`
- `pointer_output_is_one_hot`
- `wraparound_and_multi_code_coverage`

## Observed Mismatch Framing

The supplied buggy artifact violates one or more public behavior checks above under the release validation testbench.
Repair the observable behavior without renaming modules, changing ports, or weakening the public testbench contract.

## Output Contract

Return exactly one source artifact named `dut_fixed.va`.
Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

## DWA/DEM encoder bugfix

Repair the supplied buggy Verilog-A implementation for `DWA/DEM encoder`.

The fixed implementation must preserve the public module name and ports used by
the reference Spectre testbench. Domain: pure voltage-domain behavioral
Verilog-A. Do not use current contributions, transistor-level devices,
AC/noise analysis, or KCL/KVL solving assumptions.
