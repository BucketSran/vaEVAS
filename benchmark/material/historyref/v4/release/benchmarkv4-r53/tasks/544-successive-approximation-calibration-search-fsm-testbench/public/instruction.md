# Successive Approximation Calibration Search FSM Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Successive Approximation Calibration Search FSM` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `successive_approximation_calibration_search_fsm.va`:
  - Module `successive_approximation_calibration_search_fsm` (entry)
    - position 0: `clk` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `vin` (input, electrical)
    - position 3: `out` (output, electrical)
    - position 4: `metric` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/successive_approximation_calibration_search_fsm.va`
- DUT instance: `XDUT (clk rst vin out metric) successive_approximation_calibration_search_fsm`
- Required saved public traces: `clk`, `rst`, `vin`, `out`, `metric`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `successive_approximation_calibration_search_fsm.tr` defaults to `1e-10` s; valid range: tr > 0; sets out and metric transition smoothing.
- `successive_approximation_calibration_search_fsm.vth` defaults to `0.45` V; valid range: vmin < vth < vmax; sets clk and rst logic threshold.
- `successive_approximation_calibration_search_fsm.target` defaults to `0.45` V; valid range: vmin <= target <= vmax; sets zero-error decision point and reset trial value.
- `successive_approximation_calibration_search_fsm.step_init` defaults to `0.18` V; valid range: step_init > 0; sets the first signed trial adjustment and reset step size.
- `successive_approximation_calibration_search_fsm.vmin` defaults to `0.05` V; valid range: vmin < vmax; sets the lower trial-trim clamp.
- `successive_approximation_calibration_search_fsm.vmax` defaults to `0.85` V; valid range: vmax > vmin; sets the upper trial-trim clamp.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RESET_SEARCH_STATE`: exercise and make observable: Active reset restores out to target, the current step to step_init, the cycle count to zero, and metric low. Required traces: `time`, `clk`, `rst`, `out`, `metric`.
- `P_SIGNED_TRIAL_UPDATE`: exercise and make observable: On each active rising clk update before completion, vin above target increases out by the current step and vin below target decreases it. Required traces: `time`, `clk`, `rst`, `vin`, `out`.
- `P_SUCCESSIVE_STEP_HALVING`: exercise and make observable: The current step halves after every active decision update, yielding the public successive-approximation sequence from step_init. Required traces: `time`, `clk`, `vin`, `out`.
- `P_FOUR_STEP_DONE`: exercise and make observable: Metric asserts after four active search updates and subsequent rising clocks hold the completed trial state until reset. Required traces: `time`, `clk`, `rst`, `vin`, `out`, `metric`.
- `P_TRIM_CLAMP`: exercise and make observable: Out remains within vmin through vmax for every trial update. Required traces: `time`, `out`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- Initialize the trial trim to `target`, the step size to `step_init`, and `metric` low.
- On each rising crossing of `clk` through `vth`, update the search state unless the search is already done.
- While `rst` is above `vth`, reset the trial trim to `target`, restore the initial step size, clear the cycle counter, and drive `metric` low.
- Treat `V(vin) - target` as the signed decision input.
- For a positive decision input, increase the trial trim by the current step size.
- For a negative decision input, decrease the trial trim by the current step size.
- Halve the step size after each active decision update.
- Assert `metric` after the public four-step search window has completed.
- Clamp the trial trim between `vmin` and `vmax`.


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
