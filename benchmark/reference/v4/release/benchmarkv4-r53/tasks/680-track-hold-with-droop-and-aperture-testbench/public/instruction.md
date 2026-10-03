# Track/Hold with Droop and Aperture Metric Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Track/Hold with Droop and Aperture Metric` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `track_hold_aperture.va`:
  - Module `track_hold_aperture` (entry)
    - position 0: `vin` (input, electrical)
    - position 1: `track` (input, electrical)
    - position 2: `rst` (input, electrical)
    - position 3: `enable` (input, electrical)
    - position 4: `vhold` (output, electrical)
    - position 5: `aperture_metric` (output, electrical)
    - position 6: `droop_metric` (output, electrical)
    - position 7: `valid` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/track_hold_aperture.va`
- DUT instance: `XDUT (vin track rst enable vhold aperture_metric droop_metric valid) track_hold_aperture`
- Required saved public traces: `vin`, `track`, `rst`, `enable`, `vhold`, `aperture_metric`, `droop_metric`, `valid`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `track_hold_aperture.vdd` defaults to `0.9`; valid range: finite; overrides vdd.
- `track_hold_aperture.vss` defaults to `0.0`; valid range: finite; overrides vss.
- `track_hold_aperture.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `track_hold_aperture.tick` defaults to `1n from (0:inf)`; valid range: finite; overrides tick.
- `track_hold_aperture.droop_per_tick` defaults to `0.015 from [0:inf)`; valid range: finite; overrides droop_per_tick.
- `track_hold_aperture.aperture_gain` defaults to `0.6 from [0:inf)`; valid range: finite; overrides aperture_gain.
- `track_hold_aperture.tr` defaults to `100p from (0:inf)`; valid range: finite; overrides tr.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RESET_DISABLE_CLEAR`: exercise and make observable: Reset or a low `enable` clears `vhold`, `aperture_metric`, `droop_metric`, and `valid`. Required traces: `time`, `vin`, `track`, `rst`, `enable`, `vhold`, `aperture_metric`, `droop_metric`, `valid`.
- `P_TRACK_MODE_FOLLOWS_INPUT`: exercise and make observable: While `track` is high and the DUT is enabled, the held state follows `vin` at the internal update cadence and `valid` remains low. Required traces: `time`, `vin`, `track`, `rst`, `enable`, `vhold`, `valid`.
- `P_FALLING_TRACK_SAMPLE_APERTURE`: exercise and make observable: A falling `track` edge samples `vin`, asserts `valid`, and reports an aperture metric proportional to the step from the previous tracked value. Required traces: `time`, `vin`, `track`, `enable`, `vhold`, `aperture_metric`, `valid`.
- `P_HOLD_MODE_DROOP`: exercise and make observable: During hold mode, `vhold` droops downward by `droop_per_tick` on each update tick without going below `vss`. Required traces: `time`, `track`, `enable`, `vhold`, `droop_metric`.
- `P_DROOP_METRIC_ACCUMULATION`: exercise and make observable: `droop_metric` accumulates total hold-mode droop and clears on a new sample, reset, or disable. Required traces: `time`, `track`, `rst`, `enable`, `droop_metric`, `valid`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- Reset or a low `enable` clears the held output, aperture metric, droop metric, and valid flag.
- While `track` is high, the held state tracks the input at the internal update cadence and `valid` remains low.
- On a falling `track` edge, sample `vin`, assert `valid`, and report an aperture metric proportional to the step from the previous tracked value.
- During hold mode, the held output droops downward by `droop_per_tick` on each update tick without going below `vss`.
- `droop_metric` accumulates the total hold-mode droop and clears on a new sample, reset, or disable.


The required trace names are: `time`, `vin`, `track`, `rst`, `enable`, `vhold`, `aperture_metric`, `droop_metric`, `valid`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
