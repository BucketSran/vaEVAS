# Clocked Cascaded Two-Pole Filter Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Clocked Cascaded Two-Pole Filter` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `higher_order_filter.va`:
  - Module `higher_order_filter` (entry)
    - position 0: `clk` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `vin` (input, electrical)
    - position 3: `out` (output, electrical)
    - position 4: `metric` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/higher_order_filter.va`
- DUT instance: `XFB_DUT (clk rst vin out metric) higher_order_filter`
- Required saved public traces: `clk`, `rst`, `vin`, `out`, `metric`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `higher_order_filter.tr` defaults to `1e-10` s; valid range: tr > 0; sets output transition smoothing.
- `higher_order_filter.gain` defaults to `1.8` V/V; valid range: gain > 0; sets input-deviation gain about 0.45 V common mode.
- `higher_order_filter.alpha` defaults to `0.18` unitless; valid range: 0 < alpha <= 1; sets each cascaded sampled low-pass update coefficient.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_COMMON_MODE_INITIAL_RESET`: exercise and make observable: Both cascaded states and observable out return to 0.45 V during initialization and active-high reset. Required traces: `time`, `rst`, `out`, `metric`.
- `P_GAINED_BOUNDED_TARGET`: exercise and make observable: Each eligible rising edge forms a rail-bounded target from gain times the input deviation around 0.45 V. Required traces: `time`, `clk`, `rst`, `vin`, `out`.
- `P_TWO_POLE_SAMPLED_SETTLING`: exercise and make observable: Out follows the second of two cascaded alpha-weighted sampled low-pass states and therefore settles more slowly than a single direct update. Required traces: `time`, `clk`, `vin`, `out`, `metric`.
- `P_LAG_METRIC`: exercise and make observable: Metric exposes the centered lag between the two cascaded states during settling and returns toward its baseline after convergence. Required traces: `time`, `clk`, `vin`, `out`, `metric`.
- `P_SIGNAL_RANGE`: exercise and make observable: The driven output remains within the public 0 V through 0.9 V signal range. Required traces: `time`, `out`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


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

The visible testbench is a public verification scenario for wiring and saved
observables. Do not hard-code its transient stop time, waveform breakpoints, or
sample windows into the DUT.


The required trace names are: `time`, `clk`, `rst`, `vin`, `out`, `metric`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
