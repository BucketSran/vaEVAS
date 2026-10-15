# LNA Gain Compression Macro Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `LNA Gain Compression Macro` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `lna_gain_compression_macro.va`:
  - Module `lna_gain_compression_macro` (entry)
    - position 0: `clk` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `vin` (input, electrical)
    - position 3: `out` (output, electrical)
    - position 4: `metric` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/lna_gain_compression_macro.va`
- DUT instance: `XDUT (clk rst vin out metric) lna_gain_compression_macro`
- Required saved public traces: `clk`, `rst`, `vin`, `out`, `metric`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `lna_gain_compression_macro.tr` defaults to `1e-10` s; valid range: tr > 0; sets output transition smoothing.
- `lna_gain_compression_macro.vth` defaults to `0.45` V; valid range: finite real; sets clk and rst logic threshold.
- `lna_gain_compression_macro.gain` defaults to `2.2` V/V; valid range: gain > 0; sets small-signal gain about 0.45 V common mode.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_INITIAL_AND_RESET_COMMON_MODE`: exercise and make observable: Initialization sets out to 0.45 V and clears metric; an active-high reset sampled on a rising clk crossing restores the same state. Required traces: `time`, `clk`, `rst`, `out`, `metric`.
- `P_SMALL_SIGNAL_GAIN`: exercise and make observable: For linear values from 0.14 V through 0.76 V, out equals 0.45 V plus gain times the sampled vin deviation and metric is 0.1 V. Required traces: `time`, `clk`, `vin`, `out`, `metric`.
- `P_POSITIVE_COMPRESSION`: exercise and make observable: Above linear 0.76 V, excess signal is compressed by factor 0.28 and metric is 0.8 V. Required traces: `time`, `clk`, `vin`, `out`, `metric`.
- `P_NEGATIVE_COMPRESSION`: exercise and make observable: Below linear 0.14 V, excess signal is compressed by factor 0.28 and metric is 0.8 V. Required traces: `time`, `clk`, `vin`, `out`, `metric`.
- `P_FINAL_OUTPUT_CLAMP`: exercise and make observable: The final held output remains within 0.04 V through 0.86 V. Required traces: `time`, `out`.
- `P_CLOCKED_HOLD`: exercise and make observable: Out and metric update on rising clock crossings and hold between samples. Required traces: `time`, `clk`, `vin`, `out`, `metric`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- Initialize `out` to the 0.45 V common-mode level and `metric` low.
- Update the held output state on rising `clk` crossings.
- On a rising `clk` crossing where `rst` is high, return the output to common mode and clear `metric`; reset is sampled synchronously with `clk`.
- Compute the small-signal value as `linear = 0.45 + gain * (V(vin) - 0.45)`.
- In the linear region `0.14 <= linear <= 0.76`, drive `out = linear` and
  drive `metric = 0.1`.
- For positive compression, when `linear > 0.76`, drive
  `out = 0.76 + 0.28 * (linear - 0.76)` and drive `metric = 0.8`.
- For negative compression, when `linear < 0.14`, drive
  `out = 0.14 + 0.28 * (linear - 0.14)` and drive `metric = 0.8`.
- Clamp the final output to the public range `0.04 V <= out <= 0.86 V`.

The visible testbench is a public verification scenario for wiring and saved
observables. Do not hard-code its transient stop time, waveform breakpoints, or
sample windows into the DUT.


The required trace names are: `time`, `clk`, `rst`, `vin`, `out`, `metric`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
