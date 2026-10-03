# DC Aware ADC3bit Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `DC Aware ADC3bit` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `dc_aware_adc3bit.va`:
  - Module `dc_aware_adc3bit` (entry)
    - position 0: `vin` (input, electrical)
    - position 1: `d2` (output, electrical)
    - position 2: `d1` (output, electrical)
    - position 3: `d0` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/dc_aware_adc3bit.va`
- DUT instance: `XDUT (vin d2 d1 d0) dc_aware_adc3bit`
- Required saved public traces: `vin`, `d2`, `d1`, `d0`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `dc_aware_adc3bit.vref` defaults to `1` V; valid range: vref > 0; sets the analog full-scale reference and uniform quantization span.
- `dc_aware_adc3bit.vh` defaults to `0.9` V; valid range: vh > 0; sets the voltage-coded output high level.
- `dc_aware_adc3bit.tr` defaults to `2e-11` s; valid range: tr > 0; sets output transition smoothing.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_STATIC_CONVERSION`: exercise and make observable: The output code represents the current vin level without requiring a clock or prior transient event. Required traces: `time`, `vin`, `d2`, `d1`, `d0`.
- `P_UNIFORM_QUANTIZATION`: exercise and make observable: The 0-to-vref input span is divided into eight ordered uniform code regions producing unsigned codes 0 through 7. Required traces: `time`, `vin`, `d2`, `d1`, `d0`.
- `P_INPUT_CLIPPING`: exercise and make observable: Inputs at or below 0 V produce code 0, and inputs at or above vref produce code 7. Required traces: `time`, `vin`, `d2`, `d1`, `d0`.
- `P_BINARY_BIT_ORDER`: exercise and make observable: d2 is the most significant output bit and d0 is the least significant output bit. Required traces: `time`, `d2`, `d1`, `d0`.
- `P_OUTPUT_LEVELS`: exercise and make observable: Each output bit approaches 0 V for logic low and vh for logic high with finite transition smoothing. Required traces: `time`, `d2`, `d1`, `d0`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Model a static, analysis-friendly three-bit ADC. Clip `vin` to the 0-to-`vref`
range, quantize the clipped value into eight uniform output codes, and drive
`d2..d0` as the binary representation of that code. The conversion is
combinational/static rather than clocked: the output word should represent the
current input level after transition smoothing, including at the beginning of a
transient run.


The required trace names are: `time`, `vin`, `d2`, `d1`, `d0`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
