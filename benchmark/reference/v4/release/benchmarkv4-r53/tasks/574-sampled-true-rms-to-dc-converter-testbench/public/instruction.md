# Sampled True-RMS-to-DC Converter Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Sampled True-RMS-to-DC Converter` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `sampled_true_rms_to_dc.va`:
  - Module `sampled_true_rms_to_dc` (entry)
    - position 0: `vinp` (input, electrical)
    - position 1: `vinn` (input, electrical)
    - position 2: `clk` (input, electrical)
    - position 3: `reset` (input, electrical)
    - position 4: `enable` (input, electrical)
    - position 5: `rms_out` (output, electrical)
    - position 6: `valid` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/sampled_true_rms_to_dc.va`
- DUT instance: `XDUT (vinp vinn clk reset enable rms_out valid) sampled_true_rms_to_dc`
- Required saved public traces: `vinp`, `vinn`, `clk`, `reset`, `enable`, `rms_out`, `valid`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `sampled_true_rms_to_dc.vth` defaults to `0.45` V; valid range: finite; sets the logic threshold.
- `sampled_true_rms_to_dc.vhigh` defaults to `0.9` V; valid range: vhigh > vth; sets valid logic high.
- `sampled_true_rms_to_dc.tr` defaults to `1e-10` s; valid range: tr > 0; sets output smoothing.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_DIFFERENTIAL_RMS`: exercise and make observable: rms_out equals sqrt(mean((vinp-vinn)^2)) for each completed window. Required traces: `time`, `vinp`, `vinn`, `clk`, `reset`, `enable`, `rms_out`, `valid`.
- `P_FOUR_SAMPLE_WINDOW`: exercise and make observable: Exactly four enabled rising-edge samples form each non-overlapping result window. Required traces: `time`, `vinp`, `vinn`, `clk`, `reset`, `enable`, `rms_out`, `valid`.
- `P_ENABLE_FREEZE`: exercise and make observable: Disabled clock edges preserve partial accumulation and rms_out while deasserting valid. Required traces: `time`, `clk`, `enable`, `rms_out`, `valid`.
- `P_ASYNC_RESET`: exercise and make observable: Active-high reset asynchronously clears partial state and both outputs. Required traces: `time`, `clk`, `reset`, `rms_out`, `valid`.
- `P_VALID_PULSE`: exercise and make observable: valid is high for one sampling interval after each completed window. Required traces: `time`, `clk`, `valid`.
- `P_OUTPUT_HOLD`: exercise and make observable: rms_out holds between completed windows. Required traces: `time`, `clk`, `rms_out`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


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


The required trace names are: `time`, `vinp`, `vinn`, `clk`, `reset`, `enable`, `rms_out`, `valid`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
