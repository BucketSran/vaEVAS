# LNA Blocker Compression Detector Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `LNA Blocker Compression Detector` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `lna_blocker_compression_detector.va`:
  - Module `lna_blocker_compression_detector` (entry)
    - position 0: `vin` (inout, electrical)
    - position 1: `blocker` (inout, electrical)
    - position 2: `enable` (inout, electrical)
    - position 3: `rst` (inout, electrical)
    - position 4: `vout` (inout, electrical)
    - position 5: `compression_metric` (inout, electrical)
    - position 6: `compressed` (inout, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/lna_blocker_compression_detector.va`
- DUT instance: `XDUT (vin blocker enable rst vout compression_metric compressed) lna_blocker_compression_detector`
- Required saved public traces: `vin`, `blocker`, `enable`, `rst`, `vout`, `compression_metric`, `compressed`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `lna_blocker_compression_detector.vdd` defaults to `0.9`; valid range: finite; overrides vdd.
- `lna_blocker_compression_detector.vss` defaults to `0.0`; valid range: finite; overrides vss.
- `lna_blocker_compression_detector.vcm` defaults to `0.45`; valid range: finite; overrides vcm.
- `lna_blocker_compression_detector.vth` defaults to `0.45`; valid range: finite; overrides vth.
- `lna_blocker_compression_detector.tr` defaults to `200p from (0:inf)`; valid range: finite; overrides tr.
- `lna_blocker_compression_detector.small_gain` defaults to `6.0`; valid range: finite; overrides small_gain.
- `lna_blocker_compression_detector.blocker_start` defaults to `0.6`; valid range: finite; overrides blocker_start.
- `lna_blocker_compression_detector.compression_tol` defaults to `0.1`; valid range: finite; overrides compression_tol.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_ON_RESET_OR_WHEN_DISABLED_DRIVE`: exercise and make observable: On reset or when disabled, drive output to `vcm` and clear compression outputs. Required traces: `time`, `vin`, `blocker`, `enable`, `rst`, `vout`, `compression_metric`, `compressed`.
- `P_AMPLIFY_VIN_VCM_WITH_SMALL_SIGNAL`: exercise and make observable: Amplify `vin - vcm` with small-signal gain when `blocker` is low. Required traces: `time`, `vin`, `blocker`, `enable`, `rst`, `vout`, `compression_metric`, `compressed`.
- `P_REDUCE_EFFECTIVE_GAIN_AS_BLOCKER_RISES`: exercise and make observable: Reduce effective gain as `blocker` rises above `blocker_start`. Required traces: `time`, `vin`, `blocker`, `enable`, `rst`, `vout`, `compression_metric`, `compressed`.
- `P_EXPOSE_GAIN_REDUCTION_ON_COMPRESSION_METRIC`: exercise and make observable: Expose gain reduction on `compression_metric`. Required traces: `time`, `vin`, `blocker`, `enable`, `rst`, `vout`, `compression_metric`, `compressed`.
- `P_ASSERT_COMPRESSED_ONLY_WHEN_THE_EFFECTIVE`: exercise and make observable: Assert `compressed` only when the effective gain is reduced by more than `compression_tol`. Required traces: `time`, `vin`, `blocker`, `enable`, `rst`, `vout`, `compression_metric`, `compressed`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- On reset or when disabled, drive output to `vcm` and clear compression outputs.
- Amplify `vin - vcm` with small-signal gain when `blocker` is low.
- Reduce effective gain as `blocker` rises above `blocker_start`.
- Expose gain reduction on `compression_metric`.
- Assert `compressed` only when the effective gain is reduced by more than `compression_tol`.
- Use only voltage-domain behavioral state and voltage contributions on public electrical outputs.
- Do not expose pass/fail flags; expose only the public observable metrics named in the interface.


The required trace names are: `time`, `vin`, `blocker`, `enable`, `rst`, `vout`, `compression_metric`, `compressed`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
