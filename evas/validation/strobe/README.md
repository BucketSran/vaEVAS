# Strobe control fixtures

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
