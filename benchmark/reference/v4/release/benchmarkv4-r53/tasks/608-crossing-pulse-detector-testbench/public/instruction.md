# Crossing Pulse Detector Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Crossing Pulse Detector` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `source_crossing_pulse_detector.va`:
  - Module `source_crossing_pulse_detector` (entry)
    - position 0: `sigin` (input, electrical)
    - position 1: `sigout` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/source_crossing_pulse_detector.va`
- DUT instance: `XDUT (sigin sigout) source_crossing_pulse_detector`
- Required saved public traces: `sigin`, `sigout`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `source_crossing_pulse_detector.pulse_width` defaults to `4e-09` s; valid range: pulse_width > 0; sets output high duration after each qualifying crossing.
- `source_crossing_pulse_detector.sigcrossing` defaults to `0.45` V; valid range: finite real; sets the bidirectional sigin detection threshold.
- `source_crossing_pulse_detector.vlogic_high` defaults to `0.9` V; valid range: finite real; sets the asserted output level.
- `source_crossing_pulse_detector.vlogic_low` defaults to `0.0` V; valid range: finite real; sets the deasserted output level.
- `source_crossing_pulse_detector.tdel` defaults to `1e-09` s; valid range: tdel >= 0; sets output transition delay.
- `source_crossing_pulse_detector.trise` defaults to `2e-11` s; valid range: trise > 0; sets sigout rise smoothing.
- `source_crossing_pulse_detector.tfall` defaults to `2e-11` s; valid range: tfall > 0; sets sigout fall smoothing.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_RISING_CROSS_PULSE`: exercise and make observable: A rising sigin crossing through sigcrossing initiates a sigout pulse. Required traces: `time`, `sigin`, `sigout`.
- `P_FALLING_CROSS_PULSE`: exercise and make observable: A falling sigin crossing through sigcrossing also initiates a sigout pulse. Required traces: `time`, `sigin`, `sigout`.
- `P_PULSE_WIDTH`: exercise and make observable: After each qualifying crossing, the output target remains at vlogic_high for pulse_width before returning to vlogic_low. Required traces: `time`, `sigin`, `sigout`.
- `P_LOW_BETWEEN_EVENTS`: exercise and make observable: Sigout returns to vlogic_low between sufficiently separated threshold crossings. Required traces: `time`, `sigin`, `sigout`.
- `P_REPEATABLE_BIDIRECTIONAL_EVENTS`: exercise and make observable: Alternating rising and falling crossings each produce corresponding pulses rather than only the first event or one polarity. Required traces: `time`, `sigin`, `sigout`.
- `P_TRANSITION_TIMING`: exercise and make observable: Sigout changes use tdel delay with trise and tfall smoothing. Required traces: `time`, `sigin`, `sigout`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

The supplied DUT emits a fixed-width pulse when `sigin`
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


The required trace names are: `time`, `sigin`, `sigout`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
