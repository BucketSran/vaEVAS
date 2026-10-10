# Strobe control fixtures

## Fixed timer history consumers

`timer_composition.py` reuses SEF-TIMER, SEF-INTERRUPT and SEF-ISOLATION without
changing their models or checker. All output records, including event boundaries,
retain the original 100 µV output, 10 nV input and ±5 ps event budgets.
The new STROBE-TIMER-IDT case checks changing sampled input followed by `idt`,
with a nonzero .05 V integral initial condition. Its independent answer is the
sum of held-value rectangle areas at nominal event times. It uses the same 100 µV output budget and the
precision pilot's input checks, 100 ps timer window and 2.1 ps counter brackets.
This extra case does not replace or relax the original 12 precision configurations.
Unlike the hold-value check, its nominal integral error includes the effect of
legal timer shifts. A permitted callback shift can therefore still fail this
total-error budget. The separate `--timer-diagnostic` freeze tightens only the
TT binding to 10 ps and 1 ps in the both profile, retaining source, stimulus,
observation grid and the original numerical checks. It never replaces the four
100 ps results. `timer_report.py` verifies these controlled differences.

The runner applies all four precision-pilot profiles to both EVAS and Spectre,
retains failures and reads back actual settings. EVAS requires exact requested
times with accepted-frame receipts. Spectre requested/native time coverage is
reported separately, including deviations beyond 16 ULP(stop). It is not an
additional engineering gate. All voltages are checked at their actual exported
times under the unchanged contract; no resampling supplies a missing strobe and
engineering passes do not prove exact Spectre forced-point identity.
Existing SEF cases use the dense contract grid; the new
integral uses the precision grid with both sides of every timer and source corner.
Ordinary waveform queries cannot satisfy the EVAS forced-point obligation.

Calibration rejects missing events, resets, a stale integral slope, incomplete
coverage and nonfinite outputs. Run `python3 -B -m unittest discover -s
evas/validation/strobe -v`. Execution and receipt tools live in
`experiments/backends/strobe/composition_run.py` and `timer_report.py`.

## Original control fixtures

Four small models exercise independent forced-solve controls. The committed VA,
Spectre decks and EVAS manifests share each model and stimulus. Each `case.json`
fixes requested times, analytic values and a 1e-6 V absolute comparison budget.
All exact native rows at a requested time are retained; missing times remain I.
No nearest-row replacement or interpolation supplies a missing observation.

- `static-irregular`: y=2t, explicit times .2 and .7.
- `continuous-periodic`: y=1-exp(-t), period .25 with delay .125.
- `implicit-irregular`: y=t solves z'=1+2y, z=y+y², z(0)=0.
- `timer-periodic`: count=floor(4t); stop=1 is reported as a separate event boundary.

The first actual Spectre 21.1.0.509.isr12 run produced all internal forced points.
The two irregular cases lack native t=0 rows. Those coverage obligations remain I.
The decks request reltol=1e-7; native logs report 1e-8 with conservative preset
and gear2only. This effective-setting difference is retained. Missing preparation
metadata also leaves the original generic settings readback I. This is a finite
strobe diagnostic, not an upgrade of the paper matrix or old strict C1/#79/VCO gates.

Raw runs and the frozen execution plan are retained in the visible integration
workspace under `runs/alignment-implementation-20261009/strobe/reference`.
Direct EVAS pairing and final runtime identity are recorded in the compact report
at `experiments/backends/strobe/` when completed. The raw dataset is local-only.
