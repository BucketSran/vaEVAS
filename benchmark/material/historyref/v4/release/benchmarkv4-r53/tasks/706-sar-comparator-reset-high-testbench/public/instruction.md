# SAR Comparator Reset High Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `SAR Comparator Reset High` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `sar_comparator_reset_high.va`:
  - Module `sar_comparator_reset_high` (entry)
    - position 0: `cmpck` (input, electrical)
    - position 1: `vinn` (input, electrical)
    - position 2: `vinp` (input, electrical)
    - position 3: `dcmpn` (output, electrical)
    - position 4: `dcmpp` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/sar_comparator_reset_high.va`
- DUT instance: `XDUT (cmpck vinn vinp dcmpn dcmpp) sar_comparator_reset_high`
- Required saved public traces: `cmpck`, `dcmpn`, `dcmpp`, `vinn`, `vinp`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `sar_comparator_reset_high.vdd` defaults to `0.9`; valid range: finite; overrides vdd.
- `sar_comparator_reset_high.td_cmp` defaults to `20p`; valid range: finite; overrides td_cmp.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_INITIALIZE_BOTH_DECISION_OUTPUTS_HIGH_WHENEVER`: exercise and make observable: Initialize both decision outputs high. Whenever `cmpck` falls through `vdd/2`, reset both outputs high. Whenever `cmpck` rises through `vdd/2`, latch a differential decision: `dcmpp` high for `vinp > vinn`, `dcmpn` high for `vinp < vinn`, and both outputs low for equal inputs. Hold the latched or reset state until the next clock event. Required traces: `time`, `cmpck`, `dcmpn`, `dcmpp`, `vinn`, `vinp`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Initialize both decision outputs high. Whenever `cmpck` falls through `vdd/2`, reset both outputs high. Whenever `cmpck` rises through `vdd/2`, latch a differential decision: `dcmpp` high for `vinp > vinn`, `dcmpn` high for `vinp < vinn`, and both outputs low for equal inputs. Hold the latched or reset state until the next clock event.


The required trace names are: `time`, `cmpck`, `dcmpn`, `dcmpp`, `vinn`, `vinp`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
