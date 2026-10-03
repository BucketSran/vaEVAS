# Clocked Comparator Dual Output Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Clocked Comparator Dual Output` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `clocked_comparator_dual_output.va`:
  - Module `clocked_comparator_dual_output` (entry)
    - position 0: `clk` (input, electrical)
    - position 1: `vinn` (input, electrical)
    - position 2: `vinp` (input, electrical)
    - position 3: `outn` (output, electrical)
    - position 4: `outp` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/clocked_comparator_dual_output.va`
- DUT instance: `XDUT (clk vinn vinp outn outp) clocked_comparator_dual_output`
- Required saved public traces: `clk`, `outn`, `outp`, `vinn`, `vinp`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `clocked_comparator_dual_output.vdd` defaults to `1.0`; valid range: finite; overrides vdd.
- `clocked_comparator_dual_output.td_cmp` defaults to `100p`; valid range: finite; overrides td_cmp.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_INITIALIZE_BOTH_DECISION_OUTPUTS_LOW`: exercise and make observable: Initialize both decision outputs low. Required traces: `time`, `clk`, `outn`, `outp`, `vinn`, `vinp`.
- `P_WHENEVER_CLK_FALLS_THROUGH_VDD_2`: exercise and make observable: Whenever `clk` falls through `vdd/2`, reset both outputs low. Required traces: `time`, `clk`, `outn`, `outp`, `vinn`, `vinp`.
- `P_WHENEVER_CLK_RISES_THROUGH_VDD_2`: exercise and make observable: Whenever `clk` rises through `vdd/2`, latch a differential decision. Required traces: `time`, `clk`, `outn`, `outp`, `vinn`, `vinp`.
- `P_DRIVE_OUTP_HIGH_AND_OUTN_LOW`: exercise and make observable: Drive `outp` high and `outn` low for `vinp > vinn`. Required traces: `time`, `clk`, `outn`, `outp`, `vinn`, `vinp`.
- `P_DRIVE_OUTN_HIGH_AND_OUTP_LOW`: exercise and make observable: Drive `outn` high and `outp` low for `vinp < vinn`. Required traces: `time`, `clk`, `outn`, `outp`, `vinn`, `vinp`.
- `P_DRIVE_BOTH_OUTPUTS_LOW_FOR_AN`: exercise and make observable: Drive both outputs low for an equal-input decision. Required traces: `time`, `clk`, `outn`, `outp`, `vinn`, `vinp`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- Initialize both decision outputs low.
- Whenever `clk` falls through `vdd/2`, reset both outputs low.
- Whenever `clk` rises through `vdd/2`, latch a differential decision.
- Drive `outp` high and `outn` low for `vinp > vinn`.
- Drive `outn` high and `outp` low for `vinp < vinn`.
- Drive both outputs low for an equal-input decision.
- Hold the latched or reset state until the next clock event.


The required trace names are: `time`, `clk`, `outn`, `outp`, `vinn`, `vinp`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
