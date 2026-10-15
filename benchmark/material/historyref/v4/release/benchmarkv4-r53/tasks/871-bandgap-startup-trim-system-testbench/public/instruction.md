# Bandgap Startup and Trim System Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Bandgap Startup and Trim System` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `bandgap_trim_top.va`:
  - Module `bandgap_trim_top` (entry)
    - position 0: `vdd_sense` (inout, electrical)
    - position 1: `clk` (inout, electrical)
    - position 2: `rst` (inout, electrical)
    - position 3: `trim_req` (inout, electrical)
    - position 4: `temp_proxy` (inout, electrical)
    - position 5: `vref` (inout, electrical)
    - position 6: `trim_3` (inout, electrical)
    - position 7: `trim_2` (inout, electrical)
    - position 8: `trim_1` (inout, electrical)
    - position 9: `trim_0` (inout, electrical)
    - position 10: `ready` (inout, electrical)
    - position 11: `error_metric` (inout, electrical)
- Artifact `startup_detector.va`:
  - Module `startup_detector` (required_submodule)
    - position 0: `vdd_sense` (inout, electrical)
    - position 1: `clk` (inout, electrical)
    - position 2: `rst` (inout, electrical)
    - position 3: `startup_en` (inout, electrical)
- Artifact `ptat_ctat_core.va`:
  - Module `ptat_ctat_core` (required_submodule)
    - position 0: `temp_proxy` (inout, electrical)
    - position 1: `startup_en` (inout, electrical)
    - position 2: `core_ref` (inout, electrical)
