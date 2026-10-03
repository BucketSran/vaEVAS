# Iterative ISAR DAC Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Iterative ISAR DAC` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `iterative_isar_dac.va`:
  - Module `iterative_isar_dac` (entry)
    - position 0: `dcmp` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `clk` (input, electrical)
    - position 3: `vdac` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/iterative_isar_dac.va`
- DUT instance: `XDUT (dcmp rst clk vdac) iterative_isar_dac`
- Required saved public traces: `dcmp`, `rst`, `clk`, `vdac`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `iterative_isar_dac.vth` defaults to `0.5`; valid range: finite; overrides vth.
- `iterative_isar_dac.tr` defaults to `100p`; valid range: finite; overrides tr.
- `iterative_isar_dac.range` defaults to `0.1`; valid range: finite; overrides range.
- `iterative_isar_dac.lsb` defaults to `10u`; valid range: finite; overrides lsb.
- `iterative_isar_dac.radix` defaults to `2`; valid range: finite; overrides radix.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RESET_INITIAL_SEARCH_STATE`: exercise and make observable: At initialization and reset, `vdac` returns to zero and the search step returns to `range`. Required traces: `time`, `rst`, `vdac`.
- `P_COMPARATOR_POLARITY_UPDATE`: exercise and make observable: On each rising `clk` crossing while active, `dcmp > vth` steps `vdac` in the specified comparator-driven direction and low decisions step the opposite way. Required traces: `time`, `clk`, `dcmp`, `vdac`.
- `P_RADIX_STEP_REDUCTION`: exercise and make observable: The search step is divided by the public radix after each active comparison until it reaches the LSB limit. Required traces: `time`, `clk`, `dcmp`, `rst`, `vdac`.
- `P_HELD_DAC_OUTPUT`: exercise and make observable: `vdac` holds the current iterative search value between reset and qualifying clock events. Required traces: `time`, `clk`, `rst`, `vdac`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

At initialization and reset, set `vdac` to zero and set the search step to `range`. On each rising `clk` crossing while the step remains above `lsb`, update `vdac` according to the comparator decision: if `dcmp > vth`, subtract the current step from `vdac`; if `dcmp <= vth`, add the current step to `vdac`. After each update, divide the step by `radix`. Hold the DAC value after the step reaches the LSB limit.


The required trace names are: `time`, `dcmp`, `rst`, `clk`, `vdac`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
