# DFE Error-proxy Loop Bugfix

## Task Contract

The supplied Verilog-A system violates its public circuit contract. Repair the
complete editable bundle.

## Public Verilog-A Interface

Preserve this exact artifact and module interface:

- Artifact `dfe_error_proxy_loop_top.va`:
  - Module `dfe_error_proxy_loop_top` (entry)
    - position 0: `sample_in` (inout, electrical)
    - position 1: `decision_clk` (inout, electrical)
    - position 2: `rst` (inout, electrical)
    - position 3: `enable` (inout, electrical)
    - position 4: `tap_1` (inout, electrical)
    - position 5: `tap_0` (inout, electrical)
    - position 6: `corrected_out` (inout, electrical)
    - position 7: `error_metric` (inout, electrical)
    - position 8: `converged` (inout, electrical)
- Artifact `decision_history.va`:
  - Module `decision_history` (required_submodule)
    - position 0: `sample_in` (inout, electrical)
    - position 1: `decision_clk` (inout, electrical)
    - position 2: `rst` (inout, electrical)
    - position 3: `enable` (inout, electrical)
    - position 4: `hist_1` (inout, electrical)
    - position 5: `hist_0` (inout, electrical)
- Artifact `feedback_correction_core.va`:
  - Module `feedback_correction_core` (required_submodule)
    - position 0: `sample_in` (inout, electrical)
    - position 1: `decision_clk` (inout, electrical)
    - position 2: `rst` (inout, electrical)
    - position 3: `enable` (inout, electrical)
    - position 4: `hist_1` (inout, electrical)
    - position 5: `hist_0` (inout, electrical)
    - position 6: `tap_1` (inout, electrical)
    - position 7: `tap_0` (inout, electrical)
    - position 8: `corrected_out` (inout, electrical)
    - position 9: `error_metric` (inout, electrical)
    - position 10: `converged` (inout, electrical)

## Public Parameter Contract

