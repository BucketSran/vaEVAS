# Pipeline ADC Stage Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Pipeline ADC Stage` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `pipeline_stage.va`:
  - Module `pipeline_stage` (entry)
    - position 0: `VDD` (input, electrical)
    - position 1: `VSS` (input, electrical)
    - position 2: `PHI1` (input, electrical)
    - position 3: `PHI2` (input, electrical)
    - position 4: `VIN` (input, electrical)
    - position 5: `VREF` (input, electrical)
    - position 6: `VRES` (output, electrical)
    - position 7: `D1` (output, electrical)
    - position 8: `D0` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/pipeline_stage.va`
- DUT instance: `XDUT (vdd vss phi1 phi2 vin vref vres d1 d0) pipeline_stage tedge=200p vdd=0.9 vth=0.45`
- Required saved public traces: `VDD`, `VSS`, `PHI1`, `PHI2`, `VIN`, `VREF`, `VRES`, `D1`, `D0`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `pipeline_stage.vth` defaults to `0.45` V; valid range: V(VSS) < vth < V(VDD); sets PHI1 and PHI2 decision threshold.
- `pipeline_stage.vdd` defaults to `0.9` V; valid range: vdd > 0; sets nominal initialized output high level.
- `pipeline_stage.tedge` defaults to `2e-10` s; valid range: tedge > 0; sets output transition smoothing.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_TWO_PHASE_SAMPLING`: exercise and make observable: VIN is sampled on a rising PHI1 edge and converted on a rising PHI2 edge. Required traces: `time`, `PHI1`, `PHI2`, `VIN`, `VRES`, `D1`, `D0`.
- `P_SUBADC_REGIONS`: exercise and make observable: Upper, middle, and lower sampled-input regions produce decision codes 10, 01, and 00 respectively. Required traces: `time`, `PHI2`, `VIN`, `VREF`, `D1`, `D0`.
- `P_RESIDUE_MAPPING`: exercise and make observable: The residue is gain-two with the specified half-reference subtraction, no offset, or addition for the three regions. Required traces: `time`, `PHI2`, `VIN`, `VREF`, `VRES`, `D1`, `D0`.
- `P_RESIDUE_CLAMP`: exercise and make observable: VRES remains within the VSS-to-VDD supply range. Required traces: `time`, `VDD`, `VSS`, `VRES`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

On each rising `PHI1` edge, sample `VIN`. On each rising `PHI2` edge, compare
the sampled input around `V(VDD)/2` against the 1.5-bit thresholds
`+V(VREF)/4` and `-V(VREF)/4`.

- Upper region: drive `D1` high, `D0` low, and subtract a half-reference from
  the gain-two residue.
- Middle region: drive `D1` low, `D0` high, and use the gain-two residue
  without reference subtraction or addition.
- Lower region: drive both decision outputs low and add a half-reference to the
  gain-two residue.

Clamp `VRES` to the supply range and drive all outputs with smooth
voltage-domain transitions.


The required trace names are: `time`, `VDD`, `VSS`, `PHI1`, `PHI2`, `VIN`, `VREF`, `VRES`, `D1`, `D0`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
