# Hysteresis Trip Characterizer Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Hysteresis Trip Characterizer` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `hysteresis_trip_characterizer.va`:
  - Module `hysteresis_trip_characterizer` (entry)
    - position 0: `vdd` (input, electrical)
    - position 1: `vss` (input, electrical)
    - position 2: `vin` (input, electrical)
    - position 3: `cmp_out` (input, electrical)
    - position 4: `trip_rise` (output, electrical)
    - position 5: `trip_fall` (output, electrical)
    - position 6: `hyst_width` (output, electrical)
    - position 7: `valid` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/hysteresis_trip_characterizer.va`
- DUT instance: `XMEAS (vdd vss vin cmp_out trip_rise trip_fall hyst_width valid) hysteresis_trip_characterizer`
- Required saved public traces: `vdd`, `vss`, `vin`, `cmp_out`, `trip_rise`, `trip_fall`, `hyst_width`, `valid`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `hysteresis_trip_characterizer.tr` defaults to `2e-11` s; valid range: tr >= 0; sets transition smoothing for captured trip values, hysteresis width, and valid.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_SUPPLY_MIDPOINT_THRESHOLD`: exercise and make observable: The characterizer detects cmp_out transitions through the instantaneous midpoint of vdd and vss. Required traces: `time`, `vdd`, `vss`, `cmp_out`.
- `P_RISING_TRIP_CAPTURE`: exercise and make observable: On each rising cmp_out midpoint crossing, trip_rise captures the instantaneous vin minus vss value. Required traces: `time`, `vss`, `vin`, `cmp_out`, `trip_rise`.
- `P_FALLING_TRIP_CAPTURE`: exercise and make observable: On each falling cmp_out midpoint crossing, trip_fall captures the instantaneous vin minus vss value. Required traces: `time`, `vss`, `vin`, `cmp_out`, `trip_fall`.
- `P_LATEST_EDGE_REFRESH`: exercise and make observable: Later rising or falling transitions refresh the corresponding captured trip value rather than leaving only the first measurement. Required traces: `time`, `vin`, `cmp_out`, `trip_rise`, `trip_fall`.
- `P_HYSTERESIS_WIDTH_SIGN`: exercise and make observable: After both directions are captured, hyst_width equals trip_rise minus trip_fall with that signed polarity. Required traces: `time`, `trip_rise`, `trip_fall`, `hyst_width`.
- `P_VALID_AFTER_BOTH_DIRECTIONS`: exercise and make observable: Valid remains at vss until at least one rising and one falling trip have been captured, then rises to vdd. Required traces: `time`, `vdd`, `vss`, `cmp_out`, `valid`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- Use the midpoint between `vdd` and `vss` as the decision threshold for
  `cmp_out`.
- When `cmp_out` rises through the midpoint, capture the instantaneous
  `vin - vss` value into `trip_rise`.
- When `cmp_out` falls through the midpoint, capture the instantaneous
  `vin - vss` value into `trip_fall`.
- Continue updating the captured values on later output transitions.
- Drive `hyst_width` as `trip_rise - trip_fall` once both captures are present.
- Drive `valid` low until both directions have been captured, then drive it
  high.


The required trace names are: `time`, `vdd`, `vss`, `vin`, `cmp_out`, `trip_rise`, `trip_fall`, `hyst_width`, `valid`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Include the supplied read-only support files only from
  `./dut/support/...`; do not reference `./support/...` or undeclared paths.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
