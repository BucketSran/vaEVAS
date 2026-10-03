# Cyclic Decoder 12bit Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Cyclic Decoder 12bit` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `cyclic_decoder_12bit.va`:
  - Module `cyclic_decoder_12bit` (entry)
    - position 0: `d0` (input, electrical)
    - position 1: `d1` (input, electrical)
    - position 2: `d2` (input, electrical)
    - position 3: `d3` (input, electrical)
    - position 4: `d4` (input, electrical)
    - position 5: `d5` (input, electrical)
    - position 6: `d6` (input, electrical)
    - position 7: `d7` (input, electrical)
    - position 8: `d8` (input, electrical)
    - position 9: `d9` (input, electrical)
    - position 10: `d10` (input, electrical)
    - position 11: `d11` (input, electrical)
    - position 12: `clks` (input, electrical)
    - position 13: `dout` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/cyclic_decoder_12bit.va`
- DUT instance: `XDUT (d0 d1 d2 d3 d4 d5 d6 d7 d8 d9 d10 d11 clks dout) cyclic_decoder_12bit`
- Required saved public traces: `clks`, `d0`, `d1`, `d10`, `d11`, `d2`, `d3`, `d4`, `d5`, `d6`, `d7`, `d8`, `d9`, `dout`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `cyclic_decoder_12bit.vth` defaults to `0.55`; valid range: finite; overrides vth.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RISING_EDGE_12BIT_DECODE`: exercise and make observable: Each rising `clks` crossing samples the twelve voltage-coded bits into an unsigned code. Required traces: `time`, `clks`, `d0`, `d1`, `d10`, `d11`, `d2`, `d3`, `d4`, `d5`, `d6`, `d7`, `d8`, `d9`, `dout`.
- `P_BIT_WEIGHT_ORDER`: exercise and make observable: `d0` is the LSB and `d11` is the MSB in the decoded code. Required traces: `time`, `clks`, `d0`, `d1`, `d10`, `d11`, `d2`, `d3`, `d4`, `d5`, `d6`, `d7`, `d8`, `d9`, `dout`.
- `P_CENTERED_OUTPUT_SCALE`: exercise and make observable: The decoded value is normalized to the full 12-bit range, shifted by the half-scale midpoint, and held on `dout`. Required traces: `time`, `clks`, `d0`, `d1`, `d10`, `d11`, `d2`, `d3`, `d4`, `d5`, `d6`, `d7`, `d8`, `d9`, `dout`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

On each rising crossing of `clks` through `vth`, decode `d0` as the LSB and `d11` as the MSB of a 12-bit unsigned code. Normalize the code to the full 12-bit range and subtract 0.5 before driving `dout`.


The required trace names are: `time`, `clks`, `d0`, `d1`, `d10`, `d11`, `d2`, `d3`, `d4`, `d5`, `d6`, `d7`, `d8`, `d9`, `dout`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
