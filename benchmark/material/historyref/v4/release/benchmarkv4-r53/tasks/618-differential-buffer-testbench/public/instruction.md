# Differential Buffer Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Differential Buffer` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `differential_buffer.va`:
  - Module `differential_buffer` (entry)
    - position 0: `VINP` (input, electrical)
    - position 1: `VINN` (input, electrical)
    - position 2: `VOUTP` (output, electrical)
    - position 3: `VOUTN` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/differential_buffer.va`
- DUT instance: `XDUT (vinp vinn voutp voutn) differential_buffer`
- Required saved public traces: `vinp`, `vinn`, `voutp`, `voutn`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- No public parameter is declared.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_POSITIVE_UNITY`: exercise and make observable: VOUTP continuously follows VINP with unity voltage gain and unchanged polarity. Required traces: `time`, `vinp`, `voutp`.
- `P_NEGATIVE_UNITY`: exercise and make observable: VOUTN continuously follows VINN with unity voltage gain and unchanged polarity. Required traces: `time`, `vinn`, `voutn`.
- `P_CHANNEL_INDEPENDENCE`: exercise and make observable: Each output depends on its corresponding input and is not cross-coupled to the opposite input. Required traces: `time`, `vinp`, `vinn`, `voutp`, `voutn`.
- `P_DIFFERENTIAL_PRESERVATION`: exercise and make observable: The differential output VOUTP minus VOUTN equals the differential input VINP minus VINN. Required traces: `time`, `vinp`, `vinn`, `voutp`, `voutn`.
- `P_COMMON_MODE_PRESERVATION`: exercise and make observable: The output pair preserves the input pair common-mode voltage without conversion or rail logic. Required traces: `time`, `vinp`, `vinn`, `voutp`, `voutn`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Drive `VOUTP` from `VINP` and `VOUTN` from `VINN` with unity gain and the same polarity on each side.


The required trace names are: `time`, `vinp`, `vinn`, `voutp`, `voutn`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
