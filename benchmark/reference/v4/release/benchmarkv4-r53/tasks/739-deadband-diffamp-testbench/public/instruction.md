# Deadband Diffamp Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Deadband Diffamp` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `deadband_diffamp.va`:
  - Module `deadband_diffamp` (entry)
    - position 0: `sigin_p` (input, electrical)
    - position 1: `sigin_n` (input, electrical)
    - position 2: `sigout` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/deadband_diffamp.va`
- DUT instance: `XDUT (sigin_p sigin_n sigout) deadband_diffamp`
- Required saved public traces: `sigin_n`, `sigin_p`, `sigout`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `deadband_diffamp.sigin_dead_low` defaults to `-0.1`; valid range: finite; overrides sigin_dead_low.
- `deadband_diffamp.sigin_dead_high` defaults to `0.1`; valid range: finite; overrides sigin_dead_high.
- `deadband_diffamp.sigout_leak` defaults to `0.02`; valid range: finite; overrides sigout_leak.
- `deadband_diffamp.gain_low` defaults to `2.0`; valid range: finite; overrides gain_low.
- `deadband_diffamp.gain_high` defaults to `3.0`; valid range: finite; overrides gain_high.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_DIFFERENTIAL_POLARITY`: exercise and make observable: Compute the differential input as `V(sigin_p, sigin_n)` with the documented polarity. Required traces: `time`, `sigin_n`, `sigin_p`, `sigout`.
- `P_DEADBAND_LEAK_OUTPUT`: exercise and make observable: Inside the inclusive differential deadband, drive the public leakage level `sigout_leak`. Required traces: `time`, `sigin_n`, `sigin_p`, `sigout`.
- `P_ASYMMETRIC_RESIDUE_GAINS`: exercise and make observable: Below the lower threshold use `gain_low` for the low-side signed residue plus leakage; above the upper threshold use `gain_high` for the high-side signed residue plus leakage. Required traces: `time`, `sigin_n`, `sigin_p`, `sigout`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Compute the differential input from `sigin_p` to `sigin_n`. Inside the deadband, including both thresholds, drive `sigout_leak`. Below the lower threshold, drive the low-side signed residue using `gain_low` and add the leakage level. Above the upper threshold, drive the high-side signed residue using `gain_high` and add the leakage level.


The required trace names are: `time`, `sigin_n`, `sigin_p`, `sigout`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
