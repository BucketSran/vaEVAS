# Deserializer DEMUX Alignment Macro Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Deserializer DEMUX Alignment Macro` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `deserializer_demux_alignment_macro.va`:
  - Module `deserializer_demux_alignment_macro` (entry)
    - position 0: `clk` (inout, electrical)
    - position 1: `rst` (inout, electrical)
    - position 2: `enable` (inout, electrical)
    - position 3: `serial_in` (inout, electrical)
    - position 4: `align_pulse` (inout, electrical)
    - position 5: `out0` (inout, electrical)
    - position 6: `out1` (inout, electrical)
    - position 7: `out2` (inout, electrical)
    - position 8: `out3` (inout, electrical)
    - position 9: `phase_metric` (inout, electrical)
    - position 10: `word_valid` (inout, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/deserializer_demux_alignment_macro.va`
- DUT instance: `XDUT (clk rst enable serial_in align_pulse out0 out1 out2 out3 phase_metric word_valid) deserializer_demux_alignment_macro`
- Required saved public traces: `clk`, `rst`, `enable`, `serial_in`, `align_pulse`, `out0`, `out1`, `out2`, `out3`, `phase_metric`, `word_valid`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `deserializer_demux_alignment_macro.vdd` defaults to `0.9`; valid range: finite; overrides vdd.
- `deserializer_demux_alignment_macro.vss` defaults to `0.0`; valid range: finite; overrides vss.
- `deserializer_demux_alignment_macro.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `deserializer_demux_alignment_macro.tr` defaults to `200p from (0:inf)`; valid range: finite; overrides tr.
- `deserializer_demux_alignment_macro.tick` defaults to `250p from (0:inf)`; valid range: finite; overrides tick.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_ON_RESET_OR_WHEN_DISABLED_CLEAR`: exercise and make observable: On reset or when disabled, clear all parallel outputs, `phase_metric`, and `word_valid`. Required traces: `time`, `clk`, `rst`, `enable`, `serial_in`, `align_pulse`, `out0`, `out1`, `out2`, `out3`, `phase_metric`, `word_valid`.
- `P_A_RISING_ALIGN_PULSE_RESETS_THE`: exercise and make observable: A rising `align_pulse` resets the slot pointer so the next sampled serial bit is written to `out0`. Required traces: `time`, `clk`, `rst`, `enable`, `serial_in`, `align_pulse`, `out0`, `out1`, `out2`, `out3`, `phase_metric`, `word_valid`.
- `P_ON_EACH_RISING_CLK_EDGE_WHILE`: exercise and make observable: On each rising `clk` edge while enabled, sample `serial_in` into the active output slot and advance the slot pointer. Required traces: `time`, `clk`, `rst`, `enable`, `serial_in`, `align_pulse`, `out0`, `out1`, `out2`, `out3`, `phase_metric`, `word_valid`.
- `P_ASSERT_WORD_VALID_AFTER_ALL_FOUR`: exercise and make observable: Assert `word_valid` after all four output slots have been updated since the most recent alignment event. Required traces: `time`, `clk`, `rst`, `enable`, `serial_in`, `align_pulse`, `out0`, `out1`, `out2`, `out3`, `phase_metric`, `word_valid`.
- `P_PHASE_METRIC_MUST_EXPOSE_THE_ACTIVE`: exercise and make observable: `phase_metric` must expose the active slot pointer. Required traces: `time`, `clk`, `rst`, `enable`, `serial_in`, `align_pulse`, `out0`, `out1`, `out2`, `out3`, `phase_metric`, `word_valid`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- On reset or when disabled, clear all parallel outputs, `phase_metric`, and `word_valid`.
- A rising `align_pulse` resets the slot pointer so the next sampled serial bit is written to `out0`.
- On each rising `clk` edge while enabled, sample `serial_in` into the active output slot and advance the slot pointer.
- Assert `word_valid` after all four output slots have been updated since the most recent alignment event.
- `phase_metric` must expose the active slot pointer.


The required trace names are: `time`, `clk`, `rst`, `enable`, `serial_in`, `align_pulse`, `out0`, `out1`, `out2`, `out3`, `phase_metric`, `word_valid`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
