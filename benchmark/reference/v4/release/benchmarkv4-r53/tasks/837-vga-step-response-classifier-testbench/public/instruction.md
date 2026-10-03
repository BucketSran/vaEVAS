# VGA Step-response Classifier Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `VGA Step-response Classifier` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `vga_step_response_classifier.va`:
  - Module `vga_step_response_classifier` (entry)
    - position 0: `vin` (inout, electrical)
    - position 1: `clk` (inout, electrical)
    - position 2: `rst` (inout, electrical)
    - position 3: `enable` (inout, electrical)
    - position 4: `gain_2` (inout, electrical)
    - position 5: `gain_1` (inout, electrical)
    - position 6: `gain_0` (inout, electrical)
    - position 7: `vout` (inout, electrical)
    - position 8: `overshoot_metric` (inout, electrical)
    - position 9: `settled` (inout, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/vga_step_response_classifier.va`
- DUT instance: `XDUT (vin clk rst enable gain_2 gain_1 gain_0 vout overshoot_metric settled) vga_step_response_classifier`
- Required saved public traces: `vin`, `clk`, `rst`, `enable`, `gain_2`, `gain_1`, `gain_0`, `vout`, `overshoot_metric`, `settled`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `vga_step_response_classifier.vdd` defaults to `0.9`; valid range: finite; overrides vdd.
- `vga_step_response_classifier.vss` defaults to `0.0`; valid range: finite; overrides vss.
- `vga_step_response_classifier.vcm` defaults to `0.45`; valid range: finite; overrides vcm.
- `vga_step_response_classifier.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `vga_step_response_classifier.tr` defaults to `200p from (0:inf)`; valid range: finite; overrides tr.
- `vga_step_response_classifier.gain_lsb` defaults to `0.5`; valid range: finite; overrides gain_lsb.
- `vga_step_response_classifier.settle_tol` defaults to `12e-3`; valid range: finite; overrides settle_tol.
- `vga_step_response_classifier.tick` defaults to `250p from (0:inf)`; valid range: finite; overrides tick.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_ON_RESET_OR_WHEN_DISABLED_DRIVE`: exercise and make observable: On reset or while disabled, restore `prev_code=0` and the unchanged-code counter to zero, drive `vout=vcm`, and drive `overshoot_metric=settled=vss`. Required traces: `time`, `vin`, `clk`, `rst`, `enable`, `gain_2`, `gain_1`, `gain_0`, `vout`, `overshoot_metric`, `settled`.
- `P_ON_EACH_ENABLED_RISING_CLK_EDGE`: exercise and make observable: Poll every `tick`; on each enabled rising `clk` edge decode `code=4*gain_2+2*gain_1+gain_0` and drive `vout=clamp(vcm+(1+gain_lsb*code)*(vin-vcm),vss,vdd)`. Required traces: `time`, `vin`, `clk`, `rst`, `enable`, `gain_2`, `gain_1`, `gain_0`, `vout`, `overshoot_metric`, `settled`.
- `P_APPLY_BOUNDED_SETTLING_WITH_A_CODE`: exercise and make observable: Use the `tr` transition for bounded output smoothing without adding an overshoot excursion to `vout`; expose the code-step proxy separately on `overshoot_metric`. Required traces: `time`, `vin`, `clk`, `rst`, `enable`, `gain_2`, `gain_1`, `gain_0`, `vout`, `overshoot_metric`, `settled`.
- `P_EXPOSE_OVERSHOOT_MAGNITUDE_ON_OVERSHOOT_METRIC`: exercise and make observable: On every enabled rising edge drive `overshoot_metric=vdd*abs(code-prev_code)/7` before storing the current code as `prev_code`. Required traces: `time`, `vin`, `clk`, `rst`, `enable`, `gain_2`, `gain_1`, `gain_0`, `vout`, `overshoot_metric`, `settled`.
- `P_ASSERT_SETTLED_AFTER_TWO_CONSECUTIVE_UPDATES`: exercise and make observable: Use unchanged gain code as the deterministic settling proxy: increment the counter when `code==prev_code`, clear it otherwise, assert `settled=vdd` at count two, and drive `vss` otherwise; a newly changed code therefore needs two subsequent unchanged-code comparisons. Required traces: `time`, `vin`, `clk`, `rst`, `enable`, `gain_2`, `gain_1`, `gain_0`, `vout`, `overshoot_metric`, `settled`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- On reset or when disabled, drive `vout` to `vcm`, clear metric, and clear `settled`.
- On each enabled rising `clk` edge, decode the gain code and update the target output from `vin`.
- Apply bounded settling with a code-dependent overshoot proxy after large gain changes.
- Expose overshoot magnitude on `overshoot_metric`.
- Assert `settled` after two consecutive updates within `settle_tol` of the target.
- Use only voltage-domain behavioral state and voltage contributions on public electrical outputs.
- Do not expose pass/fail flags; expose only the public observable metrics named in the interface.

Treat `gain_2,gain_1,gain_0` as a binary code
`code = 4*gain_2 + 2*gain_1 + gain_0`, with each bit high when its voltage is
greater than `vth`.  The state starts with `prev_code = 0` and an unchanged-code
counter of zero.  On reset or while disabled, restore those values, drive
`vout = vcm`, and drive `overshoot_metric = settled = vss`.

Poll the controls every `tick`.  On each enabled rising `clk` edge, compute

`target = clamp(vcm + (1 + gain_lsb*code)*(vin-vcm), vss, vdd)`

and update `vout` to that target.  The bounded step-response proxy is reported
only through

`overshoot_metric = vdd*abs(code-prev_code)/7`.

Do not add a separate overshoot excursion to `vout`; the public `tr` transition
provides its output smoothing.  If `code == prev_code`, increment the
unchanged-code counter; otherwise clear it to zero.  Assert `settled = vdd`
when that counter reaches two and drive `settled = vss` otherwise, then store
the current code as `prev_code`.  Thus a newly changed code settles after two
subsequent unchanged-code comparisons.  This unchanged-code counter is the
deterministic public proxy for consecutive updates within `settle_tol`; the
`settle_tol` parameter remains part of the compatible public interface.


The required trace names are: `time`, `vin`, `clk`, `rst`, `enable`, `gain_2`, `gain_1`, `gain_0`, `vout`, `overshoot_metric`, `settled`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
