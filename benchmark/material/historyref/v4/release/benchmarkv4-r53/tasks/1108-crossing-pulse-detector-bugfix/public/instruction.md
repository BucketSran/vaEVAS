# Crossing Pulse Detector Bugfix

## Task Contract

The supplied Verilog-A system violates its public circuit contract. Repair the
complete editable bundle.

## Public Verilog-A Interface

Preserve this exact artifact and module interface:

- Artifact `source_crossing_pulse_detector.va`:
  - Module `source_crossing_pulse_detector` (entry)
    - position 0: `sigin` (input, electrical)
    - position 1: `sigout` (output, electrical)

## Public Parameter Contract

- `source_crossing_pulse_detector.pulse_width` defaults to `4e-09` s; valid range: pulse_width > 0; sets output high duration after each qualifying crossing.
- `source_crossing_pulse_detector.sigcrossing` defaults to `0.45` V; valid range: finite real; sets the bidirectional sigin detection threshold.
- `source_crossing_pulse_detector.vlogic_high` defaults to `0.9` V; valid range: finite real; sets the asserted output level.
- `source_crossing_pulse_detector.vlogic_low` defaults to `0.0` V; valid range: finite real; sets the deasserted output level.
- `source_crossing_pulse_detector.tdel` defaults to `1e-09` s; valid range: tdel >= 0; sets output transition delay.
- `source_crossing_pulse_detector.trise` defaults to `2e-11` s; valid range: trise > 0; sets sigout rise smoothing.
- `source_crossing_pulse_detector.tfall` defaults to `2e-11` s; valid range: tfall > 0; sets sigout fall smoothing.


## Required Behavior

The repaired bundle must satisfy every public property:

- `P_RISING_CROSS_PULSE`: restore: A rising sigin crossing through sigcrossing initiates a sigout pulse. Required traces: `time`, `sigin`, `sigout`.
- `P_FALLING_CROSS_PULSE`: restore: A falling sigin crossing through sigcrossing also initiates a sigout pulse. Required traces: `time`, `sigin`, `sigout`.
- `P_PULSE_WIDTH`: restore: After each qualifying crossing, the output target remains at vlogic_high for pulse_width before returning to vlogic_low. Required traces: `time`, `sigin`, `sigout`.
- `P_LOW_BETWEEN_EVENTS`: restore: Sigout returns to vlogic_low between sufficiently separated threshold crossings. Required traces: `time`, `sigin`, `sigout`.
- `P_REPEATABLE_BIDIRECTIONAL_EVENTS`: restore: Alternating rising and falling crossings each produce corresponding pulses rather than only the first event or one polarity. Required traces: `time`, `sigin`, `sigout`.
- `P_TRANSITION_TIMING`: restore: Sigout changes use tdel delay with trise and tfall smoothing. Required traces: `time`, `sigin`, `sigout`.


The following canonical public behavior is normative for this derived form:

This task asks for the `source_crossing_pulse_detector` behavioral DUT module,
not a testbench. The module emits a fixed-width pulse when `sigin`
crosses the configured threshold in either direction.

Support these public parameters and legal overrides:

| Parameter | Default | Unit / range | Contract |
| --- | ---: | --- | --- |
| `pulse_width` | `4 ns` | time, `(0:inf)` | Output high duration after a qualifying input crossing. |
| `sigcrossing` | `0.45` | V | Threshold for `sigin`. |
| `vlogic_high` | `0.9` | V | Output high level. |
| `vlogic_low` | `0.0` | V | Output low level. |
| `tdel` | `1 ns` | time, `[0:inf)` | Output transition delay. |
| `trise` | `20 ps` | time, `(0:inf)` | Output rise time. |
| `tfall` | `20 ps` | time, `(0:inf)` | Output fall time. |

Required observable behavior:

- Detect `sigin` crossings through `sigcrossing` in either direction.
- On each qualifying crossing, drive `sigout` high.
- Use a timer to return `sigout` low after `pulse_width`.
- Produce a pulse after each input crossing and return low between pulses.
- Drive `sigout` through smoothed voltage contributions.

Use voltage contributions only. Do not use current contributions, `ddt()`,
`idt()`, transistor-level devices, AC/noise analysis, validation logic, validation-only
test hooks, or simulator-specific side channels.


## Modeling Constraints

- Use bidirectional threshold crossing detection and timer-controlled pulse state.
- Drive sigout with a smoothed voltage contribution using the public timing parameters.
- Do not use current contributions, ddt(), idt(), transistor-level devices, AC/noise analysis, validation hooks, or simulator-specific side channels.
- Preserve the exact file set, module graph, ports, parameters, and public traces.
- Do not add debug outputs, validation state, side channels, or stimulus-specific fixes.

## Output Contract

Return the repaired bundle with exactly these paths: `source_crossing_pulse_detector.va`.
Every supplied `.va` file is editable; do not add or omit files.
