# Dither Adder Bugfix

## Task Contract

The supplied Verilog-A system violates its public circuit contract. Repair the
complete editable bundle.

## Public Verilog-A Interface

Preserve this exact artifact and module interface:

- Artifact `dither_adder.va`:
  - Module `dither_adder` (entry)
    - position 0: `VRES_P` (input, electrical)
    - position 1: `VRES_N` (input, electrical)
    - position 2: `DPN` (input, electrical)
    - position 3: `VOUT_P` (output, electrical)
    - position 4: `VOUT_N` (output, electrical)

## Public Parameter Contract

- `dither_adder.vdd` defaults to `0.9` V; valid range: vdd > 0; preserves the public compatibility supply-domain parameter.
- `dither_adder.vth` defaults to `0.45` V; valid range: finite real; sets the DPN polarity threshold.
- `dither_adder.DITHER_AMP` defaults to `0.014063` V differential; valid range: DITHER_AMP >= 0; sets the magnitude of the injected differential dither.


## Required Behavior

The repaired bundle must satisfy every public property:

- `P_POSITIVE_DITHER`: restore: When DPN is above vth, the output differential exceeds the input differential by DITHER_AMP. Required traces: `time`, `vres_p`, `vres_n`, `dpn`, `vout_p`, `vout_n`.
- `P_NEGATIVE_DITHER`: restore: When DPN is at or below vth, the output differential is lower than the input differential by DITHER_AMP. Required traces: `time`, `vres_p`, `vres_n`, `dpn`, `vout_p`, `vout_n`.
- `P_SYMMETRIC_SPLIT`: restore: Half of the selected differential dither is added to VOUT_P and half is subtracted from VOUT_N. Required traces: `time`, `vres_p`, `vres_n`, `dpn`, `vout_p`, `vout_n`.
- `P_COMMON_MODE_PRESERVATION`: restore: The output pair preserves the input common mode and does not introduce a vdd/2 offset. Required traces: `time`, `vres_p`, `vres_n`, `vout_p`, `vout_n`.
- `P_PARAMETER_OVERRIDE`: restore: Legal DITHER_AMP and vth overrides change only dither magnitude and polarity decision as declared. Required traces: `time`, `dpn`, `vres_p`, `vres_n`, `vout_p`, `vout_n`.


The following canonical public behavior is normative for this derived form:

Implement a standalone differential dither injection block. The module receives
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

Only `dither_adder.va` is graded as the candidate implementation.


## Modeling Constraints

- Use deterministic voltage-domain differential dither injection.
- Preserve common mode and smooth polarity-updated dither targets.
- Do not use transistor-level devices, AC/noise analysis, waveform artifacts, or simulator side channels.
- Preserve the exact file set, module graph, ports, parameters, and public traces.
- Do not add debug outputs, validation state, side channels, or stimulus-specific fixes.

## Output Contract

Return the repaired bundle with exactly these paths: `dither_adder.va`.
Every supplied `.va` file is editable; do not add or omit files.
