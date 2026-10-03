# LC VCO Behavioral Source Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `LC VCO Behavioral Source` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `lc_vco_behavioral_source.va`:
  - Module `lc_vco_behavioral_source` (entry)
    - position 0: `vctrl` (input, electrical)
    - position 1: `enable` (input, electrical)
    - position 2: `rst` (input, electrical)
    - position 3: `osc_p` (output, electrical)
    - position 4: `osc_n` (output, electrical)
    - position 5: `freq_metric` (output, electrical)
    - position 6: `amp_metric` (output, electrical)
    - position 7: `valid` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/lc_vco_behavioral_source.va`
- DUT instance: `XDUT (vctrl enable rst osc_p osc_n freq_metric amp_metric valid) lc_vco_behavioral_source`
- Required saved public traces: `vctrl`, `enable`, `rst`, `osc_p`, `osc_n`, `freq_metric`, `amp_metric`, `valid`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `lc_vco_behavioral_source.vdd` defaults to `0.9` V; valid range: vdd > vss; sets the logic-high output level.
- `lc_vco_behavioral_source.vss` defaults to `0.0` V; valid range: vss < vdd; sets the logic-low output level.
- `lc_vco_behavioral_source.vcm` defaults to `0.45` V; valid range: vss < vcm < vdd; sets output common mode.
- `lc_vco_behavioral_source.fmin` defaults to `5000000.0` Hz; valid range: fmin > 0; sets minimum frequency.
- `lc_vco_behavioral_source.fmax` defaults to `25000000.0` Hz; valid range: fmax > fmin; sets maximum frequency.
- `lc_vco_behavioral_source.vth` defaults to `0.45` V; valid range: vss < vth < vdd; sets the digital-voltage crossing threshold.
- `lc_vco_behavioral_source.amplitude` defaults to `0.4` V; valid range: 0 < amplitude <= min(vcm-vss,vdd-vcm); sets differential half-amplitude.
- `lc_vco_behavioral_source.tr` defaults to `2e-10` s; valid range: tr > 0; sets transition smoothing.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RESET_DISABLE_CENTER`: exercise and make observable: Reset or disable centers both oscillator outputs at vcm and clears metrics and valid. Required traces: `time`, `vctrl`, `enable`, `rst`, `osc_p`, `osc_n`, `freq_metric`, `amp_metric`, `valid`.
- `P_CONTROL_FREQUENCY_MAP`: exercise and make observable: Enabled edge periods follow the linear clamped vctrl mapping from fmin to fmax. Required traces: `time`, `vctrl`, `enable`, `rst`, `osc_p`, `osc_n`, `freq_metric`, `amp_metric`, `valid`.
- `P_NO_RETIME_PENDING_TRANSITION`: exercise and make observable: A control-voltage change affects the next half-period and does not retime a transition that was already pending. Required traces: `time`, `vctrl`, `enable`, `rst`, `osc_p`, `osc_n`, `freq_metric`, `amp_metric`, `valid`.
- `P_COMPLEMENTARY_AMPLITUDE`: exercise and make observable: Enabled oscillator outputs are complementary around vcm with the declared amplitude. Required traces: `time`, `vctrl`, `enable`, `rst`, `osc_p`, `osc_n`, `freq_metric`, `amp_metric`, `valid`.
- `P_METRIC_REPORTING`: exercise and make observable: freq_metric reports clamped vctrl and amp_metric reports amplitude while enabled. Required traces: `time`, `vctrl`, `enable`, `rst`, `osc_p`, `osc_n`, `freq_metric`, `amp_metric`, `valid`.
- `P_VALID_AFTER_TWO_CYCLES`: exercise and make observable: valid remains low until two complete oscillator cycles have elapsed after enable. Required traces: `time`, `vctrl`, `enable`, `rst`, `osc_p`, `osc_n`, `freq_metric`, `amp_metric`, `valid`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- On reset or when disabled, drive both oscillator outputs to `vcm`, clear metrics, and clear `valid`.
- When enabled, clamp `vctrl` to `vss..vdd` and map it linearly to `fmin..fmax`.
- Generate complementary square-wave oscillator outputs at `vcm + amplitude` and `vcm - amplitude`.
- Drive `freq_metric` to the clamped control voltage and `amp_metric` to `amplitude` while enabled.
- Assert `valid` after two completed oscillator cycles following enable.
- This is a behavioral oscillator source and must not require an LC tank or branch-current model. On enable, restart both outputs at `vcm`; the first complementary state begins one half-period later. A control-voltage change affects the next half-period and must not retime a transition already pending.


The required trace names are: `time`, `vctrl`, `enable`, `rst`, `osc_p`, `osc_n`, `freq_metric`, `amp_metric`, `valid`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
