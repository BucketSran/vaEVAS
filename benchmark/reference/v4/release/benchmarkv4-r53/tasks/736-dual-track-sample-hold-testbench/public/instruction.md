# Dual Track Sample Hold Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Dual Track Sample Hold` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `dual_track_sample_hold.va`:
  - Module `dual_track_sample_hold` (entry)
    - position 0: `vdd` (inout, electrical)
    - position 1: `vss` (inout, electrical)
    - position 2: `clk` (input, electrical)
    - position 3: `vin` (input, electrical)
    - position 4: `vout` (output, electrical)
    - position 5: `phase` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/dual_track_sample_hold.va`
- DUT instance: `XDUT (vdd vss clk vin vout phase) dual_track_sample_hold`
- Required saved public traces: `clk`, `phase`, `vin`, `vout`, `vdd`, `vss`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `dual_track_sample_hold.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `dual_track_sample_hold.tick` defaults to `0.5n from (0:inf)`; valid range: finite; overrides tick.
- `dual_track_sample_hold.alpha_in` defaults to `0.45 from (0:1]`; valid range: finite; overrides alpha_in.
- `dual_track_sample_hold.alpha_out` defaults to `0.55 from (0:1]`; valid range: finite; overrides alpha_out.
- `dual_track_sample_hold.tedge` defaults to `50p from (0:inf)`; valid range: finite; overrides tedge.
- `dual_track_sample_hold.vinit` defaults to `0.0`; valid range: finite; overrides vinit.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_COMPLEMENTARY_TRACK_HOLD_SEQUENCE`: exercise and make observable: During low clock phase the input stage tracks `vin` while output holds; after the rising edge, the output stage tracks the retained input-stage value during high clock phase; after the falling edge, output holds until the next high phase. Required traces: `time`, `clk`, `phase`, `vin`, `vout`, `vdd`, `vss`.
- `P_FINITE_TRACKING_AND_HOLD`: exercise and make observable: Use finite acquisition updates and preserve held values between tracking windows rather than making the output continuously transparent or a single ideal edge sample. Required traces: `time`, `clk`, `phase`, `vin`, `vout`, `vdd`, `vss`.
- `P_PHASE_MONITOR_POLARITY`: exercise and make observable: Drive `phase` high only during output-stage tracking and low otherwise. Required traces: `time`, `clk`, `phase`, `vin`, `vout`, `vdd`, `vss`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

During low clock phase, the input stage tracks `vin` with finite acquisition while the output stage holds. On the rising clock transition, the input stage retains its acquired value. During high clock phase, the output stage tracks that retained input-stage value with finite bandwidth. On falling clock transition, the output stage holds until the next high phase. Clamp internal stored voltages to the local rail span and drive `phase` high only during output-stage tracking.


The required trace names are: `time`, `clk`, `phase`, `vin`, `vout`, `vdd`, `vss`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
