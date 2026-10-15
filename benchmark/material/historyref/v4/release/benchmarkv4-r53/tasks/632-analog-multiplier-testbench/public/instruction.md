# Analog Multiplier Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Analog Multiplier` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `analog_multiplier_gain.va`:
  - Module `analog_multiplier_gain` (entry)
    - position 0: `sigin1` (input, electrical)
    - position 1: `sigin2` (input, electrical)
    - position 2: `sigout` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/analog_multiplier_gain.va`
- DUT instance: `XDUT (sigin1 sigin2 sigout) analog_multiplier_gain gain=2`
- Required saved public traces: `sigin1`, `sigin2`, `sigout`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `analog_multiplier_gain.gain` defaults to `1`; valid range: finite; overrides gain.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_ANALOG_PRODUCT`: exercise and make observable: Drive `sigout` to `V(sigin1) * V(sigin2)` scaled by `gain`, preserving product sign. Required traces: `time`, `sigin1`, `sigin2`, `sigout`.
- `P_GAIN_PARAMETER_APPLIED`: exercise and make observable: Apply the overridable `gain` parameter multiplicatively to the input product. Required traces: `time`, `sigin1`, `sigin2`, `sigout`.
- `P_MULTIPLICATIVE_NOT_ADDITIVE`: exercise and make observable: The transfer must be multiplicative and must not replace the product with addition or a square of one input. Required traces: `time`, `sigin1`, `sigin2`, `sigout`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Drive `sigout` to the product `gain * V(sigin1) * V(sigin2)` for both positive and negative input products.


The required trace names are: `time`, `sigin1`, `sigin2`, `sigout`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
