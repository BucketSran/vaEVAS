# PA Compression Macro Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `PA Compression Macro` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `pa_compression_macro.va`:
  - Module `pa_compression_macro` (entry)
    - position 0: `clk` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `vin` (input, electrical)
    - position 3: `out` (output, electrical)
    - position 4: `metric` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/pa_compression_macro.va`
- DUT instance: `XFB_DUT (clk rst vin out metric) pa_compression_macro`
- Required saved public traces: `clk`, `rst`, `vin`, `out`, `metric`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `pa_compression_macro.tr` defaults to `1e-10` s; valid range: tr > 0; sets output and metric transition smoothing.
- `pa_compression_macro.vth` defaults to `0.45` V; valid range: 0 < vth < 0.9; sets clk and rst logic threshold.
- `pa_compression_macro.gain` defaults to `3.0`; valid range: gain > 0; sets the moderate-drive voltage gain about 0.45 V common mode.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RESET_COMMON_MODE`: exercise and make observable: Initialization or active reset returns out to 0.45 V common mode and clears metric to 0 V. Required traces: `time`, `clk`, `rst`, `out`, `metric`.
- `P_CLOCKED_UPDATE`: exercise and make observable: Out and metric update from the sampled signed drive vin - 0.45 V on rising clk crossings and hold between updates. Required traces: `time`, `clk`, `rst`, `vin`, `out`, `metric`.
- `P_LINEAR_REGION`: exercise and make observable: When 0.45 V + gain*(vin - 0.45 V) lies from 0.12 V through 0.78 V, out equals that target and metric is 0.1 V. Required traces: `time`, `clk`, `vin`, `out`, `metric`.
- `P_SYMMETRIC_COMPRESSION`: exercise and make observable: Targets above 0.78 V or below 0.12 V are compressed with slope 0.18 about the corresponding boundary, and metric is 0.85 V. Required traces: `time`, `clk`, `vin`, `out`, `metric`.
- `P_OUTPUT_CLAMP`: exercise and make observable: The compressed output remains within 0.02 V through 0.88 V with finite transition smoothing. Required traces: `time`, `out`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- Initialize `out` to the 0.45 V common-mode level and `metric` to `0 V`.
- Update the held output state on rising `clk` crossings through `vth`.
- When `rst` is high, return the output to common mode and clear `metric`.
- Treat `x = V(vin) - 0.45 V` as the signed drive and compute `drive = 0.45 + gain * x`.
- In the moderate-drive region, `0.12 V <= drive <= 0.78 V`, drive `out = drive` and `metric = 0.1 V`.
- For high-side compression, when `drive > 0.78 V`, drive `out = 0.78 + 0.18 * (drive - 0.78)` and `metric = 0.85 V`.
- For low-side compression, when `drive < 0.12 V`, drive `out = 0.12 + 0.18 * (drive - 0.12)` and `metric = 0.85 V`.
- Clamp the output to `[0.02 V, 0.88 V]`.

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
