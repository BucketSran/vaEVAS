# Clocked Sample And Hold Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Clocked Sample And Hold` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `sample_hold.va`:
  - Module `sample_hold` (entry)
    - position 0: `VDD` (input, electrical)
    - position 1: `VSS` (input, electrical)
    - position 2: `IN` (input, electrical)
    - position 3: `CLK` (input, electrical)
    - position 4: `OUT` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/sample_hold.va`
- DUT instance: `XDUT (vdd vss in clk out) sample_hold`
- Required saved public traces: `vdd`, `vss`, `in`, `clk`, `out`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `sample_hold.vth` defaults to `0.45` V; valid range: finite real; sets the rising CLK sampling threshold.
- `sample_hold.tedge` defaults to `1e-10` s; valid range: tedge > 0; sets OUT transition smoothing.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RISING_EDGE_SAMPLE`: exercise and make observable: OUT acquires the IN voltage present at each rising CLK crossing through vth, subject only to transition smoothing. Required traces: `time`, `in`, `clk`, `out`.
- `P_INTERSAMPLE_HOLD`: exercise and make observable: OUT retains the most recently sampled value between rising CLK crossings. Required traces: `time`, `in`, `clk`, `out`.
- `P_NO_HIGH_PHASE_TRACKING`: exercise and make observable: Changes on IN while CLK remains high do not make OUT transparent before the next rising crossing. Required traces: `time`, `in`, `clk`, `out`.
- `P_LOCAL_RAIL_REFERENCE`: exercise and make observable: The held analog voltage is driven as a smooth voltage-domain output referenced to the local VDD and VSS rails. Required traces: `time`, `vdd`, `vss`, `in`, `out`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- Sample `IN` on each rising `CLK` crossing of `vth`.
- Hold the sampled voltage on `OUT` between rising clock crossings.
- Do not continuously track `IN` while the clock is between sample events.
- Drive `OUT` with smooth voltage-domain behavior referenced to the local rails.


The required trace names are: `time`, `vdd`, `vss`, `in`, `clk`, `out`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
