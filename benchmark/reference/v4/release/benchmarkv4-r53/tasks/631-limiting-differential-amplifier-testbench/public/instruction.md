# Limiting Differential Amplifier Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Limiting Differential Amplifier` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `limiting_differential_amplifier.va`:
  - Module `limiting_differential_amplifier` (entry)
    - position 0: `sigin_p` (input, electrical)
    - position 1: `sigin_n` (input, electrical)
    - position 2: `sigout` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/limiting_differential_amplifier.va`
- DUT instance: `XDUT (sigin_p sigin_n sigout) limiting_differential_amplifier gain=3 sigin_offset=0.05 sigout_high=0.8 sigout_low=-0.4`
- Required saved public traces: `sigin_n`, `sigin_p`, `sigout`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `limiting_differential_amplifier.gain` defaults to `1`; valid range: finite; overrides gain.
- `limiting_differential_amplifier.sigout_high` defaults to `10`; valid range: finite; overrides sigout_high.
- `limiting_differential_amplifier.sigout_low` defaults to `-10`; valid range: finite; overrides sigout_low.
- `limiting_differential_amplifier.sigin_offset` defaults to `0`; valid range: finite; overrides sigin_offset.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_OFFSET_CORRECTED_DIFFERENTIAL_GAIN`: exercise and make observable: Compute `gain * (V(sigin_p, sigin_n) - sigin_offset)`. Required traces: `time`, `sigin_p`, `sigin_n`, `sigout`.
- `P_OUTPUT_MIDPOINT_REFERENCE`: exercise and make observable: Center the amplified value at `(sigout_high + sigout_low) / 2`. Required traces: `time`, `sigin_p`, `sigin_n`, `sigout`.
- `P_OUTPUT_RAIL_CLAMP`: exercise and make observable: Clamp the final target to the inclusive interval `[sigout_low, sigout_high]`. Required traces: `time`, `sigin_p`, `sigin_n`, `sigout`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Read `V(sigin_p, sigin_n)`, subtract the input-referred offset, multiply by `gain`, and center the result at the midpoint of `sigout_high` and `sigout_low`. Clamp the final output target to the inclusive output rail interval.


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
