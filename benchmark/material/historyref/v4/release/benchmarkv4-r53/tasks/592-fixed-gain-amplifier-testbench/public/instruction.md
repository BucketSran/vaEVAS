# Fixed Gain Amplifier Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Fixed Gain Amplifier` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `gain_amp_fixed.va`:
  - Module `gain_amp_fixed` (entry)
    - position 0: `VIN_P` (input, electrical)
    - position 1: `VIN_N` (input, electrical)
    - position 2: `VOUT_P` (output, electrical)
    - position 3: `VOUT_N` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/gain_amp_fixed.va`
- DUT instance: `XDUT (vin_p vin_n vout_p vout_n) gain_amp_fixed ACTUAL_GAIN=gain vdd=vdd`
- Required saved public traces: `vin_p`, `vin_n`, `vout_p`, `vout_n`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `gain_amp_fixed.vdd` defaults to `0.9` V; valid range: vdd > 0; sets twice the output common-mode level.
- `gain_amp_fixed.ACTUAL_GAIN` defaults to `8.64` V/V; valid range: ACTUAL_GAIN > 0; sets positive differential voltage gain.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_DIFFERENTIAL_GAIN`: exercise and make observable: The output differential equals ACTUAL_GAIN times the input differential. Required traces: `time`, `vin_p`, `vin_n`, `vout_p`, `vout_n`.
- `P_POSITIVE_POLARITY`: exercise and make observable: A positive input differential produces a positive output differential and a negative input differential produces a negative output differential. Required traces: `time`, `vin_p`, `vin_n`, `vout_p`, `vout_n`.
- `P_OUTPUT_COMMON_MODE`: exercise and make observable: The output pair remains centered at vdd/2 independently of input common mode. Required traces: `time`, `vin_p`, `vin_n`, `vout_p`, `vout_n`.
- `P_SYMMETRIC_OUTPUT_PAIR`: exercise and make observable: Half the amplified differential is added to VOUT_P and half is subtracted from VOUT_N. Required traces: `time`, `vin_p`, `vin_n`, `vout_p`, `vout_n`.
- `P_PARAMETER_OVERRIDES`: exercise and make observable: Legal ACTUAL_GAIN and vdd overrides alter differential gain and output common mode according to their declared meanings. Required traces: `time`, `vin_p`, `vin_n`, `vout_p`, `vout_n`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

The supplied DUT is a standalone fixed-gain differential amplifier. The supplied DUT receives
`VIN_P/VIN_N`, computes the input differential voltage, multiplies it by the
`ACTUAL_GAIN` parameter, and produces a differential output centered around
`vdd/2`:

```text
vout_diff = ACTUAL_GAIN * (VIN_P - VIN_N)
VOUT_P = vdd/2 + vout_diff / 2
VOUT_N = vdd/2 - vout_diff / 2
```

The amplifier must preserve output common-mode at `vdd/2`, keep positive
polarity from input differential to output differential, and honor different
`ACTUAL_GAIN` and `vdd` values supplied by the testbench.

Public parameters:

- `ACTUAL_GAIN = 8.64`: positive dimensionless differential voltage gain.
- `vdd = 0.9 V`: positive output common-mode supply parameter; the nominal
  output common-mode is `vdd/2`.

Honor legal testbench overrides of both parameters while preserving positive
differential polarity and common-mode behavior.

Keep the model pure behavioral Verilog-A. Do not use transistor-level devices,
AC/noise analysis, waveform files, validation artifacts, or simulator side
channels.


The required trace names are: `time`, `vin_p`, `vin_n`, `vout_p`, `vout_n`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
