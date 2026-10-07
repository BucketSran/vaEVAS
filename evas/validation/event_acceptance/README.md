# Changed-event acceptance validation

Six development models check held timers, held thresholds, dynamic roots, sampled history and nonlinear deadline changes. Each model has base/fine maxstep settings, for a fixed denominator of twelve configurations. [Spec B](https://github.com/BucketSran/vaEVAS/issues/97) defines the equations; `checker.py` uses exact rational formulas and has no DUT imports. The source and inputs were frozen before the refactor. `cases/*/condition.json` records the mathematical and observation contracts.

The external limits are 1 µV for continuous outputs and 200 ns for event timing, with exact counts/order. These differ from backend solver settings. EVAS requests use vabstol=1e-8, reltol=0; the Spectre decks request reltol=1e-8, vabstol=1e-10, iabstol=1e-14, traponly. Base/fine maxstep is 0.02/0.002 s. The original Spectre source did not change; only output precision was derived, with both deck identities recorded.

For each configuration, use its `evas-manifest.json` with the documented EVAS CLI or run its `tb.scs` with Spectre. Save outputs in a fresh ignored directory and bind the selected kernel/tool identities. The complete recorded comparison is [here](../../../experiments/backends/event-acceptance/README.md).

```sh
python3 -B evas/validation/event_acceptance/checker.py E1 runs/example/evas.json --backend evas --stop 1 --maxstep .02 --output runs/example/check.json
```

The independent checker requires the exact scientific domain endpoints. It retains numeric failures, incomplete endpoints and exact-boundary observations separately. Native EVAS data does not automatically establish full compatibility; decimal Spectre export alone does not qualify its observation origin. No interpolation or nearest-point replacement supplies missing endpoints. E5's 1/3 is not representable in binary64.

`calibrate.py` executes 48 constructed positive/reject/incomplete controls and writes `CALIBRATION.json` beside itself. To avoid modifying the source tree, copy the two scripts into a fresh ignored output directory before calibration. The recorded checker is byte-identical to the frozen execution checker; raw backend waveforms remain local-only. These are development cases, not an unseen confirmation set or paper qualification.
