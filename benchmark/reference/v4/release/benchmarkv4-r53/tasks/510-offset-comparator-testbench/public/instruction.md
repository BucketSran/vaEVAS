# Offset Comparator Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Offset Comparator` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `cmp_offset_ref.va`:
  - Module `cmp_offset_ref` (entry)
    - position 0: `VDD` (input, electrical)
    - position 1: `VSS` (input, electrical)
    - position 2: `CLK` (input, electrical)
    - position 3: `VINP` (input, electrical)
    - position 4: `VINN` (input, electrical)
    - position 5: `OUT_P` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/cmp_offset_ref.va`
- DUT instance: `XDUT (VDD VSS CLK VINP VINN OUT_P) cmp_offset_ref`
- Required saved public traces: `VDD`, `VSS`, `CLK`, `VINP`, `VINN`, `OUT_P`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `cmp_offset_ref.vos` defaults to `0.005` V; valid range: vos >= 0; sets positive input-referred decision offset.
- `cmp_offset_ref.tt` defaults to `2e-11` s; valid range: tt > 0; sets output transition smoothing.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RISING_EDGE_SAMPLE`: exercise and make observable: OUT_P updates only on CLK rising crossings through the local rail midpoint. Required traces: `time`, `VDD`, `VSS`, `CLK`, `VINP`, `VINN`, `OUT_P`.
- `P_OFFSET_DECISION`: exercise and make observable: OUT_P latches high only when VINP relative to VINN is greater than the positive vos threshold. Required traces: `time`, `CLK`, `VINP`, `VINN`, `OUT_P`.
- `P_LATCH_HOLD`: exercise and make observable: OUT_P holds its sampled decision between rising clock edges. Required traces: `time`, `CLK`, `VINP`, `VINN`, `OUT_P`.
- `P_RAIL_REFERENCE`: exercise and make observable: OUT_P low and high levels track VSS and VDD respectively with finite smoothing. Required traces: `time`, `VDD`, `VSS`, `OUT_P`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- Initialize `OUT_P` low relative to `VSS`.
- On each rising crossing of `CLK` through the local rail midpoint, latch whether `V(VINP,VSS) - V(VINN,VSS)` is greater than `vos`.
- Drive `OUT_P` high to the `VDD` rail only for latched inputs above the positive offset threshold; otherwise drive it low to `VSS`.
- Hold the latched decision between rising clock edges, even if the input polarity changes between samples.
- Use smoothed rail-referenced voltage-domain output transitions.


The required trace names are: `time`, `VDD`, `VSS`, `CLK`, `VINP`, `VINN`, `OUT_P`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
