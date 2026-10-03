# VGA Step-response Classifier Bugfix

## Task Contract

The supplied Verilog-A system violates its public circuit contract. Repair the
complete editable bundle.

## Public Verilog-A Interface

Preserve this exact artifact and module interface:

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

The repaired bundle must satisfy every public property:

- `P_ON_RESET_OR_WHEN_DISABLED_DRIVE`: restore: On reset or while disabled, restore `prev_code=0` and the unchanged-code counter to zero, drive `vout=vcm`, and drive `overshoot_metric=settled=vss`. Required traces: `time`, `vin`, `clk`, `rst`, `enable`, `gain_2`, `gain_1`, `gain_0`, `vout`, `overshoot_metric`, `settled`.
- `P_ON_EACH_ENABLED_RISING_CLK_EDGE`: restore: Poll every `tick`; on each enabled rising `clk` edge decode `code=4*gain_2+2*gain_1+gain_0` and drive `vout=clamp(vcm+(1+gain_lsb*code)*(vin-vcm),vss,vdd)`. Required traces: `time`, `vin`, `clk`, `rst`, `enable`, `gain_2`, `gain_1`, `gain_0`, `vout`, `overshoot_metric`, `settled`.
- `P_APPLY_BOUNDED_SETTLING_WITH_A_CODE`: restore: Use the `tr` transition for bounded output smoothing without adding an overshoot excursion to `vout`; expose the code-step proxy separately on `overshoot_metric`. Required traces: `time`, `vin`, `clk`, `rst`, `enable`, `gain_2`, `gain_1`, `gain_0`, `vout`, `overshoot_metric`, `settled`.
- `P_EXPOSE_OVERSHOOT_MAGNITUDE_ON_OVERSHOOT_METRIC`: restore: On every enabled rising edge drive `overshoot_metric=vdd*abs(code-prev_code)/7` before storing the current code as `prev_code`. Required traces: `time`, `vin`, `clk`, `rst`, `enable`, `gain_2`, `gain_1`, `gain_0`, `vout`, `overshoot_metric`, `settled`.
- `P_ASSERT_SETTLED_AFTER_TWO_CONSECUTIVE_UPDATES`: restore: Use unchanged gain code as the deterministic settling proxy: increment the counter when `code==prev_code`, clear it otherwise, assert `settled=vdd` at count two, and drive `vss` otherwise; a newly changed code therefore needs two subsequent unchanged-code comparisons. Required traces: `time`, `vin`, `clk`, `rst`, `enable`, `gain_2`, `gain_1`, `gain_0`, `vout`, `overshoot_metric`, `settled`.


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


## Modeling Constraints

- Use deterministic voltage-domain behavioral Verilog-A.
- Do not hard-code validation stimulus, stop times, sample windows, gold internals, or simulator side channels.
- Preserve the exact file set, module graph, ports, parameters, and public traces.
- Do not add debug outputs, validation state, side channels, or stimulus-specific fixes.

## Output Contract

Return the repaired bundle with exactly these paths: `vga_step_response_classifier.va`.
Every supplied `.va` file is editable; do not add or omit files.