- `dfe_error_proxy_loop_top.vdd` defaults to `0.9`; valid range: finite; overrides vdd.
- `dfe_error_proxy_loop_top.vss` defaults to `0.0`; valid range: finite; overrides vss.
- `dfe_error_proxy_loop_top.vcm` defaults to `0.45`; valid range: finite; overrides vcm.
- `dfe_error_proxy_loop_top.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `dfe_error_proxy_loop_top.tr` defaults to `200p from (0:inf)`; valid range: finite; overrides tr.
- `dfe_error_proxy_loop_top.residual_tol` defaults to `35e-3 from [0:inf)`; valid range: finite; overrides residual_tol.
- `decision_history.vdd` defaults to `0.9`; valid range: finite; overrides vdd.
- `decision_history.vss` defaults to `0.0`; valid range: finite; overrides vss.
- `decision_history.vcm` defaults to `0.45`; valid range: finite; overrides vcm.
- `decision_history.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `decision_history.tr` defaults to `200p from (0:inf)`; valid range: finite; overrides tr.
- `feedback_correction_core.vdd` defaults to `0.9`; valid range: finite; overrides vdd.
- `feedback_correction_core.vss` defaults to `0.0`; valid range: finite; overrides vss.
- `feedback_correction_core.vcm` defaults to `0.45`; valid range: finite; overrides vcm.
- `feedback_correction_core.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `feedback_correction_core.tr` defaults to `200p from (0:inf)`; valid range: finite; overrides tr.
- `feedback_correction_core.residual_tol` defaults to `35e-3 from [0:inf)`; valid range: finite; overrides residual_tol.


## Required Behavior

The repaired bundle must satisfy every public property:

- `P_ON_RESET_OR_WHEN_DISABLED_CLEAR`: restore: On reset or when disabled, clear signed tap weights and decision history; drive `tap_1`, `tap_0`, and `corrected_out` to `vcm`, and drive `error_metric` and `converged` to `vss`. Required traces: `time`, `sample_in`, `decision_clk`, `rst`, `enable`, `tap_1`, `tap_0`, `corrected_out`, `error_metric`, `converged`.
- `P_ON_EACH_ENABLED_DECISION_CLOCK_LATCH`: restore: On each enabled rising `decision_clk` edge, use the pre-edge history for the weight update, then latch `d = +1` when `sample_in >= vcm` else `-1` and shift `h0 = h1; h1 = d`. Required traces: `time`, `sample_in`, `decision_clk`, `rst`, `enable`, `tap_1`, `tap_0`, `corrected_out`, `error_metric`, `converged`.
- `P_USE_THE_PREVIOUS_DECISION_HISTORY_TO`: restore: With `x = sample_in-vcm`, compute `r0 = x-w1*h1-w0*h0`, update `w1 = clamp(w1+0.04*r0*h1,-0.18,0.18)` and `w0 = clamp(w0+0.025*r0*h0,-0.12,0.12)`, then recompute `r = x-w1*h1-w0*h0`. Required traces: `time`, `sample_in`, `decision_clk`, `rst`, `enable`, `tap_1`, `tap_0`, `corrected_out`, `error_metric`, `converged`.
- `P_EXPOSE_THE_ABSOLUTE_RESIDUAL_ON_ERROR`: restore: Drive `tap_1 = vcm+w1`, `tap_0 = vcm+w0`, `corrected_out = clamp(vcm+r,vss,vdd)`, and `error_metric = clamp(abs(r),vss,vdd)` after each enabled update. Required traces: `time`, `sample_in`, `decision_clk`, `rst`, `enable`, `tap_1`, `tap_0`, `corrected_out`, `error_metric`, `converged`.
- `P_ASSERT_CONVERGED_WHEN_THE_RESIDUAL_REMAINS`: restore: Drive `converged = vdd` after three consecutive enabled updates with `abs(r) <= residual_tol`, otherwise drive `vss`. Required traces: `time`, `sample_in`, `decision_clk`, `rst`, `enable`, `tap_1`, `tap_0`, `corrected_out`, `error_metric`, `converged`.


The following canonical public behavior is normative for this derived form:

- On reset or when disabled, clear taps, corrected output, error metric, and `converged`.
- On each enabled decision clock, latch the sign of `sample_in - vcm` as the current decision.
- Use the previous decision history to subtract a two-tap feedback estimate from the live sample.
- Expose the absolute residual on `error_metric`.
- Assert `converged` when the residual remains below `residual_tol` for three decisions.
- Use only voltage-domain behavioral state and voltage contributions on public electrical outputs.
- Do not expose pass/fail flags; expose only the public observable metrics named in the interface.

`tap_1` and `tap_0` are DUT-driven observable tap-weight outputs, not
coefficient inputs.  Represent a signed weight `w` as `vcm + w`.  On reset or
while disabled drive both tap outputs and `corrected_out` to `vcm`, and drive
`error_metric` and `converged` to `vss`.

Use signed decision history `h1, h0`, initialized to zero.  At each enabled
rising `decision_clk` edge, use the history that existed before that edge and
perform this exact update, in order:

1. `x = sample_in - vcm` and `r0 = x - w1*h1 - w0*h0`.
2. `w1 = clamp(w1 + 0.04*r0*h1, -0.18, 0.18)` and
   `w0 = clamp(w0 + 0.025*r0*h0, -0.12, 0.12)`.
3. `r = x - w1*h1 - w0*h0` using the updated weights.
4. Latch `d = +1` when `sample_in >= vcm`, otherwise `d = -1`, then shift
   history as `h0 = h1; h1 = d`.

After the edge, drive `tap_1 = vcm + w1`, `tap_0 = vcm + w0`,
`corrected_out = clamp(vcm + r, vss, vdd)`, and
`error_metric = clamp(abs(r), vss, vdd)`.  `converged` is `vdd` after three
consecutive enabled edge updates with `abs(r) <= residual_tol`, and is `vss`
otherwise.  Reset or disable clears both weights, both history values, the
residual, and the convergence streak.


## Modeling Constraints

- Use deterministic voltage-domain behavioral Verilog-A.
- Do not hard-code validation stimulus, stop times, sample windows, gold internals, or simulator side channels.
- Preserve the exact file set, module graph, ports, parameters, and public traces.
- Do not add debug outputs, validation state, side channels, or stimulus-specific fixes.

## Output Contract

Return the repaired bundle with exactly these paths: `dfe_error_proxy_loop_top.va`, `decision_history.va`, `feedback_correction_core.va`.
Every supplied `.va` file is editable; do not add or omit files.
