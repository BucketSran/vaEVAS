# Residue Amplifier Gain-calibration Loop

## Task Contract

Implement a Verilog-A DUT source package for a multi-module mixed-signal behavioral system.

- Target artifacts: `residue_amp_gain_calibration_top.va`, `residue_amp_core.va`, `gain_cal_controller.va`
- Public top module: `residue_amp_gain_calibration_top`
- Required public modules: `residue_amp_gain_calibration_top`, `residue_amp_core`, `gain_cal_controller`

The submitted package may include helper modules, but it must include the target artifacts and public modules listed above. The public top module is the top-level DUT entry point; helper modules must be part of the returned DUT source package, not verification harness code.

## Public Verilog-A Interface

Declare top module `residue_amp_gain_calibration_top` with positional electrical ports `vin, residue_ref, clk, rst, cal_en, gain_2, gain_1, gain_0, vout, error_metric, locked`. All top-level ports are electrical.

Each required public helper module must be declared in one of the returned source artifacts. The helper modules may use implementation-local ports chosen by the solver, but the top module must expose exactly the public top-level port order above.

## Public Parameter Contract

Provide these overrideable public parameters on the top module and propagate compatible values to helper modules where needed:

- `vdd = 0.9 V`: logic high and upper output rail.
- `vss = 0.0 V`: logic low and lower output rail.
- `vcm = 0.45 V`: signal common-mode reference.
- `vth = 0.45 V`: threshold for voltage-coded control inputs.
- `tr = 200 ps`: output transition smoothing time.
- `base_gain = 2.0`: residue gain at code zero.
- `gain_lsb = 0.25`: gain step.
- `lock_tol = 15e-3 V`: lock threshold.

## Required Behavior

- On reset, clear gain code, output, error metric, and `locked`.
- While `cal_en` is high, compare the current residue output against `residue_ref` on each rising `clk` edge.
- Increment or decrement the gain code by one step to reduce the signed error.
- Drive `vout` as a clamped residue-amplified version of `vin - vcm` using the active gain code.
- Assert `locked` after three consecutive updates with error magnitude below `lock_tol`.
- Use only voltage-domain behavioral state and voltage contributions on public electrical outputs.
- Do not expose pass/fail flags; expose only the public observable metrics named in the interface.

`gain_2`, `gain_1`, and `gain_0` are DUT-driven observable outputs that encode
an unsigned gain code from 0 through 7; they are not coefficient inputs.  On
reset or while `cal_en` is low, clear the code and lock streak, drive the three
gain outputs, `error_metric`, and `locked` to `vss`, and drive `vout` to the
neutral residue level `vcm`.  Holding `vout` at `vcm` is the defined cleared
output state for this common-mode-centered residue signal.

While enabled, decode the active code as
`gain = base_gain + gain_lsb*code` and drive
`vout = clamp(vcm + gain*(vin-vcm), vss, vdd)`.  At each rising `clk` edge,
sample `signed_error = residue_ref-vout`.  When `signed_error > lock_tol`,
increment the code by one, saturating at 7.  When
`signed_error < -lock_tol`, decrement the code by one, saturating at 0.  When
`abs(signed_error) <= lock_tol`, leave the code unchanged.  Expose the error
magnitude as `error_metric = abs(residue_ref-vout)`.

Count consecutive enabled rising-edge samples whose error magnitude is at or
below `lock_tol`.  Drive `locked` to `vdd` after the third such sample and to
`vss` otherwise.  An out-of-tolerance sample, reset, or disabled interval
clears the consecutive-sample count.  Apply the public `tr` smoothing time to
observable output transitions without changing these settled values.

## Modeling Constraints

Use deterministic voltage-domain behavioral Verilog-A suitable for transient simulation. Use voltage contributions for public electrical outputs. Do not instantiate transistor-level devices. Do not add verification harnesses, simulation decks, generated result files, logs, reports, debug-only ports, or pass/fail flags.

This is a modular DUT task: keep the required helper-module boundaries meaningful rather than collapsing all behavior into a single monolithic top module. Keep required public modules present and meaningful, and keep top-level behavior sufficient to validate the public contract under varied stimulus conditions.

## Output Contract

Return exactly these complete source artifacts:

- `residue_amp_gain_calibration_top.va`
- `residue_amp_core.va`
- `gain_cal_controller.va`
