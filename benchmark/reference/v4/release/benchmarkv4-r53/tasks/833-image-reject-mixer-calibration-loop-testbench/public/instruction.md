# Image-reject Mixer Calibration Loop Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Image-reject Mixer Calibration Loop` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `image_reject_mixer_cal_loop_top.va`:
  - Module `image_reject_mixer_cal_loop_top` (entry)
    - position 0: `rf_in` (inout, electrical)
    - position 1: `lo_i` (inout, electrical)
    - position 2: `lo_q` (inout, electrical)
    - position 3: `clk` (inout, electrical)
    - position 4: `rst` (inout, electrical)
    - position 5: `enable` (inout, electrical)
    - position 6: `i_out` (inout, electrical)
    - position 7: `q_out` (inout, electrical)
    - position 8: `image_metric` (inout, electrical)
    - position 9: `calibrated` (inout, electrical)
- Artifact `quadrature_mixer_proxy.va`:
  - Module `quadrature_mixer_proxy` (required_submodule)
    - position 0: `rf_in` (inout, electrical)
    - position 1: `lo_i` (inout, electrical)
    - position 2: `lo_q` (inout, electrical)
    - position 3: `rst` (inout, electrical)
    - position 4: `enable` (inout, electrical)
    - position 5: `gain_trim` (inout, electrical)
    - position 6: `phase_trim` (inout, electrical)
    - position 7: `i_out` (inout, electrical)
    - position 8: `q_out` (inout, electrical)
    - position 9: `raw_image_metric` (inout, electrical)
