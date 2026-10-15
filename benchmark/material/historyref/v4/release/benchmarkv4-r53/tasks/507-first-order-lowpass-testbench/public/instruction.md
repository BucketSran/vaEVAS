# First Order Lowpass Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `First Order Lowpass` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `first_order_lowpass.va`:
  - Module `first_order_lowpass` (entry)
    - position 0: `vin` (input, electrical)
    - position 1: `vout` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/first_order_lowpass.va`
- DUT instance: `XDUT (vin vout) first_order_lowpass`
- Required saved public traces: `vin`, `vout`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `first_order_lowpass.alpha` defaults to `0.025`; valid range: 0 < alpha <= 1; sets the fraction of input error applied on each update.
- `first_order_lowpass.tr` defaults to `2e-10` s; valid range: tr > 0; sets output transition smoothing.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_INITIAL_STATE`: exercise and make observable: vout begins at 0 V before the first periodic update. Required traces: `time`, `vout`.
- `P_PERIODIC_UPDATE`: exercise and make observable: The internal output updates only on the public 500 ps periodic schedule using y := y + alpha*(vin-y). Required traces: `time`, `vin`, `vout`.
- `P_STEP_MONOTONICITY`: exercise and make observable: For a positive input step, vout is monotone and bounded by the input level. Required traces: `time`, `vin`, `vout`.
- `P_LOW_PASS_RESPONSE`: exercise and make observable: The step response is slower than an instantaneous copy of vin. Required traces: `time`, `vin`, `vout`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- Initialize the internal output state to `0 V`.
- Update the state only on a periodic `500 ps` timer.
- At each update, apply `y = y + alpha * (V(vin) - y)`.
- Drive `vout` from the internal state with a smoothed voltage contribution.
- For a positive input step, the response must be monotone, bounded by the input level, and slower than an instantaneous copy of `vin`.


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
