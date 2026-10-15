# Differential Gain Driver Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Differential Gain Driver` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `differential_gain_driver.va`:
  - Module `differential_gain_driver` (entry)
    - position 0: `sigin_p` (input, electrical)
    - position 1: `sigin_n` (input, electrical)
    - position 2: `sigout_p` (output, electrical)
    - position 3: `sigout_n` (output, electrical)
    - position 4: `sigref` (input, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/differential_gain_driver.va`
- DUT instance: `XDUT (sigin_p sigin_n sigout_p sigout_n sigref) differential_gain_driver gain=2`
- Required saved public traces: `sigin_n`, `sigin_p`, `sigout_n`, `sigout_p`, `sigref`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `differential_gain_driver.gain` defaults to `1`; valid range: finite; overrides gain.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_DIFFERENTIAL_INPUT_GAIN`: exercise and make observable: Read `V(sigin_p, sigin_n)` and multiply it by the overridable `gain` parameter. Required traces: `time`, `sigin_p`, `sigin_n`, `sigout_p`, `sigout_n`, `sigref`.
- `P_BALANCED_HALF_SPLIT`: exercise and make observable: Drive `sigout_p` and `sigout_n` as equal and opposite half-swings around `sigref`. Required traces: `time`, `sigin_p`, `sigin_n`, `sigout_p`, `sigout_n`, `sigref`.
- `P_OUTPUT_POLARITY`: exercise and make observable: For a positive input differential, `sigout_p` rises relative to `sigref` and `sigout_n` falls relative to `sigref`. Required traces: `time`, `sigin_p`, `sigin_n`, `sigout_p`, `sigout_n`, `sigref`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Read `V(sigin_p, sigin_n)` and generate a differential output equal to that input differential voltage multiplied by `gain`. Split the output swing equally: `sigout_p` moves positive around `sigref`, and `sigout_n` moves negative around `sigref` for a positive input differential.


The required trace names are: `time`, `sigin_n`, `sigin_p`, `sigout_n`, `sigout_p`, `sigref`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
