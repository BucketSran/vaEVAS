# UVLO Brownout Detector Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `UVLO Brownout Detector` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `uvlo_brownout_detector.va`:
  - Module `uvlo_brownout_detector` (entry)
    - position 0: `clk` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `vin` (input, electrical)
    - position 3: `out` (output, electrical)
    - position 4: `metric` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/uvlo_brownout_detector.va`
- DUT instance: `XDUT (clk rst vin out metric) uvlo_brownout_detector`
- Required saved public traces: `clk`, `rst`, `vin`, `out`, `metric`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `uvlo_brownout_detector.tr` defaults to `1e-10` s; valid range: tr > 0; sets out and metric transition smoothing.
- `uvlo_brownout_detector.vth` defaults to `0.45` V; valid range: 0 < vth < 0.9; sets clk and rst voltage-coded logic threshold.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RESET_FAULT`: exercise and make observable: Active reset clears the power-good out signal and drives metric to the public fault code 0.9 V. Required traces: `time`, `clk`, `rst`, `out`, `metric`.
- `P_UPPER_TRIP_ASSERT`: exercise and make observable: On a sampled update, vin strictly greater than 0.65 V asserts power-good out. Required traces: `time`, `clk`, `rst`, `vin`, `out`.
- `P_HYSTERESIS_HOLD`: exercise and make observable: For sampled vin values from 0.55 V through 0.65 V inclusive, out preserves its previous power-good state. Required traces: `time`, `clk`, `vin`, `out`.
- `P_BROWNOUT_CLEAR`: exercise and make observable: On a sampled update, vin strictly less than 0.55 V clears out to the brownout state. Required traces: `time`, `clk`, `rst`, `vin`, `out`.
- `P_STATUS_DISTINCTION`: exercise and make observable: Metric is the checker-observable status code: 0.1 V when out is power-good high and 0.9 V when reset, undervoltage, or brownout is active. Required traces: `time`, `vin`, `out`, `metric`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- `clk` and `rst` are voltage-coded logic signals.
- Treat `vin` as the monitored supply voltage.
- Assert the power-good output `out` high only on a sampled clock update where `vin > 0.65 V`.
- Preserve the previous `out` state on sampled clock updates where `0.55 V <= vin <= 0.65 V`.
- Clear `out` low on reset or on a sampled clock update where `vin < 0.55 V`.
- Drive `metric` as a public status code: `0.1 V` when `out` is power-good high, and `0.9 V` when reset, undervoltage, or brownout is active.
- Keep the model pure voltage-domain behavioral Verilog-A. Do not use branch-current contributions, transistor-level devices, AC/noise analysis, or KCL/KVL regulation loops.


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
