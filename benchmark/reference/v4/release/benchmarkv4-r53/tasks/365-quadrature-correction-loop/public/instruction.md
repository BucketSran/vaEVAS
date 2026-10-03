# Quadrature Correction Loop

## Task Contract

Implement a Verilog-A DUT source package for a multi-module mixed-signal behavioral system.

- Target artifacts: `quad_corr_top.va`, `gain_trim.va`, `skew_estimator.va`, `corrector.va`
- Public top module: `quad_corr_top`
- Required public modules: `quad_corr_top`, `gain_trim`, `skew_estimator`, `corrector`

The submitted package may include helper modules, but it must include the target artifacts and public modules listed above. The public top module is the only module instantiated by the evaluator; helper modules must be part of the DUT source package, not testbench code.

## Public Verilog-A Interface

Declare top module `quad_corr_top` with positional electrical ports `i_in, q_in, clk, rst, cal_en, i_out, q_out, gain_code_3, gain_code_2, gain_code_1, gain_code_0, phase_code_3, phase_code_2, phase_code_1, phase_code_0, error_metric, locked`. All top-level ports are electrical.

Each required public helper module must be declared with these positional electrical ports:

- `gain_trim(i_in, q_in, clk, rst, cal_en, gain_code_3, gain_code_2, gain_code_1, gain_code_0)`
- `skew_estimator(i_in, q_in, clk, rst, cal_en, phase_code_3, phase_code_2, phase_code_1, phase_code_0, error_metric, locked)`
- `corrector(i_in, q_in, rst, gain_code_3, gain_code_2, gain_code_1, gain_code_0, phase_code_3, phase_code_2, phase_code_1, phase_code_0, i_out, q_out)`

The top module must expose exactly the public top-level port order above and connect the required helper modules as part of the DUT package.

## Public Parameter Contract

Provide these overrideable public parameters on the top module and propagate compatible values to helper modules where needed:

- `vdd = 0.9 V`: logic high output level.
- `vss = 0.0 V`: logic low output level.
- `vcm = 0.45 V`: common-mode reference.
- `vth = 0.45 V`: threshold for clock, reset, and calibration enable.
- `trim_lsb = 10e-3 V`: correction step represented by one trim-code step.
- `error_tol = 15e-3 V`: lock tolerance for the public error metric.
- `tr = 200 ps`: output transition smoothing time.

## Required Behavior

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

Use deterministic voltage-domain behavioral Verilog-A suitable for transient simulation. Use voltage contributions for public electrical outputs. Do not instantiate transistor-level devices. Do not add testbench code, Spectre decks, checker code, generated result files, debug-only ports, or pass/fail flags.

This is a modular DUT task: keep the required helper-module boundaries meaningful rather than collapsing all behavior into a single monolithic top module. The evaluator may use static checks to confirm that the required public modules are present, and behavior checks to validate the top-level observable contract.

## Output Contract

Return exactly these complete source artifacts:

- `quad_corr_top.va`
- `gain_trim.va`
- `skew_estimator.va`
- `corrector.va`
