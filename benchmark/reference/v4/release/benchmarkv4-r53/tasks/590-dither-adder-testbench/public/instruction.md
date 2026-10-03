# Dither Adder Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Dither Adder` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `dither_adder.va`:
  - Module `dither_adder` (entry)
    - position 0: `VRES_P` (input, electrical)
    - position 1: `VRES_N` (input, electrical)
    - position 2: `DPN` (input, electrical)
    - position 3: `VOUT_P` (output, electrical)
    - position 4: `VOUT_N` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/dither_adder.va`
- DUT instance: `XDUT (vres_p vres_n dpn vout_p vout_n) dither_adder DITHER_AMP=dither vdd=vdd vth=0.45`
- Required saved public traces: `vres_p`, `vres_n`, `dpn`, `vout_p`, `vout_n`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `dither_adder.vdd` defaults to `0.9` V; valid range: vdd > 0; preserves the public compatibility supply-domain parameter.
- `dither_adder.vth` defaults to `0.45` V; valid range: finite real; sets the DPN polarity threshold.
- `dither_adder.DITHER_AMP` defaults to `0.014063` V differential; valid range: DITHER_AMP >= 0; sets the magnitude of the injected differential dither.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_POSITIVE_DITHER`: exercise and make observable: When DPN is above vth, the output differential exceeds the input differential by DITHER_AMP. Required traces: `time`, `vres_p`, `vres_n`, `dpn`, `vout_p`, `vout_n`.
- `P_NEGATIVE_DITHER`: exercise and make observable: When DPN is at or below vth, the output differential is lower than the input differential by DITHER_AMP. Required traces: `time`, `vres_p`, `vres_n`, `dpn`, `vout_p`, `vout_n`.
- `P_SYMMETRIC_SPLIT`: exercise and make observable: Half of the selected differential dither is added to VOUT_P and half is subtracted from VOUT_N. Required traces: `time`, `vres_p`, `vres_n`, `dpn`, `vout_p`, `vout_n`.
- `P_COMMON_MODE_PRESERVATION`: exercise and make observable: The output pair preserves the input common mode and does not introduce a vdd/2 offset. Required traces: `time`, `vres_p`, `vres_n`, `vout_p`, `vout_n`.
- `P_PARAMETER_OVERRIDE`: exercise and make observable: Legal DITHER_AMP and vth overrides change only dither magnitude and polarity decision as declared. Required traces: `time`, `dpn`, `vres_p`, `vres_n`, `vout_p`, `vout_n`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

The supplied DUT is a standalone differential dither injection block. The supplied DUT receives
a differential residual signal on `VRES_P/VRES_N` and a voltage-coded dither
polarity input `DPN`. When `DPN` is above the threshold, inject a positive
differential dither; when it is below the threshold, inject a negative
differential dither.

The injected differential offset is controlled by parameter `DITHER_AMP`
and must be split symmetrically between the two outputs:

```text
dither_diff = +DITHER_AMP when V(DPN) > vth
dither_diff = -DITHER_AMP when V(DPN) <= vth
VOUT_P = VRES_P + dither_diff / 2
VOUT_N = VRES_N - dither_diff / 2
```

This keeps the output common-mode equal to the input common-mode while adding
only the requested differential dither. Keep the block usable with legal
`DITHER_AMP` parameter overrides.

The standalone dither operation preserves input common-mode and does not add a
`vdd/2` output offset. Honor legal overrides of these parameters. Use `vth` to
interpret the voltage-coded `DPN` polarity input, and keep the model pure
behavioral Verilog-A. Smooth the event-updated dither target with a short
transition so the output does not introduce discontinuous digital steps. Do not
use transistor-level devices, AC/noise analysis, waveform files, validation
artifacts, or simulator side channels.


The required trace names are: `time`, `vres_p`, `vres_n`, `dpn`, `vout_p`, `vout_n`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
