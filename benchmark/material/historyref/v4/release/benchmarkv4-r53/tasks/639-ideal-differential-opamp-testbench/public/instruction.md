# Ideal Differential Opamp Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Ideal Differential Opamp` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `ideal_differential_opamp.va`:
  - Module `ideal_differential_opamp` (entry)
    - position 0: `vinp` (input, electrical)
    - position 1: `vinn` (input, electrical)
    - position 2: `voutp` (output, electrical)
    - position 3: `voutn` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/ideal_differential_opamp.va`
- DUT instance: `XDUT (vinp vinn voutp voutn) ideal_differential_opamp`
- Required saved public traces: `vinn`, `vinp`, `voutn`, `voutp`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- No public parameter is declared.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_FIXED_COMMON_MODE`: exercise and make observable: Maintain both outputs symmetric around a fixed 0.5 V common mode. Required traces: `time`, `voutp`, `voutn`.
- `P_DIFFERENTIAL_GAIN_FOUR`: exercise and make observable: Make the differential output `V(voutp) - V(voutn)` equal to four times `V(vinp, vinn)`. Required traces: `time`, `vinp`, `vinn`, `voutp`, `voutn`.
- `P_OUTPUT_POLARITY`: exercise and make observable: For positive `V(vinp, vinn)`, drive `voutp` above common mode and `voutn` below common mode. Required traces: `time`, `vinp`, `vinn`, `voutp`, `voutn`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Maintain a fixed output common mode of 0.5 V. The differential output must be four times the input differential voltage, with `voutp` increasing and `voutn` decreasing when `V(vinp, vinn)` is positive.


The required trace names are: `time`, `vinn`, `vinp`, `voutn`, `voutp`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
