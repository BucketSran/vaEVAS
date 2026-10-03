# Smooth Absolute Value Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Smooth Absolute Value` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `absolute_value.va`:
  - Module `absolute_value` (entry)
    - position 0: `sigin` (input, electrical)
    - position 1: `sigout` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/absolute_value.va`
- DUT instance: `XDUT (sigin sigout) absolute_value`
- Required saved public traces: `sigin`, `sigout`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `absolute_value.smooth` defaults to `0.05 from (0:inf)`; valid range: finite; overrides smooth.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_SMOOTH_ABSOLUTE_TRANSFER`: exercise and make observable: Drive `sigout` as the smooth absolute-value transfer `V(sigin) * tanh(V(sigin) / smooth)`: even in input, nonnegative, deterministic, memoryless, rounded near zero, and asymptotically equal to input magnitude for large positive and negative inputs. Required traces: `time`, `sigin`, `sigout`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Drive `sigout` as the smooth absolute-value transfer `V(sigin) * tanh(V(sigin) / smooth)`. The transfer should be even in the input, nonnegative, deterministic, memoryless, and rounded near zero instead of using a sharp ideal absolute-value cusp. For large positive and negative inputs, the output should approach the corresponding input magnitude.


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
