# Thermometer Bus Encoder Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Thermometer Bus Encoder` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `thermometer_bus_encoder.va`:
  - Module `thermometer_bus_encoder` (entry)
    - position 0: `vin` (input, electrical)
    - position 1: `t0` (output, electrical)
    - position 2: `t1` (output, electrical)
    - position 3: `t2` (output, electrical)
    - position 4: `t3` (output, electrical)
    - position 5: `t4` (output, electrical)
    - position 6: `t5` (output, electrical)
    - position 7: `t6` (output, electrical)
    - position 8: `t7` (output, electrical)
    - position 9: `t8` (output, electrical)
    - position 10: `t9` (output, electrical)
    - position 11: `t10` (output, electrical)
    - position 12: `t11` (output, electrical)
    - position 13: `t12` (output, electrical)
    - position 14: `t13` (output, electrical)
    - position 15: `t14` (output, electrical)
    - position 16: `t15` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/thermometer_bus_encoder.va`
- DUT instance: `XDUT (vin t0 t1 t2 t3 t4 t5 t6 t7 t8 t9 t10 t11 t12 t13 t14 t15) thermometer_bus_encoder`
- Required saved public traces: `vin`, `t0`, `t1`, `t2`, `t3`, `t4`, `t5`, `t6`, `t7`, `t8`, `t9`, `t10`, `t11`, `t12`, `t13`, `t14`, `t15`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `thermometer_bus_encoder.vref` defaults to `1` V; valid range: vref > 0; sets the analog full-scale reference and segment span.
- `thermometer_bus_encoder.vh` defaults to `0.9` V; valid range: vh > 0; sets the voltage-coded segment high level.
- `thermometer_bus_encoder.tr` defaults to `2e-11` s; valid range: tr > 0; sets segment-output transition smoothing.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_PREFIX_CODE`: exercise and make observable: Active segment outputs always form a contiguous prefix beginning at t0; no higher segment may be high while a lower segment is low. Required traces: `time`, `vin`, `t0`, `t1`, `t2`, `t3`, `t4`, `t5`, `t6`, `t7`, `t8`, `t9`, `t10`, `t11`, `t12`, `t13`, `t14`, `t15`.
- `P_ORDERED_ACTIVATION`: exercise and make observable: As vin increases, segments activate in order t0 through t15 and the active-segment count never decreases. Required traces: `time`, `vin`, `t0`, `t1`, `t2`, `t3`, `t4`, `t5`, `t6`, `t7`, `t8`, `t9`, `t10`, `t11`, `t12`, `t13`, `t14`, `t15`.
- `P_UNIFORM_SEGMENTS`: exercise and make observable: The clipped 0-to-vref input span selects among sixteen equal-width thermometer segments. Required traces: `time`, `vin`, `t0`, `t1`, `t2`, `t3`, `t4`, `t5`, `t6`, `t7`, `t8`, `t9`, `t10`, `t11`, `t12`, `t13`, `t14`, `t15`.
- `P_INPUT_CLIPPING`: exercise and make observable: Inputs at or below 0 V produce no active segments, and inputs at or above vref produce all sixteen active segments. Required traces: `time`, `vin`, `t0`, `t1`, `t2`, `t3`, `t4`, `t5`, `t6`, `t7`, `t8`, `t9`, `t10`, `t11`, `t12`, `t13`, `t14`, `t15`.
- `P_OUTPUT_LEVELS`: exercise and make observable: Each inactive segment approaches 0 V and each active segment approaches vh with finite transition smoothing. Required traces: `time`, `t0`, `t1`, `t2`, `t3`, `t4`, `t5`, `t6`, `t7`, `t8`, `t9`, `t10`, `t11`, `t12`, `t13`, `t14`, `t15`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Convert `vin` into a 16-segment thermometer code. Clip the input to the
0-to-`vref` range, choose the number of active segments from the clipped input
level, and drive a prefix thermometer word: `t0` is the first segment to turn
on, then `t1`, and so on up to `t15`. The output must remain monotonic with
the input and must not emit a binary-coded word.


The required trace names are: `time`, `vin`, `t0`, `t1`, `t2`, `t3`, `t4`, `t5`, `t6`, `t7`, `t8`, `t9`, `t10`, `t11`, `t12`, `t13`, `t14`, `t15`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
