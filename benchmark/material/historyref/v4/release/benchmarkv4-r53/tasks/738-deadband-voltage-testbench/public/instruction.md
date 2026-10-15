# Deadband Voltage Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Deadband Voltage` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `deadband_voltage.va`:
  - Module `deadband_voltage` (entry)
    - position 0: `sigin` (input, electrical)
    - position 1: `sigout` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/deadband_voltage.va`
- DUT instance: `XDUT (sigin sigout) deadband_voltage`
- Required saved public traces: `sigin`, `sigout`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `deadband_voltage.sigin_dead_low` defaults to `-0.25`; valid range: finite; overrides sigin_dead_low.
- `deadband_voltage.sigin_dead_high` defaults to `0.25`; valid range: finite; overrides sigin_dead_high.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_DEADBAND_ZERO_REGION`: exercise and make observable: Inside the inclusive deadband window from `sigin_dead_low` to `sigin_dead_high`, drive `sigout` to `0 V`. Required traces: `time`, `sigin`, `sigout`.
- `P_SIGNED_RESIDUE_OUTSIDE_WINDOW`: exercise and make observable: Below the lower edge, drive the signed excess below `sigin_dead_low`; above the upper edge, drive the signed excess above `sigin_dead_high` while preserving sign. Required traces: `time`, `sigin`, `sigout`.
- `P_DEADBAND_EDGE_CONTINUITY`: exercise and make observable: Use the public lower and upper threshold values so the output is continuous at both deadband edges. Required traces: `time`, `sigin`, `sigout`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Inside the deadband window, including both edges, drive `sigout` to `0 V`. Below the lower edge, drive the signed excess below `sigin_dead_low`. Above the upper edge, drive the signed excess above `sigin_dead_high`. The output should preserve sign outside the window and be continuous at both thresholds.


The required trace names are: `time`, `sigin`, `sigout`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
