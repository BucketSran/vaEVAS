# CPPLL Tracking Reacquire Timer Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `CPPLL Tracking Reacquire Timer` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `cppll_timer_ref.va`:
  - Module `cppll_timer_ref` (entry)
    - position 0: `VDD` (inout, electrical)
    - position 1: `VSS` (inout, electrical)
    - position 2: `ref_clk` (input, electrical)
    - position 3: `fb_clk` (output, electrical)
    - position 4: `dco_clk` (output, electrical)
    - position 5: `vctrl_mon` (output, electrical)
    - position 6: `lock` (output, electrical)
- Artifact `ref_step_clk.va`:
  - Module `ref_step_clk` (entry)
    - position 0: `VDD` (inout, electrical)
    - position 1: `VSS` (inout, electrical)
    - position 2: `CLK` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include paths: `./dut/cppll_timer_ref.va`, `./dut/ref_step_clk.va`
- DUT instance: `XREF (vdd vss ref_clk) ref_step_clk period_post=19.8n period_pre=20.4n t_switch=2u tedge=100p`
- DUT instance: `XDUT (vdd vss ref_clk fb_clk dco_clk vctrl_mon lock) cppll_timer_ref div_ratio=8 f_center=784.313725e6 f_max=1.2e9 f_min=500e6 ki=8.0e4 kp=2.5e6 kvco_hz_per_v=220e6 lock_count_target=4 lock_tol=1.2n tedge=1n vctrl_init=0.45`
- Required saved public traces: `vdd`, `vss`, `ref_clk`, `fb_clk`, `dco_clk`, `vctrl_mon`, `lock`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `cppll_timer_ref.div_ratio` defaults to `8` ratio; valid range: div_ratio >= 1; sets DCO rising-edge division ratio for fb_clk.
- `cppll_timer_ref.f_center` defaults to `800000000.0` Hz; valid range: f_center > 0; sets DCO frequency at common-mode control.
- `cppll_timer_ref.kvco_hz_per_v` defaults to `350000000.0` Hz/V; valid range: kvco_hz_per_v > 0; sets DCO frequency sensitivity to vctrl_mon.
- `cppll_timer_ref.f_min` defaults to `300000000.0` Hz; valid range: f_min > 0 and f_min <= f_max; sets lower DCO frequency clamp.
- `cppll_timer_ref.f_max` defaults to `1600000000.0` Hz; valid range: f_max > 0 and f_max >= f_min; sets upper DCO frequency clamp.
- `cppll_timer_ref.kp` defaults to `8000000.0` loop scale; valid range: kp >= 0; sets proportional phase-error correction scale.
- `cppll_timer_ref.ki` defaults to `120000.0` loop scale; valid range: ki >= 0; sets accumulated phase-error correction scale.
- `cppll_timer_ref.integ_min` defaults to `-0.45` V-equivalent; valid range: integ_min < integ_max; sets lower integral-state bound.
- `cppll_timer_ref.integ_max` defaults to `0.45` V-equivalent; valid range: integ_max > integ_min; sets upper integral-state bound.
- `cppll_timer_ref.vctrl_init` defaults to `0.45` V; valid range: finite real within the intended supply range; sets initial control-voltage monitor.
- `cppll_timer_ref.tedge` defaults to `2e-11` s; valid range: tedge > 0; sets voltage-coded output transition smoothing.
- `cppll_timer_ref.lock_tol` defaults to `4e-10` s; valid range: lock_tol > 0; sets phase-error tolerance for lock streaks.
- `cppll_timer_ref.lock_count_target` defaults to `6` events; valid range: lock_count_target >= 1; sets consecutive in-tolerance events required for lock.
- `ref_step_clk.period_pre` defaults to `2e-08` s; valid range: period_pre > 0; sets reference-clock period before t_switch.
- `ref_step_clk.period_post` defaults to `1.95e-08` s; valid range: period_post > 0; sets reference-clock period after t_switch.
- `ref_step_clk.t_switch` defaults to `2e-06` s; valid range: t_switch >= 0; sets time of the reference-cadence step.
- `ref_step_clk.tedge` defaults to `1e-10` s; valid range: tedge > 0; sets reference-clock transition smoothing.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_REFERENCE_PERIOD_STEP`: exercise and make observable: The bundled reference-step clock produces the configured period_pre cadence before t_switch and period_post cadence afterwards, with rail-referenced levels. Required traces: `time`, `vdd`, `vss`, `ref_clk`.
- `P_DCO_FREQUENCY_CONTROL`: exercise and make observable: Dco_clk frequency responds to bounded vctrl_mon around f_center with kvco_hz_per_v sensitivity and remains clamped to f_min through f_max. Required traces: `time`, `dco_clk`, `vctrl_mon`.
- `P_FEEDBACK_DIVISION`: exercise and make observable: Fb_clk is derived from dco_clk rising-edge activity using div_ratio. Required traces: `time`, `dco_clk`, `fb_clk`.
- `P_BOUNDED_TRACKING_CONTROL`: exercise and make observable: Reference-versus-feedback phase error updates proportional and bounded integral correction while vctrl_mon remains within the supply rails. Required traces: `time`, `vdd`, `vss`, `ref_clk`, `fb_clk`, `vctrl_mon`.
- `P_INITIAL_LOCK_ACQUISITION`: exercise and make observable: Stable pre-step tracking asserts lock only after lock_count_target consecutive in-tolerance events. Required traces: `time`, `ref_clk`, `fb_clk`, `lock`.
- `P_DISTURBANCE_UNLOCK`: exercise and make observable: The reference-period step removes or destabilizes lock qualification while the loop responds to the changed cadence. Required traces: `time`, `ref_clk`, `fb_clk`, `vctrl_mon`, `lock`.
- `P_LATE_REACQUISITION`: exercise and make observable: After the step, fb_clk tracks the new reference cadence and lock reasserts while vctrl_mon remains rail-bounded. Required traces: `time`, `vdd`, `vss`, `ref_clk`, `fb_clk`, `vctrl_mon`, `lock`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Required observable behavior:

- Use `ref_clk` as the reference timing input.
- Generate a behavioral DCO clock on `dco_clk`.
- Generate `fb_clk` by dividing the DCO activity according to `div_ratio`.
- Update a bounded control-voltage monitor on `vctrl_mon`.
- Drive `lock` high after stable tracking, low or unstable during the
  reference-frequency disturbance, and high again after reacquisition.
- The late-window relation should show `fb_clk` tracking the new `ref_clk`
  cadence while `vctrl_mon` remains within the supply rails.

Use voltage-coded logic with a mid-supply decision threshold where applicable,
drive high logic outputs near `VDD` and low outputs near `VSS`, and keep the
model pure behavioral Verilog-A. Do not use transistor-level devices, AC/noise
analysis, validation logic, validation-only hooks, or simulator-specific side channels.

`cppll_timer_ref.va` is the primary loop implementation and `ref_step_clk.va`
is the bundled reference-step source used by the flow. Both files are required
source artifacts.


The required trace names are: `time`, `vdd`, `vss`, `ref_clk`, `fb_clk`, `dco_clk`, `vctrl_mon`, `lock`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
