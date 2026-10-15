# Ramp Step Source Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Ramp Step Source` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `bound_step_period_guard_ref.va`:
  - Module `bound_step_period_guard_ref` (entry)
    - position 0: `VDD` (inout, electrical)
    - position 1: `VSS` (inout, electrical)
    - position 2: `guard_out` (output, electrical)
    - position 3: `phase_out` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/bound_step_period_guard_ref.va`
- DUT instance: `IDUT (VDD VSS guard_out phase_out) bound_step_period_guard_ref period=8n points_per_period=16 pulse_w=1.5n tedge=40p`
- Required saved public traces: `VDD`, `VSS`, `guard_out`, `phase_out`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `bound_step_period_guard_ref.period` defaults to `8e-09` s; valid range: period > 0; sets the repetition interval and phase-ramp wrap time.
- `bound_step_period_guard_ref.pulse_w` defaults to `1.5e-09` s; valid range: pulse_w > 0; sets the guard_out high duration from the start of each period; values at least as large as period leave no low remainder in that period.
- `bound_step_period_guard_ref.points_per_period` defaults to `16.0`; valid range: points_per_period > 0; sets transient timestep guidance used to resolve the ramp and guard pulse without changing their ideal timing.
- `bound_step_period_guard_ref.tedge` defaults to `4e-11` s; valid range: tedge > 0; sets guard_out transition smoothing.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_PHASE_RAMP`: exercise and make observable: Within each period, phase_out rises linearly from VSS toward VDD as normalized phase advances from zero toward one. Required traces: `time`, `VDD`, `VSS`, `phase_out`.
- `P_PHASE_WRAP`: exercise and make observable: At each period boundary, phase_out wraps from the end of the ramp back to VSS and begins the next ramp. Required traces: `time`, `VDD`, `VSS`, `phase_out`.
- `P_GUARD_WINDOW`: exercise and make observable: guard_out is at VDD during the first min(pulse_w, period) seconds of each period. Required traces: `time`, `VDD`, `VSS`, `guard_out`.
- `P_GUARD_LOW`: exercise and make observable: If pulse_w is less than period, guard_out remains at VSS after the guard window and before the next period boundary; if pulse_w is greater than or equal to period, guard_out has no low remainder in that period. Required traces: `time`, `VDD`, `VSS`, `guard_out`.
- `P_RAIL_TRACKING`: exercise and make observable: Both outputs derive their low and high endpoints from the observed VSS and VDD rails rather than fixed absolute voltages. Required traces: `time`, `VDD`, `VSS`, `guard_out`, `phase_out`.
- `P_PERIODICITY`: exercise and make observable: The ramp-wrap and guard-window pattern repeats every period with guard transitions smoothed by tedge. Required traces: `time`, `guard_out`, `phase_out`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Generate a periodic normalized phase ramp and a guard pulse. Within each
period, `phase_out` ramps from `VSS` toward `VDD` and wraps at the start of the
next period. `guard_out` is high during the first `min(pulse_w, period)` seconds
of each period. If `pulse_w >= period`, `guard_out` has no low remainder during
that period. The output levels should track the supplied rail
voltages, not hard-coded absolute rails.

Using `$bound_step(period / points_per_period)` is allowed to keep the narrow
guard pulse observable, but the scored behavior is the ramp wrap and guard
timing.


The required trace names are: `time`, `VDD`, `VSS`, `guard_out`, `phase_out`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
