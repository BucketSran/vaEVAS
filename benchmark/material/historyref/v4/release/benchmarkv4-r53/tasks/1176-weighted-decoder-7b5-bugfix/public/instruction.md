# Weighted Decoder 7b5 Bugfix

## Task Contract

The supplied Verilog-A system violates its public circuit contract. Repair the
complete editable bundle.

## Public Verilog-A Interface

Preserve this exact artifact and module interface:

- Artifact `weighted_decoder_7b5.va`:
  - Module `weighted_decoder_7b5` (entry)
    - position 0: `d0` (input, electrical)
    - position 1: `d1` (input, electrical)
    - position 2: `d2` (input, electrical)
    - position 3: `d3` (input, electrical)
    - position 4: `d4` (input, electrical)
    - position 5: `d5` (input, electrical)
    - position 6: `d6` (input, electrical)
    - position 7: `d7` (input, electrical)
    - position 8: `d8` (input, electrical)
    - position 9: `aout7b` (output, electrical)
    - position 10: `aout7b5` (output, electrical)
    - position 11: `aout8b` (output, electrical)

## Public Parameter Contract

- `weighted_decoder_7b5.vth` defaults to `0.5`; valid range: finite; overrides vth.


## Required Behavior

The repaired bundle must satisfy every public property:

- `P_SHARED_272_DENOMINATOR`: restore: All decoded outputs use the shared normalization denominator of 272.0, including the fixed reference basis. Required traces: `time`, `d0`, `d1`, `d2`, `d3`, `d4`, `d5`, `d6`, `d7`, `d8`, `aout7b`, `aout7b5`, `aout8b`.
- `P_SEVEN_BIT_OUTPUT`: restore: `aout7b` reports the 7-bit decoded analog output with the specified redundant SAR weights. Required traces: `time`, `d0`, `d1`, `d2`, `d3`, `d4`, `d5`, `d6`, `aout7b`.
- `P_SEVEN_HALF_BIT_OUTPUT`: restore: `aout7b5` preserves the half-bit redundant contribution and correct polarity. Required traces: `time`, `d0`, `d1`, `d2`, `d3`, `d4`, `d5`, `d6`, `d7`, `aout7b5`.
- `P_EIGHT_BIT_OUTPUT`: restore: `aout8b` reports the full 8-bit weighted output with the correct amplitude. Required traces: `time`, `d0`, `d1`, `d2`, `d3`, `d4`, `d5`, `d6`, `d7`, `d8`, `aout8b`.


The following canonical public behavior is normative for this derived form:

Produce three related decoded analog outputs using a shared normalization denominator of `272.0`, corresponding to twice the public redundant SAR array basis including the fixed reference basis rather than only the switchable weights. Let `b0..b8` be the signed input decisions, where a high input is `+1` and a low input is `-1`. `aout7b` decodes the shared ladder from `d1..d8` as `(b1 + 2*b2 + 4*b3 + 8*b4 + 8*b5 + 16*b6 + 32*b7 + 64*b8) / 272.0`. `aout8b` adds the half-weight `d0` contribution as `(0.5*b0 + b1 + 2*b2 + 4*b3 + 8*b4 + 8*b5 + 16*b6 + 32*b7 + 64*b8) / 272.0`. For `aout7b5`, use `d0` and `d1` as a three-level subrange pair: both high selects `+1`, both low selects `-1`, and mixed decisions select `0`; then decode `(sublevel + 2*b2 + 4*b3 + 8*b4 + 8*b5 + 16*b6 + 32*b7 + 64*b8) / 272.0`.


## Modeling Constraints

- Use deterministic voltage-domain behavioral Verilog-A.
- Do not hard-code validation stimulus, stop times, sample windows, gold internals, or simulator side channels.
- Preserve the exact file set, module graph, ports, parameters, and public traces.
- Do not add debug outputs, validation state, side channels, or stimulus-specific fixes.

## Output Contract

Return the repaired bundle with exactly these paths: `weighted_decoder_7b5.va`.
Every supplied `.va` file is editable; do not add or omit files.
