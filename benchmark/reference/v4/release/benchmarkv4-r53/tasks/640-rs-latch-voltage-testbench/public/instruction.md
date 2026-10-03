# RS Latch Voltage Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `RS Latch Voltage` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `rs_latch_voltage.va`:
  - Module `rs_latch_voltage` (entry)
    - position 0: `vin_s` (input, electrical)
    - position 1: `vin_r` (input, electrical)
    - position 2: `vout_q` (output, electrical)
    - position 3: `vout_qbar` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/rs_latch_voltage.va`
- DUT instance: `XDUT (vin_s vin_r vout_q vout_qbar) rs_latch_voltage`
- Required saved public traces: `vin_r`, `vin_s`, `vout_q`, `vout_qbar`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- No public parameter is declared.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_LOGIC_THRESHOLDS_OUTPUT_AMPLITUDE`: exercise and make observable: Interpret set and reset as logic high above 0.45 V and drive outputs with 0.9 V high and 0.0 V low levels. Required traces: `time`, `vin_s`, `vin_r`, `vout_q`, `vout_qbar`.
- `P_SET_RESET_PRIORITY`: exercise and make observable: A set-only input drives Q high, and a reset-only input drives Q low. Required traces: `time`, `vin_s`, `vin_r`, `vout_q`, `vout_qbar`.
- `P_HOLD_STATE`: exercise and make observable: When neither set-only nor reset-only is asserted, preserve the previous Q state after initializing Q low. Required traces: `time`, `vin_s`, `vin_r`, `vout_q`, `vout_qbar`.
- `P_QBAR_COMPLEMENT`: exercise and make observable: Drive `vout_qbar` as the logical complement of Q. Required traces: `time`, `vout_q`, `vout_qbar`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Interpret set and reset as logic 1 above 0.45 V. Initialize Q low. A set-only input drives Q high, a reset-only input drives Q low, and the hold condition preserves the previous state. Drive `vout_qbar` as the complement of Q. Use 0.9 V for high and 0.0 V for low.


The required trace names are: `time`, `vin_r`, `vin_s`, `vout_q`, `vout_qbar`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
