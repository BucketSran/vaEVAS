# Dynamic Supply Level Driver Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Dynamic Supply Level Driver` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `dynamic_supply_level_driver.va`:
  - Module `dynamic_supply_level_driver` (entry)
    - position 0: `din` (input, electrical)
    - position 1: `vdd` (input, electrical)
    - position 2: `vss` (input, electrical)
    - position 3: `out` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/dynamic_supply_level_driver.va`
- DUT instance: `XDUT (din vdd vss out) dynamic_supply_level_driver`
- Required saved public traces: `din`, `out`, `vdd`, `vss`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `dynamic_supply_level_driver.vsup_min` defaults to `0.55`; valid range: finite; overrides vsup_min.
- `dynamic_supply_level_driver.vth_frac` defaults to `0.5`; valid range: finite; overrides vth_frac.
- `dynamic_supply_level_driver.vlo_frac` defaults to `0.0`; valid range: finite; overrides vlo_frac.
- `dynamic_supply_level_driver.vhi_frac` defaults to `1.0`; valid range: finite; overrides vhi_frac.
- `dynamic_supply_level_driver.tr` defaults to `40p`; valid range: finite; overrides tr.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_MODEL_A_DYNAMIC_SUPPLY_ELECTRICAL_LEVEL`: exercise and make observable: Model a dynamic-supply electrical level driver. Compute the input level relative to the local rails, not global ground. When `V(vdd, vss)` is at least `vsup_min`, drive `out` to the local low or high rail-derived level according to whether the normalized input exceeds `vth_frac`. When the supply is below `vsup_min`, drive `out` to the local low level. Smooth the output with `transition()`. Required traces: `time`, `din`, `out`, `vdd`, `vss`.
- `P_BUILD_A_DYNAMIC_SUPPLY_VOLTAGE_DOMAIN`: exercise and make observable: Build a dynamic-supply voltage-domain level driver. The module thresholds its input relative to local supply rails, drives its output relative to those same rails, and falls back to the local low level when the supply is invalid. Required traces: `time`, `din`, `out`, `vdd`, `vss`.
- `P_VSUP_MIN_0_55_V_MINIMUM`: exercise and make observable: `vsup_min = 0.55 V`: minimum `V(vdd, vss)` required for normal operation. Required traces: `time`, `din`, `out`, `vdd`, `vss`.
- `P_VTH_FRAC_0_5_INPUT_THRESHOLD`: exercise and make observable: `vth_frac = 0.5`: input threshold expressed as a fraction of the local supply Required traces: `time`, `din`, `out`, `vdd`, `vss`.
- `P_VLO_FRAC_0_0_VHI_FRAC`: exercise and make observable: `vlo_frac = 0.0`, `vhi_frac = 1.0`: output low and high levels expressed as Required traces: `time`, `din`, `out`, `vdd`, `vss`.
- `P_TR_40P_OUTPUT_TRANSITION_SMOOTHING_TIME`: exercise and make observable: `tr = 40p`: output transition smoothing time. Required traces: `time`, `din`, `out`, `vdd`, `vss`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Model a dynamic-supply electrical level driver. Compute the input level relative
to the local rails, not global ground. When `V(vdd, vss)` is at least
`vsup_min`, drive `out` to the local low or high rail-derived level according to
whether the normalized input exceeds `vth_frac`. When the supply is below
`vsup_min`, drive `out` to the local low level. Smooth the output with
`transition()`.


The required trace names are: `time`, `din`, `out`, `vdd`, `vss`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
