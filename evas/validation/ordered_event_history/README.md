# Ordered event history independent validation

This fixed contract contains four original 1 ns timer cases and two separate 1 fs timer diagnostics. Both families use exact binary64 literal Fractions. A=Q(2e-6), B=Q(3e-6), C=Q(6e-6), STOP=Q(7e-6); 3A<2B, so the third A timer precedes the second B sample. They are not simultaneous. Nonlinear z is the reciprocal of one plus the integrated clock area; linear z is the clock area plus the exact PWL integral. Samples retain z(B), then z(2B).

Physical voltage tolerance is 1 µV for continuous state and retained samples; physical callback timing tolerance is 1 ns. Integer counts are exact. The checker separates finite records, scientific endpoint completeness and nearby-clock ordering. Decimal tokens that project to the numeric stop do not certify its exact rational value. Event counter reconstruction from EVAS records is an explicit observation adapter, not a physical exact-clock convention.

Copy `history_checker.py`, `spec_b_checker.py` and `calibrate.py` into a fresh ignored directory, then run `python3 -B calibrate.py` there. This preserves the retained calibration identity because the script writes `CALIBRATION.json` beside itself.

This executes 24 controls: 22 history controls and 2 controls guarding the unchanged E6 helper dependency. Accept, 2 µV fault, duplicate/delayed callback, missing/sparse observation, nonfinite and exact nearby-clock sample controls are included. Neither program source nor solver output is imported by the independent mathematical formula.

Each fixtures/<configuration> directory contains the same source, original Spectre deck and EVAS JSON manifest used in its frozen execution. Run Spectre with tb.scs as input from that fixture directory; compile.va includes the ordinary disciplines.vams and unchanged dut.va. Solver settings are explicit in each deck. Source and deck hashes are in the companion receipt. Original1ns sources must stay separate from 1 fs diagnostics.

EVAS replay requires a separately identified frontend and kernel. Read the fixture evas-manifest.json, compile dut.va with its module instance mapping, and transmit the listed physical sources, stop, max_step, output_times and original tolerances to that kernel. Record frontend/kernel hashes and retain actual request/response before using the result. Historical native-point replay used all numeric in-domain PSF points, excluded no such point, and extended no original numeric stop. A current rerun needs a new execution identity; this fixture set does not bundle an executable historical kernel.

To analyze a retained ASCII PSF from Python:

```python
from spec_b_checker import read_psf
from history_checker import inspect
rows = read_psf(psf_path)
result = inspect(rows, family, original_max_step)
```

The [comparison](../../../experiments/backends/ordered-event-history/README.md) contains compact actual evidence. Raw local-only archives are not included, so the retained receipts establish what was executed, not publicly retrievable historical waveforms.
