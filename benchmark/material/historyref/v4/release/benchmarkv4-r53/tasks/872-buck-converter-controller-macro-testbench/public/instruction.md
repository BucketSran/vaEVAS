# Buck Converter Controller Macro Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Buck Converter Controller Macro` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `buck_ctrl_top.va`:
  - Module `buck_ctrl_top` (entry)
    - position 0: `vfb` (input, electrical)
    - position 1: `vref` (input, electrical)
    - position 2: `clk` (input, electrical)
    - position 3: `rst` (input, electrical)
    - position 4: `enable` (input, electrical)
    - position 5: `pwm` (output, electrical)
    - position 6: `duty_metric` (output, electrical)
    - position 7: `soft_ref` (output, electrical)
    - position 8: `pgood` (output, electrical)
- Artifact `error_comparator.va`:
  - Module `error_comparator` (required_submodule)
    - position 0: `vfb` (input, electrical)
    - position 1: `soft_ref` (input, electrical)
    - position 2: `duty_up` (output, electrical)
- Artifact `power_good.va`:
  - Module `power_good` (required_submodule)
    - position 0: `clk` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `enable` (input, electrical)
    - position 3: `vfb` (input, electrical)
    - position 4: `vref` (input, electrical)
    - position 5: `pgood` (output, electrical)
- Artifact `pwm_modulator.va`:
  - Module `pwm_modulator` (required_submodule)
    - position 0: `clk` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `enable` (input, electrical)
    - position 3: `duty_up` (input, electrical)
    - position 4: `pwm` (output, electrical)
    - position 5: `duty_metric` (output, electrical)
- Artifact `soft_start.va`:
  - Module `soft_start` (required_submodule)
    - position 0: `clk` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `enable` (input, electrical)
    - position 3: `vref` (input, electrical)
    - position 4: `soft_ref` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include paths: `./dut/buck_ctrl_top.va`, `./dut/error_comparator.va`, `./dut/power_good.va`, `./dut/pwm_modulator.va`, `./dut/soft_start.va`
