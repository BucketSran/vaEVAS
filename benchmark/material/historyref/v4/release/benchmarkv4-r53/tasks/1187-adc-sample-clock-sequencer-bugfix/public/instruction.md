# ADC Sample Clock Sequencer Bugfix

## Task Contract

The supplied Verilog-A system violates its public circuit contract. Repair the
complete editable bundle.

## Public Verilog-A Interface

Preserve this exact artifact and module interface:

- Artifact `adc_sample_clock_sequencer.va`:
  - Module `adc_sample_clock_sequencer` (entry)
    - position 0: `rst` (output, electrical)
    - position 1: `s` (output, electrical)
    - position 2: `ss` (output, electrical)
    - position 3: `nc_az` (output, electrical)
    - position 4: `nc` (output, electrical)
    - position 5: `conv` (output, electrical)

## Public Parameter Contract

- No public parameter is declared.


## Required Behavior

The repaired bundle must satisfy every public property:

- `P_PERIODIC_18NS_FRAME`: restore: Generate a repeating 18 ns timing frame. Required traces: `time`, `conv`, `nc`, `nc_az`, `rst`, `s`, `ss`.
- `P_RESET_SAMPLE_AND_SS_WINDOWS`: restore: `rst`, `s`, and `ss` are high only in the declared frame windows. Required traces: `time`, `conv`, `nc`, `nc_az`, `rst`, `s`, `ss`.
- `P_NONOVERLAP_AND_AUTOZERO_WINDOWS`: restore: `nc` and `nc_az` use the declared non-overlap and autozero windows without swapping outputs. Required traces: `time`, `conv`, `nc`, `nc_az`, `rst`, `s`, `ss`.
- `P_CONVERSION_WINDOW_TIMING`: restore: `conv` is asserted in the declared conversion windows with the correct phase. Required traces: `time`, `conv`, `nc`, `nc_az`, `rst`, `s`, `ss`.
- `P_TIMING_OUTPUT_LEVELS`: restore: All timing outputs drive valid voltage-coded low/high levels. Required traces: `time`, `conv`, `nc`, `nc_az`, `rst`, `s`, `ss`.


The following canonical public behavior is normative for this derived form:

Generate a repeating 18 ns ADC timing frame with these high windows: `rst` from 0 to 0.25 ns; `s` from 0.6 to 1.0 ns, 6.6 to 7.0 ns, and 12.6 to 13.0 ns; `ss` from 0.6 to 1.2 ns, 6.6 to 7.2 ns, and 12.6 to 13.2 ns; `nc_az` from 1.35 to 1.55 ns, 7.35 to 7.55 ns, and 13.35 to 13.55 ns; `nc` from 1.7 to 2.05 ns, 7.7 to 8.05 ns, and 13.7 to 14.05 ns; and `conv` from 2.4 to 5.4 ns, 8.4 to 11.4 ns, and 14.4 to 17.4 ns. All outputs should return low between their public windows and repeat every 18 ns.


## Modeling Constraints

- Use deterministic voltage-domain behavioral Verilog-A.
- Do not hard-code validation stimulus, stop times, sample windows, gold internals, or simulator side channels.
- Preserve the exact file set, module graph, ports, parameters, and public traces.
- Do not add debug outputs, validation state, side channels, or stimulus-specific fixes.

## Output Contract

Return the repaired bundle with exactly these paths: `adc_sample_clock_sequencer.va`.
Every supplied `.va` file is editable; do not add or omit files.
