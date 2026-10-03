# LT Readout SAR4 Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `LT Readout SAR4` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `lt_readout_sar4.va`:
  - Module `lt_readout_sar4` (entry)
    - position 0: `d0` (input, electrical)
    - position 1: `d1` (input, electrical)
    - position 2: `d2` (input, electrical)
    - position 3: `d3` (input, electrical)
    - position 4: `vout` (output, electrical)
    - position 5: `gnd` (input, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/lt_readout_sar4.va`
- DUT instance: `XDUT (d0 d1 d2 d3 vout gnd) lt_readout_sar4`
- Required saved public traces: `d0`, `d1`, `d2`, `d3`, `gnd`, `vout`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `lt_readout_sar4.vth` defaults to `0.9`; valid range: finite; overrides vth.
- `lt_readout_sar4.vref` defaults to `1.8`; valid range: finite; overrides vref.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_CONTINUOUSLY_DECODE_D0_D3_AS_AN`: exercise and make observable: Continuously decode `d0..d3` as an unsigned binary code with `d0` as LSB and `d3` as MSB. Drive `vout` to the readout level `code * vref / 16`. The output should update when the voltage-coded input bits cross the threshold. Required traces: `time`, `d0`, `d1`, `d2`, `d3`, `gnd`, `vout`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Continuously decode `d0..d3` as an unsigned binary code with `d0` as LSB and `d3` as MSB. Drive `vout` to the readout level `code * vref / 16`. The output should update when the voltage-coded input bits cross the threshold.


The required trace names are: `time`, `d0`, `d1`, `d2`, `d3`, `gnd`, `vout`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
