# Comparator Offset Calibration Loop Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Comparator Offset Calibration Loop` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `comparator_offset_calibration_loop.va`:
  - Module `comparator_offset_calibration_loop` (entry)
    - position 0: `vdd` (input, electrical)
    - position 1: `vss` (input, electrical)
    - position 2: `clk` (input, electrical)
    - position 3: `dcmpp` (input, electrical)
    - position 4: `vinp` (output, electrical)
    - position 5: `vinn` (output, electrical)
    - position 6: `offset_est` (output, electrical)
    - position 7: `valid` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/comparator_offset_calibration_loop.va`
- DUT instance: `XLOOP (vdd vss clk dcmpp vinp vinn offset_est valid) comparator_offset_calibration_loop`
- Required saved public traces: `vdd`, `vss`, `clk`, `dcmpp`, `vinp`, `vinn`, `offset_est`, `valid`, `vos_ref`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `comparator_offset_calibration_loop.step_initial` defaults to `0.064` V; valid range: step_initial > 0; sets the first signed differential search increment.
- `comparator_offset_calibration_loop.iterations` defaults to `7` updates; valid range: iterations >= 1; sets the number of falling-clock updates before valid asserts.
- `comparator_offset_calibration_loop.tr` defaults to `2e-11` s; valid range: tr >= 0; sets transition smoothing for generated stimulus, estimate, and valid outputs.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_ZERO_INITIAL_ESTIMATE`: exercise and make observable: The signed estimate initializes to zero, the search increment initializes to step_initial, and valid begins low. Required traces: `time`, `offset_est`, `valid`.
- `P_FALLING_EDGE_UPDATE`: exercise and make observable: The calibration state updates only on falling clk crossings through the midpoint of vdd and vss. Required traces: `time`, `vdd`, `vss`, `clk`, `dcmpp`, `offset_est`.
- `P_DECISION_DIRECTION`: exercise and make observable: At an update, a high dcmpp decreases the estimate by the current step and a low dcmpp increases it by the current step. Required traces: `time`, `clk`, `dcmpp`, `offset_est`.
- `P_SUCCESSIVE_STEP_HALVING`: exercise and make observable: The magnitude of the search increment halves after every update, yielding a successive-approximation trajectory. Required traces: `time`, `clk`, `dcmpp`, `offset_est`.
- `P_SYMMETRIC_DIFFERENTIAL_STIMULUS`: exercise and make observable: Vinp and vinn remain symmetric around mid-supply and vinp minus vinn equals offset_est. Required traces: `time`, `vdd`, `vss`, `vinp`, `vinn`, `offset_est`.
- `P_VALID_COMPLETION`: exercise and make observable: Valid remains at vss until iterations updates complete, then rises to vdd and the reported estimate resolves the supplied comparator trip point represented by vos_ref within the search resolution. Required traces: `time`, `vdd`, `vss`, `clk`, `offset_est`, `valid`, `vos_ref`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- Initialize the signed differential estimate to zero and the search step to
  `step_initial`.
- On each falling crossing of `clk` through the midpoint between `vdd` and
  `vss`, sample `dcmpp`.
- A high sampled decision means the applied differential stimulus is above the
  comparator trip point, so the loop decreases the estimate by the current
  search step. A low sampled decision means the loop increases the estimate by
  the current search step.
- Halve the search step after every update.
- Drive `vinp` and `vinn` symmetrically around mid-supply so that `vinp - vinn`
  equals the current estimate.
- Drive `offset_est` with the current signed estimate. Drive `valid` low until
  the configured number of updates has completed, then drive it high.


The required trace names are: `time`, `vdd`, `vss`, `clk`, `dcmpp`, `vinp`, `vinn`, `offset_est`, `valid`, `vos_ref`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Include the supplied read-only support files only from
  `./dut/support/...`; do not reference `./support/...` or undeclared paths.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
