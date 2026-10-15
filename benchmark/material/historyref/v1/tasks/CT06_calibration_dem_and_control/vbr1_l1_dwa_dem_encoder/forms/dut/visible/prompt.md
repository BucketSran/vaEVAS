# Task: vbr1_l1_dwa_dem_encoder:dut

## Release Task Contract

- Form: `dut`
- Level: `L1`
- Category: Calibration, DEM, and Control
- Base function: DWA/DEM encoder
- Domain: `voltage`
- Target artifact(s): `dwa_ptr_gen.va`, `v2b_4b.va`
- Supplied/reference support artifact(s): `tb_dwa_ptr_gen_ref.scs`
- Visible context: public task, interface, artifact, stimulus, and observable contract only.
- Hidden evaluator boundary: deterministic checker and EVAS/Spectre validation are external; do not generate checker logic.

## Form-Specific Requirements

- Implement only the requested Verilog-A DUT artifact(s); do not generate a Spectre testbench in this form.
- Preserve the public module names, port order, parameters, and waveform observable names.

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

## Public Behavior Checks

- `pointer_advances_by_sampled_input_code`
- `cell_enable_window_matches_effective_code_plus_lsb_boundary`
- `pointer_output_is_one_hot`
- `wraparound_and_multi_code_coverage`

## Output Contract

Return exactly these source artifacts:

- `dwa_ptr_gen.va`
- `v2b_4b.va`

Do not include explanatory prose outside the source artifact contents.

## Task-Specific Public Description

## DWA/DEM encoder DUT

Write the Verilog-A DUT artifact(s) for `DWA/DEM encoder`.

This is a function-checked DUT task, not a generic companion wrapper. The
public contract below defines the exact module interface, voltage-domain
behavior, and waveform observables used by the release checker.

Domain: pure voltage-domain behavioral Verilog-A.

## Module Contract

- Declaration: `dwa_ptr_gen(clk_i, rst_ni, code_msb_i[3:0], cell_en_o[15:0], ptr_o[15:0])`

Ports:

- `clk_i`: input electrical clock
- `rst_ni`: input electrical active-low reset
- `code_msb_i[3:0]`: input electrical 4-bit code bus
- `cell_en_o[15:0]`: output electrical selected unit-element window
- `ptr_o[15:0]`: output electrical one-hot rotating pointer

## Behavioral Contract

- Treat `clk_i`, `rst_ni`, and each `code_msb_i` bit as 0/0.9 V logic using a 0.45 V threshold.
- Reset initializes the one-hot pointer to `ptr_init`.
- Decode `code_msb_i[3:0]` as an unsigned integer from 0 to 15.
- On each post-reset rising clock edge, sample the code and update `ptr_next = (ptr_prev + code) % 16`.
- Drive `ptr_o` as a one-hot output at `ptr_next`.
- Drive `cell_en_o` as the DWA selected-cell mask for that sampled code: assert the rotating MSB span ending at `ptr_next`, plus the LSB boundary cell at `lsb_idx = (ptr_next - code + 16) % 16`.
- Equivalently, for each cell index `j`, assert `cell_en_o[j]` when `((ptr_next - j + 16) % 16) < code` or `j == lsb_idx`; drive all other cells low.
- For code 0, only the LSB boundary cell is high.
- Expose vector bits as scalar waveform columns in the companion testbench.

## Public Evaluation Observables

The companion validation testbench saves these waveform columns:

- `clk_i`
- `rst_ni`
- `code_3..code_0`
- `cell_en_15..cell_en_0`
- `ptr_15..ptr_0`
