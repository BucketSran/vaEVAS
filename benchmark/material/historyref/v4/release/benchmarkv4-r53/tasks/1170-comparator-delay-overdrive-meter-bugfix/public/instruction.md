# Comparator Delay Overdrive Meter Bugfix

## Task Contract

The supplied Verilog-A system violates its public circuit contract. Repair the
complete editable bundle.

## Public Verilog-A Interface

Preserve this exact artifact and module interface:

- Artifact `comparator_delay_overdrive_meter.va`:
  - Module `comparator_delay_overdrive_meter` (entry)
    - position 0: `vdd` (input, electrical)
    - position 1: `vss` (input, electrical)
    - position 2: `clk` (input, electrical)
    - position 3: `vinp` (input, electrical)
    - position 4: `vinn` (input, electrical)
    - position 5: `outp` (input, electrical)
    - position 6: `outn` (input, electrical)
    - position 7: `delay_ps` (output, electrical)
    - position 8: `overdrive_mv` (output, electrical)
    - position 9: `polarity` (output, electrical)
    - position 10: `valid` (output, electrical)

## Public Parameter Contract

- `comparator_delay_overdrive_meter.tr` defaults to `20p`; valid range: finite; overrides tr.


## Required Behavior

The repaired bundle must satisfy every public property:

- `P_CLOCK_ARMED_MEASUREMENT`: restore: Each rising `clk` threshold crossing stores the launch time, captures absolute differential overdrive, and arms exactly one pending measurement. Required traces: `time`, `clk`, `vinp`, `vinn`, `overdrive_mv`, `valid`.
- `P_DECISION_DELAY_CAPTURE`: restore: The first qualifying `outp` or `outn` decision edge while armed reports the elapsed clock-to-decision delay in `delay_ps`. Required traces: `time`, `clk`, `outp`, `outn`, `delay_ps`, `valid`.
- `P_ABSOLUTE_OVERDRIVE_METRIC`: restore: `overdrive_mv` reports the absolute input differential magnitude at launch time. Required traces: `time`, `clk`, `vinp`, `vinn`, `overdrive_mv`.
- `P_POLARITY_AND_VALID_FLAG`: restore: `polarity` reports the winning output decision direction and `valid` asserts only for a completed armed measurement. Required traces: `time`, `outp`, `outn`, `polarity`, `valid`.


The following canonical public behavior is normative for this derived form:

On each rising `clk` threshold crossing, store the current time and the absolute differential input overdrive. Arm one pending measurement. When either `outp` or `outn` rises through the decision threshold while armed, drive the voltage on `delay_ps` to the elapsed clock-to-output delay expressed in seconds and drive the voltage on `overdrive_mv` to the stored overdrive expressed in volts. The historical port suffixes name the human-facing diagnostic units; the evaluator converts these SI-valued electrical observables to picoseconds and millivolts. Set `polarity` high for an `outp` decision and low for an `outn` decision, assert `valid`, and disarm until the next clock edge. Hold reported values between measurements.


## Modeling Constraints

- Use deterministic voltage-domain behavioral Verilog-A.
- Do not hard-code validation stimulus, stop times, sample windows, gold internals, or simulator side channels.
- Preserve the exact file set, module graph, ports, parameters, and public traces.
- Do not add debug outputs, validation state, side channels, or stimulus-specific fixes.

## Output Contract

Return the repaired bundle with exactly these paths: `comparator_delay_overdrive_meter.va`.
Every supplied `.va` file is editable; do not add or omit files.
