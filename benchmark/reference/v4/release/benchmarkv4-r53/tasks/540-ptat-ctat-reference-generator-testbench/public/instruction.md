# PTAT CTAT Reference Generator Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `PTAT CTAT Reference Generator` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `ptat_ctat_reference_generator.va`:
  - Module `ptat_ctat_reference_generator` (entry)
    - position 0: `clk` (input, electrical)
    - position 1: `rst` (input, electrical)
    - position 2: `vin` (input, electrical)
    - position 3: `out` (output, electrical)
    - position 4: `metric` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/ptat_ctat_reference_generator.va`
- DUT instance: `XDUT (clk rst vin out metric) ptat_ctat_reference_generator`
- Required saved public traces: `clk`, `rst`, `vin`, `out`, `metric`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `ptat_ctat_reference_generator.tr` defaults to `1e-10` s; valid range: tr > 0; sets output and metric transition smoothing.
- `ptat_ctat_reference_generator.vth` defaults to `0.45` V; valid range: 0 < vth < 0.9; sets clk and rst logic threshold.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RESET_REFERENCE`: exercise and make observable: Reset initializes out to 0.45 V and metric to 0 V until a valid rising-clock update. Required traces: `time`, `clk`, `rst`, `out`, `metric`.
- `P_INPUT_CLAMP`: exercise and make observable: Each rising clk update with reset inactive samples vin and clamps the temperature/control value to 0 V through 0.9 V. Required traces: `time`, `clk`, `rst`, `vin`, `out`, `metric`.
- `P_PTAT_TREND`: exercise and make observable: Metric reports the PTAT branch 0.18 V plus 0.34 times the clamped sampled input and therefore increases monotonically with vin. Required traces: `time`, `clk`, `vin`, `metric`.
- `P_CTAT_PTAT_AVERAGE`: exercise and make observable: Out is the equal-weight average of PTAT = 0.18 V + 0.34*vin_clamped and CTAT = 0.78 V - 0.34*vin_clamped. Required traces: `time`, `clk`, `vin`, `out`, `metric`.
- `P_REFERENCE_BOUNDS`: exercise and make observable: Out remains within the public 0 V through 0.9 V voltage range with finite transition smoothing. Required traces: `time`, `out`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

- `clk` and `rst` are voltage-coded logic signals.
- Treat `vin` as a normalized temperature/control voltage in the 0 V to 0.9 V range.
- Reset should initialize `out` to 0.45 V and drive `metric` to 0 V until
  valid updates occur.
- On each rising `clk` crossing with reset low, clamp the sampled temperature
  input to `[0 V, 0.9 V]`.
- Compute the PTAT branch as `0.18 V + 0.34 * vin_clamped` and the CTAT branch
  as `0.78 V - 0.34 * vin_clamped`.
- Drive the reference output as the equal-weight branch average:
  `out = 0.5 * ptat + 0.5 * ctat`.
- Drive `metric` as the PTAT branch voltage so it increases with the
  temperature/control input.
- Clamp the driven `out` voltage to the public 0 V to 0.9 V voltage-domain
  range.
- Keep the model pure voltage-domain behavioral Verilog-A. Do not use branch-current contributions, transistor-level devices, AC/noise analysis, or KCL/KVL regulation loops.


The required trace names are: `time`, `clk`, `rst`, `vin`, `out`, `metric`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
