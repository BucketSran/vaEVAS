# Sampled True-RMS-to-DC Converter Bugfix

## Task Contract

The supplied Verilog-A system violates its public circuit contract. Repair the
complete editable bundle.

## Public Verilog-A Interface

Preserve this exact artifact and module interface:

- Artifact `sampled_true_rms_to_dc.va`:
  - Module `sampled_true_rms_to_dc` (entry)
    - position 0: `vinp` (input, electrical)
    - position 1: `vinn` (input, electrical)
    - position 2: `clk` (input, electrical)
    - position 3: `reset` (input, electrical)
    - position 4: `enable` (input, electrical)
    - position 5: `rms_out` (output, electrical)
    - position 6: `valid` (output, electrical)

## Public Parameter Contract

- `sampled_true_rms_to_dc.vth` defaults to `0.45` V; valid range: finite; sets the logic threshold.
- `sampled_true_rms_to_dc.vhigh` defaults to `0.9` V; valid range: vhigh > vth; sets valid logic high.
- `sampled_true_rms_to_dc.tr` defaults to `1e-10` s; valid range: tr > 0; sets output smoothing.


## Required Behavior

The repaired bundle must satisfy every public property:

- `P_DIFFERENTIAL_RMS`: restore: rms_out equals sqrt(mean((vinp-vinn)^2)) for each completed window. Required traces: `time`, `vinp`, `vinn`, `clk`, `reset`, `enable`, `rms_out`, `valid`.
- `P_FOUR_SAMPLE_WINDOW`: restore: Exactly four enabled rising-edge samples form each non-overlapping result window. Required traces: `time`, `vinp`, `vinn`, `clk`, `reset`, `enable`, `rms_out`, `valid`.
- `P_ENABLE_FREEZE`: restore: Disabled clock edges preserve partial accumulation and rms_out while deasserting valid. Required traces: `time`, `clk`, `enable`, `rms_out`, `valid`.
- `P_ASYNC_RESET`: restore: Active-high reset asynchronously clears partial state and both outputs. Required traces: `time`, `clk`, `reset`, `rms_out`, `valid`.
- `P_VALID_PULSE`: restore: valid is high for one sampling interval after each completed window. Required traces: `time`, `clk`, `valid`.
- `P_OUTPUT_HOLD`: restore: rms_out holds between completed windows. Required traces: `time`, `clk`, `rms_out`.


The following canonical public behavior is normative for this derived form:

- On each rising `clk` crossing, accept `V(vinp,vinn)` only when `reset` is low
  and `enable` is high.
- Accumulate the square of each accepted sample. On the fourth accepted sample,
  update `rms_out` to `sqrt(sum(sample^2)/4)` and start a new empty window.
- Disabled clock edges do not advance or clear a partial window. They hold
  `rms_out` and deassert `valid`.
- `valid` is asserted for one sampling interval when a four-sample window
  completes, then deasserted at the next rising clock edge.
- Between update events, both outputs hold their state.
- A rising `reset` asynchronously clears the partial window, drives `rms_out`
  to `0 V`, and deasserts `valid`. While reset is high, clock edges keep the
  converter cleared.


## Modeling Constraints

- Use rising clock crossings and differential voltage samples.
- Use non-overlapping four-sample true-RMS windows.
- Do not use file I/O or hidden state outputs.
- Preserve the exact file set, module graph, ports, parameters, and public traces.
- Do not add debug outputs, validation state, side channels, or stimulus-specific fixes.

## Output Contract

Return the repaired bundle with exactly these paths: `sampled_true_rms_to_dc.va`.
Every supplied `.va` file is editable; do not add or omit files.