- DUT instance: `XDUT (vfb vref clk rst enable pwm duty_metric soft_ref pgood) buck_ctrl_top pgood_tol=0.025 soft_step=0.025`
- Required saved public traces: `vfb`, `vref`, `clk`, `rst`, `enable`, `pwm`, `duty_metric`, `soft_ref`, `pgood`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `buck_ctrl_top.vdd` defaults to `0.9` V; valid range: vdd > vss; overrides the public vdd behavior parameter consistently for this module.
- `buck_ctrl_top.vss` defaults to `0` V; valid range: vss < vdd; overrides the public vss behavior parameter consistently for this module.
- `buck_ctrl_top.vth` defaults to `0.45` V; valid range: vth is finite and preserves the public operating range; overrides the public vth behavior parameter consistently for this module.
- `buck_ctrl_top.duty_min` defaults to `0.05`; valid range: 0 <= duty_min < duty_max; overrides the public duty_min behavior parameter consistently for this module.
- `buck_ctrl_top.duty_max` defaults to `0.95`; valid range: duty_min < duty_max <= 1; overrides the public duty_max behavior parameter consistently for this module.
- `buck_ctrl_top.soft_step` defaults to `0.025` V; valid range: soft_step is finite and preserves the public operating range; overrides the public soft_step behavior parameter consistently for this module.
- `buck_ctrl_top.pgood_tol` defaults to `0.025` V; valid range: pgood_tol is finite and preserves the public operating range; overrides the public pgood_tol behavior parameter consistently for this module.
- `buck_ctrl_top.tr` defaults to `2e-10` s; valid range: tr > 0; overrides the public tr behavior parameter consistently for this module.
- `error_comparator.vdd` defaults to `0.9` V; valid range: vdd > vss; overrides the public vdd behavior parameter consistently for this module.
- `error_comparator.vss` defaults to `0` V; valid range: vss < vdd; overrides the public vss behavior parameter consistently for this module.
- `error_comparator.tr` defaults to `2e-10` s; valid range: tr > 0; overrides the public tr behavior parameter consistently for this module.
- `power_good.vdd` defaults to `0.9` V; valid range: vdd > vss; overrides the public vdd behavior parameter consistently for this module.
- `power_good.vss` defaults to `0` V; valid range: vss < vdd; overrides the public vss behavior parameter consistently for this module.
- `power_good.vth` defaults to `0.45` V; valid range: vth is finite and preserves the public operating range; overrides the public vth behavior parameter consistently for this module.
- `power_good.pgood_tol` defaults to `0.025` V; valid range: pgood_tol is finite and preserves the public operating range; overrides the public pgood_tol behavior parameter consistently for this module.
- `power_good.tr` defaults to `2e-10` s; valid range: tr > 0; overrides the public tr behavior parameter consistently for this module.
- `pwm_modulator.vdd` defaults to `0.9` V; valid range: vdd > vss; overrides the public vdd behavior parameter consistently for this module.
- `pwm_modulator.vss` defaults to `0` V; valid range: vss < vdd; overrides the public vss behavior parameter consistently for this module.
- `pwm_modulator.vth` defaults to `0.45` V; valid range: vth is finite and preserves the public operating range; overrides the public vth behavior parameter consistently for this module.
- `pwm_modulator.duty_min` defaults to `0.05`; valid range: 0 <= duty_min < duty_max; overrides the public duty_min behavior parameter consistently for this module.
- `pwm_modulator.duty_max` defaults to `0.95`; valid range: duty_min < duty_max <= 1; overrides the public duty_max behavior parameter consistently for this module.
- `pwm_modulator.tr` defaults to `2e-10` s; valid range: tr > 0; overrides the public tr behavior parameter consistently for this module.
- `soft_start.vdd` defaults to `0.9` V; valid range: vdd > vss; overrides the public vdd behavior parameter consistently for this module.
- `soft_start.vss` defaults to `0` V; valid range: vss < vdd; overrides the public vss behavior parameter consistently for this module.
- `soft_start.vth` defaults to `0.45` V; valid range: vth is finite and preserves the public operating range; overrides the public vth behavior parameter consistently for this module.
- `soft_start.soft_step` defaults to `0.025` V; valid range: soft_step is finite and preserves the public operating range; overrides the public soft_step behavior parameter consistently for this module.
- `soft_start.tr` defaults to `2e-10` s; valid range: tr > 0; overrides the public tr behavior parameter consistently for this module.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RESET_DISABLE_CLEAR`: exercise and make observable: Reset or disabled operation clears PWM, duty metric, soft reference, and power-good. Required traces: `time`, `clk`, `rst`, `enable`, `pwm`, `duty_metric`, `soft_ref`, `pgood`.
- `P_SOFT_START_TRACKING`: exercise and make observable: At each enabled rising edge move soft_ref toward vref by soft_step without overshoot and set duty_up high exactly when vfb<soft_ref. Required traces: `time`, `clk`, `rst`, `enable`, `vref`, `soft_ref`.
- `P_DUTY_DIRECTION_BOUNDS`: exercise and make observable: Starting from zero, add 0.05 to duty when duty_up is high and subtract 0.05 otherwise, clamp the post-update value to [duty_min,duty_max], and expose it on duty_metric. Required traces: `time`, `clk`, `rst`, `enable`, `vfb`, `soft_ref`, `duty_metric`.
- `P_PWM_ENCODING`: exercise and make observable: After each duty update advance carrier_count=(carrier_count+1)%20 and drive pwm=vdd exactly when carrier_count+0.5<20*duty_metric, otherwise vss. Required traces: `time`, `clk`, `rst`, `enable`, `pwm`, `duty_metric`.
- `P_POWER_GOOD_QUALIFICATION`: exercise and make observable: Count consecutive enabled edges with abs(vfb-vref)<=pgood_tol, assert pgood at count three, and clear the count and pgood when qualification is lost; reset or disable also clears all controller state. Required traces: `time`, `clk`, `rst`, `enable`, `vfb`, `vref`, `pgood`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- On reset or when `enable` is low, clear `pwm`, `duty_metric`, `soft_ref`, and `pgood`.
- `soft_start` ramps `soft_ref` toward `vref` by at most `soft_step` per rising `clk` edge.
- `error_comparator` compares `vfb` against `soft_ref` and requests a larger duty metric when feedback is low.
- `pwm_modulator` updates a bounded duty metric once per rising `clk` edge and drives `pwm` from that metric.
- Clamp `duty_metric` between `duty_min` and `duty_max`.
- `power_good` asserts `pgood` after three consecutive cycles where `vfb` is within `pgood_tol` of `vref`.
- This DUT models the controller only; it must not instantiate an inductor, switch device, or current-domain power stage.

On every enabled rising edge, move `soft_ref` toward `vref` by `soft_step`
without overshoot. Set the internal `duty_up` decision high exactly when
`vfb < soft_ref`. Starting from duty zero, add 0.05 when `duty_up` is high and
subtract 0.05 otherwise, then clamp the updated duty to
`[duty_min,duty_max]` and expose it on `duty_metric`.

Maintain an integer carrier counter modulo 20. After updating the duty,
advance the counter as `carrier_count=(carrier_count+1)%20` and drive
`pwm=vdd` exactly when `carrier_count+0.5 < 20*duty_metric`, otherwise drive
`pwm=vss`. Count consecutive enabled edges satisfying
`abs(vfb-vref)<=pgood_tol`; assert `pgood` at count three and clear both the
count and `pgood` when the condition is lost. Reset or disable clears soft
reference, duty, PWM, carrier count, power-good count, and `pgood` to vss.


The required trace names are: `time`, `vfb`, `vref`, `clk`, `rst`, `enable`, `pwm`, `duty_metric`, `soft_ref`, `pgood`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
