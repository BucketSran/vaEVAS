# Quadrature Correction Loop Bugfix

## Task Contract

The supplied Verilog-A system violates its public circuit contract. Repair the
complete editable bundle.

## Public Verilog-A Interface

Preserve this exact artifact and module interface:

- Artifact `quad_corr_top.va`:
  - Module `quad_corr_top` (entry)
    - position 0: `i_in` (input, electrical)
    - position 1: `q_in` (input, electrical)
    - position 2: `clk` (input, electrical)
    - position 3: `rst` (input, electrical)
    - position 4: `cal_en` (input, electrical)
    - position 5: `i_out` (output, electrical)
    - position 6: `q_out` (output, electrical)
    - position 7: `gain_code_3` (output, electrical)
    - position 8: `gain_code_2` (output, electrical)
    - position 9: `gain_code_1` (output, electrical)
    - position 10: `gain_code_0` (output, electrical)
    - position 11: `phase_code_3` (output, electrical)
    - position 12: `phase_code_2` (output, electrical)
    - position 13: `phase_code_1` (output, electrical)
    - position 14: `phase_code_0` (output, electrical)
    - position 15: `error_metric` (output, electrical)
    - position 16: `locked` (output, electrical)
- Artifact `gain_trim.va`:
  - Module `gain_trim` (required_submodule)
    - position 0: `i_in` (input, electrical)
    - position 1: `q_in` (input, electrical)
    - position 2: `clk` (input, electrical)
    - position 3: `rst` (input, electrical)
    - position 4: `cal_en` (input, electrical)
    - position 5: `gain_code_3` (output, electrical)
    - position 6: `gain_code_2` (output, electrical)
    - position 7: `gain_code_1` (output, electrical)
    - position 8: `gain_code_0` (output, electrical)
- Artifact `skew_estimator.va`:
  - Module `skew_estimator` (required_submodule)
    - position 0: `i_in` (input, electrical)
    - position 1: `q_in` (input, electrical)
    - position 2: `clk` (input, electrical)
    - position 3: `rst` (input, electrical)
    - position 4: `cal_en` (input, electrical)
    - position 5: `phase_code_3` (output, electrical)
    - position 6: `phase_code_2` (output, electrical)
    - position 7: `phase_code_1` (output, electrical)
    - position 8: `phase_code_0` (output, electrical)
    - position 9: `error_metric` (output, electrical)
    - position 10: `locked` (output, electrical)
- Artifact `corrector.va`:
  - Module `corrector` (required_submodule)
    - position 0: `i_in` (input, electrical)
    - position 1: `q_in` (input, electrical)
    - position 2: `rst` (input, electrical)
    - position 3: `gain_code_3` (input, electrical)
    - position 4: `gain_code_2` (input, electrical)
    - position 5: `gain_code_1` (input, electrical)
    - position 6: `gain_code_0` (input, electrical)
    - position 7: `phase_code_3` (input, electrical)
    - position 8: `phase_code_2` (input, electrical)
    - position 9: `phase_code_1` (input, electrical)
    - position 10: `phase_code_0` (input, electrical)
    - position 11: `i_out` (output, electrical)
    - position 12: `q_out` (output, electrical)

## Public Parameter Contract

- `quad_corr_top.vdd` defaults to `0.9`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vdd behavior for module quad_corr_top.
- `quad_corr_top.vss` defaults to `0.0`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vss behavior for module quad_corr_top.
- `quad_corr_top.vcm` defaults to `0.45`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vcm behavior for module quad_corr_top.
- `quad_corr_top.vth` defaults to `0.45`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vth behavior for module quad_corr_top.
- `quad_corr_top.trim_lsb` defaults to `10e-3` s; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public trim_lsb behavior for module quad_corr_top.
- `quad_corr_top.error_tol` defaults to `15e-3`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public error_tol behavior for module quad_corr_top.
- `quad_corr_top.tr` defaults to `200p from (0:inf)` s; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public tr behavior for module quad_corr_top.
- `gain_trim.vdd` defaults to `0.9`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vdd behavior for module gain_trim.
- `gain_trim.vss` defaults to `0.0`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vss behavior for module gain_trim.
- `gain_trim.vcm` defaults to `0.45`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vcm behavior for module gain_trim.
- `gain_trim.vth` defaults to `0.45`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vth behavior for module gain_trim.
- `gain_trim.trim_lsb` defaults to `10e-3` s; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public trim_lsb behavior for module gain_trim.
- `gain_trim.error_tol` defaults to `15e-3`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public error_tol behavior for module gain_trim.
- `gain_trim.tr` defaults to `200p from (0:inf)` s; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public tr behavior for module gain_trim.
- `skew_estimator.vdd` defaults to `0.9`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vdd behavior for module skew_estimator.
- `skew_estimator.vss` defaults to `0.0`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vss behavior for module skew_estimator.
- `skew_estimator.vcm` defaults to `0.45`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vcm behavior for module skew_estimator.
- `skew_estimator.vth` defaults to `0.45`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vth behavior for module skew_estimator.
- `skew_estimator.trim_lsb` defaults to `10e-3` s; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public trim_lsb behavior for module skew_estimator.
- `skew_estimator.error_tol` defaults to `15e-3`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public error_tol behavior for module skew_estimator.
- `skew_estimator.tr` defaults to `200p from (0:inf)` s; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public tr behavior for module skew_estimator.
- `corrector.vdd` defaults to `0.9`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vdd behavior for module corrector.
- `corrector.vss` defaults to `0.0`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vss behavior for module corrector.
- `corrector.vcm` defaults to `0.45`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vcm behavior for module corrector.
- `corrector.vth` defaults to `0.45`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vth behavior for module corrector.
- `corrector.trim_lsb` defaults to `10e-3` s; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public trim_lsb behavior for module corrector.
- `corrector.tr` defaults to `200p from (0:inf)` s; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public tr behavior for module corrector.


