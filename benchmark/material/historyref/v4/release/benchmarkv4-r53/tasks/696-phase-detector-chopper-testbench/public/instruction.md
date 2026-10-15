# Phase Detector Chopper Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Phase Detector Chopper` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `phase_detector_chopper.va`:
  - Module `phase_detector_chopper` (entry)
    - position 0: `vlocal_osc` (input, electrical)
    - position 1: `vin_rf` (input, electrical)
    - position 2: `vif` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/phase_detector_chopper.va`
- DUT instance: `XDUT (vlocal_osc vin_rf vif) phase_detector_chopper`
- Required saved public traces: `vif`, `vin_rf`, `vlocal_osc`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `phase_detector_chopper.gain` defaults to `1.25`; valid range: finite; overrides gain.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_POSITIVE_LO_GAIN_PATH`: exercise and make observable: When `vlocal_osc` is positive, drive `vif = gain * vin_rf`. Required traces: `time`, `vif`, `vin_rf`, `vlocal_osc`.
- `P_NEGATIVE_LO_CHOP_PATH`: exercise and make observable: When `vlocal_osc` is not positive, drive `vif = -gain * vin_rf`. Required traces: `time`, `vif`, `vin_rf`, `vlocal_osc`.
- `P_CONTINUOUS_TRACKING`: exercise and make observable: `vif` tracks `vin_rf` and `vlocal_osc` continuously without clocked state or hidden latching. Required traces: `time`, `vif`, `vin_rf`, `vlocal_osc`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Drive `vif` as `gain*vin_rf` when `vlocal_osc` is positive and as `-gain*vin_rf` otherwise. The output should track input changes continuously without clocked state.


The required trace names are: `time`, `vif`, `vin_rf`, `vlocal_osc`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
