# Precision Rectifier Envelope Detector Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Precision Rectifier Envelope Detector` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `precision_rectifier_envelope_detector.va`:
  - Module `precision_rectifier_envelope_detector` (entry)
    - position 0: `clk` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `vin` (input, electrical)
    - position 3: `rect` (output, electrical)
    - position 4: `env` (output, electrical)
    - position 5: `metric` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/precision_rectifier_envelope_detector.va`
- DUT instance: `XDUT (clk rst vin rect env metric) precision_rectifier_envelope_detector`
- Required saved public traces: `clk`, `rst`, `vin`, `rect`, `env`, `metric`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `precision_rectifier_envelope_detector.vth` defaults to `0.45` V; valid range: 0 < vth < 0.9; sets the clk and rst voltage-coded decision threshold.
- `precision_rectifier_envelope_detector.vcm` defaults to `0.45` V; valid range: 0 <= vcm <= 0.9; sets rectification common mode and envelope reset level.
- `precision_rectifier_envelope_detector.decay` defaults to `0.018` V/update; valid range: decay >= 0; sets the envelope decrement on each sampled decay update.
- `precision_rectifier_envelope_detector.tr` defaults to `1.5e-10` s; valid range: tr > 0; sets env and metric transition smoothing.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_FULL_WAVE_RECTIFICATION`: exercise and make observable: Rect equals vcm plus the absolute input deviation from vcm, so equal positive and negative excursions produce equal rectified levels, bounded to 0 V through 0.9 V. Required traces: `time`, `vin`, `rect`.
- `P_RESET_ENVELOPE`: exercise and make observable: Initialization or a rising clk update with rst active restores env to vcm and clears envelope memory. Required traces: `time`, `clk`, `rst`, `env`, `metric`.
- `P_PEAK_ATTACK`: exercise and make observable: At a rising clk update, a rectified value above the stored envelope is acquired immediately as the new env value. Required traces: `time`, `clk`, `rst`, `rect`, `env`.
- `P_BOUNDED_DECAY`: exercise and make observable: When rect is below the stored envelope, each rising clk update lowers env by at most decay and never below rect or vcm. Required traces: `time`, `clk`, `rect`, `env`.
- `P_ENVELOPE_LAG_METRIC`: exercise and make observable: Metric is high while env exceeds rect by more than 30 mV and low otherwise. Required traces: `time`, `rect`, `env`, `metric`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- Compute `rect` as a precision full-wave rectified voltage around `vcm`, bounded to the valid signal range.
- Initialize the envelope state to `vcm`.
- On each rising `clk` crossing, reset the envelope state to `vcm` when `rst` is above `vth`.
- When not reset, update the envelope by immediately following upward rectified peaks and otherwise decaying by `decay` toward the current rectified level.
- Do not let the envelope decay below either the current rectified level or `vcm`.
- Drive `metric` high when the envelope exceeds the instantaneous rectified value by more than `30 mV`, and low otherwise.


The required trace names are: `time`, `clk`, `rst`, `vin`, `rect`, `env`, `metric`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