## Required Behavior

The repaired bundle must satisfy every public property:

- `P_RESET_CLEAR`: restore: Reset asynchronously clears signed_gain, signed_phase, both encoded trim buses, error_metric, the qualification counter, and locked, and drives i_out=q_out=vcm. Required traces: `time`, `rst`, `i_out`, `q_out`, `gain_code_3`, `gain_code_2`, `gain_code_1`, `gain_code_0`, `phase_code_3`, `phase_code_2`, `phase_code_1`, `phase_code_0`, `error_metric`, `locked`.
- `P_TRIM_DIRECTION`: restore: On each enabled rising edge update signed_gain from gain_error=abs(i_in-vcm)-abs(q_in-vcm)-signed_gain*trim_lsb and signed_phase from phase_error=(i_in-vcm)*(q_in-vcm)-signed_phase*trim_lsb using +/-error_tol thresholds, saturating each to -8..7 and encoding negatives as code=7-signed_value. Required traces: `time`, `i_in`, `q_in`, `clk`, `cal_en`, `gain_code_3`, `gain_code_2`, `gain_code_1`, `gain_code_0`, `phase_code_3`, `phase_code_2`, `phase_code_1`, `phase_code_0`, `error_metric`.
- `P_CORRECTION_APPLICATION`: restore: Decode signed trim buses, set gain_corr=signed_gain*trim_lsb and phase_corr=signed_phase*trim_lsb, and clamp i_out=vcm+(i_in-vcm)-0.5*gain_corr and q_out=vcm+(q_in-vcm)+0.5*gain_corr-phase_corr*(i_in-vcm)/vcm to the supplies. Required traces: `time`, `i_in`, `q_in`, `rst`, `i_out`, `q_out`, `gain_code_3`, `gain_code_2`, `gain_code_1`, `gain_code_0`, `phase_code_3`, `phase_code_2`, `phase_code_1`, `phase_code_0`.
- `P_LOCK_HOLD`: restore: Expose post-update phase_error on error_metric; count inclusive in-tolerance pre-update phase errors, clear the count on a phase update, assert locked at count three, and hold codes and correction while cal_en is low. Required traces: `time`, `clk`, `cal_en`, `gain_code_3`, `gain_code_2`, `gain_code_1`, `gain_code_0`, `phase_code_3`, `phase_code_2`, `phase_code_1`, `phase_code_0`, `error_metric`, `locked`.


The following canonical public behavior is normative for this derived form:

- On reset, clear gain and phase trim codes, outputs, `error_metric`, and `locked`.
- When `cal_en` is high, `skew_estimator` samples I/Q imbalance once per rising `clk` edge and updates a signed public error metric.
- `gain_trim` updates the gain code in the direction that reduces amplitude imbalance between I and Q deviations from `vcm`.
- `corrector` applies the gain and phase trim codes to drive corrected `i_out` and `q_out`.
- Clamp gain and phase trim codes to 0 through 15 and expose them on their voltage-coded output buses.
- Assert `locked` after three consecutive calibration updates where `error_metric` magnitude is within `error_tol`.
- When `cal_en` is low, hold trim codes and continue applying the last correction.

Use signed trim states `signed_gain,signed_phase` in the range -8 through 7.
Encode a nonnegative signed value directly as public code 0 through 7, and
encode a negative value as `code = 7-signed_value` (so -1 through -8 map to
8 through 15). On each enabled rising edge compute

`gain_error = abs(i_in-vcm) - abs(q_in-vcm) - signed_gain*trim_lsb`

and increment/decrement `signed_gain` when this error is respectively above
`error_tol` or below `-error_tol`. Independently compute

`phase_error = (i_in-vcm)*(q_in-vcm) - signed_phase*trim_lsb`

and update `signed_phase` by the same threshold rule. Expose the post-update
`phase_error` on `error_metric`. Count consecutive edges on which the
pre-update phase error is within the inclusive tolerance; clear the count on a
phase update and assert `locked` when the count reaches three.

Decode the two exposed buses back to signed values, let
`gain_corr=signed_gain*trim_lsb`, `phase_corr=signed_phase*trim_lsb`, and drive

`i_out = clamp(vcm + (i_in-vcm) - 0.5*gain_corr, vss, vdd)`

`q_out = clamp(vcm + (q_in-vcm) + 0.5*gain_corr - phase_corr*(i_in-vcm)/vcm, vss, vdd)`.

Reset asynchronously clears both signed states, codes, metric, counter, and
lock, and drives both corrected outputs to `vcm`. Low `cal_en` holds all
calibration state while the corrector remains active.


## Modeling Constraints

- Use deterministic voltage-domain behavioral Verilog-A suitable for transient simulation.
- Use public voltage contributions only and preserve the declared artifact and module interfaces.
- Do not hard-code evaluator stimulus, sample windows, checker tolerances, gold internals, or simulator side channels.
- Preserve the exact file set, module graph, ports, parameters, and public traces.
- Do not add debug outputs, validation state, side channels, or stimulus-specific fixes.

## Output Contract

Return the repaired bundle with exactly these paths: `quad_corr_top.va`, `gain_trim.va`, `skew_estimator.va`, `corrector.va`.
Every supplied `.va` file is editable; do not add or omit files.
