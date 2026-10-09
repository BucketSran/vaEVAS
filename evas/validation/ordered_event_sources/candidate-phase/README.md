# Independent physical query phase checks

This addendum retains the original 16 fixed-grid requests and adds a separate 16-request observation matrix. Both use the same frozen Verilog-A programs, input budgets and independent binary64-literal Fraction formulas. The original groups contain six normalized-original requests, four stricter-timer requests and six diagnostic requests. They remain separate evidence groups.

The extra queries are binary64 `0.3`, strictly before the physical timer sum `Q(0.1)+Q(0.2)`, and binary64 `0.3000000000000001`, strictly after every relevant physical root. `Q` converts a binary64 value to its exact Fraction. `calibrate.py` asserts these inequalities before checking actual query states or direct `y`. Event representatives do not determine the physical query phase. Exact-clock equality and unresolved root-window phases are outside these two proven probes.

Run the independent calibration from this directory:

```sh
python3 -B calibrate.py
```

It executes 33 transport/query-state controls (five transport controls, fourteen positive state controls and fourteen deliberately wrong state controls), plus six separately counted direct-output controls. It imports no simulator code and invokes no kernel. The two retained checkers are byte-identical frozen independent formulas; the diagnostic version adds the nocross family only.

`PLAN.json` and `PHASE_PLAN.json` map portable fixtures, complete wire requests and checker hashes. The wire payloads can be supplied on stdin to an EVAS kernel with the recorded identity. An accepted response uses stdout; a specific rejection uses actual structured stderr with a nonzero return code. Hidden-tight acceptance requires `event_resolution` and `cross_ttol_unrepresentable`, and excludes an accepted waveform. Other unexpected rejections fail requests that require finite output.

The frozen finite numeric checker deliberately omits `y` error within 1 ns of a jump. This limits its finite waveform conclusion. The separate phase checker compares actual `transient.states` and direct `y` at the two independently proven physical-phase probes, without that jump-window omission. It keeps mixed-source 0.1 µV and hidden-source 1 µV output budgets. Callback counts, bodies and source order are checked independently; matching event metadata cannot excuse wrong actual query states.

These fixtures retain the leading-zero normalization and manifest transport corrections documented in the earlier package. They do not turn the original Spectre compile failures, runtime crash or earlier numeric failures into passes. Bulk responses and kernel binaries remain local-only; compact receipt hashes are not a claim of publicly downloadable raw evidence.
