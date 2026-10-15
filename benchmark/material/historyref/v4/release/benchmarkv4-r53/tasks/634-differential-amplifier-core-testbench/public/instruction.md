# Differential Amplifier Core Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Differential Amplifier Core` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `differential_amplifier_core.va`:
  - Module `differential_amplifier_core` (entry)
    - position 0: `sigin_p` (input, electrical)
    - position 1: `sigin_n` (input, electrical)
    - position 2: `sigout` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/differential_amplifier_core.va`
- DUT instance: `XDUT (sigin_p sigin_n sigout) differential_amplifier_core`
- Required saved public traces: `sigin_n`, `sigin_p`, `sigout`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- No public parameter is declared.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_DIFFERENTIAL_INPUT`: exercise and make observable: Use `V(sigin_p, sigin_n)` as the input signal. Required traces: `time`, `sigin_p`, `sigin_n`, `sigout`.
- `P_INPUT_OFFSET`: exercise and make observable: Subtract the fixed 0.05 V input-referred offset before applying gain. Required traces: `time`, `sigin_p`, `sigin_n`, `sigout`.
- `P_GAIN_TWO_OUTPUT`: exercise and make observable: Drive `sigout` to `2.0 * (V(sigin_p, sigin_n) - 0.05)`. Required traces: `time`, `sigin_p`, `sigin_n`, `sigout`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Use `V(sigin_p, sigin_n)` as the input. Subtract a 0.05 V input-referred offset, apply a fixed voltage gain of 2.0, and drive the resulting single-ended output voltage on `sigout`.


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
