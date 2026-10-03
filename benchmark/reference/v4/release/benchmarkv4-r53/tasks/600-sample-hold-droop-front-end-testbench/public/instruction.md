# Sample Hold Droop Front End Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Sample Hold Droop Front End` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `sample_hold_droop_ref.va`:
  - Module `sample_hold_droop_ref` (entry)
    - position 0: `vdd` (inout, electrical)
    - position 1: `vss` (inout, electrical)
    - position 2: `clk` (input, electrical)
    - position 3: `vin` (input, electrical)
    - position 4: `vout` (output, electrical)
    - position 5: `valid` (output, electrical)
    - position 6: `coarse` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/sample_hold_droop_ref.va`
- DUT instance: `XDUT (vdd vss clk vin vout valid coarse) sample_hold_droop_ref dt=0.5n taperture=200p tau=90n trf=40p valid_width=2n vth=0.45`
- Required saved public traces: `vdd`, `vss`, `clk`, `vin`, `vout`, `valid`, `coarse`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `sample_hold_droop_ref.vth` defaults to `0.45` V; valid range: finite real; sets the clock crossing and coarse-decision threshold.
- `sample_hold_droop_ref.trf` defaults to `4e-11` s; valid range: trf >= 0; sets output transition smoothing.
- `sample_hold_droop_ref.tau` defaults to `9e-08` s; valid range: tau > 0; sets the held-value droop time constant.
- `sample_hold_droop_ref.dt` defaults to `5e-10` s; valid range: dt > 0; sets the interval between bounded droop updates.
- `sample_hold_droop_ref.taperture` defaults to `2e-10` s; valid range: taperture >= 0; sets sampling delay after a rising clk crossing.
- `sample_hold_droop_ref.valid_width` defaults to `2e-09` s; valid range: valid_width > 0; sets the duration of the valid pulse after sampling.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_APERTURE_CAPTURE`: exercise and make observable: Each rising clk crossing schedules capture of vin after taperture rather than sampling at an unrelated time. Required traces: `time`, `clk`, `vin`, `vout`.
- `P_SUPPLY_CLAMPED_SAMPLE`: exercise and make observable: At aperture capture, the held output updates to the sampled vin clamped between the instantaneous vss and vdd rails. Required traces: `time`, `vdd`, `vss`, `clk`, `vin`, `vout`.
- `P_COARSE_DECISION`: exercise and make observable: At each capture, coarse is high when the sampled value exceeds vth and low otherwise, then holds until the next capture. Required traces: `time`, `clk`, `vin`, `coarse`.
- `P_VALID_PULSE`: exercise and make observable: Valid asserts at the aperture sample and deasserts after valid_width. Required traces: `time`, `clk`, `valid`.
- `P_LOW_PHASE_DROOP`: exercise and make observable: While clk is low, vout applies bounded droop updates governed by tau and dt instead of remaining ideal or changing discontinuously. Required traces: `time`, `clk`, `vout`.
- `P_NO_TRACK_THROUGH`: exercise and make observable: Between aperture captures, vout does not transparently track changes on vin; only the specified droop behavior is permitted. Required traces: `time`, `clk`, `vin`, `vout`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

Model a compact sampling front end:

- On each rising `clk` crossing, schedule a sample after `taperture`.
- At the aperture sample, capture `vin`, clamp the held value to the local
  `vss`-to-`vdd` range, update `vout`, assert `valid`, and update `coarse`.
- `coarse` is high when the sampled value is above `vth` and low otherwise.
- While the clock is low, apply bounded droop to the held output using `tau`
  and `dt`.
- Deassert `valid` after `valid_width`.


The required trace names are: `time`, `vdd`, `vss`, `clk`, `vin`, `vout`, `valid`, `coarse`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
