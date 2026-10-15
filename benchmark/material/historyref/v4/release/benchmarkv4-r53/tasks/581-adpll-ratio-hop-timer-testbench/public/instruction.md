# ADPLL Ratio Hop Timer Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `ADPLL Ratio Hop Timer` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `adpll_ratio_hop_ref.va`:
  - Module `adpll_ratio_hop_ref` (entry)
    - position 0: `VDD` (inout, electrical)
    - position 1: `VSS` (inout, electrical)
    - position 2: `ref_clk` (input, electrical)
    - position 3: `ratio_ctrl` (input, electrical)
    - position 4: `fb_clk` (output, electrical)
    - position 5: `vout` (output, electrical)
    - position 6: `vctrl_mon` (output, electrical)
    - position 7: `lock` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/adpll_ratio_hop_ref.va`
- DUT instance: `IDUT (vdd vss ref_clk ratio_ctrl fb_clk vout vctrl_mon lock) adpll_ratio_hop_ref code_center=32 code_init=20 code_max=44 code_min=20 f_center=240e6 f_max=360e6 f_min=180e6 freq_step_hz=5e6 lock_count_target=8 lock_tol=2n ratio_max=12 ratio_min=3 tedge=200p`
- Required saved public traces: `vdd`, `vss`, `ref_clk`, `ratio_ctrl`, `fb_clk`, `vout`, `vctrl_mon`, `lock`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `adpll_ratio_hop_ref.f_center` defaults to `240000000.0` Hz; valid range: f_center > 0; sets the DCO center frequency near code_center.
- `adpll_ratio_hop_ref.freq_step_hz` defaults to `5000000.0` Hz/code; valid range: freq_step_hz > 0; sets DCO frequency change per control-code step.
- `adpll_ratio_hop_ref.f_min` defaults to `120000000.0` Hz; valid range: f_min > 0 and f_min <= f_max; sets the lower generated-frequency clamp.
- `adpll_ratio_hop_ref.f_max` defaults to `420000000.0` Hz; valid range: f_max > 0 and f_max >= f_min; sets the upper generated-frequency clamp.
- `adpll_ratio_hop_ref.code_min` defaults to `0` code; valid range: code_min >= 0 and code_min <= code_max; sets the minimum loop-control code.
- `adpll_ratio_hop_ref.code_max` defaults to `63` code; valid range: code_max >= 1 and code_max >= code_min; sets the maximum loop-control code.
- `adpll_ratio_hop_ref.code_center` defaults to `32` code; valid range: code_min <= code_center <= code_max; sets the control code corresponding to f_center.
- `adpll_ratio_hop_ref.code_init` defaults to `24` code; valid range: code_min <= code_init <= code_max; sets the initial bounded loop-control code.
- `adpll_ratio_hop_ref.ratio_min` defaults to `2` ratio; valid range: ratio_min >= 1 and ratio_min <= ratio_max; sets the minimum accepted feedback divide ratio.
- `adpll_ratio_hop_ref.ratio_max` defaults to `16` ratio; valid range: ratio_max >= 2 and ratio_max >= ratio_min; sets the maximum accepted feedback divide ratio.
- `adpll_ratio_hop_ref.tedge` defaults to `2e-10` s; valid range: tedge > 0; sets voltage-coded output transition smoothing.
- `adpll_ratio_hop_ref.lock_tol` defaults to `2e-09` s; valid range: lock_tol > 0; sets the timing-error tolerance for lock qualification.
- `adpll_ratio_hop_ref.lock_count_target` defaults to `5` events; valid range: lock_count_target >= 1; sets the required consecutive in-tolerance feedback-event count.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RATIO_REQUEST_CLAMP`: exercise and make observable: The voltage-coded ratio request rounds V(ratio_ctrl) to the nearest integer with half-step boundaries and then clips the feedback divide ratio to the inclusive ratio_min through ratio_max range, including legal non-default override ranges. Required traces: `time`, `ratio_ctrl`, `vout`, `fb_clk`.
- `P_RATIO_HALF_STEP_ROUNDING`: exercise and make observable: Requests immediately below a positive half-step round down while an exact positive half-step rounds up before divider selection. Required traces: `time`, `ratio_ctrl`, `vout`, `fb_clk`.
- `P_RATIO_OVERRIDE_SATURATION`: exercise and make observable: Requests below ratio_min or above ratio_max saturate to the respective inclusive endpoint when legal non-default bounds are configured. Required traces: `time`, `ratio_ctrl`, `vout`, `fb_clk`.
- `P_DCO_FREQUENCY_BOUNDS`: exercise and make observable: The behavioral DCO on vout remains within the configured f_min and f_max limits. Required traces: `time`, `vout`.
- `P_FEEDBACK_DERIVED_FROM_DCO`: exercise and make observable: Feedback-clock activity is derived by dividing vout activity by the requested ratio rather than from an independent clock source. Required traces: `time`, `ratio_ctrl`, `vout`, `fb_clk`.
- `P_BOUNDED_CONTROL_MONITOR`: exercise and make observable: Reference-versus-feedback timing error adjusts a bounded control state represented by rail-referenced vctrl_mon. Required traces: `time`, `vdd`, `vss`, `ref_clk`, `fb_clk`, `vctrl_mon`.
- `P_PRE_HOP_LOCK`: exercise and make observable: Stable pre-hop tracking produces lock only after lock_count_target consecutive feedback events satisfy lock_tol. Required traces: `time`, `ref_clk`, `fb_clk`, `lock`.
- `P_RATIO_HOP_REACQUISITION`: exercise and make observable: A changed ratio request causes loss of lock qualification followed by renewed lock after the loop tracks the new feedback cadence. Required traces: `time`, `ratio_ctrl`, `ref_clk`, `fb_clk`, `vctrl_mon`, `lock`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

The supplied DUT models an ADPLL timing loop that locks to a reference,
responds to a commanded divider-ratio hop, and reacquires lock after the hop.

Required observable behavior:

- Use `ref_clk` as the reference timing input.
- Interpret `ratio_ctrl` as a voltage-coded requested feedback divide ratio in
  volts: round `V(ratio_ctrl)` to the nearest integer with half-step boundaries,
  with an exact positive half-step rounding upward to the next integer, then
  clip the requested ratio to the inclusive `ratio_min` through `ratio_max`
  range. Legal overrides of `ratio_min` and `ratio_max` must define the active
  saturation endpoints rather than limiting the encoding to the default
  2-through-16 range.
- Generate a behavioral DCO clock on `vout`.
- Generate `fb_clk` by dividing the DCO activity according to the requested
  ratio.
- Adjust a bounded internal control code from reference/feedback timing error
  rather than driving `fb_clk` from an independent source.
- Drive `vctrl_mon` as a rail-referenced monitor of the bounded loop-control
  state.
- Assert `lock` after stable pre-hop tracking, deassert or lose qualification
  during a ratio hop, and assert again after reacquisition.
- Keep generated frequencies within `f_min` and `f_max`; use appropriate
  timestep guidance such as `$bound_step` for oscillator timing.

Use voltage-coded logic with a mid-supply decision threshold where applicable,
drive high logic outputs near `VDD` and low outputs near `VSS`, and keep the
model pure behavioral Verilog-A. Do not use transistor-level devices, AC/noise
analysis, validation logic, validation-only hooks, or simulator-specific side
channels.


The required trace names are: `time`, `vdd`, `vss`, `ref_clk`, `ratio_ctrl`, `fb_clk`, `vout`, `vctrl_mon`, `lock`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