- Artifact `image_cal_controller.va`:
  - Module `image_cal_controller` (required_submodule)
    - position 0: `clk` (inout, electrical)
    - position 1: `rst` (inout, electrical)
    - position 2: `enable` (inout, electrical)
    - position 3: `raw_image_metric` (inout, electrical)
    - position 4: `gain_trim` (inout, electrical)
    - position 5: `phase_trim` (inout, electrical)
    - position 6: `image_metric` (inout, electrical)
    - position 7: `calibrated` (inout, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include paths: `./dut/image_reject_mixer_cal_loop_top.va`, `./dut/quadrature_mixer_proxy.va`, `./dut/image_cal_controller.va`
- DUT instance: `XDUT (rf_in lo_i lo_q clk rst enable i_out q_out image_metric calibrated) image_reject_mixer_cal_loop_top`
- Required saved public traces: `rf_in`, `lo_i`, `lo_q`, `clk`, `rst`, `enable`, `i_out`, `q_out`, `image_metric`, `calibrated`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `image_reject_mixer_cal_loop_top.vdd` defaults to `0.9`; valid range: finite; overrides vdd.
- `image_reject_mixer_cal_loop_top.vss` defaults to `0.0`; valid range: finite; overrides vss.
- `image_reject_mixer_cal_loop_top.vcm` defaults to `0.45`; valid range: finite; overrides vcm.
- `image_reject_mixer_cal_loop_top.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `image_reject_mixer_cal_loop_top.tr` defaults to `200p from (0:inf)`; valid range: finite; overrides tr.
- `image_reject_mixer_cal_loop_top.image_tol` defaults to `40e-3`; valid range: finite; overrides image_tol.
- `quadrature_mixer_proxy.vdd` defaults to `0.9`; valid range: finite; overrides vdd.
- `quadrature_mixer_proxy.vss` defaults to `0.0`; valid range: finite; overrides vss.
- `quadrature_mixer_proxy.vcm` defaults to `0.45`; valid range: finite; overrides vcm.
- `quadrature_mixer_proxy.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `quadrature_mixer_proxy.tr` defaults to `200p from (0:inf)`; valid range: finite; overrides tr.
- `image_cal_controller.vdd` defaults to `0.9`; valid range: finite; overrides vdd.
- `image_cal_controller.vss` defaults to `0.0`; valid range: finite; overrides vss.
- `image_cal_controller.vcm` defaults to `0.45`; valid range: finite; overrides vcm.
- `image_cal_controller.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `image_cal_controller.tr` defaults to `200p from (0:inf)`; valid range: finite; overrides tr.
- `image_cal_controller.image_tol` defaults to `40e-3`; valid range: finite; overrides image_tol.
- `image_cal_controller.step` defaults to `18e-3`; valid range: finite; overrides step.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_ON_RESET_OR_WHEN_DISABLED_CLEAR`: exercise and make observable: On reset or while disabled, reset both internal trims to `vcm`, drive `i_out` and `q_out` to `vcm`, and drive `image_metric` and `calibrated` to `vss`. Required traces: `time`, `rf_in`, `lo_i`, `lo_q`, `clk`, `rst`, `enable`, `i_out`, `q_out`, `image_metric`, `calibrated`.
- `P_ON_EACH_ENABLED_RISING_CLK_EDGE`: exercise and make observable: Continuously evaluate the voltage-domain mixer proxy while enabled, and latch its raw image metric on each enabled rising `clk` edge. Required traces: `time`, `rf_in`, `lo_i`, `lo_q`, `clk`, `rst`, `enable`, `i_out`, `q_out`, `image_metric`, `calibrated`.
- `P_GENERATE_I_AND_Q_OUTPUTS_USING`: exercise and make observable: With `x=rf_in-vcm`, LO signs `si` and `sq`, `g=0.8*(gain_trim-vcm)`, and `p=0.6*(phase_trim-vcm)`, compute `i=x*si*(1-g)` and `q=-x*sq*(1+g)-p*x*si`; drive rail-clamped `vcm+i`, `vcm+q`, and raw image metric `0.5*abs(i+q)`. Required traces: `time`, `rf_in`, `lo_i`, `lo_q`, `clk`, `rst`, `enable`, `i_out`, `q_out`, `image_metric`, `calibrated`.
- `P_UPDATE_A_SIMPLE_GAIN_PHASE_CORRECTION`: exercise and make observable: For an in-tolerance sample halve both trim deviations toward `vcm`; otherwise update gain trim by `d*18e-3`, phase trim by `-d*9e-3`, clamp both to `vcm+/-0.18`, and reverse `d`. Required traces: `time`, `rf_in`, `lo_i`, `lo_q`, `clk`, `rst`, `enable`, `i_out`, `q_out`, `image_metric`, `calibrated`.
- `P_ASSERT_CALIBRATED_AFTER_THREE_CONSECUTIVE_UPDA`: exercise and make observable: Drive `calibrated` to `vdd` after three consecutive enabled rising-edge samples with image metric below `image_tol`, otherwise drive `vss`; reset or disable clears the count and restores search direction `d=+1`. Required traces: `time`, `rf_in`, `lo_i`, `lo_q`, `clk`, `rst`, `enable`, `i_out`, `q_out`, `image_metric`, `calibrated`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- On reset or when disabled, clear outputs, image metric, and `calibrated`.
- On each enabled rising `clk` edge, sample RF and quadrature LO inputs as voltage-domain mixer proxies.
- Generate I and Q outputs using opposite LO polarities.
- Update a simple gain/phase correction state to reduce the image metric.
- Assert `calibrated` after three consecutive updates with image metric below `image_tol`.
- Use only voltage-domain behavioral state and voltage contributions on public electrical outputs.
- Do not expose pass/fail flags; expose only the public observable metrics named in the interface.

`i_out`, `q_out`, `image_metric`, and `calibrated` are DUT-driven outputs.  On
reset or while disabled, reset both internal trim states to `vcm`, drive
`i_out` and `q_out` to the neutral mixer level `vcm`, and drive `image_metric`
and `calibrated` to `vss`.

While enabled, let `x = rf_in-vcm`, let `si` be `+1` when `lo_i > vth` and
`-1` otherwise, and define `sq` the same way from `lo_q`.  Encode the internal
signed trim states as `g = 0.8*(gain_trim-vcm)` and
`p = 0.6*(phase_trim-vcm)`.  The continuously evaluated mixer proxy is:

1. `i = x*si*(1-g)`.
2. `q = -x*sq*(1+g) - p*x*si`.
3. `i_out = clamp(vcm+i, vss, vdd)` and
   `q_out = clamp(vcm+q, vss, vdd)`.
4. `raw_image_metric = clamp(0.5*abs(i+q), vss, vdd)`.

On each enabled rising `clk` edge, latch `image_metric = raw_image_metric`.
The controller starts with `gain_trim = phase_trim = vcm` and search direction
`d = +1`.  When the sampled metric is below `image_tol`, move both trim
deviations halfway back toward zero and increment the consecutive-good count:
`gain_trim = vcm + 0.5*(gain_trim-vcm)` and
`phase_trim = vcm + 0.5*(phase_trim-vcm)`.  Otherwise clear that count, update
`gain_trim = clamp(gain_trim+d*18e-3, vcm-0.18, vcm+0.18)` and
`phase_trim = clamp(phase_trim-d*9e-3, vcm-0.18, vcm+0.18)`, then reverse the
direction with `d = -d`.  Drive `calibrated` to `vdd` after three consecutive
below-threshold samples and to `vss` otherwise.  Reset or disable also clears
the count and restores `d = +1`.


The required trace names are: `time`, `rf_in`, `lo_i`, `lo_q`, `clk`, `rst`, `enable`, `i_out`, `q_out`, `image_metric`, `calibrated`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
