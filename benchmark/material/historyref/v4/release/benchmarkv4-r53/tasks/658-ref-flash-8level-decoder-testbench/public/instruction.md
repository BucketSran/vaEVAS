# Ref Flash 8level Decoder Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Ref Flash 8level Decoder` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `ref_flash_8level_decoder.va`:
  - Module `ref_flash_8level_decoder` (entry)
    - position 0: `vin` (input, electrical)
    - position 1: `dt0` (input, electrical)
    - position 2: `dt1` (input, electrical)
    - position 3: `dt2` (input, electrical)
    - position 4: `dt3` (input, electrical)
    - position 5: `dt4` (input, electrical)
    - position 6: `dt5` (input, electrical)
    - position 7: `dt6` (input, electrical)
    - position 8: `dt7` (input, electrical)
    - position 9: `clks` (input, electrical)
    - position 10: `dout` (output, electrical)
    - position 11: `vres` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/ref_flash_8level_decoder.va`
- DUT instance: `XDUT (vin dt0 dt1 dt2 dt3 dt4 dt5 dt6 dt7 clks dout vres) ref_flash_8level_decoder`
- Required saved public traces: `clks`, `dout`, `dt0`, `dt1`, `dt2`, `dt3`, `dt4`, `dt5`, `dt6`, `dt7`, `vin`, `vres`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `ref_flash_8level_decoder.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `ref_flash_8level_decoder.tt` defaults to `10p`; valid range: finite; overrides tt.
- `ref_flash_8level_decoder.vref` defaults to `1`; valid range: finite; overrides vref.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_CLOCKED_EIGHT_TAP_COUNT`: exercise and make observable: Each rising `clks` crossing counts all eight asserted flash taps into the held decoder count. Required traces: `time`, `clks`, `dout`, `dt0`, `dt1`, `dt2`, `dt3`, `dt4`, `dt5`, `dt6`, `dt7`, `vin`, `vres`.
- `P_RESIDUE_CENTERING`: exercise and make observable: `vres` subtracts the centered four-count flash estimate from the sampled input residue. Required traces: `time`, `clks`, `dout`, `dt0`, `dt1`, `dt2`, `dt3`, `dt4`, `dt5`, `dt6`, `dt7`, `vin`, `vres`.
- `P_OUTPUT_NORMALIZATION`: exercise and make observable: `dout` reports the tap count normalized by eight without extra output scaling. Required traces: `time`, `clks`, `dout`, `dt0`, `dt1`, `dt2`, `dt3`, `dt4`, `dt5`, `dt6`, `dt7`, `vin`, `vres`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

On each rising crossing of `clks` through `vth`, count the asserted flash taps. Drive `dout` with the count divided by eight. Drive `vres` with the sampled `vin` minus the centered tap count scaled by `vref/8`.


The required trace names are: `time`, `clks`, `dout`, `dt0`, `dt1`, `dt2`, `dt3`, `dt4`, `dt5`, `dt6`, `dt7`, `vin`, `vres`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
