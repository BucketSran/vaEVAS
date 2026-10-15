# Accum3 Pulse Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Accum3 Pulse` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `accum3_pulse.va`:
  - Module `accum3_pulse` (entry)
    - position 0: `clk` (input, electrical)
    - position 1: `out` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/accum3_pulse.va`
- DUT instance: `XDUT (clk out) accum3_pulse`
- Required saved public traces: `clk`, `out`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `accum3_pulse.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `accum3_pulse.vdd` defaults to `0.9`; valid range: finite; overrides vdd.
- `accum3_pulse.tdel` defaults to `10p`; valid range: finite; overrides tdel.
- `accum3_pulse.tr` defaults to `10p`; valid range: finite; overrides tr.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_INITIALIZE_THE_INTERNAL_3_BIT_COUNT`: exercise and make observable: Initialize the internal 3-bit count to 7. Required traces: `time`, `clk`, `out`.
- `P_INCREMENT_THE_COUNT_MODULO_8_ON`: exercise and make observable: Increment the count modulo 8 on each rising `clk` crossing. Required traces: `time`, `clk`, `out`.
- `P_DRIVE_OUT_HIGH_ONLY_WHEN_THE`: exercise and make observable: Drive `out` high only when the modulo count is 0. Required traces: `time`, `clk`, `out`.
- `P_DRIVE_OUT_LOW_FOR_ALL_OTHER`: exercise and make observable: Drive `out` low for all other count values. Required traces: `time`, `clk`, `out`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- Initialize the internal 3-bit count to 7.
- Increment the count modulo 8 on each rising `clk` crossing.
- Drive `out` high only when the modulo count is 0.
- Drive `out` low for all other count values.


The required trace names are: `time`, `clk`, `out`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
