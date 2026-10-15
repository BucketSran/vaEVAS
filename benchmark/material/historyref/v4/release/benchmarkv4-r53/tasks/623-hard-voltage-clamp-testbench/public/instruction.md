# Hard Voltage Clamp Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Hard Voltage Clamp` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `hard_voltage_clamp_behavior.va`:
  - Module `hard_voltage_clamp_behavior` (entry)
    - position 0: `vin` (input, electrical)
    - position 1: `vout` (output, electrical)
    - position 2: `vgnd` (input, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/hard_voltage_clamp_behavior.va`
- DUT instance: `XDUT (vin vout 0) hard_voltage_clamp_behavior vclamp_lower=-0.2 vclamp_upper=0.6`
- Required saved public traces: `vin`, `vout`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `hard_voltage_clamp_behavior.vclamp_upper` defaults to `1`; valid range: finite; overrides vclamp_upper.
- `hard_voltage_clamp_behavior.vclamp_lower` defaults to `0`; valid range: finite; overrides vclamp_lower.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_GROUND_REFERENCED_INPUT`: exercise and make observable: Measure the clamp input as `V(vin, vgnd)` and drive `V(vout, vgnd)` relative to the same reference. Required traces: `time`, `vin`, `vout`.
- `P_PASSBAND_TRANSFER`: exercise and make observable: When the referenced input lies inside `[vclamp_lower, vclamp_upper]`, pass that referenced voltage to the output. Required traces: `time`, `vin`, `vout`.
- `P_LOWER_CLAMP`: exercise and make observable: When the referenced input is below `vclamp_lower`, drive the lower clamp value. Required traces: `time`, `vin`, `vout`.
- `P_UPPER_CLAMP`: exercise and make observable: When the referenced input is above `vclamp_upper`, drive the upper clamp value. Required traces: `time`, `vin`, `vout`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- `P_GROUND_REFERENCED_INPUT`: Measure the clamp input as `V(vin, vgnd)` and drive `V(vout, vgnd)` relative to the same reference.

- `P_PASSBAND_TRANSFER`: When the referenced input lies inside `[vclamp_lower, vclamp_upper]`, pass that referenced voltage to the output.

- `P_LOWER_CLAMP`: When the referenced input is below `vclamp_lower`, drive the lower clamp value.

- `P_UPPER_CLAMP`: When the referenced input is above `vclamp_upper`, drive the upper clamp value.


The required trace names are: `time`, `vin`, `vout`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
