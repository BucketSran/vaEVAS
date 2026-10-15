# Reference Startup Enable Flow Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Reference Startup Enable Flow` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `reference_startup_enable_flow.va`:
  - Module `reference_startup_enable_flow` (entry)
    - position 0: `clk` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `vdd_in` (input, electrical)
    - position 3: `en` (input, electrical)
    - position 4: `out` (output, electrical)
    - position 5: `metric` (output, electrical)
    - position 6: `supply_ok` (output, electrical)
    - position 7: `enable_mon` (output, electrical)
    - position 8: `state_mon` (output, electrical)
    - position 9: `startup_mon` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/reference_startup_enable_flow.va`
- DUT instance: `XDUT (clk rst vdd_in en out metric supply_ok enable_mon state_mon startup_mon) reference_startup_enable_flow`
- Required saved public traces: `clk`, `rst`, `vdd_in`, `en`, `out`, `metric`, `supply_ok`, `enable_mon`, `state_mon`, `startup_mon`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `reference_startup_enable_flow.tr` defaults to `1e-10` s; valid range: finite real; use tr >= 0 for physical transition smoothing; sets smoothing for all voltage-coded outputs.
- `reference_startup_enable_flow.vth` defaults to `0.45` V; valid range: finite real; sets clk, rst, and en decision thresholds.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_SUPPLY_AND_ENABLE_MONITORS`: exercise and make observable: Supply_ok is 0.9 V exactly when vdd_in exceeds 0.32 V, while enable_mon is 0.9 V exactly when en exceeds vth. Required traces: `time`, `vdd_in`, `en`, `supply_ok`, `enable_mon`.
- `P_RESET_OR_BROWNOUT`: exercise and make observable: Active reset or a bad supply clears out, metric, startup progress, and state; a supply dip also removes valid status. Required traces: `time`, `clk`, `rst`, `vdd_in`, `out`, `metric`, `state_mon`, `startup_mon`.
- `P_DISABLED_REFERENCE`: exercise and make observable: With supply good and enable low, out is 0.05 V, metric is 0.1 V, startup progress is cleared, and state_mon represents state 1. Required traces: `time`, `clk`, `vdd_in`, `en`, `out`, `metric`, `state_mon`, `startup_mon`.
- `P_ENABLED_SETTLING`: exercise and make observable: On each rising clk crossing with supply good and enable high, out advances by 0.32 times its remaining error to 0.55 V and the startup count increments up to 8. Required traces: `time`, `clk`, `vdd_in`, `en`, `out`, `startup_mon`.
- `P_STARTUP_VALIDITY`: exercise and make observable: During enabled startup metric is 0.25 V and state is 2; after at least five enabled updates with out above 0.48 V, metric is 0.9 V and state is 3. Required traces: `time`, `clk`, `out`, `metric`, `state_mon`, `startup_mon`.
- `P_BROWNOUT_RECOVERY`: exercise and make observable: After a supply dip and restoration with enable asserted, the output and monitors repeat the same startup sequence before returning valid. Required traces: `time`, `clk`, `vdd_in`, `en`, `out`, `metric`, `supply_ok`, `state_mon`, `startup_mon`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- `clk`, `rst`, and `en` are voltage-coded logic signals.
- `vdd_in` is the monitored supply waveform for the reference-startup flow.
- Update the startup flow on rising `clk` crossings through `vth`.
- Treat the supply as good when `vdd_in > 0.32 V`; drive `supply_ok` to 0.9 V when good and to 0 V otherwise.
- Drive `enable_mon` to 0.9 V when `en > vth` and to 0 V otherwise.
- When reset is active or the supply is not good, reset `out = 0 V`, `metric = 0 V`, startup count `0`, and state `0`.
- When supply is good but enable is low, hold the disabled reference at `out = 0.05 V`, drive `metric = 0.1 V`, reset startup count to `0`, and use state `1`.
- When supply is good and enable is high, update the reference as `out_next = out_prev + 0.32 * (0.55 - out_prev)` and increment the startup count by one until it saturates at `8`.
- The startup is valid after the enabled update when the count is at least `5` and `out > 0.48 V`. In startup but not yet valid, drive `metric = 0.25 V` and use state `2`; when valid, drive `metric = 0.9 V` and use state `3`.
- Drive `state_mon = 0.9 * state / 3.0`. Drive `startup_mon = 0.9 * count / 8.0` using the saturated startup count.
- A supply dip should reset valid status and startup progress; after the supply returns and enable remains asserted, the flow should recover through the same startup sequence.
- Keep the model pure voltage-domain behavioral Verilog-A. Do not use branch-current contributions, transistor-level devices, AC/noise analysis, or KCL/KVL regulation loops.


The required trace names are: `time`, `clk`, `rst`, `vdd_in`, `en`, `out`, `metric`, `supply_ok`, `enable_mon`, `state_mon`, `startup_mon`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
