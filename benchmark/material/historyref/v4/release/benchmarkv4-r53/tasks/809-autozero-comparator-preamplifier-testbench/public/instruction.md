# Auto-zero Comparator Preamplifier Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Auto-zero Comparator Preamplifier` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `autozero_comparator_preamplifier_top.va`:
  - Module `autozero_comparator_preamplifier_top` (entry)
    - position 0: `vinp` (input, electrical)
    - position 1: `vinn` (input, electrical)
    - position 2: `clk` (input, electrical)
    - position 3: `rst` (input, electrical)
    - position 4: `az_en` (input, electrical)
    - position 5: `eval_en` (input, electrical)
    - position 6: `decision` (output, electrical)
    - position 7: `offset_store` (output, electrical)
    - position 8: `ready` (output, electrical)
- Artifact `offset_store_cell.va`:
  - Module `offset_store_cell` (required_submodule)
    - position 0: `vinp` (input, electrical)
    - position 1: `vinn` (input, electrical)
    - position 2: `clk` (input, electrical)
    - position 3: `rst` (input, electrical)
    - position 4: `az_en` (input, electrical)
    - position 5: `offset_store` (output, electrical)
    - position 6: `ready` (output, electrical)
- Artifact `clocked_comparator_core.va`:
  - Module `clocked_comparator_core` (required_submodule)
    - position 0: `vinp` (input, electrical)
    - position 1: `vinn` (input, electrical)
    - position 2: `clk` (input, electrical)
    - position 3: `rst` (input, electrical)
    - position 4: `eval_en` (input, electrical)
    - position 5: `ready` (input, electrical)
    - position 6: `offset_store` (input, electrical)
    - position 7: `decision` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include paths: `./dut/autozero_comparator_preamplifier_top.va`, `./dut/offset_store_cell.va`, `./dut/clocked_comparator_core.va`
- DUT instance: `XDUT (vinp vinn clk rst az_en eval_en decision offset_store ready) autozero_comparator_preamplifier_top`
- Required saved public traces: `vinp`, `vinn`, `clk`, `rst`, `az_en`, `eval_en`, `decision`, `offset_store`, `ready`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `autozero_comparator_preamplifier_top.vdd` defaults to `0.9`; valid range: finite; overrides vdd.
- `autozero_comparator_preamplifier_top.vss` defaults to `0.0`; valid range: finite; overrides vss.
- `autozero_comparator_preamplifier_top.vcm` defaults to `0.45`; valid range: finite; overrides vcm.
- `autozero_comparator_preamplifier_top.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `autozero_comparator_preamplifier_top.tr` defaults to `200p from (0:inf)`; valid range: finite; overrides tr.
- `offset_store_cell.vdd` defaults to `0.9`; valid range: finite; overrides vdd.
- `offset_store_cell.vss` defaults to `0.0`; valid range: finite; overrides vss.
- `offset_store_cell.vcm` defaults to `0.45`; valid range: finite; overrides vcm.
- `offset_store_cell.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `offset_store_cell.tr` defaults to `200p from (0:inf)`; valid range: finite; overrides tr.
- `clocked_comparator_core.vdd` defaults to `0.9`; valid range: finite; overrides vdd.
- `clocked_comparator_core.vss` defaults to `0.0`; valid range: finite; overrides vss.
- `clocked_comparator_core.vcm` defaults to `0.45`; valid range: finite; overrides vcm.
- `clocked_comparator_core.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `clocked_comparator_core.tr` defaults to `200p from (0:inf)`; valid range: finite; overrides tr.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_ON_RESET_CLEAR_STORED_OFFSET_DECISION`: exercise and make observable: On reset, clear stored offset, `decision`, and `ready`. Required traces: `time`, `vinp`, `vinn`, `clk`, `rst`, `az_en`, `eval_en`, `decision`, `offset_store`, `ready`.
- `P_DURING_AN_AUTO_ZERO_CLOCK_UPDATE`: exercise and make observable: During an auto-zero clock update with `az_en` high, store the apparent differential offset between `vinp` and `vinn`. Required traces: `time`, `vinp`, `vinn`, `clk`, `rst`, `az_en`, `eval_en`, `decision`, `offset_store`, `ready`.
- `P_DURING_AN_EVALUATION_CLOCK_UPDATE_WITH`: exercise and make observable: During an evaluation clock update with `eval_en` high, subtract the stored offset from the live differential input. Required traces: `time`, `vinp`, `vinn`, `clk`, `rst`, `az_en`, `eval_en`, `decision`, `offset_store`, `ready`.
- `P_DRIVE_DECISION_HIGH_FOR_CORRECTED_NONNEGATIVE`: exercise and make observable: Drive `decision` high for corrected nonnegative differential input and low otherwise. Required traces: `time`, `vinp`, `vinn`, `clk`, `rst`, `az_en`, `eval_en`, `decision`, `offset_store`, `ready`.
- `P_EXPOSE_STORED_OFFSET_ON_OFFSET_STORE`: exercise and make observable: Expose stored offset on `offset_store` and assert `ready` after at least one auto-zero update. Required traces: `time`, `vinp`, `vinn`, `clk`, `rst`, `az_en`, `eval_en`, `decision`, `offset_store`, `ready`.
- `P_USE_ONLY_VOLTAGE_DOMAIN_BEHAVIORAL_STATE`: exercise and make observable: Use only voltage-domain behavioral state and voltage contributions on public electrical outputs. Required traces: `time`, `vinp`, `vinn`, `clk`, `rst`, `az_en`, `eval_en`, `decision`, `offset_store`, `ready`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- On reset, clear stored offset, `decision`, and `ready`.
- During an auto-zero clock update with `az_en` high, store the apparent differential offset between `vinp` and `vinn`.
- During an evaluation clock update with `eval_en` high, subtract the stored offset from the live differential input.
- Drive `decision` high for corrected nonnegative differential input and low otherwise.
- Expose stored offset on `offset_store` and assert `ready` after at least one auto-zero update.
- Use only voltage-domain behavioral state and voltage contributions on public electrical outputs.
- Do not expose pass/fail flags; expose only the public observable metrics named in the interface.


The required trace names are: `time`, `vinp`, `vinn`, `clk`, `rst`, `az_en`, `eval_en`, `decision`, `offset_store`, `ready`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
