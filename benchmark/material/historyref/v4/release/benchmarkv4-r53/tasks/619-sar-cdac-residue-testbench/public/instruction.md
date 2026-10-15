# SAR CDAC Residue Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `SAR CDAC Residue` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `sar_cdac_residue.va`:
  - Module `sar_cdac_residue` (entry)
    - position 0: `VIN` (input, electrical)
    - position 1: `CLK` (input, electrical)
    - position 2: `S6` (input, electrical)
    - position 3: `S5` (input, electrical)
    - position 4: `S4` (input, electrical)
    - position 5: `S3` (input, electrical)
    - position 6: `S2` (input, electrical)
    - position 7: `S1` (input, electrical)
    - position 8: `VRES` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/sar_cdac_residue.va`
- DUT instance: `XDUT (vin clk s6 s5 s4 s3 s2 s1 vres) sar_cdac_residue`
- Required saved public traces: `vin`, `clk`, `s6`, `s5`, `s4`, `s3`, `s2`, `s1`, `vres`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `sar_cdac_residue.vdd` defaults to `0.9` V; valid range: vdd > 0; sets the rising CLK sampling threshold at one half of vdd.
- `sar_cdac_residue.vrefp` defaults to `0.9` V; valid range: vrefp > vrefn; sets the upper endpoint of the reference span used by all residue steps.
- `sar_cdac_residue.vrefn` defaults to `0.0` V; valid range: vrefn < vrefp; sets the lower endpoint of the reference span used by all residue steps.
- `sar_cdac_residue.tr` defaults to `1e-12` s; valid range: tr > 0; sets the transition time of the VRES voltage output.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_INPUT_SAMPLE`: exercise and make observable: At initial_step and each rising CLK crossing through vdd/2, the residue state samples VIN. Required traces: `time`, `vin`, `clk`, `vres`.
- `P_S6_HALF_ADD`: exercise and make observable: Each falling S6 crossing through vdd/2 adds one half of the public reference span to the current residue. Required traces: `time`, `s6`, `vres`.
- `P_BINARY_SUBTRACTIONS`: exercise and make observable: Rising crossings of S5, S4, S3, S2, and S1 through vdd/2 subtract one fourth, one eighth, one sixteenth, one thirty-second, and one sixty-fourth of the public reference span respectively. Required traces: `time`, `s5`, `s4`, `s3`, `s2`, `s1`, `vres`.
- `P_EDGE_POLARITY`: exercise and make observable: S6 updates only on falling vdd/2 threshold crossings, while S5 through S1 update only on rising vdd/2 threshold crossings. Required traces: `time`, `s6`, `s5`, `s4`, `s3`, `s2`, `s1`, `vres`.
- `P_ACCUMULATED_STATE`: exercise and make observable: Between declared sampling and switch events, VRES represents and holds the accumulated residue state. Required traces: `time`, `vin`, `clk`, `s6`, `s5`, `s4`, `s3`, `s2`, `s1`, `vres`.
- `P_OUTPUT_TRANSITION`: exercise and make observable: VRES changes from the residue state using the declared tr transition time. Required traces: `time`, `vres`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Sample `VIN` into the residue at `initial_step` and on each rising `CLK`
crossing at `vdd/2`. A falling `S6` crossing through `vdd/2` adds one half of
the reference span. Rising `S5`, `S4`, `S3`, `S2`, and `S1` crossings through
`vdd/2` subtract one fourth, one eighth, one sixteenth, one thirty-second, and
one sixty-fourth of the reference span respectively. Drive `VRES` from the
current residue state.


The required trace names are: `time`, `vin`, `clk`, `s6`, `s5`, `s4`, `s3`, `s2`, `s1`, `vres`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
