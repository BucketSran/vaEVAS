# Fractional-N Divider Accumulator Flow Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Fractional-N Divider Accumulator Flow` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `fracn_pll_timer_ref.va`:
  - Module `fracn_pll_timer_ref` (entry)
    - position 0: `VDD` (inout, electrical)
    - position 1: `VSS` (inout, electrical)
    - position 2: `ref_clk` (input, electrical)
    - position 3: `fb_clk` (output, electrical)
    - position 4: `dco_clk` (output, electrical)
    - position 5: `vctrl_mon` (output, electrical)
    - position 6: `lock` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/fracn_pll_timer_ref.va`
- DUT instance: `XDUT (VDD VSS ref_clk fb_clk dco_clk vctrl_mon lock) fracn_pll_timer_ref acc_modulus=8 div_int=8 f_center=800e6 f_max=1.2e9 f_min=500e6 frac_word=3 ki=8.0e4 kp=2.5e6 kvco_hz_per_v=220e6 lock_count_target=3 lock_tol=3n tedge=1n vctrl_init=0.45`
- Required saved public traces: `VDD`, `VSS`, `ref_clk`, `fb_clk`, `dco_clk`, `vctrl_mon`, `lock`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `fracn_pll_timer_ref.div_int` defaults to `8 from [1:inf)`; valid range: finite; overrides div_int.
- `fracn_pll_timer_ref.frac_word` defaults to `3 from [0:inf)`; valid range: finite; overrides frac_word.
- `fracn_pll_timer_ref.acc_modulus` defaults to `8 from [1:inf)`; valid range: finite; overrides acc_modulus.
- `fracn_pll_timer_ref.f_center` defaults to `800.0e6 from (0:inf)`; valid range: finite; overrides f_center.
- `fracn_pll_timer_ref.kvco_hz_per_v` defaults to `350.0e6 from (0:inf)`; valid range: finite; overrides kvco_hz_per_v.
- `fracn_pll_timer_ref.f_min` defaults to `300.0e6 from (0:inf)`; valid range: finite; overrides f_min.
- `fracn_pll_timer_ref.f_max` defaults to `1.6e9 from (0:inf)`; valid range: finite; overrides f_max.
- `fracn_pll_timer_ref.kp` defaults to `8.0e6 from [0:inf)`; valid range: finite; overrides kp.
- `fracn_pll_timer_ref.ki` defaults to `1.2e5 from [0:inf)`; valid range: finite; overrides ki.
- `fracn_pll_timer_ref.integ_min` defaults to `-0.45`; valid range: finite; overrides integ_min.
- `fracn_pll_timer_ref.integ_max` defaults to `0.45`; valid range: finite; overrides integ_max.
- `fracn_pll_timer_ref.vctrl_init` defaults to `0.45`; valid range: finite; overrides vctrl_init.
- `fracn_pll_timer_ref.tedge` defaults to `20p from (0:inf)`; valid range: finite; overrides tedge.
- `fracn_pll_timer_ref.lock_tol` defaults to `0.4e-9 from (0:inf)`; valid range: finite; overrides lock_tol.
- `fracn_pll_timer_ref.lock_count_target` defaults to `6 from [1:inf)`; valid range: finite; overrides lock_count_target.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_USE_REF_CLK_AS_THE_REFERENCE`: exercise and make observable: Use `ref_clk` as the reference timing input. Required traces: `time`, `VDD`, `VSS`, `ref_clk`, `fb_clk`, `dco_clk`, `vctrl_mon`, `lock`.
- `P_GENERATE_A_BEHAVIORAL_DCO_CLOCK_ON`: exercise and make observable: Generate a behavioral DCO clock on `dco_clk`. Required traces: `time`, `VDD`, `VSS`, `ref_clk`, `fb_clk`, `dco_clk`, `vctrl_mon`, `lock`.
- `P_GENERATE_FB_CLK_BY_TOGGLING_IT`: exercise and make observable: Generate `fb_clk` by toggling it after a DCO rising-edge count selected by a Required traces: `time`, `VDD`, `VSS`, `ref_clk`, `fb_clk`, `dco_clk`, `vctrl_mon`, `lock`.
- `P_UPDATE_A_BOUNDED_CONTROL_VOLTAGE_MONITOR`: exercise and make observable: Update a bounded control-voltage monitor on `vctrl_mon` from the PFD phase Required traces: `time`, `VDD`, `VSS`, `ref_clk`, `fb_clk`, `dco_clk`, `vctrl_mon`, `lock`.
- `P_DRIVE_LOCK_HIGH_AFTER_STABLE_TRACKING`: exercise and make observable: Drive `lock` high after stable tracking, low or unstable during the Required traces: `time`, `VDD`, `VSS`, `ref_clk`, `fb_clk`, `dco_clk`, `vctrl_mon`, `lock`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

The verification harness supplies a reference-step clock source and
instantiates the supplied DUT in a fractional-N PLL tracking/reacquire scenario.

This is a behavioral continuous-time task. Do not use `I(...)`, `ddt(...)`, or
`idt(...)`. Use voltage contributions only.

Required observable behavior:

- Use `ref_clk` as the reference timing input.
- Generate a behavioral DCO clock on `dco_clk`.
- Generate `fb_clk` by toggling it after a DCO rising-edge count selected by a
  fractional accumulator: maintain an accumulator that increments by `frac_word`
  after each feedback-output toggle; on overflow (modulo `acc_modulus`) use
  `div_int - 1` for the next toggle count, otherwise use `div_int`. A complete
  rising-edge period of `fb_clk` spans two such output toggles.
- Update a bounded control-voltage monitor on `vctrl_mon` from the PFD phase
  error (proportional + bounded integral).
- Drive `lock` high after stable tracking, low or unstable during the
  reference-frequency disturbance, and high again after reacquisition.

Use voltage-coded logic with a mid-supply decision threshold where applicable,
drive high logic outputs near `VDD` and low outputs near `VSS`. Keep the model
pure behavioral Verilog-A. Do not use transistor-level devices, AC/noise
analysis, external validation code, or simulator-specific test hooks.

The supplied reference-step support clock uses public defaults
`period_pre = 20 ns`, `period_post = 19.5 ns`, `t_switch = 2 us`, and
`tedge = 100 ps`. The supplied DUT must work when the harness supplies a legal nearby
reference cadence.


The required trace names are: `time`, `VDD`, `VSS`, `ref_clk`, `fb_clk`, `dco_clk`, `vctrl_mon`, `lock`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Include the supplied read-only support files only from
  `./dut/support/...`; do not reference `./support/...` or undeclared paths.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
