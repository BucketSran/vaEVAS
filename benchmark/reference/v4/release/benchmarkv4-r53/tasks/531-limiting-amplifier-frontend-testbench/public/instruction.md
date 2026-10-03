# Limiting Amplifier Frontend Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Limiting Amplifier Frontend` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `limiting_amplifier_frontend.va`:
  - Module `limiting_amplifier_frontend` (entry)
    - position 0: `clk` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `vin` (input, electrical)
    - position 3: `out` (output, electrical)
    - position 4: `metric` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/limiting_amplifier_frontend.va`
- DUT instance: `XDUT (clk rst vin out metric) limiting_amplifier_frontend`
- Required saved public traces: `clk`, `rst`, `vin`, `out`, `metric`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `limiting_amplifier_frontend.tr` defaults to `1e-10` s; valid range: tr > 0; sets output transition smoothing.
- `limiting_amplifier_frontend.vth` defaults to `0.45` V; valid range: finite real; sets clk and rst logic threshold.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_INITIAL_AND_RESET_COMMON_MODE`: exercise and make observable: Initialization sets out to 0.45 V and metric to 0 V; an active-high reset sampled on a rising clk crossing restores the same state. Required traces: `time`, `clk`, `rst`, `out`, `metric`.
- `P_LINEAR_REGION`: exercise and make observable: For sampled input deviation from -0.09 V through 0.09 V, out equals 0.45 V plus 1.7 times the deviation and metric is 0 V. Required traces: `time`, `clk`, `vin`, `out`, `metric`.
- `P_POSITIVE_LIMITING`: exercise and make observable: Above the positive boundary, out follows 0.73 V plus 0.45 times excess deviation and metric is 0.85 V. Required traces: `time`, `clk`, `vin`, `out`, `metric`.
- `P_NEGATIVE_LIMITING`: exercise and make observable: Below the negative boundary, out follows 0.17 V plus 0.45 times excess negative deviation and metric is 0.85 V. Required traces: `time`, `clk`, `vin`, `out`, `metric`.
- `P_OUTPUT_CLAMP`: exercise and make observable: The final held output remains within 0.04 V through 0.86 V. Required traces: `time`, `out`.
- `P_CLOCKED_HOLD`: exercise and make observable: Out and metric update only on rising clock crossings and hold between samples. Required traces: `time`, `clk`, `vin`, `out`, `metric`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- Initialize `out` to `0.45 V` and `metric` to `0 V`.
- On each rising `clk` crossing through `vth`, sample `vin` unless reset is active.
- On a rising `clk` crossing where `rst` is above `vth`, reset `out` to `0.45 V` and clear `metric` to `0 V`; reset is sampled synchronously with `clk`.
- Treat `x = V(vin) - 0.45 V` as the signed input.
- In the central linear region, when `-0.09 V <= x <= 0.09 V`, drive `out = 0.45 + 1.7 * x` and `metric = 0 V`.
- In the positive limiting region, when `x > 0.09 V`, drive `out = 0.73 + 0.45 * (x - 0.09)` and `metric = 0.85 V`.
- In the negative limiting region, when `x < -0.09 V`, drive `out = 0.17 + 0.45 * (x + 0.09)` and `metric = 0.85 V`.
- Clamp the output to `[0.04 V, 0.86 V]`.


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