- Artifact `trim_controller.va`:
  - Module `trim_controller` (required_submodule)
    - position 0: `clk` (inout, electrical)
    - position 1: `rst` (inout, electrical)
    - position 2: `trim_req` (inout, electrical)
    - position 3: `startup_en` (inout, electrical)
    - position 4: `core_ref` (inout, electrical)
    - position 5: `trim_3` (inout, electrical)
    - position 6: `trim_2` (inout, electrical)
    - position 7: `trim_1` (inout, electrical)
    - position 8: `trim_0` (inout, electrical)
    - position 9: `trim_corr` (inout, electrical)
    - position 10: `ready` (inout, electrical)
    - position 11: `error_metric` (inout, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include paths: `./dut/bandgap_trim_top.va`, `./dut/startup_detector.va`, `./dut/ptat_ctat_core.va`, `./dut/trim_controller.va`
- DUT instance: `XDUT (vdd_sense clk rst trim_req temp_proxy vref trim_3 trim_2 trim_1 trim_0 ready error_metric) bandgap_trim_top`
- Required saved public traces: `vdd_sense`, `clk`, `rst`, `trim_req`, `temp_proxy`, `vref`, `trim_3`, `trim_2`, `trim_1`, `trim_0`, `ready`, `error_metric`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `bandgap_trim_top.vhi` defaults to `0.9` V; valid range: finite; overrides logic high and upper clamp.
- `bandgap_trim_top.vlo` defaults to `0.0` V; valid range: finite; overrides logic low and lower clamp.
- `bandgap_trim_top.vpor` defaults to `0.72` V; valid range: finite; overrides startup threshold.
- `bandgap_trim_top.vref_nom` defaults to `0.6` V; valid range: finite; overrides nominal reference target.
- `bandgap_trim_top.trim_lsb` defaults to `2e-3` V; valid range: finite positive; overrides reference correction per trim-code step.
- `bandgap_trim_top.ready_tol` defaults to `5e-3` V; valid range: finite positive; overrides ready tolerance around reference target.
- `bandgap_trim_top.vth` defaults to `0.45` V; valid range: finite; overrides clock/reset/trim threshold.
- `bandgap_trim_top.tr` defaults to `200p from (0:inf)` s; valid range: positive; overrides output transition smoothing time.
- `startup_detector.vhi` defaults to `0.9` V; valid range: finite; overrides logic high output level.
- `startup_detector.vlo` defaults to `0.0` V; valid range: finite; overrides logic low output level.
- `startup_detector.vpor` defaults to `0.72` V; valid range: finite; overrides startup threshold.
- `startup_detector.vth` defaults to `0.45` V; valid range: finite; overrides clock/reset threshold.
- `startup_detector.tr` defaults to `200p from (0:inf)` s; valid range: positive; overrides output transition smoothing time.
- `ptat_ctat_core.vhi` defaults to `0.9` V; valid range: finite; overrides upper reference clamp.
- `ptat_ctat_core.vlo` defaults to `0.0` V; valid range: finite; overrides lower reference clamp.
- `ptat_ctat_core.vref_nom` defaults to `0.6` V; valid range: finite; overrides nominal reference target.
- `ptat_ctat_core.vth` defaults to `0.45` V; valid range: finite; overrides startup enable threshold.
- `ptat_ctat_core.tr` defaults to `200p from (0:inf)` s; valid range: positive; overrides output transition smoothing time.
- `trim_controller.vhi` defaults to `0.9` V; valid range: finite; overrides logic high output level.
- `trim_controller.vlo` defaults to `0.0` V; valid range: finite; overrides logic low output level.
- `trim_controller.vref_nom` defaults to `0.6` V; valid range: finite; overrides nominal reference target.
- `trim_controller.trim_lsb` defaults to `2e-3` V; valid range: finite positive; overrides reference correction per trim-code step.
- `trim_controller.ready_tol` defaults to `5e-3` V; valid range: finite positive; overrides ready tolerance around reference target.
- `trim_controller.vth` defaults to `0.45` V; valid range: finite; overrides clock/reset/trim threshold.
- `trim_controller.tr` defaults to `200p from (0:inf)` s; valid range: positive; overrides output transition smoothing time.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RESET_BROWNOUT_CLEAR`: exercise and make observable: On reset or brownout below POR, clear trim code, ready, error metric, and drive vref low. Required traces: `time`, `vdd_sense`, `clk`, `rst`, `trim_req`, `temp_proxy`, `vref`, `trim_3`, `trim_2`, `trim_1`, `trim_0`, `ready`, `error_metric`.
- `P_POR_STARTUP`: exercise and make observable: Enable the reference only after vdd_sense remains above vpor for two consecutive rising clock edges. Required traces: `time`, `vdd_sense`, `clk`, `rst`, `trim_req`, `temp_proxy`, `vref`, `trim_3`, `trim_2`, `trim_1`, `trim_0`, `ready`, `error_metric`.
- `P_CORE_REFERENCE`: exercise and make observable: Generate a behavioral PTAT/CTAT reference metric from temp_proxy around vref_nom. Required traces: `time`, `vdd_sense`, `clk`, `rst`, `trim_req`, `temp_proxy`, `vref`, `trim_3`, `trim_2`, `trim_1`, `trim_0`, `ready`, `error_metric`.
- `P_TRIM_SEARCH`: exercise and make observable: When trim_req is high, update the 4-bit trim code once per rising clock edge to reduce reference error. Required traces: `time`, `vdd_sense`, `clk`, `rst`, `trim_req`, `temp_proxy`, `vref`, `trim_3`, `trim_2`, `trim_1`, `trim_0`, `ready`, `error_metric`.
- `P_READY_QUALIFICATION`: exercise and make observable: Assert ready only after three consecutive enabled updates with error magnitude within ready_tol. Required traces: `time`, `vdd_sense`, `clk`, `rst`, `trim_req`, `temp_proxy`, `vref`, `trim_3`, `trim_2`, `trim_1`, `trim_0`, `ready`, `error_metric`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- On reset or when `vdd_sense` is below `vpor`, clear the trim code, `ready`, `error_metric`, and drive `vref` low.
- `startup_detector` enables the reference only after `vdd_sense` has been above `vpor` for two consecutive rising `clk` edges.
- `ptat_ctat_core` must generate a behavioral reference metric from `temp_proxy` around `vref_nom`.
- When `trim_req` is high, `trim_controller` updates the 4-bit trim code once per rising `clk` edge to reduce reference error.
- `vref` must reflect the core reference plus trim correction and remain clamped between `vlo` and `vhi`.
- Drive `trim_3..trim_0` as voltage-coded copies of the trim code.
- Assert `ready` after three consecutive enabled updates with `error_metric` magnitude within `ready_tol`.


The required trace names are: `time`, `vdd_sense`, `clk`, `rst`, `trim_req`, `temp_proxy`, `vref`, `trim_3`, `trim_2`, `trim_1`, `trim_0`, `ready`, `error_metric`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
