# Coarse QTZ 3bit Residue Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Coarse QTZ 3bit Residue` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `coarse_qtz_3bit_residue.va`:
  - Module `coarse_qtz_3bit_residue` (entry)
    - position 0: `vin` (input, electrical)
    - position 1: `d0` (output, electrical)
    - position 2: `d1` (output, electrical)
    - position 3: `d2` (output, electrical)
    - position 4: `vres` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/coarse_qtz_3bit_residue.va`
- DUT instance: `XDUT (vin d0 d1 d2 vres) coarse_qtz_3bit_residue`
- Required saved public traces: `d0`, `d1`, `d2`, `vin`, `vres`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `coarse_qtz_3bit_residue.vref` defaults to `1.0`; valid range: finite; overrides vref.
- `coarse_qtz_3bit_residue.vdd` defaults to `1.0`; valid range: finite; overrides vdd.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_CLIP_VIN_TO_THE_RANGE_FROM`: exercise and make observable: Clip `vin` to the range from `-vref` to `+vref`. Required traces: `time`, `d0`, `d1`, `d2`, `vin`, `vres`.
- `P_QUANTIZE_THE_CLIPPED_VALUE_INTO_EIGHT`: exercise and make observable: Quantize the clipped value into eight 3-bit codes using round-to-nearest behavior. Required traces: `time`, `d0`, `d1`, `d2`, `vin`, `vres`.
- `P_SATURATE_THE_CODE_AT_THE_ENDPOINTS`: exercise and make observable: Saturate the code at the endpoints. Required traces: `time`, `d0`, `d1`, `d2`, `vin`, `vres`.
- `P_USE_UNIFORMLY_SPACED_QUANTIZATION_LEVELS_START`: exercise and make observable: Use uniformly spaced quantization levels starting at `-vref`, with one LSB equal to one eighth of the full input span. Required traces: `time`, `d0`, `d1`, `d2`, `vin`, `vres`.
- `P_DRIVE_D0_D1_AND_D2_AS`: exercise and make observable: Drive `d0`, `d1`, and `d2` as LSB-to-MSB voltage-coded bits. Required traces: `time`, `d0`, `d1`, `d2`, `vin`, `vres`.
- `P_DRIVE_VRES_AS_THE_CLIPPED_INPUT`: exercise and make observable: Drive `vres` as the clipped input minus the selected quantized analog level. Required traces: `time`, `d0`, `d1`, `d2`, `vin`, `vres`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- Clip `vin` to the range from `-vref` to `+vref`.
- Quantize the clipped value into eight 3-bit codes using round-to-nearest behavior.
- Saturate the code at the endpoints.
- Use uniformly spaced quantization levels starting at `-vref`, with one LSB equal to one eighth of the full input span.
- Drive `d0`, `d1`, and `d2` as LSB-to-MSB voltage-coded bits.
- Drive `vres` as the clipped input minus the selected quantized analog level.


The required trace names are: `time`, `d0`, `d1`, `d2`, `vin`, `vres`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
