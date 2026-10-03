# Linear PFD Gain Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Linear PFD Gain` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `linear_pfd_gain.va`:
  - Module `linear_pfd_gain` (entry)
    - position 0: `in1` (input, electrical)
    - position 1: `in2` (input, electrical)
    - position 2: `out` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/linear_pfd_gain.va`
- DUT instance: `XDUT (in1 in2 out) linear_pfd_gain`
- Required saved public traces: `in1`, `in2`, `out`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `linear_pfd_gain.kphi` defaults to `2.03`; valid range: finite; overrides kphi.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_DIFFERENTIAL_INPUT_POLARITY`: exercise and make observable: `out` uses the input difference `in1 - in2`, preserving the specified differential polarity. Required traces: `time`, `in1`, `in2`, `out`.
- `P_KPHI_GAIN_SCALE`: exercise and make observable: `out` is scaled by the public gain coefficient `kphi` rather than unit gain or an alternate scale. Required traces: `time`, `in1`, `in2`, `out`.
- `P_CONTINUOUS_ANALOG_TRACKING`: exercise and make observable: `out` continuously tracks analog input changes without clocked state, clipping, or single-ended substitution. Required traces: `time`, `in1`, `in2`, `out`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Drive `out` continuously as the gain coefficient times the input difference `in1 - in2`. The output should track analog input changes without clocked state or clipping.


The required trace names are: `time`, `in1`, `in2`, `out`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
