# Digitally Controlled Delay Cell Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Digitally Controlled Delay Cell` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `digitally_controlled_delay_cell.va`:
  - Module `digitally_controlled_delay_cell` (entry)
    - position 0: `in_clk` (input, electrical)
    - position 1: `load` (input, electrical)
    - position 2: `rst` (input, electrical)
    - position 3: `code_5` (input, electrical)
    - position 4: `code_4` (input, electrical)
    - position 5: `code_3` (input, electrical)
    - position 6: `code_2` (input, electrical)
    - position 7: `code_1` (input, electrical)
    - position 8: `code_0` (input, electrical)
    - position 9: `out_clk` (output, electrical)
    - position 10: `delay_metric` (output, electrical)
    - position 11: `valid` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/digitally_controlled_delay_cell.va`
- DUT instance: `XDUT (in_clk load rst code_5 code_4 code_3 code_2 code_1 code_0 out_clk delay_metric valid) digitally_controlled_delay_cell`
- Required saved public traces: `in_clk`, `load`, `rst`, `code_5`, `code_4`, `code_3`, `code_2`, `code_1`, `code_0`, `out_clk`, `delay_metric`, `valid`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `digitally_controlled_delay_cell.vdd` defaults to `0.9`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vdd behavior for module digitally_controlled_delay_cell.
- `digitally_controlled_delay_cell.vss` defaults to `0.0`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vss behavior for module digitally_controlled_delay_cell.
- `digitally_controlled_delay_cell.vth` defaults to `0.45`; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public vth behavior for module digitally_controlled_delay_cell.
- `digitally_controlled_delay_cell.delay_min` defaults to `20e-12` s; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public delay_min behavior for module digitally_controlled_delay_cell.
- `digitally_controlled_delay_cell.delay_lsb` defaults to `3e-12` s; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public delay_lsb behavior for module digitally_controlled_delay_cell.
- `digitally_controlled_delay_cell.tr` defaults to `100p from (0:inf)` s; valid range: declared Verilog-A parameter constraint or finite portable value; overrides public tr behavior for module digitally_controlled_delay_cell.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RESET_CLEAR`: exercise and make observable: Reset clears the loaded code state, delayed clock, delay metric, valid indication, and pending edges. Required traces: `time`, `rst`, `load`, `out_clk`, `delay_metric`, `valid`.
- `P_CODE_CAPTURE_METRIC`: exercise and make observable: A rising load edge captures the six-bit unsigned code and the delay metric reports the normalized captured code. Required traces: `time`, `load`, `code_5`, `code_4`, `code_3`, `code_2`, `code_1`, `code_0`, `delay_metric`.
- `P_EDGE_DELAY_MAPPING`: exercise and make observable: Each input-clock edge appears at the output after delay_min plus delay_lsb times the code captured for that edge. Required traces: `time`, `in_clk`, `out_clk`, `load`, `code_5`, `code_4`, `code_3`, `code_2`, `code_1`, `code_0`.
- `P_PULSE_INTEGRITY_VALID`: exercise and make observable: Rising and falling edges receive equal delay, preserving pulse width, and valid asserts after the first delayed rising edge. Required traces: `time`, `rst`, `in_clk`, `out_clk`, `valid`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- On reset, clear the latched code, `out_clk`, `delay_metric`, and `valid`.
- On rising `load`, capture `code_5..code_0` as an unsigned delay code.
- Map the latched code to a delay equal to `delay_min + delay_lsb * code`.
- For each rising edge of `in_clk`, produce a corresponding rising edge on `out_clk` after the mapped delay.
- Delay both rising and falling input edges by the same selected delay, preserving the input pulse width. Latch the selected delay independently at each originating edge so a later code load does not retime an already pending output edge.
- `delay_metric` must expose the latched code normalized onto `vss..vdd`, using `vss + (vdd - vss) * code / 63`.
- `valid` must assert after the first output pulse generated from a loaded code.
- Reset cancels pending delayed edges, clears the loaded-code state, and drives `out_clk` low.


The required trace names are: `time`, `in_clk`, `load`, `rst`, `code_5`, `code_4`, `code_3`, `code_2`, `code_1`, `code_0`, `out_clk`, `delay_metric`, `valid`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
