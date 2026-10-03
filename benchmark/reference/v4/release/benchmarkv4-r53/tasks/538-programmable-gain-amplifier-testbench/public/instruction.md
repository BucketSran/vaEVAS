# Programmable Gain Amplifier Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Programmable Gain Amplifier` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `programmable_gain_amplifier.va`:
  - Module `programmable_gain_amplifier` (entry)
    - position 0: `clk` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `gain_sel` (input, electrical)
    - position 3: `vin` (input, electrical)
    - position 4: `out` (output, electrical)
    - position 5: `metric` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/programmable_gain_amplifier.va`
- DUT instance: `XDUT (clk rst gain_sel vin out metric) programmable_gain_amplifier`
- Required saved public traces: `clk`, `rst`, `gain_sel`, `vin`, `out`, `metric`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `programmable_gain_amplifier.vth` defaults to `0.45` V; valid range: vmin < vth < vmax; sets clk, rst, and gain_sel logic threshold.
- `programmable_gain_amplifier.vcm` defaults to `0.45` V; valid range: vmin <= vcm <= vmax; sets the input and output common-mode reference.
- `programmable_gain_amplifier.gain_low` defaults to `0.8`; valid range: gain_low > 0; sets the sampled low-gain transfer slope.
- `programmable_gain_amplifier.gain_high` defaults to `2.4`; valid range: gain_high > 0; sets the sampled high-gain transfer slope.
- `programmable_gain_amplifier.vmin` defaults to `0.0` V; valid range: vmin < vmax; sets the lower output clamp.
- `programmable_gain_amplifier.vmax` defaults to `0.9` V; valid range: vmax > vmin; sets the upper output clamp.
- `programmable_gain_amplifier.tr` defaults to `2e-10` s; valid range: tr > 0; sets out and metric transition smoothing.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RESET_UNITY`: exercise and make observable: While rst is active, the sampled gain is unity, out is vcm, and metric is low. Required traces: `time`, `clk`, `rst`, `out`, `metric`.
- `P_SAMPLED_GAIN_SELECT`: exercise and make observable: Each rising clk crossing with reset inactive samples gain_sel, selecting gain_high above vth and gain_low below vth; the selection holds between crossings. Required traces: `time`, `clk`, `rst`, `gain_sel`, `vin`, `out`.
- `P_COMMON_MODE_GAIN`: exercise and make observable: The unclamped output target is vcm plus the sampled gain times vin minus vcm. Required traces: `time`, `vin`, `out`.
- `P_OUTPUT_CLAMP`: exercise and make observable: Out is limited to the inclusive vmin through vmax range with finite smoothing. Required traces: `time`, `out`.
- `P_CLIP_METRIC`: exercise and make observable: Metric is high exactly when the unclamped target lies outside vmin through vmax, and low otherwise; reset forces it low. Required traces: `time`, `rst`, `vin`, `out`, `metric`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- Initialize the sampled gain to unity.
- On each rising `clk` crossing, sample `gain_sel` unless reset is active.
- While `rst` is above `vth`, use unity gain, drive `out` to `vcm`, and drive `metric` low.
- When not reset, select `gain_high` for high `gain_sel` and `gain_low` for low `gain_sel`.
- Drive `out` as `vcm + gain * (V(vin) - vcm)` after clipping to the `vmin` to `vmax` range.
- Drive `metric` high when the unclamped target would exceed either clamp limit, and low otherwise.


The required trace names are: `time`, `clk`, `rst`, `gain_sel`, `vin`, `out`, `metric`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
