# Slew Rate Limiter Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Slew Rate Limiter` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `slew_rate_limiter.va`:
  - Module `slew_rate_limiter` (entry)
    - position 0: `vin` (input, electrical)
    - position 1: `vout` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/slew_rate_limiter.va`
- DUT instance: `XDUT (vin vout) slew_rate_limiter`
- Required saved public traces: `vin`, `vout`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `slew_rate_limiter.step` defaults to `0.015` V; valid range: step > 0; sets maximum state change per update.
- `slew_rate_limiter.tr` defaults to `2e-10` s; valid range: tr > 0; sets output transition smoothing.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_INITIAL_ZERO`: exercise and make observable: vout begins at 0 V. Required traces: `time`, `vout`.
- `P_PERIODIC_UPDATE`: exercise and make observable: The state changes only on the public 1 ns periodic update schedule. Required traces: `time`, `vin`, `vout`.
- `P_BIDIRECTIONAL_STEP_LIMIT`: exercise and make observable: Each rising or falling update changes the state toward vin by no more than step. Required traces: `time`, `vin`, `vout`.
- `P_NEAR_TARGET_SETTLE`: exercise and make observable: When vin is within one step, vout may settle directly to vin. Required traces: `time`, `vin`, `vout`.
- `P_EVENTUAL_TRACKING`: exercise and make observable: The limited response eventually reaches sustained high and low input levels while remaining non-instantaneous. Required traces: `time`, `vin`, `vout`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- Initialize the internal output state to `0 V`.
- Update the state only on a periodic `1 ns` timer.
- On each update, move the internal state toward `V(vin)` by no more than `step`.
- Limit both rising and falling changes.
- If `V(vin)` is within one `step` of the internal state, the state may settle directly to `V(vin)`.
- Drive `vout` from the internal state with a smoothed voltage contribution.
- The response must eventually reach both high and low input levels while remaining slower than an instantaneous copy of `vin`.


The required trace names are: `time`, `vin`, `vout`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
