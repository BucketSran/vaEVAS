# Duty-cycle Corrector Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Duty-cycle Corrector` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `dcc_top.va`:
  - Module `dcc_top` (entry)
    - position 0: `clk_in` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `enable` (input, electrical)
    - position 3: `clk_out` (output, electrical)
    - position 4: `trim_3` (output, electrical)
    - position 5: `trim_2` (output, electrical)
    - position 6: `trim_1` (output, electrical)
    - position 7: `trim_0` (output, electrical)
    - position 8: `duty_metric` (output, electrical)
    - position 9: `locked` (output, electrical)
- Artifact `duty_meter.va`:
  - Module `duty_meter` (required_submodule)
    - position 0: `clk_in` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `enable` (input, electrical)
    - position 3: `duty_metric` (output, electrical)
    - position 4: `measure_clk` (output, electrical)
- Artifact `trim_controller.va`:
  - Module `trim_controller` (required_submodule)
    - position 0: `measure_clk` (input, electrical)
    - position 1: `duty_metric` (input, electrical)
    - position 2: `rst` (input, electrical)
    - position 3: `enable` (input, electrical)
    - position 4: `trim_3` (output, electrical)
    - position 5: `trim_2` (output, electrical)
    - position 6: `trim_1` (output, electrical)
    - position 7: `trim_0` (output, electrical)
    - position 8: `locked` (output, electrical)
- Artifact `delay_pair.va`:
  - Module `delay_pair` (required_submodule)
    - position 0: `clk_in` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `enable` (input, electrical)
    - position 3: `trim_3` (input, electrical)
    - position 4: `trim_2` (input, electrical)
    - position 5: `trim_1` (input, electrical)
    - position 6: `trim_0` (input, electrical)
    - position 7: `clk_out` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include paths: `./dut/dcc_top.va`, `./dut/duty_meter.va`, `./dut/trim_controller.va`, `./dut/delay_pair.va`
- DUT instance: `XDUT (clk_in rst enable clk_out trim_3 trim_2 trim_1 trim_0 duty_metric locked) dcc_top tr=20p`
- Required saved public traces: `clk_in`, `rst`, `enable`, `clk_out`, `trim_3`, `trim_2`, `trim_1`, `trim_0`, `duty_metric`, `locked`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `dcc_top.vdd` defaults to `0.9`; valid range: finite; overrides vdd for module dcc_top.
- `dcc_top.vss` defaults to `0.0`; valid range: finite; overrides vss for module dcc_top.
- `dcc_top.vth` defaults to `0.45`; valid range: finite; overrides vth for module dcc_top.
- `dcc_top.target_duty` defaults to `0.5`; valid range: finite; overrides target_duty for module dcc_top.
- `dcc_top.duty_tol` defaults to `0.03`; valid range: finite; overrides duty_tol for module dcc_top.
- `dcc_top.trim_step` defaults to `5e-12`; valid range: finite; overrides trim_step for module dcc_top.
- `dcc_top.tr` defaults to `100p`; valid range: finite; overrides tr for module dcc_top.
- `duty_meter.vdd` defaults to `0.9`; valid range: finite; overrides vdd for module duty_meter.
- `duty_meter.vss` defaults to `0.0`; valid range: finite; overrides vss for module duty_meter.
- `duty_meter.vth` defaults to `0.45`; valid range: finite; overrides vth for module duty_meter.
- `duty_meter.tr` defaults to `100p`; valid range: finite; overrides tr for module duty_meter.
- `trim_controller.vdd` defaults to `0.9`; valid range: finite; overrides vdd for module trim_controller.
- `trim_controller.vss` defaults to `0.0`; valid range: finite; overrides vss for module trim_controller.
- `trim_controller.vth` defaults to `0.45`; valid range: finite; overrides vth for module trim_controller.
- `trim_controller.target_duty` defaults to `0.5`; valid range: finite; overrides target_duty for module trim_controller.
- `trim_controller.duty_tol` defaults to `0.03`; valid range: finite; overrides duty_tol for module trim_controller.
- `trim_controller.tr` defaults to `100p`; valid range: finite; overrides tr for module trim_controller.
- `delay_pair.vdd` defaults to `0.9`; valid range: finite; overrides vdd for module delay_pair.
- `delay_pair.vss` defaults to `0.0`; valid range: finite; overrides vss for module delay_pair.
- `delay_pair.vth` defaults to `0.45`; valid range: finite; overrides vth for module delay_pair.
- `delay_pair.trim_step` defaults to `5e-12`; valid range: finite; overrides trim_step for module delay_pair.
- `delay_pair.tr` defaults to `100p`; valid range: finite; overrides tr for module delay_pair.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RESET_DISABLE_CLEAR`: exercise and make observable: Reset or low enable clears trim, duty metric, lock, and output clock. Required traces: `time`, `clk_in`, `rst`, `enable`, `clk_out`, `trim_3`, `trim_2`, `trim_1`, `trim_0`, `duty_metric`, `locked`.
- `P_DUTY_MEASUREMENT`: exercise and make observable: The metric reports high-time fraction over each complete input-clock cycle. Required traces: `time`, `clk_in`, `rst`, `enable`, `duty_metric`.
- `P_TRIM_DIRECTION`: exercise and make observable: The trim code moves up below the target window and down above it, with rail saturation. Required traces: `time`, `clk_in`, `rst`, `enable`, `trim_3`, `trim_2`, `trim_1`, `trim_0`, `duty_metric`.
- `P_EDGE_DELAY`: exercise and make observable: Rising edges pass without intentional delay while falling edges receive the latched trim-code delay. Required traces: `time`, `clk_in`, `clk_out`, `rst`, `enable`, `trim_3`, `trim_2`, `trim_1`, `trim_0`.
- `P_LOCK_QUALIFICATION`: exercise and make observable: Lock asserts after three consecutive measured cycles inside the target window. Required traces: `time`, `clk_in`, `rst`, `enable`, `duty_metric`, `locked`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- On reset or when `enable` is low, clear the trim code, `duty_metric`, `locked`, and drive `clk_out` low.
- `duty_meter` measures high-time fraction over complete input-clock cycles.
- `trim_controller` increments the trim code when measured duty is below `target_duty - duty_tol` and decrements it when above `target_duty + duty_tol`.
- `delay_pair` passes each rising input edge without intentional delay and delays its corresponding falling edge by `trim_code * trim_step`, using the trim code latched at that rising edge. A trim update must not retime an already active output pulse.
- Clamp the trim code to 0 through 15 and drive `trim_3..trim_0` as voltage-coded bits.
- Assert `locked` after three consecutive completed cycles within tolerance.
- `duty_metric` must expose the latest measured duty fraction directly as a voltage, so a measured fraction of 0.5 is reported as 0.5 V. Reset or low `enable` cancels a pending falling edge and drives `clk_out` low.


The required trace names are: `time`, `clk_in`, `rst`, `enable`, `clk_out`, `trim_3`, `trim_2`, `trim_1`, `trim_0`, `duty_metric`, `locked`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
