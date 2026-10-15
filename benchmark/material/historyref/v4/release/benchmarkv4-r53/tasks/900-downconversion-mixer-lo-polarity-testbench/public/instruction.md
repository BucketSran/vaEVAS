# Downconversion Mixer with LO Polarity Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Downconversion Mixer with LO Polarity` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `downconversion_mixer_lo_polarity.va`:
  - Module `downconversion_mixer_lo_polarity` (entry)
    - position 0: `rf_in` (input, electrical)
    - position 1: `lo_i` (input, electrical)
    - position 2: `lo_q` (input, electrical)
    - position 3: `rst` (input, electrical)
    - position 4: `enable` (input, electrical)
    - position 5: `i_out` (output, electrical)
    - position 6: `q_out` (output, electrical)
    - position 7: `lo_i_metric` (output, electrical)
    - position 8: `lo_q_metric` (output, electrical)
    - position 9: `polarity_ok` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/downconversion_mixer_lo_polarity.va`
- DUT instance: `XDUT (rf_in lo_i lo_q rst enable i_out q_out lo_i_metric lo_q_metric polarity_ok) downconversion_mixer_lo_polarity conversion_gain=0.5`
- Required saved public traces: `rf_in`, `lo_i`, `lo_q`, `rst`, `enable`, `i_out`, `q_out`, `lo_i_metric`, `lo_q_metric`, `polarity_ok`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `downconversion_mixer_lo_polarity.vdd` defaults to `0.9` V; valid range: vdd > vss; sets the logic-high output level.
- `downconversion_mixer_lo_polarity.vss` defaults to `0.0` V; valid range: vss < vdd; sets the logic-low output level.
- `downconversion_mixer_lo_polarity.vcm` defaults to `0.45` V; valid range: vss < vcm < vdd; sets RF and output common mode.
- `downconversion_mixer_lo_polarity.vth` defaults to `0.45` V; valid range: vss < vth < vdd; sets the digital-voltage crossing threshold.
- `downconversion_mixer_lo_polarity.conversion_gain` defaults to `0.5` 1; valid range: conversion_gain >= 0; sets baseband conversion gain.
- `downconversion_mixer_lo_polarity.tr` defaults to `2e-10` s; valid range: tr > 0; sets discrete polarity/status smoothing.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RESET_DISABLE_CENTER`: exercise and make observable: Reset or disable centers I/Q outputs and clears LO metrics and polarity_ok. Required traces: `time`, `rf_in`, `lo_i`, `lo_q`, `rst`, `enable`, `i_out`, `q_out`, `lo_i_metric`, `lo_q_metric`, `polarity_ok`.
- `P_LO_POLARITY_METRICS`: exercise and make observable: Each LO threshold state selects signed polarity and is mirrored by its public metric. Required traces: `time`, `rf_in`, `lo_i`, `lo_q`, `rst`, `enable`, `i_out`, `q_out`, `lo_i_metric`, `lo_q_metric`, `polarity_ok`.
- `P_IQ_CONVERSION`: exercise and make observable: I and Q outputs follow the declared common-mode referenced conversion-gain equations with independent LO signs. Required traces: `time`, `rf_in`, `lo_i`, `lo_q`, `rst`, `enable`, `i_out`, `q_out`, `lo_i_metric`, `lo_q_metric`, `polarity_ok`.
- `P_OUTPUT_CLAMP`: exercise and make observable: Both baseband outputs remain within the declared supply rails. Required traces: `time`, `rf_in`, `lo_i`, `lo_q`, `rst`, `enable`, `i_out`, `q_out`, `lo_i_metric`, `lo_q_metric`, `polarity_ok`.
- `P_POLARITY_QUALIFICATION`: exercise and make observable: polarity_ok asserts only after both LO controls have toggled while enabled. Required traces: `time`, `rf_in`, `lo_i`, `lo_q`, `rst`, `enable`, `i_out`, `q_out`, `lo_i_metric`, `lo_q_metric`, `polarity_ok`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- On reset or when `enable` is low, drive `i_out` and `q_out` to `vcm`, clear LO metrics, and clear `polarity_ok`.
- Interpret `lo_i` and `lo_q` as voltage-coded quadrature LO polarity controls.
- Map each LO control to signed multiplier `s`: high means `s = +1` and low
  means `s = -1`.
- Drive `i_out = vcm + conversion_gain * (V(rf_in) - vcm) * s_i` and
  `q_out = vcm + conversion_gain * (V(rf_in) - vcm) * s_q` before clamping.
- Clamp `i_out` and `q_out` to `[vss, vdd]`.
- `lo_i_metric` and `lo_q_metric` must be `vdd` for positive polarity and
  `vss` for negative polarity.
- Assert `polarity_ok` only after both LO controls have been observed toggling while enabled.


The required trace names are: `time`, `rf_in`, `lo_i`, `lo_q`, `rst`, `enable`, `i_out`, `q_out`, `lo_i_metric`, `lo_q_metric`, `polarity_ok`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
