# DWA DEM Encoder Bugfix

## Task Contract

The supplied Verilog-A system violates its public circuit contract. Repair the
complete editable bundle.

## Public Verilog-A Interface

Preserve this exact artifact and module interface:

- Artifact `dwa_ptr_gen.va`:
  - Module `dwa_ptr_gen` (entry)
    - position 0: `clk_i` (input, electrical)
    - position 1: `rst_ni` (input, electrical)
    - position 2: `code_msb_i[3:0]` (input, electrical)
    - position 3: `cell_en_o[15:0]` (output, electrical)
    - position 4: `ptr_o[15:0]` (output, electrical)
- Artifact `v2b_4b.va`:
  - Module `v2b_4b` (entry)
    - position 0: `clk` (input, electrical)
    - position 1: `vin` (input, electrical)
    - position 2: `out_3` (output, electrical)
    - position 3: `out_2` (output, electrical)
    - position 4: `out_1` (output, electrical)
    - position 5: `out_0` (output, electrical)

## Public Parameter Contract

- `dwa_ptr_gen.vdd` defaults to `0.9` V; valid range: vdd > 0; sets logic-high output level.
- `dwa_ptr_gen.vth` defaults to `0.45` V; valid range: 0 < vth < vdd; sets input logic threshold.
- `dwa_ptr_gen.ptr_init` defaults to `0` index; valid range: 0 <= ptr_init <= 15; sets reset pointer position in the circular element array.
- `v2b_4b.vdd` defaults to `0.9` V; valid range: vdd > 0; sets output high level and twice the clock threshold.
- `v2b_4b.tedge` defaults to `1e-10` s; valid range: tedge > 0; sets output-bit transition smoothing.


## Required Behavior

The repaired bundle must satisfy every public property:

- `P_V2B_ROUND_AND_CLAMP`: restore: On each rising helper clock crossing, vin rounds to the nearest integer and clamps to a four-bit code from 0 through 15. Required traces: `time`, `clk_i`, `vin_node`, `code_3`, `code_2`, `code_1`, `code_0`.
- `P_ACTIVE_LOW_RESET_POINTER`: restore: A sampled active-low reset initializes ptr to the one-hot ptr_init position. Required traces: `time`, `clk_i`, `rst_ni`, `ptr_15`, `ptr_14`, `ptr_13`, `ptr_12`, `ptr_11`, `ptr_10`, `ptr_9`, `ptr_8`, `ptr_7`, `ptr_6`, `ptr_5`, `ptr_4`, `ptr_3`, `ptr_2`, `ptr_1`, `ptr_0`.
- `P_ROTATING_POINTER_UPDATE`: restore: Each post-reset rising edge advances the circular pointer by the sampled unsigned code modulo 16. Required traces: `time`, `clk_i`, `rst_ni`, `code_3`, `code_2`, `code_1`, `code_0`, `ptr_15`, `ptr_14`, `ptr_13`, `ptr_12`, `ptr_11`, `ptr_10`, `ptr_9`, `ptr_8`, `ptr_7`, `ptr_6`, `ptr_5`, `ptr_4`, `ptr_3`, `ptr_2`, `ptr_1`, `ptr_0`.
- `P_POINTER_ONE_HOT`: restore: Ptr remains exactly one-hot at the updated circular pointer position. Required traces: `time`, `ptr_15`, `ptr_14`, `ptr_13`, `ptr_12`, `ptr_11`, `ptr_10`, `ptr_9`, `ptr_8`, `ptr_7`, `ptr_6`, `ptr_5`, `ptr_4`, `ptr_3`, `ptr_2`, `ptr_1`, `ptr_0`.
- `P_DWA_SELECTED_MASK`: restore: Cell_en implements the public rotating span and LSB boundary-cell rule for the sampled code, including the code-zero boundary-cell case. Required traces: `time`, `code_3`, `code_2`, `code_1`, `code_0`, `cell_en_15`, `cell_en_14`, `cell_en_13`, `cell_en_12`, `cell_en_11`, `cell_en_10`, `cell_en_9`, `cell_en_8`, `cell_en_7`, `cell_en_6`, `cell_en_5`, `cell_en_4`, `cell_en_3`, `cell_en_2`, `cell_en_1`, `cell_en_0`, `ptr_15`, `ptr_14`, `ptr_13`, `ptr_12`, `ptr_11`, `ptr_10`, `ptr_9`, `ptr_8`, `ptr_7`, `ptr_6`, `ptr_5`, `ptr_4`, `ptr_3`, `ptr_2`, `ptr_1`, `ptr_0`.
- `P_SYSTEM_CODE_BINDING`: restore: The four helper outputs feed the DWA code bus in MSB-to-LSB order without bit reversal. Required traces: `time`, `vin_node`, `code_3`, `code_2`, `code_1`, `code_0`, `cell_en_15`, `cell_en_14`, `cell_en_13`, `cell_en_12`, `cell_en_11`, `cell_en_10`, `cell_en_9`, `cell_en_8`, `cell_en_7`, `cell_en_6`, `cell_en_5`, `cell_en_4`, `cell_en_3`, `cell_en_2`, `cell_en_1`, `cell_en_0`, `ptr_15`, `ptr_14`, `ptr_13`, `ptr_12`, `ptr_11`, `ptr_10`, `ptr_9`, `ptr_8`, `ptr_7`, `ptr_6`, `ptr_5`, `ptr_4`, `ptr_3`, `ptr_2`, `ptr_1`, `ptr_0`.


The following canonical public behavior is normative for this derived form:

For `dwa_ptr_gen`:

- Treat `clk_i`, `rst_ni`, and each `code_msb_i` bit as voltage-coded logic using threshold `vth`.
- Reset initializes the one-hot pointer to `ptr_init`.
- Decode `code_msb_i[3:0]` as an unsigned integer from 0 to 15.
- On each post-reset rising clock edge, sample the code and update `ptr_next = (ptr_prev + code) % 16`.
- Drive `ptr_o` as a one-hot output at `ptr_next`.
- Drive `cell_en_o` as the DWA selected-cell mask for that sampled code: assert the rotating MSB span ending at `ptr_next`, plus the LSB boundary cell at `lsb_idx = (ptr_next - code + 16) % 16`.
- Equivalently, for each cell index `j`, assert `cell_en_o[j]` when `((ptr_next - j + 16) % 16) < code` or `j == lsb_idx`; drive all other cells low.
- For code 0, only the LSB boundary cell is high.

For `v2b_4b`:

- Treat `clk` as voltage-coded logic with a threshold of `0.5 * vdd`.
- On each rising `clk` crossing, convert `V(vin)` to the nearest integer code using `floor(V(vin) + 0.5)`.
- Clamp the code to the 0 to 15 range.
- Drive `out_3..out_0` as a 4-bit binary code with `out_3` as the most significant bit.


## Modeling Constraints

- Keep both public source files and both public module interfaces; the helper-to-encoder connection is part of the system binding.
- Use voltage contributions and event-driven sampled state only.
- Do not use current contributions, ddt(), idt(), debug strobes, pass/fail ports, or simulator-specific side channels.
- Preserve the exact file set, module graph, ports, parameters, and public traces.
- Do not add debug outputs, validation state, side channels, or stimulus-specific fixes.

## Output Contract

Return the repaired bundle with exactly these paths: `dwa_ptr_gen.va`, `v2b_4b.va`.
Every supplied `.va` file is editable; do not add or omit files.
