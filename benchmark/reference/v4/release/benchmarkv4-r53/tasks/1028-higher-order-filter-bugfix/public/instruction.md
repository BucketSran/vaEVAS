# Clocked Cascaded Two-Pole Filter Bugfix

## Task Contract

The supplied Verilog-A system violates its public circuit contract. Repair the
complete editable bundle.

## Public Verilog-A Interface

Preserve this exact artifact and module interface:

- Artifact `higher_order_filter.va`:
  - Module `higher_order_filter` (entry)
    - position 0: `clk` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `vin` (input, electrical)
    - position 3: `out` (output, electrical)
    - position 4: `metric` (output, electrical)

## Public Parameter Contract

- `higher_order_filter.tr` defaults to `1e-10` s; valid range: tr > 0; sets output transition smoothing.
- `higher_order_filter.gain` defaults to `1.8` V/V; valid range: gain > 0; sets input-deviation gain about 0.45 V common mode.
- `higher_order_filter.alpha` defaults to `0.18` unitless; valid range: 0 < alpha <= 1; sets each cascaded sampled low-pass update coefficient.


## Required Behavior

The repaired bundle must satisfy every public property:

- `P_COMMON_MODE_INITIAL_RESET`: restore: Both cascaded states and observable out return to 0.45 V during initialization and active-high reset. Required traces: `time`, `rst`, `out`, `metric`.
- `P_GAINED_BOUNDED_TARGET`: restore: Each eligible rising edge forms a rail-bounded target from gain times the input deviation around 0.45 V. Required traces: `time`, `clk`, `rst`, `vin`, `out`.
- `P_TWO_POLE_SAMPLED_SETTLING`: restore: Out follows the second of two cascaded alpha-weighted sampled low-pass states and therefore settles more slowly than a single direct update. Required traces: `time`, `clk`, `vin`, `out`, `metric`.
- `P_LAG_METRIC`: restore: Metric exposes the centered lag between the two cascaded states during settling and returns toward its baseline after convergence. Required traces: `time`, `clk`, `vin`, `out`, `metric`.
- `P_SIGNAL_RANGE`: restore: The driven output remains within the public 0 V through 0.9 V signal range. Required traces: `time`, `out`.


The following canonical public behavior is normative for this derived form:

- Initialize the two filter states, output state, and metric baseline near
  `0.45 V`.
- On each rising `clk` crossing, update the sampled filter state.
- Treat `rst` as active high when `V(rst) > 0.45`; while reset is active,
  return both filter states and `out` to the common-mode level.
- When reset is low, form a bounded target by amplifying `vin` around the
  `0.45 V` common-mode level, then drive two cascaded sampled low-pass states
  toward that bounded target.
- Drive `out` from the second filtered state, bounded to the signal rails.
- Drive `metric` as a voltage observable of the lag between the cascaded filter
  states, centered around the common-mode level, so the settling transient is
  visible without exposing validation-only sample windows.

The validation scenario is a public verification scenario for wiring and saved
observables. Do not hard-code its transient stop time, waveform breakpoints, or
sample windows into the DUT.


## Modeling Constraints

- Use two deterministic cascaded rising-edge sampled low-pass states.
- Use voltage contributions only.
- Do not use current contributions, ddt(), validation hooks, or simulator-specific side channels.
- Preserve the exact file set, module graph, ports, parameters, and public traces.
- Do not add debug outputs, validation state, side channels, or stimulus-specific fixes.

## Output Contract

Return the repaired bundle with exactly these paths: `higher_order_filter.va`.
Every supplied `.va` file is editable; do not add or omit files.
