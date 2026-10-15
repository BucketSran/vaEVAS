# Power-On Reset Detector Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Power-On Reset Detector` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `power_on_reset_detector.va`:
  - Module `power_on_reset_detector` (entry)
    - position 0: `clk` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `vin` (input, electrical)
    - position 3: `out` (output, electrical)
    - position 4: `metric` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/power_on_reset_detector.va`
- DUT instance: `XDUT (clk rst vin out metric) power_on_reset_detector`
- Required saved public traces: `clk`, `rst`, `vin`, `out`, `metric`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `power_on_reset_detector.tr` defaults to `1e-10` s; valid range: tr > 0; sets output and metric transition smoothing.
- `power_on_reset_detector.vth` defaults to `0.45` V; valid range: 0 < vth < 0.9; sets clk and rst logic threshold.
- `power_on_reset_detector.vtrip` defaults to `0.62` V; valid range: 0 < vtrip < 0.9; sets the monitored-supply power-good threshold.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RESET_ASSERTED_UNSAFE`: exercise and make observable: Out is active-high reset and remains asserted while rst is high or vin is below vtrip. Required traces: `time`, `rst`, `vin`, `out`.
- `P_DELAYED_RELEASE`: exercise and make observable: After rst releases and vin is power-good, out stays asserted for four rising clk updates before deasserting. Required traces: `time`, `clk`, `rst`, `vin`, `out`.
- `P_RELEASE_STATUS`: exercise and make observable: Metric uses an intermediate status level during the release delay, is high after delayed reset release completes, and is cleared when reset is reasserted or supply is not power-good. Required traces: `time`, `clk`, `rst`, `vin`, `out`, `metric`.
- `P_FAULT_REASSERTION`: exercise and make observable: A new reset assertion or a brownout below vtrip immediately reasserts out and clears the accumulated release delay, independent of the next clk edge. Required traces: `time`, `clk`, `rst`, `vin`, `out`, `metric`.
- `P_VOLTAGE_CODED_LEVELS`: exercise and make observable: Out and metric use bounded voltage-coded low and high levels with finite transition smoothing. Required traces: `time`, `out`, `metric`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- `clk` and `rst` are voltage-coded logic signals.
- Treat `vin` as the monitored supply ramp and brownout stimulus.
- `out` is an active-high reset voltage.
- Keep `out` reset-asserted high while reset input is high or `vin` is below the supply-good threshold.
- After `vin` is power-good and reset is released, wait four rising clock updates before deasserting `out` low.
- During the release delay, drive `metric` to an intermediate status level; after release, drive `metric` high.
- If the supply falls below `vtrip` or `rst` rises above `vth`, assert `out` high and clear the release delay immediately, independent of the next clock edge.
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
