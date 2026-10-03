# Buck Converter Controller Macro Bugfix

## Task Contract

The supplied Verilog-A system violates its public circuit contract. Repair the
complete editable bundle.

## Public Verilog-A Interface

Preserve this exact artifact and module interface:

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

The repaired bundle must satisfy every public property:

- `P_RESET_DISABLE_CLEAR`: restore: Reset or disabled operation clears PWM, duty metric, soft reference, and power-good. Required traces: `time`, `clk`, `rst`, `enable`, `pwm`, `duty_metric`, `soft_ref`, `pgood`.
- `P_SOFT_START_TRACKING`: restore: At each enabled rising edge move soft_ref toward vref by soft_step without overshoot and set duty_up high exactly when vfb<soft_ref. Required traces: `time`, `clk`, `rst`, `enable`, `vref`, `soft_ref`.
- `P_DUTY_DIRECTION_BOUNDS`: restore: Starting from zero, add 0.05 to duty when duty_up is high and subtract 0.05 otherwise, clamp the post-update value to [duty_min,duty_max], and expose it on duty_metric. Required traces: `time`, `clk`, `rst`, `enable`, `vfb`, `soft_ref`, `duty_metric`.
- `P_PWM_ENCODING`: restore: After each duty update advance carrier_count=(carrier_count+1)%20 and drive pwm=vdd exactly when carrier_count+0.5<20*duty_metric, otherwise vss. Required traces: `time`, `clk`, `rst`, `enable`, `pwm`, `duty_metric`.
- `P_POWER_GOOD_QUALIFICATION`: restore: Count consecutive enabled edges with abs(vfb-vref)<=pgood_tol, assert pgood at count three, and clear the count and pgood when qualification is lost; reset or disable also clears all controller state. Required traces: `time`, `clk`, `rst`, `enable`, `vfb`, `vref`, `pgood`.


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


## Modeling Constraints

- Use deterministic voltage-domain transient behavior.
- Use portable Spectre-compatible Verilog-A and voltage contributions for public outputs.
- Do not use branch-current oracles, hidden pass/fail ports, checker side channels, or testbench code in the DUT bundle.
- Preserve the exact file set, module graph, ports, parameters, and public traces.
- Do not add debug outputs, validation state, side channels, or stimulus-specific fixes.

## Output Contract

Return the repaired bundle with exactly these paths: `buck_ctrl_top.va`, `error_comparator.va`, `power_good.va`, `pwm_modulator.va`, `soft_start.va`.
Every supplied `.va` file is editable; do not add or omit files.
