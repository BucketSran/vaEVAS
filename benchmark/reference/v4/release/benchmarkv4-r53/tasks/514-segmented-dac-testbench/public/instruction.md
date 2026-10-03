# Segmented DAC Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Segmented DAC` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `segmented_dac.va`:
  - Module `segmented_dac` (entry)
    - position 0: `b0` (input, electrical)
    - position 1: `b1` (input, electrical)
    - position 2: `t0` (input, electrical)
    - position 3: `t1` (input, electrical)
    - position 4: `t2` (input, electrical)
    - position 5: `vref` (input, electrical)
    - position 6: `vss` (input, electrical)
    - position 7: `aout` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/segmented_dac.va`
- DUT instance: `XDUT (b0 b1 t0 t1 t2 vref vss aout) segmented_dac`
- Required saved public traces: `b0`, `b1`, `t0`, `t1`, `t2`, `vref`, `vss`, `aout`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `segmented_dac.vth` defaults to `0.45` V; valid range: vth > 0; sets binary and thermometer control threshold.
- `segmented_dac.tr` defaults to `5e-10` s; valid range: tr > 0; sets output transition smoothing.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_SEGMENT_WEIGHTS`: exercise and make observable: b0 and b1 contribute one and two LSB steps while each active thermometer control contributes four LSB steps. Required traces: `time`, `b0`, `b1`, `t0`, `t1`, `t2`, `aout`.
- `P_CODE_MONOTONICITY`: exercise and make observable: Increasing the summed segmented code does not decrease aout. Required traces: `time`, `b0`, `b1`, `t0`, `t1`, `t2`, `aout`.
- `P_ENDPOINTS`: exercise and make observable: The zero code maps to vss and the all-active 15-step code maps to vref. Required traces: `time`, `b0`, `b1`, `t0`, `t1`, `t2`, `vref`, `vss`, `aout`.
- `P_RAIL_RELATIVE_MAPPING`: exercise and make observable: Intermediate codes linearly span the vss-to-vref range. Required traces: `time`, `b0`, `b1`, `t0`, `t1`, `t2`, `vref`, `vss`, `aout`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Treat `b0` and `b1` as binary LSB controls with weights 1 and 2. Treat
`t0`, `t1`, and `t2` as unary thermometer segment controls, each contributing
four LSB steps. Drive `aout` between `vss` and `vref` according to the summed
15-step segmented code, so the all-active code reaches full scale.


The required trace names are: `time`, `b0`, `b1`, `t0`, `t1`, `t2`, `vref`, `vss`, `aout`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
