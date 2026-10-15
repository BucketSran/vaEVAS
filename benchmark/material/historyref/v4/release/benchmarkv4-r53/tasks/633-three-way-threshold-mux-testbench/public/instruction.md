# Three Way Threshold Mux Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Three Way Threshold Mux` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `three_way_threshold_mux.va`:
  - Module `three_way_threshold_mux` (entry)
    - position 0: `sigin1` (input, electrical)
    - position 1: `sigin2` (input, electrical)
    - position 2: `sigin3` (input, electrical)
    - position 3: `cntrlp` (input, electrical)
    - position 4: `cntrlm` (input, electrical)
    - position 5: `sigout` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/three_way_threshold_mux.va`
- DUT instance: `XDUT (sigin1 sigin2 sigin3 cntrlp cntrlm sigout) three_way_threshold_mux sigth_high=0.2 sigth_low=-0.2`
- Required saved public traces: `cntrlm`, `cntrlp`, `sigin1`, `sigin2`, `sigin3`, `sigout`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `three_way_threshold_mux.sigth_high` defaults to `1`; valid range: finite; overrides sigth_high.
- `three_way_threshold_mux.sigth_low` defaults to `-1`; valid range: finite; overrides sigth_low.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_DIFFERENTIAL_CONTROL`: exercise and make observable: Use `V(cntrlp, cntrlm)` as the mux control signal. Required traces: `time`, `cntrlp`, `cntrlm`, `sigout`.
- `P_LOW_REGION_SELECTS_SIGIN1`: exercise and make observable: When control is below `sigth_low`, drive `sigout` from `sigin1`. Required traces: `time`, `sigin1`, `cntrlp`, `cntrlm`, `sigout`.
- `P_MIDDLE_REGION_SELECTS_SIGIN2`: exercise and make observable: When control is in the inclusive window `[sigth_low, sigth_high]`, drive `sigout` from `sigin2`. Required traces: `time`, `sigin2`, `cntrlp`, `cntrlm`, `sigout`.
- `P_HIGH_REGION_SELECTS_SIGIN3`: exercise and make observable: When control is above `sigth_high`, drive `sigout` from `sigin3`. Required traces: `time`, `sigin3`, `cntrlp`, `cntrlm`, `sigout`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Use `V(cntrlp, cntrlm)` as the control signal. Select `sigin1` when the control is below `sigth_low`, select `sigin2` when it is inside the inclusive threshold window, and select `sigin3` when it is above `sigth_high`.


The required trace names are: `time`, `cntrlm`, `cntrlp`, `sigin1`, `sigin2`, `sigin3`, `sigout`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
