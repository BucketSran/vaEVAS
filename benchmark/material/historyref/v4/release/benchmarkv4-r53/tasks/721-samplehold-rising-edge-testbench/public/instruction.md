# Samplehold Rising Edge Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Samplehold Rising Edge` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `samplehold_rising_edge.va`:
  - Module `samplehold_rising_edge` (entry)
    - position 0: `control` (input, electrical)
    - position 1: `vin` (input, electrical)
    - position 2: `vout` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/samplehold_rising_edge.va`
- DUT instance: `XDUT (control vin vout) samplehold_rising_edge`
- Required saved public traces: `control`, `vin`, `vout`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `samplehold_rising_edge.thresh` defaults to `2.5`; valid range: finite; overrides thresh.
- `samplehold_rising_edge.tdel` defaults to `20p`; valid range: finite; overrides tdel.
- `samplehold_rising_edge.tr` defaults to `20p`; valid range: finite; overrides tr.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_SAMPLE_VIN_ON_EACH_RISING_CONTROL`: exercise and make observable: Sample `vin` on each rising `control` crossing of `thresh`. Required traces: `time`, `control`, `vin`, `vout`.
- `P_HOLD_THE_SAMPLED_VOLTAGE_ON_VOUT`: exercise and make observable: Hold the sampled voltage on `vout` until the next rising control crossing. Required traces: `time`, `control`, `vin`, `vout`.
- `P_DO_NOT_CONTINUOUSLY_TRACK_VIN_BETWEEN`: exercise and make observable: Do not continuously track `vin` between sample events. Required traces: `time`, `control`, `vin`, `vout`.
- `P_DRIVE_VOUT_WITH_SMOOTH_VOLTAGE_DOMAIN`: exercise and make observable: Drive `vout` with smooth voltage-domain output behavior. Required traces: `time`, `control`, `vin`, `vout`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- Sample `vin` on each rising `control` crossing of `thresh`.
- Hold the sampled voltage on `vout` until the next rising control crossing.
- Do not continuously track `vin` between sample events.
- Drive `vout` with smooth voltage-domain output behavior.


The required trace names are: `time`, `control`, `vin`, `vout`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
