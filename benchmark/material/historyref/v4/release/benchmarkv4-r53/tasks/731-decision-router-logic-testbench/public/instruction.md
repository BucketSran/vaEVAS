# Decision Router Logic Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Decision Router Logic` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `decision_router_logic.va`:
  - Module `decision_router_logic` (entry)
    - position 0: `vin1` (input, electrical)
    - position 1: `vin2` (input, electrical)
    - position 2: `valid` (input, electrical)
    - position 3: `x` (output, electrical)
    - position 4: `y` (output, electrical)
    - position 5: `z` (output, electrical)
    - position 6: `dm` (output, electrical)
    - position 7: `dl` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/decision_router_logic.va`
- DUT instance: `XDUT (vin1 vin2 valid x y z dm dl) decision_router_logic`
- Required saved public traces: `dl`, `dm`, `valid`, `vin1`, `vin2`, `x`, `y`, `z`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `decision_router_logic.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `decision_router_logic.vh` defaults to `0.9`; valid range: finite; overrides vh.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_INTERPRET_VIN1_VIN2_AND_VALID_RELATIVE`: exercise and make observable: Interpret `vin1`, `vin2`, and `valid` relative to `vth`; all routed decisions below are evaluated from those voltage-coded Boolean inputs. Required traces: `time`, `dl`, `dm`, `valid`, `vin1`, `vin2`, `x`, `y`, `z`.
- `P_DRIVE_DM_HIGH_WHEN_VIN1_IS`: exercise and make observable: Drive `dm` high when `vin1` is high and low otherwise. Required traces: `time`, `dl`, `dm`, `valid`, `vin1`, `vin2`, `x`, `y`, `z`.
- `P_DRIVE_DL_HIGH_WHEN_VIN1_IS`: exercise and make observable: Drive `dl` high when `vin1` is low and `vin2` is high, and low otherwise. Required traces: `time`, `dl`, `dm`, `valid`, `vin1`, `vin2`, `x`, `y`, `z`.
- `P_DRIVE_X_HIGH_WHEN_VALID_IS`: exercise and make observable: Drive `x` high only when `valid` is high and both decision inputs are low. Required traces: `time`, `dl`, `dm`, `valid`, `vin1`, `vin2`, `x`, `y`, `z`.
- `P_DRIVE_Y_HIGH_WHEN_VALID_IS`: exercise and make observable: Drive `y` high only when `valid` is high and both decision inputs are high. Required traces: `time`, `dl`, `dm`, `valid`, `vin1`, `vin2`, `x`, `y`, `z`.
- `P_DRIVE_Z_HIGH_WHEN_VALID_IS`: exercise and make observable: Drive `z` high only when `valid` is high, `vin1` is low, and `vin2` is high. Required traces: `time`, `dl`, `dm`, `valid`, `vin1`, `vin2`, `x`, `y`, `z`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- Interpret `vin1`, `vin2`, and `valid` relative to `vth`.
- Drive `dm` high when `vin1` is high.
- Drive `dl` high when `vin1` is low and `vin2` is high.
- Drive `x` high when `valid` is high and both decision inputs are low.
- Drive `y` high when `valid` is high and both decision inputs are high.
- Drive `z` high when `valid` is high, `vin1` is low, and `vin2` is high.
- Drive all other listed outputs low under their inactive conditions.


The required trace names are: `time`, `dl`, `dm`, `valid`, `vin1`, `vin2`, `x`, `y`, `z`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
