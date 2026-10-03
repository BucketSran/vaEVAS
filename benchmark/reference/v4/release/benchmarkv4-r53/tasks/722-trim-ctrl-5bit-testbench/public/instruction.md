# Trim Ctrl 5bit Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Trim Ctrl 5bit` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `trim_ctrl_5bit.va`:
  - Module `trim_ctrl_5bit` (entry)
    - position 0: `ain` (input, electrical)
    - position 1: `dout0` (output, electrical)
    - position 2: `dout1` (output, electrical)
    - position 3: `dout2` (output, electrical)
    - position 4: `dout3` (output, electrical)
    - position 5: `dout4` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/trim_ctrl_5bit.va`
- DUT instance: `XDUT (ain dout0 dout1 dout2 dout3 dout4) trim_ctrl_5bit`
- Required saved public traces: `ain`, `dout0`, `dout1`, `dout2`, `dout3`, `dout4`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `trim_ctrl_5bit.vh` defaults to `0.9`; valid range: finite; overrides vh.
- `trim_ctrl_5bit.tr` defaults to `20p`; valid range: finite; overrides tr.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_CONVERT_V_AIN_TO_THE_NEAREST`: exercise and make observable: Convert `V(ain)` to the nearest integer code using half-up rounding. Required traces: `time`, `ain`, `dout0`, `dout1`, `dout2`, `dout3`, `dout4`.
- `P_CLAMP_THE_CODE_TO_THE_VALID`: exercise and make observable: Clamp the code to the valid 5-bit trim range `0..31`. Required traces: `time`, `ain`, `dout0`, `dout1`, `dout2`, `dout3`, `dout4`.
- `P_DRIVE_DOUT0_DOUT4_FROM_THE_CLAMPED`: exercise and make observable: Drive `dout0..dout4` from the clamped binary code, LSB first. Required traces: `time`, `ain`, `dout0`, `dout1`, `dout2`, `dout3`, `dout4`.
- `P_DRIVE_HIGH_BITS_NEAR_VH_AND`: exercise and make observable: Drive high bits near `vh` and low bits near 0 V. Required traces: `time`, `ain`, `dout0`, `dout1`, `dout2`, `dout3`, `dout4`.
- `P_UPDATE_DETERMINISTICALLY_AS_THE_ANALOG_INPUT`: exercise and make observable: Update deterministically as the analog input changes. Required traces: `time`, `ain`, `dout0`, `dout1`, `dout2`, `dout3`, `dout4`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- Convert `V(ain)` to the nearest integer code using half-up rounding.
- Clamp the code to the valid 5-bit trim range `0..31`.
- Drive `dout0..dout4` from the clamped binary code, LSB first.
- Drive high bits near `vh` and low bits near 0 V.
- Update deterministically as the analog input changes.


The required trace names are: `time`, `ain`, `dout0`, `dout1`, `dout2`, `dout3`, `dout4`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
