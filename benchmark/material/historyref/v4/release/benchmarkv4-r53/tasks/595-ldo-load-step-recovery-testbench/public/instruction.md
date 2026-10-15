# LDO Load Step Recovery Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `LDO Load Step Recovery` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `ldo_load_step_recovery_flow.va`:
  - Module `ldo_load_step_recovery_flow` (entry)
    - position 0: `clk` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `vin` (input, electrical)
    - position 3: `out` (output, electrical)
    - position 4: `metric` (output, electrical)
    - position 5: `load_mon` (output, electrical)
    - position 6: `ctrl_mon` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/ldo_load_step_recovery_flow.va`
- DUT instance: `XDUT (clk rst vin out metric load_mon ctrl_mon) ldo_load_step_recovery_flow`
- Required saved public traces: `clk`, `rst`, `vin`, `out`, `metric`, `load_mon`, `ctrl_mon`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `ldo_load_step_recovery_flow.tr` defaults to `1e-10` s; valid range: tr > 0; sets output transition smoothing.
- `ldo_load_step_recovery_flow.vth` defaults to `0.45` V; valid range: finite real; sets clock and reset logic threshold.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RESET_REGULATION_STATE`: exercise and make observable: Active-high reset initializes out and target to 0.60 V, load_mon to 0.10 V, ctrl_mon to 0.50 V, metric to 0.9 V, and clears recovery progress. Required traces: `time`, `rst`, `out`, `metric`, `load_mon`, `ctrl_mon`.
- `P_BOUNDED_LOAD_AND_TARGET`: exercise and make observable: Each non-reset rising clk edge clips vin to 0 V through 0.9 V on load_mon and uses the public load-dependent target 0.61 V minus 0.025 times load. Required traces: `time`, `clk`, `rst`, `vin`, `load_mon`, `out`.
- `P_CONTROL_MONITOR`: exercise and make observable: Ctrl_mon represents the public load and regulation-error control expression and remains clamped to 0.05 V through 0.85 V. Required traces: `time`, `clk`, `load_mon`, `out`, `ctrl_mon`.
- `P_HEAVY_LOAD_DROOP`: exercise and make observable: A sampled load increase greater than 0.20 V causes the public 0.13 V transient droop before first-order recovery and restarts recovery qualification. Required traces: `time`, `clk`, `load_mon`, `out`, `metric`.
- `P_LIGHT_LOAD_KICK`: exercise and make observable: A sampled load decrease greater than 0.20 V causes the public 0.05 V light-load recovery kick before first-order recovery and restarts qualification. Required traces: `time`, `clk`, `load_mon`, `out`, `metric`.
- `P_RECOVERY_AND_SETTLING`: exercise and make observable: Every non-reset update applies the public 0.30 first-order recovery, clamps out to 0.20 V through 0.75 V, and sets metric high only after at least five updates with target error below 0.045 V. Required traces: `time`, `clk`, `out`, `metric`, `load_mon`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- `clk` and `rst` are voltage-coded logic signals.
- Treat `vin` as a bounded load-step request for a behavioral LDO recovery flow.
- On reset, initialize the regulator output state and target to 0.60 V,
  `load_mon` to 0.10 V, `ctrl_mon` to 0.50 V, `metric` to 0.9 V, and the
  recovery counter to zero.
- On each rising `clk` crossing with reset low, clamp the sampled load request
  to `[0 V, 0.9 V]` and drive `load_mon` from that bounded load.
- Compute the load-dependent regulation target as `0.61 V - 0.025 * load`.
- Compute the abstract pass/recovery control monitor as
  `0.45 V + 0.40 * load + 0.50 * (target - regulator_state)`, clamped to
  `[0.05 V, 0.85 V]`, and drive `ctrl_mon` from that value.
- If the bounded load has increased by more than 0.20 V since the previous
  sampled load, apply a transient droop by subtracting 0.13 V from the
  regulator state and reset the recovery counter.
- If the bounded load has decreased by more than 0.20 V since the previous
  sampled load, apply a light-load recovery kick by adding 0.05 V to the
  regulator state and reset the recovery counter.
- On every non-reset update, after applying any load-step kick, update the
  current regulator state with first-order recovery:
  `state_next = state_prev + 0.30 * (target - state_prev)`, then clamp the
  driven `out` voltage to `[0.20 V, 0.75 V]`.
- Increment the recovery counter on each non-reset update. Drive `metric` to
  0.9 V when the recovery counter is at least 5 and
  `abs(regulator_state - target) < 0.045 V`; otherwise drive `metric` to
  0.25 V.
- Keep the model pure voltage-domain behavioral Verilog-A. Do not use branch-current contributions, transistor-level devices, AC/noise analysis, or KCL/KVL regulation loops.


The required trace names are: `time`, `clk`, `rst`, `vin`, `out`, `metric`, `load_mon`, `ctrl_mon`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
