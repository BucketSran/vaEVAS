# Trim Ctrl 4bit Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Trim Ctrl 4bit` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `trim_ctrl_4bit.va`:
  - Module `trim_ctrl_4bit` (entry)
    - position 0: `ain` (input, electrical)
    - position 1: `dout0` (output, electrical)
    - position 2: `dout1` (output, electrical)
    - position 3: `dout2` (output, electrical)
    - position 4: `dout3` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/trim_ctrl_4bit.va`
- DUT instance: `XDUT (ain dout0 dout1 dout2 dout3) trim_ctrl_4bit`
- Required saved public traces: `ain`, `dout0`, `dout1`, `dout2`, `dout3`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- No public parameter is declared.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_ANALOG_INPUT_ROUNDING`: exercise and make observable: Round `ain` to the nearest integer code level rather than truncating. Required traces: `time`, `ain`, `dout0`, `dout1`, `dout2`, `dout3`.
- `P_LOW_FOUR_BIT_MAPPING`: exercise and make observable: Emit the low four bits of the rounded code on `dout0..dout3` in the declared bit order. Required traces: `time`, `ain`, `dout0`, `dout1`, `dout2`, `dout3`.
- `P_CONTINUOUS_CODE_UPDATE`: exercise and make observable: Update deterministically as `ain` changes without requiring hidden state or clocks. Required traces: `time`, `ain`, `dout0`, `dout1`, `dout2`, `dout3`.
- `P_TRIM_OUTPUT_LEVELS`: exercise and make observable: All trim outputs are voltage-coded at valid low/high levels. Required traces: `time`, `ain`, `dout0`, `dout1`, `dout2`, `dout3`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Round nonnegative `ain` to the nearest integer code level, with exact half-code values rounding upward. Emit the rounded code modulo 16 on `dout0..dout3`, so rounded codes 16 through 31 wrap once onto output codes 0 through 15. Update deterministically as `ain` changes and keep the output voltage-coded rather than current-domain.


The required trace names are: `time`, `ain`, `dout0`, `dout1`, `dout2`, `dout3`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
