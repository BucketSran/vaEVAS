# Differential Deadband Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Differential Deadband` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `differential_deadband.va`:
  - Module `differential_deadband` (entry)
    - position 0: `sigin_p` (input, electrical)
    - position 1: `sigin_n` (input, electrical)
    - position 2: `sigout` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/differential_deadband.va`
- DUT instance: `XDUT (sigin_p sigin_n sigout) differential_deadband dead_high=0.2 dead_low=-0.2 gain=1 leak=0.05`
- Required saved public traces: `sigin_n`, `sigin_p`, `sigout`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `differential_deadband.dead_high` defaults to `0.1`; valid range: finite; overrides dead_high.
- `differential_deadband.dead_low` defaults to `-0.1`; valid range: finite; overrides dead_low.
- `differential_deadband.gain` defaults to `1`; valid range: finite; overrides gain.
- `differential_deadband.leak` defaults to `0`; valid range: finite; overrides leak.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_DIFFERENTIAL_INPUT`: exercise and make observable: Use `V(sigin_p, sigin_n)` as the signed input error; do not collapse the transfer to one input terminal. Required traces: `time`, `sigin_p`, `sigin_n`, `sigout`.
- `P_LEAK_INSIDE_DEADBAND`: exercise and make observable: For `dead_low <= V(sigin_p, sigin_n) <= dead_high`, drive `sigout` to the parameter `leak`. Required traces: `time`, `sigin_p`, `sigin_n`, `sigout`.
- `P_GAINED_RESIDUE_OUTSIDE_DEADBAND`: exercise and make observable: Below `dead_low`, drive `gain * (diff - dead_low) + leak`; above `dead_high`, drive `gain * (diff - dead_high) + leak`. Required traces: `time`, `sigin_p`, `sigin_n`, `sigout`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- `P_DIFFERENTIAL_INPUT`: Use `V(sigin_p, sigin_n)` as the signed input error; do not collapse the transfer to one input terminal.

- `P_LEAK_INSIDE_DEADBAND`: For `dead_low <= V(sigin_p, sigin_n) <= dead_high`, drive `sigout` to the parameter `leak`.

- `P_GAINED_RESIDUE_OUTSIDE_DEADBAND`: Below `dead_low`, drive `gain * (diff - dead_low) + leak`; above `dead_high`, drive `gain * (diff - dead_high) + leak`.


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
