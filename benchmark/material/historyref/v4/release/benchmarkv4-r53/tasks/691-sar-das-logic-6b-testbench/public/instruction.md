# SAR DAS Logic 6b Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `SAR DAS Logic 6b` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `sar_das_logic_6b.va`:
  - Module `sar_das_logic_6b` (entry)
    - position 0: `clk_sampling` (input, electrical)
    - position 1: `clk_sar` (input, electrical)
    - position 2: `vcomp` (input, electrical)
    - position 3: `d1` (output, electrical)
    - position 4: `d2` (output, electrical)
    - position 5: `d3` (output, electrical)
    - position 6: `d4` (output, electrical)
    - position 7: `d5` (output, electrical)
    - position 8: `d6` (output, electrical)
    - position 9: `db1` (output, electrical)
    - position 10: `db2` (output, electrical)
    - position 11: `db3` (output, electrical)
    - position 12: `db4` (output, electrical)
    - position 13: `db5` (output, electrical)
    - position 14: `db6` (output, electrical)
    - position 15: `co` (output, electrical)
    - position 16: `cob` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/sar_das_logic_6b.va`
- DUT instance: `XDUT (clk_sampling clk_sar vcomp d1 d2 d3 d4 d5 d6 db1 db2 db3 db4 db5 db6 co cob) sar_das_logic_6b`
- Required saved public traces: `clk_sampling`, `clk_sar`, `co`, `cob`, `d1`, `d2`, `d3`, `d4`, `d5`, `d6`, `db1`, `db2`, `db3`, `db4`, `db5`, `db6`, `vcomp`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `sar_das_logic_6b.tde` defaults to `50p`; valid range: finite; overrides tde.
- `sar_das_logic_6b.tdc` defaults to `50p`; valid range: finite; overrides tdc.
- `sar_das_logic_6b.vdd` defaults to `1.1`; valid range: finite; overrides vdd.
- `sar_das_logic_6b.vcm` defaults to `0.55`; valid range: finite; overrides vcm.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_SAMPLING_RESET_CONVERSION_STATE`: exercise and make observable: A rising `clk_sampling` transition clears controls and pulses, and a falling transition arms the SAR conversion sequence. Required traces: `time`, `clk_sampling`, `clk_sar`, `co`, `cob`, `d1`, `d2`, `d3`, `d4`, `d5`, `d6`, `db1`, `db2`, `db3`, `db4`, `db5`, `db6`, `vcomp`.
- `P_SAR_COMPARATOR_POLARITY`: exercise and make observable: Each rising `clk_sar` transition compares `vcomp` to `vcm` and drives `co/cob` with the declared polarity. Required traces: `time`, `clk_sampling`, `clk_sar`, `co`, `cob`, `d1`, `d2`, `d3`, `d4`, `d5`, `d6`, `db1`, `db2`, `db3`, `db4`, `db5`, `db6`, `vcomp`.
- `P_SIX_BIT_DECISION_SEQUENCE`: exercise and make observable: The SAR decisions update `d6..d1` in the declared order through the conversion. Required traces: `time`, `clk_sampling`, `clk_sar`, `co`, `cob`, `d1`, `d2`, `d3`, `d4`, `d5`, `d6`, `db1`, `db2`, `db3`, `db4`, `db5`, `db6`, `vcomp`.
- `P_CONTROL_OUTPUT_LEVELS`: exercise and make observable: Decision pulses and bit-control outputs use valid voltage-coded low/high levels. Required traces: `time`, `clk_sampling`, `clk_sar`, `co`, `cob`, `d1`, `d2`, `d3`, `d4`, `d5`, `d6`, `db1`, `db2`, `db3`, `db4`, `db5`, `db6`, `vcomp`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

On a rising `clk_sampling` transition through `vcm`, clear all bit controls and decision pulses and reset the decision index to the start of a conversion. On a falling `clk_sampling` transition through `vcm`, preset all `d1..d6` and `db1..db6` controls high while keeping `co/cob` low. The first subsequent `clk_sar` rising decision uses decision index 7, then the index decrements after each `clk_sar` rising decision.

On each rising `clk_sar` transition through `vcm`, compare `vcomp` against `vcm`. If `vcomp > vcm`, drive `co` high and `cob` low; if the decision index is 7, set or keep `d6` high, and for later indices 6, 5, 4, 3, and 2 clear `db5`, `db4`, `db3`, `db2`, and `db1` respectively. If `vcomp <= vcm`, drive `cob` high and `co` low; if the decision index is 7, set or keep `db6` high, and for later indices 6, 5, 4, 3, and 2 clear `d5`, `d4`, `d3`, `d2`, and `d1` respectively. Bit controls not listed for the current decision retain their previous states. On each falling `clk_sar` transition through `vcm`, clear `co/cob` back low.


The required trace names are: `time`, `clk_sampling`, `clk_sar`, `co`, `cob`, `d1`, `d2`, `d3`, `d4`, `d5`, `d6`, `db1`, `db2`, `db3`, `db4`, `db5`, `db6`, `vcomp`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
