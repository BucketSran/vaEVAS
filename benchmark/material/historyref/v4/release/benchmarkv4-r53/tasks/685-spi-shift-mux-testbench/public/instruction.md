# SPI Shift Mux Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `SPI Shift Mux` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `spi_shift_mux.va`:
  - Module `spi_shift_mux` (entry)
    - position 0: `scki` (input, electrical)
    - position 1: `sdi` (input, electrical)
    - position 2: `rst` (input, electrical)
    - position 3: `out0` (output, electrical)
    - position 4: `out1` (output, electrical)
    - position 5: `out2` (output, electrical)
    - position 6: `out3` (output, electrical)
    - position 7: `out4` (output, electrical)
    - position 8: `out5` (output, electrical)
    - position 9: `out6` (output, electrical)
    - position 10: `out7` (output, electrical)
    - position 11: `sdo` (output, electrical)
    - position 12: `scko` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/spi_shift_mux.va`
- DUT instance: `XDUT (scki sdi rst out0 out1 out2 out3 out4 out5 out6 out7 sdo scko) spi_shift_mux`
- Required saved public traces: `out0`, `out1`, `out2`, `out3`, `out4`, `out5`, `out6`, `out7`, `rst`, `scki`, `scko`, `sdi`, `sdo`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- No public parameter is declared.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RESET_LOADS_DEFAULT_WORD`: exercise and make observable: Initialization and active-high `rst` load the 8-bit word `10110010` with `out7` as the leftmost bit and `out0` as the rightmost bit. Required traces: `time`, `out0`, `out1`, `out2`, `out3`, `out4`, `out5`, `out6`, `out7`, `rst`, `scki`, `scko`, `sdi`, `sdo`.
- `P_SHIFT_ON_SCKI_TRANSITIONS`: exercise and make observable: While reset is inactive, every `scki` transition shifts the register exactly once. Required traces: `time`, `out0`, `out1`, `out2`, `out3`, `out4`, `out5`, `out6`, `out7`, `rst`, `scki`, `scko`, `sdi`, `sdo`.
- `P_SHIFT_DIRECTION_AND_SDI_INSERTION`: exercise and make observable: The shift moves bits toward higher output indexes and inserts `sdi` into the declared end of the register. Required traces: `time`, `out0`, `out1`, `out2`, `out3`, `out4`, `out5`, `out6`, `out7`, `rst`, `scki`, `scko`, `sdi`, `sdo`.
- `P_SDO_EXPOSES_SHIFTED_OUT_BIT`: exercise and make observable: `sdo` exposes the shifted-out `out7` bit rather than another register bit. Required traces: `time`, `out0`, `out1`, `out2`, `out3`, `out4`, `out5`, `out6`, `out7`, `rst`, `scki`, `scko`, `sdi`, `sdo`.
- `P_OUTPUT_RAIL_LEVELS`: exercise and make observable: The parallel outputs and `sdo` are voltage-coded at valid low/high levels. Required traces: `time`, `out0`, `out1`, `out2`, `out3`, `out4`, `out5`, `out6`, `out7`, `rst`, `scki`, `scko`, `sdi`, `sdo`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Initialize and reset the 8-bit configuration word to `10110010`, with the leftmost bit exposed on `out7` and `sdo` and the rightmost bit on `out0`. While `rst` is high, reload that word and block serial shifting. On each `scki` threshold crossing while reset is inactive, shift the word toward `out7`; sampled `sdi` enters `out0`. Drive `sdo` from the current `out7` bit and drive `scko` from the current `scki` logic state.


The required trace names are: `time`, `out0`, `out1`, `out2`, `out3`, `out4`, `out5`, `out6`, `out7`, `rst`, `scki`, `scko`, `sdi`, `sdo`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
